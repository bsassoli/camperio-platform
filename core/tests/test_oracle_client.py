import json
import sys
from pathlib import Path

import pytest

from camperio_core.config import from_env
from camperio_core.oracle.client import FIXTURES, OracleClient, OracleIndisponibileError


def _client_demo():
    return OracleClient(cfg=from_env(env={}))


def test_senza_ora_il_client_e_demo():
    assert _client_demo().mode() == "DEMO"


def test_demo_serve_la_fixture_sintetica():
    rows = _client_demo().query("SELECT CODCLI FROM ANTASIMGEST.CNT", fixture="contratti")
    assert rows


def _trova_codcli(obj, trovati):
    if isinstance(obj, dict):
        if "CODCLI" in obj:
            trovati.append(obj["CODCLI"])
        for v in obj.values():
            _trova_codcli(v, trovati)
    elif isinstance(obj, list):
        for v in obj:
            _trova_codcli(v, trovati)


def test_tutte_le_fixture_sono_sintetiche():
    # garanzia anti-dati-reali: OGNI fixture DEMO deve contenere solo CODCLI "DEMO*"
    percorsi = sorted(Path(FIXTURES).glob("*.json"))
    assert percorsi, "nessuna fixture trovata: la guardia anti-dati-reali non verifica nulla"
    for percorso in percorsi:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
        trovati = []
        _trova_codcli(dati, trovati)
        for codcli in trovati:
            assert str(codcli).startswith("DEMO"), (
                f"{percorso}: CODCLI={codcli!r} non inizia con 'DEMO' — "
                "possibile dato reale di cliente in una fixture"
            )


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


def test_live_oracle_irraggiungibile_solleva_errore_non_fallback_demo(monkeypatch):
    def _connect_fallisce(**kwargs):
        raise Exception("boom")

    stub_oracledb = type("StubOracledb", (), {})()
    stub_oracledb.connect = staticmethod(_connect_fallisce)
    monkeypatch.setitem(sys.modules, "oracledb", stub_oracledb)

    cfg = from_env(env={"ORA_USER": "u", "ORA_PWD": "p", "ORA_DSN": "d"})
    client = OracleClient(cfg=cfg)

    with pytest.raises(OracleIndisponibileError):
        client.query("SELECT 1", fixture="contratti")


def test_live_mappa_le_righe_in_dict(monkeypatch):
    class StubCursor:
        def __init__(self):
            self.description = [("CODCLI",), ("DESCLI",)]
            self.closed = False
            self.execute_args = None

        def execute(self, sql, params):
            self.execute_args = (sql, params)

        def fetchall(self):
            return [("X1", "Cliente")]

        def close(self):
            self.closed = True

    class StubConn:
        def __init__(self):
            self.cursor_stub = StubCursor()

        def cursor(self):
            return self.cursor_stub

    cfg = from_env(env={"ORA_USER": "u", "ORA_PWD": "p", "ORA_DSN": "d"})
    client = OracleClient(cfg=cfg)
    stub_conn = StubConn()
    monkeypatch.setattr(OracleClient, "_connect", lambda self: stub_conn)

    rows = client.query("SELECT CODCLI, DESCLI FROM X")

    assert rows == [{"CODCLI": "X1", "DESCLI": "Cliente"}]
    assert stub_conn.cursor_stub.execute_args == ("SELECT CODCLI, DESCLI FROM X", {})
    assert stub_conn.cursor_stub.closed is True


def test_close_e_context_manager():
    class _StubConn:
        def __init__(self): self.closed = False
        def close(self): self.closed = True

    stub = _StubConn()
    client = _client_demo()
    client._conn = stub
    client.close()
    assert stub.closed and client._conn is None
    client.close()  # idempotente: nessuna eccezione, _conn resta None
    assert client._conn is None

    with _client_demo() as c:
        assert c.mode() == "DEMO"
