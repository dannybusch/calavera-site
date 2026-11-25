"""Tests für den Planungskalender: python -m pytest tests/planer -q"""
from __future__ import annotations

import csv
import io
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import importlib.util  # noqa: E402

# planer.py (Script) und planer/ (Paket) heißen gleich → Script per Pfad laden
_spec = importlib.util.spec_from_file_location("planer_cli", ROOT / "planer.py")
planer_cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(planer_cli)
from planer import auswertung, calavera, sheets  # noqa: E402
from planer.quellen import aladin, dark_kalender, eisen, modernes, polyester  # noqa: E402
from planer.termin import WOCHENTAG_KURZ, Termin, zu_datetime  # noqa: E402

FIX = Path(__file__).parent / "fixtures"
VON, BIS = date(2026, 11, 21), date(2027, 1, 31)


class FakeHttp:
    """Antwortet je nach URL-Teilstück mit einer Fixture-Datei oder einem Text."""

    def __init__(self, antworten: dict[str, str]):
        self.antworten = antworten
        self.abrufe = 0
        self.urls: list[str] = []

    def text(self, url: str) -> str:
        self.urls.append(url)
        self.abrufe += 1
        for teil, inhalt in self.antworten.items():
            if teil in url:
                return inhalt
        raise RuntimeError(f"keine Fixture für {url}")


def fix(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def dark_csv(jahr: int, eintraege: dict[tuple[int, int], str], wochentag_jahr: int | None = None,
             ohne_kopf: bool = False, eine_zelle: bool = False) -> str:
    """Baut ein Jahresblatt wie Sheet B (Kalenderpedia): Zeile 2 Monate (je 4 Spalten), Zeile 3 Legende,
    ab Zeile 4 Tage. ohne_kopf: Kopfzeilen fehlen (wie im echten CSV-Export). eine_zelle: „15 Fr Titel“
    steht in einer Zelle statt in Tag | Wochentag | Eintrag."""
    wj = wochentag_jahr or jahr
    zeilen = [["Partyplanungen Bremen-Oldenburg"] + [""] * 47]
    kopf = []
    for m in sheets.MONATE:
        kopf += [m, "", "", ""]
    zeilen.append(kopf)
    zeilen.append(["Festivals", "", "Gothika OL", "", "Unknown Pleasures", "", "Dark Entries"] + [""] * 41)
    for tag in range(1, 32):
        z = []
        for monat in range(1, 13):
            try:
                d = date(wj, monat, tag)
            except ValueError:
                z += ["", "", "", ""]
                continue
            wt = WOCHENTAG_KURZ[d.weekday()]
            kw = str(d.isocalendar()[1]) if wt == "Mo" else ""
            if eine_zelle:
                z += [f"{tag} {wt} {eintraege.get((monat, tag), '')}".strip(), "", "", kw]
            else:
                z += [str(tag), wt, eintraege.get((monat, tag), ""), kw]
        zeilen.append(z)
    if ohne_kopf:
        zeilen = zeilen[3:]
    puffer = io.StringIO()
    csv.writer(puffer).writerows(zeilen)
    return puffer.getvalue()


# --- Abend-Zuordnung --------------------------------------------------------------------------

def test_beginn_nach_mitternacht_zaehlt_zum_vorabend():
    t = Termin(quelle="x", titel="y", tag=date(2026, 12, 5), beginn=zu_datetime(date(2026, 12, 5), 0, 30))
    assert t.abend == date(2026, 12, 4)
    t2 = Termin(quelle="x", titel="y", tag=date(2026, 12, 5), beginn=zu_datetime(date(2026, 12, 5), 23, 0))
    assert t2.abend == date(2026, 12, 5)


# --- Plugins ----------------------------------------------------------------------------------

def test_modernes():
    http = FakeHttp({
        "/programm/": fix("modernes_programm.html"),
        "fruehparty-ue30": fix("modernes_fruehparty.html"),
        "spaetschicht": fix("modernes_spaetschicht.html"),
        "dublin-legends": fix("modernes_dublin.html"),
        "robots.txt": "",
    })
    termine = modernes.hole(http, VON, BIS, {})
    titel = {(t.tag, t.titel, t.uhrzeit) for t in termine}
    assert (date(2026, 12, 4), "Frühparty Ü30", "18:00") in titel          # JSON-LD
    assert (date(2026, 12, 4), "Spätschicht – 80s & Wave", "23:00") in titel  # Text nahe Titel, nicht Seitenleiste
    assert (date(2026, 12, 5), "Dublin Legends", "20:00") in titel          # Beginn vor Einlass
    assert not any("sonntagskonzert" in u for u in http.urls)               # Sonntag: keine Detailseite
    assert len(termine) == 4                                                # … zählt aber im Status
    assert len(auswertung.nur_fr_sa(termine, VON, BIS)) == 3


def test_eisen():
    http = FakeHttp({
        "veranstaltungen.php": fix("eisen_liste.html"),
        "eckkneipendisco-2026-12-05": fix("eisen_eckkneipe.html"),
        "dark-dezember-2026-12-11": fix("eisen_dark.html"),
    })
    roh = eisen.hole(http, VON, BIS, {})
    assert len(roh) == 3                                           # Do 26.11. zählt im Status mit …
    assert not any("bad-luck-baby" in u for u in http.urls)        # … aber ohne Detailseite
    termine = {t.titel: t for t in auswertung.nur_fr_sa(roh, VON, BIS)}
    assert set(termine) == {"ECKKNEIPENDISCO!", "Dark Dezember"}  # Do 26.11. fällt weg
    assert termine["ECKKNEIPENDISCO!"].uhrzeit == "21:00"
    assert termine["Dark Dezember"].tag == date(2026, 12, 11)


def test_aladin_datum_und_raum_aus_der_karte():
    http = FakeHttp({"unser-programm": fix("aladin_programm.html"), "veranstaltungen/34495": fix("aladin_dm.html"),
                     "veranstaltungen/": "<html><body>keine Uhrzeit</body></html>"})
    termine = {t.titel: t for t in aladin.hole(http, VON, BIS, {})}
    assert set(termine) == {"Depeche Mode - The Cure - The Smiths - Party", "Old but Gold", "BOOMBOX",
                            "70 JAHRE BRAVO", "Aladin Allstars"}
    dm = termine["Depeche Mode - The Cure - The Smiths - Party"]
    assert (dm.tag, dm.ort, dm.uhrzeit) == (date(2026, 11, 21), "Tivoli", "22:00")
    assert termine["Old but Gold"].ort == "Aladin"
    assert termine["70 JAHRE BRAVO"].ort == "Aladin & Tivoli"
    assert termine["Aladin Allstars"].ort == "Tivoli"             # Titel zählt nicht als Raum
    assert termine["BOOMBOX"].tag == date(2026, 11, 26)
    assert not any("boombox" in u for u in http.urls)             # Donnerstag: keine Detailseite


def test_aladin_datum_vor_titel():
    karten_html = "".join(
        f'<div><span>{d}</span><h3><a href="/veranstaltungen/{slug}/">{t}</a></h3><p>Tivoli</p></div>'
        for d, slug, t in [("Fr., 4. Dezember 2026", "a", "Erste"), ("Sa., 5. Dezember 2026", "b", "Zweite"),
                           ("Fr., 11. Dezember 2026", "c", "Dritte")])
    http = FakeHttp({"unser-programm": f"<html><body>{karten_html}</body></html>"})
    termine = {t.titel: t.tag for t in aladin.hole(http, VON, BIS, {"details": False})}
    assert termine == {"Erste": date(2026, 12, 4), "Zweite": date(2026, 12, 5), "Dritte": date(2026, 12, 11)}


def test_polyester():
    http = FakeHttp({"mec-ical-feed": fix("polyester.ics")})
    termine = auswertung.nur_fr_sa(polyester.hole(http, VON, BIS, {}), VON, BIS)
    nach_titel = {t.titel: t for t in termine}
    assert set(nach_titel) == {"Konzert: MATH ON MONDAY", "Gothic Nachtschicht", "Frühtanz Club"}
    assert nach_titel["Gothic Nachtschicht"].abend == date(2026, 12, 4)   # Sa 00:30 → Freitagabend
    assert nach_titel["Konzert: MATH ON MONDAY"].kategorien == ["Konzert/Live"]
    assert all(t.stadt == "Oldenburg" for t in termine)


@pytest.mark.parametrize("ohne_kopf,eine_zelle", [(False, False), (True, False), (True, True)])
def test_dark_kalender_liest_titel_und_filtert_feiertage(ohne_kopf, eine_zelle):
    eintraege = {(1, 1): "Neujahr", (1, 15): "The House Of Usher + UP - JEVER",
                 (1, 16): "Dark Entries\nWave Night", (12, 31): "Silvester Schwarz Tanzen"}
    art = {"ohne_kopf": ohne_kopf, "eine_zelle": eine_zelle}
    http = FakeHttp({"Kalender%202027%20Bremen": dark_csv(2027, eintraege, **art),
                     "Kalender%202026%20Bremen": dark_csv(2027, {}, **art)})  # 2026 fehlt → Google liefert 2027
    warnungen = []
    termine = dark_kalender.hole(http, date(2026, 11, 21), date(2027, 12, 31), {}, warn=warnungen.append)
    funde = {(t.tag, t.titel) for t in termine}
    assert (date(2027, 1, 15), "The House Of Usher + UP - JEVER") in funde
    assert (date(2027, 1, 16), "Dark Entries") in funde and (date(2027, 1, 16), "Wave Night") in funde
    assert (date(2027, 12, 31), "Schwarz Tanzen") in funde      # Feiertag vorn abgeschnitten
    assert not any(t.titel == "Neujahr" for t in termine)
    assert all(t.artverwandt and t.ort == "" for t in termine)
    assert any("2026" in w for w in warnungen)                    # falsches Blatt erkannt und verworfen
    assert not any(t.tag.year == 2026 for t in termine)


def test_dark_kalender_kw_nummer_nur_montags_entfernt():
    assert dark_kalender.titel_aus_rest("Gothic Night 5", "Mo") == ["Gothic Night"]
    assert dark_kalender.titel_aus_rest("Gothika 2", "Sa") == ["Gothika 2"]
    assert dark_kalender.titel_aus_rest("44", "Mo") == []


# --- Sheet A (lesen) --------------------------------------------------------------------------

def test_calavera_monatsblatt():
    zeilen = list(csv.reader(io.StringIO(fix("sheet_a_dezember_2026.csv"))))
    abende = calavera.lese_monat(zeilen, 2026, 12)
    assert abende[date(2026, 12, 4)] == "Nachtschwärmer"
    assert abende[date(2026, 12, 6)].startswith("Honey")
    assert calavera.lese_monat(zeilen, 2027, 1) is None   # anderes Blatt geliefert → erkannt


# --- Auswertung -------------------------------------------------------------------------------

def test_duplikate_innerhalb_quelle():
    a = Termin(quelle="m", titel="Wave Night Party", tag=date(2026, 12, 4), url="u")
    b = Termin(quelle="m", titel="Wave Night", tag=date(2026, 12, 4), beginn=zu_datetime(date(2026, 12, 4), 22, 0))
    c = Termin(quelle="m", titel="Frühparty", tag=date(2026, 12, 4))
    ergebnis = auswertung.zusammenfuehren([a, b, c])
    assert len(ergebnis) == 2
    assert any(t.uhrzeit == "22:00" for t in ergebnis)   # der mit Uhrzeit bleibt


def test_artverwandt_und_kollision():
    stichworte = {"artverwandt": ["wave", "depeche mode"], "ausschluss": ["kinderdisco"]}
    fr = date(2026, 12, 4)
    t1 = Termin(quelle="m", titel="Depeche Mode – The Cure Party", tag=fr, stadt="Bremen")
    t2 = Termin(quelle="m", titel="Schlagerabend", tag=fr, stadt="Bremen")
    t3 = Termin(quelle="p", titel="New Wave Club", tag=fr, stadt="Oldenburg")
    t4 = Termin(quelle="m", titel="Wave Kinderdisco", tag=fr, stadt="Bremen")
    auswertung.markiere_artverwandt([t1, t2, t3, t4], stichworte)
    eigene = {fr: "Nachtschwärmer"}
    assert auswertung.kollision(t1, eigene) == auswertung.HOCH
    assert auswertung.kollision(t2, eigene) == ""
    assert auswertung.kollision(t3, eigene) == auswertung.MITTEL
    assert not t4.artverwandt


def test_zwei_termine_einer_location_in_einer_zelle_und_dark_hinweis():
    fr = date(2026, 12, 4)
    termine = [
        Termin(quelle="modernes", titel="Spätschicht", tag=fr, beginn=zu_datetime(fr, 23, 0), ort="Modernes"),
        Termin(quelle="modernes", titel="Frühparty Ü30", tag=fr, beginn=zu_datetime(fr, 18, 0), ort="Modernes"),
        Termin(quelle="dark_kalender", titel="Spätschicht", tag=fr, artverwandt=True),
    ]
    auswertung.dark_hinweise(termine)
    z = auswertung.zellen(termine, {fr: "Nachtschwärmer"})
    assert z[fr]["modernes"] == "18:00 Frühparty Ü30\n23:00 Spätschicht"
    assert z[fr]["dark_kalender"] == "⚠ Spätschicht (= Modernes)"


# --- Gesamtlauf und Schreibschutz ---------------------------------------------------------------

def test_gesamtlauf_ohne_netz():
    http = FakeHttp({
        "/programm/": fix("modernes_programm.html"),
        "fruehparty-ue30": fix("modernes_fruehparty.html"),
        "spaetschicht": fix("modernes_spaetschicht.html"),
        "dublin-legends": fix("modernes_dublin.html"),
        "veranstaltungen.php": fix("eisen_liste.html"),
        "eckkneipendisco-2026-12-05": fix("eisen_eckkneipe.html"),
        "dark-dezember-2026-12-11": "<html></html>",   # kaputte Detailseite → Titel aus Slug
        "mec-ical-feed": fix("polyester.ics"),
        "unser-programm": fix("aladin_programm.html"),
        "veranstaltungen/34495": fix("aladin_dm.html"),
        "aladin-bremen.de/veranstaltungen/": "<html></html>",
        "/shows": fix("shagall_shows.html"),
        "category/termine/page/": "<html></html>",
        "category/termine": fix("zollkantine_termine.html"),
        "zakk.klubraum.org": fix("zakk_start.html"),
        "/bl1/": fix("openligadb_bl1.json"),
        "shows-tickets": fix("lila_eule.html"),
        "pink-lemon-party": fix("pink_lemon.html"),
        "events/?month=202612": fix("weserterrassen-202612.html"),
        "events/?month=202701": fix("weserterrassen-202701.html"),
        "weserterrassen": fix("weserterrassen.html"),
        "/dfb/": "[]",
        "Kalender%202026%20Bremen": dark_csv(2027, {}, ohne_kopf=True),
        "Kalender%202027%20Bremen": dark_csv(2027, {(1, 15): "Spätschicht"}, ohne_kopf=True),
        "Dezember%202026": fix("sheet_a_dezember_2026.csv"),
        "gviz": '"x"\n',                               # andere Monatsblätter: leer
    })
    import yaml
    konfig = yaml.safe_load((ROOT / "planer" / "quellen.yml").read_text(encoding="utf-8"))
    stichworte = yaml.safe_load((ROOT / "planer" / "stichworte.yml").read_text(encoding="utf-8"))
    zellen, termine, status, eigene, spalten = planer_cli.lauf(http, VON, BIS, konfig, stichworte, None)
    fr = date(2026, 12, 4)
    assert "18:00 Frühparty Ü30" in zellen[fr]["modernes"]
    assert "⚠ 23:00 Spätschicht – 80s & Wave" in zellen[fr]["modernes"]  # artverwandt (wave/80s) + Calavera-Abend
    assert "◐" in zellen[fr]["polyester"]                                # Gothic in Oldenburg
    assert zellen[date(2026, 12, 11)]["eisen"].endswith("Dark Dezember")   # aus dem Slug
    assert [s for _, s in spalten] == ["Werder", "Dark-Kalender", "Modernes", "Aladin/Tivoli", "Eisen", "Polyester OL",
                                       "Shagall", "Zollkantine", "zakk", "Lila Eule", "Pink Lemon",
                                       "Weserterrassen"]
    assert zellen[date(2026, 12, 4)]["shagall"] == "22:00 XMAS CLUBBING"
    assert zellen[date(2026, 12, 4)]["zollkantine"] == "20:00 Hond // Farson // Buried"
    assert zellen[date(2026, 11, 27)]["werder"] == "20:30 HEIM Werder – Dortmund"
    assert zellen[date(2026, 12, 6)]["modernes"] == "Sonntagskonzert"   # So 06.12. steht in Sheet A → relevant
    assert date(2026, 12, 13) not in zellen                             # So 13.12. hat keine Zeile → nicht
    assert zellen[date(2026, 11, 21)]["aladin"].startswith("◐ 22:00 Depeche Mode")  # kein eigener Abend im Fixture
    assert not any(s["fehler"] for s in status)
    text = planer_cli.tabelle(zellen, eigene, spalten, VON, BIS)
    assert "Fr 04.12.2026   Calavera: Nachtschwärmer" in text


def test_eine_kaputte_quelle_haelt_die_anderen_nicht_auf():
    http = FakeHttp({"mec-ical-feed": fix("polyester.ics")})   # Modernes antwortet nicht
    konfig = {"quellen": [{"id": "modernes"}, {"id": "polyester"}]}
    zellen, termine, status, eigene, spalten = planer_cli.lauf(http, VON, BIS, konfig, {}, None, mit_calavera=False)
    st = {s["quelle"]: s for s in status}
    assert st["modernes"]["fehler"] and not st["polyester"]["fehler"]
    assert st["polyester"]["fr_sa"] == 3
    bericht, problem = planer_cli.statusbericht(status)
    assert problem and "✗ Modernes" in bericht


def test_schreiben_nur_in_sheet_a():
    sheets.pruefe_schreibziel(sheets.SHEET_A)
    with pytest.raises(sheets.SchreibVerbot):
        sheets.pruefe_schreibziel(sheets.SHEET_B)
    with pytest.raises(sheets.SchreibVerbot):
        sheets.pruefe_schreibziel("irgendwas")


def test_kein_code_schreibt_in_sheet_b():
    """Sheet B darf nur in sheets.py (Konstante) und im Dark-Kalender (lesen) vorkommen."""
    fundorte = [p.relative_to(ROOT).as_posix() for p in (ROOT / "planer").rglob("*.py")
                if "SHEET_B" in p.read_text(encoding="utf-8")]
    assert sorted(fundorte) == ["planer/quellen/dark_kalender.py", "planer/sheets.py"]
    quelltext = (ROOT / "planer" / "quellen" / "dark_kalender.py").read_text(encoding="utf-8")
    assert "lese_blatt(http, sheets.SHEET_B" in quelltext
    assert "schreib" not in quelltext.lower().replace("ausschreib", "")


def test_status_nur_verdaechtig_wenn_gar_nichts_kommt():
    ok = [{"quelle": "eisen", "spalte": "Eisen", "roh": 2, "fr_sa": 0, "fehler": "", "warnungen": [], "sekunden": 1}]
    leer = [{"quelle": "eisen", "spalte": "Eisen", "roh": 0, "fr_sa": 0, "fehler": "", "warnungen": [], "sekunden": 1}]
    assert planer_cli.statusbericht(ok) == ("✓ Eisen: 0 an relevanten Tagen (2 insgesamt, 1 s)", False)
    assert planer_cli.statusbericht(leer)[1] is True


# --- Etappe 2: Schreiben in Sheet A -----------------------------------------------------------

from planer import schreiben  # noqa: E402

DEZ = [["", "", "Titel", "Theke", "Tür", "DJ"], [],
       ["Fr", "04.12.", "Nachtschwärmer", "Jorma", "", "DJ Kijote"],
       ["Sa", "05.12.", "Wave To The 80s", "Tine", "", "MZ"],
       ["So", "06.12.", "Honey Café", "", "", "Kijote"], [],
       ["Fr", "11.12.", "90s?", "", "", "Matze"],
       ["So", "13.12.", "Honey Cafe: Flashdance", "", "", "Kijote"], [],
       ["Do", "31.12.", "Silvester", "Celine", "", "Pete"]]
SPALTEN = [("dark_kalender", "Dark-Kalender"), ("modernes", "Modernes")]


def anwenden(modell: list[list[str]], plan: schreiben.MonatsPlan) -> list[list[str]]:
    """Plan so auf eine Kopie anwenden, wie es die API täte (Einfügen der Reihe nach, dann Werte)."""
    m = [list(z) for z in modell]
    for i, _ in plan.einfuegen:
        m.insert(i, [])
    for i, z in plan.neue_zeilen:
        m[i] = (m[i] + ["", ""])[:max(2, len(m[i]))]
        m[i][0:2] = z[:2]
    for j, titel in plan.kopf.items():
        m[0] += [""] * (j + 1 - len(m[0]))
        m[0][j] = titel
    for j, werte in plan.spalten.items():
        for k, w in enumerate(werte):
            z = m[k + 1]
            z += [""] * (j + 1 - len(z))
            z[j] = w
    return m


def test_plane_monat_spalten_und_fehlende_fr_sa():
    zellen = {date(2026, 12, 4): {"modernes": "18:00 Frühparty\n23:00 Spätschicht"},
              date(2026, 12, 12): {"dark_kalender": "⚠ Dark Entries"},
              date(2026, 12, 19): {"modernes": "Weihnachtsparty"}}
    plan = schreiben.plane_monat(DEZ, 2026, 12, date(2026, 11, 21), date(2026, 12, 31), SPALTEN, zellen)
    m = anwenden(DEZ, plan)
    assert m[0][6:8] == ["Dark-Kalender ⚙", "Modernes ⚙"]
    # Spalten A–F bestehender Zeilen unverändert, Reihenfolge der eigenen Zeilen gleich
    alte = [z[:6] for z in DEZ[2:] if z]
    assert [z[:6] for z in m if len(z) > 2 and z[2]][1:] == [(z + [""] * 6)[:6] for z in alte]
    nach_datum = {z[1]: z for z in m[1:] if len(z) > 1 and z[1]}
    assert nach_datum["04.12."][7] == "18:00 Frühparty\n23:00 Spätschicht"
    # Sa 12.12. kommt in den Block seiner Woche: nach Fr 11.12., vor So 13.12.
    daten = [z[1] for z in m[1:] if len(z) > 1 and z[1]]
    assert daten.index("12.12.") == daten.index("11.12.") + 1 and daten.index("13.12.") == daten.index("12.12.") + 1
    assert nach_datum["12.12."][:2] == ["Sa", "12.12."] and nach_datum["12.12."][6] == "⚠ Dark Entries"
    # 18./19.12. und 25./26.12. fehlten ganz: neue Wochenblöcke vor Silvester, mit Leerzeilen getrennt
    assert daten == ["04.12.", "05.12.", "06.12.", "11.12.", "12.12.", "13.12.", "18.12.", "19.12.",
                     "25.12.", "26.12.", "31.12."]
    i18 = next(i for i, z in enumerate(m) if len(z) > 1 and z[1] == "18.12.")
    assert not any(m[i18 - 1]) and nach_datum["19.12."][7] == "Weihnachtsparty"
    i26 = next(i for i, z in enumerate(m) if len(z) > 1 and z[1] == "26.12.")
    assert not any(m[i26 + 1]) and m[i26 + 2][1] == "31.12."


def test_plane_monat_ist_wiederholbar_und_laesst_vergangenes_stehen():
    zellen = {date(2026, 12, 4): {"modernes": "Alt"}, date(2026, 12, 11): {"modernes": "Neu"}}
    erst = anwenden(DEZ, schreiben.plane_monat(DEZ, 2026, 12, date(2026, 11, 21), date(2026, 12, 31), SPALTEN, zellen))
    # eine Woche später: 04.12. liegt in der Vergangenheit, Quelle liefert ihn nicht mehr
    zellen2 = {date(2026, 12, 11): {"modernes": "Neu"}}
    plan2 = schreiben.plane_monat(erst, 2026, 12, date(2026, 12, 7), date(2026, 12, 31), SPALTEN, zellen2)
    assert not plan2.einfuegen and not plan2.kopf
    zweit = anwenden(erst, plan2)
    assert len(zweit) == len(erst)                        # keine neuen Zeilen beim zweiten Lauf
    assert next(z for z in zweit if len(z) > 1 and z[1] == "04.12.")[7] == "Alt"   # Vergangenes bleibt
    assert next(z for z in zweit if len(z) > 1 and z[1] == "11.12.")[7] == "Neu"
    plan3 = schreiben.plane_monat(zweit, 2026, 12, date(2026, 12, 7), date(2026, 12, 31), SPALTEN, zellen2)
    assert plan3.leer                                     # nichts geändert → kein Schreibzugriff


def test_plane_monat_haengt_hinter_eigene_zusatzspalten_an():
    blatt = [["", "", "Titel", "Theke", "Tür", "DJ", "Notiz", "Modernes ⚙"], [], ["Fr", "04.12.", "X"]]
    plan = schreiben.plane_monat(blatt, 2026, 12, date(2026, 12, 1), date(2026, 12, 5), SPALTEN, {})
    assert plan.kopf == {8: "Dark-Kalender ⚙"}           # Notiz (G) bleibt, Modernes (H) wird wiederverwendet
    assert 6 not in plan.spalten


def test_neues_monatsblatt():
    inhalt = schreiben.plane_neues_blatt(2027, 6, ["", "", "Titel"])
    assert inhalt[0] == ["", "", "Titel"] and inhalt[1] == []
    daten = [z[1] for z in inhalt[2:] if z]
    assert daten == ["04.06.", "05.06.", "11.06.", "12.06.", "18.06.", "19.06.", "25.06.", "26.06."]
    assert inhalt[4] == []                                # Leerzeile zwischen den Wochen


def test_monatsnamen_und_fehlende_monate():
    assert schreiben.monat_aus_name("Dezember 2026") == (2026, 12)
    assert schreiben.monat_aus_name("Crawler-Status") is None
    da = {"Dezember 2026": {}, "Januar 2027": {}, "Crawler-Status": {}}
    assert schreiben.fehlende_monate(da, date(2026, 12, 3), date(2027, 3, 31)) == [(2027, 2), (2027, 3)]


class FakeSitzung:
    def __init__(self):
        self.posts = []

    def post(self, url, json, timeout):
        self.posts.append((url, json))

        class R:
            status_code, text = 200, "{}"

            @staticmethod
            def json():
                return {}
        return R()


def test_api_schreibt_nur_sheet_a():
    with pytest.raises(sheets.SchreibVerbot):
        schreiben.SheetsApi(FakeSitzung(), sheets.SHEET_B)
    s = FakeSitzung()
    api = schreiben.SheetsApi(s)
    api.id = sheets.SHEET_B                               # selbst wenn jemand das Ziel nachträglich ändert …
    with pytest.raises(sheets.SchreibVerbot):
        api.schreibe([("'X'!A1", [["x"]])])
    assert s.posts == []                                  # … geht nichts raus


def test_wende_monat_an_erzeugt_richtige_bereiche():
    s = FakeSitzung()
    api = schreiben.SheetsApi(s)
    zellen = {date(2026, 12, 12): {"modernes": "Party"}}
    plan = schreiben.plane_monat(DEZ, 2026, 12, date(2026, 12, 7), date(2026, 12, 13), SPALTEN, zellen)
    schreiben.wende_monat_an(api, "Dezember 2026", 42, plan)
    assert all(sheets.SHEET_A in url for url, _ in s.posts)
    einfuegen = s.posts[0][1]["requests"]
    assert einfuegen == [{"insertDimension": {"range": {"sheetId": 42, "dimension": "ROWS", "startIndex": 7,
                                                        "endIndex": 8}, "inheritFromBefore": True}}]
    bereiche = {d["range"]: d["values"] for d in s.posts[1][1]["data"]}
    assert bereiche["'Dezember 2026'!A8:B8"] == [["Sa", "12.12."]]
    assert bereiche["'Dezember 2026'!G1"] == [["Dark-Kalender ⚙"]]
    assert bereiche["'Dezember 2026'!H2:H11"][6] == ["Party"]   # Zeile 8 = Index 6 ab Zeile 2


def test_testkopie_per_umgebung_aber_nie_sheet_b(monkeypatch):
    monkeypatch.setenv("PLANER_SHEET_A", "kopie123")
    assert schreiben.SheetsApi(FakeSitzung()).id == "kopie123"
    monkeypatch.setenv("PLANER_SHEET_A", sheets.SHEET_B)
    with pytest.raises(sheets.SchreibVerbot):
        schreiben.SheetsApi(FakeSitzung())


# --- Etappe 3: Shagall, Zollkantine, zakk -----------------------------------------------------

from planer.quellen import shagall, zakk, zollkantine  # noqa: E402


def test_shagall():
    http = FakeHttp({"/shows": fix("shagall_shows.html")})
    termine = {t.titel: t for t in shagall.hole(http, VON, BIS, {})}
    assert "K-POP by Korean Party Factory" not in termine          # 20.11. vor VON
    gk = termine["GAYKISS CLUBBING"]
    assert (gk.tag, gk.uhrzeit, gk.abend) == (date(2026, 11, 21), "23:00", date(2026, 11, 21))
    assert termine["XMAS CLUBBING"].tag == date(2026, 12, 4)
    assert termine["GAYKISS – BIG SILVESTER PARTY 26/27"].tag == date(2026, 12, 31)


def test_shagall_warnt_ohne_links():
    warnungen = []
    assert shagall.hole(FakeHttp({"/shows": "<html><body>Lädt…</body></html>"}), VON, BIS, {},
                        warn=warnungen.append) == []
    assert "JavaScript" in warnungen[0]


def test_zakk():
    termine = zakk.hole(FakeHttp({"zakk.klubraum.org": fix("zakk_start.html")}), VON, BIS, {})
    assert [(t.tag, t.uhrzeit, t.titel) for t in termine] == [
        (date(2026, 11, 21), "21:00", "The Spin Society // offener Vinylabend"),
        (date(2026, 11, 26), "19:00", "zakk: öffentliches treffen"),
        (date(2026, 11, 27), "21:00", "rosa solikneipe"),
        (date(2026, 11, 28), "20:00", "take back the night kneipe")]


def test_zollkantine_datumsformen_und_seiten():
    http = FakeHttp({"/page/2/": fix("zollkantine_seite2.html"), "/page/3/": "<html><body></body></html>",
                     "category/termine": fix("zollkantine_termine.html")})
    termine = zollkantine.hole(http, date(2026, 11, 1), date(2026, 12, 31), {})
    paare = {(t.tag, t.titel, t.uhrzeit) for t in termine}
    assert (date(2026, 11, 10), "Sotabosc // Aufhebung // Undrone", "20:00") in paare
    assert {(d, u) for d, ti, u in paare if ti == "shortbandcontest 2026"} == {
        (date(2026, 12, 27), "18:00"), (date(2026, 12, 28), "18:00"), (date(2026, 12, 29), "18:00")}
    assert {d for d, ti, _ in paare if ti == "WD*42 Festival 2026"} == {date(2026, 11, 13), date(2026, 11, 14),
                                                                        date(2026, 11, 15)}
    assert (date(2026, 12, 12), "Dark Wave Abend", "21:00") in paare           # von Seite 2
    assert all(t.ort == "Zollkantine" for t in termine)
    assert not any(t.titel in ("Zollkantine", "Angebot", "Termine") for t in termine)


def test_zollkantine_jahr_raten():
    assert zollkantine._jahr_raten(27, 12, date(2026, 11, 21)) == 2026
    assert zollkantine._jahr_raten(9, 1, date(2026, 11, 21)) == 2027


# --- Werder Bremen ------------------------------------------------------------------------------

from planer.quellen import werder  # noqa: E402


def test_werder():
    http = FakeHttp({"/bl1/": fix("openligadb_bl1.json"), "/dfb/": fix("openligadb_dfb.json")})
    termine = auswertung.nur_fr_sa(werder.hole(http, VON, BIS, {}), VON, BIS)
    zeilen = {(t.abend, t.uhrzeit, t.titel) for t in termine}
    assert zeilen == {(date(2026, 11, 27), "20:30", "HEIM Werder – Dortmund"),
                      (date(2026, 12, 5), "15:30", "auswärts Bayern – Werder")}   # So-Spiel, Pokal-Mi, Bayern–BVB weg
    assert {u for u in http.urls} >= {"https://api.openligadb.de/getmatchdata/bl1/2026"}


def test_werder_zeit_vorlaeufig_und_saison():
    http = FakeHttp({"/bl1/": fix("openligadb_bl1.json"), "/dfb/": "[]"})
    termine = werder.hole(http, date(2026, 11, 21), date(2027, 3, 31), {})
    feb = next(t for t in termine if t.tag == date(2027, 2, 6))
    assert feb.titel.endswith("(Zeit vorläufig)") and feb.ort == "Weserstadion"
    assert werder.saison(date(2027, 2, 6)) == 2026 and werder.saison(date(2027, 8, 1)) == 2027


def test_erste_spalte_konfigurierbar():
    plan = schreiben.plane_monat(DEZ, 2026, 12, date(2026, 12, 1), date(2026, 12, 5), SPALTEN, {}, erste_spalte="I")
    assert plan.kopf == {8: "Dark-Kalender ⚙", 9: "Modernes ⚙"}
    assert schreiben.spaltenindex("AA") == 26
    # schon vorhandene Quellenspalte bleibt, wo sie ist (z. B. von Hand verschoben)
    blatt = [["", "", "Titel", "Theke", "Tür", "DJ", "Modernes ⚙"], [], ["Fr", "04.12.", "X"]]
    plan = schreiben.plane_monat(blatt, 2026, 12, date(2026, 12, 1), date(2026, 12, 5), SPALTEN, {}, erste_spalte="I")
    assert plan.kopf == {8: "Dark-Kalender ⚙"}


# --- Lila Eule -----------------------------------------------------------------------------------

from planer.quellen import lila_eule  # noqa: E402


def test_lila_eule_datum_vor_und_nach_titel():
    http = FakeHttp({"shows-tickets": fix("lila_eule.html")})
    termine = {(t.tag, t.uhrzeit, t.titel) for t in lila_eule.hole(http, date(2026, 11, 1), date(2027, 3, 31), {})}
    assert (date(2026, 11, 28), "19:30", "IGINIO (RELEASE SHOW), special guests Spirited Away & She Danced Slowly") in termine
    assert (date(2026, 12, 21), "20:30", "BITUME + special guest") in termine            # „neuer Termin:“ davor
    assert (date(2026, 12, 4), "20:00", "SOFTCULT, special guest RAPID STRIDES") in termine
    assert (date(2026, 12, 31), "23:30", "SILVESTER PARTY – 80's til 2020s sure shots, mit DJ FIRST CLAAS") in termine
    assert (date(2027, 1, 30), "20:15", "JOCHEN PRANG (Stand Up Comedy)") in termine     # Titel vor dem Datum
    assert (date(2027, 2, 12), "20:00", "SANDRA SCHMIDT (Stand Up Comedy)") in termine
    assert (date(2027, 2, 27), "19:30", "DARKWAYS, special guest CULT NOIR") in termine
    assert len(termine) == 8


def test_lila_eule_warnt_bei_falschem_wochentag():
    warnungen = []
    lila_eule.termine_aus_text("Fr. 21.12.2026\num 20 h\nBITUME", warnungen.append)
    assert "Mo" in warnungen[0]


def test_sonntag_nur_wenn_zeile_im_sheet():
    zellen = {date(2026, 12, 6): {"modernes": "Sonntagskonzert"}, date(2026, 12, 20): {"modernes": "Weg damit"}}
    plan = schreiben.plane_monat(DEZ, 2026, 12, date(2026, 12, 1), date(2026, 12, 31), SPALTEN, zellen)
    m = anwenden(DEZ, plan)
    nach_datum = {z[1]: z for z in m[1:] if len(z) > 1 and z[1]}
    assert nach_datum["06.12."][7] == "Sonntagskonzert"              # So-Zeile gibt es → wird gefüllt
    assert "20.12." not in nach_datum                               # So-Zeilen legt der Planer nie an
    assert all(z[0] in ("Fr", "Sa") for _, z in plan.neue_zeilen)


def test_sonntag_ohne_titel_zaehlt_als_tag_aber_nicht_als_eigener_abend():
    zeilen = [["", "", "Titel"], ["So", "13.12.", ""], ["Sa", "12.12.", "Party"]]
    abende = calavera.lese_monat(zeilen, 2026, 12)
    assert abende == {date(2026, 12, 13): "", date(2026, 12, 12): "Party"}
    t = Termin(quelle="m", titel="Dark", tag=date(2026, 12, 13), artverwandt=True, stadt="Bremen")
    assert auswertung.kollision(t, abende) == auswertung.MITTEL     # kein eigener Abend → nur ◐


def test_format_der_quellspalten():
    s = FakeSitzung()
    api = schreiben.SheetsApi(s)
    plan = schreiben.plane_monat(DEZ, 2026, 12, date(2026, 12, 1), date(2026, 12, 5), SPALTEN, {}, erste_spalte="I")
    schreiben.wende_monat_an(api, "Dezember 2026", 42, plan, schriftgroesse=7, spaltenbreite=80, umbruch=True)
    fmt = s.posts[-1][1]["requests"]
    assert {"repeatCell": {"range": {"sheetId": 42, "startColumnIndex": 8, "endColumnIndex": 9},
                           "cell": {"userEnteredFormat": {"textFormat": {"fontSize": 7}, "wrapStrategy": "WRAP"}},
                           "fields": "userEnteredFormat.textFormat.fontSize,userEnteredFormat.wrapStrategy"}} in fmt
    assert {"updateDimensionProperties": {"range": {"sheetId": 42, "dimension": "COLUMNS", "startIndex": 9,
                                                    "endIndex": 10},
                                          "properties": {"pixelSize": 80}, "fields": "pixelSize"}} in fmt
    assert len(fmt) == 4                                        # nur die zwei ⚙-Spalten, nicht A–H


def test_format_auch_ohne_aenderung_und_abschaltbar():
    blatt = [["", "", "Titel", "Theke", "Tür", "DJ", "", "", "Dark-Kalender ⚙", "Modernes ⚙"], [],
             ["Fr", "04.12.", "X", "", "", "", "", "", "", ""], ["Sa", "05.12.", "Y"]]
    plan = schreiben.plane_monat(blatt, 2026, 12, date(2026, 12, 1), date(2026, 12, 5), SPALTEN, {}, erste_spalte="I")
    assert plan.leer
    s = FakeSitzung()
    schreiben.wende_monat_an(schreiben.SheetsApi(s), "Dezember 2026", 1, plan, schriftgroesse=7, formatieren=True)
    assert len(s.posts) == 1 and len(s.posts[0][1]["requests"]) == 2
    s2 = FakeSitzung()
    schreiben.wende_monat_an(schreiben.SheetsApi(s2), "Dezember 2026", 1, plan, formatieren=True)
    assert s2.posts == []                                       # ohne Einstellung wird nichts formatiert


# --- Pink Lemon, Weserterrassen ------------------------------------------------------------------

from planer.quellen import pink_lemon, weserterrassen  # noqa: E402


def test_pink_lemon():
    termine = pink_lemon.hole(FakeHttp({"pink-lemon-party": fix("pink_lemon.html")}), VON, BIS, {})
    # Oktober ist vorbei, Februar liegt hinter BIS
    assert [(t.tag, t.uhrzeit, t.titel, t.ort) for t in termine] == [
        (date(2026, 12, 5), "20:00", "Pink Lemon Party", "Up den Höfen")]


WESER = {"events/?month=202612": fix("weserterrassen-202612.html"),
         "events/?month=202701": fix("weserterrassen-202701.html"),
         "events/?month=202611": fix("weserterrassen.html")}


def test_weserterrassen_contao_nur_jungbrunnen_mit_blaettern():
    http = FakeHttp(WESER)
    termine = weserterrassen.hole(http, VON, BIS, {"nur": ["Jungbrunnen"]})
    # Jazz, Kinderflohmarkt, Weihnachtskonzert usw. werden ignoriert, Titel in der Schreibweise aus quellen.yml
    assert [(t.tag, t.uhrzeit, t.titel, t.url) for t in termine] == [
        (date(2026, 11, 28), "20:00", "Jungbrunnen", "https://www.weserterrassen.com/events/details/jungbrunnen-60/"),
        (date(2026, 12, 26), "20:00", "Jungbrunnen", "https://www.weserterrassen.com/events/details/jungbrunnen-61/")]
    assert [u.rsplit("=", 1)[1] for u in http.urls] == ["202611", "202612", "202701"]


def test_weserterrassen_contao_andere_reihe_und_fehlender_monat():
    warnungen = []
    nur_nov = {"events/?month=202611": fix("weserterrassen.html")}
    termine = weserterrassen.hole(FakeHttp(nur_nov), VON, BIS, {"nur": ["jazz"]}, warn=warnungen.append)
    assert termine == []                      # Jazz am 04.11. liegt vor VON
    termine = weserterrassen.hole(FakeHttp(nur_nov), date(2026, 11, 1), date(2026, 12, 31),
                                  {"nur": ["jazz", "flohmarkt"]}, warn=warnungen.append)
    assert [(t.tag, t.uhrzeit, t.titel) for t in termine] == [
        (date(2026, 11, 4), "20:00", "Jazz & More: JazzInvaders"), (date(2026, 11, 8), "10:00", "Kinderflohmarkt")]
    assert any("12/2026 nicht abrufbar" in w for w in warnungen)


def test_weserterrassen_nur_jungbrunnen_aus_text():
    termine = weserterrassen.hole(FakeHttp({"weserterrassen": fix("weserterrassen-text.html")}), VON, BIS, {})
    assert [(t.tag, t.uhrzeit, t.titel) for t in termine] == [
        (date(2026, 11, 28), "20:00", "Jungbrunnen – Die Ü30-Party"),
        (date(2026, 12, 26), "20:00", "Jungbrunnen – Die Ü30-Party")]


def test_weserterrassen_jsonld_und_warnung():
    html = ('<html><head><script type="application/ld+json">[{"@type":"Event","name":"Jungbrunnen",'
            '"startDate":"2026-11-28T20:00:00+01:00","url":"https://www.weserterrassen.com/events/jb/"},'
            '{"@type":"Event","name":"Lesung","startDate":"2026-11-27T19:00:00+01:00"}]</script></head></html>')
    termine = weserterrassen.hole(FakeHttp({"weserterrassen": html}), VON, BIS, {})
    assert [(t.tag, t.uhrzeit, t.titel, t.url) for t in termine] == [
        (date(2026, 11, 28), "20:00", "Jungbrunnen", "https://www.weserterrassen.com/events/jb/")]
    warnungen = []
    weserterrassen.hole(FakeHttp({"weserterrassen": "<html>nix</html>"}), VON, BIS, {}, warn=warnungen.append)
    assert "Jungbrunnen" in warnungen[0]
