"""Shagall Klub Bremen (shagall-klub.com, Wix).

Liste unter /shows, Event-Links /events/<slug>, Datum hinter dem Titel ohne Wochentag:
„21. Nov. 2026, 23:00 – 22. Nov. 2026, 03:00“ oder nur „20. Nov. 2026, 22:30“.
Der Beginn reicht; die Abend-Zuordnung (nach Mitternacht → Vortag) macht Termin.abend.
"""
from __future__ import annotations

import re
from datetime import date

from . import _karten
from ..seite import lese, titel_aus_slug
from ..termin import Termin, zu_datetime

SPALTE = "Shagall"
STADT = "Bremen"
LISTE = "https://www.shagall-klub.com/shows"
MUSTER = re.compile(r"shagall-klub\.com/events/(?P<slug>[^/?#]+)/?$")

KURZMONATE = {"jan": 1, "feb": 2, "mär": 3, "mar": 3, "märz": 3, "apr": 4, "mai": 5, "jun": 6, "juni": 6,
              "jul": 7, "juli": 7, "aug": 8, "sep": 9, "sept": 9, "okt": 10, "nov": 11, "dez": 12,
              "januar": 1, "februar": 2, "april": 4, "august": 8, "september": 9, "oktober": 10,
              "november": 11, "dezember": 12}
_DATUM = re.compile(r"\b(\d{1,2})\.\s*([A-Za-zÄÖÜäöü]{3,9})\.?\s+(\d{4})(?:,?\s*(\d{1,2}):(\d{2}))?")


def finde(text: str) -> list[tuple[date, tuple[int, int] | None]]:
    """Nur das erste Datum je „von – bis“ zählt (sonst hätte jede Karte zwei Treffer)."""
    teile = re.split(r"\s[–—-]\s", text, maxsplit=1)
    aus = []
    for m in _DATUM.finditer(teile[0]):
        monat = KURZMONATE.get(m.group(2).lower())
        if not monat:
            continue
        try:
            d = date(int(m.group(3)), monat, int(m.group(1)))
        except ValueError:
            continue
        zeit = (int(m.group(4)), int(m.group(5))) if m.group(4) else None
        aus.append((d, zeit))
    return aus


def hole(http, von, bis, einstellungen, warn=lambda text: None):
    url = einstellungen.get("url", LISTE)
    seite = lese(http.text(url), url)
    termine = []
    for k in _karten.karten(seite, MUSTER, finde):
        treffer = finde(k["text"])
        if not treffer:
            continue
        tag, zeit = treffer[0] if k["richtung"] == "danach" else treffer[-1]
        if not (von <= tag <= bis):
            continue
        termine.append(Termin(quelle="shagall", titel=k["titel"] or titel_aus_slug(re.sub(r"-\d+$", "", k["slug"])),
                              tag=tag, beginn=zu_datetime(tag, *zeit) if zeit else None,
                              ort="Shagall", stadt=STADT, url=k["url"], uid=k["url"]))
    if not termine and any(MUSTER.search(seite.absolut(l.href)) for l in seite.links):
        warn("Event-Links gefunden, aber kein Datum erkannt – Aufbau geändert?")
    elif not any(MUSTER.search(seite.absolut(l.href)) for l in seite.links):
        warn("keine Event-Links im HTML – lädt Wix die Liste jetzt per JavaScript nach?")
    return termine
