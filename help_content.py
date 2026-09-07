"""In-app help and SickChill parity data for TV Manager."""
from __future__ import annotations

from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class ParityItem:
    area: str
    sickchill_feature: str
    tv_manager_location: str
    status: str
    notes: str

from parity_catalog import FEATURES
PARITY_ITEMS = [ParityItem(*row) for row in FEATURES]

HELP_SECTIONS = {
    "getting-started": {
        "title": "Getting started",
        "summary": "Use Launchpad first, then configure metadata, downloaders, providers, post-processing, and media servers.",
        "steps": [
            "Open Launchpad and review readiness.",
            "Import a copied SickChill database or add shows with Search/Trakt.",
            "Open Show Queue to review missing/downloaded totals.",
            "Configure Download Center and run a downloader test.",
            "Configure Post Processing and run a preview before moving files.",
            "Use Manage Center for bulk episode rules and wanted/ignored status."
        ],
    },
    "show-queue": {
        "title": "Show Queue",
        "summary": "The queue ranks shows by missing episode need and downloaded progress, while respecting ignored episodes and the Season 00 setting.",
        "steps": ["Sort by Missing / Downloads.", "Click a show to open Show Detail.", "Use ignored rules when metadata contains specials, trailers, recaps, or unwanted entries."],
    },
    "episode-management": {
        "title": "Episode management",
        "summary": "Bulk manage episodes SickChill-style without deleting them from the database.",
        "steps": ["Filter by season/status/search.", "Preview bulk changes.", "Mark selected or filtered episodes ignored, wanted, downloaded, or unmonitored.", "Use Include to bring an ignored episode back into queue/search counts."],
    },
    "ignore-rules": {
        "title": "Ignore rules",
        "summary": "Ignored episodes remain visible but are excluded from missing totals, searches, queue status, progress meters, and readiness math.",
        "steps": ["Use Ignore S00 Specials to ignore all specials for one show.", "Use the global Season 00 setting for all shows.", "Use episode-level ignore for trailers, interviews, recaps, duplicates, or bad guide entries."],
    },
    "download-center": {
        "title": "Download Center",
        "summary": "Validate downloader setup, monitor handoffs, and check queue polling from one place.",
        "steps": ["Run Test Downloader.", "Send one selected episode search result.", "Open Jobs and Logs for progress/errors.", "Use blackhole only when client APIs are unavailable."],
    },
    "post-processing": {
        "title": "Post Processing",
        "summary": "Preview completed downloads before moving, copying, linking, or renaming media files.",
        "steps": ["Set completed download folder.", "Run Preview.", "Review matches/unmatched files.", "Process selected items first before processing all."],
    },
    "subtitles": {
        "title": "Subtitles",
        "summary": "Audit missing subtitle status safely without letting slow NAS/network paths hang the interface.",
        "steps": ["Use the default candidate cap for fast scans.", "Enable network subtitle scans only when NAS paths are responsive.", "Watch Jobs and Logs during long scans."],
    },
    "troubleshooting": {
        "title": "Troubleshooting",
        "summary": "Use Jobs for progress, Logs for errors, Database Safety for recovery, and System for runtime diagnostics.",
        "steps": ["Refresh with Ctrl+F5 after installing a new release.", "Check /jobs for running or stuck tasks.", "Check /logs for failing API calls.", "Open Database Safety before changing a damaged database."],
    },
}

WORKFLOW_MAP = [
    {"goal": "Add a new show", "start": "Add/Search Show", "next": "Open Show Detail and confirm episode rules", "help": "/help/getting-started"},
    {"goal": "Find missing episodes", "start": "Show Queue", "next": "Sort by Missing / Downloads, then search selected episodes", "help": "/help/show-queue"},
    {"goal": "Ignore specials", "start": "Show Detail or Manage Center", "next": "Use Ignore S00 Specials or bulk ignored rules", "help": "/help/ignore-rules"},
    {"goal": "Fix many episode statuses", "start": "Manage Center", "next": "Preview bulk update before apply", "help": "/help/episode-management"},
    {"goal": "Check download handoff", "start": "Download Center", "next": "Run Test Downloader and inspect Jobs/Logs", "help": "/help/download-center"},
    {"goal": "Process completed downloads", "start": "Post Processing", "next": "Preview completed folder before moving files", "help": "/help/post-processing"},
    {"goal": "Investigate slow/stuck work", "start": "Jobs and Logs", "next": "Open Database Safety and System if needed", "help": "/help/troubleshooting"},
]

def parity_items():
    return [asdict(item) for item in PARITY_ITEMS]

def parity_summary():
    counts = {}
    for item in PARITY_ITEMS:
        counts[item.status] = counts.get(item.status, 0) + 1
    return {
        "total": len(PARITY_ITEMS),
        "counts": counts,
        "items": parity_items(),
        "next_gaps": [item for item in parity_items() if item["status"] in {"Partial", "Missing"}],
    }

def help_section(slug: str):
    return HELP_SECTIONS.get(slug)

def help_index():
    return [{"slug": k, **v} for k, v in HELP_SECTIONS.items()]
