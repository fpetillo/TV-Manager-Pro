"""One serving process per installation, including offline recovery tools."""
import atexit
from pathlib import Path
import media_operations

_lease = None


def acquire(base):
    global _lease
    if _lease is not None:
        return
    folder = Path(base) / '.runtime'
    folder.mkdir(exist_ok=True)
    lease = media_operations.exclusive(folder)
    try:
        lease.__enter__()
    except ValueError as exc:
        raise RuntimeError('TV Manager is already running from this installation. Stop that instance before starting or restoring another.') from exc
    _lease = lease
    atexit.register(release)


def release():
    global _lease
    if _lease is not None:
        lease, _lease = _lease, None
        lease.__exit__(None, None, None)
