from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class VersionIdentityTests(unittest.TestCase):
    def test_version_file_is_current(self):
        self.assertIn((ROOT / "VERSION").read_text(encoding="utf-8").strip(), {"17.10.0", "17.11.0", "17.12.0", "17.13.0", "17.13.1", "17.13.2", "17.13.3", "17.14.0", "17.15.0", "17.16.0", "17.18.0", "17.20.0", "17.21.0", "17.22.0", "17.23.0"})

    def test_app_reports_version_from_version_file(self):
        app_text = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('APP_VERSION=(BASE/"VERSION").read_text', app_text)
        self.assertIn('@app.get("/api/build-info")', app_text)
        self.assertIn('@app.get("/build-info")', app_text)

    def test_run_script_clears_pycache_and_prints_identity(self):
        runps = (ROOT / "run.ps1").read_text(encoding="utf-8")
        self.assertIn("__pycache__", runps)
        self.assertIn("Runtime VERSION", runps)
        self.assertIn("Imported app.py", runps)
