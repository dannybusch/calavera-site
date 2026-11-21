# 0010 – Reels als eigener Prozess

Stand: Oktober/November 2026 · Status: gilt

## Entscheidung
- `reels.py` ist vom Website-Build getrennt (eigener Workflow, eigene Pakete: Playwright + ffmpeg).
- Vorlagen als HTML-Animationen in `reels/vorlagen/` (countdown, flyerfahrt, freunde, kellerfunk, teaser, woche).
- Kein Import fremder SVG/PDF-Layouts als Reel-Vorlage – stattdessen „reel für reel“ gezielt bauen.
- „Freunde von“-Reels enden immer mit „u.v.a.m.“, das bis zum Flyer stehen bleibt (09.11.2026).
- Kellerfunk-Monatsreel (`reels.py kellerfunk`) liest den Sendeplan, zeigt Club/Stream-Kennzeichnung und Genres.
