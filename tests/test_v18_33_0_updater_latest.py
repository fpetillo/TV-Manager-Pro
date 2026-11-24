"""v18.33.0: update-server.ps1 installs the newest release tag by default."""
import io
import json
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / 'update-server.ps1').read_text(encoding='utf-8')


@pytest.fixture
def updater():
    code = SCRIPT.split("$Updater = @'", 1)[1].split("\n'@", 1)[0]
    module = types.ModuleType('standalone_updater')
    exec(compile(code, 'updater', 'exec'), module.__dict__)
    return module


def test_default_version_is_latest_not_a_pinned_release():
    assert re.search(r"\[string\]\$Version = ''", SCRIPT)
    assert "if ($Version) { $Arguments += @('--version', $Version) }" in SCRIPT
    assert "'--version', $Version, '--keep-backups'" not in SCRIPT


def test_latest_release_picks_highest_semver_tag(updater, monkeypatch):
    pages = {1: [{'name': 'v18.9.0'}, {'name': 'v18.32.0'}, {'name': 'v18.3.3'}, {'name': 'beta'}, {'name': 'v18.31.0'}]}

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    def urlopen(request, timeout=None):
        page = int(request.full_url.rsplit('page=', 1)[1])
        return Resp(json.dumps(pages.get(page, [])).encode())
    monkeypatch.setattr(updater.urllib.request, 'urlopen', urlopen)
    assert updater.latest_release() == '18.32.0'


def test_already_up_to_date_stops_before_backup(updater, tmp_path, monkeypatch):
    root = tmp_path / 'TV'
    (root / '.venv' / 'Scripts').mkdir(parents=True)
    for name in ['app.py', 'tvmanager.db', 'runtime_guard.py', '.venv/Scripts/python.exe']:
        (root / name).write_text('x')
    (root / 'VERSION').write_text('18.32.0')
    monkeypatch.setattr(updater, 'latest_release', lambda: '18.32.0')
    monkeypatch.setattr(updater, 'installation_lock', lambda root: pytest.fail('no backup or install when up to date'))
    assert updater.update(root, '') is None
