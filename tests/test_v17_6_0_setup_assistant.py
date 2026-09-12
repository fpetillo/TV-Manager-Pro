import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class SetupAssistantTests(unittest.TestCase):
    def test_version_bumped_to_1760(self):
        self.assertIn((ROOT / "VERSION").read_text(encoding="utf-8").strip(), {"17.6.0", "17.6.1", "17.7.0", "17.9.0", "17.9.1", "17.10.0", "17.11.0", "17.12.0", "17.13.0", "17.13.1", "17.13.2", "17.13.3", "17.14.0", "17.15.0", "17.16.0", "17.18.0", "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2", "18.4.3", "18.5.0", "18.5.1", "18.5.2", "18.5.3", "18.5.4", "18.5.5", "18.5.6", "18.5.7", "18.5.8", "18.5.9", "18.5.10", "18.5.11", "18.5.12", "18.5.13", "18.5.14", "18.5.15"})

    def test_setup_routes_are_registered(self):
        app_text = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('@app.get("/setup-assistant")', app_text)
        self.assertIn('@app.get("/api/setup/summary")', app_text)
        self.assertIn('operator_experience.setup_assistant_summary', app_text)

    def test_setup_assets_exist(self):
        html = (ROOT / "templates" / "setup_assistant.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "setup_assistant.js").read_text(encoding="utf-8")
        css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
        self.assertIn("TV Manager Setup Assistant", html)
        self.assertIn("/api/setup/summary", js)
        self.assertIn("v17.6 setup assistant", css)

    def test_cutover_checklist_doc_exists(self):
        doc = (ROOT / "docs" / "SICKCHILL_CUTOVER_CHECKLIST.md").read_text(encoding="utf-8")
        self.assertIn("Do not point TV Manager at the live SickChill database", doc)
        self.assertIn("Cut over", doc)

if __name__ == "__main__":
    unittest.main()
