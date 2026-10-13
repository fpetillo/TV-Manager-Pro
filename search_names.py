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


_QUALIFIER=re.compile(r'(?i)(?:19|20)\d\d|us|uk|au|nz|ca')
MATCH_MODES=('strict','loose')


def _identity(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value).casefold() if c.isalnum())


def _tokens(value):
    """Words of a title with apostrophes removed, &/+ as 'and' and dotted initials joined."""
    text=''.join(c for c in unicodedata.normalize('NFKD',str(value or '')).casefold() if not unicodedata.combining(c))
    text=re.sub("[%s]"%re.escape(APOSTROPHES),'',text)
    text=re.sub(r'\s*[&+]\s*',' and ',text)
    out,letters=[],[]
    for token in re.sub(r'[^0-9a-z]+',' ',text).split():
        if len(token)==1 and token.isalpha():letters.append(token);continue
        if letters:out.append(''.join(letters));letters=[]
        out.append(token)
    if letters:out.append(''.join(letters))
    return out


def extra_names(value):
    """Operator-entered extra search names: one per line, or separated by commas or semicolons."""
    out=[];seen=set()
    for part in re.split(r'[\r\n,;]+',str(value or '')):
        part=' '.join(part.split())
        if part and any(c.isalnum() for c in part) and part.casefold() not in seen and len(out)<10:
            out.append(part[:250]);seen.add(part.casefold())
    return out


def show_year(show):
    try:
        year=int(str(dict(show or {}).get('first_air_date') or '')[:4])
    except ValueError:
        return None
    return year if 1900<=year<=2100 else None


def title_matches(prefix,names,year=None):
    """True when a release prefix is one of the show's names.

    Punctuation, spacing, apostrophes, &/and, accents and dotted initials are
    ignored. A release may drop a leading The, drop a year or country that is
    part of the show's own name, or add the show's first-air year. Any other
    extra word (Band of Brothers, Brothers and Sisters, Brothers 1984) is a
    different show.
    """
    release=_tokens(prefix)
    if not release:return False
    joined=''.join(release)
    for name in names:
        words=_tokens(name)
        if not words:continue
        forms=[words]
        core=list(words)
        while core and _QUALIFIER.fullmatch(core[-1]):core=core[:-1]
        if core and core!=words:forms.append(core)
        for form in list(forms):
            if form[0]=='the' and len(form)>1:forms.append(form[1:])
        for form in forms:
            if joined==''.join(form):return True
            if year and joined==''.join(form)+str(year):return True
    return False


def _numbering_pattern(show,episode,season):
    if season is not None:
        return rf'(?i)(?<![a-z0-9])s0*{int(season)}(?![a-z0-9])',None
    if (show.get('air_by_date') or show.get('sports')) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(episode.get('airdate') or '')[:10]):
        year,month,day=str(episode['airdate'])[:10].split('-')
        return rf'(?<!\d){year}[ ._-]{month}[ ._-]{day}(?!\d)',None
    if show.get('anime') and episode.get('absolute_number') is not None:
        return rf'(?<![a-z0-9])0*{int(episode["absolute_number"])}(?:v\d+)?(?![a-z0-9])',None
    sn,en=episode.get('season'),episode.get('episode')
    if show.get('scene_numbering') and episode.get('scene_season') is not None and episode.get('scene_episode') is not None:
        sn,en=episode['scene_season'],episode['scene_episode']
    if sn is None or en is None:return None,'Could not verify the episode numbering for this title match.'
    return rf'(?i)(?<![a-z0-9])(?:s0*{int(sn)}[ ._-]*e0*{int(en)}|0*{int(sn)}x0*{int(en)})(?!\d)',None


def release_rejection(title,name,show=None,episode=None,season=None,names=None):
    """Reject a result unless its title is this show followed by the right numbering.

    name is the show name; names adds aliases and operator-entered search names.
    """
    show,episode=dict(show or {}),dict(episode or {})
    title=re.sub(r'^\s*(?:\[[^]\r\n]+\]\s*)+','',str(title or ''))
    if season is not None and re.search(r'(?i)s\d+[ ._-]*e\d+|\d+x\d+',title):return 'An episode release is not a season pack.'
    pattern,error=_numbering_pattern(show,episode,season)
    if error:return error
    accepted=[]
    for value in [name,*(names or [])]:
        if value and value not in accepted:accepted.append(value)
    candidates=[v for value in accepted for v in variants(value)]
    year=show_year(show)
    for match in re.finditer(pattern,title):
        if title_matches(title[:match.start()],candidates,year):return None
    return 'Not this show or episode: the title must be the show name ('+str(name)+') followed by the episode number.'
