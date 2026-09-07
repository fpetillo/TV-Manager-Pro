from pathlib import Path
import engine


def test_postprocess_matching_blocks_from_inside_friends_from_college():
    shows = [
        {"id": 1, "name": "FROM", "location": r"X:\\TV\\From", "season_folders": 1},
        {"id": 2, "name": "Friends from College", "location": r"X:\\TV\\Friends from College", "season_folders": 1},
    ]
    p = Path(r"C:\\Complete\\Friends.from.College.S01.REPACK.2160p\\Friends.from.College.S01E03.All-Nighter.REPACK.2160p.NF.WEB-DL.mkv")
    match, error = engine._choose_postprocess_show(shows, p)
    assert error is None
    assert match["show"]["name"] == "Friends from College"
    assert match["confidence"] == "high"


def test_postprocess_matching_does_not_match_er_inside_friends_episode_title():
    shows = [
        {"id": 1, "name": "ER", "location": r"X:\\TV\\ER", "season_folders": 1},
        {"id": 2, "name": "Friends", "location": r"X:\\TV\\Friends", "season_folders": 1},
    ]
    p = Path(r"C:\\Complete\\Friends.S03.2160p.BluRay\\Friends.S03E10.The.One.Where.Rachel.Quits.2160p.UHD.BluRay.mkv")
    match, error = engine._choose_postprocess_show(shows, p)
    assert error is None
    assert match["show"]["name"] == "Friends"
    assert match["confidence"] == "high"


def test_postprocess_matching_still_accepts_short_show_exact_prefixes():
    shows = [
        {"id": 1, "name": "ER", "location": r"X:\\TV\\ER", "season_folders": 1},
        {"id": 2, "name": "FROM", "location": r"X:\\TV\\From", "season_folders": 1},
    ]
    er, er_error = engine._choose_postprocess_show(shows, Path("ER.S03E10.The_Holidays.mkv"))
    frm, frm_error = engine._choose_postprocess_show(shows, Path("From.S01E03.Choosing.Day.mkv"))
    assert er_error is None and er["show"]["name"] == "ER"
    assert frm_error is None and frm["show"]["name"] == "FROM"


def test_postprocess_unmatched_details_are_available_for_rejected_short_substrings():
    shows = [{"id": 1, "name": "FROM", "location": r"X:\\TV\\From", "season_folders": 1}]
    match, error = engine._choose_postprocess_show(shows, Path("Friends.from.College.S01E03.All-Nighter.mkv"))
    assert match is None
    assert "No show title matched" in error
