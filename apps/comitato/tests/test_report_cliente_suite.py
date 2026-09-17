# -*- coding: utf-8 -*-
"""I tre report al cliente in modalita' DEMO: quadrature, foliazione e testi editoriali.

I controlli sono quelli che nel documento non possono saltare: il ponte patrimoniale che
torna alla lira, il lordo che e' il netto piu' le commissioni restituite, la matrice
mensile che si compone nel rendimento dell'esercizio.
"""
import os

import pytest

import contenuti as CONT
import data_layer as DL
import report_cliente as RC
import report_rendiconto as RR
from camperio_core.portfolio import rendimento as RD

DAL, AL = "2025-12-31", "2026-08-14"


def _pagine(path):
    with open(path, "rb") as f:
        b = f.read()
    return b.count(b"/Type /Page") - b.count(b"/Type /Pages")


@pytest.fixture(scope="module")
def dati():
    pf = DL.get_portfolio("ANTASIMGEST", "DEMO01")
    return RR.build_rendiconto(pf, DL.REPO)


# ----------------------------------------------------------------- numeri
def test_il_ponte_patrimoniale_quadra(dati):
    p = dati["patrimoniale"]
    somma = p["cons_ini"] + p["apporti"] + p["prelievi"] + p["risultato_netto"]
    assert somma == pytest.approx(p["cons_fin"], abs=0.01)


def test_il_lordo_e_il_netto_piu_le_commissioni(dati):
    p = dati["patrimoniale"]
    assert dati["gain"] == pytest.approx(p["risultato_netto"] + dati["comm_tot"], abs=0.01)


def test_il_rendimento_lordo_supera_il_netto(dati):
    assert dati["ytd_p"] > dati["ytd_n"] > 0
    assert dati["extra"] == pytest.approx(dati["ytd_p"] - dati["ytd_b"], abs=1e-12)


def test_le_commissioni_sono_quelle_del_periodo(dati):
    assert dati["comm"], "in DEMO devono esserci addebiti nel periodo"
    assert all(DAL < c["data"] <= AL for c in dati["comm"])
    assert dati["comm_tot"] == pytest.approx(RD.totale_commissioni(dati["comm"]), abs=0.01)


def test_la_matrice_si_compone_nel_rendimento_dell_esercizio(dati):
    per_anno = {a: p for a, p, _b, _z in dati["anni"]}
    for anno, mesi in dati["matrice"].items():
        composto = RD.componi([mesi[m][0] for m in sorted(mesi)])
        assert composto == pytest.approx(per_anno[anno], abs=1e-12), anno


def test_l_esercizio_in_corso_coincide_con_il_rendimento_di_periodo(dati):
    corrente = {a: p for a, p, _b, _z in dati["anni"]}[int(AL[:4])]
    assert corrente == pytest.approx(dati["ytd_p"], abs=1e-9)


def test_solo_l_esercizio_in_corso_e_parziale(dati):
    parziali = [a for a, _p, _b, z in dati["anni"] if z]
    assert parziali == [int(AL[:4])]


def test_i_reparti_sommano_alle_posizioni(dati):
    somma = sum(r["val"] for _k, r in dati["reparti"])
    assert somma == pytest.approx(dati["nav"], abs=1.0)
    assert sum(r["n"] for _k, r in dati["reparti"]) == dati["n_pos"]


def test_le_due_basi_restano_separate(dati):
    """Il NAV di inizio periodo e la base delle allocazioni sono numeri diversi
    (CLAUDE.md): se qualcuno li riunifica, la narrativa della prima pagina mente."""
    assert dati["nav_inizio"] != dati["base_alloc"]
    assert dati["nav_inizio"] == pytest.approx(dati["patrimoniale"]["cons_ini"], abs=0.01)


def test_la_media_annua_non_esiste_per_lo_ytd(dati):
    ytd = [c for c in dati["cumulati"] if c["etichetta"] == "Da inizio anno"][0]
    assert ytd["media"] is None
    assert ytd["pf"] == pytest.approx(dati["ytd_p"], abs=1e-9)


# ----------------------------------------------------------------- contenuti
def test_le_convinzioni_citano_solo_titoli_in_portafoglio(dati):
    presenti = {p["nome"].upper() for _k, r in dati["reparti"] for p in r["pos"]}
    for c in dati["convinzioni"]:
        assert c["pct"] > 0
        assert any(c["titolo"].split()[0].upper() in n for n in presenti) or c["val"] > 0


def test_linea_senza_file_dedicato_usa_il_default():
    t = CONT.carica("Linea Inesistente")
    assert t["convinzioni"] == []
    assert t["reparti"]["Difesa"]


def test_slug_della_linea():
    assert CONT.slug("Camperio Plus") == "camperio-plus"
    assert CONT.slug("") == ""


# ----------------------------------------------------------------- PDF
def test_la_sintetica_sta_in_una_pagina(dati, tmp_path):
    p = str(tmp_path / "s.pdf")
    RC.sintetica_pdf(dati, p)
    assert _pagine(p) == 1


def test_la_sintesi_ha_tre_pagine(dati, tmp_path):
    p = str(tmp_path / "s3.pdf")
    RC.sintesi_pdf(dati, p)
    assert _pagine(p) == 3


def test_il_rendiconto_ha_le_sezioni_previste(dati, tmp_path):
    p = str(tmp_path / "r.pdf")
    RR.rendiconto_pdf(dati, p)
    assert _pagine(p) >= 6
    assert os.path.getsize(p) > 20000


def test_l_anteprima_html_del_rendiconto_mostra_lordo_e_netto(dati):
    h = RR.rendiconto_html(dati)
    assert "Rendimento lordo" in h and "netto" in h
    assert "Quadro patrimoniale" in h
