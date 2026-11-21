# 0004 – `events/` und `config.yml` pflegt Danny selbst

Stand: Oktober 2026 · Status: gilt

## Kontext
„Bitte die events/ nicht anpassen. Das mache ich lokal selbst.“ – „bitte keine config.yml mitschicken,
ich ergänze die Zeile selbst.“

## Entscheidung
Claude ändert weder Event-Dateien noch `config.yml`. Neue Einstellungen werden als YAML-Schnipsel genannt;
der Code hat immer einen sinnvollen Standard, falls die Einstellung fehlt. Tests mit eigenen Event-Dateien
oder geänderter Konfiguration nur in einer Kopie des Projekts.

## Folgen
- Jede neue Option: Standardwert im Code + Schnipsel in README und in der Antwort an Danny.
- Ebenso `.htaccess`: Danny schreibt sie von Hand (UTF-8 ohne BOM); Claude schlägt nur Zeilen vor.
