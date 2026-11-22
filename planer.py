#!/usr/bin/env python3
"""
Calavera Planungskalender – sammelt Fr/Sa-Termine anderer Locations für Sheet A.

Eigenständig wie presse.py: hängt nicht an build.py. Ein Plugin pro Quelle (planer/quellen/),
Einstellungen in planer/quellen.yml, „artverwandt“-Liste in planer/stichworte.yml.

Ohne --schreiben ist jeder Aufruf ein Probelauf: holt alles, schreibt nichts, zeigt eine Tabelle.

  python planer.py                          Probelauf: heute bis 6 Monate voraus
  python planer.py --bis 2027-06            bis einschließlich Juni 2027
  python planer.py --nur modernes,eisen     nur diese Quellen
  python planer.py --ohne-calavera          eigene Abende aus Sheet A nicht lesen
  python planer.py --json termine.json      zusätzlich alle Termine als JSON
  python planer.py --cache 60               Seiten 60 Minuten zwischenspeichern (.cache/planer/)
  python planer.py --fuelle-bis 2027-06     zeigen, welche Monatsblätter in Sheet A fehlen
  python planer.py --schreiben              in Sheet A schreiben (braucht GOOGLE_SA_JSON)
  python planer.py --schreiben --fuelle-bis 2027-06   … und fehlende Monatsblätter vorher anlegen
  --now "JJJJ-MM-TT HH:MM"                  so tun, als wäre jetzt …

Sheet B (Dark-Kalender) wird ausschließlich gelesen (CSV-Export). Geschrieben wird nur mit
--schreiben, nur mit dem Service-Account und nur in Sheet A: eigene Spalten „<Quelle> ⚙“, fehlende
Fr/Sa-Zeilen (nur A/B) und das Blatt „Crawler-Status“. Spalten A–F bestehender Zeilen nie.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from planer import auswertung, calavera, quellen, schreiben, sheets  # noqa: E402
from planer.http import Http  # noqa: E402
from planer.termin import TZ, WOCHENTAG_KURZ, ist_fr_sa  # noqa: E402

KONFIG = ROOT / "planer" / "quellen.yml"
STICHWORTE = ROOT / "planer" / "stichworte.yml"


def info(msg: str = "") -> None:
    print(msg, flush=True)


def zusammenfassung(text: str, art: str = "") -> None:
    """Auf GitHub: Zeile in der Lauf-Übersicht (und als Warnung markiert) – sonst nichts extra"""
    if os.environ.get("GITHUB_ACTIONS"):
        if art in ("warning", "error"):
            print(f"::{art}::{text}", flush=True)
        datei = os.environ.get("GITHUB_STEP_SUMMARY")
        if datei:
            with open(datei, "a", encoding="utf-8") as f:
                f.write(text + "\n\n")


def monatsende(text: str) -> date:
    j, m = (int(x) for x in text.split("-")[:2])
    erster_naechster = date(j + (m == 12), 1 if m == 12 else m + 1, 1)
    return erster_naechster - timedelta(days=1)


def plus_monate(d: date, n: int) -> date:
    m = d.month - 1 + n
    return monatsende(f"{d.year + m // 12}-{m % 12 + 1:02d}")


def fr_sa_abende(von: date, bis: date, extra=()) -> list[date]:
    d, aus = von, []
    while d <= bis:
        if ist_fr_sa(d) or d in extra:
            aus.append(d)
        d += timedelta(days=1)
    return aus


def lauf(http, von: date, bis: date, konfig: dict, stichworte: dict, nur: set[str] | None,
         mit_calavera: bool = True, blatt_leser=None):
    """Alle Quellen holen und auswerten. → (zellen, termine, status, calavera_abende, spalten)

    Relevant sind Fr und Sa – und jeder andere Tag, für den es in Sheet A schon eine Zeile gibt
    (z. B. Honey Café am Sonntag, Silvester am Donnerstag). Solche Zeilen legt der Planer nie selbst an."""
    status: list[dict] = []
    alle = []
    spalten: list[tuple[str, str]] = []

    eigene: dict[date, str] = {}
    sheet_a_status = None
    if mit_calavera:
        warn_a: list[str] = []
        eigene = calavera.lese(http, von, bis, warn=warn_a.append, leser=blatt_leser)
        sheet_a_status = {"quelle": "sheet_a", "spalte": "Calavera (Sheet A, nur gelesen)", "roh": len(eigene),
                          "fr_sa": sum(1 for t in eigene.values() if t), "fehler": "", "warnungen": warn_a, "sekunden": 0}
    extra = {d for d in eigene if not ist_fr_sa(d)}

    for eintrag in konfig.get("quellen", []):
        qid = eintrag["id"]
        if not eintrag.get("aktiv", True) or (nur and qid not in nur):
            continue
        modul = quellen.lade(qid)
        spalten.append((qid, modul.SPALTE))
        warnungen: list[str] = []
        t0 = time.time()
        try:
            gefunden = modul.hole(http, von, bis, {**eintrag, "extra_tage": extra}, warn=warnungen.append)
            fehler = ""
        except Exception as e:  # eine kaputte Quelle hält die anderen nicht auf
            gefunden, fehler = [], f"{type(e).__name__}: {e}"
        roh = len(gefunden)
        gefunden = auswertung.nur_fr_sa(gefunden, von, bis, extra)
        alle += gefunden
        status.append({"quelle": qid, "spalte": modul.SPALTE, "roh": roh, "fr_sa": len(gefunden),
                       "fehler": fehler, "warnungen": warnungen, "sekunden": round(time.time() - t0, 1)})

    alle = auswertung.zusammenfuehren(alle)
    auswertung.markiere_artverwandt(alle, stichworte)
    auswertung.dark_hinweise(alle)
    if sheet_a_status:
        status.append(sheet_a_status)
    return auswertung.zellen(alle, eigene), alle, status, eigene, spalten


def tabelle(zellen, eigene, spalten, von, bis) -> str:
    breite = max([len(s) for _, s in spalten] + [8])
    zeilen = []
    for abend in fr_sa_abende(von, bis, eigene):
        kopf = f"{WOCHENTAG_KURZ[abend.weekday()]} {abend:%d.%m.%Y}"
        if eigene.get(abend):
            kopf += f"   Calavera: {eigene[abend]}"
        zeilen.append(kopf)
        tag = zellen.get(abend, {})
        for qid, spalte in spalten:
            if qid in tag:
                text = tag[qid].split("\n")
                zeilen.append(f"    {spalte:<{breite}}  {text[0]}")
                zeilen += [f"    {'':<{breite}}  {t}" for t in text[1:]]
        if abend.weekday() >= 5:
            zeilen.append("")
    return "\n".join(zeilen)


def statusbericht(status) -> tuple[str, bool]:
    zeilen, problem = [], False
    for s in status:
        if s["fehler"]:
            zeile = f"✗ {s['spalte']}: FEHLER {s['fehler']}"
            problem = True
        elif s["quelle"] == "sheet_a" and s["roh"] == 0:
            zeile = f"? {s['spalte']}: keine eigenen Abende gelesen – Freigabe oder Blattnamen prüfen"
            problem = True
        elif s["quelle"] != "sheet_a" and s["roh"] == 0:
            zeile = f"? {s['spalte']}: keine kommenden Termine gefunden – Seite umgebaut oder Programm leer?"
            problem = True
        else:
            zeile = f"✓ {s['spalte']}: {s['fr_sa']} an relevanten Tagen ({s['roh']} insgesamt, {s['sekunden']} s)"
        zeilen.append(zeile)
        zeilen += [f"    ! {w}" for w in s["warnungen"]]
    return "\n".join(zeilen), problem


def fehlende_monatsblaetter(http, bis: date, heute: date) -> list[str]:
    """Probelauf für --fuelle-bis: welche Monatsblätter gibt es in Sheet A noch nicht?"""
    fehlend = []
    for jahr, monat in calavera.monate(heute.replace(day=1), bis):
        name = sheets.monatsblatt_name(jahr, monat)
        try:
            ok = calavera.lese_monat(sheets.lese_blatt(http, sheets.ziel_a(), name), jahr, monat) is not None
        except Exception:
            ok = False
        if not ok:
            fehlend.append(name)
    return fehlend


def schreib_lauf(args, http, jetzt: datetime) -> int:
    """Echter Lauf: holen, auswerten, in Sheet A schreiben. Sheet B wird nur gelesen."""
    heute = jetzt.date()
    try:
        api = schreiben.SheetsApi.aus_umgebung()
        vorhandene = api.blaetter()
    except Exception as e:
        info(f"FEHLER: kein Zugriff auf Sheet A – {e}")
        zusammenfassung(f"Planungskalender: kein Zugriff auf Sheet A – {e}", "error")
        return 1

    if args.fuelle_bis:
        info("Monatsblätter anlegen:")
        neu = schreiben.fuelle(api, vorhandene, heute, monatsende(args.fuelle_bis), info=info)
        if not neu:
            info("  (alle schon da)")

    monatsblaetter = {schreiben.monat_aus_name(n): n for n in vorhandene if schreiben.monat_aus_name(n)}
    letzter = max(monatsblaetter) if monatsblaetter else (heute.year, heute.month)
    von = heute
    bis = monatsende(args.bis) if args.bis else monatsende(f"{letzter[0]}-{letzter[1]:02d}")
    konfig = yaml.safe_load(KONFIG.read_text(encoding="utf-8")) or {}
    stichworte = yaml.safe_load(STICHWORTE.read_text(encoding="utf-8")) or {}
    nur = {x.strip() for x in args.nur.split(",")} if args.nur else None

    sheet_a = konfig.get("sheet_a") or {}
    erste_spalte = str(sheet_a.get("erste_spalte", "G"))
    schriftgroesse = sheet_a.get("schriftgroesse")      # z. B. 7
    spaltenbreite = sheet_a.get("spaltenbreite")        # Pixel, z. B. 80
    umbruch = bool(sheet_a.get("umbruch", False))
    schreiben.spaltenindex(erste_spalte)  # Tippfehler in quellen.yml früh melden
    cache: dict[str, list[list[str]]] = {}

    def leser(name: str) -> list[list[str]]:
        if name not in vorhandene:
            return []
        if name not in cache:
            cache[name] = api.werte(name)
        return cache[name]

    info(f"Planungskalender – Lauf {von:%d.%m.%Y} bis {bis:%d.%m.%Y}, schreibt in Sheet A\n")
    zellen, termine, status, eigene, spalten = lauf(http, von, bis, konfig, stichworte, nur, blatt_leser=leser)

    # Spalten einer kaputten Quelle nicht leeren: deren Zellen bleiben auf dem letzten Stand
    kaputt = {s["quelle"] for s in status if s["fehler"]}
    schreib_spalten = [(q, n) for q, n in spalten if q not in kaputt]
    for jahr, monat in calavera.monate(von, bis):
        name = sheets.monatsblatt_name(jahr, monat)
        if name not in vorhandene:
            continue
        plan = schreiben.plane_monat(leser(name), jahr, monat, von, bis, schreib_spalten, zellen,
                                     erste_spalte=erste_spalte)
        schreiben.wende_monat_an(api, name, vorhandene[name]["id"], plan, schriftgroesse=schriftgroesse,
                                 spaltenbreite=spaltenbreite, umbruch=umbruch, formatieren=True)
        neu = len(plan.neue_zeilen)
        info(f"  {name}: {len(plan.spalten)} Spalten geschrieben" + (f", {neu} Fr/Sa-Zeilen ergänzt" if neu else ""))

    schreiben.schreibe_status(api, vorhandene, schreiben.status_tabelle(status, f"{jetzt:%d.%m.%Y %H:%M}"))
    bericht, problem = statusbericht(status)
    info("\nQuellen:\n" + bericht + f"\n\n{api.aufrufe} Aufrufe der Sheets API")
    zusammenfassung("**Planungskalender**\n\n```\n" + bericht + "\n```", "warning" if problem else "")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Calavera Planungskalender (Termin-Crawler)",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--bis", help="letzter Monat (JJJJ-MM), Standard: 6 Monate voraus")
    ap.add_argument("--nur", help="nur diese Quellen, durch Komma getrennt")
    ap.add_argument("--ohne-calavera", action="store_true", help="eigene Abende aus Sheet A nicht lesen")
    ap.add_argument("--json", help="alle Termine zusätzlich in diese Datei")
    ap.add_argument("--cache", type=float, default=0, help="Seiten so viele Minuten zwischenspeichern")
    ap.add_argument("--fuelle-bis", help="fehlende Monatsblätter in Sheet A bis JJJJ-MM zeigen (mit --schreiben: anlegen)")
    ap.add_argument("--schreiben", action="store_true", help="in Sheet A schreiben (braucht GOOGLE_SA_JSON)")
    ap.add_argument("--now", help="so tun, als wäre jetzt … (JJJJ-MM-TT HH:MM)")
    args = ap.parse_args()

    jetzt = datetime.strptime(args.now, "%Y-%m-%d %H:%M").replace(tzinfo=TZ) if args.now else datetime.now(TZ)
    heute = jetzt.date()
    http = Http(cache_ordner=ROOT / ".cache" / "planer", cache_minuten=args.cache)

    if args.fuelle_bis and not args.schreiben:
        fehlend = fehlende_monatsblaetter(http, monatsende(args.fuelle_bis), heute)
        if fehlend:
            info("Diese Monatsblätter fehlen in Sheet A und würden mit --schreiben angelegt:")
            info("\n".join(f"  + {n}" for n in fehlend))
        else:
            info("Alle Monatsblätter sind schon da.")
        return 0

    if args.schreiben:
        return schreib_lauf(args, http, jetzt)

    von = heute
    bis = monatsende(args.bis) if args.bis else plus_monate(heute, 6)
    konfig = yaml.safe_load(KONFIG.read_text(encoding="utf-8")) or {}
    stichworte = yaml.safe_load(STICHWORTE.read_text(encoding="utf-8")) or {}
    nur = {x.strip() for x in args.nur.split(",")} if args.nur else None

    info(f"Planungskalender – Probelauf {von:%d.%m.%Y} bis {bis:%d.%m.%Y} (nur Fr/Sa, nichts wird geschrieben)\n")
    zellen, termine, status, eigene, spalten = lauf(http, von, bis, konfig, stichworte, nur,
                                                    mit_calavera=not args.ohne_calavera)
    info(tabelle(zellen, eigene, spalten, von, bis))
    bericht, problem = statusbericht(status)
    info("Quellen:\n" + bericht)
    info(f"\n{auswertung.HOCH} artverwandt + Calavera-Abend in Bremen · {auswertung.MITTEL} artverwandt, "
         f"Oldenburg oder kein eigener Abend · {http.abrufe} Abrufe")
    zusammenfassung("**Planungskalender (Probelauf)**\n\n```\n" + bericht + "\n```",
                    "warning" if problem else "")

    if args.json:
        Path(args.json).write_text(json.dumps([{
            "quelle": t.quelle, "abend": t.abend.isoformat(), "uhrzeit": t.uhrzeit, "titel": t.titel,
            "ort": t.ort, "stadt": t.stadt, "url": t.url, "artverwandt": t.artverwandt, "hinweis": t.hinweis,
            "kollision": auswertung.kollision(t, eigene)} for t in sorted(termine, key=lambda x: (x.abend, x.quelle))],
            ensure_ascii=False, indent=1), encoding="utf-8")
        info(f"JSON: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
