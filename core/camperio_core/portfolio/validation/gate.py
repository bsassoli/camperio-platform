"""Gate di emissione report — aggrega tutti i controlli deterministici.

Regola operativa (da codificare anche nella skill `camperio-portfolio`):
PRIMA di scrivere qualunque report, eseguire `validate_report`. Se `ok` è False,
correggere e NON emettere. I WARNING vanno riportati ma non bloccano.
"""

from __future__ import annotations

from camperio_core.portfolio.validation.checks import (
    ValidationResult,
    check_aggregations,
    check_concentration,
    check_cross_page_consistency,
    check_fund_sum_equals_quota,
    check_special_mappings,
    check_fx_sums_to_nav,
)


def validate_report(report: dict) -> ValidationResult:
    """Esegue tutti i controlli applicabili al `report` e ne aggrega i risultati.

    Chiavi riconosciute (tutte opzionali — si validano solo le sezioni presenti):
      - nav: float
      - fx: dict[str, float]                 → check_fx_sums_to_nav
      - funds: dict[str, dict]               → {nome_fondo: {valuta: €}} con quote in `fund_quotas`
      - fund_quotas: dict[str, float]
      - cross_page: dict[str, list[float]]   → check_cross_page_consistency
      - positions: list[dict]                → mapping speciali, aggregazioni, concentrazione
    """
    result = ValidationResult()

    nav = report.get("nav")
    fx = report.get("fx")
    if fx is not None and nav is not None:
        result = result.merge(check_fx_sums_to_nav(fx, nav))

    funds = report.get("funds") or {}
    quotas = report.get("fund_quotas") or {}
    for nome, fund_fx in funds.items():
        if nome in quotas:
            result = result.merge(check_fund_sum_equals_quota(fund_fx, quotas[nome]))

    cross_page = report.get("cross_page")
    if cross_page:
        result = result.merge(check_cross_page_consistency(cross_page))

    positions = report.get("positions")
    if positions:
        result = result.merge(check_special_mappings(positions))
        result = result.merge(check_aggregations(positions))
        result = result.merge(check_concentration(positions))

    return result
