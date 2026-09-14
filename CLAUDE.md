# camperio-platform — regole per chi lavora nel repo

Questo file è letto da Claude Code a ogni sessione. Vale per tutti, sul Mac di
Bernardino come sul PC del cliente. Le regole qui sotto non sono consigli: sono il
contratto che tiene allineato il codice locale con quello che gira in produzione
(ANTANA) e in test (ANTATEST).

## Lingua

Prosa in italiano: commenti, docstring, documenti, messaggi di commit, PR.
Gli identificatori restano come sono (`eur`, `macro`, `currency_of`, `check_*`):
non si traducono API esistenti. Vedi `README.md`.

## Flusso di lavoro obbligatorio

1. **Mai lavorare su `main`.** Ogni modifica parte da un branch:
   `git switch -c <tipo>/<descrizione-breve>` (tipi: `fix/`, `feat/`, `docs/`).
2. **Test verdi prima di ogni commit.** Dalla radice del repo:
   `.venv/bin/python -m pytest` (Windows: `.venv\Scripts\python -m pytest`).
   Se un test fallisce non si committa e non si "aggiusta" il test per farlo passare:
   si capisce perché fallisce.
3. **Ogni modifica alla logica di calcolo porta con sé un test.** Se cambi
   `apps/comitato/report_comitato.py`, `report_cliente.py`, `lookthrough.py`,
   `data_layer.py` o qualsiasi cosa in `core/camperio_core/`, aggiungi o aggiorna
   un test in `apps/comitato/tests/` o `core/tests/` che dimostri il nuovo
   comportamento. Una PR di calcolo senza test non viene accettata.
4. **Si chiude sempre con una Pull Request verso `main`**, con descrizione in
   italiano: cosa cambia, perché, come è stato verificato. Il merge e il deploy
   sulla VM li fa Bernardino. Nessuna modifica arriva in produzione senza revisione.
5. Commit piccoli e con messaggio descrittivo (`build_matrix: ...`, `hedge: ...`).

## Cosa non toccare senza accordo esplicito con Bernardino

- `deploy/` (Dockerfile, compose, nginx, systemd, TLS) e `docs/DEPLOY.md`.
- L'autenticazione in `apps/comitato/app.py` (header `X-Auth-Request-User`,
  `COMITATO_AUTH`, logout Entra).
- `core/camperio_core/config.py` e `core/camperio_core/oracle/`.
- Le fixture in `apps/comitato/fixtures/` e `core/tests/`: sono dati sintetici
  che i test danno per buoni. Cambiarle cambia il significato dei test.

## Dati e segreti

- **Mai dati reali nel repo.** Niente estrazioni Oracle, Excel dei fondi, CSV
  iShares, report prodotti. Il `.gitignore` blocca `*.xlsx`, `*.csv`, `*.pdf`,
  `*.docx`, `data/`, `outputs/`: non aggirarlo.
- **Mai credenziali in file versionati.** `ORA_USER`, `ORA_PWD`, `ORA_DSN` vivono
  solo nell'ambiente o in un `.env` locale ignorato da git. Vedi `docs/SECRETS.md`.
- Senza `ORA_*` l'app gira in **modalità DEMO** su fixture sintetiche. È il modo
  normale di sviluppare. I numeri DEMO non sono mai da confrontare con quelli veri.

## Aree delicate (leggere prima di modificare)

- **Hedge e derivati** (`apps/comitato/lookthrough.py`): la copertura degli indici
  è ancorata per nome tramite la mappa `_IDXKW` e il segno arriva da `VALOREFUT`.
  Non reintrodurre contratti hardcoded. Test in `tests/test_hedge.py`.
- **Denominatore delle allocazioni** (`report_cliente.py`): la base delle
  allocazioni è separata dal NAV di inizio anno. Non riunificarle.
- **Parser iShares** (`lookthrough.py`, `parse_ishares`): il formato dei CSV cambia
  senza preavviso; ogni modifica va provata su un CSV scaricato di recente.
- **Gate deterministico** (voce 18) su Matrice Valutaria e Sintesi Comitato:
  `core/camperio_core/portfolio/validation/gate.py`. Non aggiungere eccezioni.

## Dove orientarsi

- `README.md`: layout del monorepo e convenzioni.
- `apps/comitato/README.md`: avvio locale dell'app.
- `docs/INSTALLAZIONE-LOCALE.md`: installazione da zero su Windows, Ubuntu, macOS.
- `docs/STATO-MIGRAZIONE.md`: cosa è già allineato con la produzione e cosa no.
- `docs/HANDOFF-VM-HEDGE.md`: contesto sull'ultima validazione dell'hedge.
