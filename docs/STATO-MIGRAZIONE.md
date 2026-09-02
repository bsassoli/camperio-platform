# Stato migrazione — punto fermo del 28 agosto 2026

Primo deploy sulla VM Elmec (`app-ai.camperiosim.com`) portato fino alla **fine della
Parte 6** del runbook (`DEPLOY.md`). I blocchi per la Parte 7 sono **due**,
entrambi in attesa di consegne esterne: il **certificato TLS** (richiesta B1, IT) e le
**credenziali Oracle** `ORA_USER`/`ORA_PWD` (richiesta A1, DBA — v. sezione dedicata).
Il resto della configurazione è stato validato fino al punto in cui, senza quelle
consegne, non si può andare.

## Dove siamo, voce per voce

| Parte del runbook | Stato |
|---|---|
| 1 — Preparazione VM (Docker, deploy key, clone in `/opt/camperio`) | ✅ fatta |
| 2 — Prova DEMO + test di hardening | ✅ fatta |
| 3 — Segreti compilati in `/etc/camperio/camperio.env` | ⚠ quasi: **mancano `ORA_USER` e `ORA_PWD`** (v. sotto) |
| 3.3 — Certificato TLS in `/etc/camperio/tls/` | ❌ AD CS in attesa dell'IT (B1) — **dal 2 settembre 2026 sbloccato dalla CA interna provvisoria** (runbook 3.3 B, `deploy/tls/genera-ca-interna.sh`) |
| 4 — Prova LIVE, gate su dati reali, auth applicativa (401/200) | ⚠ **da rifare**: senza `ORA_USER`/`ORA_PWD` l'app era in DEMO, non LIVE |
| 5 — Unit systemd installate, `camperio.service` **abilitato ma non avviato** | ✅ fatta |
| 6 — Checklist pre-esposizione | ✅ tranne la voce certificato |
| 6.1 — Pre-flight `nginx -t` | ⏳ arriva fino a `cannot load certificate` — che è l'esito atteso senza certificato |
| 7 — Accensione | ❌ **non fatta** (un tentativo prematuro, rientrato: v. sotto) |

**Stato della VM al momento dello stop:** stack Compose spento
(`sudo systemctl stop camperio`), nessun container attivo, nessuna porta esposta.
`camperio.service` resta `enabled`: se la VM viene riavviata prima dell'arrivo del
certificato, lo stack riparte da solo e **nginx andrà in crash-loop** sul certificato
mancante. È innocuo (nginx non serve nulla in quello stato) ma rumoroso nei log; se la
VM deve essere riavviata in questa finestra, o si preferisce il silenzio:
`sudo systemctl disable camperio` e re-`enable` alla ripresa.

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
4. **Tentata la Parte 7 senza certificato**: nginx in crash-loop, `curl` muto sulla
   443. Rientrato con `systemctl stop camperio`. La Parte 7 si apre **solo** a
   checklist di Parte 6 tutta verde — il certificato è una delle voci.

## Il secondo blocco: le credenziali Oracle mancano

L'inventario del file (28/8, sera) ha chiuso le verifiche che erano rimaste aperte:

- **`OAUTH2_PROXY_ALLOWED_GROUPS` c'è** ✅ — il lato Entra/oauth2-proxy è completo
  (c'è anche `OAUTH2_PROXY_PROVIDER`, non prevista dal template ma corretta).
- **Mancano `ORA_USER` e `ORA_PWD`** ❌ — c'è solo `ORA_DSN`: l'indirizzo del
  database senza le credenziali. E poiché il file è stato ricostruito dall'ambiente
  *completo* del container, con ogni probabilità non ci sono mai state: l'app ha
  sempre girato in DEMO, e la Parte 4 va considerata **non fatta**.

Perché è bloccante quanto il certificato: senza `ORA_*` completi l'app **non dà
errore** — parte in DEMO su dati sintetici, per contratto. Arrivare alla Parte 7 così
significherebbe pubblicare l'app con dati finti e nessun sintomo a dirlo. Il 503 sui
guasti Oracle scatta solo a configurazione LIVE completa.

Rimedio (non serve il certificato, si può fare subito):

```bash
# 1. valori dal DBA / Passwordstate (richiesta A1); poi:
sudo nano /etc/camperio/camperio.env        # aggiungere ORA_USER=... e ORA_PWD=...

# 2. prova del collegamento
cd /opt/camperio/deploy
docker compose up -d --force-recreate comitato
docker compose exec comitato python -c "import data_layer as DL; print(DL.mode())"   # atteso: LIVE

# 3. poi la Parte 4 per intero: gate su dati reali via tunnel (4.2) e auth 401/200 (4.3)
```

## Bug trovato il 2 settembre 2026: la VM spariva a ogni `systemctl start camperio`

**Sintomo:** dopo l'avvio dello stack la VM non rispondeva più (né ping né ssh) ai PC
aziendali in `172.18.x.x`; dalla macchina `172.30.231.70`, stessa subnet della VM,
tutto funzionava. **Causa:** il compose non fissava una subnet e Docker ha assegnato
alla rete `camperio_default` la `172.18.0.0/16`, aggiungendo sulla VM una rotta che
dirottava nel bridge Docker ogni risposta verso i client aziendali. **Correzione:**
subnet fissa `192.168.238.0/24` nel compose (commit nel repo) e pool Docker ristretto
in `/etc/docker/daemon.json` (runbook 1.2-bis, da applicare a mano sulla VM).

## Ripresa, quando arriva il certificato

Non si rifà nulla delle Parti 1–5: unit systemd già installate e abilitate, immagine
già costruita, segreti già compilati. La sequenza è:

**1. Installare il certificato** (runbook 3.3). Decisione del 2 settembre 2026: non si
aspetta più B1, si parte con la **CA interna provvisoria**:

```bash
cd /opt/camperio && git pull
sudo /opt/camperio/deploy/tls/genera-ca-interna.sh
grep -c "BEGIN CERTIFICATE" /etc/camperio/tls/fullchain.pem   # atteso: 2
```

Poi `ca.crt` va installato sui client pilota **prima** del loro primo accesso (3.3 B:
con HSTS il browser non offre il "procedi comunque"). Quando l'IT consegna il
certificato AD CS si sovrascrivono i due file e si ricarica nginx (3.3 A).

**2. Credenziali Oracle a bordo e Parte 4 rifatta** (sezione sopra) — si può fare
anche prima che il certificato arrivi.

**3. Rifare il pre-flight 6.1** — stavolta fino in fondo:

```bash
cd /opt/camperio/deploy
docker compose up -d comitato oauth2-proxy
docker compose ps          # entrambi Up (dare ~30 s: un 'Up Less than a second' non basta)
docker compose run --rm --no-deps --entrypoint nginx nginx -t   # atteso: syntax is ok / test is successful
ss -tlnp | grep ':443'     # atteso: vuoto — la 443 e' ancora chiusa
```

**4. Ripassare la checklist di Parte 6** — ora spuntabile per intero.

**5. Accendere** (runbook Parte 7, invariato):

```bash
sudo systemctl start camperio.service
docker compose ps                          # tre container Up — e che ci RESTINO
ss -tlnp | grep ':443'                     # la 443, e nient'altro
curl -k -sI https://127.0.0.1/ | grep -iE "^(HTTP|location)"   # atteso: 302 verso login.microsoftonline.com
```

Poi le verifiche con utenti reali (7.2 — dentro e fuori dal gruppo Entra, **prima** di
comunicare l'URL) e il timer ETF (7.3).

**Se qualcosa va storto al punto 5:** `sudo systemctl stop camperio` riporta alla
situazione attuale — spento, chiuso, nessun danno. È il rollback della Parte 8.
