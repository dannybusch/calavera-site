#!/usr/bin/env python3
"""Adventskalender: fehlende Streaming-Links in advent/adventskalender<jahr>.yml ergänzen.

  python adventskalender-anreichern.py --tag 2              zeigt, was es für Tür 2 finden würde (ändert nichts)
  python adventskalender-anreichern.py --tag 2 --schreiben  trägt es in die YAML ein
  python adventskalender-anreichern.py --schreiben          alle Türen mit Song + Künstler:in

So geht es:
  1. Song suchen im Apple-Musikkatalog (iTunes-Suche, ohne Schlüssel; Ersatz: Deezer-Suche).
     Künstler:in muss genau passen, der Titel auch (Klammern wie „2012 Remaster“ zählen nicht).
     Live-, Remix-, Demo- und Karaoke-Fassungen kommen nach hinten; passt `erschienen:`, kommt das Original vorn.
  2. Die anderen Dienste direkt fragen:
       Apple Music, Deezer   immer, ohne Schlüssel
       Spotify               mit SPOTIFY_CLIENT_ID + SPOTIFY_CLIENT_SECRET (kostenlose App auf developer.spotify.com)
       Tidal                 mit TIDAL_CLIENT_ID + TIDAL_CLIENT_SECRET (kostenlose App auf developer.tidal.com);
                             gesucht wird über die ISRC der Deezer-Aufnahme, also genau dieselbe Aufnahme
       YouTube Music         mit dem Paket ytmusicapi (pip install ytmusicapi) – ohne Konto, aber inoffiziell
     Was nicht eingerichtet ist, wird übersprungen. Schlüssel nur als Umgebungsvariable setzen, nie in eine Datei.
     SoundCloud gibt es nicht (keine offene Schnittstelle) – bei Bedarf von Hand.
  3. Nur LEERE Links füllen. Was schon drinsteht, bleibt, wie es ist. Bandcamp fasst das Skript nie an.
     Fehlt ein Dienst ganz, wird er unten an die links: der Tür angehängt (Reihenfolge = Reihenfolge der Knöpfe).

Die YAML wird zeilenweise geändert – Kommentare und Formatierung bleiben erhalten.
Braucht nur PyYAML (wie build.py), für YouTube Music zusätzlich ytmusicapi. Zwischen den Türen wartet das
Skript kurz, weil die iTunes-Suche nur rund 20 Anfragen pro Minute erlaubt.

Bitte die Treffer vor dem Veröffentlichen einmal anklicken: Die Suche nimmt die beste Fassung, die sie
findet – bei Neuaufnahmen oder gleichnamigen Songs kann das danebenliegen. Das Skript zeigt deshalb an,
welche Fassung (Album, Jahr) es genommen hat.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
import base64
import difflib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
LAND = "DE"
# Schlüssel in der YAML. Reihenfolge = Reihenfolge, in der fehlende Dienste angehängt werden.
DIENSTE = ("youtube_music", "spotify", "apple_music", "tidal", "deezer")
NIE = {"bandcamp", "andere"}          # fasst das Skript nicht an
FASSUNG_WEG = re.compile(r"\b(live|remix|mix|demo|karaoke|instrumental|acoustic|akustik|cover|re-?recorded|session|edit)\b", re.I)


# ------------------------------------------------------------------ Netz
class DienstFehler(Exception):
    pass


def hole(url: str, dienst: str, daten: bytes | None = None, kopf: dict | None = None) -> dict:
    """JSON holen. Fehler nennen immer Dienst und Adresse (ohne Schlüssel)."""
    sichtbar = re.sub(r"([?&]key=)[^&]+", r"\1***", url)
    req = urllib.request.Request(url, data=daten, headers={"User-Agent": "calavera-adventskalender/1.0",
                                                          "Accept": "application/json", **(kopf or {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            antwort = " ".join(exc.read().decode("utf-8", "replace").split())[:300]
        except Exception:  # noqa: BLE001
            antwort = ""
        raise DienstFehler(f"{dienst}: HTTP {exc.code} {exc.reason} – {sichtbar}"
                           + (f"\n        Antwort: {antwort}" if antwort else "")) from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise DienstFehler(f"{dienst}: {getattr(exc, 'reason', exc)} – {sichtbar}") from None


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s).replace("ß", "ss")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(.*?\)|\[.*?\]", " ", s)                      # (2012 Remaster), [Live]
    s = re.sub(r"\s-\s.*$", " ", s)                               # „Song - Remastered 2011“
    s = s.replace("&", " and ")
    s = re.sub(r"^the\s+", "", s.strip())
    return re.sub(r"[^a-z0-9]+", "", s)


FEAT = re.compile(r"\s+(feat\.?|ft\.?|featuring|with|x|&|und|and|,)\s+.*$", re.I)
FEAT_TITEL = re.compile(r"\s*[\(\[]\s*(feat\.?|ft\.?|featuring|with)\s+[^\)\]]*[\)\]]", re.I)


def hauptname(name: str) -> str:
    """„Chris Harms feat. VNV Nation“ → „chrisharms“; Bands mit & im Namen bleiben ganz, wenn beide Seiten gleich sind."""
    return norm(FEAT.sub("", str(name).strip()))


VERWORFEN: list[tuple[float, str]] = []      # pro Tür: (Ähnlichkeit, Zeile) – wird bei „nichts gefunden“ gezeigt


def aehnlich(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def bewerte(titel: str, kuenstler: str, album: str, jahr: str, song: str, artist: str, erschienen: str,
            dienst: str = "") -> int | None:
    """None = passt nicht. Sonst: je kleiner, desto besser.
    Künstler:in muss passen (nach Vereinfachung: Groß/klein, Satzzeichen, „feat.“ egal), der Titel genau oder fast.
    Das Jahr schließt nie aus, es sortiert nur."""
    k_ist, k_soll = hauptname(kuenstler), hauptname(artist)
    t_ist, t_soll = norm(re.sub(FEAT_TITEL, "", titel)), norm(song)
    k_aeh, t_aeh = aehnlich(k_ist, k_soll), aehnlich(t_ist, t_soll)
    p = 0
    if k_ist != k_soll:                          # beim Namen kein „fast“: „Suicide Commander“ ist jemand anderes
        grund = "anderer Künstler" if t_ist == t_soll else "anderer Künstler und Titel"
        VERWORFEN.append((k_aeh + t_aeh, f"{dienst}: {kuenstler} – {titel} · {album}{' · ' + jahr if jahr else ''}  → {grund}"))
        return None
    if t_ist != t_soll:                          # beim Titel reicht fast gleich (Tippfehler, Schreibweise)
        if t_aeh < .9:
            VERWORFEN.append((k_aeh + t_aeh, f"{dienst}: {kuenstler} – {titel} · {album}{' · ' + jahr if jahr else ''}  → Titel passt nicht"))
            return None
        p += 30
    if FASSUNG_WEG.search(titel) and not FASSUNG_WEG.search(song):
        p += 100
    if FASSUNG_WEG.search(album):
        p += 20
    if re.search(r"\b(karaoke|tribute|made famous)\b", f"{album} {kuenstler}", re.I):
        p += 500
    if re.fullmatch(r"\d{4}", erschienen or "") and re.fullmatch(r"\d{4}", jahr or ""):
        p += 0 if jahr == erschienen else 10 + min(abs(int(jahr) - int(erschienen)), 40)
    return p


def suche_apple(song: str, artist: str, erschienen: str) -> dict | None:
    treffer = []
    for land in (LAND, "US"):                   # manches gibt es im deutschen Katalog nicht (oder anders sortiert)
        q = urllib.parse.urlencode({"term": f"{artist} {song}", "entity": "song", "country": land, "limit": 50})
        ergebnisse = hole(f"https://itunes.apple.com/search?{q}", "iTunes-Suche").get("results", [])
        if not ergebnisse:
            VERWORFEN.append((0, f"Apple ({land}): keine Ergebnisse für „{artist} {song}“"))
        for r in ergebnisse:
            jahr = (r.get("releaseDate") or "")[:4]
            p = bewerte(r.get("trackName", ""), r.get("artistName", ""), r.get("collectionName", ""), jahr, song,
                        artist, erschienen, f"Apple ({land})")
            if p is not None:
                treffer.append((p, jahr or "9999", r))
        if treffer:
            break
    if not treffer:
        return None
    _, jahr, r = min(treffer, key=lambda t: (t[0], t[1]))
    url = re.sub(r"[?&]uo=\d+", "", r["trackViewUrl"])
    return {"url": url, "quelle": "Apple Music", "titel": r["trackName"], "kuenstler": r["artistName"],
            "album": r.get("collectionName", ""), "jahr": jahr}


def suche_deezer(song: str, artist: str, erschienen: str) -> dict | None:
    treffer = []
    # erst frei, dann mit Feldern – gefiltert wird danach über Künstler:in + Titel
    for frage in (f"{artist} {song}", f'artist:"{artist}" track:"{song}"'):
        q = urllib.parse.urlencode({"q": frage, "limit": 50})
        for r in hole(f"https://api.deezer.com/search?{q}", "Deezer-Suche").get("data", []):
            p = bewerte(r.get("title", ""), r.get("artist", {}).get("name", ""), r.get("album", {}).get("title", ""), "",
                        song, artist, "", "Deezer")
            if p is not None:
                treffer.append((p, r.get("rank", 0) * -1, r))
        if treffer:
            break
    if not treffer:
        return None
    r = min(treffer, key=lambda t: (t[0], t[1]))[2]
    return {"url": r["link"], "quelle": "Deezer", "titel": r["title"], "kuenstler": r["artist"]["name"],
            "album": r.get("album", {}).get("title", ""), "jahr": "", "id": r.get("id")}


def isrc_von_deezer(track_id) -> str:
    """ISRC = weltweite Kennung der Aufnahme. Damit findet Tidal genau diese Aufnahme."""
    return str(hole(f"https://api.deezer.com/track/{track_id}", "Deezer-Track").get("isrc") or "")


_tidal_token = None


def suche_tidal(isrc: str) -> str | None:
    """Nur mit TIDAL_CLIENT_ID + TIDAL_CLIENT_SECRET (kostenlose App auf developer.tidal.com). Sucht per ISRC."""
    global _tidal_token
    cid, geheim = os.environ.get("TIDAL_CLIENT_ID"), os.environ.get("TIDAL_CLIENT_SECRET")
    if not cid or not geheim or not isrc:
        return None
    if not _tidal_token:
        auth = base64.b64encode(f"{cid}:{geheim}".encode()).decode()
        _tidal_token = hole("https://auth.tidal.com/v1/oauth2/token", "Tidal-Anmeldung",
                            daten=b"grant_type=client_credentials",
                            kopf={"Authorization": f"Basic {auth}",
                                  "Content-Type": "application/x-www-form-urlencoded"})["access_token"]
    q = urllib.parse.urlencode({"countryCode": LAND, "filter[isrc]": isrc})
    daten = hole(f"https://openapi.tidal.com/v2/tracks?{q}", "Tidal-Suche",
                 kopf={"Authorization": f"Bearer {_tidal_token}", "Accept": "application/vnd.api+json"})
    tracks = [d for d in daten.get("data") or [] if d.get("id")]
    return f"https://tidal.com/track/{tracks[0]['id']}" if tracks else None


def suche_youtube_music(song: str, artist: str, erschienen: str) -> str | None:
    """Nur wenn das Paket ytmusicapi installiert ist (pip install ytmusicapi) – ohne Konto und ohne Schlüssel.
    Inoffiziell: Ändert YouTube etwas, kann es ausfallen; dann einfach von Hand eintragen."""
    try:
        from ytmusicapi import YTMusic
    except ImportError:
        return None
    try:
        ergebnisse = YTMusic(language="de", location=LAND).search(f"{artist} {song}", filter="songs", limit=20)
    except Exception as exc:  # noqa: BLE001
        raise DienstFehler(f"YouTube-Music-Suche (ytmusicapi): {exc}") from None
    treffer = []
    for i, r in enumerate(ergebnisse):
        artists = [a.get("name", "") for a in r.get("artists") or []]
        p = bewerte(r.get("title", ""), artists[0] if artists else "", (r.get("album") or {}).get("name", ""),
                    str(r.get("year") or ""), song, artist, erschienen, "YouTube Music")
        if p is not None and r.get("videoId"):
            treffer.append((p, i, r))
    if not treffer:
        return None
    return f"https://music.youtube.com/watch?v={min(treffer, key=lambda t: (t[0], t[1]))[2]['videoId']}"


_spotify_token = None


def suche_spotify(song: str, artist: str, erschienen: str) -> tuple[str, str] | None:
    """Nur mit SPOTIFY_CLIENT_ID + SPOTIFY_CLIENT_SECRET (kostenlose App auf developer.spotify.com)."""
    global _spotify_token
    cid, geheim = os.environ.get("SPOTIFY_CLIENT_ID"), os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not cid or not geheim:
        return None
    if not _spotify_token:
        auth = base64.b64encode(f"{cid}:{geheim}".encode()).decode()
        _spotify_token = hole("https://accounts.spotify.com/api/token", "Spotify-Anmeldung",
                              daten=b"grant_type=client_credentials",
                              kopf={"Authorization": f"Basic {auth}",
                                    "Content-Type": "application/x-www-form-urlencoded"})["access_token"]
    # erst frei („Suicide Commando No More“ – findet das, was man auch in der App findet), dann mit Feldern;
    # gefiltert wird danach über Künstler:in + Titel. limit: seit Februar 2026 höchstens 10 – mehr gibt HTTP 400
    treffer = []
    for frage in (f"{artist} {song}", f"track:{song} artist:{artist}"):
        q = urllib.parse.urlencode({"q": frage, "type": "track", "market": LAND, "limit": 10})
        for r in hole(f"https://api.spotify.com/v1/search?{q}", "Spotify-Suche",
                      kopf={"Authorization": f"Bearer {_spotify_token}"}).get("tracks", {}).get("items", []):
            jahr = (r.get("album", {}).get("release_date") or "")[:4]
            artists = [a.get("name", "") for a in r.get("artists", [])]
            p = bewerte(r.get("name", ""), artists[0] if artists else "", r.get("album", {}).get("name", ""), jahr,
                        song, artist, erschienen, "Spotify")
            if p is not None:
                treffer.append((p, -int(r.get("popularity", 0)), r))
        if treffer:
            break
    if not treffer:
        return None
    r = min(treffer, key=lambda t: (t[0], t[1]))[2]
    return r["external_urls"]["spotify"], str((r.get("external_ids") or {}).get("isrc") or "")


def fehlt_einrichtung() -> dict[str, str]:
    """Dienste, die nur mit Einrichtung gehen – und was dafür fehlt."""
    fehlt = {}
    if not (os.environ.get("SPOTIFY_CLIENT_ID") and os.environ.get("SPOTIFY_CLIENT_SECRET")):
        fehlt["spotify"] = "SPOTIFY_CLIENT_ID/SECRET nicht gesetzt"
    if not (os.environ.get("TIDAL_CLIENT_ID") and os.environ.get("TIDAL_CLIENT_SECRET")):
        fehlt["tidal"] = "TIDAL_CLIENT_ID/SECRET nicht gesetzt"
    try:
        import ytmusicapi  # noqa: F401
    except ImportError:
        fehlt["youtube_music"] = "pip install ytmusicapi"
    return fehlt


def finde_links(song: str, artist: str, erschienen: str) -> tuple[dict | None, dict[str, str], list[str]]:
    """(Treffer, Links, Hinweise). Jeder Dienst sucht für sich – findet Apple nichts, suchen die anderen trotzdem.
    Treffer = die Fassung, die angezeigt wird (Apple, sonst Deezer); kann None sein, auch wenn es Links gibt."""
    hinweise, links = [], {}

    def versuch(f):
        try:
            return f()
        except DienstFehler as exc:
            hinweise.append(str(exc))
            return None

    ap = versuch(lambda: suche_apple(song, artist, erschienen))
    if ap:
        links["apple_music"] = ap["url"]
    dz = versuch(lambda: suche_deezer(song, artist, erschienen))
    if dz:
        links["deezer"] = dz["url"]
    sp = versuch(lambda: suche_spotify(song, artist, erschienen))
    if sp:
        links["spotify"] = sp[0]
    if "tidal" not in fehlt_einrichtung():
        # Tidal sucht über die ISRC (Kennung der Aufnahme): von Deezer, sonst von Spotify
        isrc = (versuch(lambda: isrc_von_deezer(dz["id"])) if dz and dz.get("id") else "") or (sp[1] if sp else "")
        if isrc:
            url = versuch(lambda: suche_tidal(isrc))
            if url:
                links["tidal"] = url
        else:
            hinweise.append("Tidal: übersprungen – keine ISRC (weder Deezer noch Spotify haben den Song gefunden)")
    yt = versuch(lambda: suche_youtube_music(song, artist, erschienen))
    if yt:
        links["youtube_music"] = yt
    return ap or dz, {k: links[k] for k in DIENSTE if k in links}, hinweise


# ------------------------------------------------------------------ YAML zeilenweise ändern
TUER = re.compile(r"^(\s*)-\s+tag:\s*(\d+)\b")
LEER = {"", '""', "''", "~", "null"}


def trage_ein(zeilen: list[str], tag: int, neu: dict[str, str]) -> tuple[list[str], list[str]]:
    """Füllt leere Links der Tür und hängt fehlende Dienste an. Gibt (zeilen, geänderte Schlüssel) zurück."""
    start = ende = None
    einzug = ""
    for i, z in enumerate(zeilen):
        m = TUER.match(z)
        if m and start is None and int(m.group(2)) == tag:
            start, einzug = i, m.group(1)
        elif m and start is not None:
            ende = i
            break
        elif start is not None and z.strip() and not z.startswith(einzug + " ") and not z.lstrip().startswith("#"):
            ende = i                                 # nächster Block auf oberster Ebene
            break
    if start is None:
        return zeilen, []
    ende = ende if ende is not None else len(zeilen)
    while ende > start + 1 and not zeilen[ende - 1].strip():
        ende -= 1                                   # Leerzeilen am Blockende nicht mitzählen
    feld = einzug + "  "                            # „  - tag:“ → Felder stehen 2 weiter drin (unter „tag“)
    links_i = next((i for i in range(start, ende) if re.match(rf"^{feld}links:\s*(#.*)?$", zeilen[i])), None)
    geaendert = []
    if links_i is None:
        zeilen = zeilen[:ende] + [f"{feld}links:"] + zeilen[ende:]
        links_i, ende = ende, ende + 1
    kind = feld + "  "
    vorhanden, letzte = {}, links_i
    for i in range(links_i + 1, ende):
        m = re.match(rf"^{kind}([a-z_]+):(.*)$", zeilen[i])
        if not m:
            if zeilen[i].strip() and not zeilen[i].startswith(kind):
                break
            continue
        vorhanden[m.group(1)] = i
        letzte = i
    for key, url in neu.items():
        if key in NIE:
            continue
        if key in vorhanden:
            i = vorhanden[key]
            m = re.match(rf"^({kind}{key}:)\s*([^#]*?)\s*(#.*)?$", zeilen[i])
            if m and m.group(2).strip() in LEER:
                rest = f"   {m.group(3)}" if m.group(3) else ""
                zeilen[i] = f'{m.group(1)} "{url}"{rest}'
                geaendert.append(key)
        else:
            letzte += 1
            zeilen.insert(letzte, f'{kind}{key}: "{url}"')
            geaendert.append(key)
    return zeilen, geaendert


# ------------------------------------------------------------------ Ablauf
def main() -> int:
    ap = argparse.ArgumentParser(description="Fehlende Streaming-Links im Adventskalender ergänzen.")
    ap.add_argument("--datei", help="YAML-Datei (Standard: neueste advent/adventskalender*.yml)")
    ap.add_argument("--tag", type=int, action="append", help="nur diese Tür(en), z. B. --tag 2 --tag 5")
    ap.add_argument("--schreiben", action="store_true", help="Ergebnis in die Datei schreiben (sonst nur anzeigen)")
    ap.add_argument("--nur-vorhandene", action="store_true",
                    help="nur Dienste füllen, die bei der Tür schon (leer) stehen – keine neuen anhängen")
    args = ap.parse_args()

    pfad = Path(args.datei) if args.datei else max((ROOT / "advent").glob("adventskalender*.yml"))
    text = pfad.read_text(encoding="utf-8")
    daten = yaml.safe_load(text) or {}
    zeilen = text.split("\n")
    tueren = [t for t in daten.get("tueren") or [] if isinstance(t, dict)]
    if args.tag:
        tueren = [t for t in tueren if t.get("tag") in args.tag]
    print(f"{pfad.relative_to(ROOT) if pfad.is_relative_to(ROOT) else pfad}: {len(tueren)} Tür(en)\n")

    erste = True
    for t in sorted(tueren, key=lambda t: int(t.get("tag", 0))):
        tag, song, artist = int(t["tag"]), str(t.get("song") or "").strip(), str(t.get("kuenstler") or "").strip()
        if not song or not artist:
            print(f"Tür {tag:2}: song oder kuenstler fehlt – übersprungen")
            continue
        links = t.get("links") if isinstance(t.get("links"), dict) else {}
        leer = [k for k in DIENSTE if not str(links.get(k) or "").strip()]
        if args.nur_vorhandene:
            leer = [k for k in leer if k in links]
        if not leer:
            print(f"Tür {tag:2}: {artist} – {song}: nichts zu tun")
            continue
        if not erste:
            time.sleep(3)                            # iTunes-Suche: rund 20 Anfragen pro Minute
        erste = False
        print(f"Tür {tag:2}: {artist} – {song}" + (f" ({t.get('erschienen')})" if t.get("erschienen") else ""))
        VERWORFEN.clear()
        try:
            seed, gefunden, hinweise = finde_links(song, artist, str(t.get("erschienen") or "").strip())
        except DienstFehler as exc:
            print(f"    Fehler bei {exc}")
            continue
        for h in hinweise:
            print(f"    {h}" if h.startswith("Tidal: übersprungen") else f"    Fehler bei {h}")
        if seed:
            print(f"    gefunden über {seed['quelle']}: {seed['kuenstler']} – {seed['titel']}"
                  f" · {seed['album']}{' · ' + seed['jahr'] if seed['jahr'] else ''}")
            e = str(t.get("erschienen") or "").strip()
            if re.fullmatch(r"\d{4}", e) and re.fullmatch(r"\d{4}", seed.get("jahr") or "") \
                    and abs(int(e) - int(seed["jahr"])) >= 3:
                print(f"    Achtung: in der Datei steht erschienen: {e}, der Treffer ist von {seed['jahr']} – "
                      "bitte prüfen (zählt fürs Ratespiel)")
        if not gefunden:
            print("    nichts gefunden – bitte von Hand eintragen")
        if not seed or not gefunden:
            naechste = sorted(VERWORFEN, key=lambda v: -v[0])[:5]
            if naechste:
                print("    am nächsten dran waren:")
                for _, zeile in naechste:
                    print(f"      {zeile}")
        if not gefunden:
            continue
        neu = {k: v for k, v in gefunden.items() if k in leer}
        fehlt = fehlt_einrichtung()
        for k in leer:
            grund = f"nicht eingerichtet: {fehlt[k]}" if k in fehlt else "bei diesem Dienst nicht gefunden"
            print(f"    {k:14} {neu.get(k, f'– ({grund})')}")
        if args.schreiben and neu:
            zeilen, geaendert = trage_ein(zeilen, tag, neu)
            print(f"    eingetragen: {', '.join(geaendert) or 'nichts'}")

    if args.schreiben:
        neu_text = "\n".join(zeilen)
        yaml.safe_load(neu_text)                     # Sicherheitsnetz: nur gültiges YAML schreiben
        if neu_text != text:
            pfad.write_text(neu_text, encoding="utf-8")
            print(f"\n→ {pfad.name} gespeichert. Bitte die neuen Links einmal anklicken.")
        else:
            print("\n→ keine Änderung")
    else:
        print("\n(nur angezeigt – mit --schreiben eintragen)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
