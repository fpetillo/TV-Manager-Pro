import tempfile, unittest
from pathlib import Path
import dbcore

class DBTests(unittest.TestCase):
    def test_wal_and_busy_timeout(self):
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/"x.db"
            with dbcore.connect(db) as c:
                c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY)")
                c.commit()
                self.assertGreaterEqual(c.execute("PRAGMA busy_timeout").fetchone()[0],30000)
                self.assertEqual(c.execute("PRAGMA foreign_keys").fetchone()[0],1)
            self.assertEqual(dbcore.quick_check(db),"ok")

    def test_context_closes_connection(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/"close.db"
            c=dbcore.connect(db)
            with c:
                c.execute("CREATE TABLE t(id INTEGER)")
            with self.assertRaises(sqlite3.ProgrammingError):
                c.execute("SELECT 1")

    def test_online_backup(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/"a.db";dst=Path(td)/"b.db"
            with dbcore.connect(src) as c:
                c.execute("CREATE TABLE t(v TEXT)")
                c.execute("INSERT INTO t VALUES('ok')")
                c.commit()
            dbcore.online_backup(src,dst)
            with dbcore.connect(dst,wal=False,readonly=True) as c:
                self.assertEqual(c.execute("SELECT v FROM t").fetchone()[0],"ok")
