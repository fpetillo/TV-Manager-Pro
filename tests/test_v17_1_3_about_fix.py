from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class AboutPageFixTests(unittest.TestCase):
    def test_about_route_is_server_rendered_with_fallback(self):
        app_text = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('@app.get("/about")', app_text)
        self.assertIn('def _about_payload()', app_text)
        self.assertIn('return render_template("about.html", about=data)', app_text)
        self.assertIn('fallback.format(version=APP_VERSION', app_text)

    def test_about_template_has_visible_version_without_javascript(self):
        about = (ROOT / "templates" / "about.html").read_text(encoding="utf-8")
        self.assertIn('TV Manager v{{ about.version if about else app_version }}', about)
        self.assertIn('server-rendered', about)
        self.assertIn('/api/about', about)
        self.assertNotIn('<script', about.lower())

    def test_about_api_and_public_paths_exist(self):
        app_text = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('@app.get("/api/about")', app_text)
        self.assertIn('jsonify(**_about_payload())', app_text)
        self.assertIn('"/about"', app_text)
        self.assertIn('"/api/about"', app_text)
        self.assertIn('"/api/version"', app_text)

if __name__ == "__main__":
    unittest.main()
