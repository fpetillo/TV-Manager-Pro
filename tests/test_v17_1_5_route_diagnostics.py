import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class V1715RouteDiagnosticsTests(unittest.TestCase):
    def test_route_diagnostics_and_404_fallback_registered(self):
        text = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('@app.get("/routes")', text)
        self.assertIn('@app.get("/api/routes")', text)
        self.assertIn('@app.errorhandler(404)', text)
        self.assertIn('def _route_inventory()', text)
        self.assertIn('404 fallback rendered', text)

    def test_server_fails_fast_if_required_routes_missing(self):
        text = (ROOT / "server.py").read_text(encoding="utf-8")
        self.assertIn('Required route check', text)
        self.assertIn('required_routes', text)
        self.assertIn('/library-health', text)
        self.assertIn('/about', text)
        self.assertIn('/api/library/health-report', text)

    def test_version_bumped_to_1715(self):
        self.assertIn((ROOT / "VERSION").read_text(encoding="utf-8").strip(), {"17.1.8", "17.1.9", "17.2.0", "17.3.0", "17.3.1", "17.3.2", "17.3.3", "17.3.4", "17.3.5", "17.4.0", "17.5.0", "17.6.0", "17.6.1", "17.7.0", "17.9.0", "17.9.1", "17.10.0", "17.11.0", "17.12.0", "17.13.0", "17.13.1", "17.13.2", "17.13.3", "17.14.0", "17.15.0", "17.16.0", "17.18.0", "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3"})
