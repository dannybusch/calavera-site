#!/usr/bin/env python3
"""
Calavera Bremen – dist/ per SFTP auf den Server spiegeln (ersetzt lftp, braucht nur Python)

  - lädt nur hoch, was neu ist oder dessen Inhalt sich geändert hat: Prüfsummen der hochgeladenen Dateien
    liegen auf dem Server in .calavera-pruefsummen.json (fehlt die Datei, wird einmal alles hochgeladen),
  - lädt in Stufen hoch, damit nie eine Seite online ist, die auf noch Fehlendes verweist:
    1. Bilder & Dateien, 2. Veranstaltungsseiten, 3. Übersichtsseiten (zuletzt /programm/ und Startseite),
    4. sitemap.xml, llms.txt, Kalender & Co. – klappt in einer Stufe etwas nicht, bleiben die späteren aus,
  - ersetzt jede Datei in einem Schritt (Zwischenname + Umbenennen): nie eine halb hochgeladene Seite online,
  - sichert den Stand zwischendurch (nach jeder Stufe, sonst jede Minute): nach einem Verbindungsabbruch
    macht der nächste Versuch dort weiter, statt alles noch einmal hochzuladen,
  - löscht auf dem Server, was es in dist/ nicht mehr gibt – erst nach dem Hochladen, Seiten vor ihren Bildern,
  - lässt .htaccess (überall), .well-known/ und _behalten/ auf dem Server unangetastet,
  - prüft den Server-Schlüssel gegen ~/.ssh/known_hosts (wie lftp mit StrictHostKeyChecking=yes),
  - setzt in sitemap.xml <lastmod> je Seite auf den Zeitpunkt, an dem sich ihr Inhalt zuletzt geändert hat
    (gemerkt ebenfalls in .calavera-pruefsummen.json), und schreibt auf Wunsch die Liste der geänderten
    Seiten in eine Datei – für indexnow.py (Bing & Co. benachrichtigen).

  python hochladen.py dist/ /ziel/ordner            hochladen
  python hochladen.py dist/ /ziel/ordner --probe    nur anzeigen
  python hochladen.py dist/ /ziel/ordner --alles    alles neu hochladen (Prüfsummen ignorieren)
  python hochladen.py dist/ /ziel/ordner --geaendert-liste geaendert.txt
                                                    zusätzlich geänderte/entfernte Seiten-URLs in die Datei

Zugang aus der Umgebung: SFTP_HOST, SFTP_PORT (Standard 22), SFTP_USER, SFTP_PASSWORD
Braucht: pip install paramiko
"""
from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import os
import posixpath
import re
import stat
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

AUSNAHME_ORDNER = (".well-known", "_behalten")
PRUEFSUMMEN = ".calavera-pruefsummen.json"   # liegt im Zielordner; wird nie gelöscht oder gespiegelt
AUSNAHME_DATEIEN = (".htaccess", PRUEFSUMMEN)


def ausgenommen(rel: str) -> bool:
    teile = rel.split("/")
    return teile[-1] in AUSNAHME_DATEIEN or any(t in AUSNAHME_ORDNER for t in teile)


def lokal_auflisten(quelle: Path) -> tuple[dict, set]:
    dateien, ordner = {}, set()
    for p in sorted(quelle.rglob("*")):
        rel = p.relative_to(quelle).as_posix()
        if ausgenommen(rel):
            continue
        if p.is_dir():
            ordner.add(rel)
        elif p.is_file():
            dateien[rel] = (p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest())
    return dateien, ordner


def entfernt_auflisten(sftp, ziel: str) -> tuple[dict, set]:
    dateien, ordner = {}, set()
    stapel = [""]
    while stapel:
        rel = stapel.pop()
        try:
            eintraege = sftp.listdir_attr(posixpath.join(ziel, rel) if rel else ziel)
        except FileNotFoundError:
            continue
        for e in eintraege:
            r = f"{rel}/{e.filename}" if rel else e.filename
            if ausgenommen(r):
                continue
            if stat.S_ISDIR(e.st_mode):
                ordner.add(r)
                stapel.append(r)
            else:
                dateien[r] = (e.st_size, int(e.st_mtime or 0))
    return dateien, ordner


def verbinden():
    import paramiko
    host, user, pw = os.environ.get("SFTP_HOST", ""), os.environ.get("SFTP_USER", ""), os.environ.get("SFTP_PASSWORD", "")
    port = int(os.environ.get("SFTP_PORT") or 22)
    if not (host and user and pw):
        sys.exit("FEHLER: SFTP_HOST, SFTP_USER und SFTP_PASSWORD müssen gesetzt sein")
    client = paramiko.SSHClient()
    known = Path(os.environ.get("SFTP_KNOWN_HOSTS_FILE") or Path.home() / ".ssh" / "known_hosts")
    if known.is_file():
        client.load_host_keys(str(known))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())   # unbekannter Schlüssel → Abbruch
    client.connect(host, port=port, username=user, password=pw, look_for_keys=False, allow_agent=False,
                   timeout=30, banner_timeout=30, auth_timeout=30)
    client.get_transport().set_keepalive(20)
    return client, client.open_sftp()


def pruefsummen_laden(sftp, ziel: str) -> tuple[dict, dict]:
    """→ (Prüfsummen der Dateien, Seiten-Stand für sitemap/IndexNow: {url: {"inhalt": …, "lastmod": …}})"""
    try:
        with sftp.open(posixpath.join(ziel, PRUEFSUMMEN), "r") as f:
            daten = json.loads(f.read().decode("utf-8"))
        if not isinstance(daten, dict):
            return {}, {}
        return daten.get("dateien", {}) or {}, daten.get("seiten", {}) or {}
    except (FileNotFoundError, ValueError, OSError):
        return {}, {}


def pruefsummen_schreiben(sftp, ziel: str, summen: dict, seiten: dict | None = None) -> None:
    """erst unter anderem Namen, dann umbenennen – nie eine halbe Datei"""
    inhalt = json.dumps({"hinweis": "von hochladen.py verwaltet – nicht löschen (sonst wird einmal alles neu hochgeladen)",
                         "stand": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "dateien": summen, "seiten": seiten or {}},
                        ensure_ascii=False, indent=0, sort_keys=True).encode("utf-8")
    ziel_datei, tmp = posixpath.join(ziel, PRUEFSUMMEN), posixpath.join(ziel, PRUEFSUMMEN + ".neu")
    sftp.putfo(io.BytesIO(inhalt), tmp)
    try:
        sftp.posix_rename(tmp, ziel_datei)
    except OSError:   # Server ohne posix-rename: altes löschen, dann umbenennen
        try:
            sftp.remove(ziel_datei)
        except FileNotFoundError:
            pass
        sftp.rename(tmp, ziel_datei)


# ------------------------------------------------------------------ sitemap.xml: lastmod + geänderte Seiten
# Grundlage ist der *Inhalt* jeder Seite aus der Sitemap. Versionsanhänge wie ?v=1a2b3c4d (ändern sich bei jeder
# CSS-/JS-Änderung auf allen Seiten) und als <!-- lastmod:ohne --> markierte Bereiche zählen nicht – sonst hätte
# nach jeder Stiländerung oder jedem vergangenen Termin fast jede Seite ein neues Datum.
VERSIONS_ANHANG = re.compile(rb"\?v=[0-9a-f]{6,40}")
# Bereiche, die sich ändern, ohne dass die Seite selbst neu ist (z. B. "Weitere Termine" auf Veranstaltungsseiten)
OHNE_BEREICH = re.compile(rb"<!-- lastmod:ohne -->.*?<!-- /lastmod:ohne -->", re.S)


def inhalt_pruefsumme(daten: bytes) -> str:
    return hashlib.sha256(OHNE_BEREICH.sub(b"", VERSIONS_ANHANG.sub(b"", daten))).hexdigest()


def seite_datei(quelle: Path, url: str, basis: str) -> Path | None:
    pfad = url[len(basis):] if url.startswith(basis) else ""
    pfad = pfad.lstrip("/")
    p = quelle / pfad / "index.html" if (not pfad or pfad.endswith("/")) else quelle / pfad
    return p if p.is_file() else None


def sitemap_aktualisieren(quelle: Path, alt: dict, jetzt: str) -> tuple[dict, list[str]]:
    """sitemap.xml in quelle um <lastmod> ergänzen. → (neuer Seiten-Stand, geänderte/neue/entfernte URLs)"""
    sm = quelle / "sitemap.xml"
    if not sm.is_file():
        return alt, []
    text = sm.read_text(encoding="utf-8")
    urls = [html.unescape(u) for u in re.findall(r"<loc>(.*?)</loc>", text)]
    if not urls:
        return alt, []
    m = re.match(r"(https?://[^/]+)", urls[0])
    basis = m.group(1) if m else ""
    neu, geaendert = {}, []
    for url in urls:
        datei = seite_datei(quelle, url, basis)
        inhalt = inhalt_pruefsumme(datei.read_bytes()) if datei else ""
        vorher = alt.get(url) or {}
        if inhalt and vorher.get("inhalt") == inhalt and vorher.get("lastmod"):
            neu[url] = vorher
        else:
            neu[url] = {"inhalt": inhalt, "lastmod": jetzt}
            geaendert.append(url)
    entfernt = sorted(set(alt) - set(neu))
    zeilen = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    zeilen += [f"  <url><loc>{html.escape(u)}</loc><lastmod>{neu[u]['lastmod']}</lastmod></url>" for u in urls]
    zeilen.append("</urlset>")
    sm.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return neu, geaendert + entfernt


# ------------------------------------------------------------------ Reihenfolge
# Hochgeladen wird in Stufen, damit online nie eine Seite steht, die auf etwas noch Fehlendes verweist:
#   1. Bilder & Dateien      – static/, media/, termin.ics der Veranstaltungen … (alles außer HTML)
#   2. Veranstaltungsseiten  – /programm/<slug>/ und /intern/<slug>/
#   3. Übersichtsseiten      – Landingpages, Archiv, feste Seiten …, zum Schluss /programm/ und die Startseite
#   4. Verzeichnisse         – sitemap.xml, llms.txt, robots.txt, kalender.ics & Abos, build.json
# Gelöscht wird erst danach und in umgekehrter Folge (erst Seiten, dann ihre Bilder).
STUFEN = ("Bilder & Dateien", "Veranstaltungsseiten", "Übersichtsseiten", "Verzeichnisse")
EVENT_ORDNER = ("programm", "intern")             # /<ordner>/<slug>/index.html = eine Veranstaltung
KEINE_VERANSTALTUNG = ("archiv",)                 # /programm/archiv/ ist eine Übersicht
GANZ_ZULETZT = ("programm/index.html", "index.html")   # innerhalb der Übersichtsseiten zuletzt, in dieser Folge
NEU_ENDUNG = ".calavera-neu"                      # Zwischenname beim Hochladen (danach umbenannt)
ZWISCHENSTAND_SEK = 60                            # spätestens so oft die Prüfsummen auf dem Server sichern


def stufe(rel: str) -> int:
    teile = rel.split("/")
    ist_html = rel.endswith(".html")
    veranstaltung = len(teile) >= 3 and teile[0] in EVENT_ORDNER and teile[1] not in KEINE_VERANSTALTUNG
    if len(teile) == 1 and not ist_html:
        return 3                                  # sitemap.xml, llms.txt, robots.txt, kalender.ics, build.json …
    if not ist_html:
        # Abo-Kalender der Landingpages (/dark/calavera-dark.ics) verweisen auf Veranstaltungsseiten → zuletzt;
        # termin.ics einer Veranstaltung wird von ihrer Seite verlinkt → vorher
        return 3 if rel.endswith(".ics") and not veranstaltung else 0
    return 1 if veranstaltung else 2


def reihenfolge(rel: str) -> tuple:
    zuletzt = GANZ_ZULETZT.index(rel) + 1 if rel in GANZ_ZULETZT else 0
    return stufe(rel), zuletzt, rel


class StufenFehler(Exception):
    """Einzelne Dateien ließen sich nicht hochladen – spätere Stufen wurden bewusst ausgelassen."""


def verbindung_steht(sftp) -> bool:
    try:
        return bool(sftp.get_channel().get_transport().is_active())
    except AttributeError:   # (Test-Ersatz ohne Kanal)
        return True


def spiegeln(quelle: Path, ziel: str, probe: bool, alles: bool = False, liste: Path | None = None) -> dict:
    client, sftp = verbinden()
    try:
        try:
            sftp.stat(ziel)
        except FileNotFoundError:
            sys.exit(f"FEHLER: Zielordner {ziel} gibt es auf dem Server nicht")
        ent_dateien, ent_ordner = entfernt_auflisten(sftp, ziel)
        summen, seiten_alt = pruefsummen_laden(sftp, ziel)
        if alles:
            summen = {}
        # erst die Sitemap mit lastmod schreiben, dann Prüfsummen bilden – sonst würde die alte Fassung hochgeladen
        jetzt = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        seiten, geaendert = sitemap_aktualisieren(quelle, seiten_alt, jetzt)
        lok_dateien, lok_ordner = lokal_auflisten(quelle)
        if geaendert:
            print(f"  Seiten mit neuem Inhalt (lastmod {jetzt[:10]}): {len(geaendert)}")
        if liste is not None:
            liste.write_text("".join(u + "\n" for u in geaendert), encoding="utf-8")
        if not summen and not alles and ent_dateien:
            print(f"  (noch keine {PRUEFSUMMEN} auf dem Server – dieses Mal wird alles hochgeladen)")
        zahl = {"hoch": 0, "gleich": 0, "geloescht": 0, "ordner": 0, "warnungen": 0}

        # Was auf dem Server steht und wie es zuletzt hochgeladen wurde. Wird beim Hochladen fortgeschrieben und
        # zwischendurch gesichert: Reißt die Verbindung ab, macht der nächste Versuch dort weiter.
        stand = {rel: s for rel, s in summen.items() if rel in ent_dateien}
        zu_tun = []
        for rel, (groesse, summe) in lok_dateien.items():
            alt = ent_dateien.get(rel)
            # gleich = auf dem Server vorhanden, gleiche Größe, und zuletzt mit genau diesem Inhalt hochgeladen
            if alt and alt[0] == groesse and summen.get(rel) == summe:
                zahl["gleich"] += 1
            else:
                zu_tun.append(rel)
        zu_tun.sort(key=reihenfolge)
        weg = sorted(set(ent_dateien) - set(lok_dateien), key=lambda r: (-stufe(r), r))

        if not zu_tun and not weg:
            print("  Alles aktuell – nichts hochzuladen.")

        for rel in sorted(lok_ordner - ent_ordner, key=lambda r: r.count("/")):
            print(f"  Ordner anlegen: {rel}")
            zahl["ordner"] += 1
            if not probe:
                sftp.mkdir(posixpath.join(ziel, rel))

        gesichert = [time.monotonic(), dict(stand)]

        def sichern(immer: bool = False) -> None:
            if probe or stand == gesichert[1]:
                return
            if immer or time.monotonic() - gesichert[0] >= ZWISCHENSTAND_SEK:
                pruefsummen_schreiben(sftp, ziel, stand, seiten_alt)   # Seiten-Stand erst, wenn alles oben ist
                gesichert[:] = [time.monotonic(), dict(stand)]

        atomar = [True]   # Server kann posix-rename (OpenSSH) – sonst direkt überschreiben

        def hochladen(rel: str) -> None:
            lokal, entfernt = str(quelle / rel), posixpath.join(ziel, rel)
            stand.pop(rel, None)   # ab jetzt ist offen, was auf dem Server steht
            if atomar[0]:
                # erst unter Zwischennamen, dann in einem Schritt ersetzen: nie eine halbe Seite online
                tmp = entfernt + NEU_ENDUNG
                sftp.put(lokal, tmp, confirm=True)
                try:
                    sftp.posix_rename(tmp, entfernt)
                    return
                except OSError:
                    if not verbindung_steht(sftp):
                        raise
                    atomar[0] = False
                    print("    (Server kann nicht in einem Schritt ersetzen – lade ab jetzt direkt hoch)")
                    try:
                        sftp.remove(tmp)
                    except OSError:
                        pass
            sftp.put(lokal, entfernt, confirm=True)

        for nr, name in enumerate(STUFEN):
            dateien = [r for r in zu_tun if stufe(r) == nr]
            if not dateien:
                continue
            print(f"  ── {nr + 1}/{len(STUFEN)} {name}: {len(dateien)} Datei(en)")
            fehler = []
            for rel in dateien:
                print(f"  {'Aktualisieren' if rel in ent_dateien else 'Neu'}: {rel}")
                zahl["hoch"] += 1
                if probe:
                    continue
                try:
                    hochladen(rel)
                except OSError as e:
                    if not verbindung_steht(sftp):
                        raise   # Verbindung weg → neuer Versuch ab dem letzten Zwischenstand
                    print(f"    FEHLER beim Hochladen: {e.__class__.__name__}: {e}")
                    fehler.append(rel)
                    zahl["hoch"] -= 1
                    continue
                stand[rel] = lok_dateien[rel][1]
                sichern()
            if fehler:
                sichern(immer=True)
                rest = len([r for r in zu_tun if stufe(r) > nr])
                raise StufenFehler(
                    f"{len(fehler)} Datei(en) in Stufe „{name}“ nicht hochgeladen ({', '.join(fehler[:5])}"
                    f"{' …' if len(fehler) > 5 else ''}). Abgebrochen, damit nichts auf Fehlendes verweist: "
                    f"{rest} Datei(en) späterer Stufen und alle Löschungen ausgelassen. Erledigtes ist gemerkt.")
            sichern(immer=True)   # nach jeder Stufe: Grundlage für die nächste steht sicher auf dem Server

        for rel in weg:
            print(f"  Löschen: {rel}")
            zahl["geloescht"] += 1
            if probe:
                continue
            try:
                sftp.remove(posixpath.join(ziel, rel))
            except FileNotFoundError:
                pass
            except OSError as e:
                if not verbindung_steht(sftp):
                    raise
                print(f"    WARNUNG: nicht gelöscht ({e.__class__.__name__}: {e})")
                zahl["geloescht"] -= 1
                zahl["warnungen"] += 1
                continue
            stand.pop(rel, None)
        for rel in sorted(ent_ordner - lok_ordner, key=lambda r: -r.count("/")):
            print(f"  Ordner löschen: {rel}")
            if not probe:
                try:
                    sftp.rmdir(posixpath.join(ziel, rel))
                except OSError:
                    print("    (nicht leer – enthält ausgenommene Dateien, bleibt stehen)")
        zahl["seiten"] = len(geaendert)
        if not probe and (stand != summen or seiten != seiten_alt):
            pruefsummen_schreiben(sftp, ziel, stand, seiten)
        return zahl
    finally:
        sftp.close()
        client.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="dist/ per SFTP spiegeln (wie lftp mirror --reverse --delete)")
    ap.add_argument("quelle")
    ap.add_argument("ziel")
    ap.add_argument("--probe", action="store_true", help="nur anzeigen, nichts ändern")
    ap.add_argument("--alles", action="store_true", help="alles neu hochladen (Prüfsummen ignorieren)")
    ap.add_argument("--geaendert-liste", metavar="DATEI",
                    help="URLs der Seiten mit neuem/geändertem Inhalt (und entfernte) in diese Datei schreiben – für indexnow.py")
    args = ap.parse_args()
    quelle = Path(args.quelle)
    if not quelle.is_dir():
        sys.exit(f"FEHLER: {quelle} ist kein Ordner")
    ziel = args.ziel.strip()
    if ziel in ("~", "~/") or ziel.startswith("~/"):   # wie bei lftp: "~" = Startordner des Zugangs
        ziel = ziel[2:] or "."
    ziel = ziel.rstrip("/") or "/"
    alles = args.alles
    for versuch in range(1, 4):   # Spiegeln ist wiederholbar – nach Verbindungsabbruch macht es dort weiter,
        try:                      # wo der letzte gesicherte Zwischenstand war
            zahl = spiegeln(quelle, ziel, args.probe, alles,
                            Path(args.geaendert_liste) if args.geaendert_liste else None)
            print(("Probelauf: " if args.probe else "Fertig: ")
                  + f"{zahl['hoch']} hochgeladen, {zahl['geloescht']} gelöscht, {zahl['ordner']} Ordner neu, {zahl['gleich']} unverändert"
                  + f", {zahl['seiten']} Seite(n) mit neuem Inhalt")
            if zahl["warnungen"]:
                hinweis = f"{zahl['warnungen']} Datei(en) auf dem Server ließen sich nicht löschen (siehe oben)"
                print(f"::warning::{hinweis}" if os.environ.get("GITHUB_ACTIONS") else f"WARNUNG: {hinweis}")
            return 0
        except StufenFehler as e:
            sys.exit(f"FEHLER: {e}")
        except Exception as e:   # noqa: BLE001
            import paramiko
            if isinstance(e, paramiko.AuthenticationException):
                sys.exit("FEHLER: Anmeldung abgelehnt (SFTP_USER / SFTP_PASSWORD prüfen)")
            if isinstance(e, paramiko.BadHostKeyException) or "not found in known_hosts" in str(e):
                sys.exit(f"FEHLER: Server-Schlüssel stimmt nicht mit known_hosts überein – Abbruch ({e})")
            if not isinstance(e, (OSError, EOFError, paramiko.SSHException)) or versuch == 3:
                raise
            print(f"Verbindung unterbrochen ({e.__class__.__name__}: {e}) – neuer Versuch {versuch + 1}/3, "
                  "macht beim letzten Zwischenstand weiter …")
            alles = False   # bei --alles: schon Hochgeladenes steht im Zwischenstand, nicht noch einmal
            time.sleep(5 * versuch)
    return 1


if __name__ == "__main__":
    sys.exit(main())
