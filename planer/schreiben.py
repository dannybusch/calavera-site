"""Etappe 2: Ergebnisse in Sheet A schreiben (nur Sheet A, nur mit --schreiben).

Regeln (0021):
- Jede Quelle hat eine eigene Spalte mit Kopf „<SPALTE> ⚙“. Fehlt sie, wird sie hinten angehängt.
- Fehlende Fr/Sa-Zeilen werden in den Block ihrer Woche eingefügt (nur A Wochentag, B „TT.MM.“).
- Spalten A–F bestehender Zeilen werden nie geschrieben, Zeilen nie gelöscht oder verschoben.
- Vergangene Abende (vor `von`) behalten ihren letzten Stand.

Die Planung (`plane_monat`, `plane_neues_blatt`) ist reine Logik ohne Netz und wird getestet;
`SheetsApi` setzt sie mit wenigen Aufrufen der Sheets API um.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from urllib.parse import quote

from . import sheets
from .termin import WOCHENTAG_KURZ, ist_fr_sa

MARKE = " ⚙"
EIGENE_SPALTEN = 6            # A–F gehören dem Team
STATUS_BLATT = "Crawler-Status"
_DATUM = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})\.?\s*$")


def spaltenbuchstabe(index0: int) -> str:
    s, n = "", index0 + 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def a1(blatt: str, bereich: str) -> str:
    return "'" + blatt.replace("'", "''") + "'!" + bereich


def zeilen_datum(zeile: list[str], jahr: int, monat: int) -> date | None:
    m = _DATUM.match(zeile[1] if len(zeile) > 1 else "")
    if not m or int(m.group(2)) != monat:
        return None
    try:
        return date(jahr, monat, int(m.group(1)))
    except ValueError:
        return None


def fr_sa_im_monat(jahr: int, monat: int) -> list[date]:
    d, aus = date(jahr, monat, 1), []
    while d.month == monat:
        if ist_fr_sa(d):
            aus.append(d)
        d += timedelta(days=1)
    return aus


def neue_zeile(d: date) -> list[str]:
    return [WOCHENTAG_KURZ[d.weekday()], f"{d:%d.%m.}"]


@dataclass
class MonatsPlan:
    einfuegen: list[tuple[int, list[str]]] = field(default_factory=list)  # Einfügestellen in API-Reihenfolge
    neue_zeilen: list[tuple[int, list[str]]] = field(default_factory=list)  # Endposition → [A, B]
    kopf: dict[int, str] = field(default_factory=dict)                  # neue Spaltenköpfe
    spalten: dict[int, list[str]] = field(default_factory=dict)         # Spalte → Werte ab Zeile 2
    zeilen_nachher: int = 0

    @property
    def leer(self) -> bool:
        return not (self.einfuegen or self.kopf or self.spalten)


def _einfuege_stelle(modell: list[list[str]], d: date, jahr: int, monat: int) -> tuple[int, list[list[str]]]:
    """Wo kommt eine fehlende Fr/Sa-Zeile hin? → (Index, einzufügende Zeilen)."""
    daten = [(i, zeilen_datum(z, jahr, monat)) for i, z in enumerate(modell)]
    daten = [(i, x) for i, x in daten if x]
    woche = d.isocalendar()[:2]
    gleiche_woche = [(i, x) for i, x in daten if x.isocalendar()[:2] == woche]
    if gleiche_woche:
        spaeter = [i for i, x in gleiche_woche if x > d]
        return (spaeter[0] if spaeter else gleiche_woche[-1][0] + 1), [neue_zeile(d)]
    spaeter = [i for i, x in daten if x > d]
    if spaeter:
        return spaeter[0], [neue_zeile(d), []]          # neuer Wochenblock vor dem nächsten, Leerzeile danach
    letzte = max((i for i, z in enumerate(modell) if any(c.strip() for c in z)), default=0)
    if letzte == 0:
        return 1, [[], neue_zeile(d)]                   # leeres Blatt: Kopf, Leerzeile, dann Termine
    return letzte + 1, [[], neue_zeile(d)]              # ans Ende, mit Leerzeile davor


def spaltenindex(buchstaben: str) -> int:
    """„I“ → 8 (0-basiert)"""
    n = 0
    for c in buchstaben.strip().upper():
        if not "A" <= c <= "Z":
            raise ValueError(f"keine Spalte: {buchstaben!r}")
        n = n * 26 + ord(c) - 64
    return n - 1


def plane_monat(zeilen: list[list[str]], jahr: int, monat: int, von: date, bis: date,
                spalten: list[tuple[str, str]], zellen: dict[date, dict[str, str]],
                erste_spalte: str = "G") -> MonatsPlan:
    """`erste_spalte`: ab hier legt der Planer neue Quellenspalten an (davor bleibt frei)."""
    plan = MonatsPlan()
    modell = [list(z) for z in zeilen] or [[]]

    # 1. fehlende Fr/Sa im Zeitraum ergänzen (im Modell, Reihenfolge = Reihenfolge der API-Aufrufe)
    vorhanden = {zeilen_datum(z, jahr, monat) for z in modell}
    eingefuegt: set[int] = set()
    for d in fr_sa_im_monat(jahr, monat):
        if d in vorhanden or not (von <= d <= bis):
            continue
        stelle, neu = _einfuege_stelle(modell, d, jahr, monat)
        for k, z in enumerate(neu):
            zeile = list(z)
            modell.insert(stelle + k, zeile)
            eingefuegt.add(id(zeile))
            plan.einfuegen.append((stelle + k, zeile))
        vorhanden.add(d)
    # spätere Einfügungen verschieben frühere – A/B erst an der Endposition schreiben
    plan.neue_zeilen = [(i, z) for i, z in enumerate(modell) if id(z) in eingefuegt and z]

    # 2. Spalten der Quellen finden oder anlegen
    kopf = modell[0]
    belegt = max([i + 1 for i, c in enumerate(kopf) if c.strip()] + [EIGENE_SPALTEN, spaltenindex(erste_spalte)])
    index: dict[str, int] = {}
    for qid, name in spalten:
        titel = name + MARKE
        if titel in kopf:
            index[qid] = kopf.index(titel)
        else:
            index[qid] = belegt
            plan.kopf[belegt] = titel
            belegt += 1

    # 3. Werte je Spalte (vergangene Abende und Nicht-Fr/Sa behalten ihren Stand)
    for qid, j in index.items():
        werte = []
        for z in modell[1:]:
            alt = z[j] if j < len(z) else ""
            d = zeilen_datum(z, jahr, monat)
            if d and von <= d <= bis and ist_fr_sa(d):
                werte.append(zellen.get(d, {}).get(qid, ""))
            else:
                werte.append(alt)
        if [z[j] if j < len(z) else "" for z in modell[1:]] != werte or plan.einfuegen or j in plan.kopf:
            plan.spalten[j] = werte
    plan.zeilen_nachher = len(modell)
    return plan


def plane_neues_blatt(jahr: int, monat: int, kopfzeile: list[str]) -> list[list[str]]:
    """Inhalt eines neuen Monatsblatts: Kopf, Leerzeile, je Woche Fr/Sa, Leerzeile dazwischen."""
    zeilen = [list(kopfzeile), []]
    letzte_woche = None
    for d in fr_sa_im_monat(jahr, monat):
        woche = d.isocalendar()[:2]
        if letzte_woche is not None and woche != letzte_woche:
            zeilen.append([])
        zeilen.append(neue_zeile(d))
        letzte_woche = woche
    return zeilen


def status_tabelle(status: list[dict], zeitpunkt: str) -> list[list[str]]:
    zeilen = [["Quelle", "Zustand", "Fr/Sa", "insgesamt", "Meldungen", "Letzter Lauf"]]
    for s in status:
        zustand = "Fehler" if s["fehler"] else ("verdächtig" if s["roh"] == 0 else "ok")
        meldung = s["fehler"] or "; ".join(s["warnungen"])
        zeilen.append([s["spalte"], zustand, str(s["fr_sa"]), str(s["roh"]), meldung[:500], zeitpunkt])
    zeilen.append([])
    zeilen.append(["Dieses Blatt schreibt der Planer bei jedem Lauf neu – nicht von Hand bearbeiten."])
    return zeilen


# --- Sheets API -------------------------------------------------------------------------------

class SheetsApi:
    """Dünne Hülle um die Sheets API v4, fest auf Sheet A. Jeder schreibende Aufruf prüft das Ziel."""

    BASIS = "https://sheets.googleapis.com/v4/spreadsheets/"

    def __init__(self, sitzung, sheet_id: str | None = None) -> None:
        sheet_id = sheet_id or sheets.ziel_a()
        sheets.pruefe_schreibziel(sheet_id)
        self.s = sitzung
        self.id = sheet_id
        self.aufrufe = 0

    @classmethod
    def aus_umgebung(cls) -> "SheetsApi":
        roh = os.environ.get("GOOGLE_SA_JSON", "")
        if not roh.strip():
            raise RuntimeError("GOOGLE_SA_JSON fehlt (Inhalt des Service-Account-Schlüssels als Umgebungsvariable)")
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account
        info = json.loads(roh)
        cred = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        return cls(AuthorizedSession(cred))

    def _antwort(self, r):
        self.aufrufe += 1
        if r.status_code >= 400:
            raise RuntimeError(f"Sheets API {r.status_code}: {r.text[:300]}")
        return r.json() if r.text else {}

    def _get(self, pfad: str, **params):
        return self._antwort(self.s.get(self.BASIS + self.id + pfad, params=params, timeout=30))

    def _post(self, pfad: str, daten: dict):
        sheets.pruefe_schreibziel(self.id)
        return self._antwort(self.s.post(self.BASIS + self.id + pfad, json=daten, timeout=60))

    # Lesen
    def blaetter(self) -> dict[str, dict]:
        """Titel → {"id": sheetId, "index": Position}"""
        meta = self._get("", fields="sheets.properties(sheetId,title,index)")
        return {b["properties"]["title"]: {"id": b["properties"]["sheetId"], "index": b["properties"].get("index", 0)}
                for b in meta.get("sheets", [])}

    def werte(self, blatt: str) -> list[list[str]]:
        antwort = self._get("/values/" + quote(a1(blatt, "A1:ZZ"), safe=""), valueRenderOption="FORMATTED_VALUE")
        return antwort.get("values", [])

    # Schreiben
    def batch(self, anfragen: list[dict]) -> None:
        if anfragen:
            self._post(":batchUpdate", {"requests": anfragen})

    def schreibe(self, daten: list[tuple[str, list[list[str]]]]) -> None:
        if daten:
            self._post("/values:batchUpdate", {"valueInputOption": "RAW",
                                               "data": [{"range": r, "values": v} for r, v in daten]})

    def leere(self, bereiche: list[str]) -> None:
        if bereiche:
            self._post("/values:batchClear", {"ranges": bereiche})


def wende_monat_an(api: SheetsApi, blatt: str, blatt_id: int, plan: MonatsPlan) -> None:
    if plan.leer:
        return
    api.batch([{"insertDimension": {"range": {"sheetId": blatt_id, "dimension": "ROWS",
                                              "startIndex": i, "endIndex": i + 1},
                                    "inheritFromBefore": i > 0}} for i, _ in plan.einfuegen])
    daten: list[tuple[str, list[list[str]]]] = []
    for i, z in plan.neue_zeilen:
        daten.append((a1(blatt, f"A{i + 1}:B{i + 1}"), [z[:2]]))
    for j, titel in plan.kopf.items():
        daten.append((a1(blatt, f"{spaltenbuchstabe(j)}1"), [[titel]]))
    for j, werte in plan.spalten.items():
        b = spaltenbuchstabe(j)
        daten.append((a1(blatt, f"{b}2:{b}{len(werte) + 1}"), [[w] for w in werte]))
    api.schreibe(daten)


def lege_monat_an(api: SheetsApi, vorlage: str, vorlage_id: int, name: str, inhalt: list[list[str]],
                  position: int) -> None:
    """Vorlage duplizieren (Format, Breiten, Kopf), Inhalt ab Zeile 2 leeren, Fr/Sa-Gerüst schreiben."""
    api.batch([{"duplicateSheet": {"sourceSheetId": vorlage_id, "insertSheetIndex": position,
                                   "newSheetName": name}}])
    api.leere([a1(name, "A2:ZZ")])
    api.schreibe([(a1(name, f"A3:B{len(inhalt)}"), [(z + ["", ""])[:2] for z in inhalt[2:]])])


def schreibe_status(api: SheetsApi, vorhandene: dict[str, dict], tabelle: list[list[str]]) -> None:
    if STATUS_BLATT not in vorhandene:
        api.batch([{"addSheet": {"properties": {"title": STATUS_BLATT}}}])
    api.leere([a1(STATUS_BLATT, "A1:Z")])
    api.schreibe([(a1(STATUS_BLATT, f"A1:F{len(tabelle)}"), [(z + [""] * 6)[:6] for z in tabelle])])


def monat_aus_name(name: str) -> tuple[int, int] | None:
    """„Dezember 2026“ → (2026, 12)"""
    m = re.fullmatch(r"\s*(\S+)\s+(\d{4})\s*", name)
    if not m or m.group(1) not in sheets.MONATE:
        return None
    return int(m.group(2)), sheets.MONATE.index(m.group(1)) + 1


def fehlende_monate(vorhandene: dict[str, dict], von: date, bis: date) -> list[tuple[int, int]]:
    from .calavera import monate
    da = {monat_aus_name(n) for n in vorhandene}
    return [jm for jm in monate(von.replace(day=1), bis) if jm not in da]


def fuelle(api: SheetsApi, vorhandene: dict[str, dict], von: date, bis: date, info=print) -> list[str]:
    """Fehlende Monatsblätter bis `bis` anlegen, jeweils hinter dem Vormonat. → angelegte Namen"""
    angelegt = []
    for jahr, monat in fehlende_monate(vorhandene, von, bis):
        monatsblaetter = sorted(((monat_aus_name(n), n) for n in vorhandene if monat_aus_name(n)), key=lambda x: x[0])
        frueher = [x for x in monatsblaetter if x[0] < (jahr, monat)]
        if not frueher:
            info(f"  ! {sheets.monatsblatt_name(jahr, monat)}: kein früheres Monatsblatt als Vorlage – übersprungen")
            continue
        vorlage = frueher[-1][1]
        name = sheets.monatsblatt_name(jahr, monat)
        inhalt = plane_neues_blatt(jahr, monat, [])
        lege_monat_an(api, vorlage, vorhandene[vorlage]["id"], name, inhalt, vorhandene[vorlage]["index"] + 1)
        vorhandene.update(api.blaetter())
        angelegt.append(name)
        info(f"  + {name} (Vorlage: {vorlage})")
    return angelegt
