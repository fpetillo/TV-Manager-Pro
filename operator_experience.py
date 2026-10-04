from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def _scalar(db: Path, sql: str, default: int = 0) -> int:
    try:
        with sqlite3.connect(db) as cx:
            cx.row_factory = sqlite3.Row
            row = cx.execute(sql).fetchone()
            return int(row[0] if row else default)
    except Exception:
        return default


def _table_exists(cx: sqlite3.Connection, name: str) -> bool:
    row = cx.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return bool(row)


def launchpad_summary(db: Path, version: str, health: dict[str, Any] | None = None, network=None) -> dict[str, Any]:
    import dbcore
    import readiness
    health = dict(health or {})
    counts = health.get('counts') or {}
    imports = 0
    latest = None
    try:
        with dbcore.connect(db, readonly=True, wal=False) as cx:
            if _table_exists(cx, 'import_runs'):
                imports = int(cx.execute('SELECT COUNT(*) FROM import_runs').fetchone()[0])
                row = cx.execute('SELECT * FROM import_runs ORDER BY id DESC LIMIT 1').fetchone()
                latest = dict(row) if row else None
    except Exception:
        health['ok'] = False
    checklist = readiness.summary(db, version, health, network)
    return {
        'ok': True, 'version': version, 'database_exists': Path(db).exists(),
        'readiness': 'verified' if checklist['score']==100 else 'needs_attention',
        'readiness_score': checklist['score'], 'readiness_checklist': checklist,
        'readiness_explanation': checklist['explanation'],
        'counts': dict(shows=counts.get('shows',0), episodes=counts.get('episodes',0),
            import_runs=imports, missing_files=counts.get('missing_episode_files',0),
            duplicate_groups=counts.get('duplicate_groups',0),
            shows_without_location=counts.get('shows_without_location',0),
            metadata_gaps=counts.get('shows_missing_external_ids',0),
            metadata_stale_or_missing=counts.get('metadata_stale_or_missing',0)),
        'latest_import': latest,
        'actions': [dict(priority='attention',title=item['title'],detail=item['detail'],href=item['href'],label='Open correction page')
                    for item in checklist['checks'] if item['status']!='passed'],
    }


def setup_assistant_summary(db: Path, base: Path, version: str, health: dict[str, Any] | None = None, network=None) -> dict[str, Any]:
    """Return a guided setup/cutover checklist for operators.

    The goal is to make the product feel like an installed replacement system,
    not just a set of pages. Everything is defensive so it works during first
    run, after partial imports, and on machines that are being prepared for
    SickChill cutover.
    """
    db = Path(db)
    base = Path(base)
    counts = (health or {}).get('counts', {}) if isinstance(health, dict) else {}
    shows = _scalar(db, 'SELECT COUNT(*) FROM shows') if db.exists() else 0
    episodes = _scalar(db, 'SELECT COUNT(*) FROM episodes') if db.exists() else 0
    imports = _scalar(db, 'SELECT COUNT(*) FROM import_runs') if db.exists() else 0
    missing_files = int(counts.get('missing_episode_files') or 0)
    duplicate_groups = int(counts.get('duplicate_groups') or 0)
    folder_gaps = int(counts.get('shows_without_location') or 0)
    metadata_gaps = int(counts.get('shows_missing_external_ids') or counts.get('metadata_stale_or_missing') or 0)
    import readiness
    accepted = readiness.summary(db, version, health, network)
    checked = {row['key']: row['status']=='passed' for row in accepted['checks']}

    files = {
        'version_file': (base / 'VERSION').exists(),
        'env_example': (base / '.env.example').exists(),
        'run_script': (base / 'run.ps1').exists(),
        'prod_script': (base / 'run-prod.ps1').exists(),
        'linux_installer': (base / 'scripts' / 'install-linux-service.sh').exists(),
        'server_runbook': (base / 'docs' / 'SICKCHILL_REPLACEMENT_SERVER_INSTALL.md').exists(),
        'cutover_checklist': (base / 'docs' / 'SICKCHILL_CUTOVER_CHECKLIST.md').exists(),
    }

    stages = [
        {
            'id': 'install',
            'title': 'Install TV Manager side-by-side',
            'status': 'done' if files['run_script'] and files['version_file'] else 'attention',
            'detail': 'Package files and startup scripts are present.' if files['run_script'] else 'Extract the package into the final TV Manager folder.',
            'href': '/system',
            'action': 'Review System'
        },
        {
            'id': 'import',
            'title': 'Import SickChill safely',
            'status': 'done' if imports and shows else 'next',
            'detail': f'{shows} shows and {episodes} episodes are visible.' if shows else 'Use Analyze, Preview, then Import from a copied sickbeard.db.',
            'href': '/import',
            'action': 'Open Import Center'
        },
        {
            'id': 'health',
            'title': 'Clear Library Health findings',
            'status': 'done' if all(checked.get(key) for key in ['library','folders','files','duplicates','ids','metadata']) else 'attention',
            'detail': f'{missing_files} missing files, {duplicate_groups} duplicate groups, {folder_gaps} folder gaps, {metadata_gaps} metadata gaps.',
            'href': '/library-health',
            'action': 'Open Library Health'
        },
        {
            'id': 'configure',
            'title': 'Configure automation and quality',
            'status': 'done' if checked.get('search_download') and checked.get('processing') else ('next' if shows else 'blocked'),
            'detail': 'Review providers, download clients, quality profiles, naming, subtitles, backups and notifications.',
            'href': '/settings',
            'action': 'Open Settings'
        },
        {
            'id': 'cutover',
            'title': 'Cut over from SickChill',
            'status': 'done' if accepted['score']==100 else 'blocked',
            'detail': 'Stop SickChill only after import, health validation, and automation configuration are confirmed.',
            'href': '/launchpad',
            'action': 'Review Readiness Checks'
        },
    ]

    blockers = [item['title'] + ': ' + item['detail'] for item in accepted['checks'] if item['status']!='passed']

    return {
        'ok': True,
        'version': version,
        'database_exists': db.exists(),
        'counts': {
            'shows': shows,
            'episodes': episodes,
            'imports': imports,
            'missing_files': missing_files,
            'duplicate_groups': duplicate_groups,
            'folder_gaps': folder_gaps,
            'metadata_gaps': metadata_gaps,
        },
        'files': files,
        'stages': stages,
        'blockers': blockers,
        'readiness_score': accepted['score'],
        'ready_for_cutover': accepted['score']==100,
        'readiness_url': '/launchpad',
    }
