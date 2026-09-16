# apps/promotori — Monitoraggio Promotori

Cruscotto per referente commerciale: masse per servizio, apporti/prelievi, commissioni per
trimestre e tipologia, fondi Controlfida alla data, dettaglio contratti. È il porting
dell'artifact cowork `edoricc/monitoraggio-promotori`, che interrogava Oracle dal browser via
MCP. Le query sono le stesse e anche i numeri. Le differenze:

- le query girano sul server con il client Oracle di piattaforma, e referente e date sono
  **bind variable** (nell'artifact venivano concatenati nel testo SQL);
- i calcoli, prima in JavaScript, sono in `promotori/calcoli.py` e coperti da test;
- i nomi dei referenti non sono più scritti nel codice: stanno in un file sulla VM (sotto);
- il periodo di default non è più fisso al 01/01–30/06/2026 ma va dal 1° gennaio all'ultimo
  aggiornamento disponibile.

Differenze minori e dubbi di metodo da chiudere con Edoardo: `DOMANDE-EDOARDO.md`.

## Avvio locale (DEMO)

    .venv/bin/pip install -e ".[promotori]"
    cd apps/promotori && ../../.venv/bin/python -m promotori.app
    # http://127.0.0.1:5002 — tre referenti sintetici, D00001 è il più completo

Senza variabili `ORA_*` l'app è in DEMO su `fixtures/`, con dati interamente sintetici. Mai
copiare qui dati reali. In DEMO le date Dal/Al cambiano masse, saldi e flussi (le fixture
hanno più snapshot); i fondi Controlfida restano invece una fotografia fissa.

## Struttura

| File | Ruolo |
|---|---|
| `promotori/query.py` | le 12 query Oracle, con il perché di ogni filtro |
| `promotori/dati.py` | `Sorgente`: esegue le query in LIVE, filtra le fixture in DEMO |
| `promotori/calcoli.py` | stato, periodo, masse, flussi, rendimenti, commissioni, fondi |
| `promotori/nomi.py` | lettura del file dei nomi e avvisi |
| `promotori/app.py` | Flask: `/`, `/api/referenti`, `/api/cruscotto` |
| `promotori/templates/index.html` | la pagina: solo presentazione |

## Contratto di piattaforma

- Porta da `PORT` (default 5002), bind su `127.0.0.1`.
- Con `PROMOTORI_AUTH=1` l'utente deve arrivare dall'header `X-Auth-Request-User`
  (oauth2-proxy); senza, 401.
- La pagina chiama le API con URL relativi, quindi funziona anche dietro nginx sotto un
  prefisso (`/promotori/`).
- Oracle irraggiungibile in LIVE: HTTP 503 con messaggio, mai dati DEMO al posto dei veri.
- Grafici: Chart.js da jsDelivr con controllo di integrità (SRI), come nell'artifact. Se il
  browser non raggiunge il CDN i grafici spariscono e i numeri restano in pagina.
- Contratti, masse di fine anno, commissioni e operazioni restano in memoria 5 minuti per
  referente, così un cambio di data non rilancia le query pesanti. «Ricarica» li rilegge.

**Non ancora cablato nel deploy**: `deploy/` va concordato con Bernardino. Serve un servizio
nel compose (stessa immagine base di comitato, `PROMOTORI_AUTH=1`, volume `camperio-data`),
una location `/promotori/` in nginx e il gruppo Entra di accesso.

## File dei nomi dei referenti

I codici dei referenti (`TAGS_VALUE.VALITEM_DES`) su Oracle non hanno un nome leggibile. La
decodifica sta in un file JSON **mantenuto a mano**: nessun processo lo aggiorna, e se
arriva un referente nuovo qualcuno deve aggiungerlo.

- **Dove**: `$CAMPERIO_DATA/promotori/nomi-referenti.json`, cioè
  `/var/lib/camperio/promotori/nomi-referenti.json` dentro il container (volume
  `camperio-data`). In DEMO si usa `fixtures/nomi-referenti.json`, con nomi sintetici.
- **Formato**: un oggetto codice → nome, in UTF-8. Le chiavi che iniziano con `_` sono
  commenti e vengono ignorate.

  ```json
  {
    "_aggiornato": "2026-09-15, da <chi>",
    "A00001": "Nome Cognome",
    "A00002": "Altro Nome"
  }
  ```

- **Chi e quando**: chi amministra la piattaforma, ogni volta che compare un referente
  nuovo o ne cambia uno. Il nome non è un segreto, ma è un dato personale interno: il file
  non va nel repo né in allegati email.
- **Come si aggiorna**: si modifica il file e lo si copia nel volume, per esempio
  `docker compose cp nomi-referenti.json promotori:/var/lib/camperio/promotori/`. L'app lo
  rilegge a ogni apertura della pagina, **senza riavvio**.
- **Cosa succede se qualcosa non va**: il menu non si blocca mai, mostra il solo codice.
  In testa alla pagina compare un riquadro giallo «Nomi dei referenti» che dice cosa
  sistemare:
  - file non trovato (con il percorso cercato);
  - JSON non valido, con riga e colonna dell'errore;
  - file non in UTF-8, o non leggibile per i permessi;
  - contenuto che non è un oggetto `{"CODICE": "Nome"}`;
  - voci ignorate perché il nome è vuoto o non è un testo;
  - referenti presenti su Oracle ma assenti dal file (da aggiungere);
  - voci del file che non corrispondono a nessun referente su Oracle (codice sbagliato o
    referente senza più contratti).

## Validazione in LIVE (prima di comunicare l'URL)

In DEMO i test coprono le regole. I numeri veri però vanno confrontati con la dashboard viva,
aperta in cowork, sullo stesso referente e sulle stesse date Dal/Al: KPI, composizioni, fondi
e le righe del dettaglio. I casi già verificati dall'autore contro le estrazioni Antana, con
i numeri attesi, sono nei commenti dell'artifact originale: fondi e fotografia storica
(`sqlFondi`), contratto chiuso prima di Al (`sqlFondi`), flussi reali (`sqlFlussiReali`),
rendimento da SRE (commento in `render`). Si ripartono da lì. I numeri non si copiano in
questo repo.
