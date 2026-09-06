import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class V16ContractTests(unittest.TestCase):
    def test_security_routes_and_middleware(self):
        app=(ROOT/"app.py").read_text(encoding="utf-8")
        for text in ["@app.before_request","/login","/security/setup","/api/security/status",
                     "/api/security/password","/api/security/browser-auth","X-CSRF-Token"]:
            self.assertIn(text,app)

    def test_naming_ui_routes(self):
        app=(ROOT/"app.py").read_text(encoding="utf-8")
        settings=(ROOT/"templates"/"settings.html").read_text(encoding="utf-8")
        js=(ROOT/"static"/"settings-v5.js").read_text(encoding="utf-8")
        for route in ["/api/naming/config","/api/naming/preview-sample"]:
            self.assertIn(route,app)
        self.assertIn('data-view="naming"',settings)
        self.assertIn("loadNaming",js)

    def test_csrf_client_wrapper(self):
        js=(ROOT/"static"/"global.js").read_text(encoding="utf-8")
        self.assertIn("tvmanager_csrf",js)
        self.assertIn("X-CSRF-Token",js)

    def test_lan_guard(self):
        server=(ROOT/"server.py").read_text(encoding="utf-8")
        self.assertIn("browser_auth_enabled",server)
        self.assertIn("Refusing non-loopback HOST",server)

    def test_metadata_scheduler_is_real(self):
        engine=(ROOT/"engine.py").read_text(encoding="utf-8")
        service=(ROOT/"metadata_service.py").read_text(encoding="utf-8")
        self.assertIn("metadata_service.refresh_batch()",engine)
        self.assertIn("metadata_refresh_state",service)
        self.assertNotIn("scheduled batch refresh reserved",engine)

    def test_scheduler_postprocess_gate(self):
        engine=(ROOT/"engine.py").read_text(encoding="utf-8")
        self.assertIn('get_setting("General","process_automatically"',engine)
        self.assertIn('get_setting("TVManager","simulation_mode"',engine)
