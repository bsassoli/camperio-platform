# Stato migrazione — punto fermo del 28 agosto 2026

Primo deploy sulla VM Elmec (`app-ai.camperiosim.com`) portato fino alla **fine della
Parte 6** del runbook (`DEPLOY.md`). Ci si è fermati lì per l'unico motivo previsto:
**manca il certificato TLS** (richiesta B1 all'IT, ancora aperta). Non ci sono problemi
tecnici in sospeso sulla piattaforma: la configurazione è stata validata fino al punto
in cui, senza certificato, non si può andare.

## Dove siamo, voce per voce

| Parte del runbook | Stato |
|---|---|
| 1 — Preparazione VM (Docker, deploy key, clone in `/opt/camperio`) | ✅ fatta |
| 2 — Prova DEMO + test di hardening | ✅ fatta |
| 3 — Segreti compilati in `/etc/camperio/camperio.env` | ✅ fatta (v. incidente sotto) |
| 3.3 — Certificato TLS in `/etc/camperio/tls/` | ❌ **in attesa dell'IT (B1)** |
| 4 — Prova LIVE, gate su dati reali, auth applicativa (401/200) | ✅ fatta |
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

## Due verifiche rimaste aperte sul file dei segreti

Dopo la ricostruzione (punto 3 sopra) il file contava **10 variabili** scommentate; le
attese sono 11. Alla ripresa, per prima cosa:

```bash
sudo sed 's/=.*/=***/' /etc/camperio/camperio.env      # inventario, valori mascherati
sudo grep -c '^OAUTH2_PROXY_ALLOWED_GROUPS=..*' /etc/camperio/camperio.env   # atteso: 1
```

Attese: `ORA_USER`, `ORA_PWD`, `ORA_DSN`, `ANTHROPIC_API_KEY`,
`OAUTH2_PROXY_OIDC_ISSUER_URL`, `OAUTH2_PROXY_CLIENT_ID`, `OAUTH2_PROXY_CLIENT_SECRET`,
`OAUTH2_PROXY_COOKIE_SECRET`, `OAUTH2_PROXY_ALLOWED_GROUPS`,
`OAUTH2_PROXY_REDIRECT_URL`, `OAUTH2_PROXY_WHITELIST_DOMAIN`.
(`CAMPERIO_DATA` non serve nel file: la imposta il compose.) Se la mancante è
`REDIRECT_URL` o `WHITELIST_DOMAIN`, i valori sono nel template
`camperio.example.env`. Se fosse `ALLOWED_GROUPS`, **è bloccante**: senza, dopo il
login entra chiunque abbia un account nel tenant.

## Ripresa, quando arriva il certificato

Non si rifà nulla delle Parti 1–5: unit systemd già installate e abilitate, immagine
già costruita, segreti già compilati. La sequenza è:

**1. Installare il certificato** (runbook 3.3):

```bash
# fullchain.pem (certificato + catena intermedia) e privkey.pem in /etc/camperio/tls/
sudo chmod 600 /etc/camperio/tls/privkey.pem
grep -c "BEGIN CERTIFICATE" /etc/camperio/tls/fullchain.pem   # atteso: >= 2
```

Se stampa `1` manca la catena intermedia: tornare dall'IT prima di proseguire.

**2. Chiudere le due verifiche aperte** sul file dei segreti (sezione sopra).

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
