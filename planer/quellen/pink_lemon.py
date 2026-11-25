"""Pink Lemon Party (pink-lemon-party.de) – Ü-Party „Up den Höfen“ Bremen, 1. Samstag alle zwei Monate.

Die Startseite listet die Termine als Text: „05. dezember 2026“, dazu „von 20:00 bis 1:00 Uhr“ und
das Line-up je Club. Keine Links zu Einzelterminen.
"""
from __future__ import annotations

from ..seite import finde_daten, finde_uhrzeit, lese
from ..termin import Termin, zu_datetime

SPALTE = "Pink Lemon"
STADT = "Bremen"
LISTE = "https://www.pink-lemon-party.de/"


def hole(http, von, bis, einstellungen, warn=lambda text: None):
    url = einstellungen.get("url", LISTE)
    seite = lese(http.text(url), url)
    text = seite.rohtext
    # gemeinsame Uhrzeit („von 20:00 bis 1:00 Uhr“), falls je Termin keine eigene steht
    standard = finde_uhrzeit(text)
    daten = finde_daten(text)
    termine, gesehen = [], set()
    for k, (pos, tag) in enumerate(daten):
        if tag in gesehen or not (von <= tag <= bis):
            continue
        gesehen.add(tag)
        ende = daten[k + 1][0] if k + 1 < len(daten) else pos + 400
        zeit = finde_uhrzeit(text[pos:ende]) or standard
        termine.append(Termin(quelle="pink_lemon", titel="Pink Lemon Party", tag=tag,
                              beginn=zu_datetime(tag, *zeit) if zeit else None,
                              ort="Up den Höfen", stadt=STADT, url=url, uid=f"pink-lemon-{tag}"))
    if not daten:
        warn("kein Datum auf der Seite gefunden – Aufbau geändert?")
    return termine
