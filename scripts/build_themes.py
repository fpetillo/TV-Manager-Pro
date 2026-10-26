"""Builds static/themes.css from static/style.css.

The base stylesheet is the Classic theme. Every other theme is a colour remap of it:
each rule that sets a colour gets a scoped copy under html[data-theme="<name>"] with
the colour translated by that theme's rules, followed by the hand-written finishing
touches in THEME_EXTRAS (backgrounds, glass blur, form controls).

Run after changing static/style.css:   python scripts/build_themes.py
The test suite fails if static/themes.css is out of date.
"""
from __future__ import annotations

import colorsys
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "static" / "style.css"
TARGET = ROOT / "static" / "themes.css"

sys.path.insert(0, str(ROOT))
from ui_themes import THEMES  # noqa: E402  (single list of themes)

COLOR_RE = re.compile(r"#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|rgba?\([^()]*\)")
COLOR_PROPS = re.compile(
    r"^(color|background|background-color|background-image|border(-top|-right|-bottom|-left)?(-color)?|"
    r"outline(-color)?|box-shadow|text-shadow|fill|stroke|caret-color|accent-color|column-rule(-color)?|"
    r"text-decoration(-color)?|--[\w-]+)$"
)


# ------------------------------------------------------------------ colours
class Color:
    __slots__ = ("r", "g", "b", "a")

    def __init__(self, r, g, b, a=1.0):
        self.r, self.g, self.b, self.a = r, g, b, a

    @classmethod
    def parse(cls, text: str) -> "Color | None":
        t = text.strip().lower()
        if t.startswith("#"):
            h = t[1:]
            if len(h) == 3:
                h = "".join(c * 2 for c in h)
            a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
            return cls(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)
        m = re.match(r"rgba?\(([^)]*)\)", t)
        if not m:
            return None
        parts = [p.strip() for p in re.split(r"[,\s/]+", m.group(1)) if p.strip()]
        if len(parts) < 3:
            return None
        try:
            r, g, b = (float(p[:-1]) * 2.55 if p.endswith("%") else float(p) for p in parts[:3])
            a = 1.0
            if len(parts) > 3:
                a = float(parts[3][:-1]) / 100 if parts[3].endswith("%") else float(parts[3])
        except ValueError:
            return None
        return cls(r, g, b, a)

    def hls(self):
        return colorsys.rgb_to_hls(self.r / 255, self.g / 255, self.b / 255)

    @classmethod
    def from_hls(cls, h, l, s, a=1.0):
        r, g, b = colorsys.hls_to_rgb(h, max(0.0, min(1.0, l)), max(0.0, min(1.0, s)))
        return cls(r * 255, g * 255, b * 255, a)

    @property
    def accent(self):
        """A saturated brand/status colour rather than a surface or text neutral."""
        _, l, s = self.hls()
        return s >= 0.5 and 0.32 <= l <= 0.85

    def css(self) -> str:
        r, g, b = (int(round(max(0, min(255, v)))) for v in (self.r, self.g, self.b))
        if self.a >= 0.999:
            return f"#{r:02x}{g:02x}{b:02x}"
        return f"rgba({r},{g},{b},{round(self.a, 3):g})"


# ------------------------------------------------------------------ roles
def role_of(prop: str, rule_has_accent_bg: bool) -> str:
    """What a colour does in this declaration: bg, border, shadow, text, accentvar or keep."""
    if prop.startswith("--"):
        name = prop.lower()
        if any(k in name for k in ("text", "muted", "fg")):
            return "text"
        if any(k in name for k in ("line", "border")):
            return "border"
        if "shadow" in name:
            return "shadow"
        if any(k in name for k in ("bg", "panel", "surface", "card", "sidebar")):
            return "bg"
        return "accentvar"
    if prop in ("color", "fill", "caret-color", "text-decoration", "text-decoration-color"):
        return "keep" if rule_has_accent_bg else "text"
    if prop.startswith(("border", "outline", "column-rule")):
        return "border"
    if prop in ("box-shadow", "text-shadow"):
        return "shadow"
    if prop.startswith("background"):
        return "bg"
    return "keep"


def glassy(c: Color, role: str) -> Color:
    h, l, s = c.hls()
    if c.accent or role in ("keep", "text", "accentvar", "shadow"):
        return c
    if role == "bg" and c.a >= 0.999 and l < 0.32:
        return Color(200, 215, 255, round(0.035 + l * 0.32, 3))
    if role == "border" and l < 0.4:
        return Color(255, 255, 255, 0.13 if c.a >= 0.999 else min(0.2, c.a + 0.06))
    return c


def midnight(c: Color, role: str) -> Color:
    h, l, s = c.hls()
    if c.accent or role in ("keep", "accentvar", "shadow"):
        return c
    if role == "bg" and l < 0.35:
        return Color.from_hls(h, l * 0.42, s * 0.2, c.a)
    if role == "border" and l < 0.45:
        return Color.from_hls(h, l * 0.78, s * 0.2, c.a)
    if role == "text":
        return Color.from_hls(h, l, s * 0.35, c.a)
    return c


def daylight(c: Color, role: str) -> Color:
    h, l, s = c.hls()
    if role == "keep":
        return c
    if role == "shadow":
        if c.accent:
            return c
        return Color(15, 23, 42, round(min(c.a, 0.3) * 0.4, 3))
    if c.accent:
        if role in ("text", "accentvar", "border") and l > 0.5:
            yellow = 0.08 <= h <= 0.19  # gold/amber needs to be much darker to read on white
            return Color.from_hls(h, 0.33 if yellow else (0.42 if s > 0.85 else 0.46), min(1.0, s * 1.05), c.a)
        return c
    if role in ("text", "accentvar"):
        if role == "accentvar" and l <= 0.6:
            return c
        return Color.from_hls(h, min(0.5, 0.08 + (1 - l) * 0.75), s * 0.6, c.a)
    if role == "bg":
        if c.a < 0.999:
            # Tints over the page: dark shading becomes light, light washes become dark.
            if l < 0.3:
                return Color(255, 255, 255, round(min(0.7, c.a * 1.6), 3))
            return Color(15, 23, 42, round(min(0.08, c.a), 3))
        if l < 0.5:
            return Color.from_hls(h, 1 - l * 0.55, s * 0.45, c.a)
        return c
    if role == "border":
        if c.a < 0.999:
            return Color(15, 23, 42, round(min(0.16, max(0.07, c.a)), 3))
        if l < 0.55:
            return Color.from_hls(h, 0.93 - l * 0.6, s * 0.4, c.a)
    return c


PAGE_SELECTOR = re.compile(r"^(:root|html|body)$")

MAPPERS = {"glassy": glassy, "midnight": midnight, "daylight": daylight}


# ------------------------------------------------------------------ css parsing
def strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def split_top(text: str, sep: str) -> list[str]:
    out, depth, cur, quote = [], 0, [], ""
    for ch in text:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == sep and depth == 0:
            out.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    out.append("".join(cur))
    return out


def parse_blocks(css: str):
    """Returns ('rule', selector, body) and ('at', prelude, children) items."""
    i, n = 0, len(css)
    items = []
    while i < n:
        j = css.find("{", i)
        if j < 0:
            break
        prelude = css[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            if css[k] == "{":
                depth += 1
            elif css[k] == "}":
                depth -= 1
            k += 1
        body = css[j + 1:k - 1]
        if prelude.startswith("@"):
            if prelude.startswith(("@media", "@supports")):
                items.append(("at", prelude, parse_blocks(body)))
            # @keyframes, @font-face and the like are not themed.
        elif prelude:
            items.append(("rule", prelude, body))
        i = k
    return items


def scope(selector: str, theme: str) -> str:
    root = f'html[data-theme="{theme}"]'
    out = []
    for sel in split_top(selector, ","):
        sel = " ".join(sel.split())
        if not sel:
            continue
        if sel.startswith(":root"):
            out.append(root + sel[5:])
        elif re.match(r"html(?![\w-])", sel):
            out.append(root + sel[4:])
        else:
            out.append(f"{root} {sel}")
    return ",".join(out)


def declarations(body: str):
    for part in split_top(body, ";"):
        if ":" not in part:
            continue
        prop, value = part.split(":", 1)
        yield prop.strip().lower(), value.strip()


def rule_has_accent_bg(decls) -> bool:
    for prop, value in decls:
        if prop in ("background", "background-color"):
            first = COLOR_RE.search(value)
            if first:
                c = Color.parse(first.group(0))
                if c and c.accent and c.a > 0.6:
                    return True
    return False


def remap_value(value: str, theme: str, role: str) -> str:
    mapper = MAPPERS[theme]

    def sub(m):
        c = Color.parse(m.group(0))
        if not c:
            return m.group(0)
        mapped = mapper(c, role).css()
        return m.group(0) if mapped == c.css() else mapped

    return COLOR_RE.sub(sub, value)


def theme_rules(items, theme: str) -> list[str]:
    out = []
    for kind, prelude, payload in items:
        if kind == "at":
            inner = theme_rules(payload, theme)
            if inner:
                out.append(prelude + "{" + "".join(inner) + "}\n")
            continue
        decls = list(declarations(payload))
        accent_bg = rule_has_accent_bg(decls)
        page = all(PAGE_SELECTOR.match(" ".join(s.split())) for s in split_top(prelude, ","))
        changed = []
        for prop, value in decls:
            if not COLOR_PROPS.match(prop) or not COLOR_RE.search(value):
                continue
            if page and prop.startswith("background"):
                continue  # the page backdrop comes from THEME_EXTRAS
            new = remap_value(value, theme, role_of(prop, accent_bg))
            changed.append((prop, new, new != value))
        # Rules with unchanged colours are copied too: a scoped copy of a general rule must
        # not outrank a more specific base rule that was left alone (keeps the cascade).
        if changed:
            out.append(scope(prelude, theme) + "{" + ";".join(f"{p}:{v}" for p, v, _ in changed) + "}\n")
    return out


# ------------------------------------------------------------------ hand-written finishing
GLASS_SURFACES = (
    ".panel,.card,.dash-card,.show-list-panel,.appnav.side-nav,.command-dock,.topbar,"
    ".launch-hero,.season-block,.modal"
)

THEME_EXTRAS = {
    "glassy": f"""
html[data-theme="glassy"]{{background:#0b1024;color-scheme:dark;--glass-line:rgba(255,255,255,.18)}}
html[data-theme="glassy"] body{{background:
  radial-gradient(900px 640px at 4% -4%,rgba(132,94,255,.62),transparent 60%),
  radial-gradient(820px 600px at 98% 2%,rgba(0,200,255,.46),transparent 58%),
  radial-gradient(760px 620px at 40% 62%,rgba(52,110,255,.22),transparent 62%),
  radial-gradient(980px 720px at 70% 112%,rgba(255,92,170,.40),transparent 60%),
  linear-gradient(160deg,#0b0f26 0%,#111a40 46%,#0a1128 100%) fixed}}
html[data-theme="glassy"] :is({GLASS_SURFACES}){{
  background:linear-gradient(145deg,rgba(255,255,255,.12),rgba(255,255,255,.035) 55%,rgba(255,255,255,.06))!important;
  border-color:var(--glass-line)!important;
  -webkit-backdrop-filter:blur(22px) saturate(170%);backdrop-filter:blur(22px) saturate(170%);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.22),inset 0 -1px 0 rgba(255,255,255,.04),0 12px 36px rgba(3,6,20,.40)!important}}
html[data-theme="glassy"] :is(input,select,textarea){{background:rgba(8,12,28,.42);border-color:rgba(255,255,255,.16)}}
html[data-theme="glassy"] :is(.secondary,.btn.secondary){{background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.14)}}
html[data-theme="glassy"] :is(.blue,.btn.blue){{background:linear-gradient(135deg,rgba(94,140,255,.92),rgba(64,196,255,.85));box-shadow:0 6px 22px rgba(64,140,255,.35)}}
""",
    "midnight": """
html[data-theme="midnight"]{background:#000;color-scheme:dark}
html[data-theme="midnight"] body{background:#000}
""",
    "daylight": """
html[data-theme="daylight"]{background:#eef3fa;color-scheme:light}
html[data-theme="daylight"] body{background:linear-gradient(180deg,#f5f8fd 0%,#e9eff8 100%);color:#172033}
html[data-theme="daylight"] :is(input,select,textarea){color:#172033}
html[data-theme="daylight"] :is(input,textarea)::placeholder{color:#7b8799}
""",
}


def build() -> str:
    items = parse_blocks(strip_comments(SOURCE.read_text(encoding="utf-8")))
    parts = [
        "/* Generated by scripts/build_themes.py from static/style.css. Do not edit by hand. */\n",
        "/* Themes: " + ", ".join(f"{k} ({v[0]})" for k, v in THEMES.items()) + " */\n",
    ]
    for theme in MAPPERS:
        parts.append(f"\n/* ===== {THEMES[theme][0]} ===== */\n")
        parts.extend(theme_rules(items, theme))
        parts.append(THEME_EXTRAS[theme].lstrip("\n"))
    return "".join(parts)


def main(argv: list[str]) -> int:
    css = build()
    if "--check" in argv:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current != css:
            print("static/themes.css is out of date; run: python scripts/build_themes.py")
            return 1
        print("static/themes.css is up to date")
        return 0
    TARGET.write_text(css, encoding="utf-8", newline="\n")
    print(f"Wrote {TARGET.relative_to(ROOT)} ({len(css):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
