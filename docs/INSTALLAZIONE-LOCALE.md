# Installazione locale dell'app Comitato

Guida per far girare e modificare l'app Comitato sul proprio PC: Windows, Ubuntu
o macOS. Serve a chi propone modifiche al codice; il deploy sulla VM resta
descritto in `docs/DEPLOY.md` e lo fa Bernardino.

Il principio da tenere a mente: **senza le variabili `ORA_*` l'app gira in modalità
DEMO** su dati sintetici. È il modo normale di sviluppare e di provare una modifica.
Il collegamento a Oracle (LIVE) è un passo opzionale, descritto in fondo.

Le regole di lavoro (branch, test, Pull Request) sono in `CLAUDE.md` alla radice del
repo: Claude Code le legge da solo, ma vanno lette anche da chi le deve rispettare.

---

## 1. Prerequisiti

Tre programmi: **Git**, **Python 3.13 o superiore**, **Claude Code**. Docker è
opzionale (sezione 6).

### Windows 10/11

1. Git: <https://git-scm.com/download/win>, installazione con le opzioni predefinite.
   Include *Git Bash*, ma qui si usa **PowerShell**.
2. Python: <https://www.python.org/downloads/windows/>, versione 3.13.x.
   Nell'installer spuntare **"Add python.exe to PATH"** prima di premere Install.
3. Claude Code: da PowerShell
   ```powershell
   irm https://claude.ai/install.ps1 | iex
   ```
   poi chiudere e riaprire PowerShell.

Verifica:
```powershell
git --version
python --version      # deve dire 3.13 o superiore
claude --version
```

### Ubuntu 22.04 / 24.04

Ubuntu 24.04 ha Python 3.12 di serie: serve il PPA deadsnakes per il 3.13.
```bash
sudo apt update && sudo apt install -y git curl software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update && sudo apt install -y python3.13 python3.13-venv
curl -fsSL https://claude.ai/install.sh | bash
```
Chiudere e riaprire il terminale. Verifica:
```bash
git --version
python3.13 --version
claude --version
```
Su Ubuntu 25.04 o successive `python3` è già 3.13: basta `sudo apt install -y git python3-venv`
e nei comandi che seguono si può usare `python3` al posto di `python3.13`.

### macOS

Con Homebrew (<https://brew.sh>):
```bash
brew install git python@3.13
curl -fsSL https://claude.ai/install.sh | bash
```
Chiudere e riaprire il Terminale. Verifica:
```bash
git --version
python3.13 --version
claude --version
```

---

## 2. Scaricare il codice

Serve l'accesso al repository GitHub `bsassoli/camperio-platform` (lo concede
Bernardino). Al primo `git clone` Git chiede di autenticarsi via browser.

Windows (PowerShell):
```powershell
cd $HOME
git clone https://github.com/bsassoli/camperio-platform.git
cd camperio-platform
```

Ubuntu e macOS:
```bash
cd ~
git clone https://github.com/bsassoli/camperio-platform.git
cd camperio-platform
```

Se il repo è già stato clonato in passato, si aggiorna invece con:
```
git switch main
git pull origin main
```

---

## 3. Ambiente Python e dipendenze

Si crea un ambiente virtuale dentro il repo (cartella `.venv`, ignorata da git) e
si installano le librerie dell'app. Va fatto una volta sola, e ripetuto solo se
`pyproject.toml` cambia.

Windows:
```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[comitato,dev]"
```

Ubuntu:
```bash
python3.13 -m venv .venv
.venv/bin/pip install -e ".[comitato,dev]"
```

macOS:
```bash
python3.13 -m venv .venv
.venv/bin/pip install -e ".[comitato,dev]"
```

Verifica che tutto sia a posto eseguendo i test dalla radice del repo:

| Sistema | Comando |
|---|---|
| Windows | `.venv\Scripts\python -m pytest` |
| Ubuntu / macOS | `.venv/bin/python -m pytest` |

Risultato atteso: l'ultima riga dice `N passed` senza `failed`. Se qualcosa fallisce
già qui, fermarsi e segnalarlo a Bernardino: non è una condizione da cui partire.

> Su Windows, se PowerShell rifiuta di eseguire script (`... is not digitally signed`),
> una volta sola: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

---

## 4. Avviare l'app (DEMO)

Windows:
```powershell
cd apps\comitato
..\..\.venv\Scripts\python app.py
```

Ubuntu / macOS:
```bash
cd apps/comitato
../../.venv/bin/python app.py
```

Aprire nel browser <http://127.0.0.1:5001>. La pagina mostra il banner **DEMO** e
il contratto sintetico `DEMO01`. Per fermare l'app: `Ctrl+C` nel terminale.

Se la porta 5001 è occupata, impostare `PORT` prima di avviare
(Windows `$env:PORT = "5002"`, Ubuntu/macOS `export PORT=5002`).

In DEMO la cartella dei file fondi è `apps/comitato/data-demo/fondi/` ed è vuota:
per il look-through degli ETF scattano le distribuzioni di ripiego. È normale.

---

## 5. Lavorare con Claude Code

Claude Code si avvia **dalla radice del repo**, così legge `CLAUDE.md` e vede tutto
il progetto:

```
cd ~/camperio-platform        # Windows: cd $HOME\camperio-platform
claude
```

Al primo avvio chiede il login con l'account Claude. Da lì in poi si descrive la
modifica in italiano. Claude Code, seguendo `CLAUDE.md`, deve:

1. creare un branch (`fix/...` o `feat/...`), mai lavorare su `main`;
2. modificare il codice **e** i test;
3. eseguire `pytest` e mostrare che è verde;
4. committare e aprire una Pull Request verso `main`.

Il ciclo consigliato per chi propone la modifica:

- tenere l'app avviata in un secondo terminale (sezione 4) e ricaricare il browser
  per vedere l'effetto: con `app.py` bisogna fermare e riavviare l'app dopo ogni
  modifica al codice Python; con Docker (sezione 6) il riavvio è automatico;
- prima di aprire la PR, chiedere esplicitamente a Claude Code di rieseguire i test;
- nella PR scrivere cosa cambia nei numeri e perché ci si aspetta quel cambiamento.

Il merge lo fa Bernardino dopo revisione. Se la PR viene rimandata con commenti,
si riprende lo stesso branch: `git switch <nome-branch>`, poi di nuovo `claude`.

Cose da **non** fare: modificare file dentro `deploy/`, la parte di autenticazione
di `app.py`, o le fixture dei test; usare Claude Desktop o altri strumenti che
scrivono nei file senza passare da git.

---

## 6. Opzionale: eseguire con Docker

Serve solo per provare la modifica **nella stessa immagine che gira sulla VM**
(Python 3.13 e driver Oracle inclusi) prima di aprire la PR. Per il lavoro
quotidiano basta la sezione 4.

Installare Docker Desktop (Windows, macOS: <https://www.docker.com/products/docker-desktop/>;
su Windows richiede WSL2, che l'installer configura) oppure Docker Engine su Ubuntu
(`sudo apt install -y docker.io docker-compose-v2` e aggiungere il proprio utente al
gruppo `docker`).

Dalla cartella `deploy/` del repo:
```
cd deploy
docker compose -f docker-compose.yml -f compose.demo.yml up --build comitato
```

L'app risponde su <http://127.0.0.1:5001>. L'override `compose.demo.yml` monta il
codice del repo dentro il container e riavvia il server a ogni salvataggio: si
modifica sul PC e si ricarica il browser, senza ricostruire l'immagine. `--build`
serve solo la prima volta o dopo una modifica al Dockerfile.

Per fermare: `Ctrl+C`, poi `docker compose -f docker-compose.yml -f compose.demo.yml down`.

> Nonostante il nome, `compose.demo.yml` non forza la modalità DEMO: se sul PC
> esiste `/etc/camperio/camperio.env` con le `ORA_*` compilate, l'app parte LIVE.

---

## 7. Opzionale: collegamento a Oracle (LIVE)

Da fare solo se serve vedere i numeri reali e solo con l'accordo di Bernardino e
del DBA. Il PC deve raggiungere il database (rete aziendale o VPN).

1. Installare il driver, che non è tra le dipendenze standard:
   - Windows: `.venv\Scripts\pip install "oracledb>=2.0"`
   - Ubuntu/macOS: `.venv/bin/pip install "oracledb>=2.0"`
2. Impostare le variabili **nel terminale**, mai in un file dentro il repo:

   Windows (PowerShell, valgono solo per quella finestra):
   ```powershell
   $env:ORA_USER = "utenza_sola_lettura"
   $env:ORA_PWD  = "..."
   $env:ORA_DSN  = "selmora01.ad.camperiosim.com:1521/<service_name>"
   $env:CAMPERIO_DATA = "$HOME\camperio-data"
   ```
   Ubuntu/macOS:
   ```bash
   export ORA_USER="utenza_sola_lettura"
   export ORA_PWD="..."
   export ORA_DSN="selmora01.ad.camperiosim.com:1521/<service_name>"
   export CAMPERIO_DATA="$HOME/camperio-data"
   ```
3. Creare la cartella dei file fondi e scaricare i CSV iShares (serve internet):
   ```
   mkdir -p ~/camperio-data/data/fondi      # Windows: mkdir $HOME\camperio-data\data\fondi
   cd apps/comitato
   ../../.venv/bin/python scarica_etf.py    # Windows: ..\..\.venv\Scripts\python scarica_etf.py
   ```
   Senza questi file l'hedge sugli indici risulta vuoto.
4. Avviare l'app come in sezione 4 e controllare che il banner DEMO **non** compaia.
   Verifica dal terminale, sempre da `apps/comitato`:
   ```
   ../../.venv/bin/python -c "import data_layer as DL; print(DL.mode())"
   ```
   deve stampare `LIVE`.

I report prodotti in locale non sono quelli ufficiali: fanno fede quelli della VM
dopo la validazione descritta in `docs/STATO-MIGRAZIONE.md`.

---

## Problemi frequenti

| Sintomo | Causa probabile | Rimedio |
|---|---|---|
| `python` non trovato (Windows) | PATH non aggiornato | Reinstallare Python spuntando "Add to PATH", oppure usare `py -3.13` |
| `No module named flask` | venv non attivo o dipendenze non installate | Rifare la sezione 3, usare sempre il python dentro `.venv` |
| `pytest` rosso subito dopo il clone | ambiente diverso dal previsto | Segnalare a Bernardino con l'output completo |
| Pagina senza banner DEMO ma dati strani | `ORA_*` impostate a metà | Controllare le tre variabili; per tornare in DEMO chiudere il terminale |
| Porta 5001 occupata | altra istanza dell'app o Docker attivo | Fermare l'altra istanza o cambiare `PORT` |
| Claude Code lavora su `main` | avviato fuori dal repo, non legge `CLAUDE.md` | Avviarlo dalla radice del repo |
