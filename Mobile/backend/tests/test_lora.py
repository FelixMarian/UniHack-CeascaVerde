import importlib.util
import os
from pathlib import Path
import uuid
from concurrent.futures import ThreadPoolExecutor
import pytest
import psycopg
from psycopg import sql
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from smartwaste.db import make_engine
from smartwaste.manage import migrate
from smartwaste.integration import install

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('packet', ROOT.parent / 'lora/packet.py')
packet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packet)


def test_packet_aliases_and_sequence_restart():
    expected = {'bin_id':'BIN_001', 'latitude':45.75, 'longitude':21.2, 'fill_level':85}
    assert packet.validate_reading({'id':'BIN_001','lat':45.75,'long':21.2,'fill_level':85,'sequence':0}) == expected
    assert packet.validate_reading({**expected, 'sequence':999}) == expected


@pytest.mark.parametrize('change', [
    {'fill_level':True}, {'fill_level':101}, {'fill_level':85.5},
    {'latitude':None}, {'latitude':float('nan')}, {'longitude':181},
    {'bin_id':' '}, {'battery':True}, {'lat':44}, {'longitude':'21.2'},
])
def test_invalid_packets(change):
    with pytest.raises(ValueError):
        packet.validate_reading({'bin_id':'BIN_001','latitude':45.75,'longitude':21.2,'fill_level':85, **change})


@pytest.mark.skipif(not os.getenv('SMARTWASTE_TEST_DATABASE_URL'), reason='Isolated PostgreSQL URL not configured')
def test_lora_postgres_changes_and_concurrent_duplicates():
    url = os.environ['SMARTWASTE_TEST_DATABASE_URL']
    schema = 'sw_test_lora_' + uuid.uuid4().hex
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    engine = make_engine(url + ('&' if '?' in url else '?') + 'options=-csearch_path%3D' + schema)
    try:
        original = (ROOT/'reference/existing_schema.sql').read_text().replace(
            " WITH (timescaledb.hypertable, timescaledb.partition_column = 'recorded_at')", '')
        with engine.begin() as c:
            c.exec_driver_sql(original)
            c.execute(text("INSERT INTO bins(bin_id) VALUES ('BIN_001'), ('BIN_002')"))
        migrate(engine)
        app = FastAPI()
        install(app, engine=engine, legacy=object(), device_key='test-key')
        headers = {'X-API-Key':'test-key'}
        body = {'bin_id':'BIN_001','latitude':45.75,'longitude':21.2,'fill_level':85}
        with TestClient(app) as client:
            def post(data):
                response = client.post('/iot/readings',headers=headers,json=data)
                assert response.status_code == 200, response.text
                return response.json()
            assert client.post('/iot/readings',json=body).status_code == 401
            assert client.post('/iot/readings',headers=headers,json={**body,'bin_id':'MISSING'}).status_code == 404
            for invalid in [{'latitude':True}, {'fill_level':True}, {'fill_level':-1}, {'longitude':181}]:
                assert client.post('/iot/readings',headers=headers,json={**body, **invalid}).status_code == 422
            assert post(body) == {'bin_id':'BIN_001','changed':True,'measurement_saved':True,'coordinates_updated':True,'reason':'updated'}
            assert post(body)['changed'] is False
            with engine.connect() as c:
                first_time = c.execute(text('SELECT recorded_at FROM bin_measurements')).scalar()
            moved = {**body, 'latitude':46.0}
            result = post(moved)
            assert result['coordinates_updated'] and not result['measurement_saved']
            with engine.connect() as c:
                assert c.execute(text('SELECT recorded_at FROM bin_measurements')).scalar() == first_time
            assert post({**body,'bin_id':'BIN_002'})['measurement_saved']
            assert post(moved)['changed'] is False  # Comparison is per bin, not global.
            # New app instance simulates a receiver/server restart: no in-memory cache is needed.
            restarted = FastAPI()
            install(restarted, engine=engine, legacy=object(), device_key='test-key')
            with TestClient(restarted) as second:
                assert second.post('/iot/readings',headers=headers,json=moved).json()['changed'] is False
            with ThreadPoolExecutor(max_workers=6) as pool:
                results = list(pool.map(lambda _: post({**moved,'fill_level':60}), range(12)))
            assert sum(r['measurement_saved'] for r in results) == 1
            assert post(moved)['measurement_saved']  # 85 -> 60 -> 85 is a real change.
            assert post({**moved,'battery':80})['measurement_saved']
            assert post(moved)['changed'] is False  # Missing battery doesn't erase stored battery.
        with engine.connect() as c:
            assert c.execute(text("SELECT count(*) FROM bin_measurements WHERE bin_id='BIN_001'")).scalar() == 4
            assert c.execute(text("SELECT count(*) FROM bin_measurements WHERE bin_id='BIN_002'")).scalar() == 1
            assert c.execute(text("SELECT latitude FROM bins WHERE bin_id='BIN_001'")).scalar() == 46.0
    finally:
        engine.dispose()
        with psycopg.connect(url, autocommit=True) as connection:
            connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
