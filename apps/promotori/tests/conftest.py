"""Ambiente di test dell'app Promotori: DEMO forzato, niente auth, cache vuota."""
import os

import pytest

for _k in ("ORA_USER", "ORA_PWD", "ORA_DSN"):
    os.environ.pop(_k, None)


@pytest.fixture(autouse=True)
def _ambiente_pulito(monkeypatch):
    from promotori import app as modulo
    monkeypatch.delenv("PROMOTORI_AUTH", raising=False)
    modulo.svuota_cache()
    yield
    modulo.svuota_cache()
