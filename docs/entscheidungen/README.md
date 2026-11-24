# Entscheidungen

Je Grundsatzentscheidung eine Datei: Kontext, Entscheidung, Folgen. Neue Datei mit nächster Nummer anlegen;
Überholtes nicht löschen, sondern Status auf „abgelöst durch NNNN“ setzen.

| Nr. | Thema | Status |
|---|---|---|
| [0001](0001-statische-website.md) | Statische Website aus einem Python-Script | gilt |
| [0002](0002-keine-daten-im-browser.md) | Keine Cookies, kein Browser-Speicher, nichts Externes | gilt |
| [0003](0003-zugangsdaten.md) | Zugangsdaten nur in GitHub Secrets/Variables | gilt |
| [0004](0004-events-und-config-pflegt-danny.md) | `events/` und `config.yml` pflegt Danny selbst | gilt |
| [0005](0005-lieferform.md) | Lieferform: geänderte Dateien + Patch (Cloud-Chat) → direkt im Repo (Desktop) | abgelöst für lokale Sitzungen |
| [0006](0006-effektsystem.md) | Effekte auf Flyern/Kacheln: Aufbau und Qualitätsanspruch | gilt |
| [0007](0007-rahmen-und-takeover.md) | Neutrale Rahmen, Startseiten-Übernahme | gilt |
| [0008](0008-kellerfunk.md) | Kellerfunk: Darstellung und Kennzeichnung | gilt |
| [0009](0009-seiteneffekte.md) | Seiteneffekte: global, zeitgesteuert, generisch | gilt |
| [0010](0010-reels.md) | Reels als eigener Prozess | gilt |
| [0011](0011-wochenbild-media.md) | „Diese Woche im Calavera“-Bild (`media.py`) | gilt |
| [0012](0012-rausgegangen.md) | rausgegangen.de per API (`rausgegangen.py`) | gilt (Einrichtung offen, siehe docs/offen.md) |
| [0013](0013-hochladen.md) | Hochladen mit `hochladen.py` statt lftp | gilt |
| [0014](0014-seo-und-ki.md) | Suchmaschinen und KI-Antworten | gilt |
| [0015](0015-facebook.md) | Facebook: Veranstaltungen und Automatisierung | teils offen |
| [0016](0016-pressemitteilung.md) | Wöchentliche Pressemitteilung (`presse.py`) | gilt (SMTP-Einrichtung offen) |
| [0017](0017-landingpages.md) | Landingpages `/dark/` und `/party/` aus `landing/*.md` | gilt |
| [0018](0018-bild-cache.md) | Bild-Cache mit Prüfsumme in `build.py` | gilt |
| [0019](0019-indexnow-und-lastmod.md) | IndexNow nach dem Upload, echte `lastmod` in der Sitemap | gilt (Schlüssel einrichten, siehe docs/offen.md) |
| [0020](0020-adventskalender.md) | Adventskalender `/adventskalender/` aus `advent/*.yml`, nur geöffnete Türen im HTML | gilt |
| [0021](0021-planungskalender.md) | Planungskalender: Fr/Sa-Termine anderer Locations in Sheet A (`planer.py`) | gilt (Etappe 1, Schreiben ab Etappe 2) |
| [0022](0022-kalender-abo.md) | Kalender-Abo per webcal:// (`calavera.ics`, je Landingpage) | gebaut, ausgeschaltet (Android-Problem offen) |
