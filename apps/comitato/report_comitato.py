# -*- coding: utf-8 -*-
"""Report 4 - Sintesi Comitato (Word). Performance di periodo e YTD vs benchmark (SRE),
pesi per asset class AL vs DAL con i 3 fondi separati (WCTDD+VAL), esposizione azionaria
DELTA-ADJUSTED (dirette + delta azionario fondi - copertura derivati), settori, EM,
top/bottom performance, contributori/detrattori, operazioni del periodo (ORD). Dati da Oracle."""
import html as _html
import os
from camperio_core.oracle.client import OracleIndisponibileError
import data_layer as DL
import lookthrough as L

def _pct(x, dec=2, sign=False):
    if x is None: return "n.d."
    fmt = ("{:+." if sign else "{:.") + str(dec) + "f}"
    return fmt.format(x * 100).replace(".", ",") + "%"

def _eur(x):
    return "{:,.0f}".format(round(x or 0)).replace(",", ".") + " €"

def _num(x, dec=2):
    return ("{:,." + str(dec) + "f}").format(x or 0).replace(",", "§").replace(".", ",").replace("§", ".")

_DEV = {"EUR", "USD", "GBP", "CHF", "JPY", "NOK", "DKK", "SEK", "CAD", "Oro", "Altro (<1%)"}

def _it(iso):
    return (iso[8:10] + "/" + iso[5:7] + "/" + iso[0:4]) if (iso and len(iso) >= 10) else (iso or "")

def _peso_azioni_storico(hist, al_iso, eq_eur, nav):
    """Confronto del peso azionario (dirette+ETF) vs settimana precedente / inizio mese / inizio anno."""
    import datetime as _dt
    cur = (eq_eur / nav) if nav else None
    al = _dt.date.fromisoformat(al_iso)
    past = [h for h in hist if h.get("date") and h["date"] < al_iso and h.get("pct") is not None]
    def near_week():
        if not past: return None
        tgt = al - _dt.timedelta(days=7)
        return min(past, key=lambda h: abs((_dt.date.fromisoformat(h["date"]) - tgt).days))
    def period_start(first_iso):
        inp = [h for h in past if h["date"] >= first_iso]
        if inp: return min(inp, key=lambda h: h["date"])          # primo snapshot del periodo
        before = [h for h in past if h["date"] < first_iso]
        return before[-1] if before else None                     # carry-forward dell'ultimo prima
    refs = {"week": near_week(),
            "month": period_start(al.replace(day=1).isoformat()),
            "year": period_start(al.replace(month=1, day=1).isoformat())}
    out = {"cur_pct": cur, "cur_eur": eq_eur, "n": len(hist)}
    for k, r in refs.items():
        out[k] = None if (r is None or cur is None) else {"pct": r["pct"], "date": r["date"], "delta": cur - r["pct"]}
    return out

def _pesi_inizio_mese(hist, al_iso):
    """Ultimo snapshot dei pesi per asset class registrato a inizio mese (o carry-forward
    dell'ultimo disponibile prima, se il mese e' appena iniziato). hist e' gia' ordinato per data."""
    import datetime as _dt
    first_iso = _dt.date.fromisoformat(al_iso).replace(day=1).isoformat()
    past = [h for h in hist if h.get("date") and h["date"] < al_iso]
    inp = [h for h in past if h["date"] >= first_iso]
    if inp:
        return min(inp, key=lambda h: h["date"])
    return past[-1] if past else None

def build_comitato(pf, repo_dir):
    """Costruisce i dati della Sintesi Comitato.
    EFFETTO COLLATERALE: a ogni chiamata scrive in history/ lo snapshot del peso azionario
    e dei pesi per asset class alla data del portafoglio (accumulo in avanti, non ricostruibile)."""
    meta = pf["meta"]
    info = DL.contract_info(meta["schema"], meta["codcli"])
    var = L.build_variazioni(pf, repo_dir)
    mat = L.build_matrix(pf, repo_dir)
    tit = L.build_titoli(pf, repo_dir)
    ex = DL.comitato_extra(meta["schema"], meta["codcli"], meta.get("data_prec"), meta["data"])
    nav_al = ex.get("nav_al") or float(meta.get("nav") or 0) or 1.0
    nav_dal = ex.get("nav_dal") or nav_al
    # performance periodo + YTD
    ret = (ex["tcli_al"] / ex["tcli_dal"] - 1) if ex.get("tcli_dal") else None
    bmk = (ex["tbmk_al"] / ex["tbmk_dal"] - 1) if ex.get("tbmk_dal") else None
    dret = (ret - bmk) if (ret is not None and bmk is not None) else None
    rytd = (ex["tcli_al"] / ex["tcli_base"] - 1) if ex.get("tcli_base") else None
    bytd = (ex["tbmk_al"] / ex["tbmk_base"] - 1) if ex.get("tbmk_base") else None
    dytd = (rytd - bytd) if (rytd is not None and bytd is not None) else None
    # pesi asset class (fondi gia' separati da comitato_extra)
    comp = []
    for c in ex.get("comp", []):
        pa = c["val_al"] / nav_al; pd = c["val_dal"] / nav_dal
        comp.append({"macro": c["macro"], "pa": pa, "pd": pd, "d": pa - pd})
    comp.sort(key=lambda x: -x["pa"])
    # pesi ad inizio mese per asset class (storico dedicato, carry-forward come per il peso azionario)
    al_iso = meta["data"]
    hist_classi = DL.update_class_weight_history(meta["codcli"], al_iso, {c["macro"]: c["pa"] for c in comp}, nav_al)
    ref_mese = _pesi_inizio_mese(hist_classi, al_iso)
    for c in comp:
        c["pm"] = (ref_mese["pesi"].get(c["macro"]) if ref_mese else None)
    mese_info = {"date": ref_mese["date"] if ref_mese else None, "n": len(hist_classi)}
    # esposizione azionaria DELTA-ADJUSTED (motore Titoli)
    navt = tit.get("nav") or nav_al
    e_dir = tit.get("tot_diretto", 0.0) / navt
    e_fond = (tit.get("tot_fondi", 0.0) + tit.get("tot_indici", 0.0)) / navt
    e_hed = tit.get("tot_hedge", 0.0) / navt
    e_net = tit.get("tot_netto", 0.0) / navt
    em = sum(v for cc, v in mat["totale"].items() if cc not in _DEV)
    em_pct = em / mat["nav"] if mat.get("nav") else 0.0
    # settori (azioni dirette, vista Variazioni)
    eqrows = [r for r in var["rows"] if r["var"] is not None]
    sett = {}
    for r in eqrows:
        sett[r["settore"]] = sett.get(r["settore"], 0.0) + r["peso"]
    sett = sorted(sett.items(), key=lambda x: -x[1])
    # top/bottom performance e contributi
    byvar = sorted(eqrows, key=lambda r: -r["var"])
    top = byvar[:10]; bot = list(reversed(byvar[-10:]))
    contrib_class = sorted([{"macro": c["macro"], "contrib": (c["pa"] * nav_al - c["pd"] * nav_dal) / nav_dal}
                            for c in comp], key=lambda x: -x["contrib"])
    bycon = sorted(eqrows, key=lambda r: -(r["peso"] * r["var"]))
    ctop = bycon[:10]; cbot = list(reversed(bycon[-10:]))
    # peso azionario (azioni dirette + ETF azionari/REIT) e andamento nel tempo (accumulo in avanti)
    eq_dir_etf = sum(p.get("valmer", 0.0) for p in pf["positions"]
                     if (p.get("grutit") or "").upper().startswith("E")
                     or (p.get("grutit") or "").upper() in ("H10", "H16", "H18", "H23"))
    hist = DL.update_weight_history(meta["codcli"], al_iso, eq_dir_etf, nav_al)
    paz = _peso_azioni_storico(hist, al_iso, eq_dir_etf, nav_al)
    try:
        dett = DL.dettaglio_mensile(meta["schema"], meta["codcli"], meta.get("data_prec"), meta["data"], nav_dal, nav_al)
    except OracleIndisponibileError:
        raise                         # fail-safe di piattaforma: mai un report parziale su Oracle giu'
    except Exception:
        import traceback; traceback.print_exc(); dett = None
    return {"dal": var["dal"], "al": var["al"], "bench": ex.get("bench", ""), "paz": paz, "dett": dett,
            "codcli": meta["codcli"], "descli": info.get("descli") or meta.get("descli") or meta["codcli"],
            "nav_al": nav_al, "nav_dal": nav_dal,
            "ret": ret, "bmk": bmk, "dret": dret, "rytd": rytd, "bytd": bytd, "dytd": dytd,
            "comp": comp, "mese_info": mese_info, "e_dir": e_dir, "e_fond": e_fond, "e_hed": e_hed, "e_net": e_net, "em_pct": em_pct,
            "sett": sett, "top": top, "bot": bot, "ctop": ctop, "cbot": cbot,
            "trades": ex.get("trades", []), "best": var.get("best"), "worst": var.get("worst"),
            "contrib_class": contrib_class}

def comitato_word(d, path):
    from docx.shared import Pt, RGBColor
    titolo_linea = d["descli"] + " (" + d["codcli"] + ")"
    doc = L._doc("Sintesi Comitato Investimenti — " + titolo_linea,
                 "Periodo " + d["dal"] + " → " + d["al"] + " · benchmark " + (d["bench"] or "—")
                 + " · NAV " + _eur(d["nav_al"]) + " · USO INTERNO")
    def h(txt):
        p = doc.add_paragraph(); r = p.add_run(txt); r.bold = True; r.font.size = Pt(11)
        r.font.color.rgb = RGBColor(0x15, 0x1F, 0x6D)
    # 1. Performance
    h("1. Performance vs benchmark")
    L._table(doc, ["Orizzonte", "Portafoglio", "Benchmark " + (d["bench"] or ""), "Scostamento p.p."],
             [["Periodo (" + d["dal"] + " → " + d["al"] + ")", _pct(d["ret"], 2, True), _pct(d["bmk"], 2, True), _pct(d["dret"], 2, True)],
              ["Da inizio anno (YTD)", _pct(d["rytd"], 2, True), _pct(d["bytd"], 2, True), _pct(d["dytd"], 2, True)]])
    doc.add_paragraph("NAV da " + _eur(d["nav_dal"]) + " a " + _eur(d["nav_al"]) + ".")
    # 2. Pesi per asset class (fondi separati)
    h("2. Pesi di linea per asset class (vs " + d["dal"] + ")")
    mi = d.get("mese_info") or {}
    L._table(doc, ["Asset class / fondo", "% NAV " + d["al"][:5], "% NAV " + d["dal"][:5], "% inizio mese", "Δ p.p."],
             [[c["macro"], _pct(c["pa"]), _pct(c["pd"]),
               (_pct(c.get("pm")) if c.get("pm") is not None else "n.d."), _pct(c["d"], 2, True)] for c in d["comp"]]
             + [["TOTALE", "100,00%", "100,00%", ("100,00%" if mi.get("date") else "n.d."), ""]])
    nota2 = doc.add_paragraph()
    if mi.get("date"):
        nota2.add_run("Peso a inizio mese riportato dalla rilevazione del " + _it(mi["date"])
                      + " (storico interno, " + str(mi.get("n", 0)) + " rilevazion"
                      + ("e" if mi.get("n", 0) == 1 else "i") + " salvate).").italic = True
    else:
        nota2.add_run("Peso a inizio mese non ancora disponibile: nessuna rilevazione storica precedente al periodo corrente.").italic = True
    # 3. Esposizione azionaria DELTA-ADJUSTED
    h("3. Esposizione azionaria delta-adjusted")
    L._table(doc, ["Componente", "% NAV"],
             [["Azioni dirette", _pct(d["e_dir"])],
              ["Azionario via fondi (delta: equity + indici)", _pct(d["e_fond"], 2, True)],
              ["Copertura derivati su indice", _pct(d["e_hed"], 2, True)],
              ["= Esposizione azionaria netta delta-adjusted", _pct(d["e_net"])],
              ["Di cui mercati emergenti (look-through)", _pct(d["em_pct"])]])
    # 3-bis. Andamento peso azionario (dirette + ETF) nel tempo
    p = d.get("paz") or {}
    h("3-bis. Andamento peso azionario (azioni dirette + ETF)")
    def _wrow(lbl, r):
        return [lbl, _it(r["date"]), _pct(r["pct"]), _pct(r["delta"], 2, True)] if r else [lbl, "—", "in accumulo", "—"]
    L._table(doc, ["Riferimento", "Data", "Peso azioni (dir.+ETF) % NAV", "Δ vs attuale p.p."],
             [["Attuale", d["al"], _pct(p.get("cur_pct")), "—"],
              _wrow("Inizio settimana", p.get("week")),
              _wrow("Inizio mese", p.get("month")),
              _wrow("Inizio anno", p.get("year"))])
    _npt = p.get("n", 0)
    nota = doc.add_paragraph()
    nota.add_run("Azioni dirette + ETF azionari = " + _eur(p.get("cur_eur")) + ". La serie viene registrata a ogni generazione del report ("
                 + str(_npt) + " rilevazion" + ("e" if _npt == 1 else "i") + "); i confronti con settimana/mese/anno si popolano man mano che lo storico matura.").italic = True
    # 4. Settori
    h("4. Peso per settore (azioni in portafoglio)")
    L._table(doc, ["Settore", "% NAV"], [[s, _pct(w)] for s, w in d["sett"]])
    # 5. Migliori/peggiori
    h("5. Migliori e peggiori per performance di periodo")
    L._table(doc, ["#", "Migliori 10", "Var. %", "Peggiori 10", "Var. %"],
             [[i + 1, d["top"][i]["name"], _pct(d["top"][i]["var"], 2, True),
               (d["bot"][i]["name"] if i < len(d["bot"]) else ""),
               (_pct(d["bot"][i]["var"], 2, True) if i < len(d["bot"]) else "")] for i in range(min(10, len(d["top"])))])
    # 6. Contributori/detrattori
    h("6. Contributori e detrattori di performance (peso × variazione, p.p.)")
    L._table(doc, ["#", "Top contributori", "Contrib. p.p.", "Top detrattori", "Contrib. p.p."],
             [[i + 1, d["ctop"][i]["name"], _pct(d["ctop"][i]["peso"] * d["ctop"][i]["var"], 3, True),
               (d["cbot"][i]["name"] if i < len(d["cbot"]) else ""),
               (_pct(d["cbot"][i]["peso"] * d["cbot"][i]["var"], 3, True) if i < len(d["cbot"]) else "")] for i in range(min(10, len(d["ctop"])))])
    doc.add_paragraph().add_run("Contributo per classe di attivo (p.p.) — include azioni, fondi, obbligazioni, oro, derivati").italic = True
    L._table(doc, ["Classe di attivo", "Contributo p.p."],
             [[c["macro"], _pct(c["contrib"], 3, True)] for c in d["contrib_class"]])
    # 7. Operazioni con segno
    h("7. Operazioni del periodo")
    if d["trades"]:
        L._table(doc, ["Data", "Titolo", "Operazione", "Quantità", "Prezzo", "Controvalore €"],
                 [[t["data"], t["nome"], t["verso"], _num(t["qty"], 0), _num(t["prezzo"], 2), _eur(t["ctv"])] for t in d["trades"]])
    else:
        doc.add_paragraph("Nessuna operazione di compravendita nel periodo (esclusi movimenti di cambio).")
    # 8-10. Dettaglio titolo-per-titolo (azioni, fondi/ETF, oro) — da MOV+VAL, total-return EUR
    dt = d.get("dett")
    pdal = d["dal"][:5]; pal = d["al"][:5]
    def _nm(r):
        s = r["nome"] + (" *" if r.get("div") else "")
        if r.get("stato") == "nuova": s += " (nuova)"
        elif r.get("stato") == "chiusa": s += " (chiusa)"
        return s
    h("8. Dettaglio azioni — peso e performance titolo per titolo")
    if dt:
        L._table(doc, ["Titolo", "Peso " + pdal, "Peso " + pal, "Δ p.p.", "Perf. EUR", "Perf. loc."],
                 [[_nm(r), _pct(r["peso_dal"]), _pct(r["peso_al"]), _pct(r["d"], 2, True), _pct(r["perf_eur"], 2, True), _pct(r["perf_loc"], 2, True)] for r in dt["azioni"]]
                 + [["TOTALE AZIONI", _pct(dt["az_tot_dal"]), _pct(dt["az_tot_al"]), _pct(dt["az_tot_al"] - dt["az_tot_dal"], 2, True), "", ""]])
        doc.add_paragraph("* dividendo staccato nel periodo (incluso nella Perf. EUR total-return). (nuova)/(chiusa) = posizione aperta/chiusa nel mese. Perf. EUR = prezzo+cambio+dividendi; Perf. loc. = solo prezzo in valuta locale.").italic = True
    else:
        doc.add_paragraph("Dettaglio mensile non disponibile in questa modalità.")
    h("9. Fondi ed ETF")
    if dt:
        L._table(doc, ["Strumento", "Peso " + pdal, "Peso " + pal, "Δ p.p.", "Perf. EUR"],
                 [[_nm(r), _pct(r["peso_dal"]), _pct(r["peso_al"]), _pct(r["d"], 2, True), _pct(r["perf_eur"], 2, True)] for r in dt["fondi_etf"]]
                 + [["TOTALE FONDI/ETF", _pct(dt["fe_tot_dal"]), _pct(dt["fe_tot_al"]), _pct(dt["fe_tot_al"] - dt["fe_tot_dal"], 2, True), ""]])
    else:
        doc.add_paragraph("Dettaglio mensile non disponibile in questa modalità.")
    h("10. Oro fisico")
    if dt and dt["oro"]:
        L._table(doc, ["Strumento", "Peso " + pdal, "Peso " + pal, "Perf. EUR"],
                 [[r["nome"], _pct(r["peso_dal"]), _pct(r["peso_al"]), _pct(r["perf_eur"], 2, True)] for r in dt["oro"]])
    elif dt:
        doc.add_paragraph("Nessuna posizione in oro fisico nel periodo.")
    else:
        doc.add_paragraph("Dettaglio mensile non disponibile in questa modalità.")
    doc.save(path); return path

def comitato_html(d):
    def cc(x): return "1F7A4D" if (x or 0) >= 0 else "B3261E"
    def esc(x): return _html.escape(str(x or ""))   # ogni stringa da Oracle passa di qui
    titolo_linea = _html.escape(str(d.get("descli") or d.get("codcli") or "")) + " (" + _html.escape(str(d.get("codcli") or "")) + ")"
    head = (f'<div class="rh"><div class="rt">Sintesi Comitato — {titolo_linea}</div>'
            f'<div class="rs">Periodo {d["dal"]} &#8594; {d["al"]} · benchmark {esc(d["bench"])} · NAV {_eur(d["nav_al"])} · export in Word</div></div>')
    kp = ('<div class="kp">'
          + f'<div class="ki"><div class="kl">Perf. periodo</div><div class="kv" style="color:#{cc(d["ret"])}">{_pct(d["ret"],2,True)}</div><div class="ks">bench {_pct(d["bmk"],2,True)} · Δ {_pct(d["dret"],2,True)} pp</div></div>'
          + f'<div class="ki"><div class="kl">Perf. YTD</div><div class="kv" style="color:#{cc(d["rytd"])}">{_pct(d["rytd"],2,True)}</div><div class="ks">bench {_pct(d["bytd"],2,True)} · Δ {_pct(d["dytd"],2,True)} pp</div></div>'
          + f'<div class="ki"><div class="kl">Azionario netto delta-adj</div><div class="kv">{_pct(d["e_net"])}</div><div class="ks">diretta {_pct(d["e_dir"])} · EM {_pct(d["em_pct"])}</div></div>'
          + f'<div class="ki"><div class="kl">Operazioni periodo</div><div class="kv">{len(d["trades"])}</div><div class="ks">con segno acq./vend.</div></div>'
          + '</div>')
    def tbl(headers, rows):
        th = "".join((f"<th class=r>{x}</th>" if i else f"<th>{x}</th>") for i, x in enumerate(headers))
        body = "".join("<tr>" + "".join((f"<td class=r>{c}</td>" if i else f"<td>{c}</td>") for i, c in enumerate(r)) + "</tr>" for r in rows)
        return f'<div style="overflow-x:auto"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'
    comp = tbl(["Asset class / fondo", "% " + d["al"][:5], "% " + d["dal"][:5], "% inizio mese", "Δ pp"],
               [[esc(c["macro"]), _pct(c["pa"]), _pct(c["pd"]),
                 (_pct(c.get("pm")) if c.get("pm") is not None else "n.d."), _pct(c["d"], 2, True)] for c in d["comp"]])
    _mi = d.get("mese_info") or {}
    comp += ('<div class="note">Peso a inizio mese dalla rilevazione del ' + _it(_mi["date"]) + '.</div>'
             if _mi.get("date") else '<div class="note">Peso a inizio mese non ancora disponibile (nessuna rilevazione storica precedente).</div>')
    eqt = tbl(["Componente", "% NAV"],
              [["Azioni dirette", _pct(d["e_dir"])],
               ["Azionario via fondi (delta)", _pct(d["e_fond"], 2, True)],
               ["Copertura derivati su indice", _pct(d["e_hed"], 2, True)],
               ["= Azionario netto delta-adjusted", _pct(d["e_net"])],
               ["di cui Emerging Markets", _pct(d["em_pct"])]])
    p = d.get("paz") or {}
    def _prow(lbl, r):
        return [lbl, _it(r["date"]), _pct(r["pct"]), _pct(r["delta"], 2, True)] if r else [lbl, "—", "in accumulo", "—"]
    pazt = tbl(["Riferimento", "Data", "Peso azioni (dir.+ETF)", "Δ vs attuale pp"],
               [["Attuale", d["al"], _pct(p.get("cur_pct")), "—"],
                _prow("Inizio settimana", p.get("week")),
                _prow("Inizio mese", p.get("month")),
                _prow("Inizio anno", p.get("year"))])
    sett = tbl(["Settore", "% NAV"], [[esc(s), _pct(w)] for s, w in d["sett"]])
    perf = tbl(["#", "Migliori 10", "Var. %", "Peggiori 10", "Var. %"],
               [[i + 1, esc(d["top"][i]["name"]), _pct(d["top"][i]["var"], 2, True),
                 (esc(d["bot"][i]["name"]) if i < len(d["bot"]) else ""),
                 (_pct(d["bot"][i]["var"], 2, True) if i < len(d["bot"]) else "")] for i in range(min(10, len(d["top"])))])
    contr = tbl(["#", "Contributori", "p.p.", "Detrattori", "p.p."],
                [[i + 1, esc(d["ctop"][i]["name"]), _pct(d["ctop"][i]["peso"] * d["ctop"][i]["var"], 3, True),
                  (esc(d["cbot"][i]["name"]) if i < len(d["cbot"]) else ""),
                  (_pct(d["cbot"][i]["peso"] * d["cbot"][i]["var"], 3, True) if i < len(d["cbot"]) else "")] for i in range(min(10, len(d["ctop"])))])
    clazz = tbl(["Classe di attivo", "Contributo p.p."], [[esc(c["macro"]), _pct(c["contrib"], 3, True)] for c in d["contrib_class"]])
    trd = (tbl(["Data", "Titolo", "Operazione", "Quantità", "Prezzo", "Controvalore"],
               [[esc(t["data"]), esc(t["nome"]), esc(t["verso"]), _num(t["qty"], 0), _num(t["prezzo"], 2), _eur(t["ctv"])] for t in d["trades"]])
           if d["trades"] else '<div class="note">Nessuna operazione nel periodo (esclusi cambi).</div>')
    dt = d.get("dett")
    _nd = '<div class="note">Dettaglio mensile non disponibile in questa modalità.</div>'
    if dt:
        def _nm(r):
            s = _html.escape(str(r["nome"] or "")) + (" *" if r.get("div") else "")
            if r.get("stato") == "nuova": s += ' <span style="color:#2E5A9E">(nuova)</span>'
            elif r.get("stato") == "chiusa": s += ' <span style="color:#B36B00">(chiusa)</span>'
            return s
        pdal = d["dal"][:5]; pal = d["al"][:5]
        azt = tbl(["Titolo", "Peso " + pdal, "Peso " + pal, "Δ pp", "Perf. EUR", "Perf. loc."],
                  [[_nm(r), _pct(r["peso_dal"]), _pct(r["peso_al"]), _pct(r["d"], 2, True), _pct(r["perf_eur"], 2, True), _pct(r["perf_loc"], 2, True)] for r in dt["azioni"]]
                  + [["<b>TOTALE AZIONI</b>", "<b>" + _pct(dt["az_tot_dal"]) + "</b>", "<b>" + _pct(dt["az_tot_al"]) + "</b>", _pct(dt["az_tot_al"] - dt["az_tot_dal"], 2, True), "", ""]])
        azt += '<div style="font-size:11.5px;color:#666;margin-top:4px">* dividendo nel periodo (incluso nella Perf. EUR); (nuova)/(chiusa) = aperta/chiusa nel mese.</div>'
        fet = tbl(["Strumento", "Peso " + pdal, "Peso " + pal, "Δ pp", "Perf. EUR"],
                  [[_nm(r), _pct(r["peso_dal"]), _pct(r["peso_al"]), _pct(r["d"], 2, True), _pct(r["perf_eur"], 2, True)] for r in dt["fondi_etf"]]
                  + [["<b>TOTALE FONDI/ETF</b>", "<b>" + _pct(dt["fe_tot_dal"]) + "</b>", "<b>" + _pct(dt["fe_tot_al"]) + "</b>", _pct(dt["fe_tot_al"] - dt["fe_tot_dal"], 2, True), ""]])
        orot = (tbl(["Strumento", "Peso " + pdal, "Peso " + pal, "Perf. EUR"],
                    [[_html.escape(str(r["nome"] or "")), _pct(r["peso_dal"]), _pct(r["peso_al"]), _pct(r["perf_eur"], 2, True)] for r in dt["oro"]])
                if dt["oro"] else '<div class="note">Nessuna posizione in oro fisico nel periodo.</div>')
    else:
        azt = fet = orot = _nd
    dett_html = ("<h3>8. Dettaglio azioni — titolo per titolo (total-return EUR)</h3>" + azt
                 + "<h3>9. Fondi ed ETF</h3>" + fet
                 + "<h3>10. Oro fisico</h3>" + orot)
    return (head + kp
            + "<h3>Pesi di linea per asset class (fondi separati)</h3>" + comp
            + "<h3>Esposizione azionaria delta-adjusted</h3>" + eqt
            + "<h3>Andamento peso azionario (dirette + ETF): settimana / mese / anno</h3>" + pazt
            + "<h3>Peso per settore (azioni)</h3>" + sett
            + "<h3>Migliori e peggiori per performance</h3>" + perf
            + "<h3>Contributori e detrattori (singoli titoli)</h3>" + contr
            + "<h3>Contributo per classe di attivo</h3>" + clazz
            + "<h3>Operazioni del periodo</h3>" + trd
            + dett_html)
