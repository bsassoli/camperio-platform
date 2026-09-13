# Istruzioni passo-passo — validazione hotfix hedge su ANTANA (produzione)

Scritto il 13/09/2026 dopo aver completato la stessa validazione su ANTATEST. Da seguire su **ANTANA**, la VM di produzione usata dai clienti veri — non ANTATEST. Ogni comando va dato dentro una sessione SSH sulla VM, da `/opt/camperio/deploy`, salvo dove indicato.

## 0. Prerequisito — non partire prima di questo

**PR #3** (`fix: parse_ishares guidata dall'header`, https://github.com/bsassoli/camperio-platform/pull/3) deve essere **mergiata in `main`** prima di toccare ANTANA. Su produzione si aggiorna con un `git pull` pulito, non con un cherry-pick locale come fatto su ANTATEST per validare in fretta.

Controllo dallo stesso terminale (anche da ANTATEST, non serve essere su ANTANA):

```bash
gh pr view 3 --json state,mergedAt
```

Se `"state":"MERGED"`, si procede. Se è ancora `"OPEN"`, aspettare che qualcuno del team la approvi e la unisca — **non aprire scorciatoie su produzione**.

Consigliata anche la merge di **PR #4** (la nota di registro), ma non è bloccante per la validazione tecnica.

## 1. Cosa aspettarsi (contesto in breve)

Su ANTATEST abbiamo trovato che il future S&P 500 (contratto SET-26, scade **giovedì 18/09/2026**) veniva letto correttamente ma la copertura (`hedge_dett`/`tot_hedge`) risultava vuota, perché iShares ha cambiato formato al CSV con la composizione del fondo `IUSA` e il vecchio lettore lo ignorava silenziosamente. La correzione (PR #3) rende il lettore guidato dall'header invece che da colonne fisse.

Su ANTANA il dato di partenza (portafoglio, CSV scaricati) è indipendente da ANTATEST: **non dare per scontato che il sintomo sia identico**. Il passo 4 qui sotto distingue i casi possibili.

## 2. Collegarsi e aggiornare il codice

```bash
ssh <utente>@<host-antana>
cd /opt/camperio
git status --short        # deve essere pulito; se non lo è, fermarsi e capire perché prima di continuare
git pull
cd deploy
docker compose build
```

**Atteso:** `git pull` mostra il merge di PR #3 (e #4) tra i nuovi commit; la build finisce con `Built` / `naming to ...`, senza errori.

## 3. Riavviare e verificare che il servizio risponda

> ⚠️ Questo comando **ricrea tutti i container**, incluso `nginx`: c'è una breve interruzione (pochi secondi) per gli utenti collegati in quel momento. Se possibile farlo fuori dall'orario di punta, o avvisare prima.

```bash
docker compose up -d --force-recreate
curl -k -s https://127.0.0.1/ -o /dev/null -w "smoke test (atteso 302): %{http_code}\n"
```

**Atteso:** `smoke test (atteso 302): 302`.

## 4. Controllare i dati grezzi e distinguere un eventuale problema

```bash
docker compose exec comitato python -c "import data_layer as D;print(D.mode(),D.get_portfolio('ANTASIMGEST','8097S')['deriv'])"
```

**Atteso:** `LIVE`, e una lista con il future S&P 500 (`grutit` tipo `G12`, `valorefut` negativo, intorno a −330.000 € ma cambia ogni giorno — controllare che il segno sia negativo, cioè hedge in essere).

Poi:

```bash
docker compose exec comitato python -c "import os,data_layer as D,lookthrough as L;print(D.REPO,os.listdir(D.REPO));f=L._find_csv(D.REPO,'IUSA');print(f,len(L.parse_ishares(f)) if f else None)"
```

Tre esiti possibili:

- **Un file `IUSA_*.csv` c'è, e il numero dopo è > 400** → tutto bene, andare al passo 5.
- **`listdir` non contiene nessun `IUSA_*.csv`** → il download ETF non ha ancora girato o è fallito su questa VM. Lanciare a mano: `docker compose run --rm -T comitato python scarica_etf.py`, poi rileggere il log (`_download_etf.log` nella cartella stampata come `D.REPO`) e ripetere questo comando.
- **Il file c'è ma il numero è `0`** → non dovrebbe più succedere con PR #3 mergiata; se succede comunque, fermarsi: vuol dire che il formato del CSV su questa VM è ancora diverso da quello incontrato su ANTATEST, e serve capire perché prima di andare avanti (guardare l'header con `head -5 <percorso file>`).

## 5. Verificare che la copertura si calcoli giusta

```bash
docker compose exec comitato python -c "import data_layer as D,lookthrough as L;t=L.build_titoli(D.get_portfolio('ANTASIMGEST','8097S'),D.REPO);print(t['hedge_dett']);print('tot_hedge:',round(t['tot_hedge']))"
```

**Atteso:**
- `hedge_dett` con una voce, `indice: IUSA`, `valorefut` uguale a quello letto al passo 4.
- `tot_hedge` entro lo **0,5%** del `valorefut` del future (su ANTATEST lo scarto era 0,17% — dovuto al fatto che i pesi IUSA non sommano esattamente al 100%).

Se lo scarto supera lo 0,5%, non proseguire: segnalarlo prima di dichiarare la validazione conclusa (vedi tabella "Numeri attesi" in `docs/HANDOFF-VM-HEDGE.md` per i riferimenti).

## 6. Far girare i test automatici

```bash
docker compose run --rm -T \
  -v /opt/camperio/apps/comitato/tests:/opt/camperio/apps/comitato/tests:ro \
  comitato sh -c "pip install --no-cache-dir pytest >/dev/null && python -m pytest tests/test_hedge.py tests/test_ishares.py -v"
```

**Atteso:** `15 passed`.

## 7. Registrare l'esito

Aggiungere in `docs/STATO-MIGRAZIONE.md` una voce analoga a quella già scritta per ANTATEST (data, numeri letti, eventuali differenze), seguendo lo stesso schema che segue una modifica documentale via branch + PR (non modificare il file direttamente senza committare):

```bash
cd /opt/camperio
git checkout -b docs/stato-validazione-hedge-antana
# modificare docs/STATO-MIGRAZIONE.md
git add docs/STATO-MIGRAZIONE.md
git commit -m "docs: registra validazione hotfix hedge su ANTANA"
git push -u origin docs/stato-validazione-hedge-antana
gh pr create --base main --head docs/stato-validazione-hedge-antana --title "docs: registra validazione hotfix hedge su ANTANA" --body "..."
git checkout main && git reset --hard origin/main
```

## 8. Se qualcosa va storto

Rollback (Parte 8 del runbook `docs/DEPLOY.md`): `sudo systemctl disable --now camperio-scarica-etf.timer && sudo systemctl stop camperio`. Il vecchio mondo sul PC del cliente resta valido finché questa voce non è "migrata e verificata".

## Promemoria di sicurezza (validi anche qui)

- I segreti sono in `/etc/camperio/camperio.env`: **non leggerli, non stamparli, non copiarli** (né con `cat`, né in log).
- **Mai copiare dati reali nel repo** né committare CSV/xlsx/json di clienti.
- Nessuna modifica di codice diretta su `main` in produzione: se serve un fix non ancora pronto, si scopre qui e si torna a lavorarci su ANTATEST/in locale, poi si ripete questa procedura da capo dopo il merge.
