"""Dark-Kalender = Sheet B „Partyplanungen Bremen-Oldenburg“. NUR LESEN.

Aufbau je Jahresblatt („Kalender 2027 Bremen“, Kalenderpedia-Vorlage): je Monat ein Spaltenblock
(Tag, Wochentag, Eintrag, KW), eine Zeile pro Tag 1–31. Die Blöcke werden an der Zeile „Tag 1“ erkannt,
nicht an der Kopfzeile, weil der CSV-Export Kopfzeilen weglassen kann. Zelltext: „15 Fr The House Of Usher + UP - JEVER“, Montage mit
KW-Nummer am Ende, dazu Feiertage aus der Kalendervorlage. Ort ist egal, es zählt der Titel.
Zellfarben spielen keine Rolle.

Schutz gegen falsches Blatt: Google liefert bei unbekanntem Blattnamen das erste Blatt. Deshalb
wird jeder Wochentag im Zelltext gegen das echte Datum geprüft; passt das Jahr nicht, wird das
Blatt verworfen.
"""
from __future__ import annotations

import re
from datetime import date

from .. import sheets
from ..termin import WOCHENTAG_KURZ, Termin

SPALTE = "Dark-Kalender"
STADT = ""

BLAETTER = ["Kalender {jahr} Bremen"]

FEIERTAGE = [
    "Neujahr", "Heilige Drei Könige", "Weiberfastnacht", "Rosenmontag", "Fastnacht", "Aschermittwoch",
    "Valentinstag", "Gründonnerstag", "Karfreitag", "Karsamstag", "Ostersonntag", "Ostermontag", "Ostern",
    "Tag der Arbeit", "Muttertag", "Christi Himmelfahrt", "Vatertag", "Pfingstsonntag", "Pfingstmontag",
    "Pfingsten", "Fronleichnam", "Mariä Himmelfahrt", "Weltkindertag", "Tag der Deutschen Einheit",
    "Reformationstag", "Halloween", "Allerheiligen", "Allerseelen", "Martinstag", "Volkstrauertag",
    "Buß- und Bettag", "Totensonntag", "Nikolaus", "1. Advent", "2. Advent", "3. Advent", "4. Advent",
    "Heiligabend", "1. Weihnachtstag", "2. Weihnachtstag", "Weihnachten", "Silvester",
    "Sommerzeit", "Winterzeit", "Beginn Sommerzeit", "Ende Sommerzeit",
]
# Längere zuerst, damit „1. Weihnachtstag“ nicht als „Weihnachten…“ halb abgeschnitten wird
_FEIERTAG_RE = re.compile(
    r"^(?:" + "|".join(re.escape(f) for f in sorted(FEIERTAGE, key=len, reverse=True)) + r")\b[\s,;/–-]*",
    re.I)
_ZELLE = re.compile(r"^\s*(\d{1,2})\s*\.?\s+(Mo|Di|Mi|Do|Fr|Sa|So)\b\.?\s*(.*)$", re.S)


_TAG_ZELLE = re.compile(r"^\s*(\d{1,2})\s*\.?(?:\s+(Mo|Di|Mi|Do|Fr|Sa|So)\b.*)?$", re.S)
_WT_ZELLE = re.compile(r"^\s*(Mo|Di|Mi|Do|Fr|Sa|So)\b\.?", re.S)


def _tagesanfaenge(zeile: list[str], tag: int) -> list[int]:
    """Spalten, in denen ein Tagesblock „<tag> <Wochentag> …“ beginnt (Wochentag in derselben
    oder einer der zwei folgenden Zellen). Eine KW-Zahl wird so nicht mit einem Tag verwechselt."""
    anfaenge = []
    for j, zelle in enumerate(zeile):
        m = _TAG_ZELLE.match(zelle or "")
        if not m or int(m.group(1)) != tag:
            continue
        if m.group(2) or any(_WT_ZELLE.match(z or "") for z in zeile[j + 1:j + 3]):
            anfaenge.append(j)
    return anfaenge


def _bloecke_finden(zeilen: list[list[str]]) -> tuple[int, dict[int, tuple[int, int]]]:
    """Zeile mit Tag 1 und je Monat (1–12) der Spaltenbereich [von, bis).

    Ohne Kopfzeile: Google lässt Titel-/Monatszeilen im CSV-Export manchmal weg. In der Zeile
    „Tag 1“ hat jeder der zwölf Monate einen Eintrag – deren Spalten sind die Blockanfänge."""
    breite = max((len(z) for z in zeilen), default=0)
    for i, zeile in enumerate(zeilen[:15]):
        anfaenge = _tagesanfaenge(zeile, 1)
        if len(anfaenge) == 12:
            bereiche = {}
            for k, j in enumerate(anfaenge):
                bereiche[k + 1] = (j, anfaenge[k + 1] if k < 11 else breite)
            return i, bereiche
    probe = " | ".join(f"Z{i + 1}: " + " ¦ ".join(z for z in zeile if z.strip())[:120] for i, zeile in enumerate(zeilen[:3]))
    raise ValueError("keine Zeile mit „1 <Wochentag>“ in allen zwölf Monaten gefunden – Aufbau geändert? "
                     f"Anfang des Blatts: {probe or '(leer)'}")


def titel_aus_rest(rest: str, wochentag: str) -> list[str]:
    """Feiertage und KW-Nummer entfernen; mehrere Zeilen in einer Zelle = mehrere Termine."""
    titel = []
    for teil in re.split(r"\s*\n\s*", rest.strip()):
        t = teil.strip()
        while True:
            neu = _FEIERTAG_RE.sub("", t, count=1).strip()
            if neu == t:
                break
            t = neu
        if wochentag == "Mo":
            t = re.sub(r"\s*\b\d{1,2}$", "", t).strip()
        t = t.strip(" ,;/–-")
        if t and not re.fullmatch(r"\d{1,2}", t):
            titel.append(" ".join(t.split()))
    return titel


def lese_jahresblatt(zeilen: list[list[str]], jahr: int) -> tuple[list[tuple[date, str]], int, int]:
    """→ (Liste (Tag, Titel), Anzahl geprüfter Tageszellen, davon falscher Wochentag)"""
    erste, bereiche = _bloecke_finden(zeilen)
    funde: list[tuple[date, str]] = []
    geprueft = falsch = 0
    for zeile in zeilen[erste:]:
        for monat, (a, b) in bereiche.items():
            zellen = [z.strip() for z in zeile[a:b] if z and z.strip()]
            if not zellen:
                continue
            m = _ZELLE.match(" ".join(zellen) if len(zellen) > 1 else zellen[0])
            if not m:
                continue
            tagnr, wt, rest = int(m.group(1)), m.group(2), m.group(3)
            try:
                d = date(jahr, monat, tagnr)
            except ValueError:
                continue
            geprueft += 1
            if WOCHENTAG_KURZ[d.weekday()] != wt:
                falsch += 1
                continue
            for t in titel_aus_rest(rest, wt):
                funde.append((d, t))
    return funde, geprueft, falsch


def hole(http, von, bis, einstellungen, warn=lambda text: None):
    vorlagen = einstellungen.get("blaetter", BLAETTER)
    termine: list[Termin] = []
    for jahr in range(von.year, bis.year + 1):
        for vorlage in vorlagen:
            name = vorlage.format(jahr=jahr)
            try:
                zeilen = sheets.lese_blatt(http, sheets.SHEET_B, name)
                funde, geprueft, falsch = lese_jahresblatt(zeilen, jahr)
            except Exception as e:
                warn(f"{name}: {e}")
                continue
            if geprueft == 0 or falsch > geprueft * 0.1:
                warn(f"{name}: Wochentage passen nicht zu {jahr} – Blatt fehlt wohl, übersprungen")
                continue
            for d, titel in funde:
                termine.append(Termin(quelle="dark_kalender", titel=titel, tag=d,
                                      uid=f"dark-{d.isoformat()}-{titel}", artverwandt=True))
    return termine
