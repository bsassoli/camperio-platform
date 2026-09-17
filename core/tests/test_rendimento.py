# -*- coding: utf-8 -*-
"""Rendimento lordo, netto e mensile: i numeri di riferimento sono quelli del
contratto S9060 al 15/09/2026, riconciliati con Antana alla terza cifra decimale."""
import pytest

from camperio_core.portfolio import rendimento as R

# Fine-mese di SRE (TCLI netto, TBMK) dal 31/12/2025 al 31/08/2026.
SERIE = [
    {"data": "2025-12-31", "tcli": 1707.486236, "tbmk": 2024.162769},
    {"data": "2026-01-31", "tcli": 1772.534226, "tbmk": 2057.426208},
    {"data": "2026-02-28", "tcli": 1819.286773, "tbmk": 2086.689361},
    {"data": "2026-03-31", "tcli": 1742.546442, "tbmk": 2014.329546},
    {"data": "2026-04-30", "tcli": 1807.736305, "tbmk": 2094.380557},
    {"data": "2026-05-31", "tcli": 1872.294913, "tbmk": 2154.005198},
    {"data": "2026-06-30", "tcli": 1890.165203, "tbmk": 2179.876290},
    {"data": "2026-07-31", "tcli": 1862.711150, "tbmk": 2169.602069},
    {"data": "2026-08-31", "tcli": 1880.936637, "tbmk": 2183.624681},
]
# Addebiti commissionali 2026 (MOV.CTVREG, IVA inclusa) con il NAV del giorno.
COMM = [
    {"data": "2026-03-31", "tipo": "CDG", "importo": 12616.53, "nav": 8123870.70},
    {"data": "2026-05-11", "tipo": "RSP", "importo": 224.72, "nav": 8582619.30},
    {"data": "2026-06-30", "tipo": "CDG", "importo": 13065.92, "nav": 8807569.89},
    {"data": "2026-08-04", "tipo": "RSP", "importo": 230.97, "nav": 8772250.20},
    {"data": "2026-09-07", "tipo": "CTR", "importo": 122.00, "nav": 8766578.19},
]
TCLI_AL, TBMK_AL = 1857.886108, 2166.442839
DAL, AL = "2025-12-31", "2026-09-15"


def test_netto_e_quello_del_gestionale():
    assert R.rendimento_netto(SERIE[0]["tcli"], TCLI_AL) == pytest.approx(0.088083, abs=1e-6)


def test_lordo_riconcilia_con_antana():
    lordo = R.rendimento_lordo(SERIE[0]["tcli"], TCLI_AL, R.nel_periodo(COMM, DAL, AL))
    assert lordo == pytest.approx(0.091462, abs=1e-6)


def test_benchmark_non_si_rettifica():
    assert R.rendimento_benchmark(SERIE[0]["tbmk"], TBMK_AL) == pytest.approx(0.070291, abs=1e-6)


def test_lordo_maggiore_del_netto():
    comm = R.nel_periodo(COMM, DAL, AL)
    assert R.rendimento_lordo(SERIE[0]["tcli"], TCLI_AL, comm) > R.rendimento_netto(SERIE[0]["tcli"], TCLI_AL)


def test_totale_commissioni_del_periodo():
    assert R.totale_commissioni(R.nel_periodo(COMM, DAL, AL)) == pytest.approx(26260.14, abs=0.01)


def test_risultato_lordo_in_euro():
    comm = R.nel_periodo(COMM, DAL, AL)
    assert R.risultato_lordo(701356.32, comm) == pytest.approx(727616.46, abs=0.01)


def test_nel_periodo_esclude_la_data_iniziale_e_include_la_finale():
    assert R.nel_periodo(COMM, "2026-03-31", "2026-06-30") == COMM[1:3]
    assert R.nel_periodo(COMM, "2026-01-01", "2026-03-31") == COMM[:1]


def test_commissione_senza_nav_non_falsa_il_rendimento():
    rotta = [{"data": "2026-03-31", "importo": 12616.53, "nav": 0}]
    assert R.fattore_commissioni(rotta) == 1.0


def test_la_matrice_mensile_si_compone_nel_rendimento_di_periodo():
    """Il prodotto dei mesi deve dare il rendimento calcolato sugli estremi:
    e' il controllo che tiene insieme la pagina della matrice e la prima pagina."""
    mesi = R.rendimenti_mensili(SERIE, COMM)
    assert len(mesi) == 8
    atteso = R.rendimento_lordo(SERIE[0]["tcli"], SERIE[-1]["tcli"],
                                R.nel_periodo(COMM, SERIE[0]["data"], SERIE[-1]["data"]))
    assert R.componi([m["lordo"] for m in mesi]) == pytest.approx(atteso, abs=1e-12)
    atteso_b = R.rendimento_benchmark(SERIE[0]["tbmk"], SERIE[-1]["tbmk"])
    assert R.componi([m["bench"] for m in mesi]) == pytest.approx(atteso_b, abs=1e-12)


def test_marzo_2026_e_negativo_e_peggiore_del_parametro():
    mesi = {(m["anno"], m["mese"]): m for m in R.rendimenti_mensili(SERIE, COMM)}
    marzo = mesi[(2026, 3)]
    assert marzo["lordo"] == pytest.approx(-0.0407, abs=5e-4)
    assert marzo["lordo"] < marzo["bench"] < 0


def test_media_annua_non_annualizza_sotto_un_anno_e_mezzo():
    assert R.media_annua(0.091462, 0.71) is None
    assert R.media_annua(0.3019, 4.7096) == pytest.approx(0.0577, abs=1e-4)


def test_valori_non_calcolabili_tornano_none():
    assert R.rendimento_netto(0, 100) is None
    assert R.rendimento_netto(None, 100) is None
    assert R.rendimento_lordo(None, 100, COMM) is None
    assert R.componi([0.01, None]) is None
    assert R.componi([]) is None
