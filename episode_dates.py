"""Normalize imported episode dates consistently across queue and searches."""
from datetime import datetime

def normalize(value):
    """Normalize legacy SickChill/imported airdate values to YYYY-MM-DD for API clients.

    Some SickChill/imported rows store dates as Python ordinals (for example
    737203) instead of normal ISO text.  Those values looked like IDs in the
    Show Queue screenshot, so normalize them before returning rows to the UI.
    Unknown numeric fragments such as ``1`` are not useful dates and are hidden.
    """
    if value is None:
        return ""
    text=str(value).strip()
    if not text or text in {"0","0000-00-00","None","null"}:
        return ""
    # Already ISO-ish
    try:
        if len(text) >= 10 and text[4] == '-' and text[7] == '-':
            return datetime.fromisoformat(text[:10]).date().isoformat()
    except Exception:
        pass
    # Common US imported values
    for fmt in ("%m/%d/%Y","%m-%d-%Y","%Y%m%d","%Y/%m/%d","%d-%b-%Y","%b %d, %Y"):
        try:
            return datetime.strptime(text[:20],fmt).date().isoformat()
        except Exception:
            pass
    # SickChill/Python ordinal dates occasionally appear in imported data.
    try:
        if text.isdigit() and 700000 <= int(text) <= 900000:
            return datetime.fromordinal(int(text)).date().isoformat()
    except Exception:
        pass
    # Unix timestamps occasionally appear in legacy data.
    try:
        if text.isdigit() and len(text) in (10,13):
            ts=int(text[:10])
            if ts > 0:
                return datetime.fromtimestamp(ts).date().isoformat()
    except Exception:
        pass
    # Small numeric fragments are not real dates; hide instead of showing noise.
    if text.isdigit():
        return ""
    return text
