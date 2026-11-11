#!/usr/bin/env python3
"""
Calavera Bremen – Veranstaltungen automatisch auf rausgegangen.de eintragen (Rausgegangen-API v2)

Eigenständig wie reels.py/media.py: liest events/*.md und config.yml, ändert hier nichts.
Jede Veranstaltung wird bei rausgegangen ein Event mit einem Termin (Show) im Calavera.
Zugeordnet wird über die mapping_id "calavera-<dateiname>" – bei jedem Lauf wird angelegt,
was fehlt, und nachgetragen, was sich geändert hat. Doppelt angelegt wird nichts.

  python rausgegangen.py                 Probelauf: zeigt, was gesendet würde (sendet nichts)
  python rausgegangen.py --senden        wirklich anlegen/aktualisieren
  python rausgegangen.py melancholie     nur Veranstaltungen mit "melancholie" im Dateinamen
  python rausgegangen.py --json          Probelauf mit den vollständigen Daten
  python rausgegangen.py location        Calavera bei rausgegangen suchen (ID für config.yml)
  python rausgegangen.py status          was steht dort schon, was fehlt, was ist dort übrig?

  --bilder        Bilder auch bei schon angelegten Events neu übertragen (sonst nur beim Anlegen)
  --now "JJJJ-MM-TT HH:MM"   so tun, als wäre jetzt …

Zugang: der API-Token kommt NUR aus der Umgebungsvariable RAUSGEGANGEN_API_KEY
(auf GitHub: Settings → Secrets → Actions → RAUSGEGANGEN_API_KEY). Den Token gibt es über
zentrale@rausgegangen.de – das "secret" der Doku-Seite ist kein API-Token.

In config.yml:
  rausgegangen:
    location: "uuid-der-location"   # einmal mit "python rausgegangen.py location" ermitteln
    veroeffentlichen: false         # true = Events sind auf rausgegangen.de sichtbar (Standard: false = nur Vorschau)
    kategorie: party                # Standard-Kategorie (Konzerte werden automatisch konzerte-und-musik)

In einer Event-Datei (optional):
  rausgegangen: false               # diese Veranstaltung nicht übertragen
  rausgegangen_kategorie: theater   # andere Kategorie für diese Veranstaltung
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402  – nur zum Lesen der Event-Dateien; baut nichts

API = os.environ.get("RAUSGEGANGEN_API_URL", "https://api.zentrale.rausgegangen.de").rstrip("/")
PREFIX = "calavera-"
KATEGORIEN = ("aktiv-und-kreativ", "ausstellung", "feste-und-festival", "film", "food-und-drinks", "gesprochenes",
              "kinder-und-familien", "konzerte-und-musik", "markt", "party", "shows-und-performances", "sport", "theater")
# Art der Veranstaltung (art: in der Event-Datei) → Kategorie bei rausgegangen
ART_KATEGORIE = [(r"konzert|live|band|unplugged|session", "konzerte-und-musik"),
                 (r"lesung|slam|vortrag|talk|gespräch", "gesprochenes"),
                 (r"film|kino", "film"),
                 (r"markt|flohmarkt|börse", "markt"),
                 (r"theater|kabarett|comedy|show|performance|drag", "shows-und-performances"),
                 (r"ausstellung|vernissage", "ausstellung"),
                 (r"workshop|kurs", "aktiv-und-kreativ"),
                 (r"café|cafe|kaffee|brunch", "food-und-drinks")]
ERLAUBT = {"p", "h3", "h4", "h5", "strong", "u", "i", "s", "a", "ul", "ol", "li", "sup", "sub", "br"}
UMBENENNEN = {"b": "strong", "em": "i", "h1": "h3", "h2": "h3", "h6": "h5", "del": "s"}


def info(msg: str = "") -> None:
    print(msg, flush=True)


def fehler(msg: str, code: int = 1) -> None:
    print(f"FEHLER: {msg}", file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------------------
#  API
# ---------------------------------------------------------------------------
class ApiFehler(Exception):
    def __init__(self, status: int, text: str):
        super().__init__(f"HTTP {status}: {text[:600]}")
        self.status = status


class Api:
    def __init__(self, token: str):
        self.token = token

    def _url(self, pfad: str, params: dict | None = None) -> str:
        q = {"api_key": self.token, **{k: v for k, v in (params or {}).items() if v not in (None, "")}}
        return f"{API}{pfad}?{urllib.parse.urlencode(q)}"

    def anfrage(self, methode: str, pfad: str, daten: dict | None = None, params: dict | None = None):
        url = pfad if pfad.startswith("http") else self._url(pfad, params)
        if pfad.startswith("http") and "api_key=" not in url:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode({"api_key": self.token})
        body = json.dumps(daten).encode() if daten is not None else None
        req = urllib.request.Request(url, data=body, method=methode,
                                     headers={"Accept": "application/json", "Content-Type": "application/json",
                                              "User-Agent": "calavera-bremen-rausgegangen/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                text = r.read().decode("utf-8") or "null"
                return json.loads(text)
        except urllib.error.HTTPError as e:
            raise ApiFehler(e.code, e.read().decode("utf-8", "replace")) from None
        except urllib.error.URLError as e:
            fehler(f"rausgegangen-API nicht erreichbar: {e.reason}")

    def liste(self, pfad: str, params: dict | None = None) -> list[dict]:
        """GET mit seitenweiser Ausgabe (Django REST: {"results": [...], "next": url}) oder einfacher Liste"""
        daten = self.anfrage("GET", pfad, params=params)
        if isinstance(daten, list):
            return daten
        alle = list(daten.get("results") or [])
        weiter, seiten = daten.get("next"), 0
        while weiter and seiten < 200:
            daten = self.anfrage("GET", weiter)
            alle += daten.get("results") or []
            weiter, seiten = daten.get("next"), seiten + 1
        return alle

    def schreiben(self, methode: str, pfad: str, daten: dict, rg_id: str | None = None) -> dict:
        """POST/PATCH an die Sammel-Adresse (laut Doku: Zuordnung über id/mapping_id im Inhalt);
        lehnt der Server das ab (404/405), noch einmal an die Einzel-Adresse …/<id>/"""
        try:
            return self.anfrage(methode, pfad, daten)
        except ApiFehler as e:
            if e.status in (404, 405) and rg_id:
                return self.anfrage(methode, f"{pfad.rstrip('/')}/{rg_id}/", daten)
            raise


# ---------------------------------------------------------------------------
#  Veranstaltung → rausgegangen
# ---------------------------------------------------------------------------
def kategorie(ev, meta: dict, standard: str) -> str:
    k = str(meta.get("rausgegangen_kategorie") or "").strip().lower()
    if k:
        if k not in KATEGORIEN:
            fehler(f"{ev.source.name}: rausgegangen_kategorie \"{k}\" gibt es nicht – möglich: {', '.join(KATEGORIEN)}")
        return k
    text = f"{ev.kind} {ev.highlight}".lower()
    for muster, kat in ART_KATEGORIE:
        if re.search(muster, text):
            return kat
    return standard


def preise(eintritt: str, standard: str, standard_notiz: str, kasse: str) -> dict:
    """"5 €" → price 5.00; "frei" → 0.00; "Hutspende" → nur Beschreibung; mehrere Beträge → min/max"""
    text = (eintritt or standard or "").strip()
    betraege = [float(b.replace(",", ".")) for b in re.findall(r"(\d+(?:[.,]\d{1,2})?)\s*(?:€|EUR|Euro)", text, re.I)]
    frei = bool(re.search(r"\b(frei|kostenlos|umsonst)\b", text, re.I)) and not betraege
    notiz = []
    if text and (len(betraege) != 1 or not re.fullmatch(r"\d+(?:[.,]\d{1,2})?\s*(?:€|EUR|Euro)", text, re.I)):
        notiz.append(text)
    if not eintritt or eintritt == standard:
        notiz.append(standard_notiz)
    notiz.append(kasse)
    p = {"price": None, "min_price": None, "max_price": None,
         "price_description": " · ".join(n for n in notiz if n)}
    if len(betraege) == 1:
        p["price"] = f"{betraege[0]:.2f}"
    elif len(betraege) > 1:
        p["min_price"], p["max_price"] = f"{min(betraege):.2f}", f"{max(betraege):.2f}"
    elif frei:
        p["price"] = "0.00"
    return p


class _Saeuberer:
    """HTML auf das reduzieren, was rausgegangen erlaubt (p, h3–h5, strong, u, i, s, a, ul, ol, sup, sub)"""
    def __init__(self):
        from html.parser import HTMLParser
        outer = self

        class P(HTMLParser):
            def handle_starttag(self, tag, attrs):
                tag = UMBENENNEN.get(tag, tag)
                if tag in ERLAUBT:
                    if tag == "a":
                        href = dict(attrs).get("href") or ""
                        if href.startswith("/"):
                            href = outer.basis + href
                        outer.teile.append(f'<a href="{html.escape(href, quote=True)}">')
                    else:
                        outer.teile.append(f"<{tag}>")

            def handle_endtag(self, tag):
                tag = UMBENENNEN.get(tag, tag)
                if tag in ERLAUBT and tag != "br":
                    outer.teile.append(f"</{tag}>")

            def handle_data(self, data):
                outer.teile.append(html.escape(data, quote=False))

        self.parser_klasse = P

    def __call__(self, text: str, basis: str) -> str:
        self.teile, self.basis = [], basis
        p = self.parser_klasse(convert_charrefs=True)
        p.feed(text)
        p.close()
        return re.sub(r"\n{2,}", "\n", "".join(self.teile)).strip()


saeubern = _Saeuberer()


def beschreibung(ev, cfg: dict) -> str:
    site, club = cfg["site"], cfg.get("club") or {}
    teile = []
    if ev.teaser:
        teile.append(f"<p><strong>{html.escape(ev.teaser)}</strong></p>")
    if ev.body_html:
        teile.append(saeubern(ev.body_html, site["url"]))
    zeilen = []
    if ev.djs:
        zeilen.append(f"<strong>{'DJs' if len(ev.djs) > 1 else 'DJ'}:</strong> {html.escape(ev.lineup)}")
    if ev.genres:
        zeilen.append(f"<strong>Musik:</strong> {html.escape(', '.join(ev.genres))}")
    if ev.doors:
        zeilen.append(f"<strong>Einlass:</strong> {ev.doors:%H:%M} Uhr")
    if ev.stream_url:
        zeilen.append(f'<strong>Auch im Livestream:</strong> <a href="{html.escape(ev.stream_url, quote=True)}">{html.escape(ev.stream_url)}</a>')
    if zeilen:
        teile.append("<p>" + "<br>".join(zeilen) + "</p>")
    teile.append(f'<p>Calavera · {html.escape(club.get("address", ""))} · {html.escape(club.get("city", ""))}<br>'
                 f'Alle Infos: <a href="{site["url"]}{ev.url}">{site["url"].replace("https://", "")}{ev.url}</a></p>')
    return "\n".join(t for t in teile if t)


def bild_url(ev, site_url: str) -> str:
    if ev.visual_src:   # vom Build erzeugt (build.py → process_visual), liegt nach dem Veröffentlichen online
        return f"{site_url}/media/events/{ev.slug}/breit.jpg"
    if re.match(r"^https?://", ev.visual_url or ""):
        return ev.visual_url
    return ""


def event_daten(ev, meta: dict, cfg: dict, rcfg: dict) -> dict:
    club = cfg.get("club") or {}
    tags = []
    for t in [*ev.genres, *ev.tags]:
        t = str(t).strip().lower()
        if t and t not in tags:
            tags.append(t[:50])
    d = {
        "mapping_id": PREFIX + ev.slug,
        "title": (ev.title if len(ev.title) <= 120 else ev.title[:119] + "…"),
        "category": kategorie(ev, meta, rcfg.get("kategorie") or "party"),
        "tags": tags[:12],
        "organizer_description": beschreibung(ev, cfg),
        **preise(ev.entry, str(club.get("entry") or ""), str(club.get("entry_note") or ""), str(club.get("box_office") or "")),
        "published": bool(rcfg.get("veroeffentlichen", False)),
    }
    bild = bild_url(ev, cfg["site"]["url"])
    if bild:
        d["picture"] = bild
        d["picture_credits"] = str(meta.get("bildrechte") or meta.get("picture_credits") or "Calavera Bremen")[:120]
    return d


def show_daten(ev, location: str, rg_event_id: str | None) -> dict:
    d = {"mapping_id": f"{PREFIX}{ev.slug}-1", "start_date": ev.start.isoformat(), "end_date": ev.end.isoformat(),
         "location": location, "state": "takes_place"}
    if rg_event_id:
        d["event"] = rg_event_id
    return d


# ---------------------------------------------------------------------------
#  Vergleich (nur senden, was sich geändert hat)
# ---------------------------------------------------------------------------
def _norm(feld: str, wert):
    if wert in (None, "", []):
        return None
    if feld in ("price", "min_price", "max_price"):
        return f"{float(wert):.2f}"
    if feld in ("start_date", "end_date"):
        return datetime.fromisoformat(str(wert).replace("Z", "+00:00")).timestamp()
    if feld == "organizer_description":
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(str(wert)))).strip()
    if feld == "tags":
        return sorted(str(t).lower() for t in wert)
    if isinstance(wert, dict):   # z. B. location als Objekt
        return wert.get("id")
    return wert


def unterschiede(soll: dict, ist: dict, ohne: tuple = ()) -> list[str]:
    return [k for k, v in soll.items() if k not in ohne and k != "mapping_id" and _norm(k, v) != _norm(k, ist.get(k))]


# ---------------------------------------------------------------------------
def laden(cfg: dict, tz, now: datetime, auswahl: str | None) -> list[tuple]:
    evs = []
    for ev in build.load_events(cfg, tz):
        if ev.end <= now:
            continue
        if auswahl and auswahl.lower() not in ev.slug.lower() and auswahl.lower() not in ev.source.name.lower():
            continue
        meta, _ = build.read_front_matter(ev.source)
        if meta.get("rausgegangen") is False:
            info(f"  · {ev.source.name}: rausgegangen: false – wird ausgelassen")
            continue
        evs.append((ev, meta))
    return evs


def location_suchen(api: Api, cfg: dict) -> None:
    club = cfg.get("club") or {}
    stadt = re.sub(r"^\d{5}\s*", "", str(club.get("city") or "Bremen")).strip() or "Bremen"
    treffer = []
    for pfad in ("/v2/locations/search/", "/v2/locations/search", "/locations/search"):
        try:
            for q in ("Calavera", None):
                treffer += api.liste(pfad, {"q": q, "address_city": stadt,
                                            "address_street": None if q else club.get("address")})
            break
        except ApiFehler as e:
            if e.status != 404:
                raise
    eigene = api.liste("/v2/locations/")
    gesehen = set()
    info(f"Locations für \"Calavera\" / {club.get('address')} in {stadt}:")
    for l in [*eigene, *treffer]:
        if l.get("id") in gesehen:
            continue
        gesehen.add(l.get("id"))
        info(f"  {l.get('id')}  {l.get('title')} · {l.get('address_street')}, {l.get('address_zipcode')} {l.get('address_city')}"
             + ("  (eure eigene)" if l in eigene else ""))
    if not gesehen:
        info("  (nichts gefunden – dann bitte die Location in der Zentrale anlegen oder beim Support nachfragen)")
    info("\nDie passende ID in config.yml eintragen:\n  rausgegangen:\n    location: \"…\"")


def main() -> int:
    ap = argparse.ArgumentParser(description="Veranstaltungen auf rausgegangen.de eintragen",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("auswahl", nargs="?", help="Teil des Dateinamens – oder: location / status")
    ap.add_argument("--senden", action="store_true", help="wirklich übertragen (sonst nur Probelauf)")
    ap.add_argument("--json", action="store_true", help="im Probelauf die vollständigen Daten zeigen")
    ap.add_argument("--bilder", action="store_true", help="Bilder auch bei vorhandenen Events neu übertragen")
    ap.add_argument("--now", help="so tun, als wäre jetzt … (JJJJ-MM-TT HH:MM)")
    args = ap.parse_args()

    import yaml
    cfg = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    rcfg = cfg.get("rausgegangen") or {}
    tz = ZoneInfo(cfg["site"].get("timezone", "Europe/Berlin"))
    now = datetime.strptime(args.now, "%Y-%m-%d %H:%M").replace(tzinfo=tz) if args.now else datetime.now(tz)
    token = os.environ.get("RAUSGEGANGEN_API_KEY", "").strip()
    modus = (args.auswahl or "").lower()

    if modus in ("location", "status") or args.senden:
        if not token:
            if args.senden and os.environ.get("GITHUB_ACTIONS"):
                info("RAUSGEGANGEN_API_KEY ist (noch) nicht als GitHub-Secret hinterlegt – nichts zu tun.")
                return 0
            fehler("RAUSGEGANGEN_API_KEY fehlt – z. B.: RAUSGEGANGEN_API_KEY=… python rausgegangen.py " + " ".join(sys.argv[1:]))
    api = Api(token) if token else None

    if modus == "location":
        location_suchen(api, cfg)
        return 0

    location = str(rcfg.get("location") or "").strip()
    if not location and (args.senden or modus == "status"):
        fehler("in config.yml fehlt rausgegangen → location (ID mit \"python rausgegangen.py location\" ermitteln)")

    evs = laden(cfg, tz, now, None if modus == "status" else args.auswahl)
    if not evs and modus != "status":
        info("Keine kommenden Veranstaltungen" + (f" mit \"{args.auswahl}\"" if args.auswahl else "") + ".")
        return 0

    vorhanden_ev, vorhanden_sh = {}, {}
    if api:
        vorhanden_ev = {e.get("mapping_id"): e for e in api.liste("/v2/events/") if e.get("mapping_id")}
        vorhanden_sh = {s.get("mapping_id"): s for s in api.liste("/v2/shows/") if s.get("mapping_id")}

    if modus == "status":
        lokal = {PREFIX + ev.slug for ev, _ in evs}
        info(f"rausgegangen: {sum(1 for m in vorhanden_ev if m.startswith(PREFIX))} Events von uns · hier: {len(lokal)} kommende Veranstaltungen")
        for ev, _ in evs:
            e = vorhanden_ev.get(PREFIX + ev.slug)
            sh = (e or {}).get("shows") or []
            url = (sh[0].get("public_url") if (e or {}).get("published") else sh[0].get("preview_url")) if sh else ""
            info(f"  {'✓' if e else '·'} {ev.start:%d.%m.} {ev.title}" + (f"  → {url}" if url else ("" if e else "  (fehlt noch)")))
        uebrig = [e for m, e in vorhanden_ev.items() if m.startswith(PREFIX) and m not in lokal
                  and any(datetime.fromisoformat(str(s.get("start_date")).replace("Z", "+00:00")) > now for s in e.get("shows") or [])]
        if uebrig:
            info("\nDort noch kommend, hier aber nicht mehr vorhanden (umbenannt, gelöscht, Entwurf?) – bitte in der Zentrale prüfen:")
            for e in uebrig:
                info(f"  ! {e.get('title')}  (mapping_id {e.get('mapping_id')})")
        return 0

    info(("Übertrage" if args.senden else "Probelauf (nichts wird gesendet – mit --senden übertragen)")
         + f": {len(evs)} Veranstaltung(en) · {'öffentlich' if rcfg.get('veroeffentlichen') else 'nicht veröffentlicht (nur Vorschau)'}")
    zahlen = {"neu": 0, "geändert": 0, "unverändert": 0, "fehler": 0}
    for ev, meta in evs:
        soll = event_daten(ev, meta, cfg, rcfg)
        ist = vorhanden_ev.get(soll["mapping_id"])
        kopf = f"  {build.WOCHENTAG[ev.start.weekday()]} {ev.start:%d.%m. %H:%M} {ev.title}  [{soll['category']}]"
        if ist is None:
            aktion, felder = "neu", list(soll)
        else:
            felder = unterschiede(soll, ist, ohne=() if args.bilder else ("picture", "picture_credits"))
            if "published" in felder and not rcfg.get("veroeffentlichen") and ist.get("published"):
                felder.remove("published")   # in der Zentrale von Hand veröffentlicht – nicht wieder verstecken
            aktion = "geändert" if felder else "unverändert"
        sh_soll = show_daten(ev, location or "<location aus config.yml>", (ist or {}).get("id"))
        sh_ist = vorhanden_sh.get(sh_soll["mapping_id"])
        sh_felder = list(sh_soll) if sh_ist is None else unterschiede(sh_soll, sh_ist)
        if aktion == "unverändert" and sh_felder:
            aktion = "geändert"
        info(f"{kopf}  → {aktion}" + (f" ({', '.join(felder + [f'Termin.{f}' for f in sh_felder if ist])})" if aktion == "geändert" else ""))
        if args.json and not args.senden:
            info(json.dumps({"event": soll, "show": sh_soll}, ensure_ascii=False, indent=2))
        if not args.senden or aktion == "unverändert":
            zahlen[aktion] += 1
            continue
        try:
            if ist is None:
                antwort = api.schreiben("POST", "/v2/events/", soll)
            elif felder:
                antwort = api.schreiben("PATCH", "/v2/events/", {"id": ist["id"], "mapping_id": soll["mapping_id"],
                                                                  **{k: soll[k] for k in felder}}, ist["id"])
            else:
                antwort = ist
            rg_id = (antwort or {}).get("id") or (ist or {}).get("id")
            if not rg_id:
                raise ApiFehler(0, f"keine Event-ID in der Antwort: {json.dumps(antwort)[:300]}")
            sh_soll["event"] = rg_id
            if sh_ist is None:
                sh = api.schreiben("POST", "/v2/shows/", sh_soll)
            elif sh_felder:
                sh = api.schreiben("PATCH", "/v2/shows/", {"id": sh_ist["id"], "mapping_id": sh_soll["mapping_id"],
                                                           **{k: sh_soll[k] for k in sh_felder}}, sh_ist["id"])
            else:
                sh = sh_ist
            url = (sh or {}).get("public_url") if soll["published"] else (sh or {}).get("preview_url")
            if url:
                info(f"      {url}")
            zahlen[aktion] += 1
        except ApiFehler as e:
            zahlen["fehler"] += 1
            info(f"      ! {e}")
    info("Fertig: " + " · ".join(f"{v} {k}" for k, v in zahlen.items() if v))
    return 1 if zahlen["fehler"] else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ApiFehler as e:
        hinweis = {401: "Token ungültig oder abgelaufen?", 403: "Token ungültig, oder keine Rechte für diese Aktion?"}.get(e.status, "")
        fehler(f"rausgegangen-API: {e}" + (f"\n  → {hinweis}" if hinweis else ""))
