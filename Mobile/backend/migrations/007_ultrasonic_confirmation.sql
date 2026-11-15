ALTER TABLE sw_ultrasonic_measurements
    ADD COLUMN IF NOT EXISTS classification_confirmed BOOLEAN NOT NULL DEFAULT TRUE;
