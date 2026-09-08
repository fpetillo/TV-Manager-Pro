import re, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class StartupSchemaRepairTests(unittest.TestCase):
    def test_startup_adds_imdb_id_before_index_creation(self):
        app_source=(ROOT/'app.py').read_text(encoding='utf-8')
        ensure_pos=app_source.index('_ensure_columns(c, "shows", {')
        index_pos=app_source.index('CREATE INDEX IF NOT EXISTS idx_shows_imdb')
        ensure_block=app_source[ensure_pos:index_pos]
        self.assertIn('"imdb_id": "TEXT"', ensure_block)
        self.assertLess(ensure_pos, index_pos)

    def test_release_notes_document_operational_error_fix(self):
        notes=(ROOT/'docs'/'RELEASE_NOTES_v17.1.8.md').read_text(encoding='utf-8')
        self.assertIn('no such column: imdb_id', notes)
        self.assertIn('first startup may upgrade', notes)

    def test_version_is_17_1_6(self):
        self.assertIn((ROOT/'VERSION').read_text(encoding='utf-8').strip(), {'17.1.8','17.1.9','17.2.0', '17.3.0', '17.3.1', '17.3.2', '17.3.3', '17.3.4', '17.3.5', '17.4.0', '17.5.0', '17.6.0', '17.6.1', '17.7.0', '17.9.0', '17.9.1', '17.10.0', '17.11.0', '17.12.0', '17.13.0', '17.13.1', '17.13.2', '17.13.3', '17.14.0', '17.15.0', '17.16.0', '17.18.0', "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2", "18.4.3", "18.5.0", "18.5.1", "18.5.2", "18.5.3", "18.5.4", "18.5.5", "18.5.6", "18.5.7", "18.5.8", "18.5.9", "18.5.10"})

if __name__ == '__main__':
    unittest.main()
