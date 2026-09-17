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

## I report al cliente

Tre documenti, stesso layout ("Comitato Investimenti") e stesso motore
(`pdf_comune.py`):

| Voce nel menu | Modulo | Pagine |
|---|---|---|
| Cliente — Sintetica | `report_cliente.sintetica_pdf` | 1 |
| Cliente — Sintesi | `report_cliente.sintesi_pdf` | 3 |
| Cliente — Rendiconto periodico | `report_rendiconto.rendiconto_pdf` | 9 |

Sostituiscono la vecchia voce `cliente1`. Il prospetto dei movimenti resta
allegato contabile separato: nel rendiconto viene solo richiamato in nota.

**I rendimenti esposti sono al lordo delle commissioni.** `SRE.TCLI` è netto:
il lordo si ottiene restituendo al montante le commissioni Camperio IVA
inclusa (`MOV.CTVREG`), con la formula in
`camperio_core/portfolio/rendimento.py`. Il netto compare una volta sola, nel
quadro patrimoniale del Rendiconto, dove la differenza si legge come riga di
commissioni.

I testi che non escono da Oracle — ruolo dei tre reparti, convinzioni di
gestione, note metodologiche — stanno in `contenuti/<linea>.json` e si
aggiornano senza toccare il codice; `contenuti/default.json` è il ripiego per
le linee senza file dedicato. Le convinzioni citano solo titoli effettivamente
in portafoglio: il peso è calcolato dal database e una convinzione che non
trova posizioni non viene stampata.

## Contratto di piattaforma

Utente dagli header `X-Auth-Request-User` (oauth2-proxy); porta da `PORT`
(default 5001, bind su 127.0.0.1 dietro nginx in produzione — piano 3).
