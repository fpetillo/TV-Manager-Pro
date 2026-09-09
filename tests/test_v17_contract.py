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
        self.assertIn((ROOT/"VERSION").read_text(encoding="utf-8").strip(),{"17.0","17.1","17.1.1","17.1.3","17.1.4","17.1.5","17.1.7","17.1.8", "17.1.9", "17.2.0", "17.3.0", "17.3.1", "17.3.2", "17.3.3", "17.3.4", "17.3.5", "17.4.0", "17.5.0", "17.6.0", "17.6.1", "17.7.0", "17.9.0", "17.9.1", "17.10.0", "17.11.0", "17.12.0", "17.13.0", "17.13.1", "17.13.2", "17.13.3", "17.14.0", "17.15.0", "17.16.0", "17.18.0", "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2", "18.4.3", "18.5.0", "18.5.1", "18.5.2", "18.5.3", "18.5.4", "18.5.5", "18.5.6", "18.5.7", "18.5.8", "18.5.9", "18.5.10", "18.5.11"})
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
