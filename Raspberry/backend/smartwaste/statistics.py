import json
import uuid
from datetime import datetime, timedelta, timezone
from random import sample, randint
from typing import Literal
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from .models import Bin, Collection, UltrasonicMeasurement, Trip, User, now
from .security import db, current_user
from .company import route as base_route
from .services import bin_json, latest_categories
from .route_planner import plan
from .forecasts import suggestions, preventive_candidates
from .preventive_routing import preventive_plan

router = APIRouter(prefix='/api/v1/company')


def company_user(user=Depends(current_user)):
    if user.role != 'Company': raise HTTPException(403, 'Acces rezervat companiei.')
    return user


class RouteInput(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    consumption: float = Field(default=20, ge=1, le=100)


class FinishInput(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    actual_km: float | None = Field(default=None, ge=0, le=10000)


class TestRouteInput(RouteInput):
    stops: list[str] = Field(min_length=1, max_length=12)


class OptimizeInput(RouteInput):
    suggested_bin_ids: list[str] = Field(default_factory=list, max_length=12)
    automatic_preventive: bool = False


class SegmentInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    segment: int = Field(ge=0, le=12, strict=True)


def demo_bins(session, user):
    return select(Bin).where(Bin.company_id == user.id, Bin.demo.is_(True),
                             Bin.is_stolen.is_(False), Bin.is_damaged.is_(False))


def demo_reading(bin, category):
    return UltrasonicMeasurement(bin_id=bin.bin_id, fill_category=category,
        distance_mid_cm=4 if category >= 2 else 30,
        distance_full_cm=4 if category == 3 else 30,
        distance_top_cm={1: 30, 2: 8, 3: 4}[category], config_hash='test'.ljust(64, '0'))


@router.post('/test/scenario')
def test_scenario(user=Depends(company_user), session=Depends(db)):
    bins = list(session.scalars(demo_bins(session, user).order_by(Bin.bin_id).with_for_update()))
    if not bins:
        raise HTTPException(409, 'Compania nu are tomberoane demo disponibile.')
    located = [b.bin_id for b in bins if b.latitude is not None and b.longitude is not None]
    full = set(sample(located, min(len(located), randint(4, 12))))
    readings = [demo_reading(b, 3 if b.bin_id in full else randint(1, 2)) for b in bins]
    session.add_all(readings)
    session.flush()
    result = [bin_json(b, {}, reading) for b, reading in zip(bins, readings)]
    session.commit()
    return result


@router.post('/test/bins/{bin_id}/empty')
def empty_test_bin(bin_id: str, user=Depends(company_user), session=Depends(db)):
    bin = session.scalar(demo_bins(session, user).where(Bin.bin_id == bin_id).with_for_update())
    if bin is None:
        raise HTTPException(404, 'Tomberon demo indisponibil.')
    previous = latest_categories(session, [bin_id]).get(bin_id)
    if previous is None or previous.fill_category != 1:
        previous = demo_reading(bin, 1)
        session.add(previous)
        session.add(Collection(collection_id=uuid.uuid4(), bin_id=bin_id, confirmed_by=user.username))
        session.flush()
    result = bin_json(bin, {}, previous)
    session.commit()
    return result


@router.post('/test/route')
def test_route(body: TestRouteInput, user=Depends(company_user), session=Depends(db)):
    if user.hq_latitude is None or user.hq_longitude is None:
        raise HTTPException(409, 'Roagă administratorul să configureze sediul.')
    bins = list(session.scalars(demo_bins(session, user).where(Bin.bin_id.in_(body.stops))))
    latest = latest_categories(session, body.stops)
    if len(bins) != len(body.stops) or any(
        b.latitude is None or b.longitude is None or b.bin_id not in latest
        or latest[b.bin_id].fill_category != 3 for b in bins
    ):
        raise HTTPException(422, 'Selectează tomberoane demo pline, cu coordonate.')
    route = plan((user.hq_latitude, user.hq_longitude), [bin_json(b, {}, latest[b.bin_id]) for b in bins])
    result = {**route, 'id': str(uuid.uuid4()), 'hq_latitude': user.hq_latitude,
            'hq_longitude': user.hq_longitude, 'skipped_bin_ids': [], 'status': 'planned',
            'consumption': body.consumption,
            'estimated_fuel_liters': round(route['distance_meters'] / 100000 * body.consumption, 2)}
    snapshot = {bin.bin_id: latest[bin.bin_id].id for bin in bins}
    session.add(Trip(id=result['id'], company_id=user.id, demo=True,
                     route_json=json.dumps({**result, 'test_snapshot': snapshot}, default=str),
                     distance_meters=route['distance_meters'], consumption=body.consumption))
    session.commit()
    return result


@router.post('/test/routes/{id}/complete')
def complete_test_route(id: str, user=Depends(company_user), session=Depends(db)):
    trip = owned_trip(session, user, id)
    snapshot = json.loads(trip.route_json).get('test_snapshot')
    if not trip.demo or not snapshot:
        raise HTTPException(404, 'Rută de test inexistentă.')
    bins = list(session.scalars(demo_bins(session, user).where(Bin.bin_id.in_(snapshot))
                               .order_by(Bin.bin_id).with_for_update()))
    if len(bins) != len(snapshot):
        raise HTTPException(409, 'O oprire de test nu mai este disponibilă.')
    latest = latest_categories(session, list(snapshot))
    if trip.status != 'completed':
        if any(b.bin_id not in latest or latest[b.bin_id].id != snapshot[b.bin_id] for b in bins):
            raise HTTPException(409, 'Nivelurile s-au schimbat. Calculează din nou traseul de test.')
        for bin in bins:
            reading = demo_reading(bin, 1)
            session.add(reading)
            session.add(Collection(collection_id=uuid.uuid4(), bin_id=bin.bin_id, confirmed_by=user.username))
            latest[bin.bin_id] = reading
        trip.completed_at, trip.status, trip.planned_completion = now(), 'completed', True
        session.flush()
    result = [bin_json(bin, {}, latest[bin.bin_id]) for bin in bins]
    session.commit()
    return result


@router.get('/route/suggestions')
def route_suggestions(request: Request, user=Depends(company_user), session=Depends(db)):
    base = base_route(request, user, session)
    capacity = max(0, 12 - len(base['stops']))
    return {'capacity': capacity, 'bins': suggestions(session, user, base, now()) if capacity else []}


@router.post('/route/optimize')
def optimize(body: OptimizeInput, request: Request, user=Depends(company_user), session=Depends(db)):
    base = base_route(request, user, session)
    if body.suggested_bin_ids:
        available = {item['bin_id']: item for item in suggestions(session, user, base, now())}
        already_full = {stop['bin_id'] for stop in base['stops']}
        extra_ids = dict.fromkeys(id for id in body.suggested_bin_ids if id not in already_full)
        if any(id not in available for id in extra_ids):
            raise HTTPException(409, 'Propunerile s-au schimbat. Actualizează lista.')
        extra_bins = list(session.scalars(select(Bin).where(
            Bin.company_id == user.id, Bin.bin_id.in_(extra_ids),
            Bin.is_stolen.is_(False), Bin.is_damaged.is_(False))))
        if len(extra_bins) != len(extra_ids):
            raise HTTPException(409, 'O propunere nu mai este disponibilă.')
        latest = latest_categories(session, list(extra_ids))
        if any(b.bin_id not in latest or latest[b.bin_id].fill_category != 2 for b in extra_bins):
            raise HTTPException(409, 'Nivelurile s-au schimbat. Actualizează lista.')
        base['stops'].extend(bin_json(b, {}, latest[b.bin_id]) for b in extra_bins)
    if len(base['stops']) > 12:
        raise HTTPException(409, 'O rută poate avea cel mult 12 opriri.')
    if not base['stops']:
        raise HTTPException(409, 'Nu există tomberoane pline cu coordonate pentru colectare.')
    hq = (base['hq_latitude'], base['hq_longitude'])
    planned, automatic, status = None, [], 'no_candidates'
    capacity = min(4, 12 - len(base['stops']))
    if body.automatic_preventive and capacity and not body.suggested_bin_ids:
        candidates = preventive_candidates(session, user, base, now(), capacity)
        if candidates:
            planned, automatic, status = preventive_plan(hq, base['stops'], candidates, body.consumption)
    if planned is None:
        planned = plan(hq, base['stops'])
    result = {**base, **planned, 'id': str(uuid.uuid4()), 'consumption': body.consumption,
              'estimated_fuel_liters': round(planned['distance_meters'] / 100000 * body.consumption, 2), 'status': 'planned'}
    if body.automatic_preventive:
        result['preventive_status'] = status
        result['preventive_stops'] = automatic
    session.add(Trip(id=result['id'], company_id=user.id, route_json=json.dumps(result, default=str),
                     distance_meters=planned['distance_meters'], consumption=body.consumption))
    session.commit()
    return result


def owned_trip(session, user, id):
    item = session.scalar(select(Trip).where(Trip.id == id, Trip.company_id == user.id).with_for_update())
    if item is None: raise HTTPException(404, 'Rută inexistentă.')
    return item


@router.get('/routes')
def trips(user=Depends(company_user), session=Depends(db)):
    return [{**json.loads(t.route_json), 'status': t.status} for t in session.scalars(
        select(Trip).where(Trip.company_id == user.id, Trip.demo.is_(False)).order_by(Trip.created_at.desc()).limit(30))]


def resumable_route(session, company_id):
    trips = session.scalars(select(Trip).where(Trip.company_id == company_id, Trip.demo.is_(False),
        Trip.status == 'started').order_by(Trip.created_at.desc(), Trip.id.desc()))
    for trip in trips:
        route = json.loads(trip.route_json)
        if route.get('navigation_opened') is True:
            return {**route, 'id': trip.id, 'status': trip.status}
    return None


@router.get('/route/active')
def active_route(user=Depends(company_user), session=Depends(db)):
    return {'route': resumable_route(session, user.id)}


@router.post('/routes/{id}/segment')
def confirm_segment(id: str, body: SegmentInput, user=Depends(company_user), session=Depends(db)):
    item = owned_trip(session, user, id)
    if item.demo or item.status != 'started':
        raise HTTPException(409, 'Cursa nu mai este activă.')
    route = json.loads(item.route_json)
    completed = route.get('segments_done', 0)
    total = (len(route['stops']) + 4) // 4
    if body.segment > completed or body.segment >= total:
        raise HTTPException(409, 'Segmentul nu poate fi confirmat.')
    if body.segment == completed:
        route['segments_done'] = completed + 1
        item.route_json = json.dumps(route)
    session.commit()
    return {'segments_done': route.get('segments_done', 0)}


@router.post('/routes/{id}/discard')
def discard_route(id: str, user=Depends(company_user), session=Depends(db)):
    item = owned_trip(session, user, id)
    if item.demo or item.status == 'completed':
        raise HTTPException(409, 'Cursa nu poate fi abandonată.')
    route = json.loads(item.route_json)
    route['discarded'] = True
    item.route_json = json.dumps(route)
    item.status = 'planned'
    session.commit()
    return {'status': 'discarded'}


@router.post('/routes/{id}/start')
def start(id: str, navigation: Literal['prepare', 'opened'] | None = None,
          user=Depends(company_user), session=Depends(db)):
    session.execute(select(User.id).where(User.id == user.id).with_for_update())
    item = owned_trip(session, user, id)
    if item.demo: raise HTTPException(404, 'Rută inexistentă.')
    if item.status == 'completed': raise HTTPException(409, 'Ruta este deja finalizată.')
    route = json.loads(item.route_json)
    if route.get('discarded'):
        raise HTTPException(409, 'Cursa a fost abandonată.')
    active = resumable_route(session, user.id)
    if active and active['id'] != id:
        raise HTTPException(409, 'Există deja o cursă activă. Actualizează și continuă cursa.')
    stop_ids = {stop['bin_id'] for stop in route['stops']}
    eligible = set(session.scalars(select(Bin.bin_id).where(
        Bin.bin_id.in_(stop_ids), Bin.company_id == user.id,
        Bin.is_stolen.is_(False), Bin.is_damaged.is_(False))))
    if stop_ids != eligible:
        raise HTTPException(409, 'O oprire nu mai este disponibilă. Calculează din nou ruta.')
    if navigation == 'prepare':
        return {'status': item.status}
    if navigation == 'opened':
        route['navigation_opened'] = True
        item.route_json = json.dumps(route)
    item.status = 'started'
    session.commit()
    return {'status': item.status}


@router.post('/routes/{id}/complete')
def complete(id: str, body: FinishInput, include_bins: bool = False, user=Depends(company_user), session=Depends(db)):
    item = owned_trip(session, user, id)
    if item.demo: raise HTTPException(404, 'Rută inexistentă.')
    already_completed = item.status == 'completed'
    if already_completed:
        if body.actual_km is not None and item.actual_km != body.actual_km: raise HTTPException(409, 'Ruta a fost deja finalizată cu alt kilometraj.')
        if not include_bins:
            return {'status': item.status}
    elif item.status != 'started':
        raise HTTPException(409, 'Pornește ruta înainte de finalizare.')

    stop_ids = [stop['bin_id'] for stop in json.loads(item.route_json)['stops']]
    bins = list(session.scalars(demo_bins(session, user).where(Bin.bin_id.in_(stop_ids))
                               .order_by(Bin.bin_id).with_for_update()))
    latest = latest_categories(session, [bin.bin_id for bin in bins])
    if not already_completed:
        for bin in bins:
            previous = latest.get(bin.bin_id)
            if previous is not None and previous.fill_category == 1:
                continue
            reading = demo_reading(bin, 1)
            if previous is not None:
                reading.battery = previous.battery
            session.add(reading)
            session.add(Collection(collection_id=uuid.uuid4(), bin_id=bin.bin_id, confirmed_by=user.username))
            latest[bin.bin_id] = reading
        item.planned_completion = body.actual_km is None
        item.actual_km, item.completed_at, item.status = body.actual_km, now(), 'completed'
        session.flush()
    # Keep the status-only response for older APKs.
    result = {'status': item.status}
    if include_bins:
        result['bins'] = [bin_json(bin, {}, latest[bin.bin_id]) for bin in bins if bin.bin_id in latest]
    session.commit()
    return result


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@router.get('/statistics')
def statistics(user=Depends(company_user), session=Depends(db)):
    today = datetime.now(ZoneInfo('Europe/Bucharest')).replace(hour=0, minute=0, second=0, microsecond=0)
    boundaries = {'day': today, 'week': today - timedelta(days=today.weekday()), 'month': today.replace(day=1)}
    start_history = (today - timedelta(days=90)).astimezone(timezone.utc)
    bins = list(session.scalars(select(Bin).where(Bin.company_id == user.id).order_by(Bin.bin_id)))
    ids = [b.bin_id for b in bins]
    # confirmed_by anchors historical collection ownership, not just today's bin assignment.
    events = list(session.scalars(select(Collection).where(Collection.confirmed_by == user.username,
        Collection.collected_at >= start_history).order_by(Collection.collected_at)))
    trips = list(session.scalars(select(Trip).where(Trip.company_id == user.id, Trip.status == 'completed', Trip.completed_at >= start_history)))
    periods = []
    for key, start in boundaries.items():
        since = start.astimezone(timezone.utc)
        selected = [t for t in trips if utc(t.completed_at) >= since]
        periods.append({'period': key, 'collections': sum(utc(e.collected_at) >= since for e in events),
            'completed_routes': len(selected), 'reported_km': round(sum(t.actual_km or 0 for t in selected), 2),
            'planned_km': round(sum(t.distance_meters / 1000 for t in selected if t.planned_completion), 2),
            'estimated_fuel_liters': round(sum((t.distance_meters / 1000 if t.planned_completion else (t.actual_km or 0)) * t.consumption / 100 for t in selected), 2)})
    # Include the previous state before the window to count transitions rather than repeated full readings.
    measurements = list(session.scalars(select(UltrasonicMeasurement).where(UltrasonicMeasurement.bin_id.in_(ids),
        UltrasonicMeasurement.classification_confirmed.is_(True),
        UltrasonicMeasurement.recorded_at >= start_history).order_by(UltrasonicMeasurement.recorded_at, UltrasonicMeasurement.id)))
    previous = {}
    for id in ids:
        old = session.scalar(select(UltrasonicMeasurement).where(UltrasonicMeasurement.bin_id == id,
            UltrasonicMeasurement.classification_confirmed.is_(True),
            UltrasonicMeasurement.recorded_at < start_history).order_by(UltrasonicMeasurement.recorded_at.desc(), UltrasonicMeasurement.id.desc()).limit(1))
        previous[id] = old.fill_category if old else None
    full_counts = {id: 0 for id in ids}
    observed = {m.bin_id for m in measurements}
    for m in measurements:
        if m.fill_category == 3 and previous[m.bin_id] in (1, 2): full_counts[m.bin_id] += 1
        previous[m.bin_id] = m.fill_category
    details = []
    for b in bins:
        times = [utc(e.collected_at) for e in events if e.bin_id == b.bin_id]
        intervals = [(b-a).total_seconds()/3600 for a, b in zip(times, times[1:])]
        details.append({'bin_id': b.bin_id, 'name': b.name, 'demo': b.demo, 'collections': len(times),
            'full_events': full_counts[b.bin_id], 'has_measurements': b.bin_id in observed,
            'average_collection_hours': round(sum(intervals)/len(intervals), 1) if intervals else None,
            'last_collection': times[-1].isoformat() if times else None})
    daily = [{'date': (today-timedelta(days=d)).date().isoformat(),
        'collections': sum(utc(e.collected_at).astimezone(ZoneInfo('Europe/Bucharest')).date() == (today-timedelta(days=d)).date() for e in events)} for d in range(13, -1, -1)]
    return {'periods': periods, 'bins': sorted(details, key=lambda b: (-b['full_events'], b['bin_id'])), 'daily': daily,
        'history_days': 90, 'has_demo_data': any(b.demo for b in bins) or any(t.demo for t in trips)}
