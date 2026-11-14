"""Run from backend/: python -m smartwaste.manage inspect|migrate|seed."""
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import inspect, select, text
from .db import Base, make_engine, sessions
from .models import User, Bin, Assignment
from .security import passwords


def inspect_schema(engine):
    inspector = inspect(engine)
    result = {}
    for table in ('bins', 'bin_measurements', 'collections', 'reports'):
        result[table] = {'columns': [
            {'name': c['name'], 'type': str(c['type']), 'nullable': c['nullable'], 'default': c.get('default')}
            for c in inspector.get_columns(table)], 'foreign_keys': inspector.get_foreign_keys(table)} if inspector.has_table(table) else None
    return result


def migrate(engine):
    # Add application metadata to bins; never alter measurements or collections.
    with engine.begin() as conn:
        if engine.dialect.name == 'postgresql':
            for migration in ('001_mobile.sql', '002_ultrasonic.sql', '003_company_proofs.sql'):
                sql = (Path(__file__).parent.parent / 'migrations' / migration).read_text(encoding='utf-8')
                # SQLAlchemy owns the outer transaction across both additive migrations.
                conn.exec_driver_sql(sql.replace('\nBEGIN;', '').replace('\nCOMMIT;', ''))
        else:
            Base.metadata.create_all(conn)  # SQLite is exclusively a test fixture.


def seed(engine):
    with sessions(engine).begin() as session:
        if engine.dialect.name == 'postgresql':
            session.execute(text('SELECT pg_advisory_xact_lock(2026111302)'))
        accounts = {}
        for username, role, password in [('admin', 'Admin', 'admin'), ('resident1', 'Resident', 'resident1'),
            ('resident2', 'Resident', 'resident2'), ('company1', 'Company', 'company1'), ('company2', 'Company', 'company2')]:
            user = session.scalar(select(User).where(User.username == username))
            if user is None:
                if role == 'Admin' and session.scalar(select(User).where(User.role == 'Admin')):
                    raise ValueError('An Admin already exists under another username; seed aborted.')
                user = User(username=username, role=role, password_hash=passwords.hash(password), display_name=f'Demo {username}', demo=True)
                session.add(user)
                session.flush()
            elif user.role != role or not user.demo:
                raise ValueError(f'Refusing to repurpose existing non-demo account: {username}')
            accounts[username] = user
        for i in (1, 2):
            bin_id = f'DEMO_BIN_00{i}'
            bin = session.get(Bin, bin_id)
            if bin is None:
                bin = Bin(bin_id=bin_id, name=f'Demo tomberon {i}', company_id=accounts[f'company{i}'].id,
                          latitude=45.748 + i * .001, longitude=21.208 + i * .001, demo=True)
                session.add(bin)
                session.flush()
                session.add(Assignment(user_id=accounts[f'resident{i}'].id, bin_id=bin_id))
            elif not bin.demo:
                raise ValueError(f'Refusing to repurpose an existing non-demo bin: {bin_id}')
        # Deliberately no measurements, no collections, and no changes to BIN_001.


def load_environment(env_file=None):
    # Do not search from the downloaded package or depend on the current directory.
    path = Path(env_file) if env_file is not None else Path(__file__).resolve().parents[2] / '.env'
    load_dotenv(path, override=env_file is not None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['inspect', 'migrate', 'seed'])
    parser.add_argument('--env-file', type=Path, help='Explicit server .env path for package installation')
    args = parser.parse_args()
    if args.env_file is not None and not args.env_file.is_file():
        raise SystemExit('The specified server .env file does not exist.')
    load_environment(args.env_file)
    import os
    if not os.environ.get('TIGER_DATABASE_URL'):
        raise SystemExit('TIGER_DATABASE_URL is missing. Pass --env-file /home/djoldskull/smartwaste/.env')
    engine = make_engine()
    if args.command == 'inspect':
        print(json.dumps(inspect_schema(engine), indent=2, default=str))
    elif args.command == 'migrate':
        schema = inspect_schema(engine)
        if any(schema[t] is None for t in schema):
            raise SystemExit('Existing backend tables missing; check database/search_path before migration.')
        migrate(engine)
        print('Additive migration applied. Sensor, collection and report rows unchanged.')
    elif args.command == 'seed':
        seed(engine)
        print('Demo accounts and demo bin registrations ready. No measurements inserted.')


if __name__ == '__main__':
    main()
