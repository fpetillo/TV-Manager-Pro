from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]

class V1714RouteHardeningTests(unittest.TestCase):
    def test_version_bumped(self):
        self.assertIn((ROOT/"VERSION").read_text(encoding="utf-8").strip(), {"17.1.8", "17.1.9", "17.2.0", "17.3.0", "17.3.1", "17.3.2", "17.3.3", "17.3.4", "17.3.5", "17.4.0", "17.5.0", "17.6.0", "17.6.1", "17.7.0", "17.9.0", "17.9.1", "17.10.0", "17.11.0", "17.12.0", "17.13.0", "17.13.1", "17.13.2", "17.13.3", "17.14.0", "17.15.0", "17.16.0", "17.18.0", "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1"})

    def test_library_health_has_fallback_and_aliases(self):
        app=(ROOT/"app.py").read_text(encoding="utf-8")
        for text in ['@app.get("/library-health/")','@app.get("/library_health")','@app.get("/health/library")','def _render_library_health_fallback']:
            self.assertIn(text, app)

    def test_about_and_api_have_trailing_slash_aliases(self):
        app=(ROOT/"app.py").read_text(encoding="utf-8")
        for text in ['@app.get("/about/")','@app.get("/version")','@app.get("/api/version/")','@app.get("/api/about/")','@app.get("/api/library-health/report")']:
            self.assertIn(text, app)

if __name__ == "__main__":
    unittest.main()
