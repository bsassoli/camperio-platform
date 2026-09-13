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
