"""Transactional management of configured TV library roots."""
import ntpath
import posixpath
import re
from library_destinations import library_roots


def path_key(path):
    path=str(path or '').strip()
    module=ntpath if ('\\' in path or ntpath.splitdrive(path)[0]) else posixpath
    return module.normcase(module.normpath(path))


def validate_root(value):
    value=str(value or '').strip()
    if not value or re.search(r'[|\x00-\x1f<>"?*]',value):
        raise ValueError('Enter an absolute Windows, network share or Linux directory path.')
    module=ntpath if ('\\' in value or ntpath.splitdrive(value)[0]) else posixpath
    if not module.isabs(value) or (module is ntpath and not ntpath.splitdrive(value)[0]):
        raise ValueError('Use a complete path such as D:\\TV or \\\\server\\share\\TV.')
    return module.normpath(value)


def contains(root,location):
    if not location:return False
    module=ntpath if ('\\' in root or ntpath.splitdrive(root)[0]) else posixpath
    try:return module.normcase(module.commonpath([root,location]))==module.normcase(module.normpath(root))
    except ValueError:return False


def read_roots(c):
    row=c.execute("SELECT value FROM settings WHERE lower(section)='general' AND lower(name)='root_dirs'").fetchone()
    return library_roots(row['value'] if row else '')


def locations(c):
    roots,default=read_roots(c)
    shows=[dict(x) for x in c.execute('SELECT id,name,location FROM shows WHERE location IS NOT NULL ORDER BY name')]
    return [dict(path=root,is_default=root==default,shows=[s for s in shows if contains(root,s['location'])]) for root in roots]


class LocationInUse(ValueError):
    def __init__(self,shows):
        super().__init__('This location is used by shows. Reassign their library folders before editing or removing it.')
        self.shows=shows


def change(c,body):
    action=body.get('action')
    roots,default=read_roots(c)
    old=next((p for p in roots if path_key(p)==path_key(body.get('path'))),None)
    if action not in {'add','edit','remove','default'}:raise ValueError('Unknown location action.')
    if action!='add' and old is None:raise ValueError('Location no longer exists. Refresh the list.')
    if action in {'edit','remove'}:
        used=[dict(s) for s in c.execute('SELECT id,name,location FROM shows WHERE location IS NOT NULL ORDER BY name') if contains(old,s['location'])]
        if used:raise LocationInUse(used)
    if action in {'add','edit'}:
        new=validate_root(body.get('new_path'))
        if any(path_key(p)==path_key(new) for p in roots if p!=old or action=='add'):raise ValueError('That location is already configured.')
        if action=='add':
            roots.append(new)
            if not default:default=new
        else:
            roots[roots.index(old)]=new
            if default==old:default=new
    elif action=='remove':
        roots.remove(old)
        if default==old:default=roots[0] if roots else ''
    else:default=old
    raw=str(roots.index(default))+'|'+'|'.join(roots) if roots else ''
    row=c.execute("SELECT section,name FROM settings WHERE lower(section)='general' AND lower(name)='root_dirs'").fetchone()
    if row:
        c.execute('UPDATE settings SET value=?,source=?,updated_at=CURRENT_TIMESTAMP WHERE section=? AND name=?',(raw,'tvmanager',row['section'],row['name']))
    else:
        c.execute("INSERT INTO settings(section,name,value,is_secret,source,updated_at) VALUES('General','root_dirs',?,0,'tvmanager',CURRENT_TIMESTAMP)",(raw,))
    return locations(c)
