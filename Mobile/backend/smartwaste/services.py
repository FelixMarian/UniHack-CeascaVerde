from fastapi import HTTPException
from sqlalchemy import select
from .models import Bin, Assignment, User


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


def bin_json(bin, measurements):
    reading = measurements.get(bin.bin_id, {})
    return {**{k: getattr(bin, k) for k in ('bin_id', 'name', 'latitude', 'longitude', 'company_id', 'demo')},
            'fill_level': reading.get('fill_level'), 'recorded_at': reading.get('recorded_at'),
            'battery': reading.get('battery')}
