"""Previewed in-library renames with conflict checks and a recovery journal."""
from pathlib import Path
import json
import os
import uuid
import dbcore
import naming


def signature(path):
    stat=path.stat()
    return [stat.st_size,stat.st_mtime_ns,stat.st_ino]


def contained(path,root):
    return path.resolve().is_relative_to(root.resolve())


def preview(db,show_id,pattern,associated=True):
    with dbcore.connect(db,readonly=True) as c:
        row=c.execute('SELECT * FROM shows WHERE id=?',(show_id,)).fetchone()
        if not row:raise ValueError('Show not found')
        show=dict(row)
        if not show.get('location'):raise ValueError('Set the show library folder first')
        episodes=[dict(r) for r in c.execute("SELECT * FROM episodes WHERE show_id=? AND COALESCE(location,'')<>'' ORDER BY season,episode",(show_id,))]
        all_paths=[(r['show_id'],r['location']) for r in c.execute("SELECT show_id,location FROM episodes WHERE COALESCE(location,'')<>''")]
    root=Path(show['location'])
    if not root.is_dir():raise ValueError('The show library folder is unavailable')
    groups={}
    for ep in episodes:groups.setdefault(os.path.normcase(os.path.abspath(ep['location'])),[]).append(ep)
    result=[]
    for group in groups.values():
        source=Path(group[0]['location']);item={'episode_ids':[e['id'] for e in group],'source':str(source),'moves':[],'blocked':None}
        try:
            if source.is_symlink() or not source.is_file() or not contained(source,root):raise ValueError('Source is missing, linked, or outside this show folder')
            if any(sid!=show_id and os.path.normcase(os.path.abspath(p))==os.path.normcase(os.path.abspath(source)) for sid,p in all_paths):raise ValueError('File is also used by another show')
            dest=naming.configured_destination(root,show['name'],group,source,pattern,True,bool(show.get('season_folders',1)))
            pairs=[(source,dest)]
            if associated:pairs+=naming.associated_destinations(source,dest)
            item['destination']=str(dest)
            for src,dst in pairs:
                if src==dst:continue
                if src.is_symlink() or not contained(src,root) or not contained(dst,root):raise ValueError('A file path leaves the show folder')
                if dst.exists():raise ValueError('Destination already exists: '+str(dst))
                item['moves'].append({'source':str(src),'destination':str(dst),'signature':signature(src)})
        except (ValueError,OSError) as exc:item['blocked']=str(exc);item['moves']=[]
        result.append(item)
    destinations={}
    for item in result:
        for move in item['moves']:
            key=os.path.normcase(os.path.abspath(move['destination']))
            if key in destinations:
                item['blocked']='Multiple files would use the same destination'
                destinations[key]['blocked']=item['blocked']
            destinations[key]=item
    return {'show_id':show_id,'show_name':show['name'],'root':str(root),'pattern':pattern,'associated':associated,'items':result}


def move_exclusive(source,destination):
    """Never replace an existing destination, including one created after preview."""
    if os.name=='nt':os.rename(source,destination)
    else:
        os.link(source,destination)
        try:os.unlink(source)
        except BaseException:
            os.unlink(destination)
            raise


def write_journal(path,data):
    temp=path.with_suffix('.tmp')
    with temp.open('w',encoding='utf-8') as handle:
        json.dump(data,handle,indent=2);handle.flush();os.fsync(handle.fileno())
    os.replace(temp,path)


def apply(db,plan,selected,journal_dir):
    if not selected:raise ValueError('Select at least one file to rename')
    if any(type(i) is not int or i<0 or i>=len(plan['items']) for i in selected):raise ValueError('Invalid file selection')
    if len(set(selected))!=len(selected):raise ValueError('Duplicate file selection')
    journal_dir=Path(journal_dir);journal_dir.mkdir(parents=True,exist_ok=True)
    # Keep incomplete work visible after a crash instead of guessing which path to trust.
    for path in journal_dir.glob('*.json'):
        prior=json.loads(path.read_text(encoding='utf-8'))
        if prior.get('show_id')==plan['show_id'] and prior.get('state')=='pending':raise ValueError('An interrupted rename requires review: '+str(path))
    with dbcore.connect(db) as c:
        c.execute('BEGIN IMMEDIATE')
        fresh=preview(db,plan['show_id'],plan['pattern'],plan['associated'])
        if fresh!=plan:raise ValueError('The library changed since preview. Preview again.')
        items=[plan['items'][i] for i in selected]
        if any(i['blocked'] or not i['moves'] for i in items):raise ValueError('Selection includes blocked or unchanged files')
        path=journal_dir/(uuid.uuid4().hex+'.json')
        journal={'state':'pending','show_id':plan['show_id'],'items':items}
        write_journal(path,journal)
        moved=[]
        try:
            for item in items:
                for move in item['moves']:
                    src,dst=Path(move['source']),Path(move['destination'])
                    if signature(src)!=move['signature'] or not contained(dst,Path(plan['root'])):raise ValueError('A file changed during processing')
                    dst.parent.mkdir(parents=True,exist_ok=True)
                    move_exclusive(src,dst);moved.append((src,dst))
                for eid in item['episode_ids']:
                    c.execute('UPDATE episodes SET location=? WHERE id=? AND show_id=?',(item['destination'],eid,plan['show_id']))
                if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='media_fingerprints'").fetchone():
                    c.execute('UPDATE media_fingerprints SET path=? WHERE path=?',(item['destination'],item['source']))
            c.commit()
        except BaseException:
            c.rollback()
            rollback_ok=True
            for src,dst in reversed(moved):
                try:move_exclusive(dst,src)
                except OSError:rollback_ok=False
            if rollback_ok:journal['state']='rolled_back';write_journal(path,journal)
            raise
        journal['state']='completed';write_journal(path,journal)
    return {'renamed':len(items),'files':len(moved),'journal':str(path)}
