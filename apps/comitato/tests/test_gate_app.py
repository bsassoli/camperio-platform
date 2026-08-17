import data_layer as DL
import lookthrough as L
from app import _controlla_matrice


def test_gate_blocca_matrice_incoerente():
    m = {"nav": 1000000.0, "gran_tot": {"EUR": 700000.0}, "oro": 0.0}
    res = _controlla_matrice(m)
    assert not res.ok
    assert any(f.code == "fx_sum_mismatch" for f in res.errors)


def test_gate_passa_sul_portafoglio_demo():
    pf = DL.get_portfolio("ANTASIMGEST", "DEMO01")
    m = L.build_matrix(pf, DL.REPO)
    assert _controlla_matrice(m).ok
