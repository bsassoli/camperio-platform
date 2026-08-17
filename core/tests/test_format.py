from camperio_core.render.format import eur, num, pct


def test_eur_formato_italiano():
    assert eur(1234567.89) == "€ 1.234.568"
    assert eur(1234567.89, dec=2) == "€ 1.234.567,89"


def test_eur_input_non_numerico():
    assert eur(None) == "—"
    assert eur("abc") == "—"


def test_pct_segno_e_virgola():
    assert pct(1.234) == "+1,23%"
    assert pct(-0.5) == "-0,50%"
    assert pct(3.0, dec=1, seg=False) == "3,0%"
    assert pct(None) == "—"


def test_num():
    assert num(1234.5, dec=1) == "1.234,5"
    assert num(1000000) == "1.000.000"
    assert num("x") == "—"
