# 0022 – Kalender-Abo (`calavera.ics` per webcal://)

Stand: 24.11.2026 · Status: gilt

## Kontext
Aus einer Ideenliste hat Danny „Kalender-Abo“ gewählt: Gäste sollen die Calavera-Termine automatisch im
Handy-Kalender haben. `kalender.ics` gab es schon, aber nur als unauffälliger Link „Programm in den Kalender“
(https, mit `?v=…`): Handys importieren das meist einmalig statt zu abonnieren, und vergangene Termine fielen
sofort heraus. Nachtrag Danny: Das Abo muss sich über `config.yml` ganz abschalten lassen.

## Entscheidung
- **Abo statt Import:** Hauptknopf `webcal://…/calavera.ics` (iPhone, Mac, Outlook), dazu Google Kalender
  (`calendar.google.com/calendar/r?cid=https://…`) für Android. Anfangs stand dort `cid=webcal://…`; Google
  macht daraus `http://` (24.11. bei Danny gesehen) – deshalb https://.
  **Kein Download-Knopf, keine Adresse zum Kopieren** (Danny, 24.11.): nur die zwei Abo-Wege, nichts Technisches.
- **Android (24.11.):** Auf Dannys Samsung S24 öffnete „Abonnieren“ (webcal://) eine fremde App – Android hat
  kein eingebautes Kalender-Abo. „Google Kalender“ meldete „Kalender hinzugefügt“, zeigte aber keine Termine:
  Google synchronisiert per Adresse abonnierte Kalender nicht von selbst aufs Handy, und der erste Abruf dauert.
  Darum auf Android: nur „Google Kalender“ plus 3-Schritte-Anleitung (Hinzufügen → in der App „Synchronisieren“
  einschalten → Geduld beim ersten Abruf). (Zwischenstand „nur am Computer“ war falsch und ist zurückgenommen.)
  Verworfen: Zusatz-Apps wie ICSx⁵ empfehlen (fremde App, für Gäste zu umständlich). Abo-Adressen **ohne** `?v=`, damit sie dauerhaft gleich bleiben.
- Kein eigener Dienst, keine Konten, nichts im Browser gespeichert (0002): nur statische Dateien und Links.
  Der Google-Link ist ein normaler Link, keine eingebundene Ressource.
- **Je Landingpage ein eigenes Abo** (`/dark/calavera-dark.ics`, `/party/calavera-party.ics`) mit genau der Auswahl
  der Seite (`Landing.passt`). „Pro Reihe“ läuft damit über die Landingpages – Reihen ohne Landingpage haben
  keine sichtbare Seite, auf der man ein Abo anbieten könnte.
- Abo-Dateien enthalten auch die Termine der letzten 30 Tage (`kalender.abo_vergangene_tage`), damit Abende
  nicht am Morgen danach aus dem Kalender verschwinden. Kopfzeilen `REFRESH-INTERVAL`/`X-PUBLISHED-TTL` = 6 h.
- Sichtbar als Kasten „Kalender-Abo“ unter dem Programm (Startseite, `/programm/`, Landingpages), kleine
  Zeile auf Veranstaltungsseiten, Link im Fuß. Auf Android stellt `site.js` den Google-Knopf nach vorn.
- **Name (24.11., Danny):** Kalender heißt im Handy „Calavera Bremen“ (`site.name`), die Datei `calavera.ics`
  statt `kalender.ics` – manche Apps zeigen den Dateinamen als Namen. `kalender.ics` bleibt als unverlinkte
  Kopie, damit bestehende Abos der alten Adresse weiterlaufen.
- **Schalter:** `config.yml → kalender.abo: false` = keine Abo-Dateien (auch nicht je Landingpage), kein
  Kasten, keine Links (Fuß, Veranstaltungsseiten, `<link rel="alternate">`, `llms.txt`). Standard: an.
  `termin.ics` je Veranstaltung („In den Kalender“) gehört nicht zum Abo und bleibt.

## Folgen
- Wie oft Kalender-Apps nachladen, entscheiden sie selbst (Google ca. alle 12–24 h). Änderungen am Programm
  kommen also nicht sofort bei Abonnenten an.
- UIDs bleiben `<slug>@www.calavera.club`: Dateinamen von Veranstaltungen nach dem Veröffentlichen nicht mehr
  ändern, sonst steht der Termin bei Abonnenten doppelt (alter verschwindet erst nach 30 Tagen).
- Abschalten nach dem Start: Wer abonniert hat, behält die geladenen Termine, bekommt aber nichts Neues.
