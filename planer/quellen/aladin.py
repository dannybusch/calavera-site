"""Aladin & Tivoli Bremen (aladin-bremen.de, WordPress + WooCommerce).

Die Programmseite ist eine lange, chronologische Liste (bis ins übernächste Jahr). Die Event-Links
(/veranstaltungen/<slug-oder-id>/) tragen kein Datum; das steht als Text in der Karte:
„Sa. 21 November 2026“, dazu der Raum (Aladin, Tivoli, Aladin & Tivoli).

Karten werden mit `_karten` ohne CSS-Selektoren erkannt. Uhrzeiten nennt die Liste nicht,
die kommen von der Detailseite (nur Fr/Sa).
"""
from __future__ import annotations

import re
from datetime import date

from ..seite import finde_daten, finde_uhrzeit, jsonld_events, lese, sauberer_titel, titel_aus_slug
from ..termin import Termin, ist_fr_sa, zu_datetime
from . import _karten
from ._links import _iso

SPALTE = "Aladin/Tivoli"
STADT = "Bremen"
LISTE = "https://www.aladin-bremen.de/unser-programm/"
MUSTER = re.compile(r"aladin-bremen\.de/veranstaltungen/(?P<slug>[^/?#]+)/?$")
_RAUM = re.compile(r"\b(Aladin\s*(?:&|und|\+)\s*Tivoli|Tivoli|Aladin)\b", re.I)


def _raum(text: str) -> str:
    m = _RAUM.search(text)
    if not m:
        return "Aladin"
    r = m.group(1)
    return "Aladin & Tivoli" if "tivoli" in r.lower() and "aladin" in r.lower() else r.capitalize()


def karten(seite) -> list[dict]:
    """→ Liste {url, titel, tag, raum} in Seitenreihenfolge."""
    aus = []
    for k in _karten.karten(seite, MUSTER, finde_daten):
        daten = finde_daten(k["text"])
        if not daten:
            continue
        tag = daten[0][1] if k["richtung"] == "danach" else daten[-1][1]
        aus.append({"url": k["url"], "titel": k["titel"] or titel_aus_slug(k["slug"]), "tag": tag,
                    "raum": _raum(k["text"])})
    return aus


def hole(http, von, bis, einstellungen, warn=lambda text: None):
    url = einstellungen.get("url", LISTE)
    seite = lese(http.text(url), url)
    termine: list[Termin] = []
    for k in karten(seite):
        tag: date = k["tag"]
        if not (von <= tag <= bis):
            continue
        titel, beginn, ende = k["titel"], None, None
        if einstellungen.get("details", True) and ist_fr_sa(tag):
            try:
                detail = lese(http.text(k["url"]), k["url"])
            except Exception:
                detail = None
            if detail:
                ev = next(iter(jsonld_events(detail)), None)
                if ev:
                    beginn, ende = _iso(ev.get("startDate")), _iso(ev.get("endDate"))
                if beginn is None:
                    text = detail.text
                    pos = text.lower().find(titel.lower()[:20])
                    hm = finde_uhrzeit(text[pos:pos + 800] if pos >= 0 else text[:1500])
                    if hm:
                        beginn = zu_datetime(tag, *hm)
                if not titel:
                    titel = sauberer_titel(detail.meta.get("og:title") or detail.titel, ["Aladin", "Aladin Bremen"])
        termine.append(Termin(quelle="aladin", titel=titel, tag=tag, beginn=beginn, ende=ende,
                              ort=k["raum"], stadt=STADT, url=k["url"], uid=k["url"], hinweis=k["raum"]))
    if not termine and seite.links:
        warn("keine Karten mit Datum erkannt – Aufbau der Programmseite geändert?")
    return termine
