import unittest
from pathlib import Path
import naming

class NamingTests(unittest.TestCase):
    def eps(self):
        return [
            {"season":1,"episode":1,"name":"Pilot"},
            {"season":1,"episode":2,"name":"Second / Part"},
        ]

    def test_sickchill_default_multi_episode(self):
        p=naming.render("Season %0S/%SN - S%0SE%0E - %EN","My Show",self.eps(),".mkv")
        self.assertEqual(str(p).replace("\\","/"),
                         "Season 01/My Show - S01E01E02 - Pilot + Second _ Part.mkv")

    def test_windows_reserved_and_invalid(self):
        self.assertEqual(naming.safe_component("CON"),"_CON")
        self.assertEqual(naming.safe_component('Bad:Name?'),"Bad_Name_")

    def test_no_rename_season_folder(self):
        p=naming.configured_destination(r"C:\TV\Show","Show",[self.eps()[0]],"source.mkv",
                                        rename=False,season_folders=True)
        self.assertTrue(str(p).replace("\\","/").endswith("Season 01/source.mkv"))
