import json
import os
import uuid
import pytest
import psycopg
from psycopg import sql
from sqlalchemy import select, func
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from test_api import env, login, Legacy
from test_postgres import ROOT
from smartwaste.db import sessions, make_engine
from smartwaste.models import Incident, Trip
from smartwaste.manage import migrate, seed
from smartwaste.integration import install
from smartwaste import route_planner, statistics


@pytest.mark.parametrize('mode,status,error', [('verified','verified',None),('pending','pending','SOLANA_CONFIRMATION_PENDING'),('funds','failed','SOLANA_INSUFFICIENT_FUNDS')])
def test_automatic_proof_outcomes(env, monkeypatch, tmp_path, mode, status, error):
    from solders.keypair import Keypair
    from smartwaste import automatic_proofs, solana_worker
    from smartwaste.proofs import SolanaRPCError
    client,engine,_=env
    monkeypatch.setenv('SMARTWASTE_SOLANA_KEYPAIR',str(tmp_path/'absent'))
    headers,_=login(client,'resident1')
    id=client.post('/api/v1/incidents',headers=headers,json={'bin_id':'DEMO_BIN_001','category':'damaged','comment':'Test'}).json()['id']
    wallet=tmp_path/'wallet.json';wallet.write_text(json.dumps(list(bytes(Keypair()))))
    monkeypatch.setenv('SMARTWASTE_SOLANA_KEYPAIR',str(wallet))
    def publish(*args):
        if mode=='funds': raise SolanaRPCError('SOLANA_INSUFFICIENT_FUNDS')
        return 'verified' if mode=='verified' else 'submitted'
    monkeypatch.setattr(solana_worker,'publish_one',publish)
    monkeypatch.setattr(automatic_proofs,'check',lambda item: {'status':'pending'})
    automatic_proofs.process(sessions(engine),id,wait_seconds=0)
    result=client.get(f'/api/v1/incidents/{id}/blockchain',headers=headers).json()
    assert result['status']==status and result['error_code']==error


def test_automatic_solana_failure_saved_and_idempotent(env, monkeypatch, tmp_path):
    client, engine, _ = env
    monkeypatch.setenv('SMARTWASTE_SOLANA_KEYPAIR', str(tmp_path/'absent.json'))
    headers, _ = login(client, 'resident1')
    payload = {'bin_id': 'DEMO_BIN_001', 'category': 'damaged', 'comment': 'Broken', 'request_id': str(uuid.uuid4())}
    first = client.post('/api/v1/incidents', headers=headers, json=payload)
    second = client.post('/api/v1/incidents', headers=headers, json=payload)
    assert first.status_code == second.status_code == 201
    id = first.json()['id']
    assert second.json()['id'] == id
    result = client.get(f'/api/v1/incidents/{id}/blockchain', headers=headers).json()
    assert result['status'] == 'failed' and result['error_code'] == 'SOLANA_NOT_CONFIGURED'
    assert client.post('/api/v1/incidents', headers=headers, json={**payload, 'comment': 'Other'}).status_code == 409
    other, _ = login(client, 'resident2')
    assert client.get(f'/api/v1/incidents/{id}/blockchain', headers=other).status_code == 404
    with sessions(engine)() as db:
        assert db.scalar(select(func.count()).select_from(Incident)) == 1


def test_gemini_and_road_geometry_validation(monkeypatch):
    for key, value in [('OPENROUTESERVICE_API_KEY','test-ors'),('GEMINI_API_KEY','test-gemini'),('GEMINI_MODEL','test-model')]: monkeypatch.setenv(key,value)
    calls = []
    def post(url, key, payload, gemini=False):
        calls.append((url,payload))
        if 'matrix' in url: return {'distances': [[0,1,8],[4,0,2],[3,7,0]]}
        if gemini: return {'candidates':[{'content':{'parts':[{'text':'{"order":[2,1]}'}]}}]}
        return {'features':[{'geometry':{'coordinates':[[21,45],[21.1,45.1],[21,45]]},'properties':{'summary':{'distance':600,'duration':100}}}]}
    monkeypatch.setattr(route_planner,'post',post)
    bins=[{'bin_id':'A','latitude':45.1,'longitude':21.1},{'bin_id':'B','latitude':45.2,'longitude':21.2}]
    result=route_planner.plan((45,21),bins)
    assert [b['bin_id'] for b in result['stops']] == ['A','B']
    assert result['geometry'][1]==[45.1,21.1] and result['distance_meters']==600
    assert len(calls)==3 and 'generateContent' in calls[1][0]
    monkeypatch.setattr(route_planner,'post',lambda url,key,payload,gemini=False:
        {'distances':[[0,1,2],[1,0,2],[2,2,0]]} if not gemini else {'candidates':[{'content':{'parts':[{'text':'{"order":[1,1]}'}]}}]})
    with pytest.raises(HTTPException) as exc: route_planner.plan((45,21),bins)
    assert exc.value.status_code==502


def test_route_trip_lifecycle_and_statistics_scope(env, monkeypatch):
    client, engine, _ = env
    owner,user=login(client,'company1'); other,_=login(client,'company2')
    client.put(f"/api/v1/companies/{user['id']}/hq",headers=owner,json={'latitude':45,'longitude':21})
    monkeypatch.setattr(statistics,'plan',lambda hq,bins: {'stops':bins,'geometry':[[45,21],[45.1,21.1]],'distance_meters':12000,'duration_seconds':900,'planner':'test'})
    response=client.post('/api/v1/company/route/optimize',headers=owner,json={'consumption':20})
    assert response.status_code==200,response.text
    id=response.json()['id']
    assert response.json()['estimated_fuel_liters']==2.4
    assert client.post(f'/api/v1/company/routes/{id}/start',headers=other).status_code==404
    assert client.post(f'/api/v1/company/routes/{id}/complete',headers=owner,json={'actual_km':13}).status_code==409
    stats=client.get('/api/v1/company/statistics',headers=owner).json()
    assert stats['periods'][0]['reported_km']==0
    client.post(f'/api/v1/company/routes/{id}/start',headers=owner)
    for _ in range(2): assert client.post(f'/api/v1/company/routes/{id}/complete',headers=owner,json={'actual_km':13}).status_code==200
    stats=client.get('/api/v1/company/statistics',headers=owner).json()
    assert stats['periods'][0]['reported_km']==13 and stats['periods'][0]['estimated_fuel_liters']==2.6
    assert client.get('/api/v1/company/statistics',headers=other).json()['periods'][0]['reported_km']==0
    assert client.get('/api/v1/company/routes',headers=other).json()==[]


@pytest.mark.skipif(not os.getenv('SMARTWASTE_TEST_DATABASE_URL'), reason='Local PostgreSQL not configured')
def test_timisoara_seed_and_statistics_postgres():
    url=os.environ['SMARTWASTE_TEST_DATABASE_URL']; schema='sw_v130_'+uuid.uuid4().hex
    with psycopg.connect(url,autocommit=True) as c: c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    scoped=url+'?options=-csearch_path%3D'+schema
    engine=make_engine(scoped)
    try:
        with engine.begin() as c: c.exec_driver_sql((ROOT/'reference/existing_schema.sql').read_text().replace(" WITH (timescaledb.hypertable, timescaledb.partition_column = 'recorded_at')",''))
        migrate(engine); migrate(engine); seed(engine)
        with engine.connect().execution_options(isolation_level='AUTOCOMMIT', no_parameters=True) as c:
            c.exec_driver_sql((ROOT/'demo_timisoara.sql').read_text(encoding='utf-8'))
        with psycopg.connect(scoped,autocommit=True) as c:
            seed_sql=(ROOT/'demo_timisoara.sql').read_text(encoding='utf-8')
            c.execute(seed_sql)
            before=c.execute('SELECT count(*) FROM collections').fetchone()[0]
            c.execute(seed_sql)
            assert c.execute('SELECT count(*) FROM collections').fetchone()[0]==before
            assert c.execute("SELECT count(*) FROM bins WHERE bin_id LIKE 'DEMO_TM_%'").fetchone()[0]==10
            assert c.execute("SELECT count(DISTINCT company_id) FROM bins WHERE bin_id LIKE 'DEMO_TM_%'").fetchone()[0]==1
            c.execute((ROOT/'company_statistics.sql').read_text(encoding='utf-8'))
        app=FastAPI(); install(app,engine=engine,legacy=Legacy(),device_key='test')
        with TestClient(app) as client:
            company,_=login(client,'company1')
            bins=client.get('/api/v1/bins',headers=company).json()
            assert {b['fill_category'] for b in bins if b['bin_id'].startswith('DEMO_TM_')}=={1,2,3,4}
            stats=client.get('/api/v1/company/statistics',headers=company)
            assert stats.status_code==200,stats.text
            assert stats.json()['periods'][0]['collections']==3
            assert stats.json()['periods'][0]['completed_routes']==1
            assert stats.json()['periods'][2]['estimated_fuel_liters']>0
            assert max(b['full_events'] for b in stats.json()['bins'])>0
            assert stats.json()['has_demo_data']
    finally:
        engine.dispose()
        with psycopg.connect(url,autocommit=True) as c: c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
