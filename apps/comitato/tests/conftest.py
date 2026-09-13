"""Ambiente di test dell'app: DEMO forzato e matplotlib senza display."""
import os

import pytest

os.environ.setdefault("MPLBACKEND", "Agg")
for _k in ("ORA_USER", "ORA_PWD", "ORA_DSN"):
    os.environ.pop(_k, None)


@pytest.fixture(autouse=True)
def _storico_pesi_in_tmp(tmp_path_factory, monkeypatch):
    """Lo storico pesi (JSON) non deve mai finire in apps/comitato/history/ durante i test."""
    import data_layer as DL
    monkeypatch.setattr(DL, "_HISTDIR", str(tmp_path_factory.mktemp("history")))
