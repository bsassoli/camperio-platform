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
    # R1450, ANTASIMN 22/07/2026: esposizione 70.039,56 su NAV 103.199,94 = 67,87%
    # (nota: il brief riporta 67,86%; l'aritmetica esatta arrotonda a 67,87 - vedi report)
    assert round(70039.56 / 103199.94 * 100, 2) == 67.87
