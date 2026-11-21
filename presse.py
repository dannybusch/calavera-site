#!/usr/bin/env python3
"""
Calavera Bremen – wöchentliche Pressemitteilung "Diese Woche im Calavera"

Eigenständig wie media.py/reels.py: liest events/*.md, config.yml und den Kellerfunk-Sendeplan,
schreibt die Mitteilung nach presse/out/ (Text + HTML) und schickt sie mit --senden per Mail
an die Adresse(n) unter presse.an – zum Prüfen und Weiterleiten an den eigenen Presseverteiler.

  python presse.py                     Probelauf: Mitteilung für die laufende Woche (Mo–So) erzeugen und zeigen
  python presse.py --senden            … und per Mail an presse.an schicken
  python presse.py --naechste          die kommende Woche
  python presse.py --woche 48          Kalenderwoche 48 (oder 2026-W48)
  python presse.py --ab 2026-11-23     die Woche, in der dieser Tag liegt
  --ohne-kellerfunk / --plan DATEI     wie bei media.py
  --now "JJJJ-MM-TT HH:MM"             so tun, als wäre jetzt …

Mailversand (nur über Umgebungsvariablen / GitHub-Secrets, nie in Dateien):
  SMTP_HOST, SMTP_PORT (Standard 465), SMTP_USER, SMTP_PASSWORD
  SMTP_SICHERHEIT: ssl oder starttls (Standard: ssl bei Port 465, sonst starttls)

In config.yml (alles optional außer "an" für --senden):
  presse:
    an: ["team@calavera.club"]          # wer die Mitteilung zum Prüfen bekommt
    von: "presse@calavera.club"         # Absender (Standard: SMTP_USER)
    kontakt: "Name · presse@calavera.club · 0421 …"   # Pressekontakt am Ende (Standard: club.email)
    bildrechte: "Calavera Bremen"       # Standard-Bildnachweis für die Flyer
    ueber: "Das Calavera ist …"         # eigener Absatz "Über das Calavera" (sonst aus site/club gebaut)
"""
from __future__ import annotations

import argparse
import html
import os
import re
import smtplib
import ssl
import sys
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402  – nur zum Lesen der Event-Dateien
from media import woche_waehlen  # noqa: E402  – gleiche Wochenwahl wie beim Wochenbild

AUSGABE = ROOT / "presse" / "out"
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]


def info(msg: str = "") -> None:
    print(msg, flush=True)


def fehler(msg: str) -> None:
    print(f"FEHLER: {msg}", file=sys.stderr)
    sys.exit(1)


def tag_lang(d: date) -> str:
    return f"{build.WOCHENTAG_LANG[d.weekday()]}, {d.day}. {MONATE[d.month - 1]}"


def uhrzeit(d: datetime) -> str:
    return f"{d:%-H} Uhr" if d.minute == 0 else f"{d:%-H.%M} Uhr"


def zeitraum(montag: date) -> str:
    sonntag = montag + timedelta(days=6)
    if montag.month == sonntag.month:
        return f"{montag.day}. bis {sonntag.day}. {MONATE[sonntag.month - 1]} {sonntag.year}"
    return f"{montag.day}. {MONATE[montag.month - 1]} bis {sonntag.day}. {MONATE[sonntag.month - 1]} {sonntag.year}"


def aufzaehlen(teile: list[str]) -> str:
    return teile[0] if len(teile) == 1 else ", ".join(teile[:-1]) + " und " + teile[-1]


# ---------------------------------------------------------------------------
#  Termine sammeln
# ---------------------------------------------------------------------------
def text_aus(ev) -> str:
    """Teaser + Beschreibung als Fließtext, ohne den Teaser doppelt zu bringen"""
    rumpf = build.html_to_plain(ev.body_html or "").strip()
    absaetze = [re.sub(r"\s+", " ", a).strip() for a in re.split(r"\n\s*\n", rumpf) if a.strip()]
    # Teaser nur, wenn es keinen Text gibt – er fasst den Text meist zusammen und wiederholt ihn sonst
    teile = absaetze or ([ev.teaser.strip()] if ev.teaser else [])
    text = "\n\n".join(teile)
    return text if len(text) <= 1200 else text[:1200].rsplit(" ", 1)[0] + " …"


def event_eintraege(events, cfg: dict) -> tuple[list[dict], list[str]]:
    site, club = cfg["site"], cfg["club"]
    default_entry = str((cfg.get("events") or {}).get("default_entry") or "").strip()
    pcfg = cfg.get("presse") or {}
    eintraege, hinweise = [], []
    for ev in events:
        e = {"start": ev.start, "art": "event", "titel": ev.social_title or ev.title, "byline": ev.byline,
             "genres": ", ".join(ev.genres), "text": text_aus(ev), "url": site["url"] + ev.url,
             "eintritt": ev.entry or default_entry, "stream": ev.stream_url or "",
             "bild": f"{site['url']}/media/events/{ev.slug}/1200.jpg" if ev.visual_src else
                     (ev.visual_url if re.match(r"^https?://", ev.visual_url or "") else ""),
             "bildrechte": pcfg.get("bildrechte") or site["name"]}
        if (ev.entry or default_entry) == default_entry:
            zusatz = [x for x in (club.get("entry_note"), club.get("box_office")) if x and x.lower() not in e["eintritt"].lower()]
            if zusatz:
                e["eintritt"] += f" ({', '.join(zusatz)})"
        if not e["text"]:
            hinweise.append(f"„{ev.title}“ ({ev.start:%d.%m.}) hat keinen Beschreibungstext – nur Eckdaten in der Mitteilung.")
        if re.search(r"\[[A-ZÄÖÜ ]+\]|TODO|folgt", f"{ev.title} {e['text']}"):
            hinweise.append(f"„{ev.title}“ ({ev.start:%d.%m.}) enthält noch einen Platzhalter.")
        eintraege.append(e)
    return eintraege, hinweise


def kellerfunk_eintraege(cfg: dict, args, tz, von, bis, now) -> tuple[list[dict], list[str]]:
    import yaml
    import reels
    kcfg = cfg.get("kellerfunk") or {}
    quelle = args.plan or kcfg.get("config") or "https://live.calavera.club/config.yml"
    try:
        plan = yaml.safe_load(reels._laden(quelle).decode("utf-8")) or {}
    except Exception as e:   # noqa: BLE001
        return [], [f"Kellerfunk-Sendeplan nicht ladbar ({e.__class__.__name__}) – Sendungen fehlen in der Mitteilung."]
    kf_url = str(kcfg.get("url") or "https://live.calavera.club")
    eintraege = []
    for s in plan.get("shows") or []:
        s = s or {}
        start = reels._sendezeit(s.get("start"), tz)
        if not start or not (von <= start < bis):
            continue
        titel = str(s.get("title") or "")
        djs = [str(d) for d in build.as_list(s.get("djs")) if d and not reels._platzhalter(str(d))]
        genres = [str(g) for g in build.as_list(s.get("genres") or s.get("genre")) if g and not reels._platzhalter(str(g))]
        eintraege.append({"start": start, "art": "kellerfunk", "titel": "" if reels._platzhalter(titel) else titel,
                          "byline": " & ".join(djs), "genres": ", ".join(genres), "text": "", "url": kf_url,
                          "club": s.get("club") is True, "eintritt": "", "stream": kf_url, "bild": "", "bildrechte": ""})
    return eintraege, []


def zusammenfuehren(events: list[dict], sendungen: list[dict]) -> list[dict]:
    """Sendung am selben Abend wie ein Clubabend (±3 h): nur einmal – beim Event als "auch im Livestream" """
    for s in sendungen:
        gleich = next((e for e in events if e["start"].date() == s["start"].date()
                       and abs((e["start"] - s["start"]).total_seconds()) <= 3 * 3600), None)
        if gleich:
            gleich["stream"] = gleich["stream"] or s["stream"]
        else:
            events.append(s)
    return sorted(events, key=lambda e: e["start"])


# ---------------------------------------------------------------------------
#  Mitteilung schreiben
# ---------------------------------------------------------------------------
def name_von(e: dict) -> str:
    if e["art"] == "kellerfunk":
        return f"Kellerfunk: {e['titel']}" if e["titel"] else "Kellerfunk"
    return e["titel"]


def mitteilung(cfg: dict, montag: date, eintraege: list[dict], heute: date) -> dict:
    site, club = cfg["site"], cfg["club"]
    pcfg = cfg.get("presse") or {}
    abende = [e for e in eintraege if e["art"] == "event"]
    sendungen = [e for e in eintraege if e["art"] == "kellerfunk"]
    kf_url = re.sub(r"^https?://", "", str((cfg.get("kellerfunk") or {}).get("url") or "live.calavera.club")).strip("/")
    stadt = " ".join(club["city"].split(" ")[1:]) or "Bremen"

    namen = [name_von(e) for e in eintraege if e["art"] == "event"] + [name_von(e) for e in eintraege if e["art"] == "kellerfunk"]
    ueberschrift = "Diese Woche im Calavera: " + (aufzaehlen(namen) if len(namen) <= 3 else ", ".join(namen[:3]) + " und mehr")
    betreff = f"Pressemitteilung: Programm im Calavera Bremen vom {zeitraum(montag)}"

    # Einleitung – nur Fakten, keine erfundenen Zitate
    saetze = []
    if abende:
        teile = [f"„{e['titel']}“ am {build.WOCHENTAG_LANG[e['start'].weekday()]}" for e in abende]
        anzahl = {1: "eine Veranstaltung", 2: "zwei Veranstaltungen", 3: "drei Veranstaltungen", 4: "vier Veranstaltungen",
                  5: "fünf Veranstaltungen"}.get(len(abende), f"{len(abende)} Veranstaltungen")
        saetze.append(f"Der Club Calavera am {club['address']} im Bremer Viertel lädt in der Woche vom {zeitraum(montag)} "
                      f"zu {anzahl} ein: {aufzaehlen(teile)}.")
    if sendungen:
        wann = aufzaehlen([f"{build.WOCHENTAG_LANG[s['start'].weekday()]} ab {uhrzeit(s['start'])}" for s in sendungen])
        saetze.append(("Außerdem sendet" if abende else "In dieser Woche sendet") +
                      f" der Kellerfunk, das Livestream-Format aus dem Calavera-Keller, am {wann} auf {kf_url}.")
    eintritt = (cfg.get("events") or {}).get("default_entry") or club.get("entry", "")
    if abende and eintritt:
        saetze.append(f"Wenn nicht anders angegeben, kostet der Eintritt {eintritt}, Azubis und Studierende kommen frei hinein"
                      f"{' (' + club['box_office'] + ')' if club.get('box_office') else ''}."
                      if "frei" not in eintritt.lower() or "azubi" not in eintritt.lower() else
                      f"Wenn nicht anders angegeben: Eintritt {eintritt}.")
    einleitung = " ".join(saetze)

    abschnitte = []
    for e in eintraege:
        kopf = f"{tag_lang(e['start'].date())}, {uhrzeit(e['start'])}: {name_von(e)}"
        zeilen = []
        mit = []
        if e["byline"]:
            mit.append(("mit " if e["byline"].lower().startswith(("dj", "djane")) or e["art"] == "kellerfunk" else "") + e["byline"])
        if e["genres"]:
            mit.append(e["genres"])
        if e["art"] == "kellerfunk":
            zeilen.append(("Im Club und im Livestream" if e.get("club") else "Nur im Livestream") + f" auf {kf_url}.")
        else:
            if e["eintritt"]:
                zeilen.append(f"Eintritt: {e['eintritt']}")
            if e["stream"]:
                zeilen.append(f"Auch im Livestream: {re.sub(r'^https?://', '', e['stream']).strip('/')}")
            zeilen.append(f"Mehr: {e['url']}")
        abschnitte.append({"kopf": kopf, "mit": " · ".join(mit), "text": e["text"], "zeilen": zeilen})

    fotos = [(name_von(e), e["bild"], e["bildrechte"]) for e in eintraege if e.get("bild")]
    ueber = str(pcfg.get("ueber") or "").strip()
    if not ueber:
        ueber = f"{site['name']}, {club['address']}, {club['city']}" + (f" ({club['directions']})" if club.get("directions") else "")
        ueber += f": {site.get('description', '').strip()}"
        if club.get("hours"):
            ueber += f" Geöffnet: {club['hours']}."
    kontakt = str(pcfg.get("kontakt") or f"{site['name']} · {club.get('email', '')}")
    return {"betreff": betreff, "ueberschrift": ueberschrift, "ort_datum": f"{stadt}, {heute.day}. {MONATE[heute.month - 1]} {heute.year}",
            "einleitung": einleitung, "abschnitte": abschnitte, "fotos": fotos, "ueber": ueber, "kontakt": kontakt,
            "web": site["url"], "termine_url": site["url"] + "/programm/"}


def als_text(m: dict, hinweise: list[str]) -> str:
    z = []
    if hinweise:
        z += ["--- Hinweise für dich (vor dem Weiterleiten löschen) ---", *[f"* {h}" for h in hinweise], "---", ""]
    z += ["PRESSEMITTEILUNG", "", m["ueberschrift"], "", f"{m['ort_datum']} – {m['einleitung']}", ""]
    for a in m["abschnitte"]:
        z += [a["kopf"]] + ([a["mit"]] if a["mit"] else [])
        if a["text"]:
            z += ["", a["text"]]
        z += [""] + a["zeilen"] + [""]
    z += [f"Das ganze Programm: {m['termine_url']}", ""]
    if m["fotos"]:
        z += ["Pressefotos (Flyer, honorarfrei zur Berichterstattung über die Veranstaltung):"]
        z += [f"- {n}: {u} (Bild: {r})" for n, u, r in m["fotos"]] + [""]
    z += ["Über das Calavera", m["ueber"], "", "Pressekontakt", m["kontakt"], m["web"], ""]
    return "\n".join(z)


def als_html(m: dict, hinweise: list[str]) -> str:
    e = html.escape
    def link(t: str) -> str:
        return re.sub(r"(https?://[^\s)]+)", r'<a href="\1">\1</a>', e(t))
    teile = ['<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.5;color:#111;max-width:680px">']
    if hinweise:
        teile.append('<div style="border:2px solid #b3122e;padding:10px 14px;margin-bottom:18px;background:#fff4f5">'
                     '<strong>Hinweise für dich (vor dem Weiterleiten löschen)</strong><ul style="margin:6px 0 0">'
                     + "".join(f"<li>{e(h)}</li>" for h in hinweise) + "</ul></div>")
    teile.append('<p style="font-size:12px;letter-spacing:.12em;color:#666;margin:0">PRESSEMITTEILUNG</p>')
    teile.append(f'<h1 style="font-size:22px;margin:6px 0 14px">{e(m["ueberschrift"])}</h1>')
    teile.append(f"<p><strong>{e(m['ort_datum'])}</strong> – {e(m['einleitung'])}</p>")
    for a in m["abschnitte"]:
        teile.append(f'<h2 style="font-size:17px;margin:22px 0 4px">{e(a["kopf"])}</h2>')
        if a["mit"]:
            teile.append(f'<p style="margin:0;color:#444">{e(a["mit"])}</p>')
        for absatz in [t for t in a["text"].split("\n\n") if t]:
            teile.append(f"<p>{e(absatz)}</p>")
        if a["zeilen"]:
            teile.append("<p>" + "<br>".join(link(z) for z in a["zeilen"]) + "</p>")
    teile.append(f'<p>Das ganze Programm: <a href="{e(m["termine_url"])}">{e(m["termine_url"])}</a></p>')
    if m["fotos"]:
        teile.append('<h3 style="font-size:15px;margin:22px 0 4px">Pressefotos</h3><p style="margin:0 0 6px;color:#444">'
                     'Flyer, honorarfrei zur Berichterstattung über die Veranstaltung:</p><ul>'
                     + "".join(f'<li>{e(n)}: <a href="{e(u)}">{e(u)}</a> (Bild: {e(r)})</li>' for n, u, r in m["fotos"]) + "</ul>")
    teile.append(f'<h3 style="font-size:15px;margin:22px 0 4px">Über das Calavera</h3><p>{e(m["ueber"])}</p>')
    teile.append(f'<h3 style="font-size:15px;margin:22px 0 4px">Pressekontakt</h3><p>{e(m["kontakt"])}<br>'
                 f'<a href="{e(m["web"])}">{e(m["web"])}</a></p></div>')
    return "\n".join(t for t in teile if t)


def senden(cfg: dict, m: dict, text: str, html_text: str) -> None:
    pcfg = cfg.get("presse") or {}
    an = [a for a in build.as_list(pcfg.get("an")) if a]
    if not an:
        fehler("in config.yml fehlt presse → an (wer die Mitteilung bekommen soll)")
    host, user, pw = (os.environ.get(k, "").strip() for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"))
    if not (host and user and pw):
        if os.environ.get("GITHUB_ACTIONS"):
            info("SMTP_HOST / SMTP_USER / SMTP_PASSWORD sind (noch) nicht als GitHub-Secrets hinterlegt – nichts gesendet.")
            return
        fehler("SMTP_HOST, SMTP_USER und SMTP_PASSWORD müssen gesetzt sein")
    port = int(os.environ.get("SMTP_PORT") or 465)
    von = str(pcfg.get("von") or user)
    msg = EmailMessage()
    msg["Subject"] = m["betreff"]
    msg["From"] = formataddr((cfg["site"]["name"], von))
    msg["To"] = ", ".join(an)
    if cfg["club"].get("email"):
        msg["Reply-To"] = cfg["club"]["email"]
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=von.split("@")[-1])
    msg.set_content(text)
    msg.add_alternative(f"<!doctype html><html><body>{html_text}</body></html>", subtype="html")
    kontext = ssl.create_default_context()
    art = (os.environ.get("SMTP_SICHERHEIT") or ("ssl" if port == 465 else "starttls")).strip().lower()
    try:
        if art == "ssl":
            with smtplib.SMTP_SSL(host, port, context=kontext, timeout=30) as s:
                s.login(user, pw)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.starttls(context=kontext)
                s.login(user, pw)
                s.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        fehler("Mailserver: Anmeldung abgelehnt (SMTP_USER / SMTP_PASSWORD prüfen)")
    except (smtplib.SMTPException, OSError) as e:
        fehler(f"Mailversand fehlgeschlagen ({e.__class__.__name__}: {e}) – SMTP_HOST/SMTP_PORT/SMTP_SICHERHEIT prüfen")
    info(f"  ✉ gesendet an {', '.join(an)}")


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Wöchentliche Pressemitteilung",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--senden", action="store_true", help="per Mail an presse.an schicken")
    ap.add_argument("--woche", help="Kalenderwoche, z. B. 48 oder 2026-W48")
    ap.add_argument("--ab", help="die Woche, in der dieser Tag liegt (JJJJ-MM-TT)")
    ap.add_argument("--naechste", action="store_true", help="eine Woche später")
    ap.add_argument("--ohne-kellerfunk", action="store_true", help="Kellerfunk-Sendeplan nicht einlesen")
    ap.add_argument("--plan", help="Kellerfunk-Sendeplan aus dieser Datei/Adresse")
    ap.add_argument("--now", help="so tun, als wäre jetzt … (JJJJ-MM-TT HH:MM)")
    args = ap.parse_args()
    args.alle = True   # für woche_waehlen/kompatibel: in der Mitteilung stehen alle Termine der Woche

    import yaml
    cfg = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    tz = ZoneInfo(cfg["site"].get("timezone", "Europe/Berlin"))
    now = datetime.strptime(args.now, "%Y-%m-%d %H:%M").replace(tzinfo=tz) if args.now else datetime.now(tz)
    montag = woche_waehlen(args, now)
    von = datetime.combine(montag, datetime.min.time(), tzinfo=tz)
    bis = von + timedelta(days=7)

    events = [ev for ev in build.load_events(cfg, tz) if von <= ev.start < bis]
    eintraege, hinweise = event_eintraege(events, cfg)
    if not args.ohne_kellerfunk:
        sendungen, h2 = kellerfunk_eintraege(cfg, args, tz, von, bis, now)
        hinweise += h2
        eintraege = zusammenfuehren(eintraege, sendungen)
    kw = montag.isocalendar()
    info(f"Pressemitteilung KW {kw[1]} ({montag:%d.%m.} – {(bis - timedelta(days=1)):%d.%m.%Y}): {len(eintraege)} Termin(e)")
    if not eintraege:
        info("  Keine Termine in dieser Woche – keine Pressemitteilung.")
        return 0

    m = mitteilung(cfg, montag, eintraege, now.date())
    text, html_text = als_text(m, hinweise), als_html(m, hinweise)
    AUSGABE.mkdir(parents=True, exist_ok=True)
    name = f"presse-{kw[0]}-kw{kw[1]:02d}"
    (AUSGABE / f"{name}.txt").write_text(f"Betreff: {m['betreff']}\n\n{text}", encoding="utf-8")
    (AUSGABE / f"{name}.html").write_text(f"<!doctype html><html lang=\"de\"><meta charset=\"utf-8\"><title>{html.escape(m['betreff'])}</title>"
                                          f"<body>{html_text}</body></html>", encoding="utf-8")
    info(f"  → presse/out/{name}.txt und .html")
    for h in hinweise:
        info(f"  ! {h}")
    if args.senden:
        senden(cfg, m, text, html_text)
    else:
        info("\nBetreff: " + m["betreff"] + "\n\n" + text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
