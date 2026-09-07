import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class OperatorWorkflowTests(unittest.TestCase):
    def test_version_bumped_to_1740(self):
        self.assertIn((ROOT / "VERSION").read_text(encoding="utf-8").strip(), {"17.4.0", "17.5.0", "17.6.0", "17.6.1", "17.7.0", "17.9.0", "17.9.1", "17.10.0", "17.11.0", "17.12.0", "17.13.0", "17.13.1", "17.13.2", "17.13.3", "17.14.0", "17.15.0", "17.16.0", "17.18.0", "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2"})

    def test_workflow_route_and_api_are_registered(self):
        app_text = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('@app.get("/workflow")', app_text)
        self.assertIn('@app.get("/api/workflow/summary")', app_text)
        self.assertIn('def api_workflow_summary()', app_text)

    def test_workflow_template_and_static_assets_exist(self):
        html = (ROOT / "templates" / "workflow.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "workflow.js").read_text(encoding="utf-8")
        css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
        self.assertIn("Replacement Command Workflow", html)
        self.assertIn("/api/workflow/summary", js)
        self.assertIn("v17.4 operator workflow polish", css)

    def test_operator_workflow_doc_exists(self):
        doc = (ROOT / "docs" / "OPERATOR_WORKFLOW.md").read_text(encoding="utf-8")
        self.assertIn("Install TV Manager side-by-side with SickChill", doc)
        self.assertIn("Every risky action has a preview", doc)

if __name__ == "__main__":
    unittest.main()
