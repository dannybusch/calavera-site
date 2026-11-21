"""Polyester Klub Oldenburg – fertiger iCal-Feed des Modern Events Calendar.

Der Feed enthält auch Vergangenes (ab 2024); gefiltert wird später auf Zeitraum und Fr/Sa.
LOCATION fehlt im Feed, deshalb fester Ort.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from icalendar import Calendar

from ..termin import TZ, Termin

SPALTE = "Polyester OL"
STADT = "Oldenburg"
FEED = "https://www.polyester-klub.de/?mec-ical-feed=1"


def _als_datetime(wert) -> tuple[date, datetime | None]:
    if isinstance(wert, datetime):
        d = wert if wert.tzinfo else wert.replace(tzinfo=TZ)
        d = d.astimezone(TZ)
        return d.date(), d
    return wert, None  # ganztägig


def hole(http, von, bis, einstellungen, warn=lambda text: None):
    text = http.text(einstellungen.get("url", FEED))
    kal = Calendar.from_ical(text)
    termine: list[Termin] = []
    for ev in kal.walk("VEVENT"):
        if ev.get("DTSTART") is None:
            continue
        tag, beginn = _als_datetime(ev.decoded("DTSTART"))
        ende = None
        if ev.get("DTEND") is not None:
            _, ende = _als_datetime(ev.decoded("DTEND"))
        # Vorfilter großzügig (Abend kann Vortag sein); exakter Fr/Sa-Filter passiert zentral
        if not (von - timedelta(days=1) <= tag <= bis + timedelta(days=1)):
            continue
        kategorien: list[str] = []
        cats = ev.get("CATEGORIES")
        for c in (cats if isinstance(cats, list) else [cats] if cats else []):
            kategorien += [str(x) for x in getattr(c, "cats", [c])]
        termine.append(Termin(
            quelle="polyester", titel=" ".join(str(ev.get("SUMMARY", "")).split()), tag=tag,
            beginn=beginn, ende=ende, ort="Polyester", stadt=STADT,
            url=str(ev.get("URL")) if ev.get("URL") else None, kategorien=kategorien,
            uid=str(ev.get("UID", "")) or f"polyester-{tag}-{ev.get('SUMMARY')}"))
    return termine
