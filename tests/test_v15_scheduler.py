import tempfile, unittest
from pathlib import Path
import scheduler_guard, dbcore

class SchedulerGuardTests(unittest.TestCase):
    def test_lease_is_exclusive_and_releasable(self):
        old=scheduler_guard.DB
        with tempfile.TemporaryDirectory() as td:
            scheduler_guard.DB=Path(td)/"tvmanager.db"
            try:
                scheduler_guard.init()
                self.assertTrue(scheduler_guard.acquire("recent_search",10))
                self.assertFalse(scheduler_guard.acquire("recent_search",10))
                scheduler_guard.release("recent_search")
                self.assertTrue(scheduler_guard.acquire("recent_search",10))
                scheduler_guard.release("recent_search")
            finally:
                scheduler_guard.DB=old

    def test_running_jobs_recovered_as_abandoned(self):
        old=scheduler_guard.DB
        with tempfile.TemporaryDirectory() as td:
            scheduler_guard.DB=Path(td)/"tvmanager.db"
            try:
                scheduler_guard.init()
                with dbcore.connect(scheduler_guard.DB) as c:
                    c.execute("INSERT INTO scheduler_runs(job_name,status) VALUES('x','Running')")
                scheduler_guard.init()
                with dbcore.connect(scheduler_guard.DB) as c:
                    row=c.execute("SELECT status FROM scheduler_runs ORDER BY id DESC LIMIT 1").fetchone()
                    self.assertEqual(row["status"],"Abandoned")
            finally:
                scheduler_guard.DB=old
    def test_active_lease_preserves_running_record(self):
        old=scheduler_guard.DB
        with tempfile.TemporaryDirectory() as td:
            scheduler_guard.DB=Path(td)/"tvmanager.db"
            try:
                scheduler_guard.init()
                self.assertTrue(scheduler_guard.acquire("jobx",15))
                with dbcore.connect(scheduler_guard.DB) as c:
                    c.execute("INSERT INTO scheduler_runs(job_name,status) VALUES('jobx','Running')")
                scheduler_guard.init()
                with dbcore.connect(scheduler_guard.DB) as c:
                    row=c.execute("SELECT status FROM scheduler_runs ORDER BY id DESC LIMIT 1").fetchone()
                    self.assertEqual(row["status"],"Running")
                self.assertTrue(scheduler_guard.renew("jobx",15))
                scheduler_guard.release("jobx")
            finally:
                scheduler_guard.DB=old

