"""Test del gate di emissione — engine/validation/gate.py.

Il gate aggrega tutti i check: un report incoerente NON deve passare.
"""

from camperio_core.portfolio.validation.gate import validate_report


def test_gate_blocca_report_incoerente():
    report = {
        "nav": 1_000_000,
        "fx": {"EUR": 600_000, "USD": 200_000},  # non somma a NAV
    }
    res = validate_report(report)
    assert not res.ok


def test_gate_passa_report_coerente():
    report = {
        "nav": 1_000_000,
        "fx": {"EUR": 600_000, "USD": 280_000, "Oro": 120_000},
        "cross_page": {"USD_pct": [0.28, 0.28]},
        "positions": [{"name": "X", "ticker": "X US", "weight": 0.01, "currency": "EUR"}],
    }
    res = validate_report(report)
    assert res.ok


def test_gate_blocca_su_bug_riunione_cross_page():
    # Stesso valore USD diverso tra pagine: deve bloccare anche se le somme tornano.
    report = {
        "nav": 1_000_000,
        "fx": {"EUR": 600_000, "USD": 280_000, "Oro": 120_000},
        "cross_page": {"USD_pct": [0.2549, 0.229]},
    }
    res = validate_report(report)
    assert not res.ok


def test_gate_concentrazione_non_blocca():
    # Un single-name sopra soglia genera avviso ma il report passa.
    report = {
        "nav": 1_000_000,
        "fx": {"EUR": 700_000, "USD": 300_000},
        "positions": [{"name": "Big", "ticker": "BIG US", "weight": 0.025, "currency": "USD"}],
    }
    res = validate_report(report)
    assert res.ok
    assert res.warnings
