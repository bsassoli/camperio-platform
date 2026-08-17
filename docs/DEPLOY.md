# Runbook di deploy — piattaforma Camperio

Sequenza: prima **WSL Ubuntu** (test, Oracle read-only raggiungibile), poi **VM Elmec**
(`app-ai.camperiosim.com`). I segreti e il certificato li inserisce Bernardino a mano:
nel repo esistono solo placeholder. Architettura: ADR 0010 (container Compose + timer
systemd dell'host); perimetro nginx: spec §2.

## 0 · Prerequisiti

- Docker Engine + Compose ≥ 2.24 (sulla VM: già verificati dai probe).
- Il repo in `/opt/camperio` via deploy key SSH read-only (mai token personali):
  `git clone git@github.com:bsassoli/camperio-platform.git /opt/camperio`
- Un utente di servizio non-root nel gruppo `docker` per operare lo stack.

## 1 · Segreti e certificato (manuale, per ambiente)

    sudo mkdir -p /etc/camperio/tls
    sudo cp camperio.example.env /etc/camperio/camperio.env
    sudo chmod 600 /etc/camperio/camperio.env && sudo chown root:root /etc/camperio/camperio.env
    sudo $EDITOR /etc/camperio/camperio.env    # ORA_*, OAUTH2_PROXY_*, ANTHROPIC_API_KEY

- `ORA_DSN`: `selmora01.ad.camperiosim.com:1521/<service_name>` (service name: richiesta DBA, punto A1).
- `OAUTH2_PROXY_*`: dall'app registration Entra (richiesta IT, punto B2); cookie secret: `openssl rand -base64 32`.
- Certificato AD CS per `app-ai.camperiosim.com` (richiesta IT, punto B1) in
  `/etc/camperio/tls/fullchain.pem` + `privkey.pem` (chiave `chmod 600`).
- Consegna dei valori: mai per email — Passwordstate o di persona (docs/SECRETS.md).

## 2 · Prova su WSL (senza esporre nulla)

    cd /opt/camperio/deploy
    docker compose build
    docker compose -f docker-compose.yml -f compose.demo.yml up -d comitato   # DEMO
    curl -s http://127.0.0.1:5001/ | grep "DEMO"
    docker compose -f docker-compose.yml -f compose.demo.yml down

Poi con `/etc/camperio/camperio.env` compilato (LIVE):

    docker compose up -d comitato
    docker compose exec comitato python -c "import data_layer as DL; print(DL.mode())"   # LIVE
    # con config LIVE e Oracle irraggiungibile l'app DEVE dare 503, mai dati DEMO.

**Prova del gate su dati reali (obbligatoria prima della VM, rilievo del piano 2):**
generare la Matrice Valutaria del contratto reale via `/api/preview` e verificare che il
gate passi (o capire perché no): decide se la tolleranza 0,5% è un presidio o un ostacolo.
Output e log restano su WSL — MAI copiare dati reali nel repo.

## 3 · Installazione sulla VM

    cd /opt/camperio/deploy
    docker compose build
    sudo cp systemd/*.service systemd/*.timer /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now camperio.service
    sudo systemctl enable --now camperio-scarica-etf.timer
    systemctl list-timers 'camperio-*'

Verifiche: `curl -k https://127.0.0.1/` dalla VM → redirect a `login.microsoftonline.com`;
da un client VPN, `https://app-ai.camperiosim.com/` → login Entra → app con l'utente in
alto; `docker compose logs oauth2-proxy` senza errori di issuer/redirect.

## 4 · Checklist pre-esposizione (da spuntare PRIMA di comunicare l'URL)

- [ ] `COMITATO_AUTH=1` effettivo (curl interno senza header → 401)
- [ ] test di hardening verdi (`apps/comitato/tests/test_hardening.py`)
- [ ] gate provato su snapshot reale (sezione 2)
- [ ] nessuna porta pubblicata oltre 443 (`docker compose ps`, `ss -tlnp`)
- [ ] `/etc/camperio/camperio.env` root 600; niente segreti nei log (`docker compose logs | grep -i secret` vuoto)
- [ ] gruppi Entra nel token verificati con un utente reale (matrice app→gruppo, voce 3)

## 5 · Rollback

Il vecchio mondo (PC di Edoardo) resta intatto finché la voce corrispondente non è
migrata E verificata (regola del registro): il rollback è `sudo systemctl stop camperio`
+ ripristino dell'operatività attuale. Nessun dato è solo sulla VM in questa fase:
`data/` si ricostruisce dagli input, `output/` è rigenerabile.
