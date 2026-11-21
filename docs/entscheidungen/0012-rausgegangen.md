# 0012 – rausgegangen.de per API (`rausgegangen.py`)

Stand: 11.11.2026 · Status: gilt (Einrichtung offen, siehe docs/offen.md)

## Entscheidung
- Je Veranstaltung ein Event mit einer Show in der Calavera-Location. Zuordnung über `mapping_id`
  `calavera-<slug>` (Event) / `calavera-<slug>-1` (Show) – keine lokale Statusdatei nötig.
- Neue Events per POST, geänderte per PATCH nur mit geänderten Feldern; nichts wird automatisch gelöscht
  (`status` listet Übriggebliebenes).
- Probelauf ist Standard; gesendet wird nur mit `--senden`. `published` kommt aus `rausgegangen.veroeffentlichen`
  (Standard false = nur Vorschau). Von Hand veröffentlichte Events werden nicht wieder versteckt.
- Bild: 16:9-Fassung `breit.jpg` (Flyer auf unscharfem Hintergrund, erzeugt vom Build). Ist sie nicht öffentlich
  erreichbar → `1200.jpg` → ohne Bild; lehnt rausgegangen das Bild ab, wird ohne Bild eingetragen und später nachgetragen.
- Läuft auf GitHub nach jedem erfolgreichen Deploy (dann sind die Bilder online).

## Unsicher (aus der Doku nicht eindeutig)
PATCH an Sammel- oder Einzeladresse? Pfad der Location-Suche mit/ohne `/v2/`? Das Script probiert beides.
