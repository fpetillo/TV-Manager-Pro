import tempfile, unittest
from pathlib import Path
import dbcore, engine
class V13Tests(unittest.TestCase):
    def test_magnet_hash(self):
        h="0123456789abcdef0123456789abcdef01234567"
        self.assertEqual(engine._magnet_hash("magnet:?xt=urn:btih:"+h),h)
    def test_db_pragmas(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"x.db"
            with dbcore.connect(p) as c:
                c.execute("create table t(id integer primary key)");c.commit()
                self.assertEqual(c.execute("pragma foreign_keys").fetchone()[0],1)
            self.assertEqual(dbcore.quick_check(p),"ok")
if __name__=="__main__":unittest.main()
