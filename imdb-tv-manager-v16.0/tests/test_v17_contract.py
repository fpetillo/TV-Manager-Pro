import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class V17ContractTests(unittest.TestCase):
    def test_v17_routes_and_modules_exist(self):
        app=(ROOT/"app.py").read_text(encoding="utf-8")
        for text in [
            "sickchill_importer",
            "/api/import/sickchill/analyze",
            "/api/import/sickchill/preview",
            "/api/library/duplicates",
            "/api/metadata/refresh/run",
        ]:
            self.assertIn(text,app)
        self.assertTrue((ROOT/"sickchill_importer.py").exists())
        self.assertTrue((ROOT/"library_maintenance.py").exists())

    def test_v17_docs_and_version(self):
        self.assertEqual((ROOT/"VERSION").read_text(encoding="utf-8").strip(),"17.0")
        self.assertIn("SickChill import analysis", (ROOT/"docs"/"RELEASE_NOTES_v17.md").read_text(encoding="utf-8"))
        self.assertIn("v17 Development Track", (ROOT/"docs"/"ROADMAP.md").read_text(encoding="utf-8"))

    def test_migration_tracks_v16_and_v17(self):
        text=(ROOT/"migrations.py").read_text(encoding="utf-8")
        self.assertIn("VERSION=17",text)
        self.assertIn("legacy_identity_map",text)
        self.assertIn("import_run_details",text)
        self.assertIn("16,\"16.0\"",text)

if __name__ == "__main__":
    unittest.main()
