import textwrap

import pytest

import lookthrough as L

_IT = textwrap.dedent("""\
    Ticker,Nome,Settore,Asset Class,Valore di mercato,Ponderazione (%),ISIN
    AAPL,APPLE INC,Informatica,Azionario,"1.000,00","6,27",US0378331005
    XXX,CASH EUR,Liquidità,Liquidità,"1,00","0,10",-
    """)
_EN_COLONNE_SPOSTATE = textwrap.dedent("""\
    Ticker,Name,Sector,Asset Class,Market Value,Weight (%),Notional Value,Location
    AAPL,APPLE INC,Information Technology,Equity,"1,000.00",6.27,"1,000.00",United States
    MSFT,MICROSOFT CORP,Information Technology,Equity,"1,000.00",5.5,"1,000.00",United States
    """)


def test_formato_italiano(tmp_path):
    p = tmp_path / "IUSA_2026-09-10.csv"; p.write_text("intestazione\n\n" + _IT, encoding="utf-8")
    assert L.parse_ishares(str(p)) == [("APPLE INC", pytest.approx(0.0627))]


def test_formato_inglese(tmp_path):
    p = tmp_path / "IUSA_2026-09-10.csv"; p.write_text(_EN_COLONNE_SPOSTATE, encoding="utf-8")
    assert L.parse_ishares(str(p)) == [("APPLE INC", pytest.approx(0.0627)), ("MICROSOFT CORP", pytest.approx(0.055))]


def test_senza_riga_ticker_lista_vuota(tmp_path):
    p = tmp_path / "IUSA_x.csv"; p.write_text("niente\n", encoding="utf-8")
    assert L.parse_ishares(str(p)) == []


@pytest.mark.parametrize("s,v", [("6,27", 0.0627), ("6.27", 0.0627), ("1.234,5%", 12.345), ("0", 0.0)])
def test_pct_ishares(s, v):
    assert L._pct_ishares(s) == pytest.approx(v)
