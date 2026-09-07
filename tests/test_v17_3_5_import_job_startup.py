import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ImportJobStartupFixTests(unittest.TestCase):
    def test_import_job_queued_call_does_not_pass_job_id_twice(self):
        app_text = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("_set_import_job(job_id, job_id=job_id", app_text)
        self.assertIn('_set_import_job(job_id, status="queued"', app_text)

    def test_version_is_17_3_5(self):
        self.assertIn((ROOT / "VERSION").read_text(encoding="utf-8").strip(), {"17.3.5", "17.4.0", "17.5.0", "17.6.0", "17.6.1", "17.7.0", "17.9.0", "17.9.1", "17.10.0", "17.11.0", "17.12.0", "17.13.0", "17.13.1", "17.13.2", "17.13.3", "17.14.0", "17.15.0", "17.16.0", "17.18.0", "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2"})


if __name__ == "__main__":
    unittest.main()
