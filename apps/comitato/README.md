# apps/comitato — Comitato Investimenti

Porting fedele della `Comitato_App` (analisi-portafoglio) dentro la
piattaforma: metodologia e formati da `camperio_core`, Oracle via
`OracleClient` (LIVE fallisce esplicito, mai dati DEMO come veri), gate
deterministico (voce 18) su Matrice Valutaria e Sintesi Comitato.

## Avvio locale (DEMO)

    .venv/bin/pip install -e ".[comitato]"
    cd apps/comitato && ../../.venv/bin/python app.py
    # http://127.0.0.1:5001 — contratto sintetico DEMO01

Senza variabili `ORA_*` l'app è in DEMO su `fixtures/` (dati interamente
sintetici — mai copiare qui dati reali). Il repository file fondi in DEMO è
`data-demo/fondi/` (vuoto: per il look-through scattano le distribuzioni di
ripiego della skill).

## Contratto di piattaforma

Utente dagli header `X-Auth-Request-User` (oauth2-proxy); porta da `PORT`
(default 5001, bind su 127.0.0.1 dietro nginx in produzione — piano 3).
