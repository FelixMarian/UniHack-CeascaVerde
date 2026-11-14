"""Salted incident commitments; only an exact, successful finalized memo is verified."""
import hashlib
import json
import secrets
from datetime import timezone
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from .models import Incident
from .security import current_user, db
from .services import owned_bin

RPC = 'https://api.devnet.solana.com'
MEMO_PROGRAM = 'MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr'
router = APIRouter(prefix='/api/v1')


def content_hash(item):
    created = item.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    payload = {'version': 1, 'nonce': item.proof_nonce, 'id': item.id,
               'bin_id': item.bin_id, 'user_id': item.user_id, 'category': item.category,
               'comment': item.comment, 'created_at': created.astimezone(timezone.utc).isoformat()}
    # Workflow status deliberately excluded: resolving an incident does not rewrite its report.
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def prepare(item):
    if item.proof_hash is None:
        item.proof_nonce = secrets.token_hex(32)
        item.proof_hash = content_hash(item)


def memo(item):
    return 'smartwaste:incident:v1:' + item.proof_hash


def rpc(method, params):
    with httpx.Client(timeout=12, follow_redirects=False) as client:
        response = client.post(RPC, json={'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})
        response.raise_for_status()
        body = response.json()
    if 'error' in body or 'result' not in body:
        raise ValueError('Solana RPC error')
    return body['result']


def transaction_matches(tx, item):
    if not isinstance(tx, dict) or not isinstance(tx.get('meta'), dict) or 'err' not in tx['meta'] or tx['meta']['err'] is not None:
        return False
    transaction = tx.get('transaction', {})
    if item.solana_signature not in transaction.get('signatures', []):
        return False
    instructions = transaction.get('message', {}).get('instructions', [])
    return any(i.get('programId') == MEMO_PROGRAM and i.get('parsed') == memo(item) for i in instructions)


def check(item):
    result = {'sha256': item.proof_hash, 'signature': item.solana_signature, 'network': 'devnet',
              'status': 'prepared', 'explorer_url': None}
    if not item.proof_hash or not item.proof_nonce or content_hash(item) != item.proof_hash:
        result['status'] = 'content_changed'
    elif item.solana_signature:
        try:
            tx = rpc('getTransaction', [item.solana_signature,
                {'encoding': 'jsonParsed', 'commitment': 'finalized', 'maxSupportedTransactionVersion': 0}])
            result['status'] = 'pending' if tx is None else 'verified' if transaction_matches(tx, item) else 'invalid'
            result['explorer_url'] = f'https://explorer.solana.com/tx/{item.solana_signature}?cluster=devnet'
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            result['status'] = 'unavailable'
    return result


@router.post('/incidents/{incident_id}/proof')
def proof(incident_id: int, user=Depends(current_user), session=Depends(db)):
    item = session.scalar(select(Incident).where(Incident.id == incident_id).with_for_update())
    if not item or (user.role == 'Resident' and item.user_id != user.id):
        raise HTTPException(404, 'Sesizare inexistentă.')
    if user.role == 'Company':
        owned_bin(session, user, item.bin_id)
    prepare(item)
    session.commit()
    return check(item)
