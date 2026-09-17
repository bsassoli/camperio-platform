# -*- coding: utf-8 -*-
"""Le funzioni di serie storiche e oneri del data layer, in modalita' DEMO."""
import pytest

import data_layer as DL

DAL, AL = "2025-12-31", "2026-08-14"


def test_serie_mensile_e_ordinata_e_parte_da_un_31_dicembre():
    s = DL.serie_mensile("ANTASIMGEST", "DEMO01", AL)
    assert s, "la fixture DEMO deve contenere la serie mensile"
    assert s[0]["data"].endswith("-12-31")
    assert [r["data"] for r in s] == sorted(r["data"] for r in s)
    assert all(r["tcli"] > 0 and r["tbmk"] > 0 for r in s)


def test_serie_giornaliera_rispetta_gli_estremi():
    g = DL.serie_giornaliera("ANTASIMGEST", "DEMO01", DAL, AL)
    assert len(g) > 20
    assert g[0]["data"] == DAL and g[-1]["data"] == AL


def test_commissioni_escludono_la_data_iniziale():
    c = DL.commissioni("ANTASIMGEST", "DEMO01", DAL, AL)
    assert c and all(DAL < r["data"] <= AL for r in c)
    # senza NAV il riaccredito non sarebbe calcolabile: la fixture lo garantisce
    assert all(r["nav"] > 0 for r in c)


def test_quadro_patrimoniale_quadra():
    p = DL.quadro_patrimoniale("ANTASIMGEST", "DEMO01", DAL, AL)
    assert p["cons_ini"] + p["apporti"] + p["prelievi"] + p["risultato_netto"] == \
        pytest.approx(p["cons_fin"], abs=0.01)


def test_oneri_coerenti_con_le_commissioni():
    o = DL.oneri("ANTASIMGEST", "DEMO01", DAL, AL)
    c = DL.commissioni("ANTASIMGEST", "DEMO01", DAL, AL)
    assert sum(o["per_tipo"].values()) == pytest.approx(sum(x["importo"] for x in c), abs=0.01)
    assert o["spese_negoziazione"] >= 0 and o["ritenute"] >= 0


def test_contratto_senza_fixture_non_esplode():
    """Un contratto senza file rendiconto in DEMO torna vuoto, non un errore."""
    assert DL.serie_mensile("ANTASIMGEST", "DEMO99", AL) == []
    assert DL.commissioni("ANTASIMGEST", "DEMO99", DAL, AL) == []
    assert DL.quadro_patrimoniale("ANTASIMGEST", "DEMO99", DAL, AL) == {}


def test_posizioni_con_quantita_e_prezzi():
    """Il prospetto analitico del Rendiconto ha bisogno di questi campi."""
    pf = DL.get_portfolio("ANTASIMGEST", "DEMO01")
    titoli = [p for p in pf["positions"] if not (p.get("grutit") or "").startswith("Z")]
    assert titoli
    assert all("quanti" in p and "divisa" in p for p in titoli)
    assert any(p.get("unimer") for p in titoli)
