---
# VORLAGE für eine Landingpage – Datei kopieren, umbenennen (z. B. "wave.md" → www.calavera.club/wave/)
# und ausfüllen. Dateien, deren Name mit _ beginnt, werden nicht veröffentlicht.
#
# Die Seite zeigt: Überschrift + Einleitung (Text unten), darunter automatisch die passenden kommenden
# Veranstaltungen als Kacheln, dann optional weiteren Text, Häufige Fragen und die letzten vergangenen Termine.

title: "Dark"                                   # große Überschrift auf der Seite
seo_title: "Gothic-, Wave- & EBM-Partys in Bremen"   # Titel im Browser-Tab und bei Google (sonst: title)
                                                #   (" · Calavera Bremen" wird automatisch angehängt)
description: "Ein Satz für Google, höchstens ca. 155 Zeichen. Was gibt es hier, wo, für wen?"
                                                # sonst: Anfang der Einleitung
kicker: "Calavera Dark"                         # kleine Zeile über der Überschrift (hinter "Programm /")
lead: "Ein kurzer Satz direkt unter der Überschrift."   # optional
link_text: "Calavera Dark"                      # Linktext auf Veranstaltungsseiten und im Programm (sonst: title)

# Welche Veranstaltungen gehören auf die Seite? (Kombinationen möglich)
zeigt:
  reihen: [dark]                # Veranstaltungen mit "reihe: dark" (Reihen stehen in config.yml → reihen)
  # genres: [Gothic, Wave]      # … oder mit einem dieser Genres (Groß-/Kleinschreibung egal)
  # ohne_reihen: [dark]         # alle AUSSER diesen Reihen (z. B. für "alle anderen Partys")
  # nur_partys: true            # Veranstaltungen mit "art:" (Konzert, Lesung, …) weglassen
# Einzelne Veranstaltungen zusätzlich hierher holen, ohne sie einer Reihe zuzuordnen: in der events/*.md
#   auch_auf: [dark]            # (Dateiname dieser Landingpage ohne .md) – siehe README, „Landingpages“

# archiv: 8                     # so viele vergangene Termine unten als Liste (0 = keine), Standard 8
# leer: "Gerade steht nichts an – schaut bald wieder rein."   # Text, wenn nichts Passendes im Programm ist
# bild: "dark.jpg"              # Vorschaubild beim Teilen (liegt neben dieser .md); sonst Flyer des nächsten Termins
# noindex: true                 # nicht in Suchmaschinen/Sitemap
# draft: true                   # Entwurf: wird nicht veröffentlicht

# Häufige Fragen: erscheinen auf der Seite und als FAQ für Google/KI-Antworten. Nur echte Antworten!
faq:
  - frage: "Was kostet der Eintritt?"
    antwort: "5 €, Azubis & Studis frei – nur Abendkasse."
---
Hier steht die Einleitung – ganz normales Markdown, erscheint ÜBER den Kacheln. Suchbegriffe, nach denen Leute suchen (z. B. „Gothic Party Bremen“), natürlich in den Text einbauen.

<!-- mehr -->

Alles unter der Zeile `<!-- mehr -->` erscheint UNTER den Kacheln. Platz für ausführlicheren Text: Geschichte der Reihe, DJs, Musikrichtungen, Anfahrt … (Zwischenüberschriften mit ## gehen auch.)