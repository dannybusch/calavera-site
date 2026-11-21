# 0002 – Keine Cookies, kein Browser-Speicher, nichts Externes

Stand: Oktober/November 2026 · Status: gilt

## Kontext
Danny: „wir wollen keine Daten / keine Cookies speichern“. Ein früherer Stand merkte sich weggeklickte Bänder
(R.I.P., On-Air) in `sessionStorage` – das wurde ausdrücklich abgelehnt und entfernt.

## Entscheidung
- Keine Cookies, kein `localStorage`, `sessionStorage`, IndexedDB.
- Zustand wie „Band weggeklickt“ gilt nur bis zum nächsten Seitenaufruf (Variable im Speicher).
- Schriften, Scripts, Bilder lokal; nichts von Google o. Ä. nachladen.

## Folgen
- Kein Cookie-Banner nötig (stattdessen der augenzwinkernde „No-Cookie“-Hinweis).
- Weggeklicktes erscheint auf der nächsten Seite wieder – bewusst in Kauf genommen.
