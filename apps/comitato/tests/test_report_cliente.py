import pytest

import data_layer as DL
import report_cliente as RC


def test_percentuali_di_allocazione_su_nav_consfin():
    pf = DL.get_portfolio("ANTASIMGEST", "DEMO01")
    d = RC.build_cliente(pf, DL.REPO)
    nav = pf["meta"]["nav"]
    for nome, val, pct in d["alloc"]:
        assert pct == pytest.approx(val / nav), nome   # mai (nav + der_eq)


def test_nav_base_resta_il_nav_di_inizio_anno():
    """Il denominatore dell'allocazione non deve ombreggiare il NAV di inizio anno:
    il PDF stampa «il valore e' passato da nav_base a nav»."""
    pf = DL.get_portfolio("ANTASIMGEST", "DEMO01")
    d = RC.build_cliente(pf, DL.REPO)
    assert d["nav_base"] == 9_800_000.0        # fixture DEMO01_comitato
    assert d["nav_base"] != d["nav"]
