"""Bounded punctuation-tolerant queries without renaming library shows."""
import re
import unicodedata

APOSTROPHES="'’‘ʼ`"


def variants(name):
    original=' '.join(str(name or '').split())
    folded=''.join(c for c in unicodedata.normalize('NFKD',original) if not unicodedata.combining(c))
    folded=folded.translate(str.maketrans({c:"'" for c in APOSTROPHES}))
    def words(value):return ' '.join(''.join(c if c.isalnum() else ' ' for c in value).split())
    joined=folded.replace("'",'')
    candidates=[original,words(joined),words(folded),
                ' '.join(''.join(c for c in joined if c.isalnum() or c.isspace()).split()),
                words(joined.replace('&',' and ')),words(re.sub(r"(?i)'s\b",'',folded))]
    out=[];seen=set()
    for value in candidates:
        if value and any(c.isalnum() for c in value) and value.casefold() not in seen:
            out.append(value);seen.add(value.casefold())
    return out[:6]


def _identity(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value).casefold() if c.isalnum())


def release_rejection(title,name,show=None,episode=None,season=None):
    """Require the full title prefix and numbering on broadened text searches."""
    show,episode=dict(show or {}),dict(episode or {})
    title=re.sub(r'^\s*(?:\[[^]\r\n]+\]\s*)+','',str(title or ''))
    if season is not None:
        pattern=rf'(?i)(?<![a-z0-9])s0*{int(season)}(?![a-z0-9])'
        if re.search(r'(?i)s\d+[ ._-]*e\d+|\d+x\d+',title):return 'An episode release is not a season pack.'
    elif (show.get('air_by_date') or show.get('sports')) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(episode.get('airdate') or '')[:10]):
        year,month,day=str(episode['airdate'])[:10].split('-')
        pattern=rf'(?<!\d){year}[ ._-]{month}[ ._-]{day}(?!\d)'
    elif show.get('anime') and episode.get('absolute_number') is not None:
        pattern=rf'(?<![a-z0-9])0*{int(episode["absolute_number"])}(?:v\d+)?(?![a-z0-9])'
    else:
        sn,en=episode.get('season'),episode.get('episode')
        if show.get('scene_numbering') and episode.get('scene_season') is not None and episode.get('scene_episode') is not None:
            sn,en=episode['scene_season'],episode['scene_episode']
        if sn is None or en is None:return 'Could not verify the episode numbering for this title match.'
        pattern=rf'(?i)(?<![a-z0-9])(?:s0*{int(sn)}[ ._-]*e0*{int(en)}|0*{int(sn)}x0*{int(en)})(?!\d)'
    identities={_identity(value) for value in variants(name)}
    if any(_identity(title[:match.start()]) in identities for match in re.finditer(pattern,title)):
        return None
    return 'The broader title search returned a different show or episode number.'
