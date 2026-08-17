# Layer di validazione deterministica

Fase 3 del piano (`piano/2026-06-21-ricostruzione-reportistica.md`). È il controllo
**aritmetico puro** che sterilizza le allucinazioni del modello sui numeri: nessun
report viene emesso senza che questi check passino in verde (requisito A2.1).

## Idea

Il modello (LLM) fa associazioni statistiche, non calcoli. Questo modulo non usa il
modello: data una struttura dati, verifica vincoli deterministici e ritorna errori
o avvisi. È il "layer in più, deterministico" chiesto in riunione.

## Uso

```python
from camperio_core.portfolio.validation import validate_report

report = {
    "nav": 4_672_354,
    "fx": {"EUR": 2_359_000, "USD": 1_191_000, "Oro": 256_028, ...},
    "funds": {"DELTA": {"EUR": 417_000, "USD": 224_000, ...}},
    "fund_quotas": {"DELTA": 757_530},
    "cross_page": {"USD_pct": [0.2549, 0.2549]},   # stesso valore su più pagine
    "positions": [{"name": "...", "ticker": "...", "currency": "...", "weight": 0.01}],
}

res = validate_report(report)
if not res.ok:
    for e in res.errors:
        print("BLOCCANTE:", e.message)   # → non emettere il report
for w in res.warnings:
    print("avviso:", w.message)          # → segnalare al Comitato, ma si può emettere
```

## Due livelli di severità

| Severità | Esempio | Effetto |
|---|---|---|
| **ERROR** | somma valute ≠ NAV; stesso valore diverso tra pagine; Samsung GDR in USD | **blocca** l'emissione |
| **WARNING** | single-name > 2% NAV | segnala, **non** blocca |

## Controlli implementati

- `check_fx_sums_to_nav` — la matrice valutaria (oro incluso) somma al NAV.
- `check_fund_sum_equals_quota` — le valute di un fondo sommano alla quota Camperio.
- `check_cross_page_consistency` — stesso valore identico ovunque compaia (il bug della riunione).
- `check_special_mappings` — Samsung GDR→KRW, IEEM→Other EM, TIPS 2056→USD, oro fuori FX.
- `check_aggregations` — Alphabet A+C aggregati, controllate Samsung escluse, fondo 21st non doppio-contato.
- `check_concentration` — soglie §B8 (avvisi).

## Decisioni di dominio aperte (in cima a `checks.py`)

Le **tolleranze** sono in `CONFIG` e sono una scelta di Edoardo/Bernardino, non un
default tecnico:

- `TOL_FX_SUM_REL = 0.5%` — scarto massimo ammesso sulla somma valute prima di bloccare.
- `TOL_FUND_QUOTA_REL = 0.5%` — idem per la somma per fondo.
- `TOL_CROSS_PAGE = 0.01 p.p.` — quanto due occorrenze dello stesso valore possono differire.

Più strette = più rigore ma più falsi allarmi da arrotondamento; più larghe = rischio di
lasciar passare errori reali. Da calibrare con qualche report reale (Fase 2/4).

## Da estendere (Task 3.2+ del piano)

- Validare la **regola asimmetrica fondi** (§B1) una volta pronto `engine/lookthrough_fx.py` (Fase 2):
  oggi il gate verifica le *somme*, non che la metodologia per-fondo sia quella giusta.
- Cluster top-5 tema, AI totale, USD totale (servono input aggregati).
- Eventuale revisore LLM secondario (Task 3.4 — decisione aperta).

## Test

```
python3 -m pytest
```
