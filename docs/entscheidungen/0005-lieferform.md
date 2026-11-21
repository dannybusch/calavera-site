# 0005 – Lieferform: geänderte Dateien + Patch (Cloud-Chat) → direkt im Repo (Desktop)

Stand: November 2026 · Status: abgelöst für lokale Sitzungen

## Kontext
Bis November 2026 lief die Arbeit in einem Cloud-Chat ohne Zugriff auf Dannys Repo. Geliefert wurden nur
geänderte Dateien (ZIP) plus ein Patch gegen den jeweils zuletzt gelieferten Stand (Patch-Kette).

## Entscheidung
Mit Claude Desktop und lokalem Repo wird direkt in den Dateien gearbeitet. Committen/Pushen nur auf Ansage.
Die Regeln aus 0004 (events/, config.yml, .htaccess) gelten weiter.

## Folgen
Keine Patch-Kette mehr nötig; Änderungen sind über Git nachvollziehbar.
