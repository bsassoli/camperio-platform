import pytest

from camperio_core.portfolio.methodology import MACRO_ORDER, macro


@pytest.mark.parametrize("grutit, attesa", [
    ("A10", ("Difesa", "Obbligazionario")),
    ("Z01", ("Difesa", "Liquidità & margini")),
    ("H19", ("Difesa", "Oro fisico")),
    ("H14", ("Difesa", "ETF obbligazionari")),
    ("H06", ("Centro Campo", "Fondi UCITS")),
    ("H20", ("Centro Campo", "Fondi UCITS")),
    ("H10", ("Attacco", "ETF azionari")),
    ("H16", ("Attacco", "ETF azionari")),
    ("H18", ("Attacco", "ETF azionari")),
    ("H23", ("Attacco", "REIT")),
    ("E01", ("Attacco", "Azioni dirette")),
    ("B05", ("Attacco", "Azioni dirette")),
    ("F01", ("Overlay", "Derivati (opzioni)")),
    ("H99", ("Centro Campo", "Fondi/ETF")),
    ("", ("Altro", "Altro")),
    (None, ("Altro", "Altro")),
])
def test_macro_mappa_le_classi(grutit, attesa):
    assert macro(grutit) == attesa


def test_macro_e_case_insensitive():
    assert macro("h19") == ("Difesa", "Oro fisico")


def test_ordine_delle_macro():
    assert MACRO_ORDER == ["Difesa", "Centro Campo", "Attacco", "Overlay", "Altro"]
