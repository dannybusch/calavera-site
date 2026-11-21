# 0007 – Neutrale Rahmen, Startseiten-Übernahme

Stand: Oktober/November 2026 · Status: gilt

## Entscheidung
- Kein roter Rahmen um die große Kachel und die Übernahme – „generell störend“. Neutraler Rahmen
  (`inset 0 0 0 1px #2c2a29`). Ausnahme: Effekte, deren Wesen ein Leuchtrahmen ist (`neon`).
- Startseiten-Übernahme: Die Veranstaltung des Tages ersetzt ab X Stunden vor Beginn den Claim
  „Vielfalt. Musik. Freude“. Einstellbar: `site.startseite_uebernahme` (an/aus), `site.startseite_uebernahme_stunden`
  (Standard 6). Die übernommene Veranstaltung erscheint im Programm darunter nicht doppelt hervorgehoben.
- Lange Titel: nie mitten im Wort trennen; `site.js` (`wortPassen`) verkleinert die Schrift bis max. auf die Hälfte (14.11.2026).
