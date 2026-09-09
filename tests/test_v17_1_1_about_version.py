import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class V1711VersionVisibilityTests(unittest.TestCase):
    def test_about_page_and_api_route_exist(self):
        app=(ROOT/'app.py').read_text(encoding='utf-8')
        self.assertIn('@app.get("/about")', app)
        self.assertIn('@app.get("/api/version")', app)
        self.assertIn('APP_VERSION', app)

    def test_templates_show_visible_version(self):
        self.assertIn((ROOT/'VERSION').read_text(encoding='utf-8').strip(), {'17.1.8','17.1.9','17.2.0', '17.3.0', '17.3.1', '17.3.2', '17.3.3', '17.3.4', '17.3.5', '17.4.0', '17.5.0', '17.6.0', '17.6.1', '17.7.0', '17.9.0', '17.9.1', '17.10.0', '17.11.0', '17.12.0', '17.13.0', '17.13.1', '17.13.2', '17.13.3', '17.14.0', '17.15.0', '17.16.0', '17.18.0', "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2", "18.4.3", "18.5.0", "18.5.1", "18.5.2", "18.5.3", "18.5.4", "18.5.5", "18.5.6", "18.5.7", "18.5.8", "18.5.9", "18.5.10", "18.5.11", "18.5.12"})
        about=(ROOT/'templates'/'about.html').read_text(encoding='utf-8')
        system=(ROOT/'templates'/'system.html').read_text(encoding='utf-8')
        dashboard=(ROOT/'templates'/'dashboard.html').read_text(encoding='utf-8')
        self.assertIn('v{{ app_version }}', about)
        self.assertIn('v{{ app_version }}', system)
        self.assertIn('app-version-footer', dashboard)
        self.assertIn('/about', dashboard)

    def test_release_notes_exist(self):
        notes=(ROOT/'docs'/'RELEASE_NOTES_v17.1.1.md')
        self.assertTrue(notes.exists())
        text=notes.read_text(encoding='utf-8')
        self.assertIn('/api/version', text)
        self.assertIn('/about', text)

if __name__ == '__main__':
    unittest.main()
