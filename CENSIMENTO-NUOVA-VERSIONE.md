# Censimento «Nuova versione» vs monorepo — e piano di riallineamento

Data analisi: 12/09/2026 · Verifica e correzione: 13/09/2026 (controllo riga per riga contro codice, git e mtime) · Analisi in sola lettura, nessun file dell'applicazione modificato.

- **VECCHIA** = `camperio-platform/` (monorepo `core/` + `apps/comitato/` + `deploy/`, in produzione su **ANTANA**, test su **ANTATEST**).
- **NUOVA** = `Analisi portafoglio per comitato/` **alla radice del repo**, più lo zip gemello `Analisi portafoglio per comitato.zip` (stessi 611 file). Entrambi untracked; l'app vive in `Comitato_App/`.

---

## 1. Verdetto

La premessa «la nuova versione supera la vecchia» è **vera solo a metà, e la metà falsa è quella pericolosa**.

Non si tratta di due versioni sulla stessa linea, ma di un **fork divergente in entrambe le direzioni**, e va detto con precisione da quale parte è avvenuta la divergenza. Il monorepo nasce il **17/08/2026** con il commit `f9b2956` «porting fedele di Comitato_App»: gate di validazione, `OracleIndisponibileError`, `html.escape()`, bind su loopback e controllo `X-Auth-Request-User` entrano quel giorno (`af3a612`, `809f2b6`); i fix di footer e contatti sono del **04/09** e **09/09**. I file del drop hanno mtime reali (vedi §8): `report_cliente.py` 23/07, `app.py` 17/08, `data_layer.py` e `lookthrough.py` 10/09. **La NUOVA non ha quindi rimosso nulla**: è la linea originale del cliente, proseguita da un antenato comune di metà agosto. Le voci elencate sotto come «regressioni» sono, più esattamente, **fix e hardening che la linea del cliente non ha mai ricevuto**. Il piano operativo non cambia; cambia il modo in cui va presentato all'autore.

| | VECCHIA (monorepo) | NUOVA (drop) |
|---|---|---|
| Metodologia di calcolo | ferma a prima del 23/07/2026 | **avanti**: fix hedge 10/09, denominatore 23/07, `_is_equity_deriv` |
| Funzionalità | base | **avanti**: opzioni, QA, storico pesi, report comitato ampliato |
| Architettura | `core/` condiviso, packaging, ~15 file di test | copia locale del core, zero test |
| Sicurezza / safety | gate di validazione, SSO Entra, anti-XSS, fail-safe Oracle | **assente**: mai ricevuti dalla linea del cliente (aggiunti nel monorepo dal 17/08) |
| Fix già in produzione | presenti | **5 su 6 mai ricevuti** (commit del 04/09 e 09/09, posteriori al fork) |
| Deploy | Docker + nginx + TLS + oauth2-proxy + systemd | assente (solo `.bat` e due guide) |
| Segreti | fuori repo (`docs/SECRETS.md`) | **credenziali Oracle in chiaro nel drop** |

**Conseguenza operativa:** sostituire la produzione col drop così com'è è da escludere. La strada è un **back-port selettivo, file per file, dalla NUOVA nel monorepo**, rifiutando esplicitamente le differenze elencate al §6 come «da non portare».

---

## 2. Le due urgenze

### 2.1 Il future S&P scade il 18/09/2026 — fra 5 giorni (al 13/09)

Il monorepo in produzione contiene ancora il codice hedge **pre-correzione**: `apps/comitato/lookthrough.py` righe 178, 180, 333, 334 aggancia il future col **codice contratto hardcoded `E35126`** (c'è anche un match su `"S&P" in des`, ma `pod.des` contiene il codice e non il nome, come mostra `diagnostica_output.txt`: il match sul nome è morto) e ricostruisce il nozionale a mano (`|PNET| × prezzo × 50 ÷ cambio fisso 1,1358`).

Al rollover il codice contratto cambia → **l'hedge sparisce silenziosamente** → nel report «Titoli azionari lordo/netto» il **netto torna uguale al lordo**, cioè lo short non viene contato. Sul portafoglio 8097S l'errore misurato al 10/09/2026 vale **−328.220 €, pari a −7,1% del NAV**: il rischio azionario risulterebbe sottostimato di ~7 punti percentuali senza alcun segnale d'errore.

È esattamente l'incidente che il changelog della NUOVA classifica come «CORREZIONE GRAVE». **Questo è l'unico intervento che non può aspettare la fine del riallineamento.**

### 2.2 Credenziali Oracle di produzione in chiaro nel drop

- `Comitato_App/config.env`, righe **6-8**: `ORA_USER`, `ORA_PWD`, `ORA_DSN` valorizzati con credenziali reali (non placeholder; verificato per lunghezza senza mai leggerne il valore).
- `Comitato_App/GUIDA_IT_LOGIN_SSO.md`, righe **63-65**: **username** e hostname/DSN Oracle di produzione in chiaro (solo la password era già mascherata dall'autore).

`config.env` è **già coperto** da `.gitignore` (`git check-ignore` lo conferma). Il vettore reale è un altro: lo **zip alla radice non è ignorato e contiene `config.env`**. Un `git add .` (verificato con `git add -n .`) stagerebbe lo zip, 41 `.py` (incluso il dump dati), 60 `.docx`, 16 `.json`, 10 `.html`, il `.pptx` e la skill. Il remote è `github.com/bsassoli/camperio-platform`. Prima di qualsiasi operazione git:

1. spostare fuori dal repo (o ignorare) **lo zip** e la cartella; aggiungere a `.gitignore` anche `*.zip`, `*.docx`, `*.pptx`, `*.tmp`, `.~lock.*#`, `*.bak*`;
2. **rotazione della password Oracle** con il DBA — va considerata compromessa perché ha circolato in chiaro dentro uno zip;
3. bonifica di `GUIDA_IT_LOGIN_SSO.md` (username e host);
4. attenzione anche a `_motore/dati_8097S.py`: contiene un **dump di dati cliente reali** (serie NAV, 114 posizioni di cui 24 con ISIN, movimenti) incollato nel sorgente; e `Comitato_App/diagnostica_output.txt` contiene il percorso Windows con il nome utente del cliente, mentre `export/` ha nomi di clienti nei filename.

Il pattern corretto esiste già ed è quello da mantenere: `Comitato_App/data_layer.py` righe 169-174 legge tutto da `os.getenv`, e `config.example.env` è un template pulito.

---

## 3. Censimento — file presenti in entrambe le versioni

Conteggio righe Python:

| File | NUOVA | VECCHIA | Δ |
|---|---:|---:|---:|
| `app.py` | 179 | 184 | −5 |
| `data_layer.py` | **612** | 455 | **+157** |
| `lookthrough.py` | **864** | 809 | **+55** |
| `report_cliente.py` | 390 | 393 | −3 |
| `report_comitato.py` | **307** | 169 | **+138** |
| `scarica_etf.py` | 16 | 16 | 0 (identico byte a byte) |
| `methodology.py` | 111 (in `Comitato_App/`) | 101 (in `core/camperio_core/portfolio/`) | +10, ricollocato |

### 3.1 `app.py`

**Novità:** `import qa as QA`, `import opzioni as OPZ`; nuove rotte `/api/ask`, `/opzioni`, `/opzioni/genera`, `/opzioni/view`, `/opzioni/excel`.

**Assente rispetto alla VECCHIA (hardening aggiunto nel monorepo il 17/08, mai ricevuto dalla linea del cliente):**
- **Gate di validazione**: mancano `validate_report` e `OracleIndisponibileError` da `camperio_core`, la funzione `_controlla_matrice()` (che blocca l'emissione del report se la matrice valute+oro non quadra col NAV), `_blocco_html()` e l'`@app.errorhandler`.
- **Hardening**: logout Entra ID, controllo header `X-Auth-Request-User`, `html.escape()` anti-XSS. Superficie XSS concreta nella NUOVA: `dal`/`al` dalla query string tornano non escapati nel messaggio d'errore di `resolve_period` e finiscono in `innerHTML` in `templates/index.html` (righe 145 e 188); `str(e)` grezzo in tre rotte (`app.py` 102, 113, 131).
- **Binding di rete**: default `127.0.0.1` (VECCHIA) → `0.0.0.0` hardcoded (NUOVA), servizio esposto su tutte le interfacce.

Nessun import di `camperio_core` in tutto il file: è assenza vera di codice equivalente, non un cambio di percorso di import.

### 3.2 `data_layer.py`

**Novità da portare:**
- `_is_equity_deriv(nome)` + `der_eq` calcolato in Python (classificazione dei derivati per **parola chiave su `TIT.DESTITB`**, non per codice contratto). Intercetta anche le **opzioni su singolo titolo**, che il vecchio filtro SQL per sole parole-chiave di indice perdeva.
- Nuova estrazione `pf["deriv"]` (`WCTDD` `F*`/`G*` con `VALOREFUT<>0`), necessaria al fix hedge di `lookthrough`.
- Storico su JSON: `load_weight_history`, `update_weight_history`, `load_class_weight_history`, `update_class_weight_history`, `_hist_file`, `_hist_class_file` (scrivono in `Comitato_App/history/`, con `except Exception: pass`).
- `dettaglio_mensile()` — dettaglio mensile titolo/fondo/oro, performance total-return EUR vs valuta locale.
- `_fx_case()`. (`contract_info()` esiste già identica nella VECCHIA, riga 438: non è una novità.)

**Assente (differenza grave):** il **fail-safe Oracle**. La VECCHIA, in modalità LIVE con Oracle irraggiungibile, solleva `OracleIndisponibileError` → HTTP 503 (via `core/camperio_core/oracle/client.py`). La NUOVA cattura qualunque eccezione in `_connect()` (righe 165-181) e **ricade silenziosamente su DEMO**, segnalando solo con un `print()`. Peggio di quanto sembri: il DEMO della NUOVA serve `cache/8097S.json`, cioè **dati reali stantii del cliente**, non fixture sintetiche. Un guasto di rete momentaneo produce quindi un report vero con numeri vecchi, indistinguibile da uno aggiornato. Inoltre `mode()` richiama `_connect()` a ogni richiesta e, dopo un fallimento, ritenta la connessione ogni volta. Viola il contratto di piattaforma esplicitato in `docs/DEPLOY.md` §4.1.

Assente anche `_default_repo()` (funzione locale di `apps/comitato/data_layer.py`, righe 24-29, che passa da `camperio_core.config.from_env()`), sostituita da `COMITATO_REPO` env var con default `<drop>/Repository_Fondi`.

**Punto da chiarire prima del back-port:** la NUOVA riscrive la fonte dei movimenti da `ORD.TIPOPE` (euristica sui prefissi stringa, definita «inaffidabile» nei commenti del codice nuovo stesso) a **`MOV.TIPOMO` ('A'/'D') + `CTVTIT`** già in EUR. Tecnicamente più robusto — ma il changelog del **26/06/2026 prescrive l'opposto** (riga 77: «Usare **ORD** (solo trade) e NON MOV (mescola movimenti tecnici: collaterale, trasferimenti, che non riconciliano)»), e nessuna voce successiva lo revoca. La NUOVA è per giunta **mista**: `price_changes` usa ancora ORD per l'aggiustamento post-AL (righe 370-371, identiche alla VECCHIA) e la docstring di `comitato_extra` parla ancora di «registro ORD». Va deciso con l'autore prima di portarla.

### 3.3 `lookthrough.py`

**Novità da portare:**
- **Fix hedge 10/09/2026** in `build_titoli()` (righe ~358-390 della NUOVA, al posto delle ~329-334 della VECCHIA): mappa `_IDXKW` nome-indice → ETF, `VALOREFUT` **con segno** preso da `WCTDD` (già in EUR, negativo per gli short), ripartito sui costituenti dell'ETF dell'indice; restituisce anche `hedge_dett`. Rimossi dal percorso principale: codice `E35126` e nozionale manuale. Regge sia long che short e sopravvive al rollover. **Ma la dipendenza da `pod` non è sparita**: alla riga **378** resta un fallback `if not derivs:` che scorre `pf["pod"]` e ricostruisce il nozionale con la vecchia formula `−|pnet| × val × 50 ÷ 1,1358`. Nel back-port va rimosso, non copiato.
- `parse_ishares()` riscritta: parsing guidato dall'header invece che per indici di colonna fissi → resiste ai cambi di formato dei CSV iShares.
- `variazioni_*`: metodologia passata da EUR/FX-inclusa (`e_dal`/`e_al`) a **valuta locale** (`var_loc`), esposta anche in UI.
- Suffisso codice cliente `" (8097S)"` nei titoli dei report.

**Differenze residue:** contatti aziendali come in `report_cliente.py` (`_F1`, riga 561 VECCHIA / 614 NUOVA); import locali (`import methodology as M`, `from methodology import eur, pct`) al posto di `camperio_core`; nuovo helper `_pct_ishares()` (righe 200-205); diciture di HTML/Excel/Word aggiornate a «netto = lordo + delta derivati su indice». `_F2` (testo legale) invariato.

**Difetto aperto dentro la NUOVA stessa:** la riga **178** — dentro `build_matrix()`, la funzione gemella che costruisce la matrice valute — è **identica byte a byte nelle due versioni** e contiene ancora `E35126` + `×50 ÷ 1,1358`. Il fix del 10/09 è stato applicato solo a `build_titoli()`. Le due funzioni sorelle sono quindi disallineate *all'interno della nuova versione*. Va corretta comunque, qualunque linea vinca. (Nota metodologica del changelog: opzioni e future su indice dei fondi restano volutamente **esclusi** dalla matrice FX — ma l'esclusione va scritta bene, non affidata a un codice contratto morto.)

### 3.4 `report_cliente.py`

**Novità da portare:** riga 121 VECCHIA → riga 120 NUOVA, `base = (nav + der_eq) if (nav + der_eq) else nav` → **`base = nav`**. È la correzione del 23/07/2026, validata al centesimo su R1450 (ANTASIMN 22/07/2026): il denominatore dell'esposizione azionaria deve essere **sempre NAV = `SRE.CONSFIN`**, mai «NAV + delta derivati» (era una taratura errata su 8097S che gonfiava la base e abbassava la percentuale). Cambia tutte e quattro le percentuali di allocazione ogni volta che `der_eq ≠ 0`.

**Assenti — tre fix del monorepo posteriori al fork (`report_cliente.py` della NUOVA è del 23/07; i commit sono del 04/09 e 09/09). Il diff completo del file ha solo tre hunk: contatti/`_F2`, `base`, footer.**

| Fix in produzione | Commit | Stato nella NUOVA |
|---|---|---|
| Footer alzato di 3 mm | `bec19af` (09/09) | **assente** — ogni riga è 3 mm più in basso (`_F1` 12,5 mm vs 15,5; `_DISC` 5,8 vs 8,8) |
| Split del footer su confine di frase | `c616d42` (04/09) | **assente** — torna a `_F2[:118]` / `_F2[118:]`, taglio a indice fisso, cioè a metà parola |
| Numero pagina coperto dal disclaimer | `e1683a3` (04/09) | **assente** — disclaimer e «Pag. N» di nuovo alla **stessa quota** (5,8 mm) |

E una quarta, sistemica: i **contatti aziendali**. NUOVA: `Tel +39-02 30322100` / `camperioSIM@camperio.net`. VECCHIA: `Tel +39 02.50020918` / `camperioSIM@camperiosim.com`, valore introdotto apposta dai commit `e6d3a86` e `7015155` («Fix contatti errati»). Salvo smentita dell'ufficio, **vale la VECCHIA**. La stringa pre-fix ricorre anche in `lookthrough.py`, `templates/index.html`, `reports.py`, `_motore/esporta.py` e in tutti i 16 `build_*.py` di Earnings Review.

### 3.5 `report_comitato.py`

**Espansione puramente additiva** (169 → 307 righe), nessuna funzionalità rimossa: le sezioni 1-7 restano strutturalmente intatte.

Nuove funzioni: `_it()` (data ISO → formato italiano), `_peso_azioni_storico()` (peso azionario diretto+ETF vs settimana/mese/anno precedente, con carry-forward sullo storico JSON), `_pesi_inizio_mese()`. In `build_comitato()`: `contract_info()`, storico pesi di classe, colonna «% inizio mese» per asset class, `eq_dir_etf` (azioni dirette + ETF `H10/H16/H18/H23`), `dett = DL.dettaglio_mensile(...)`. Nuove sezioni di report: **3-bis** (andamento peso azionario), **8** (dettaglio azioni titolo per titolo), **9** (fondi ed ETF), **10** (oro fisico). Titolo personalizzato col nome cliente invece della «Linea Camperio» statica.

**Attenzione:** le sezioni 8/9/10 dipendono da `dettaglio_mensile()`, avvolta in try/except con fallback silenzioso a `None`. Combinata col fallback DEMO silenzioso di `data_layer` (§3.2), è una catena che può produrre sezioni popolate con dati finti senza alcun avviso. Va portata **dopo** aver ripristinato il fail-safe.

### 3.6 `methodology.py`

Nella NUOVA è una **copia locale arricchita**, non un import dal core. Aggiunge `eur()`, `pct()`, `num()` (prima da `camperio_core.render.format`) e `MACRO_COLOR` (Difesa `#151F6D`, Centro Campo `#2E5A9E`, Attacco `#FF8200`, Overlay `#666666`, Altro `#999999`).

`macro()` e `currency_of()` (con `_ccy_from_isin`, `_ccy_from_descr`, `_EXCH`, `_OVERRIDE_BBG`, `_NAME_CCY`, `CCY_LABEL`) sono **logicamente identici**: cambia solo la formulazione di una docstring. Le copie locali di `eur()`/`pct()`/`num()` mancano invece della guardia `math.isfinite` presente in `core/camperio_core/render/format.py`: usare il core.

`MACRO_COLOR` va **riconciliato con `core/camperio_core/branding/palette.py`** (11 righe, coperto da `core/tests/test_palette.py`), non duplicato.

### 3.7 `scarica_etf.py`

Identico byte a byte (a meno di CRLF/LF). Nessun intervento.

---

## 4. Censimento — presente solo nella NUOVA

### 4.1 Moduli applicativi

| File | Righe | Ruolo | Agganciato ad `app.py`? |
|---|---:|---|---|
| `opzioni.py` | 175 | Report «Analisi Opzioni sul Portafoglio» (IV-rank, skew), output HTML+Excel. **Byte a byte identico** a `scripts/opzioni.py` dentro `analisi-opzioni-camperio.skill` (skill Claude del 18/08 inclusa nel drop). Importa `blpapi_fetch` in try/except: **il modulo non è nel drop**, quindi il percorso Bloomberg non può funzionare così com'è e vale solo il fallback su `report_opzioni/iv_data.json` | **Sì** — rotte `/opzioni*` |
| `qa.py` | 120 | «Chiedi al portafoglio»: risposte deterministiche per parole chiave, **nessun LLM, nessuna rete** | **Sì** — rotta `/api/ask` |
| `reports.py` | 243 | Modulo completo report pesi/fx/titoli in HTML/Word/Excel (`compute`, `html_fragment`, `word`, `excel`) | **No — orfano.** Zero riferimenti in `app.py`, che usa `report_comitato.py` con API diversa |
| `diagnostica_hedge.py` | 61 | Script diagnostico manuale sugli hedge, con `diagnostica.bat` | **No** — uso manuale |

`reports.py` è codice maturo ma **duplicato/orfano** rispetto a `report_comitato.py`. Prima di integrarlo va chiarito con l'autore se è un refactoring incompiuto, codice futuro non ancora cablato, o materiale superato. `diagnostica_hedge.py`, se lo si tiene, va in un `tools/` separato, non nel percorso applicativo.

### 4.2 Asset non-Python

- `templates/opzioni.html` — nuovo, coerente col modulo opzioni.
- `static/style.css` — +22 righe, **solo aggiunte** (regole del pannello QA), nessuna rimozione.
- Loghi: i 3 PNG sono identici (md5 uguale); **2 SVG differiscono** — differenza accertata ma non qualificata, da ispezionare prima di portarli.
- Nessun file JS separato in nessuna delle due versioni.

### 4.3 Fixture e modalità DEMO

| VECCHIA | NUOVA |
|---|---|
| `apps/comitato/fixtures/contratti.json` | `Comitato_App/cache/contratti.json` |
| `fixtures/DEMO01.json`, `DEMO01_comitato.json`, `DEMO01_var.json` | `cache/8097S.json`, `8097S_comitato.json`, `8097S_var.json` (stesso schema, rinominati) |
| — | `history/` (`pesi_000.json`, `pesi_8097S.json`, `pesi_classi_8097S.json`) — **solo NUOVA** |
| — | `report_opzioni/` (`ctx.json`, `iv_data.json`, `meta.json`, `weights.json` + output) — **solo NUOVA** |
| — | `esempi_output/` — **solo NUOVA** |

La modalità DEMO **esiste** anche nella NUOVA, ma con garanzie più deboli: vedi §3.2.

### 4.4 Dipendenze

| | VECCHIA | NUOVA |
|---|---|---|
| WSGI | `gunicorn` pinnato in `pyproject.toml` | **assente** da `requirements.txt`; `waitress` solo citato in `README_DEPLOY.md` come `pip install` manuale |
| Oracle | `oracledb` dipendenza core | `oracledb` presente ma di fatto opzionale |
| Packaging | `pyproject.toml` + package `camperio_core` | nessuno, solo `requirements.txt` flat |

Nessuna libreria nuova di rilievo. Nulla da importare qui se non la conferma che il set di dipendenze non cresce.

### 4.5 Sottosistemi `_motore/` ed `Earnings Review/`

**`_motore/`** (`dati_8097S.py` 168, `esporta.py` 302, `genera_analisi.py` 488): script batch monolitici da lanciare a mano in sequenza, nessun `main()`, nessun parsing argomenti. Reimplementano in modo statico ciò che `data_layer.py` fa con connessione live + cache, e ricalcolano da zero la logica già incapsulata in `reports.py` — il testo legale del footer è **identico verbatim** fra `esporta.py` (righe 64-67) e `reports.py` (righe 13-17), prova di copia-incolla. `genera_analisi.py` righe 312-314 **dichiara nel testo prodotto** che il download da ishares.com «è riuscito», ma il file non contiene alcuna chiamata HTTP: rischio di affermazione falsa dentro un report. Qualità da scratch d'analista: logica a livello di modulo, nessuna gestione errori, path della macchina personale hardcoded, HTML concatenato senza escaping. Contiene inoltre il dump di dati cliente reali già segnalato. **Da lasciare fuori dal repo applicativo**; semmai si recupera la metodologia, non il codice.

**`Earnings Review/`** (49 MB, 305 file): 16 script `build_<ticker>.py` (513-668 righe l'uno) che generano i report post-earnings. **Zero input esterni**: KPI, testi e giudizi sono letterali nel sorgente; i path (`BASE`/`LOGO`/`OUT`/`CHART`) puntano a sessioni sandbox effimere (`/sessions/<nome-random>/mnt/...`) diverse per script → **non eseguibili fuori dalla sessione originale**. Duplicazione misurata sul confronto integrale di `build_aena.py` vs `build_nvda.py` più campionamento su altri quattro: **~45-55% di ogni file (250-300 righe su 500-615) è boilerplate identico**, stesse ~20 funzioni helper con gli stessi nomi. La sottocartella `_build2108/` è un tentativo di refactoring del 21/08/2026 con libreria condivisa parametrica (`camperio_lib.py`, 407 righe) usata dai 5 script che stanno lì dentro — **mai adottato** dai 16 principali; `_build2108/_srchead.py` è un file orfano troncato a metà `def`. Nessun segreto trovato. **Da lasciare fuori dal repo applicativo.**

### 4.6 Volumi binari e scarti

Il drop pesa **69 MB**: 41 `.py`, e poi 153 `.csv`, 87 `.png`, 83 `.pdf`, 60 `.docx`, 56 `.xlsx`, 16 `.json`. Le cartelle `Analisi mensile/`, `Presentazioni clienti/`, `Report Opzioni/`, `Repository_Fondi/` (~13 MB), `Snapshot/`, `export/`, `_esempi_output/` sono quasi interamente **dati di input e output generati**, non codice. Fra gli scarti: 35 `.tmp`, 35 lock LibreOffice `.~lock.*#`, `earnings_registry.json.bak_20260911`, `__pycache__/`. Il file singolo più grande è `Presentazioni clienti/Opzioni_AFCF_2026.pptx` (1,1 MB).

Nulla di tutto questo va committato: storage esterno, e `.gitignore`.

---

## 5. Censimento — presente solo nella VECCHIA (cosa si perderebbe)

**Package condiviso `core/camperio_core`:** `config.py` (33), `oracle/client.py` (81), `portfolio/methodology.py` (101), `portfolio/validation/checks.py` (259), `portfolio/validation/gate.py` (55), `render/format.py` (37), `branding/palette.py` (11).

**Tutti i test — la NUOVA non ne ha nessuno.** `core/tests/`: `test_checks.py` (157), `test_oracle_client.py` (130), `test_methodology_currency.py` (61), `test_gate.py` (49), `test_methodology_macro.py` (33), `test_format.py` (30), `test_config.py` (23), `test_palette.py` (12), `test_smoke.py` (2). `apps/comitato/tests/`: `test_hardening.py` (71), `test_app_demo.py` (62), `test_data_layer.py` (50), `test_fixtures_sintetiche.py` (35), `test_gate_app.py` (30), `conftest.py` (6).

**Infrastruttura di deploy — interamente assente nella NUOVA:**

| VECCHIA | Equivalente NUOVA |
|---|---|
| `deploy/comitato/Dockerfile` | nessuno |
| `deploy/docker-compose.yml`, `deploy/compose.demo.yml` | nessuno |
| `deploy/nginx/nginx.conf` (TLS, `auth_request` oauth2-proxy, **azzeramento anti-spoofing** di `X-Remote-User`/`X-Forwarded-User` in ingresso) | nessuno; solo *descritto* per IIS in `GUIDA_IT_LOGIN_SSO.md` |
| `deploy/systemd/camperio.service` | nessuno |
| `deploy/systemd/camperio-scarica-etf.timer`/`.service` | `pianifica_etf.bat` (Task Scheduler Windows), senza retry né log |
| `deploy/tls/genera-ca-interna.sh` | nessuno |
| `jobs/`, `agent/` | nessuno |
| `docs/DEPLOY.md`, `RICHIESTE-IT.md`, `SECRETS.md`, `STATO-MIGRAZIONE.md` | solo `README_DEPLOY.md` (sintetico) |

Nota di sicurezza: **entrambe** le versioni leggono `X-Remote-User`/`X-Forwarded-User` senza verifica nel codice Python (`app.py` riga 38 VECCHIA, 23-24 NUOVA). La differenza non è nel codice ma attorno: la VECCHIA li azzera in `nginx.conf` (righe 84-85) e ascolta solo su loopback; la NUOVA ascolta su `0.0.0.0` e demanda la protezione — solo sulla carta — alla configurazione IIS.

---

## 6. Riepilogo decisionale

### Da portare nel monorepo (in quest'ordine)

| # | Cosa | File monorepo | Priorità |
|---|---|---|---|
| 1 | Fix hedge 10/09: `_IDXKW` + `VALOREFUT` con segno + `hedge_dett`; rimozione di `E35126` e del nozionale manuale, **incluso il fallback `pod` della riga 378 della NUOVA** | `apps/comitato/lookthrough.py` (`build_titoli`) + `data_layer.py` (`pf["deriv"]`) | **urgente, entro il 18/09** |
| 2 | Stesso fix esteso a `build_matrix()` (riga 178) — difetto aperto in *entrambe* le versioni | `apps/comitato/lookthrough.py` | **urgente** |
| 3 | Denominatore 23/07: `base = nav` + `_is_equity_deriv()` lato Python | `report_cliente.py:121`, `data_layer.py` | alta |
| 4 | `parse_ishares()` guidata dall'header | `lookthrough.py` | media |
| 5 | Espansione additiva del report comitato (3-bis, 8, 9, 10; storico JSON; `contract_info`) | `report_comitato.py`, `data_layer.py` | media, **dopo** il ripristino del fail-safe |
| 6 | `opzioni.py` + `qa.py` + `templates/opzioni.html` + CSS QA | nuovi in `apps/comitato/` | media |
| 7 | `MACRO_COLOR` riconciliato dentro `branding/palette.py` | `core/camperio_core/branding/palette.py` | bassa |
| 8 | `variazioni_*` in valuta locale | `lookthrough.py` | bassa, è un cambio di metodologia visibile all'utente: da confermare |

### Da NON portare (differenze in cui vale il monorepo)

1. Assenza del gate di validazione (`_controlla_matrice`, `_blocco_html`, handler `OracleIndisponibileError`).
2. Assenza di SSO/logout Entra, controllo `X-Auth-Request-User`, `html.escape()`; e il bind su `0.0.0.0`.
3. Fallback DEMO silenzioso in `_connect()`.
4. Il footer PDF pre-fix (split a metà parola, footer 3 mm più basso, sovrapposizione disclaimer/numero pagina).
5. Il cambio dei contatti aziendali (telefono/fax/email), salvo conferma esplicita dell'ufficio.
6. Gli import locali al posto di `camperio_core` (pattern «copia locale»): annullano la propagazione dei fix del core.
7. `_motore/` ed `Earnings Review/` nel repo applicativo.

### Da chiarire con l'autore prima di decidere

- **`ORD` o `MOV`** per ricostruire le quantità alla data AL: il codice nuovo e il changelog del 26/06 si contraddicono.
- **`reports.py`**: superato, refactoring incompiuto, o codice futuro?
- **`blpapi_fetch`**: esiste sulla macchina dell'autore? Senza, `opzioni.py` gira solo su dati seed.
- **Contatti aziendali**: quale set è quello corrente?
- **2 loghi SVG** che differiscono.

---

## 7. Piano di allineamento — GitHub e VM

### Fase 0 — Messa in sicurezza (prima di toccare git)

1. Rotazione della password Oracle col DBA (la credenziale ha circolato in chiaro).
2. Spostare **zip e cartella** fuori dal repo (storage aziendale), poi aggiungere a `.gitignore`: `Analisi portafoglio per comitato*`, `*.zip`, `*.docx`, `*.pptx`, `*.tmp`, `.~lock.*#`, `*.bak*`. (`config.env`, `__pycache__/`, `*.pyc`, `*.csv`, `*.xlsx`, `*.pdf` sono già coperti.)
3. Verificare con `git add -n .` che non resti nulla del drop da stagiare.
4. Bonificare `GUIDA_IT_LOGIN_SSO.md` (username e host) prima di riusarne il contenuto in `docs/`.

⚠️ Cartella e zip sono untracked: **nessun `git clean`** finché non sono archiviati altrove.

### Fase 1 — Hotfix hedge (entro il 18/09, corsia veloce)

Branch dedicato `hotfix/hedge-rollover`, un solo argomento:

- `data_layer.get_portfolio`: aggiunta estrazione `pf["deriv"]`.
- `lookthrough.build_titoli`: sostituzione del blocco `E35126` con `_IDXKW` + `VALOREFUT` con segno + `hedge_dett`, **senza** il fallback `pod` (NUOVA riga 378).
- `lookthrough.build_matrix`: stessa bonifica alla riga 178.
- **Test nuovo** in `apps/comitato/tests/` che verifichi: (a) il netto ≠ lordo con uno short presente, (b) l'hedge sopravvive a un cambio di codice contratto, (c) la put su Euro-Bobl resta esclusa.
- Verifica numerica contro il valore validato: derivati equity su indice = **−328.220 €** su NAV 4.633.877 (8097S, 10/09/2026) = **−7,1%**. Attenzione: `diagnostica_output.txt` del 10/09 riporta `tot_hedge = −327.662`, perché i pesi dei costituenti IUSA non sommano a 100%. Il confronto va fatto con **tolleranza** (≤ 0,5%), non a uguaglianza.

Percorso: PR su GitHub → merge in `main` → deploy su **ANTATEST** → confronto del report Titoli con i numeri validati → deploy su **ANTANA**.

### Fase 2 — Back-port metodologico

Un branch e una PR **per singolo punto** dell'elenco §6, in quell'ordine, ciascuno con il proprio test. Motivo: ogni punto cambia numeri che finiscono davanti al cliente o al comitato; vanno validati uno alla volta contro i casi già verificati (R1450 per il denominatore, 8097S per l'hedge, luglio 2026 per NAV/TWR).

Prima del punto 5 va **ripristinato e verificato il fail-safe Oracle**, altrimenti le nuove sezioni 8/9/10 possono mostrare dati DEMO senza avviso.

### Fase 3 — Nuove funzionalità

`opzioni.py`, `qa.py`, template e CSS, adattati alle convenzioni del monorepo: import da `camperio_core` invece delle copie locali, `html.escape()` sugli output, rotte dietro lo stesso controllo di identità delle altre. `diagnostica_hedge.py` in `tools/`. Decisione su `reports.py` dopo il chiarimento.

### Fase 4 — Chiusura del fork

Il drop non deve restare una linea di sviluppo parallela: alla fine del back-port va concordato con l'autore che **lo sviluppo prosegue solo sul monorepo**, con l'ambiente locale in modalità DEMO (`pip install -e ".[comitato]"`, nessuna variabile `ORA_*`) come previsto dal contratto di piattaforma. Altrimenti fra due mesi il problema si ripresenta identico.

### Sulle VM

Nulla cambia nel modello di deploy: resta quello del monorepo (Docker Compose + nginx + oauth2-proxy/Entra + systemd, ANTATEST prima, ANTANA poi). Il drop non porta infrastruttura da allineare — porta solo codice applicativo. L'ipotesi IIS + Waitress + Task Scheduler descritta in `README_DEPLOY.md`/`GUIDA_IT_LOGIN_SSO.md` è un percorso alternativo mai implementato: adottarla significherebbe ricostruire da zero TLS, SSO e schedulazione già funzionanti in produzione.

---

## 8. Nota sulle date

I mtime del drop **sono reali** (lo zip li conserva; nessun file è datato 12/09, solo lo zip stesso è del 13/09) e vanno dal 25/06 all'11/09/2026. Datazione dei file rilevanti:

| File | mtime | Nota |
|---|---|---|
| `methodology.py`, `reports.py`, `README_DEPLOY.md`, `cache/*.json` | 25-29/06 | base originaria |
| `config.env` | 26/06 | |
| `qa.py`, `report_cliente.py` | 23/07 | fix denominatore |
| `report_comitato.py`, `history/pesi_000.json` | 03/08 | espansione report comitato |
| `app.py`, `opzioni.py`, `.skill` | 17-18/08 | stesso giorno della nascita del monorepo (17/08) |
| `data_layer.py`, `lookthrough.py`, `diagnostica_*` | 10/09 | fix hedge |
| Earnings Review (ORCL, AVAV) | 11/09 | ultimi file |

Coerenti con le date dichiarate nei due changelog — `AGGIORNAMENTO_SKILL_camperio-portfolio.md` (25/06, 26/06, 23/07, 10/09/2026) e `FIX_report_mensile_camperio.md` (luglio 2026) — e con la storia git del monorepo (§1).
