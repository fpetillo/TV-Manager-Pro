"""Explicit SickChill transfer methods with reversible per-file operations."""
from pathlib import Path
import os
import shutil
import uuid

METHODS={'move','copy','hardlink','symlink','symlink_reversed'}


def method(value):
    value=str(value or 'move').lower().replace('hard link','hardlink')
    if value not in METHODS:raise ValueError('Unsupported processing method. Choose Move, Copy, Hardlink or a symbolic-link method.')
    return value


def check_links(base,selected):
    if selected not in {'symlink','symlink_reversed'}:return
    folder=Path(base)/'.runtime';folder.mkdir(exist_ok=True)
    probe=folder/('link-check-'+uuid.uuid4().hex)
    try:os.symlink(str(folder),str(probe),target_is_directory=True)
    except OSError as exc:raise ValueError('This account cannot create symbolic links. Enable the operating system permission or choose Copy/Hardlink.') from exc
    finally:
        if probe.is_symlink():probe.unlink()


def transfer(source,destination,selected):
    source,destination=Path(source),Path(destination);selected=method(selected)
    if destination.exists() or destination.is_symlink():raise FileExistsError('Destination already exists: '+str(destination))
    if source.is_symlink():raise ValueError('Source is already a symbolic link; review it before processing.')
    if selected=='copy':shutil.copy2(source,destination)
    elif selected=='hardlink':os.link(source,destination)
    elif selected=='symlink_reversed':os.symlink(str(source.resolve()),str(destination))
    else:
        shutil.move(str(source),str(destination))
        if selected=='symlink':
            try:os.symlink(str(destination.resolve()),str(source))
            except OSError:
                shutil.move(str(destination),str(source));raise
    return (str(source),str(destination),selected)


def undo(operation):
    source,destination,selected=operation;source,destination=Path(source),Path(destination)
    if selected=='symlink':
        if not source.is_symlink() or source.resolve()!=destination.resolve():raise ValueError('Source link changed; manual recovery required.')
        source.unlink();shutil.move(str(destination),str(source))
    elif selected=='move':
        if source.exists() or source.is_symlink():raise ValueError('Source path is occupied; manual recovery required.')
        shutil.move(str(destination),str(source))
    else:destination.unlink()
