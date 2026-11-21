"""Werder Bremen – Heim- und Auswärtsspiele (Bundesliga, DFB-Pokal) über OpenLigaDB.

werderbremen.de selbst sperrt automatische Abrufe; OpenLigaDB (api.openligadb.de) ist eine freie
JSON-API mit dem kompletten Spielplan und Anstoßzeiten. Die DFL legt die genauen Anstoßzeiten erst
einige Wochen vorher fest; bis dahin steht dort ein vorläufiger Termin. Spiele weiter als
VORLAEUFIG_TAGE in der Zukunft bekommen deshalb „(Zeit vorläufig)“.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from ..termin import TZ, Termin

SPALTE = "Werder"
STADT = "Bremen"
API = "https://api.openligadb.de/getmatchdata/{liga}/{saison}"
LIGEN = ["bl1", "dfb"]          # Bundesliga, DFB-Pokal (bl2, falls nötig, in quellen.yml ergänzen)
TEAM_ID = 134                   # „SV Werder Bremen“ in OpenLigaDB
VORLAEUFIG_TAGE = 35


def saison(d: date) -> int:
    """Saison 2026/27 heißt bei OpenLigaDB 2026 und läuft etwa von Juli bis Juni."""
    return d.year if d.month >= 7 else d.year - 1


def ist_werder(team: dict) -> bool:
    return team.get("teamId") == TEAM_ID or "werder" in (team.get("teamName") or "").lower()


def kurz(team: dict) -> str:
    return "Werder" if ist_werder(team) else (team.get("shortName") or team.get("teamName") or "?")


def hole(http, von, bis, einstellungen, warn=lambda text: None):
    termine: list[Termin] = []
    gesehen: set = set()
    for liga in einstellungen.get("ligen", LIGEN):
        for s in sorted({saison(von), saison(bis)}):
            url = API.format(liga=liga, saison=s)
            try:
                spiele = json.loads(http.text(url))
            except Exception as e:
                warn(f"{liga} {s}: {e}")
                continue
            for sp in spiele or []:
                t1, t2 = sp.get("team1") or {}, sp.get("team2") or {}
                if not (ist_werder(t1) or ist_werder(t2)) or sp.get("matchID") in gesehen:
                    continue
                gesehen.add(sp.get("matchID"))
                roh = sp.get("matchDateTimeUTC") or sp.get("matchDateTime")
                try:
                    beginn = datetime.fromisoformat(roh.replace("Z", "+00:00"))
                except (AttributeError, ValueError):
                    continue
                beginn = (beginn if beginn.tzinfo else beginn.replace(tzinfo=TZ)).astimezone(TZ)
                tag = beginn.date()
                if not (von <= tag <= bis):
                    continue
                heim = ist_werder(t1)
                wettbewerb = "Pokal: " if liga == "dfb" else ""
                titel = f"{wettbewerb}{'HEIM' if heim else 'auswärts'} {kurz(t1)} – {kurz(t2)}"
                if tag - von > timedelta(days=einstellungen.get("vorlaeufig_tage", VORLAEUFIG_TAGE)):
                    titel += " (Zeit vorläufig)"
                termine.append(Termin(quelle="werder", titel=titel, tag=tag, beginn=beginn,
                                      ort="Weserstadion" if heim else "", stadt=STADT if heim else "",
                                      kategorien=["Fußball", liga], uid=f"werder-{sp.get('matchID')}"))
    return termine
