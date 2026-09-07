from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def test_import_js_has_json_guard():
    js = (BASE / "static" / "import.js").read_text(encoding="utf-8")
    assert "async function expectJson" in js
    assert "returned HTML/text instead of JSON" in js
    assert "Start import job" in js


def test_api_error_handler_returns_json_for_api_routes():
    src = (BASE / "app.py").read_text(encoding="utf-8")
    assert "def api_exception_json" in src
    assert 'request.path.startswith("/api/")' in src
    assert 'endpoint=request.path' in src


def test_import_job_routes_have_slash_compatibility():
    src = (BASE / "app.py").read_text(encoding="utf-8")
    assert '@app.post("/api/import/sickchill/jobs/")' in src
    assert '@app.get("/api/import/sickchill/jobs/<job_id>/")' in src
