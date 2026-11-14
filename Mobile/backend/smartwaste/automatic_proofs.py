"""Automatic server-side publication, with durable status and retry-safe signatures."""
import json
import os
import time
from pathlib import Path
from .models import Incident
from .proofs import check, content_hash

MESSAGES = {
 'SOLANA_INSUFFICIENT_FUNDS': 'Portofelul serverului nu are suficient SOL de test Devnet pentru taxa tranzacției.',
 'SOLANA_TRANSACTION_EXPIRED': 'Tranzacția Solana a expirat înainte de publicare. Administratorul trebuie să verifice republicarea pe server.',
 'SOLANA_NOT_CONFIGURED': 'Portofelul Solana nu este configurat pe Raspberry Pi.',
 'SOLANA_WALLET_INVALID': 'Portofelul Solana al serverului nu poate fi citit.',
 'SOLANA_PUBLICATION_FAILED': 'Publicarea Solana a eșuat. Verifică rețeaua, soldul Devnet și valabilitatea tranzacției pe server.',
 'SOLANA_UNAVAILABLE': 'Rețeaua Solana nu poate fi contactată momentan.',
 'SOLANA_CONFIRMATION_PENDING': 'Solana nu a confirmat încă tranzacția. Sesizarea rămâne salvată și verificarea continuă pe server.',
 'SOLANA_INVALID_PROOF': 'Tranzacția Solana nu confirmă conținutul sesizării.',
}


def result(item):
    if item.proof_hash and content_hash(item) != item.proof_hash:
        return {'status': 'failed', 'error_code': 'SOLANA_INVALID_PROOF', 'message': MESSAGES['SOLANA_INVALID_PROOF'],
                'sha256': item.proof_hash, 'signature': item.solana_signature, 'network': 'devnet'}
    return {'status': item.blockchain_status, 'error_code': item.blockchain_error,
            'message': MESSAGES.get(item.blockchain_error), 'sha256': item.proof_hash,
            'signature': item.solana_signature, 'network': 'devnet'}


def save_status(factory, id, status, error=None):
    with factory.begin() as session:
        item = session.get(Incident, id)
        item.blockchain_status, item.blockchain_error = status, error


def process(factory, id, wait_seconds=35):
    path = os.getenv('SMARTWASTE_SOLANA_KEYPAIR', str(Path.home() / '.config/smartwaste/solana-devnet.json'))
    if not Path(path).is_file():
        save_status(factory, id, 'failed', 'SOLANA_NOT_CONFIGURED')
        return
    try:
        from solders.keypair import Keypair
        wallet = Keypair.from_bytes(bytes(json.loads(Path(path).read_text())))
    except (ImportError, OSError, ValueError, TypeError):
        save_status(factory, id, 'failed', 'SOLANA_WALLET_INVALID')
        return
    try:
        from .solana_worker import publish_one
        status = publish_one(factory, id, wallet)
        if status == 'verified':
            save_status(factory, id, 'verified')
            return
        if status in ('invalid', 'content_changed', 'missing_transaction'):
            save_status(factory, id, 'failed', 'SOLANA_INVALID_PROOF')
            return
        deadline = time.monotonic() + wait_seconds
        while True:
            with factory() as session:
                checked = check(session.get(Incident, id))['status']
            if checked == 'verified':
                save_status(factory, id, 'verified')
                return
            if checked in ('invalid', 'content_changed'):
                save_status(factory, id, 'failed', 'SOLANA_INVALID_PROOF')
                return
            if time.monotonic() >= deadline:
                save_status(factory, id, 'pending', 'SOLANA_UNAVAILABLE' if checked == 'unavailable' else 'SOLANA_CONFIRMATION_PENDING')
                return
            time.sleep(2)
    except Exception as exc:
        code = getattr(exc, 'code', 'SOLANA_PUBLICATION_FAILED')
        save_status(factory, id, 'failed', code if code in MESSAGES else 'SOLANA_PUBLICATION_FAILED')
