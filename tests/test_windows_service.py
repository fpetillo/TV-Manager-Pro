import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

import pytest
import service_runtime

ROOT = Path(__file__).resolve().parents[1]


def test_service_manifest_has_stop_logs_and_no_credentials():
    xml = ET.parse(ROOT / 'installer/windows/TVManagerService.xml').getroot()
    assert xml.findtext('id') == 'TVManagerPro'
    assert xml.findtext('startarguments') == '--service'
    assert xml.findtext('stoparguments') == '--stop-service'
    assert xml.findtext('delayedAutoStart') == 'true'
    assert xml.find('serviceaccount') is None
    assert xml.find('log').attrib['mode'] == 'roll-by-size'


def test_drain_rejects_new_work_and_releases_failed_response():
    service_runtime.STOPPING.clear()
    called = []
    def application(environ, start):
        called.append(True)
        return [b'OK']
    middleware = service_runtime.DrainMiddleware(application)
    response = middleware({}, lambda *args: None)
    assert middleware.active == 1
    assert list(response) == [b'OK']
    assert middleware.active == 0
    service_runtime.STOPPING.set()
    statuses = []
    assert middleware({}, lambda status, headers: statuses.append(status)) == [b'TV Manager is stopping. Try again after it restarts.']
    assert statuses == ['503 Service Unavailable'] and called == [True]
    service_runtime.STOPPING.clear()


def test_stop_during_initialization_records_request(tmp_path):
    assert service_runtime.request_stop(tmp_path) == 0
    request = json.loads((tmp_path / '.runtime/service-stop.json').read_text())
    assert request['instance'] is None and request['requested_at'] > 0


def test_real_service_runtime_drains_job_and_stops(tmp_path):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    script = tmp_path / 'fixture.py'
    script.write_text('''
import sys,time,threading
from pathlib import Path
import service_runtime
base=Path(sys.argv[1])
def application(environ,start):
    if environ['PATH_INFO']=='/job':
        def worker():
            time.sleep(1)
            (base/'job-finished').write_text('finished')
        threading.Thread(target=worker,name='tvmanager-fixture',daemon=True).start()
    start('200 OK',[('Content-Type','text/plain')])
    return [b'OK']
raise SystemExit(service_runtime.serve(application,base,threading.Event(),'127.0.0.1',int(sys.argv[2]),drain_seconds=5))
''')
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    process = subprocess.Popen([sys.executable, str(script), str(tmp_path), str(port)], env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        url = f'http://127.0.0.1:{port}'
        for attempt in range(80):
            try:
                with urllib.request.urlopen(url, timeout=.5) as response:
                    assert response.read() == b'OK'
                break
            except OSError:
                time.sleep(.05)
        else:
            pytest.fail('Fixture HTTP server did not start')
        with urllib.request.urlopen(url + '/job', timeout=2) as response:
            assert response.status == 200
        service_runtime.request_stop(tmp_path)
        output, errors = process.communicate(timeout=12)
        assert process.returncode == 0, output + errors
        assert (tmp_path / 'job-finished').read_text() == 'finished'
        assert not (tmp_path / '.runtime/service.json').exists()
        assert 'Service shutdown complete.' in output
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows PowerShell')
def test_service_script_parses_and_compiles_rights_helper(tmp_path):
    script = ROOT / 'installer/windows/Manage-Service.ps1'
    source = script.read_text()
    csharp = source.split("Add-Type -TypeDefinition @'\n", 1)[1].split("\n'@", 1)[0]
    cs = tmp_path / 'rights.cs'
    cs.write_text(csharp)
    check = tmp_path / 'parse.ps1'
    check.write_text("$ErrorActionPreference='Stop'\n$tokens=$null;$errors=$null\n"
                     + "[System.Management.Automation.Language.Parser]::ParseFile('" + str(script) + "',[ref]$tokens,[ref]$errors) | Out-Null\n"
                     + "if($errors.Count){throw ($errors | Out-String)}\nAdd-Type -Path '" + str(cs) + "'\n")
    result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(check)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows PowerShell')
def test_service_install_default_path_fails_before_any_registration(tmp_path):
    import shutil
    script = tmp_path / 'Manage-Service.ps1'
    shutil.copy2(ROOT / 'installer/windows/Manage-Service.ps1', script)
    result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script), '-Action', 'Install'],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert 'Run as administrator' in result.stderr or 'Package file missing' in result.stderr
    assert 'empty string' not in result.stderr
