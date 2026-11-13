-- Additive PostgreSQL migration for the supplied existing schema.
-- Run in a transaction; repeatable. No DROP, DELETE, measurement or report changes.
BEGIN;
SELECT pg_advisory_xact_lock(2026111301);
CREATE TABLE IF NOT EXISTS sw_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('Resident','Company','Admin')),
    display_name VARCHAR(120) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    demo BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE UNIQUE INDEX IF NOT EXISTS sw_single_admin ON sw_users(role) WHERE role = 'Admin';
ALTER TABLE bins ADD COLUMN IF NOT EXISTS name VARCHAR(120) NOT NULL DEFAULT 'Tomberon';
ALTER TABLE bins ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES sw_users(id);
ALTER TABLE bins ADD COLUMN IF NOT EXISTS demo BOOLEAN NOT NULL DEFAULT FALSE;
CREATE TABLE IF NOT EXISTS sw_sessions (
    token_hash VARCHAR(64) PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES sw_users(id),
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_sw_sessions_user_id ON sw_sessions(user_id);
CREATE TABLE IF NOT EXISTS sw_resident_bins (
    user_id INTEGER NOT NULL REFERENCES sw_users(id),
    bin_id TEXT NOT NULL REFERENCES bins(bin_id),
    PRIMARY KEY(user_id, bin_id)
);
CREATE TABLE IF NOT EXISTS sw_incidents (
    id SERIAL PRIMARY KEY,
    bin_id TEXT NOT NULL REFERENCES bins(bin_id),
    user_id INTEGER NOT NULL REFERENCES sw_users(id),
    category VARCHAR(40) NOT NULL,
    comment VARCHAR(2000) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_progress','resolved')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_sw_incidents_bin_id ON sw_incidents(bin_id);
COMMIT;
