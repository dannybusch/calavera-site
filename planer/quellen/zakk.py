"""zakk klubraum (zakk.klubraum.org).

Die Startseite zeigt die nächsten Tage: „Sa 21.11.26, 21:00“, darunter der Titel. Die Termine sind
nicht verlinkt. Das Monatsprogramm (/programs/current) ist ein InDesign-XML ohne Jahr und taugt
nicht als Quelle – deshalb sieht der Planer beim zakk nur etwa eine Woche voraus.
"""
from __future__ import annotations

import re
from datetime import date

from ..seite import lese
from ..termin import Termin, zu_datetime

SPALTE = "zakk"
STADT = "Bremen"
LISTE = "https://zakk.klubraum.org/"
_DATUM = re.compile(r"\b(Mo|Di|Mi|Do|Fr|Sa|So)\.?\s+(\d{1,2})\.(\d{1,2})\.(\d{2}(?:\d{2})?)\s*,?\s*(?:(\d{1,2})[:.](\d{2}))?")


def hole(http, von, bis, einstellungen, warn=lambda text: None):
    url = einstellungen.get("url", LISTE)
    seite = lese(http.text(url), url)
    zeilen = [z.strip() for z in seite.text.split("\n") if z.strip()]
    termine = []
    for i, zeile in enumerate(zeilen):
        m = _DATUM.search(zeile)
        if not m:
            continue
        jahr = int(m.group(4))
        jahr += 2000 if jahr < 100 else 0
        try:
            tag = date(jahr, int(m.group(3)), int(m.group(2)))
        except ValueError:
            continue
        rest = zeile[m.end():].strip(" ,–-|")
        titel = rest or next((z for z in zeilen[i + 1:i + 3] if not _DATUM.search(z)), "")
        if not titel or not (von <= tag <= bis):
            continue
        beginn = zu_datetime(tag, int(m.group(5)), int(m.group(6))) if m.group(5) else None
        termine.append(Termin(quelle="zakk", titel=" ".join(titel.split()), tag=tag, beginn=beginn,
                              ort="zakk", stadt=STADT, url=url, uid=f"zakk-{tag}-{titel}"))
    return termine
