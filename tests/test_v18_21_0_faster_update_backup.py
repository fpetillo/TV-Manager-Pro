"""v18.21.0: the update backup copies only what an update can change, and is verified."""
from contextlib import closing, nullcontext
import json
import sqlite3

import pytest

from test_windows_updater import VERSION, archive, installation, updater  # noqa: F401 (fixtures)


@pytest.fixture
def unlocked(updater, monkeypatch):  # noqa: F811
    # The real lock uses msvcrt (Windows only); the backup logic is the same everywhere.
    monkeypatch.setattr(updater, 'installation_lock', lambda root: nullcontext())
    return updater


def _add_runtime_data(root):
    for name in ['managed_trash/upgrades/Old.Show.S01E01.mkv', 'imports/batch.csv', 'logs/app.log',
                 'diagnostics/report.txt', 'uploads/file.bin', 'corrupt-db/old.db', 'archive-staging/x.rar']:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'x' * 1024)
    (root / 'tvmanager.log').write_text('log')
    (root / 'old-release.zip').write_bytes(b'zip')


def _backup_names(backup):
    base = backup / 'installation'
    return {p.relative_to(base).as_posix() for p in base.rglob('*') if p.is_file()}


def test_runtime_data_is_left_in_place_not_copied(unlocked, installation, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(unlocked, 'checked_run', lambda command, root: None)
    _add_runtime_data(installation)
    backup = unlocked.update(installation, VERSION, str(archive(tmp_path / 'release.zip')))
    names = _backup_names(backup)
    assert {'app.py', 'VERSION', '.env', 'config.ini', '.tvmanager-session-key', 'tvmanager.db'} <= names
    for folder in ['managed_trash', 'imports', 'logs', 'diagnostics', 'uploads', 'corrupt-db',
                   'archive-staging', 'recovery', 'backups', '.git']:
        assert not any(n.startswith(folder + '/') for n in names), folder
    assert 'tvmanager.log' not in names and 'old-release.zip' not in names
    # Left in place and unchanged.
    assert (installation / 'managed_trash/upgrades/Old.Show.S01E01.mkv').read_bytes() == b'x' * 1024
    record = json.loads((backup / 'update.json').read_text())
    for relative, expected in record['backup_sha256'].items():
        assert unlocked.digest(backup / 'installation' / relative) == expected
    assert 'managed_trash' in record['left_in_place']
    assert set(record['timings_seconds']) >= {'backup_files', 'backup_database', 'install_files'}


def test_unchanged_requirements_skip_pip_and_environment_backup(unlocked, installation, tmp_path, monkeypatch):  # noqa: F811
    calls = []
    monkeypatch.setattr(unlocked, 'checked_run', lambda command, root: calls.append(command))
    (installation / 'requirements.txt').write_text('')  # same as the release
    backup = unlocked.update(installation, VERSION, str(archive(tmp_path / 'release.zip')))
    assert calls == []
    assert not (backup / 'installation/.venv').exists()
    assert (installation / '.venv/Scripts/python.exe').read_text() == 'fixture-runtime'
    record = json.loads((backup / 'update.json').read_text())
    assert record['dependencies_changed'] is False and '.venv' in record['left_in_place']
    assert (installation / 'VERSION').read_text() == VERSION


def test_changed_requirements_back_up_environment_and_run_pip(unlocked, installation, tmp_path, monkeypatch):  # noqa: F811
    calls = []
    monkeypatch.setattr(unlocked, 'checked_run', lambda command, root: calls.append(command))
    (installation / 'requirements.txt').write_text('Flask==3.0.0\n')
    backup = unlocked.update(installation, VERSION, str(archive(tmp_path / 'release.zip', {'requirements.txt': 'Flask==3.1.0\n'})))
    assert len(calls) == 2 and calls[1][-2:] == ['pip', 'check']
    assert (backup / 'installation/.venv/Scripts/python.exe').read_text() == 'fixture-runtime'


def test_refresh_dependencies_forces_pip(unlocked, installation, tmp_path, monkeypatch):  # noqa: F811
    calls = []
    monkeypatch.setattr(unlocked, 'checked_run', lambda command, root: calls.append(command))
    (installation / 'requirements.txt').write_text('')
    backup = unlocked.update(installation, VERSION, str(archive(tmp_path / 'release.zip')), refresh_dependencies=True)
    assert len(calls) == 2
    assert (backup / 'installation/.venv').is_dir()


def test_failed_pip_restores_environment_when_requirements_changed(unlocked, installation, tmp_path, monkeypatch):  # noqa: F811
    def broken(command, root):
        (root / '.venv/Scripts/python.exe').write_text('modified')
        raise RuntimeError('pip failed')
    monkeypatch.setattr(unlocked, 'checked_run', broken)
    with pytest.raises(RuntimeError):
        unlocked.update(installation, VERSION, str(archive(tmp_path / 'release.zip')))
    assert (installation / '.venv/Scripts/python.exe').read_text() == 'fixture-runtime'
    assert (installation / 'VERSION').read_text() == '18.11.0'


def test_failed_install_rolls_back_source_without_environment_copy(unlocked, installation, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(unlocked, 'checked_run', lambda *a: pytest.fail('pip must not run'))
    (installation / 'requirements.txt').write_text('')
    original = unlocked.install_files
    def fail_midway(root, stage, files, changed):
        original(root, stage, ['app.py', 'new_module.py'], changed)
        raise OSError('copy failure')
    monkeypatch.setattr(unlocked, 'install_files', fail_midway)
    with pytest.raises(OSError):
        unlocked.update(installation, VERSION, str(archive(tmp_path / 'release.zip')))
    assert (installation / 'app.py').read_text() == '# old source'
    assert not (installation / 'new_module.py').exists()
    journal = next(tmp_path.glob('* Update Backups/*/update.json'))
    assert json.loads(journal.read_text())['status'] == 'rolled_back'


def test_wal_rows_are_in_the_database_backup(unlocked, installation, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(unlocked, 'checked_run', lambda *a: None)
    writer = sqlite3.connect(installation / 'tvmanager.db')
    writer.execute('PRAGMA journal_mode=WAL')
    writer.execute("INSERT INTO settings VALUES('wal_row','preserved')")
    writer.commit()
    assert (installation / 'tvmanager.db-wal').is_file()
    try:
        backup = unlocked.update(installation, VERSION, str(archive(tmp_path / 'release.zip')))
    finally:
        writer.close()
    assert not (backup / 'installation/tvmanager.db-wal').exists()
    with closing(sqlite3.connect(backup / 'installation/tvmanager.db')) as copy:
        assert copy.execute("SELECT value FROM settings WHERE name='wal_row'").fetchone()[0] == 'preserved'


def test_corrupt_database_stops_before_any_change(unlocked, installation, tmp_path, monkeypatch):  # noqa: F811
    (installation / 'tvmanager.db').write_bytes(b'not a database' * 100)
    monkeypatch.setattr(unlocked, 'checked_run', lambda *a: pytest.fail('must not install'))
    with pytest.raises(sqlite3.DatabaseError):
        unlocked.update(installation, VERSION, str(archive(tmp_path / 'release.zip')))
    assert (installation / 'app.py').read_text() == '# old source'


def _old_backup(parent, name, status):
    folder = parent / name
    (folder / 'installation').mkdir(parents=True)
    (folder / 'update.json').write_text(json.dumps({'status': status}))
    return folder


def test_old_backups_pruned_keeping_newest_and_unfinished(unlocked, installation, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(unlocked, 'checked_run', lambda *a: None)
    parent = installation.parent / (installation.name + ' Update Backups')
    for day in range(1, 7):
        _old_backup(parent, f'2026010{day}-000000-v18.0.{day}-aaaa', 'installed_restart_required')
    keep_failed = _old_backup(parent, '20260101-000000-v17.0.0-bbbb', 'manual_recovery_required')
    keep_rolled = _old_backup(parent, '20260101-000001-v17.0.1-cccc', 'rolled_back')
    backup = unlocked.update(installation, VERSION, str(archive(tmp_path / 'release.zip')), keep_backups=3)
    finished = sorted(p.name for p in parent.iterdir()
                      if json.loads((p / 'update.json').read_text())['status'] == 'installed_restart_required')
    assert finished == ['20260105-000000-v18.0.5-aaaa', '20260106-000000-v18.0.6-aaaa', backup.name]
    assert keep_failed.is_dir() and keep_rolled.is_dir()


def test_keep_backups_zero_keeps_everything(unlocked, installation, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(unlocked, 'checked_run', lambda *a: None)
    parent = installation.parent / (installation.name + ' Update Backups')
    for day in range(1, 4):
        _old_backup(parent, f'2026010{day}-000000-v18.0.{day}-aaaa', 'installed_restart_required')
    unlocked.update(installation, VERSION, str(archive(tmp_path / 'release.zip')), keep_backups=0)
    assert len(list(parent.iterdir())) == 4


def test_powershell_passes_new_options():
    from test_windows_updater import SCRIPT
    text = SCRIPT.read_text(encoding='utf-8')
    assert '[int]$KeepBackups = 5' in text and '[switch]$RefreshDependencies' in text
    assert "'--keep-backups', [string]$KeepBackups" in text and "'--refresh-dependencies'" in text


def test_auto_update_leaves_pruning_to_its_own_setting():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / 'auto_update.py').read_text(encoding='utf-8')
    assert '"-KeepBackups", "0"' in source
