# www.calavera.club – Website des Calavera Bremen

Statische Website, erzeugt von einem Python-Script. Kein Server-Code, keine Datenbank, keine Cookies:
Am Ende liegt in `dist/` ein Ordner mit fertigen HTML-Dateien, der auf jeden Webspace passt.

## Einmal einrichten

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Bauen und ansehen

```bash
python build.py                          # baut nach dist/
python build.py --serve                  # baut und zeigt die Seite auf http://localhost:8000
python build.py --now "2026-11-08 12:00" # tut so, als wäre es diese Zeit (zum Testen)
python build.py --strict                 # Abbruch mit Fehlercode, wenn eine Event-Datei kaputt ist
```

Im Browser kann man die Uhrzeit ebenfalls simulieren: `/?now=2026-10-23T23:00`.

## Ordner

| Ordner/Datei | Inhalt |
|---|---|
| `config.yml` | Name, Adresse, Öffnungszeiten, Menü, Standardwerte, Spalten im Programm, Kellerfunk |
| `events/` | **eine `.md` pro Veranstaltung**, Visual daneben mit gleichem Namen |
| `pages/` | feste Seiten: Safe Space, Über den Club, Calavera mieten, Kontakt, Datenschutz |
| `templates/` | HTML-Vorlagen (Jinja2) |
| `static/` | CSS, Script, Schriften, Logo – alles lokal, nichts von Google |
| `dist/` | Ergebnis, wird bei jedem Build komplett neu geschrieben |

## Eine Veranstaltung anlegen

1. `events/_vorlage.md` kopieren, umbenennen: `JJJJ-MM-TT-name.md`, z. B. `2026-12-04-indie-army-now.md`.
   Der Dateiname wird zur Adresse: `www.calavera.club/programm/2026-12-04-indie-army-now/`.
2. Kopf ausfüllen – mindestens `title` und `start`:

   ```yaml
   ---
   title: "Indie Army Now"
   start: "2026-12-04 22:00"
   djs: ["DJ Alexis On Fire"]
   genres: ["Indie", "Alternative"]
   tags: ["Ab 18"]
   ---
   Hier der Text in Markdown …
   ```

3. Den Flyer **mit gleichem Namen** daneben legen: `2026-12-04-indie-army-now.jpg` (oder `.png`/`.webp`).
   Alternativ im Kopf `visual: "irgendein-name.jpg"`. Ohne Visual erscheint eine dunkle Fläche mit blassem Wappen.
4. `python build.py` – fertig.

Alle Felder mit Erklärung stehen in `events/_vorlage.md`. Das Format lehnt sich an die `shows:` von
live.calavera.club an (`title`, `start`/`end` als `"JJJJ-MM-TT HH:MM"` in Bremer Zeit, `djs`, `visual`).

**Vergangenheit erkennt der Generator selbst:** Eine Veranstaltung ist vorbei, wenn ihr Ende erreicht ist
(ohne `end:` 6 Stunden nach Beginn, einstellbar in `config.yml`). Sie verschwindet dann aus dem Programm
und steht unter `/programm/archiv/`; ihre Seite bleibt erreichbar und zeigt „Diese Veranstaltung ist vorbei“.
Alte Dateien muss also niemand löschen. Das Script im Browser blendet zusätzlich alles aus, was seit dem
letzten Build vorbei ist, und hebt den nächsten Termin hervor („Heute“, „Morgen“, „Läuft gerade“).

## Was der Build erzeugt

- Startseite mit Claim, Kellerfunk-Karte, Infos und den nächsten Terminen (Anzahl: `programm.startseite_max`)
- `/programm/` mit allen kommenden, `/programm/archiv/` mit vergangenen Terminen
- eine Seite pro Veranstaltung mit Flyer, Fakten, Text, Kalender-Datei, Teilen, Anfahrt, „Danach“ am selben Abend
- Visuals verkleinert (`640.webp` für Kacheln, `1200.jpg` für Detailseite und Vorschau beim Teilen)
- `kalender.ics` (das ganze Programm zum Abonnieren), `sitemap.xml`, `robots.txt`, `404.html`
- Vorschaubilder für WhatsApp/Instagram/Signal (Open Graph) und Event-Daten für Google (schema.org)
- Weiterleitungen von alten Adressen (`/privatveranstaltungen/` → `/calavera-mieten/`)

## Highlight und Stream

```yaml
highlight: "Live-Konzert"   # Kachel abheben: rotes Etikett, roter Schimmer (gleiche Größe wie alle)
stream: true                # Abend läuft auch im Kellerfunk-Stream ("Vor Ort & im Stream")
```

`stream` geht auch mit eigenem Link und Text: `stream: { url: "https://…", label: "Auch im Stream" }`.
Auf der Veranstaltungsseite erscheint dann eine Stream-Karte, die während der Veranstaltung von
selbst auf „Jetzt live“ mit rotem „Jetzt reinhören“ umschaltet und danach verschwindet.

## Effekte (Nebel, Gewitter, Fratzen)

Für besondere Abende – Halloween, Calavera Dark – bekommt eine Veranstaltung Animationen auf ihrer
Programm-Kachel und oben auf ihrer Seite:

```yaml
effekte: [nebel, gewitter, fratzen]   # eine, mehrere oder alle; auch "effekt: nebel"
```

- **nebel** – Bodennebel zieht in zwei Schichten über Flyer, Kachel und Seite; der Vollmond-Bereich des Flyers glimmt
- **gewitter** – alle 7 Sekunden ein Doppelblitz: Flyer und Titel leuchten auf, Blitze zucken. Mehrere
  Gewitter-Kacheln blitzen versetzt. Zwei Blitze in 7 Sekunden liegen weit unter der Grenze, die für
  Menschen mit Epilepsie gefährlich werden kann (3 pro Sekunde).
- **fratzen** – Calavera-Schädel mit roten Augen, Kürbisgrinsen und Geister tauchen auf und verschwinden

Alles reines CSS, ohne JavaScript; Klicks gehen durch die Effekte hindurch. Wer am Gerät „Bewegung
reduzieren“ eingestellt hat, sieht nur einen stehenden Nebel. Tippfehler im Effektnamen meldet der Build.

## Reihen

Zusammengehörige Veranstaltungen (z. B. „Calavera Dark“) stehen als Reihe in `config.yml`:

```yaml
reihen:
  - tag: dark
    title: "Calavera Dark"
    more: "Weitere Dunkelveranstaltungen"
```

In der Event-Datei: `reihe: dark`. Das wirkt auf „Weitere Termine“ einer Veranstaltungsseite:
Zuerst stehen bis zu zwei kommende Termine aus derselben Reihe (Überschrift = `more`), danach
„Außerdem im Programm“ mit dem übrigen Programm, ohne Doppelte. Ohne Reihe oder ohne weitere
Termine der Reihe sieht der Bereich aus wie bisher. Anzahl einstellbar unter `programm.weitere_termine`
und `programm.aus_der_reihe`. Ein Tippfehler bei `reihe:` wird beim Build gemeldet.

## 3 oder 4 Kacheln pro Reihe

`config.yml` → `programm.spalten: 3` oder `4`. Auf dem Tablet werden es automatisch 2,
auf dem Handy eine Liste.

## Kellerfunk

Die Startseite liest im Browser die `config.yml` von live.calavera.club – dieselbe Datei wie die
Kellerfunk-Seite und das OBS-Overlay – und schaltet automatisch auf „Jetzt live“ mit Ringen, Visual
der laufenden Sendung und rotem Knopf. Sonst zeigt sie die nächste Sendung. Es gilt dieselbe Logik wie
auf live.calavera.club: `site.live: auto | an | aus`, Sendungen ohne `end` laufen 6 Stunden.

Weil die Datei von einer anderen Adresse kommt, muss **live.calavera.club** sie für www.calavera.club
freigeben (CORS). Apache (`.htaccess` neben der `config.yml`):

```apache
<Files "config.yml">
  Header set Access-Control-Allow-Origin "https://www.calavera.club"
  Header set Cache-Control "no-cache"
</Files>
```

nginx:

```nginx
location = /config.yml {
  add_header Access-Control-Allow-Origin "https://www.calavera.club";
  add_header Cache-Control "no-cache";
}
```

Auch die Visuals der Sendungen werden von dort geladen (als normale Bilder, dafür braucht es kein CORS).
Ist live.calavera.club nicht erreichbar, bleibt einfach die statische Kellerfunk-Karte stehen.

## Hochladen

`dist/` ist die komplette Website. Zum Beispiel:

```bash
python build.py --strict && rsync -av --delete dist/ user@server:/var/www/www.calavera.club/
```

Damit „vorbei“ auch ohne neue Inhalte stimmt, den Build am besten einmal täglich laufen lassen
(z. B. per Cronjob um 5 Uhr morgens, nach Clubschluss):

```cron
0 5 * * *  cd /pfad/zu/calavera-site && .venv/bin/python build.py --strict && rsync -a --delete dist/ /var/www/www.calavera.club/
```

Der Server sollte für fehlende Seiten `404.html` ausliefern (Apache: `ErrorDocument 404 /404.html`).

### `.htaccess` für www.calavera.club

Liegt direkt im Ordner von www.calavera.club auf dem Server und wird vom automatischen Upload nicht
angefasst – also einmal von Hand anlegen bzw. ergänzen. **Als UTF-8 ohne BOM speichern und die
Zeilen selbst tippen** (aus Chats kopierte Anführungszeichen/Leerzeichen führen zu Fehler 500).

```apache
# Seiten und Kalender nicht ungeprüft aus dem Zwischenspeicher nehmen
<IfModule mod_headers.c>
  <FilesMatch "\.(html|ics)$">
    Header set Cache-Control "no-cache"
  </FilesMatch>
</IfModule>

# Kalenderdateien richtig ausliefern
AddType text/calendar .ics
AddCharset utf-8 .ics

# Eigene Fehlerseite
ErrorDocument 404 /404.html
```

`no-cache` heißt: Der Browser darf eine Kopie behalten, muss aber vor jeder Verwendung beim Server
nachfragen, ob sie noch aktuell ist. Bilder, Schriften, CSS und JS bekommen ohnehin einen
Fingerabdruck (`?v=…`) in der Adresse und dürfen lange zwischengespeichert werden.

Zusätzlich bekommen alle Links auf `kalender.ics` und `termin.ics` einen Fingerabdruck des Inhalts
(`/kalender.ics?v=…`). Er ändert sich nur, wenn sich ein Termin ändert – nicht bei jedem Build.

## Automatisch veröffentlichen (GitHub Actions → STRATO per SFTP)

`.github/workflows/deploy.yml` baut die Website und lädt `dist/` per SFTP hoch. Variablen und Secrets liegen im GitHub-Environment `calavera-site.env` (Settings → Environments); der Name steht im Workflow unter `environment:`.

Der Workflow läuft:

- bei jedem **Push auf `main`**,
- **täglich** um 04:17 UTC (05:17 Uhr Winterzeit / 06:17 Uhr Sommerzeit), damit Vergangenes ins Archiv wandert,
- **von Hand** unter Actions → „Bauen und veröffentlichen“ → „Run workflow“ – dort standardmäßig als
  **Probelauf**, der nur anzeigt, was hochgeladen und gelöscht würde.

Ist eine Event-Datei fehlerhaft, bricht der Build ab (`--strict`) und es wird **nichts** veröffentlicht.

**Einrichten** (einmalig, im GitHub-Environment `calavera-site.env` unter Settings → Environments):

| Art | Name | Wert |
|---|---|---|
| Variable | `SFTP_HOST` | SFTP-Server aus dem STRATO-Kundenlogin (Ihr Paket → Datenbanken und Webspace → SFTP & SSH) |
| Variable | `SFTP_USER` | SFTP-Benutzername von dort |
| Variable | `SFTP_REMOTE_DIR` | Ordner von www.calavera.club auf dem Webspace, z. B. `www.calavera.club` – oder `/` bei einem eigenen Zugang (nächste Zeile) |
| Variable | `SFTP_USER_IS_WEBROOT` | `true`, wenn der SFTP-Zugang bei STRATO **nur** den Ordner von www.calavera.club sieht – dann ist `/` als Zielordner erlaubt |
| Variable | `SFTP_PORT` | optional, Standard 22 |
| Secret | `SFTP_PASSWORD` | SFTP-Passwort |
| Secret | `SFTP_KNOWN_HOSTS` | optional, empfohlen: Ausgabe von `ssh-keyscan <SFTP_HOST>` (einmal lokal ausführen) |

Am besten legt man bei STRATO für GitHub einen **eigenen SFTP-Zugang** an, der nur auf den Ordner von
www.calavera.club zugreifen darf. Dann kann ein falscher Ordnername nichts anderes treffen.

**Wichtig – `SFTP_REMOTE_DIR`:** Der Upload spiegelt `dist/` in diesen Ordner und **löscht dort alles,
was es in `dist/` nicht gibt**. Er muss also genau der Ordner sein, auf den www.calavera.club zeigt –
niemals das Wurzelverzeichnis des Webspace, in dem auch live.calavera.club liegt (das verhindert der
Workflow zusätzlich). Unangetastet bleiben im Zielordner: `.htaccess`, `.well-known/` und alles in einem
Ordner `_behalten/` (für Dateien, die nicht aus dem Generator kommen).

**Erster Start:** Workflow von Hand mit Häkchen „Probelauf“ starten und im Protokoll prüfen, dass
Ordner und Dateien stimmen. Danach von Hand ohne Häkchen starten oder einfach pushen.

Hinweise: GitHub startet geplante Läufe manchmal mit Verzögerung. In **öffentlichen** Repositories
schaltet GitHub den täglichen Lauf nach 60 Tagen ohne Aktivität ab (Actions → Workflow → „Enable workflow“);
in privaten Repositories nicht.

## Interne Seiten für Facebook, Instagram & Co. (`/intern/`)

Für jede kommende Veranstaltung baut der Build unter **www.calavera.club/intern/** eine Seite mit
fertigen Texten und Bildern – jeweils mit „Kopieren“-Knopf:

- **Eckdaten**: Name, Ort, Beginn/Ende (Datum und Uhrzeit getrennt, wie Facebook sie abfragt), Link
- **Facebook-Veranstaltung**: Beschreibung (Text der .md + Abbinder) und Titelbild 1920 × 1005
- **Instagram**: Beitragstext (Teaser + Abbinder + „Link in Bio“ + Hashtags, mit Zeichenzähler bis 2200)
  sowie Bilder für Beitrag (1080 × 1350) und Story (1080 × 1920)
- **Veranstaltungskalender**: Kurztext, Langtext mit Link, nur der Abbinder

Die Bilder entstehen automatisch aus dem Flyer (unscharfer, abgedunkelter Hintergrund, Flyer mittig).

**Der Abbinder** steht am Ende jedes Textes und wird aus der Event-Datei zusammengesetzt:

```
Was euch musikalisch (u. a.) erwarten könnte: …   ← aus fans_of:
--
»F*** Dich Ins Knie, Melancholie«                ← social_title: (sonst title:)
mit DJ Alexis On Fire / @dj_alexis_on_fire        ← djs: + Instagram-Namen aus config.yml → kuenstler
7. November 2026 ab 22:00h                        ← start: (mit einlass: „Einlass … Beginn …“)
Eintritt: EUR 5,- / frei für Azubis+Studis        ← eintritt: oder config.yml → abbinder.eintritt
- rauchfreie Veranstaltung -                      ← tags: + config.yml → abbinder.zeilen_fuer_tags
```

Einstellungen dazu in `config.yml` unter `abbinder:` (Einleitungssatz, Eintritt, Zeilen je Tag, Hashtags)
und `kuenstler:` (Instagram-Namen ohne @, Name genau wie bei `djs:`).

Neue Felder in der Event-Datei:

```yaml
social_title: "F*** Dich Ins Knie, Melancholie"      # anderer Titel für Social Media
facebook: "https://www.facebook.com/events/…"       # sobald das Facebook-Event angelegt ist
```

Mit `facebook:` zeigt die Übersicht „✓ Facebook“, und die öffentliche Veranstaltungsseite bekommt einen
Link „Facebook-Event“.

Die Seiten sind nirgends verlinkt, haben `noindex` und stehen in `robots.txt` unter `Disallow`.
**Geheim sind sie nicht** – wer die Adresse kennt, kann sie öffnen. Es steht aber nichts darauf, was
nicht ohnehin öffentlich wird. Wer sie trotzdem schützen will, richtet im STRATO-Kundenbereich einen
Verzeichnisschutz für `/intern/` ein. Die `.htaccess`, die dabei entsteht, lässt der Deploy stehen;
liegt die `.htpasswd` ebenfalls in `/intern/`, in `deploy.yml` ein `--exclude-glob .htpasswd` ergänzen.

Tipp: Sternchen im Fließtext (z. B. `F***`) mit Backslash schreiben: `F\*\*\*` – sonst macht Markdown
daraus Kursiv/Fett.

## No-Cookie-Banner

Erscheint nur, wenn jemand von außen auf die Seite kommt, und verschwindet nach `sekunden` von selbst.
Text und An/Aus in `config.yml` unter `no_cookie_banner`. Gespeichert wird dafür nichts.

Zum Testen `#nocookie` an eine beliebige Adresse hängen, z. B. `http://localhost:8000/#nocookie`
oder `/programm/#nocookie`. Das geht auch auf einer schon offenen Seite: `#nocookie` in die
Adresszeile tippen und Enter – das Banner erscheint sofort und kann so beliebig oft ausgelöst werden.

## Feste Seiten

Liegen in `pages/` als Markdown und werden in Kopf und Fuß der Website eingebettet – Menü und Fuß
ändert man so an einer Stelle. Kartenraster (wie bei den Clubregeln) gehen so:

```markdown
<div class="cards" markdown="1">
<div class="card" markdown="1">
### Überschrift
Text
</div>
</div>
```

Stellen in `<span class="placeholder">[…]</span>` sind rot hinterlegt und müssen noch ausgefüllt werden.

## Lizenzen

Schriften Bebas Neue, Space Grotesk, IBM Plex Mono: SIL Open Font License (siehe `static/fonts/`).
js-yaml: MIT (siehe `static/js/`).
