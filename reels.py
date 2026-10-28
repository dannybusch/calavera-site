#!/usr/bin/env python3
"""
Calavera Bremen – Reels für Instagram (1080 × 1920, 30 fps, H.264 + AAC)

Eigenständig, unabhängig vom Website-Build: liest nur events/*.md und config.yml,
schreibt nur nach reels/out/. Braucht: Python-Pakete aus requirements.txt + requirements-reels.txt,
den Browser von Playwright (einmal: python -m playwright install chromium) und ffmpeg.

  python reels.py                      alle kommenden Veranstaltungen mit "reels:" in der Event-Datei
  python reels.py melancholie          nur Veranstaltungen, deren Dateiname "melancholie" enthält
  python reels.py halloween --vorlage flyerfahrt,teaser
  python reels.py woche                Programm der nächsten 7 Tage (--ab 2026-11-02 --tage 7)
  python reels.py kellerfunk           Kellerfunk-Sendeplan eines Monats (--monat 2026-11, --plan datei.yml)
  python reels.py --liste              zeigt, was es rendern würde
  python reels.py melancholie --pruefen   prüft nur Musik/BPM/Eins

  --schnell       Vorschau: ohne Bewegungsunschärfe, ca. 4× schneller
  --klick         Metronom statt Musik (zum Prüfen des Takts)
  --hilfslinien   blendet die Flächen ein, die Instagram mit Bedienelementen überdeckt

In der Event-Datei (alles optional):
  reels: [flyerfahrt, freunde, countdown, teaser]
  musik: "melancholie.mp3"        # liegt in events/ oder reels/musik/ (sonst: events/<dateiname>.mp3)
  bpm: 124                        # Tempo des Titels
  eins: "0:42.310"                # Zeitpunkt einer "1" (Taktanfang) – dort beginnt das Reel
  reel_fokus: [[50, 20], [40, 70], [60, 45]]   # Flyer-Fahrt: 3 Punkte (x/y in % des Flyers)
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import struct
import subprocess
import sys
import wave
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402  – nur zum Lesen (Event-Dateien, Texte, Nebelbilder); baut nichts

VORLAGEN = ROOT / "reels" / "vorlagen"
AUSGABE = ROOT / "reels" / "out"
CACHE = ROOT / "reels" / ".cache"
MUSIK = ROOT / "reels" / "musik"
FPS = 30
ALLE_VORLAGEN = ("flyerfahrt", "freunde", "countdown", "teaser")
VORLAGE_ALIAS = {"fahrt": "flyerfahrt", "flyer": "flyerfahrt", "fans": "freunde", "fuer_freunde_von": "freunde", "text": "teaser"}
# Atmosphäre im Reel passend zu den Effekten der Website
ATMO = {"rauschnebel": "nebel", "buehnennebel": "nebel", "flyerausnebel": "nebel", "fratzen": "nebel", "gewitter": "nebel",
        "grunge": "funken", "vhs": "funken", "flanell": "funken",
        "konfetti": "konfetti", "regenbogenfolie": "konfetti", "seifenblasen": "konfetti", "discokugel": "konfetti", "spraydose": "konfetti",
        "bassboom": "konfetti", "snow": "schnee", "twinklestar": "sterne", "schwerelos": "sterne", "feuerwerk": "sterne",
        "lichterkette": "sterne", "gluehwuermchen": "sterne", "kerzenlicht": "funken", "dampf": "funken", "superdark": "nebel"}


def info(msg: str) -> None:
    print(msg, flush=True)


def fehler(msg: str) -> None:
    sys.exit(f"Fehler: {msg}")


# ---------------------------------------------------------------------------
#  Musik: zuschneiden, Takt prüfen, Bässe pro Bild
# ---------------------------------------------------------------------------
def zeit(s) -> float:
    """'0:42.310' / '42.31' / 42.31 → Sekunden"""
    if isinstance(s, (int, float)):
        return float(s)
    parts = str(s).strip().split(":")
    sec = 0.0
    for p in parts:
        sec = sec * 60 + float(p.replace(",", "."))
    return sec


def pcm(datei: Path, start: float, dauer: float, sr: int, filt: str = "") -> list[float]:
    """Mono-Samples (−1…1) eines Ausschnitts, über ffmpeg dekodiert"""
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{max(0, start):.3f}", "-t", f"{dauer:.3f}", "-i", str(datei), "-ac", "1", "-ar", str(sr)]
    if filt:
        cmd += ["-af", filt]
    cmd += ["-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return [v / 32768 for v in struct.unpack(f"<{len(raw) // 2}h", raw)]


def bass_huelle(datei: Path, start: float, dauer: float, hop_s: float) -> list[float]:
    """Lautstärke der Bässe (unter 150 Hz) in Schritten von hop_s Sekunden"""
    sr = 11025
    x = pcm(datei, start, dauer, sr, "lowpass=f=150,lowpass=f=150")
    hop = max(1, int(sr * hop_s))
    return [math.sqrt(sum(v * v for v in x[i:i + hop]) / hop) for i in range(0, max(0, len(x) - hop), hop)]


def takt_pruefen(datei: Path, bpm: float, eins: float) -> tuple[float, list[str]]:
    """Schätzt das Tempo, rastet 'eins' auf den nächsten Bassschlag ein (±70 ms). Gibt (eins, Hinweise) zurück."""
    hop = 0.01
    notes: list[str] = []
    env = bass_huelle(datei, eins, 24, hop)
    if len(env) < 400:
        return eins, ["Musik zu kurz für eine Takt-Prüfung"]
    onset = [max(0.0, env[i] - env[i - 1]) for i in range(1, len(env))]
    mean = sum(onset) / len(onset)
    onset = [o - mean for o in onset]
    # Tempo per Autokorrelation (60–200 BPM)
    best, best_lag = -1e9, 0
    for lag in range(int(60 / 200 / hop), int(60 / 60 / hop) + 1):
        c = sum(onset[i] * onset[i + lag] for i in range(len(onset) - lag))
        if c > best:
            best, best_lag = c, lag
    if best_lag:
        geschaetzt = 60 / (best_lag * hop)
        kandidaten = [geschaetzt * f for f in (.5, 1, 2)]
        nah = min(kandidaten, key=lambda k: abs(k - bpm))
        if abs(nah - bpm) / bpm > .025:
            notes.append(f"Achtung: erkanntes Tempo ≈ {nah:.1f} BPM, eingetragen sind {bpm:g} BPM")
        else:
            notes.append(f"Tempo passt (erkannt ≈ {nah:.1f} BPM)")
    # Eins einrasten: Anfang des nächsten Bassschlags (Hülle mit 8-ms-Fenster, 1 ms Raster,
    # Einsatz = erster Punkt bei 30 % des Anstiegs) – nur wenn er höchstens 70 ms entfernt liegt
    sr, win = 11025, .008
    x = pcm(datei, eins - .07, .19, sr, "lowpass=f=150")
    hop, w = int(sr * .001), int(sr * win)
    env2 = [math.sqrt(sum(v * v for v in x[i:i + w]) / w) for i in range(0, max(0, len(x) - w), hop)]
    if len(env2) > 20:
        peak = max(range(len(env2)), key=lambda i: env2[i])
        lo = min(env2[:peak + 1])
        if env2[peak] > lo * 3:
            th = lo + .3 * (env2[peak] - lo)
            k = next(i for i in range(peak + 1) if env2[i] >= th)
            neu = eins - .07 + k * .001 + win / 2
            if abs(neu - eins) <= .07:
                if abs(neu - eins) >= .004:
                    notes.append(f"Eins eingerastet: {eins:.3f} s → {neu:.3f} s ({(neu - eins) * 1000:+.0f} ms)")
                eins = neu
    return eins, notes


def musik_vorbereiten(datei: Path, eins: float, dauer: float, takt: float, ziel: Path) -> list[float]:
    """Schneidet ab 'eins' heraus, blendet im letzten Takt aus, normalisiert auf −14 LUFS (Instagram).
    Gibt die Bass-Lautstärke pro Videobild (0…1) zurück."""
    fade = min(takt, dauer / 3)
    af = f"afade=t=in:st=0:d=0.008,afade=t=out:st={dauer - fade:.3f}:d={fade:.3f},loudnorm=I=-14:TP=-1.5:LRA=11"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{eins:.3f}", "-t", f"{dauer:.3f}", "-i", str(datei),
                    "-af", af, "-ar", "48000", "-ac", "2", str(ziel)], check=True)
    env = bass_huelle(datei, eins, dauer, 1 / FPS)
    if not env:
        return []
    srt = sorted(env)
    ref = srt[int(len(srt) * .95)] or 1
    out, cur = [], 0.0
    for v in env:   # schneller Anstieg, langsames Abklingen (wie ein Pegelmesser)
        v = min(1.0, v / ref)
        cur = v if v > cur else cur * .82 + v * .18
        out.append(round(cur, 3))
    return out


def klick_spur(bpm: float, beats: int, ziel: Path) -> None:
    """Metronom: die 1 jedes Takts höher"""
    sr = 48000
    n = int(beats * 60 / bpm * sr)
    buf = [0.0] * n
    for j in range(beats):
        st = int(round(j * 60 / bpm * sr))
        f, amp = (1760, .55) if j % 4 == 0 else (1100, .35)
        for k in range(int(.035 * sr)):
            if st + k < n:
                buf[st + k] += amp * math.sin(2 * math.pi * f * k / sr) * math.exp(-k / (.008 * sr))
    with wave.open(str(ziel), "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, x)) * 32000)) for x in buf))


def finde_musik(ev, meta: dict) -> Path | None:
    name = str(meta.get("musik") or meta.get("music") or "").strip()
    kandidaten = []
    if name:
        kandidaten += [ROOT / "events" / name, MUSIK / name, ROOT / name]
    kandidaten += [ev.source.with_suffix(x) for x in (".mp3", ".m4a", ".wav", ".ogg")]
    for k in kandidaten:
        if k.is_file():
            return k
    if name:
        info(f"  ! Musik \"{name}\" nicht gefunden (gesucht in events/ und reels/musik/)")
    return None


# ---------------------------------------------------------------------------
#  Bilder und Arbeitsordner
# ---------------------------------------------------------------------------
def flyer_bilder(ev, ziel: Path) -> tuple[str, str, float]:
    """Flyer als JPEG (volle Auflösung) + unscharfe Hintergrund-Version; ohne Flyer ein Platzhalter mit Logo."""
    from PIL import Image, ImageEnhance, ImageFilter, ImageDraw
    name = ev.slug
    if ev.visual_src and Path(ev.visual_src).is_file():
        im = Image.open(ev.visual_src).convert("RGB")
    else:
        im = Image.new("RGB", (1000, 1414), (22, 22, 22))
        ImageDraw.Draw(im).rectangle([40, 40, 960, 1374], outline=(179, 18, 46), width=6)
    if im.height > 2400:
        im = im.resize((round(im.width * 2400 / im.height), 2400), Image.LANCZOS)
    im.save(ziel / f"{name}.jpg", quality=94)
    bg = im.resize((540, round(540 * im.height / im.width))).filter(ImageFilter.GaussianBlur(28))
    ImageEnhance.Color(bg).enhance(1.4).resize((1080, round(1080 * im.height / im.width))).save(ziel / f"{name}-unscharf.jpg", quality=88)
    return f"assets/{name}.jpg", f"assets/{name}-unscharf.jpg", im.height / im.width


def arbeitsordner(job: str) -> Path:
    d = CACHE / job
    if d.exists():
        shutil.rmtree(d)
    (d / "assets").mkdir(parents=True)
    for f in VORLAGEN.iterdir():
        if f.is_file():
            shutil.copy(f, d / f.name)
    for f in (ROOT / "static" / "fonts").glob("*.woff2"):
        shutil.copy(f, d / "assets" / f.name)
    shutil.copy(ROOT / "static" / "img" / "calavera_logo.svg", d / "assets" / "calavera_logo.svg")
    fx = CACHE / "_fx" / "static" / "img" / "fx"
    if not (fx / "nebel-hinten.webp").is_file():
        build.make_fx_textures(CACHE / "_fx")
    for f in fx.glob("nebel-*.webp"):
        shutil.copy(f, d / "assets" / f.name)
    return d


# ---------------------------------------------------------------------------
#  Rendern: Unterbilder (Bewegungsunschärfe) → ffmpeg
# ---------------------------------------------------------------------------
def rendern(ordner: Path, vorlage: str, daten: dict, audio: Path | None, ziel: Path, schnell: bool, klick: bool) -> None:
    from playwright.sync_api import sync_playwright
    (ordner / "daten.js").write_text("window.DATA = " + json.dumps(daten, ensure_ascii=False) + ";\n", encoding="utf-8")
    sub, shutter = (1, 0) if schnell else (4, .5)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
        fehlerliste: list[str] = []
        page.on("pageerror", lambda e: fehlerliste.append(str(e)))
        page.goto((ordner / f"{vorlage}.html").as_uri())
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(400)
        page.evaluate("document.getAnimations().forEach(a => a.pause())")
        if fehlerliste:
            fehler(f"Vorlage {vorlage}: {fehlerliste[0]}")
        beats = int(page.evaluate("REEL.beats"))
        bpm = daten["bpm"]
        dauer = beats * 60 / bpm
        n = round(dauer * FPS)
        if klick and audio is None:
            audio = ordner / "klick.wav"
            klick_spur(bpm, beats, audio)
        info(f"    {beats} Schläge = {dauer:.1f} s, {n} Bilder{'' if schnell else f' × {sub} Unterbilder'} …")
        vf = [f"tmix=frames={sub}", f"select='eq(mod(n\\,{sub})\\,{sub - 1})'", f"setpts=N/({FPS}*TB)"] if sub > 1 else []
        vf += ["eq=contrast=1.06:saturation=1.1:gamma=0.97", "rgbashift=rh=-2:bh=2", "vignette=angle=PI/5",
               "noise=alls=3:allf=t", "format=yuv420p"]
        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS * sub), "-c:v", "mjpeg", "-i", "-"]
        cmd += ["-i", str(audio)] if audio else ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        cmd += ["-vf", ",".join(vf), "-r", str(FPS), "-c:v", "libx264", "-profile:v", "high",
                "-crf", "23" if schnell else "18", "-maxrate", "16M", "-bufsize", "32M",
                "-preset", "veryfast" if schnell else "slow", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-t", f"{n / FPS:.3f}", "-movflags", "+faststart", str(ziel)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        js = "t => { REEL.render(t / 1000 * DATA.bpm / 60, t / 1000); document.getAnimations().forEach(a => { a.currentTime = t; }); }"
        schritt = max(1, n // 10)
        for i in range(n):
            for s in range(sub):
                page.evaluate(js, (i + s / sub * shutter) / FPS * 1000)
                proc.stdin.write(page.screenshot(type="jpeg", quality=85 if schnell else 95))
            if i % schritt == 0:
                print(f"\r    {i * 100 // n:3d} %", end="", flush=True)
        proc.stdin.close()
        if proc.wait() != 0:
            fehler("ffmpeg ist fehlgeschlagen")
        print("\r    100 %", flush=True)
        # Titelbild für Instagram: Schlusstafel kurz vor Ende (oder der Schlag, den die Vorlage als "cover" nennt)
        cover = page.evaluate("typeof REEL.cover === 'number' ? REEL.cover : null")
        page.evaluate(js, (beats - .6 if cover is None else cover) * 60 / bpm * 1000)
        page.screenshot(path=str(ziel.with_suffix(".jpg")), type="jpeg", quality=92)
        browser.close()


# ---------------------------------------------------------------------------
#  Daten für die Vorlagen
# ---------------------------------------------------------------------------
def infozeile(ev, club: dict) -> str:
    wt = build.WOCHENTAG[ev.start.weekday()]
    uhr = lambda d: f"{d:%H}" if d.minute == 0 else f"{d:%H:%M}"
    if ev.doors:
        return f"{wt} · Einlass {ev.doors:%H:%M} · Beginn {ev.start:%H:%M}"
    return f"{wt} · ab {uhr(ev.start)} Uhr · {club.get('address', '')}"


def event_daten(ev, cfg: dict, meta: dict, assets: Path) -> dict:
    flyer, unscharf, ratio = flyer_bilder(ev, assets)
    atmos = [ATMO[f] for f in ev.effekte if f in ATMO]
    fokus = meta.get("reel_fokus") or meta.get("fokus") or [[50, 20], [40, 70], [60, 45]]
    return {
        "bpm": float(meta.get("bpm") or cfg.get("reels", {}).get("bpm", 124)),
        "titel": ev.social_title or ev.title,
        "datum": f"{ev.start:%d.%m.}",
        "wochentag": build.WOCHENTAG_LANG[ev.start.weekday()],
        "uhrzeit": f"{ev.start:%H}" if ev.start.minute == 0 else f"{ev.start:%H:%M}",
        "byline": ev.byline, "byline_mit": bool(ev.djs and not ev.subtitle),
        "infozeile": infozeile(ev, cfg.get("club", {})),
        "genres": ev.genres, "fans": ev.fans_of, "teaser": ev.teaser,
        "atmo": atmos[0] if atmos else "funken", "blitz": "gewitter" in ev.effekte,
        "flyer": flyer, "flyer_unscharf": unscharf, "flyer_ratio": ratio,
        "fokus": [[float(a), float(b)] for a, b in fokus][:3] + [[50, 20], [40, 70], [60, 45]][len(fokus):],
        "energie": [],
    }


def reels_fuer(meta: dict, ev, explizit: list[str] | None) -> list[str]:
    if explizit:
        return explizit
    liste = [VORLAGE_ALIAS.get(str(x).strip().lower(), str(x).strip().lower()) for x in build.as_list(meta.get("reels") or meta.get("reel"))]
    for x in liste:
        if x not in ALLE_VORLAGEN:
            info(f"  ! {ev.source.name}: Reel-Vorlage \"{x}\" gibt es nicht – möglich: {', '.join(ALLE_VORLAGEN)}")
    return [x for x in liste if x in ALLE_VORLAGEN]


def ein_reel(ev, cfg, meta, vorlage, args, tage: int | None = None) -> Path | None:
    if vorlage == "freunde" and len(ev.fans_of) < 4:
        info(f"  · {vorlage}: übersprungen – mindestens 4 Namen unter fans_of nötig")
        return None
    job = f"{ev.slug}-{vorlage}" + (f"-{tage}" if tage is not None else "")
    ordner = arbeitsordner(job)
    daten = event_daten(ev, cfg, meta, ordner / "assets")
    daten["hilfslinien"] = args.hilfslinien
    if tage is not None:
        daten["tage"] = tage
    ziel_dir = AUSGABE / ev.slug
    ziel_dir.mkdir(parents=True, exist_ok=True)
    ziel = ziel_dir / (f"{vorlage}" + (f"-{tage}" if tage is not None else "") + ".mp4")
    audio = None
    musik = None if args.klick else finde_musik(ev, meta)
    if musik:
        eins = zeit(meta.get("eins") or meta.get("musik_start") or 0)
        if not meta.get("bpm"):
            info("  ! Musik ohne bpm: – Takt wird mit 124 BPM angenommen")
        eins, notes = takt_pruefen(musik, daten["bpm"], eins)
        for n_ in notes:
            info(f"    {n_}")
        # Länge erst nach dem Laden der Vorlage bekannt → großzügig vorbereiten, ffmpeg schneidet auf Videolänge
        takt = 4 * 60 / daten["bpm"]
        dauer = _vorlage_beats(ordner, vorlage, daten) * 60 / daten["bpm"]
        audio = ordner / "musik.wav"
        daten["energie"] = musik_vorbereiten(musik, eins, dauer, takt, audio)
    info(f"  → {ziel.relative_to(ROOT)}")
    rendern(ordner, vorlage, daten, audio, ziel, args.schnell, args.klick)
    (ziel_dir / "bildtext-instagram.txt").write_text(build.social_texts(ev, cfg)["instagram"], encoding="utf-8")
    return ziel


def _vorlage_beats(ordner: Path, vorlage: str, daten: dict) -> int:
    """Länge einer Vorlage in Schlägen (hängt von den Daten ab, z. B. Anzahl Namen)"""
    from playwright.sync_api import sync_playwright
    (ordner / "daten.js").write_text("window.DATA = " + json.dumps(daten, ensure_ascii=False) + ";\n", encoding="utf-8")
    with sync_playwright() as pw:
        b = pw.chromium.launch(); p = b.new_page(viewport={"width": 1080, "height": 1920})
        p.goto((ordner / f"{vorlage}.html").as_uri()); p.evaluate("document.fonts.ready")
        beats = int(p.evaluate("REEL.beats")); b.close()
    return beats


def programm_musik(musik_name, eins_wert, ordner: Path, vorlage: str, daten: dict) -> Path | None:
    """Musik für Reels ohne Event-Datei (woche, kellerfunk): suchen, Takt prüfen, zuschneiden. Setzt daten["energie"]."""
    if not musik_name:
        return None
    m = next((p for p in (MUSIK / musik_name, ROOT / "events" / musik_name, ROOT / musik_name) if p.is_file()), None)
    if not m:
        info(f"  ! Musik \"{musik_name}\" nicht gefunden (gesucht in reels/musik/ und events/)")
        return None
    eins, notes = takt_pruefen(m, daten["bpm"], zeit(eins_wert or 0))
    for n_ in notes:
        info(f"    {n_}")
    beats = _vorlage_beats(ordner, vorlage, daten)
    audio = ordner / "musik.wav"
    daten["energie"] = musik_vorbereiten(m, eins, beats * 60 / daten["bpm"], 4 * 60 / daten["bpm"], audio)
    return audio


def woche(events, cfg, args, now) -> None:
    rcfg = cfg.get("reels", {})
    ab = datetime.strptime(args.ab, "%Y-%m-%d").replace(tzinfo=now.tzinfo) if args.ab else now.replace(hour=0, minute=0, second=0, microsecond=0)
    bis = ab + timedelta(days=args.tage)
    auswahl = [e for e in events if ab <= e.start < bis and e.end > now][:8]
    if not auswahl:
        fehler(f"keine Veranstaltungen zwischen {ab:%d.%m.} und {bis - timedelta(days=1):%d.%m.}")
    job = f"woche-{ab:%Y-%m-%d}"
    ordner = arbeitsordner(job)
    termine = []
    for e in auswahl:
        f, u, r = flyer_bilder(e, ordner / "assets")
        termine.append({"datum": f"{build.WOCHENTAG[e.start.weekday()]} {e.start:%d.%m.}", "titel": e.social_title or e.title,
                        "byline": e.byline, "flyer": f, "flyer_unscharf": u, "flyer_ratio": r})
    kopf = ["Diese Woche", "im Calavera", f"{ab:%d.%m.} – {(bis - timedelta(days=1)):%d.%m.}"] if args.tage <= 7 \
        else ["Demnächst", "im Calavera", f"{ab:%d.%m.} – {(bis - timedelta(days=1)):%d.%m.}"]
    daten = {"bpm": float(args.bpm or rcfg.get("bpm", 124)), "termine": termine, "kopf": kopf,
             "url": rcfg.get("url_text", "calavera.club/programm"), "energie": [], "hilfslinien": args.hilfslinien}
    AUSGABE.mkdir(parents=True, exist_ok=True)
    ziel = AUSGABE / f"{job}.mp4"
    audio = None if args.klick else programm_musik(args.musik or rcfg.get("woche_musik"), args.eins or rcfg.get("woche_eins", 0), ordner, "woche", daten)
    info(f"Programm {ab:%d.%m.}–{(bis - timedelta(days=1)):%d.%m.}: {len(termine)} Veranstaltungen → {ziel.relative_to(ROOT)}")
    rendern(ordner, "woche", daten, audio, ziel, args.schnell, args.klick)


# ---------------------------------------------------------------------------
#  Kellerfunk: Sendeplan eines Monats aus der config.yml von live.calavera.club
# ---------------------------------------------------------------------------
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]


def _laden(quelle: str) -> bytes:
    """Datei (Pfad) oder Adresse (http/https) lesen"""
    if re.match(r"^https?://", quelle):
        import urllib.request
        req = urllib.request.Request(quelle, headers={"User-Agent": "calavera-reels/1.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.read()
    return Path(quelle).read_bytes()


def _aufloesen(wert: str, basis: str) -> str:
    """Bildangabe aus dem Sendeplan → volle Adresse bzw. Pfad (relativ zur config.yml)"""
    if not wert or re.match(r"^https?://", wert):
        return wert
    if re.match(r"^https?://", basis):
        from urllib.parse import urljoin
        return urljoin(basis, wert)
    return str((Path(basis).parent / wert).resolve())


def _bild_holen(quelle: str, ziel: Path, name: str, unscharf: bool = True) -> tuple[str, str] | None:
    """Bild laden, als JPEG/PNG ablegen (+ unscharfe Version). Fehlt es → None (Vorlage zeigt dann das Testbild)."""
    from io import BytesIO
    from PIL import Image, ImageEnhance, ImageFilter
    try:
        im = Image.open(BytesIO(_laden(quelle)))
        im.load()
    except Exception as e:   # noqa: BLE001 – fehlendes Bild ist kein Abbruchgrund
        info(f"  ! Bild nicht ladbar: {quelle} ({e.__class__.__name__})")
        return None
    if not unscharf:   # Logo: Transparenz behalten
        im = im.convert("RGBA")
        if im.width > 1400:
            im = im.resize((1400, round(1400 * im.height / im.width)), Image.LANCZOS)
        im.save(ziel / f"{name}.png")
        return f"assets/{name}.png", ""
    im = im.convert("RGB")
    if max(im.size) > 1800:
        f = 1800 / max(im.size)
        im = im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS)
    im.save(ziel / f"{name}.jpg", quality=93)
    bg = im.resize((480, max(1, round(480 * im.height / im.width)))).filter(ImageFilter.GaussianBlur(22))
    ImageEnhance.Color(bg).enhance(1.4).save(ziel / f"{name}-unscharf.jpg", quality=85)
    return f"assets/{name}.jpg", f"assets/{name}-unscharf.jpg"


def _rauschen(ziel: Path) -> None:
    """Bildrauschen (Schnee wie beim alten Fernseher), 360 × 640, wird in der Vorlage 3× vergrößert"""
    import random
    from PIL import Image
    rnd = random.Random(7)
    im = Image.frombytes("L", (360, 640), rnd.randbytes(360 * 640))
    im.convert("RGB").save(ziel / "rauschen.png")


def _platzhalter(s: str) -> bool:
    return bool(re.fullmatch(r"\s*\[.*\]\s*", s or ""))


def _sendezeit(wert, tz) -> datetime | None:
    """'2026-11-06 21:00' (Bremer Ortszeit) – YAML liefert evtl. schon datetime/date"""
    if isinstance(wert, datetime):
        return wert.replace(tzinfo=tz) if wert.tzinfo is None else wert.astimezone(tz)
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2})[:.](\d{2})", str(wert or "").strip())
    if not m:
        return None
    return datetime(*map(int, m.groups()), tzinfo=tz)


def kellerfunk(cfg, args, now, tz) -> None:
    import yaml
    kcfg, rcfg = cfg.get("kellerfunk", {}) or {}, cfg.get("reels", {}) or {}
    quelle = args.plan or kcfg.get("config") or "https://live.calavera.club/config.yml"
    info(f"Kellerfunk: Sendeplan von {quelle}")
    try:
        plan = yaml.safe_load(_laden(quelle).decode("utf-8")) or {}
    except Exception as e:   # noqa: BLE001
        fehler(f"Sendeplan nicht ladbar ({e}). Ohne Internet: --plan pfad/zur/config.yml")
    if args.monat:
        jahr, mon = map(int, args.monat.split("-"))
    else:   # ab dem 15. kündigt man den nächsten Monat an
        jahr, mon = (now.year, now.month) if now.day < 15 else ((now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1))
    sendungen = []
    for s in plan.get("shows") or []:
        start = _sendezeit((s or {}).get("start"), tz)
        if start and (start.year, start.month) == (jahr, mon):
            sendungen.append((start, s))
    sendungen.sort(key=lambda x: x[0])
    if not sendungen:
        fehler(f"keine Sendungen im {MONATE[mon - 1]} {jahr} im Sendeplan")
    if len(sendungen) > 8:
        info(f"  ! {len(sendungen)} Sendungen – im Reel die ersten 8 einzeln, im Sendeplan alle")

    job = f"kellerfunk-{jahr}-{mon:02d}"
    ordner = arbeitsordner(job)
    assets = ordner / "assets"
    _rauschen(assets)
    basis = quelle if re.match(r"^https?://", quelle) else str(Path(quelle).resolve())
    logo = None
    logo_quellen = ([str(Path(quelle).resolve().parent / "kellerfunk.png")] if not re.match(r"^https?://", quelle) else []) \
        + [kcfg.get("logo") or _aufloesen("kellerfunk.png", basis)]
    for lq in logo_quellen:
        if lq and (re.match(r"^https?://", lq) or Path(lq).is_file()):
            r = _bild_holen(lq, assets, "kellerfunk-logo", unscharf=False)
            if r:
                logo = r[0]
                break
    if not logo:
        info("  · ohne Logo – die Vorlage schreibt \"Kellerfunk\"")

    liste, alle = [], []
    for i, (start, s) in enumerate(sendungen):
        djs = [d for d in build.as_list(s.get("djs")) if d and not _platzhalter(str(d))]
        titel = str(s.get("title") or "Kellerfunk")
        if _platzhalter(titel):
            titel = "Kellerfunk"
        eintrag = {"wt": build.WOCHENTAG[start.weekday()], "datum": f"{start:%d.%m.}",
                   "zeit": f"{start:%H} Uhr" if start.minute == 0 else f"{start:%H:%M} Uhr",
                   "titel": titel, "djs": " & ".join(map(str, djs)), "visual": "", "unscharf": "",
                   # wie auf live.calavera.club: club: true = "Live im Club & im Stream", false = "Nur im Stream"
                   "club": s.get("club") if isinstance(s.get("club"), bool) else None,
                   "genres": " · ".join(str(g) for g in build.as_list(s.get("genres") or s.get("genre") or s.get("musik")) if g and not _platzhalter(str(g)))}
        vq = _aufloesen(str(s.get("visual") or s.get("flyer") or ""), basis)
        if vq and i < 8:
            r = _bild_holen(vq, assets, f"sendung-{i + 1}")
            if r:
                eintrag["visual"], eintrag["unscharf"] = r
        elif i < 8:
            info(f"  · {eintrag['datum']} {titel}: ohne Visual – im Monitor erscheint das Testbild")
        alle.append(eintrag)
        if i < 8:
            liste.append(eintrag)
        info(f"  {eintrag['wt']} {eintrag['datum']} {eintrag['zeit']:>9}  {titel}" + (f" – {eintrag['djs']}" if eintrag["djs"] else ""))

    url = str(kcfg.get("url") or "https://live.calavera.club")
    daten = {"bpm": float(args.bpm or rcfg.get("kellerfunk_bpm") or rcfg.get("bpm", 124)),
             "monat": MONATE[mon - 1], "jahr": jahr, "sendungen": liste, "plan": alle, "logo": logo,
             "url": re.sub(r"^https?://", "", url).rstrip("/"),
             "claim": rcfg.get("kellerfunk_claim", "Live aus dem Calavera-Keller"),
             "unterzeile": rcfg.get("kellerfunk_unterzeile", "Im Stream · aus dem Keller"),
             "hinweis": rcfg.get("kellerfunk_hinweis", "Link in Bio"),
             "energie": [], "hilfslinien": args.hilfslinien}
    audio = None if args.klick else programm_musik(args.musik or rcfg.get("kellerfunk_musik"), args.eins or rcfg.get("kellerfunk_eins", 0), ordner, "kellerfunk", daten)
    AUSGABE.mkdir(parents=True, exist_ok=True)
    ziel = AUSGABE / f"{job}.mp4"
    info(f"  → {ziel.relative_to(ROOT)}")
    rendern(ordner, "kellerfunk", daten, audio, ziel, args.schnell, args.klick)

    # Bildtext für Instagram
    zeilen = [f"Kellerfunk im {MONATE[mon - 1]} 📻 {daten['claim']}.", ""]
    for e in alle:
        zeilen.append(f"▸ {e['wt']} {e['datum']} · {e['zeit']} · {e['titel']}" + (f" mit {e['djs']}" if e["djs"] else ""))
    zeilen += ["", f"Einschalten: {daten['url']} (Link in Bio)", "",
               " ".join(dict.fromkeys("#" + re.sub(r"[^0-9a-zäöüß]", "", str(h).lower()) for h in
                                      ["kellerfunk", *((cfg.get("abbinder") or {}).get("hashtags") or []), "livestream", "djset"]))]
    (AUSGABE / f"{job}-bildtext.txt").write_text("\n".join(zeilen) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Reels für Instagram aus den Event-Dateien", formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("auswahl", nargs="?", help='Teil des Dateinamens einer Veranstaltung, oder "woche" / "kellerfunk"')
    ap.add_argument("--vorlage", help=f"nur diese Vorlage(n), Komma-getrennt: {', '.join(ALLE_VORLAGEN)}")
    ap.add_argument("--countdown", default="3,1,0", help="Countdown-Varianten in Tagen (Standard 3,1,0)")
    ap.add_argument("--schnell", action="store_true", help="Vorschau ohne Bewegungsunschärfe")
    ap.add_argument("--klick", action="store_true", help="Metronom statt Musik")
    ap.add_argument("--hilfslinien", action="store_true", help="Instagram-Bedienflächen einblenden")
    ap.add_argument("--liste", action="store_true", help="nur anzeigen, was gerendert würde")
    ap.add_argument("--pruefen", action="store_true", help="nur Musik prüfen (Tempo, Eins)")
    ap.add_argument("--now", help="so tun, als wäre jetzt … (JJJJ-MM-TT HH:MM)")
    ap.add_argument("--ab", help="woche: erster Tag (JJJJ-MM-TT), Standard heute")
    ap.add_argument("--tage", type=int, default=7, help="woche: Anzahl Tage (Standard 7)")
    ap.add_argument("--musik", help="woche/kellerfunk: Musikdatei (in reels/musik/ oder events/)")
    ap.add_argument("--bpm", type=float, help="woche/kellerfunk: Tempo der Musik")
    ap.add_argument("--eins", help="woche/kellerfunk: Zeitpunkt der Eins in der Musik")
    ap.add_argument("--monat", help="kellerfunk: Monat JJJJ-MM (Standard: bis zum 14. dieser, danach der nächste)")
    ap.add_argument("--plan", help="kellerfunk: Sendeplan aus dieser Datei/Adresse statt live.calavera.club/config.yml")
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        fehler("ffmpeg nicht gefunden – bitte installieren (macOS: brew install ffmpeg · Windows: winget install ffmpeg · Linux: apt install ffmpeg)")
    try:
        import playwright  # noqa: F401
    except ImportError:
        fehler("Playwright fehlt – einmal: pip install -r requirements-reels.txt && python -m playwright install chromium")

    import yaml
    cfg = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    tz = ZoneInfo(cfg["site"].get("timezone", "Europe/Berlin"))
    now = datetime.strptime(args.now, "%Y-%m-%d %H:%M").replace(tzinfo=tz) if args.now else datetime.now(tz)
    events = build.load_events(cfg, tz)
    upcoming = [e for e in events if e.end > now]

    if args.auswahl == "woche":
        woche(upcoming, cfg, args, now)
        return 0
    if args.auswahl == "kellerfunk":
        kellerfunk(cfg, args, now, tz)
        return 0

    explizit = [VORLAGE_ALIAS.get(v.strip(), v.strip()) for v in args.vorlage.split(",")] if args.vorlage else None
    if args.auswahl:
        sel = [e for e in upcoming if args.auswahl.lower() in e.slug.lower()]
        if not sel:
            fehler(f"keine kommende Veranstaltung mit \"{args.auswahl}\" im Dateinamen")
    else:
        sel = upcoming
    jobs = []
    for ev in sel:
        meta, _ = build.read_front_matter(ev.source)
        vl = reels_fuer(meta, ev, explizit)
        if not vl and args.auswahl:   # ausdrücklich gewählt, aber keine "reels:" → sinnvolle Auswahl
            vl = ["flyerfahrt", "teaser"] + (["freunde"] if len(ev.fans_of) >= 4 else [])
        if vl:
            jobs.append((ev, meta, vl))
    if not jobs:
        info("Nichts zu tun: keine kommende Veranstaltung mit \"reels:\" in der Event-Datei.")
        return 0

    for ev, meta, vl in jobs:
        musik = finde_musik(ev, meta)
        info(f"{ev.start:%d.%m.} {ev.title}: {', '.join(vl)}" + (f"  · Musik: {musik.name}" if musik else "  · ohne Musik"))
        if args.liste:
            continue
        if args.pruefen:
            if musik:
                _, notes = takt_pruefen(musik, float(meta.get("bpm") or 124), zeit(meta.get("eins") or 0))
                for n_ in notes:
                    info(f"    {n_}")
            continue
        for v in vl:
            if v == "countdown":
                for t in [int(x) for x in args.countdown.split(",") if x.strip()]:
                    ein_reel(ev, cfg, meta, v, args, tage=t)
            else:
                ein_reel(ev, cfg, meta, v, args)
    if not (args.liste or args.pruefen):
        info(f"Fertig. Reels liegen in {AUSGABE.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
