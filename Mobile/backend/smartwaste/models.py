from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, Boolean, Float, ForeignKey, DateTime, CheckConstraint, Index, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = 'sw_users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    display_name: Mapped[str] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    demo: Mapped[bool] = mapped_column(Boolean, default=False)
    hq_latitude: Mapped[float | None] = mapped_column(Float)
    hq_longitude: Mapped[float | None] = mapped_column(Float)
    __table_args__ = (
        CheckConstraint("role IN ('Resident','Company','Admin')"),
        CheckConstraint("(hq_latitude IS NULL AND hq_longitude IS NULL) OR "
                        "(role = 'Company' AND hq_latitude IS NOT NULL AND hq_longitude IS NOT NULL "
                        "AND hq_latitude BETWEEN -90 AND 90 AND hq_longitude BETWEEN -180 AND 180)",
                        name='sw_hq_coordinates'),
        Index('sw_single_admin', 'role', unique=True,
              postgresql_where=text("role = 'Admin'"), sqlite_where=text("role = 'Admin'")),
    )


class Session(Base):
    __tablename__ = 'sw_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('sw_users.id'), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Bin(Base):
    __tablename__ = 'bins'
    bin_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    company_id: Mapped[int | None] = mapped_column(ForeignKey('sw_users.id'))
    demo: Mapped[bool] = mapped_column(Boolean, default=False)
    is_stolen: Mapped[bool] = mapped_column(Boolean, default=False)
    is_damaged: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (
        CheckConstraint('latitude IS NULL OR latitude BETWEEN -90 AND 90'),
        CheckConstraint('longitude IS NULL OR longitude BETWEEN -180 AND 180'),
        CheckConstraint('(latitude IS NULL) = (longitude IS NULL)'),
    )


class Assignment(Base):
    __tablename__ = 'sw_resident_bins'
    user_id: Mapped[int] = mapped_column(ForeignKey('sw_users.id'), primary_key=True)
    bin_id: Mapped[str] = mapped_column(ForeignKey('bins.bin_id'), primary_key=True)


class Incident(Base):
    __tablename__ = 'sw_incidents'
    id: Mapped[int] = mapped_column(primary_key=True)
    bin_id: Mapped[str] = mapped_column(ForeignKey('bins.bin_id'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('sw_users.id'))
    category: Mapped[str] = mapped_column(String(40))
    comment: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(20), default='open')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    proof_nonce: Mapped[str | None] = mapped_column(String(64))
    proof_hash: Mapped[str | None] = mapped_column(String(64))
    solana_signature: Mapped[str | None] = mapped_column(String(100))
    proof_transaction: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(36))
    blockchain_status: Mapped[str] = mapped_column(String(30), default='prepared')
    blockchain_error: Mapped[str | None] = mapped_column(String(60))
    __table_args__ = (CheckConstraint("status IN ('open','in_progress','resolved')"),
                      UniqueConstraint('user_id', 'request_id', name='sw_incident_request_unique'))


class UltrasonicMeasurement(Base):
    __tablename__ = 'sw_ultrasonic_measurements'
    id: Mapped[int] = mapped_column(primary_key=True)
    bin_id: Mapped[str] = mapped_column(ForeignKey('bins.bin_id'))
    fill_category: Mapped[int] = mapped_column(Integer)
    distance_mid_cm: Mapped[float] = mapped_column(Float)
    distance_full_cm: Mapped[float] = mapped_column(Float)
    distance_top_cm: Mapped[float] = mapped_column(Float)
    battery: Mapped[int | None] = mapped_column(Integer)
    config_hash: Mapped[str] = mapped_column(String(64))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        CheckConstraint('fill_category BETWEEN 1 AND 3'),
        CheckConstraint('distance_mid_cm > 0 AND distance_full_cm > 0 AND distance_top_cm > 0'),
        CheckConstraint('battery IS NULL OR battery BETWEEN 0 AND 100'),
        Index('ix_sw_ultrasonic_bin_time', 'bin_id', 'recorded_at', 'id'),
    )


class Collection(Base):
    __tablename__ = 'collections'
    collection_id: Mapped[object] = mapped_column(Uuid, primary_key=True)
    bin_id: Mapped[str] = mapped_column(ForeignKey('bins.bin_id'))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    confirmed_by: Mapped[str] = mapped_column(Text)


class Trip(Base):
    __tablename__ = 'sw_trips'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('sw_users.id'), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default='planned')
    route_json: Mapped[str] = mapped_column(Text)
    distance_meters: Mapped[float] = mapped_column(Float)
    consumption: Mapped[float] = mapped_column(Float)
    planned_completion: Mapped[bool] = mapped_column(Boolean, default=False)
    actual_km: Mapped[float | None] = mapped_column(Float)
    demo: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (CheckConstraint("status IN ('planned','started','completed')"),
        CheckConstraint('distance_meters >= 0 AND consumption BETWEEN 1 AND 100'),
        CheckConstraint('actual_km IS NULL OR actual_km >= 0'))
