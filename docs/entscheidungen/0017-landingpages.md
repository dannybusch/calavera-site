# 0017 – Landingpages `/dark/` und `/party/`

Stand: 21.11.2026 · Status: gilt

## Kontext
Wer „Gothic Party Bremen“ oder „Party Bremen Viertel“ sucht, landet bisher auf der Startseite oder einer
einzelnen Veranstaltung, die nach dem Abend veraltet. Danny möchte Themenseiten mit eigenem Text.

## Entscheidung
- Je Datei in `landing/` eine Seite (`landing/dark.md` → `/dark/`). Text und SEO-Angaben (`seo_title`,
  `description`, `faq`) schreibt Danny in die Datei; `<!-- mehr -->` trennt Text über und unter den Kacheln.
- Die Termine kommen automatisch aus `events/` über `zeigt:` (Reihen, Genres, Ausschlüsse, `nur_partys`).
  `/dark/` = `reihe: dark`; `/party/` = alle übrigen Partys ohne `art:` (keine Konzerte/Lesungen).
- Vergangene passende Termine bleiben als Liste stehen, damit die Seite nie leer ist.
- JSON-LD: `CollectionPage` mit allen kommenden Terminen (wie 0014: Events immer mit Titel ausliefern),
  `BreadcrumbList`, `FAQPage` nur mit echten Antworten. Eintrag in `sitemap.xml` und `llms.txt`.
- Eigener Ordner statt `pages/`, weil Landingpages Termine brauchen und `pages/` reine Textseiten bleiben.

## Folgen
- Neue Landingpage = neue `.md` in `landing/`, kein Code nötig.
- Hauptmenü nur über `config.yml → navigation` (pflegt Danny).
