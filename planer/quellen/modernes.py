"""Modernes Bremen (modernes.de, Astro-Seite).

Event-Links tragen das Datum: /events/2026-11-21/elternabend/ – Früh- und Spätparty am selben
Abend sind zwei Links mit demselben Datum und landen später in derselben Zelle.
"""
from __future__ import annotations

import re

from ._links import hole_ueber_links

SPALTE = "Modernes"
STADT = "Bremen"
LISTE = "https://modernes.de/programm/"
MUSTER = re.compile(r"modernes\.de/events/(?P<datum>\d{4}-\d{2}-\d{2})/(?P<slug>[^/?#]+)/?$")


def hole(http, von, bis, einstellungen, warn=lambda text: None):
    return hole_ueber_links(
        http, quelle="modernes", liste_url=einstellungen.get("url", LISTE), muster=MUSTER,
        ort="Modernes", stadt=STADT, von=von, bis=bis, seitenname=["Modernes", "Modernes Bremen"],
        details=einstellungen.get("details", True))
