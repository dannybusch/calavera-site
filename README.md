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

## Effekte

Für besondere Abende bekommt eine Veranstaltung Animationen auf ihrer Programm-Kachel und oben auf
ihrer Seite – eine, mehrere oder viele, Reihenfolge = Reihenfolge der Ebenen:

```yaml
effekte: [rauschnebel, gewitter, fratzen]   # auch "effekt: rauschnebel"
effekte: [snow, twinklestar]                # Weihnachten
```

| Effekt | Was passiert | passt z. B. zu |
|---|---|---|
| **Nebel** | | |
| `rauschnebel` | fasriger Nebel in drei Schichten: hinten dicht und langsam, vorn dünne Fetzen | Halloween, Calavera Dark |
| `buehnennebel` | Dunst wie aus der Nebelmaschine, zwei Scheinwerferkegel schwenken (Calavera-Rot, warmweiß) – immer im Raum hinter dem Flyer, nie auf ihm | jede Clubnacht |
| `flyerausnebel` | unterer Teil des Flyers verschwindet im Nebel, Fetzen ziehen davor durch (verschleiert Infos ganz unten etwas) | Dark RIOT |
| **Halloween** | | |
| `gewitter` | alle 7 s ein Doppelblitz, Flyer und Titel leuchten auf (weit unter der Epilepsie-Grenze von 3 Blitzen/s) | Halloween |
| `fratzen` | Calavera-Schädel mit roten Augen, Kürbisgrinsen und Geister tauchen auf und verschwinden | Halloween |
| **Winter** | | |
| `snow` (auch `schnee`) | Schneeflocken rieseln, unterschiedlich groß, leicht schaukelnd | Advent |
| `twinklestar` (auch `sterne`) | weiße und goldene Sterne erscheinen, funkeln, verschwinden | Advent, Silvester |
| **90er** | | |
| `grunge` | Kopierer-Korn, Staub und Kratzer, Flyer leicht ausgeblichen | Take The Power Back |
| `vhs` | Videokassette: Zeilen, Störstreifen läuft durch, Bild ruckelt ab und zu | Take The Power Back, 80s |
| `flanell` | rotes Holzfäller-Karo zieht über den Hintergrund (Kachel + Seite) | Take The Power Back |
| **Gute Laune** | | |
| `konfetti` | buntes Konfetti fällt, dreht sich und flattert | Fick Dich Ins Knie, Melancholie, Neue Freunde |
| `regenbogenfolie` (auch `holo`) | Hologramm-Schimmer zieht schräg über den Flyer | Gute-Laune-Partys („Einhörner“) |
| `seifenblasen` | schillernde Blasen steigen auf und zerplatzen | Honeycafé, Sommer |
| `discokugel` (auch `disco`) | verwaschene blau-weiße Lichtflecken (Fünfecke) wie von der Calavera-Kugel wandern im Kreis, auf der Seite hängt die Kugel | Feiern für Fortgeschrittene, Flashdance |
| **Hip-Hop** | | |
| `bassboom` | Flyer pumpt im Takt (90 BPM) | They call it HIP HOP |
| `spraydose` (auch `graffiti`) | Sprühkante oben, bunte Farbnasen laufen herunter | They call it HIP HOP |
| **Dunkel / Elektronisch** | | |
| `glitch` | alle paar Sekunden springen Streifen des Flyers kurz zur Seite, mit Farbversatz | Dark RIOT, EBM |
| `laser` | rote und eine grüne Laserlinie fächern von oben (schön mit `buehnennebel`) | Dark RIOT |
| `scanlines` | der Flyer wird zum Monitor: Zeilen, ein heller Streifen läuft durch | Electro, Wave |
| **80er** | | |
| `retrogrid` (auch `synthwave`) | Neon-Gitterboden läuft auf den Horizont zu, gestreifte Sonne | 80s SEX BEAT, Flashdance |
| `neon` | Titel leuchtet wie eine Neonröhre und flackert ab und zu, Kachel mit Neonrahmen | 80er, Wave |
| `vinyl` | Schallplatte in der Flyer-Ecke dreht sich mit 33⅓ (verdeckt die Ecke unten rechts) | Wave To The 80s („Vinyl only“) |
| `schwerelos` | Flyer schwebt sanft, Sterne ziehen vorbei | Flashdance („völlig losgelöst“) |
| **Advent / Honeycafé** | | |
| `lichterkette` | Lichterkette an der Oberkante, Birnchen glimmen unregelmäßig | Honeycafé |
| `dampf` | weicher Dampf steigt auf wie von einer Tasse Glühwein | Honeycafé |
| `kerzenlicht` (auch `kerze`) | warmer Schein flackert ruhig von unten | Honeycafé, Konzerte |
| **Titel / Ort** | | |
| `gluehwuermchen` (auch `glühwürmchen`) | Leuchtpunkte schwirren umher, glimmen auf und verlöschen | Nachtschwärmer |
| `spotlight` | ein warmer Lichtkegel auf den Flyer, ganz ruhig | Konzerte |
| `cempasuchil` (auch `papelpicado`) | Papel-picado-Wimpel oben, Studentenblumen-Blätter fallen (Totenfest, 1./2. November) | Calavera selbst |
| `feuerwerk` | Buketts zerplatzen in Calavera-Rot, Gold und Weiß | Silvester, Jubiläen |
| `superdark` | Die Dunkelheit übernimmt: auf der Veranstaltungsseite verblassen nach dem Laden alle Farben, die Seite wird deutlich dunkler und kühl, ein silbriger Schimmer zieht darüber; Kachel: Flyer entsättigt mit Glanz | Darkwave, Gothic, Dark RIOT |

**Wo die Effekte laufen:** Im Programm (Startseite und `/programm/`) zeigen nur die **ersten zwei Kacheln**
ihre Effekte – einstellbar in `config.yml` unter `programm.effekte_kacheln`. Auf der eigenen Seite einer
Veranstaltung laufen sie immer.

**Wie sie gebaut sind:** reines CSS (`static/css/fx/<effekt>.css`, je 1–2 KB). Jede Seite lädt nur die
Dateien der Effekte, die auf ihr vorkommen – Seiten ohne Effekt laden gar nichts davon. Bilder für Nebel,
Scheinwerfer, Korn, Staub, Discopunkte und Dampf berechnet der Build einmal (`static/img/fx/`, braucht
Pillow); geladen werden sie nur, wenn ein Effekt sie benutzt. Animiert werden nur Position, Größe,
Drehung und Deckkraft. Effekte, die gerade nicht im Bild sind, und alle in einem Tab im Hintergrund
werden angehalten. Klicks gehen durch die Effekte hindurch.

**Bewegung reduzieren:** Wer das am Gerät eingestellt hat, sieht keine Bewegung – nur ruhige Teile
(Nebel, Scheinwerfer, Lichterkette, Sterne, Neon …), Teilchen wie Schnee oder Konfetti werden ausgeblendet.

Tippfehler im Effektnamen meldet der Build und lässt den Effekt weg.

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

**Auf jeder Seite:** Läuft gerade eine Sendung, erscheint ganz oben ein schmales rotes Band
„Live im Kellerfunk · Titel · DJs – Reinhören ↗“. Beginnt eine in weniger als 60 Minuten, steht dort
dezent grau „Gleich auf Sendung: …“ mit Countdown. Das Band lässt sich wegklicken (gilt für diese
Sendung, bis der Tab geschlossen wird).

**Abende mit `stream:`** brauchen keinen eigenen Effekt: In der Stream-Karte auf der Veranstaltungsseite
hängt ein kleines „On Air“-Leuchtschild, das aus ist und während des Abends rot aufleuchtet; das
Stream-Kennzeichen auf der Kachel glüht dann ebenfalls.

## Startseiten-Übernahme

Ab 6 Stunden vor Beginn übernimmt die Veranstaltung des Tages den großen Claim („Vielfalt. Musik.
Freude.“): Flyer mit Effekten, Datum, Titel und ein Countdown bis Einlass bzw. Beginn, während des
Abends „Jetzt geöffnet · bis 04:00 Uhr“. Im Programm darunter wird dann keine Kachel mehr extra groß
gezeigt. Danach steht wieder der Claim da – das entscheidet der Browser, ein neuer Build ist nicht nötig.

```yaml
site:
  startseite_uebernahme: false        # ausschalten (Standard: an)
  startseite_uebernahme_stunden: 6    # wie lange vorher (Standard: 6)
```

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

## Reels für Instagram (`reels.py`)

Ein eigenständiges Programm macht aus den Event-Dateien kurze Videos für Instagram-Reels und -Stories
(1080 × 1920, 30 Bilder/s, H.264 + AAC). Es ist **vom Website-Build getrennt**: liest nur `events/` und
`config.yml`, schreibt nur nach `reels/out/` und verändert nichts an der Website.

**Einmal einrichten** (zusätzlich zur Website):

```bash
pip install -r requirements-reels.txt
python -m playwright install chromium
# ffmpeg:  macOS: brew install ffmpeg · Windows: winget install ffmpeg · Linux: sudo apt install ffmpeg
```

**Benutzen:**

```bash
python reels.py --liste                     # was würde gerendert?
python reels.py                             # alle kommenden Veranstaltungen mit "reels:"
python reels.py melancholie                 # nur diese (Teil des Dateinamens)
python reels.py melancholie --schnell       # Vorschau, ca. 4× schneller (ohne Bewegungsunschärfe)
python reels.py melancholie --pruefen       # nur Musik prüfen: Tempo und Eins
python reels.py woche                       # Programm der nächsten 7 Tage (--ab 2026-11-02 --tage 7)
python reels.py kellerfunk                  # Kellerfunk-Sendeplan eines Monats (--monat 2026-11)
```

Weitere Schalter: `--vorlage flyerfahrt,teaser`, `--countdown 7,3,1,0`, `--klick` (Metronom statt Musik,
zum Prüfen des Takts), `--hilfslinien` (zeigt die Flächen, die Instagram mit Bedienelementen überdeckt).

Ergebnis in `reels/out/<veranstaltung>/`: je Reel ein `.mp4` und ein `.jpg` (Titelbild für Instagram,
die Schlusstafel), dazu `bildtext-instagram.txt` – derselbe Text wie auf `/intern/`.
Ein Reel braucht in voller Qualität einige Minuten (jedes Bild entsteht aus 4 Zwischenbildern).

**In der Event-Datei** (alles optional):

```yaml
reels: [flyerfahrt, freunde, countdown, teaser]
musik: "melancholie.mp3"                     # in events/ oder reels/musik/ (ohne Angabe: events/<dateiname>.mp3)
bpm: 124                                     # Tempo des Titels
eins: "0:42.310"                             # Zeitpunkt einer "1" (Taktanfang) – dort beginnt das Reel
reel_fokus: [[50, 20], [40, 70], [60, 45]]   # Flyer-Fahrt: 3 Kamerapunkte (x/y in % des Flyers)
```

| Vorlage | Was passiert | Länge |
|---|---|---|
| `flyerfahrt` | harter Einstieg in eine Nahaufnahme des Flyers, Reißschwenks zu zwei weiteren Stellen (`reel_fokus`), Aufziehen mit Kippen im Raum, Schlusstafel | 6 Takte |
| `freunde` | Datum riesig · „Was euch erwartet“ · ein Name aus `fans_of` pro Schlag (bis 12) · Flyer · Schlusstafel; Ende führt nahtlos zurück zum Anfang | 6–8 Takte |
| `countdown` | „Noch 3 Tage“ / „Morgen“ / „Heute“, Flyer, Schlusstafel – für Stories über die Woche (`--countdown`) | 4 Takte |
| `teaser` | der Teaser-Satz in Häppchen, Wort für Wort auf dem halben Schlag, längstes Wort rot; Flyer wird scharf | je nach Text |
| `woche` | „Diese Woche im Calavera“ · ein Takt pro Veranstaltung · „calavera.club/programm“ | je nach Programm |
| `kellerfunk` | Sender-Look: Rauschen, Logo glimmt auf, Monat + Anzahl · je Sendung ein Kanalwechsel mit Datum, Visual im Monitor, Titel, DJs · Sendeplan zum Anhalten · „Einschalten: live.calavera.club“ | 5 + Anzahl Takte |

**Kellerfunk-Reel:** Die Sendungen kommen aus derselben `config.yml` wie live.calavera.club und das
OBS-Overlay (`shows:` mit `title`, `start`, `djs`, `visual`, optional `club: true/false` für „Live im Club & im
Stream“ / „Nur im Stream“ und `genres: [...]`) – nichts doppelt eintragen. Ohne `--monat`
nimmt es bis zum 14. den laufenden Monat, danach den nächsten. Sendungen ohne Visual zeigen im Monitor das
Kellerfunk-Logo auf Streifen; Platzhalter wie `[DJ]` werden weggelassen. Ergebnis: `reels/out/kellerfunk-JJJJ-MM.mp4`,
`.jpg` (Titelbild: Monat + Anzahl) und `kellerfunk-JJJJ-MM-bildtext.txt` mit allen Terminen.
Ohne Internet oder zum Ausprobieren: `--plan pfad/zur/config.yml` (Visuals und `kellerfunk.png` werden dann
relativ zu dieser Datei gesucht).

Die Stimmung passt sich den Effekten der Website an: Nebel bei `rauschnebel` & Co., Blitze bei `gewitter`,
Konfetti bei `konfetti`, Schnee bei `snow`, Sterne bei `twinklestar` – sonst Funken.

**Musik und Takt:** Die MP3 lädst du selbst (z. B. Pixabay) und legst sie neben die Event-Datei oder in
`reels/musik/`. Alles im Reel ist in Schlägen geplant: Schnitte, Namen, Blitze und das Pumpen sitzen auf
dem Schlag, und zusätzlich reagiert das Pumpen auf die Bässe der Musik. Dafür braucht es:

- `bpm` – das Tempo (zeigt z. B. Mixxx, eine freie DJ-Software, beim Laden an)
- `eins` – den Zeitpunkt einer „1“, am besten am Anfang einer Phrase (Refrain, Drop). In Audacity oder
  Mixxx in die Wellenform zoomen und den Anfang eines kräftigen Schlags ablesen.

`reels.py` prüft beides: Es warnt, wenn das erkannte Tempo deutlich abweicht, und rastet `eins` auf den
Anfang des nächsten Bassschlags ein, wenn sie bis zu 70 ms daneben liegt. Die Musik wird auf das Reel
zugeschnitten, im letzten Takt ausgeblendet und auf Instagram-Lautheit (−14 LUFS) gebracht. Titel mit
festem Tempo nehmen (elektronisch produziert); in der Instagram-App keine andere Musik darüberlegen.

**Optional in `config.yml`:**

```yaml
reels:
  bpm: 124                       # Standard-Tempo, wenn in der Event-Datei keins steht
  woche_musik: "woche.mp3"       # Musik für "woche" (in reels/musik/), dazu woche_eins: "0:12.500"
  url_text: "calavera.club/programm"
  kellerfunk_musik: "kellerfunk.mp3"   # Musik für "kellerfunk", dazu kellerfunk_bpm: 120 und kellerfunk_eins: "0:08.000"
  kellerfunk_claim: "Live aus dem Calavera-Keller"
  kellerfunk_unterzeile: "Im Stream · aus dem Keller"
  kellerfunk_hinweis: "Link in Bio"
```

Für `woche` und `kellerfunk` geht die Musik auch direkt: `--musik datei.mp3 --bpm 120 --eins 0:08.000`.

**Auf GitHub:** Actions → „Reels rendern“ → „Run workflow“ (Auswahl, Vorlage, Schnell). Die Videos liegen
danach unter „Artifacts“ zum Herunterladen. Dafür muss die Musik im Repository liegen. Änderungen an Reels
und Musik lösen keine Veröffentlichung der Website aus.

**Tipps:** Flyer ab etwa 2000 px Breite machen die Nahaufnahmen scharf (aktuell ~800 px → leicht weich).
Die Vorlagen liegen in `reels/vorlagen/` (HTML/CSS, eine Datei pro Vorlage) und lassen sich wie die
Website-Vorlagen anpassen.

## Lizenzen

Schriften Bebas Neue, Space Grotesk, IBM Plex Mono: SIL Open Font License (siehe `static/fonts/`).
js-yaml: MIT (siehe `static/js/`).
