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


def launchpad_summary(db: Path, version: str, health: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return an operator-first product summary for the Launchpad screen.

    This intentionally favors clear next actions over raw tables. It is defensive
    so the screen works during first run, after partial imports, or on older DBs.
    """
    db = Path(db)
    shows = episodes = import_runs = 0
    latest_import = None
    try:
        with sqlite3.connect(db) as cx:
            cx.row_factory = sqlite3.Row
            if _table_exists(cx, 'shows'):
                shows = int(cx.execute('SELECT COUNT(*) FROM shows').fetchone()[0])
            if _table_exists(cx, 'episodes'):
                episodes = int(cx.execute('SELECT COUNT(*) FROM episodes').fetchone()[0])
            if _table_exists(cx, 'import_runs'):
                import_runs = int(cx.execute('SELECT COUNT(*) FROM import_runs').fetchone()[0])
                row = cx.execute('SELECT * FROM import_runs ORDER BY id DESC LIMIT 1').fetchone()
                latest_import = dict(row) if row else None
    except Exception as exc:
        latest_import = {'error': str(exc)}

    counts = (health or {}).get('counts', {}) if isinstance(health, dict) else {}
    missing_files = int(counts.get('missing_files') or 0)
    duplicate_groups = int(counts.get('duplicate_groups') or 0)
    shows_without_location = int(counts.get('shows_without_location') or 0)
    metadata_gaps = int(counts.get('metadata_gaps') or counts.get('shows_missing_ids') or 0)

    actions = []
    if not import_runs or shows == 0:
        actions.append({
            'priority': 'critical',
            'title': 'Import SickChill library',
            'detail': 'Start with Analyze, Preview, then Import so the replacement database has shows and episodes.',
            'href': '/import',
            'label': 'Open Import Center'
        })
    else:
        actions.append({
            'priority': 'good',
            'title': 'Import complete',
            'detail': f'{shows} shows and {episodes} episodes are visible in the active TV Manager database.',
            'href': '/manager',
            'label': 'Review Shows'
        })

    if missing_files or duplicate_groups or shows_without_location or metadata_gaps:
        actions.append({
            'priority': 'attention',
            'title': 'Resolve Library Health findings',
            'detail': f'{missing_files} missing files, {duplicate_groups} duplicate groups, {shows_without_location} shows without folders, {metadata_gaps} metadata gaps.',
            'href': '/library-health',
            'label': 'Open Library Health'
        })
    else:
        actions.append({
            'priority': 'good',
            'title': 'Library Health is clean',
            'detail': 'No major health findings were reported by the current health scan.',
            'href': '/library-health',
            'label': 'View Health'
        })

    actions.append({
        'priority': 'next',
        'title': 'Configure replacement automation',
        'detail': 'Set download clients, providers, quality profiles, subtitles, naming, backups and notifications before cutover.',
        'href': '/settings',
        'label': 'Open Settings'
    })
    actions.append({
        'priority': 'planned',
        'title': 'Cut over from SickChill safely',
        'detail': 'Run side-by-side first, validate imports, then stop SickChill only after TV Manager health checks are clean.',
        'href': '/workflow',
        'label': 'Open Workflow'
    })

    if shows == 0:
        readiness = 'not_ready'
        score = 15
    elif missing_files or duplicate_groups or shows_without_location:
        readiness = 'needs_attention'
        score = max(45, 85 - min(40, missing_files + duplicate_groups * 5 + shows_without_location * 2))
    else:
        readiness = 'ready_for_operator_review'
        score = 92 if import_runs else 70

    return {
        'ok': True,
        'version': version,
        'database_exists': db.exists(),
        'readiness': readiness,
        'readiness_score': score,
        'counts': {
            'shows': shows,
            'episodes': episodes,
            'import_runs': import_runs,
            'missing_files': missing_files,
            'duplicate_groups': duplicate_groups,
            'shows_without_location': shows_without_location,
            'metadata_gaps': metadata_gaps,
        },
        'latest_import': latest_import,
        'actions': actions,
    }



def setup_assistant_summary(db: Path, base: Path, version: str, health: dict[str, Any] | None = None) -> dict[str, Any]:
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
    missing_files = int(counts.get('missing_files') or 0)
    duplicate_groups = int(counts.get('duplicate_groups') or 0)
    folder_gaps = int(counts.get('shows_without_location') or 0)
    metadata_gaps = int(counts.get('metadata_gaps') or counts.get('shows_missing_ids') or 0)

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
            'status': 'attention' if (missing_files or duplicate_groups or folder_gaps or metadata_gaps) else ('done' if shows else 'blocked'),
            'detail': f'{missing_files} missing files, {duplicate_groups} duplicate groups, {folder_gaps} folder gaps, {metadata_gaps} metadata gaps.',
            'href': '/library-health',
            'action': 'Open Library Health'
        },
        {
            'id': 'configure',
            'title': 'Configure automation and quality',
            'status': 'next' if shows else 'blocked',
            'detail': 'Review providers, download clients, quality profiles, naming, subtitles, backups and notifications.',
            'href': '/settings',
            'action': 'Open Settings'
        },
        {
            'id': 'cutover',
            'title': 'Cut over from SickChill',
            'status': 'ready' if shows and not (missing_files or duplicate_groups or folder_gaps) else 'blocked',
            'detail': 'Stop SickChill only after import, health validation, and automation configuration are confirmed.',
            'href': '/workflow',
            'action': 'Open Workflow'
        },
    ]

    blockers = []
    if not shows:
        blockers.append('No shows are visible in TV Manager yet.')
    if missing_files:
        blockers.append(f'{missing_files} episode files are missing from disk.')
    if duplicate_groups:
        blockers.append(f'{duplicate_groups} duplicate groups need operator review.')
    if folder_gaps:
        blockers.append(f'{folder_gaps} shows have no folder path.')
    if not files['server_runbook']:
        blockers.append('Server replacement runbook is missing from the package.')

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
        'ready_for_cutover': bool(shows and not (missing_files or duplicate_groups or folder_gaps)),
    }
