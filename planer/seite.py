"""Hilfen zum Lesen von HTML ohne feste CSS-Selektoren.

Die Plugins verlassen sich bewusst auf Dinge, die Umbauten meist überleben: Link-Muster
(Datum in der URL), JSON-LD, og:title und Uhrzeiten im Text.
"""
from __future__ import annotations

import html as html_mod
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin


@dataclass
class Link:
    href: str
    text: str
    pos: int = 0   # Stelle im Rohtext der Seite (Seite.rohtext), an der der Link beginnt


class _Sammler(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[Link] = []
        self.meta: dict[str, str] = {}
        self.jsonld: list[str] = []
        self.titel = ""
        self.text_teile: list[str] = []
        self._a: list[list] = []          # offene <a>: [href, textteile]
        self._in_script_ld = False
        self._in_skip = 0
        self._in_title = False
        self._ld_puffer: list[str] = []
        self._laenge = 0

    def _text(self, t: str) -> None:
        self.text_teile.append(t)
        self._laenge += len(t)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self._a.append([a["href"], [], self._laenge])
        elif tag == "meta":
            key = a.get("property") or a.get("name")
            if key and a.get("content") is not None:
                self.meta.setdefault(key.lower(), a["content"])
        elif tag == "script":
            if (a.get("type") or "").lower() == "application/ld+json":
                self._in_script_ld = True
                self._ld_puffer = []
            else:
                self._in_skip += 1
        elif tag == "style":
            self._in_skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in ("br", "p", "div", "li", "h1", "h2", "h3", "h4", "tr", "section", "article"):
            self._text("\n")

    def handle_endtag(self, tag):
        if tag == "a" and self._a:
            href, teile, pos = self._a.pop()
            self.links.append(Link(href, " ".join("".join(teile).split()), pos))
        elif tag == "script":
            if self._in_script_ld:
                self.jsonld.append("".join(self._ld_puffer))
                self._in_script_ld = False
            elif self._in_skip:
                self._in_skip -= 1
        elif tag == "style" and self._in_skip:
            self._in_skip -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_script_ld:
            self._ld_puffer.append(data)
            return
        if self._in_skip:
            return
        if self._in_title:
            self.titel += data
        for offen in self._a:
            offen[1].append(data)
        self._text(data)


@dataclass
class Seite:
    url: str
    links: list[Link]
    meta: dict[str, str]
    jsonld: list
    titel: str
    text: str          # aufgeräumt (Leerraum zusammengefasst)
    rohtext: str = ""  # unverändert, passend zu Link.pos

    def absolut(self, href: str) -> str:
        return urljoin(self.url, href)


def lese(html: str, url: str) -> Seite:
    s = _Sammler()
    s.feed(html)
    s.close()
    objekte = []
    for roh in s.jsonld:
        try:
            objekte.append(json.loads(roh))
        except (json.JSONDecodeError, ValueError):
            continue
    roh = "".join(s.text_teile)
    text = re.sub(r"[ \t\r\f\v]+", " ", roh)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return Seite(url, s.links, s.meta, objekte, " ".join(s.titel.split()), text, roh)


def jsonld_events(seite: Seite) -> list[dict]:
    """Alle schema.org-Objekte vom Typ *Event (auch in @graph oder Listen)."""
    gefunden: list[dict] = []

    def gehe(o):
        if isinstance(o, list):
            for x in o:
                gehe(x)
        elif isinstance(o, dict):
            typ = o.get("@type")
            typen = typ if isinstance(typ, list) else [typ]
            if any(isinstance(t, str) and t.endswith("Event") for t in typen):
                gefunden.append(o)
            for k in ("@graph", "itemListElement", "item", "subEvent", "event"):
                if k in o:
                    gehe(o[k])

    gehe(seite.jsonld)
    return gefunden


_ZEIT = re.compile(r"\b(?:Beginn|Start|Einlass|Doors|ab|von)\s*:?\s*(\d{1,2})[:.](\d{2})\s*(?:Uhr)?", re.I)
_ZEIT_FREI = re.compile(r"\b(\d{1,2})[:.](\d{2})\s*Uhr\b")


def finde_uhrzeit(text: str) -> tuple[int, int] | None:
    """Beginn bevorzugt, sonst Einlass, sonst die erste „HH:MM Uhr“."""
    beginn = re.search(r"\bBeginn\s*:?\s*(\d{1,2})[:.](\d{2})", text, re.I)
    m = beginn or _ZEIT.search(text) or _ZEIT_FREI.search(text)
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    if hh > 23 or mm > 59:
        return None
    return hh, mm


def sauberer_titel(titel: str, abschneiden: list[str] = ()) -> str:
    """og:title/<title> ohne Seitennamen („Elternabend | Modernes“ → „Elternabend“)."""
    t = html_mod.unescape(titel or "").strip()
    for stueck in abschneiden:
        t = re.sub(rf"\s*[|–—·-]\s*{re.escape(stueck)}.*$", "", t, flags=re.I)
        t = re.sub(rf"^{re.escape(stueck)}\s*[|–—·:-]\s*", "", t, flags=re.I)
    return " ".join(t.split())


def titel_aus_slug(slug: str) -> str:
    worte = [w for w in re.split(r"[-_]+", slug) if w]
    return " ".join(w.capitalize() if w.islower() else w for w in worte)


MONATE = ["januar", "februar", "märz", "april", "mai", "juni", "juli", "august", "september", "oktober",
          "november", "dezember"]
_DATUM_LANG = re.compile(
    r"\b(?:(Mo|Di|Mi|Do|Fr|Sa|So)[a-z]*\.{0,2},?\s*)?(\d{1,2})\.?\s+(" + "|".join(MONATE) + r"|maerz)\s+(\d{4})\b",
    re.I)


def finde_daten(text: str) -> list[tuple[int, "date"]]:
    """Alle deutschen Langdaten („Sa., 21. November 2026“, „Sa. 21 November 2026“) mit Position."""
    from datetime import date as _date
    aus = []
    for m in _DATUM_LANG.finditer(text):
        monat_name = m.group(3).lower().replace("maerz", "märz")
        try:
            aus.append((m.start(), _date(int(m.group(4)), MONATE.index(monat_name) + 1, int(m.group(2)))))
        except ValueError:
            continue
    return aus
