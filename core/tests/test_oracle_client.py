import pytest

from camperio_core.config import from_env
from camperio_core.oracle.client import OracleClient


def _client_demo():
    return OracleClient(cfg=from_env(env={}))


def test_senza_ora_il_client_e_demo():
    assert _client_demo().mode() == "DEMO"


def test_demo_serve_la_fixture_sintetica():
    rows = _client_demo().query("SELECT CODCLI FROM ANTASIMGEST.CNT", fixture="contratti")
    assert rows
    # garanzia anti-dati-reali: le fixture contengono solo contratti DEMO*
    assert all(str(r["CODCLI"]).startswith("DEMO") for r in rows)


def test_demo_senza_nome_fixture_e_errore_chiaro():
    with pytest.raises(ValueError, match="DEMO"):
        _client_demo().query("SELECT 1 FROM DUAL")


def test_demo_fixture_mancante_e_errore_chiaro():
    with pytest.raises(FileNotFoundError):
        _client_demo().query("SELECT 1 FROM DUAL", fixture="inesistente")


def test_fixtures_dir_personalizzabile(tmp_path):
    (tmp_path / "saldi.json").write_text('[{"SALDO": 42}]', encoding="utf-8")
    client = OracleClient(cfg=from_env(env={}), fixtures_dir=tmp_path)
    assert client.query("SELECT SALDO FROM X", fixture="saldi") == [{"SALDO": 42}]
