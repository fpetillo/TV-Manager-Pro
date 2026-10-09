"""v18.18.0: Post Processing matches show titles to release names flexibly."""
import unittest
from pathlib import Path

import engine

LIBRARY = [
    "Grey's Anatomy", "Law & Order: Special Victims Unit", "Law & Order", "Marvel's Agents of S.H.I.E.L.D.",
    "Doctor Who (2005)", "Pokémon", "The Handmaid's Tale", "Mr. & Mrs. Smith", "It's Always Sunny in Philadelphia",
    "9-1-1", "9-1-1: Lone Star", "Bob's Burgers", "ER", "From", "Friends", "Friends from College", "S.W.A.T. (2017)",
    "The Office (US)", "Spider-Man", "Love Island (US)", "Love Island", "Shameless", "House of the Dragon",
]
SHOWS = [{"id": i, "name": n} for i, n in enumerate(LIBRARY, 1)]

EXPECTED = {
    "Greys.Anatomy.S21E01.1080p.WEB-DL.mkv": "Grey's Anatomy",
    "Grey’s Anatomy - S21E01.mkv": "Grey's Anatomy",
    "Law.and.Order.Special.Victims.Unit.S26E01.mkv": "Law & Order: Special Victims Unit",
    "Law.and.Order.S24E01.mkv": "Law & Order",
    "Law.&.Order.S24E01.mkv": "Law & Order",
    "Marvels.Agents.of.SHIELD.S07E01.mkv": "Marvel's Agents of S.H.I.E.L.D.",
    "Marvels.Agents.of.S.H.I.E.L.D.S07E01.mkv": "Marvel's Agents of S.H.I.E.L.D.",
    "Doctor.Who.S14E01.mkv": "Doctor Who (2005)",
    "Doctor.Who.2005.S14E01.mkv": "Doctor Who (2005)",
    "Pokemon.S01E01.mkv": "Pokémon",
    "Handmaids.Tale.S06E01.mkv": "The Handmaid's Tale",
    "The.Handmaids.Tale.S06E01.mkv": "The Handmaid's Tale",
    "Mr.and.Mrs.Smith.S01E01.mkv": "Mr. & Mrs. Smith",
    "Its.Always.Sunny.in.Philadelphia.S17E01.mkv": "It's Always Sunny in Philadelphia",
    "911.S08E01.mkv": "9-1-1",
    "911.Lone.Star.S05E01.mkv": "9-1-1: Lone Star",
    "9-1-1.Lone.Star.S05E01.mkv": "9-1-1: Lone Star",
    "Bobs.Burgers.S15E01.mkv": "Bob's Burgers",
    "SWAT.2017.S08E01.mkv": "S.W.A.T. (2017)",
    "S.W.A.T.S08E01.mkv": "S.W.A.T. (2017)",
    "The.Office.US.S09E01.mkv": "The Office (US)",
    "Spiderman.S01E01.mkv": "Spider-Man",
    "Love.Island.US.S07E01.mkv": "Love Island (US)",
    "Love.Island.S07E01.mkv": "Love Island",
    "Shameless.US.S11E01.mkv": "Shameless",
    "House.of.the.Dragon.S02E01.mkv": "House of the Dragon",
    # Short titles still match only the whole title, never a substring.
    "ER.S03E10.mkv": "ER",
    "From.S01E03.mkv": "From",
    "Friends.S03E10.mkv": "Friends",
    "Friends.from.College.S01E03.mkv": "Friends from College",
}


def choose(name, shows=SHOWS):
    return engine._choose_postprocess_show(shows, Path(name))


class FlexibleShowMatchingTests(unittest.TestCase):
    def test_release_names_match_their_shows(self):
        for name, show in EXPECTED.items():
            with self.subTest(name=name):
                match, error = choose(name)
                self.assertIsNotNone(match, error)
                self.assertEqual(match["show"]["name"], show)

    def test_different_show_with_extra_words_is_not_taken(self):
        match, error = choose("Law.And.Order.SVU.S26E01.mkv", [{"id": 1, "name": "Law & Order"}])
        self.assertIsNone(match)

    def test_same_base_title_in_two_editions_is_ambiguous(self):
        shows = [{"id": 1, "name": "The Office (US)"}, {"id": 2, "name": "The Office (UK)"}]
        match, error = choose("The.Office.S01E01.mkv", shows)
        self.assertIsNone(match)
        self.assertIn("Ambiguous", error)

    def test_exact_title_beats_edition_without_year(self):
        shows = [{"id": 1, "name": "Doctor Who"}, {"id": 2, "name": "Doctor Who (2005)"}]
        self.assertEqual(choose("Doctor.Who.S01E01.mkv", shows)[0]["show"]["name"], "Doctor Who")
        self.assertEqual(choose("Doctor.Who.2005.S01E01.mkv", shows)[0]["show"]["name"], "Doctor Who (2005)")

    def test_folder_name_is_matched_the_same_way(self):
        match, error = choose("Greys Anatomy S21E01/episode.s21e01.mkv")
        self.assertIsNotNone(match, error)
        self.assertEqual(match["show"]["name"], "Grey's Anatomy")


if __name__ == "__main__":
    unittest.main()
