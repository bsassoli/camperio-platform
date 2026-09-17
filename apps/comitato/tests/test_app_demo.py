import pytest

from app import app as flask_app


@pytest.fixture()
def client():
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def test_home_e_in_demo(client):
    r = client.get("/")
    testo = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "DEMO" in testo
    # il contratto sintetico compare nell'indice (per codice o per descrizione)
    assert ("DEMO01" in testo) or ("Portafoglio Demo" in testo)


def test_api_dates(client):
    r = client.get("/api/dates?schema=ANTASIMGEST&codcli=DEMO01")
    assert r.get_json() == ["2026-08-14", "2026-08-07", "2026-07-31"]


@pytest.mark.parametrize("tipo", ["matrice", "titoli", "variazioni", "comitato",
                                 "cliente_sintetica", "cliente_sintesi", "cliente_rendiconto"])
def test_preview_di_ogni_report(client, tipo):
    r = client.get("/api/preview?schema=ANTASIMGEST&codcli=DEMO01&tipo=" + tipo)
    d = r.get_json()
    assert d["ok"] is True, d.get("html", "")[:400]
    assert "note err" not in d["html"], d["html"][:400]


def test_preview_matrice_contiene_le_regole_chiave(client):
    r = client.get("/api/preview?schema=ANTASIMGEST&codcli=DEMO01&tipo=matrice")
    html = r.get_json()["html"]
    assert "KRW" in html            # Samsung GDR nella colonna giusta
    assert "Oro" in html            # oro fuori FX ma nel 100%


def test_download_matrice_excel(client):
    r = client.get("/download?schema=ANTASIMGEST&codcli=DEMO01&tipo=matrice&fmt=excel")
    assert r.status_code == 200
    assert r.data[:2] == b"PK"      # zip: xlsx valido


def test_download_comitato_word(client):
    r = client.get("/download?schema=ANTASIMGEST&codcli=DEMO01&tipo=comitato")
    assert r.status_code == 200
    assert r.data[:2] == b"PK"      # zip: docx valido


def test_al_inesistente_niente_report(client):
    r = client.get("/api/preview?schema=ANTASIMGEST&codcli=DEMO01&tipo=matrice&al=2026-08-13")
    d = r.get_json()
    assert d["ok"] is True and "non viene prodotto" in d["html"]


@pytest.mark.parametrize("tipo", ["cliente_sintetica", "cliente_sintesi", "cliente_rendiconto"])
def test_download_dei_report_al_cliente(client, tipo):
    r = client.get("/download?schema=ANTASIMGEST&codcli=DEMO01&tipo=" + tipo)
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    assert r.data[:5] == b"%PDF-"


def test_il_vecchio_cliente1_non_esiste_piu(client):
    """Sostituito dai tre report: un link vecchio deve dare 400, non un PDF sbagliato."""
    r = client.get("/download?schema=ANTASIMGEST&codcli=DEMO01&tipo=cliente1")
    assert r.status_code == 400
