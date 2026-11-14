-- DEMO ONLY: synthetic locations, readings, collections and journeys, not real municipal bins.
-- Run after migrate 004. Atomic and repeat-safe; never modifies existing real bins/HQ.
BEGIN;
SELECT pg_advisory_xact_lock(2026111403);
DO $$
DECLARE
 company INTEGER; i INTEGER; d INTEGER; level INTEGER; id TEXT; stamp TIMESTAMPTZ;
 lat DOUBLE PRECISION[] := ARRAY[45.7536,45.7489,45.7590,45.7448,45.7367,45.7328,45.7570,45.7665,45.7501,45.7450];
 lon DOUBLE PRECISION[] := ARRAY[21.2258,21.2087,21.2290,21.2280,21.2160,21.2360,21.2440,21.2140,21.1900,21.2530];
 names TEXT[] := ARRAY['Centru','Iosefin','Cetate nord','Complex studențesc','Elisabetin','Soarelui','Fabric','Circumvalațiunii','Dâmbovița','Calea Buziașului'];
 categories INTEGER[] := ARRAY[3,1,2,3,3,2,1,2,3,3];
 trip_id TEXT; km DOUBLE PRECISION;
BEGIN
 SELECT sw_users.id INTO company FROM sw_users WHERE username='company1' AND role='Company' AND active;
 IF company IS NULL THEN RAISE EXCEPTION 'Contul activ company1 nu există. Creează-l din Admin înainte de script.'; END IF;
 IF EXISTS (SELECT 1 FROM bins WHERE bin_id LIKE 'DEMO_TM_%') THEN
  IF (SELECT count(*) FROM bins WHERE bin_id LIKE 'DEMO_TM_%' AND demo AND company_id=company)=10
     AND (SELECT count(*) FROM bins WHERE bin_id LIKE 'DEMO_TM_%')=10 THEN
   RAISE NOTICE 'Setul DEMO_TM există deja. Nu s-au duplicat datele.'; RETURN;
  END IF;
  RAISE EXCEPTION 'Prefixul DEMO_TM este deja utilizat parțial sau de alte date. Nu se suprascrie nimic.';
 END IF;
 UPDATE sw_users SET hq_latitude=45.7480,hq_longitude=21.2150
 WHERE sw_users.id=company AND hq_latitude IS NULL AND hq_longitude IS NULL;
 FOR i IN 1..10 LOOP
  id := 'DEMO_TM_' || lpad(i::text,3,'0');
  INSERT INTO bins(bin_id,name,latitude,longitude,company_id,demo,is_damaged,capacity_liters)
  VALUES(id,'DEMO • '||names[i],lat[i],lon[i],company,true,i IN (4,8),240);
  FOR d IN REVERSE 35..1 LOOP
   stamp := date_trunc('day',now()) - make_interval(days=>d) + interval '8 hours';
   level := CASE WHEN d % (1+i%4)=0 THEN 3 WHEN d % 2=0 THEN 2 ELSE 1 END;
   INSERT INTO sw_ultrasonic_measurements(bin_id,fill_category,distance_mid_cm,distance_full_cm,distance_top_cm,battery,config_hash,recorded_at)
   VALUES(id,level,CASE WHEN level>=2 THEN 4 ELSE 30 END,CASE WHEN level=3 THEN 4 ELSE 30 END,
     CASE WHEN level=3 THEN 4 WHEN level=2 THEN 8 ELSE 30 END,85,repeat('d',64),stamp);
   IF level=3 THEN
    INSERT INTO collections(collection_id,bin_id,collected_at,confirmed_by)
    VALUES(md5('smartwaste-tm-v130-'||i||'-'||d)::uuid,id,stamp+interval '2 hours','company1');
    INSERT INTO sw_ultrasonic_measurements(bin_id,fill_category,distance_mid_cm,distance_full_cm,distance_top_cm,battery,config_hash,recorded_at)
    VALUES(id,1,30,30,30,85,repeat('d',64),stamp+interval '3 hours');
   END IF;
  END LOOP;
  IF i<=3 THEN
   INSERT INTO collections(collection_id,bin_id,collected_at,confirmed_by)
   VALUES(md5('smartwaste-tm-v130-today-'||i)::uuid,id,now()-make_interval(mins=>i*3),'company1');
  END IF;
  level := categories[i];
  INSERT INTO sw_ultrasonic_measurements(bin_id,fill_category,distance_mid_cm,distance_full_cm,distance_top_cm,battery,config_hash,recorded_at)
  VALUES(id,level,CASE WHEN level>=2 THEN 4 ELSE 30 END,CASE WHEN level=3 THEN 4 ELSE 30 END,
    CASE WHEN level=3 THEN 4 WHEN level=2 THEN 8 ELSE 30 END,85,repeat('d',64),now()-interval '1 minute');
 END LOOP;
 FOR d IN 0..30 LOOP
  trip_id := md5('smartwaste-tm-trip-v130-'||d)::uuid::text;
  km := 8 + (d%7)*1.3;
  INSERT INTO sw_trips(id,company_id,created_at,completed_at,status,route_json,distance_meters,consumption,actual_km,demo)
  VALUES(trip_id,company,now()-make_interval(days=>d)-interval '3 hours',now()-make_interval(days=>d)-interval '5 minutes',
   'completed',json_build_object('id',trip_id,'hq_latitude',45.7480,'hq_longitude',21.2150,'stops',json_build_array(),
   'geometry',json_build_array(),'skipped_bin_ids',json_build_array(),'distance_meters',km*1000,'duration_seconds',km*180,
   'consumption',20,'estimated_fuel_liters',km*.2,'planner','DEMO sintetic','status','completed')::text,km*1000,20,km,true);
 END LOOP;
END $$;
COMMIT;

SELECT bin_id,name,latitude,longitude,is_damaged,company_id FROM bins WHERE bin_id LIKE 'DEMO_TM_%' ORDER BY bin_id;
-- Optional: give an existing resident access, only if wanted:
-- INSERT INTO sw_resident_bins(user_id,bin_id)
-- SELECT u.id,b.bin_id FROM sw_users u CROSS JOIN bins b
-- WHERE u.username='resident1' AND u.role='Resident' AND b.bin_id LIKE 'DEMO_TM_%'
-- ON CONFLICT DO NOTHING;
