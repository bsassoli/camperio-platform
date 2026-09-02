# Stato migrazione — aggiornato al 2 settembre 2026 (pomeriggio)

Lo stack è **esposto**: `sudo systemctl start camperio.service` è stato dato, i tre
container (`comitato`, `oauth2-proxy`, `nginx`) sono `Up`, la 443 risponde con `302`
verso `login.microsoftonline.com` e l'app è in modalità **LIVE** (`ORA_USER`/`ORA_PWD`
sono a bordo). La Parte 7.1 del runbook (`DEPLOY.md`) è fatta. Restano da chiudere la
7.2 (verifica con utenti reali, assegnati e non assegnati all'app in Entra) e la 7.3
(accensione del timer ETF).

## Dove siamo, voce per voce

| Parte del runbook | Stato |
|---|---|
| 1 — Preparazione VM (Docker, deploy key, clone in `/opt/camperio`) | ✅ fatta |
| 2 — Prova DEMO + test di hardening | ✅ fatta |
| 3 — Segreti compilati in `/etc/camperio/camperio.env` | ✅ fatta (`ORA_USER`/`ORA_PWD` a bordo) |
| 3.3 — Certificato TLS in `/etc/camperio/tls/` | ✅ CA interna provvisoria attiva (runbook 3.3 B, `deploy/tls/genera-ca-interna.sh`) — resta da sostituire col certificato AD CS quando l'IT lo consegna (B1, 3.3 A) |
| 4 — Prova LIVE, gate su dati reali, auth applicativa (401/200) | ✅ fatta — `data_layer.mode()` conferma `LIVE` |
| 5 — Unit systemd installate, `camperio.service` abilitato | ✅ fatta, e ora **avviato** |
| 6 — Checklist pre-esposizione | ✅ fatta per intero |
| 6.1 — Pre-flight `nginx -t` | ✅ passato |
| 7.1 — Accensione | ✅ fatta: tre container `Up`, `curl -k https://127.0.0.1/` → `302` verso Microsoft |
| 7.2 — Verifiche con utenti reali (assegnato/non assegnato all'app in Entra) | ❌ **da fare** — richiede un browser e due utenti Entra, non automatizzabile dalla VM |
| 7.3 — Timer ETF | ❌ **da fare** — `camperio-scarica-etf.timer` ancora `disabled`/`inactive` |

**Stato della VM ora:** stack su, esposto sulla 443, nessun altro fuori. Se la VM
viene riavviata, `camperio.service` riparte da solo (è `enabled`).

## Cosa è successo durante il deploy (per non ripeterlo)

1. **Cookie secret oauth2-proxy in crash-loop** (`must be 16, 24, or 32 bytes ... but
   is 44 bytes`): il secret era stato generato con `openssl rand -base64 32` **senza**
   il `tr '+/' '-_'`. oauth2-proxy vuole base64 URL-safe. Corretto nel runbook (3.2),
   nel template e in SECRETS.md — commit `3902d3a`.
2. **`nginx -t` del 6.1 fallito con `host not found in upstream`**: nginx risolve gli
   upstream all'avvio, e `oauth2-proxy` era giù (per l'errore 1). Il runbook ora alza
   `comitato` e `oauth2-proxy` prima del test — stesso commit.
3. **File dei segreti sovrascritto per errore** durante la correzione del cookie
   secret: un salvataggio da nano ha ridotto `/etc/camperio/camperio.env` alla sola
   riga del secret. **Ricostruito** estraendo l'ambiente dal container `comitato`
   ancora in esecuzione (`docker inspect`), che aveva caricato il file completo.
   Lezione: per cambiare una riga sola, meglio `sudo sed -i` della riga che un
   editor sull'intero file.
4. **Tentata la Parte 7 senza certificato** (28/8): nginx in crash-loop, `curl` muto
   sulla 443. Rientrato con `systemctl stop camperio`. Sbloccato poi dalla CA interna
   provvisoria (v. sotto).
5. **La VM spariva dalla rete a ogni `systemctl start camperio`** (2/9, mattina): il
   compose non fissava una subnet e Docker ha assegnato a `camperio_default` la
   `172.18.0.0/16`, la stessa dei PC aziendali — le risposte finivano nel bridge
   Docker invece che al gateway. **Correzione:** subnet fissa `192.168.238.0/24` nel
   compose, pool Docker ristretto in `/etc/docker/daemon.json` (runbook 1.2-bis).
6. **oauth2-proxy rifiutava ogni redirect dopo l'esposizione** (2/9, pomeriggio):
   `OAUTH2_PROXY_WHITELIST_DOMAINS` non era configurato, e senza whitelist
   oauth2-proxy scarta **qualunque** redirect assoluto — nginx costruisce sempre
   `rd=` assoluto nell'`error_page 401`. Un utente reale (`172.18.11.23`) ha provato
   ad accedere 4 volte prima ancora che l'URL fosse comunicato (7.2 non ancora
   fatta). **Corretto** aggiungendo `app-ai.camperiosim.com` alla whitelist —
   commit `060a749`, verificato con `--force-recreate` di `oauth2-proxy`.

## Rimasto da fare

**1. Parte 7.2 — verifica con utenti reali**, da un client con `ca.crt` già
installato (3.3 B):

```
https://app-ai.camperiosim.com/  con un utente ASSEGNATO all'app  → login, app col tuo utente
stesso URL con un utente NON ASSEGNATO                             → Entra rifiuta in login (AADSTS50105), non 403 dell'app
```

Controllo aggiuntivo dalla VM: `docker compose logs oauth2-proxy` senza errori di
issuer o redirect (a parte gli eventuali test da `127.0.0.1`, che sono attesi).

**2. Parte 7.3 — accendere il timer ETF:**

```bash
sudo systemctl start camperio-scarica-etf.service
journalctl -u camperio-scarica-etf -n 50
sudo systemctl enable --now camperio-scarica-etf.timer
systemctl list-timers 'camperio-*'
```

**Se qualcosa va storto:** `sudo systemctl stop camperio` spegne tutto senza danno —
è il rollback della Parte 8.
