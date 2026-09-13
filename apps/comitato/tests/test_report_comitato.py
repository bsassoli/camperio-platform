# -*- coding: utf-8 -*-
"""Report comitato ampliato: storico pesi su JSON, sezioni 3-bis/8/9/10, fail-safe Oracle."""
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
    monkeypatch.setattr(DL, "dettaglio_mensile", _boom)
    pf = DL.get_portfolio("ANTASIMGEST", "DEMO01")
    with pytest.raises(OracleIndisponibileError):
        RC.build_comitato(pf, DL.REPO)


_XSS = "<img src=x onerror=1>"


def _riga(nome, stato="normale", **kw):
    r = {"nome": nome, "isin": "", "ccy": "EUR", "peso_dal": 0.10, "peso_al": 0.12,
         "perf_eur": 0.05, "perf_loc": 0.04, "div": False, "stato": stato}
    r.update(kw)
    r["d"] = r["peso_al"] - r["peso_dal"]
    return r


def _dett_sintetico():
    """Stessa forma che DL.dettaglio_mensile ritorna in LIVE (qui costruita a mano:
    in DEMO non esiste dettaglio e non si inventano dati)."""
    az = [_riga("APPLE INC", div=True),
          _riga("NVIDIA CORP", "nuova", peso_dal=0.0, perf_eur=None),
          _riga("INTEL CORP", "chiusa", peso_al=0.0, perf_eur=None),
          _riga(_XSS)]
    fe = [_riga("ISHARES S&P 500"), _riga("DELTA UCITS", "nuova", peso_dal=0.0, perf_eur=None)]
    oro = [_riga("ORO FISICO " + _XSS)]
    return {"azioni": az, "fondi_etf": fe, "oro": oro,
            "az_tot_dal": sum(r["peso_dal"] for r in az), "az_tot_al": sum(r["peso_al"] for r in az),
            "fe_tot_dal": sum(r["peso_dal"] for r in fe), "fe_tot_al": sum(r["peso_al"] for r in fe)}


def _d_con_dettaglio():
    pf = DL.get_portfolio("ANTASIMGEST", "DEMO01")
    d = RC.build_comitato(pf, DL.REPO)
    d["dett"] = _dett_sintetico()
    return d


def test_sezioni_8_9_10_mostrano_righe_stati_e_totali():
    html = RC.comitato_html(_d_con_dettaglio())
    assert "8. Dettaglio azioni" in html and "9. Fondi ed ETF" in html and "10. Oro fisico" in html
    assert "APPLE INC" in html and "ISHARES S&amp;P 500" in html and "ORO FISICO" in html
    assert "(nuova)" in html and "(chiusa)" in html
    assert "TOTALE AZIONI" in html and "TOTALE FONDI/ETF" in html
    assert "non disponibile" not in html.lower()


def test_nomi_da_oracle_sono_escapati_nell_html():
    d = _d_con_dettaglio()
    d["bench"] = _XSS
    d["comp"][0]["macro"] = _XSS
    d["top"][0]["name"] = _XSS
    d["ctop"][0]["name"] = _XSS
    d["trades"][0]["nome"] = _XSS
    d["contrib_class"][0]["macro"] = _XSS
    d["sett"][0] = (_XSS, 0.5)
    html = RC.comitato_html(d)
    assert "<img" not in html
    assert "&lt;img" in html


def test_comitato_word_con_dettaglio_non_solleva(tmp_path):
    out = tmp_path / "x.docx"
    assert RC.comitato_word(_d_con_dettaglio(), str(out)) == str(out)
    assert out.exists()
