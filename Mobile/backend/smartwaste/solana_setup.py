"""Create a NEW Devnet-only keypair file, never overwrite an existing wallet."""
import json
import os
from pathlib import Path
from solders.keypair import Keypair


def main():
    path = Path.home() / '.config/smartwaste/solana-devnet.json'
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    wallet = Keypair()
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        wallet = Keypair.from_bytes(bytes(json.loads(path.read_text())))
        print('Existing wallet preserved.')
    else:
        with os.fdopen(fd, 'w') as output:
            json.dump(list(bytes(wallet)), output)
    print(f'Devnet public address: {wallet.pubkey()}')
    print(f'Private key file (do not share): {path}')
    print('Request TEST SOL at https://faucet.solana.com/ (Devnet). No real SOL is needed.')


if __name__ == '__main__':
    main()
