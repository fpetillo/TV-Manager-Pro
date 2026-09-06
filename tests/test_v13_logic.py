import tempfile, unittest
from pathlib import Path
import dbcore, advanced

class V13LogicTests(unittest.TestCase):
    def test_multi_episode_ranges(self):
        self.assertEqual(advanced.split_multi_episode("Show.S01E01E02.mkv"),[(1,1),(1,2)])
        self.assertEqual(advanced.split_multi_episode("Show.S02E03-E05.mkv"),[(2,3),(2,4),(2,5)])

    def test_shared_transaction_pattern(self):
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/"x.db"
            with dbcore.connect(db) as c:
                c.execute("CREATE TABLE a(id INTEGER PRIMARY KEY,v TEXT)")
                c.execute("INSERT INTO a(v) VALUES('one')")
                c.execute("INSERT INTO a(v) VALUES('two')")
                c.commit()
            with dbcore.connect(db) as c:
                self.assertEqual(c.execute("SELECT COUNT(*) FROM a").fetchone()[0],2)
