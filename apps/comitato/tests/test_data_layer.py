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


@pytest.mark.parametrize("nome,atteso", [
    ("S&P 500 MINI FUT SET-26", True),
    ("UBER TECHNOLOGIES CALL 90 DIC-26", True),          # single-name: azionario
    ("EURO BOBL OTT-26 PUT 114.25", False),
    ("IL CALL US ULTRA 10Y", False),                      # tasso USD (fixture DEMO01_comitato)
    ("EUR/USD FX FUT DIC-26", False),
    ("BRENT CRUDE OIL FUT", False),
    ("GOLDMAN SACHS GROUP CALL 500", True),               # single-name: non e' l'oro
    ("CORNING INC PUT 40", True),                         # single-name: non e' il mais
    ("GOLD FUT DIC-26", False),                           # commodity vera
])
def test_is_equity_deriv_per_sottostante(nome, atteso):
    assert DL._is_equity_deriv(nome) is atteso


def test_storico_pesi_segue_la_env_comitato_history(tmp_path, monkeypatch):
    """In produzione lo storico sta sul volume persistente: la directory va risolta
    a ogni chiamata, non congelata all'import del modulo."""
    monkeypatch.setenv("COMITATO_HISTORY", str(tmp_path))
    DL.update_weight_history("DEMOX", "2026-08-14", 5_000_000.0, 10_000_000.0)
    DL.update_class_weight_history("DEMOX", "2026-08-14", {"Azioni": 0.5}, 10_000_000.0)
    assert (tmp_path / "pesi_DEMOX.json").exists()
    assert (tmp_path / "pesi_classi_DEMOX.json").exists()


def test_scrittura_storico_atomica_senza_file_temporanei(tmp_path, monkeypatch):
    monkeypatch.setenv("COMITATO_HISTORY", str(tmp_path))
    DL.update_weight_history("DEMOX", "2026-08-14", 5_000_000.0, 10_000_000.0)
    DL.update_class_weight_history("DEMOX", "2026-08-14", {"Azioni": 0.5}, 10_000_000.0)
    assert [p.name for p in tmp_path.iterdir() if p.suffix == ".tmp"] == []


def test_storico_corrotto_non_di_tipo_lista_ritorna_vuoto(tmp_path, monkeypatch):
    monkeypatch.setenv("COMITATO_HISTORY", str(tmp_path))
    (tmp_path / "pesi_DEMOX.json").write_text("null", encoding="utf-8")
    (tmp_path / "pesi_classi_DEMOX.json").write_text('{"date": "x"}', encoding="utf-8")
    assert DL.load_weight_history("DEMOX") == []
    assert DL.load_class_weight_history("DEMOX") == []
