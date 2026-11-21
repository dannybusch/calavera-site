# 0008 – Kellerfunk: Darstellung und Kennzeichnung

Stand: Oktober/November 2026 · Status: gilt

## Kontext
Kellerfunk ist das Livestream-Format aus dem Calavera-Keller (live.calavera.club). Sendungen sind meist
**kein** Clubabend. Danny: „den kellerfunk muss man besser kennzeichnen, die leute checken das sonst nicht“.

## Entscheidung
- Quelle ist immer der Sendeplan `https://live.calavera.club/config.yml` (`shows:`), nicht `events/`.
- Website: Kellerfunk-Karte (Ruhezustand heißt „Kellerfunk“, nicht das negativ klingende „Off Air“),
  dezentes „On Air“-Schild, On-Air-Band auf allen Seiten (rot live, grauer Countdown < 60 min, wegklickbar ohne Speichern).
- Überall, wo Sendungen neben Clubabenden stehen (Wochenbild, Reels, Presse), deutlich: rotes Etikett
  „Kellerfunk“ + „Nur im Livestream · live.calavera.club“ bzw. „Im Club & im Livestream“, wenn `club: true`.
- Fällt eine Sendung auf einen Clubabend (gleicher Tag, ±3 h), erscheint sie nur einmal – beim Event als „Club & Stream“.
