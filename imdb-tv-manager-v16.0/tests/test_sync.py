import unittest
import sync

class SyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sync.init()
        with sync.cx() as c:
            c.execute("CREATE TABLE IF NOT EXISTS shows(id INTEGER PRIMARY KEY,name TEXT)")
            c.execute("""CREATE TABLE IF NOT EXISTS episodes(
                         id INTEGER PRIMARY KEY,show_id INTEGER,season INTEGER,episode INTEGER,location TEXT)""")
            c.commit()

    def test_lookup_missing(self):
        self.assertIsNone(sync._episode_lookup("__unlikely_show__",999,999))

    def test_mapping_source_round_trip(self):
        sync.save_mapping_source("UnitTest XEM","xem","https://example.invalid",False)
        self.assertTrue(any(r["name"]=="UnitTest XEM" for r in sync.mapping_status()))

if __name__=="__main__":
    unittest.main()
