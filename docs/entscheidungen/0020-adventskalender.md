# 0020 – Adventskalender `/adventskalender/`

Stand: 21.11.2026 · Status: gilt

## Kontext
Danny möchte einen Adventskalender: hinter jeder Tür ein Lieblingssong von jemandem aus dem Team oder von
den DJs, mit kurzem Text und Links zu Streamingdiensten. Von drei Entwürfen (Türen im Raster, Plattenkiste,
Fallblatt-Tafel) wurde der nah am Seitendesign gewählt; verspielte Gimmicks sind ausdrücklich nicht gewünscht.

## Entscheidung
- Daten in `advent/adventskalender<jahr>.yml` (eigener Ordner wie `landing/`), gebaut von `build.py`
  (`load_advent`, `advent_stand`), Template `adventskalender.html`, CSS/JS nur auf dieser Seite.
- **Nichts Künftiges ausliefern:** Die YAML wird nie kopiert; ins HTML (auch JSON-LD, `llms.txt`) kommen
  nur Türen, deren Tag am Build-Zeitpunkt erreicht ist. Künftige Türen: nur Zahl + Datum. Das Script enthält
  keine Daten. Leere, aber fällige Türen sehen aus wie geschlossene („Folgt in Kürze“).
- Statische Seite → neue Tür über einen zusätzlichen Deploy um 00:07 Uhr (30.11.–23.12., cron `7 23 …`).
  Fällige, leere Türen sind nur ein Hinweis, kein `--strict`-Fehler – sonst fiele um Mitternacht der ganze Deploy aus.
- Nur Links, keine eingebetteten Player (fremde Skripte/Cookies, siehe 0002).
- Deep-Links `#tuer-N` zum Teilen; ohne JavaScript Liste der geöffneten Türen.
- Seitenmenü: sechster Punkt passt auf Tablets nicht neben das Wappen → `.nav` hält Abstand zum Wappen und
  bricht in eine zweite Zeile um (behebt nebenbei eine Überlappung, die es schon mit fünf Punkten gab).

## Folgen
- Menüpunkt über `config.yml → navigation` (Danny). Zum Start `draft: false` setzen.
- GitHub-Verspätungen bei geplanten Läufen: Tür kann sich um Minuten (selten bis ~1 h) verzögern;
  der Lauf um 05:17 Uhr ist das Netz.
