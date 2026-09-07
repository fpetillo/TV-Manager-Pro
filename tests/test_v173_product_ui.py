from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V173ProductUITests(unittest.TestCase):
    def test_version_bumped_to_173(self):
        self.assertIn((ROOT / "VERSION").read_text().strip(), {"17.3.0", "17.3.1", "17.3.2", "17.3.3", "17.3.4", "17.3.5", "17.4.0", "17.5.0", "17.6.0", "17.6.1", "17.7.0", "17.9.0", "17.9.1", "17.10.0", "17.11.0", "17.12.0", "17.13.0", "17.13.1", "17.13.2", "17.13.3", "17.14.0", "17.15.0", "17.16.0", "17.18.0", "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2"})

    def test_product_experience_css_present(self):
        css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
        self.assertIn("v17.3 product experience refresh", css)
        self.assertIn(".product-hero", css)
        self.assertIn(".professional-nav a.active", css)

    def test_active_navigation_script_present(self):
        js = (ROOT / "static" / "global.js").read_text(encoding="utf-8")
        self.assertIn("v17.3 navigation polish", js)
        self.assertIn("aria-current", js)

    def test_key_pages_have_product_hero(self):
        for rel in [
            "templates/dashboard.html",
            "templates/manager.html",
            "templates/import.html",
            "templates/library_health.html",
            "templates/about.html",
        ]:
            self.assertIn("product-hero", (ROOT / rel).read_text(encoding="utf-8"), rel)

    def test_design_system_doc_exists(self):
        doc = (ROOT / "docs" / "UI_DESIGN_SYSTEM.md").read_text(encoding="utf-8")
        self.assertIn("Operator clarity", doc)
        self.assertIn("Migration confidence", doc)

if __name__ == '__main__':
    unittest.main()
