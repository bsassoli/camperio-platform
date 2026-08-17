from camperio_core.config import from_env


def test_senza_variabili_ora_e_demo():
    cfg = from_env(env={})
    assert cfg.mode == "DEMO"
    assert not cfg.live


def test_con_tutte_le_ora_e_live():
    cfg = from_env(env={"ORA_USER": "svc", "ORA_PWD": "x", "ORA_DSN": "host:1521/srv"})
    assert cfg.mode == "LIVE"
    assert cfg.live


def test_ora_parziali_restano_demo():
    assert from_env(env={"ORA_USER": "svc"}).mode == "DEMO"
    assert from_env(env={"ORA_USER": "svc", "ORA_PWD": "x"}).mode == "DEMO"


def test_data_dir_default_e_override():
    assert str(from_env(env={}).data_dir) == "/var/lib/camperio"
    assert str(from_env(env={"CAMPERIO_DATA": "/tmp/dati"}).data_dir) == "/tmp/dati"
