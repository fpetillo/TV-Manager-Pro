import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class V171ContractTests(unittest.TestCase):
    def test_v171_routes_templates_and_docs_exist(self):
        app=(ROOT/'app.py').read_text(encoding='utf-8')
        for text in ['/library-health','/api/library/health-report','/api/library/duplicates/preview','/api/library/duplicates/apply']:
            self.assertIn(text, app)
        self.assertTrue((ROOT/'templates'/'library_health.html').exists())
        self.assertTrue((ROOT/'static'/'library_health.js').exists())
        self.assertTrue((ROOT/'docs'/'RELEASE_NOTES_v17.1.md').exists())

    def test_version_and_migration_are_v171(self):
        self.assertIn((ROOT/'VERSION').read_text(encoding='utf-8').strip(), {'17.1.8','17.1.9','17.2.0', '17.3.0', '17.3.1', '17.3.2', '17.3.3', '17.3.4', '17.3.5', '17.4.0', '17.5.0', '17.6.0', '17.6.1', '17.7.0', '17.9.0', '17.9.1', '17.10.0', '17.11.0', '17.12.0', '17.13.0', '17.13.1', '17.13.2', '17.13.3', '17.14.0', '17.15.0', '17.16.0', '17.18.0', "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2", "18.4.3", "18.5.0", "18.5.1", "18.5.2", "18.5.3", "18.5.4", "18.5.5", "18.5.6", "18.5.7", "18.5.8", "18.5.9", "18.5.10", "18.5.11"})
        migration=(ROOT/'migrations.py').read_text(encoding='utf-8')
        self.assertIn('VERSION=171', migration)
        self.assertIn('duplicate_cleanup_actions', migration)
        self.assertIn('17.1', migration)

    def test_import_center_buttons_exist(self):
        html=(ROOT/'templates'/'import.html').read_text(encoding='utf-8')
        js=(ROOT/'static'/'import.js').read_text(encoding='utf-8')
        for token in ['analyzeBtn','previewBtn','importBtn']:
            self.assertIn(token, html)
            self.assertIn(token, js)

if __name__ == '__main__':
    unittest.main()
