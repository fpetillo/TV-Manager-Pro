import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LargeLibraryPagingTests(unittest.TestCase):
    def test_version_advanced_for_large_library_release(self):
        self.assertIn((ROOT / "VERSION").read_text(encoding="utf-8").strip(), {"17.10.0", "17.11.0", "17.12.0", "17.13.0", "17.13.1", "17.13.2", "17.13.3", "17.14.0", "17.15.0", "17.16.0", "17.18.0", "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2", "18.4.3", "18.5.0", "18.5.1", "18.5.2", "18.5.3", "18.5.4", "18.5.5", "18.5.6", "18.5.7", "18.5.8", "18.5.9", "18.5.10", "18.5.11", "18.5.12", "18.5.13", "18.5.14", "18.5.15"})

    def test_shows_api_is_server_side_paged(self):
        app_py = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('def shows():', app_py)
        self.assertIn('limit=int(request.args.get("limit") or 100)', app_py)
        self.assertIn('offset=int(request.args.get("offset") or 0)', app_py)
        self.assertIn('LIMIT ? OFFSET ?', app_py)
        self.assertIn('next_offset=', app_py)
        self.assertIn('has_more=', app_py)

    def test_manager_uses_server_side_paging(self):
        js = (ROOT / "static" / "manager.js").read_text(encoding="utf-8")
        self.assertIn('p.set("limit",showLimit)', js)
        self.assertIn('p.set("offset",showOffset)', js)
        self.assertIn('Load next', js)
        self.assertIn('Library API returned', js)
        self.assertIn('Showing ${shown.toLocaleString()} of', js)

    def test_large_library_docs_exist(self):
        doc = (ROOT / "docs" / "LARGE_LIBRARY_PERFORMANCE.md").read_text(encoding="utf-8")
        self.assertIn('/api/shows?limit=100&offset=0', doc)
        self.assertIn('39K+', (ROOT / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
