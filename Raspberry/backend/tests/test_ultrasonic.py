import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
import psycopg
from psycopg import sql
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from smartwaste.db import make_engine
from smartwaste.manage import migrate, seed
from smartwaste.integration import install
from smartwaste.ultrasonic_classifier import parse_thresholds, classify, CalibrationError, SensorError
from test_lora import packet

ROOT = Path(__file__).resolve().parents[1]
# Test fixture values ONLY, not a calibration for the user's physical bin.
CONFIG = '''#define MID_DETECT_CM 10
#define FULL_DETECT_CM 10
#define TOP_FULL_CM 20
#define TOP_MEDIUM_CM 60
#define SENSOR_MIN_CM 2
#define SENSOR_MAX_CM 400
'''


@pytest.mark.parametrize('mid,full,top,result', [
    (50,50,90,1), (5,50,40,2), (5,5,10,3),
    (10,50,60,2), (10,10,20,3),
    (50,5,10,3), (50,50,10,None), (5,50,10,2),
    (5,5,90,None), (5,50,90,None), (50,50,40,None),
    (0,50,90,None), (float('nan'),50,90,None), (50,50,401,None),
])
def test_classifier(mid,full,top,result):
    if result is None:
        with pytest.raises(SensorError): classify(mid,full,top,parse_thresholds(CONFIG))
    else:
        assert classify(mid,full,top,parse_thresholds(CONFIG)) == result


@pytest.mark.parametrize('config', [
    CONFIG.replace('TOP_FULL_CM 20','TOP_FULL_CM 70'),
    CONFIG.replace('MID_DETECT_CM 10','MID_DETECT_CM -1'),
    CONFIG + '#define MID_DETECT_CM 12\n',
    CONFIG.replace('FULL_DETECT_CM 10','FULL_DETECT_CM run_code()'),
    CONFIG.replace('#define SENSOR_MAX_CM 400\n',''),
])
def test_bad_configuration(config):
    with pytest.raises(CalibrationError): parse_thresholds(config)


@pytest.mark.parametrize('mid,full,top,category', [
    (6,6,11,1), (5,6,10,2), (5,6,3,2), (5,5,5,3), (20,5,5,3),
    (5,5,5.01,None), (5,6,10.01,None), (6,6,10,None),
])
def test_user_thresholds(mid,full,top,category):
    config=(ROOT/'config/ultrasonic_thresholds.h').read_text()
    thresholds=parse_thresholds(config)
    assert (thresholds.mid,thresholds.full,thresholds.top_medium,thresholds.top_full)==(5,5,10,5)
    if category is None:
        with pytest.raises(SensorError): classify(mid,full,top,thresholds)
    else:
        assert classify(mid,full,top,thresholds)==category


def test_packet_distances():
    body = {'id':'BIN_001','lat':45.7,'long':21.2,'distance_mid_cm':5,'distance_full_cm':50,'distance_top_cm':40}
    result = packet.validate_ultrasonic(body)
    assert result['bin_id'] == 'BIN_001' and result['distance_mid_cm'] == 5.0
    for changes in ({'distance_mid_cm':0},{'distance_top_cm':None},{'distance_full_cm':True},{'fill_level':85}):
        with pytest.raises(ValueError): packet.validate_ultrasonic({**body, **changes})


@pytest.mark.skipif(not os.getenv('SMARTWASTE_TEST_DATABASE_URL'), reason='Isolated PostgreSQL URL not configured')
def test_ultrasonic_postgres_and_mobile(monkeypatch,tmp_path):
    url = os.environ['SMARTWASTE_TEST_DATABASE_URL']
    schema = 'sw_test_ultra_' + uuid.uuid4().hex
    with psycopg.connect(url, autocommit=True) as c:
        c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    engine = make_engine(url + ('&' if '?' in url else '?') + 'options=-csearch_path%3D' + schema)
    config_file = tmp_path/'thresholds.h'
    config_file.write_text(CONFIG)
    monkeypatch.setenv('SMARTWASTE_ULTRASONIC_CONFIG',str(config_file))
    try:
        original = (ROOT/'reference/existing_schema.sql').read_text().replace(
            " WITH (timescaledb.hypertable, timescaledb.partition_column = 'recorded_at')", '')
        with engine.begin() as c: c.exec_driver_sql(original)
        migrate(engine); migrate(engine); seed(engine)
        with engine.begin() as c:
            c.execute(text("INSERT INTO bin_measurements(bin_id,fill_level) VALUES ('DEMO_BIN_001',85)"))
        app = FastAPI()
        install(app,engine=engine,legacy=object(),device_key='test-key')
        headers = {'X-API-Key':'test-key'}
        body = {'bin_id':'DEMO_BIN_001','latitude':45.7,'longitude':21.2,
                'distance_mid_cm':50,'distance_full_cm':50,'distance_top_cm':90}
        path = '/iot/ultrasonic-readings'
        with TestClient(app) as client:
            def post(payload):
                response=client.post(path,headers=headers,json=payload)
                assert response.status_code == 200,response.text
                return response.json()
            assert client.post(path,json=body).status_code == 401
            config_file.write_text(CONFIG.replace('MID_DETECT_CM 10','MID_DETECT_CM -1'))
            assert client.post(path,headers=headers,json=body).status_code == 503
            config_file.write_text(CONFIG)
            for invalid in ({'distance_mid_cm':0},{'distance_top_cm':None},{'distance_full_cm':True},
                            {'distance_mid_cm':5,'distance_top_cm':90}):
                assert client.post(path,headers=headers,json={**body,**invalid}).status_code == 422
            assert client.post(path,headers=headers,json={**body,'bin_id':'NO_SUCH_BIN'}).status_code == 404
            assert post(body)['fill_category'] == 1
            assert not post({**body,'distance_top_cm':95})['changed']
            medium={**body,'distance_mid_cm':5,'distance_top_cm':40}
            assert post(medium)['fill_category'] == 2
            full={**medium,'distance_full_cm':5,'distance_top_cm':10}
            with ThreadPoolExecutor(max_workers=6) as pool:
                responses=list(pool.map(lambda _:post(full),range(12)))
            assert sum(r['measurement_saved'] for r in responses) == 1
            coords=post({**full,'latitude':46.0})
            assert coords['coordinates_updated'] and not coords['measurement_saved']
            # Invalid readings cannot overwrite the last valid classification/coordinates.
            assert client.post(path,headers=headers,json={**body,'latitude':0,'distance_top_cm':10}).status_code == 422
            login=client.post('/api/v1/auth/login',json={'username':'resident1','password':'resident1'})
            mobile=client.get('/api/v1/bins',headers={'Authorization':'Bearer '+login.json()['access_token']})
            assert mobile.status_code == 200,mobile.text
            assert len(mobile.json()) == 1
            assert mobile.json()[0]['fill_category'] == 3
            assert mobile.json()[0]['fill_level'] is None  # Never 3% or invented 100%.
            assert mobile.json()[0]['latitude'] == 46.0
        # Recreate app to prove persisted comparison, not an in-memory cache.
        again=FastAPI(); install(again,engine=engine,legacy=object(),device_key='test-key')
        with TestClient(again) as client:
            assert not client.post(path,headers=headers,json={**full,'latitude':46.0}).json()['changed']
        with engine.connect() as c:
            assert c.execute(text('SELECT count(*) FROM sw_ultrasonic_measurements')).scalar() == 3
            assert c.execute(text('SELECT fill_level FROM bin_measurements')).scalar() == 85
            assert c.execute(text('SELECT fill_category FROM sw_ultrasonic_measurements ORDER BY id')).scalars().all() == [1,2,3]
    finally:
        engine.dispose()
        with psycopg.connect(url,autocommit=True) as c:
            c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
