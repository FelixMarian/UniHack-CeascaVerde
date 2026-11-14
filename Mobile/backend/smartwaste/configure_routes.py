"""Interactive server-only configuration. Keys are never printed or sent to the APK."""
from getpass import getpass
from pathlib import Path
from dotenv import set_key


def main():
    env = Path(__file__).resolve().parents[2] / '.env'
    if not env.is_file():
        raise SystemExit('Server .env not found. Run the installed module inside ~/smartwaste/backend.')
    ors = getpass('openrouteservice API key (hidden): ').strip()
    if not ors:
        raise SystemExit('No key entered. No settings changed.')
    set_key(str(env), 'OPENROUTESERVICE_API_KEY', ors, quote_mode='always')
    env.chmod(0o600)
    print('Configuration saved. Restart smartwaste.service. Keys were not printed.')


if __name__ == '__main__':
    main()
