# camperio-platform

La piattaforma che sostituisce le 25 skill Claude e gli 11 repo sparsi di Camperio SIM:
`core/` (libreria condivisa), `jobs/` (schedulati, output servito da nginx), `apps/`
(interattive), `agent/` (dove serve un LLM). Design completo e registro di migrazione
nel repo `bsassoli/migrate-camperio` (`docs/specs/2026-08-16-camperio-platform-design.md`).

## Sviluppo

Serve Python ≥ 3.13. Senza variabili `ORA_*` tutto gira in **modalità DEMO** su fixture
sintetiche — è il contratto di piattaforma: si sviluppa sul Mac senza Oracle.

    python3 -m venv .venv && .venv/bin/pip install pytest
    .venv/bin/python -m pytest

Configurazione: solo variabili d'ambiente via `camperio_core.config` —
vedi `camperio.example.env` e `docs/SECRETS.md`. Tutto in italiano.
