import sqlite3
from contextlib import contextmanager
import engine


def test_unsaved_defaults_are_editable(tmp_path, monkeypatch):
    path = tmp_path / 'settings.db'
    @contextmanager
    def cx():
        c = sqlite3.connect(path)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()
    with cx() as c:
        c.execute('CREATE TABLE settings(section,name,value,is_secret,source,updated_at, UNIQUE(section,name))')
    monkeypatch.setattr(engine, 'cx', cx)
    monkeypatch.setattr(engine, 'configurable_defaults', lambda: {'TVManager': {'recent_days': '14'}})
    assert engine.setting_sections_public()[0]['setting_count'] == 1
    assert engine.settings_for_section('TVManager')[0]['value'] == '14'
    engine.update_setting_safe('TVManager', 'recent_days', '21')
    assert engine.settings_for_section('TVManager')[0]['value'] == '21'
    assert len(engine.settings_for_section('TVManager')) == 1
