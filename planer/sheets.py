"""Zugriff auf die Google Sheets.

Etappe 1 liest nur, und zwar über den öffentlichen CSV-Export (beide Sheets sind per Link lesbar):
ein reiner HTTP-GET, der nichts verändern kann. Geschrieben wird erst in Etappe 2 mit dem
Service-Account – und dann ausschließlich in Sheet A (siehe `pruefe_schreibziel`).
"""
from __future__ import annotations

import csv
import io
import os
from urllib.parse import quote

# [A] Calavera Terminkalender – Ziel. Ein Blatt pro Monat, z. B. „Dezember 2026“.
SHEET_A = "1vB4JxJv_iHta4a0sm-YMjgMOTlVuuYT_cyYqO6lPf3I"
# [B] Partyplanungen Bremen-Oldenburg (Dark Parties) – NUR LESEN. Niemals hineinschreiben.
SHEET_B = "1RMqFT66ruLpih4hzMufI24EmYQvyj2ErY8Ae2vVw23U"

SCHREIBBAR = frozenset({SHEET_A})


def ziel_a() -> str:
    """Sheet A – oder zum Ausprobieren eine Kopie davon (Umgebungsvariable PLANER_SHEET_A)."""
    kopie = os.environ.get("PLANER_SHEET_A", "").strip()
    return kopie or SHEET_A

MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September",
          "Oktober", "November", "Dezember"]


class SchreibVerbot(Exception):
    pass


def pruefe_schreibziel(sheet_id: str) -> None:
    """Jeder schreibende Zugriff muss hier durch. Alles außer Sheet A wird abgewiesen."""
    if sheet_id == SHEET_B or sheet_id not in SCHREIBBAR | {ziel_a()}:
        raise SchreibVerbot(f"Schreiben in Sheet {sheet_id} ist verboten – nur Sheet A ist Ziel.")


def export_url(sheet_id: str, blatt: str) -> str:
    # headers=0: Google soll keine Kopfzeilen erraten und zusammenfassen
    return (f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq"
            f"?tqx=out:csv&headers=0&sheet={quote(blatt)}")


def lese_blatt(http, sheet_id: str, blatt: str) -> list[list[str]]:
    """Blatt als Zeilenliste (Strings). Achtung: Google liefert bei unbekanntem Blattnamen
    stillschweigend das erste Blatt – Aufrufer müssen den Inhalt prüfen."""
    text = http.text(export_url(sheet_id, blatt))
    if text.lstrip().startswith("<"):
        raise ValueError(f"Blatt „{blatt}“: keine CSV-Antwort (Freigabe geändert?)")
    return [list(z) for z in csv.reader(io.StringIO(text))]


def monatsblatt_name(jahr: int, monat: int) -> str:
    return f"{MONATE[monat - 1]} {jahr}"
