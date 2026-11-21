# Adventskalender – drei Entwürfe (Prototypen)

> **Überholt (21.11.):** Der Kalender ist jetzt richtig in der Seite (`/adventskalender/`, siehe README im
> Projektordner, Abschnitt „Adventskalender“, und docs/entscheidungen/0020). Dieser Ordner kann gelöscht werden.

Nur Entwürfe, **nicht im Build** (`build.py` kopiert nur `static/` und liest `events/`, `pages/`, `landing/`).
Alle Songs, Namen, Texte und Links sind **Platzhalter** (gelbes Band oben, gepunktet unterstrichen).

| Datei | Idee |
|---|---|
| `a-tueren.html` | **Türen im Raster** – nah an den Programm-Kacheln, Zahlen gemischt, Türen klappen in 3D auf, heutige Tür rot. Geöffnete Tür als Fenster mit roter Seite und großer Zahl. |
| `b-plattenkiste.html` | **Plattenkiste** – 24 Plattenhüllen (Muster nur in Schwarz/Rot/Hell), geschlossene eingeschweißt mit Datumsaufkleber, offene zeigen die Platte. Beim Öffnen rutscht die Platte heraus und dreht sich, Links als „Trackliste“. |
| `c-fallblatt.html` | **Fallblatt-Tafel** – Liste wie eine Abfahrtstafel/Setlist mit Lichterkette und Countdown, heutige Zeile „rattert“ beim Öffnen auf, Inhalt klappt in der Zeile auf. Am besten auf dem Handy. |

**Stand 21.11.: A ist Favorit.** B und C sind verworfen und können gelöscht werden (`b-plattenkiste.html`, `c-fallblatt.html`, `daten.js`, `screenshots/b-*`, `screenshots/c-*`).

## Entwurf A mit echten Daten

A liest jetzt `advent/adventskalender2026.yml` (Vorlage mit 24 leeren Türen, Format oben in der Datei erklärt).
Leere Felder erscheinen als Platzhalter (gepunktet unterstrichen, gelbes „Platzhalter“-Etikett im Fenster).
Weil der Browser die YAML per `file://` nicht nachlädt, über einen kleinen Webserver öffnen:

```bash
python -m http.server 8001        # im Projektordner
# → http://localhost:8001/entwuerfe/adventskalender/a-tueren.html?heute=7
```

B und C öffnen sich weiterhin direkt per Doppelklick (alte Platzhalter aus `daten.js`). Simulieren:

- `?heute=7` – so tun, als wäre der 7. Dezember (ohne: im Dezember 2026 der echte Tag, sonst der 7.)
- `?offen=7` – Tür 7 gleich geöffnet zeigen

Gemeinsame Platzhalter-Daten: `daten.js`. Screenshots (Desktop 1440 px, Handy 390 px): `screenshots/`, Übersicht `screenshots/vergleich.png`.

Hinweise für die echte Umsetzung:
- Keine Einbettungen (YouTube-/Bandcamp-Player laden fremde Skripte und Cookies) – nur Links, wie hier.
- Inhalte künftiger Türen gar nicht erst ausliefern (sonst stehen sie im Quelltext). Der tägliche Deploy könnte genau die Türen bis heute bauen.
- Kein localStorage – geöffnete Türen nur im Speicher der Seite (so in allen drei Entwürfen).
