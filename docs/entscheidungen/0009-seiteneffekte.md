# 0009 – Seiteneffekte: global, zeitgesteuert, generisch

Stand: Oktober/November 2026 · Status: gilt

## Entscheidung
- Eigenes Modul für Effekte auf der ganzen Seite (nicht pro Event): `config.yml → seiteneffekte:` mit optional
  `start`/`ende` (Bremer Zeit). Erste: `spinne`, `logo` (das Auge im Logo lebt) – entstanden für Halloween.
- Kein Effekt für eine bestimmte Person (ein „stewart“-Memorial wurde wieder entfernt). Stattdessen generisch
  `rip` mit Feldern `person`, `daten`, `text`, `link`, `sterne` – für musikrelevante Verstorbene.
