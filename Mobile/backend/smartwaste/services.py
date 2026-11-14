from fastapi import HTTPException
from sqlalchemy import select, func
from .models import Bin, Assignment, User, UltrasonicMeasurement


def visible_bins(session, user):
    query = select(Bin)
    if user.role == 'Resident':
        query = query.join(Assignment).where(Assignment.user_id == user.id)
    elif user.role == 'Company':
        query = query.where(Bin.company_id == user.id)
    return query.order_by(Bin.bin_id)


def owned_bin(session, user, bin_id):
    result = session.scalar(visible_bins(session, user).where(Bin.bin_id == bin_id))
    if not result:
        raise HTTPException(404, 'Tomberon inexistent sau neasignat.')
    return result


def company(session, company_id):
    if company_id is not None:
        account = session.get(User, company_id)
        if not account or account.role != 'Company' or not account.active:
            raise HTTPException(422, 'Selectează o companie activă.')


def latest_categories(session, bin_ids):
    if not bin_ids:
        return {}
    ranked = select(UltrasonicMeasurement.id,
        func.row_number().over(partition_by=UltrasonicMeasurement.bin_id,
            order_by=(UltrasonicMeasurement.recorded_at.desc(), UltrasonicMeasurement.id.desc())).label('rank'))\
        .where(UltrasonicMeasurement.bin_id.in_(bin_ids)).subquery()
    rows = session.scalars(select(UltrasonicMeasurement).join(ranked, ranked.c.id == UltrasonicMeasurement.id)
        .where(ranked.c.rank == 1)).all()
    return {row.bin_id: row for row in rows}


def bin_json(bin, measurements, ultrasonic=None):
    reading = measurements.get(bin.bin_id, {})
    return {**{k: getattr(bin, k) for k in ('bin_id', 'name', 'latitude', 'longitude', 'company_id', 'demo')},
            'fill_level': None if ultrasonic else reading.get('fill_level'),
            'fill_category': 4 if bin.is_damaged else ultrasonic.fill_category if ultrasonic else None,
            'recorded_at': ultrasonic.recorded_at if ultrasonic else reading.get('recorded_at'),
            'battery': ultrasonic.battery if ultrasonic else reading.get('battery')}
