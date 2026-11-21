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

## Folgen
Optional per `.htaccess` sperrbar: `<Files ".calavera-pruefsummen.json">Require all denied</Files>`.
