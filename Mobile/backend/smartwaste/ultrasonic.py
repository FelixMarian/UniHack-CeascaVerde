import os
from uuid import uuid4
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from sqlalchemy import select, func
from .iot import device
from .models import Bin, Collection, UltrasonicMeasurement, User
from .security import db
from .ultrasonic_classifier import parse_thresholds, classify, CalibrationError, SensorError

router = APIRouter(prefix='/iot', tags=['IoT'])
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / 'config/ultrasonic_thresholds.h'


class UltrasonicReading(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    bin_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,80}$')
    latitude: float = Field(ge=-90, le=90, strict=True)
    longitude: float = Field(ge=-180, le=180, strict=True)
    distance_mid_cm: float = Field(strict=True)
    distance_full_cm: float = Field(gt=0, strict=True)
    distance_top_cm: float = Field(gt=0, strict=True)
    battery: StrictInt | None = Field(default=None, ge=0, le=100)


@router.post('/ultrasonic-readings', dependencies=[Depends(device)])
def ingest(body: UltrasonicReading, session=Depends(db)):
    try:
        config_path = Path(os.getenv('SMARTWASTE_ULTRASONIC_CONFIG', str(DEFAULT_CONFIG)))
        thresholds = parse_thresholds(config_path.read_text(encoding='utf-8'))
    except (OSError, CalibrationError) as exc:
        detail = str(exc) if isinstance(exc, CalibrationError) else 'Fișierul de calibrare nu poate fi citit.'
        raise HTTPException(503, detail) from None
    mid = None if body.distance_mid_cm == -1 else body.distance_mid_cm
    try:
        result = classify(mid, body.distance_full_cm, body.distance_top_cm, thresholds)
    except SensorError as exc:
        raise HTTPException(422, str(exc)) from None
    bin = session.scalar(select(Bin).where(Bin.bin_id == body.bin_id).with_for_update())
    if bin is None:
        raise HTTPException(404, 'Bin not registered. Creează tomberonul în Admin folosind același ID.')
    history = select(UltrasonicMeasurement).where(UltrasonicMeasurement.bin_id == body.bin_id)
    latest = history.order_by(UltrasonicMeasurement.recorded_at.desc(), UltrasonicMeasurement.id.desc())
    previous = session.scalar(latest.limit(1))
    category = result.category
    battery = body.battery if body.battery is not None else (previous.battery if previous else None)
    state_changed = (previous is None or previous.fill_category != category or
                     previous.classification_confirmed != result.confirmed or previous.battery != battery or
                     (previous.distance_mid_cm is None) != (mid is None))
    previous_confirmed = previous
    if result.confirmed and category == 1 and previous and not previous.classification_confirmed:
        previous_confirmed = session.scalar(latest.where(UltrasonicMeasurement.classification_confirmed.is_(True)).limit(1))
    coordinates_changed = bin.latitude != body.latitude or bin.longitude != body.longitude
    if coordinates_changed:
        bin.latitude, bin.longitude = body.latitude, body.longitude
    if state_changed:
        session.add(UltrasonicMeasurement(bin_id=body.bin_id, fill_category=category, classification_confirmed=result.confirmed,
            distance_mid_cm=mid, distance_full_cm=body.distance_full_cm,
            distance_top_cm=body.distance_top_cm, battery=battery, config_hash=thresholds.fingerprint,
            recorded_at=func.clock_timestamp()))
    if result.confirmed and category == 1 and previous_confirmed and previous_confirmed.fill_category in (2, 3) and not (
            bin.demo or bin.is_stolen or bin.is_damaged) and bin.company_id is not None:
        company = session.get(User, bin.company_id)
        if company and company.role == 'Company':
            session.add(Collection(collection_id=uuid4(), bin_id=bin.bin_id,
                                   confirmed_by=company.username, collected_at=func.clock_timestamp()))
    session.commit()
    return {'bin_id':body.bin_id, 'fill_category':category,
            'previous_category': previous.fill_category if previous else None,
            'category_label':{1:'gol',2:'mediu',3:'plin'}[category], 'classification_confirmed':result.confirmed,
            'changed':state_changed or coordinates_changed, 'measurement_saved':state_changed,
            'coordinates_updated':coordinates_changed, 'reason':'updated' if state_changed or coordinates_changed else 'unchanged'}
