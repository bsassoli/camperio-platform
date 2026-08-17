from camperio_core.portfolio.methodology import CCY_LABEL, currency_of


def test_oro_fuori_dal_computo_fx():
    assert currency_of({"grutit": "H19", "des": "ISHARES PHYSICAL GOLD"}) is None


def test_fondi_ucits_richiedono_lookthrough():
    assert currency_of({"grutit": "H06"}) == "LOOKTHROUGH"
    assert currency_of({"grutit": "H20"}) == "LOOKTHROUGH"


def test_liquidita_dal_nome():
    assert currency_of({"grutit": "Z01", "des": "CONTO USD"}) == "USD"
    assert currency_of({"grutit": "Z01", "des": "LIQUIDITA' EURO"}) == "EUR"


def test_samsung_gdr_e_krw_mai_usd():
    # regola tassativa (skill matrice-valutaria): il sottostante è coreano
    assert currency_of({"grutit": "E01", "bbg": "SMSN LI Equity"}) == "KRW"


def test_ticker_bloomberg_suffisso_borsa():
    assert currency_of({"grutit": "E01", "bbg": "AAPL US Equity"}) == "USD"
    assert currency_of({"grutit": "E01", "bbg": "NESN SW Equity"}) == "CHF"


def test_etf_em_diversificato_va_in_other_em():
    pos = {"grutit": "H10", "bbg": "IEEM LN", "des": "ISHARES MSCI EM UCITS"}
    assert currency_of(pos) == "EM"
    assert CCY_LABEL["EM"] == "Other EM"


def test_bond_da_isin():
    assert currency_of({"grutit": "A10", "isin": "US912828ABC1"}) == "USD"
    assert currency_of({"grutit": "A10", "codisin": "DE0001102345"}) == "EUR"


def test_bond_da_descrizione():
    assert currency_of({"grutit": "A10", "des": "NORWEGIAN GOVT 2030"}) == "NOK"
    assert currency_of({"grutit": "A10", "des": "IBRD SUPRANATIONAL (BRL) 2027"}) == "BRL"


def test_default_prudenziale_eur():
    assert currency_of({"grutit": "A10", "des": "TITOLO IGNOTO"}) == "EUR"
