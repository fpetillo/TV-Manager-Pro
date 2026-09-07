from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V17132BuildAndDatabaseSafetyTests(unittest.TestCase):
    def test_build_script_sets_packaging_guard_and_excludes_live_db(self):
        script = (ROOT / "installer" / "windows" / "build-exe.ps1").read_text(encoding="utf-8")
        self.assertIn("TVMANAGER_BUILDING_EXE", script)
        self.assertIn("tvmanager.db", script)
        self.assertIn(".env", script)
        self.assertIn("$env:TEMP", script)

    def test_app_skips_startup_repair_during_exe_build(self):
        app_text = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("TVMANAGER_BUILDING_EXE", app_text)
        self.assertIn("db_doctor.repair(DB)", app_text)

    def test_db_doctor_flags_malformed_database_before_repair(self):
        import db_doctor
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.db"
            path.write_bytes(b"not a sqlite database")
            report = db_doctor.quick_check_database(path)
            self.assertFalse(report["ok"])
            with self.assertRaises(db_doctor.DatabaseSafetyError):
                db_doctor.repair(path)

    def test_db_doctor_accepts_new_empty_database(self):
        import db_doctor
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fresh.db"
            report = db_doctor.repair(path)
            self.assertEqual(report["quick_check"], "ok")
            con = sqlite3.connect(path)
            try:
                self.assertIsNotNone(con.execute("select 1 from sqlite_master where name='shows'").fetchone())
            finally:
                con.close()


if __name__ == "__main__":
    unittest.main()
