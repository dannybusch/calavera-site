#!/usr/bin/env python3
"""
Calavera Bremen – Static Site Generator
=======================================

Liest
  config.yml        Einstellungen der Website
  events/*.md       eine Datei pro Veranstaltung (YAML-Kopf + Markdown-Text),
                    Visual daneben mit gleichem Namen oder per "visual:"
  pages/*.md        feste Seiten (Safe Space, Über den Club, …)
  landing/*.md      Landingpages (/dark/, /party/, …): eigener Text + passende Veranstaltungen
  advent/*.yml      Adventskalender (/adventskalender/): nur bereits geöffnete Türen landen im HTML
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
import inspect
import json
import os
import random
import re
import shutil
import socketserver
import sys
import urllib.parse
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
    "konfetti", "regenbogenfolie", "seifenblasen",                # Gute Laune
    "disco1", "disco2", "disco3",                                # Discokugel: ursprünglich / Projektion / mit Pulsieren
    "bassboom", "spraydose",                                     # Hip-Hop
    "glitch", "laser", "scanlines",                              # Dunkel / Elektronisch
    "retrogrid", "neon", "vinyl", "schwerelos",                  # 80er
    "lichterkette", "dampf", "kerzenlicht",                      # Advent / Honeycafé
    "gluehwuermchen", "spotlight", "cempasuchil", "feuerwerk",   # passend zu Titel / Ort
    "superdark",                                                 # Darkwave: Dunkelheit übernimmt die Seite
    "funemotes",                                                 # fröhliche Emojis steigen auf wie Live-Reaktionen
    "heartbubble",                                               # Herzen steigen aus der Flyer-Ecke rechts unten
    "lichtorgel", "lichtorgel2", "lichtorgel3", "lichtorgel4",   # Lichtorgel: klassisch / Multi-Kreise / Lauflicht / Farbrad
    "lichtorgel5",                                               # Multi-Lichtorgel, Kreise im 3×3-Raster wie im Calavera
    "tanzflaeche", "tanzflaeche2", "tanzflaeche3",               # Tanzfläche: Wellen / Ringe / Schachbrett im Takt
)
EFFEKT_ALIAS = {"bühnennebel": "buehnennebel", "flyer-aus-nebel": "flyerausnebel", "schnee": "snow", "sterne": "twinklestar",
                "twinkle": "twinklestar", "stars": "twinklestar", "glühwürmchen": "gluehwuermchen", "regenbogen": "regenbogenfolie",
                "holo": "regenbogenfolie", "disco": "disco2", "discokugel": "disco2", "papelpicado": "cempasuchil", "kerze": "kerzenlicht",
                "blasen": "seifenblasen", "graffiti": "spraydose", "synthwave": "retrogrid", "bass": "bassboom",
                "super-dark": "superdark", "darkwave": "superdark",
                "emojis": "funemotes", "emoticons": "funemotes", "smileys": "funemotes", "emotes": "funemotes",
                "herzen": "heartbubble", "hearts": "heartbubble", "heartbubbles": "heartbubble",
                "multilichtorgel": "lichtorgel2", "farbrad": "lichtorgel4",
                "dancefloor": "tanzflaeche", "tanzfläche": "tanzflaeche", "tanzfläche2": "tanzflaeche2", "tanzfläche3": "tanzflaeche3"}
# CSS-Dateien je Effekt (static/css/fx/<datei>.css); ohne Eintrag: Datei heißt wie der Effekt
EFFEKT_CSS = {"rauschnebel": ["nebel"], "flyerausnebel": ["nebel", "flyerausnebel"], "buehnennebel": ["buehnennebel"],
              "spotlight": ["buehnennebel", "spotlight"], "vhs": ["grunge", "vhs"],
              "disco1": ["kugel", "disco1"], "disco2": ["kugel", "disco2"], "disco3": ["kugel", "disco3"],
              "lichtorgel5": ["lichtorgel2"], "tanzflaeche2": ["tanzflaeche", "tanzflaeche2"], "tanzflaeche3": ["tanzflaeche", "tanzflaeche3"]}


# Seiteneffekte – wirken global auf jeder Seite (config.yml → seiteneffekte:), optional mit Zeitfenster.
# Je Effekt: static/css/seiteneffekte/<name>.css; das Verhalten steckt in static/js/seiteneffekte.js.
SEITENEFFEKTE = ("spinne", "logo", "rip")
SEITENEFFEKT_ALIAS = {"logolebt": "logo", "logo-lebt": "logo", "lebendes-logo": "logo", "spider": "spinne", "r.i.p.": "rip", "gedenken": "rip", "trauer": "rip"}


def seiteneffekte_aus(cfg: dict, tz: ZoneInfo, now: datetime) -> list[dict]:
    """Liest seiteneffekte: aus config.yml. Einträge: "spinne" oder {effekt: spinne, start: "2026-10-31T18:00", end: "…"}.
    Zeiten gelten in Bremer Ortszeit. Schon abgelaufene Einträge fallen beim Bauen weg; ob einer gerade läuft,
    entscheidet der Browser (der Build kann älter sein)."""
    out = []
    for e in cfg.get("seiteneffekte") or []:
        if isinstance(e, str):
            e = {"effekt": e}
        if not isinstance(e, dict):
            continue
        name = str(e.get("effekt") or e.get("name") or "").strip().lower()
        name = SEITENEFFEKT_ALIAS.get(name, name)
        if name not in SEITENEFFEKTE:
            warn(f"config.yml: Seiteneffekt \"{name}\" gibt es nicht – möglich: {', '.join(SEITENEFFEKTE)}")
            continue
        zeiten = {}
        for key in ("start", "end"):
            v = e.get(key) or e.get({"start": "beginn", "end": "ende"}[key])
            if not v:
                continue
            if isinstance(v, datetime):
                dt = v if v.tzinfo else v.replace(tzinfo=tz)
            else:
                try:
                    dt = datetime.fromisoformat(str(v).strip().replace(" ", "T"))
                except ValueError:
                    warn(f"config.yml: Seiteneffekt {name}: {key} \"{v}\" nicht lesbar (Format 2026-10-31T18:00)")
                    dt = None
                if dt is not None and dt.tzinfo is None:
                    dt = dt.replace(tzinfo=tz)
            if dt is not None:
                zeiten[key] = dt
        if "end" in zeiten and zeiten["end"] <= now:
            continue                                            # schon vorbei
        eintrag = {"name": name, "start": zeiten["start"].isoformat() if "start" in zeiten else "",
                   "end": zeiten["end"].isoformat() if "end" in zeiten else ""}
        if name == "rip":                                       # wen wir ehren – nur Text, kein HTML
            eintrag.update({k: str(e.get(k) or "").strip() for k in ("person", "daten", "text", "link")})
            eintrag["sterne"] = e.get("sterne", True) is not False
            if not eintrag["person"]:
                warn("config.yml: Seiteneffekt rip ohne person: – übersprungen")
                continue
            if eintrag["link"] and not eintrag["link"].startswith(("https://", "http://")):
                eintrag["link"] = ""
        out.append(eintrag)
    return out


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


def hinweis(msg: str) -> None:
    """Nur anzeigen, nicht als Problem zählen (bricht auch mit --strict den Deploy nicht ab)."""
    print(f"  · {msg}")


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


# ------------------------------------------------------------------ Bild-Cache
# Erzeugte Bilder (Flyer-Fassungen, Social-Bilder, Seitenbilder, Effekt-Texturen) werden in
# .cache/bilder/<art>-<prüfsumme>/ aufgehoben. Die Prüfsumme umfasst den Inhalt der Quellbilder, die
# Einstellungen, den Code der erzeugenden Funktion und die Pillow-Version – ändert sich eines davon,
# wird neu gerechnet. Sonst wird nur kopiert. Einträge, die ein Build nicht mehr braucht, räumt er weg.

BILD_CACHE = Path(os.environ.get("CALAVERA_BILD_CACHE") or ROOT / ".cache" / "bilder")
bild_cache_an = True                        # --ohne-cache schaltet ihn ab (alles neu rechnen, Cache unberührt)
_cache_benutzt: set[str] = set()
_cache_zahlen = {"cache": 0, "neu": 0}


def aus_cache(art: str, quellen: list[Path], einstellungen, code: tuple, ziel: Path, erzeugen) -> None:
    """Legt die Bilder, die erzeugen(ordner) schreibt, in ziel ab – aus dem Cache, wenn möglich."""
    ziel.mkdir(parents=True, exist_ok=True)
    if not bild_cache_an:
        erzeugen(ziel)
        _cache_zahlen["neu"] += 1
        return
    h = hashlib.sha256()
    for teil in (art, getattr(Image, "__version__", ""), repr(einstellungen), *(inspect.getsource(f) for f in code)):
        h.update(teil.encode("utf-8") + b"\0")
    for q in quellen:
        h.update(hashlib.sha256(q.read_bytes()).digest())
    name = f"{art}-{h.hexdigest()[:24]}"
    eintrag = BILD_CACHE / name
    if (eintrag / ".fertig").is_file():
        _cache_zahlen["cache"] += 1
    else:
        tmp = BILD_CACHE / f".tmp-{name}-{os.getpid()}"
        try:
            shutil.rmtree(tmp, ignore_errors=True)
            tmp.mkdir(parents=True)
        except OSError as exc:                                # Cache nicht beschreibbar → direkt erzeugen
            warn(f"Bild-Cache {BILD_CACHE} nicht nutzbar ({exc}) – Bilder werden ohne Cache erzeugt")
            globals()["bild_cache_an"] = False
            return aus_cache(art, quellen, einstellungen, code, ziel, erzeugen)
        try:
            erzeugen(tmp)
            (tmp / ".fertig").touch()
            shutil.rmtree(eintrag, ignore_errors=True)
            tmp.rename(eintrag)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        _cache_zahlen["neu"] += 1
    _cache_benutzt.add(name)
    for f in sorted(eintrag.iterdir()):
        if f.name != ".fertig":
            copy_public(f, ziel / f.name)


def bild_cache_aufraeumen() -> None:
    """Nach einem vollständigen Build: Einträge löschen, die er nicht benutzt hat (alte Flyer, alter Code)."""
    if not bild_cache_an or not BILD_CACHE.is_dir():
        return
    for d in BILD_CACHE.iterdir():
        # nur eigene Einträge anfassen – falls CALAVERA_BILD_CACHE auf einen Ordner mit anderem Inhalt zeigt
        if d.is_dir() and re.fullmatch(r"(?:fx|flyer|social|seite)-[0-9a-f]{24}", d.name) and d.name not in _cache_benutzt:
            shutil.rmtree(d, ignore_errors=True)


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
    auch_auf: list[str] = field(default_factory=list)   # zusätzlich auf diesen Landingpages (z. B. ["dark"]), ohne zur Reihe zu gehören
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
        offers, frei = eintritt_offers(self.entry, site["url"] + self.url)
        if offers:
            data["offers"] = offers
        if frei:
            data["isAccessibleForFree"] = True
        if self.stream_url:
            data["eventAttendanceMode"] = "https://schema.org/MixedEventAttendanceMode"
            data["location"] = [data["location"], {"@type": "VirtualLocation", "url": self.stream_url}]
        return data


def eintritt_offers(text: str, url: str) -> tuple[list[dict], bool]:
    """Eintritt (z. B. "5 € · Azubis & Studis frei", "Bis 23:00 frei, danach 5 €", "Hutspende") → schema.org-Offers.
    Ein Preis wird zum Angebot an der Abendkasse; "frei"/"gratis" daneben ergibt ein zweites Angebot für 0 €.
    Ganz ohne Preis, aber frei oder auf Spende → isAccessibleForFree."""
    text = (text or "").strip()
    if not text:
        return [], False
    m = re.search(r"(\d+(?:[.,]\d{1,2})?)\s*(?:€|eur\b|euro\b)|(?:€|eur)\s*(\d+(?:[.,]\d{1,2})?)", text, re.I)
    frei = bool(re.search(r"\bfrei\b|gratis|kostenlos", text, re.I))
    spende = bool(re.search(r"spende|\bhut\b", text, re.I))
    basis = {"@type": "Offer", "priceCurrency": "EUR", "availability": "https://schema.org/InStoreOnly",
             "url": url, "description": text}
    if m:
        preis = float((m.group(1) or m.group(2)).replace(",", "."))
        offers = [dict(basis, price=f"{preis:.2f}")]
        if frei:
            offers.append(dict(basis, price="0.00"))
        return offers, False
    if frei or spende:
        return [dict(basis, price="0.00")], True
    return [], False


TAGE_SCHEMA = {"mo": "Monday", "di": "Tuesday", "mi": "Wednesday", "do": "Thursday", "fr": "Friday", "sa": "Saturday", "so": "Sunday"}


def oeffnungszeiten_schema(text: str) -> list[dict]:
    """ "Fr + Sa · 22–04" → openingHoursSpecification (Tage: Mo…So, mit "+", "," oder "–"; Zeit HH oder HH:MM).
    Nicht erkannt → leere Liste (dann fehlt die Angabe einfach)."""
    t = (text or "").lower()
    zeit = re.search(r"(\d{1,2})(?::(\d{2}))?\s*[–-]\s*(\d{1,2})(?::(\d{2}))?", t)
    if not zeit:
        return []
    tage_teil = t[:zeit.start()]
    reihenfolge = list(TAGE_SCHEMA)
    tage = []
    for von, bis in re.findall(r"\b(mo|di|mi|do|fr|sa|so)\b(?:\s*[–-]\s*\b(mo|di|mi|do|fr|sa|so)\b)?", tage_teil):
        if bis:
            i, j = reihenfolge.index(von), reihenfolge.index(bis)
            tage += reihenfolge[i:j + 1] if i <= j else reihenfolge[i:] + reihenfolge[:j + 1]
        else:
            tage.append(von)
    if not tage:
        return []
    auf = f"{int(zeit.group(1)):02d}:{zeit.group(2) or '00'}"
    zu = f"{int(zeit.group(3)):02d}:{zeit.group(4) or '00'}"
    return [{"@type": "OpeningHoursSpecification", "dayOfWeek": [f"https://schema.org/{TAGE_SCHEMA[d]}" for d in dict.fromkeys(tage)],
             "opens": auf, "closes": zu}]


def club_json_ld(cfg: dict, events: list | None = None, max_events: int = 20) -> dict:
    """Strukturierte Daten für den Club selbst (Startseite, Programm): schema.org/NightClub –
    mit den kommenden Veranstaltungen samt Titel. Ohne sie leiten Suchmaschinen/KI-Antworten aus den
    Öffnungszeiten ("Fr + Sa") nur namenlose "Party"-Termine für jeden Freitag und Samstag ab."""
    site, club = cfg["site"], cfg["club"]
    base = site["url"].rstrip("/")
    data = {
        "@context": "https://schema.org", "@type": "NightClub", "@id": base + "/#club",
        "name": site["name"], "url": base + "/", "description": site.get("description", ""),
        "logo": base + "/static/img/calavera_logo.svg", "image": base + "/static/img/calavera_logo.svg",
        "address": {"@type": "PostalAddress", "streetAddress": club["address"], "postalCode": club["city"].split(" ")[0],
                    "addressLocality": " ".join(club["city"].split(" ")[1:]) or "Bremen", "addressCountry": "DE"},
        "priceRange": club.get("entry", ""),
        "sameAs": [s["url"] for s in cfg.get("social", []) if s.get("url")],
    }
    if club.get("email"):
        data["email"] = club["email"]
    if club.get("telefon") or club.get("phone"):
        data["telephone"] = club.get("telefon") or club.get("phone")
    if club.get("maps_url"):
        data["hasMap"] = club["maps_url"]
    oz = oeffnungszeiten_schema(club.get("hours", ""))
    if oz:
        data["openingHoursSpecification"] = oz
    eintritt = (cfg.get("events") or {}).get("default_entry") or " · ".join(x for x in [club.get("entry"), club.get("entry_note")] if x)
    if eintritt:
        data["publicAccess"] = True
        data["description"] = (data["description"] + " Eintritt: " + eintritt + ".").strip()
    if events:
        data["event"] = [{k: v for k, v in ev.json_ld(site, club).items() if k != "@context"} for ev in events[:max_events]]
    return {k: v for k, v in data.items() if v not in ("", [], None)}


def llms_txt(cfg: dict, upcoming: list, pages: list, kalender_url: str, landings: list | None = None,
             advent: tuple | None = None) -> str:
    """llms.txt – klare Kurzfassung für KI-Suchdienste (https://llmstxt.org): wer, wo, wann, was es kostet, nächste Termine."""
    site, club = cfg["site"], cfg["club"]
    base = site["url"].rstrip("/")
    eintritt = (cfg.get("events") or {}).get("default_entry") or f"{club.get('entry', '')} · {club.get('entry_note', '')}"
    zeilen = [f"# {site['name']}", "", f"> {site.get('description', '').strip()}", "",
              "## Auf einen Blick", "",
              f"- Adresse: {club['address']}, {club['city']} ({club.get('directions', '')})",
              f"- Geöffnet: {club.get('hours', '')}" + (f" – {club['hours_note']}" if club.get("hours_note") else ""),
              f"- Eintritt (wenn nicht anders angegeben): {eintritt}" + (f", {club['box_office']}" if club.get("box_office") else ""),
              f"- Kontakt: {club.get('email', '')}",
              f"- Programm: {base}/programm/"]
    if kalender_url.startswith("/kalender.ics"):
        zeilen.append(f"- Programm als Kalender (ICS): {base}{kalender_url.split('?')[0]}")
    elif kalender_url:
        zeilen.append(f"- Programm als Kalender-Abo (ICS): {base}{kalender_url.split('?')[0]}")
        for l in [l for l in landings or [] if l.in_sitemap]:
            zeilen.append(f"- Nur {l.title} als Kalender-Abo (ICS): {base}{l.url}calavera-{l.slug}.ics")
    kf = cfg.get("kellerfunk") or {}
    if kf.get("url"):
        zeilen.append(f"- Kellerfunk (Live-Streams aus dem Club): {kf['url']}")
    if cfg.get("social"):
        zeilen.append("- " + ", ".join(f"{s['label']}: {s['url']}" for s in cfg["social"] if s.get("url")))
    zeilen += ["", "## Nächste Veranstaltungen", ""]
    for ev in upcoming[:16]:
        teile = [f"{WOCHENTAG[ev.start.weekday()]} {ev.start:%d.%m.%Y}, {ev.start:%H:%M} Uhr", ev.title]
        if ev.byline:
            teile.append(ev.byline)
        if ev.genres:
            teile.append(", ".join(ev.genres))
        if ev.entry and ev.entry != eintritt:
            teile.append(f"Eintritt: {ev.entry}")
        zeilen.append(f"- [{' – '.join(teile)}]({base}{ev.url})" + (f": {ev.teaser}" if ev.teaser else ""))
    if not upcoming:
        zeilen.append("- Gerade steht nichts im Programm.")
    if landings:
        zeilen += ["", "## Partys nach Musikrichtung", ""]
        for l in landings:
            if l.in_sitemap:
                zeilen.append(f"- [{l.seo_title}]({base}{l.url})" + (f": {l.description}" if l.description else ""))
    if advent and advent[0].in_sitemap:   # (Advent, geöffnete Türen) – nur Geöffnetes, nie Künftiges
        a, offen = advent
        zeilen += ["", f"## {a.seo_title}", "", f"- [{a.seo_title}]({base}{a.url}): {a.description}"]
        for t in offen:
            zeilen.append(f"- [Tür {t.tag} ({t.datum:%d.%m.}): {t.song} – {t.kuenstler}]({base}{a.url}#tuer-{t.tag})"
                          f", ausgewählt von {t.person}" + (f" ({t.rolle})" if t.rolle else ""))
    zeilen += ["", "## Seiten", ""]
    for p in pages:
        if p.in_sitemap:
            zeilen.append(f"- [{p.title}]({base}{p.url})" + (f": {p.description}" if p.description else ""))
    return "\n".join(zeilen).rstrip() + "\n"


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
    aus_cache("fx", [], None, (_fx_texturen, _fractal, _noise), out / "static" / "img" / "fx", _fx_texturen)


def _fx_texturen(target: Path) -> None:
    """Rechnet die Effekt-Texturen nach target (über den Bild-Cache aufgerufen)."""
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

    # disco1 (die ursprüngliche Variante): größere, verwaschene Fünfecke, nur blau-weiß, frei verteilt.
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
    save(pts.resize((512, 512), Image.LANCZOS), "lichtpunkte-alt.webp", quality=82, method=3)   # weich genug für halbe Auflösung

    # disco2/disco3 – Lichtpunkte wie die Kugel im Calavera: verwaschene, blau-weiße Fünfecke – angeordnet, wie eine
    # Spiegelkugel sie wirft: Ringe um die Kugel (Bildmitte), je Ring etwa gleich viele Punkte (gleicher Winkel
    # zwischen den Spiegeln), nach außen größer, weiter auseinander und in Strahlrichtung gestreckt (Perspektive).
    # Etwas Streuung und ein paar fehlende Spiegel, damit es nicht wie ein Raster aussieht.
    # Gezeichnet auf 2800 px, gespeichert als 1024 px; im CSS dreht es sich um die Mitte (= die Kugel).
    rnd = random.Random(21)
    S = 2800; c = S / 2
    pts = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(pts)
    # disco3: dieselben Punkte zusätzlich auf drei Gruppen verteilt – jede Gruppe pulsiert für sich
    gruppen = [Image.new("RGBA", (S, S), (0, 0, 0, 0)) for _ in range(3)]; gd = [ImageDraw.Draw(g) for g in gruppen]
    grnd = random.Random(5)                                     # eigener Zufall → disco2 bleibt unverändert
    ring, rr = 0, 170.0
    while rr < c * 1.02:
        n = 19 + rnd.randint(-2, 2)
        versatz = (ring % 2) * .5 + rnd.uniform(-.15, .15)
        for k in range(n):
            if rnd.random() < .22:
                continue                                        # fehlender / verschmutzter Spiegel
            wi = (k + versatz + rnd.uniform(-.18, .18)) * 2 * math.pi / n
            r = rr * rnd.uniform(.94, 1.06)
            x, y = c + r * math.cos(wi), c + r * math.sin(wi)
            gr = r * rnd.uniform(.05, .068)                     # Größe wächst mit dem Abstand
            streck = 1 + .5 * r / c                             # außen in Strahlrichtung länger
            rot = rnd.uniform(0, 2 * math.pi)
            col = rnd.choice([(236, 242, 255), (236, 242, 255), (210, 225, 255), (175, 200, 255)])
            a = int(rnd.randrange(110, 200) * min(1, .45 + r / c) * (1 - .25 * r / c))   # nah an der Kugel schwächer
            poly = []
            for j in range(5):
                t = rot + j * 2 * math.pi / 5
                px, py = gr * math.cos(t) * streck, gr * math.sin(t)     # in Strahlrichtung gestreckt …
                poly.append((x + px * math.cos(wi) - py * math.sin(wi), y + px * math.sin(wi) + py * math.cos(wi)))   # … und dorthin gedreht
            d.polygon(poly, fill=col + (a,))
            gd[grnd.randrange(3)].polygon(poly, fill=col + (min(255, int(a * 1.25)),))
        ring += 1
        rr *= 1.27 + rnd.uniform(-.03, .03)
    verwaschen = lambda im: Image.alpha_composite(im.filter(ImageFilter.GaussianBlur(22)), im.filter(ImageFilter.GaussianBlur(8)))
    for gi, g in enumerate(gruppen):
        save(verwaschen(g).resize((1024, 1024), Image.LANCZOS), f"lichtpunkte-{gi + 1}.webp", quality=72, method=4)
    pts = verwaschen(pts)
    save(pts.resize((1024, 1024), Image.LANCZOS), "lichtpunkte.webp", quality=74, method=4)

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

    def erzeugen(ordner: Path) -> None:
        with Image.open(ev.visual_src) as src:
            im = ImageOps.exif_transpose(src).convert("RGB")
        for key, (w, h, label) in SOCIAL_FORMATS.items():
            bg = ImageOps.fit(im, (w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(max(w, h) // 45))
            bg = ImageEnhance.Brightness(bg).enhance(0.4)
            margin = round(min(w, h) * 0.05)
            scale = min((w - 2 * margin) / im.width, (h - 2 * margin) / im.height)
            fg = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
            bg.paste(fg, ((w - fg.width) // 2, (h - fg.height) // 2))
            bg.save(ordner / f"{key}-{w}x{h}.jpg", "JPEG", quality=88, optimize=True, progressive=True)

    try:
        aus_cache("social", [ev.visual_src], {k: (w, h) for k, (w, h, _) in SOCIAL_FORMATS.items()},
                  (make_social_images,), target, erzeugen)
        for key, (w, h, label) in SOCIAL_FORMATS.items():
            name = f"{key}-{w}x{h}.jpg"
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
                auch_auf=[a.strip("/").lower() for a in as_list(meta.get("auch_auf"))],
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

    def erzeugen(ordner: Path) -> None:
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)
            rgb = im.convert("RGB")
            for width, name, fmt, opts in ((640, "640.webp", "WEBP", {"quality": 82}),
                                           (1200, "1200.jpg", "JPEG", {"quality": 85, "optimize": True, "progressive": True})):
                copy = rgb.copy()
                if copy.width > width:
                    copy.thumbnail((width, width * 4), Image.LANCZOS)
                copy.save(ordner / name, fmt, **opts)
            # 16:9-Fassung (für rausgegangen.py): ganzer Flyer mittig auf unscharfem, abgedunkeltem Hintergrund
            W, H = 1600, 900
            hg = ImageOps.fit(rgb, (W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(36))
            hg = Image.blend(hg, Image.new("RGB", (W, H), (11, 11, 11)), .55)
            vorn = rgb.copy()
            vorn.thumbnail((W - 80, H - 80), Image.LANCZOS)
            hg.paste(vorn, ((W - vorn.width) // 2, (H - vorn.height) // 2))
            hg.save(ordner / "breit.jpg", "JPEG", quality=85, optimize=True, progressive=True)

    try:
        aus_cache("flyer", [src], None, (process_visual,), target_dir, erzeugen)
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
        small = f"{src.stem}-900.webp"

        def erzeugen(ordner: Path, src=src, small=small) -> None:
            with Image.open(src) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                if im.width > 900:
                    im.thumbnail((900, 900 * 4), Image.LANCZOS)
                im.save(ordner / small, "WEBP", quality=84)

        try:
            aus_cache("seite", [src], small, (process_page_images,), target, erzeugen)
            item["url"] = f"/media/pages/{page.slug}/{small}"
        except Exception as exc:  # noqa: BLE001
            warn(f"pages/{page.slug}: Bild {src.name} konnte nicht verkleinert werden ({exc})")


# ------------------------------------------------------------------ Landingpages (/dark/, /party/, …)
# Je Datei in landing/ eine Seite: eigener Einleitungstext + SEO-Angaben im Kopf, darunter die
# passenden Veranstaltungen als Kacheln (automatisch aus events/). Ausführlich: landing/_vorlage.md

LANDING_MEHR = "<!-- mehr -->"   # trennt im Text der .md: oberhalb = Einleitung, unterhalb = Text unter den Kacheln


@dataclass
class Landing:
    slug: str
    title: str                     # Überschrift (H1)
    seo_title: str                 # <title> und og:title
    description: str               # meta description
    kicker: str
    lead: str
    intro_html: str                # Text über den Kacheln
    outro_html: str                # Text unter den Kacheln (für Suchmaschinen: gern ausführlicher)
    reihen: list[str] = field(default_factory=list)       # nur Veranstaltungen dieser Reihen …
    ohne_reihen: list[str] = field(default_factory=list)  # … oder alle außer diesen Reihen
    genres: list[str] = field(default_factory=list)       # zusätzlich: mit einem dieser Genres
    nur_partys: bool = False       # Veranstaltungen mit "art:" (Konzert, Lesung, …) weglassen
    archiv: int = 8                # so viele vergangene Termine unten als Liste (0 = keine)
    leer: str = ""                 # Text, wenn gerade nichts Passendes im Programm steht
    link_text: str = ""            # Linktext auf Veranstaltungsseiten und im Programm
    rueckverlink: bool = True      # False: Veranstaltungsseiten verlinken nicht hierher (Sammelseite, keine Reihe)
    faq: list[dict] = field(default_factory=list)          # [{frage, antwort}] → sichtbar + FAQPage-JSON-LD
    bild: Path | None = None       # og:image (Vorschaubild beim Teilen)
    bild_url: str = ""
    in_sitemap: bool = True
    kalender_name: str = ""        # Name des Abo-Kalenders im Handy (sonst „Calavera <title>“)
    source: Path | None = None

    @property
    def url(self) -> str:
        return f"/{self.slug}/"

    def passt(self, ev: "Event", auch_auf: bool = True) -> bool:
        """Gehört die Veranstaltung auf diese Seite? auch_auf=False: nur nach Regeln aus "zeigt:" – ohne
        Veranstaltungen, die sich per "auch_auf:" nur dazugestellt haben (für Links auf Veranstaltungsseiten)."""
        if auch_auf and self.slug in ev.auch_auf:
            return True
        if self.nur_partys and ev.kind:
            return False
        if self.ohne_reihen and ev.reihe in self.ohne_reihen:
            return False
        treffer = []
        if self.reihen:
            treffer.append(ev.reihe in self.reihen)
        if self.genres:
            eigene = {g.strip().lower() for g in ev.genres}
            treffer.append(any(g in eigene for g in self.genres))
        return any(treffer) if treffer else True


def _kleine_liste(value) -> list[str]:
    return [s.strip().lower() for s in as_list(value) if s.strip()]


def load_landings(reihen: dict[str, dict], seiten_slugs: set[str]) -> list[Landing]:
    folder = ROOT / "landing"
    if not folder.is_dir():
        return []
    landings = []
    for path in sorted(folder.glob("*.md")):
        if path.name.startswith(("_", ".")):
            continue
        try:
            meta, body = read_front_matter(path)
            if meta.get("draft"):
                continue
            slug = str(meta.get("slug") or path.stem).strip("/").lower()
            if slug in seiten_slugs or slug in ("programm", "intern", "static", "media"):
                warn(f"landing/{path.name}: Adresse /{slug}/ ist schon vergeben – Seite wird übersprungen")
                continue
            vorne, _, hinten = body.partition(LANDING_MEHR)
            intro_html, outro_html = md(vorne.strip()), md(hinten.strip())
            zeigt = meta.get("zeigt") or {}
            if not isinstance(zeigt, dict):
                zeigt = {}
            l_reihen = _kleine_liste(zeigt.get("reihen") or zeigt.get("reihe"))
            l_ohne = _kleine_liste(zeigt.get("ohne_reihen") or zeigt.get("ohne_reihe"))
            for tag in l_reihen + l_ohne:
                if tag not in reihen:
                    warn(f"landing/{path.name}: Reihe \"{tag}\" steht nicht in config.yml unter reihen:")
            faq = []
            for i, f in enumerate(meta.get("faq") or [], start=1):
                if not isinstance(f, dict) or not (f.get("frage") and f.get("antwort")):
                    warn(f"landing/{path.name}: FAQ-Eintrag {i} braucht frage: und antwort: – wird ignoriert")
                    continue
                antwort_html = md(str(f["antwort"]).strip())
                faq.append({"frage": str(f["frage"]).strip(), "antwort_html": antwort_html,
                            "antwort_text": plain_text(antwort_html)})
            title = str(meta.get("title") or slug.replace("-", " ").title())
            bild = _page_image(path, meta.get("bild"), "bild") if meta.get("bild") else None
            landings.append(Landing(
                slug=slug, title=title,
                seo_title=str(meta.get("seo_title") or title),
                description=str(meta.get("description") or shorten(plain_text(intro_html), 160)),
                kicker=str(meta.get("kicker") or ""),
                lead=str(meta.get("lead") or ""),
                intro_html=intro_html, outro_html=outro_html,
                reihen=l_reihen, ohne_reihen=l_ohne, genres=_kleine_liste(zeigt.get("genres")),
                nur_partys=bool(zeigt.get("nur_partys", False)),
                archiv=int(meta.get("archiv", 8) or 0),
                leer=str(meta.get("leer") or "Gerade steht hier nichts im Programm – schaut bald wieder rein."),
                link_text=str(meta.get("link_text") or title),
                rueckverlink=meta.get("rueckverlink", True) is not False,
                faq=faq, bild=bild,
                in_sitemap=not meta.get("noindex", False),
                kalender_name=str(meta.get("kalender_name") or "").strip(),
                source=path,
            ))
        except Exception as exc:  # noqa: BLE001
            warn(f"landing/{path.name}: {exc} – Seite wird übersprungen")
    return landings


def landing_json_ld(l: Landing, cfg: dict, events: list["Event"], max_events: int = 30) -> dict:
    """Strukturierte Daten: CollectionPage mit den kommenden Veranstaltungen (MusicEvent, samt Titel),
    Brotkrumen und – wenn vorhanden – FAQPage. Der Club selbst steckt per @id in der Startseite."""
    site, club = cfg["site"], cfg["club"]
    base = site["url"].rstrip("/")
    seite = {
        "@type": "CollectionPage", "@id": base + l.url, "url": base + l.url,
        "name": l.seo_title, "description": l.description, "inLanguage": site.get("language", "de"),
        "isPartOf": {"@type": "WebSite", "name": site["name"], "url": base + "/"},
        "about": {"@id": base + "/#club"},
        "breadcrumb": {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": site["name"], "item": base + "/"},
            {"@type": "ListItem", "position": 2, "name": l.title, "item": base + l.url}]},
    }
    if l.bild_url:
        seite["image"] = base + l.bild_url
    if events:
        seite["mainEntity"] = {"@type": "ItemList", "itemListElement": [
            {"@type": "ListItem", "position": i,
             "item": {k: v for k, v in ev.json_ld(site, club).items() if k != "@context"}}
            for i, ev in enumerate(events[:max_events], start=1)]}
    graph = [seite]
    if l.faq:
        graph.append({"@type": "FAQPage", "@id": base + l.url + "#faq", "mainEntity": [
            {"@type": "Question", "name": f["frage"],
             "acceptedAnswer": {"@type": "Answer", "text": f["antwort_text"]}} for f in l.faq]})
    return {"@context": "https://schema.org", "@graph": graph}


def process_landing_image(l: Landing, out: Path) -> None:
    if not l.bild:
        return
    target = out / "media" / "landing" / l.slug
    target.mkdir(parents=True, exist_ok=True)
    copy_public(l.bild, target / l.bild.name)
    l.bild_url = f"/media/landing/{l.slug}/{l.bild.name}"


# ------------------------------------------------------------------ Adventskalender

# Die Datei advent/adventskalender<jahr>.yml wird nie ausgeliefert (static/ ist der einzige kopierte Ordner).
# Ins HTML kommen nur Türen, deren Tag erreicht ist; künftige Türen bestehen nur aus Zahl und Datum –
# ob sie schon ausgefüllt sind, ist von außen nicht zu erkennen.
ADVENT_SLUG = "adventskalender"
ADVENT_DIENSTE = {"youtube_music": "YouTube Music", "bandcamp": "Bandcamp", "spotify": "Spotify",
                  "apple_music": "Apple Music", "tidal": "Tidal", "soundcloud": "SoundCloud", "deezer": "Deezer"}
# Reihenfolge im Raster: klassisch durcheinander, aber fest (sonst springt es bei jedem Build)
ADVENT_MISCHUNG = (17, 3, 22, 9, 1, 14, 6, 20, 11, 24, 4, 15, 8, 19, 2, 12, 23, 7, 16, 10, 5, 21, 13, 18)
ADVENT_GROSS = {24: "w2 h2", 6: "w2 keep", 13: "w2", 19: "w2"}   # größere Türen fürs Raster


@dataclass
class AdventTuer:
    tag: int
    datum: date
    song: str = ""
    kuenstler: str = ""
    erschienen: str = ""
    person: str = ""
    rolle: str = ""
    text_html: str = ""
    links: list[dict] = field(default_factory=list)    # [{dienst, url}] in der Reihenfolge der Datei
    raten: list[int] = field(default_factory=list)     # Ratespiel: drei Jahre (eins richtig), gemischt; leer = kein Spiel
    raten_salz: str = ""
    raten_h: str = ""                                  # Prüfwert des richtigen Jahres (das Jahr selbst steht nicht im HTML)

    @property
    def fertig(self) -> bool:
        return bool(self.song and self.kuenstler and self.person)


@dataclass
class Advent:
    jahr: int
    titel: str
    kicker: str
    einleitung: str
    seo_title: str
    description: str
    tueren: dict[int, AdventTuer]
    source: Path
    in_sitemap: bool = True
    startseite_ab: date | None = None   # Karte auf der Startseite (neben dem Kellerfunk) ab diesem Tag (Standard: 27.11.)
    startseite_bis: date | None = None  # … bis einschließlich diesem Tag (Standard: 6.1. des Folgejahres)
    startseite: bool = True             # false = keine Karte auf der Startseite (Menüpunkt bleibt)

    @property
    def url(self) -> str:
        return f"/{ADVENT_SLUG}/"

    @property
    def titel_teile(self) -> tuple[str, str]:
        """Überschrift aufteilen: der letzte Satz erscheint rot (wie der Claim auf der Startseite)."""
        saetze = re.findall(r"[^.!?]+[.!?]*\s*", self.titel)
        if len(saetze) < 2:
            return self.titel, ""
        return "".join(saetze[:-1]).strip(), saetze[-1].strip()


def _advent_links(roh, wo: str) -> list[dict]:
    links = []
    if not isinstance(roh, dict):
        return links
    for key, wert in roh.items():
        eintraege = ([(str(a.get("name") or "Link"), a.get("url")) for a in wert if isinstance(a, dict)]
                     if key == "andere" and isinstance(wert, list) else [(ADVENT_DIENSTE.get(key, str(key)), wert)])
        for name, url in eintraege:
            url = str(url or "").strip()
            if not url:
                continue
            if not re.match(r"https?://", url):
                hinweis(f"{wo}: Link \"{url}\" beginnt nicht mit https:// – wird ignoriert")
                continue
            links.append({"dienst": name, "url": url})
    return links


def _advent_datum(roh, standard: date, wo: str) -> date:
    if not roh:
        return standard
    if isinstance(roh, datetime):
        return roh.date()
    if isinstance(roh, date):
        return roh
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(str(roh).strip(), fmt).date()
        except ValueError:
            pass
    warn(f"{wo}: \"{roh}\" ist kein Datum (2026-11-27 oder 27.11.2026) – nehme {standard:%d.%m.%Y}")
    return standard


def advent_hinweis(a: Advent, now: datetime) -> dict | None:
    """Karte auf der Startseite (teilt sich den Platz mit dem Kellerfunk) und hervorgehobener Menüpunkt.
    None = außerhalb des Zeitraums. startseite: false schaltet nur die Karte ab, nicht den Menüpunkt.
    Liegt der Build bis zu 7 Tage vor startseite_ab, steht die Karte schon versteckt im HTML und
    site.js blendet sie am Stichtag ein (und nach startseite_bis wieder aus) – ohne eigenen Deploy.
    Gezeigt wird nur, was ohnehin offen ist: vor dem 1.12. Titel + Einleitung, danach die Tür von heute."""
    heute = now.date()
    if heute > a.startseite_bis or (a.startseite_ab - heute).days > 7:
        return None
    start, ende = date(a.jahr, 12, 1), date(a.jahr, 12, 24)
    tag = (heute - start).days + 1 if start <= heute <= ende else 0
    t = a.tueren.get(tag) if tag else None
    return {"url": a.url, "ab": a.startseite_ab.isoformat(), "bis": a.startseite_bis.isoformat(),
            "versteckt": heute < a.startseite_ab, "vor_start": heute < start, "tag": tag, "karte": a.startseite,
            "tuer": t if t and t.fertig else None, "titel_teile": a.titel_teile, "einleitung": a.einleitung}


def _fnv1a(text: str) -> str:
    """32-bit FNV-1a als Hex – dieselbe Rechnung macht adventskalender.js."""
    h = 0x811C9DC5
    for b in text.encode("utf-8"):
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def _advent_raten(e: dict, tag: int, jahr_kal: int, wo: str) -> tuple[list[int], str, str]:
    """Ratespiel „Wann ist der Song erschienen?“: das richtige Jahr + zwei falsche, gemischt.
    jahr_raten: [1983, 1991] in der Tür legt die falschen selbst fest; jahr_raten: false schaltet das Spiel ab.
    Sonst gewürfelt: ±2 bis 5 Jahre ums echte Jahr, nicht in der Zukunft – fest pro Tür (alle sehen dieselben Zahlen).
    Ins HTML kommt nur ein Prüfwert des richtigen Jahres, nicht das Jahr selbst."""
    roh_jahr = str(e.get("erschienen") or "").strip()
    vorgabe = e.get("jahr_raten")
    if vorgabe is False or not re.fullmatch(r"\d{4}", roh_jahr):
        return [], "", ""
    echt = int(roh_jahr)
    rng = random.Random(f"{jahr_kal}-{tag}-{echt}-{e.get('song')}")
    falsch: list[int] = []
    if vorgabe not in (None, True, ""):
        werte = vorgabe if isinstance(vorgabe, list) else [vorgabe]
        for w in werte:
            try:
                w = int(w)
            except (TypeError, ValueError):
                hinweis(f"{wo}: jahr_raten: „{w}“ ist keine Jahreszahl – wird ignoriert")
                continue
            if w != echt and w not in falsch:
                falsch.append(w)
        if len(falsch) > 2:
            hinweis(f"{wo}: jahr_raten: mehr als zwei Jahre – nehme die ersten beiden")
            falsch = falsch[:2]
    kandidaten = [echt + d for d in (-5, -4, -3, -2, 2, 3, 4, 5)
                  if echt + d <= jahr_kal and echt + d not in falsch]
    rng.shuffle(kandidaten)
    for k in kandidaten:
        if len(falsch) >= 2:
            break
        if all(abs(k - f) >= 2 for f in falsch):     # nicht zwei fast gleiche Jahre
            falsch.append(k)
    if len(falsch) < 2:
        return [], "", ""
    wahl = [echt] + falsch
    rng.shuffle(wahl)
    salz = f"{random.SystemRandom().getrandbits(32):08x}"
    return wahl, salz, _fnv1a(salz + str(echt))


def load_advent(belegt: set[str]) -> Advent | None:
    """Neueste advent/adventskalender*.yml ohne draft: true. Ohne Datei: keine Seite."""
    folder = ROOT / "advent"
    if not folder.is_dir():
        return None
    for path in sorted(folder.glob("adventskalender*.yml"), reverse=True):
        try:
            d = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if d.get("draft"):
                continue
            if ADVENT_SLUG in belegt:
                warn(f"advent/{path.name}: Adresse /{ADVENT_SLUG}/ ist schon vergeben – Seite wird übersprungen")
                return None
            jahr = int(d.get("jahr") or 0)
            if not 2000 <= jahr <= 2100:
                warn(f"advent/{path.name}: jahr: fehlt oder ist ungültig – Seite wird übersprungen")
                continue
            tueren = {}
            for e in d.get("tueren") or []:
                if not isinstance(e, dict):
                    continue
                try:
                    tag = int(e.get("tag"))
                except (TypeError, ValueError):
                    hinweis(f"advent/{path.name}: Tür ohne gültigen tag: – wird ignoriert")
                    continue
                if not 1 <= tag <= 24 or tag in tueren:
                    hinweis(f"advent/{path.name}: tag: {tag} ist doppelt oder nicht 1–24 – wird ignoriert")
                    continue
                txt = lambda k: str(e.get(k) or "").strip()  # noqa: E731
                raten, salz, pruef = _advent_raten(e, tag, jahr, f"advent/{path.name}, Tür {tag}")
                tueren[tag] = AdventTuer(raten=raten, raten_salz=salz, raten_h=pruef,
                    tag=tag, datum=date(jahr, 12, tag), song=txt("song"), kuenstler=txt("kuenstler"),
                    erschienen=txt("erschienen"), person=txt("person"), rolle=txt("rolle"),
                    text_html=md(txt("text")) if txt("text") else "",
                    links=_advent_links(e.get("links"), f"advent/{path.name}, Tür {tag}"))
            einleitung = str(d.get("einleitung") or "").strip()
            titel = str(d.get("titel") or "Adventskalender").strip()
            return Advent(
                jahr=jahr, titel=titel, kicker=str(d.get("kicker") or f"Calavera · Advent {jahr}").strip(),
                einleitung=einleitung, seo_title=str(d.get("seo_title") or f"Adventskalender {jahr}").strip(),
                description=str(d.get("description") or "").strip() or shorten(einleitung, 160)
                            or f"Der Calavera-Adventskalender {jahr}: jeden Tag ein Lieblingssong aus dem Team und von den DJs.",
                tueren=tueren, source=path, in_sitemap=not d.get("noindex", False),
                startseite_ab=_advent_datum(d.get("startseite_ab"), date(jahr, 11, 27), f"advent/{path.name}: startseite_ab"),
                startseite_bis=_advent_datum(d.get("startseite_bis"), date(jahr + 1, 1, 6), f"advent/{path.name}: startseite_bis"),
                startseite=d.get("startseite", True) is not False)
        except Exception as exc:  # noqa: BLE001
            warn(f"advent/{path.name}: {exc} – Seite wird übersprungen")
    return None


def advent_stand(a: Advent, now: datetime) -> dict:
    """Was am Build-Zeitpunkt sichtbar ist. Künftige Türen: nur tag + Datum, keine Daten aus der Datei."""
    heute = now.date()
    offen, kacheln = [], {}
    for tag in range(1, 25):
        d = date(a.jahr, 12, tag)
        k = {"tag": tag, "wt": WOCHENTAG[d.weekday()], "datum": d.strftime("%d.%m."), "gross": ADVENT_GROSS.get(tag, ""),
             "zustand": "zu", "tuer": None}
        if d <= heute:
            t = a.tueren.get(tag)
            if t and t.fertig:
                k["zustand"], k["tuer"] = ("heute" if d == heute else "offen"), t
                offen.append(t)
            else:
                k["zustand"] = "folgt"
                hinweis(f"advent/{a.source.name}: Tür {tag} ist dran, aber song/kuenstler/person fehlen – "
                     "auf der Seite steht „folgt in Kürze“")
        kacheln[tag] = k
    vor_start = heute < date(a.jahr, 12, 1)
    # Mitwirkende: alle Personen aus der Datei (auch hinter noch geschlossenen Türen), ohne Doppelte und
    # in zufälliger Reihenfolge – so ist nicht abzulesen, welche Tür zu wem gehört.
    # (adventskalender.js mischt bei jedem Besuch noch einmal neu.)
    mitwirkende = sorted({t.person.strip() for t in a.tueren.values() if t.person.strip()})
    random.SystemRandom().shuffle(mitwirkende)
    return {"kacheln": [kacheln[t] for t in ADVENT_MISCHUNG], "offen": offen, "vor_start": vor_start,
            "mitwirkende": mitwirkende,
            "alle_offen": heute >= date(a.jahr, 12, 24)}


def advent_json_ld(a: Advent, cfg: dict, offen: list[AdventTuer]) -> dict:
    """CollectionPage mit den geöffneten Türen als MusicRecording (nur geöffnete!) + Brotkrumen."""
    site = cfg["site"]
    base = site["url"].rstrip("/")
    seite = {
        "@type": "CollectionPage", "@id": base + a.url, "url": base + a.url,
        "name": a.seo_title, "description": a.description, "inLanguage": site.get("language", "de"),
        "isPartOf": {"@type": "WebSite", "name": site["name"], "url": base + "/"},
        "about": {"@id": base + "/#club"},
        "breadcrumb": {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": site["name"], "item": base + "/"},
            {"@type": "ListItem", "position": 2, "name": a.seo_title, "item": base + a.url}]},
    }
    if offen:
        items = []
        for i, t in enumerate(offen, start=1):
            rec = {"@type": "MusicRecording", "name": t.song, "byArtist": {"@type": "MusicGroup", "name": t.kuenstler},
                   "url": f"{base}{a.url}#tuer-{t.tag}"}
            if t.links:
                rec["sameAs"] = [l["url"] for l in t.links]
            items.append({"@type": "ListItem", "position": i, "item": rec})
        seite["mainEntity"] = {"@type": "ItemList", "itemListElement": items}
    return {"@context": "https://schema.org", "@graph": [seite]}


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


def ics_for(events: list[Event], cfg: dict, stamp: datetime, calname: str,
            abo: bool = False, beschreibung: str = "") -> str:
    """Kalenderdatei. abo=True: Kopfzeilen für abonnierte Kalender (Name, Beschreibung, Zeitzone und wie oft
    Kalender-Apps neu laden sollen – Apple, Google und Outlook lesen je eine andere der beiden Angaben)."""
    site, club = cfg["site"], cfg["club"]
    fmt = lambda dt: dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")  # noqa: E731
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Calavera Bremen//Website//DE",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH", f"X-WR-CALNAME:{ics_escape(calname)}"]
    if abo:
        lines += [f"X-WR-TIMEZONE:{site.get('timezone', 'Europe/Berlin')}",
                  "REFRESH-INTERVAL;VALUE=DURATION:PT6H", "X-PUBLISHED-TTL:PT6H"]
        if beschreibung:
            lines.append(f"X-WR-CALDESC:{ics_escape(beschreibung)}")
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


def kalender_abo(pfad: str, ics_text: str, cfg: dict, name: str, seite: str = "/programm/") -> dict:
    """Links für ein Kalender-Abo unter `pfad` (z. B. "/calavera.ics"):
    webcal:// öffnet auf iPhone, Mac und in Outlook direkt „Abonnieren“; Android hat dafür nichts Eigenes,
    dort führt der Google-Kalender-Link zum Abo. Google bekommt die https://-Adresse: aus webcal:// macht Google
    sonst http://, und der Abruf scheitert oder hängt an einer Weiterleitung. Beide ohne ?v=…, damit die Abo-Adresse für immer gleich bleibt.
    name = Name des Kalenders im Handy (für den Hinweis im Kasten), seite = Seite mit dem Kasten."""
    https = cfg["site"]["url"].rstrip("/") + pfad
    webcal = "webcal://" + re.sub(r"^https?://", "", https)
    return {"https": https, "webcal": webcal,
            # Google mit https:// statt webcal:// – aus webcal:// macht Google http:// (Danny, 24.11.)
            "google": "https://calendar.google.com/calendar/r?cid=" + urllib.parse.quote(https, safe=""),
            "name": name, "seite": seite}


def abo_termine(events: list[Event], now: datetime, tage: int) -> list[Event]:
    """Termine fürs Abo: alle kommenden und die der letzten `tage` Tage. So verschwindet ein Abend nicht am
    Morgen danach aus dem Handy-Kalender (wer nachschauen will, wann er im Calavera war, findet ihn noch)."""
    grenze = now - timedelta(days=max(0, tage))
    return [e for e in events if e.end > grenze]


# ------------------------------------------------------------------ Bauen

def build(out: Path, now: datetime | None, strict: bool) -> int:
    cfg = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    tz = ZoneInfo(cfg["site"].get("timezone", "Europe/Berlin"))
    # Mit --now gebaut: Zeitpunkt auch fürs Script im Browser vormerken (sonst rechnet site.js mit der echten Uhr)
    jetzt_simuliert = now.strftime("%Y-%m-%dT%H:%M") if now else ""
    now = now or datetime.now(tz)
    print(f"Calavera · baue Website für Stand {now:%d.%m.%Y %H:%M} ({tz.key})")

    events = load_events(cfg, tz)
    pages = load_pages()
    landings = load_landings(load_reihen(cfg), {p.slug for p in pages})
    landing_slugs = {l.slug for l in landings}
    advent = load_advent({p.slug for p in pages} | landing_slugs | {"programm", "intern", "static", "media"})
    for ev in events:
        for slug in ev.auch_auf:
            if slug not in landing_slugs:
                warn(f"{ev.source.name}: auch_auf: \"{slug}\" – keine Landingpage landing/{slug}.md – wird ignoriert")
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
                       pages={p.slug: p for p in pages}, landings=landings,
                       seiteneffekte=seiteneffekte_aus(cfg, tz, now),
                       advent_hero=advent_hinweis(advent, now) if advent else None,
                       jetzt_simuliert=jetzt_simuliert)

    # Programm-Kalender vorab erzeugen: Links darauf bekommen ?v=…, damit Handys nach einer
    # Änderung nicht die zwischengespeicherte alte Datei öffnen.
    # Dieselbe Datei dient als Abo (webcal://) und zum einmaligen Laden; sie enthält auch die Termine der
    # letzten Tage (kalender.abo_vergangene_tage, Standard 30), damit sie im abonnierten Kalender stehen bleiben.
    # Datei heißt calavera.ics (manche Kalender-Apps zeigen den Dateinamen als Kalendernamen). kalender.ics wird
    # als gleiche Kopie weiter geschrieben, aber nicht mehr verlinkt – für alle, die die alte Adresse abonniert haben.
    # Das Abo ist vorerst AUS (Danny, 24.11.: klappte auf Android nicht). Einschalten mit kalender.abo: true.
    # Aus = Stand vor dem Abo: nur kalender.ics mit den kommenden Terminen, Knopf „Programm in den Kalender“
    # (Startseite, /programm/), „Programm als Kalender“ im Fuß – kein Kasten, keine calavera*.ics.
    kal_cfg = cfg.get("kalender") or {}
    abo_an = kal_cfg.get("abo", False) is True
    abo_tage = int(kal_cfg.get("abo_vergangene_tage", 30) or 0)
    abo_name = str(kal_cfg.get("abo_name") or cfg["site"]["name"])     # „Calavera Bremen“
    if abo_an:
        programm_ics = ics_for(abo_termine(events, now, abo_tage), cfg, now, abo_name, abo=True,
                               beschreibung=f"Partys und Konzerte im {cfg['site']['name']}, {cfg['club']['address']}. "
                                            f"Programm: {cfg['site']['url']}/programm/")
    else:
        programm_ics = ics_for(upcoming, cfg, now, "Calavera Bremen – Programm")
    env.globals["fx_particles"] = fx_particles
    # Effekte nur auf den vordersten Kacheln im Programm (Startseite und /programm/); Veranstaltungsseiten immer
    env.globals["fx_kacheln"] = int(cfg.get("programm", {}).get("effekte_kacheln", 2))
    # Wenige Termine: 2 → Muster A (gleich groß), 3 bis leiste_bis → Muster B (Teaser + Leiste), sonst normal
    leiste_bis = int(cfg.get("programm", {}).get("leiste_bis", 4))
    env.globals["leiste_bis"] = leiste_bis
    env.globals["wenig_modus"] = lambda n: "a" if n == 2 else ("b" if 3 <= n <= leiste_bis else "")
    env.globals["kalender_url"] = f"/{'calavera' if abo_an else 'kalender'}.ics?v={ics_version(programm_ics)}"
    env.globals["abo"] = kalender_abo("/calavera.ics", programm_ics, cfg, abo_name) if abo_an else None

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
    # Startseiten-Übernahme: die Veranstaltung des Tages ersetzt ab X Stunden vor Beginn den Claim
    # (site.startseite_uebernahme: false schaltet das ab). Mitgegeben werden die nächsten 8 als
    # <template> – welche gerade dran ist, entscheidet site.js im Browser (der Build kann älter sein).
    site_cfg = cfg.get("site", {}) or {}
    uebernahme_an = site_cfg.get("startseite_uebernahme", True) is not False
    uebernahme = upcoming[:8] if uebernahme_an else []
    uebernahme_h = float(site_cfg.get("startseite_uebernahme_stunden", 6) or 6)
    render("index.html", "/", page_path="/", events=upcoming[:home_max],
           fx_css=fx_css_for([fx for ev in upcoming[:home_max][:fx_n] + uebernahme for fx in ev.effekte]),
           more=max(0, len(upcoming) - home_max), cols=cols, span=months_span(upcoming[:home_max]),
           uebernahme=uebernahme, uebernahme_h=uebernahme_h, club_ld=club_json_ld(cfg, upcoming))
    render("programm.html", "/programm/", page_path="/programm/", events=upcoming, cols=cols, fx_css=fx_list(upcoming),
           span=months_span(upcoming), has_archive=bool(past), club_ld=club_json_ld(cfg, upcoming, max_events=50))
    render("archiv.html", "/programm/archiv/", page_path="/programm/archiv/", events=past)

    reihen = load_reihen(cfg)
    more_total = int(cfg.get("programm", {}).get("weitere_termine", 4))
    more_reihe = int(cfg.get("programm", {}).get("aus_der_reihe", 2))
    for ev in events:
        more_same, more_rest = more_events(ev, upcoming, more_total, more_reihe)
        termin_ics = ics_for([ev], cfg, now, ev.title)
        render("event.html", ev.url, page_path=ev.url, ev=ev, fx_css=fx_css_for(ev.effekte),
               more_same=more_same, more_rest=more_rest, reihe=reihen.get(ev.reihe),
               landing=next((l for l in landings if l.rueckverlink and l.passt(ev, auch_auf=False)), None),
               termin_url=f"termin.ics?v={ics_version(termin_ics)}")
        (out / ev.url.lstrip("/") / "termin.ics").write_text(termin_ics, encoding="utf-8", newline="")

    for page in pages:
        process_page_images(page, out)
        render("page.html", page.url, page_path=page.url, page=page)

    # Landingpages: eigener Text aus landing/*.md + passende Veranstaltungen (kommende als Kacheln,
    # vergangene als Liste – so bleibt die Seite für Suchmaschinen auch in Programmpausen gefüllt)
    for l in landings:
        process_landing_image(l, out)
        l_kommend = [e for e in upcoming if l.passt(e)]
        l_vorbei = [e for e in past if l.passt(e)][:max(0, l.archiv)]
        # Eigenes Abo je Landingpage (/dark/calavera-dark.ics …): nur die Termine, die auch auf der Seite stehen
        kurz = cfg["site"]["name"].split()[0]            # „Calavera“
        l_name = l.kalender_name or (l.title if kurz.lower() in l.title.lower() else f"{kurz} {l.title}")
        l_ics = ics_for(abo_termine([e for e in events if l.passt(e)], now, abo_tage), cfg, now, l_name, abo=True,
                        beschreibung=f"{l.description} {cfg['site']['url']}{l.url}".strip())
        render("landing.html", l.url, page_path=l.url, l=l, events=l_kommend, past_events=l_vorbei, cols=cols,
               fx_css=fx_list(l_kommend), landing_ld=landing_json_ld(l, cfg, l_kommend),
               l_abo=kalender_abo(f"{l.url}calavera-{l.slug}.ics", l_ics, cfg, l_name, l.url)
               if abo_an else None)
        if abo_an:
            (out / l.slug / f"calavera-{l.slug}.ics").write_text(l_ics, encoding="utf-8", newline="")

    # Adventskalender: Stand zum Build-Zeitpunkt (der Deploy läuft im Dezember kurz nach Mitternacht)
    advent_offen: list = []
    if advent:
        stand = advent_stand(advent, now)
        advent_offen = stand["offen"]
        render("adventskalender.html", advent.url, page_path=advent.url, a=advent, **stand,
               advent_ld=advent_json_ld(advent, cfg, advent_offen))

    for old, new in (cfg.get("redirects") or {}).items():
        render("redirect.html", f"/{str(old).strip('/')}/", target=new)

    render("404.html", "/404.html", page_path="/404.html")
    if abo_an:
        (out / "calavera.ics").write_text(programm_ics, encoding="utf-8", newline="")
    (out / "kalender.ics").write_text(programm_ics, encoding="utf-8", newline="")   # mit Abo: alte Adresse, nicht verlinkt

    # Interne Seiten: fertige Texte und Bilder für Facebook, Instagram und Veranstaltungskalender.
    # Nicht verlinkt, nicht in der Sitemap, für Suchmaschinen gesperrt (robots.txt + noindex).
    social = {ev.slug: social_texts(ev, cfg) for ev in upcoming}
    render("intern_index.html", "/intern/", page_path="/intern/", events=upcoming, texts=social)
    for ev in upcoming:
        render("intern_event.html", f"/intern/{ev.slug}/", page_path=f"/intern/{ev.slug}/", ev=ev, s=social[ev.slug])

    base = cfg["site"]["url"].rstrip("/")
    urls = (["/", "/programm/", "/programm/archiv/"] + [l.url for l in landings if l.in_sitemap]
            + ([advent.url] if advent and advent.in_sitemap else [])
            + [p.url for p in pages if p.in_sitemap] + [e.url for e in events])
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{html.escape(base + u)}</loc></url>\n" for u in urls)
        + "</urlset>\n", encoding="utf-8")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: /intern/\nSitemap: {base}/sitemap.xml\n",
                                    encoding="utf-8")
    # IndexNow (Bing & Co.): Schlüsseldatei im Wurzelordner, damit die Suchmaschinen Meldungen von indexnow.py
    # prüfen können. Der Schlüssel ist nicht geheim, kommt aber wie alle Zugänge aus der Umgebung (GitHub Variable).
    indexnow_key = os.environ.get("INDEXNOW_KEY", "").strip()
    if indexnow_key:
        if re.fullmatch(r"[A-Za-z0-9-]{8,128}", indexnow_key):
            (out / f"{indexnow_key}.txt").write_text(indexnow_key, encoding="utf-8")
        else:
            warn("INDEXNOW_KEY ungültig (8–128 Zeichen a–z, A–Z, 0–9, -) – keine Schlüsseldatei erzeugt")
    (out / "llms.txt").write_text(llms_txt(cfg, upcoming, pages, env.globals["kalender_url"], landings,
                                              (advent, advent_offen) if advent else None), encoding="utf-8")
    (out / "build.json").write_text(json.dumps({
        "built_at": now.isoformat(), "upcoming": len(upcoming), "past": len(past), "pages": len(pages),
        "landingpages": len(landings), "adventskalender": bool(advent)
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    bild_cache_aufraeumen()
    if _cache_zahlen["cache"] or _cache_zahlen["neu"]:
        print(f"  Bilder: {_cache_zahlen['neu']} neu berechnet, {_cache_zahlen['cache']} aus dem Cache"
              + ("" if bild_cache_an else " (Cache aus)"))
    print(f"  ✓ {len(upcoming)} kommende, {len(past)} vergangene Veranstaltungen, {len(pages)} feste Seiten, "
          f"{len(landings)} Landingpage(s)"
          + (f", Adventskalender ({len(advent_offen)} Türen offen)" if advent else "") + f" → {out}")
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
    ap.add_argument("--ohne-cache", action="store_true",
                    help="alle Bilder neu berechnen, Bild-Cache (.cache/bilder/) weder lesen noch schreiben")
    ap.add_argument("--serve", nargs="?", const=8000, type=int, metavar="PORT",
                    help="nach dem Bauen eine Vorschau starten (Standard-Port 8000)")
    args = ap.parse_args()

    cfg_tz = ZoneInfo(yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))["site"].get("timezone", "Europe/Berlin"))
    now = parse_when(args.now, cfg_tz, what="--now") if args.now else None
    out = Path(args.out).resolve()
    if args.ohne_cache:
        global bild_cache_an
        bild_cache_an = False
    code = build(out, now, args.strict)
    if args.serve and code == 0:
        serve(out, args.serve)
    return code


if __name__ == "__main__":
    sys.exit(main())
