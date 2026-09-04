# Stato migrazione — completata il 4 settembre 2026

Il runbook (`DEPLOY.md`, Parti 1–7) è **chiuso per intero**. Lo stack è esposto
(`camperio`, `oauth2-proxy`, `nginx` `Up`), l'app è in modalità **LIVE** su
**ANTANA (produzione)** — `ORA_DSN=selmora01.ad.camperiosim.com:1521/antana.ad.camperiosim.com`
— login Entra verificato con utenti assegnati e non assegnati (7.2), e il timer
`camperio-scarica-etf.timer` è attivo (7.3, abilitato il 4/9, primo run atteso
giovedì 2026-09-10 11:00 UTC — il test-fire manuale dello stesso giorno ha già dato
9/9 ETF scaricati).

Resta aperto solo un punto non bloccante: il certificato TLS gira ancora sulla **CA
interna provvisoria** (3.3 B), in attesa del certificato AD CS dall'IT (richiesta B1,
3.3 A) — sostituzione a runbook invariato quando arriva, nessun altro impatto.

## Dove siamo, voce per voce

| Parte del runbook | Stato |
|---|---|
| 1 — Preparazione VM (Docker, deploy key, clone in `/opt/camperio`) | ✅ fatta |
| 2 — Prova DEMO + test di hardening | ✅ fatta |
| 3 — Segreti compilati in `/etc/camperio/camperio.env` | ✅ fatta (`ORA_USER`/`ORA_PWD` a bordo) |
| 3.3 — Certificato TLS in `/etc/camperio/tls/` | ✅ CA interna provvisoria attiva (runbook 3.3 B, `deploy/tls/genera-ca-interna.sh`) — resta da sostituire col certificato AD CS quando l'IT lo consegna (B1, 3.3 A) |
| 4 — Prova LIVE, gate su dati reali, auth applicativa (401/200) | ✅ fatta — `data_layer.mode()` conferma `LIVE`, connesso su **ANTANA (produzione)** dal 4/9 (prima su ANTATEST per il collaudo) |
| 5 — Unit systemd installate, `camperio.service` abilitato | ✅ fatta, e ora **avviato** |
| 6 — Checklist pre-esposizione | ✅ fatta per intero |
| 6.1 — Pre-flight `nginx -t` | ✅ passato |
| 7.1 — Accensione | ✅ fatta: tre container `Up`, `curl -k https://127.0.0.1/` → `302` verso Microsoft |
| 7.2 — Verifiche con utenti reali (assegnato/non assegnato all'app in Entra) | ✅ fatta |
| 7.3 — Timer ETF | ✅ fatta — test-fire manuale 9/9 OK, timer abilitato, `NEXT`: giovedì 2026-09-10 11:00 UTC |

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
7. **Login Entra impossibile, `AADSTS700016`** (2/9, pomeriggio): nessuna app
   registration esisteva davvero su Entra ID — `OAUTH2_PROXY_CLIENT_ID` era un
   placeholder mai sostituito. Nello stesso file, `OAUTH2_PROXY_ALLOWED_GROUPS`
   non conteneva un objectId di gruppo ma quasi lo stesso valore di
   `OAUTH2_PROXY_CLIENT_SECRET` (mancava solo il primo carattere): un segreto
   finito per errore in due variabili durante una ricostruzione precedente del
   file. **Risolto** creando l'app registration "app-ai" da zero (redirect URI,
   claim/assegnazione, nuovo client secret) — v. commit `46b8718` per il
   passaggio da autorizzazione a gruppo ad autorizzazione per utenti assegnati,
   che nel frattempo ha reso `ALLOWED_GROUPS` non più pertinente.
8. **Oracle irraggiungibile in LIVE, `DPY-6001` (`ORA-12514`)** (4/9): la rete
   verso `selmora01.ad.camperiosim.com:1521` funzionava, ma quel listener non ha
   mai avuto il servizio `ANTATEST` registrato — lo serve `selmora02`, non
   `selmora01` (che serve `ANTANA`, l'ambiente di produzione). Il messaggio
   d'errore mostrato in pagina (`apps/comitato/app.py:163`) riporta solo il
   testo generico di `OracleIndisponibileError`, non la causa reale: per
   vederla bisogna connettersi a mano da dentro il container (comando in fondo
   a questo file). **Corretto** il DSN in
   `selmora02.ad.camperiosim.com:1521/ANTATEST`; connessione verificata OK.
   Rete verso `selmora02` già aperta, nessuna richiesta aggiuntiva all'IT.
9. **Passaggio da ANTATEST ad ANTANA (produzione)** (4/9): verificato prima che
   `ORA_USER`/`ORA_PWD` avessero accesso anche su ANTANA (stesso listener
   `selmora01`, service name `antana.ad.camperiosim.com` — stringa lunga, non
   un nome breve come `ANTATEST`), poi cambiato il DSN. Connessione OK,
   confermata dopo la 7.2. **L'app ora legge dati reali di produzione.**
10. **`X-Auth-Request-User` mostrava il `sub` OIDC** (id opaco pairwise, tipo
    `7p7Z2Eq3...`), non il nome utente (4/9): è così di default in
    oauth2-proxy, il flag `--prefer-email-to-user` **non** si applica a questo
    header (solo a `--pass-user-headers`/`--pass-basic-auth`). **Corretto** in
    nginx: `$auth_user` ora prende `$upstream_http_x_auth_request_email`
    invece di `..._user`. Aggiunti anche due pulsanti in pagina: "Esci"
    (chiude solo la sessione app) e "Esci da tutto" (redirect al logout Entra,
    chiude anche la sessione SSO nel browser — disconnette pure altre app
    aziendali che la condividono, è voluto).
11. **`nginx` con DNS stantio su `oauth2-proxy` dopo un force-recreate** (4/9,
    scoperto verificando il punto 10): `proxy_pass http://oauth2-proxy:4180`
    è statico, nginx risolve l'hostname una sola volta all'avvio — esattamente
    il problema già noto e corretto per `comitato` (v. commento in
    `nginx.conf`), ma mai applicato a `oauth2-proxy`. Ricreare `oauth2-proxy`
    senza ricreare anche `nginx` lascia nginx puntato al vecchio IP:
    `connect() failed (111: Connection refused)` nei log, 500 al posto del
    302 di login. **Corretto** con lo stesso pattern resolver+variabile.
    **Promemoria operativo:** ricreare sempre `nginx` insieme a `oauth2-proxy`
    (o a `comitato`), non uno dei due soltanto.
12. **Contatti sbagliati in calce alla pagina** (4/9): telefono e dominio email
    non aggiornati (`+39-02 30322100` e `camperioSIM@camperio.net`, un dominio
    non aziendale). **Corretto** in `+39 02.50020918` e
    `CamperioSim@camperiosim.com`.
13. **Timer ETF mai testato prima dell'abilitazione** (4/9): nessun log, nessun
    run precedente. Lanciato a mano `docker compose run --rm -T comitato python
    scarica_etf.py` come test-fire: **9/9 ETF scaricati OK**. Timer poi
    abilitato — prossimo run giovedì 2026-09-10 11:00 UTC.

## Rimasto da fare

Un solo punto, non bloccante: **sostituire la CA interna provvisoria col certificato
AD CS** (3.3 A) quando l'IT lo consegna (richiesta B1) — procedura in `DEPLOY.md`
3.3, nessun altro impatto sul resto dello stack.

**Rollback, se mai servisse:** `sudo systemctl stop camperio` spegne tutto senza
danno (Parte 8). Per il solo timer ETF: `sudo systemctl disable --now camperio-scarica-etf.timer`.

## Comando per leggere l'errore Oracle reale (non quello mostrato in pagina)

`apps/comitato/app.py:163` mostra solo il messaggio generico di
`OracleIndisponibileError`, non la causa. Per vederla:

```bash
docker compose exec -T comitato python -c "
from camperio_core import config as _config
import oracledb
cfg = _config.from_env()
print('DSN:', cfg.ora_dsn)
try:
    oracledb.connect(user=cfg.ora_user, password=cfg.ora_pwd, dsn=cfg.ora_dsn).close()
    print('CONNESSIONE OK')
except Exception as e:
    print('ERRORE:', type(e).__name__, '-', e)
"
```
