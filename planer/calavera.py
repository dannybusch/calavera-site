"""Eigene Abende aus Sheet A lesen (nur lesen) – Grundlage der Kollisionsbewertung.

Monatsblatt „Dezember 2026“: Zeile 1 Kopf (C Titel, D Theke, E Tür, F DJ), A Wochentag,
B Datum „04.12.“ ohne Jahr (das Jahr kommt aus dem Blattnamen).
"""
from __future__ import annotations

import re
from datetime import date

from . import sheets
from .termin import WOCHENTAG_KURZ

_DATUM = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})\.?\s*$")


def monate(von: date, bis: date) -> list[tuple[int, int]]:
    j, m, aus = von.year, von.month, []
    while (j, m) <= (bis.year, bis.month):
        aus.append((j, m))
        j, m = (j + 1, 1) if m == 12 else (j, m + 1)
    return aus


def lese_monat(zeilen: list[list[str]], jahr: int, monat: int) -> dict[date, str] | None:
    """→ {Datum: Titel} oder None, wenn das Blatt nicht zu diesem Monat passt."""
    abende: dict[date, str] = {}
    fremd = 0
    for z in zeilen[1:]:
        z = (z + [""] * 3)[:3]
        m = _DATUM.match(z[1])
        if not m:
            continue
        tag, mon = int(m.group(1)), int(m.group(2))
        if mon != monat:
            fremd += 1
            continue
        try:
            d = date(jahr, mon, tag)
        except ValueError:
            continue
        if z[0].strip() and z[0].strip()[:2] != WOCHENTAG_KURZ[d.weekday()]:
            fremd += 1
            continue
        if z[2].strip():
            abende[d] = z[2].strip()
    if fremd and fremd >= len(abende):
        return None  # Google hat ein anderes Blatt geliefert
    return abende


def lese(http, von: date, bis: date, warn=lambda text: None, leser=None) -> dict[date, str]:
    """`leser(blattname) -> Zeilen` – Standard: CSV-Export; mit Service-Account: Sheets API."""
    leser = leser or (lambda name: sheets.lese_blatt(http, sheets.ziel_a(), name))
    alle: dict[date, str] = {}
    fehlend: list[str] = []
    for jahr, monat in monate(von, bis):
        name = sheets.monatsblatt_name(jahr, monat)
        try:
            ergebnis = lese_monat(leser(name), jahr, monat)
        except Exception as e:
            warn(f"Sheet A „{name}“: {e}")
            continue
        if ergebnis is None:
            fehlend.append(name)
            continue
        alle.update(ergebnis)
    if fehlend:
        warn(f"Sheet A: Blätter fehlen (noch): {', '.join(fehlend)} – dort ⚠/◐ ohne eigene Abende")
    return alle
