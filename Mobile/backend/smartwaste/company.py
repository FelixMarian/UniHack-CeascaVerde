"""Company operations. Routes are visit ordering, not street navigation."""
from math import radians, sin, cos, atan2, sqrt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .security import current_user, db, public_user
from .models import User
from .services import owned_bin, visible_bins, latest_categories, bin_json

router = APIRouter(prefix='/api/v1')


class HQInput(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode='after')
    def pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError('Completează ambele coordonate HQ.')
        return self


class DamageInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    damaged: bool = Field(strict=True)


@router.put('/companies/{company_id}/hq')
def headquarters(company_id: int, body: HQInput, user=Depends(current_user), session=Depends(db)):
    if user.role != 'Admin' and not (user.role == 'Company' and user.id == company_id):
        raise HTTPException(403, 'Nu poți modifica sediul acestei companii.')
    account = session.get(User, company_id)
    if not account or account.role != 'Company':
        raise HTTPException(404, 'Companie inexistentă.')
    account.hq_latitude, account.hq_longitude = body.latitude, body.longitude
    session.commit()
    return public_user(account)


@router.patch('/bins/{bin_id}/damage')
def damage(bin_id: str, body: DamageInput, user=Depends(current_user), session=Depends(db)):
    if user.role != 'Company':
        raise HTTPException(403, 'Doar compania responsabilă gestionează deteriorarea.')
    item = owned_bin(session, user, bin_id)
    item.is_damaged = body.damaged
    session.commit()
    return {'bin_id': bin_id, 'is_damaged': item.is_damaged}


def distance(a, b):
    lat1, lat2 = radians(a[0]), radians(b[0])
    dlat, dlon = lat2 - lat1, radians(b[1] - a[1])
    h = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    return 6371000 * 2 * atan2(sqrt(min(1, h)), sqrt(max(0, 1-h)))


def order_stops(origin, bins):
    remaining, ordered, total, point = list(bins), [], 0.0, origin
    while remaining:
        nearest = min(remaining, key=lambda b: (distance(point, (b['latitude'], b['longitude'])), b['bin_id']))
        target = (nearest['latitude'], nearest['longitude'])
        total += distance(point, target)
        ordered.append(nearest)
        remaining.remove(nearest)
        point = target
    if ordered:
        total += distance(point, origin)
    return ordered, round(total)


@router.post('/company/route')
def route(request: Request, user=Depends(current_user), session=Depends(db)):
    if user.role != 'Company':
        raise HTTPException(403, 'Funcție disponibilă companiilor.')
    if user.hq_latitude is None or user.hq_longitude is None:
        raise HTTPException(409, 'Configurează mai întâi coordonatele HQ.')
    rows = session.scalars(visible_bins(session, user)).all()
    categories = latest_categories(session, [b.bin_id for b in rows])
    legacy = request.app.state.sw_legacy.readings() if any(b.bin_id not in categories for b in rows) else {}
    items = [bin_json(b, legacy, categories.get(b.bin_id)) for b in rows]
    full = [b for b in items if b['fill_category'] == 3 or
            (b['fill_category'] is None and b['fill_level'] is not None and b['fill_level'] >= 80)]
    located = [b for b in full if b['latitude'] is not None and b['longitude'] is not None]
    stops, meters = order_stops((user.hq_latitude, user.hq_longitude), located)
    return {'hq_latitude': user.hq_latitude, 'hq_longitude': user.hq_longitude,
            'stops': stops, 'straight_line_meters': meters,
            'skipped_bin_ids': [b['bin_id'] for b in full if b not in located]}
