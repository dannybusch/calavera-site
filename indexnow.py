#!/usr/bin/env python3
"""
Calavera Bremen – geänderte Seiten per IndexNow melden (Bing, Yandex, Seznam, Naver, Yep, …)

IndexNow (https://www.indexnow.org) ist ein gemeinsames Protokoll mehrerer Suchmaschinen: eine Meldung an
api.indexnow.org wird an alle teilnehmenden weitergereicht. Google macht nicht mit – Google liest die
sitemap.xml mit <lastmod> (setzt hochladen.py).

Der Schlüssel (INDEXNOW_KEY, 8–128 Zeichen a–z, A–Z, 0–9, -) ist nicht geheim: build.py legt ihn als
dist/<schlüssel>.txt ab, damit die Suchmaschinen prüfen können, dass die Meldung von uns kommt.

  python indexnow.py geaendert.txt               URLs aus der Datei melden (eine pro Zeile, von hochladen.py)
  python indexnow.py https://www.calavera.club/dark/ …   einzelne URLs melden
  python indexnow.py geaendert.txt --probe       nur anzeigen, nichts senden
  python indexnow.py geaendert.txt --pruefen     zusätzlich vorher prüfen, ob die Schlüsseldatei online ist

Schlüssel aus der Umgebung: INDEXNOW_KEY. Ohne Schlüssel: Hinweis und Ende (Code 3).
Braucht nur Python (keine Pakete).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ENDPUNKT = "https://api.indexnow.org/indexnow"
SCHLUESSEL_MUSTER = re.compile(r"^[A-Za-z0-9-]{8,128}$")
HOECHSTENS = 10_000          # Grenze von IndexNow je Meldung
KENNUNG = "calavera-indexnow/1.0"

ANTWORTEN = {
    200: "angenommen",
    202: "angenommen (Schlüssel wird noch geprüft)",
    400: "ungültige Anfrage",
    403: "Schlüssel ungültig – liegt dist/<schlüssel>.txt wirklich online?",
    422: "URLs gehören nicht zur Domain oder Schlüssel passt nicht",
    429: "zu viele Meldungen – später erneut",
}


def urls_lesen(quellen: list[str]) -> list[str]:
    urls: list[str] = []
    for q in quellen:
        if q.startswith(("http://", "https://")):
            urls.append(q.strip())
        else:
            p = Path(q)
            if not p.is_file():
                sys.exit(f"FEHLER: {q} ist weder URL noch Datei")
            urls += [z.strip() for z in p.read_text(encoding="utf-8").splitlines() if z.strip() and not z.startswith("#")]
    return list(dict.fromkeys(urls))   # Doppelte raus, Reihenfolge bleibt


def schluesseldatei_pruefen(host: str, key: str) -> bool:
    url = f"https://{host}/{key}.txt"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": KENNUNG}), timeout=20) as r:
            ok = r.read().decode("utf-8", "replace").strip() == key
    except (urllib.error.URLError, OSError) as e:
        print(f"  Schlüsseldatei {url} nicht erreichbar ({e})")
        return False
    print(f"  Schlüsseldatei {url}: {'passt' if ok else 'Inhalt passt NICHT zum Schlüssel'}")
    return ok


def melden(urls: list[str], key: str) -> tuple[int, str]:
    host = urlparse(urls[0]).netloc
    daten = json.dumps({"host": host, "key": key, "keyLocation": f"https://{host}/{key}.txt",
                        "urlList": urls[:HOECHSTENS]}).encode("utf-8")
    req = urllib.request.Request(ENDPUNKT, data=daten, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": KENNUNG})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, ANTWORTEN.get(r.status, "")
    except urllib.error.HTTPError as e:
        return e.code, ANTWORTEN.get(e.code, e.reason or "")
    except (urllib.error.URLError, OSError) as e:
        return 0, f"keine Verbindung ({e})"


def main() -> int:
    ap = argparse.ArgumentParser(description="Geänderte Seiten per IndexNow melden (Bing & Co.)")
    ap.add_argument("quellen", nargs="+", help="Datei mit URLs (eine pro Zeile) und/oder einzelne URLs")
    ap.add_argument("--probe", action="store_true", help="nur anzeigen, nichts senden")
    ap.add_argument("--pruefen", action="store_true", help="vorher prüfen, ob die Schlüsseldatei online ist")
    args = ap.parse_args()

    urls = urls_lesen(args.quellen)
    if not urls:
        print("IndexNow: keine geänderten Seiten – nichts zu melden.")
        return 0
    hosts = {urlparse(u).netloc for u in urls}
    if len(hosts) != 1:
        sys.exit(f"FEHLER: URLs von mehreren Domains ({', '.join(sorted(hosts))}) – je Meldung nur eine erlaubt")
    host = hosts.pop()

    print(f"IndexNow: {len(urls)} Seite(n) von {host}")
    for u in urls[:50]:
        print(f"  {u}")
    if len(urls) > 50:
        print(f"  … und {len(urls) - 50} weitere")
    if len(urls) > HOECHSTENS:
        print(f"  (IndexNow nimmt höchstens {HOECHSTENS} je Meldung – der Rest wird ausgelassen)")

    key = os.environ.get("INDEXNOW_KEY", "").strip()
    if not key:
        print("HINWEIS: INDEXNOW_KEY ist nicht gesetzt – nichts gemeldet (siehe README, „IndexNow“).")
        return 3
    if not SCHLUESSEL_MUSTER.match(key):
        sys.exit("FEHLER: INDEXNOW_KEY muss 8–128 Zeichen lang sein und darf nur a–z, A–Z, 0–9 und - enthalten")
    if args.probe:
        print("Probelauf: nichts gesendet.")
        return 0
    if args.pruefen and not schluesseldatei_pruefen(host, key):
        print("FEHLER: Schlüsseldatei fehlt oder passt nicht – Meldung abgebrochen.")
        return 1

    status, text = melden(urls, key)
    if status in (200, 202):
        print(f"Fertig: an IndexNow gemeldet – {status} {text}")
        return 0
    print(f"FEHLER: IndexNow antwortet {status or '–'} {text}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
