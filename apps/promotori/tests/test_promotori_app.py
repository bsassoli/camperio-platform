"""App Promotori in DEMO: API, numeri sulle fixture sintetiche, errori e autenticazione."""
import pytest

from camperio_core.oracle.client import OracleIndisponibileError
from promotori import app as modulo


@pytest.fixture()
def client():
    modulo.app.config["TESTING"] = True
    return modulo.app.test_client()


def _cruscotto(client, **params):
    r = client.get("/api/cruscotto", query_string={"ref": "D00001", **params})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def test_home_in_demo(client):
    r = client.get("/")
    testo = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "MODALITÀ DEMO" in testo
    # URL relativi: la pagina deve funzionare anche sotto il prefisso /promotori/ di nginx
    assert "fetch('api/' +" in testo and "fetch('/" not in testo


def test_referenti_con_nomi_e_avviso_sul_codice_scoperto(client):
    d = client.get("/api/referenti").get_json()
    assert [r["etichetta"] for r in d["referenti"]] == [
        "D00001 — Referente Demo Uno", "D00002 — Referente Demo Due", "D00003"]
    assert d["referenti"][0]["contratti"] == 6
    assert d["nomi"]["stato"] == "ok"
    assert len(d["nomi"]["avvisi"]) == 1 and "D00003" in d["nomi"]["avvisi"][0]


def test_referenti_con_file_nomi_mancante(client, monkeypatch, tmp_path):
    monkeypatch.setattr(modulo, "PERCORSO_NOMI", tmp_path / "assente.json")
    d = client.get("/api/referenti").get_json()
    assert [r["etichetta"] for r in d["referenti"]] == ["D00001", "D00002", "D00003"]
    assert d["nomi"]["stato"] == "mancante" and "non trovato" in d["nomi"]["avvisi"][0]


def test_cruscotto_periodo_di_default(client):
    v = _cruscotto(client)
    assert v["anni"] == [2024, 2025, 2026] and v["anno"] == 2026 and v["anno_in_corso"]
    assert v["periodo"] == {"dal": "2026-01-01", "al": "2026-09-12",
                           "dal_personalizzato": False, "al_personalizzato": False}
    k = v["kpi"]
    assert k["massa"] == 2_510_000
    assert k["flusso_reale"] == 88_000
    assert k["commissioni"] == 13_100
    assert k["rendimento_commissionale"] == pytest.approx(13_100 / 2_510_000 * 100)
    assert (k["contratti_attivi"], k["contratti_aperti"], k["contratti_chiusi"]) == (4, 1, 1)
    assert k["contratti_storico"] == 6
    assert k["fondi"] == 280_000
    assert {s["chiave"]: (s["valore"], s["n"]) for s in v["masse"]} == {
        "rto": (575_000, 2), "consulenza": (350_000, 1), "gestione": (1_585_000, 2)}
    assert {s["chiave"]: (s["valore"], s["n"]) for s in v["commissioni"]["servizi"]} == {
        "rto": (2_900, 2), "consulenza": (1_700, 1), "gestione": (8_500, 2)}
    assert v["commissioni"]["per_trimestre"] == [4200, 4800, 4100, 0]
    assert v["commissioni"]["per_tipo"][0]["categoria"] == "Gestione, fee ricorrente (CDG)"
    assert {s["chiave"]: (s["valore"], s["n"]) for s in v["fondi"]["servizi"]} == {
        "rto": (25_000, 1), "consulenza": (40_000, 1), "gestione": (215_000, 2)}
    assert v["fondi"]["tutti_oicr"] == {"valore": 370_000, "n": 4}

    righe = {r["codice"]: r for r in v["contratti"]}
    assert list(righe) == ["DEMO-R01", "DEMO-R02", "DEMO-R03", "DEMO-G01", "DEMO-G02"]  # R04 chiuso nel 2025
    r01 = righe["DEMO-R01"]
    assert (r01["massa"], r01["saldo"], r01["rendimento_eur"], r01["commissioni"], r01["operazioni"]) == \
        (575_000, 15_000, 20_000, 2_600, 27)
    assert r01["rendimento_pct"] == pytest.approx((1195 / 1160 - 1) * 100)
    g02 = righe["DEMO-G02"]
    assert g02["rendimento_eur"] is None and g02["operazioni"] is None


def test_cruscotto_al_personalizzato(client):
    v = _cruscotto(client, anno="2026", al="2026-06-30")
    assert v["periodo"]["al"] == "2026-06-30" and v["periodo"]["al_personalizzato"]
    assert v["kpi"]["massa"] == 2_473_500
    assert v["kpi"]["flusso_reale"] == 80_000
    # R04, chiuso nel 2025, entra nel conteggio RTO tramite la fotografia alla data (vedi DOMANDE-EDOARDO.md)
    assert {s["chiave"]: s["n"] for s in v["masse"]} == {"rto": 3, "consulenza": 1, "gestione": 2}
    r01 = next(r for r in v["contratti"] if r["codice"] == "DEMO-R01")
    assert (r01["massa"], r01["saldo"], r01["rendimento_eur"]) == (566_000, 10_000, 16_000)


def test_cruscotto_dal_personalizzato(client):
    v = _cruscotto(client, anno="2026", dal="2026-03-31")
    assert v["periodo"] == {"dal": "2026-03-31", "al": "2026-09-12",
                           "dal_personalizzato": True, "al_personalizzato": False}
    assert v["kpi"]["massa"] == 2_510_000              # R04 ha solo lo snapshot Dal: non conta
    assert v["kpi"]["flusso_reale"] == -172_000
    righe = {r["codice"]: r for r in v["contratti"]}
    assert (righe["DEMO-R01"]["saldo"], righe["DEMO-R01"]["rendimento_eur"]) == (5_000, 18_000)
    assert righe["DEMO-G02"]["rendimento_eur"] == 4_000


def test_cruscotto_anno_chiuso(client):
    v = _cruscotto(client, anno="2025")
    assert v["periodo"]["al"] == "2025-12-31" and not v["anno_in_corso"]
    assert v["kpi"]["massa"] == 2_330_000
    assert v["kpi"]["flusso_reale"] == -27_000
    assert (v["kpi"]["contratti_attivi"], v["kpi"]["contratti_chiusi"]) == (4, 1)
    assert "DEMO-R04" in {r["codice"] for r in v["contratti"]}


@pytest.mark.parametrize("params, messaggio", [
    ({"ref": "NESSUNO"}, "sconosciuto"),
    ({"ref": "D00001' OR '1'='1"}, "sconosciuto"),
    ({"ref": "D00001", "al": "30/06/2026"}, "Data Al non valida"),
    ({"ref": "D00001", "dal": "2026-02-30"}, "Data Dal non valida"),
    ({"ref": "D00001", "anno": "duemila"}, "Anno non valido"),
    ({"ref": "D00001", "anno": "2019"}, "non disponibile"),
    ({"ref": "D00001", "dal": "2026-07-01", "al": "2026-06-30"}, "Dal non può essere successiva"),
])
def test_richieste_non_valide(client, params, messaggio):
    r = client.get("/api/cruscotto", query_string=params)
    assert r.status_code == 400
    assert messaggio in r.get_json()["errore"]


def test_con_auth_attiva_serve_l_header(client, monkeypatch):
    monkeypatch.setenv("PROMOTORI_AUTH", "1")
    assert client.get("/").status_code == 401
    assert client.get("/api/referenti").status_code == 401
    r = client.get("/", headers={"X-Auth-Request-User": "mrossi@camperiosim.com"})
    assert r.status_code == 200 and "mrossi" in r.get_data(as_text=True)


def test_oracle_irraggiungibile_da_503_leggibile(client, monkeypatch):
    def giu(*_):
        raise OracleIndisponibileError("test")
    monkeypatch.setattr(modulo.SORGENTE, "elenco_referenti", giu)
    r = client.get("/api/referenti")
    assert r.status_code == 503
    assert "Oracle non raggiungibile" in r.get_json()["errore"]


def test_dati_di_base_in_cache_e_ricarica(client, monkeypatch):
    chiamate = []
    originale = modulo.SORGENTE.contratti

    def contata(ref):
        chiamate.append(ref)
        return originale(ref)
    monkeypatch.setattr(modulo.SORGENTE, "contratti", contata)
    _cruscotto(client)
    _cruscotto(client, al="2026-06-30")          # cambio data: niente riletture dei dati di base
    assert chiamate == ["D00001"]
    _cruscotto(client, refresh="1")
    assert chiamate == ["D00001", "D00001"]
