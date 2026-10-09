#requires -Version 5.1
<#
Updates an existing source installation, without Git. Finish jobs and stop TV
Manager (including its startup task/service) before running. Leaves it stopped.
Example:
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\update-server.ps1
#>
[CmdletBinding()]
param(
    [string]$InstallDir = 'C:\Acuityware TV Manager',
    [ValidatePattern('^\d+\.\d+\.\d+$')][string]$Version = '18.18.0',
    [string]$ArchivePath = ''
)
$ErrorActionPreference = 'Stop'
try {
    $Root = (Resolve-Path -LiteralPath $InstallDir).ProviderPath
    $Python = Join-Path $Root '.venv\Scripts\python.exe'
    if (!(Test-Path -LiteralPath $Python -PathType Leaf)) {
        throw "Working Python environment missing: $Python. Repair it before updating."
    }
    # Run the updater with base Python so the installation's environment can be
    # backed up and restored without holding its python.exe open.
    $BasePython = & $Python -I -c 'import sys; print(sys._base_executable)'
    if ($LASTEXITCODE -ne 0 -or !$BasePython -or !(Test-Path -LiteralPath $BasePython -PathType Leaf)) {
        throw 'The installed Python environment is broken. Repair it before updating.'
    }
    if ($ArchivePath) { $ArchivePath = (Resolve-Path -LiteralPath $ArchivePath).ProviderPath }
    $Updater = @'
import argparse
from contextlib import contextmanager, closing
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import urllib.request
import uuid
import zipfile

BACKUP_EXCLUDE = {'.git', 'backups', '.runtime'}
CACHE_DIRS = {'__pycache__', '.pytest_cache'}
DEPLOY_DIRS = {'static', 'templates', 'docs', 'scripts', 'installer', 'tests'}
MAX_ARCHIVE = 128 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024

def version_tuple(value):
    if not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise ValueError('Version must have the form 18.12.0.')
    return tuple(map(int, value.split('.')))

def digest(path):
    result = hashlib.sha256()
    with long_path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()

def long_path(path):
    # Deep backup paths must work even without Windows long-path policy enabled.
    value = str(Path(path).absolute())
    if os.name == 'nt' and not value.startswith('\\\\?\\'):
        value = '\\\\?\\UNC\\' + value[2:] if value.startswith('\\\\') else '\\\\?\\' + value
    return Path(value)

def copy_file(source, destination):
    return shutil.copy2(long_path(source), long_path(destination))

def no_link(path):
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Linked/reparse paths require a manual update: ' + str(path))

def contained(root, relative):
    path = root.joinpath(*PurePosixPath(relative).parts)
    if not path.resolve().is_relative_to(root.resolve()) or path == root:
        raise ValueError('Unsafe update path: ' + relative)
    for part in [path, *path.parents]:
        no_link(part)
        if part == root:
            break
    return path

def deployable(parts):
    # Runtime state is never installed, even if accidentally included in a ZIP.
    if any(p.lower() in {'.git', '.venv', '.runtime', 'backups', 'imports', 'logs',
                           'recovery', 'managed_trash', 'uploads', 'diagnostics',
                           'archive-staging', 'rename-journals', '.acquisition-locks'} for p in parts):
        return False
    name = parts[-1].lower()
    if (name.startswith('.env') and name != '.env.example') or name in {'config.ini', '.tvmanager-session-key'}:
        return False
    if name.endswith(('.db', '.db-wal', '.db-shm', '.log', '.backup', '.zip')):
        return False
    if len(parts) > 1:
        return parts[0] in DEPLOY_DIRS and not any(p.startswith('.') for p in parts)
    return name in {'version', 'license', '.env.example'} or Path(name).suffix in {'.py', '.ps1', '.md', '.json', '.txt', '.spec', '.sh'}

def stage_archive(archive, stage, version):
    root_name = 'TV-Manager-Pro-' + version
    seen, selected, total = set(), [], 0
    with zipfile.ZipFile(archive) as source:
        for item in source.infolist():
            name = item.orig_filename.rstrip('/')
            parts = name.split('/')
            if (not name or '\\' in name or parts[0] != root_name
                or any(p in {'', '.', '..'} or ':' in p or p.endswith((' ', '.'))
                       or re.search(r'[<>"|?*\x00-\x1f]', p)
                       or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', p, re.I) for p in parts)):
                raise ValueError('Unsafe or unexpected path in release ZIP.')
            if stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('Release ZIP contains a symbolic link.')
            key = name.casefold()
            if key in seen:
                raise ValueError('Release ZIP contains duplicate paths.')
            seen.add(key)
            total += item.file_size
            if total > MAX_EXPANDED or item.file_size > 64 * 1024 * 1024 or len(seen) > 20000:
                raise ValueError('Release ZIP exceeds source update limits.')
            if not item.is_dir() and len(parts) > 1 and deployable(parts[1:]):
                relative = '/'.join(parts[1:])
                target = contained(stage, relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(item) as incoming, target.open('xb') as outgoing:
                    shutil.copyfileobj(incoming, outgoing)
                selected.append(relative)
    for required in ['VERSION', 'RELEASE_MANIFEST.json', 'app.py', 'server.py', 'runtime_guard.py',
                     'requirements.txt', 'run-prod.ps1', 'templates/settings.html', 'static/app.js']:
        if required not in selected:
            raise ValueError('Release ZIP is incomplete: ' + required)
    if (stage / 'VERSION').read_text(encoding='utf-8-sig').strip() != version:
        raise ValueError('Release VERSION does not match requested version.')
    if json.loads((stage / 'RELEASE_MANIFEST.json').read_text(encoding='utf-8-sig'))['version'] != version:
        raise ValueError('Release manifest does not match requested version.')
    for relative in selected:
        if relative.endswith('.py'):
            compile((stage / relative).read_bytes(), relative, 'exec')
    return selected

@contextmanager
def installation_lock(root):
    folder = contained(root, '.runtime')
    folder.mkdir(exist_ok=True)
    path = contained(root, '.runtime/.media-files.lock')
    with path.open('a+b') as handle:
        if path.stat().st_size == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        import msvcrt
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise ValueError('TV Manager is running. Finish active jobs, stop TV Manager and its startup task/service, then run this script again.') from None
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

def inventory(root):
    files = []
    for folder, directories, names in os.walk(root, followlinks=False):
        parent = Path(folder)
        directories[:] = [d for d in directories if d not in CACHE_DIRS and not (parent == root and d in BACKUP_EXCLUDE)]
        for name in directories + names:
            no_link(parent / name)
        for name in names:
            if (not name.endswith(('.pyc', '.pyo')) and name != '.media-files.lock'
                and not (parent == root and name in BACKUP_EXCLUDE)):
                files.append((parent / name).relative_to(root).as_posix())
    return files

def check_database(path):
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as database:
        rows = database.execute('PRAGMA quick_check').fetchall()
        if rows != [('ok',)]:
            raise ValueError('Database check failed; update stopped. Restore a known-good database before continuing.')

def checked_run(command, root):
    subprocess.run(command, cwd=root, check=True)

def install_files(root, stage, files, changed):
    for relative in files:
        destination = contained(root, relative)
        changed.append(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        copy_file(stage / relative, destination)
        if digest(destination) != digest(stage / relative):
            raise OSError('Installed file verification failed: ' + relative)

def rollback(root, snapshot, changed, restore_environment):
    for relative in reversed(changed):
        destination = contained(root, relative)
        original = snapshot / relative
        if original.is_file():
            copy_file(original, destination)
        elif destination.exists():
            destination.unlink()
    if restore_environment:
        environment = contained(root, '.venv')
        # Only this verified installation child is removed; media/state is untouched.
        if environment.resolve().parent != root.resolve():
            raise ValueError('Unsafe environment rollback path.')
        shutil.rmtree(environment)
        shutil.copytree(long_path(snapshot / '.venv'), long_path(environment), copy_function=copy_file)

def update(root, version, archive_path=''):
    root = root.absolute()
    for parent in [root, *root.parents]:
        no_link(parent)
    for required in ['app.py', 'VERSION', 'tvmanager.db', 'runtime_guard.py', '.venv/Scripts/python.exe']:
        if not contained(root, required).is_file():
            raise ValueError('Not a supported existing source installation; missing ' + required)
    if (root / 'TVManagerService.exe').exists():
        raise ValueError('This installation contains the packaged Windows service. Use the service ZIP upgrade instructions; source updates do not replace the EXE.')
    old_version = (root / 'VERSION').read_text(encoding='utf-8-sig').strip()
    if version_tuple(version) < version_tuple(old_version):
        raise ValueError('Downgrades are not supported by this updater.')
    python = str(root / '.venv/Scripts/python.exe')
    with installation_lock(root), tempfile.TemporaryDirectory(prefix='tvmanager-update-') as workspace:
        work = Path(workspace).resolve()
        archive = work / 'release.zip'
        if archive_path:
            if Path(archive_path).stat().st_size > MAX_ARCHIVE:
                raise ValueError('Release archive is too large.')
            shutil.copyfile(archive_path, archive)
        else:
            url = 'https://github.com/fpetillo/TV-Manager-Pro/archive/refs/tags/v' + version + '.zip'
            print('Downloading official GitHub release v' + version + '...', flush=True)
            with urllib.request.urlopen(url, timeout=60) as response, archive.open('wb') as target:
                length = 0
                for block in iter(lambda: response.read(1024 * 1024), b''):
                    length += len(block)
                    if length > MAX_ARCHIVE:
                        raise ValueError('Release archive is too large.')
                    target.write(block)
        stage = work / 'source'
        stage.mkdir()
        files = stage_archive(archive, stage, version)
        for relative in files:
            target = contained(root, relative)
            if target.exists() and not target.is_file():
                raise ValueError('Release file conflicts with an installed directory: ' + relative)
        check_database(root / 'tvmanager.db')
        backup_parent = root.parent / (root.name + ' Update Backups')
        no_link(backup_parent)
        backup_parent.mkdir(exist_ok=True)
        backup = backup_parent / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-v' + old_version + '-' + uuid.uuid4().hex[:8])
        snapshot = backup / 'installation'
        snapshot.mkdir(parents=True)
        source_files = inventory(root)
        needed = sum(long_path(root / f).stat().st_size for f in source_files) + sum((stage / f).stat().st_size for f in files) + 100 * 1024 * 1024
        if shutil.disk_usage(backup_parent).free < needed:
            raise ValueError('Not enough free disk space for the backup and update.')
        print('Creating verified recovery backup (including Python environment): ' + str(backup), flush=True)
        hashes = {}
        for relative in source_files:
            target = snapshot / relative
            long_path(target.parent).mkdir(parents=True, exist_ok=True)
            copy_file(root / relative, target)
            hashes[relative] = digest(root / relative)
            if digest(target) != hashes[relative]:
                raise OSError('Backup verification failed: ' + relative)
        check_database(snapshot / 'tvmanager.db')
        record = {'installation': str(root), 'from_version': old_version, 'to_version': version,
                  'archive_sha256': digest(archive), 'backup_sha256': hashes,
                  'excluded': sorted(BACKUP_EXCLUDE | CACHE_DIRS) + ['*.pyc', '*.pyo', '.media-files.lock'],
                  'status': 'backup_verified', 'release_files': files}
        journal = backup / 'update.json'
        def save_status(status):
            record['status'] = status
            journal.write_text(json.dumps(record, indent=2), encoding='utf-8')
        save_status('backup_verified')
        (backup / 'RESTORE.txt').write_text(
            'Keep TV Manager and its startup task/service stopped.\n'
            'The installation folder here contains pre-update source, database, configuration and .venv.\n'
            'The .venv must be restored at the ORIGINAL installation path shown in update.json.\n'
            'Existing backups, Git history, runtime lease and caches are excluded and remain in place.\n'
            'If manual recovery is necessary, retain the failed installation separately and restore these files\n'
            'to the original location. Do not overlay an older database on newer WAL/SHM files.\n'
            'Do not restore this database after resuming production without reviewing newer work.\n', encoding='utf-8')
        changed, dependencies_started = [], False
        try:
            save_status('updating_dependencies')
            dependencies_started = True
            checked_run([python, '-m', 'pip', 'install', '--disable-pip-version-check', '-r', str(stage / 'requirements.txt')], root)
            checked_run([python, '-m', 'pip', 'check'], root)
            save_status('installing_source')
            install_files(root, stage, files, changed)
            save_status('installed_restart_required')
        except Exception:
            print('Update failed. Restoring previous source and Python environment...', flush=True)
            try:
                rollback(root, snapshot, changed, dependencies_started)
                save_status('rolled_back')
            except Exception as recovery_error:
                save_status('manual_recovery_required')
                print('Automatic recovery failed: ' + str(recovery_error), file=sys.stderr)
            print('Keep TV Manager stopped. Recovery backup: ' + str(backup), file=sys.stderr)
            raise
        print('\nUpdated source to v' + version + '. TV Manager remains stopped.')
        print('Database, settings, library paths and startup configuration preserved.')
        print('Recovery backup: ' + str(backup))
        print('Start with your existing task/service, OR run (not both):')
        print('powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' + str(root / 'run-prod.ps1') + '"')
        print('Verify v' + version + ' in About, then refresh the browser with Ctrl+F5.')
        print('For LAN access: Settings > Network; save 192.168.1.11 / 5050 if this computer owns that IP; restart.')
        return backup

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install-dir', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--archive', default='')
    args = parser.parse_args()
    try:
        update(Path(args.install_dir), args.version, args.archive)
    except Exception as error:
        print('UPDATE FAILED: ' + str(error), file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
'@
    # A temporary file avoids Windows PowerShell 5.1 native argument quoting
    # changing the embedded Python text. It contains code only, never settings.
    $HelperPath = [System.IO.Path]::GetTempFileName()
    try {
        [System.IO.File]::WriteAllText($HelperPath, $Updater, (New-Object System.Text.UTF8Encoding($false)))
        $Arguments = @('-I', $HelperPath, '--install-dir', $Root, '--version', $Version)
        if ($ArchivePath) { $Arguments += @('--archive', $ArchivePath) }
        & $BasePython @Arguments
        if ($LASTEXITCODE -ne 0) { throw 'Update did not complete. Review the error above; do not start a partial installation.' }
    } finally {
        Remove-Item -LiteralPath $HelperPath -Force -ErrorAction SilentlyContinue
    }
} catch {
    Write-Error $_
    exit 1
}
