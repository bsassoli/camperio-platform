# Segreti della piattaforma — quali esistono, dove vivono, chi li rigenera

Mai i valori in questo repo, nei log o negli output (spec §7). Sei segreti in tutto:

| Segreto | Dove vive | Chi lo rigenera |
|---|---|---|
| `ORA_PWD` (utenza servizio sola lettura) | `/etc/camperio/camperio.env` (root, 600) | DBA Camperio |
| `ANTHROPIC_API_KEY` | `/etc/camperio/camperio.env` | Bernardino (console Anthropic) |
| Client secret oauth2-proxy (app registration Entra) | `/etc/camperio/camperio.env` | IT Camperio (Entra ID) |
| Cookie secret oauth2-proxy | `/etc/camperio/camperio.env` | Bernardino (`openssl rand -base64 32`) |
| Password Postgres | `/etc/camperio/camperio.env` | Bernardino (sulla VM) |
| Deploy key SSH read-only (una per ambiente) | `~/.ssh/` dell'ambiente | Bernardino (GitHub deploy keys) |

Credenziale email (SMTP o Graph): si aggiunge quando l'IT sceglie il canale (voce 9).
Consegna: mai per email — Passwordstate, canale cifrato o di persona.
