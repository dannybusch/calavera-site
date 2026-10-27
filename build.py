#!/usr/bin/env python3
"""
Calavera Bremen – Static Site Generator
=======================================

Liest
  config.yml        Einstellungen der Website
  events/*.md       eine Datei pro Veranstaltung (YAML-Kopf + Markdown-Text),
                    Visual daneben mit gleichem Namen oder per "visual:"
  pages/*.md        feste Seiten (Safe Space, Über den Club, …)
  templates/        Jinja2-Vorlagen
  static/           CSS, JS, Schriften, Logo

und schreibt die fertige Website nach dist/.

Aufruf
  python build.py                          baut nach dist/
  python build.py --now "2026-11-08 12:00" tut so, als wäre es diese Zeit (zum Testen)
  python build.py --serve                  baut und startet eine Vorschau auf http://localhost:8000
  python build.py --strict                 bricht bei Fehlern in Event-Dateien ab (z. B. im Cronjob)
"""

from __future__ import annotations

import argparse
import hashlib
import html
import http.server
import json
import os
import re
import shutil
import socketserver
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import markdown
    import yaml
    from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
except ImportError as exc:  # pragma: no cover
    sys.exit(f"Fehlendes Python-Paket: {exc.name}. Bitte einmal ausführen:  pip install -r requirements.txt")

try:
    from PIL import Image, ImageChops, ImageFilter, ImageOps
except ImportError:  # Pillow ist optional: ohne Pillow werden Visuals nur kopiert
    Image = None

ROOT = Path(__file__).resolve().parent
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif")
WOCHENTAG = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
WOCHENTAG_LANG = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONAT = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
         "August", "September", "Oktober", "November", "Dezember"]

problems: list[str] = []


# Animationen für Kachel und Veranstaltungsseite ("effekte:" in der Event-Datei) – siehe README → Effekte
EFFEKTE = (
    "rauschnebel", "buehnennebel", "flyerausnebel",            # Nebel
    "gewitter", "fratzen",                                       # Halloween
    "snow", "twinklestar",                                       # Winter
    "grunge", "vhs", "flanell",                                  # 90er
    "konfetti", "regenbogenfolie", "seifenblasen", "discokugel", # Gute Laune
    "bassboom", "spraydose",                                     # Hip-Hop
    "glitch", "laser", "scanlines",                              # Dunkel / Elektronisch
    "retrogrid", "neon", "vinyl", "schwerelos",                  # 80er
    "lichterkette", "dampf", "kerzenlicht",                      # Advent / Honeycafé
    "gluehwuermchen", "spotlight", "cempasuchil", "feuerwerk",   # passend zu Titel / Ort
)
EFFEKT_ALIAS = {"bühnennebel": "buehnennebel", "flyer-aus-nebel": "flyerausnebel", "schnee": "snow", "sterne": "twinklestar",
                "twinkle": "twinklestar", "stars": "twinklestar", "glühwürmchen": "gluehwuermchen", "regenbogen": "regenbogenfolie",
                "holo": "regenbogenfolie", "disco": "discokugel", "papelpicado": "cempasuchil", "kerze": "kerzenlicht",
                "blasen": "seifenblasen", "graffiti": "spraydose", "synthwave": "retrogrid", "bass": "bassboom"}
# CSS-Dateien je Effekt (static/css/fx/<datei>.css); ohne Eintrag: Datei heißt wie der Effekt
EFFEKT_CSS = {"rauschnebel": ["nebel"], "flyerausnebel": ["nebel", "flyerausnebel"], "buehnennebel": ["buehnennebel"],
              "spotlight": ["buehnennebel", "spotlight"], "vhs": ["grunge", "vhs"]}


def fx_css_for(effekte) -> list[str]:
    """CSS-Dateien, die eine Seite für diese Effekte braucht (basis zuerst, keine doppelt)."""
    files = []
    for fx in effekte:
        for f in EFFEKT_CSS.get(fx, [fx]):
            if f not in files:
                files.append(f)
    return ["basis"] + files if files else []


def fx_particles(n: int, seed: str) -> list[dict]:
    """Feste Zufallswerte für Schneeflocken/Sterne (gleicher Build → gleiche Werte, kein JavaScript nötig)."""
    import random
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        out.append({
            "x": round((i + rnd.random()) / n * 100, 1),      # gleichmäßig über die Breite verteilt
            "y": round(rnd.uniform(4, 92), 1),
            "size": round(rnd.choice([2, 2.5, 3, 3, 4, 5, 6]) * rnd.uniform(.85, 1.15), 1),
            "dur": round(rnd.uniform(7, 15), 1),
            "delay": round(-rnd.uniform(0, 15), 1),           # negativ: beim Laden schon mitten im Fall
            "drift": round(rnd.uniform(-18, 18)),
            "sway": round(rnd.uniform(2.5, 5), 1),
            "op": round(rnd.uniform(.45, .95), 2),
            "tw": round(rnd.uniform(3.5, 7.5), 1),             # Sterne: Dauer eines Funkelns
            "tdelay": round(rnd.uniform(0, 8), 1),
            "rot": rnd.choice([0, 15, 30, 45]),
            "gold": rnd.random() < .45,
        })
    return out


def warn(msg: str) -> None:
    problems.append(msg)
    print(f"  ! {msg}")


# ------------------------------------------------------------------ Hilfen

def read_front_matter(path: Path) -> tuple[dict, str]:
    """Trennt den YAML-Kopf (zwischen ---) vom Markdown-Text."""
    text = path.read_text(encoding="utf-8").lstrip("\ufeff")
    m = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)(.*)$", text, re.S)
    if not m:
        return {}, text
    meta = yaml.safe_load(m.group(1)) or {}
    if not isinstance(meta, dict):
        raise ValueError("Der Kopf zwischen den --- ist kein gültiges YAML-Wörterbuch")
    return meta, m.group(2)


def as_list(value) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    # "Synthpop, Wave · EBM" → ["Synthpop", "Wave", "EBM"]
    return [p.strip() for p in re.split(r"\s*[,·|]\s*", str(value)) if p.strip()]


def parse_when(value, tz: ZoneInfo, *, base: datetime | None = None, what: str = "Zeit") -> datetime:
    """
    Akzeptiert "JJJJ-MM-TT HH:MM" (wie auf live.calavera.club), ein YAML-Datum/-Datetime
    oder – mit base – nur "HH:MM". Ein reines "HH:MM", das vor base liegt, gilt für den Folgetag.
    """
    if isinstance(value, datetime):
        return value.replace(tzinfo=tz) if value.tzinfo is None else value.astimezone(tz)
    if isinstance(value, date):
        raise ValueError(f"{what}: Uhrzeit fehlt (Format \"JJJJ-MM-TT HH:MM\")")
    s = str(value).strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2})[:.](\d{2})", s)
    if m:
        y, mo, d, h, mi = map(int, m.groups())
        return datetime(y, mo, d, h, mi, tzinfo=tz)
    m = re.fullmatch(r"(\d{1,2})[:.](\d{2})", s)
    if m and base is not None:
        h, mi = map(int, m.groups())
        dt = base.replace(hour=h, minute=mi, second=0, microsecond=0)
        if dt <= base:
            dt += timedelta(days=1)
        return dt
    raise ValueError(f"{what} \"{s}\" nicht verstanden (Format \"JJJJ-MM-TT HH:MM\")")


def plain_text(html_text: str) -> str:
    text = re.sub(r"<(br|/p|/li|/h\d|/blockquote)\b[^>]*>", " ", html_text)   # Blockgrenzen → Leerzeichen
    text = re.sub(r"<[^>]+>", "", text)                                         # Inline-Tags einfach entfernen
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def shorten(text: str, limit: int = 180) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:–- ")
    return cut + " …"


def copy_public(src: Path, dest: Path) -> None:
    """Datei kopieren und für den Webserver lesbar machen (Rechte der Quelle nicht übernehmen)."""
    shutil.copyfile(src, dest)
    os.chmod(dest, 0o644)


def md(text: str) -> str:
    # nl2br: ein einfacher Zeilenumbruch in der .md-Datei wird auch auf der Seite ein Umbruch
    return markdown.markdown(text, extensions=["extra", "sane_lists", "nl2br"], output_format="html")


def accent_palette(hex_color: str, ground: str = "#161616") -> dict:
    """
    Aus der Akzentfarbe (config.yml → site.accent) drei Varianten ableiten:
      accent          Flächen, Linien, Funkringe – unverändert
      accent_display  große Schrift (≥ 24 px): so wenig wie nötig aufgehellt, Kontrast ≥ 3 : 1
      accent_text     kleine Schrift: aufgehellt bis Kontrast ≥ 4,5 : 1
    Gemessen gegen die hellste dunkle Fläche der Seite, damit es überall reicht.
    """
    def rgb(h):
        h = h.lstrip("#")
        return [int(h[i:i + 2], 16) for i in (0, 2, 4)]

    def lum(c):
        def f(v):
            v /= 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        r, g, b = c
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

    def contrast(a, b):
        hi, lo = sorted((lum(a), lum(b)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)

    def tint(c, t):
        return [round(v + (255 - v) * t) for v in c]

    def to_hex(c):
        return "#" + "".join(f"{v:02x}" for v in c)

    base, bg = rgb(hex_color), rgb(ground)

    def lighten_until(target):
        t = 0.0
        while t < 1 and contrast(tint(base, t), bg) < target:
            t += 0.01
        return to_hex(tint(base, t))

    return {"accent": to_hex(base), "accent_rgb": ", ".join(map(str, base)),
            "accent_display": lighten_until(3.0), "accent_text": lighten_until(4.6)}


def text_palette(hex_color: str, page_bg: str = "#0b0b0b", ground: str = "#161616") -> dict:
    """
    Schriftfarben aus einem Grundton (config.yml → site.text) abstufen, indem er Richtung
    Hintergrund gemischt wird. "muted" wird nur so weit abgedunkelt, dass kleine Schrift
    auf der hellsten dunklen Fläche noch 4,6 : 1 Kontrast hat.
    """
    def rgb(h):
        h = h.lstrip("#")
        return [int(h[i:i + 2], 16) for i in (0, 2, 4)]

    def lum(c):
        def f(v):
            v /= 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])

    def contrast(a, b):
        hi, lo = sorted((lum(a), lum(b)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)

    def mix(a, b, t):
        return [round(a[i] * t + b[i] * (1 - t)) for i in range(3)]

    def to_hex(c):
        return "#" + "".join(f"{v:02x}" for v in c)

    base, bg, gr = rgb(hex_color), rgb(page_bg), rgb(ground)
    t = 0.6
    while t < 1 and contrast(mix(base, bg, t), gr) < 4.6:
        t += 0.01
    return {"text": to_hex(base), "text_2": to_hex(mix(base, bg, 0.85)),
            "text_3": to_hex(mix(base, bg, max(0.72, t))), "muted": to_hex(mix(base, bg, t))}


# ------------------------------------------------------------------ Veranstaltungen

@dataclass
class Event:
    slug: str
    source: Path
    title: str
    start: datetime
    end: datetime
    doors: datetime | None = None
    kind: str = ""
    subtitle: str = ""
    djs: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    fans_of: list[str] = field(default_factory=list)
    entry: str = ""
    teaser: str = ""
    body_html: str = ""
    visual_src: Path | None = None
    visual_url: str = ""          # extern (http…) oder nach dem Kopieren gesetzt
    visual_thumb: str = ""
    visual_og: str = ""
    visual_alt: str = ""
    links: list[dict] = field(default_factory=list)
    highlight: str = ""          # Etikett einer hervorgehobenen Veranstaltung, z. B. "Live-Konzert"
    effekte: list[str] = field(default_factory=list)   # Animationen, siehe EFFEKTE (beliebig kombinierbar)
    social_title: str = ""       # Titel für Facebook/Instagram, falls abweichend (z. B. "F*** Dich …")
    facebook: str = ""           # Link zum Facebook-Event, sobald angelegt (für /intern/)
    social_images: dict = field(default_factory=dict)   # Bilder für Facebook/Instagram (für /intern/)
    reihe: str = ""              # Kürzel der Reihe aus config.yml → reihen (z. B. "dark")
    stream_url: str = ""         # gesetzt, wenn der Abend auch im Stream läuft (hybrid)
    stream_label: str = ""
    is_past: bool = False
    after: list["Event"] = field(default_factory=list)
    before: list["Event"] = field(default_factory=list)

    @property
    def url(self) -> str:
        return f"/programm/{self.slug}/"

    @property
    def fx_classes(self) -> str:
        """CSS-Klassen für die Effekte, z. B. "has-fx fx-mit-rauschnebel fx-mit-fratzen".
        ("fx-mit-…", damit die Namen nie mit den Klassen der Effekt-Ebenen wie .fx-laser kollidieren)"""
        return ("has-fx " + " ".join(f"fx-mit-{fx}" for fx in self.effekte)) if self.effekte else ""

    @property
    def fx_delay(self) -> str:
        """Versatz pro Veranstaltung, damit mehrere Gewitter-Kacheln nicht im Gleichtakt blitzen."""
        return f"{int(hashlib.sha1(self.slug.encode()).hexdigest()[:4], 16) % 70 / 10:.1f}s"

    @property
    def lineup(self) -> str:
        return " & ".join(self.djs) if len(self.djs) <= 2 else ", ".join(self.djs[:-1]) + " & " + self.djs[-1]

    @property
    def byline(self) -> str:
        return self.subtitle or self.lineup

    def json_ld(self, site: dict, club: dict) -> dict:
        """Strukturierte Daten für Suchmaschinen (schema.org/MusicEvent)."""
        image = self.visual_og
        if image and not image.startswith("http"):
            image = site["url"] + image
        data = {
            "@context": "https://schema.org",
            "@type": "MusicEvent",
            "name": self.title,
            "startDate": self.start.isoformat(),
            "endDate": self.end.isoformat(),
            "eventStatus": "https://schema.org/EventScheduled",
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "url": site["url"] + self.url,
            "location": {
                "@type": "Place", "name": site["name"],
                "address": {"@type": "PostalAddress", "streetAddress": club["address"],
                            "postalCode": club["city"].split(" ")[0], "addressLocality": "Bremen",
                            "addressCountry": "DE"},
            },
            "organizer": {"@type": "Organization", "name": site["name"], "url": site["url"]},
        }
        if self.teaser:
            data["description"] = self.teaser
        if image:
            data["image"] = [image]
        if self.djs:
            data["performer"] = [{"@type": "Person", "name": d} for d in self.djs]
        if self.doors:
            data["doorTime"] = self.doors.isoformat()
        if self.stream_url:
            data["eventAttendanceMode"] = "https://schema.org/MixedEventAttendanceMode"
            data["location"] = [data["location"], {"@type": "VirtualLocation", "url": self.stream_url}]
        return data


def load_reihen(cfg: dict) -> dict[str, dict]:
    """
    Reihen aus config.yml lesen. Erlaubt ist eine Liste mit "tag:" …

        reihen:
          - tag: dark
            title: "Calavera Dark"
            more: "Weitere Dunkelveranstaltungen"

    … oder ein Wörterbuch mit dem Kürzel als Schlüssel (reihen: {dark: {title: …, more: …}}).
    """
    raw = cfg.get("reihen") or []
    items = [dict(v or {}, tag=k) for k, v in raw.items()] if isinstance(raw, dict) else list(raw)
    reihen: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict) or not str(item.get("tag") or "").strip():
            warn("config.yml: Eintrag unter reihen: ohne tag – wird ignoriert")
            continue
        tag = str(item["tag"]).strip().lower()
        title = str(item.get("title") or tag).strip()
        reihen[tag] = {"tag": tag, "title": title,
                       "more": str(item.get("more") or f"Mehr aus der Reihe {title}").strip()}
    return reihen


def more_events(ev: "Event", upcoming: list["Event"], total: int, from_reihe: int) -> tuple[list, list]:
    """
    Auswahl für "Weitere Termine" einer Veranstaltungsseite:
      1. bis zu `from_reihe` kommende Termine aus derselben Reihe (chronologisch)
      2. aufgefüllt bis `total` mit dem übrigen Programm (chronologisch), ohne Doppelte.
    Die Veranstaltung selbst und Programmpunkte am selben Abend (stehen schon als
    "Davor/Danach" auf der Seite) werden nicht noch einmal gezeigt.
    """
    pool = [e for e in upcoming if e is not ev and e not in ev.after and e not in ev.before]
    same = [e for e in pool if ev.reihe and e.reihe == ev.reihe][:max(0, from_reihe)]
    rest = [e for e in pool if e not in same][:max(0, total - len(same))]
    return same, rest


# ------------------------------------------------------------------ Texte für Facebook, Instagram & Co.

def html_to_plain(html_text: str) -> str:
    """Event-Text (HTML aus dem Markdown) als Klartext mit Absätzen – Facebook und Instagram
    können weder Markdown noch HTML. Fett/Kursiv fällt weg, Links werden zu "Text (Adresse)"."""
    t = html_text
    t = re.sub(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
               lambda m: m.group(2) if m.group(1) in m.group(2) else f"{m.group(2)} ({m.group(1)})", t, flags=re.S)
    t = re.sub(r"<br\s*/?>", "\n", t)
    t = re.sub(r"<li[^>]*>", "– ", t)
    t = re.sub(r"</li>", "\n", t)
    t = re.sub(r"</(p|h\d|blockquote|ul|ol)>", "\n\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in t.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def datum_lang(dt: datetime) -> str:
    """7. November 2026"""
    return f"{dt.day}. {MONAT[dt.month - 1]} {dt.year}"


def abbinder_text(ev: "Event", cfg: dict) -> str:
    """
    Der Abbinder unter jedem Text, z. B.

        Was euch musikalisch (u. a.) erwarten könnte: Nina Chuba, KUMMER, …, ...

        --
        »F*** Dich Ins Knie, Melancholie«
        mit DJ Alexis On Fire / @dj_alexis_on_fire
        7. November 2026 ab 22:00h
        Eintritt: EUR 5,- / frei für Azubis+Studis
        - rauchfreie Veranstaltung -
    """
    ab = cfg.get("abbinder") or {}
    kuenstler = cfg.get("kuenstler") or {}

    def handle(name: str) -> str:
        info = kuenstler.get(name) or {}
        return str(info.get("instagram") or "").strip().lstrip("@") if isinstance(info, dict) else ""

    blocks = []
    if ev.fans_of:
        blocks.append(f"{ab.get('musik_einleitung', 'Was euch musikalisch (u. a.) erwarten könnte:')} "
                      f"{', '.join(ev.fans_of)}{ab.get('musik_ende', '')}")

    sig = ["-- ", f"»{ev.social_title or ev.title}«"]
    if ev.djs:
        if len(ev.djs) == 1:
            h = handle(ev.djs[0])
            sig.append(f"mit {ev.djs[0]}" + (f" / @{h}" if h else ""))
        else:
            names = [f"{n} (@{handle(n)})" if handle(n) else n for n in ev.djs]
            sig.append("mit " + ", ".join(names[:-1]) + " & " + names[-1])
    elif ev.subtitle:
        sig.append(ev.subtitle)
    if ev.doors:
        sig.append(f"{datum_lang(ev.start)}, Einlass {ev.doors:%H:%M}h, Beginn {ev.start:%H:%M}h")
    else:
        sig.append(f"{datum_lang(ev.start)} ab {ev.start:%H:%M}h")
    # Eigener Eintritt aus der Event-Datei gewinnt; sonst die Schreibweise aus dem Abbinder
    default_entry = str((cfg.get("events") or {}).get("default_entry", ""))
    entry = ev.entry if ev.entry and ev.entry != default_entry else ab.get("eintritt") or ev.entry
    if entry:
        sig.append(f"Eintritt: {entry}")
    tag_lines = {str(k).lower(): str(v) for k, v in (ab.get("zeilen_fuer_tags") or {}).items()}
    sig += [tag_lines[t.lower()] for t in ev.tags if t.lower() in tag_lines]
    if ev.stream_url:
        sig.append(f"Auch live im Stream: {ev.stream_url}")
    blocks.append("\n".join(sig))
    return "\n\n".join(blocks)


def hashtags_for(ev: "Event", cfg: dict) -> str:
    base = [str(h) for h in ((cfg.get("abbinder") or {}).get("hashtags") or [])]
    tags = []
    for t in base + list(ev.genres):
        slug = re.sub(r"[^0-9a-zäöüß]", "", t.lower())
        if slug and slug not in tags:
            tags.append(slug)
    return " ".join("#" + t for t in tags)


def social_texts(ev: "Event", cfg: dict) -> dict:
    """Fertige Texte für die internen Seiten. Länge wird für Instagram (max. 2.200 Zeichen) mitgeliefert."""
    site_url = cfg["site"]["url"].rstrip("/")
    body = html_to_plain(ev.body_html)
    abbinder = abbinder_text(ev, cfg)
    title = ev.social_title or ev.title
    intro = ev.teaser or (shorten(body.split("\n\n")[0], 300) if body else "")
    facebook = "\n\n".join(x for x in [body, abbinder] if x)
    instagram = "\n\n".join(x for x in [intro, abbinder, "Alle Infos: Link in Bio", hashtags_for(ev, cfg)] if x)
    portal = "\n\n".join(x for x in [body, abbinder, f"Alle Infos: {site_url}{ev.url}"] if x)
    ort = f"{cfg['site']['name'].replace(' Bremen', '')}, {cfg['club']['address']}, {cfg['club']['city']}"
    return {
        "title": title,
        "facebook": facebook,
        "instagram": instagram,
        "instagram_len": len(instagram),
        "portal": portal,
        "kurz": ev.teaser or shorten(body, 200),
        "abbinder": abbinder,
        "ort": ort,
        "url": f"{site_url}{ev.url}",
        "start_datum": ev.start.strftime("%d.%m.%Y"), "start_zeit": ev.start.strftime("%H:%M"),
        "ende_datum": ev.end.strftime("%d.%m.%Y"), "ende_zeit": ev.end.strftime("%H:%M"),
        "einlass": ev.doors.strftime("%H:%M") if ev.doors else "",
    }


SOCIAL_FORMATS = {
    "facebook":  (1920, 1005, "Facebook-Titelbild"),
    "instagram": (1080, 1350, "Instagram-Beitrag (4:5)"),
    "story":     (1080, 1920, "Instagram-Story (9:16)"),
}


def _noise(w: int, h: int, cells: tuple[int, int], rnd) -> "Image.Image":
    """Weiches Zufallsrauschen, das in beide Richtungen nahtlos kachelt (Raster wird 3×3 gekachelt und vergrößert)."""
    cx, cy = cells
    small = Image.new("L", (cx, cy))
    small.putdata([rnd.randrange(256) for _ in range(cx * cy)])
    big = Image.new("L", (cx * 3, cy * 3))
    for i in range(3):
        for j in range(3):
            big.paste(small, (i * cx, j * cy))
    big = big.resize((w * 3, h * 3), Image.BICUBIC)
    return big.crop((w, h, 2 * w, 2 * h))


def _fractal(w: int, h: int, base: tuple[int, int], octaves: int, seed: int) -> "Image.Image":
    """Fraktales Rauschen: mehrere Rausch-Schichten, jede doppelt so fein und halb so stark."""
    import random
    rnd = random.Random(seed)
    acc, total, weight = None, 0.0, 1.0
    for o in range(octaves):
        layer = _noise(w, h, (base[0] * 2 ** o, base[1] * 2 ** o), rnd)
        total += weight
        acc = layer if acc is None else Image.blend(acc, layer, weight / total)
        weight *= .5
    return ImageOps.autocontrast(acc, cutoff=1)


def make_fx_textures(out: Path) -> None:
    """Bilder für die Effekte – einmal pro Build berechnet, im Browser nur noch verschoben/gedreht
    (keine Weichzeichnung zur Laufzeit): Nebel (waagerecht nahtlos), Scheinwerferkegel, Filmkorn,
    Staub & Kratzer, Discokugel-Lichtpunkte, Dampf."""
    if Image is None:
        warn("Pillow fehlt – Nebelbilder nicht erzeugt (pip install -r requirements.txt)")
        return
    target = out / "static" / "img" / "fx"
    target.mkdir(parents=True, exist_ok=True)
    w, h = 1024, 256

    def profile(bottom: float, top: float, gamma: float) -> "Image.Image":
        """Senkrechter Verlauf: oben 'top', unten 'bottom' (0–1), dazwischen gekrümmt."""
        col = [int(255 * (top + (bottom - top) * (y / (h - 1)) ** gamma)) for y in range(h)]
        g = Image.new("L", (1, h)); g.putdata(col)
        return g.resize((w, h))

    def curve(img, lo, hi, gamma):
        return img.point(lambda v: 0 if v <= lo else int(255 * min(1, (v - lo) / (hi - lo)) ** gamma))

    layers = {
        # Name: (Grundraster, Oktaven, Zufall, Kontrast lo/hi/gamma, Verlauf unten/oben/Krümmung, Stärke)
        "nebel-hinten": ((4, 2), 5, 11, (40, 215, 1.1), (1.0, 0.0, 1.6), .85),
        "nebel-mitte":  ((6, 3), 5, 23, (70, 225, 1.3), (1.0, 0.0, 1.2), .75),
        "nebel-vorn":   ((3, 6), 4, 37, (125, 235, 1.7), (0.9, 0.05, 0.8), .9),   # in die Länge gezogene Fetzen
        "nebel-dunst":  ((5, 2), 4, 51, (30, 230, 1.0), (0.8, 0.35, 1.0), .6),    # gleichmäßiger Dunst (Bühne)
    }
    # Scheinwerferkegel (Bühnennebel): Spitze oben in der Mitte, weiche Ränder, läuft nach unten ganz aus.
    # Feines Rauschen ("Dithering") verhindert Treppenstufen im sehr schwachen Verlauf.
    import math
    import random
    bw, bh = 256, 512
    rnd = random.Random(5)
    for name, rgb, strength in (("kegel-rot", (214, 38, 70), .55), ("kegel-warm", (255, 228, 205), .32)):
        data = []
        for y in range(bh):
            fy = y / (bh - 1)
            vert = (1 - fy) ** 1.6 * min(1.0, fy / .03 + .35)       # oben hell, unten 0
            for x in range(bw):
                ang = math.degrees(math.atan2(x - bw / 2 + .5, y + 6))
                cone = math.exp(-(ang / 6.5) ** 2)                    # Kegel ±≈7°
                glow = math.exp(-((x - bw / 2) ** 2 + y ** 2) / 900)  # Lampe an der Spitze
                v = 255 * strength * min(1.0, cone * vert + glow * .8)
                data.append(max(0, min(255, int(v + rnd.uniform(-1.5, 1.5)))))
        a = Image.new("L", (bw, bh)); a.putdata(data)
        img = Image.new("RGBA", (bw, bh), rgb + (0,)); img.putalpha(a)
        path = target / f"{name}.webp"
        img.save(path, "WEBP", lossless=True)
        path.chmod(0o644)

    def save(img, name, **kw):
        path = target / name
        img.save(path, "WEBP", **(kw or {"quality": 80, "method": 3}))
        path.chmod(0o644)

    # Filmkorn (grunge, vhs): 256×256, nahtlos, helle und dunkle Körner
    rnd = random.Random(8)
    g = Image.new("L", (256, 256)); g.putdata([rnd.randrange(256) for _ in range(256 * 256)])
    a = g.point(lambda v: min(255, int(abs(v - 128) * 1.6)))
    img = Image.merge("RGBA", (g, g, g, a))
    save(img, "korn.webp", lossless=True)

    # Staub, Fusseln und Haare (grunge): 512×512, nahtlos (über die Ränder weitergezeichnet)
    from PIL import ImageDraw
    rnd = random.Random(12)
    m = Image.new("L", (512, 512), 0); d = ImageDraw.Draw(m)
    for _ in range(70):
        x, y, r = rnd.uniform(0, 512), rnd.uniform(0, 512), rnd.choice([.6, .8, 1, 1.2, 1.6, 2.2])
        for ox in (-512, 0, 512):
            for oy in (-512, 0, 512):
                d.ellipse([x - r + ox, y - r + oy, x + r + ox, y + r + oy], fill=rnd.randrange(120, 230))
    for _ in range(6):                                    # Haare: kleine Bögen
        x, y, hl = rnd.uniform(0, 470), rnd.uniform(0, 470), rnd.uniform(14, 40)
        d.arc([x, y, x + hl, y + hl * rnd.uniform(.3, .8)], rnd.randrange(0, 180), rnd.randrange(200, 360), fill=200, width=1)
    dark = Image.new("RGBA", (512, 512), (20, 18, 16, 0)); dark.putalpha(m)
    save(dark, "staub.webp", lossless=True)

    # Discokugel-Lichtpunkte wie die Kugel im Calavera: größere, verwaschene Fünfecke, nur blau-weiß.
    # 1024×1024, nahtlos (über die Ränder weitergezeichnet); im CSS auf 360 px verkleinert.
    rnd = random.Random(21)
    pts = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0)); d = ImageDraw.Draw(pts)
    for _ in range(20):
        x, y, r = rnd.uniform(0, 1024), rnd.uniform(0, 1024), rnd.uniform(42, 72)
        rot = rnd.uniform(0, 2 * math.pi)
        stretch = rnd.uniform(.75, 1.15)            # leicht verzogen, wie auf schrägen Wänden
        col = rnd.choice([(236, 242, 255), (236, 242, 255), (200, 220, 255), (165, 195, 255), (130, 165, 255)])
        a = rnd.randrange(110, 200)
        for ox in (-1024, 0, 1024):
            for oy in (-1024, 0, 1024):
                poly = [(x + ox + r * math.cos(rot + k * 2 * math.pi / 5), y + oy + r * stretch * math.sin(rot + k * 2 * math.pi / 5)) for k in range(5)]
                d.polygon(poly, fill=col + (a,))
    pts = Image.alpha_composite(pts.filter(ImageFilter.GaussianBlur(24)), pts.filter(ImageFilter.GaussianBlur(10)))   # verwaschen
    save(pts.resize((512, 512), Image.LANCZOS), "lichtpunkte.webp", quality=82, method=3)   # weich genug für halbe Auflösung

    # Dampf (dampf): 256×512, senkrechte Schwaden, oben/unten/seitlich ausgeblendet
    dw, dh = 256, 512
    st = curve(_fractal(dw, dh, (3, 3), 3, 64), 50, 230, 1.2).filter(ImageFilter.GaussianBlur(7))   # weiche Schwaden, keine Fäden
    prof = Image.new("L", (dw, dh))
    prof.putdata([int(255 * math.sin(math.pi * y / dh) ** 1.2 * math.sin(math.pi * (x + .5) / dw) ** 1.5) for y in range(dh) for x in range(dw)])
    st = ImageChops.multiply(st, prof).point(lambda v: int(v * .8))
    img = Image.new("RGBA", (dw, dh), (236, 230, 222, 0)); img.putalpha(st)
    save(img, "dampf.webp")

    for name, (base, octv, seed, (lo, hi, gm), (pb, pt, pg), strength) in layers.items():
        alpha = curve(_fractal(w, h, base, octv, seed), lo, hi, gm)
        alpha = ImageChops.multiply(alpha, profile(pb, pt, pg))
        alpha = alpha.point(lambda v: int(v * strength))
        img = Image.new("RGBA", (w, h), (214, 209, 201, 0))
        img.putalpha(alpha)
        path = target / f"{name}.webp"
        img.save(path, "WEBP", quality=80, method=3)
        path.chmod(0o644)


def make_social_images(ev: "Event", out: Path) -> None:
    """Flyer in die Formate von Facebook und Instagram bringen: Flyer vollständig sichtbar,
    die Ränder mit einer abgedunkelten, unscharfen Fassung desselben Flyers gefüllt."""
    if Image is None or not ev.visual_src:
        return
    from PIL import ImageEnhance, ImageFilter
    target = out / "media" / "events" / ev.slug
    target.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(ev.visual_src) as src:
            im = ImageOps.exif_transpose(src).convert("RGB")
        for key, (w, h, label) in SOCIAL_FORMATS.items():
            bg = ImageOps.fit(im, (w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(max(w, h) // 45))
            bg = ImageEnhance.Brightness(bg).enhance(0.4)
            margin = round(min(w, h) * 0.05)
            scale = min((w - 2 * margin) / im.width, (h - 2 * margin) / im.height)
            fg = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
            bg.paste(fg, ((w - fg.width) // 2, (h - fg.height) // 2))
            name = f"{key}-{w}x{h}.jpg"
            bg.save(target / name, "JPEG", quality=88, optimize=True, progressive=True)
            os.chmod(target / name, 0o644)
            ev.social_images[key] = {"url": f"/media/events/{ev.slug}/{name}", "w": w, "h": h,
                                     "label": label, "file": f"{ev.slug}-{key}.jpg"}
    except Exception as exc:  # noqa: BLE001
        warn(f"{ev.source.name}: Bilder für Facebook/Instagram nicht erzeugt ({exc})")


def load_events(cfg: dict, tz: ZoneInfo) -> list[Event]:
    reihen = load_reihen(cfg)
    ev_cfg = cfg.get("events", {})
    default_start = str(ev_cfg.get("default_start", "22:00"))
    default_hours = float(ev_cfg.get("default_hours", 6))
    default_entry = str(ev_cfg.get("default_entry", ""))
    stream_default_url = str(cfg.get("kellerfunk", {}).get("url", "https://live.calavera.club"))
    stream_default_label = str(ev_cfg.get("stream_label", "Vor Ort & im Stream"))
    events: list[Event] = []
    folder = ROOT / "events"
    for path in sorted(folder.glob("*.md")):
        if path.name.startswith(("_", ".")) or path.name.lower() == "readme.md":
            continue
        try:
            meta, body = read_front_matter(path)
            if meta.get("draft") or meta.get("entwurf"):
                print(f"  · {path.name}: Entwurf, wird übersprungen")
                continue
            title = str(meta.get("title") or "").strip()
            if not title:
                raise ValueError("title fehlt")
            raw_start = meta.get("start")
            if raw_start is None:
                raise ValueError("start fehlt (Format \"JJJJ-MM-TT HH:MM\")")
            if isinstance(raw_start, date) and not isinstance(raw_start, datetime):
                raw_start = f"{raw_start.isoformat()} {default_start}"
            elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(raw_start).strip()):
                raw_start = f"{str(raw_start).strip()} {default_start}"
            start = parse_when(raw_start, tz, what="start")
            end = (parse_when(meta["end"], tz, base=start, what="end") if meta.get("end")
                   else start + timedelta(hours=default_hours))
            if end <= start:
                raise ValueError("end liegt vor start")
            doors = parse_when(meta["einlass"], tz, base=start - timedelta(hours=12), what="einlass") \
                if meta.get("einlass") else None

            body_html = md(body.strip()) if body.strip() else ""
            teaser = str(meta.get("teaser") or "").strip()
            if not teaser and body_html:
                first_p = re.search(r"<p>(.*?)</p>", body_html, re.S)
                teaser = shorten(plain_text(first_p.group(1) if first_p else body_html))

            ev = Event(
                slug=path.stem,
                source=path,
                title=title,
                start=start,
                end=end,
                doors=doors,
                kind=str(meta.get("art") or meta.get("kind") or "").strip(),
                subtitle=str(meta.get("subtitle") or meta.get("untertitel") or "").strip(),
                djs=as_list(meta.get("djs")),
                genres=as_list(meta.get("genres")),
                tags=as_list(meta.get("tags")),
                fans_of=as_list(meta.get("fans_of") or meta.get("fuer_freunde_von")),
                entry=str(meta.get("eintritt") or meta.get("entry") or default_entry).strip(),
                teaser=teaser,
                body_html=body_html,
                visual_alt=str(meta.get("visual_alt") or f"Flyer: {title}").strip(),
                links=[l for l in (meta.get("links") or []) if isinstance(l, dict) and l.get("url")],
                # highlight: true → "Highlight", highlight: "Live-Konzert" → eigenes Etikett
                highlight=("Highlight" if meta.get("highlight") is True
                           else str(meta.get("highlight") or "").strip()),
                reihe=str(meta.get("reihe") or "").strip().lower(),
                social_title=str(meta.get("social_title") or meta.get("titel_social") or "").strip(),
                facebook=str(meta.get("facebook") or "").strip(),
            )
            # effekte: rauschnebel | [buehnennebel, fratzen]  (auch "effekt:")
            for fx in as_list(meta.get("effekte") or meta.get("effekt")):
                fx = str(fx).strip().lower()
                fx = EFFEKT_ALIAS.get(fx, fx)
                if fx in EFFEKTE and fx not in ev.effekte:
                    ev.effekte.append(fx)
                elif fx not in EFFEKTE:
                    warn(f"{path.name}: Effekt \"{fx}\" gibt es nicht – möglich: {', '.join(EFFEKTE)}")
            if ev.facebook:   # öffentlich als Link "Facebook-Event" auf der Veranstaltungsseite
                ev.links.append({"label": "Facebook-Event", "url": ev.facebook})
            if ev.reihe and ev.reihe not in reihen:
                warn(f"{path.name}: Reihe \"{ev.reihe}\" steht nicht in config.yml unter reihen: – wird ignoriert")
                ev.reihe = ""

            # stream: true | "https://…" | {url: …, label: …}  → der Abend läuft auch im Stream
            stream = meta.get("stream")
            if stream:
                if isinstance(stream, dict):
                    ev.stream_url = str(stream.get("url") or stream_default_url).strip()
                    ev.stream_label = str(stream.get("label") or stream_default_label).strip()
                else:
                    ev.stream_url = str(stream).strip() if isinstance(stream, str) and stream.strip().startswith("http") \
                        else stream_default_url
                    ev.stream_label = stream_default_label

            visual = str(meta.get("visual") or "").strip()
            if visual.startswith(("http://", "https://")):
                ev.visual_url = ev.visual_thumb = ev.visual_og = visual
            elif visual:
                p = (path.parent / visual).resolve()
                if p.is_file():
                    ev.visual_src = p
                else:
                    warn(f"{path.name}: Visual \"{visual}\" nicht gefunden – es wird ein Platzhalter gezeigt")
            else:
                for ext in IMAGE_EXTS:
                    for cand in (path.with_suffix(ext), path.with_suffix(ext.upper())):
                        if cand.is_file():
                            ev.visual_src = cand
                            break
                    if ev.visual_src:
                        break
            events.append(ev)
        except Exception as exc:  # noqa: BLE001 – jede kaputte Datei melden, nicht abbrechen
            warn(f"{path.name}: {exc} – Veranstaltung wird übersprungen")
    events.sort(key=lambda e: (e.start, e.title))

    # Abende mit mehreren Programmpunkten verknüpfen (Konzert 20:00 → Party 22:00)
    for ev in events:
        same_night = [o for o in events if o is not ev and o.start.date() == ev.start.date()]
        ev.after = [o for o in same_night if o.start > ev.start]
        ev.before = [o for o in same_night if o.start < ev.start]
    return events


def process_visual(ev: Event, out: Path) -> None:
    """Kopiert das Visual nach dist/media/ und erzeugt (mit Pillow) eine kleine und eine Teilen-Version."""
    if not ev.visual_src:
        return
    src = ev.visual_src
    target_dir = out / "media" / "events" / ev.slug
    target_dir.mkdir(parents=True, exist_ok=True)
    original = target_dir / f"flyer{src.suffix.lower()}"
    copy_public(src, original)
    base = f"/media/events/{ev.slug}"
    ev.visual_url = ev.visual_thumb = ev.visual_og = f"{base}/{original.name}"
    if Image is None:
        return
    try:
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)
            rgb = im.convert("RGB")
            for width, name, fmt, opts in ((640, "640.webp", "WEBP", {"quality": 82}),
                                           (1200, "1200.jpg", "JPEG", {"quality": 85, "optimize": True, "progressive": True})):
                copy = rgb.copy()
                if copy.width > width:
                    copy.thumbnail((width, width * 4), Image.LANCZOS)
                copy.save(target_dir / name, fmt, **opts)
        ev.visual_thumb = f"{base}/640.webp"
        ev.visual_og = f"{base}/1200.jpg"
    except Exception as exc:  # noqa: BLE001
        warn(f"{ev.source.name}: Visual konnte nicht verkleinert werden ({exc}) – Original wird verwendet")


# ------------------------------------------------------------------ Feste Seiten

@dataclass
class Page:
    slug: str
    title: str
    kicker: str
    lead: str
    body_html: str
    description: str
    in_sitemap: bool = True
    cards: list[dict] = field(default_factory=list)   # Kacheln aus "cards:" im Kopf
    numbered: bool = True                              # Kacheln automatisch nummerieren
    hero: dict | None = None                           # großes Bild aus "titelbild:"
    source: Path | None = None

    @property
    def url(self) -> str:
        return f"/{self.slug}/"


def _page_image(page_path: Path, value, what: str) -> Path | None:
    """Bildpfad aus einer Seite auflösen: relativ zu pages/ (z. B. "safe-space/regel-1.png")."""
    if not value:
        return None
    p = (page_path.parent / str(value).strip()).resolve()
    if p.is_file():
        return p
    warn(f"pages/{page_path.name}: {what} \"{value}\" nicht gefunden")
    return None


def load_pages() -> list[Page]:
    pages = []
    for path in sorted((ROOT / "pages").glob("*.*")):
        if path.suffix.lower() not in (".md", ".html") or path.name.startswith(("_", ".")):
            continue
        try:
            meta, body = read_front_matter(path)
            body_html = md(body) if path.suffix.lower() == ".md" else body
            slug = str(meta.get("slug") or path.stem).strip("/")

            cards = []
            for i, c in enumerate(meta.get("cards") or [], start=1):
                if not isinstance(c, dict):
                    continue
                cards.append({
                    "nr": i,
                    "titel": str(c.get("titel") or c.get("title") or "").strip(),
                    "motto": str(c.get("motto") or "").strip(),
                    "text_html": md(str(c.get("text") or "").strip()) if c.get("text") else "",
                    "alt": str(c.get("alt") or "").strip(),   # leer = Bild ist Schmuck, Text steht daneben
                    "src": _page_image(path, c.get("bild") or c.get("image"), f"Bild in Kachel {i}"),
                    "url": "", "full": "",
                })
            hero = None
            tb = meta.get("titelbild")
            if tb:
                tb = tb if isinstance(tb, dict) else {"bild": tb}
                src = _page_image(path, tb.get("bild"), "titelbild")
                if src:
                    hero = {"src": src, "alt": str(tb.get("alt") or "").strip(), "url": "", "full": ""}

            pages.append(Page(
                slug=slug,
                title=str(meta.get("title") or slug.replace("-", " ").title()),
                kicker=str(meta.get("kicker") or ""),
                lead=str(meta.get("lead") or ""),
                body_html=body_html,
                description=str(meta.get("description") or shorten(plain_text(body_html), 160)),
                in_sitemap=not meta.get("noindex", False),
                cards=cards,
                numbered=meta.get("nummern", True) is not False,
                hero=hero,
                source=path,
            ))
        except Exception as exc:  # noqa: BLE001
            warn(f"pages/{path.name}: {exc} – Seite wird übersprungen")
    return pages


def process_page_images(page: Page, out: Path) -> None:
    """Bilder einer festen Seite nach dist/media/pages/<slug>/ kopieren, mit Pillow zusätzlich verkleinern."""
    items = ([page.hero] if page.hero else []) + [c for c in page.cards if c.get("src")]
    if not items:
        return
    target = out / "media" / "pages" / page.slug
    target.mkdir(parents=True, exist_ok=True)
    for item in items:
        src: Path = item["src"]
        copy_public(src, target / src.name)
        item["url"] = item["full"] = f"/media/pages/{page.slug}/{src.name}"
        if Image is None:
            continue
        try:
            with Image.open(src) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                if im.width > 900:
                    im.thumbnail((900, 900 * 4), Image.LANCZOS)
                small = f"{src.stem}-900.webp"
                im.save(target / small, "WEBP", quality=84)
            item["url"] = f"/media/pages/{page.slug}/{small}"
        except Exception as exc:  # noqa: BLE001
            warn(f"pages/{page.slug}: Bild {src.name} konnte nicht verkleinert werden ({exc})")


# ------------------------------------------------------------------ Kalender (.ics)

def ics_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def ics_fold(line: str) -> str:
    out, cur = [], b""
    for ch in line:
        enc = ch.encode("utf-8")
        if len(cur) + len(enc) > (75 if not out else 74):
            out.append(cur.decode("utf-8"))
            cur = b""
        cur += enc
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def ics_version(ics_text: str) -> str:
    """Fingerabdruck einer Kalenderdatei für ?v=… in Links. Der Erstellungszeitpunkt (DTSTAMP)
    zählt nicht mit – sonst bekäme der Link bei jedem Build einen neuen Wert, auch ohne Änderung."""
    relevant = "\n".join(l for l in ics_text.splitlines() if not l.startswith("DTSTAMP:"))
    return hashlib.sha1(relevant.encode("utf-8")).hexdigest()[:8]


def ics_for(events: list[Event], cfg: dict, stamp: datetime, calname: str) -> str:
    site, club = cfg["site"], cfg["club"]
    fmt = lambda dt: dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")  # noqa: E731
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Calavera Bremen//Website//DE",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH", f"X-WR-CALNAME:{ics_escape(calname)}"]
    for ev in events:
        desc = " · ".join(x for x in [ev.byline, " · ".join(ev.genres), ev.entry] if x)
        if ev.teaser:
            desc += "\n\n" + ev.teaser
        if ev.stream_url:
            desc += f"\n\nAuch live im Stream: {ev.stream_url}"
        # Der Link zur Veranstaltungsseite steht im URL-Feld, nicht mehr in der Beschreibung.
        lines += ["BEGIN:VEVENT",
                  f"UID:{ev.slug}@{re.sub(r'^https?://', '', site['url'])}",
                  f"DTSTAMP:{fmt(stamp)}",
                  f"DTSTART:{fmt(ev.start)}",
                  f"DTEND:{fmt(ev.end)}",
                  f"SUMMARY:{ics_escape(ev.title + ' – Calavera')}",
                  f"DESCRIPTION:{ics_escape(desc)}",
                  f"LOCATION:{ics_escape('Calavera, ' + club['address'] + ', ' + club['city'])}",
                  f"URL:{site['url']}{ev.url}"]
        # Flyer als Anhang (Verweis auf das Bild, nicht das Bild selbst). Absolute Adresse nötig.
        image = ev.visual_og
        if image:
            if not image.startswith(("http://", "https://")):
                image = site["url"].rstrip("/") + image
            ext = Path(image.split("?", 1)[0]).suffix.lower()
            mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                    ".webp": "image/webp", ".gif": "image/gif"}.get(ext)
            lines.append(f"ATTACH;FMTTYPE={mime}:{image}" if mime else f"ATTACH:{image}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(ics_fold(l) for l in lines) + "\r\n"


# ------------------------------------------------------------------ Bauen

def build(out: Path, now: datetime | None, strict: bool) -> int:
    cfg = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    tz = ZoneInfo(cfg["site"].get("timezone", "Europe/Berlin"))
    now = now or datetime.now(tz)
    print(f"Calavera · baue Website für Stand {now:%d.%m.%Y %H:%M} ({tz.key})")

    events = load_events(cfg, tz)
    pages = load_pages()
    if strict and problems:
        print("Abbruch wegen --strict.")
        return 1

    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / "static", out / "static", copy_function=copy_public)
    make_fx_textures(out)

    for ev in events:
        ev.is_past = ev.end <= now
        process_visual(ev, out)
        if not ev.is_past:
            make_social_images(ev, out)   # nur für kommende Veranstaltungen – spart Zeit beim Build
    upcoming = [e for e in events if not e.is_past]
    past = sorted((e for e in events if e.is_past), key=lambda e: e.start, reverse=True)

    def asset(rel: str) -> str:
        p = ROOT / "static" / rel
        v = hashlib.sha1(p.read_bytes()).hexdigest()[:8] if p.is_file() else "0"
        return f"/static/{rel}?v={v}"

    def ddmm(dt: datetime) -> str:
        return dt.strftime("%d.%m.")

    def ddmmyyyy(dt: datetime) -> str:
        return dt.strftime("%d.%m.%Y")

    def hhmm(dt: datetime | None) -> str:
        return dt.strftime("%H:%M") if dt else ""

    def wd(dt: datetime) -> str:
        return WOCHENTAG[dt.weekday()]

    def wd_long(dt: datetime) -> str:
        return WOCHENTAG_LANG[dt.weekday()]

    def month_year(dt: datetime) -> str:
        return f"{MONAT[dt.month - 1]} {dt.year}"

    def relative_label(ev: Event) -> str:
        """Etikett für den hervorgehobenen nächsten Termin (wird im Browser aktualisiert)."""
        if ev.start <= now < ev.end:
            return f"Läuft gerade · {hhmm(ev.start)}"
        days = (ev.start.date() - now.date()).days
        if days == 0:
            return f"Heute · {hhmm(ev.start)}"
        if days == 1:
            return f"Morgen · {hhmm(ev.start)}"
        return f"Als Nächstes · {wd(ev.start)} {ddmm(ev.start)}"

    def months_span(evs: list[Event]) -> str:
        if not evs:
            return ""
        a, b = evs[0].start, evs[-1].start
        if (a.year, a.month) == (b.year, b.month):
            return month_year(a)
        if a.year == b.year:
            return f"{MONAT[a.month - 1]} – {MONAT[b.month - 1]} {b.year}"
        return f"{month_year(a)} – {month_year(b)}"

    env = Environment(loader=FileSystemLoader(ROOT / "templates"),
                      autoescape=select_autoescape(["html", "xml"]),
                      undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)
    env.filters.update(ddmm=ddmm, ddmmyyyy=ddmmyyyy, hhmm=hhmm, wd=wd, wd_long=wd_long,
                       iso=lambda dt: dt.isoformat(), month_year=month_year)
    env.globals.update(cfg=cfg, site=cfg["site"], club=cfg["club"], nav=cfg.get("navigation", []),
                       social=cfg.get("social", []), kellerfunk=cfg.get("kellerfunk", {}),
                       asset=asset, now=now, relative_label=relative_label, year=now.year,
                       palette=accent_palette(cfg["site"].get("accent", "#b3122e")),
                       textpal=text_palette(cfg["site"].get("text", "#d1cabf")),
                       pages={p.slug: p for p in pages})

    # Programm-Kalender vorab erzeugen: Links darauf bekommen ?v=…, damit Handys nach einer
    # Änderung nicht die zwischengespeicherte alte Datei öffnen.
    programm_ics = ics_for(upcoming, cfg, now, "Calavera Bremen – Programm")
    env.globals["fx_particles"] = fx_particles
    # Effekte nur auf den vordersten Kacheln im Programm (Startseite und /programm/); Veranstaltungsseiten immer
    env.globals["fx_kacheln"] = int(cfg.get("programm", {}).get("effekte_kacheln", 2))
    env.globals["kalender_url"] = f"/kalender.ics?v={ics_version(programm_ics)}"

    def render(template: str, dest: str, **ctx) -> None:
        path = out / dest.lstrip("/")
        if dest.endswith("/"):
            path = path / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(env.get_template(template).render(**ctx), encoding="utf-8")

    cols = int(cfg.get("programm", {}).get("spalten", 4))
    cols = cols if cols in (3, 4) else 4
    home_max = int(cfg.get("programm", {}).get("startseite_max", 12))

    fx_n = env.globals["fx_kacheln"]
    def fx_list(evs):   # Effekte der vordersten Kacheln → nur deren CSS wird eingebunden
        return fx_css_for([fx for ev in evs[:fx_n] for fx in ev.effekte])
    render("index.html", "/", page_path="/", events=upcoming[:home_max], fx_css=fx_list(upcoming[:home_max]),
           more=max(0, len(upcoming) - home_max), cols=cols, span=months_span(upcoming[:home_max]))
    render("programm.html", "/programm/", page_path="/programm/", events=upcoming, cols=cols, fx_css=fx_list(upcoming),
           span=months_span(upcoming), has_archive=bool(past))
    render("archiv.html", "/programm/archiv/", page_path="/programm/archiv/", events=past)

    reihen = load_reihen(cfg)
    more_total = int(cfg.get("programm", {}).get("weitere_termine", 4))
    more_reihe = int(cfg.get("programm", {}).get("aus_der_reihe", 2))
    for ev in events:
        more_same, more_rest = more_events(ev, upcoming, more_total, more_reihe)
        termin_ics = ics_for([ev], cfg, now, ev.title)
        render("event.html", ev.url, page_path=ev.url, ev=ev, fx_css=fx_css_for(ev.effekte),
               more_same=more_same, more_rest=more_rest, reihe=reihen.get(ev.reihe),
               termin_url=f"termin.ics?v={ics_version(termin_ics)}")
        (out / ev.url.lstrip("/") / "termin.ics").write_text(termin_ics, encoding="utf-8", newline="")

    for page in pages:
        process_page_images(page, out)
        render("page.html", page.url, page_path=page.url, page=page)

    for old, new in (cfg.get("redirects") or {}).items():
        render("redirect.html", f"/{str(old).strip('/')}/", target=new)

    render("404.html", "/404.html", page_path="/404.html")
    (out / "kalender.ics").write_text(programm_ics, encoding="utf-8", newline="")

    # Interne Seiten: fertige Texte und Bilder für Facebook, Instagram und Veranstaltungskalender.
    # Nicht verlinkt, nicht in der Sitemap, für Suchmaschinen gesperrt (robots.txt + noindex).
    social = {ev.slug: social_texts(ev, cfg) for ev in upcoming}
    render("intern_index.html", "/intern/", page_path="/intern/", events=upcoming, texts=social)
    for ev in upcoming:
        render("intern_event.html", f"/intern/{ev.slug}/", page_path=f"/intern/{ev.slug}/", ev=ev, s=social[ev.slug])

    base = cfg["site"]["url"].rstrip("/")
    urls = ["/", "/programm/", "/programm/archiv/"] + [p.url for p in pages if p.in_sitemap] + [e.url for e in events]
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{html.escape(base + u)}</loc></url>\n" for u in urls)
        + "</urlset>\n", encoding="utf-8")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: /intern/\nSitemap: {base}/sitemap.xml\n",
                                    encoding="utf-8")
    (out / "build.json").write_text(json.dumps({
        "built_at": now.isoformat(), "upcoming": len(upcoming), "past": len(past), "pages": len(pages)
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  ✓ {len(upcoming)} kommende, {len(past)} vergangene Veranstaltungen, {len(pages)} feste Seiten → {out}")
    if problems:
        print(f"  {len(problems)} Hinweis(e), siehe oben.")
    return 1 if (strict and problems) else 0


def serve(out: Path, port: int) -> None:
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(out), **kw)

        def send_error(self, code, message=None, explain=None):
            if code == 404 and (out / "404.html").is_file():
                body = (out / "404.html").read_bytes()
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().send_error(code, message, explain)

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), Handler) as httpd:
        print(f"Vorschau: http://localhost:{port}  (Strg+C beendet)")
        httpd.serve_forever()


def main() -> int:
    ap = argparse.ArgumentParser(description="Baut die Calavera-Website nach dist/.")
    ap.add_argument("--out", default=str(ROOT / "dist"), help="Zielordner (Standard: dist/)")
    ap.add_argument("--now", help='Zeitpunkt simulieren, z. B. "2026-11-08 12:00"')
    ap.add_argument("--strict", action="store_true", help="bei Fehlern in Event-Dateien mit Code 1 abbrechen")
    ap.add_argument("--serve", nargs="?", const=8000, type=int, metavar="PORT",
                    help="nach dem Bauen eine Vorschau starten (Standard-Port 8000)")
    args = ap.parse_args()

    cfg_tz = ZoneInfo(yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))["site"].get("timezone", "Europe/Berlin"))
    now = parse_when(args.now, cfg_tz, what="--now") if args.now else None
    out = Path(args.out).resolve()
    code = build(out, now, args.strict)
    if args.serve and code == 0:
        serve(out, args.serve)
    return code


if __name__ == "__main__":
    sys.exit(main())
