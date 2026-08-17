"""Nessun dato reale nelle fixture dell'app: ogni codcli e' sintetico, e i nomi
file ammessi sono limitati a un'allowlist. I codabi NON sono controllati qui:
sono chiavi interne del motore di look-through (codici titolo/fondo), non
identificativi di cliente — non ci si aspetta che comincino per DEMO."""
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


def test_solo_file_ammessi_tra_le_fixture():
    for p in Path(DL.FIXTURES).iterdir():
        ammesso = p.name == "contratti.json" or (p.suffix == ".json" and p.stem.startswith("DEMO"))
        assert ammesso, f"{p.name}: nome file non ammesso tra le fixture (allowlist: contratti.json o DEMO*.json)"
