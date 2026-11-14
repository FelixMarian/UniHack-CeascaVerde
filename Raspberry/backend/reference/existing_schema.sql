-- Schema supplied by the user, 2026-11-13. REFERENCE ONLY, not a migration.
CREATE TABLE IF NOT EXISTS bins (
    bin_id TEXT PRIMARY KEY,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    capacity_liters INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS bin_measurements (
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    bin_id TEXT NOT NULL REFERENCES bins(bin_id),
    fill_level INTEGER NOT NULL CHECK (fill_level BETWEEN 0 AND 100),
    battery INTEGER CHECK (battery BETWEEN 0 AND 100)
) WITH (timescaledb.hypertable, timescaledb.partition_column = 'recorded_at');
CREATE INDEX IF NOT EXISTS idx_bin_measurements ON bin_measurements (bin_id, recorded_at DESC);
CREATE TABLE IF NOT EXISTS collections (
    collection_id UUID PRIMARY KEY,
    bin_id TEXT NOT NULL REFERENCES bins(bin_id),
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmed_by TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
    report_id UUID PRIMARY KEY,
    report_type TEXT NOT NULL,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    content JSONB NOT NULL,
    sha256_hash TEXT NOT NULL,
    solana_signature TEXT,
    blockchain_status TEXT NOT NULL DEFAULT 'pending'
);
