# 0016 – Wöchentliche Pressemitteilung (`presse.py`)

Stand: 16.11.2026 · Status: gilt (SMTP-Einrichtung offen)

## Entscheidung (von Danny gewählt)
- Versand: montags früh per Mail **an Danny** (`presse.an`), der prüft und an seinen Verteiler weiterleitet –
  nicht direkt an Redaktionen.
- Form: klassische Mitteilung mit Fließtext – Überschrift, Einleitung, je Termin ein Absatz aus dem Event-Text,
  Eintritt, Link; Kellerfunk als Livestream gekennzeichnet; Pressefotos als Links; „Über das Calavera“; Pressekontakt.

## Weitere Festlegungen (von Claude, nicht ausdrücklich bestätigt)
- Keine erfundenen Zitate oder Fakten; Teaser nur, wenn es keinen Text gibt (sonst Wiederholung).
- Öffentlicher Titel = `social_title` (z. B. „F*** Dich Ins Knie, Melancholie“).
- Hinweiskasten „vor dem Weiterleiten löschen“ bei fehlendem Text/Platzhaltern; keine Mail in leeren Wochen.
- Zeitplan: cron `17 5 * * 1` (UTC) ≈ 6:17 Uhr Winter / 7:17 Uhr Sommer.

## Nachtrag 21.11.2026
Erster Lauf war grün, aber ohne Mail: Host/Port/Benutzer lagen (richtigerweise) als Variables vor, der Workflow
las nur Secrets – und das Script beendete sich bei fehlendem Zugang still erfolgreich. Seitdem: Variables mit
Secrets als Rückfall; fehlender Zugang → von Hand rot, geplant gelb; jede Ausführung schreibt eine Zusammenfassung.
