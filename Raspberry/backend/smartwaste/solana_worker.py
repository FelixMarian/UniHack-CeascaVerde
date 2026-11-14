"""Devnet-only publisher. Run once or --watch; wallet stays on the server.

Persist signed transaction BEFORE broadcast; retries reuse identical bytes/signature.
No automatic replacement of expired transactions (avoid ambiguous duplicate publication).
"""
import argparse
import base64
import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import select
from .db import make_engine, sessions
from .models import Incident
from .proofs import MEMO_PROGRAM, content_hash, prepare, memo, rpc, check


def sign_memo(item, wallet, blockhash):
    from solders.hash import Hash
    from solders.instruction import Instruction, AccountMeta
    from solders.message import Message
    from solders.pubkey import Pubkey
    from solders.transaction import Transaction
    instruction = Instruction(Pubkey.from_string(MEMO_PROGRAM), memo(item).encode(),
                              [AccountMeta(wallet.pubkey(), True, False)])
    message = Message([instruction], wallet.pubkey())
    tx = Transaction([wallet], message, Hash.from_string(blockhash))
    return str(tx.signatures[0]), base64.b64encode(bytes(tx)).decode()


def publish_one(factory, incident_id, wallet):
    with factory() as session:
        item = session.scalar(select(Incident).where(Incident.id == incident_id).with_for_update())
        prepare(item)
        if content_hash(item) != item.proof_hash:
            return 'content_changed'
        if not item.solana_signature:
            blockhash = rpc('getLatestBlockhash', [{'commitment': 'finalized'}])['value']['blockhash']
            item.solana_signature, item.proof_transaction = sign_memo(item, wallet, blockhash)
            session.commit()
        result = check(item)
        if result['status'] in ('verified', 'invalid', 'content_changed', 'unavailable'):
            return result['status']
        if not item.proof_transaction:
            return 'missing_transaction'
        signature = rpc('sendTransaction', [item.proof_transaction, {'encoding': 'base64', 'preflightCommitment': 'finalized', 'maxRetries': 3}])
        if signature != item.solana_signature:
            raise ValueError('Unexpected transaction signature')
        return 'submitted'  # Never call a broadcast response a confirmation.


def main():
    from solders.keypair import Keypair
    load_dotenv(Path(__file__).resolve().parents[2] / '.env')
    parser = argparse.ArgumentParser()
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    wallet_path = os.getenv('SMARTWASTE_SOLANA_KEYPAIR')
    if not wallet_path:
        raise SystemExit('Set SMARTWASTE_SOLANA_KEYPAIR to the server-only Devnet keypair JSON path.')
    wallet = Keypair.from_bytes(bytes(json.loads(Path(wallet_path).read_text())))
    factory = sessions(make_engine())
    print(f'SmartWaste Devnet publisher: {wallet.pubkey()}', flush=True)
    verified = set()
    while True:
        with factory() as session:
            ids = list(session.scalars(select(Incident.id).order_by(Incident.id)))
        for incident_id in ids:
            if incident_id in verified:
                continue
            try:
                status = publish_one(factory, incident_id, wallet)
                from .automatic_proofs import save_status
                if status == 'verified':
                    save_status(factory, incident_id, 'verified')
                elif status in ('invalid', 'content_changed'):
                    save_status(factory, incident_id, 'failed', 'SOLANA_INVALID_PROOF')
                else:
                    save_status(factory, incident_id, 'pending', 'SOLANA_CONFIRMATION_PENDING')
                if status == 'verified':
                    verified.add(incident_id)
                print(f'Incident {incident_id}: {status}', flush=True)
            except Exception:
                # Do not log secrets, RPC bodies, DB URLs or comments.
                print(f'Incident {incident_id}: publication failed; check network, Devnet balance or expired blockhash. Stored signature retained.', flush=True)
        if not args.watch:
            break
        time.sleep(30)


if __name__ == '__main__':
    main()
