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


def test_caratterizzazione_etf_senza_ticker_domicilio_irlandese_va_in_eur():
    # Limite noto: un ETF a esposizione USD ma domiciliato IE, senza ticker
    # Bloomberg, finisce in EUR via ISIN. Il look-through del piano 3 dovrà
    # emettere un warning per le posizioni che cadono qui.
    assert currency_of({"grutit": "H14", "isin": "IE00B4WXJJ64"}) == "EUR"


def test_caratterizzazione_liquidita_chf_va_in_eur():
    # La regola Z gestisce solo USD/EUR: un conto CHF oggi finisce in EUR.
    assert currency_of({"grutit": "Z01", "des": "CONTO CORRENTE CHF"}) == "EUR"


def test_caratterizzazione_tag_valuta_vale_anche_per_azioni():
    assert currency_of({"grutit": "E01", "des": "FONDO SPECIALE (USD) CLASSE A"}) == "USD"
