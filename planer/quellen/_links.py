"""Baustein für Seiten, deren Event-Links das Datum enthalten (Modernes, Eisen).

Ablauf: Programmseite holen → Links nach Muster suchen → für jeden Fr/Sa im Zeitraum die
Detailseite holen → Titel und Uhrzeit aus JSON-LD, sonst og:title und Text.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from ..seite import finde_uhrzeit, jsonld_events, lese, sauberer_titel, titel_aus_slug
from ..termin import TZ, Termin, ist_fr_sa, zu_datetime

# Texte von Buttons, die kein Titel sind
GENERISCH = re.compile(r"^(zur party|zum konzert|mehr( infos?)?|details?|tickets?|infos?|weiterlesen|"
                       r"anmelden|kalender|📅.*|→|»|more|read more|jetzt.*)$", re.I)


def _iso(wert) -> datetime | None:
    if not isinstance(wert, str):
        return None
    try:
        d = datetime.fromisoformat(wert.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=TZ)
    return d


def hole_ueber_links(http, *, quelle: str, liste_url: str, muster: re.Pattern, ort: str, stadt: str,
                     von: date, bis: date, seitenname: list[str], details: bool = True) -> list[Termin]:
    """`muster` muss die Gruppen `datum` (JJJJ-MM-TT) und `slug` haben."""
    liste = lese(http.text(liste_url), liste_url)

    # gleiche Event-URL kann mehrfach verlinkt sein (Bild, Titel, Button) → Texte sammeln
    kandidaten: dict[str, dict] = {}
    for link in liste.links:
        url = liste.absolut(link.href).split("#")[0]
        m = muster.search(url)
        if not m:
            continue
        try:
            tag = date.fromisoformat(m.group("datum"))
        except ValueError:
            continue
        k = kandidaten.setdefault(url, {"tag": tag, "slug": m.group("slug"), "texte": []})
        if link.text and not GENERISCH.match(link.text) and len(link.text) <= 160:
            k["texte"].append(link.text)

    termine: list[Termin] = []
    for url, k in sorted(kandidaten.items(), key=lambda kv: (kv[1]["tag"], kv[0])):
        tag = k["tag"]
        if not (von <= tag <= bis):
            continue
        listentitel = max(k["texte"], key=len) if k["texte"] else ""
        titel, beginn, ende = listentitel, None, None

        # Detailseiten nur für Fr/Sa holen; andere Tage zählen nur für den Statusbericht
        if details and ist_fr_sa(tag):
            try:
                seite = lese(http.text(url), url)
            except Exception:  # Detailseite kaputt → mit dem weitermachen, was die Liste hergibt
                seite = None
            if seite:
                ev = next(iter(jsonld_events(seite)), None)
                if ev:
                    titel = sauberer_titel(str(ev.get("name") or "")) or titel
                    beginn = _iso(ev.get("startDate"))
                    ende = _iso(ev.get("endDate"))
                if not titel:
                    titel = sauberer_titel(seite.meta.get("og:title") or seite.titel, seitenname)
                if beginn is None:
                    # Uhrzeit nur in der Nähe des Titels suchen, nicht in Seitenleisten mit anderen Terminen
                    text = seite.text
                    pos = text.lower().find((titel or "").lower()[:20]) if titel else -1
                    ausschnitt = text[pos:pos + 800] if pos >= 0 else text[:1500]
                    hm = finde_uhrzeit(ausschnitt)
                    if hm:
                        beginn = zu_datetime(tag, *hm)

        termine.append(Termin(quelle=quelle, titel=titel or titel_aus_slug(k["slug"]), tag=tag,
                              beginn=beginn, ende=ende, ort=ort, stadt=stadt, url=url, uid=url))
    return termine
