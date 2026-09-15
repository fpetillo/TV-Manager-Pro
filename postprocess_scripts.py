"""Configured extra scripts with SickChill's six positional episode arguments."""
import json
from pathlib import Path
import engine
import process_runner


def settings():
    return json.loads(engine.get_setting('TVManager','postprocess_scripts','[]') or '[]')


def save(rows):
    if not isinstance(rows,list) or len(rows)>20:raise ValueError('Configure up to 20 processing scripts.')
    valid=[]
    for row in rows:
        path=Path(str(row.get('executable','')))
        if not path.is_absolute() or not path.is_file() or path.suffix.lower() in {'.bat','.cmd'}:
            raise ValueError('Use the full path to an executable or interpreter.')
        arguments=row.get('arguments',[])
        if not isinstance(arguments,list) or len(arguments)>50 or any(not isinstance(a,str) or '\x00' in a for a in arguments):raise ValueError('Enter each fixed argument on a separate line.')
        valid.append(dict(executable=str(path),arguments=arguments,enabled=engine.as_bool(row.get('enabled')),timeout=max(1,min(3600,int(row.get('timeout',60))))))
    engine.set_setting('TVManager','postprocess_scripts',json.dumps(valid))
    return valid


def run(destination,source,show_id,episode):
    with engine.cx() as c:show=dict(c.execute('SELECT * FROM shows WHERE id=?',(show_id,)).fetchone())
    positional=[str(destination),str(source),str(show.get('tvdb_id') or show.get('tmdb_id') or show_id),str(episode['season']),str(episode['episode']),str(episode.get('airdate') or '')]
    results=[]
    for row in settings():
        if not row.get('enabled'):continue
        try:
            result=process_runner.run([row['executable'],*row['arguments'],*positional],cwd=engine.BASE,timeout=row['timeout'])
        except Exception as exc:result={'ok':False,'error':str(exc)}
        results.append({'script':row['executable'],**result})
    return results
