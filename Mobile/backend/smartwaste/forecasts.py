"""Estimate the remaining time in a Medium → Full cycle from observed transitions."""
from datetime import timedelta, timezone
from statistics import mean, median

from sqlalchemy import select

from .company import distance
from .models import Bin, Collection, UltrasonicMeasurement


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def estimate(readings, current_time):
    previous = None
    medium_since = None
    durations = []
    for reading in readings:
        category, timestamp = reading.fill_category, utc(reading.recorded_at)
        if timestamp > current_time or category == previous:
            continue
        if category == 3 and previous == 2 and medium_since is not None:
            hours = (timestamp - medium_since).total_seconds() / 3600
            if 0 < hours <= 168:
                durations.append(hours)
        if category == 2:
            medium_since = timestamp if previous == 1 else None
        previous = category

    if previous != 2 or medium_since is None or len(durations) < 3:
        return None
    elapsed = (current_time - medium_since).total_seconds() / 3600
    typical = median(durations)
    # An overdue estimate with no new transition is too uncertain to recommend.
    if elapsed > typical or typical - elapsed > 24:
        return None
    return round(typical - elapsed, 1), len(durations)


def suggestions(session, user, base, current_time):
    # Use real sensor history. Synthetic scenarios have their own planning workflow.
    bins = list(session.scalars(select(Bin).where(
        Bin.company_id == user.id, Bin.demo.is_(False),
        Bin.is_damaged.is_(False), Bin.is_stolen.is_(False),
        Bin.latitude.is_not(None), Bin.longitude.is_not(None))))
    history = {bin.bin_id: [] for bin in bins}
    readings = session.scalars(select(UltrasonicMeasurement).where(
        UltrasonicMeasurement.bin_id.in_(history),
        UltrasonicMeasurement.classification_confirmed.is_(True),
        UltrasonicMeasurement.recorded_at >= current_time - timedelta(days=90),
        UltrasonicMeasurement.recorded_at <= current_time,
    ).order_by(UltrasonicMeasurement.recorded_at, UltrasonicMeasurement.id))
    for reading in readings:
        history[reading.bin_id].append(reading)
    points = [(base['hq_latitude'], base['hq_longitude'])]
    points.extend((stop['latitude'], stop['longitude']) for stop in base['stops'])
    selected = {stop['bin_id'] for stop in base['stops']}
    result = []
    for bin in bins:
        if bin.bin_id in selected:
            continue
        near = min(distance((bin.latitude, bin.longitude), point) for point in points)
        prediction = estimate(history[bin.bin_id], current_time) if near <= 1500 else None
        if prediction is not None:
            hours, cycles = prediction
            result.append({'bin_id': bin.bin_id, 'name': bin.name, 'latitude': bin.latitude,
                           'longitude': bin.longitude, 'hours_to_full': hours,
                           'cycles': cycles, 'nearby_meters': round(near)})
    return sorted(result, key=lambda item: (item['hours_to_full'], item['nearby_meters'], item['bin_id']))


def preventive_candidates(session, user, base, current_time, limit):
    """Pair each observed full transition with its preceding collection."""
    stop_ids = {stop['bin_id'] for stop in base['stops']}
    rows = list(session.scalars(select(Bin).where(
        Bin.company_id == user.id, Bin.demo.is_(False), Bin.is_damaged.is_(False),
        Bin.is_stolen.is_(False), Bin.latitude.is_not(None), Bin.longitude.is_not(None))))
    cutoff = current_time - timedelta(days=90)
    history = {bin.bin_id: [] for bin in rows if bin.bin_id not in stop_ids}
    collections = {id: [] for id in history}
    for id, timestamp in session.execute(select(Collection.bin_id, Collection.collected_at).where(
        Collection.bin_id.in_(history), Collection.collected_at.between(cutoff, current_time)
    ).order_by(Collection.collected_at)):
        collections[id].append(utc(timestamp))
    for reading in session.scalars(select(UltrasonicMeasurement).where(
        UltrasonicMeasurement.bin_id.in_(history), UltrasonicMeasurement.classification_confirmed.is_(True),
        UltrasonicMeasurement.recorded_at.between(cutoff, current_time)
    ).order_by(UltrasonicMeasurement.recorded_at, UltrasonicMeasurement.id)):
        history[reading.bin_id].append(reading)
    points = [(base['hq_latitude'], base['hq_longitude'])]
    points.extend((stop['latitude'], stop['longitude']) for stop in base['stops'])
    result = []
    for bin in rows:
        if bin.bin_id not in history:
            continue
        readings, emptied = history[bin.bin_id], collections[bin.bin_id]
        if not readings or not emptied or readings[-1].fill_category != 2:
            continue
        if utc(readings[-1].recorded_at) <= emptied[-1]:
            continue
        durations = []
        next_empty = 0
        paired = -1
        previous = None
        for reading in readings:
            timestamp = utc(reading.recorded_at)
            while next_empty < len(emptied) and emptied[next_empty] < timestamp:
                next_empty += 1
            cycle = next_empty - 1
            if cycle >= 0 and cycle != paired and reading.fill_category == 3 and previous in (1, 2):
                hours = (timestamp - emptied[cycle]).total_seconds() / 3600
                if 0 < hours <= 336:
                    durations.append(hours)
                paired = cycle
            previous = reading.fill_category
        if len(durations) < 3:
            continue
        typical = mean(durations)
        age = (current_time - emptied[-1]).total_seconds() / 3600
        remaining = typical - age
        nearby = min(distance((bin.latitude, bin.longitude), point) for point in points)
        if nearby <= 1500 and -24 <= remaining <= 24:
            result.append({
                'bin_id': bin.bin_id, 'name': bin.name, 'latitude': bin.latitude,
                'longitude': bin.longitude, 'company_id': bin.company_id, 'demo': False,
                'fill_category': 2, 'fill_level': None, 'battery': readings[-1].battery,
                'recorded_at': utc(readings[-1].recorded_at).isoformat(),
                'average_fill_hours': round(typical, 1), 'hours_since_empty': round(age, 1),
                'hours_to_full': round(max(0, remaining), 1), 'cycles': len(durations),
                'nearby_meters': round(nearby),
            })
    return sorted(result, key=lambda item: (item['hours_to_full'], item['nearby_meters'], item['bin_id']))[:limit]
