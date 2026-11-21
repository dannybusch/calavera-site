"""Zollkantine = Termine von musikszene-bremen.de (WordPress, Kategorie „termine“).

Jeder Termin ist ein Beitrag; das Veranstaltungsdatum steht als Text hinter dem Titel, in mehreren
Formen: „Sa., 14.11.2026 20:00“, „So., 27.12. - Di., 29.12. 18:00“ (ohne Jahr) oder
„13. - 15. November 2026“. Mehrtägiges erscheint an jedem Tag. Ort fehlt meist → „Zollkantine“.
Die Liste kann über /page/2/ … weitergehen.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from . import _karten
from ..seite import MONATE, lese, titel_aus_slug
from ..termin import Termin, zu_datetime

SPALTE = "Zollkantine"
STADT = "Bremen"
LISTE = "https://www.musikszene-bremen.de/category/termine/"
MAX_SEITEN = 6
MAX_TAGE = 7          # längere Spannen sind eher „Ausstellung“ als ein Abend
MUSTER = re.compile(r"musikszene-bremen\.de/(?!category/|tag/|author/|page/|feed|wp-|kontakt|impressum|datenschutz)"
                    r"(?P<slug>[a-z0-9][a-z0-9-]*)/?$")

_WT = r"(?:(?:Mo|Di|Mi|Do|Fr|Sa|So)[a-z]*\.?,?\s*)?"
_ZEIT = r"(?:\s*,?\s*(?:ab\s*)?(\d{1,2})[:.](\d{2}))?"
_SPANNE_KURZ = re.compile(_WT + r"(\d{1,2})\.(\d{1,2})\.(\d{4})?\s*[–—-]\s*" + _WT + r"(\d{1,2})\.(\d{1,2})\.(\d{4})?" + _ZEIT)
_EINZEL = re.compile(_WT + r"(\d{1,2})\.(\d{1,2})\.(\d{4})" + _ZEIT)
_SPANNE_LANG = re.compile(r"(\d{1,2})\.\s*[–—-]\s*(\d{1,2})\.\s+(" + "|".join(MONATE) + r")\s+(\d{4})", re.I)


def _jahr_raten(tag: int, monat: int, heute: date) -> int:
    """Datum ohne Jahr: das nächste Vorkommen ab 60 Tagen vor heute."""
    for jahr in (heute.year, heute.year + 1):
        try:
            if date(jahr, monat, tag) >= heute - timedelta(days=60):
                return jahr
        except ValueError:
            continue
    return heute.year + 1


def daten(text: str, heute: date) -> list[tuple[list[date], tuple[int, int] | None]]:
    """Alle Termin-Angaben eines Abschnitts → [(Tage, Uhrzeit)]."""
    aus, belegt = [], []

    def frei(m):
        return not any(a < m.end() and m.start() < b for a, b in belegt)

    def spanne(a: date, b: date) -> list[date]:
        if b < a or (b - a).days >= MAX_TAGE:
            return [a]
        return [a + timedelta(days=i) for i in range((b - a).days + 1)]

    for m in _SPANNE_KURZ.finditer(text):
        t1, m1, j1, t2, m2, j2, hh, mm = m.groups()
        j2 = int(j2) if j2 else (int(j1) if j1 else _jahr_raten(int(t2), int(m2), heute))
        j1 = int(j1) if j1 else (j2 if int(m1) <= int(m2) else j2 - 1)
        try:
            a, b = date(j1, int(m1), int(t1)), date(j2, int(m2), int(t2))
        except ValueError:
            continue
        aus.append((m.start(), spanne(a, b), (int(hh), int(mm)) if hh else None))
        belegt.append((m.start(), m.end()))
    for m in _SPANNE_LANG.finditer(text):
        if not frei(m):
            continue
        t1, t2, monat, jahr = m.groups()
        mo = MONATE.index(monat.lower()) + 1
        try:
            aus.append((m.start(), spanne(date(int(jahr), mo, int(t1)), date(int(jahr), mo, int(t2))), None))
        except ValueError:
            continue
        belegt.append((m.start(), m.end()))
    for m in _EINZEL.finditer(text):
        if not frei(m):
            continue
        t, mo, j, hh, mm = m.groups()
        try:
            aus.append((m.start(), [date(int(j), int(mo), int(t))], (int(hh), int(mm)) if hh else None))
        except ValueError:
            continue
        belegt.append((m.start(), m.end()))
    return [(tage, zeit) for _, tage, zeit in sorted(aus, key=lambda x: x[0])]


def hole(http, von, bis, einstellungen, warn=lambda text: None):
    start = einstellungen.get("url", LISTE)
    heute = von
    gesehen: set[str] = set()
    termine: list[Termin] = []
    for nr in range(1, einstellungen.get("max_seiten", MAX_SEITEN) + 1):
        url = start if nr == 1 else start.rstrip("/") + f"/page/{nr}/"
        try:
            seite = lese(http.text(url), url)
        except Exception:
            if nr == 1:
                raise
            break  # keine weitere Seite
        neu = 0
        for k in _karten.karten(seite, MUSTER, lambda t: daten(t, heute)):
            if k["url"] in gesehen:
                continue
            gesehen.add(k["url"])
            treffer = daten(k["text"], heute)
            if not treffer:
                continue
            neu += 1
            tage, zeit = treffer[0]
            titel = k["titel"] or titel_aus_slug(k["slug"])
            for tag in tage:
                if von <= tag <= bis:
                    termine.append(Termin(quelle="zollkantine", titel=titel, tag=tag,
                                          beginn=zu_datetime(tag, *zeit) if zeit else None,
                                          ort="Zollkantine", stadt=STADT, url=k["url"], uid=f"{k['url']}#{tag}"))
        if neu == 0:
            break
    return termine
