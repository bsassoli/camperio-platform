from camperio_core.branding.palette import BLU_CAMPERIO, MACRO_COLOR
from camperio_core.portfolio.methodology import MACRO_ORDER


def test_blu_camperio_ufficiale():
    # il vecchio #1F3864 muore qui (spec §3)
    assert BLU_CAMPERIO == "#151F6D"


def test_ogni_macro_ha_un_colore():
    assert set(MACRO_COLOR) == set(MACRO_ORDER)
    assert MACRO_COLOR["Difesa"] == BLU_CAMPERIO
