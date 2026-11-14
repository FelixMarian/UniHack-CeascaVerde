ALTER TABLE sw_incidents ADD COLUMN IF NOT EXISTS request_id VARCHAR(36);
ALTER TABLE sw_incidents ADD COLUMN IF NOT EXISTS blockchain_status VARCHAR(30) NOT NULL DEFAULT 'prepared';
ALTER TABLE sw_incidents ADD COLUMN IF NOT EXISTS blockchain_error VARCHAR(60);
CREATE UNIQUE INDEX IF NOT EXISTS sw_incident_request_unique ON sw_incidents(user_id, request_id);
CREATE TABLE IF NOT EXISTS sw_trips (
 id VARCHAR(36) PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES sw_users(id),
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), completed_at TIMESTAMPTZ,
 status VARCHAR(20) NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','started','completed')),
 route_json TEXT NOT NULL, distance_meters DOUBLE PRECISION NOT NULL CHECK (distance_meters >= 0),
 consumption DOUBLE PRECISION NOT NULL CHECK (consumption BETWEEN 1 AND 100),
 actual_km DOUBLE PRECISION CHECK (actual_km >= 0), demo BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS sw_trips_company ON sw_trips(company_id, completed_at);
CREATE INDEX IF NOT EXISTS sw_collections_bin_time ON collections(bin_id, collected_at);
