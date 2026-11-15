"""Interactive server-only configuration. Keys are never printed or sent to the APK."""
import argparse
import re
from getpass import getpass
from pathlib import Path
from dotenv import set_key


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gemini', action='store_true', help='Configure only Gemini')
    args = parser.parse_args()
    env = Path(__file__).resolve().parents[2] / '.env'
    if not env.is_file():
        raise SystemExit('Server .env not found. Run the installed module inside ~/smartwaste/backend.')
    if args.gemini:
        key = getpass('Gemini API key (hidden): ').strip()
        model = input('Gemini model ID (without models/): ').strip()
        if not key or not re.fullmatch(r'[A-Za-z0-9._-]+', model):
            raise SystemExit('Missing key or invalid model ID. No settings changed.')
        values = {'GEMINI_API_KEY': key, 'GEMINI_MODEL': model}
    else:
        ors = getpass('openrouteservice API key (hidden): ').strip()
        if not ors:
            raise SystemExit('No key entered. No settings changed.')
        values = {'OPENROUTESERVICE_API_KEY': ors}
    for name, value in values.items():
        set_key(str(env), name, value, quote_mode='always')
    env.chmod(0o600)
    print('Configuration saved. Restart smartwaste.service. Keys were not printed.')


if __name__ == '__main__':
    main()
