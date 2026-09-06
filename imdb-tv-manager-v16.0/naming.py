from __future__ import annotations
from pathlib import Path
import re

WINDOWS_RESERVED={"CON","PRN","AUX","NUL",*(f"COM{i}" for i in range(1,10)),*(f"LPT{i}" for i in range(1,10))}
INVALID='<>:"/\\\\|?*'

def safe_component(value):
    value=str(value or "").strip()
    value="".join("_" if ch in INVALID or ord(ch)<32 else ch for ch in value)
    value=value.rstrip(" .")
    if not value:value="_"
    if value.upper() in WINDOWS_RESERVED:value="_"+value
    return value

def _episode_token(episodes,padded):
    nums=[int(e["episode"]) for e in episodes]
    if not nums:return ""
    vals=[f"{n:02d}" if padded else str(n) for n in nums]
    return "E".join(vals)

def _episode_names(episodes):
    names=[safe_component(e.get("name") or f'Episode {int(e["episode"]):02d}') for e in episodes]
    return " + ".join(names)

def render(pattern,show_name,episodes,extension):
    if not episodes:raise ValueError("At least one episode is required")
    episodes=sorted(episodes,key=lambda e:(int(e["season"]),int(e["episode"])))
    season=int(episodes[0]["season"])
    if any(int(e["season"])!=season for e in episodes):
        raise ValueError("A single media file cannot be named across different seasons")
    # Longest tokens first so %S does not consume %SN/%0S.
    values={
        "%SN":safe_component(show_name),
        "%0S":f"{season:02d}",
        "%S":str(season),
        "%0E":_episode_token(episodes,True),
        "%E":_episode_token(episodes,False),
        "%EN":_episode_names(episodes),
    }
    out=str(pattern or "%SN - S%0SE%0E - %EN")
    for token in ("%SN","%0S","%0E","%EN","%S","%E"):
        out=out.replace(token,values[token])
    parts=re.split(r"[\\/]+",out)
    parts=[safe_component(x) for x in parts if x not in ("","." )]
    if not parts:raise ValueError("Naming pattern produced an empty filename")
    ext=str(extension or "")
    if ext and not ext.startswith("."):ext="."+ext
    if not parts[-1].lower().endswith(ext.lower()):
        parts[-1]+=ext
    return Path(*parts)

def configured_destination(show_root,show_name,episodes,source_name,pattern=None,rename=True,season_folders=True):
    source=Path(source_name)
    root=Path(show_root)
    if rename:
        rel=render(pattern or "Season %0S/%SN - S%0SE%0E - %EN",show_name,episodes,source.suffix)
        return root/rel
    if season_folders:
        season=int(episodes[0]["season"])
        return root/f"Season {season:02d}"/source.name
    return root/source.name


def associated_destinations(source,destination):
    source=Path(source);destination=Path(destination)
    allowed={".srt",".sub",".idx",".nfo",".jpg",".jpeg",".png",".webp",".ass",".ssa",".vtt"}
    out=[]
    parent=source.parent
    prefix=source.stem
    for f in parent.iterdir():
        if not f.is_file() or f==source:continue
        if f.suffix.lower() not in allowed:continue
        if not f.name.lower().startswith(prefix.lower()):continue
        tail=f.name[len(prefix):]
        out.append((f,destination.with_name(destination.stem+tail)))
    return out
