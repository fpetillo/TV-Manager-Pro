"""Real routes in a separate installation; never import the production app."""
from pathlib import Path
import shutil
import subprocess
import sys


def test_optional_login_lan_and_reenable(tmp_path):
    root = Path(__file__).resolve().parents[1]
    for source in root.glob('*.py'):
        shutil.copy2(source, tmp_path / source.name)
    for name in ['VERSION', 'settings_defaults.json', 'RELEASE_MANIFEST.json']:
        shutil.copy2(root / name, tmp_path / name)
    for name in ['templates', 'static']:
        shutil.copytree(root / name, tmp_path / name)
    check = tmp_path / 'verify_optional.py'
    check.write_text('''
import app
client=app.app.test_client()
lan={'REMOTE_ADDR':'192.168.1.99'}
assert not app.security.admin_configured()
assert not app.security.browser_auth_enabled()
assert client.get('/settings',environ_overrides=lan).status_code==200
assert client.get('/api/shows',environ_overrides=lan).status_code==200
assert client.post('/api/settings/network',json={'host':'0.0.0.0','port':5050},environ_overrides=lan).status_code==200
assert client.post('/api/security/browser-auth',json={'enabled':True},environ_overrides=lan).status_code==400
assert client.post('/api/security/password',json={'username':'fixture','password':'Optional-test-password'},environ_overrides=lan).status_code==200
assert client.post('/api/security/browser-auth',json={'enabled':True},environ_overrides=lan).status_code==200
assert client.get('/settings',environ_overrides=lan).status_code==302
assert client.get('/api/shows',environ_overrides=lan).status_code==401
assert client.post('/api/security/browser-auth',json={'enabled':False},environ_overrides=lan).status_code==401
assert client.post('/login',data={'username':'fixture','password':'Optional-test-password'},environ_overrides=lan).status_code==302
assert client.post('/api/security/browser-auth',json={'enabled':False},environ_overrides=lan).status_code==403
with client.session_transaction() as session:token=session['csrf_token']
app.app.config['TVMANAGER_NETWORK']={'host':'0.0.0.0','port':5050}
assert client.post('/api/security/browser-auth',json={'enabled':False},headers={'X-CSRF-Token':token},environ_overrides=lan).status_code==200
anonymous=app.app.test_client()
assert anonymous.get('/settings',environ_overrides=lan).status_code==200
assert anonymous.get('/api/shows',environ_overrides=lan).status_code==200
assert anonymous.post('/api/security/password',json={'password':'Must-not-replace'},environ_overrides=lan).status_code==401
assert anonymous.post('/api/security/browser-auth',json={'enabled':True},environ_overrides=lan).status_code==200
assert anonymous.get('/settings',environ_overrides=lan).status_code==302
assert client.get('/settings',environ_overrides=lan).status_code==200
''', encoding='utf-8')
    result = subprocess.run([sys.executable, str(check)], cwd=tmp_path, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
