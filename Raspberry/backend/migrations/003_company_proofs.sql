-- Additive; safe to run again. No sensor history is rewritten.
ALTER TABLE bins ADD COLUMN IF NOT EXISTS is_damaged BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE sw_users ADD COLUMN IF NOT EXISTS hq_latitude DOUBLE PRECISION;
ALTER TABLE sw_users ADD COLUMN IF NOT EXISTS hq_longitude DOUBLE PRECISION;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'sw_hq_coordinates' AND conrelid = 'sw_users'::regclass) THEN
  ALTER TABLE sw_users ADD CONSTRAINT sw_hq_coordinates CHECK (
   (hq_latitude IS NULL AND hq_longitude IS NULL) OR
   (role = 'Company' AND hq_latitude IS NOT NULL AND hq_longitude IS NOT NULL
    AND hq_latitude BETWEEN -90 AND 90 AND hq_longitude BETWEEN -180 AND 180));
 END IF;
END $$;
ALTER TABLE sw_incidents ADD COLUMN IF NOT EXISTS proof_nonce VARCHAR(64);
ALTER TABLE sw_incidents ADD COLUMN IF NOT EXISTS proof_hash VARCHAR(64);
ALTER TABLE sw_incidents ADD COLUMN IF NOT EXISTS solana_signature VARCHAR(100);
ALTER TABLE sw_incidents ADD COLUMN IF NOT EXISTS proof_transaction TEXT;
