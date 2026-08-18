# Runbook di deploy — piattaforma Camperio

Questo documento porta la piattaforma da zero a funzionante, **un passo alla volta**.
Ogni passo dice tre cose: **il comando da dare**, **cosa fa**, e **cosa devi vedere**
se è andato bene. Non serve fare deploy tutti i giorni per seguirlo.

**La sequenza è obbligata**: prima si prova tutto su **WSL Ubuntu** (l'ambiente di test
sul PC Windows, da cui Oracle è raggiungibile in sola lettura), e solo quando lì è tutto
verde si ripete sulla **VM Elmec** (`app-ai.camperiosim.com`, la produzione). Niente
debutta in produzione.

**Cosa gira, in due righe** (architettura: ADR 0010 nel repo di pianificazione):
tre container orchestrati da Docker Compose — l'app `comitato` (Flask), `oauth2-proxy`
(il login aziendale Entra ID) e `nginx` (l'unica porta esposta, la 443) — più i job
schedulati, lanciati non da Docker ma da **timer systemd dell'host** che eseguono
`docker compose run`. I segreti (credenziali Oracle, certificato TLS, chiavi) **non
sono nel repo**: li inserisce Bernardino a mano, ambiente per ambiente.

## Cosa serve avere in mano, e quando

| Cosa | Da chi | Serve a partire da |
|---|---|---|
| Niente | — | Parte 1 e 2 (la prova DEMO gira senza alcun segreto) |
| Utenza Oracle di servizio + service name del DSN | DBA (richiesta A1) | Parte 3 |
| App registration Entra (client id/secret, tenant) | IT (richiesta B2) | Parte 3 |
| Certificato AD CS per `app-ai.camperiosim.com` | IT (richiesta B1) | Parte 3 (solo stack completo) |
| Chiave API Anthropic | Bernardino | Parte 3 |

---

## Parte 1 — Preparare l'ambiente WSL

### 1.1 Entrare in Ubuntu

Da Windows: menu Start → digita **Ubuntu** → Invio. In alternativa, apri PowerShell
o Windows Terminal e digita `wsl`.

**Cosa fa:** apre una sessione Linux dentro Windows. Tutti i comandi di questo runbook
si danno *lì*, nel prompt Linux (riconoscibile: finisce con `$`), non in PowerShell.

**Risultato atteso:** un prompt tipo `bernardino@PCNOME:~$`. Verifica con:

```bash
lsb_release -d
```

che deve rispondere `Ubuntu ...`.

### 1.2 Attivare systemd in WSL

Prima controlla se è già attivo:

```bash
systemctl is-system-running
```

Se risponde `running` (o `degraded`), salta al passo 1.3. Se risponde con un errore
tipo "System has not been booted with systemd":

```bash
sudo nano /etc/wsl.conf
```

e aggiungi (o completa) queste due righe:

```ini
[boot]
systemd=true
```

Salva (Ctrl+O, Invio) ed esci (Ctrl+X). Poi **da PowerShell** (finestra Windows):

```powershell
wsl --shutdown
```

e riapri Ubuntu come al passo 1.1.

**Cosa fa:** WSL di default non avvia systemd, il gestore dei servizi di Linux. A noi
serve perché i job schedulati usano timer systemd, e vanno provati qui prima della VM.

**Risultato atteso:** riaperta la sessione, `systemctl is-system-running` risponde
`running` o `degraded` (entrambi vanno bene).

### 1.3 Installare Docker

Controlla se c'è già:

```bash
docker --version && docker compose version
```

Se entrambi rispondono e Compose è **≥ 2.24**, salta al passo 1.4. Altrimenti:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

Poi chiudi la sessione (`exit`) e rientra in Ubuntu (passo 1.1).

**Cosa fa:** il primo comando installa Docker Engine e Compose con lo script ufficiale.
Il secondo aggiunge il tuo utente al gruppo `docker`, così potrai dare i comandi
`docker ...` senza `sudo` — serve rientrare perché i gruppi si rileggono al login.

**Risultato atteso:**

```bash
docker run --rm hello-world
```

stampa "Hello from Docker!".

> Sulla VM questo passo non servirà: Docker è già presente e verificato dai probe.

### 1.4 Creare la deploy key per GitHub

Il repo è privato e si clona **con una chiave SSH dedicata in sola lettura** — mai con
token personali: se la macchina viene compromessa, la chiave dà accesso a un solo repo
e non può scriverci.

```bash
ssh-keygen -t ed25519 -C "camperio-deploy-wsl" -f ~/.ssh/camperio_deploy -N ""
cat ~/.ssh/camperio_deploy.pub
```

**Cosa fa:** genera una coppia di chiavi; `cat` stampa la parte **pubblica** (una riga
che inizia con `ssh-ed25519`). Copiala.

Ora su GitHub (dal browser): repo `bsassoli/camperio-platform` → **Settings** →
**Deploy keys** → **Add deploy key** → incolla la chiave, dalle un titolo (es.
"WSL Bernardino"), **lascia deselezionato "Allow write access"** → Add key.

Poi di' a SSH di usare quella chiave per GitHub:

```bash
cat >> ~/.ssh/config <<'EOF'
Host github.com
  IdentityFile ~/.ssh/camperio_deploy
  IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config
```

**Risultato atteso:**

```bash
ssh -T git@github.com
```

risponde "Hi bsassoli/camperio-platform! You've successfully authenticated…".

### 1.5 Clonare il repo in `/opt/camperio`

```bash
sudo mkdir -p /opt/camperio
sudo chown $USER: /opt/camperio
git clone git@github.com:bsassoli/camperio-platform.git /opt/camperio
```

**Cosa fa:** crea la cartella standard di installazione (`/opt/camperio` è il percorso
che le unit systemd si aspettano — non cambiarlo), te ne dà la proprietà, e scarica
il codice.

**Risultato atteso:** `ls /opt/camperio` mostra `apps core deploy docs jobs ...`.

---

## Parte 2 — Prova DEMO (senza nessun segreto)

La piattaforma ha un contratto: **senza variabili `ORA_*` gira in modalità DEMO**, su
dati sintetici. Questa prova dimostra che immagine e stack funzionano *prima* di
toccare credenziali vere.

> **⚠ Ordine importante**: fai questa prova **prima** di creare
> `/etc/camperio/camperio.env` (Parte 3). Se il file esiste già con gli `ORA_*`
> compilati, l'app parte LIVE e il controllo DEMO qui sotto fallisce — non è un bug,
> è il contratto. (In tal caso: rinomina temporaneamente il file.)

### 2.1 Costruire l'immagine

```bash
cd /opt/camperio/deploy
docker compose build
```

**Cosa fa:** costruisce l'immagine Docker con dentro `core/` e l'app Comitato. La
prima volta scarica l'immagine base: qualche minuto.

**Risultato atteso:** termina senza errori (ultima riga con `Built` / `naming to ...`).

### 2.2 Avviare la sola app in DEMO

```bash
docker compose -f docker-compose.yml -f compose.demo.yml up -d comitato
```

**Cosa fa:** i due `-f` sommano la configurazione base e l'override demo, che pubblica
l'app su `127.0.0.1:5001` (solo localhost, nulla di esposto). Parte **solo** il
container `comitato` — niente nginx, niente oauth2-proxy: per questo non servono
certificato né Entra.

**Risultato atteso:** `docker compose ps` mostra `comitato` con stato `running`.

### 2.3 Verificare che sia davvero DEMO

```bash
curl -s http://127.0.0.1:5001/ | grep "DEMO"
```

**Risultato atteso:** una o più righe di HTML col banner DEMO. Se `grep` non trova
nulla, l'app è partita LIVE (v. avviso sopra) o non è partita: guarda
`docker compose logs comitato`.

### 2.4 Spegnere

```bash
docker compose -f docker-compose.yml -f compose.demo.yml down
```

---

## Parte 3 — Segreti e certificato (manuale, per ambiente)

Ogni ambiente (WSL, poi VM) ha i **suoi** valori: non si copiano da uno all'altro.
Consegna dei valori: **mai per email** — Passwordstate o di persona (v. `docs/SECRETS.md`).

### 3.1 Creare il file dei segreti

```bash
sudo mkdir -p /etc/camperio/tls
sudo cp /opt/camperio/camperio.example.env /etc/camperio/camperio.env
sudo chown root:docker /etc/camperio/camperio.env
sudo chmod 640 /etc/camperio/camperio.env
```

**Cosa fa:** copia il template (che contiene solo placeholder commentati) nel percorso
che i compose file si aspettano. Permessi `root:docker` + `640`: il proprietario è
root, ma chi sta nel gruppo `docker` può *leggere* il file — così l'operatore lancia
`docker compose up` senza `sudo`, e nessun altro utente vede i segreti.

### 3.2 Compilare i valori

```bash
sudo nano /etc/camperio/camperio.env
```

Scommenta e compila, riga per riga:

| Variabile | Cosa metterci | Da dove viene |
|---|---|---|
| `ORA_USER` / `ORA_PWD` | l'utenza Oracle di servizio, **sola lettura** | DBA (A1) |
| `ORA_DSN` | `selmora01.ad.camperiosim.com:1521/<service_name>` | service name dal DBA (A1) |
| `CAMPERIO_DATA` | `/var/lib/camperio` | fisso |
| `ANTHROPIC_API_KEY` | la chiave API | Bernardino |
| `OAUTH2_PROXY_OIDC_ISSUER_URL` | `https://login.microsoftonline.com/<TENANT_ID>/v2.0` | tenant id dall'IT (B2) |
| `OAUTH2_PROXY_CLIENT_ID` / `CLIENT_SECRET` | dall'app registration Entra | IT (B2) |
| `OAUTH2_PROXY_COOKIE_SECRET` | generane uno: `openssl rand -base64 32` | tu, adesso |
| `OAUTH2_PROXY_ALLOWED_GROUPS` | l'objectId del gruppo Entra abilitato | IT (B2) |
| `OAUTH2_PROXY_REDIRECT_URL` / `WHITELIST_DOMAIN` | già precompilati per `app-ai.camperiosim.com` | — |

> **⚠ `OAUTH2_PROXY_ALLOWED_GROUPS` è obbligatorio.** Senza, *qualunque* account del
> tenant Camperio entra nell'app dopo il login. È la prima voce della checklist di
> esposizione (Parte 6).

### 3.3 Installare il certificato TLS

Serve solo per lo stack completo con nginx (VM, o prova completa su WSL) — la prova
LIVE della Parte 4 non lo richiede.

L'IT consegna il certificato AD CS per `app-ai.camperiosim.com` (richiesta B1). Vanno
messi due file in `/etc/camperio/tls/`:

- `fullchain.pem` — il certificato **più la catena intermedia**
- `privkey.pem` — la chiave privata, poi `sudo chmod 600 /etc/camperio/tls/privkey.pem`

Se l'IT consegna un file `.pfx` unico, convertilo:

```bash
openssl pkcs12 -in cert.pfx -out fullchain.pem -nokeys -clcerts
openssl pkcs12 -in cert.pfx -out privkey.pem -nocerts -nodes
```

**Verifica che la catena ci sia** (deve stampare almeno 2):

```bash
grep -c "BEGIN CERTIFICATE" fullchain.pem
```

Se stampa `1`, dentro c'è solo il certificato foglia: chiedi all'IT anche l'intermedio.

---

## Parte 4 — Prova LIVE su WSL

Ora che `/etc/camperio/camperio.env` è compilato, l'app deve partire in modalità LIVE
e leggere da Oracle (WSL raggiunge Oracle in sola lettura via rete aziendale).

### 4.1 Avviare e verificare la modalità

```bash
cd /opt/camperio/deploy
docker compose -f docker-compose.yml -f compose.demo.yml up -d comitato
docker compose exec comitato python -c "import data_layer as DL; print(DL.mode())"
```

**Risultato atteso:** stampa `LIVE`.

**Perché di nuovo l'override "demo"?** Nonostante il nome, quel file non forza la
modalità DEMO: si limita a pubblicare l'app su `127.0.0.1:5001` e a spegnere l'auth
per la prova locale. DEMO o LIVE lo decide solo la presenza degli `ORA_*` nel file
dei segreti — che ora è compilato, quindi l'app parte LIVE ma raggiungibile da
localhost per il passo 4.2.

**Contratto da conoscere:** con configurazione LIVE e Oracle irraggiungibile l'app
**deve rispondere 503** — mai ripiegare in silenzio sui dati DEMO. Se vedi dati DEMO
con gli `ORA_*` compilati, qualcosa è rotto: fermati e indaga.

### 4.2 Prova del gate su dati reali — OBBLIGATORIA prima della VM

(Rilievo del piano 2.) Con l'app su in LIVE (passo 4.1), apri
`http://127.0.0.1:5001/` dal browser di Windows, genera la **Matrice Valutaria del
contratto reale** (endpoint `/api/preview`) e verifica che il gate di validazione
passi — o capisci *perché* non passa. Questa prova decide se la tolleranza dello
0,5% è un presidio o un ostacolo.

**Regola assoluta:** output e log di questa prova restano su WSL. **MAI copiare dati
reali nel repo.**

### 4.3 Verificare le unit systemd (su WSL, prima che tocchino la VM)

```bash
systemd-analyze verify /opt/camperio/deploy/systemd/*
```

**Cosa fa:** controlla sintassi e riferimenti delle unit. Nessun output = tutto bene.
Le unit non devono debuttare in produzione: volendo si possono anche installare e
provare qui (stessi comandi della Parte 5) e rimuovere a prova finita.

---

## Parte 5 — Installazione sulla VM

Collegati alla VM (solo da VPN):

```bash
ssh <utente>@app-ai.camperiosim.com
```

Sulla VM Docker c'è già (verificato dai probe). Ripeti **sulla VM**:

1. **Parte 1.4–1.5** — deploy key *nuova* (es. `camperio-deploy-vm`: le chiavi non si
   copiano tra macchine) e clone in `/opt/camperio`.
2. **Parte 2** — la prova DEMO anche qui, *prima* dei segreti: 5 minuti che confermano
   l'immagine.
3. **Parte 3** — segreti e certificato con i valori di produzione.

### 5.1 Costruire e installare le unit

```bash
cd /opt/camperio/deploy
docker compose build
sudo cp systemd/*.service systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
```

**Cosa fanno le unit:**
- `camperio.service` — porta su l'intero stack Compose (app + oauth2-proxy + nginx)
  al boot della VM, e lo spegne allo stop.
- `camperio-scarica-etf.timer` + `.service` — lancia il job di download ETF ogni
  **giovedì alle 11:00** (`Persistent=true`: se la VM era spenta a quell'ora, il run
  perso parte al riavvio).

### 5.2 Abilitare e avviare

```bash
sudo systemctl enable --now camperio.service
sudo systemctl enable --now camperio-scarica-etf.timer
systemctl list-timers 'camperio-*'
```

**Risultato atteso:** `list-timers` mostra il timer con il prossimo giovedì in `NEXT`.

> **⚠ `Persistent=true` può far scattare un run subito** al primo `enable`, se systemd
> ritiene di aver "perso" l'occorrenza precedente. È atteso, non un bug.

### 5.3 Test-fire del job (mai lasciare che il primo run avvenga da solo di giovedì)

```bash
sudo systemctl start camperio-scarica-etf.service
journalctl -u camperio-scarica-etf -n 50
```

**Risultato atteso:** il log mostra il run completo senza errori.

### 5.4 Verifiche dello stack

Dalla VM stessa:

```bash
curl -k -sI https://127.0.0.1/ | grep -iE "^(HTTP|location)"
```

**Risultato atteso:** un redirect (302) con `Location:` verso
`login.microsoftonline.com`.

Da un client in VPN, nel browser: `https://app-ai.camperiosim.com/` → login Entra →
l'app si apre con il tuo utente in alto.

Altri controlli:

```bash
docker compose logs oauth2-proxy   # nessun errore di issuer o redirect
```

> `/output/` che risponde 403/404 finché nessun job ha ancora scritto file è **atteso**,
> non un mount rotto.

---

## Parte 6 — Checklist pre-esposizione (da spuntare PRIMA di comunicare l'URL)

- [ ] `OAUTH2_PROXY_ALLOWED_GROUPS` valorizzato; verificato che un utente fuori gruppo riceve 403
- [ ] `COMITATO_AUTH=1` effettivo (curl interno senza header → 401)
- [ ] test di hardening verdi — sull'host di sviluppo/WSL: `.venv/bin/python -m pytest apps/comitato/tests/test_hardening.py` (l'immagine non contiene pytest)
- [ ] gate provato su snapshot reale (Parte 4.2)
- [ ] nessuna porta pubblicata oltre 443 (`docker compose ps`, `ss -tlnp`)
- [ ] `/etc/camperio/camperio.env` root:docker 640; niente segreti nei log (`docker compose logs | grep -i secret` vuoto)
- [ ] gruppi Entra nel token verificati con un utente reale (matrice app→gruppo, voce 3 del registro)

---

## Parte 7 — Rollback

Il vecchio mondo (il PC di Edoardo) resta intatto finché la voce corrispondente non è
migrata **e** verificata (regola del registro): tornare indietro è spegnere, non
ricostruire.

```bash
sudo systemctl disable --now camperio-scarica-etf.timer
sudo systemctl stop camperio
```

**Perché anche il timer:** se fermi solo `camperio.service`, il run di giovedì del
timer rialza lo stack da solo.

Nessun dato vive solo sulla VM in questa fase: `data/` si ricostruisce dagli input,
`output/` è rigenerabile.

---

## Parte 8 — Aggiornamento (nuova versione del codice)

```bash
cd /opt/camperio
git pull                                  # scarica la nuova versione
cd deploy
docker compose build                      # ricostruisce l'immagine col nuovo codice
docker compose up -d --force-recreate     # ricrea TUTTI i container
curl -k -s https://127.0.0.1/ -o /dev/null -w "%{http_code}\n"   # smoke test: atteso 302
```

**Perché `--force-recreate`:** ricrea anche i container la cui configurazione non è
cambiata — serve in particolare a nginx, che altrimenti continuerebbe a puntare al
vecchio container dell'app.
