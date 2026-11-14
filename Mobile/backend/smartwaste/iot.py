"""Change-only LoRa ingestion; the original /readings contract stays intact."""
import secrets
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from sqlalchemy import select, text
from .models import Bin
from .security import db

router = APIRouter(prefix='/iot', tags=['IoT'])


class LoRaReading(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    bin_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,80}$')
    latitude: float = Field(ge=-90, le=90, strict=True)
    longitude: float = Field(ge=-180, le=180, strict=True)
    fill_level: StrictInt = Field(ge=0, le=100)
    battery: StrictInt | None = Field(default=None, ge=0, le=100)


def device(request: Request, x_api_key: str = Header(default='')):
    if not secrets.compare_digest(x_api_key.encode(), request.app.state.sw_device_key.encode()):
        raise HTTPException(401, 'Invalid API key')


@router.post('/readings', dependencies=[Depends(device)])
def ingest(body: LoRaReading, session=Depends(db)):
    # All callers of this route serialize per bin, including multiple server workers.
    bin = session.scalar(select(Bin).where(Bin.bin_id == body.bin_id).with_for_update())
    if bin is None:
        raise HTTPException(404, 'Bin not registered. Creează tomberonul în Admin folosind același ID.')
    previous = session.execute(text('''
        SELECT fill_level, battery FROM bin_measurements
        WHERE bin_id = :bin_id ORDER BY recorded_at DESC LIMIT 1
    '''), {'bin_id': body.bin_id}).mappings().first()
    # Omitted/unknown battery must not erase a previously known value.
    battery = body.battery if body.battery is not None else (previous['battery'] if previous else None)
    measurement_changed = previous is None or previous['fill_level'] != body.fill_level or previous['battery'] != battery
    coordinates_changed = bin.latitude != body.latitude or bin.longitude != body.longitude
    if coordinates_changed:
        bin.latitude, bin.longitude = body.latitude, body.longitude
    if measurement_changed:
        # Use wall-clock insertion time AFTER acquiring the row lock. PostgreSQL's
        # default now() is the transaction start time and can predate a lock wait.
        session.execute(text('''
            INSERT INTO bin_measurements(bin_id, fill_level, battery, recorded_at)
            VALUES (:bin_id, :fill_level, :battery, clock_timestamp())
        '''), {'bin_id': body.bin_id, 'fill_level': body.fill_level, 'battery': battery})
    session.commit()
    changed = coordinates_changed or measurement_changed
    return {'bin_id': body.bin_id, 'changed': changed,
            'measurement_saved': measurement_changed, 'coordinates_updated': coordinates_changed,
            'reason': 'updated' if changed else 'unchanged'}
