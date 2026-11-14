-- Run in Tiger Cloud. Applies only to the Timișoara demo set owned by company1.
BEGIN;
UPDATE bins b
SET name = regexp_replace(b.name, '^DEMO([[:space:]]*•)?[[:space:]]+', '', 'i')
FROM sw_users u
WHERE b.company_id = u.id AND u.username = 'company1' AND u.role = 'Company'
  AND b.demo AND (b.bin_id ~ '^DEMO_TM_(00[1-9]|010)$' OR b.bin_id = 'DEMO_BIN_001')
  AND b.name ~* '^DEMO([[:space:]]*•)?[[:space:]]+'
RETURNING b.bin_id, b.name;

-- Example HQ in Timișoara. Replace the coordinates with the actual depot if known.
UPDATE sw_users
SET hq_latitude = 45.7480, hq_longitude = 21.2150
WHERE username = 'company1' AND role = 'Company'
RETURNING username, hq_latitude, hq_longitude;
COMMIT;
