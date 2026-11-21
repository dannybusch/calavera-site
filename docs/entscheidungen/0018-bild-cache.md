# 0018 – Bild-Cache mit Prüfsumme

Stand: 21.11.2026 · Status: gilt

## Kontext
Der Build wurde immer langsamer (zuletzt ≈ 21 s bei 19 Veranstaltungen). Gemessen: ≈ 20 s davon Pillow –
Effekt-Texturen (≈ 5,5 s, bei jedem Build identisch), Flyer-Fassungen (≈ 0,25 s je Veranstaltung, **auch für
das Archiv**, das jede Woche wächst), Social-Bilder (≈ 0,5 s je kommender Veranstaltung), Seitenbilder (≈ 1 s).
Templates, JSON-LD, ICS, Sitemap zusammen < 1 s. Danny: „Cache mit Checksumme, damit nur geänderte und neue
Bilder neu gerendert werden.“

## Entscheidung
- `aus_cache()` in `build.py`: erzeugte Bilder liegen in `.cache/bilder/<art>-<prüfsumme>/`. Prüfsumme aus
  Inhalt der Quellbilder, Einstellungen, Quelltext der erzeugenden Funktion(en) und Pillow-Version – eine
  Code-Änderung macht die betroffenen Einträge automatisch ungültig, kein Versionszähler zum Hochzählen.
- `dist/` wird weiterhin jedes Mal komplett neu geschrieben; aus dem Cache wird nur kopiert (byte-gleich,
  `hochladen.py` lädt dadurch nicht mehr hoch als vorher).
- Unbenutzte Einträge löscht der Build am Ende. `--ohne-cache` rechnet alles neu, `CALAVERA_BILD_CACHE`
  legt den Ort fest. GitHub Actions: `actions/cache` (Schlüssel mit `run_id`, übernimmt den jüngsten Stand).

## Folgen
Folge-Build ≈ 1 s. Fehlt der Cache (erster Lauf, gelöscht), ist das Ergebnis dasselbe, nur langsamer.
Noch nicht umgesetzt (bei Bedarf): Bilder parallel berechnen, Weichzeichnen auf verkleinerter Fassung.
