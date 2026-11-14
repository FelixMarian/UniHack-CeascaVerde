"""Opt-in isolated-schema PostgreSQL integration test. Never points at Tiger by default."""
import importlib.util
import os
from pathlib import Path
import sys
import uuid
import pytest
import psycopg
from psycopg import sql
from fastapi.testclient import TestClient
from sqlalchemy import text
from smartwaste.db import make_engine
from smartwaste.manage import migrate, seed, inspect_schema

ROOT = Path(__file__).resolve().parents[1]


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not os.getenv('SMARTWASTE_TEST_DATABASE_URL'), reason='Isolated PostgreSQL URL not configured')
def test_postgres_original_backend_and_mobile_end_to_end(monkeypatch):
    url = os.environ['SMARTWASTE_TEST_DATABASE_URL']
    # Unique schema, never modify or drop an existing schema.
    schema = 'sw_test_' + uuid.uuid4().hex
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    scoped = url + ('&' if '?' in url else '?') + 'options=-csearch_path%3D' + schema
    engine = make_engine(scoped)
    try:
        reference_sql = (ROOT / 'reference/existing_schema.sql').read_text()
        reference_sql = reference_sql.replace(" WITH (timescaledb.hypertable, timescaledb.partition_column = 'recorded_at')", '')
        with engine.begin() as conn:
            conn.exec_driver_sql(reference_sql)
            conn.execute(text("INSERT INTO bins(bin_id,latitude,longitude,capacity_liters) VALUES ('BIN_001',45.75,21.2,240)"))
            conn.execute(text("INSERT INTO bin_measurements(bin_id,fill_level,battery) VALUES ('BIN_001',85,99)"))
        assert all(inspect_schema(engine).values())
        migrate(engine)
        migrate(engine)
        seed(engine)
        seed(engine)
        monkeypatch.setenv('TIGER_DATABASE_URL', scoped)
        monkeypatch.setenv('SMARTWASTE_API_KEY', 'test-only-device-key')
        original = load_module(ROOT / 'reference/main_original.py', 'original_test')
        monkeypatch.setitem(sys.modules, 'main', original)
        extended = load_module(ROOT / 'main_mobile.py', 'extended_test')
        device = {'X-API-Key': 'test-only-device-key'}
        with TestClient(extended.app) as client:
            def login(name):
                response = client.post('/api/v1/auth/login', json={'username': name, 'password': name})
                assert response.status_code == 200, response.text
                return {'Authorization': 'Bearer ' + response.json()['access_token']}
            admin, resident, company, other = [login(n) for n in ('admin', 'resident1', 'company1', 'resident2')]
            users = client.get('/api/v1/admin/users', headers=admin).json()
            ids = {u['username']: u['id'] for u in users}
            assert client.get('/health').json()['status'] == 'online'
            rows = client.get('/bins', headers=device).json()
            assert next(r for r in rows if r['bin_id'] == 'BIN_001')['fill_level'] == 85
            assert client.get('/bins', headers=resident).status_code == 401
            assert client.put('/api/v1/admin/bins/BIN_001', headers=admin, json={
                'bin_id': 'BIN_001', 'name': 'Existing', 'latitude':45.75, 'longitude':21.2, 'company_id':ids['company1']}).status_code == 200
            assert client.put(f"/api/v1/admin/users/{ids['resident1']}/bins", headers=admin,
                              json={'bin_ids': ['BIN_001']}).status_code == 200
            assert client.get('/api/v1/bins', headers=resident).json()[0]['fill_level'] == 85
            assert 'BIN_001' not in [b['bin_id'] for b in client.get('/api/v1/bins', headers=other).json()]
            incident = client.post('/api/v1/incidents', headers=resident, json={
                'bin_id':'BIN_001','category':'damaged','comment':'PostgreSQL integration test'})
            assert incident.status_code == 201, incident.text
            proof = client.post(f"/api/v1/incidents/{incident.json()['id']}/proof", headers=resident)
            assert proof.status_code == 200 and proof.json()['status'] == 'prepared'
            assert len(proof.json()['sha256']) == 64
            assert client.put(f"/api/v1/companies/{ids['company1']}/hq", headers=company,
                              json={'latitude': 45.7, 'longitude': 21.1}).status_code == 200
            route = client.post('/api/v1/company/route', headers=company)
            assert route.status_code == 200 and route.json()['stops'][0]['bin_id'] == 'BIN_001'
            assert client.patch('/api/v1/bins/BIN_001/damage', headers=company, json={'damaged': True}).status_code == 200
            assert client.get('/api/v1/bins', headers=resident).json()[0]['fill_category'] == 4
            assert client.post('/api/v1/company/route', headers=company).json()['stops'] == []
            assert client.patch('/api/v1/bins/BIN_001/damage', headers=company, json={'damaged': False}).status_code == 200
            assert client.patch('/api/v1/incidents/' + str(incident.json()['id']), headers=company,
                                json={'status':'resolved'}).status_code == 200
            assert client.post('/api/v1/bins/BIN_001/collections', headers=company).status_code == 200
            assert client.post('/readings', headers=device, json={'bin_id':'DEMO_BIN_001','fill_level':40,'battery':90}).status_code == 200
            assert client.post('/collections', headers=device, json={'bin_id':'DEMO_BIN_001','confirmed_by':'test-device'}).status_code == 200
            report = client.post('/reports/generate', headers=device)
            assert report.status_code == 200, report.text
            report_id = report.json()['report_id']
            assert client.get('/reports/' + report_id, headers=device).json()['sha256'] == report.json()['sha256']
            assert client.get('/reports/' + report_id, headers=resident).status_code == 401
            assert client.post('/api/v1/auth/logout', headers=resident).status_code == 204
            assert client.get('/api/v1/auth/me', headers=resident).status_code == 401
        with engine.connect() as conn:
            assert conn.execute(text("SELECT fill_level,battery FROM bin_measurements WHERE bin_id='BIN_001'")).one() == (85,99)
            assert conn.execute(text("SELECT capacity_liters FROM bins WHERE bin_id='BIN_001'")).scalar() == 240
            assert conn.execute(text('SELECT count(*) FROM sw_users')).scalar() == 5
            assert conn.execute(text('SELECT status FROM sw_incidents')).scalar() == 'resolved'
            assert conn.execute(text("SELECT confirmed_by FROM collections WHERE bin_id='BIN_001'")).scalar() == 'company1'
            assert conn.execute(text('SELECT count(*) FROM reports')).scalar() == 1
        extended.app.state.sw_sessions.kw['bind'].dispose()
    finally:
        engine.dispose()
        with psycopg.connect(url, autocommit=True) as connection:
            connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
