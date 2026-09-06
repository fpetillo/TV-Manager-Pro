import tempfile, unittest
from pathlib import Path
import dbcore, lifecycle

class LifecycleTests(unittest.TestCase):
    def test_quality_guard(self):
        ok,_=lifecycle.replacement_allowed("1080p WEB-DL","Show.S01E01.1080p.WEB-DL",
                                           "720p WEB-DL","Show.S01E01.720p.WEB-DL")
        self.assertFalse(ok)
        ok,_=lifecycle.replacement_allowed("1080p WEB-DL","Show.S01E01.1080p.WEB-DL",
                                           "1080p WEB-DL","Show.S01E01.1080p.WEB-DL.REPACK")
        self.assertTrue(ok)

    def test_quality_rank(self):
        self.assertGreater(lifecycle.quality_rank("2160p WEB-DL"),lifecycle.quality_rank("1080p BluRay"))
        self.assertGreater(lifecycle.quality_rank("1080p BluRay"),lifecycle.quality_rank("1080p HDTV"))

    def test_transition_validation(self):
        with self.assertRaises(ValueError):
            lifecycle.transition("episode",1,"Found","Completed")
