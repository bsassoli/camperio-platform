"""Test del layer di validazione deterministica — engine/validation/checks.py.

Ogni test codifica una regola di `requisiti/requisiti-e-regole.md` (Parte B/C)
e ne verifica il rispetto su dati SINTETICI (mai dati clienti reali).
"""

from camperio_core.portfolio.validation.checks import (
    check_aggregations,
    check_concentration,
    check_cross_page_consistency,
    check_fund_sum_equals_quota,
    check_fx_sums_to_nav,
    check_special_mappings,
)


# --- C: coerenza aritmetica ---------------------------------------------------

def test_fx_somma_a_nav_entro_tolleranza():
    fx = {"EUR": 600_000, "USD": 229_000, "CHF": 50_000, "Other EM": 121_000}
    res = check_fx_sums_to_nav(fx, nav=1_000_000)
    assert res.ok


def test_fx_non_somma_a_nav_e_errore():
    fx = {"EUR": 600_000, "USD": 200_000}  # somma 800k != 1M
    res = check_fx_sums_to_nav(fx, nav=1_000_000)
    assert not res.ok
    assert res.errors


def test_fund_sum_uguale_quota_ok():
    # DELTA: somma valute deve essere = quota Camperio (€757.530)
    delta = {"EUR": 417_000, "USD": 224_000, "GBP": 70_000, "CHF": 34_000, "NOK": 12_530}
    res = check_fund_sum_equals_quota(delta, quota=757_530)
    assert res.ok


def test_fund_sum_diverso_da_quota_errore():
    delta = {"EUR": 417_000, "USD": 224_000}  # somma 641k != 757.530
    res = check_fund_sum_equals_quota(delta, quota=757_530)
    assert not res.ok
    assert res.errors


def test_cross_page_incoerenza_usd_e_errore():
    # Il bug della riunione: USD 25,49% a pagina 1 ma 22,9% a pagina 3.
    occ = {"USD_pct": [0.2549, 0.229]}
    res = check_cross_page_consistency(occ)
    assert not res.ok
    assert any("USD_pct" in e.message for e in res.errors)


def test_cross_page_coerente_ok():
    occ = {"USD_pct": [0.2549, 0.2549], "EUR_pct": [0.505, 0.505]}
    res = check_cross_page_consistency(occ)
    assert res.ok


# --- B4: mapping strumenti speciali ------------------------------------------

def test_samsung_gdr_in_usd_e_errore():
    positions = [{"name": "Samsung Electronics GDR", "ticker": "SMSN LI", "currency": "USD"}]
    res = check_special_mappings(positions)
    assert not res.ok


def test_samsung_gdr_in_krw_ok():
    positions = [{"name": "Samsung Electronics GDR", "ticker": "SMSN LI", "currency": "KRW"}]
    res = check_special_mappings(positions)
    assert res.ok


def test_ieem_in_usd_e_errore():
    positions = [{"name": "iShares MSCI EM", "ticker": "IEEM", "currency": "USD"}]
    res = check_special_mappings(positions)
    assert not res.ok


def test_tips_2056_deve_essere_usd():
    pos_ok = [{"name": "US Treasury 2056", "isin": "US912810US59", "currency": "USD"}]
    pos_ko = [{"name": "US Treasury 2056", "isin": "US912810US59", "currency": "EUR"}]
    assert check_special_mappings(pos_ok).ok
    assert not check_special_mappings(pos_ko).ok


def test_oro_in_bucket_fx_e_errore():
    # L'oro è asset class autonoma: non deve avere una valuta FX.
    positions = [{"name": "Oro fisico", "ticker": "IGLN", "asset_class": "Oro", "currency": "USD"}]
    res = check_special_mappings(positions)
    assert not res.ok


def test_oro_senza_valuta_ok():
    positions = [{"name": "Oro fisico", "ticker": "IGLN", "asset_class": "Oro", "currency": None}]
    res = check_special_mappings(positions)
    assert res.ok


# --- B5: aggregazioni ---------------------------------------------------------

def test_alphabet_non_aggregato_e_errore():
    positions = [
        {"name": "Alphabet A", "ticker": "GOOGL US"},
        {"name": "Alphabet C", "ticker": "GOOG US"},
    ]
    res = check_aggregations(positions)
    assert not res.ok


def test_alphabet_una_sola_classe_non_e_errore():
    # check_aggregations segnala solo la compresenza di GOOGL US e GOOG US
    # come posizioni separate; una sola classe in portafoglio è legittima.
    res = check_aggregations([{"ticker": "GOOGL US", "name": "Alphabet Inc"}])
    assert res.ok


def test_samsung_include_controllata_e_errore():
    # Samsung SDI (006400 KS) NON va dentro Samsung Electronics.
    positions = [{"name": "Samsung Electronics", "ticker": "005930 KS", "components": ["006400 KS"]}]
    res = check_aggregations(positions)
    assert not res.ok


def test_fondo_21st_conteggiato_e_errore():
    # Il fondo 21st replica il model portfolio: non va conteggiato come posizione.
    positions = [{"name": "Fondo 21st Century", "ticker": "21ST", "value": 84_000_000}]
    res = check_aggregations(positions)
    assert not res.ok


# --- B8: concentrazione (avvisi, non bloccanti) ------------------------------

def test_concentration_single_name_sopra_2pct_warning():
    positions = [{"name": "Pippo", "weight": 0.021}]
    res = check_concentration(positions)
    assert res.ok  # avviso, non blocca
    assert res.warnings


def test_concentration_sotto_soglia_nessun_flag():
    positions = [{"name": "Pippo", "weight": 0.010}]
    res = check_concentration(positions)
    assert res.ok
    assert not res.warnings


def test_concentration_ignora_fondi_e_oro():
    # La soglia è sui single-name azionari: un fondo o l'oro al 16% NON vanno segnalati.
    positions = [
        {"name": "Fondo DELTA", "weight": 0.16, "asset_class": "Fondo UCITS", "is_fund": True},
        {"name": "Oro fisico", "weight": 0.06, "asset_class": "Oro"},
        {"name": "Bund", "weight": 0.20, "asset_class": "Bond"},
    ]
    res = check_concentration(positions)
    assert res.ok
    assert not res.warnings
