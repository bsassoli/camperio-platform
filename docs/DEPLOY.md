# Runbook di deploy — piattaforma Camperio

Questo documento porta la piattaforma da zero a funzionante, **un passo alla volta**.
Ogni passo dice tre cose: **il comando da dare**, **cosa fa**, e **cosa devi vedere**
se è andato bene. Non serve fare deploy tutti i giorni per seguirlo.

**Dove si lavora:** tutto sulla **VM Elmec** (`app-ai.camperiosim.com`). Non c'è un
ambiente di prova separato: si collauda sulla macchina di produzione *prima* che sia
raggiungibile da chiunque.

> **⚠ La regola che sostituisce l'ambiente di prova.** `nginx` è l'**unico** servizio
> che pubblica una porta (la 443); `comitato` e `oauth2-proxy` non ne espongono nessuna.
> Finché non alzi nginx, la VM non è raggiungibile da nessuno e si comporta a tutti gli
> effetti da ambiente di test. Le Parti 2–5 si fanno quindi **a stack parziale**; nginx
> si alza per ultimo, nella Parte 7, e solo a checklist verde.
>
> Il corollario pratico: **fino alla Parte 7 non dare mai `docker compose up -d` nudo.**
> Senza il nome di un servizio alza tutto, nginx incluso, e apre la 443. Nei comandi qui
> sotto i servizi sono sempre nominati esplicitamente (`comitato`, e dal 6.1 anche
> `oauth2-proxy`) — non è pedanteria.

**Cosa gira, in due righe** (architettura: ADR 0010 nel repo di pianificazione):
tre container orchestrati da Docker Compose — l'app `comitato` (Flask), `oauth2-proxy`
(il login aziendale Entra ID) e `nginx` (l'unica porta esposta, la 443) — più i job
schedulati, lanciati non da Docker ma da **timer systemd dell'host** che eseguono
`docker compose run`. I segreti (credenziali Oracle, certificato TLS, chiavi) **non
sono nel repo**: li inserisce Bernardino a mano.

## Cosa serve avere in mano, e quando

| Cosa | Da chi | Serve a partire da |
|---|---|---|
| Accesso SSH alla VM (da VPN) | IT | Parte 1 |
| Niente altro | — | Parte 2 (la prova DEMO gira senza alcun segreto) |
| Utenza Oracle di servizio + service name del DSN | DBA (richiesta A1) | Parte 3 |
| App registration Entra (client id/secret, tenant) | IT (richiesta B2) | Parte 3 |
| Chiave API Anthropic | Bernardino | Parte 3 |
| Certificato AD CS per `app-ai.camperiosim.com` | IT (richiesta B1) | Parte 7 (serve solo a nginx) |

Le Parti 2–5 si possono fare **senza il certificato**: se l'IT è in ritardo su B1, non
sei bloccato — arrivi fino alla checklist e ti fermi lì.

---

## Parte 1 — Preparare la VM

### 1.1 Collegarsi

Dalla rete aziendale o in VPN:

```bash
ssh <utente>@app-ai.camperiosim.com
```

**Cosa fa:** apre la sessione sulla VM. Tutti i comandi di questo runbook si danno lì,
salvo dove scritto esplicitamente il contrario (un solo caso: il tunnel del passo 4.2,
che si lancia dal tuo PC).

**Risultato atteso:** un prompt Linux sulla VM.

### 1.2 Verificare Docker e l'utente di servizio

```bash
docker --version && docker compose version
id -nG | tr ' ' '\n' | grep -x docker
```

**Cosa fa:** il primo comando verifica Docker Engine e Compose (serve **≥ 2.24**), già
presenti sulla VM e verificati dai probe. Il secondo controlla che il tuo utente sia nel
gruppo `docker`: è la ragione per cui potrai dare i comandi `docker ...` senza `sudo`, e
per cui più avanti il file dei segreti sarà leggibile a `root:docker` con permessi `640`.

**Risultato atteso:** le due versioni, e `docker` stampato dal secondo comando. Se il
secondo non stampa nulla: `sudo usermod -aG docker $USER`, poi esci e rientra in SSH
(i gruppi si rileggono al login).

```bash
docker run --rm hello-world
```

stampa "Hello from Docker!".

### 1.3 Creare la deploy key per GitHub

Il repo è privato e si clona **con una chiave SSH dedicata in sola lettura** — mai con
token personali: se la macchina viene compromessa, la chiave dà accesso a un solo repo
e non può scriverci.

```bash
ssh-keygen -t ed25519 -C "camperio-deploy-vm" -f ~/.ssh/camperio_deploy -N ""
cat ~/.ssh/camperio_deploy.pub
```

**Cosa fa:** genera una coppia di chiavi; `cat` stampa la parte **pubblica** (una riga
che inizia con `ssh-ed25519`). Copiala.

Ora su GitHub (dal browser): repo `bsassoli/camperio-platform` → **Settings** →
**Deploy keys** → **Add deploy key** → incolla la chiave, dalle un titolo (es.
"VM app-ai"), **lascia deselezionato "Allow write access"** → Add key.

> Una chiave per macchina: le chiavi non si copiano tra host. Se un domani la VM va
> dismessa, si revoca la sua e basta.

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

### 1.4 Clonare il repo in `/opt/camperio`

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
l'app su `127.0.0.1:5001` (solo il loopback della VM: nulla di raggiungibile dalla
rete). Parte **solo** il container `comitato` — niente nginx, niente oauth2-proxy: per
questo non servono certificato né Entra.

**Risultato atteso:** `docker compose ps` mostra `comitato` con stato `running`.
Controprova che non hai esposto niente:

```bash
ss -tlnp | grep -E ':(443|5001)'
```

deve mostrare al massimo una riga, su `127.0.0.1:5001`. Se compare `0.0.0.0:443` o
`*:443`, hai alzato nginx per sbaglio: `docker compose stop nginx` e rileggi la regola
in cima al documento.

### 2.3 Verificare che sia davvero DEMO

```bash
curl -s http://127.0.0.1:5001/ | grep "DEMO"
```

**Risultato atteso:** una o più righe di HTML col banner DEMO. Se `grep` non trova
nulla, l'app è partita LIVE (v. avviso sopra) o non è partita: guarda
`docker compose logs comitato`.

### 2.4 Far girare i test di hardening

Sono i test che dimostrano che l'app rifiuta le richieste senza identità, che non
accetta upload di estensioni arbitrarie e che non riflette HTML. Sono una voce della
checklist di esposizione (Parte 6), quindi conviene vederli verdi subito.

```bash
cd /opt/camperio/deploy
docker compose run --rm -T \
  -v /opt/camperio/apps/comitato/tests:/opt/camperio/apps/comitato/tests:ro \
  comitato sh -c "pip install --no-cache-dir pytest >/dev/null && python -m pytest tests/test_hardening.py"
```

**Cosa fa:** l'immagine di produzione **non contiene pytest** e `.dockerignore` esclude
`tests/` dal build — entrambe scelte volute, non si spedisce l'attrezzatura di test in
produzione. Quindi si monta la cartella dei test in sola lettura in un container
usa-e-getta (`--rm`) e si installa pytest solo lì dentro, per la durata del comando.

**Risultato atteso:** l'ultima riga di pytest dice `N passed`.

> Se la VM non raggiunge PyPI l'installazione fallisce. Alternativa senza rete:
> `python3 -m venv /tmp/pytest-venv && /tmp/pytest-venv/bin/pip install pytest flask
> python-docx openpyxl`, poi lanciare i test con
> `PYTHONPATH=/opt/camperio/core:/opt/camperio/apps/comitato`. È più lavoro: prova
> prima la via del container.

### 2.5 Spegnere

```bash
docker compose -f docker-compose.yml -f compose.demo.yml down
```

---

## Parte 3 — Segreti e certificato (manuale)

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
| `OAUTH2_PROXY_COOKIE_SECRET` | generane uno: `openssl rand -base64 32 \| tr '+/' '-_'` | tu, adesso |
| `OAUTH2_PROXY_ALLOWED_GROUPS` | l'objectId del gruppo Entra abilitato | IT (B2) |
| `OAUTH2_PROXY_REDIRECT_URL` / `WHITELIST_DOMAIN` | già precompilati per `app-ai.camperiosim.com` | — |

> **⚠ `OAUTH2_PROXY_ALLOWED_GROUPS` è obbligatorio.** Senza, *qualunque* account del
> tenant Camperio entra nell'app dopo il login. È la prima voce della checklist di
> esposizione (Parte 6) e il primo dei controlli pre-flight (6.1).

> **⚠ Il `tr` sul cookie secret non è un vezzo.** oauth2-proxy decodifica quel valore
> come base64 **URL-safe** e pretende 16, 24 o 32 byte decodificati. `openssl rand
> -base64 32` da solo produce base64 *standard*, che può contenere `+` e `/`: la
> decodifica fallisce, oauth2-proxy prende la stringa alla lettera e muore in
> crash-loop con
>
> ```
> cookie_secret must be 16, 24, or 32 bytes to create an AES cipher, but is 44 bytes
> ```
>
> Il `tr '+/' '-_'` converte all'alfabeto URL-safe a parità di entropia. Incolla il
> valore **senza virgolette**. Se cambi questo secret a stack avviato, tutte le
> sessioni esistenti decadono e gli utenti rifanno il login — qui non ce ne sono
> ancora, quindi è il momento buono per sbagliarlo.

### 3.3 Installare il certificato TLS

Serve **solo a nginx**, cioè solo dalla Parte 7: le prove delle Parti 4 e 5 girano senza.

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

## Parte 4 — Prova LIVE, ancora a stack parziale

Ora che `/etc/camperio/camperio.env` è compilato, l'app deve partire in modalità LIVE e
leggere da Oracle. Nginx resta giù: niente è ancora raggiungibile dalla rete.

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
dei segreti — che ora è compilato, quindi l'app parte LIVE ma raggiungibile dal
loopback della VM per il passo 4.2.

**Contratto da conoscere:** con configurazione LIVE e Oracle irraggiungibile l'app
**deve rispondere 503** — mai ripiegare in silenzio sui dati DEMO. Se vedi dati DEMO
con gli `ORA_*` compilati, qualcosa è rotto: fermati e indaga.

### 4.2 Prova del gate su dati reali — OBBLIGATORIA prima di esporre

(Rilievo del piano 2.) Serve un browser, e sulla VM non c'è. Si apre un tunnel SSH
**dal tuo PC** (nuova finestra, la sessione sulla VM resta aperta):

```bash
ssh -N -L 5001:127.0.0.1:5001 <utente>@app-ai.camperiosim.com
```

**Cosa fa:** inoltra la porta 5001 del tuo PC alla 5001 del loopback della VM. Non apre
nulla verso la rete: il traffico passa dentro la connessione SSH, e a tunnel chiuso non
resta niente. È il sostituto pulito dell'"apri il browser sulla macchina di test".

**Risultato atteso: nessun output e nessun prompt.** La finestra resta appesa, muta —
`-N` vuol dire "non eseguire nessun comando remoto": quel silenzio *è* il tunnel aperto,
non un blocco. Se invece torna il prompt, il tunnel è caduto.

> **Prima di lanciarlo, controlla che dall'altra parte ci sia qualcuno.** Il tunnel si
> apre anche se sulla VM non ascolta nessuno, e il sintomo (browser che non risponde) non
> dice dove sia il guasto. Sulla VM `docker compose ps` deve mostrare `comitato` con
> `127.0.0.1:5001->5001/tcp` nella colonna PORTS: la porta la pubblica **solo**
> l'override `compose.demo.yml` del passo 4.1. Se hai già fatto il 4.3, o un
> `docker compose down`, il container giusto non c'è più — rilancia il 4.1
> (aggiungendo `--force-recreate` se un container `comitato` esiste già: Compose non
> ripubblica le porte su un container esistente).
>
> Diagnosi rapida, se il browser non risponde: dalla VM
> `curl -s -o /dev/null -w "%{http_code}
" http://127.0.0.1:5001/` — se risponde `000`
> il problema è sulla VM, non nel tunnel. Se invece risponde `200`, guarda la finestra
> dell'`ssh -N`: `channel N: open failed` indica il forward, il silenzio va bene.

Poi, nel browser del tuo PC: `http://127.0.0.1:5001/`. Genera la **Matrice Valutaria
del contratto reale** (endpoint `/api/preview`) e verifica che il gate di validazione
passi — o capisci *perché* non passa. Questa prova decide se la tolleranza dello 0,5%
è un presidio o un ostacolo.

**Regola assoluta:** output e log di questa prova restano sulla VM. **MAI copiare dati
reali nel repo**, e non scaricarli sul PC attraverso il tunnel se non servono.

Chiudi il tunnel (Ctrl+C nella finestra dell'`ssh -N`) appena finito.

### 4.3 Verificare l'auth con la configurazione vera

Il passo 4.1 gira con `COMITATO_AUTH=0` (è l'override demo a spegnerla). Adesso la si
prova **accesa**, com'è in produzione — sempre senza pubblicare porte:

```bash
docker compose up -d comitato      # NB: senza -f, e con il servizio nominato: nginx resta giù
docker compose exec comitato python -c "
import urllib.error as E, urllib.request as R
def stato(h):
    try: return R.urlopen(R.Request('http://127.0.0.1:5001/', headers=h)).status
    except E.HTTPError as x: return x.code
print('senza header:', stato({}), '(atteso 401) | con header:',
      stato({'X-Auth-Request-User': 'bsassoli@camperiosim.com'}), '(atteso 200)')"
```

**Cosa fa:** senza l'override, `comitato` parte con `COMITATO_AUTH=1` e **non pubblica
alcuna porta** — per interrogarlo si entra nel container. Si usa urllib perché
`python:3.13-slim` non ha `curl`.

**Risultato atteso:** `senza header: 401 ... | con header: 200 ...`. Se la prima è 200,
l'auth applicativa non è attiva: **non proseguire**, l'app si fiderebbe di chiunque
arrivi a nginx.

### 4.4 Spegnere

```bash
docker compose down
```

---

## Parte 5 — Unit systemd: installarle senza avviarle

Le unit non hanno un giro di prova da un'altra parte: qui è dove debuttano. Si
verificano a freddo e si prova il comando che eseguono, prima di consegnarle a systemd.

### 5.1 Verificare le unit a freddo

```bash
cd /opt/camperio
systemd-analyze verify deploy/systemd/*
```

**Cosa fa:** controlla sintassi, direttive e riferimenti delle unit senza installarle
né eseguirle.

**Risultato atteso:** **nessun output**. Ogni riga stampata è un difetto da sistemare
prima di andare avanti.

### 5.2 Provare il job ETF come comando

```bash
cd /opt/camperio/deploy
docker compose run --rm -T comitato python scarica_etf.py
```

**Cosa fa:** è esattamente l'`ExecStart` di `camperio-scarica-etf.service`, lanciato a
mano. Scarica i 9 CSV holdings ETF da iShares nel volume dati. Provandolo qui, se più
avanti l'unit fallisce sai che il problema è nel wiring systemd e non nel job.

**Risultato atteso:** termina senza errori; i CSV sono nel volume.

### 5.3 Installare le unit — senza avviarle

```bash
sudo cp /opt/camperio/deploy/systemd/*.service /opt/camperio/deploy/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable camperio.service      # enable, NON --now
systemctl cat camperio.service              # rilettura: WorkingDirectory ed ExecStart corretti
```

**Cosa fanno le unit:**
- `camperio.service` — porta su l'intero stack Compose (app + oauth2-proxy + nginx) al
  boot della VM, e lo spegne allo stop.
- `camperio-scarica-etf.timer` + `.service` — lancia il job di download ETF ogni
  **giovedì alle 11:00** (`Persistent=true`: se la VM era spenta a quell'ora, il run
  perso parte al riavvio). Dipende da `docker.service`, non dallo stack: usa
  `docker compose run`, che si crea il suo container, quindi lanciarlo **non** alza
  nginx.

> **⚠ `enable`, non `enable --now`.** `camperio.service` esegue `docker compose up -d`:
> avviarlo adesso alzerebbe nginx e aprirebbe la 443 prima della checklist. `enable` lo
> registra per il boot senza farlo partire ora. Il timer non si abilita affatto, per
> ora: lo si accende in 7.3, quando lo stack è legittimamente su.

**Risultato atteso:** `enable` conferma la creazione del symlink; `systemctl cat`
mostra `WorkingDirectory=/opt/camperio/deploy`. `systemctl is-active camperio` deve
ancora rispondere `inactive`.

---

## Parte 6 — Checklist pre-esposizione (da spuntare PRIMA di alzare nginx)

- [ ] `OAUTH2_PROXY_ALLOWED_GROUPS` valorizzato (senza, entra chiunque nel tenant)
- [ ] certificato in `/etc/camperio/tls`: `fullchain.pem` con la catena intermedia (Parte 3.3), `privkey.pem` a 600
- [ ] `COMITATO_AUTH=1` effettivo: senza header → 401 (Parte 4.3)
- [ ] test di hardening verdi (Parte 2.4)
- [ ] gate provato su snapshot reale (Parte 4.2)
- [ ] `/etc/camperio/camperio.env` root:docker 640; niente segreti nei log (`docker compose logs | grep -i secret` vuoto)
- [ ] `ss -tlnp` non mostra ancora nulla sulla 443

### 6.1 Pre-flight: le due cose ancora sbagliabili, controllate a 443 chiusa

Fra l'apertura della 443 e la prova col primo utente reale c'è una finestra in cui un
errore di configurazione **è già esposto**. Questi due controlli la riducono alla sola
verifica che richiede per forza un browser (il 403 fuori gruppo, passo 7.2). Nessuno dei
due pubblica porte: `comitato` e `oauth2-proxy` non ne espongono nessuna, e `compose run`
non pubblica nulla se non glielo chiedi.

```bash
cd /opt/camperio/deploy
docker compose up -d comitato oauth2-proxy
docker compose ps
docker compose run --rm --no-deps --entrypoint nginx nginx -t
```

**Cosa fa:** valida la configurazione di nginx e verifica che i due file del certificato
esistano e siano leggibili. È l'errore più probabile al primo avvio, e senza questo
controllo si manifesterebbe come nginx in crash-loop a 443 già aperta.

**Perché prima si alzano gli altri due.** nginx risolve gli hostname degli upstream
**all'avvio**, non alla prima richiesta: se `oauth2-proxy` non gira, il suo nome non
esiste nel DNS di Compose e `nginx -t` si ferma lì, prima ancora di guardare il
certificato. È il senso di questo errore, se lo vedi:

```
[emerg] host not found in upstream "oauth2-proxy" in /etc/nginx/nginx.conf:25
```

**Risultato atteso:** `docker compose ps` mostra `comitato` e `oauth2-proxy` con stato
`running` — e `nginx -t` risponde `syntax is ok` / `test is successful`.

> Se `oauth2-proxy` è in `restarting`, `nginx -t` fallisce allo stesso modo: il container
> flappa e il nome DNS sparisce fra un tentativo e l'altro. La causa vera è nei log
> (`docker compose logs oauth2-proxy`) — di norma `OAUTH2_PROXY_OIDC_ISSUER_URL` o le
> credenziali dell'app registration. È il primo punto del runbook in cui quell'errore
> può emergere, ed emerge a 443 ancora chiusa: sistemalo qui.

I due container restano su fino alla Parte 7 — `docker compose up -d` del passo 7.1 si
limiterà ad aggiungere nginx. L'ultima voce della checklist (`ss -tlnp` senza nulla
sulla 443) resta valida: nessuno dei due pubblica porte.

```bash
sudo grep -c '^OAUTH2_PROXY_ALLOWED_GROUPS=..*' /etc/camperio/camperio.env
```

**Cosa fa:** verifica che la riga del gruppo Entra esista, sia **scommentata** e abbia
un valore non vuoto.

**Risultato atteso:** `1`. Se stampa `0`, torna al passo 3.2: senza quel valore
l'app è aperta a tutto il tenant nel momento stesso in cui alzi nginx.

---

## Parte 7 — Accensione

Solo ora, e in quest'ordine.

### 7.1 Alzare lo stack

```bash
sudo systemctl start camperio.service
docker compose ps
ss -tlnp | grep ':443'
```

**Cosa fa:** l'unit esegue `docker compose up -d`: partono app, oauth2-proxy e nginx.
Da questo istante la 443 è aperta sulla rete.

**Risultato atteso:** i tre container `running`; `ss` mostra la 443 e **nient'altro**.

```bash
curl -k -sI https://127.0.0.1/ | grep -iE "^(HTTP|location)"
```

**Risultato atteso:** un redirect (302) con `Location:` verso `login.microsoftonline.com`.

### 7.2 Verifiche con utenti reali — prima di comunicare l'URL

Da un client in VPN, nel browser:

1. `https://app-ai.camperiosim.com/` con **il tuo utente** (nel gruppo Entra) → login
   Entra → l'app si apre col tuo utente in alto.
2. Lo stesso URL con un utente **fuori** dal gruppo → **403**. È la voce di checklist
   che non si può provare a stack chiuso: va fatta adesso, ed è la ragione per cui fra
   7.1 e qui non si passa dell'altro tempo (matrice app→gruppo, voce 3 del registro).

Altri controlli, dalla VM:

```bash
docker compose logs oauth2-proxy   # nessun errore di issuer o redirect
```

> `/output/` che risponde 403/404 finché nessun job ha ancora scritto file è **atteso**,
> non un mount rotto.

### 7.3 Accendere il job schedulato

```bash
sudo systemctl start camperio-scarica-etf.service
journalctl -u camperio-scarica-etf -n 50
sudo systemctl enable --now camperio-scarica-etf.timer
systemctl list-timers 'camperio-*'
```

**Cosa fa:** prima un test-fire esplicito dell'unit (mai lasciare che il primo run
avvenga da solo di giovedì), poi l'abilitazione del timer.

**Risultato atteso:** il journal mostra il run completo senza errori; `list-timers`
mostra il prossimo giovedì in `NEXT`.

> **⚠ `Persistent=true` può far scattare un run subito** al primo `enable --now`, se
> systemd ritiene di aver "perso" l'occorrenza precedente. È atteso, non un bug.

---

## Parte 8 — Rollback

Il vecchio mondo (il PC di Edoardo) resta intatto finché la voce corrispondente non è
migrata **e** verificata (regola del registro): tornare indietro è spegnere, non
ricostruire.

```bash
sudo systemctl disable --now camperio-scarica-etf.timer
sudo systemctl stop camperio
```

**Perché anche il timer:** il job non rialza lo stack (dipende da `docker.service`, non
da `camperio.service`), ma di giovedì continuerebbe a scaricare i CSV mentre il vecchio
mondo è tornato in carico — due sorgenti che scrivono gli stessi dati.

Nessun dato vive solo sulla VM in questa fase: `data/` si ricostruisce dagli input,
`output/` è rigenerabile.

---

## Parte 9 — Aggiornamento (nuova versione del codice)

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

> Qui `up -d` nudo è corretto: lo stack è già esposto e lo si vuole intero. È l'unico
> punto del runbook in cui la regola in cima non si applica.
