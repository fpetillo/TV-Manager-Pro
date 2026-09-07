"""Configured TV library destinations, independent of host path syntax."""
import ntpath
import posixpath
import re


def library_roots(raw):
    parts=str(raw or '').split('|')
    default=0
    if parts and parts[0].isdigit():
        default=int(parts.pop(0))
    roots=list(dict.fromkeys(p.strip() for p in parts if p.strip()))
    return roots, roots[default] if 0 <= default < len(roots) else (roots[0] if roots else '')


def show_destination(raw, root, folder):
    roots,_=library_roots(raw)
    if root not in roots:
        raise ValueError('Choose a configured library folder. Add library roots in Settings first.')
    folder=str(folder or '').strip()
    if not folder or folder in {'.','..'} or re.search(r'[<>:"/\\|?*\x00-\x1f]',folder) or folder.endswith(('.', ' ')) or folder.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
        raise ValueError('Enter a valid show folder name without slashes or reserved characters.')
    path=ntpath if ('\\' in root or ntpath.splitdrive(root)[0]) else posixpath
    if not path.isabs(root):
        raise ValueError('The configured library root must be an absolute path.')
    return path.join(root,folder)


def rebase_episode_location(location, old_root, new_root):
    """Update only descendants of the old show folder; never move files."""
    if not location or not old_root:
        return location
    path=ntpath if ('\\' in old_root or ntpath.splitdrive(old_root)[0]) else posixpath
    try:
        if path.normcase(path.commonpath([location,old_root])) != path.normcase(path.normpath(old_root)):
            return location
        relative=path.relpath(location,old_root)
        if relative=='.': return location
        new_path=ntpath if ('\\' in new_root or ntpath.splitdrive(new_root)[0]) else posixpath
        return new_path.join(new_root,*relative.replace('\\','/').split('/'))
    except ValueError:
        return location
