import tempfile, unittest
from pathlib import Path
import integrity, dbcore

class IntegrityTests(unittest.TestCase):
    def test_fingerprint_same_content(self):
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/"a.mkv";b=Path(td)/"b.mkv"
            payload=b"x"*1024+b"middle"+b"y"*1024
            a.write_bytes(payload);b.write_bytes(payload)
            fa=integrity.fingerprint(a);fb=integrity.fingerprint(b)
            self.assertEqual(fa[0],fb[0])
            self.assertEqual(fa[1],fb[1])

    def test_fingerprint_changes(self):
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/"a.mkv";b=Path(td)/"b.mkv"
            a.write_bytes(b"a"*4096);b.write_bytes(b"b"*4096)
            self.assertNotEqual(integrity.fingerprint(a)[0],integrity.fingerprint(b)[0])
