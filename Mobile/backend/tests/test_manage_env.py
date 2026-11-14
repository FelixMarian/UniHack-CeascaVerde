from smartwaste.manage import load_environment


def test_explicit_server_env_from_unrelated_package_directory(tmp_path, monkeypatch):
    server = tmp_path / 'live server'
    package = tmp_path / 'download'
    server.mkdir()
    package.mkdir()
    (server / '.env').write_text('TIGER_DATABASE_URL=sqlite:///server-test.db\n')
    (package / '.env').write_text('TIGER_DATABASE_URL=sqlite:///wrong-test.db\n')
    monkeypatch.chdir(package)
    monkeypatch.delenv('TIGER_DATABASE_URL', raising=False)
    load_environment(server / '.env')
    import os
    assert os.environ['TIGER_DATABASE_URL'] == 'sqlite:///server-test.db'


def test_explicit_env_overrides_stale_inherited_value(tmp_path, monkeypatch):
    path = tmp_path / '.env'
    path.write_text('TIGER_DATABASE_URL=sqlite:///chosen-test.db\n')
    monkeypatch.setenv('TIGER_DATABASE_URL', 'sqlite:///stale-test.db')
    load_environment(path)
    import os
    assert os.environ['TIGER_DATABASE_URL'] == 'sqlite:///chosen-test.db'
