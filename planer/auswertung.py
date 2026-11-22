"""Filtern (nur Fr/Sa), Duplikate, „artverwandt“, Kollisionen und Zelltexte."""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from datetime import date
from difflib import SequenceMatcher

from .termin import Termin, ist_fr_sa

FUELLWORTE = {"party", "partys", "parties", "live", "presents", "praesentiert", "präsentiert", "konzert",
              "the", "die", "der", "das", "und", "and", "mit", "feat", "ft", "vs", "x", "+", "&", "-", "–"}

HOCH, MITTEL = "⚠", "◐"


# --- Vergleich von Titeln --------------------------------------------------------------------

def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _tokens(text: str) -> set[str]:
    return {w for w in _norm(text).split() if w not in FUELLWORTE}


def aehnlichkeit(a: str, b: str) -> float:
    """Wie rapidfuzz token_set_ratio, nur mit der Standardbibliothek: 0–1."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    gemeinsam = " ".join(sorted(ta & tb))
    nur_a = " ".join(sorted(ta - tb))
    nur_b = " ".join(sorted(tb - ta))
    s1 = (gemeinsam + " " + nur_a).strip()
    s2 = (gemeinsam + " " + nur_b).strip()
    werte = [SequenceMatcher(None, s1, s2).ratio()]
    if gemeinsam:
        werte += [SequenceMatcher(None, gemeinsam, s1).ratio(), SequenceMatcher(None, gemeinsam, s2).ratio()]
    return max(werte)


# --- Schritte ---------------------------------------------------------------------------------

def nur_fr_sa(termine: list[Termin], von: date, bis: date, extra_tage=()) -> list[Termin]:
    """Fr/Sa im Zeitraum – plus `extra_tage` (Tage mit eigenem Eintrag in Sheet A, z. B. Sonntag)."""
    return [t for t in termine if von <= t.abend <= bis and (ist_fr_sa(t.abend) or t.abend in extra_tage)]


def _gewicht(t: Termin) -> int:
    return (t.beginn is not None) * 2 + bool(t.url) + len(t.titel) / 1000


def zusammenfuehren(termine: list[Termin], schwelle: float = 0.85) -> list[Termin]:
    """Doppelte innerhalb einer Quelle (gleicher Abend, ähnlicher Titel, Zeit gleich oder unbekannt)."""
    ergebnis: list[Termin] = []
    for t in sorted(termine, key=lambda x: (x.quelle, x.abend, -_gewicht(x))):
        dublette = next((e for e in ergebnis
                         if e.quelle == t.quelle and e.abend == t.abend
                         and (e.uhrzeit == t.uhrzeit or not e.uhrzeit or not t.uhrzeit)
                         and aehnlichkeit(e.titel, t.titel) >= schwelle), None)
        if dublette is None:
            ergebnis.append(t)
    return ergebnis


def markiere_artverwandt(termine: list[Termin], stichworte: dict) -> None:
    passt = [_norm(w) for w in stichworte.get("artverwandt", [])]
    aus = [_norm(w) for w in stichworte.get("ausschluss", [])]
    for t in termine:
        text = " " + _norm(" ".join([t.titel, *t.kategorien])) + " "
        if any(f" {w} " in text for w in aus if w):
            t.artverwandt = False
            continue
        if t.artverwandt:  # Dark-Kalender ist per Definition artverwandt
            continue
        t.artverwandt = any(f" {w} " in text for w in passt if w)


def dark_hinweise(termine: list[Termin], schwelle: float = 0.9) -> None:
    """Dark-Kalender-Termine, die eine Location-Spalte auch hat, bekommen „= Modernes“.
    Beide bleiben stehen – Sheet B ist die Szene-Brille."""
    andere = [t for t in termine if t.quelle != "dark_kalender"]
    for d in (t for t in termine if t.quelle == "dark_kalender"):
        treffer = sorted({o.ort for o in andere if o.abend == d.abend and aehnlichkeit(d.titel, o.titel) >= schwelle})
        if treffer:
            d.hinweis = "= " + ", ".join(treffer)


def kollision(t: Termin, calavera: dict[date, str]) -> str:
    if not t.artverwandt:
        return ""
    if t.stadt == "Oldenburg" or not calavera.get(t.abend):
        return MITTEL
    return HOCH


def zeile(t: Termin, calavera: dict[date, str]) -> str:
    teile = [kollision(t, calavera), t.uhrzeit, t.titel]
    if t.hinweis:
        teile.append(f"({t.hinweis})")
    return " ".join(p for p in teile if p)


def zellen(termine: list[Termin], calavera: dict[date, str]) -> dict[date, dict[str, str]]:
    """Abend → Quelle → Zelltext (mehrere Termine untereinander, nach Uhrzeit)."""
    gruppen: dict[date, dict[str, list[Termin]]] = defaultdict(lambda: defaultdict(list))
    for t in termine:
        gruppen[t.abend][t.quelle].append(t)
    aus: dict[date, dict[str, str]] = {}
    for abend in sorted(gruppen):
        aus[abend] = {q: "\n".join(zeile(t, calavera) for t in sorted(liste, key=lambda x: (x.uhrzeit or "99", x.titel)))
                      for q, liste in gruppen[abend].items()}
    return aus
