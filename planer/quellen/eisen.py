"""Eisen Bremen (eisen-bremen.com, GastroCMS).

Event-Links tragen das Datum am Ende: /event/bad-luck-baby-2026-11-26
"""
from __future__ import annotations

import re

from ._links import hole_ueber_links

SPALTE = "Eisen"
STADT = "Bremen"
LISTE = "https://eisen-bremen.com/veranstaltungen.php"
MUSTER = re.compile(r"eisen-bremen\.com/event/(?P<slug>[^/?#]+?)-(?P<datum>\d{4}-\d{2}-\d{2})/?$")


def hole(http, von, bis, einstellungen, warn=lambda text: None):
    return hole_ueber_links(
        http, quelle="eisen", liste_url=einstellungen.get("url", LISTE), muster=MUSTER,
        ort="Eisen", stadt=STADT, von=von, bis=bis, seitenname=["Eisen", "Eisen Bremen"],
        details=einstellungen.get("details", True), extra_tage=einstellungen.get("extra_tage", ()))
