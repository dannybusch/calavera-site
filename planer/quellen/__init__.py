"""Plugin-Verzeichnis: ein Modul pro Quelle, jedes mit einer Funktion

    hole(http, von: date, bis: date, einstellungen: dict, warn) -> list[Termin]

(`warn(text)` meldet Auffälliges, ohne abzubrechen)

und den Konstanten SPALTE (Spaltenname in Sheet A) und STADT. Neues Plugin = neue Datei hier +
Eintrag in PLUGINS + Eintrag in planer/quellen.yml.
"""
from __future__ import annotations

from importlib import import_module

PLUGINS = {
    "dark_kalender": "dark_kalender",
    "modernes": "modernes",
    "aladin": "aladin",
    "eisen": "eisen",
    "polyester": "polyester",
    "shagall": "shagall",
    "zollkantine": "zollkantine",
    "zakk": "zakk",
    "werder": "werder",
}


def lade(plugin_id: str):
    if plugin_id not in PLUGINS:
        raise KeyError(f"unbekannte Quelle „{plugin_id}“ – bekannt: {', '.join(PLUGINS)}")
    return import_module(f"{__name__}.{PLUGINS[plugin_id]}")
