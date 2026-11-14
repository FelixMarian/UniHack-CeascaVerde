-- Tiger Cloud / PostgreSQL. Adds 60 demo bins for company1.
BEGIN;
SET LOCAL TIME ZONE 'Europe/Bucharest';
SELECT pg_advisory_xact_lock(2026111501);
DO $$
DECLARE
    company integer;
    i integer;
    d integer;
    slot integer;
    test_id text;
    collected timestamptz;
BEGIN
    SELECT id INTO STRICT company FROM sw_users
    WHERE username = 'company1' AND role = 'Company' AND active;
    FOR i IN 1..60 LOOP
        test_id := 'DEMO_EXT_' || lpad(i::text, 3, '0');
        INSERT INTO bins(bin_id, name, company_id, latitude, longitude, capacity_liters, demo)
        VALUES (test_id, 'Timișoara ' || i, company,
                45.733 + (i % 10) * 0.0037,
                21.175 + ((i - 1) / 10) * 0.016 + (i % 3) * 0.001, 240, true)
        ON CONFLICT (bin_id) DO NOTHING;
        IF NOT FOUND THEN CONTINUE; END IF;
        FOR d IN 0..44 LOOP
            IF (d + i) % (2 + i % 8) <> 0 THEN CONTINUE; END IF;
            slot := (i * 17 + d * 23) % 900;
            collected := date_trunc('day', now()) - make_interval(days => d) + interval '5 hours'
                         + make_interval(mins => slot);
            IF collected >= now() THEN CONTINUE; END IF;
            INSERT INTO collections(collection_id, bin_id, collected_at, confirmed_by)
            VALUES (md5('smartwaste-expanded-v1-' || test_id || '-' || d)::uuid, test_id, collected, 'company1');
            INSERT INTO sw_ultrasonic_measurements
                (bin_id, fill_category, distance_mid_cm, distance_full_cm, distance_top_cm, config_hash, recorded_at)
            VALUES (test_id, 2, 4, 30, 8, repeat('e',64), collected - interval '2 hours'),
                   (test_id, 3, 4, 4, 4, repeat('e',64), collected - interval '1 hour'),
                   (test_id, 1, 30, 30, 30, repeat('e',64), collected);
        END LOOP;
        INSERT INTO sw_ultrasonic_measurements
            (bin_id, fill_category, distance_mid_cm, distance_full_cm, distance_top_cm, config_hash, recorded_at)
        VALUES (test_id, 1 + i % 3, CASE WHEN i % 3 = 0 THEN 30 ELSE 4 END,
                CASE WHEN i % 3 = 2 THEN 4 ELSE 30 END,
                (ARRAY[30,8,4])[1+i%3], repeat('e',64), now());
    END LOOP;
END $$;
COMMIT;

SELECT (c.collected_at AT TIME ZONE 'Europe/Bucharest')::date AS zi,
       extract(hour FROM c.collected_at AT TIME ZONE 'Europe/Bucharest') AS ora,
       count(*) AS colectari
FROM collections c JOIN bins b USING (bin_id)
WHERE b.demo AND b.bin_id ~ '^DEMO_EXT_[0-9]{3}$' AND c.confirmed_by = 'company1'
GROUP BY 1, 2 ORDER BY 1 DESC, 2;
