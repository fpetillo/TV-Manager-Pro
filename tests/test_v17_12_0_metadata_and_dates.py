from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_is_17_12_0():
    assert (ROOT / 'VERSION').read_text(encoding='utf-8').strip() in {'17.12.0', '17.13.0', '17.13.1', '17.13.2', '17.13.3', '17.14.0', '17.15.0', '17.16.0', '17.18.0', "17.20.0", "17.21.0", "17.22.0", "17.23.0", "18.0.0", "18.1.0", "18.2.0", "18.2.1", "18.2.2", "18.2.3", "18.2.4", "18.2.6", "18.3.0", "18.3.1", "18.3.2", "18.3.3", "18.4.0", "18.4.1", "18.4.2"}


def test_show_queue_formats_dates_in_browser():
    js = (ROOT / 'static' / 'show_queue.js').read_text(encoding='utf-8')
    assert 'function fmtDate' in js
    assert 'Number(m)' in js
    assert 'Number(d)' in js
    assert '/api/show-queue?' in js


def test_full_metadata_refresh_endpoints_are_registered():
    app_py = (ROOT / 'app.py').read_text(encoding='utf-8')
    assert '/api/metadata/refresh/full/preview' in app_py
    assert '/api/metadata/refresh/full/start' in app_py
    assert '/api/metadata/refresh/full/jobs/<job_id>' in app_py


def test_metadata_service_has_full_refresh_job_engine():
    src = (ROOT / 'metadata_service.py').read_text(encoding='utf-8')
    assert 'def start_full_refresh' in src
    assert 'def full_refresh_preview' in src
    assert 'def _run_full_refresh_job' in src
    assert 'TMDb is not configured' in src
