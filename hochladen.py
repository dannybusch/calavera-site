#!/usr/bin/env python3
"""
Calavera Bremen – dist/ per SFTP auf den Server spiegeln (Ersatz für lftp, falls das nicht installierbar ist)

Macht dasselbe wie der lftp-Befehl in .github/workflows/deploy.yml:
  - lädt hoch, was neu ist oder sich geändert hat (Größe oder Zeitstempel),
  - löscht auf dem Server, was es in dist/ nicht mehr gibt,
  - lässt .htaccess (überall), .well-known/ und _behalten/ auf dem Server unangetastet,
  - prüft den Server-Schlüssel gegen ~/.ssh/known_hosts (wie lftp mit StrictHostKeyChecking=yes).

  python hochladen.py dist/ /ziel/ordner            hochladen
  python hochladen.py dist/ /ziel/ordner --probe    nur anzeigen

Zugang aus der Umgebung: SFTP_HOST, SFTP_PORT (Standard 22), SFTP_USER, SFTP_PASSWORD
Braucht: pip install paramiko
"""
from __future__ import annotations

import argparse
import os
import posixpath
import stat
import sys
import time
from pathlib import Path

AUSNAHME_ORDNER = (".well-known", "_behalten")
AUSNAHME_DATEIEN = (".htaccess",)


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
            st = p.stat()
            dateien[rel] = (st.st_size, int(st.st_mtime))
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


def spiegeln(quelle: Path, ziel: str, probe: bool) -> dict:
    lok_dateien, lok_ordner = lokal_auflisten(quelle)
    client, sftp = verbinden()
    try:
        try:
            sftp.stat(ziel)
        except FileNotFoundError:
            sys.exit(f"FEHLER: Zielordner {ziel} gibt es auf dem Server nicht")
        ent_dateien, ent_ordner = entfernt_auflisten(sftp, ziel)
        zahl = {"hoch": 0, "gleich": 0, "geloescht": 0, "ordner": 0}

        for rel in sorted(lok_ordner - ent_ordner, key=lambda r: r.count("/")):
            print(f"  Ordner anlegen: {rel}")
            zahl["ordner"] += 1
            if not probe:
                sftp.mkdir(posixpath.join(ziel, rel))

        for rel, (groesse, mtime) in lok_dateien.items():
            alt = ent_dateien.get(rel)
            if alt and alt[0] == groesse and alt[1] >= mtime:
                zahl["gleich"] += 1
                continue
            print(f"  {'Neu' if not alt else 'Aktualisieren'}: {rel}")
            zahl["hoch"] += 1
            if not probe:
                pfad = posixpath.join(ziel, rel)
                sftp.put(str(quelle / rel), pfad, confirm=True)
                sftp.utime(pfad, (mtime, mtime))

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
                    print(f"    (nicht leer – enthält ausgenommene Dateien, bleibt stehen)")
        return zahl
    finally:
        sftp.close()
        client.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="dist/ per SFTP spiegeln (wie lftp mirror --reverse --delete)")
    ap.add_argument("quelle")
    ap.add_argument("ziel")
    ap.add_argument("--probe", action="store_true", help="nur anzeigen, nichts ändern")
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
            zahl = spiegeln(quelle, ziel, args.probe)
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
