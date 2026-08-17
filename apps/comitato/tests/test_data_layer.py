import pytest

import data_layer as DL


def test_mode_demo_senza_variabili_ora():
    assert DL.mode() == "DEMO"


def test_list_contratti_solo_sintetici():
    cs = DL.list_contratti()
    assert cs and all(c["codcli"].startswith("DEMO") for c in cs)
    gruppi = {c["codcli"]: c["gruppo"] for c in cs}
    assert gruppi["DEMO01"] == "Gestione"
    assert gruppi["DEMO02"] == "RTO"


def test_get_portfolio_demo01_quadra_col_nav():
    pf = DL.get_portfolio("ANTASIMGEST", "DEMO01")
    nav = pf["meta"]["nav"]
    assert nav == 10130000.0
    assert abs(sum(p["valmer"] for p in pf["positions"]) - nav) < 1


def test_resolve_period_default():
    rp = DL.resolve_period("ANTASIMGEST", "DEMO01", None, None)
    assert rp["ok"] and rp["al"] == "2026-08-14" and rp["dal"] == "2026-08-07" and not rp.get("warn")


def test_get_portfolio_demo_mancante_errore_chiaro():
    with pytest.raises(ValueError, match="DEMO"):
        DL.get_portfolio("ANTASIMN", "DEMO02")


def test_config_live_con_oracle_morto_solleva_mai_demo(monkeypatch):
    import sys
    import data_layer as DLmod
    from camperio_core.config import from_env
    from camperio_core.oracle.client import OracleClient, OracleIndisponibileError

    class _OracledbRotto:
        @staticmethod
        def connect(**kw):
            raise Exception("listener giu'")

    monkeypatch.setitem(sys.modules, "oracledb", _OracledbRotto)
    cfg = from_env(env={"ORA_USER": "u", "ORA_PWD": "p", "ORA_DSN": "d"})
    monkeypatch.setattr(DLmod, "_client", OracleClient(cfg=cfg))
    with pytest.raises(OracleIndisponibileError):
        DLmod.list_contratti()
