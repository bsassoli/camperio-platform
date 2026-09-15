"""Monitoraggio Promotori: cruscotto per referente commerciale (Camperio SIM).

Porting dell'artifact cowork `edoricc/monitoraggio-promotori`: stesse query e stessi numeri.
Le query però girano qui, con bind variable e il client Oracle di piattaforma, e i calcoli
stanno in `calcoli.py`, coperti da test. La pagina si limita a mostrare.

Avvio locale: `cd apps/promotori && ../../.venv/bin/python -m promotori.app`.
"""
import datetime
import os
import re
import threading
import time
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

from camperio_core import config as _config
from camperio_core.oracle.client import OracleIndisponibileError
from promotori import calcoli as C
from promotori import nomi as N
from promotori.dati import FIXTURES, Sorgente

app = Flask(__name__)
BUILD = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
SORGENTE = Sorgente()
PERCORSO_NOMI = None      # None: lo decide la modalità (vedi percorso_nomi); i test lo sovrascrivono
DURATA_CACHE = 300        # secondi in cui elenco e dati di base di un referente non si rileggono

_DATA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_cache = {}
_cache_lock = threading.Lock()


def current_user():
    """Utente autenticato da oauth2-proxy (header). None se assente."""
    u = request.headers.get("X-Auth-Request-User") or request.environ.get("REMOTE_USER")
    return u.split("\\")[-1].split("@")[0] if u else None


@app.before_request
def _gate():
    # Con PROMOTORI_AUTH=1 serve l'utente dal proxy: blocca l'accesso diretto al container.
    if os.getenv("PROMOTORI_AUTH", "0") != "1" or request.path.startswith("/static"):
        return None
    if not current_user():
        return Response("Accesso riservato — autenticazione aziendale richiesta.",
                        status=401, mimetype="text/plain; charset=utf-8")
    return None


@app.after_request
def _nocache(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


def percorso_nomi():
    if PERCORSO_NOMI is not None:
        return Path(PERCORSO_NOMI)
    if SORGENTE.live:
        return _config.from_env().data_dir / "promotori" / "nomi-referenti.json"
    return FIXTURES / "nomi-referenti.json"


def svuota_cache():
    with _cache_lock:
        _cache.clear()


def _da_cache(chiave, carica, rinfresca=False):
    with _cache_lock:
        voce = _cache.get(chiave)
    if voce and not rinfresca and time.monotonic() - voce[0] < DURATA_CACHE:
        return voce[1]
    valore = carica()
    with _cache_lock:
        _cache[chiave] = (time.monotonic(), valore)
    return valore


def _referenti():
    return _da_cache(("referenti",), SORGENTE.elenco_referenti)


def _dati_base(ref, rinfresca):
    """Le sei query che non dipendono dalle date. Si rileggono con «Ricarica»."""
    return _da_cache(("base", ref), lambda: {
        "contratti": SORGENTE.contratti(ref),
        "sre": SORGENTE.sre(ref),
        "comm_contratto": SORGENTE.commissioni_per_contratto(ref),
        "comm_trimestre": SORGENTE.commissioni_per_trimestre(ref),
        "comm_tipo": SORGENTE.commissioni_per_tipo(ref),
        "operazioni": SORGENTE.operazioni(ref),
    }, rinfresca)


def _data(valore, etichetta):
    if not valore:
        return None
    try:
        if not _DATA_ISO.match(valore):
            raise ValueError
        datetime.date.fromisoformat(valore)
    except ValueError:
        raise C.PeriodoNonValido(f"Data {etichetta} non valida: serve il formato AAAA-MM-GG.") from None
    return valore


def _anno(valore):
    if not valore:
        return None
    if not valore.isdigit():
        raise C.PeriodoNonValido("Anno non valido.")
    return int(valore)


def _errore(messaggio, status):
    return jsonify(errore=messaggio), status


@app.route("/")
def index():
    return render_template("index.html", mode=SORGENTE.mode(), utente=current_user() or "",
                           build=BUILD)


@app.route("/api/referenti")
def api_referenti():
    righe = _referenti()
    nomi = N.carica(percorso_nomi())
    codici = [r["REFCOM"] for r in righe]
    return jsonify(
        referenti=[{"codice": r["REFCOM"], "etichetta": nomi.etichetta(r["REFCOM"]),
                    "contratti": int(C.num(r["N"]))} for r in righe],
        nomi={"stato": nomi.stato, "avvisi": nomi.avvisi + N.avvisi_copertura(nomi, codici)},
    )


@app.route("/api/cruscotto")
def api_cruscotto():
    ref = request.args.get("ref", "")
    if ref not in {r["REFCOM"] for r in _referenti()}:
        return _errore("Referente commerciale sconosciuto.", 400)
    try:
        anno = _anno(request.args.get("anno"))
        dal = _data(request.args.get("dal"), "Dal")
        al = _data(request.args.get("al"), "Al")
    except C.PeriodoNonValido as e:
        return _errore(str(e), 400)

    stato = C.costruisci_stato(**_dati_base(ref, request.args.get("refresh") == "1"))
    if not stato.anni:
        return jsonify(vuoto=True, messaggio="Nessuna massa disponibile per questo referente "
                                             "negli ultimi 5 anni.")
    try:
        periodo = C.risolvi_periodo(stato, anno, dal, al)
    except C.PeriodoNonValido as e:
        return _errore(str(e), 400)

    # Prima Al e poi Dal: lo snapshot Al sostituisce l'anno, quello Dal vi si aggiunge.
    if periodo.al_personalizzato:
        C.applica_al(stato, periodo.anno, SORGENTE.sre_alla_data(ref, periodo.al))
    if periodo.dal_personalizzato:
        C.applica_dal(stato, periodo.anno, SORGENTE.sre_alla_data(ref, periodo.dal))
    # In sequenza come nell'originale: fondi e flussi leggono tabelle molto grandi.
    fondi = SORGENTE.fondi(ref, periodo.al)
    fondi_totale = SORGENTE.fondi_totale(ref, periodo.al)
    flussi = SORGENTE.flussi_reali(ref, periodo.dal, periodo.al)
    return jsonify(C.componi_cruscotto(stato, periodo, fondi, fondi_totale, flussi))


@app.errorhandler(OracleIndisponibileError)
def _oracle_giu(e):
    messaggio = "Oracle non raggiungibile con configurazione LIVE: i dati non vengono mostrati."
    if request.path.startswith("/api/"):
        return _errore(messaggio, 503)
    return Response(messaggio, status=503, mimetype="text/plain; charset=utf-8")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5002"))
    print(f"\n  Monitoraggio Promotori - {SORGENTE.mode()} - build {BUILD} - "
          f"http://127.0.0.1:{port}\n", flush=True)
    # il contratto di piattaforma non espone mai l'app direttamente: bind su 127.0.0.1
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=port, debug=False)
