# CLAUDE.md – Calavera Bremen (www.calavera.club)

Kurzfassung für Claude. Ausführlich für Menschen: `README.md`. Warum etwas so ist: `docs/entscheidungen/`.
Was noch offen ist: `docs/offen.md`. Neue Grundsatzentscheidungen dort als eigene Datei protokollieren.

## Projekt

Statische Website des Calavera, eines kleinen Clubs im Bremer Viertel (Körnerwall 1). `build.py` (Python +
Jinja2) erzeugt aus `events/*.md`, `pages/*.md`, `config.yml` und `templates/` fertiges HTML in `dist/`.
GitHub Actions baut und lädt per SFTP zu STRATO hoch. Kein Server-Code, keine Datenbank, keine Cookies.
Daneben eigenständige Scripts für Social Media, Presse und rausgegangen.de (siehe unten).

Ansprechpartner ist Danny. Kommunikation, Code-Kommentare, Ausgaben und Oberfläche: **Deutsch**.

## Feste Regeln (immer einhalten)

- **`events/` nicht anfassen.** Veranstaltungen pflegt Danny selbst. Zum Testen eigene Dateien nur in einer Kopie.
- **`config.yml` nicht ändern.** Neue Einstellungen als YAML-Schnipsel nennen – Danny ergänzt sie selbst.
  Code muss ohne die neue Einstellung mit sinnvollem Standard laufen.
- **Keine Daten im Browser speichern:** keine Cookies, kein `localStorage`/`sessionStorage`/IndexedDB.
  Zustand (z. B. weggeklicktes Band) nur im Speicher der Seite. Keine externen Ressourcen (Schriften lokal).
- **Zugangsdaten nur in GitHub Secrets/Variables** bzw. Umgebungsvariablen – nie in Dateien, Logs oder Commits.
- **`.htaccess` schreibt Danny von Hand** (UTF-8 ohne BOM). Nur Zeilen vorschlagen, nicht ausliefern.
- **Hoher Qualitätsanspruch** bei allem Sichtbaren: lieber eine Variante richtig als viele halbgare.
  Effekte, Layouts, Reels vor dem Abgeben im Browser/als Bild prüfen.
- **Kellerfunk immer klar als Livestream kennzeichnen** („Nur im Livestream · live.calavera.club“), damit
  niemand vor verschlossener Tür steht – auf Bildern, in Reels, in der Pressemitteilung.
- **Nichts erfinden** in öffentlichen Texten (keine Zitate, keine Fakten, die nicht in den Dateien stehen).
- **Nie committen oder pushen – Danny committet immer selbst.** Auch nicht danach fragen. Kleine, nachvollziehbare Änderungen; README mitpflegen.

## Befehle

```bash
pip install -r requirements.txt               # Website, rausgegangen.py, presse.py
pip install -r requirements-reels.txt         # zusätzlich für reels.py/media.py (+ python -m playwright install chromium; reels: ffmpeg)

python build.py                               # → dist/
python build.py --serve                       # → http://localhost:8000
python build.py --now "2026-11-20 21:00"      # Zeitpunkt simulieren (im Browser zusätzlich ?now=2026-11-20T21:00)
python build.py --strict                      # Abbruch bei kaputter Event-Datei

python reels.py <teil-des-dateinamens> --vorlage freunde --schnell   # Reel (Vorlagen: reels/vorlagen/)
python reels.py kellerfunk --monat 2026-12                           # Kellerfunk-Monatsreel
python media.py [--vorlage a,b,c] [--naechste|--woche 48]            # „Diese Woche“-Bild, JPG 1080×1350
python presse.py [--naechste] [--senden]                             # Wochen-Pressemitteilung (Probelauf ohne --senden)
python rausgegangen.py [status|location] [--senden]                  # rausgegangen.de (Probelauf ohne --senden)
python hochladen.py dist/ <zielordner> --probe                       # SFTP-Spiegel wie im Deploy (+ sitemap lastmod)
python indexnow.py geaendert.txt --probe                             # geänderte Seiten an IndexNow (Bing & Co.)
python planer.py [--bis 2027-06] [--nur modernes] [--schreiben]      # Planungskalender: Fr/Sa-Termine anderer Locations (ohne --schreiben Probelauf)
python -m pytest tests/planer -q                                     # Tests Planungskalender (ohne Netz)
```

Alle Scripts: `--help`, und `--now "JJJJ-MM-TT HH:MM"` zum Simulieren. Senden/Hochladen nur mit ausdrücklichem Schalter.

## Aufbau

| Pfad | Inhalt |
|---|---|
| `build.py` | Generator: Events laden, Bilder (inkl. 16:9 `breit.jpg`), Seiten, ICS, JSON-LD, `llms.txt` |
| Kalender-Abo | `calavera.ics` (Name „Calavera Bremen“; `kalender.ics` = unverlinkte Kopie für Alt-Abos) + `/<landing>/calavera-<landing>.ics` (`ics_for(…, abo=True)`, `abo_termine`, `kalender_abo`), Kasten `partials/kalender_abo.html`; **derzeit aus** (Standard); `config.yml → kalender.abo: true` schaltet ein. Aus = alter Stand: `kalender.ics` + Knopf „Programm in den Kalender“ (0022) |
| `landing/` | Landingpages (`/dark/`, `/party/`): Text + SEO-Kopf pflegt Danny; Auswahl der Termine per `zeigt:` (siehe `_vorlage.md`) |
| `advent/` | Adventskalender `adventskalender<jahr>.yml` → `/adventskalender/` (`load_advent`, `advent_stand`): **nur Türen bis heute ins HTML, YAML nie ausliefern**; Deploy 30.11.–23.12. zusätzlich 00:07 |
| `templates/` | Jinja2: `base`, `index`, `programm`, `event`, `archiv`, `page`, `landing`, `intern_*`; `partials/tile.html`, `effekte.html`, `kellerfunk.html` |
| `static/js/site.js` | Live-Logik im Browser: vergangene Termine ausblenden, „Heute/Läuft gerade“, Startseiten-Übernahme, On-Air-Band, Titel-Einpassen (`wortPassen`) |
| `static/js/seiteneffekte.js` | globale Seiteneffekte (`spinne`, `logo`, `rip`) |
| `static/css/site.css`, `fx/*.css`, `seiteneffekte/*.css` | Grundlayout, je Effekt eine Datei |
| `reels.py` + `reels/vorlagen/` | Instagram-Reels (HTML-Animation → Playwright → ffmpeg) |
| `media.py` + `media/vorlagen/` | Wochenbild in 3 Vorlagen: `programmzettel`, `plakatwand`, `wochenstreifen` |
| `presse.py` | Wochen-Pressemitteilung als Mail (SMTP) an Danny zum Weiterleiten |
| `rausgegangen.py` | Events per Rausgegangen-API v2 eintragen (Upsert über `mapping_id` `calavera-<slug>`) |
| `hochladen.py` | SFTP-Spiegel mit Prüfsummen (`.calavera-pruefsummen.json` auf dem Server); setzt `<lastmod>` in sitemap.xml, Liste geänderter Seiten |
| `indexnow.py` | geänderte Seiten an IndexNow melden (Bing, Yandex, Seznam …); Google liest die Sitemap |
| `planer.py` + `planer/` | Planungskalender (0021): ein Plugin pro Quelle in `planer/quellen/`, nur Fr/Sa. **Sheet B (Dark-Kalender) nie beschreiben**, in Sheet A nur eigene Spalten + fehlende Fr/Sa-Zeilen |
| `.github/workflows/` | `deploy` (Push + täglich), `rausgegangen` (nach Deploy), `presse` (Mo früh), `reels`, `media` (von Hand) |

## Design

Hintergrund `#0b0b0b`, Text `#d1cabf`, hell `#f1ebe2`, Rot `#b3122e` (Flächen) / `#e0485e` (roter Text).
Schriften lokal: Bebas Neue (Display, Großbuchstaben), Space Grotesk (Text), IBM Plex Mono (Daten/Labels).
Rahmen neutral (`inset 0 0 0 1px #2c2a29`), **kein roter Rahmen** um große Kachel/Takeover (Ausnahme: Effekt `neon`).
Titel werden nie mitten im Wort getrennt – lieber Schrift verkleinern.

## Wie die Teile zusammenhängen

- **Event-Datei:** YAML-Kopf (`title`, `start`, `end`, `djs`, `genres`, `tags`, `art`, `teaser`, `visual`,
  `effekte`, `eintritt`, `einlass`, `stream`, `highlight`, `reihe`, `fans_of`, `social_title`, `draft`, …;
  erklärt in `events/_vorlage.md`) + Markdown-Text. Dateiname = Slug = URL. Flyer gleichnamig daneben.
  Vergangen = Ende erreicht (ohne `end` +6 h). Optional für Scripts: `rausgegangen: false`, `rausgegangen_kategorie`.
- **Bild-Cache:** alle Pillow-Bilder über `aus_cache()` in `build.py` → `.cache/bilder/` (Prüfsumme aus Quelle,
  Einstellungen, Funktionscode, Pillow-Version). Neue Bildarten ebenso einbinden; `--ohne-cache` zum Vergleichen.
- **Zeit:** Build-Zeitpunkt kann veraltet sein → `site.js` entscheidet live (`window.calaveraJetzt`, `?now=`).
- **Effekte (43):** Makro `fx_<name>(ev, wo, img)` in `partials/effekte.html` (wo = flyer/tile/page),
  CSS in `static/css/fx/<name>.css`, Eintrag in `EFFEKTE` (+ ggf. `EFFEKT_ALIAS`, `EFFEKT_CSS`) in `build.py`.
  Nur auf den vordersten `programm.effekte_kacheln` Kacheln; nur Compositor-Animationen (transform/opacity);
  `prefers-reduced-motion` und `fx-paused` respektieren; README-Tabelle ergänzen.
- **Seiteneffekte:** `config.yml → seiteneffekte:` mit optional `start`/`ende` (Bremer Zeit); Modul in
  `seiteneffekte.js` + CSS; Name in `SEITENEFFEKTE` (`build.py`).
- **Startseiten-Übernahme:** Event des Tages ersetzt ab X Stunden vorher den Claim
  (`site.startseite_uebernahme`, `site.startseite_uebernahme_stunden`, Standard 6).
- **Kellerfunk:** Sendeplan kommt von `https://live.calavera.club/config.yml` (`shows:`); Website-Karte,
  On-Air-Band (rot live, grauer Countdown < 60 min), Reels, Wochenbild und Presse lesen ihn.
  Offline testen mit `--plan datei.yml`.
- **Landingpages:** `landing/*.md` → `Landing` in `build.py` (`load_landings`, `Landing.passt`, `landing_json_ld`),
  Template `landing.html`. Text über/unter den Kacheln getrennt durch `<!-- mehr -->`.
  Event-Feld `auch_auf: [slug]` holt einzelne Events zusätzlich auf eine Landingpage, ohne Reihe/Reihen-Link. Texte gehören Danny – nur Entwürfe vorschlagen.
- **SEO/KI:** Event-Seiten `MusicEvent`-JSON-LD; Startseite + Programm `NightClub` **mit** allen kommenden
  Events (sonst erfinden KI-Antworten aus „Fr + Sa“ namenlose Partys); `dist/llms.txt`.

## Testen

Nie gegen echte Dienste „ausprobieren“: Probeläufe (`--probe`, ohne `--senden`), `--now`, `--plan`.
Sichtbares mit `python build.py --serve` und `?now=` im Browser prüfen; Bilder/Reels ansehen, nicht nur bauen.
Für Experimente mit Event-Dateien eine Kopie des Projekts verwenden (wegen `events/`-Regel).

## Secrets & Variablen (GitHub)

| Name | Art | Wofür |
|---|---|---|
| `SFTP_HOST`, `SFTP_PORT`, `SFTP_USER`, `SFTP_REMOTE_DIR`, `SFTP_USER_IS_WEBROOT` | Variables | Deploy |
| `SFTP_PASSWORD`, `SFTP_KNOWN_HOSTS` | Secrets | Deploy |
| `RAUSGEGANGEN_API_KEY` | Secret | rausgegangen.py (Token von zentrale@rausgegangen.de) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER` (optional `SMTP_SICHERHEIT`) | Variables | presse.py |
| `SMTP_PASSWORD` | Secret | presse.py |
| `INDEXNOW_KEY` | Variable | build.py (Schlüsseldatei) + indexnow.py (Meldung an Bing & Co.) |
| `GOOGLE_SA_JSON` | Secret | planer.py `--schreiben` (Service-Account, nur Sheet A freigegeben) |

Fehlt ein Zugang: geplante Läufe enden mit gelber Warnung, von Hand gestartete werden rot (nie still grün).
