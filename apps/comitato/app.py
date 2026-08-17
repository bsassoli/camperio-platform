# -*- coding: utf-8 -*-
"""Comitato Investimenti - app interattiva analisi portafogli Camperio SIM.
Report: Matrice Valutaria, Titoli lordo/netto vs benchmark, Pesi e scostamenti.
Date DAL/AL libere (calendario): AL deve esistere (altrimenti niente report), DAL flessibile con avviso."""
import os, tempfile, datetime
from flask import Flask, render_template, request, jsonify, send_file, Response
import data_layer as DL
import lookthrough as L
import report_comitato as RC
import report_cliente as RCLI

app = Flask(__name__)
BUILD = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
TIPI = {"matrice": "Matrice Valutaria", "titoli": "Titoli lordo/netto vs benchmark",
        "variazioni": "Variazioni prezzi", "comitato": "Sintesi Comitato (Word)"}
TIPI_CLI = {"cliente1": "Cliente — Sintetico (PDF)"}
LABEL = {**TIPI, **TIPI_CLI}

def current_user():
    """Utente autenticato dal reverse proxy (IIS Windows Auth -> header). None se assente."""
    u = (request.headers.get("X-Auth-Request-User")
         or request.headers.get("X-Remote-User") or request.headers.get("X-Forwarded-User")
         or request.environ.get("REMOTE_USER"))
    if not u:
        return None
    return u.split("\\")[-1].split("@")[0]

@app.before_request
def _gate():
    # Se COMITATO_AUTH=1, richiede l'utente dal proxy (blocca accesso diretto bypassando IIS).
    import os as _os
    if _os.getenv("COMITATO_AUTH", "0") != "1":
        return
    if request.path.startswith("/static"):
        return
    if not current_user():
        return Response("Accesso riservato — autenticazione aziendale richiesta (login Windows).",
                        status=401, mimetype="text/plain; charset=utf-8")

@app.after_request
def _nocache(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"; resp.headers["Expires"] = "0"
    return resp

@app.route("/")
def index():
    return render_template("index.html", mode=DL.mode(), contratti=DL.list_contratti(),
                           schemi=DL.SCHEMI, tipi=TIPI, tipi_cli=TIPI_CLI, build=BUILD, utente=current_user() or "")

@app.route("/api/dates")
def api_dates():
    return jsonify(DL.available_dates(request.args.get("schema"), request.args.get("codcli")))

@app.route("/api/repo-status")
def api_repo_status():
    return jsonify(DL.repo_status())

@app.route("/upload", methods=["POST"])
def upload():
    res = DL.save_uploads(request.files.getlist("file"))
    if not res:
        return jsonify(ok=False, msg="Nessun file valido (.xlsx .xls .csv).")
    parts = []
    for r in res:
        if r.get("errore"): parts.append(r["originale"] + " - ERRORE")
        elif r.get("fondo"): parts.append(r["fondo"] + " -> " + (r.get("data") or "data non rilevata"))
        else: parts.append(r["originale"] + " - non riconosciuto")
    return jsonify(ok=any(not r.get("errore") for r in res), msg="Caricato: " + "; ".join(parts), saved=[r["file"] for r in res])

@app.route("/download-etf", methods=["POST"])
def download_etf_route():
    res = DL.download_etf(); ok = [r for r in res if r.get("ok")]
    msg = ("Scaricati " + str(len(ok)) + "/" + str(len(res)) + " ETF: " + ", ".join(r["ticker"] for r in ok)) if ok \
          else "Nessun ETF scaricato: dominio iShares non raggiungibile (whitelist IT)."
    return jsonify(ok=bool(ok), msg=msg, dettaglio=res)

def _report_html(tipo, pf):
    if tipo == "matrice": return L.matrice_html(L.build_matrix(pf, DL.REPO))
    if tipo == "titoli":  return L.titoli_html(L.build_titoli(pf, DL.REPO))
    if tipo == "variazioni": return L.variazioni_html(L.build_variazioni(pf, DL.REPO))
    if tipo == "comitato": return RC.comitato_html(RC.build_comitato(pf, DL.REPO))
    if tipo == "cliente1": return RCLI.cliente_html(RCLI.build_cliente(pf, DL.REPO))
    return '<div class="note err">Tipo report non disponibile.</div>'

@app.route("/api/preview")
def api_preview():
    schema = request.args.get("schema"); codcli = request.args.get("codcli")
    tipo = request.args.get("tipo", "matrice")
    rp = DL.resolve_period(schema, codcli, request.args.get("dal") or None, request.args.get("al") or None)
    if not rp["ok"]:
        return jsonify(ok=True, html='<div class="note err">' + rp["error"] + '</div>')
    try:
        pf = DL.get_portfolio(schema, codcli, dal=rp["dal"], al=rp["al"])
        html = _report_html(tipo, pf)
        if rp.get("warn"):
            html = '<div class="note">&#9888; ' + rp["warn"] + '</div>' + html
        return jsonify(ok=True, html=html)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify(ok=False, html='<div class="note err">Errore: ' + str(e) + '</div>')

@app.route("/download")
def download():
    schema = request.args.get("schema"); codcli = request.args.get("codcli")
    tipo = request.args.get("tipo", "matrice"); fmt = request.args.get("fmt", "excel")
    if tipo == "comitato": fmt = "word"
    if tipo in TIPI_CLI: fmt = "pdf"
    if tipo not in LABEL:
        return Response("Tipo report non valido.", status=400, mimetype="text/plain")
    rp = DL.resolve_period(schema, codcli, request.args.get("dal") or None, request.args.get("al") or None)
    if not rp["ok"]:
        return Response(rp["error"], status=409, mimetype="text/plain; charset=utf-8")
    pf = DL.get_portfolio(schema, codcli, dal=rp["dal"], al=rp["al"])
    d = pf["meta"]["data"]; safe = codcli.replace("/", "_")
    base = LABEL[tipo].replace(" ", "_").replace("/", "-").replace("(", "").replace(")", "") + "_" + safe + "_" + str(d)
    tmp = tempfile.gettempdir()
    ext = ".pdf" if fmt == "pdf" else (".xlsx" if fmt == "excel" else ".docx")
    path = os.path.join(tmp, base + ext)
    if tipo == "matrice":
        m = L.build_matrix(pf, DL.REPO); (L.matrice_excel if fmt == "excel" else L.matrice_word)(m, path)
    elif tipo == "titoli":
        t = L.build_titoli(pf, DL.REPO); (L.titoli_excel if fmt == "excel" else L.titoli_word)(t, path)
    elif tipo == "variazioni":
        v = L.build_variazioni(pf, DL.REPO); (L.variazioni_excel if fmt == "excel" else L.variazioni_word)(v, path)
    elif tipo == "comitato":
        RC.comitato_word(RC.build_comitato(pf, DL.REPO), path)
    elif tipo == "cliente1":
        RCLI.cliente_pdf(RCLI.build_cliente(pf, DL.REPO), path)
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    print("\n  Comitato Camperio - " + DL.mode() + " - build " + BUILD + " - http://127.0.0.1:" + str(port) + "\n", flush=True)
    app.run(host="0.0.0.0", port=port, debug=False)
