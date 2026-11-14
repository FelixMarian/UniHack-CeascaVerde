-- Read-only queries for the Tiger Cloud SQL console. Demo and real counts separated.
-- Daily collection counts attributed to the account that confirmed collection.
SELECT (c.collected_at AT TIME ZONE 'Europe/Bucharest')::date AS zi,
       b.demo, count(*) AS colectari
FROM collections c JOIN bins b USING(bin_id)
WHERE c.confirmed_by='company1' AND c.collected_at >= now()-interval '90 days'
GROUP BY 1,2 ORDER BY 1 DESC;

-- Average interval between successive collections (not time between sensor readings).
WITH intervals AS (
 SELECT c.bin_id, c.collected_at-lag(c.collected_at) OVER(PARTITION BY c.bin_id ORDER BY c.collected_at) AS gap
 FROM collections c WHERE c.confirmed_by='company1' AND c.collected_at >= now()-interval '90 days'
)
SELECT bin_id,round(avg(extract(epoch FROM gap))/3600,1) AS interval_mediu_ore
FROM intervals GROUP BY bin_id ORDER BY bin_id;

-- Observed transitions from not-full to full, not total number of full readings.
WITH states AS (
 SELECT m.*,lag(fill_category) OVER(PARTITION BY m.bin_id ORDER BY m.recorded_at,m.id) AS previous
 FROM sw_ultrasonic_measurements m JOIN bins b USING(bin_id)
 JOIN sw_users u ON u.id=b.company_id WHERE u.username='company1'
)
SELECT bin_id,count(*) AS umpleri FROM states
WHERE fill_category=3 AND previous IN (1,2) AND recorded_at>=now()-interval '90 days'
GROUP BY bin_id ORDER BY umpleri DESC;

-- Kilometers and estimated fuel for completed trips.
SELECT date_trunc('month',t.completed_at AT TIME ZONE 'Europe/Bucharest') AS luna,t.demo,
 count(*) AS curse,sum(t.actual_km) AS km_declarati,
 sum(CASE WHEN t.planned_completion THEN t.distance_meters / 1000 ELSE 0 END) AS km_planificati,
 sum((CASE WHEN t.planned_completion THEN t.distance_meters / 1000 ELSE coalesce(t.actual_km,0) END)
     * t.consumption / 100) AS litri_estimati
FROM sw_trips t JOIN sw_users u ON u.id=t.company_id
WHERE u.username='company1' AND t.status='completed'
GROUP BY 1,2 ORDER BY 1 DESC;
