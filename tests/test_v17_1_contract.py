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
        self.assertEqual((ROOT/'VERSION').read_text(encoding='utf-8').strip(),'17.1')
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
