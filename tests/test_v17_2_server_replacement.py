from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]

class V172ServerReplacementTests(unittest.TestCase):
    def test_version_bumped(self):
        self.assertIn((ROOT / 'VERSION').read_text(encoding='utf-8').strip(), {'17.2.0', '17.3.0', '17.3.1', '17.3.2', '17.3.3', '17.3.4', '17.3.5', '17.4.0', '17.5.0', '17.6.0', '17.6.1', '17.7.0', '17.9.0', '17.10.0', '17.11.0', '17.12.0', '17.13.0', '17.13.1', '17.13.2', '17.13.3', '17.14.0', '17.15.0', '17.16.0', '17.18.0', "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2", "18.4.3", "18.5.0", "18.5.1", "18.5.2", "18.5.3", "18.5.4", "18.5.5", "18.5.6", "18.5.7", "18.5.8", "18.5.9", "18.5.10", "18.5.11", "18.5.12", "18.5.13", "18.5.15"})

    def test_replacement_docs_packaged(self):
        doc = ROOT / 'docs' / 'SICKCHILL_REPLACEMENT_SERVER_INSTALL.md'
        text = doc.read_text(encoding='utf-8')
        self.assertIn('Back up SickChill', text)
        self.assertIn('Import SickChill data', text)
        self.assertIn('Rollback plan', text)
        self.assertIn('systemctl disable sickchill', text)
        self.assertIn('/library-health', text)

    def test_linux_service_script_packaged(self):
        script = ROOT / 'scripts' / 'install-linux-service.sh'
        text = script.read_text(encoding='utf-8')
        self.assertIn('/etc/systemd/system/tvmanager.service', text)
        self.assertIn('ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/server.py', text)
        self.assertIn('systemctl enable tvmanager.service', text)

    def test_server_preflight_help_runs(self):
        proc = subprocess.run([sys.executable, str(ROOT / 'server_preflight.py'), '--help'], capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 0)
        self.assertIn('SickChill replacement preflight', proc.stdout)

    def test_release_manifest_tracks_replacement_features(self):
        text = (ROOT / 'RELEASE_MANIFEST.json').read_text(encoding='utf-8')
        self.assertIn('sickchill_replacement_server_runbook', text)
        self.assertIn('linux_systemd_installer', text)
        self.assertIn('server_preflight.py', text)

if __name__ == '__main__':
    unittest.main()
