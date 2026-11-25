"""Tests für hochladen.py (Reihenfolge, Zwischenstand, Fehler) – ohne Netz: python -m pytest tests/hochladen -q

Statt eines echten Servers dient ein Ordner im Testverzeichnis; FakeSftp bildet die benutzten SFTP-Aufrufe nach
und protokolliert, in welcher Folge hochgeladen, umbenannt und gelöscht wird.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("hochladen", ROOT / "hochladen.py")
hochladen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hochladen)


class Attr:
    def __init__(self, pfad: Path):
        st = pfad.stat()
        self.filename, self.st_mode, self.st_size, self.st_mtime = pfad.name, st.st_mode, st.st_size, st.st_mtime


class FakeSftp:
    def __init__(self, wurzel: Path, posix_rename: bool = True, scheitert: tuple = ()):
        self.wurzel, self.kann_posix, self.scheitert = wurzel, posix_rename, set(scheitert)
        self.log: list[tuple[str, str]] = []

    def _p(self, pfad: str) -> Path:
        return self.wurzel / pfad.lstrip("/")

    def stat(self, pfad):
        if not self._p(pfad).exists():
            raise FileNotFoundError(pfad)

    def listdir_attr(self, pfad):
        p = self._p(pfad)
        if not p.is_dir():
            raise FileNotFoundError(pfad)
        return [Attr(c) for c in sorted(p.iterdir())]

    def open(self, pfad, modus="r"):
        p = self._p(pfad)
        if not p.is_file():
            raise FileNotFoundError(pfad)
        return io.BytesIO(p.read_bytes())

    def putfo(self, fo, pfad):
        self._p(pfad).write_bytes(fo.read())

    def put(self, lokal, pfad, confirm=True):
        rel = pfad.removeprefix("/ziel/").removesuffix(hochladen.NEU_ENDUNG)
        if rel in self.scheitert:
            raise PermissionError(13, "Permission denied", pfad)
        shutil.copyfile(lokal, self._p(pfad))
        self.log.append(("put", pfad))

    def posix_rename(self, alt, neu):
        if not self.kann_posix:
            raise OSError("Operation unsupported")
        os.replace(self._p(alt), self._p(neu))
        self.log.append(("rename", neu))

    def rename(self, alt, neu):
        self._p(alt).rename(self._p(neu))

    def remove(self, pfad):
        p = self._p(pfad)
        if not p.is_file():
            raise FileNotFoundError(pfad)
        p.unlink()
        self.log.append(("remove", pfad))

    def mkdir(self, pfad):
        self._p(pfad).mkdir()

    def rmdir(self, pfad):
        self._p(pfad).rmdir()

    def close(self):
        pass


class FakeClient:
    def close(self):
        pass


def dist_anlegen(d: Path) -> Path:
    dateien = {
        "index.html": "<a href='/programm/'>Start</a>",
        "404.html": "weg",
        "robots.txt": "User-agent: *",
        "llms.txt": "Calavera",
        "kalender.ics": "BEGIN:VCALENDAR",
        "build.json": "{}",
        "sitemap.xml": '<?xml version="1.0"?><urlset><url><loc>https://www.calavera.club/</loc></url>'
                       "<url><loc>https://www.calavera.club/programm/2026-12-04-nacht/</loc></url></urlset>",
        "programm/index.html": "Programm",
        "programm/archiv/index.html": "Archiv",
        "programm/2026-12-04-nacht/index.html": "<img src='/media/events/2026-12-04-nacht/640.webp'>",
        "programm/2026-12-04-nacht/termin.ics": "BEGIN:VEVENT",
        "intern/index.html": "intern",
        "intern/2026-12-04-nacht/index.html": "intern nacht",
        "dark/index.html": "Dark",
        "dark/calavera-dark.ics": "BEGIN:VCALENDAR",
        "kontakt/index.html": "Kontakt",
        "media/events/2026-12-04-nacht/640.webp": "BILD",
        "static/css/site.css": "body{}",
        "static/js/site.js": "//",
    }
    for rel, text in dateien.items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(text, encoding="utf-8")
    return d


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    dist = dist_anlegen(tmp_path / "dist")
    server = tmp_path / "server"
    (server / "ziel").mkdir(parents=True)
    (server / "ziel" / ".htaccess").write_text("# von Hand", encoding="utf-8")
    zustand = {"sftp": FakeSftp(server)}
    monkeypatch.setattr(hochladen, "verbinden", lambda: (FakeClient(), zustand["sftp"]))
    return dist, server, zustand


def hochgeladen(sftp) -> list[str]:
    """Reihenfolge, in der Dateien online gingen (Umbenennen bzw. direktes put)"""
    online = []
    for art, pfad in sftp.log:
        if hochladen.PRUEFSUMMEN in pfad:   # Zwischenstand – keine Datei der Website
            continue
        if art == "rename" or (art == "put" and not pfad.endswith(hochladen.NEU_ENDUNG)):
            online.append(pfad.removeprefix("/ziel/"))
    return online


def test_stufen_einteilung():
    s = hochladen.stufe
    assert s("static/css/site.css") == s("media/events/x/640.webp") == s("programm/x/termin.ics") == 0
    assert s("programm/2026-12-04-nacht/index.html") == s("intern/2026-12-04-nacht/index.html") == 1
    assert s("programm/archiv/index.html") == s("programm/index.html") == s("dark/index.html") == 2
    assert s("index.html") == s("404.html") == s("intern/index.html") == 2
    assert s("sitemap.xml") == s("llms.txt") == s("kalender.ics") == s("dark/calavera-dark.ics") == 3


def test_reihenfolge_erst_bilder_dann_veranstaltungen_dann_uebersicht(umgebung):
    dist, server, z = umgebung
    zahl = hochladen.spiegeln(dist, "/ziel", probe=False)
    online = hochgeladen(z["sftp"])
    assert zahl["hoch"] == len(online) == 19
    stufen = [hochladen.stufe(r) for r in online]
    assert stufen == sorted(stufen), online
    # Startseite und Programm als letzte Seiten, danach nur noch Sitemap & Co.
    seiten = [r for r in online if r.endswith(".html")]
    assert seiten[-2:] == ["programm/index.html", "index.html"]
    assert online.index("media/events/2026-12-04-nacht/640.webp") < online.index("programm/2026-12-04-nacht/index.html")
    assert online.index("programm/2026-12-04-nacht/termin.ics") < online.index("programm/2026-12-04-nacht/index.html")
    assert online.index("programm/2026-12-04-nacht/index.html") < online.index("programm/index.html")
    assert online[-1] in ("sitemap.xml", "robots.txt", "llms.txt", "kalender.ics", "build.json", "dark/calavera-dark.ics")
    # keine Zwischennamen übrig, .htaccess unangetastet, Prüfsummen und Seitenstand gespeichert
    assert not list(server.rglob("*" + hochladen.NEU_ENDUNG))
    assert (server / "ziel" / ".htaccess").read_text(encoding="utf-8") == "# von Hand"
    daten = json.loads((server / "ziel" / hochladen.PRUEFSUMMEN).read_text(encoding="utf-8"))
    assert len(daten["dateien"]) == 19 and daten["seiten"]


def test_zweiter_lauf_laedt_nichts(umgebung, capsys):
    dist, server, z = umgebung
    hochladen.spiegeln(dist, "/ziel", probe=False)
    z["sftp"] = FakeSftp(server)
    zahl = hochladen.spiegeln(dist, "/ziel", probe=False)
    assert zahl["hoch"] == 0 and zahl["gleich"] == 19 and not z["sftp"].log
    assert "nichts hochzuladen" in capsys.readouterr().out


def test_probe_aendert_nichts(umgebung):
    dist, server, z = umgebung
    zahl = hochladen.spiegeln(dist, "/ziel", probe=True)
    assert zahl["hoch"] == 19 and not z["sftp"].log
    assert sorted(p.name for p in (server / "ziel").iterdir()) == [".htaccess"]


def test_fehler_bei_veranstaltung_stoppt_vor_uebersicht_und_macht_spaeter_weiter(umgebung):
    dist, server, z = umgebung
    z["sftp"] = FakeSftp(server, scheitert=("programm/2026-12-04-nacht/index.html",))
    with pytest.raises(hochladen.StufenFehler, match="Veranstaltungsseiten"):
        hochladen.spiegeln(dist, "/ziel", probe=False)
    online = hochgeladen(z["sftp"])
    assert "intern/2026-12-04-nacht/index.html" in online           # Rest der Stufe läuft durch
    assert not any(hochladen.stufe(r) >= 2 for r in online)          # aber keine Übersicht, keine Sitemap
    assert not (server / "ziel" / "index.html").exists()
    # Zwischenstand gesichert: der nächste Lauf lädt nur, was fehlt
    z["sftp"] = FakeSftp(server)
    zahl = hochladen.spiegeln(dist, "/ziel", probe=False)
    assert zahl["gleich"] == len(online)
    assert "programm/2026-12-04-nacht/index.html" in hochgeladen(z["sftp"])
    assert not any(hochladen.stufe(r) == 0 for r in hochgeladen(z["sftp"]))


def test_verbindungsabbruch_zwischenstand_nach_stufe(umgebung, monkeypatch):
    dist, server, z = umgebung

    class Abbruch(FakeSftp):
        def put(self, lokal, pfad, confirm=True):
            if "programm/index.html" in pfad:
                raise EOFError("Verbindung weg")
            super().put(lokal, pfad, confirm)

    z["sftp"] = Abbruch(server)
    with pytest.raises(EOFError):
        hochladen.spiegeln(dist, "/ziel", probe=False)
    erster = hochgeladen(z["sftp"])
    z["sftp"] = FakeSftp(server)
    hochladen.spiegeln(dist, "/ziel", probe=False)
    zweiter = hochgeladen(z["sftp"])
    # Bilder und Veranstaltungsseiten (abgeschlossene Stufen) nicht noch einmal
    assert not any(hochladen.stufe(r) <= 1 for r in zweiter)
    assert "programm/index.html" in zweiter and len(erster) + len(zweiter) >= 19


def test_loeschen_nach_dem_hochladen_seiten_vor_bildern(umgebung):
    dist, server, z = umgebung
    hochladen.spiegeln(dist, "/ziel", probe=False)
    shutil.rmtree(dist / "programm" / "2026-12-04-nacht")
    shutil.rmtree(dist / "media" / "events" / "2026-12-04-nacht")
    (dist / "programm" / "index.html").write_text("Programm ohne Nacht", encoding="utf-8")
    z["sftp"] = FakeSftp(server)
    zahl = hochladen.spiegeln(dist, "/ziel", probe=False)
    log = [(a, p.removeprefix("/ziel/")) for a, p in z["sftp"].log if hochladen.PRUEFSUMMEN not in p]
    erstes_loeschen = next(i for i, (a, _) in enumerate(log) if a == "remove")
    assert all(a == "remove" for a, _ in log[erstes_loeschen:])      # erst hoch, dann weg
    weg = [p for a, p in log if a == "remove"]
    assert weg.index("programm/2026-12-04-nacht/index.html") < weg.index("media/events/2026-12-04-nacht/640.webp")
    assert zahl["geloescht"] == 3
    assert not (server / "ziel" / "programm" / "2026-12-04-nacht").exists()


def test_ohne_posix_rename_direkt_hochladen(umgebung):
    dist, server, z = umgebung
    z["sftp"] = FakeSftp(server, posix_rename=False)
    zahl = hochladen.spiegeln(dist, "/ziel", probe=False)
    assert zahl["hoch"] == 19
    assert (server / "ziel" / "index.html").is_file()
    assert not list(server.rglob("*" + hochladen.NEU_ENDUNG))


def test_alter_zwischenname_wird_aufgeraeumt(umgebung):
    dist, server, z = umgebung
    hochladen.spiegeln(dist, "/ziel", probe=False)
    rest = server / "ziel" / "programm" / ("index.html" + hochladen.NEU_ENDUNG)
    rest.write_text("halb", encoding="utf-8")
    z["sftp"] = FakeSftp(server)
    hochladen.spiegeln(dist, "/ziel", probe=False)
    assert not rest.exists()
