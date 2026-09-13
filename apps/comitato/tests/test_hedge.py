"""Contratto dell'hedge su indice: robusto al rollover, con segno, mai per codice contratto."""
import os
import textwrap

import pytest

import data_layer as DL
import lookthrough as L


def test_get_portfolio_demo01_espone_deriv_con_segno():
    pf = DL.get_portfolio("ANTASIMGEST", "DEMO01")
    assert "deriv" in pf
    sp = [d for d in pf["deriv"] if "S&P" in d["des"]]
    bobl = [d for d in pf["deriv"] if "BOBL" in d["des"]]
    assert len(sp) == 1 and sp[0]["valorefut"] < 0        # future short: delta negativo
    assert len(bobl) == 1 and bobl[0]["valorefut"] > 0    # put su tasso: presente ma non azionario
    assert set(sp[0]) == {"des", "grutit", "isin", "valorefut"}


_IUSA_CSV = textwrap.dedent("""\
    iShares Core S&P 500 UCITS ETF
    Data,10/set/2026

    Ticker,Nome,Settore,Asset Class,Valore di mercato,Ponderazione (%),Valore nominale,Nominale,ISIN,Prezzo,Località,Borsa,Valuta di mercato
    AAPL,APPLE INC,Informatica,Azionario,"1.000,00","60,00","1.000,00","1.000,00",US0378331005,"100,00",Stati Uniti,NASDAQ,USD
    MSFT,MICROSOFT CORP,Informatica,Azionario,"1.000,00","40,00","1.000,00","1.000,00",US5949181045,"100,00",Stati Uniti,NASDAQ,USD
    XXX,CASH EUR,Liquidità,Liquidità,"1,00","0,00","1,00","1,00",-,"1,00",-,-,EUR
    """)


@pytest.fixture()
def repo(tmp_path):
    (tmp_path / "IUSA_2026-09-10.csv").write_text(_IUSA_CSV, encoding="utf-8")
    return str(tmp_path)


def _pf(deriv, pod=None):
    return {
        "meta": {"nav": 1_000_000.0},
        "positions": [{"codabi": "A1", "des": "APPLE INC", "grutit": "E03", "valmer": 100_000.0,
                       "valorefut": 100_000.0, "bbg": "", "isin": "", "ccy": "USD", "macro": "Attacco", "sub": ""}],
        "pod": pod or [],
        "deriv": deriv,
    }


def _row(t, name):
    return next(r for r in t["rows"] if r["name"].upper() == name)


def test_short_su_indice_rende_il_netto_diverso_dal_lordo(repo):
    t = L.build_titoli(_pf([{"des": "S&P 500 MINI FUT SET-26", "grutit": "G12", "isin": "", "valorefut": -100_000.0}]), repo)
    apple = _row(t, "APPLE INC")
    assert apple["lordo"] == pytest.approx(100_000.0)
    assert apple["hedge"] == pytest.approx(-60_000.0)
    assert apple["netto"] == pytest.approx(40_000.0)
    assert _row(t, "MICROSOFT CORP")["hedge"] == pytest.approx(-40_000.0)
    assert t["tot_hedge"] == pytest.approx(-100_000.0)
    assert t["hedge_dett"] == [{"nome": "S&P 500 MINI FUT SET-26", "valorefut": -100_000.0, "indice": "IUSA"}]


def test_hedge_sopravvive_al_rollover_del_contratto(repo):
    t = L.build_titoli(_pf([{"des": "S&P 500 MINI FUT DIC-26", "grutit": "G12", "isin": "", "valorefut": -100_000.0}]), repo)
    assert t["tot_hedge"] == pytest.approx(-100_000.0)


def test_put_su_bobl_resta_esclusa_dal_netto(repo):
    t = L.build_titoli(_pf([
        {"des": "S&P 500 MINI FUT SET-26", "grutit": "G12", "isin": "", "valorefut": -100_000.0},
        {"des": "EURO BOBL OTT-26 PUT 114.25", "grutit": "F19", "isin": "DE000F3ZL359", "valorefut": 105_576.31},
    ]), repo)
    assert t["tot_hedge"] == pytest.approx(-100_000.0)
    assert [h["indice"] for h in t["hedge_dett"]] == ["IUSA"]


def test_future_long_su_indice_aumenta_il_netto(repo):
    t = L.build_titoli(_pf([{"des": "EURO STOXX 50 FUT DIC-26", "grutit": "G12", "isin": "", "valorefut": 50_000.0}]), repo)
    # nessun CSV EUE nel repo di test: il derivato è riconosciuto ma non ripartibile, quindi non entra nel netto
    assert t["tot_hedge"] == pytest.approx(0.0)
    assert t["hedge_dett"] == []


def test_senza_deriv_nessun_fallback_su_pod(repo):
    pod = [{"codabi": "E35126", "des": "E35126", "pnet": -1, "val": 7643.75, "scad": "2026-09-18", "tipo": ""}]
    t = L.build_titoli(_pf([], pod=pod), repo)
    assert t["tot_hedge"] == 0.0
    assert t["hedge_dett"] == []
