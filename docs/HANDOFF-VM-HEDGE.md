# Handoff per la sessione sulla VM — validazione hotfix hedge (PR #1)

Scritto il 13/09/2026 per chi (persona o assistente) lavora direttamente sulla VM ANTATEST (`app-ai`, utente `AdminCamperio`) a validare e correggere l'hotfix della copertura. Contiene tutto il contesto che non è deducibile dal codice.

## 1. Da dove viene questo lavoro

- Il cliente ha sviluppato in locale una versione parallela dell'app (`Comitato_App`), divergente dal monorepo da metà agosto. L'analisi completa delle differenze è in `CENSIMENTO-NUOVA-VERSIONE.md`; il piano di back-port in `docs/superpowers/plans/2026-09-13-backport-nuova-versione.md`; il report non tecnico per il cliente in `docs/REPORT-RIALLINEAMENTO-CLIENTE.md`.
- **PR #1 (hotfix hedge)** è stata mergiata in `main` il 13/09 alle 10:42 (merge `1dd5c34`, commit `0da2604`, `b3ac6a9`, `f90e195`). È ciò che gira ora su ANTATEST dopo `git pull` + `docker compose build` + `up -d --force-recreate`.
- **PR #2 (Fase 2)** è aperta, base `main` dopo il retarget automatico: denominatore NAV, `parse_ishares` header-driven, report comitato esteso, correzioni della review. Non va deployata finché il cliente non risponde alle domande 1, 4, 5 del report.
- Scadenza dura: il future S&P 500 MINI SET-26 (contratto `E35126`) scade **giovedì 18/09/2026**. L'hotfix deve essere validato su ANTATEST e in produzione su ANTANA prima.

## 2. Cosa fa l'hotfix

Prima: `build_titoli` agganciava il future dal codice contratto hardcoded `E35126` nel `pod` e ricostruiva il nozionale a mano (`|PNET| × prezzo × 50 ÷ 1,1358`). Al roll il codice cambia e l'hedge spariva: netto = lordo.

Ora (`apps/comitato/lookthrough.py`):
- `data_layer.get_portfolio` espone `pf["deriv"]`: derivati `GRUTIT F*/G*` con `WCTDD.VALOREFUT ≠ 0` (EUR, con segno).
- `_IDXKW` (lista modulo, dopo `_IDX_ETF`) mappa una keyword nel nome dell'indice → ticker ETF del paniere: S&P → `IUSA`, STOXX → `EUE`, DAX → `EXS1`, FTSE → `ISF`, SMI → `EXI1`, MSCI EM → `IEEM`.
- Sezione 4 di `build_titoli`: per ogni voce di `deriv` con keyword riconosciuta e paniere disponibile (`H[etf]` non vuoto) aggiunge `valorefut × peso` a ogni costituente nel bucket `hedge`, e la voce a `hedge_dett`. **Se il paniere manca o è vuoto la voce viene saltata in silenzio** (`if not etf or not H.get(etf): continue`).
- `build_matrix`: stessa logica per le righe informative dei derivati (`_IDX_CCY`).
- Nessun fallback su `pod`, per scelta.

Test: `apps/comitato/tests/test_hedge.py` (8 test, tutti verdi in DEMO). In DEMO il paniere viene da un CSV sintetico in `tmp_path`; **in LIVE dal repository ETF reale**, ed è lì che si gioca la validazione.

## 3. Stato della validazione al 13/09, ore 11

Eseguito sulla VM, dentro il container:

```
docker compose exec comitato python -c "import data_layer as D;print(D.mode(),D.get_portfolio('ANTASIMGEST','8097S')['deriv'])"
→ LIVE [{'des': 'EURO BOBL DIC-26 PUT 113.25', 'grutit': 'F19', 'isin': 'DE000F3RN758', 'valorefut': 77175.2},
        {'des': 'S&P 500 MINI FUT SET-26', 'grutit': 'G12', 'isin': '*00000E35126', 'valorefut': -330070.7}]

docker compose exec comitato python -c "import data_layer as D,lookthrough as L;t=L.build_titoli(D.get_portfolio('ANTASIMGEST','8097S'),D.REPO);print(t['hedge_dett'],round(t['tot_hedge']))"
→ [] 0
```

Diagnosi: la parte dati è corretta (LIVE, future S&P −330.071 €, put Bobl +77.175 €, nomi giusti). **L'hedge però è vuoto**, quindi `H["IUSA"]` è vuoto: il paniere dell'S&P non viene caricato. Due cause possibili, da distinguere:

1. **Manca il CSV** `IUSA_*.csv` nel repository ETF (`D.REPO` = `/var/lib/camperio/data/fondi` in LIVE, perché `CAMPERIO_DATA=/var/lib/camperio`, volume `camperio-data`). Il download è fatto da `scarica_etf.py` (timer systemd `camperio-scarica-etf.timer`, giovedì 11:00; Parte 5.2 del runbook per lanciarlo a mano). Se il timer non è mai scattato o la VM non raggiunge ishares.com, la cartella è vuota.
2. **Il CSV c'è ma il lettore non lo legge.** Su `main` `parse_ishares` è ancora la versione a colonne fisse (`row[3] == "Azionario"`, peso in `row[5]`, header che inizia con `Ticker`). Se iShares ha cambiato formato o lingua, ritorna `[]` senza errore. La versione header-driven (IT/EN, colonne spostate) è nella PR #2, commit `daf790f`, che tocca solo `lookthrough.py` (regione `_pct_ishares`/`parse_ishares`) e aggiunge `tests/test_ishares.py`.

Comando che distingue i due casi:

```
docker compose exec comitato python -c "import os,data_layer as D,lookthrough as L;print(D.REPO,os.listdir(D.REPO));f=L._find_csv(D.REPO,'IUSA');print(f,len(L.parse_ishares(f)) if f else None)"
```

- Se `listdir` non contiene `IUSA_*.csv` → caso 1: `cd /opt/camperio/deploy && docker compose run --rm -T comitato python scarica_etf.py`, poi leggere `_download_etf.log` nella cartella REPO. Se il download fallisce (rete), il CSV va portato a mano sul volume (dal PC del cliente: i CSV in `Repository_Fondi` del drop erano del 10/09, ma il drop sta sul Mac di Bernardino, non sulla VM).
- Se il file c'è e `parse_ishares` ritorna `0` → caso 2: anticipare il fix del lettore su `main` con `git cherry-pick daf790f` (dovrebbe applicarsi pulito: il commit tocca solo `lookthrough.py` e il nuovo test file), rebuild, riprovare. In alternativa guardare l'header del CSV con `head -5` e capire cosa è cambiato.
- Se il file c'è e legge > 400 righe ma l'hedge resta vuoto → guardare `_find_csv` (prende il file più recente per nome, `sorted(..., reverse=True)`: un nome fuori schema può vincere sul file giusto) e la keyword: il nome `S&P 500 MINI FUT SET-26` deve fare match con `("S&P", "IUSA")`.

## 4. Numeri attesi quando funziona

| Grandezza | Valore atteso | Fonte |
|---|---|---|
| `deriv` S&P `valorefut` | ≈ −330.071 € (il 10/09 era −328.220) | WCTDD, cambia ogni giorno |
| `hedge_dett` | una voce, `indice: IUSA`, `valorefut` = quello sopra | |
| `tot_hedge` | entro **0,5%** del `valorefut` (i pesi IUSA non sommano a 100%; il 10/09: −327.662 vs −328.220) | diagnostica del cliente |
| `tot_netto` | < `tot_diretto + tot_fondi + tot_indici` | |
| NAV 8097S | ≈ 4,63 M€ | `pf['meta']['nav']` |
| Put Bobl | presente in `deriv`, **assente** da `hedge_dett` | è tasso, non equity |

Nel report Titoli dal browser: colonna «Delta indice» popolata, «% netto» < «% lordo» sui nomi USA (Nvidia, Apple, Microsoft in testa), riga informativa del future nella Matrice Valutaria.

## 5. Come lavorare sulla VM senza fare danni

- Il codice gira **dentro il container** `comitato`; sulla VM fuori dal container non ci sono né `oracledb` né le variabili `ORA_*`. Ogni comando Python va lanciato con `docker compose exec comitato python -c "..."` da `/opt/camperio/deploy`.
- I segreti sono in `/etc/camperio/camperio.env` (Parte 3 del runbook): non leggerli, non copiarli, non stamparli.
- **Mai copiare dati reali nel repo** e mai committare CSV/xlsx/json di clienti: `.gitignore` li blocca, ma l'output dei comandi resta sulla VM (regola in `docs/DEPLOY.md` Parte 4.2).
- Test sulla VM: l'immagine non contiene pytest né `tests/`; usare la ricetta di Parte 2.4 (monta `tests/` in sola lettura in un container usa-e-getta e installa pytest lì). Per i test dell'hedge: `... python -m pytest tests/test_hedge.py`.
- Aggiornare il codice: Parte 9 (`git pull`, `docker compose build`, `docker compose up -d --force-recreate`, smoke test 302).
- Se serve una modifica al codice: branch da `main`, commit, push, PR; non modificare i file direttamente in `/opt/camperio` senza committare, altrimenti il prossimo `git pull` la perde.
- Rollback: Parte 8 (`systemctl stop camperio`), il vecchio mondo sul PC del cliente resta valido.

## 6. Cosa resta dopo la validazione

1. Registrare in `docs/STATO-MIGRAZIONE.md`: data, commit, numeri letti su ANTATEST.
2. Stessa procedura su ANTANA (produzione), stessi comandi, stessi numeri attesi; registrare anche quelli.
3. Se il caso 2 si è verificato, dirlo nella PR #2: il commit `daf790f` è già in `main` e la PR si riduce.
4. La cartella `history/` (storico pesi, arriva con PR #2) accumula in avanti e non si ricostruisce: al deploy di PR #2 verificare che stia sul volume `camperio-data` e nei backup (già scritto in `docs/DEPLOY.md`).
