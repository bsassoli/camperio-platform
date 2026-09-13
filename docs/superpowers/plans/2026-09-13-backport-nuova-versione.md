# Back-port della «Nuova versione» nel monorepo — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Portare nel monorepo, un punto alla volta e con test, le correzioni metodologiche della linea del cliente (hedge robusto al rollover, denominatore NAV, parser iShares, report comitato ampliato), senza importare le differenze in cui vale il monorepo (gate, SSO, fail-safe Oracle, footer, contatti).

**Architecture:** Il monorepo (`core/camperio_core` + `apps/comitato`) resta l'unica linea di sviluppo e l'unico modello di deploy. Ogni punto del §6 del censimento diventa un branch + PR con il proprio test, validato contro i casi già verificati (8097S per l'hedge, R1450 per il denominatore). Il codice della NUOVA viene copiato per blocchi identificati per riga, adattato agli import da `camperio_core`, e mai copiato dove la NUOVA è più debole (fallback `pod`, fallback DEMO silenzioso, copie locali di `methodology`/`format`).

**Tech Stack:** Python 3.13, Flask, pytest (`.venv/bin/python -m pytest`, 103 test verdi al 13/09/2026), oracledb (solo LIVE), Docker Compose + nginx + oauth2-proxy su ANTATEST/ANTANA.

**Spec:** `CENSIMENTO-NUOVA-VERSIONE.md` (versione corretta del 13/09/2026). Sezioni di riferimento: §2 (urgenze), §3 (diff file per file), §6 (riepilogo decisionale), §7 (fasi).

## Global Constraints

- **Scadenza dura:** il future S&P 500 MINI SET-26 scade il **18/09/2026**. La Fase 1 deve essere in produzione su ANTANA prima.
- **Sorgente NUOVA:** `<DROP>/Comitato_App/`, dove `<DROP>` è la cartella archiviata **fuori dal repo** dalla Task 0.1 (default `~/camperio-drop-2026-09/Analisi portafoglio per comitato`). I riferimenti a riga nel piano sono a quei file, mtime 10/09/2026 per `data_layer.py`/`lookthrough.py`, 23/07 per `report_cliente.py`, 03/08 per `report_comitato.py`.
- **Mai portare** (§6 «Da NON portare»): `_connect()` con fallback DEMO, bind `0.0.0.0`, rimozione di `html.escape`/gate/handler 503, footer pre-fix, contatti `30322100`/`camperio.net`, import locali `import methodology as M` / `from methodology import eur, pct`, il fallback `pod` di `build_titoli` (NUOVA riga 372-378).
- **Import obbligatori nel monorepo:** `from camperio_core.portfolio import methodology as M`, `from camperio_core.render.format import eur, pct`, `from camperio_core.oracle.client import OracleIndisponibileError`.
- **Modalità test:** DEMO forzato da `apps/comitato/tests/conftest.py` (nessuna variabile `ORA_*`); i test non toccano mai Oracle. Fixture in `apps/comitato/fixtures/`.
- **Numeri di validazione:** 8097S al 10/09/2026: derivati equity su indice = −328.220 € su NAV 4.633.877 (−7,1%); `diagnostica_output.txt` dà `tot_hedge = −327.662` per pesi IUSA < 100% → confronto con **tolleranza 0,5%**. R1450 (ANTASIMN 22/07/2026): esposizione azionaria 70.039,56 / NAV 103.199,94 = 67,86%.
- **Commit:** un branch e una PR per task di Fase 1 e per ogni task di Fase 2; messaggi in italiano come nel log esistente; nessun file dati (`.csv`, `.xlsx`, `.pdf`, `.json` di cliente) committato, salvo le fixture sintetiche `DEMO01*`.
- **Decisioni aperte che bloccano task specifiche** (da chiedere all'autore, non da presumere): ORD vs MOV per le quantità alla data AL; destino di `reports.py`; esistenza di `blpapi_fetch`; set di contatti aziendali corrente; i 2 SVG. Le task che ne dipendono sono marcate **[GATE]**.

---

## Struttura dei file

| File | Ruolo nel piano |
|---|---|
| `.gitignore` | esclude drop, zip, formati Office e scarti (Task 0.1) |
| `apps/comitato/data_layer.py` | `get_portfolio` → `pf["deriv"]` (1.1); `comitato_extra` → `der_eq` via `_is_equity_deriv` (2.1); storico pesi e `dettaglio_mensile` (2.3) |
| `apps/comitato/lookthrough.py` | `_IDXKW` a livello modulo, `build_titoli` sezione 4 (1.2), `build_matrix` derivati (1.3), `parse_ishares` (2.2), diciture HTML/Excel/Word |
| `apps/comitato/report_cliente.py` | `base = nav` (2.1) |
| `apps/comitato/report_comitato.py` | sezioni 3-bis, 8, 9, 10 (2.3) |
| `apps/comitato/fixtures/DEMO01.json` | aggiunta chiave `deriv` (1.1) |
| `apps/comitato/fixtures/DEMO01_comitato.json` | `deriv_pos[*].equity` (2.1) |
| `apps/comitato/tests/test_hedge.py` | nuovo: contratto dell'hedge (1.1, 1.2, 1.3) |
| `apps/comitato/tests/test_ishares.py` | nuovo: parser header-driven (2.2) |
| `apps/comitato/tests/test_report_cliente.py` | nuovo: denominatore (2.1) |
| `apps/comitato/tests/test_report_comitato.py` | nuovo: sezioni aggiuntive e fail-safe (2.3) |
| `docs/STATO-MIGRAZIONE.md` | registro di ogni deploy (1.4) |

---

# Fase 0 — Messa in sicurezza (prima di qualsiasi `git add`)

### Task 0.1: Archiviare il drop fuori dal repo e chiudere `.gitignore`

**Files:**
- Modify: `.gitignore`
- Move: `Analisi portafoglio per comitato/` e `Analisi portafoglio per comitato.zip` → `~/camperio-drop-2026-09/`

**Interfaces:**
- Produces: la variabile di comodo `DROP="$HOME/camperio-drop-2026-09/Analisi portafoglio per comitato"` usata da tutte le task successive.

- [ ] **Step 1: Verificare lo stato attuale (deve mostrare cartella e zip untracked)**

Run: `cd /Users/bernardino/camperio-platform && git status --short`
Expected: le tre righe `?? "Analisi portafoglio per comitato.zip"`, `?? "Analisi portafoglio per comitato/"`, `?? CENSIMENTO-NUOVA-VERSIONE.md`.

- [ ] **Step 2: Spostare cartella e zip fuori dal repo (nessun `git clean`)**

```bash
mkdir -p "$HOME/camperio-drop-2026-09"
mv "/Users/bernardino/camperio-platform/Analisi portafoglio per comitato" "$HOME/camperio-drop-2026-09/"
mv "/Users/bernardino/camperio-platform/Analisi portafoglio per comitato.zip" "$HOME/camperio-drop-2026-09/"
ls "$HOME/camperio-drop-2026-09"
```
Expected: la cartella e lo zip elencati nella nuova posizione; `git status --short` nel repo mostra solo `?? CENSIMENTO-NUOVA-VERSIONE.md`.

- [ ] **Step 3: Aggiungere a `.gitignore` le esclusioni mancanti**

Aggiungere in coda a `.gitignore`:

```gitignore
# drop del cliente (archiviato fuori repo, mai committare)
Analisi portafoglio per comitato*
*.zip
*.skill
# formati Office e scarti
*.docx
*.pptx
*.tmp
.~lock.*#
*.bak*
```

- [ ] **Step 4: Verificare con un dry-run che nulla del drop sia stagiabile**

Run: `cd /Users/bernardino/camperio-platform && git add -n . && git check-ignore -v "Analisi portafoglio per comitato.zip" "x.docx" "y.tmp"`
Expected: `git add -n .` elenca solo `.gitignore`, `CENSIMENTO-NUOVA-VERSIONE.md`, `docs/superpowers/plans/2026-09-13-backport-nuova-versione.md`; `check-ignore` stampa una regola per ciascuno dei tre nomi.

- [ ] **Step 5: Commit**

```bash
git add .gitignore CENSIMENTO-NUOVA-VERSIONE.md docs/superpowers/plans/2026-09-13-backport-nuova-versione.md
git commit -m "docs: censimento nuova versione corretto, piano di back-port, gitignore per drop e formati Office"
```

### Task 0.2: Azioni umane fuori dal codice (da tracciare, non automatizzabili)

- [ ] **Step 1:** Chiedere al DBA la **rotazione della password Oracle** presente in `<DROP>/Comitato_App/config.env` (è circolata in chiaro dentro uno zip). Aggiornare `docs/SECRETS.md` con la data di rotazione, non con il valore.
- [ ] **Step 2:** Bonificare `<DROP>/Comitato_App/GUIDA_IT_LOGIN_SSO.md` righe 63-65 (username e host) prima di riusarne qualsiasi parte in `docs/`.
- [ ] **Step 3:** Inviare all'autore le cinque domande **[GATE]** dei Global Constraints in un unico messaggio, con la scadenza del 18/09 in evidenza; il piano di Fase 1 non dipende da nessuna risposta.

---

# Fase 1 — Hotfix hedge (branch `hotfix/hedge-rollover`, entro il 18/09)

### Task 1.1: `pf["deriv"]` in `get_portfolio` + fixture DEMO

**Files:**
- Modify: `apps/comitato/data_layer.py:262-280` (blocco `pod = _q(...)` … `return {`)
- Modify: `apps/comitato/fixtures/DEMO01.json` (aggiunta chiave `deriv`)
- Test: `apps/comitato/tests/test_hedge.py` (nuovo)

**Interfaces:**
- Produces: `pf["deriv"]` = lista di `{"des": str, "grutit": str, "isin": str, "valorefut": float}`; `valorefut` è già in EUR e con segno (negativo per gli short). Consumato da Task 1.2 e 1.3.

- [ ] **Step 1: Creare il branch**

```bash
cd /Users/bernardino/camperio-platform && git checkout -b hotfix/hedge-rollover
```

- [ ] **Step 2: Scrivere il test che fallisce (fixture DEMO senza `deriv`)**

Creare `apps/comitato/tests/test_hedge.py`:

```python
"""Contratto dell'hedge su indice: robusto al rollover, con segno, mai per codice contratto."""
import os
import textwrap

import pytest

import data_layer as DL
import lookthrough as L


def test_get_portfolio_demo01_espone_deriv_con_segno():
    pf = DL.get_portfolio("ANTASIMGEST", "DEMO01")
    assert "deriv" in pf
    sp = [d for d in pf["deriv"] if "S&P" in d["des"]]
    bobl = [d for d in pf["deriv"] if "BOBL" in d["des"]]
    assert len(sp) == 1 and sp[0]["valorefut"] < 0        # future short: delta negativo
    assert len(bobl) == 1 and bobl[0]["valorefut"] > 0    # put su tasso: presente ma non azionario
    assert set(sp[0]) == {"des", "grutit", "isin", "valorefut"}
```

- [ ] **Step 3: Eseguire il test e verificare che fallisca**

Run: `.venv/bin/python -m pytest apps/comitato/tests/test_hedge.py::test_get_portfolio_demo01_espone_deriv_con_segno -v`
Expected: FAIL con `AssertionError` su `"deriv" in pf`.

- [ ] **Step 4: Aggiungere `deriv` alla fixture `DEMO01.json`**

Con Python, per non rompere il JSON a mano (valore coerente con `der_eq = -492957.0` già in `DEMO01_comitato.json`):

```python
import json
p = "apps/comitato/fixtures/DEMO01.json"
d = json.load(open(p, encoding="utf-8"))
d["deriv"] = [
    {"des": "S&P 500 MINI FUT SET-26", "grutit": "G12", "isin": "", "valorefut": -492957.0},
    {"des": "EURO BOBL OTT-26 PUT 114.25", "grutit": "F19", "isin": "DE000F3ZL359", "valorefut": 105576.31},
]
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
```

- [ ] **Step 5: Aggiungere l'estrazione LIVE in `get_portfolio`**

In `apps/comitato/data_layer.py`, subito dopo il blocco `pod = _q(...)` (riga 262-263) inserire:

```python
    # Derivati detenuti direttamente (future/opzioni) con esposizione delta (VALOREFUT, in EUR e CON SEGNO):
    # servono a nettare gli hedge su indice nel report Titoli lordo/netto. Mai per codice contratto.
    drv = _q("SELECT t.DESTITB des, t.GRUTIT g, NVL(t.CODISIN,' ') isin, NVL(w.VALOREFUT,0) vf "
             "FROM " + schema + ".WCTDD w JOIN " + schema + ".TIT t ON t.CODABI=w.CODABI "
             "WHERE w.CODCLI=:c AND (t.GRUTIT LIKE 'F%' OR t.GRUTIT LIKE 'G%') AND NVL(w.VALOREFUT,0)<>0",
             {"c": codcli})
```

e nel dizionario di ritorno, dopo la voce `"pod": [...]`, aggiungere:

```python
        "deriv": [{"des": r["DES"] or "", "grutit": r["G"] or "", "isin": (r.get("ISIN") or "").strip(),
                   "valorefut": float(r["VF"] or 0)} for r in drv],
```

- [ ] **Step 6: Eseguire il test e la suite intera**

Run: `.venv/bin/python -m pytest apps/comitato/tests/test_hedge.py -v && .venv/bin/python -m pytest -q`
Expected: il nuovo test PASS; suite `104 passed`.

- [ ] **Step 7: Commit**

```bash
git add apps/comitato/data_layer.py apps/comitato/fixtures/DEMO01.json apps/comitato/tests/test_hedge.py
git commit -m "Estrazione pf['deriv']: delta dei derivati con segno da WCTDD, fixture DEMO01"
```

### Task 1.2: `build_titoli` — hedge da `pf["deriv"]`, senza `E35126`, senza fallback `pod`

**Files:**
- Modify: `apps/comitato/lookthrough.py:241` (`_IDX_ETF`), `:332-335` (sezione 4), `:368-372` (return), `:488` e `:508` (diciture HTML), più le diciture Excel/Word corrispondenti (`grep -n "hedge S&P" apps/comitato/lookthrough.py`)
- Test: `apps/comitato/tests/test_hedge.py`

**Interfaces:**
- Consumes: `pf["deriv"]` (Task 1.1).
- Produces: `build_titoli(pf, repo_dir)` ritorna in più `"hedge_dett": [{"nome": str, "valorefut": float, "indice": str}]`; `"hedge_notional"` diventa la somma con segno dei `valorefut` agganciati. Costante di modulo `_IDXKW: list[tuple[str, str]]` (keyword nel nome → ticker ETF). Consumato da Task 1.3 e 2.3.

- [ ] **Step 1: Scrivere i test che falliscono**

Aggiungere in fondo a `apps/comitato/tests/test_hedge.py`:

```python
_IUSA_CSV = textwrap.dedent("""\
    iShares Core S&P 500 UCITS ETF
    Data,10/set/2026

    Ticker,Nome,Settore,Asset Class,Valore di mercato,Ponderazione (%),Valore nominale,Nominale,ISIN,Prezzo,Località,Borsa,Valuta di mercato
    AAPL,APPLE INC,Informatica,Azionario,"1.000,00","60,00","1.000,00","1.000,00",US0378331005,"100,00",Stati Uniti,NASDAQ,USD
    MSFT,MICROSOFT CORP,Informatica,Azionario,"1.000,00","40,00","1.000,00","1.000,00",US5949181045,"100,00",Stati Uniti,NASDAQ,USD
    XXX,CASH EUR,Liquidità,Liquidità,"1,00","0,00","1,00","1,00",-,"1,00",-,-,EUR
    """)


@pytest.fixture()
def repo(tmp_path):
    (tmp_path / "IUSA_2026-09-10.csv").write_text(_IUSA_CSV, encoding="utf-8")
    return str(tmp_path)


def _pf(deriv, pod=None):
    return {
        "meta": {"nav": 1_000_000.0},
        "positions": [{"codabi": "A1", "des": "APPLE INC", "grutit": "E03", "valmer": 100_000.0,
                       "valorefut": 100_000.0, "bbg": "", "isin": "", "ccy": "USD", "macro": "Attacco", "sub": ""}],
        "pod": pod or [],
        "deriv": deriv,
    }


def _row(t, name):
    return next(r for r in t["rows"] if r["name"].upper() == name)


def test_short_su_indice_rende_il_netto_diverso_dal_lordo(repo):
    t = L.build_titoli(_pf([{"des": "S&P 500 MINI FUT SET-26", "grutit": "G12", "isin": "", "valorefut": -100_000.0}]), repo)
    apple = _row(t, "APPLE INC")
    assert apple["lordo"] == pytest.approx(100_000.0)
    assert apple["hedge"] == pytest.approx(-60_000.0)
    assert apple["netto"] == pytest.approx(40_000.0)
    assert _row(t, "MICROSOFT CORP")["hedge"] == pytest.approx(-40_000.0)
    assert t["tot_hedge"] == pytest.approx(-100_000.0)
    assert t["hedge_dett"] == [{"nome": "S&P 500 MINI FUT SET-26", "valorefut": -100_000.0, "indice": "IUSA"}]


def test_hedge_sopravvive_al_rollover_del_contratto(repo):
    t = L.build_titoli(_pf([{"des": "S&P 500 MINI FUT DIC-26", "grutit": "G12", "isin": "", "valorefut": -100_000.0}]), repo)
    assert t["tot_hedge"] == pytest.approx(-100_000.0)


def test_put_su_bobl_resta_esclusa_dal_netto(repo):
    t = L.build_titoli(_pf([
        {"des": "S&P 500 MINI FUT SET-26", "grutit": "G12", "isin": "", "valorefut": -100_000.0},
        {"des": "EURO BOBL OTT-26 PUT 114.25", "grutit": "F19", "isin": "DE000F3ZL359", "valorefut": 105_576.31},
    ]), repo)
    assert t["tot_hedge"] == pytest.approx(-100_000.0)
    assert [h["indice"] for h in t["hedge_dett"]] == ["IUSA"]


def test_future_long_su_indice_aumenta_il_netto(repo):
    t = L.build_titoli(_pf([{"des": "EURO STOXX 50 FUT DIC-26", "grutit": "G12", "isin": "", "valorefut": 50_000.0}]), repo)
    # nessun CSV EUE nel repo di test: il derivato è riconosciuto ma non ripartibile, quindi non entra nel netto
    assert t["tot_hedge"] == pytest.approx(0.0)
    assert t["hedge_dett"] == []


def test_senza_deriv_nessun_fallback_su_pod(repo):
    pod = [{"codabi": "E35126", "des": "E35126", "pnet": -1, "val": 7643.75, "scad": "2026-09-18", "tipo": ""}]
    t = L.build_titoli(_pf([], pod=pod), repo)
    assert t["tot_hedge"] == 0.0
    assert t["hedge_dett"] == []


def test_nessun_codice_contratto_nel_sorgente():
    src = open(os.path.join(os.path.dirname(L.__file__), "lookthrough.py"), encoding="utf-8").read()
    assert "E35126" not in src
    assert "1.1358" not in src
```

- [ ] **Step 2: Eseguire e verificare che falliscano**

Run: `.venv/bin/python -m pytest apps/comitato/tests/test_hedge.py -v`
Expected: `test_short_su_indice_*`, `test_hedge_sopravvive_*`, `test_put_su_bobl_*`, `test_nessun_codice_contratto_*` FAIL (KeyError `hedge_dett` / asserzione sul sorgente); `test_senza_deriv_*` FAIL perché il vecchio codice aggancia `E35126` dal `pod`.

- [ ] **Step 3: Aggiungere `_IDXKW` a livello di modulo**

In `apps/comitato/lookthrough.py`, subito dopo la riga 241 (`_IDX_ETF = {...}`), inserire:

```python
# Derivati su indice del portafoglio: keyword nel nome (TIT.DESTITB) → ETF dell'indice.
# Mai per codice contratto (cambia a ogni roll). Ordine: keyword più specifiche prima.
_IDXKW = [("EURO STOXX", "EUE"), ("STOXX", "EUE"), ("SX5E", "EUE"),
          ("DAX", "EXS1"), ("FTSE", "ISF"), ("UKX", "ISF"), ("SMI", "EXI1"),
          ("MSCI EM", "IEEM"), ("EM INDEX", "IEEM"), ("MXEF", "IEEM"),
          ("S&P", "IUSA"), ("SPX", "IUSA"), ("MINI FUT", "IUSA"),
          ("E-MINI", "IUSA"), ("EMINI", "IUSA"), ("MICRO", "IUSA")]
```

- [ ] **Step 4: Sostituire la sezione 4 di `build_titoli`**

Sostituire le righe 332-335 (`# 4) HEDGE S&P short del portafoglio` … `for nome, w in H["IUSA"]: A(nome, "hedge", -notional * w, None)`) con:

```python
    # 4) DERIVATI SU INDICE detenuti dal portafoglio (future/opzioni): esposizione delta
    #    (WCTDD.VALOREFUT, già in EUR e CON SEGNO → negativa per gli short) ripartita sui
    #    costituenti dell'ETF dell'indice. Robusto ai roll; esclude tasso/FX/commodity/single-name.
    notional = 0.0; hedge_dett = []
    for dv in pf.get("deriv") or []:
        nm = (dv.get("des") or "").upper(); vf = float(dv.get("valorefut") or 0.0)
        if not vf:
            continue
        etf = next((e for kw, e in _IDXKW if kw in nm), None)
        if not etf or not H.get(etf):
            continue  # non su indice azionario, o ETF senza CSV nel repository: non entra nel netto
        notional += vf
        hedge_dett.append({"nome": dv.get("des"), "valorefut": vf, "indice": etf})
        for nome, w in H[etf]: A(nome, "hedge", vf * w, None)
```

- [ ] **Step 5: Esporre `hedge_dett` nel return**

Alla riga del return (`"n": len(rows), "hedge_notional": notional, "fonti": ...`) aggiungere `"hedge_dett": hedge_dett,` dopo `"hedge_notional": notional,`.

- [ ] **Step 6: Aggiornare le diciture**

`grep -n "hedge S&P\|Hedge S&P" apps/comitato/lookthrough.py` e sostituire, in HTML (riga ~488 e ~508), Excel e Word: «netto = lordo − hedge S&P» → «netto = lordo + delta derivati su indice del portafoglio (future/opzioni short o long)»; l'intestazione di colonna «Hedge S&P» → «Delta indice». Non toccare `_F1`/`_F2`.

- [ ] **Step 7: Eseguire i test e la suite**

Run: `.venv/bin/python -m pytest apps/comitato/tests/test_hedge.py -v && .venv/bin/python -m pytest -q`
Expected: tutti PASS tranne `test_nessun_codice_contratto_nel_sorgente` (resta `E35126` in `build_matrix`, riga 178: lo chiude Task 1.3). Suite: 1 failed, il resto passed.

- [ ] **Step 8: Commit**

```bash
git add apps/comitato/lookthrough.py apps/comitato/tests/test_hedge.py
git commit -m "build_titoli: hedge da pf['deriv'] con segno, ripartito per indice; rimosso E35126 e nozionale manuale"
```

### Task 1.3: `build_matrix` — stessa bonifica della riga 178

**Files:**
- Modify: `apps/comitato/lookthrough.py:176-180`
- Test: `apps/comitato/tests/test_hedge.py`

**Interfaces:**
- Consumes: `pf["deriv"]`, `_IDXKW` (Task 1.2).
- Produces: `build_matrix(...)["derivati"]` = lista di `(etichetta, {valuta: importo_eur})`, una voce per derivato su indice azionario, importo = `valorefut` con segno. La voce `E35492` (call US Ultra 10Y) resta invariata.

- [ ] **Step 1: Scrivere il test che fallisce**

Aggiungere in fondo a `apps/comitato/tests/test_hedge.py`:

```python
def test_build_matrix_elenca_i_derivati_su_indice_dal_deriv(repo):
    pf = DL.get_portfolio("ANTASIMGEST", "DEMO01")
    pf = dict(pf, deriv=[{"des": "S&P 500 MINI FUT DIC-26", "grutit": "G12", "isin": "", "valorefut": -100_000.0}],
              pod=[])
    m = L.build_matrix(pf, repo)
    voci = {lbl: d for lbl, d in m["derivati"] if "S&P" in lbl}
    assert len(voci) == 1
    (d,) = voci.values()
    assert d == {"USD": -100_000.0}
```

- [ ] **Step 2: Eseguire e verificare che fallisca**

Run: `.venv/bin/python -m pytest apps/comitato/tests/test_hedge.py::test_build_matrix_elenca_i_derivati_su_indice_dal_deriv -v`
Expected: FAIL, `len(voci) == 0` (il vecchio codice non trova `E35126` nel `pod` svuotato).

- [ ] **Step 3: Sostituire le righe 176-180 di `build_matrix`**

Aggiungere dopo `_IDXKW` (Task 1.2, Step 3) la valuta di ciascun ETF indice:

```python
_IDX_CCY = {"IUSA": "USD", "EUE": "EUR", "EXS1": "EUR", "ISF": "GBP", "EXI1": "CHF", "IEEM": "USD"}
```

e sostituire in `build_matrix` il blocco

```python
    # derivati informativi (non FX)
    der = []
    spf = next((x for x in pf.get("pod", []) if x.get("codabi") == "E35126" or "S&P" in str(x.get("des", ""))), None)
    if spf:
        der.append(("Future S&P 500 short (hedge equity)", {"USD": -abs(spf.get("pnet", 0)) * (spf.get("val") or 0) * 50 / 1.1358}))
```

con

```python
    # derivati informativi (non FX): delta dei derivati su indice azionario, con segno, da WCTDD.VALOREFUT
    der = []
    for dv in pf.get("deriv") or []:
        nm = (dv.get("des") or "").upper(); vf = float(dv.get("valorefut") or 0.0)
        etf = next((e for kw, e in _IDXKW if kw in nm), None)
        if vf and etf:
            der.append((f"{dv.get('des')} ({'short' if vf < 0 else 'long'}, hedge equity)", {_IDX_CCY[etf]: vf}))
```

- [ ] **Step 4: Eseguire tutta la suite**

Run: `.venv/bin/python -m pytest -q`
Expected: tutti PASS, incluso `test_nessun_codice_contratto_nel_sorgente` e i test del gate (`test_gate_app.py`, `test_preview_matrice_contiene_le_regole_chiave`), perché la fixture DEMO01 ora ha `deriv` e la riga informativa continua a comparire.

- [ ] **Step 5: Commit**

```bash
git add apps/comitato/lookthrough.py apps/comitato/tests/test_hedge.py
git commit -m "build_matrix: derivati su indice da pf['deriv'], rimosso l'ultimo E35126"
```

### Task 1.4: Validazione numerica, PR, deploy ANTATEST → ANTANA

**Files:**
- Modify: `docs/STATO-MIGRAZIONE.md` (registro)

- [ ] **Step 1: Aprire la PR**

```bash
git push -u origin hotfix/hedge-rollover
gh pr create --title "Hotfix hedge: aggancio per nome e VALOREFUT con segno, robusto al roll del 18/09" \
  --body "Porta nel monorepo la correzione del 10/09 (censimento §2.1, §3.3). Rimuove E35126 e il nozionale manuale da build_titoli e build_matrix. Test: apps/comitato/tests/test_hedge.py. Validazione su ANTATEST contro 8097S al 10/09: derivati equity su indice = -328.220 EUR su NAV 4.633.877 (-7,1%), tolleranza 0,5%."
```

- [ ] **Step 2: Deploy su ANTATEST** seguendo `docs/DEPLOY.md` §4.3 (`docker compose build` + `docker compose up -d comitato`, mai nudo; nginx resta com'è).

- [ ] **Step 3: Verifica numerica sul container**

```bash
docker compose exec comitato python -c "
import data_layer as DL, lookthrough as L
pf = DL.get_portfolio('ANTASIMGEST', '8097S')
t = L.build_titoli(pf, DL.REPO)
print('mode', DL.mode(), 'nav', pf['meta']['nav'])
print('deriv', pf['deriv'])
print('hedge_dett', t['hedge_dett'])
print('tot_hedge', round(t['tot_hedge']), 'tot_netto', round(t['tot_netto']), 'tot_diretto+fondi+indici', round(t['tot_diretto']+t['tot_fondi']+t['tot_indici']))
"
```
Expected: `mode LIVE`; `deriv` contiene il future S&P (nome con la scadenza corrente, **non** un codice) con `valorefut ≈ -328220` e la put Bobl con valore positivo; `hedge_dett` ha una sola voce con `indice IUSA`; `tot_hedge` entro lo 0,5% del `valorefut` del future (al 10/09 valeva −327.662); `tot_netto < tot_diretto+fondi+indici`. Se il future è già stato rollato, il nome cambia ma il test deve valere ugualmente: è esattamente il caso coperto.

- [ ] **Step 4: Confronto visivo** del report Titoli su ANTATEST: colonna «Delta indice» popolata, «% netto» < «% lordo» sui nomi USA, riga informativa del future nella Matrice.

- [ ] **Step 5: Merge e deploy su ANTANA** (stessa procedura), poi ripetere lo Step 3 sul container di produzione.

- [ ] **Step 6: Registrare in `docs/STATO-MIGRAZIONE.md`** data, commit, i numeri letti allo Step 3 su entrambe le VM, e commit:

```bash
git add docs/STATO-MIGRAZIONE.md
git commit -m "docs: stato — hotfix hedge in produzione, numeri validati su 8097S"
```

---

# Fase 2 — Back-port metodologico (un branch/PR per task, in quest'ordine)

Nota: il fail-safe Oracle è già nel monorepo e già testato (`test_config_live_con_oracle_morto_solleva_mai_demo`). Non va «ripristinato»: va solo **non toccato** e, in Task 2.3, rispettato dal try/except delle nuove sezioni.

### Task 2.1: Denominatore = NAV e `_is_equity_deriv` (branch `feat/denominatore-nav`)

**Files:**
- Modify: `apps/comitato/report_cliente.py:121`
- Modify: `apps/comitato/data_layer.py:385-395` (`comitato_extra`, LIVE)
- Modify: `apps/comitato/fixtures/DEMO01_comitato.json` (`deriv_pos[*].equity`)
- Test: `apps/comitato/tests/test_report_cliente.py` (nuovo), `apps/comitato/tests/test_data_layer.py`

**Interfaces:**
- Produces: `DL._is_equity_deriv(nome: str) -> bool`; `comitato_extra(...)["deriv_pos"][i]["equity"]: bool`; `der_eq` = somma dei `valorefut` con `equity=True`. `build_cliente(...)["alloc"]` percentuali su `nav`.

- [ ] **Step 1: Test del classificatore (fallisce: funzione assente)**

Aggiungere a `apps/comitato/tests/test_data_layer.py`:

```python
@pytest.mark.parametrize("nome,atteso", [
    ("S&P 500 MINI FUT SET-26", True),
    ("UBER TECHNOLOGIES CALL 90 DIC-26", True),          # single-name: azionario
    ("EURO BOBL OTT-26 PUT 114.25", False),
    ("IL CALL US ULTRA 10Y", False),                      # tasso USD (fixture DEMO01_comitato)
    ("EUR/USD FX FUT DIC-26", False),
    ("BRENT CRUDE OIL FUT", False),
])
def test_is_equity_deriv_per_sottostante(nome, atteso):
    assert DL._is_equity_deriv(nome) is atteso
```

- [ ] **Step 2: Eseguire e verificare che fallisca**

Run: `.venv/bin/python -m pytest apps/comitato/tests/test_data_layer.py -k equity -v`
Expected: FAIL, `AttributeError: module 'data_layer' has no attribute '_is_equity_deriv'`.

- [ ] **Step 3: Aggiungere il classificatore a `data_layer.py`** (prima di `def comitato_extra`), copiando `_DERIV_NONEQ` e `_is_equity_deriv` da `<DROP>/Comitato_App/data_layer.py` righe 381-389 e aggiungendo `"ULTRA"` e `" 10Y"` alla tupla (la fixture DEMO01 ha un'opzione «US ULTRA 10Y» che la lista della NUOVA classificherebbe erroneamente come azionaria):

```python
# Derivati AZIONARI vs non-azionari (FX, tasso/bond, commodity): classificazione per sottostante dal nome.
_DERIV_NONEQ = ("CURR", "EUR-", "EUR/", "/USD", "USD/", "CHF/", "EUR CHF", "FX FUT", "FX FUTURE",
                "NOTE", "T-NOTE", "TNOTE", "BOND", "BOBL", "BUND", "BUXL", "SCHATZ", "BTP", "GILT", " OAT",
                "EURIBOR", "SOFR", "10YR", "10-YEAR", "2YR", "5YR", "30YR", "LONG BOND", "ULTRA", " 10Y",
                "CRUDE", "OIL", "BRENT", "COFFEE", "CORN", "COPPER", "ALUMIN", "GOLD", "SILVER",
                "WHEAT", "SUGAR", " GAS", "COCOA", "SOYBEAN", "GASOLINE", "PLATIN", "PALLAD", "NICKEL", "ZINC")

def _is_equity_deriv(nome):
    n = (nome or "").upper()
    return not any(k in n for k in _DERIV_NONEQ)
```

- [ ] **Step 4: Sostituire il calcolo SQL di `der_eq` in `comitato_extra`**

Eliminare la query `der = _q("SELECT NVL(SUM(NVL(w.VALOREFUT,0)),0) de ...")` e la riga `der_eq = float(der[0]["DE"]) if der else 0.0` (righe 385-390); dopo `deriv_pos = [...]` (riga 395) aggiungere la chiave `equity` e il calcolo Python:

```python
    deriv_pos = [{"nome": r["NOME"], "isin": r.get("ISIN") or "", "valorefut": float(r["VF"]), "valmer": float(r["VM"]),
                  "equity": _is_equity_deriv(r["NOME"])} for r in dp]
    # delta dei derivati AZIONARI per sottostante (indici E single-name; esclusi FX, tasso, commodity)
    der_eq = sum(p["valorefut"] for p in deriv_pos if p["equity"])
```

Nella fixture `DEMO01_comitato.json` aggiungere `"equity": true` alla voce S&P e `"equity": false` alla voce «IL CALL US ULTRA 10Y» (`der_eq` resta `-492957.0`, coerente).

- [ ] **Step 5: Test del denominatore (fallisce sul vecchio `base`)**

Creare `apps/comitato/tests/test_report_cliente.py`:

```python
import pytest

import data_layer as DL
import report_cliente as RC


def test_percentuali_di_allocazione_su_nav_consfin():
    pf = DL.get_portfolio("ANTASIMGEST", "DEMO01")
    d = RC.build_cliente(pf, DL.REPO)
    nav = pf["meta"]["nav"]
    for nome, val, pct in d["alloc"]:
        assert pct == pytest.approx(val / nav), nome   # mai (nav + der_eq)


def test_denominatore_r1450_caso_validato():
    # R1450, ANTASIMN 22/07/2026: esposizione 70.039,56 su NAV 103.199,94 = 67,86%
    assert round(70039.56 / 103199.94 * 100, 2) == 67.86
```

- [ ] **Step 6: Eseguire e verificare che il primo fallisca**

Run: `.venv/bin/python -m pytest apps/comitato/tests/test_report_cliente.py -v`
Expected: `test_percentuali_di_allocazione_su_nav_consfin` FAIL (con `der_eq = -492957` la base vecchia è `nav + der_eq`).

- [ ] **Step 7: Cambiare la riga 121 di `report_cliente.py`**

```python
    base = nav  # denominatore = patrimonio CONSFIN (come Antana): % = esposizione / NAV (fix 23/07/2026, validato su R1450)
```

- [ ] **Step 8: Suite intera**

Run: `.venv/bin/python -m pytest -q`
Expected: tutti PASS. Se `test_preview_di_ogni_report[cliente1]` o il gate cambiano esito, i numeri del report cliente sono cambiati: atteso per costruzione, verificare a mano che le quattro percentuali sommino come prima e siano tutte più alte in valore assoluto.

- [ ] **Step 9: Commit, PR, validazione**

```bash
git add apps/comitato/data_layer.py apps/comitato/report_cliente.py apps/comitato/fixtures/DEMO01_comitato.json apps/comitato/tests/test_data_layer.py apps/comitato/tests/test_report_cliente.py
git commit -m "Report cliente: denominatore = NAV CONSFIN; derivati azionari classificati per sottostante (fix 23/07)"
```
Validazione su ANTATEST: report cliente R1450 (ANTASIMN) alla data 22/07/2026 → Azioni **67,86%**.

### Task 2.2: `parse_ishares` guidata dall'header (branch `feat/ishares-header`)

**Files:**
- Modify: `apps/comitato/lookthrough.py:200-216`
- Test: `apps/comitato/tests/test_ishares.py` (nuovo)

**Interfaces:**
- Produces: `L._pct_ishares(s: str) -> float`; `L.parse_ishares(path) -> list[tuple[str, float]]` invariata nella firma, accetta formati IT/EN e colonne in ordine diverso.

- [ ] **Step 1: Test che fallisce (formato EN e colonna extra)**

Creare `apps/comitato/tests/test_ishares.py`:

```python
import textwrap

import pytest

import lookthrough as L

_IT = textwrap.dedent("""\
    Ticker,Nome,Settore,Asset Class,Valore di mercato,Ponderazione (%),ISIN
    AAPL,APPLE INC,Informatica,Azionario,"1.000,00","6,27",US0378331005
    XXX,CASH EUR,Liquidità,Liquidità,"1,00","0,10",-
    """)
_EN_COLONNE_SPOSTATE = textwrap.dedent("""\
    Ticker,Name,Sector,Asset Class,Market Value,Weight (%),Notional Value,Location
    AAPL,APPLE INC,Information Technology,Equity,"1,000.00",6.27,"1,000.00",United States
    MSFT,MICROSOFT CORP,Information Technology,Equity,"1,000.00",5.5,"1,000.00",United States
    """)


def test_formato_italiano(tmp_path):
    p = tmp_path / "IUSA_2026-09-10.csv"; p.write_text("intestazione\n\n" + _IT, encoding="utf-8")
    assert L.parse_ishares(str(p)) == [("APPLE INC", pytest.approx(0.0627))]


def test_formato_inglese(tmp_path):
    p = tmp_path / "IUSA_2026-09-10.csv"; p.write_text(_EN_COLONNE_SPOSTATE, encoding="utf-8")
    assert L.parse_ishares(str(p)) == [("APPLE INC", pytest.approx(0.0627)), ("MICROSOFT CORP", pytest.approx(0.055))]


def test_senza_riga_ticker_lista_vuota(tmp_path):
    p = tmp_path / "IUSA_x.csv"; p.write_text("niente\n", encoding="utf-8")
    assert L.parse_ishares(str(p)) == []


@pytest.mark.parametrize("s,v", [("6,27", 0.0627), ("6.27", 0.0627), ("1.234,5%", 12.345), ("0", 0.0)])
def test_pct_ishares(s, v):
    assert L._pct_ishares(s) == pytest.approx(v)
```

- [ ] **Step 2: Eseguire e verificare che fallisca**

Run: `.venv/bin/python -m pytest apps/comitato/tests/test_ishares.py -v`
Expected: `test_formato_inglese` FAIL (il parser a indici fissi vuole `Azionario`), `test_pct_ishares` FAIL (`AttributeError`).

- [ ] **Step 3: Sostituire `parse_ishares`** con le righe 200-244 di `<DROP>/Comitato_App/lookthrough.py` (`_pct_ishares` + `parse_ishares` header-driven), copiate tal quali.

- [ ] **Step 4: Suite intera**

Run: `.venv/bin/python -m pytest -q`
Expected: tutti PASS, inclusi i test di `test_hedge.py` (il CSV sintetico di Task 1.2 ha le intestazioni `Nome`/`Asset Class`/`Ponderazione (%)` riconosciute da entrambi i parser).

- [ ] **Step 5: Commit e PR**

```bash
git add apps/comitato/lookthrough.py apps/comitato/tests/test_ishares.py
git commit -m "parse_ishares guidata dall'header: regge formati IT/EN e colonne aggiunte"
```

### Task 2.3: Report comitato ampliato (sezioni 3-bis, 8, 9, 10; storico pesi) (branch `feat/comitato-esteso`)

**Files:**
- Modify: `apps/comitato/data_layer.py` (storico JSON, `_fx_case`, `dettaglio_mensile`)
- Modify: `apps/comitato/report_comitato.py` (`_it`, `_peso_azioni_storico`, `_pesi_inizio_mese`, `build_comitato`, `comitato_word`, `comitato_html`)
- Modify: `.gitignore` (`apps/comitato/history/`)
- Test: `apps/comitato/tests/test_report_comitato.py` (nuovo)

**Interfaces:**
- Consumes: `build_titoli(...)["tot_hedge"]` (già usato), `DL.contract_info` (già presente in VECCHIA riga 438).
- Produces: `DL.load_weight_history(codcli) -> list[dict]`, `DL.update_weight_history(codcli, date, eq_eur, nav)`, `DL.load_class_weight_history(codcli)`, `DL.update_class_weight_history(codcli, date, pesi_pct, nav)`, `DL.dettaglio_mensile(schema, codcli, dal, al, nav_dal, nav_al) -> dict | None` (None in DEMO); `build_comitato(...)` ritorna in più `paz`, `dett`, `mese_info`, `codcli`, `descli`.

- [ ] **Step 1: Test di contratto (fallisce: funzioni assenti)**

Creare `apps/comitato/tests/test_report_comitato.py`:

```python
import json

import pytest

import data_layer as DL
import report_comitato as RC


@pytest.fixture(autouse=True)
def history_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(DL, "_HISTDIR", str(tmp_path))   # mai scrivere in fixtures/ o nel repo


def test_storico_pesi_accumula_e_sovrascrive_la_stessa_data():
    DL.update_weight_history("DEMO01", "2026-08-07", 5_000_000.0, 10_000_000.0)
    DL.update_weight_history("DEMO01", "2026-08-14", 5_100_000.0, 10_130_000.0)
    DL.update_weight_history("DEMO01", "2026-08-14", 5_200_000.0, 10_130_000.0)
    h = DL.load_weight_history("DEMO01")
    assert [r["date"] for r in h] == ["2026-08-07", "2026-08-14"]
    assert h[-1]["eq"] == 5_200_000.0 and h[-1]["pct"] == pytest.approx(5_200_000.0 / 10_130_000.0)


def test_build_comitato_demo_ha_le_nuove_chiavi_e_dett_none():
    pf = DL.get_portfolio("ANTASIMGEST", "DEMO01")
    d = RC.build_comitato(pf, DL.REPO)
    for k in ("paz", "dett", "mese_info", "codcli", "descli"):
        assert k in d, k
    assert d["dett"] is None            # DEMO: nessun dettaglio mensile, mai dati finti
    assert d["codcli"] == "DEMO01"


def test_html_in_demo_dichiara_il_dettaglio_non_disponibile():
    pf = DL.get_portfolio("ANTASIMGEST", "DEMO01")
    html = RC.comitato_html(RC.build_comitato(pf, DL.REPO))
    assert "Andamento peso azionario" in html
    assert "non disponibile" in html.lower()


def test_dettaglio_mensile_non_maschera_oracle_indisponibile(monkeypatch):
    from camperio_core.oracle.client import OracleIndisponibileError
    def _boom(*a, **k): raise OracleIndisponibileError("giu'")
    pf = DL._load_cache("DEMO01")     # letto prima di forzare mode()=LIVE
    monkeypatch.setattr(DL, "dettaglio_mensile", _boom)
    monkeypatch.setattr(DL, "mode", lambda: "LIVE")
    with pytest.raises(OracleIndisponibileError):
        RC.build_comitato(pf, DL.REPO)
```

- [ ] **Step 2: Eseguire e verificare che fallisca**

Run: `.venv/bin/python -m pytest apps/comitato/tests/test_report_comitato.py -v`
Expected: 4 FAIL (`AttributeError` su `_HISTDIR`/`update_weight_history`, `KeyError` sulle nuove chiavi).

- [ ] **Step 3: Portare in `data_layer.py`** da `<DROP>/Comitato_App/data_layer.py`:
  - righe 392-443 (`_HISTDIR`, `_hist_file`, `load_weight_history`, `update_weight_history`, `_hist_class_file`, `load_class_weight_history`, `update_class_weight_history`), con `_HISTDIR = os.path.join(HERE, "history")` e **senza** gli `except Exception: pass`: sostituirli con `except OSError as e: print("[data_layer] storico pesi non scrivibile:", e)`;
  - righe 509-593 (`_fx_case`, `dettaglio_mensile`) tal quali. La guardia `if mode() == "DEMO": return None` resta.
  - Aggiungere `apps/comitato/history/` a `.gitignore` e un `apps/comitato/history/.gitkeep`.

- [ ] **Step 4: Portare in `report_comitato.py`** da `<DROP>/Comitato_App/report_comitato.py`:
  - righe 23-58 (`_it`, `_peso_azioni_storico`, `_pesi_inizio_mese`);
  - dentro `build_comitato` (righe 60-128 della NUOVA vs 21-62 della VECCHIA): `contract_info`, storico pesi di classe, colonna «% inizio mese», `eq_dir_etf` (E* + H10/H16/H18/H23), e la chiamata a `dettaglio_mensile` scritta così, non come nella NUOVA:

```python
    from camperio_core.oracle.client import OracleIndisponibileError
    try:
        dett = DL.dettaglio_mensile(meta["schema"], meta["codcli"], dal, al, nav_dal, nav_al)
    except OracleIndisponibileError:
        raise                         # fail-safe di piattaforma: mai un report parziale su Oracle giù
    except Exception:
        import traceback; traceback.print_exc(); dett = None
```
  - `comitato_word` e `comitato_html`: sezioni «3-bis Andamento peso azionario», «8 Azioni», «9 Fondi ed ETF», «10 Oro fisico» (NUOVA righe 169, 215-230 e le corrispondenti in `comitato_html`). Quando `d["dett"] is None` ogni sezione 8/9/10 stampa la riga «Dettaglio mensile non disponibile in questa modalità» invece di una tabella vuota. Ogni stringa proveniente da Oracle passa da `html.escape()` nel ramo HTML.
  - Titolo: `f"{d['descli']} ({d['codcli']})"` al posto di «Linea Camperio».

- [ ] **Step 5: Suite intera**

Run: `.venv/bin/python -m pytest -q`
Expected: tutti PASS, incluso `test_preview_di_ogni_report[comitato]` e i test del gate.

- [ ] **Step 6: Commit e PR; validazione su ANTATEST**

```bash
git add apps/comitato/data_layer.py apps/comitato/report_comitato.py apps/comitato/history/.gitkeep .gitignore apps/comitato/tests/test_report_comitato.py
git commit -m "Report comitato: andamento peso azionario, dettaglio mensile azioni/fondi/oro, storico pesi su JSON"
```
Validazione: report comitato 8097S su ANTATEST con `dal`/`al` di settembre; sezioni 8/9/10 popolate in LIVE; spegnere Oracle di test (o usare un DSN sbagliato) e verificare **HTTP 503**, non un report senza sezioni.

### Task 2.4 [GATE]: `variazioni_*` in valuta locale

Bloccata finché l'ufficio non conferma il cambio di metodologia visibile all'utente (§6 punto 8). Quando sbloccata: copiare `build_variazioni` righe 740-761 della NUOVA (`var_loc`, `loc_dal`, `loc_al`) mantenendo `var` in EUR; test su una riga sintetica con `loc_dal=100, loc_al=110, e_dal=100, e_al=105` → `var_loc == 0.10`, `var == 0.05`; diciture HTML/Excel/Word aggiornate a «var. in valuta».

### Task 2.5: `MACRO_COLOR` nel core

**Files:**
- Modify: `core/camperio_core/branding/palette.py`, `core/tests/test_palette.py`

`palette.py` ha già i cinque colori con gli stessi esadecimali (`#151F6D`, `#2E5A9E`, `#FF8200`, `#666666`, `#999999`): verificare con `diff <(grep -o '#[0-9A-F]\{6\}' core/camperio_core/branding/palette.py | sort) <(grep -o '#[0-9A-F]\{6\}' "$DROP/Comitato_App/methodology.py" | sort)`. Se il diff è vuoto, la task si chiude senza modifiche: i nuovi moduli (Fase 3) importano da `camperio_core.branding.palette` e mai da una copia locale.

---

# Fase 3 — Nuove funzionalità [GATE]

`opzioni.py`, `qa.py`, `templates/opzioni.html`, CSS del pannello QA, `diagnostica_hedge.py` in `tools/`. Piano separato, da scrivere **dopo** le risposte dell'autore su `blpapi_fetch` (senza il modulo `opzioni.py` gira solo sui seed `iv_data.json`) e su `reports.py`. Vincoli già noti per quel piano: rotte dietro lo stesso controllo di identità di `app.py`, `html.escape()` su ogni stringa da query string o da Oracle (la NUOVA riflette `dal`/`al` e `str(e)` in `innerHTML`), import da `camperio_core`, nessun `print()` come unico segnale di errore.

# Fase 4 — Chiusura del fork

Dopo il merge di Fase 2: concordare con l'autore che lo sviluppo prosegue solo sul monorepo in modalità DEMO locale (`.venv/bin/pip install -e ".[comitato]"`, nessuna `ORA_*`), registrare la decisione in `docs/STATO-MIGRAZIONE.md`, e archiviare `<DROP>` sullo storage aziendale con la nota «superato dal monorepo al <data>».
