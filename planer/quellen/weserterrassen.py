"""Bürgerhaus Weserterrassen (weserterrassen.com/events/) – nur ausgewählte Reihen, Standard „Jungbrunnen“
(Ü30-Party, meist letzter Samstag im Monat).

Die Seite läuft mit dem Contao-Eventmodul. Pro Termin gibt es ein `div.event` mit `div.date`
(„Sa, 28.11.“ – ohne Jahr) und einem Link im `h2`, dessen title-Attribut alles Nötige enthält:
    title="jungbrunnen (Samstag, 28.11.2026, 20:00 - 23:45)"
Die Liste zeigt immer nur einen Monat; geblättert wird über `events/?month=JJJJMM`.

Vorgehen pro Monat von `von` bis `bis`:
1. title-Attribute der Links, deren Name ein Stichwort aus `nur:` enthält (Groß-/Kleinschreibung egal).
2. Falls die Seite einmal umgebaut wird: JSON-LD-Events, sonst Stichwort → nächstes Datum im Text.
Stichworte in quellen.yml unter `nur:`.
"""
from __future__ import annotations

import html as html_mod
import re
from datetime import date, datetime
from urllib.parse import urljoin

from ..seite import finde_daten, finde_uhrzeit, jsonld_events, lese, sauberer_titel
from ..termin import TZ, Termin, zu_datetime

SPALTE = "Weserterrassen"
STADT = "Bremen"
LISTE = "https://www.weserterrassen.com/events/"
NUR = ["Jungbrunnen"]

_KURZ = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})\b")
_A_TAG = re.compile(r"<a\b[^>]*>", re.I)
_ATTR = re.compile(r"""\b(href|title)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
_BASE = re.compile(r"""<base\b[^>]*href\s*=\s*["']([^"']+)["']""", re.I)
# „(Samstag, 28.11.2026, 20:00 - 23:45)“ bzw. „(28.11.2026)“ oder „(28.11.2026 - 29.11.2026)“
_CONTAO = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})(?:,\s*(\d{1,2})[:.](\d{2}))?")


def monate(von: date, bis: date):
    """Alle Monate (jahr, monat) von `von` bis `bis`."""
    j, m = von.year, von.month
    while (j, m) <= (bis.year, bis.month):
        yield j, m
        j, m = (j + 1, 1) if m == 12 else (j, m + 1)


def monats_url(url: str, jahr: int, monat: int) -> str:
    trenner = "&" if "?" in url else "?"
    return f"{url}{trenner}month={jahr}{monat:02d}"


def _alle_daten(text: str):
    """Langdaten („28. November 2026“) und Zifferndaten („28.11.2026“, „28.11.26“) mit Position."""
    aus = list(finde_daten(text))
    for m in _KURZ.finditer(text):
        j = int(m.group(3))
        j += 2000 if j < 100 else 0
        try:
            aus.append((m.start(), date(j, int(m.group(2)), int(m.group(1)))))
        except ValueError:
            continue
    return sorted(aus)


def _schoener_titel(name: str, stichworte_orig: list[str]) -> str:
    """„jungbrunnen“ → „Jungbrunnen“ (Schreibweise aus quellen.yml), sonst erster Buchstabe groß."""
    for s in stichworte_orig:
        if name.lower() == s.lower():
            return s
    return name[:1].upper() + name[1:] if name.islower() else name


def contao_links(roh: str, seiten_url: str):
    """(name, tag, beginn|None, link) aus den title-Attributen der Event-Links."""
    basis = _BASE.search(roh)
    basis = basis.group(1) if basis else seiten_url
    for tag_m in _A_TAG.finditer(roh):
        attrs = {k.lower(): html_mod.unescape(a if a is not None else b)
                 for k, a, b in _ATTR.findall(tag_m.group(0))}
        title = " ".join(attrs.get("title", "").split())
        if "(" not in title:
            continue
        name, _, klammer = title.rpartition("(")
        d = _CONTAO.search(klammer)
        if not d or not name.strip():
            continue
        try:
            tag = date(int(d.group(3)), int(d.group(2)), int(d.group(1)))
        except ValueError:
            continue
        beginn = zu_datetime(tag, int(d.group(4)), int(d.group(5))) if d.group(4) else None
        link = urljoin(basis, attrs["href"]) if attrs.get("href") else None
        yield name.strip(), tag, beginn, link


def hole(http, von, bis, einstellungen, warn=lambda text: None):
    url = einstellungen.get("url", LISTE)
    nur = list(einstellungen.get("nur", NUR))
    stichworte = [s.lower() for s in nur]
    termine, gesehen = [], set()

    def neu(tag, titel, beginn, link):
        if (tag, titel.lower()) in gesehen or not (von <= tag <= bis):
            return
        gesehen.add((tag, titel.lower()))
        termine.append(Termin(quelle="weserterrassen", titel=titel, tag=tag, beginn=beginn,
                              ort="Weserterrassen", stadt=STADT, url=link or url,
                              uid=f"weserterrassen-{tag}-{titel.lower()}"))

    def passt(name):
        return any(s in name.lower() for s in stichworte)

    seiten = []
    for nr, (jahr, monat) in enumerate(monate(von, bis)):
        murl = monats_url(url, jahr, monat)
        try:
            seiten.append((murl, http.text(murl)))
        except Exception as fehler:          # ein fehlender Monat soll den Rest nicht kippen
            if nr == 0:
                raise
            warn(f"Monat {monat:02d}/{jahr} nicht abrufbar ({fehler})")

    for murl, roh in seiten:
        # 1. Contao: title-Attribute der Links
        for name, tag, beginn, link in contao_links(roh, murl):
            if passt(name):
                neu(tag, _schoener_titel(name, nur), beginn, link)

    if not termine:
        for murl, roh in seiten:
            seite = lese(roh, murl)
            # 2. JSON-LD
            for ev in jsonld_events(seite):
                name = sauberer_titel(str(ev.get("name") or ""))
                if not passt(name):
                    continue
                try:
                    beginn = datetime.fromisoformat(str(ev.get("startDate")).replace("Z", "+00:00"))
                except ValueError:
                    continue
                beginn = (beginn if beginn.tzinfo else beginn.replace(tzinfo=TZ)).astimezone(TZ)
                neu(beginn.date(), _schoener_titel(name, nur), beginn, ev.get("url"))
            # 3. Text: Stichwort → nächstgelegenes Datum
            text = seite.rohtext
            daten = _alle_daten(text)
            for s in stichworte:
                for m in re.finditer(re.escape(s), text, re.I):
                    nah = [(abs(p - m.start()), p, d) for p, d in daten if abs(p - m.start()) <= 400]
                    if not nah:
                        continue
                    _, p, tag = min(nah)
                    zeit = finde_uhrzeit(text[p:p + 200])
                    anfang = text.rfind("\n", 0, m.start()) + 1
                    ende = text.find("\n", m.end())
                    titel = " ".join(text[anfang:ende if ende >= 0 else None].split())[:120] or s.capitalize()
                    if _alle_daten(titel):
                        titel = s.capitalize() if len(titel) > 60 else titel
                    neu(tag, titel, zu_datetime(tag, *zeit) if zeit else None, None)

    if not termine:
        warn(f"keine Termine mit {', '.join(nur)} gefunden – Seite geändert oder gerade keiner angekündigt?")
    return termine
