# 0003 – Zugangsdaten nur in GitHub Secrets/Variables

Stand: Oktober 2026 · Status: gilt

## Entscheidung
Passwörter, Tokens, Schlüssel nur als GitHub Secrets (nicht-geheime Werte wie Host als Variables) bzw.
lokal als Umgebungsvariablen. Nie in `config.yml`, Code, Logs oder Commits. Workflows ohne ihr Secret
beenden sich ruhig, statt zu scheitern.

## Folgen
- SFTP: `SFTP_PASSWORD`, `SFTP_KNOWN_HOSTS` (Secrets), Host/User/Ordner als Variables.
- rausgegangen: `RAUSGEGANGEN_API_KEY`. Presse: `SMTP_*`.
- Ein im Chat genannter Schlüssel (z. B. das Doku-„secret“ von rausgegangen) gehört nicht ins Repo.
