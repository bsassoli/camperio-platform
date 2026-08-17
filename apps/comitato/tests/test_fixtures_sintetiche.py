"""Nessun dato reale nelle fixture dell'app: ogni codcli/codabi è sintetico."""
import json
from pathlib import Path

import data_layer as DL


def _tutti_i_codcli(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "codcli":
                yield v
            else:
                yield from _tutti_i_codcli(v)
    elif isinstance(obj, list):
        for x in obj:
            yield from _tutti_i_codcli(x)


def test_fixture_esistono_e_sono_sintetiche():
    files = sorted(Path(DL.FIXTURES).glob("*.json"))
    assert files, "nessuna fixture trovata in " + DL.FIXTURES
    for f in files:
        dati = json.loads(f.read_text(encoding="utf-8"))
        for cod in _tutti_i_codcli(dati):
            assert str(cod).startswith("DEMO"), f"{f.name}: codcli {cod!r} non sintetico"


def test_nessun_file_dati_reali_tra_le_fixture():
    reali = [p.name for p in Path(DL.FIXTURES).iterdir()
             if p.suffix.lower() in (".xlsx", ".xls", ".csv", ".pdf")]
    assert reali == []
