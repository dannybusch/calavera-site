"""Baustein für Programmlisten, deren Links kein Datum tragen (Aladin, Shagall, Zollkantine).

Jede „Karte“ reicht vom ersten Link eines Events bis zum ersten Link des nächsten. Ob das Datum
hinter oder vor dem Titel steht, wird an der ganzen Seite abgelesen: Es gilt die Richtung, in der
die meisten Events genau einen Datumstreffer haben. So kommen die Plugins ohne CSS-Selektoren aus.
"""
from __future__ import annotations

import re
from typing import Callable

from ._links import GENERISCH


def karten(seite, muster: re.Pattern, finder: Callable[[str], list], rand: int = 600) -> list[dict]:
    """→ [{url, slug, titel, text}] in Seitenreihenfolge; `text` ist der Kartenabschnitt mit dem Datum.
    `finder(text)` liefert die Datumstreffer eines Abschnitts (beliebige Objekte, Anzahl zählt)."""
    events: dict[str, dict] = {}
    for link in seite.links:
        url = seite.absolut(link.href).split("#")[0]
        m = muster.search(url)
        if not m:
            continue
        e = events.setdefault(url, {"url": url, "slug": m.groupdict().get("slug") or "", "von": link.pos,
                                    "bis": link.pos, "texte": []})
        e["bis"] = max(e["bis"], link.pos + len(link.text))
        if link.text and not GENERISCH.match(link.text) and len(link.text) <= 160:
            e["texte"].append(link.text)
    liste = sorted(events.values(), key=lambda e: e["von"])
    if not liste:
        return []
    roh = seite.rohtext
    for k, e in enumerate(liste):
        ende = liste[k + 1]["von"] if k + 1 < len(liste) else min(len(roh), e["bis"] + rand)
        anfang = liste[k - 1]["bis"] if k > 0 else max(0, e["von"] - rand)
        e["danach"] = roh[e["von"]:ende]
        e["davor"] = roh[anfang:e["von"]]
    danach_ok = sum(len(finder(e["danach"])) == 1 for e in liste)
    davor_ok = sum(len(finder(e["davor"])) == 1 for e in liste)
    feld = "danach" if danach_ok >= davor_ok else "davor"
    aus = []
    for e in liste:
        titel = max(e["texte"], key=len) if e["texte"] else ""
        text = e[feld]
        if titel:
            text = text.replace(titel, " ")  # Titel nicht als Raum/Datum missverstehen
        aus.append({"url": e["url"], "slug": e["slug"], "titel": titel, "text": text, "richtung": feld})
    return aus
