import re
import unittest
from pathlib import Path

class DBImportAuditTests(unittest.TestCase):
    def test_every_dbcore_reference_has_import(self):
        root = Path(__file__).resolve().parents[1]
        failures = []
        for p in root.glob("*.py"):
            text = p.read_text(encoding="utf-8", errors="ignore")
            if "dbcore." not in text:
                continue
            if not re.search(r'^\s*(?:import\s+dbcore|from\s+dbcore\s+import\s+)', text, re.M):
                failures.append(p.name)
        self.assertEqual(failures, [], f"Missing dbcore imports: {failures}")
