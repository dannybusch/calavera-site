# 0011 – „Diese Woche im Calavera“-Bild (`media.py`)

Stand: 02.11.2026 · Status: gilt

## Entscheidung
- Instagram/Facebook-Bild 1080 × 1350, JPG. Drei austauschbare Vorlagen aus den Entwürfen:
  `programmzettel` (a), `plakatwand` (b), `wochenstreifen` (c, Tage ohne Programm schrumpfen).
  Standard ohne Einstellung: alle drei rendern; `media.vorlage` legt eine fest.
- Woche = Mo–So; bereits vergangene Termine fallen weg (`--alle` zeigt sie). Höchstens 6 Termine aufs Bild,
  alle im mitgelieferten Bildtext. `passen.js` verkleinert Titel/Flyer, bis alles passt.
- Ohne Flyer: Kellerfunk → dunkle Funk-Karte, sonst helle Papierkarte mit Namen. Öffentlicher Titel = `social_title`, falls gesetzt.

## Folgen
Entwürfe liegen auf der Design-Fläche „Calavera Relaunch – 4 Entwürfe“ (Boards Woche-A/B/C).
