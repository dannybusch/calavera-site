"""Lila Eule Bremen (lilaeule.com, Jimdo).

Die Seite „Shows | Tickets“ ist reiner Text ohne Links zu Einzelterminen:

    Sa. 28.11.2026
    um 19 h / 19.30 h
    IGINIO (RELEASE SHOW), special guests …
    Tickets: …

Meist steht das Datum vor dem Titel, manchmal dahinter. Deshalb wird jede Textzeile dem nächst-
gelegenen Datum zugeordnet (gezählt in Inhaltszeilen; bei Gleichstand dem darüber, außer das Datum
darunter hat sonst keinen Titel hinter sich). Titel = erste zugeordnete Zeile hinter dem
Datum, sonst die nächste davor. Zwei Uhrzeiten („19 h / 19.30 h“) sind Einlass / Beginn → Beginn.
"""
from __future__ import annotations

import re
from datetime import date

from ..seite import lese
from ..termin import WOCHENTAG_KURZ, Termin, zu_datetime

SPALTE = "Lila Eule"
STADT = "Bremen"
LISTE = "https://www.lilaeule.com/shows-tickets/"

_DATUM = re.compile(r"\b(Mo|Di|Mi|Do|Fr|Sa|So)\.?\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
_ZEIT = re.compile(r"(\d{1,2})(?:[.:](\d{2}))?\s*h\b")
_ZEITZEILE = re.compile(r"^(um\s+)?\d{1,2}([.:]\d{2})?\s*h\b", re.I)
_META = re.compile(r"^(um\s+)?\d{1,2}([.:]\d{2})?\s*h\b|^(tickets?|vvk|vorverkauf|einlass|eintritt|beginn|link|https?://|"
                   r"reservix|eventim|deinetickets|abendkasse|ak\b|\(bis\b)", re.I)


def _ist_meta(zeile: str) -> bool:
    return bool(_META.search(zeile)) or len(zeile) < 3


def termine_aus_text(text: str, warn=lambda text: None) -> list[tuple[date, str, tuple[int, int] | None]]:
    zeilen = [" ".join(z.split()) for z in text.split("\n")]
    zeilen = [z for z in zeilen if z]
    daten: list[tuple[int, date]] = []
    for i, z in enumerate(zeilen):
        m = _DATUM.search(z)
        if m:
            try:
                d = date(int(m.group(4)), int(m.group(3)), int(m.group(2)))
            except ValueError:
                continue
            if WOCHENTAG_KURZ[d.weekday()] != m.group(1):
                warn(f"„{m.group(0)}“: Wochentag passt nicht zum Datum (ist ein {WOCHENTAG_KURZ[d.weekday()]}) – "
                     "Tippfehler auf der Seite? Eingetragen wird das Datum.")
            daten.append((i, d))
    if not daten:
        return []
    pos = [i for i, _ in daten]
    # Abstand zählt nur Inhaltszeilen (Uhrzeit-, Ticket-Zeilen zählen nicht mit)
    inhalt = [j for j, z in enumerate(zeilen) if j in pos or not _ist_meta(z)]
    rang = {j: k for k, j in enumerate(inhalt)}

    def hat_inhalt_danach(i: int) -> bool:
        naechstes = min((p for p in pos if p > i), default=len(zeilen))
        return any(j for j in inhalt if i < j < naechstes and j not in pos)

    zugeordnet: dict[int, list[int]] = {i: [] for i in pos}
    for j in inhalt:
        if j in zugeordnet:
            continue
        davor = max((i for i in pos if i < j), default=None)
        danach = min((i for i in pos if i > j), default=None)
        if davor is None and danach is None:
            continue
        if danach is None:
            ziel = davor
        elif davor is None:
            ziel = danach
        else:
            a, b = rang[j] - rang[davor], rang[danach] - rang[j]
            # Gleichstand: zum Datum darunter nur, wenn das sonst keinen Titel hinter sich hat
            ziel = davor if a < b or (a == b and hat_inhalt_danach(danach)) else danach
        zugeordnet[ziel].append(j)

    aus = []
    for i, tag in daten:
        nach = sorted(j for j in zugeordnet[i] if j > i)
        vor = sorted((j for j in zugeordnet[i] if j < i), reverse=True)
        # Rest der Datumszeile kann der Titel sein („Sa. 5.12.2026 BRAGOLIN & CARRELLE“)
        rest = _DATUM.sub("", zeilen[i]).replace("neuer Termin:", "").strip(" :–-|")
        titel = rest if len(rest) > 3 and not _ist_meta(rest) else (
            zeilen[nach[0]] if nach else (zeilen[vor[0]] if vor else ""))
        zeit = None
        for z in zeilen[i + 1:i + 4]:
            if _DATUM.search(z):
                break
            if _ZEITZEILE.match(z):
                teile = [_ZEIT.search(t) for t in z.split("(")[0].split("/")]
                teile = [t for t in teile if t and int(t.group(1)) < 24]
                if teile:
                    zeit = (int(teile[-1].group(1)), int(teile[-1].group(2) or 0))  # Einlass / Beginn → Beginn
                break
        if titel:
            aus.append((tag, titel, zeit))
    return aus


def hole(http, von, bis, einstellungen, warn=lambda text: None):
    url = einstellungen.get("url", LISTE)
    seite = lese(http.text(url), url)
    termine = []
    for tag, titel, zeit in termine_aus_text(seite.text, warn):
        if not (von <= tag <= bis):
            continue
        termine.append(Termin(quelle="lila_eule", titel=titel, tag=tag,
                              beginn=zu_datetime(tag, *zeit) if zeit else None,
                              ort="Lila Eule", stadt=STADT, url=url, uid=f"lila-eule-{tag}-{titel[:40]}"))
    return termine
