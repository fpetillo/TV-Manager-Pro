import unittest
import advanced
import production

class CoreTests(unittest.TestCase):
    def test_multi_episode(self):
        self.assertEqual(advanced.split_multi_episode("Show.S01E01E02.1080p"),[(1,1),(1,2)])
        self.assertEqual(advanced.split_multi_episode("Show.S02E03-E05"),[(2,3),(2,4),(2,5)])
        self.assertEqual(advanced.split_multi_episode("Show.3x04-3x06"),[(3,4),(3,5),(3,6)])

    def test_resolution(self):
        self.assertEqual(production._resolution("1080p WEB-DL"),1080)
        self.assertEqual(production._resolution("2160p UHD"),2160)
        self.assertEqual(production._resolution("SDTV"),480)

if __name__=="__main__":
    unittest.main()
