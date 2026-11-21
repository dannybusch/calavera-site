# 0001 – Statische Website aus einem Python-Script

Stand: Oktober 2026 · Status: gilt

## Kontext
Kleiner Club, wenig Pflegeaufwand gewünscht, Webspace bei STRATO, kein Budget für Server-Betrieb.

## Entscheidung
`build.py` (Python + Jinja2) erzeugt aus Markdown/YAML (`events/`, `pages/`, `config.yml`) fertiges HTML in `dist/`.
Kein Server-Code, keine Datenbank, kein CMS-Backend. Was sich zeitabhängig ändert (vergangene Termine,
„Läuft gerade“, Übernahme der Startseite, On-Air), entscheidet zusätzlich `site.js` im Browser, weil der
Build älter sein kann als der Seitenaufruf.

## Folgen
- Veranstaltung anlegen = eine `.md` + Flyer ablegen, pushen.
- Zeitlogik existiert doppelt (Build + Browser) und muss zusammenpassen; testbar mit `--now` und `?now=`.
- Täglicher geplanter Build (04:17 UTC), damit Vergangenes auch ohne Push verschwindet.
