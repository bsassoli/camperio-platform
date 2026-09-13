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
