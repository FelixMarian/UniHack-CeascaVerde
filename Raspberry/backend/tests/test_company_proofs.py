import base64
from datetime import timezone
import pytest
from sqlalchemy import select
from test_api import env, login
from smartwaste.db import sessions
from smartwaste.models import Incident, Bin, UltrasonicMeasurement
from smartwaste.company import order_stops
from smartwaste import proofs
from smartwaste.solana_worker import sign_memo, publish_one


def incident(client):
    headers, _ = login(client, 'resident1')
    response = client.post('/api/v1/incidents', headers=headers,
        json={'bin_id': 'DEMO_BIN_001', 'category': 'damaged', 'comment': 'Capac rupt — test'})
    assert response.status_code == 201
    return response.json()['id'], headers


def transaction(item, error=None, memo=None):
    return {'meta': {'err': error}, 'transaction': {'signatures': [item.solana_signature],
        'message': {'instructions': [{'programId': proofs.MEMO_PROGRAM,
            'parsed': proofs.memo(item) if memo is None else memo}]}}}


def test_damage_owner_only_and_sensor_does_not_clear(env):
    client, engine, _ = env
    for name, code in [('resident1', 403), ('admin', 403), ('company2', 404), ('company1', 200)]:
        headers, _ = login(client, name)
        assert client.patch('/api/v1/bins/DEMO_BIN_001/damage', headers=headers, json={'damaged': True}).status_code == code
    with sessions(engine).begin() as db:
        db.add(UltrasonicMeasurement(bin_id='DEMO_BIN_001', fill_category=1,
            distance_mid_cm=20, distance_full_cm=20, distance_top_cm=30, config_hash='a'*64))
    owner, _ = login(client, 'company1')
    assert client.get('/api/v1/bins', headers=owner).json()[0]['fill_category'] == 4
    client.patch('/api/v1/bins/DEMO_BIN_001/damage', headers=owner, json={'damaged': False})
    assert client.get('/api/v1/bins', headers=owner).json()[0]['fill_category'] == 1


def test_hq_scope_validation_and_route(env):
    client, engine, _ = env
    owner, user = login(client, 'company1')
    other, _ = login(client, 'company2')
    resident, _ = login(client, 'resident1')
    url = f"/api/v1/companies/{user['id']}/hq"
    assert client.post('/api/v1/company/route', headers=owner).status_code == 409
    for denied in (other, resident):
        assert client.put(url, headers=denied, json={'latitude': 45, 'longitude': 21}).status_code == 403
    for payload in ({'latitude': 45}, {'latitude': 91, 'longitude': 21}):
        assert client.put(url, headers=owner, json=payload).status_code == 422
    assert client.put(url, headers=owner, json={'latitude': 45, 'longitude': 21}).status_code == 200
    route = client.post('/api/v1/company/route', headers=owner).json()
    assert [b['bin_id'] for b in route['stops']] == ['DEMO_BIN_001']
    assert route['straight_line_meters'] > 0
    client.patch('/api/v1/bins/DEMO_BIN_001/damage', headers=owner, json={'damaged': True})
    assert client.post('/api/v1/company/route', headers=owner).json()['stops'] == []
    client.patch('/api/v1/bins/DEMO_BIN_001/damage', headers=owner, json={'damaged': False})
    with sessions(engine).begin() as db:
        item = db.get(Bin, 'DEMO_BIN_001')
        item.latitude = item.longitude = None
    route = client.post('/api/v1/company/route', headers=owner).json()
    assert route['stops'] == [] and route['skipped_bin_ids'] == ['DEMO_BIN_001']
    assert client.post('/api/v1/company/route', headers=resident).status_code == 403


def test_order_and_return_distance():
    stops, total = order_stops((0, 0), [{'bin_id': 'far', 'latitude': 0, 'longitude': 2},
                                     {'bin_id': 'near', 'latitude': 0, 'longitude': 1}])
    assert [s['bin_id'] for s in stops] == ['near', 'far']
    assert 444000 < total < 445000


def test_proof_scope_and_creation(env):
    client, engine, _ = env
    id, resident = incident(client)
    url = f'/api/v1/incidents/{id}/proof'
    for name in ('resident2', 'company2'):
        headers, _ = login(client, name)
        assert client.post(url, headers=headers).status_code == 404
    first = client.post(url, headers=resident).json()
    second = client.post(url, headers=resident).json()
    assert first == second and first['status'] == 'prepared' and len(first['sha256']) == 64
    owner, _ = login(client, 'company1')
    client.patch(f'/api/v1/incidents/{id}', headers=owner, json={'status': 'resolved'})
    assert client.post(url, headers=resident).json()['sha256'] == first['sha256']
    with sessions(engine).begin() as db:
        db.get(Incident, id).comment = 'Changed after proof'
    assert client.post(url, headers=resident).json()['status'] == 'content_changed'


@pytest.mark.parametrize('mode,expected', [('ok','verified'), ('pending','pending'), ('failed','invalid'), ('wrong','invalid'), ('offline','unavailable')])
def test_chain_verification(env, monkeypatch, mode, expected):
    client, engine, _ = env
    id, headers = incident(client)
    with sessions(engine).begin() as db:
        item = db.get(Incident, id)
        item.solana_signature = 'a'*88
        tx = transaction(item, error={'InstructionError': [0, 'error']} if mode == 'failed' else None,
                         memo='other' if mode == 'wrong' else None)
    def rpc(method, params):
        assert method == 'getTransaction' and params[1]['commitment'] == 'finalized'
        if mode == 'offline': raise ValueError('offline')
        return None if mode == 'pending' else tx
    monkeypatch.setattr(proofs, 'rpc', rpc)
    assert client.post(f'/api/v1/incidents/{id}/proof', headers=headers).json()['status'] == expected


def test_real_signing_roundtrip_and_retry_bytes(env, monkeypatch):
    from solders.keypair import Keypair
    from solders.hash import Hash
    from solders.transaction import Transaction
    from smartwaste import solana_worker as worker
    client, engine, _ = env
    id, _ = incident(client)
    wallet = Keypair()
    sent = []
    def rpc(method, params):
        if method == 'getLatestBlockhash': return {'value': {'blockhash': str(Hash.default())}}
        if method == 'getTransaction': return None
        if method == 'sendTransaction':
            # The signature and bytes must already be committed when RPC receives a broadcast.
            with sessions(engine)() as db:
                item = db.get(Incident, id)
                assert item.proof_transaction == params[0]
                tx = Transaction.from_bytes(base64.b64decode(params[0]))
                tx.verify()
                assert bytes(tx.message.instructions[0].data).decode() == proofs.memo(item)
                assert str(tx.signatures[0]) == item.solana_signature
                sent.append(params[0])
                if len(sent) == 1: raise ValueError('network timeout after sending')
                return item.solana_signature
        raise AssertionError(method)
    monkeypatch.setattr(proofs, 'rpc', rpc)
    monkeypatch.setattr(worker, 'rpc', rpc)
    with pytest.raises(ValueError): publish_one(sessions(engine), id, wallet)
    assert publish_one(sessions(engine), id, wallet) == 'submitted'
    assert sent[0] == sent[1]
