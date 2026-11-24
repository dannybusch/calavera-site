# Offene Punkte

Stand: 23.11.2026. Erledigtes streichen oder in eine Entscheidung (docs/entscheidungen/) überführen.

## Wartet auf Danny

- **rausgegangen einrichten:** API-Token bei zentrale@rausgegangen.de anfragen (das Doku-„secret“ ist kein Token)
  → Secret `RAUSGEGANGEN_API_KEY`; `python rausgegangen.py location` → `rausgegangen.location` in config.yml;
  Vorschau-Links prüfen, dann `veroeffentlichen: true`. Erster echter Lauf: Fehlermeldungen der API ansehen
  (PATCH-Adresse und Pfad der Location-Suche sind aus der Doku nicht eindeutig, siehe 0012).
  Nebenbei fragen: Ist rausgegangen „Official Events“-Partner von Facebook?
- **Pressemitteilung:** Variables `SMTP_HOST`/`SMTP_PORT`/`SMTP_USER` + Secret `SMTP_PASSWORD` sind angelegt
  (21.11.); erster echter Versand gegen STRATO steht noch aus – Zusammenfassung des Laufs prüfen.
- **FAQ-Seite:** Antworten fehlen zu Mindestalter, Garderobe, Kartenzahlung, Rauchen, Barrierefreiheit, Anfahrt/ÖPNV.
- **Facebook-Weg wählen** (siehe 0015): Browser-Mittelweg, lokales Script, `social.py` (Seite/Instagram
  automatisch posten) oder Event-Paket zum Abtippen.
- **Google:** Startseite und /programm/ in der Search Console neu crawlen lassen; prüfen, ob die KI-Antwort
  nun echte Titel nennt (siehe 0014).

- **Landingpages `/dark/` und `/party/`** (siehe 0017): Entwurfstexte in `landing/dark.md` und `landing/party.md`
  lesen und umschreiben; ggf. Menüeintrag in `config.yml → navigation`; nach dem Deploy in der Search Console einreichen.

- **IndexNow einrichten** (siehe 0019): Variable `INDEXNOW_KEY` im Environment `calavera-site.env` anlegen;
  nach dem ersten Deploy prüfen, dass `www.calavera.club/<schlüssel>.txt` erreichbar ist und der Schritt
  „Suchmaschinen benachrichtigen“ grün ist. Optional Bing Webmaster Tools anmelden.
- **Google:** `sitemap.xml` (jetzt mit `lastmod`) einmal in der Search Console einreichen.
- **Adventskalender** (siehe 0020): **Zuerst** die zwei `cron`-Zeilen für 00:07 Uhr in `.github/workflows/deploy.yml`
  eintragen (`deploy-yml-adventskalender.patch`; Claude darf Workflow-Dateien nicht schreiben). Dann `advent/adventskalender2026.yml` füllen (24 Türen), `einleitung`/`description`
  schreiben, `draft: false`; Menüzeile `- { label: "Adventskalender", href: "/adventskalender/" }` in
  `config.yml → navigation`; nach dem 1.12. prüfen, dass der Lauf um 00:07 Uhr kommt. Entwürfe unter
  `entwuerfe/adventskalender/` können danach weg.

- **Planungskalender** (siehe 0021): Service-Account anlegen und Sheet A als Bearbeiter freigeben (Schritte in
  der README, Abschnitt Planungskalender), Secret `GOOGLE_SA_JSON`. Dann einmal lokal oder per Actions
  `python planer.py --schreiben` und das Ergebnis in Sheet A ansehen. Workflow `.github/workflows/planer.yml`
  ist angelegt (Ausnahme von der Workflow-Regel, von Danny bestätigt am 21.11.); `planer-workflow.yml` löschen.

- **Kalender-Abo** (siehe 0022): ist ohne Einstellung **an**. Zum Abschalten in `config.yml` ergänzen:
  `kalender:` / `  abo: false`. Nach dem Deploy auf einem iPhone (Knopf „Abonnieren“) und einem Android-Handy
  (Knopf „Google Kalender“) einmal abonnieren und prüfen, dass Termine mit Flyer-Link ankommen.
  Android (24.11.): Das zuerst per webcal:// angelegte Abo in der fremden App wieder löschen. Dann über
  „Google Kalender“ hinzufügen, in der Google-Kalender-App unter Einstellungen „Calavera Bremen“ →
  Synchronisieren einschalten. Klappt das nicht, Bescheid geben (Plan B: Anleitung mit „Adresse kopieren“).

## Ideen, nicht begonnen

- `config.yml → site.description` nutzt „1/4 Bremen“; für Suchmaschinen wäre „Viertel“ besser (Danny entscheidet).
- `social.py`: Wochenbild (media.py) montags und Reels automatisch auf Facebook-Seite/Instagram posten
  (Meta-App, Seiten-Token als Secret, IG-Profikonto nötig).

## Beobachten

- GitHub-Runner: Deploy läuft fest auf `ubuntu-24.04`; irgendwann auf neuere Version prüfen.
- Dauer des Deploy-Uploads mit `hochladen.py` (Prüfsummen) – erwartet: nur geänderte Seiten.

## Referenzen

- Design-Fläche „Calavera Relaunch – 4 Entwürfe“ (Claude-Artefakt): https://claude.ai/artifact/BJGHhQ3SBQeSJ6fDV3pUYa
  – u. a. Startseiten-Varianten, Event-Detail, Hero-Schriften, Halloween-Effekte, Wochenbild-Entwürfe A/B/C.
- Rausgegangen-API-Doku: https://api.zentrale.rausgegangen.de/v2/ (Zugang über das Doku-„secret“).
