import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class LaunchpadExperienceTests(unittest.TestCase):
    def test_version_bumped_to_1750(self):
        self.assertIn((ROOT / "VERSION").read_text(encoding="utf-8").strip(), {"17.5.0", "17.6.0", "17.6.1", "17.7.0", "17.9.0", "17.9.1", "17.10.0", "17.11.0", "17.12.0", "17.13.0", "17.13.1", "17.13.2", "17.13.3", "17.14.0", "17.15.0", "17.16.0", "17.18.0", "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1"})

    def test_launchpad_routes_are_registered(self):
        app_text = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('@app.get("/launchpad")', app_text)
        self.assertIn('@app.get("/api/launchpad/summary")', app_text)
        self.assertIn('operator_experience.launchpad_summary', app_text)

    def test_launchpad_assets_exist(self):
        html = (ROOT / "templates" / "launchpad.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "launchpad.js").read_text(encoding="utf-8")
        css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
        self.assertIn("TV Manager Launchpad", html)
        self.assertIn("/api/launchpad/summary", js)
        self.assertIn("v17.5 launchpad experience polish", css)

    def test_product_experience_doc_exists(self):
        doc = (ROOT / "docs" / "PRODUCT_EXPERIENCE.md").read_text(encoding="utf-8")
        self.assertIn("recommended home screen", doc)
        self.assertIn("Health before cutover", doc)

if __name__ == "__main__":
    unittest.main()
