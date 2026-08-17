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


def test_download_bloccato_409_se_matrice_incoerente(monkeypatch):
    import app as A
    rotta = {"nav": 1000000.0, "gran_tot": {"EUR": 550000.0}, "oro": 0.0,
             "syn": [], "syn_tot": {}, "gran": [], "derivati": [], "fonti": {},
             "azioni": {}, "bond": {}, "totale": {"EUR": 550000.0}}
    monkeypatch.setattr(A.L, "build_matrix", lambda pf, repo: rotta)
    client = A.app.test_client()
    for tipo in ("matrice", "comitato", "cliente1"):
        r = client.get("/download?schema=ANTASIMGEST&codcli=DEMO01&tipo=" + tipo)
        assert r.status_code == 409, tipo
    r = client.get("/api/preview?schema=ANTASIMGEST&codcli=DEMO01&tipo=matrice")
    assert "bloccato dal controllo deterministico" in r.get_json()["html"]
