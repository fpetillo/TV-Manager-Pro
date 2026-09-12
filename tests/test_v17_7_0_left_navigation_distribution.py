from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class LeftNavigationDistributionTests(unittest.TestCase):
    def test_v177_version(self):
        self.assertIn((ROOT / "VERSION").read_text(encoding="utf-8").strip(), {"17.10.0", "17.11.0", "17.12.0", "17.13.0", "17.13.1", "17.13.2", "17.13.3", "17.14.0", "17.15.0", "17.16.0", "17.18.0", "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2", "18.4.3", "18.5.0", "18.5.1", "18.5.2", "18.5.3", "18.5.4", "18.5.5", "18.5.6", "18.5.7", "18.5.8", "18.5.9", "18.5.10", "18.5.11", "18.5.12", "18.5.13", "18.5.14", "18.5.15"})

    def test_left_sidebar_css_present(self):
        css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
        self.assertIn("v17.7 left navigation system", css)
        self.assertIn("--sidebar-width", css)
        self.assertIn(".nav-section", css)

    def test_categorized_nav_in_templates(self):
        nav = (ROOT / "templates" / "_nav.html").read_text(encoding="utf-8")
        for label in ["Command Center", "Library", "Discovery & Search", "Processing", "Setup & Migration", "Administration"]:
            self.assertIn(label, nav)
        for link in ["/logs", "/jobs", "/database-safety", "/show-queue", "/manage", "/postprocess"]:
            self.assertIn(link, nav)
        included = 0
        for template in (ROOT / "templates").glob("*.html"):
            if template.name in {"login.html", "security_setup.html", "_nav.html"}:
                continue
            text = template.read_text(encoding="utf-8")
            if '{% include "_nav.html" %}' in text:
                included += 1
        self.assertGreaterEqual(included, 10)

    def test_distribution_docs_and_installer_assets(self):
        for rel in [
            "docs/INSTALL_ALL_PLATFORMS.md",
            "docs/WINDOWS_EXE_INSTALLER.md",
            "docs/LEFT_NAVIGATION_DESIGN.md",
            "installer/windows/build-exe.ps1",
            "installer/windows/TVManager.iss",
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)
        install_doc = (ROOT / "docs" / "INSTALL_ALL_PLATFORMS.md").read_text(encoding="utf-8")
        for word in ["Windows", "Ubuntu", "RHEL", "macOS", "SickChill"]:
            self.assertIn(word, install_doc)

if __name__ == "__main__":
    unittest.main()
