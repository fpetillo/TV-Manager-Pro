import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PostProcessWorkflowTests(unittest.TestCase):
    def test_version_advanced_for_postprocess_release(self):
        self.assertIn((ROOT / "VERSION").read_text(encoding="utf-8").strip(), {"17.10.0", "17.11.0", "17.12.0", "17.13.0", "17.13.1", "17.13.2", "17.13.3", "17.14.0", "17.15.0", "17.16.0", "17.18.0", "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2"})

    def test_postprocess_api_accepts_config_and_override(self):
        app_py = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('@app.get("/api/postprocess/config")', app_py)
        self.assertIn('@app.post("/api/postprocess/config")', app_py)
        self.assertIn('root=request.args.get("root")', app_py)
        self.assertIn('selected_sources', app_py)
        self.assertIn('process_method_override', app_py)

    def test_engine_supports_safe_preview_apply_arguments(self):
        engine_py = (ROOT / "engine.py").read_text(encoding="utf-8")
        self.assertIn('root_override=None', engine_py)
        self.assertIn('selected_sources=None', engine_py)
        self.assertIn('process_method_override=None', engine_py)
        self.assertIn('if selected_sources and str(p) not in selected_sources', engine_py)

    def test_postprocess_ui_has_operator_folder_workflow(self):
        html = (ROOT / "templates" / "postprocess.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "postprocess.js").read_text(encoding="utf-8")
        self.assertIn('Configured completed TV folder', html)
        self.assertIn('Override folder for this run', html)
        self.assertIn('Process Selected', html)
        self.assertIn('Process All Approved', html)
        self.assertIn('/api/postprocess/config', js)
        self.assertIn('selectedSources', js)
        self.assertIn('Preview Folder', html)

    def test_responsive_layout_documentation_exists(self):
        doc = (ROOT / "docs" / "POST_PROCESSING_WORKFLOW.md").read_text(encoding="utf-8")
        self.assertIn('SickChill operators', doc)
        self.assertIn('Override folder', doc)
        self.assertIn('Process Selected', doc)


if __name__ == "__main__":
    unittest.main()
