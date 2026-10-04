"""Installation checks and explicitly recorded operator acceptance tests."""
from datetime import datetime, timezone, timedelta
import hashlib
import json
import dbcore


REVIEWS = {
    'search_download': ('Search and download', '/download-center', 'Verify a search finds the correct episode at the chosen resolution, the downloader accepts it, and completion is reported. Record the show/episode and client tested.'),
    'processing': ('Episode processing and media servers', '/postprocess', 'Verify every configured library root is reachable by the account running TV Manager. Check a completed episode is processed into its show folder and appears in each enabled media server. Record the episode, destination and server result; state if no media server is used.'),
    'recovery': ('Backup and recovery', '/database-safety', 'Create a verified backup and test restoring a separate copy. Record the backup and recovery result without replacing the production library.'),
    'startup': ('Restart and scheduled operation', '/jobs', 'Verify startup after a server restart, saved settings, job history and a successful cycle of each enabled scheduled job. Record the outcome.'),
    'cutover': ('Single production manager', '/workflow', 'Verify only the intended manager schedules searches and processing, and keep the rollback backup. Record how the previous SickChill automation was stopped or that this is a new installation.'),
}


def init(db):
    with dbcore.connect(db) as c:
        c.execute('''CREATE TABLE IF NOT EXISTS readiness_evidence(
            check_id TEXT PRIMARY KEY, evidence TEXT NOT NULL, verified_at TEXT NOT NULL,
            fingerprint TEXT NOT NULL, verified_by TEXT NOT NULL)''')


def fingerprint(db, version):
    """Invalidate reviews on release or saved operational configuration changes."""
    data = {'version': version}
    with dbcore.connect(db, readonly=True, wal=False) as c:
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in ['settings', 'provider_definitions', 'media_servers', 'notification_services', 'quality_profiles', 'path_mappings', 'scheduler_jobs', 'shows']:
            if table in tables:
                columns = [r[1] for r in c.execute(f'PRAGMA table_info("{table}")')]
                columns = [name for name in columns if name not in {'updated_at','created_at'} and not name.startswith('last_')]
                if table == 'shows':
                    columns = [name for name in columns if name in {'id','name','location','quality_profile_id','preferred_resolution','paused','season_folders','scene','anime','air_by_date','metadata_provider','episode_order'}]
                if table == 'scheduler_jobs':
                    columns = [name for name in columns if name in {'name','enabled','interval_minutes'}]
                fields = ','.join('"'+name+'"' for name in columns)
                data[table] = sorted([list(r) for r in c.execute(f'SELECT {fields} FROM "{table}"')], key=lambda row: json.dumps(row, default=str))
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def record(db, version, key, body, user):
    if key not in REVIEWS or not isinstance(body, dict):
        raise ValueError('Choose an operator verification check.')
    if body.get('confirmed') is not True:
        raise ValueError('Confirm that you performed this verification.')
    evidence = str(body.get('evidence') or '').strip()
    if len(evidence) < 20 or len(evidence) > 2000:
        raise ValueError('Describe the test and result in 20 to 2000 characters. Do not include passwords or keys.')
    current = fingerprint(db, version)
    if body.get('fingerprint') != current:
        raise ValueError('Configuration changed. Refresh the checklist and repeat the affected verification before recording it.')
    with dbcore.connect(db) as c:
        c.execute('''INSERT INTO readiness_evidence VALUES(?,?,?,?,?)
            ON CONFLICT(check_id) DO UPDATE SET evidence=excluded.evidence,
            verified_at=excluded.verified_at,fingerprint=excluded.fingerprint,verified_by=excluded.verified_by''',
            (key, evidence, datetime.now(timezone.utc).isoformat(), current, user))


def clear(db, key):
    if key not in REVIEWS:
        raise ValueError('Unknown verification check.')
    with dbcore.connect(db) as c:
        c.execute('DELETE FROM readiness_evidence WHERE check_id=?', (key,))


def summary(db, version, health, network=None):
    health = health or {}
    counts = health.get('counts') or {}
    valid = health.get('ok') is True and not health.get('schema_warnings')
    checks = []
    def add(key, title, ok, detail, href, unknown=False):
        checks.append(dict(key=key, title=title, status='unverified' if unknown else ('passed' if ok else 'attention'), detail=detail, href=href, source='automatic'))
    add('library', 'Shows and episodes loaded', counts.get('shows',0)>0 and counts.get('episodes',0)>0,
        f"{counts.get('shows',0)} shows and {counts.get('episodes',0)} episodes.", '/manager', not valid)
    fields = [('folders','Show folder assignments','shows_without_location','/library-storage'),
              ('files','Existing episode files','missing_episode_files','/library-health'),
              ('duplicates','Duplicate candidates','duplicate_groups','/library-health'),
              ('ids','Show metadata identities','shows_missing_external_ids','/manage'),
              ('metadata','Metadata refresh','metadata_stale_or_missing','/manage')]
    for key,title,field,href in fields:
        known = valid and field in counts
        count = counts.get(field,0)
        add(key,title,known and count==0, f'{count} findings to resolve.' if known else 'Health check failed or is incomplete. Run Library Health.',href,not known)
    add('network','Saved network address active', bool(network) and not network.get('restart_required'),
        'Restart to apply the saved address and port.' if network and network.get('restart_required') else 'Current listener matches the saved configuration.' if network else 'Listener status is unavailable.', '/settings#network', not network)
    current = fingerprint(db, version)
    with dbcore.connect(db, readonly=True, wal=False) as c:
        exists = c.execute("SELECT 1 FROM sqlite_master WHERE name='readiness_evidence'").fetchone()
        stored = {r['check_id']: dict(r) for r in c.execute('SELECT * FROM readiness_evidence')} if exists else {}
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    for key,(title,href,instruction) in REVIEWS.items():
        saved = stored.get(key)
        try:
            fresh = bool(saved and saved['fingerprint']==current and datetime.fromisoformat(saved['verified_at'])>=cutoff)
        except (ValueError,TypeError):
            fresh = False
        checks.append(dict(key=key,title=title,href=href,detail=instruction,source='operator',
            status='passed' if fresh else 'unverified', review=saved,
            stale=bool(saved and not fresh)))
    passed = sum(item['status']=='passed' for item in checks)
    return dict(checks=checks, passed=passed,total=len(checks),score=100*passed//len(checks),
        fingerprint=current, checked_at=datetime.now(timezone.utc).isoformat(),
        explanation='Installation readiness combines automatic checks and operator-recorded tests. 100% requires every check to pass. It does not certify full SickChill feature parity. Recorded tests expire after 90 days or a release/configuration change.')
