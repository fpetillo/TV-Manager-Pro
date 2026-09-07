"""Trakt.tv integration helpers for TV Manager.

Public discovery endpoints need a Trakt client id/API key. Authenticated user
sync can be added later with OAuth/device-code, but the discovery workflow is
intentionally useful with only a client id so operators can add popular,
trending, anticipated, and recently updated shows.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv

try:
    import engine
except Exception:  # pragma: no cover - lets standalone docs/tests import safely
    engine = None

BASE_URL = "https://api.trakt.tv"


class TraktConfigurationError(RuntimeError):
    pass


class TraktApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class TraktCredentials:
    client_id: str
    access_token: str = ""
    source: str = "missing"


def _setting(section: str, name: str, default: str = "") -> str:
    if engine is None:
        return default
    try:
        return engine.get_setting(section, name, default) or default
    except Exception:
        return default


def credentials() -> TraktCredentials:
    load_dotenv()
    candidates = [
        ("env:TRAKT_CLIENT_ID", os.getenv("TRAKT_CLIENT_ID") or ""),
        ("env:TRAKT_API_KEY", os.getenv("TRAKT_API_KEY") or ""),
        ("env:TRAKT_CLIENT_KEY", os.getenv("TRAKT_CLIENT_KEY") or ""),
        ("settings:Trakt.client_id", _setting("Trakt", "client_id", "")),
        ("settings:Trakt.api_key", _setting("Trakt", "api_key", "")),
    ]
    client_source, client_id = next(((src, val.strip()) for src, val in candidates if val and val.strip()), ("missing", ""))
    token = (
        os.getenv("TRAKT_ACCESS_TOKEN")
        or os.getenv("TRAKT_BEARER_TOKEN")
        or _setting("Trakt", "access_token", "")
        or ""
    ).strip()
    return TraktCredentials(client_id=client_id, access_token=token, source=client_source)


def status() -> dict[str, Any]:
    creds = credentials()
    return {
        "configured": bool(creds.client_id),
        "has_client_id": bool(creds.client_id),
        "has_access_token": bool(creds.access_token),
        "credential_source": creds.source,
        "message": "Trakt discovery is ready." if creds.client_id else "Set TRAKT_CLIENT_ID in .env or save a Trakt client id in Settings.",
    }


def headers() -> dict[str, str]:
    creds = credentials()
    if not creds.client_id:
        raise TraktConfigurationError("Trakt is not configured. Add TRAKT_CLIENT_ID to .env or save it in Settings.")
    h = {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": creds.client_id,
        "User-Agent": "TV Manager SickChill Replacement",
    }
    if creds.access_token:
        h["Authorization"] = f"Bearer {creds.access_token}"
    return h


def get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = BASE_URL + path
    try:
        r = requests.get(url, headers=headers(), params=params or {}, timeout=30)
    except TraktConfigurationError:
        raise
    except requests.RequestException as exc:
        raise TraktApiError(f"Could not contact Trakt.tv: {exc}") from exc
    if r.status_code in (401, 403):
        raise TraktApiError("Trakt rejected the configured client id/access token. Check TRAKT_CLIENT_ID and optional TRAKT_ACCESS_TOKEN.", r.status_code)
    if r.status_code == 429:
        raise TraktApiError("Trakt rate limit reached. Wait a few minutes and try again.", r.status_code)
    if r.status_code >= 400:
        raise TraktApiError(f"Trakt API returned HTTP {r.status_code}: {r.text[:240]}", r.status_code)
    return r.json()


def _normalize_show(item: dict[str, Any], category: str) -> dict[str, Any]:
    show = item.get("show") if isinstance(item.get("show"), dict) else item
    ids = show.get("ids") or {}
    return {
        "category": category,
        "trakt_id": ids.get("trakt"),
        "trakt_slug": ids.get("slug"),
        "tvdb_id": ids.get("tvdb"),
        "imdb_id": ids.get("imdb"),
        "tmdb_id": ids.get("tmdb"),
        "name": show.get("title") or show.get("name") or "Unknown",
        "year": show.get("year"),
        "overview": show.get("overview") or "",
        "network": show.get("network") or "",
        "country": show.get("country") or "",
        "status": show.get("status") or "",
        "first_air_date": show.get("first_aired") or show.get("aired_episodes"),
        "runtime": show.get("runtime"),
        "watchers": item.get("watchers"),
        "list_count": item.get("list_count"),
        "rank_score": item.get("watchers") or item.get("list_count") or 0,
        "raw": show,
    }


def discover(category: str = "trending", page: int = 1, limit: int = 50) -> list[dict[str, Any]]:
    category = (category or "trending").lower().strip()
    limit = max(1, min(int(limit or 50), 100))
    page = max(1, int(page or 1))
    endpoint_map = {
        "trending": "/shows/trending",
        "popular": "/shows/popular",
        "anticipated": "/shows/anticipated",
        "watched": "/shows/watched/weekly",
        "played": "/shows/played/weekly",
    }
    path = endpoint_map.get(category)
    if not path:
        raise ValueError("Unsupported Trakt category. Use trending, popular, anticipated, watched, or played.")
    data = get(path, {"page": page, "limit": limit, "extended": "full"})
    if not isinstance(data, list):
        return []
    return [_normalize_show(x, category) for x in data]


def search_shows(query: str, limit: int = 25) -> list[dict[str, Any]]:
    query = (query or "").strip()
    if not query:
        return []
    data = get("/search/show", {"query": query, "limit": max(1, min(int(limit or 25), 50)), "extended": "full"})
    out=[]
    for item in data if isinstance(data, list) else []:
        row=_normalize_show(item, "search")
        row["rank_score"] = item.get("score") or 0
        out.append(row)
    return out
