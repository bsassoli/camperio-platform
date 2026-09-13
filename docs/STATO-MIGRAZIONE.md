# Stato migrazione — punto fermo dell'11 settembre 2026

**Lo stack è acceso.** L'11 settembre 2026 la Parte 7.1 del runbook (`DEPLOY.md`) è
andata a buon fine: `camperio.service` avviato, i tre container su, la 443 aperta, e il
login Entra con un utente **dentro** il gruppo abilitato apre l'app Comitato. La VM
non è più spenta: da qui in avanti "tornare indietro" è la Parte 8 (`systemctl stop
camperio`), non ricostruire.

Il TLS è quello della **CA interna provvisoria** (3.3 B), non ancora il certificato AD
CS della richiesta B1: ogni client che accede deve avere `ca.crt` installato.

## Cosa resta per chiudere l'app Comitato

In ordine, prima di comunicare l'URL ai colleghi:

- [ ] **7.2 — utente fuori dal gruppo Entra → 403.** Unica voce della checklist non
      provabile a stack chiuso; serve un collega non nel gruppo che apra il sito.
- [ ] **Log oauth2-proxy puliti**: `docker compose logs oauth2-proxy`, nessun errore di
      issuer o redirect.
- [ ] **Parte 4 in LIVE**, se non rifatta dopo l'inserimento di `ORA_USER`/`ORA_PWD`:
      `DL.mode()` → `LIVE`, gate su dati reali (4.2), auth 401/200 (4.3). Al 2 settembre
      risultava ancora da rifare.
- [ ] **7.3 — job ETF**: test-fire manuale dell'unit, poi `enable --now` del timer e
      verifica del prossimo giovedì in `list-timers`.
- [ ] **Certificato AD CS (B1)**: quando l'IT lo consegna, sovrascrivere i due file in
      `/etc/camperio/tls/` e ricaricare nginx (3.3 A); da quel momento `ca.crt` sui
      client non serve più.
- [ ] **Annotare nome e objectId del gruppo Entra** usato in `OAUTH2_PROXY_ALLOWED_GROUPS`
      (in `SECRETS.md`): oggi il valore c'è sulla VM ma non è tracciato in nessun documento.

Chiuse queste, la voce `apps/comitato` del registro di migrazione (repo
`migrate-camperio`) passa a "migrata e verificata" e il vecchio mondo corrispondente si
spegne (regola anti-drift).

## Il resto della migrazione, in breve

Nel monorepo esistono `core/` e `apps/comitato`; `jobs/` e `agent/` sono vuote. Dal
registro restano 13 job (J1–J4, J6–J9, J11–J15; J10 in standby), l'app `promotori`,
lo strumento `margini`, e le 6 skill di `agent/`. Primo candidato: **J1 iban-snapshot**,
per l'urgenza dell'output fantasma (voce 20 del registro). Prerequisiti ancora in mano
a terzi: canale email dal server (voce 9, IT), destinazione backup (voce 15, IT),
ricensimento delle skill non versionate (voce 19, Edoardo). Postgres (ADR 0010) non è
ancora nel compose: serve per lo storico di J3 e per `agent_runs`.

---
