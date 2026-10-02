"""Actionable library-folder checks for interactive metadata refresh."""
from pathlib import Path


def for_show(database, show_id):
    import dbcore
    with dbcore.connect(database,readonly=True) as c:
        show=c.execute('SELECT * FROM shows WHERE id=?',(show_id,)).fetchone()
        if not show:return None
        exists=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='path_mappings'").fetchone()
        mappings=[dict(r) for r in c.execute('SELECT * FROM path_mappings ORDER BY name,id')] if exists else []
    def mapped(value):
        for item in mappings:
            if item['enabled'] and value.lower().startswith(item['remote_path'].lower()):
                return item['local_path']+value[len(item['remote_path']):]
        return value
    return inspect(show,mapped)


def inspect(show, map_path):
    show=dict(show)
    location=str(show.get('location') or '').strip()
    if not location:
        problem='The episode storage folder is not defined.'
    else:
        try:
            if Path(map_path(location)).is_dir():return None
            problem='The episode storage folder is missing or unavailable to this server.'
        except (OSError,ValueError):
            problem='The episode storage folder is unavailable to this server.'
    return {'code':'show_folder_required','error':problem+' Choose a library folder to continue.',
            'show_id':show['id'],'name':show['name'],'location':location,
            'repair_url':f"/show/{show['id']}?repair_folder=1"}


def create(root, location, map_path):
    """Create only the chosen child, never recreate an unavailable storage root."""
    parent=Path(map_path(root))
    target=Path(map_path(location))
    try:
        if not parent.is_dir():raise ValueError('The selected library root is unavailable. Check the drive/share or choose another root.')
        if target.is_dir():return
        # Mapping can target a different mount; the mapped parent must already exist.
        if not target.parent.is_dir():raise ValueError('The destination parent is unavailable. Check path mappings or choose another folder.')
        target.mkdir(exist_ok=True)
        if not target.is_dir():raise ValueError('The destination is not a directory.')
    except OSError as error:
        raise ValueError('Could not access or create the show folder. Check permissions or choose another root.') from error
