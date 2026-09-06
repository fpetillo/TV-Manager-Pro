import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class V14ContractTests(unittest.TestCase):
    def test_api_routes_present(self):
        app=(ROOT/"app.py").read_text(encoding="utf-8")
        for route in [
            "/api/queue/unified",
            "/api/acquisitions/<kind>/<int:acquisition_id>/events",
            "/api/upgrades/replacements",
            "/api/upgrades/replacements/<int:replacement_id>/rollback",
            "/api/media-servers/<int:sid>/refresh-target",
            "/api/naming/preview/<int:episode_id>",
            "/api/library/fingerprint-conflicts",
            "/api/scheduler/leases",
        ]:
            self.assertIn(route,app)

    def test_ui_wiring_present(self):
        queue=(ROOT/"static"/"queue.js").read_text(encoding="utf-8")
        upgrades=(ROOT/"static"/"upgrades.js").read_text(encoding="utf-8")
        self.assertIn("/api/queue/unified",queue)
        self.assertIn("historyFor",queue)
        self.assertIn("rollbackReplacement",upgrades)

    def test_version(self):
        self.assertIn((ROOT/"VERSION").read_text().strip(), {"16.0", "17.0", "17.1"})
