# 0021 – Planungskalender: Termine anderer Locations in Sheet A

Status: gilt (Etappen 1–3 umgesetzt; Schreiben in einer Kopie von Sheet A erfolgreich getestet am 21.11.)

## Kontext

Wir planen unsere Abende im Google Sheet „Calavera Terminkalender“ (Sheet A, ein Blatt pro Monat,
z. B. „Dezember 2026“). Um Kollisionen mit artverwandten Partys zu vermeiden, sollen die Fr/Sa-Termine
anderer Locations und der Dark-Kalender (Sheet B „Partyplanungen Bremen-Oldenburg“) dort automatisch
als Spalten erscheinen. Ausführliches Konzept: Claude-Doc „Calavera Planungskalender – Konzept Termin-Crawler“.

## Entscheidung

- `planer.py` im Site-Repo, eigenständig wie `presse.py` (hängt nicht an `build.py`), Paket `planer/`.
- **Ein Plugin pro Quelle** in `planer/quellen/`, Spaltenname = `SPALTE` im Plugin, Reihenfolge in
  `planer/quellen.yml`. Plugins lesen möglichst Dinge, die Umbauten überleben: iCal, JSON-LD, Datum im Link.
- **Nur Freitag und Samstag**, alles an diesen Abenden. Beginn vor 6 Uhr zählt zum Vorabend.
- Mehrere Termine einer Location an einem Abend stehen untereinander in derselben Zelle.
- Vergangene Abende behalten ihren letzten Stand; eine Quelle mit Fehler lässt ihre Zellen unverändert.
- Schreibzugriff per Service-Account (Entscheidung am 21.11. gegen Apps Script): ein Ort für alles, und das
  Konto ist technisch nur in Sheet A freigegeben.
- **Sheet B wird nie beschrieben.** Lesen per CSV-Export (reiner GET). Ab Etappe 2 schreibt nur ein
  Service-Account, der in Sheet B höchstens Betrachter ist; `sheets.pruefe_schreibziel()` weist jede
  andere Sheet-ID als A ab (Test vorhanden).
- In Sheet A schreibt der Crawler nur in seine eigenen Spalten und darf fehlende Fr/Sa-Zeilen ergänzen
  (nur A/B gefüllt). Spalten A–F bestehender Zeilen fasst er nie an, Zeilen löscht er nie.
- Dark-Kalender: Ort egal, Titel zählt, Zellfarben egal. Gleicher Abend in einer Location-Spalte →
  bleibt in beiden Spalten, Hinweis „= Modernes“.
- Kollision: ⚠ artverwandt (Dark-Kalender oder `planer/stichworte.yml`) + eigener Abend + nicht Oldenburg;
  ◐ artverwandt, aber Oldenburg oder kein eigener Abend.

## Folgen

- zakk zeigt online nur die nächsten Tage; weiter voraus gibt es dort nichts Maschinenlesbares.
- Scraper können still kaputtgehen → Statusbericht je Quelle, „0 Termine an Fr/Sa“ gilt als verdächtig.
- Etappen: 1 Grundgerüst + Dark-Kalender, Modernes, Eisen, Polyester (Probelauf) · 2 Schreiben in Sheet A
  (Service-Account, `--schreiben`, `--fuelle-bis`, Workflow) · 3 Shagall, Zollkantine, zakk (Aladin schon da) ·
  4 Stichworte mit echten Daten · 5 optional Mail, rausgegangen.de als Fallback.
