-- Keep legacy percentages untouched. Categories are 1=empty, 2=medium, 3=full.
BEGIN;
SELECT pg_advisory_xact_lock(2026111301);
CREATE TABLE IF NOT EXISTS sw_ultrasonic_measurements (
    id SERIAL PRIMARY KEY,
    bin_id TEXT NOT NULL REFERENCES bins(bin_id),
    fill_category INTEGER NOT NULL CHECK (fill_category BETWEEN 1 AND 3),
    distance_mid_cm DOUBLE PRECISION NOT NULL CHECK (distance_mid_cm > 0),
    distance_full_cm DOUBLE PRECISION NOT NULL CHECK (distance_full_cm > 0),
    distance_top_cm DOUBLE PRECISION NOT NULL CHECK (distance_top_cm > 0),
    battery INTEGER CHECK (battery BETWEEN 0 AND 100),
    config_hash VARCHAR(64) NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS ix_sw_ultrasonic_bin_time
    ON sw_ultrasonic_measurements(bin_id, recorded_at DESC, id DESC);
COMMIT;
