# www.calavera.club – Website des Calavera Bremen

Statische Website, erzeugt von einem Python-Script. Kein Server-Code, keine Datenbank, keine Cookies:
Am Ende liegt in `dist/` ein Ordner mit fertigen HTML-Dateien, der auf jeden Webspace passt.

Hintergründe zu Entscheidungen stehen in `docs/entscheidungen/`, offene Punkte in `docs/offen.md`,
eine Kurzfassung für Claude in `CLAUDE.md`.

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
python build.py --ohne-cache             # alle Bilder neu berechnen (Bild-Cache weder lesen noch schreiben)
```

Im Browser kann man die Uhrzeit ebenfalls simulieren: `/?now=2026-10-23T23:00`.

**Bild-Cache:** Flyer-Fassungen (640/1200/breit), Bilder für Facebook/Instagram, Seitenbilder und die
Effekt-Texturen landen zusätzlich in `.cache/bilder/` (nicht im Git). Der Schlüssel ist eine Prüfsumme aus
Quellbild, Einstellungen, dem Code der erzeugenden Funktion und der Pillow-Version – nur neue oder geänderte
Bilder werden neu berechnet, der Rest wird kopiert (Build ≈ 1 s statt ≈ 20 s, wächst nicht mehr mit dem
Archiv). Nicht mehr benötigte Einträge räumt der Build selbst weg. Den Cache kann man jederzeit löschen;
anderer Ort per Umgebungsvariable `CALAVERA_BILD_CACHE`. Im Deploy-Workflow hält `actions/cache` ihn
zwischen den Läufen fest.

## Ordner

| Ordner/Datei | Inhalt |
|---|---|
| `config.yml` | Name, Adresse, Öffnungszeiten, Menü, Standardwerte, Spalten im Programm, Kellerfunk |
| `events/` | **eine `.md` pro Veranstaltung**, Visual daneben mit gleichem Namen |
| `pages/` | feste Seiten: Safe Space, Über den Club, Calavera mieten, Kontakt, Datenschutz |
| `landing/` | Landingpages wie `/dark/` und `/party/`: eigener Text + SEO-Angaben, Termine kommen automatisch |
| `advent/` | Adventskalender (`adventskalender2026.yml` → `/adventskalender/`) – wird nie ausgeliefert |
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
  – Seitentitel der Startseite: `site.name` · `site.titel_zusatz` (z. B. „Calavera Bremen · Kellerclub im Viertel“; `titel_zusatz: ""` = nur der Name)
- `/programm/` mit allen kommenden, `/programm/archiv/` mit vergangenen Terminen
- eine Seite pro Veranstaltung mit Flyer, Fakten, Text, Kalender-Datei, Teilen, Anfahrt, „Danach“ am selben Abend
- Visuals verkleinert (`640.webp` für Kacheln, `1200.jpg` für Detailseite und Vorschau beim Teilen)
- `kalender.ics` (das ganze Programm, Knopf „Programm in den Kalender“); mit eingeschaltetem Abo zusätzlich
  `calavera.ics` und je Landingpage `/<slug>/calavera-<slug>.ics` – siehe „Kalender-Abo“
- `sitemap.xml`, `robots.txt`, `404.html`
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
| `disco1` | Discokugel, ursprüngliche Fassung: frei verteilte, verwaschene blau-weiße Fünfecke wandern im Kreis über Flyer, Kachel und Seite; auf der Seite hängt die Kugel | Feiern für Fortgeschrittene, Flashdance |
| `disco2` (auch `disco`, `discokugel`) | Discokugel als Projektion: Lichtpunkte in Ringen um die Kugel, außen größer und weiter auseinander, drehen sich langsam; auf der Seite nur im Raum (nicht auf dem Flyer), gedämpft | wie oben |
| `disco3` | wie `disco2`, aber lebendiger: die Lichtpunkte werden in verschiedenen Takten sanft heller und dunkler | wie oben |
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
| `funemotes` | Fröhliche Emojis (😄 🥳 😍 🎉 🕺 …) steigen auf wie Reaktionen in einem Live-Stream, ploppen kurz auf und wackeln; über dem Flyer am rechten Rand | Gute-Laune-Partys, Mottopartys, Geburtstage |
| `heartbubble` | Nur auf dem Flyer: Herzen in Rot- und Rosatönen steigen aus der Ecke rechts unten auf und driften leicht schräg über den Flyer, wie Herzchen in einem Live-Stream | Valentinstag, Hochzeiten, Kuschelpartys, Lieblingsabende |
| `lichtorgel` | Rot, Gelb, Grün pulsieren versetzt wie die Lichtorgel im Jugendkeller; auf der Seite mit kleiner Lampenleiste oben | 70er/80er, Partyklassiker |
| `lichtorgel2` (auch `multilichtorgel`) | Multi-Lichtorgel wie im Calavera: 9 farbige Kreise in Calavera-Farben blitzen als Gruppe auf, huschen ein Stück über die Wand, verlöschen und tauchen woanders wieder auf | jede Party |
| `lichtorgel5` | wie `lichtorgel2`, aber die 9 Kreise stehen im 3×3-Raster – so wie die Lichtorgel im Calavera | jede Party |
| `lichtorgel3` | Multi-Lichtorgel als Lauflicht: die 9 Kreise ziehen einzeln Bahnen und blitzen nacheinander auf | Dance, Pop |
| `lichtorgel4` (auch `farbrad`) | Farbrad: Farbfelder drehen sich vor dem Scheinwerfer, das Licht fächert weich von oben über die Wand und pulsiert im Takt | 70er, Soul, Funk |
| `tanzflaeche` (auch `dancefloor`) | Leuchtende Bodenfliesen in Perspektive glimmen in bunten Wellen auf – unten in der Kachel, auf der Seite leise unter dem Flyer | Dance, Disco, 2000er |
| `tanzflaeche2` | Tanzfläche mit Lichtringen, die von vorn in der Mitte nach außen laufen (Rot, Bernstein, Rosé, Creme) | Dance, Feiern für Fortgeschrittene |
| `tanzflaeche3` | Tanzfläche als Schachbrett im Takt (Rot/Bernstein), dazu ein Lauflicht-Streifen | Disco, 80er |
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

## Landingpages (`/dark/`, `/party/`, …)

Je Datei in `landing/` entsteht eine Seite unter `www.calavera.club/<dateiname>/`. Den Text und die
Angaben für Suchmaschinen schreibt man selbst in die `.md`; die passenden Veranstaltungen kommen
automatisch aus `events/` dazu: kommende als Kacheln (wie im Programm), vergangene als Liste „Zuletzt im
Calavera“ (damit die Seite auch in Programmpausen etwas zeigt). Alle Möglichkeiten stehen in
`landing/_vorlage.md`.

| Feld im Kopf | Wofür |
|---|---|
| `title` | große Überschrift |
| `seo_title` | Titel im Browser-Tab und bei Google (sonst `title`) |
| `description` | Beschreibung für Google (ca. 155 Zeichen) |
| `kicker`, `lead`, `link_text` | Zeile über der Überschrift, Satz darunter, Linktext auf anderen Seiten |
| `rueckverlink: false` | keine sichtbaren Links hierher – weder Programm noch Landingpages noch Veranstaltungsseiten; nur Sitemap/`llms.txt` (Sammelseite wie `/party/`) |
| `zeigt:` | welche Termine: `reihen: [dark]`, `genres: [...]`, `ohne_reihen: [dark]`, `nur_partys: true` (ohne alles mit `art:`) |
| `faq:` | Häufige Fragen (`frage:`/`antwort:`) – sichtbar auf der Seite und als FAQ für Google/KI |
| `archiv`, `leer`, `bild`, `noindex`, `draft` | Anzahl vergangener Termine, Text bei leerem Programm, Vorschaubild, Suchmaschinen aus, Entwurf |
| `kalender_name` | Name des eigenen Kalender-Abos im Handy (sonst „Calavera “ + `title`, z. B. „Calavera Partys“) |

**Einzelne Veranstaltung zusätzlich auf einer Landingpage**, ohne sie zur Reihe zu machen (z. B. die
Depeche-Mode-Party auf `/dark/`, ohne dass sie als „Weitere Dunkelveranstaltung“ auftaucht): in der Event-Datei

```yaml
auch_auf: [dark]          # Dateinamen der Landingpages ohne .md, mehrere möglich: [dark, wave]
```

Die Veranstaltung erscheint dann auf `/dark/` ganz normal nach Datum zwischen den anderen Kacheln (und im
JSON-LD der Seite) und weiterhin überall, wo sie ohnehin hingehört (z. B. `/party/`). Sie zählt aber **nicht**
zur Reihe: kein „Weitere Dunkelveranstaltungen“, und auf ihrer eigenen Seite verlinkt sie nicht auf `/dark/`.
Ein Tippfehler (Landingpage gibt es nicht) wird beim Build gemeldet.

Der Text unter dem Kopf ist Markdown. Alles über der Zeile `<!-- mehr -->` steht über den Kacheln,
alles darunter unter den Kacheln (Platz für ausführlicheren Text mit `##`-Zwischenüberschriften).

Derzeit: `/dark/` zeigt alle Termine mit `reihe: dark`, `/party/` alle übrigen Partys (ohne Dark und ohne
Konzerte/Lesungen). Für Suchmaschinen bekommt jede Landingpage `CollectionPage`-JSON-LD mit allen kommenden
Terminen, Brotkrumen und ggf. `FAQPage`; sie steht in `sitemap.xml` und `llms.txt`. Verlinkt wird sie aus dem
Programm (Knöpfe unten) und von jeder passenden Veranstaltungsseite („Alle Dark-Partys →“) – außer bei
`rueckverlink: false` (so bei `/party/`: keine sichtbaren Links, nur Sitemap und `llms.txt`). Ins Hauptmenü
kommt sie nur über `config.yml → navigation`.

## Kalender-Abo (`/calavera.ics`, `/dark/calavera-dark.ics`, …)

> **Derzeit ausgeschaltet** (24.11.2026, Danny: auf Android – Samsung S24 – kamen über keinen Weg Termine an).
> Ohne Einstellung baut die Seite wie vor dem Abo: `kalender.ics` mit den kommenden Terminen, Knopf
> „Programm in den Kalender“ auf Startseite und `/programm/`, „Programm als Kalender“ im Fuß.
> Einschalten mit `kalender: { abo: true }` in `config.yml`. Alles Folgende gilt für das eingeschaltete Abo.

Gäste können das Programm **abonnieren**: Dann stehen alle Termine im Handy-Kalender, und neue oder
geänderte kommen von selbst dazu. Der Build schreibt dafür

- `calavera.ics` – das ganze Programm, im Handy als Kalender „Calavera Bremen“,
- `/<landingpage>/calavera-<landingpage>.ics` – nur die Termine dieser Landingpage (derzeit
  `/dark/calavera-dark.ics` „Calavera Dark“ und `/party/calavera-party.ics` „Calavera Partys“;
  dieselbe Auswahl wie die Kacheln, inklusive `auch_auf:`).

Neben allen kommenden Terminen stehen darin auch die der **letzten 30 Tage**, damit ein Abend nicht am
Morgen danach aus dem abonnierten Kalender verschwindet. Die Dateien sagen den Kalender-Apps, dass sie
alle 6 Stunden neu laden sollen (`REFRESH-INTERVAL`/`X-PUBLISHED-TTL`). Wie oft sie es wirklich tun,
entscheidet die App: Apple und Outlook halten sich meist daran, **Google lädt nur etwa alle 12–24 Stunden**.

Sichtbar ist das Abo als Kasten „Kalender-Abo“ unter dem Programm (Startseite, `/programm/`) und auf jeder
Landingpage (dort mit deren eigenem Abo). Veranstaltungsseiten verlinken darauf („Kalender-Abo: Alle Termine
· Nur Calavera Dark“), der Fuß jeder Seite ebenso. Im Kasten:

| Knopf | Was passiert |
|---|---|
| **Abonnieren** | `webcal://www.calavera.club/calavera.ics` – iPhone, Mac und Outlook fragen direkt „Abonnieren?“ |
| **Google Kalender** | öffnet Google Kalender mit „Kalender hinzufügen“ (`cid=https://…`) – der Weg für Android (und alle mit Google-Konto) |

Einen Download-Knopf und eine Adresse zum Kopieren gibt es bewusst nicht (24.11., Danny): Einmal importierte
Termine bekommen keine Änderungen, das Abo kann alles besser. Wer eine andere App nutzt, nimmt die Adresse
aus dem Abonnieren-Link (`https://www.calavera.club/calavera.ics`).

**Android (Dannys Samsung S24, 24.11.):** Android kann von sich aus kein Kalender-Abo; `webcal://` öffnet
irgendeine App, die sich dafür angemeldet hat. Trotzdem zeigt der Kasten auf allen Geräten beide Knöpfe (Danny,
24.11.: manche haben auf Android eine Abo-App wie ICSx⁵). „Google Kalender“ klappt („Kalender hinzugefügt“), aber **Google synchronisiert per Adresse abonnierte Kalender nicht
von selbst aufs Handy**: In der Google-Kalender-App unter ☰ → Einstellungen → „Calavera Bremen“ →
**Synchronisieren** einschalten. Außerdem holt Google die Datei beim ersten Mal mit Verzögerung (Minuten bis
Stunden). Beides steht als Hinweis im Kasten.

Abo-Adressen haben **keinen** Fingerabdruck (`?v=…`), damit sie für immer gleich bleiben. Die Dateien heißen `calavera…` statt `kalender…`, weil manche Apps den Dateinamen als Kalendernamen
zeigen. Die alte Adresse `kalender.ics` schreibt der Build als gleiche Kopie weiter (nicht mehr verlinkt):
Wer sie schon abonniert hat – auch als `…/kalender.ics?v=…` –, bekommt weiter alles (der Server
ignoriert `?v=`). Die Datei je Veranstaltung (`termin.ics`, Knopf „In den Kalender“) ist davon unabhängig.

Einstellungen (alle optional, in `config.yml`):

```yaml
kalender:
  abo: true                    # Kalender-Abo einschalten (Standard: aus). Aus = wie vor dem Abo: nur kalender.ics
                               # mit kommenden Terminen und der Knopf „Programm in den Kalender“; kein Kasten,
                               # keine calavera*.ics. termin.ics je Veranstaltung gibt es immer.
  abo_vergangene_tage: 30      # so viele Tage bleiben vergangene Termine im Abo (0 = nur kommende)
  abo_name: "Calavera Bremen"  # Name des Kalenders im Handy (Standard: site.name)
```

Beim Abschalten: Wer `calavera.ics` abonniert hat, behält die bisher geladenen Termine, bekommt aber keine neuen
mehr; manche Apps melden beim Aktualisieren einen Fehler, bis das Abo gelöscht wird. Abos auf `kalender.ics`
laufen weiter (die Datei gibt es immer).

## Adventskalender (`/adventskalender/`)

24 Türen, hinter jeder ein Lieblingssong von jemandem aus dem Team oder von den DJs, mit ein paar Sätzen
dazu und Links zu YouTube Music, Bandcamp & Co. Gepflegt wird alles in **`advent/adventskalender2026.yml`**
(Format oben in der Datei erklärt). Danach `python build.py`.

**Was online steht – und was nicht:**

- Die YAML-Datei wird **nie** hochgeladen (nach `dist/` kommt nur `static/` und das fertige HTML).
- Ins HTML schreibt der Build nur Türen, deren Tag **schon erreicht** ist (Bremer Zeit, Build-Zeitpunkt).
  Künftige Türen bestehen nur aus Zahl und Datum. Im Quelltext, im Script, im JSON-LD und in `llms.txt`
  steht nichts über sie – auch nicht, ob sie schon ausgefüllt sind.
- Eine Tür erscheint erst, wenn `song`, `kuenstler` und `person` ausgefüllt sind. Ist ihr Tag erreicht und
  sie ist noch leer, steht „Folgt in Kürze“ auf der Tür (der Build meldet das, bricht aber nicht ab).
- `draft: true` oben in der Datei: Seite wird gar nicht gebaut (Start: auf `false` setzen).

**Neue Tür um Mitternacht:** Weil die Seite statisch ist, geht eine Tür mit dem ersten Build nach Mitternacht
auf. Dafür läuft der Deploy vom 30.11. bis 23.12. zusätzlich um 23:07 UTC = **00:07 Uhr** (Dezember =
Winterzeit). GitHub startet geplante Läufe manchmal verspätet; spätestens der normale Lauf um 05:17 Uhr
holt es nach. Seiten werden mit `Cache-Control: no-cache` ausgeliefert (`.htaccess`), Browser holen also
immer den neuen Stand.

**Testen:** `python build.py --now "2026-12-07 12:00" --serve` → `http://localhost:8000/adventskalender/`.
Einzelne Tür direkt öffnen (auch zum Teilen): `/adventskalender/#tuer-7`.

**Menü:** in `config.yml → navigation` (pflegt Danny):

```yaml
  - { label: "Adventskalender", href: "/adventskalender/" }
```

**Mit dabei:** Oben auf der Seite stehen alle Personen aus der Datei, auch die hinter noch geschlossenen
Türen – ohne Doppelte und in zufälliger Reihenfolge (beim Build gemischt und im Browser bei jedem Besuch neu),
damit nicht abzulesen ist, welche Tür zu wem gehört.

**Startseite:** Im Hero teilt sich eine Adventskalender-Karte den Platz mit dem Kellerfunk (Desktop: darüber,
Tablet: daneben, Handy: darüber). Vor dem 1.12. zeigt sie Titel und Einleitung mit der Marke „Ab 1. Dezember“,
vom 1. bis 24.12. eine rote Tür mit der Zahl von heute, die beim Laden nach außen aufgeht, und „Öffne das Türchen von
[Person]“ (Song und Künstler verrät die Karte nicht; ist die Tür noch leer: „Tür N folgt in Kürze“), danach „Alle 24 Türen offen“.
Zeitraum in der YAML (beides optional):

```yaml
startseite_ab: 2026-11-27     # Standard: 27.11.
startseite_bis: 2027-01-06    # Standard: 6.1. des Folgejahres
startseite: false             # Karte ganz abschalten
```

Ein Build bis zu 7 Tage vor `startseite_ab` legt die Karte schon versteckt ab, `site.js` blendet sie am
Stichtag ein (und nach `startseite_bis` aus) – dafür braucht es keinen eigenen Deploy. Testen mit
`?now=2026-11-28T12:00`. Dateien: `templates/partials/advent_karte.html`, `.adv-karte` in `static/css/site.css`.

Für Suchmaschinen: `CollectionPage`-JSON-LD mit den geöffneten Türen als `MusicRecording`, Eintrag in
`sitemap.xml` und `llms.txt` (nur Geöffnetes). Ohne JavaScript stehen die geöffneten Türen als Liste unter dem
Raster; mit JavaScript öffnen sie sich als Fenster (`static/js/adventskalender.js`, `static/css/adventskalender.css`,
Template `templates/adventskalender.html`). Für ein neues Jahr: Datei kopieren (`adventskalender2027.yml`),
die neueste Datei ohne `draft: true` gewinnt.

## 3 oder 4 Kacheln pro Reihe

`config.yml` → `programm.spalten: 3` oder `4`. Auf dem Tablet werden es automatisch 2,
auf dem Handy eine Liste.


### Wenige Termine

Stehen in einem Programm-Raster (Startseite, `/programm/`, Landingpages) nur wenige Termine, passt der große
Teaser über die volle Breite nicht. Auf großen Bildschirmen gilt deshalb:

- **1 Termin:** großer Teaser wie gewohnt.
- **2 Termine (Muster A):** kein großer Teaser – beide gleich groß als Querkarten nebeneinander;
  der nächste behält Etikett („Als Nächstes“) und rotes Datum.
- **3 bis 4 Termine (Muster B):** großer Teaser links, die übrigen als Leiste „Danach“ rechts daneben
  (bei 3 in der Leiste ohne Teasertext und Etiketten, damit sie nicht höher wird als der Teaser).
- **ab 5 Terminen:** normales Raster.

Die Obergrenze für Muster B lässt sich in `config.yml` einstellen (Standard 4):

```yaml
programm:
  leiste_bis: 4
```

Handy und Tablet bleiben unverändert. Der Build legt die Darstellung vor, `site.js` rechnet im Browser
nach, sobald Termine vorbei sind (testen mit `?now=`, z. B. `/programm/?now=2026-12-05T10:00`).

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
offene Seite – gespeichert wird dafür nichts).

**Abende mit `stream:`** brauchen keinen eigenen Effekt: In der Stream-Karte auf der Veranstaltungsseite
hängt ein kleines „On Air“-Leuchtschild, das aus ist und während des Abends rot aufleuchtet; das
Stream-Kennzeichen auf der Kachel glüht dann ebenfalls.

## Seiteneffekte

Seiteneffekte wirken global auf **jeder** Seite – unabhängig von den Veranstaltungen. Eingetragen werden sie in
`config.yml`, jeweils mit optionalem Zeitfenster (Bremer Zeit). Der Browser schaltet sie pünktlich ein und
wieder aus, ein neuer Build ist dafür nicht nötig; schon abgelaufene Einträge lässt der Build weg.

```yaml
seiteneffekte:
  - effekt: spinne
    start: "2026-10-31T18:00"     # optional
    end: "2026-11-01T04:00"       # optional
  - effekt: logo                  # ohne start/end: immer an
  - effekt: rip                   # Gedenken – Felder siehe unten
    person: "Name"
    daten: "1946 – 2026"          # optional
    text: "Danke für die Musik."  # optional
    link: "https://…"             # optional, z. B. ein Nachruf
    sterne: false                 # optional: ohne Sternenhimmel
    end: "2026-11-07T00:00"
```

| Seiteneffekt | Was passiert |
|---|---|
| `spinne` | Im rechten oberen Eck hängt ein Spinnennetz (halb hinter der Kopfleiste), eine Spinne baumelt am Faden. Zur Begrüßung und immer, wenn man wieder nach oben scrollt, seilt sie sich ab und klettert zurück; fährt man mit der Maus über sie, flüchtet sie nach oben. |
| `rip` (auch `gedenken`) | Gedenken, wenn eine für uns wichtige Musikerin oder ein Musiker gestorben ist: ein schmales, dunkles Band ganz oben – „R.I.P.“, Name, Lebensdaten, ein Satz und optional ein Link (z. B. zum Nachruf) –, dahinter ziehen ganz ruhig Sterne vorbei. Mehrere `rip`-Einträge gleichzeitig stehen nebeneinander im Band. Wegklickbar für die gerade offene Seite (es wird nichts gespeichert). |
| `logo` (auch `logolebt`) | Das Logo lebt: im offenen Auge des Totenkopfs sitzt eine Pupille, die der Maus (bzw. dem Finger) folgt; ab und zu zwinkert es, und wer eine Weile nichts tut, sieht den Kopf sich neigen und umschauen. |

Zum Testen `?now=2026-10-31T20:00` an eine Adresse hängen. Mit „Bewegung reduzieren“ hängt die Spinne still und
das Auge zwinkert nicht. Neue Seiteneffekte: Name in `SEITENEFFEKTE` (build.py), CSS in
`static/css/seiteneffekte/<name>.css`, Verhalten in `static/js/seiteneffekte.js`.

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

### Suchmaschinen und KIs

Der Build erzeugt dafür automatisch:

- **`sitemap.xml`** und **`robots.txt`** (interne Seiten gesperrt).
- **Strukturierte Daten** (schema.org): auf der Startseite der Club als `NightClub` – Adresse, Öffnungszeiten
  (aus `club.hours`, z. B. „Fr + Sa · 22–04“), Eintritt, E-Mail, Karte und die Profile aus `social:` –, auf jeder
  Veranstaltungsseite ein `MusicEvent` mit DJs, Stream und **Eintritt** (`offers`, aus `eintritt:` bzw.
  `events.default_entry`; „frei“/„Hutspende“ wird als kostenlos erkannt). Prüfen mit Googles „Test für Rich-Suchergebnisse“.
- **`llms.txt`** – eine klare Kurzfassung für KI-Suchdienste (ChatGPT, Perplexity, Gemini …): wer, wo, wann,
  Eintritt, Kontakt, Kellerfunk und die nächsten 16 Veranstaltungen mit Links; bei jedem Build aktuell.

#### Suchmaschinen über Änderungen informieren (IndexNow, Sitemap)

- **Bing, Yandex, Seznam, Naver, Yep** (und über Bing auch DuckDuckGo/Ecosia): Nach jedem Upload meldet
  `indexnow.py` die Seiten, deren Inhalt sich geändert hat, an [IndexNow](https://www.indexnow.org). Eine Meldung
  an `api.indexnow.org` geht an alle teilnehmenden Suchmaschinen.
- **Google** macht bei IndexNow nicht mit; den früheren „Sitemap-Ping“ gibt es seit 2023 nicht mehr, und die
  Indexing-API ist nur für Stellenanzeigen und Live-Videos erlaubt. Google liest `sitemap.xml` – dort setzt
  `hochladen.py` je Seite **`<lastmod>`** auf den Zeitpunkt, an dem sich ihr Inhalt zuletzt wirklich geändert hat.
  Sitemap einmal in der Search Console einreichen; danach holt Google sie regelmäßig selbst.

„Inhalt geändert“ heißt: Die Seite sieht anders aus als beim letzten Upload. Nicht mitgezählt werden die
Versionsanhänge `?v=…` (ändern sich bei jeder CSS-/JS-Änderung auf allen Seiten) und Bereiche zwischen
`<!-- lastmod:ohne -->` und `<!-- /lastmod:ohne -->` (derzeit „Weitere Termine“ auf Veranstaltungsseiten).
Der Stand je Seite liegt mit in `.calavera-pruefsummen.json` auf dem Server.

**Einrichten (einmalig):**

1. Schlüssel erzeugen, z. B. `python -c "import secrets; print(secrets.token_hex(16))"` (8–128 Zeichen a–z, 0–9, -).
2. In GitHub als **Variable** `INDEXNOW_KEY` anlegen (Environment `calavera-site.env`). Der Schlüssel ist nicht
   geheim: `build.py` legt ihn als `www.calavera.club/<schlüssel>.txt` ab, damit die Suchmaschinen prüfen können,
   dass die Meldung von uns kommt.
3. Optional: Seite in den [Bing Webmaster Tools](https://www.bing.com/webmasters) anmelden – dort sieht man die
   IndexNow-Meldungen.

Von Hand: `python indexnow.py https://www.calavera.club/dark/ --probe` (ohne `--probe` wird gesendet).
Fehlt der Schlüssel, endet der Schritt im Deploy bei Zeitplan/Push mit gelber Warnung, bei manuellem Start rot.
Wird `hochladen.py` lokal ohne `INDEXNOW_KEY` beim Build benutzt, löscht es die Schlüsseldatei auf dem Server –
dann beim nächsten Deploy wieder da.

Am meisten bringt außerhalb der Seite: das Google-Unternehmensprofil pflegen, überall dieselben Angaben zu
Name, Adresse und Öffnungszeiten, Einträge in Bremer Veranstaltungskalendern (Texte: `/intern/`).

### `.htaccess` für www.calavera.club

Liegt direkt im Ordner von www.calavera.club auf dem Server und wird vom automatischen Upload nicht
angefasst – also einmal von Hand anlegen bzw. ergänzen. **Als UTF-8 ohne BOM speichern und die
Zeilen selbst tippen** (aus Chats kopierte Anführungszeichen/Leerzeichen führen zu Fehler 500).

```apache
# Seiten und Kalender nicht ungeprüft aus dem Zwischenspeicher nehmen
<IfModule mod_headers.c>
  <FilesMatch "\.(html|ics|txt)$">
    Header set Cache-Control "no-cache"
  </FilesMatch>
</IfModule>

# Kalenderdateien und llms.txt richtig ausliefern (Umlaute!)
AddType text/calendar .ics
AddCharset utf-8 .ics .txt

# Eigene Fehlerseite
ErrorDocument 404 /404.html
```

`no-cache` heißt: Der Browser darf eine Kopie behalten, muss aber vor jeder Verwendung beim Server
nachfragen, ob sie noch aktuell ist. Bilder, Schriften, CSS und JS bekommen ohnehin einen
Fingerabdruck (`?v=…`) in der Adresse und dürfen lange zwischengespeichert werden.

Zusätzlich bekommen Download-Links auf `termin.ics` und der `<link rel="alternate">` auf `calavera.ics` einen
Fingerabdruck des Inhalts (`/calavera.ics?v=…`). Er ändert sich nur, wenn sich ein Termin ändert – nicht bei jedem Build.
Abo-Links (`webcal://`, Google) haben bewusst keinen, damit die Abo-Adresse gleich bleibt.

## Automatisch veröffentlichen (GitHub Actions → STRATO per SFTP)

`.github/workflows/deploy.yml` baut die Website und lädt `dist/` per SFTP hoch. Variablen und Secrets liegen im GitHub-Environment `calavera-site.env` (Settings → Environments); der Name steht im Workflow unter `environment:`.

Der Workflow läuft:

- bei jedem **Push auf `main`**,
- **täglich** um 04:17 UTC (05:17 Uhr Winterzeit / 06:17 Uhr Sommerzeit), damit Vergangenes ins Archiv wandert,
- vom **30.11. bis 23.12. zusätzlich um 23:07 UTC** (00:07 Uhr), damit die neue Tür im Adventskalender aufgeht,
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

**Hochladen:** übernimmt `hochladen.py` (Python, per `pip` – kein apt/lftp nötig). Es lädt nur Dateien hoch,
deren Inhalt sich geändert hat: die Prüfsummen merkt es sich auf dem Server in `.calavera-pruefsummen.json`
(nicht löschen – sonst wird beim nächsten Mal einmal alles hochgeladen). Beim Start von Hand gibt es das Häkchen
„Alles neu hochladen“. Lokal: `SFTP_HOST=… SFTP_USER=… SFTP_PASSWORD=… python hochladen.py dist/ <ordner> --probe`.
Die frühere lftp-Variante steht auskommentiert im Workflow.

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

## Bilder für Instagram/Facebook (`media.py`)

Macht das Bild **„Diese Woche im Calavera“** (1080 × 1350, JPG) aus den Event-Dateien der Woche (Mo–So)
und den Kellerfunk-Sendungen von live.calavera.club. Wie `reels.py` vom Website-Build getrennt: schreibt nur
nach `media/out/`. Braucht dieselben Pakete wie die Reels (Playwright + Chromium), aber kein ffmpeg.

```bash
python media.py                          # laufende Woche, alle drei Vorlagen
python media.py --vorlage plakatwand     # nur eine (Kürzel: a, b, c)
python media.py --naechste               # kommende Woche
python media.py --woche 47               # Kalenderwoche 47
python media.py --akzent "#b3122e"       # andere Akzentfarbe
python media.py --liste                  # nur anzeigen, welche Termine drauf kämen
```

| Vorlage | Kürzel | Aussehen |
|---|---|---|
| `programmzettel` | a | Liste: Tag/Datum, Flyer, Name; ab 3 Terminen kompakt |
| `plakatwand` | b | schräg geklebte Flyer mit Klebeband und roten Datums-Stickern |
| `wochenstreifen` | c | sieben Tage als Spalten – Tage ohne Programm schrumpfen zu schmalen Streifen |

Ergebnis: `media/out/woche-2026-kw45-<vorlage>.jpg` und `woche-2026-kw45-bildtext.txt` (Text zum Einfügen,
mit allen Terminen und Hashtags). Termine der Woche, die schon vorbei sind, fallen weg (`--alle` zeigt sie trotzdem).

- **Kellerfunk:** Sendungen der Woche kommen aus `kellerfunk.config` (ohne Internet: `--plan datei.yml`,
  ganz ohne: `--ohne-kellerfunk`). Ohne Visual erscheint eine dunkle Funk-Karte. Ist eine Sendung zugleich
  ein Abend im Club (gleicher Tag, ±3 Std.), steht sie nur einmal drauf – als Veranstaltung mit „Club & Stream“.
- **Ohne Flyer** (z. B. Honeycafé ohne Bild): eine helle Papierkarte mit dem Namen.
- **Eintritt:** steht unten (aus `club:`); weicht `eintritt:` in der Event-Datei davon ab, erscheint er beim
  Termin (z. B. „Hutspende“, „frei“).
- **Viele Termine:** Titel und Flyer werden kleiner, bis alles passt; höchstens 6 Termine aufs Bild (alle im Bildtext).
- **Auf GitHub:** Actions → „Bilder rendern“ → „Run workflow“; die JPGs liegen danach unter „Artifacts“.

Optional in `config.yml`:

```yaml
media:
  vorlage: wochenstreifen      # Standard statt "alle"
  akzent: "#e0485e"            # sonst je Vorlage
  qualitaet: 92                # JPG-Qualität
  hashtags: [bremen, viertel]  # zusätzlich im Bildtext
```

Die Vorlagen liegen in `media/vorlagen/` (HTML/CSS mit Jinja wie die Website; `passen.js` macht die Größen passend).

## rausgegangen.de (`rausgegangen.py`)

Trägt alle kommenden Veranstaltungen automatisch bei [rausgegangen.de](https://rausgegangen.de) ein (Rausgegangen-API v2):
je Veranstaltung ein Event mit einem Termin im Calavera. Zugeordnet wird über die `mapping_id`
`calavera-<dateiname>` – fehlende werden angelegt, geänderte nachgetragen (nur die geänderten Felder),
doppelt angelegt wird nichts. Auf GitHub läuft das automatisch nach jedem erfolgreichen Veröffentlichen.

**Einmalig einrichten**

1. API-Token bei rausgegangen anfragen: zentrale@rausgegangen.de (das „secret“ der Doku-Seite ist *kein* Token).
2. Token als GitHub-Secret `RAUSGEGANGEN_API_KEY` hinterlegen – nie in Dateien schreiben.
3. Die ID der Calavera-Location ermitteln und in `config.yml` eintragen:
   ```bash
   RAUSGEGANGEN_API_KEY=… python rausgegangen.py location
   ```
   ```yaml
   rausgegangen:
     location: "…"            # ID aus "python rausgegangen.py location"
     veroeffentlichen: false  # erst mal nur Vorschau; true = auf rausgegangen.de sichtbar
     kategorie: party         # Standard; "art: Konzert" u. ä. wird automatisch konzerte-und-musik
   ```

**Benutzen**

```bash
python rausgegangen.py                    # Probelauf: was würde gesendet? (braucht keinen Token)
python rausgegangen.py --json             # … mit allen Daten
RAUSGEGANGEN_API_KEY=… python rausgegangen.py --senden
RAUSGEGANGEN_API_KEY=… python rausgegangen.py status   # was steht dort, was fehlt, was ist dort übrig?
```

- **Übertragen werden:** Titel, Kategorie, Genres als Tags (max. 12), Teaser + Text (als erlaubtes HTML),
  DJs/Musik/Einlass, Link zur Calavera-Seite, Eintritt (`5 €` → 5,00 €; „Hutspende“ → nur als Text;
  dazu „Azubis & Studis frei · nur Abendkasse“), Beginn/Ende und das Bild.
- **Bild:** Der Build legt dafür je Flyer eine 16:9-Fassung an (`/media/events/<slug>/breit.jpg`, ganzer Flyer
  auf unscharfem Hintergrund) – rausgegangen würde einen Hochformat-Flyer sonst beschneiden. Das Bild wird nur
  beim Anlegen übertragen; neuer Flyer: in Actions „rausgegangen“ von Hand mit „Bilder … neu übertragen“ starten.
- **Veröffentlichen:** Solange `veroeffentlichen: false`, sind die Events nur über den Vorschau-Link sichtbar
  (steht in der Ausgabe). Ein in der Zentrale von Hand veröffentlichtes Event wird nicht wieder versteckt.
- **Nicht übertragen:** `rausgegangen: false` in die Event-Datei. Andere Kategorie: `rausgegangen_kategorie: theater`
  (möglich: aktiv-und-kreativ, ausstellung, feste-und-festival, film, food-und-drinks, gesprochenes,
  kinder-und-familien, konzerte-und-musik, markt, party, shows-und-performances, sport, theater).
- **Gelöscht/umbenannt:** wird dort nicht automatisch gelöscht – `status` listet solche Events, dann in der Zentrale entfernen.

## Wöchentliche Pressemitteilung (`presse.py`)

Jeden Montagmorgen kommt per Mail eine fertige Pressemitteilung „Diese Woche im Calavera“ für die laufende
Woche (Mo–So) – zum Prüfen und Weiterleiten an den eigenen Presseverteiler. Inhalt: Überschrift, Einleitung
mit allen Terminen, je Veranstaltung ein Abschnitt (Tag, Uhrzeit, DJ/Act, Genres, Beschreibung aus der
Event-Datei, Eintritt, Link), Kellerfunk-Sendungen (klar als Livestream gekennzeichnet), Links zu den Flyern
als Pressefotos, „Über das Calavera“ und Pressekontakt. Keine erfundenen Zitate – nur, was in den Dateien steht.
Fehlt bei einem Termin der Text oder steht noch ein Platzhalter drin, steht oben ein Hinweiskasten
(„vor dem Weiterleiten löschen“). Gibt es in einer Woche keine Termine, kommt keine Mail.

```bash
python presse.py                 # Probelauf: Mitteilung zeigen + presse/out/presse-2026-kw47.txt/.html
python presse.py --naechste      # für die kommende Woche
python presse.py --senden        # per Mail verschicken (braucht SMTP_* als Umgebungsvariablen)
```

**Einrichten:** In GitHub unter Settings → Secrets and variables → Actions die **Variables** `SMTP_HOST`,
`SMTP_PORT` (465 = SSL, 587 = STARTTLS), `SMTP_USER` und das **Secret** `SMTP_PASSWORD` anlegen (bei STRATO z. B.
`smtp.strato.de`, Port 465, Postfach-Adresse und -Passwort). Fehlt etwas, wird ein von Hand gestarteter Lauf rot;
oben in der Zusammenfassung jedes Laufs steht, ob und an wen gesendet wurde (mit Message-ID).
In `config.yml`:

```yaml
presse:
  an: ["team@calavera.club"]           # bekommt die Mitteilung zum Prüfen
  von: "presse@calavera.club"          # Absender (Standard: SMTP_USER) – muss zum Postfach passen
  kontakt: "Name · presse@calavera.club · Telefon"   # Pressekontakt (Standard: club.email)
  bildrechte: "Calavera Bremen"        # Bildnachweis der Flyer
  ueber: "Das Calavera ist …"          # eigener Absatz "Über das Calavera" (optional)
```

Läuft automatisch montags gegen 6:17 Uhr (Sommerzeit 7:17 Uhr); von Hand unter Actions → „Pressemitteilung“,
wahlweise für die kommende Woche oder nur als Probelauf (Text/HTML dann unter „Artifacts“).

## Planungskalender (`planer.py`)

Sammelt die Freitag- und Samstagtermine anderer Locations und des Dark-Kalenders, damit wir in unserem
Google Sheet „Calavera Terminkalender“ (Sheet A) Kollisionen mit artverwandten Partys sehen.
Ein Plugin pro Quelle in `planer/quellen/`. Mehr dazu in `docs/entscheidungen/0021-planungskalender.md`.

Ohne `--schreiben` ist jeder Aufruf ein Probelauf: Der Planer holt alles, schreibt nichts und zeigt eine Tabelle.
Mit `--schreiben` trägt er die Termine in Sheet A ein (Service-Account, siehe unten).

```bash
pip install -r requirements-planer.txt
python planer.py                        # Probelauf: heute bis 6 Monate voraus
python planer.py --bis 2027-06          # bis einschließlich Juni 2027
python planer.py --nur modernes,eisen   # nur diese Quellen
python planer.py --cache 60             # Seiten 60 min zwischenspeichern (.cache/planer/), gut beim Ausprobieren
python planer.py --json termine.json    # zusätzlich alle Termine als JSON
python planer.py --fuelle-bis 2027-06   # zeigen, welche Monatsblätter in Sheet A noch fehlen
python planer.py --schreiben            # in Sheet A schreiben (Umgebungsvariable GOOGLE_SA_JSON)
python planer.py --schreiben --fuelle-bis 2027-06   # vorher fehlende Monatsblätter bis Juni 2027 anlegen
python -m pytest tests/planer -q        # Tests (ohne Netz, mit Fixtures)
```

| Quelle | Spalte | Wie gelesen |
|---|---|---|
| Werder Bremen (Bundesliga, DFB-Pokal) | Werder | OpenLigaDB-API (werderbremen.de sperrt Abrufe); „HEIM“/„auswärts“, Anstoßzeit; > 5 Wochen voraus „(Zeit vorläufig)“ |
| Sheet B „Partyplanungen Bremen-Oldenburg“ | Dark-Kalender | CSV-Export je Jahresblatt „Kalender 2027 Bremen“, **nur lesen** |
| modernes.de | Modernes | Programmseite, Links `/events/JJJJ-MM-TT/…`, Detailseite für Uhrzeit |
| aladin-bremen.de | Aladin/Tivoli | Programmliste, Datum + Raum aus der Karte, Uhrzeit von der Detailseite; Raum in Klammern |
| eisen-bremen.com | Eisen | `veranstaltungen.php`, Links `/event/…-JJJJ-MM-TT` |
| polyester-klub.de | Polyester OL | iCal-Feed `?mec-ical-feed=1` |
| shagall-klub.com | Shagall | `/shows` (Wix), Datum + Uhrzeit aus der Karte |
| musikszene-bremen.de | Zollkantine | Kategorie „termine“ inkl. `/page/2/` …; auch Spannen („27.12. – 29.12.“) |
| lilaeule.com | Lila Eule | „Shows \| Tickets“ (Jimdo, reiner Text ohne Links); Zeile → nächstgelegenes Datum, Beginn aus „19 h / 19.30 h“ |
| zakk.klubraum.org | zakk | Startseite – zeigt nur die nächsten Tage (Monatsprogramm ist InDesign-XML ohne Jahr) |

Zeichen in den Zellen: **⚠** artverwandt und am selben Abend haben wir etwas in Bremen, **◐** artverwandt,
aber in Oldenburg oder an einem Abend ohne eigenen Termin. Was „artverwandt“ ist, steht in
`planer/stichworte.yml` (pflegt Danny). Dark-Kalender-Termine gelten immer als artverwandt.
Steht derselbe Abend auch in einer Location-Spalte, bekommt die Dark-Kalender-Zelle „= Modernes“.

**Was in Sheet A passiert** (nur mit `--schreiben`):

- Jede Quelle bekommt in jedem Monatsblatt eine eigene Spalte „Modernes ⚙“ usw., frühestens ab
  `sheet_a.erste_spalte` in `planer/quellen.yml` (Standard dort: `I`, G und H bleiben frei) und immer hinter
  der letzten belegten Spalte. Das ⚙ heißt: wird überschrieben. Eine schon vorhandene ⚙-Spalte bleibt, wo sie
  ist – auch wenn ihr sie von Hand verschiebt. Schriftgröße, Breite und Umbruch der ⚙-Spalten kommen aus
  `sheet_a.schriftgroesse` (7), `sheet_a.spaltenbreite` (80 px) und `sheet_a.umbruch` (ja) und werden bei
  jedem Lauf gesetzt.
- Mehrere Termine einer Location am selben Abend stehen untereinander in derselben Zelle.
- Relevant sind Freitag und Samstag – und jeder andere Tag, für den es im Monatsblatt schon eine Zeile gibt
  (z. B. Honey Café am Sonntag, Silvester). Solche Zeilen legt ihr selbst an, der Planer füllt dann auch dort
  seine Spalten.
- Fehlt ein Freitag oder Samstag, wird die Zeile im Block ihrer Woche eingefügt (nur Wochentag und Datum).
  Sonntage oder andere Tage fügt der Planer nie selbst ein.
  Ganz fehlende Wochen kommen als neuer Block mit Leerzeile dazwischen. Zeilen werden nie gelöscht.
- Vergangene Abende behalten ihren letzten Stand. Liefert eine Quelle einen Fehler, bleiben ihre Zellen unverändert.
- `--fuelle-bis` legt fehlende Monatsblätter als Kopie des Vormonats an (Kopf und Format), mit leerem
  Fr/Sa-Gerüst.
- Blatt **„Crawler-Status“**: je Quelle Zustand, Anzahl, Meldungen, Zeitpunkt des letzten Laufs.

**Sheet B wird nie beschrieben:** gelesen wird es über den öffentlichen CSV-Export, der Service-Account hat
dort keine Freigabe, und `SheetsApi` weist jede andere Sheet-ID als A ab (Test vorhanden).

**Einrichten (einmal):** Google Cloud Console → Projekt anlegen → „Google Sheets API“ aktivieren →
Dienstkonto anlegen (keine Rollen) → Schlüssel „JSON“ erzeugen. Inhalt als GitHub-**Secret** `GOOGLE_SA_JSON`
anlegen, Datei danach löschen. Sheet A mit der Adresse des Dienstkontos als **Bearbeiter** teilen, Sheet B nicht.
Lokal: `GOOGLE_SA_JSON="$(cat schluessel.json)" python planer.py --schreiben`. Zum gefahrlosen Ausprobieren
eine Kopie von Sheet A anlegen (Datei → Kopie erstellen), ebenfalls mit dem Dienstkonto teilen und deren ID
(aus der Adresse, zwischen `/d/` und `/edit`) als `PLANER_SHEET_A=<id>` mitgeben – Sheet B wird auch so abgewiesen.
Workflow: `.github/workflows/planer.yml` (Vorlage `planer-workflow.yml`, von Hand dorthin kopieren). Läuft täglich gegen 5:23 und
16:23 Uhr; von Hand unter Actions → „Planungskalender“ (wahlweise Probelauf oder mit `fuelle_bis`).

Neue Quelle: Datei in `planer/quellen/` mit `SPALTE`, `STADT` und `hole(http, von, bis, einstellungen, warn)`,
Eintrag in `PLUGINS` (`planer/quellen/__init__.py`) und in `planer/quellen.yml`, Fixture + Test in `tests/planer/`.

## Lizenzen

Schriften Bebas Neue, Space Grotesk, IBM Plex Mono: SIL Open Font License (siehe `static/fonts/`).
js-yaml: MIT (siehe `static/js/`).
