"""Calcoli del cruscotto: stesse regole del JavaScript dell'artifact cowork."""
import pytest

from promotori import calcoli as C


def _contratto(codice, ambito="RTO", tipoge="RTO", apertura="2020-01-01", chiusura=None):
    return {"AMBITO": ambito, "CODCLI": codice, "DESCLI": "Cliente " + codice, "TIPOGE": tipoge,
            "DATAPER": apertura, "DATCHIU": chiusura}


def _sre(codice, periodo, consfin, apporti=0, prelievi=0, tcli=1000):
    return {"AMBITO": "RTO", "CODCLI": codice, "PERIODO": periodo, "CONSFIN": consfin,
            "APPORTI": apporti, "PRELIEVI": prelievi, "TCLI": tcli}


def _stato(contratti, sre=(), comm=(), trim=(), tipo=(), ope=()):
    return C.costruisci_stato(contratti=list(contratti), sre=list(sre), comm_contratto=list(comm),
                              comm_trimestre=list(trim), comm_tipo=list(tipo), operazioni=list(ope))


@pytest.mark.parametrize("tipope, attesa", [
    ("CDG", "Gestione, fee ricorrente (CDG)"),
    ("CCO", "Consulenza, fee ricorrente (CCO)"),
    ("CSA", "Servizio, fee ricorrente (CSA)"),
    ("AVE", "Intermediazione/negoziazione (AV*, Exx, FUx, OPF, OCF)"),
    ("E21", "Intermediazione/negoziazione (AV*, Exx, FUx, OPF, OCF)"),
    ("FU1", "Intermediazione/negoziazione (AV*, Exx, FUx, OPF, OCF)"),
    ("OCF", "Intermediazione/negoziazione (AV*, Exx, FUx, OPF, OCF)"),
    ("CTC", "Tenuta conto (CTC)"),
    ("E2", "Altri oneri, estero/custody/vari (E2)"),        # Exx vuole esattamente due cifre
    ("E211", "Altri oneri, estero/custody/vari (E211)"),
    ("BL1", "Altri oneri, estero/custody/vari (BL1)"),
    (None, "Altri oneri, estero/custody/vari ()"),
])
def test_categorie_commissioni(tipope, attesa):
    assert C.categoria_commissione(tipope) == attesa


@pytest.mark.parametrize("ambito, tipoge, attesa", [
    ("GPM", "L01", "Gestione"),       # l'ambito GPM vince sulla linea
    ("RTO", "L01", "Consulenza"),
    ("RTO", "l02", "Consulenza"),
    ("RTO", "RTO", "RTO"),
    ("RTO", None, "RTO"),
])
def test_sotto_ambito(ambito, tipoge, attesa):
    assert C.sotto_ambito(ambito, tipoge) == attesa


@pytest.mark.parametrize("valore, atteso", [(None, 0.0), ("", 0.0), ("1.5", 1.5), ("abc", 0.0),
                                            (float("nan"), 0.0), (7, 7.0)])
def test_num_come_nel_javascript(valore, atteso):
    assert C.num(valore) == atteso


def test_periodo_di_default_anno_in_corso_e_anno_chiuso():
    stato = _stato([_contratto("A"), _contratto("B")],
                   [_sre("A", "2025-12-31", 1), _sre("A", "2026-09-10", 1), _sre("B", "2026-09-12", 1)])
    in_corso = C.risolvi_periodo(stato)
    assert (in_corso.anno, in_corso.dal, in_corso.al) == (2026, "2026-01-01", "2026-09-12")
    assert in_corso.in_corso and not in_corso.dal_personalizzato and not in_corso.al_personalizzato
    chiuso = C.risolvi_periodo(stato, anno=2025)
    assert (chiuso.dal, chiuso.al, chiuso.in_corso) == ("2025-01-01", "2025-12-31", False)
    scelto = C.risolvi_periodo(stato, anno=2026, dal="2026-04-01", al="2026-06-30")
    assert (scelto.dal, scelto.al, scelto.dal_personalizzato, scelto.al_personalizzato) == \
        ("2026-04-01", "2026-06-30", True, True)


@pytest.mark.parametrize("kwargs, messaggio", [
    ({"anno": 2019}, "non disponibile"),
    ({"dal": "2026-10-01"}, "Dal non può essere successiva"),
])
def test_periodo_non_valido(kwargs, messaggio):
    stato = _stato([_contratto("A")], [_sre("A", "2026-09-10", 1)])
    with pytest.raises(C.PeriodoNonValido, match=messaggio):
        C.risolvi_periodo(stato, **kwargs)


def test_senza_snapshot_nessun_periodo():
    with pytest.raises(C.PeriodoNonValido, match="Nessuna massa"):
        C.risolvi_periodo(_stato([_contratto("A")]))


def test_masse_per_servizio_e_contratti_senza_snapshot():
    stato = _stato(
        [_contratto("R", tipoge="RTO"), _contratto("L", tipoge="L01"),
         _contratto("G", ambito="GPM", tipoge="GP1"), _contratto("X")],
        [_sre("R", "2026-09-10", 100), _sre("L", "2026-09-10", 50), _sre("G", "2026-09-10", 350)])
    m = C.massa_anno(stato, 2026)
    assert m["totale"] == 500 and m["n"] == 3
    assert m["servizi"] == {"rto": {"valore": 100, "n": 1}, "consulenza": {"valore": 50, "n": 1},
                            "gestione": {"valore": 350, "n": 1}}


def test_flusso_e_rendimento_rispetto_al_fine_anno_precedente():
    stato = _stato([_contratto("A")], [
        _sre("A", "2025-12-31", 540000, 470000, -30000, 1160),
        _sre("A", "2026-09-12", 575000, 490000, -35000, 1195)])
    assert C.flusso_contratto(stato, "A", 2026) == 15000
    assert C.rendimento_eur(stato, "A", 2026) == 20000
    assert C.rendimento_pct(stato, "A", 2026) == pytest.approx((1195 / 1160 - 1) * 100)


def test_contratto_aperto_nell_anno_senza_massa_di_partenza():
    stato = _stato([_contratto("A")], [_sre("A", "2026-09-12", 205000, 200000, 0, 1025)])
    assert C.flusso_contratto(stato, "A", 2026) == 200000      # nessun cumulato precedente: 0
    assert C.rendimento_eur(stato, "A", 2026) is None           # manca la massa di partenza
    assert C.rendimento_pct(stato, "A", 2026) == pytest.approx(2.5)   # contro base TCLI 1000


def test_dal_personalizzato_sostituisce_il_fine_anno_precedente():
    stato = _stato([_contratto("A")], [
        _sre("A", "2025-12-31", 540000, 470000, -30000, 1160),
        _sre("A", "2026-09-12", 575000, 490000, -35000, 1195)])
    C.applica_dal(stato, 2026, [_sre("A", "2026-03-31", 552000, 480000, -30000, 1170)])
    assert C.flusso_contratto(stato, "A", 2026) == 5000
    assert C.rendimento_eur(stato, "A", 2026) == 18000
    assert C.rendimento_pct(stato, "A", 2026) == pytest.approx((1195 / 1170 - 1) * 100)


def test_al_personalizzato_sostituisce_lo_snapshot_e_conta_anche_i_chiusi():
    # SRE_ALLA_DATA non esclude i contratti chiusi (a differenza dei fondi): un contratto
    # chiuso nel 2025 rientra nel conteggio del 2026 con la sua ultima massa. Comportamento
    # dell'originale, portato così com'è e segnalato in DOMANDE-EDOARDO.md.
    stato = _stato([_contratto("A"), _contratto("CHIUSO", chiusura="2025-06-30")],
                   [_sre("A", "2026-09-12", 575000), _sre("CHIUSO", "2025-06-30", 0)])
    C.applica_al(stato, 2026, [_sre("A", "2026-06-30", 566000), _sre("CHIUSO", "2025-06-30", 0)])
    m = C.massa_anno(stato, 2026)
    assert m["totale"] == 566000 and m["n"] == 2


def test_snapshot_solo_dal_non_rompe_la_massa():
    # nell'originale un contratto con il solo snapshot Dal faceva diventare n.d. il KPI massa
    stato = _stato([_contratto("A"), _contratto("B")], [_sre("A", "2026-09-12", 100)])
    C.applica_dal(stato, 2026, [_sre("B", "2025-06-30", 0)])
    assert C.massa_anno(stato, 2026)["totale"] == 100
    assert C.flusso_contratto(stato, "B", 2026) is None
    assert C.rendimento_eur(stato, "B", 2026) is None


def test_contatori_del_periodo():
    stato = _stato([
        _contratto("ATTIVO", apertura="2020-01-01"),
        _contratto("APERTO_E_CHIUSO", apertura="2026-02-01", chiusura="2026-03-01"),
        _contratto("CHIUSO_DOPO_AL", apertura="2020-01-01", chiusura="2026-12-01"),
        _contratto("APERTO_DOPO_AL", apertura="2026-10-01"),
        _contratto("SENZA_APERTURA", apertura=None),
    ])
    assert C.stato_periodo(stato, "2026-01-01", "2026-06-30") == {
        "contratti_attivi": 2, "contratti_aperti": 1, "contratti_chiusi": 1}


def test_commissioni_per_servizio_trimestre_e_tipo():
    stato = _stato(
        [_contratto("R"), _contratto("L", tipoge="L01"), _contratto("G", ambito="GPM")],
        comm=[{"CODCLI": "R", "ANNO": 2026, "IMPORTO": 100}, {"CODCLI": "R", "ANNO": 2026, "IMPORTO": 50},
              {"CODCLI": "L", "ANNO": 2026, "IMPORTO": 30}, {"CODCLI": "SCONOSCIUTO", "ANNO": 2026, "IMPORTO": 20},
              {"CODCLI": "G", "ANNO": 2025, "IMPORTO": 999}],
        trim=[{"ANNO": 2026, "TRIM": "1", "IMPORTO": 10}, {"ANNO": 2026, "TRIM": "3", "IMPORTO": 5},
              {"ANNO": 2026, "TRIM": "X", "IMPORTO": 99}],
        tipo=[{"ANNO": 2026, "TIPOPE": "AVE", "IMPORTO": 7}, {"ANNO": 2026, "TIPOPE": "E21", "IMPORTO": 3}])
    assert C.commissioni_anno(stato, 2026) == 200
    assert C.commissioni_per_servizio(stato, 2026) == {
        "rto": {"valore": 150, "n": 1}, "consulenza": {"valore": 30, "n": 1},
        "gestione": {"valore": 20, "n": 1}}          # codice senza contratto: in Gestione
    assert stato.comm_trimestre[2026] == [10, 0, 5, 0]
    assert stato.comm_tipo[2026] == {"Intermediazione/negoziazione (AV*, Exx, FUx, OPF, OCF)": 10}
    assert stato.comm_per_contratto[("R", 2026)] == 150


def test_fondi_per_famiglia_contano_posizioni_e_servizi_contratti():
    righe = [{"CODCLI": "G", "FONDO": "delta", "VALMER": 100}, {"CODCLI": "G", "FONDO": "defensive", "VALMER": 50},
             {"CODCLI": "R", "FONDO": "delta", "VALMER": 10}, {"CODCLI": "R", "FONDO": "ignoto", "VALMER": 999}]
    agg = C.fondi_per_famiglia(righe, {"G": "Gestione", "R": "RTO"})
    assert agg["famiglie"]["delta"] == {"valore": 110, "n": 2}
    assert agg["servizi"]["gestione"] == {"valore": 150, "n": 1}
    assert agg["servizi"]["rto"] == {"valore": 10, "n": 1}


def test_tabella_esclude_i_chiusi_prima_di_dal_e_non_conta_operazioni_in_gestione():
    stato = _stato(
        [_contratto("VECCHIO", chiusura="2025-12-30"), _contratto("R"), _contratto("G", ambito="GPM")],
        [_sre("R", "2026-09-12", 100), _sre("G", "2026-09-12", 200)],
        ope=[{"CODCLI": "R", "ANNO": 2026, "N": 4}])
    righe = C.tabella_contratti(stato, 2026, "2026-01-01")
    assert [r["codice"] for r in righe] == ["R", "G"]
    assert righe[0]["operazioni"] == 4 and righe[1]["operazioni"] is None


def test_cruscotto_con_massa_zero_non_divide_per_zero():
    stato = _stato([_contratto("A")], [_sre("A", "2026-09-12", 0)],
                   comm=[{"CODCLI": "A", "ANNO": 2026, "IMPORTO": 10}],
                   tipo=[{"ANNO": 2026, "TIPOPE": "CTC", "IMPORTO": 10}])
    v = C.componi_cruscotto(stato, C.risolvi_periodo(stato), [], [], [])
    assert v["kpi"]["rendimento_commissionale"] is None
    assert v["commissioni"]["per_tipo"][0]["quota_massa"] is None
    assert v["commissioni"]["per_tipo"][0]["quota_commissioni"] == 100
    assert all(s["quota"] == 0 for s in v["masse"])
