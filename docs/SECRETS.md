# Segreti della piattaforma — quali esistono, dove vivono, chi li rigenera

Mai i valori in questo repo, nei log o negli output (spec §7). Sei segreti in tutto:

| Segreto | Dove vive | Chi lo rigenera |
|---|---|---|
| `ORA_PWD` (utenza servizio sola lettura) | `/etc/camperio/camperio.env` (`root:docker`, 640) | DBA Camperio |
| `ANTHROPIC_API_KEY` | `/etc/camperio/camperio.env` | Bernardino (console Anthropic) |
| Client secret oauth2-proxy (app registration Entra) | `/etc/camperio/camperio.env` | IT Camperio (Entra ID) |
| Cookie secret oauth2-proxy | `/etc/camperio/camperio.env` | Bernardino (`openssl rand -base64 32`) |
| Chiave privata TLS | `/etc/camperio/tls/privkey.pem` (600) | IT Camperio (AD CS) |
| Deploy key SSH read-only (una per macchina) | `~/.ssh/` della macchina | Bernardino (GitHub deploy keys) |

**Perché `root:docker` 640 e non 600:** il file lo legge `docker compose` come l'utente di
servizio, che sta nel gruppo `docker`. Con 600 servirebbe `sudo` per ogni comando compose;
con 640 il gruppo legge e nessun altro utente vede i segreti (v. `docs/DEPLOY.md` 3.1).
La chiave TLS invece resta 600: la legge nginx dentro il container, come root.

**Scadenze da presidiare** (non sono segreti da rigenerare a comando, ma smettono di
funzionare da soli):

- il **client secret** dell'app registration Entra ha una data di scadenza: farsela dare
  dall'IT insieme al valore, e sapere chi lo rinnova;
- il **certificato TLS** AD CS: stessa cosa, data e titolare del rinnovo.

Credenziale email (SMTP o Graph): si aggiunge quando l'IT sceglie il canale (voce 9).
Consegna: mai per email — Passwordstate, canale cifrato o di persona.
