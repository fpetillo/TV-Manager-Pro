"""Library calendar and RFC 5545 all-day air-date subscriptions."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import hmac
import secrets
import engine
import episode_dates


def episodes(start,end,include_specials=False):
    start,end=date.fromisoformat(start),date.fromisoformat(end)
    if end<start or (end-start).days>366:raise ValueError('Choose a calendar range of up to one year.')
    with engine.cx() as c:
        c.create_function('episode_airdate',1,episode_dates.normalize)
        rows=c.execute('''SELECT e.id,e.show_id,e.season,e.episode,e.name,e.airdate,e.status,
            s.name show_name,s.network FROM episodes e JOIN shows s ON s.id=e.show_id
            WHERE date(episode_airdate(e.airdate)) BETWEEN ? AND ?
            AND COALESCE(e.ignored,0)=0 AND lower(COALESCE(e.status,''))<>'ignored'
            AND (? OR e.season<>0) ORDER BY date(episode_airdate(e.airdate)),s.name,e.season,e.episode''',
            (start.isoformat(),end.isoformat(),int(include_specials))).fetchall()
    return [dict(r)|{'airdate':episode_dates.normalize(r['airdate'])} for r in rows]


def escape(value):
    return str(value or '').replace('\\','\\\\').replace('\r','').replace('\n',r'\n').replace(';',r'\;').replace(',',r'\,')


def fold(line):
    result=[];part=''
    for char in line:
        if len((part+char).encode('utf-8'))>75:
            result.append(part);part=' '
        part+=char
    return '\r\n'.join(result+[part])


def feed(rows):
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//TV Manager Pro//Episode Calendar//EN','CALSCALE:GREGORIAN','METHOD:PUBLISH','X-WR-CALNAME:TV Manager Episodes']
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    for e in rows:
        aired=date.fromisoformat(e['airdate'])
        summary=f"{e['show_name']} S{int(e['season']):02d}E{int(e['episode']):02d} - {e['name'] or ''}"
        lines+=['BEGIN:VEVENT',f"UID:episode-{e['show_id']}-{e['id']}@tvmanager.local",'DTSTAMP:'+stamp,
            'DTSTART;VALUE=DATE:'+aired.strftime('%Y%m%d'),'DTEND;VALUE=DATE:'+(aired+timedelta(days=1)).strftime('%Y%m%d'),
            'SUMMARY:'+escape(summary),'DESCRIPTION:'+escape(f"{e.get('network') or ''}\n{e.get('status') or ''}"),'TRANSP:TRANSPARENT','END:VEVENT']
    return '\r\n'.join(fold(line) for line in lines+['END:VCALENDAR'])+'\r\n'


def rotate_token():
    token=secrets.token_urlsafe(32)
    engine.set_setting('TVManager','calendar_token_hash',hashlib.sha256(token.encode()).hexdigest(),is_secret=1)
    return token


def verify_token(token):
    if not token:return False
    expected=engine.get_setting('TVManager','calendar_token_hash','')
    return bool(expected) and hmac.compare_digest(expected,hashlib.sha256(str(token).encode()).hexdigest())
