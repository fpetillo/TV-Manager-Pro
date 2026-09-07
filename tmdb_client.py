from __future__ import annotations

"""Shared TMDb client for TV Manager.

Supports both TMDb v4 read-access bearer tokens and legacy v3 API keys.
Credentials are resolved at call time so updates to .env or imported SickChill
settings are picked up without restarting when possible.
"""

from pathlib import Path
import os
import sqlite3
from typing import Any, Callable

import requests
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env", override=False)

class TMDBConfigurationError(RuntimeError):
    pass

class TMDBUnauthorizedError(RuntimeError):
    pass

class TMDBRequestError(RuntimeError):
    pass

_SECRET_PLACEHOLDERS = {"", "none", "null", "changeme", "paste_your_tmdb_api_read_access_token_here", "paste_your_tmdb_api_key_here", "••••••••"}


def _clean(value: Any) -> str:
    text = str(value or "").strip().strip('"').strip("'")
    if text.lower() in _SECRET_PLACEHOLDERS:
        return ""
    return text


def _settings_candidates(db_path: str | Path | None) -> list[tuple[str, str, str]]:
    if not db_path:
        return []
    path = Path(db_path)
    if not path.exists():
        return []
    names = {
        "tmdb_bearer_token", "tmdb_token", "tmdb_read_access_token", "tmdb_v4_token",
        "tmdb_api_key", "tmdb_v3_api_key", "themoviedb_api_key", "metadata_tmdb_api_key",
    }
    try:
        con = sqlite3.connect(str(path), timeout=5)
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute("SELECT section,name,value FROM settings").fetchall()
        finally:
            con.close()
    except Exception:
        return []
    out: list[tuple[str, str, str]] = []
    for row in rows:
        name = str(row["name"] or "").strip().lower()
        section = str(row["section"] or "").strip().lower()
        if name in names or ("tmdb" in name and ("key" in name or "token" in name)) or ("tmdb" in section and ("key" in name or "token" in name)):
            value = _clean(row["value"])
            if value:
                out.append((section, name, value))
    return out


def credentials(db_path: str | Path | None = None) -> dict[str, str]:
    """Return resolved TMDb auth details.

    Preference order:
      1. v4 bearer token in .env / process env
      2. v3 API key in .env / process env
      3. imported/saved settings from SickChill or TV Manager settings table
    """
    bearer = _clean(os.getenv("TMDB_BEARER_TOKEN") or os.getenv("TMDB_READ_ACCESS_TOKEN") or os.getenv("TMDB_V4_TOKEN"))
    if bearer:
        return {"mode": "bearer", "value": bearer, "source": "environment"}

    api_key = _clean(os.getenv("TMDB_API_KEY") or os.getenv("TMDB_V3_API_KEY") or os.getenv("THEMOVIEDB_API_KEY"))
    if api_key:
        return {"mode": "api_key", "value": api_key, "source": "environment"}

    for section, name, value in _settings_candidates(db_path):
        if "token" in name or "bearer" in name or "read_access" in name or value.startswith("eyJ"):
            return {"mode": "bearer", "value": value, "source": f"settings:{section}.{name}"}
    for section, name, value in _settings_candidates(db_path):
        return {"mode": "api_key", "value": value, "source": f"settings:{section}.{name}"}

    raise TMDBConfigurationError(
        "TMDb is not configured. Add TMDB_BEARER_TOKEN or TMDB_API_KEY to .env, "
        "or import/save a TMDb key in Settings."
    )


def configured(db_path: str | Path | None = None) -> dict[str, Any]:
    try:
        c = credentials(db_path)
        return {"configured": True, "mode": c["mode"], "source": c["source"]}
    except TMDBConfigurationError as ex:
        return {"configured": False, "error": str(ex)}


def get(path: str, params: dict[str, Any] | None = None, db_path: str | Path | None = None, timeout: int = 20, session: Any = None) -> dict[str, Any]:
    c = credentials(db_path)
    req_params = dict(params or {})
    headers = {"accept": "application/json"}
    if c["mode"] == "bearer":
        headers["Authorization"] = "Bearer " + c["value"]
    else:
        req_params.setdefault("api_key", c["value"])

    url = "https://api.themoviedb.org/3" + path
    requester = session or requests
    try:
        response = requester.get(url, headers=headers, params=req_params, timeout=timeout)
    except requests.RequestException as ex:
        raise TMDBRequestError(f"TMDb request failed before a response was received: {ex}") from ex

    if response.status_code == 401:
        raise TMDBUnauthorizedError(
            "TMDb rejected the configured credential with HTTP 401 Unauthorized. "
            "Verify that your TMDB_BEARER_TOKEN is the TMDb API Read Access Token, "
            "or use TMDB_API_KEY for a legacy v3 API key."
        )
    if response.status_code == 403:
        raise TMDBUnauthorizedError(
            "TMDb rejected access with HTTP 403 Forbidden. Check the TMDb credential permissions and account status."
        )
    try:
        response.raise_for_status()
    except requests.HTTPError as ex:
        raise TMDBRequestError(f"TMDb returned HTTP {response.status_code}: {response.text[:300]}") from ex
    try:
        return response.json()
    except ValueError as ex:
        raise TMDBRequestError("TMDb returned a non-JSON response.") from ex
