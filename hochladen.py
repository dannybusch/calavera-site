#!/usr/bin/env python3
"""
Calavera Bremen – dist/ per SFTP auf den Server spiegeln (ersetzt lftp, braucht nur Python)

  - lädt nur hoch, was neu ist oder dessen Inhalt sich geändert hat: Prüfsummen der hochgeladenen Dateien
    liegen auf dem Server in .calavera-pruefsummen.json (fehlt die Datei, wird einmal alles hochgeladen),
  - löscht auf dem Server, was es in dist/ nicht mehr gibt,
  - lässt .htaccess (überall), .well-known/ und _behalten/ auf dem Server unangetastet,
  - prüft den Server-Schlüssel gegen ~/.ssh/known_hosts (wie lftp mit StrictHostKeyChecking=yes).

  python hochladen.py dist/ /ziel/ordner            hochladen
  python hochladen.py dist/ /ziel/ordner --probe    nur anzeigen
  python hochladen.py dist/ /ziel/ordner --alles    alles neu hochladen (Prüfsummen ignorieren)

Zugang aus der Umgebung: SFTP_HOST, SFTP_PORT (Standard 22), SFTP_USER, SFTP_PASSWORD
Braucht: pip install paramiko
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import posixpath
import stat
import sys
import time
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


def pruefsummen_laden(sftp, ziel: str) -> dict:
    try:
        with sftp.open(posixpath.join(ziel, PRUEFSUMMEN), "r") as f:
            daten = json.loads(f.read().decode("utf-8"))
        return daten.get("dateien", {}) if isinstance(daten, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def pruefsummen_schreiben(sftp, ziel: str, summen: dict) -> None:
    """erst unter anderem Namen, dann umbenennen – nie eine halbe Datei"""
    inhalt = json.dumps({"hinweis": "von hochladen.py verwaltet – nicht löschen (sonst wird einmal alles neu hochgeladen)",
                         "stand": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "dateien": summen},
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


def spiegeln(quelle: Path, ziel: str, probe: bool, alles: bool = False) -> dict:
    lok_dateien, lok_ordner = lokal_auflisten(quelle)
    client, sftp = verbinden()
    try:
        try:
            sftp.stat(ziel)
        except FileNotFoundError:
            sys.exit(f"FEHLER: Zielordner {ziel} gibt es auf dem Server nicht")
        ent_dateien, ent_ordner = entfernt_auflisten(sftp, ziel)
        summen = {} if alles else pruefsummen_laden(sftp, ziel)
        if not summen and not alles and ent_dateien:
            print(f"  (noch keine {PRUEFSUMMEN} auf dem Server – dieses Mal wird alles hochgeladen)")
        zahl = {"hoch": 0, "gleich": 0, "geloescht": 0, "ordner": 0}

        for rel in sorted(lok_ordner - ent_ordner, key=lambda r: r.count("/")):
            print(f"  Ordner anlegen: {rel}")
            zahl["ordner"] += 1
            if not probe:
                sftp.mkdir(posixpath.join(ziel, rel))

        neue_summen = {}
        for rel, (groesse, summe) in lok_dateien.items():
            alt = ent_dateien.get(rel)
            # gleich = auf dem Server vorhanden, gleiche Größe, und zuletzt mit genau diesem Inhalt hochgeladen
            if alt and alt[0] == groesse and summen.get(rel) == summe:
                zahl["gleich"] += 1
                neue_summen[rel] = summe
                continue
            print(f"  {'Neu' if not alt else 'Aktualisieren'}: {rel}")
            zahl["hoch"] += 1
            if not probe:
                sftp.put(str(quelle / rel), posixpath.join(ziel, rel), confirm=True)
                neue_summen[rel] = summe

        for rel in sorted(set(ent_dateien) - set(lok_dateien)):
            print(f"  Löschen: {rel}")
            zahl["geloescht"] += 1
            if not probe:
                sftp.remove(posixpath.join(ziel, rel))
        for rel in sorted(ent_ordner - lok_ordner, key=lambda r: -r.count("/")):
            print(f"  Ordner löschen: {rel}")
            if not probe:
                try:
                    sftp.rmdir(posixpath.join(ziel, rel))
                except OSError:
                    print("    (nicht leer – enthält ausgenommene Dateien, bleibt stehen)")
        if not probe and (zahl["hoch"] or zahl["geloescht"] or neue_summen != summen):
            pruefsummen_schreiben(sftp, ziel, neue_summen)
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
    args = ap.parse_args()
    quelle = Path(args.quelle)
    if not quelle.is_dir():
        sys.exit(f"FEHLER: {quelle} ist kein Ordner")
    ziel = args.ziel.strip()
    if ziel in ("~", "~/") or ziel.startswith("~/"):   # wie bei lftp: "~" = Startordner des Zugangs
        ziel = ziel[2:] or "."
    ziel = ziel.rstrip("/") or "/"
    for versuch in range(1, 4):   # Spiegeln ist wiederholbar – nach Verbindungsabbruch einfach von vorn
        try:
            zahl = spiegeln(quelle, ziel, args.probe, args.alles)
            print(("Probelauf: " if args.probe else "Fertig: ")
                  + f"{zahl['hoch']} hochgeladen, {zahl['geloescht']} gelöscht, {zahl['ordner']} Ordner neu, {zahl['gleich']} unverändert")
            return 0
        except Exception as e:   # noqa: BLE001
            import paramiko
            if isinstance(e, paramiko.AuthenticationException):
                sys.exit("FEHLER: Anmeldung abgelehnt (SFTP_USER / SFTP_PASSWORD prüfen)")
            if isinstance(e, paramiko.BadHostKeyException) or "not found in known_hosts" in str(e):
                sys.exit(f"FEHLER: Server-Schlüssel stimmt nicht mit known_hosts überein – Abbruch ({e})")
            if not isinstance(e, (OSError, EOFError, paramiko.SSHException)) or versuch == 3:
                raise
            print(f"Verbindung unterbrochen ({e.__class__.__name__}: {e}) – neuer Versuch {versuch + 1}/3 …")
            time.sleep(5 * versuch)
    return 1


if __name__ == "__main__":
    sys.exit(main())
