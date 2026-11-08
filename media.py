#!/usr/bin/env python3
"""
Calavera Bremen – Bilder für Instagram/Facebook (1080 × 1350, JPG)

Eigenständig wie reels.py: liest events/*.md, config.yml und den Kellerfunk-Sendeplan,
schreibt nur nach media/out/. Braucht dieselben Pakete wie reels.py (Playwright + Chromium), kein ffmpeg.

  python media.py                          "Diese Woche im Calavera" für die laufende Woche, alle Vorlagen
  python media.py woche --vorlage plakatwand
  python media.py --vorlage a,c            Kürzel: a = programmzettel, b = plakatwand, c = wochenstreifen
  python media.py --naechste               die kommende Woche (Mo–So)
  python media.py --woche 47               Kalenderwoche 47 (oder 2026-W47)
  python media.py --ab 2026-11-16          die Woche, in der dieser Tag liegt
  python media.py --akzent "#b3122e"       andere Akzentfarbe
  python media.py --liste                  nur anzeigen, welche Termine es zeigen würde

  --alle             auch Termine dieser Woche zeigen, die schon vorbei sind
  --ohne-kellerfunk  Sendeplan von live.calavera.club nicht einlesen
  --plan DATEI       Sendeplan aus dieser Datei/Adresse statt aus config.yml → kellerfunk.config
  --qualitaet 92     JPG-Qualität (Standard 92)
  --now "JJJJ-MM-TT HH:MM"   so tun, als wäre jetzt …

In config.yml (alles optional):
  media:
    vorlage: wochenstreifen      # Standard-Vorlage(n), Komma-getrennt oder "alle"
    akzent: "#e0485e"            # sonst je Vorlage: Programmzettel/Wochenstreifen #e0485e, Plakatwand #b3122e
    qualitaet: 92
    hashtags: [bremen, viertel]  # zusätzlich zu abbinder.hashtags im Bildtext
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402  – nur zum Lesen (Event-Dateien); baut nichts

VORLAGEN = ROOT / "media" / "vorlagen"
AUSGABE = ROOT / "media" / "out"
CACHE = ROOT / "media" / ".cache"
BREITE, HOEHE = 1080, 1350
ALLE_VORLAGEN = ("programmzettel", "plakatwand", "wochenstreifen")
VORLAGE_ALIAS = {"a": "programmzettel", "zettel": "programmzettel", "liste": "programmzettel",
                 "b": "plakatwand", "plakat": "plakatwand", "wand": "plakatwand",
                 "c": "wochenstreifen", "streifen": "wochenstreifen", "woche": "wochenstreifen"}
AKZENT = {"programmzettel": "#e0485e", "plakatwand": "#b3122e", "wochenstreifen": "#e0485e"}
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
MAX_TERMINE = 6


def info(msg: str) -> None:
    print(msg, flush=True)


def fehler(msg: str) -> None:
    print(f"FEHLER: {msg}", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
#  Woche und Termine
# ---------------------------------------------------------------------------
def woche_waehlen(args, now: datetime) -> date:
    """Montag der gewünschten Woche"""
    if args.woche:
        m = re.fullmatch(r"(?:(\d{4})-?W?)?(\d{1,2})", args.woche.strip(), re.I)
        if not m:
            fehler(f"--woche \"{args.woche}\" verstehe ich nicht (z. B. 47 oder 2026-W47)")
        jahr = int(m.group(1) or now.isocalendar()[0])
        try:
            tag = date.fromisocalendar(jahr, int(m.group(2)), 1)
        except ValueError as e:
            fehler(f"--woche: {e}")
    elif args.ab:
        try:
            tag = datetime.strptime(args.ab, "%Y-%m-%d").date()
        except ValueError:
            fehler(f"--ab \"{args.ab}\": bitte JJJJ-MM-TT")
    else:
        tag = now.date()
    if args.naechste:
        tag += timedelta(days=7)
    return tag - timedelta(days=tag.weekday())


def uhr(d: datetime) -> str:
    return f"{d:%H:%M}"


def uhr_kurz(d: datetime) -> str:
    return f"{d:%H} UHR" if d.minute == 0 else f"{d:%H:%M}"


def dreh(text: str, spanne: float = 2.6) -> float:
    """feste, aber je Titel andere Schräglage für die Plakatwand"""
    h = int(hashlib.sha1(text.encode()).hexdigest()[:6], 16)
    w = 0.8 + (h % 1000) / 1000 * (spanne - 0.8)
    return round(w if (h >> 12) % 2 else -w, 2)


def flyer_kopieren(quelle: Path, assets: Path, name: str) -> tuple[str, float]:
    from PIL import Image
    im = Image.open(quelle).convert("RGB")
    if im.width > 1100:
        im = im.resize((1100, round(1100 * im.height / im.width)), Image.LANCZOS)
    im.save(assets / f"{name}.jpg", quality=92)
    return f"assets/{name}.jpg", im.height / im.width


def termin(start: datetime, titel: str, art: str) -> dict:
    return {"start": start, "wt": build.WOCHENTAG[start.weekday()].upper(), "wt_index": start.weekday(),
            "tag": f"{start.day}.", "datum": f"{start:%d.%m.}", "zeit": uhr(start), "uhr": uhr_kurz(start),
            "titel": titel, "byline": "", "genres": "", "pillen": [], "flyer": "", "ratio": 1.414,
            "art": art, "dreh": dreh(titel + start.isoformat())}


def event_termine(events, cfg: dict, assets: Path) -> list[dict]:
    default_entry = str((cfg.get("events") or {}).get("default_entry") or "").strip()
    liste = []
    for e in events:
        t = termin(e.start, e.social_title or e.title, "event")
        t["byline"] = e.byline
        t["genres"] = " · ".join(e.genres[:4])
        if e.entry and e.entry != default_entry:
            t["pillen"].append(e.entry)
        if e.stream_url:
            t["pillen"].append(e.stream_label or "Vor Ort & im Stream")
        if e.visual_src and Path(e.visual_src).is_file():
            t["flyer"], t["ratio"] = flyer_kopieren(Path(e.visual_src), assets, e.slug)
        else:
            info(f"  · {e.start:%d.%m.} {e.title}: ohne Flyer – es erscheint eine Papierkarte")
        liste.append(t)
    return liste


def kellerfunk_termine(cfg: dict, args, tz, von: datetime, bis: datetime, now: datetime, assets: Path) -> tuple[list[dict], str]:
    """Sendungen dieser Woche aus der config.yml von live.calavera.club (wie reels.py kellerfunk)"""
    import yaml
    import reels
    kcfg = cfg.get("kellerfunk") or {}
    quelle = args.plan or kcfg.get("config") or "https://live.calavera.club/config.yml"
    try:
        plan = yaml.safe_load(reels._laden(quelle).decode("utf-8")) or {}
    except Exception as e:   # noqa: BLE001 – ohne Sendeplan geht es trotzdem
        info(f"  ! Kellerfunk-Sendeplan nicht ladbar ({e.__class__.__name__}) – weiter ohne Kellerfunk. Offline: --plan datei.yml")
        return [], ""
    basis = quelle if re.match(r"^https?://", quelle) else str(Path(quelle).resolve())
    logo = ""
    lq = kcfg.get("logo") or reels._aufloesen("kellerfunk.png", basis)
    if lq and (re.match(r"^https?://", lq) or Path(lq).is_file()):
        r = reels._bild_holen(lq, assets, "kellerfunk-logo", unscharf=False)
        logo = r[0] if r else ""
    liste = []
    for i, s in enumerate(plan.get("shows") or []):
        s = s or {}
        start = reels._sendezeit(s.get("start"), tz)
        if not start or not (von <= start < bis):
            continue
        ende = reels._sendezeit(s.get("end"), tz) or start + timedelta(hours=2)
        if ende <= now and not args.alle:
            continue
        titel = str(s.get("title") or "Kellerfunk")
        t = termin(start, "Kellerfunk" if reels._platzhalter(titel) else titel, "kellerfunk")
        djs = [str(d) for d in build.as_list(s.get("djs")) if d and not reels._platzhalter(str(d))]
        t["byline"] = " & ".join(djs)
        t["genres"] = " · ".join(str(g) for g in build.as_list(s.get("genres") or s.get("genre"))[:4] if g and not reels._platzhalter(str(g)))
        t["club"] = s.get("club") is True
        t["pillen"] = ["Club & Stream" if t["club"] else "Live im Stream"]
        vq = reels._aufloesen(str(s.get("visual") or s.get("flyer") or ""), basis)
        if vq:
            r = reels._bild_holen(vq, assets, f"kellerfunk-{i + 1}")
            if r:
                t["flyer"] = r[0]
        liste.append(t)
    return liste, logo


def zusammenfuehren(termine: list[dict], sendungen: list[dict]) -> list[dict]:
    """Sendung, die zugleich ein Abend im Club ist (gleicher Tag, ±3 h): nur einmal zeigen – als Event mit Stream-Hinweis"""
    for s in sendungen:
        gleich = next((t for t in termine if t["start"].date() == s["start"].date()
                       and abs((t["start"] - s["start"]).total_seconds()) <= 3 * 3600), None)
        if gleich:
            if not any("stream" in p.lower() for p in gleich["pillen"]):
                gleich["pillen"].append("Club & Stream")
        else:
            termine.append(s)
    termine.sort(key=lambda t: (t["start"], t["titel"]))
    return termine


# ---------------------------------------------------------------------------
#  Daten für die Vorlagen
# ---------------------------------------------------------------------------
def zeitraum_lang(a: date, b: date) -> str:
    if a == b:
        return f"{a.day}. {MONATE[a.month - 1]}".upper()
    if a.month == b.month:
        return f"{a.day}. – {b.day}. {MONATE[b.month - 1]}".upper()
    return f"{a.day}. {MONATE[a.month - 1]} – {b.day}. {MONATE[b.month - 1]}".upper()


def zeitraum_kurz(a: date, b: date) -> str:
    if a == b:
        return f"{a.day}.{a.month}."
    return f"{a.day}.–{b.day}.{b.month}." if a.month == b.month else f"{a.day}.{a.month}.–{b.day}.{b.month}."


def plakat_reihen(termine: list[dict]) -> tuple[list[list[dict]], int]:
    n = len(termine)
    aufteilung = {1: [1], 2: [2], 3: [3], 4: [2, 2], 5: [3, 2], 6: [3, 3]}[n]
    breite = {1: 520, 2: 420, 3: 272, 4: 272, 5: 272, 6: 252}[n]
    reihen, i = [], 0
    for k, anzahl in enumerate(aufteilung):
        reihe = termine[i:i + anzahl]
        for j, t in enumerate(reihe):   # Sticker außen: erster links, sonst rechts – so stoßen keine zwei aneinander
            t["seite"] = "l" if j == 0 and len(reihe) > 1 else "r"
            t["versatz"] = 0 if (i + j) % 2 == 0 else (60 if n <= 2 else 22)
        reihen.append(reihe)
        i += anzahl
    return reihen, breite


def streifen_tage(montag: date, termine: list[dict]) -> list[dict]:
    tage = []
    for k in range(7):
        d = montag + timedelta(days=k)
        tl = [t for t in termine if t["start"].date() == d]
        tage.append({"wt": build.WOCHENTAG[k].upper(), "tag": f"{d.day}.", "datum": f"{d:%d.%m.}", "termine": tl, "aktiv": bool(tl)})
    return tage


def vorlagen_daten(cfg: dict, montag: date, termine: list[dict], logo_kf: str) -> dict:
    club = cfg.get("club") or {}
    sonntag = montag + timedelta(days=6)
    erster, letzter = termine[0]["start"].date(), termine[-1]["start"].date()
    eintritt = " · ".join(x for x in [club.get("entry"), club.get("entry_note")] if x)
    url = re.sub(r"^https?://", "", str((cfg.get("site") or {}).get("base_url") or "calavera.club")).strip("/")
    url = re.sub(r"^www\.", "", url)
    reihen, plakat_breite = plakat_reihen(termine)
    tage = streifen_tage(montag, termine)
    aktiv = sum(1 for t in tage if t["aktiv"])
    return {
        "termine": termine, "anzahl": len(termine),
        "zeitraum_lang": zeitraum_lang(erster, letzter),
        "zeitraum_kurz": zeitraum_kurz(erster, letzter),
        "kw": montag.isocalendar()[1],
        "woche_text": f"WOCHE {montag.isocalendar()[1]} · {montag:%d.}–{sonntag:%d.%m.%Y}" if montag.month == sonntag.month
                      else f"WOCHE {montag.isocalendar()[1]} · {montag:%d.%m.}–{sonntag:%d.%m.%Y}",
        "adresse": str(club.get("address") or "Körnerwall 1").upper(),
        "stadt": "BREMEN",
        "eintritt": eintritt.upper(),
        "url": url.upper(),
        "logo": "assets/calavera_logo.svg", "logo_kf": logo_kf,
        "kf_url": re.sub(r"^https?://", "", str((cfg.get("kellerfunk") or {}).get("url") or "live.calavera.club")).strip("/"),
        "reihen": reihen, "plakat_breite": plakat_breite,
        "tage": tage, "aktive_tage": aktiv,
    }


# ---------------------------------------------------------------------------
#  Rendern
# ---------------------------------------------------------------------------
def arbeitsordner(job: str) -> Path:
    d = CACHE / job
    if d.exists():
        shutil.rmtree(d)
    (d / "assets").mkdir(parents=True)
    for f in VORLAGEN.iterdir():
        if f.is_file() and not f.name.endswith(".html"):
            shutil.copy(f, d / f.name)
    for f in (ROOT / "static" / "fonts").glob("*.woff2"):
        shutil.copy(f, d / "assets" / f.name)
    shutil.copy(ROOT / "static" / "img" / "calavera_logo.svg", d / "assets" / "calavera_logo.svg")
    return d


def rendern(ordner: Path, vorlagen: list[str], daten: dict, akzent: dict, qualitaet: int, job: str) -> list[Path]:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from playwright.sync_api import sync_playwright
    env = Environment(loader=FileSystemLoader(str(VORLAGEN)), autoescape=select_autoescape(["html"]))
    env.globals["px"] = lambda n: f"calc(var(--s) * {n}px)"
    AUSGABE.mkdir(parents=True, exist_ok=True)
    fertig = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": BREITE, "height": HOEHE}, device_scale_factor=1)
        for v in vorlagen:
            html = env.get_template(f"{v}.html").render(akzent=akzent[v], **daten)
            datei = ordner / f"{v}.html"
            datei.write_text(html, encoding="utf-8")
            page.goto(datei.as_uri())
            page.wait_for_function("window.fertig === true", timeout=30000)
            for w in page.evaluate("window.warnungen || []"):
                info(f"  ! {v}: {w}")
            ziel = AUSGABE / f"{job}-{v}.jpg"
            page.screenshot(path=str(ziel), type="jpeg", quality=qualitaet, clip={"x": 0, "y": 0, "width": BREITE, "height": HOEHE})
            info(f"  → {ziel.relative_to(ROOT)}")
            fertig.append(ziel)
        browser.close()
    return fertig


def bildtext(cfg: dict, termine: list[dict], daten: dict) -> str:
    mcfg = cfg.get("media") or {}
    zeilen = [f"Diese Woche im Calavera 💀 ({daten['zeitraum_kurz']})", ""]
    for t in termine:
        if t["art"] == "kellerfunk":   # deutlich als Livestream kennzeichnen – sonst steht jemand vor verschlossener Tür
            z = f"📻 {t['wt'].title()} {t['datum']} · {t['zeit']} · KELLERFUNK: {t['titel']}"
        else:
            z = f"▸ {t['wt'].title()} {t['datum']} · {t['zeit']} · {t['titel']}"
        if t["byline"]:
            z += f" mit {t['byline']}" if t["byline"].lower().startswith("dj") else f" – {t['byline']}"
        if t["art"] == "kellerfunk":
            z += (" – im Club & im Livestream auf " if t.get("club") else " – nur im Livestream auf ") + daten["kf_url"]
        elif t["pillen"]:
            z += " (" + ", ".join(t["pillen"]) + ")"
        zeilen.append(z)
    club = cfg.get("club") or {}
    zeilen += ["", f"📍 {club.get('address', 'Körnerwall 1')}, Bremen"]
    eintritt = " · ".join(x for x in [club.get("entry"), club.get("entry_note")] if x)
    if eintritt:
        zeilen.append(f"🎟 {eintritt} (wenn nicht anders angegeben)")
    zeilen += [f"Alle Termine: {daten['url'].lower()} (Link in Bio)", ""]
    tags = ["calavera", "bremen", *((cfg.get("abbinder") or {}).get("hashtags") or []), *(mcfg.get("hashtags") or [])]
    if any(t["art"] == "kellerfunk" for t in termine):
        tags.append("kellerfunk")
    zeilen.append(" ".join(dict.fromkeys("#" + re.sub(r"[^0-9a-zäöüß]", "", str(h).lower()) for h in tags if str(h).strip())))
    return "\n".join(zeilen) + "\n"


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Bilder für Instagram/Facebook aus den Event-Dateien",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("art", nargs="?", default="woche", choices=["woche"], help="was erzeugt wird (bisher nur: woche)")
    ap.add_argument("--vorlage", help=f"Vorlage(n), Komma-getrennt, oder \"alle\": {', '.join(ALLE_VORLAGEN)} (Kürzel a, b, c)")
    ap.add_argument("--woche", help="Kalenderwoche, z. B. 47 oder 2026-W47")
    ap.add_argument("--ab", help="die Woche, in der dieser Tag liegt (JJJJ-MM-TT)")
    ap.add_argument("--naechste", action="store_true", help="eine Woche später")
    ap.add_argument("--alle", action="store_true", help="auch schon vergangene Termine der Woche zeigen")
    ap.add_argument("--akzent", help="Akzentfarbe, z. B. \"#b3122e\"")
    ap.add_argument("--ohne-kellerfunk", action="store_true", help="Kellerfunk-Sendeplan nicht einlesen")
    ap.add_argument("--plan", help="Kellerfunk-Sendeplan aus dieser Datei/Adresse")
    ap.add_argument("--qualitaet", type=int, help="JPG-Qualität 1–100 (Standard 92)")
    ap.add_argument("--liste", action="store_true", help="nur anzeigen, welche Termine es zeigen würde")
    ap.add_argument("--now", help="so tun, als wäre jetzt … (JJJJ-MM-TT HH:MM)")
    args = ap.parse_args()

    import yaml
    cfg = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    mcfg = cfg.get("media") or {}
    tz = ZoneInfo(cfg["site"].get("timezone", "Europe/Berlin"))
    now = datetime.strptime(args.now, "%Y-%m-%d %H:%M").replace(tzinfo=tz) if args.now else datetime.now(tz)

    wahl = str(args.vorlage or mcfg.get("vorlage") or "alle").lower()
    if wahl.strip() == "alle":
        vorlagen = list(ALLE_VORLAGEN)
    else:
        vorlagen = []
        for v in wahl.split(","):
            v = VORLAGE_ALIAS.get(v.strip(), v.strip())
            if v not in ALLE_VORLAGEN:
                fehler(f"Vorlage \"{v}\" gibt es nicht – möglich: {', '.join(ALLE_VORLAGEN)} (oder a, b, c, alle)")
            if v not in vorlagen:
                vorlagen.append(v)
    farbe = args.akzent or mcfg.get("akzent")
    if farbe and not re.fullmatch(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", str(farbe).strip()):
        fehler(f"Akzentfarbe \"{farbe}\": bitte als #rrggbb")
    akzent = {v: str(farbe).strip() if farbe else AKZENT[v] for v in vorlagen}
    qualitaet = max(1, min(100, int(args.qualitaet or mcfg.get("qualitaet") or 92)))

    montag = woche_waehlen(args, now)
    von = datetime.combine(montag, datetime.min.time(), tzinfo=tz)
    bis = von + timedelta(days=7)
    events = [e for e in build.load_events(cfg, tz) if von <= e.start < bis and (args.alle or e.end > now)]

    job = f"woche-{montag.isocalendar()[0]}-kw{montag.isocalendar()[1]:02d}"
    ordner = arbeitsordner(job)
    info(f"Diese Woche im Calavera: KW {montag.isocalendar()[1]} ({montag:%d.%m.} – {(bis - timedelta(days=1)):%d.%m.%Y})")
    termine = event_termine(events, cfg, ordner / "assets")
    logo_kf = ""
    if not args.ohne_kellerfunk:
        sendungen, logo_kf = kellerfunk_termine(cfg, args, tz, von, bis, now, ordner / "assets")
        termine = zusammenfuehren(termine, sendungen)
    if not termine:
        fehler("in dieser Woche gibt es (noch) keine Termine – andere Woche mit --naechste / --woche / --ab")
    if len(termine) > MAX_TERMINE:
        info(f"  ! {len(termine)} Termine – auf das Bild passen höchstens {MAX_TERMINE}; die letzten fallen weg (alle stehen im Bildtext)")
    for t in termine:
        info(f"  {t['wt'].title()} {t['datum']} {t['zeit']}  {t['titel']}" + (f" – {t['byline']}" if t["byline"] else "")
             + ("  [Kellerfunk]" if t["art"] == "kellerfunk" else "") + ("" if t["flyer"] or t["art"] == "kellerfunk" else "  [ohne Flyer]"))
    if args.liste:
        return 0

    try:
        import playwright  # noqa: F401
    except ImportError:
        fehler("Playwright fehlt – einmal: pip install -r requirements-reels.txt && python -m playwright install chromium")
    daten = vorlagen_daten(cfg, montag, termine[:MAX_TERMINE], logo_kf)
    rendern(ordner, vorlagen, daten, akzent, qualitaet, job)
    text = AUSGABE / f"{job}-bildtext.txt"
    text.write_text(bildtext(cfg, termine, daten), encoding="utf-8")
    info(f"  → {text.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
