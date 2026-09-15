"""Per-episode OS locks shared by manual, bulk and scheduled search workers."""
from contextlib import contextmanager
from pathlib import Path
import hashlib
import media_operations

@contextmanager
def exclusive(database, operation, episode_id):
    token = hashlib.sha256(f'{operation}:{int(episode_id)}'.encode()).hexdigest()[:24]
    folder = Path(database).resolve().parent / '.acquisition-locks' / token
    folder.mkdir(parents=True, exist_ok=True)
    try:
        with media_operations.exclusive(folder):
            yield
    except ValueError as exc:
        if str(exc).startswith('Another library file operation'):
            raise ValueError('Another search or download handoff for this episode is running. Wait for it to finish.') from exc
        raise
