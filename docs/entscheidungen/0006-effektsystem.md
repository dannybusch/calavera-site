# 0006 – Effekte auf Flyern/Kacheln: Aufbau und Qualitätsanspruch

Stand: Oktober/November 2026 · Status: gilt

## Entscheidung
- Je Effekt ein Jinja-Makro `fx_<name>(ev, wo, img)` (`partials/effekte.html`, wo = flyer/tile/page) und eine
  CSS-Datei `static/css/fx/<name>.css`; Registrierung in `EFFEKTE`/`EFFEKT_ALIAS`/`EFFEKT_CSS` (`build.py`).
  Nur das CSS der tatsächlich genutzten Effekte wird eingebunden.
- Nur auf den vordersten `programm.effekte_kacheln` Kacheln; Ebenen mit `z-index: -1` in isolierten Eltern.
- Nur Compositor-Animationen (transform/opacity), angehalten außerhalb des Bildes (`fx-paused`),
  `prefers-reduced-motion` respektiert.
- Ist ein Effekt aktiv, werden Badges leiser – der Effekt soll wirken.
- **Hoher Anspruch:** Effekte werden vor Abgabe im Browser angesehen. Abgelehnt und entfernt (Nov 2026):
  bandsalat, fanzine, nachtfalter, publikum, waschbaer, fallblatt, tanzschritte. Behalten u. a.: lichtorgel
  (1–5; 5 = 3×3-Raster wie im Club), tanzflaeche (1–3), disco1–3 (2 = Projektion von der Kugel, „nicht wie
  eine geordnete Armee“; Alias disco → disco2), superdark, funemotes, heartbubble. glitch erscheint sofort.

## Folgen
Neuer Effekt = Makro + CSS + Registrierung + README-Tabelle + Sichtprüfung (Kachel, große Kachel, Detailseite, Handy).
