import tempfile, unittest
from pathlib import Path
import security, dbcore

class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.old_db=security.DB
        self.td=tempfile.TemporaryDirectory()
        security.DB=Path(self.td.name)/"tvmanager.db"
        with dbcore.connect(security.DB) as c:
            c.execute("""CREATE TABLE settings(
              section TEXT NOT NULL,name TEXT NOT NULL,value TEXT,is_secret INTEGER DEFAULT 0,
              source TEXT DEFAULT 'app',updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY(section,name))""")
        security.init()

    def tearDown(self):
        security.DB=self.old_db
        self.td.cleanup()

    def test_password_hash_and_authentication(self):
        security.set_admin_password("admin","correct horse battery staple")
        user,error=security.authenticate("admin","correct horse battery staple","127.0.0.1")
        self.assertIsNotNone(user);self.assertIsNone(error)
        user,error=security.authenticate("admin","wrong password","127.0.0.2")
        self.assertIsNone(user);self.assertIsNotNone(error)

    def test_short_password_rejected(self):
        with self.assertRaises(ValueError):
            security.set_admin_password("admin","short")

    def test_browser_auth_requires_admin(self):
        with self.assertRaises(ValueError):
            security.set_browser_auth(True)
        security.set_admin_password("admin","this is a sufficiently long password")
        security.set_browser_auth(True)
        self.assertTrue(security.browser_auth_enabled())

    def test_loopback_detection(self):
        self.assertTrue(security.is_loopback("127.0.0.1"))
        self.assertTrue(security.is_loopback("::1"))
        self.assertFalse(security.is_loopback("192.168.1.25"))

    def test_rate_limit_after_failures(self):
        security.set_admin_password("admin","correct horse battery staple")
        for _ in range(5):
            security.authenticate("admin","bad","10.0.0.5")
        self.assertTrue(security.login_blocked("10.0.0.5"))
