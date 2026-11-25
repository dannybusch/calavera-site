# 0013 – Hochladen mit `hochladen.py` statt lftp

Stand: 11.11.2026 · Status: gilt

## Kontext
`ubuntu-latest` wechselte auf Ubuntu 26.04 („resolute“), dessen Paketquellen nicht erreichbar waren – die
lftp-Installation hing minutenlang. Danny: „ätzend, wenn das so ewig dauert“.

## Entscheidung
- Runner fest auf `ubuntu-24.04`.
- Hochladen per `hochladen.py` (Python/paramiko, nur pip): Spiegeln wie `lftp mirror --reverse --delete`,
  `.htaccess`, `.well-known/`, `_behalten/` bleiben unangetastet, Server-Schlüssel gegen known_hosts.
- Nur geänderte Inhalte: Prüfsummen in `.calavera-pruefsummen.json` auf dem Server (fehlt sie, einmal alles).
  Workflow-Häkchen „Alles neu hochladen“.
- lftp-Variante bleibt auskommentiert im Workflow.

## Nachtrag 25.11.2026 – Reihenfolge und Fehler
Danny: erst die Bilder, dann die Einzelseiten der Events, dann die Programmseiten.
- Hochgeladen wird in Stufen: 1. Bilder & Dateien (alles außer HTML), 2. Veranstaltungsseiten
  (`/programm/<slug>/`, `/intern/<slug>/`), 3. Übersichtsseiten (zuletzt `/programm/` und Startseite),
  4. `sitemap.xml`, `llms.txt`, `robots.txt`, Kalender-Dateien, `build.json`. Gelöscht wird danach, Seiten vor Bildern.
- Jede Datei geht unter Zwischennamen (`….calavera-neu`) hoch und wird dann per posix-rename ersetzt – nie eine
  halbe Seite online. Kann der Server das nicht, direkt überschreiben (wie vorher).
- Schlägt eine Datei fehl, läuft die Stufe zu Ende, spätere Stufen und Löschungen bleiben aus (Lauf wird rot).
- Zwischenstand der Prüfsummen nach jeder Stufe und spätestens jede Minute: nach Verbindungsabbruch macht der
  nächste Versuch dort weiter. Nicht löschbare Dateien: Warnung (gelb), kein Abbruch.

## Folgen
Optional per `.htaccess` sperrbar: `<Files ".calavera-pruefsummen.json">Require all denied</Files>`.
