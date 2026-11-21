# 0015 – Facebook: Veranstaltungen und Automatisierung

Stand: 12./15.11.2026 · Status: teils offen

## Kontext
Meta erlaubt das Anlegen von Facebook-Veranstaltungen per API nur Partnern der „Official Events API“
(Aufnahme neuer Partner pausiert). Beiträge auf der Seite und Instagram-Posts/Reels sind per Graph API möglich.

## Entscheidung
- Kein vollautomatischer Browser-Bot (z. B. in GitHub Actions) für Facebook-Events: Risiko für Konto und
  Calavera-Seite (Nutzungsbedingungen, Bot-Erkennung), außerdem bricht er bei jedem Facebook-Umbau.
- Angeboten, noch nicht entschieden: (a) Claude füllt das Event-Formular in Dannys angemeldetem Browser aus,
  Danny klickt „Veröffentlichen“; (b) lokales Playwright-Script, das vor dem Veröffentlichen anhält;
  (c) `social.py` für automatische Seiten-/Instagram-Beiträge (Wochenbild, Reels); (d) Event-Paket zum Abtippen
  (Text + Titelbild 1920 × 1005). Nachfragen: ob rausgegangen Official-Events-Partner ist.
