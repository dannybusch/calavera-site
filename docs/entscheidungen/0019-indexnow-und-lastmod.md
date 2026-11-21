# 0019 – IndexNow nach dem Upload, echte `lastmod` in der Sitemap

Stand: 21.11.2026 · Status: gilt (Schlüssel einrichten, siehe docs/offen.md)

## Kontext
Neue Termine und Landingpages sollen schnell in Suchmaschinen auftauchen. Bing & Co. bieten IndexNow;
Google nicht (kein IndexNow, Sitemap-Ping 2023 abgeschaltet, Indexing-API nur für Jobs/Livestreams).

## Entscheidung
- `hochladen.py` entscheidet, welche Seiten neu sind – es kennt den Stand auf dem Server. Grundlage ist eine
  Inhalts-Prüfsumme je Seite aus der Sitemap, ohne `?v=…` und ohne `<!-- lastmod:ohne -->`-Bereiche
  (z. B. „Weitere Termine“), damit nicht jede Stiländerung oder jeder vergangene Termin alles „neu“ macht.
- Daraus: `<lastmod>` je Seite in `sitemap.xml` (für Google) und eine Liste geänderter/entfernter URLs.
- `indexnow.py` meldet diese Liste an `api.indexnow.org` (verteilt an Bing, Yandex, Seznam, Naver, Yep).
  Nur Python-Standardbibliothek.
- Schlüssel als GitHub **Variable** `INDEXNOW_KEY` (nicht geheim, er liegt ohnehin öffentlich als
  `/<schlüssel>.txt`); `build.py` legt die Datei an.
- Eine fehlgeschlagene Meldung macht den Deploy nicht rot (Website ist online), nur gelb; fehlender Schlüssel
  bei manuellem Start rot (wie bei anderen Zugängen).

## Folgen
- Erster Upload nach der Umstellung: alle Seiten bekommen `lastmod` = jetzt und werden einmal gemeldet.
- Wer neue wechselnde Bereiche in Templates einbaut, die nichts über die Seite selbst aussagen, markiert sie mit
  `<!-- lastmod:ohne -->…<!-- /lastmod:ohne -->`.
