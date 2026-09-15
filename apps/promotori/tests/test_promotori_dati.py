"""Query e sorgente dati: bind variable in LIVE, emulazione delle date in DEMO."""
import pytest

from promotori import query as Q
from promotori.dati import Sorgente

# solo le query pubbliche: i frammenti privati (_MOV_COMMISSIONI, ...) hanno i segnaposto per costruzione
TUTTE = {nome: getattr(Q, nome) for nome in dir(Q) if nome.isupper() and not nome.startswith("_")}


class ClientLiveFinto:
    """Registra le query invece di eseguirle."""

    def __init__(self):
        self.chiamate = []

    def mode(self):
        return "LIVE"

    def query(self, sql, params=None, fixture=None):
        self.chiamate.append((sql, params))
        return []


@pytest.mark.parametrize("nome", sorted(TUTTE))
def test_nessuna_query_ha_segnaposto_o_concatenazioni(nome):
    sql = TUTTE[nome]
    assert "${" not in sql and "{ambito}" not in sql and "{sim}" not in sql and "{loc}" not in sql
    if nome != "ELENCO_REFERENTI":
        assert "VALITEM_DES=:ref" in sql


def test_live_il_referente_viaggia_solo_come_bind_variable():
    client = ClientLiveFinto()
    malevolo = "X' OR '1'='1"
    s = Sorgente(client)
    s.contratti(malevolo)
    s.fondi(malevolo, "2026-06-30")
    for sql, params in client.chiamate:
        assert malevolo not in sql
        assert params["ref"] == malevolo


@pytest.mark.parametrize("metodo, argomenti, parametri", [
    ("elenco_referenti", (), {}),
    ("contratti", ("R",), {"ref": "R"}),
    ("sre", ("R",), {"ref": "R"}),
    ("sre_alla_data", ("R", "2026-06-30"), {"ref": "R", "data": "2026-06-30"}),
    ("commissioni_per_contratto", ("R",), {"ref": "R"}),
    ("commissioni_per_trimestre", ("R",), {"ref": "R"}),
    ("commissioni_per_tipo", ("R",), {"ref": "R"}),
    ("operazioni", ("R",), {"ref": "R"}),
    ("fondi", ("R", "2026-06-30"), {"ref": "R", "al": "2026-06-30"}),
    ("fondi_totale", ("R", "2026-06-30"), {"ref": "R", "al": "2026-06-30"}),
    ("flussi_reali", ("R", "2026-01-01", "2026-06-30"), {"ref": "R", "dal": "2026-01-01", "al": "2026-06-30"}),
])
def test_live_ogni_query_riceve_esattamente_i_suoi_parametri(metodo, argomenti, parametri):
    # oracledb rifiuta bind in più (ORA-01036): i parametri devono combaciare con la query
    client = ClientLiveFinto()
    getattr(Sorgente(client), metodo)(*argomenti)
    sql, params = client.chiamate[0]
    assert params == parametri
    for nome in parametri:
        assert ":" + nome in sql


def test_fondi_escludono_i_chiusi_prima_di_al_e_usano_la_finestra_di_20_giorni():
    for sql in (Q.FONDI, Q.FONDI_TOTALE):
        assert "c.DATCHIU<TO_DATE(:al,'YYYY-MM-DD')" in sql
        assert "TO_DATE(:al,'YYYY-MM-DD')-20" in sql
        assert "ANTALOCGEST.WCTDD" in sql and "ANTALOCN.WCTDD" in sql
    assert "w.SOCEMI='CON'" in Q.FONDI
    assert "w.FONDI='S'" in Q.FONDI_TOTALE


def test_demo_filtra_il_referente_e_toglie_la_colonna_refcom():
    righe = Sorgente().contratti("D00002")
    assert {r["CODCLI"] for r in righe} == {"DEMO-R11", "DEMO-G11"}
    assert all("REFCOM" not in r for r in righe)


def test_demo_sre_tiene_fine_anno_e_ultimo_periodo_per_contratto():
    periodi = {(r["CODCLI"], r["PERIODO"]) for r in Sorgente().sre("D00001")
               if r["CODCLI"] in ("DEMO-R01", "DEMO-R04")}
    assert periodi == {("DEMO-R01", "2024-12-31"), ("DEMO-R01", "2025-12-31"), ("DEMO-R01", "2026-09-12"),
                       ("DEMO-R04", "2024-12-31"), ("DEMO-R04", "2025-06-30")}


def test_demo_sre_alla_data_prende_l_ultimo_snapshot_non_successivo():
    per_contratto = {r["CODCLI"]: r["PERIODO"] for r in Sorgente().sre_alla_data("D00001", "2026-04-30")}
    assert per_contratto["DEMO-R01"] == "2026-03-31"
    assert per_contratto["DEMO-R03"] == "2026-04-20"
    assert per_contratto["DEMO-R04"] == "2025-06-30"


def test_demo_flussi_sommano_i_movimenti_nel_periodo_estremi_inclusi():
    flussi = {r["CODCLI"]: r["FLUSSO"] for r in Sorgente().flussi_reali("D00001", "2026-02-10", "2026-06-15")}
    assert flussi == {"DEMO-R01": 15000, "DEMO-R02": 10000, "DEMO-G01": -10000, "DEMO-R03": -165000}
