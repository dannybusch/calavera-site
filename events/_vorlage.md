---
# VORLAGE – Datei kopieren, umbenennen (JJJJ-MM-TT-name.md) und ausfüllen.
# Dateien, deren Name mit _ beginnt, werden nicht veröffentlicht.
#
# Pflicht: title, start. Alles andere ist optional.
# Zeiten in Bremer Ortszeit, in Anführungszeichen – wie auf live.calavera.club.

title: "Name der Party"
start: "2026-12-04 22:00"        # oder nur "2026-12-04" → Standardbeginn aus config.yml (22:00)
# end: "04:00"                   # Uhrzeit = am Folgetag, wenn früher als start; ohne end: start + 6 h
# einlass: "19:30"               # nur angeben, wenn abweichend (z. B. Konzerte)
# art: "Konzert"                 # kleines Etikett über dem Datum, z. B. Konzert, Lesung, Special
# highlight: "Live-Konzert"      # hebt die Kachel im Programm hervor (gleiche Größe, rotes Etikett, roter Schimmer);
#                                # highlight: true → Etikett "Highlight"
# reihe: dark                    # gehört zu einer Reihe aus config.yml → reihen (z. B. Calavera Dark);
#                                # wirkt auf "Weitere Termine": Termine derselben Reihe stehen dort vorn
# subtitle: "Singer/Songwriter aus Berlin"   # ersetzt die DJ-Zeile unter dem Titel
djs: ["DJ Name"]
genres: ["Wave", "Postpunk"]
tags: ["Ab 18"]                  # z. B. Ab 18, Rauchfrei
# stream: true                   # läuft auch live im Stream (Standard: Kellerfunk, live.calavera.club)
# stream:                        # … oder mit eigenem Link/Text:
#   url: "https://www.mixcloud.com/live/calaverabremen/"
#   label: "Auch im Stream"
# eintritt: "Hutspende"          # sonst Standard aus config.yml (5 € · Azubis & Studis frei)
# fans_of: ["The Cure", "Joy Division"]      # "Für Freunde von"
# teaser: "Ein Satz für die Kachel"          # sonst: der erste Absatz unten, gekürzt
# visual: "mein-flyer.jpg"       # sonst automatisch: Bild mit gleichem Dateinamen wie diese .md
# visual_alt: "Flyer: …"         # Bildbeschreibung für Screenreader
# links:
#   - { label: "Bandcamp", url: "https://…" }
# draft: true                    # Entwurf: wird nicht veröffentlicht
---

Hier kommt der Text zur Veranstaltung – ganz normales Markdown:
**fett**, *kursiv*, [Links](https://example.org), Absätze durch eine Leerzeile.
