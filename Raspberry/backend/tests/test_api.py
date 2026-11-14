from datetime import timedelta
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from smartwaste.db import make_engine, sessions, Base
from smartwaste.models import User, Bin, Incident, Session, now
from smartwaste.manage import migrate, seed
from smartwaste.integration import install
from smartwaste.security import digest, passwords


class Legacy:
    def __init__(self):
        self.calls = []
        self.available = True
    def readings(self):
        if not self.available:
            raise HTTPException(502, 'Sensor service unavailable')
        return {'DEMO_BIN_001': {'fill_level': 85, 'recorded_at': '2026-11-13T15:30:20+00:00'}}
    def collect(self, bin_id, username):
        self.calls.append((bin_id, username))
        return {'collection_id': 'test-collection'}


@pytest.fixture
def env(tmp_path):
    engine = make_engine('sqlite:///' + str(tmp_path / 'test.db'))
    migrate(engine)
    seed(engine)
    legacy = Legacy()
    app = FastAPI()
    @app.get('/health')
    def health(): return {'status': 'online'}
    @app.get('/bins')
    def old_bins(): return [{'bin_id': 'BIN_001', 'fill_level': 85}]
    @app.get('/reports/{id}')
    def old_report(id: str): return {'report_id': id}
    install(app, engine=engine, legacy=legacy, device_key='test-device-only')
    with TestClient(app) as client:
        yield client, engine, legacy
    engine.dispose()


def login(client, username, password=None):
    response = client.post('/api/v1/auth/login', json={'username': username, 'password': password or username})
    assert response.status_code == 200, response.text
    data = response.json()
    assert 'password_hash' not in data['user']
    return {'Authorization': 'Bearer ' + data['access_token']}, data['user']


def test_seed_idempotent_preserves_existing_data(env):
    client, engine, _ = env
    with sessions(engine).begin() as db:
        db.add(Bin(bin_id='BIN_001', name='Existing', latitude=10, longitude=20))
        user = db.scalar(select(User).where(User.username == 'resident1'))
        user.display_name = 'Edited name'
        original_hash = user.password_hash
    seed(engine)
    seed(engine)
    with sessions(engine)() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 5
        assert db.scalar(select(func.count()).select_from(Bin)) == 3
        assert db.get(Bin, 'BIN_001').latitude == 10
        user = db.scalar(select(User).where(User.username == 'resident1'))
        assert user.display_name == 'Edited name'
        assert user.password_hash == original_hash
        assert passwords.verify('resident1', original_hash)


def test_all_roles_and_scope(env):
    client, _, _ = env
    for username, role, expected in [('admin', 'Admin', 2), ('resident1', 'Resident', 1),
        ('resident2', 'Resident', 1), ('company1', 'Company', 1), ('company2', 'Company', 1)]:
        headers, user = login(client, username)
        assert user['role'] == role
        rows = client.get('/api/v1/bins', headers=headers).json()
        assert len(rows) == expected
        if username.endswith('1'):
            assert rows[0]['bin_id'] == 'DEMO_BIN_001'
            assert rows[0]['fill_level'] == 85
        if username.endswith('2'):
            assert rows[0]['bin_id'] == 'DEMO_BIN_002'
            assert rows[0]['fill_level'] is None
    assert client.get('/api/v1/bins').status_code == 401


def test_incident_ownership_and_status(env):
    client, engine, _ = env
    r1, _ = login(client, 'resident1')
    r2, _ = login(client, 'resident2')
    c1, _ = login(client, 'company1')
    c2, _ = login(client, 'company2')
    body = {'bin_id': 'DEMO_BIN_002', 'category': 'damaged', 'comment': 'Broken lid'}
    assert client.post('/api/v1/incidents', headers=r1, json=body).status_code == 404
    body['bin_id'] = 'DEMO_BIN_001'
    assert client.post('/api/v1/incidents', headers=r1, json={**body, 'comment': '   '}).status_code == 422
    response = client.post('/api/v1/incidents', headers=r1, json=body)
    assert response.status_code == 201
    id = response.json()['id']
    assert len(client.get('/api/v1/incidents', headers=r1).json()) == 1
    assert client.get('/api/v1/incidents', headers=r2).json() == []
    assert client.get('/api/v1/incidents', headers=c2).json() == []
    for headers, code in [(r1, 403), (c2, 404), (c1, 200)]:
        assert client.patch(f'/api/v1/incidents/{id}', headers=headers, json={'status': 'resolved'}).status_code == code
    with sessions(engine)() as db:
        assert db.get(Incident, id).status == 'resolved'


def test_admin_crud_assignments_and_revocation(env):
    client, _, _ = env
    admin, _ = login(client, 'admin')
    r1, user = login(client, 'resident1')
    c2, company = login(client, 'company2')
    assert client.get('/api/v1/admin/users', headers=r1).status_code == 403
    assert client.post('/api/v1/admin/users', headers=admin, json={'username': 'evil', 'password': 'password1', 'display_name': 'Evil', 'role': 'Admin'}).status_code == 422
    new = client.post('/api/v1/admin/users', headers=admin, json={'username': 'newuser', 'password': 'password1', 'display_name': 'New', 'role': 'Resident'})
    assert new.status_code == 201
    assert client.post('/api/v1/admin/users', headers=admin, json={'username': 'newuser', 'password': 'password1', 'display_name': 'New', 'role': 'Resident'}).status_code == 409
    newbin = {'bin_id': 'NEW_BIN', 'name': 'New bin', 'latitude': 45.7, 'longitude': 21.2, 'company_id': company['id']}
    assert client.post('/api/v1/admin/bins', headers=admin, json=newbin).status_code == 201
    assert client.put(f"/api/v1/admin/users/{user['id']}/bins", headers=admin, json={'bin_ids': ['NEW_BIN']}).status_code == 200
    assert [b['bin_id'] for b in client.get('/api/v1/bins', headers=r1).json()] == ['NEW_BIN']
    assert 'NEW_BIN' in [b['bin_id'] for b in client.get('/api/v1/bins', headers=c2).json()]
    assert client.put(f"/api/v1/admin/users/{user['id']}/bins", headers=admin, json={'bin_ids': ['missing']}).status_code == 422
    assert client.get(f"/api/v1/admin/users/{user['id']}/bins", headers=admin).json() == ['NEW_BIN']
    assert client.put(f"/api/v1/admin/users/{user['id']}", headers=admin, json={'display_name': 'Disabled', 'active': False}).status_code == 200
    assert client.get('/api/v1/auth/me', headers=r1).status_code == 401
    assert client.post('/api/v1/auth/login', json={'username': 'resident1', 'password': 'resident1'}).status_code == 401


def test_collections_use_authenticated_identity(env):
    client, _, legacy = env
    r1, _ = login(client, 'resident1')
    c1, _ = login(client, 'company1')
    c2, _ = login(client, 'company2')
    path = '/api/v1/bins/DEMO_BIN_001/collections'
    assert client.post(path, headers=r1).status_code == 403
    assert client.post(path, headers=c2).status_code == 404
    assert client.post(path, headers=c1).status_code == 200
    assert legacy.calls == [('DEMO_BIN_001', 'company1')]


def test_session_hash_expiry_logout_password(env):
    client, engine, _ = env
    headers, _ = login(client, 'admin')
    token = headers['Authorization'].split()[1]
    with sessions(engine).begin() as db:
        assert db.get(Session, token) is None
        db.get(Session, digest(token)).expires_at = now() - timedelta(seconds=1)
    assert client.get('/api/v1/auth/me', headers=headers).status_code == 401
    headers, _ = login(client, 'admin')
    assert client.post('/api/v1/auth/password', headers=headers, json={'current_password': 'admin', 'new_password': 'changed-admin'}).status_code == 204
    assert client.get('/api/v1/auth/me', headers=headers).status_code == 401
    headers, _ = login(client, 'admin', 'changed-admin')
    assert client.post('/api/v1/auth/logout', headers=headers).status_code == 204
    assert client.get('/api/v1/auth/me', headers=headers).status_code == 401


def test_single_admin_database_constraint(env):
    _, engine, _ = env
    with pytest.raises(IntegrityError):
        with sessions(engine).begin() as db:
            db.add(User(username='anotheradmin', role='Admin', display_name='No', password_hash='hash'))


def test_legacy_boundary_and_unavailable_sensor(env):
    client, _, legacy = env
    assert client.get('/health').status_code == 200
    assert client.get('/bins').status_code == 401
    r1, _ = login(client, 'resident1')
    assert client.get('/bins', headers=r1).status_code == 401
    assert client.get('/reports/any', headers=r1).status_code == 401
    assert client.get('/bins', headers={'X-API-Key': 'test-device-only'}).json()[0]['fill_level'] == 85
    legacy.available = False
    assert client.get('/api/v1/bins', headers=r1).status_code == 502


def test_coordinate_validation_and_rate_limit(env):
    client, _, _ = env
    admin, _ = login(client, 'admin')
    for coords in [{'latitude': 91, 'longitude': 20}, {'latitude': 10}, {'longitude': 10}]:
        assert client.post('/api/v1/admin/bins', headers=admin, json={'bin_id': 'X', 'name': 'X', **coords}).status_code == 422
    for _ in range(10):
        assert client.post('/api/v1/auth/login', json={'username': 'none', 'password': 'bad'}).status_code == 401
    assert client.post('/api/v1/auth/login', json={'username': 'none', 'password': 'bad'}).status_code == 429
