"""Exercise the standalone PowerShell updater's embedded Python without live data."""
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import types
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'update-server.ps1'
VERSION = '18.12.0'


@pytest.fixture
def updater():
    source = SCRIPT.read_text(encoding='utf-8').split("$Updater = @'\n", 1)[1].split("\n'@", 1)[0]
    module = types.ModuleType('standalone_updater')
    exec(compile(source, str(SCRIPT), 'exec'), module.__dict__)
    return module


def archive(path, extra=None):
    files = {'VERSION': VERSION, 'RELEASE_MANIFEST.json': json.dumps({'version': VERSION}),
             'app.py': 'new_code = True\n', 'server.py': '# fixture\n', 'runtime_guard.py': '# fixture\n',
             'requirements.txt': '', 'run-prod.ps1': '# fixture\n',
             'templates/settings.html': '<p>New</p>', 'static/app.js': '/* New */',
             'new_module.py': 'new = 1\n'}
    files.update(extra or {})
    with zipfile.ZipFile(path, 'w') as handle:
        for name, content in files.items():
            info = zipfile.ZipInfo('placeholder')
            info.filename = 'TV-Manager-Pro-' + VERSION + '/' + name
            handle.writestr(info, content)
    return path


@pytest.fixture
def installation(tmp_path):
    root = tmp_path / 'TV Manager installation'
    (root / '.venv/Scripts').mkdir(parents=True)
    for name, data in {'VERSION': '18.11.0', 'app.py': '# old source',
                       'runtime_guard.py': '# fixture', '.env': 'private fixture setting',
                       'config.ini': '[fixture]', '.tvmanager-session-key': 'fixture-key',
                       '.venv/Scripts/python.exe': 'fixture-runtime',
                       'recovery/keep.txt': 'recovery fixture', 'imports/keep.txt': 'import fixture',
                       'backups/old.txt': 'previous backup', '.git/keep.txt': 'git fixture'}.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data)
    with closing(sqlite3.connect(root / 'tvmanager.db')) as connection:
        connection.execute('CREATE TABLE settings(name TEXT, value TEXT)')
        connection.execute("INSERT INTO settings VALUES('listen_host','192.168.1.11')")
        connection.commit()
    return root


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows updater/lease')
def test_update_preserves_state_and_verifies_cold_backup(updater, installation, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(updater, 'checked_run', lambda command, root: calls.append(command))
    before = {name: (installation / name).read_bytes() for name in
              ['tvmanager.db', '.env', 'config.ini', '.tvmanager-session-key',
               'imports/keep.txt', 'recovery/keep.txt', 'backups/old.txt', '.git/keep.txt']}
    package = archive(tmp_path / 'release.zip', {'.env': 'overwrite forbidden', 'tvmanager.db': 'bad',
                                               'imports/keep.txt': 'bad', '.venv/Scripts/python.exe': 'bad',
                                               '.env-before-github-old': 'do not deploy'})
    backup = updater.update(installation, VERSION, str(package))
    assert (installation / 'VERSION').read_text() == VERSION
    assert (installation / 'app.py').read_text() == 'new_code = True\n'
    for name, content in before.items():
        assert (installation / name).read_bytes() == content
        if not name.startswith(('backups/', '.git/')):
            assert (backup / 'installation' / name).read_bytes() == content
    assert not (installation / '.env-before-github-old').exists()
    assert (backup / 'installation/.venv/Scripts/python.exe').read_text() == 'fixture-runtime'
    assert not (backup / 'installation/backups').exists()
    record = json.loads((backup / 'update.json').read_text())
    assert record['status'] == 'installed_restart_required'
    assert record['archive_sha256'] == updater.digest(package)
    assert len(calls) == 2 and calls[1][-2:] == ['pip', 'check']


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows updater/lease')
@pytest.mark.parametrize('failure', ['dependencies', 'source'])
def test_failed_update_restores_code_and_environment(updater, installation, tmp_path, monkeypatch, failure):
    package = archive(tmp_path / 'release.zip')
    original_db = (installation / 'tvmanager.db').read_bytes()
    def dependency(command, root):
        (root / '.venv/partial-package.txt').write_text('partial')
        (root / '.venv/Scripts/python.exe').write_text('modified')
        if failure == 'dependencies':
            raise RuntimeError('dependency failure')
    monkeypatch.setattr(updater, 'checked_run', dependency)
    original_install = updater.install_files
    def copy_failure(root, stage, files, changed):
        original_install(root, stage, ['app.py', 'new_module.py'], changed)
        raise OSError('copy failure')
    if failure == 'source':
        monkeypatch.setattr(updater, 'install_files', copy_failure)
    with pytest.raises((RuntimeError, OSError)):
        updater.update(installation, VERSION, str(package))
    assert (installation / 'VERSION').read_text() == '18.11.0'
    assert (installation / 'app.py').read_text() == '# old source'
    assert not (installation / 'new_module.py').exists()
    assert (installation / '.venv/Scripts/python.exe').read_text() == 'fixture-runtime'
    assert not (installation / '.venv/partial-package.txt').exists()
    assert (installation / 'tvmanager.db').read_bytes() == original_db
    journals = list(tmp_path.glob('* Update Backups/*/update.json'))
    assert json.loads(journals[0].read_text())['status'] == 'rolled_back'


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows updater/lease')
def test_running_application_blocks_before_backup(updater, installation, tmp_path):
    import media_operations
    folder = installation / '.runtime'
    folder.mkdir()
    with media_operations.exclusive(folder):
        with pytest.raises(ValueError, match='running'):
            updater.update(installation, VERSION, str(tmp_path / 'not-downloaded.zip'))
    assert not list(tmp_path.glob('* Update Backups'))
    assert (installation / 'VERSION').read_text() == '18.11.0'


@pytest.mark.parametrize('bad_path', ['../escape.py', 'static/../../escape.py', 'static/C:escape.py',
                                    'static\\escape.py', 'static/NUL.txt', 'static/trailing.'])
def test_archive_rejects_unsafe_paths(updater, tmp_path, bad_path):
    package = archive(tmp_path / 'release.zip', {bad_path: 'bad'})
    stage = tmp_path / 'stage'
    stage.mkdir()
    with pytest.raises(ValueError, match='path'):
        updater.stage_archive(package, stage, VERSION)
    assert not (tmp_path / 'escape.py').exists()


@pytest.mark.parametrize('extra', [{'APP.py': '# ambiguous'}, {'VERSION': '18.10.1'},
                                 {'app.py': 'invalid !!! python'},
                                 {'RELEASE_MANIFEST.json': '{"version":"18.0.0"}'}])
def test_invalid_release_rejected_before_install(updater, tmp_path, extra):
    stage = tmp_path / 'stage'
    stage.mkdir()
    with pytest.raises((ValueError, SyntaxError)):
        updater.stage_archive(archive(tmp_path / 'release.zip', extra), stage, VERSION)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows updater/lease')
def test_corrupt_database_blocks_update(updater, installation, tmp_path, monkeypatch):
    (installation / 'tvmanager.db').write_bytes(b'not a database')
    monkeypatch.setattr(updater, 'checked_run', lambda *args: pytest.fail('must not install'))
    with pytest.raises(sqlite3.DatabaseError):
        updater.update(installation, VERSION, str(archive(tmp_path / 'release.zip')))
    assert (installation / 'VERSION').read_text() == '18.11.0'


def test_downgrade_refused(updater, installation):
    with pytest.raises(ValueError, match='Downgrades'):
        updater.update(installation, '18.10.0')


def test_source_updater_refuses_packaged_service(updater, installation):
    (installation / 'TVManagerService.exe').write_bytes(b'fixture')
    with pytest.raises(ValueError, match='packaged Windows service'):
        updater.update(installation, VERSION)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows updater/lease')
def test_wal_database_backup_retains_committed_rows(updater, installation, tmp_path, monkeypatch):
    code = "import sqlite3,os,sys; c=sqlite3.connect(sys.argv[1]); c.execute('PRAGMA journal_mode=WAL'); c.execute(\"INSERT INTO settings VALUES('wal_row','preserved')\"); c.commit(); os._exit(0)"
    subprocess.run([sys._base_executable, '-c', code, str(installation / 'tvmanager.db')], check=True)
    assert (installation / 'tvmanager.db-wal').is_file()
    monkeypatch.setattr(updater, 'checked_run', lambda *args: None)
    backup = updater.update(installation, VERSION, str(archive(tmp_path / 'release.zip')))
    record = json.loads((backup / 'update.json').read_text())
    for relative, expected in record['backup_sha256'].items():
        assert updater.digest(backup / 'installation' / relative) == expected
    with closing(sqlite3.connect(backup / 'installation/tvmanager.db')) as connection:
        assert connection.execute("SELECT value FROM settings WHERE name='wal_row'").fetchone()[0] == 'preserved'


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows updater/lease')
def test_insufficient_space_blocks_before_dependency_changes(updater, installation, tmp_path, monkeypatch):
    monkeypatch.setattr(updater.shutil, 'disk_usage', lambda path: types.SimpleNamespace(free=0))
    monkeypatch.setattr(updater, 'checked_run', lambda *args: pytest.fail('must not install'))
    with pytest.raises(ValueError, match='free disk space'):
        updater.update(installation, VERSION, str(archive(tmp_path / 'release.zip')))
    assert (installation / 'app.py').read_text() == '# old source'


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows updater/lease')
def test_bad_backup_hash_blocks_before_dependency_changes(updater, installation, tmp_path, monkeypatch):
    copy = updater.copy_file
    def corrupt_backup(source, destination):
        copy(source, destination)
        if 'Update Backups' in str(destination) and destination.name == '.env':
            destination.write_text('corrupt')
    monkeypatch.setattr(updater, 'copy_file', corrupt_backup)
    monkeypatch.setattr(updater, 'checked_run', lambda *args: pytest.fail('must not install'))
    with pytest.raises(OSError, match='Backup verification failed'):
        updater.update(installation, VERSION, str(archive(tmp_path / 'release.zip')))
    assert (installation / '.env').read_text() == 'private fixture setting'
    assert (installation / 'app.py').read_text() == '# old source'


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows PowerShell 5.1')
def test_actual_powershell_wrapper_and_dependency_commands(tmp_path):
    # No production module import or web server. A real disposable Python
    # environment and empty fixture requirements test quoting, backup and pip.
    root = tmp_path / 'TV Manager with spaces'
    root.mkdir()
    subprocess.run([sys._base_executable, '-m', 'venv', str(root / '.venv')], check=True, capture_output=True)
    for name, data in {'VERSION': '18.11.0', 'app.py': '# old', 'runtime_guard.py': '# fixture',
                       '.env': 'fixture unchanged'}.items():
        (root / name).write_text(data)
    with closing(sqlite3.connect(root / 'tvmanager.db')) as connection:
        connection.execute('CREATE TABLE marker(value TEXT)')
        connection.commit()
    package = archive(tmp_path / 'release with spaces.zip')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                             str(SCRIPT), '-InstallDir', str(root), '-ArchivePath', str(package)],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'TV Manager remains stopped' in result.stdout
    assert 'No broken requirements' in result.stdout
    assert (root / 'VERSION').read_text() == VERSION
    assert (root / '.env').read_text() == 'fixture unchanged'
    result = subprocess.run([str(root / '.venv/Scripts/python.exe'), '--version'], capture_output=True)
    assert result.returncode == 0
