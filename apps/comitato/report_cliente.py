# -*- coding: utf-8 -*-
"""Report Cliente (PDF one-pager elegante, frontespizio BIANCO con logo a colori).
Pag.1: valore + guadagno EUR, performance YTD vs benchmark + extra-rendimento (grafico a barre),
come e' investito (ciambella + tabella + barre settori), parte obbligazionaria (duration + tipologie),
esposizione valutaria look-through. Pag.2: allegato posizioni complete per categoria.
Azioni = esposizione azionaria look-through (dirette + fondi + indici). Dati live da Oracle.
Marchio Camperio + footer di legge + disclaimer MiFID."""
import os, re, datetime, tempfile
import data_layer as DL
import lookthrough as L

HERE = os.path.dirname(os.path.abspath(__file__))
_LOGO_W = os.path.join(HERE, "static", "logo-bianco.png")
_LOGO_COL = os.path.join(HERE, "static", "logo-colori.png")  # logo ufficiale a colori (blu+arancio) su fondo bianco
BLU = "#151F6D"; BLU2 = "#2E5A9E"; ARANCIO = "#FF8200"; GRIGIO = "#666666"
VERDE = "#1F7A4D"; ROSSO = "#B3261E"; RIGA = "#D9D6CE"; ALT = "#F4F2EC"; ORO = "#C9A66B"

_FUNDS = {"95ZYC2", "8W8C01", "54OPLF", "8W8C34", "8W8C45", "50QNF8", "52PZG8"}
_DEV = {"EUR", "USD", "GBP", "CHF", "JPY", "NOK", "DKK", "SEK", "CAD"}

_F1 = ("Camperio SIM S.p.A. — Via Camperio, 9 — 20123 Milano — Tel +39 02.50020918 — Fax +39 02.50020917 — "
       "camperioSIM@camperiosim.com — www.camperiosim.com")
_F2 = ("Consob delibera d'iscrizione n. 11761 del 22/12/1998 — albo n. 48 — Gestione di portafogli, Consulenza in materia di "
       "investimenti, Ricezione e trasmissione di ordini — Cap. Soc. € 3.079.083 — C.F. 02342760275 — P.IVA 11791000158 — "
       "REA MI-1409117 — Codice Banca d'Italia 16206/5 — Fondo Nazionale di Garanzia SIM0077.")
_DISC = ("Documento informativo personale, non costituisce raccomandazione personalizzata ai sensi del Reg. Consob 20307/2018. "
         "I rendimenti passati non sono indicativi di quelli futuri.")

def _eur(x, dec=0):
    return "€ " + ("{:,." + str(dec) + "f}").format(round(x or 0, dec)).replace(",", "§").replace(".", ",").replace("§", ".")

def _pct(x, sign=False, dec=1):
    if x is None: return "n.d."
    fmt = ("{:+." if sign else "{:.") + str(dec) + "f}"
    return fmt.format(x * 100).replace(".", ",") + "%"

def _categoria(p):
    g = (p.get("grutit") or "").upper(); cod = p.get("codabi") or ""
    if g == "H19": return "Oro"
    if g in ("H10", "H16", "H18"): return "ETF"
    if cod in _FUNDS or g in ("H06", "H20"): return "Fondi UCITS"
    if g.startswith("Z") or cod == "RATEI": return "Liquidità"
    if g.startswith("A") or g.startswith("B") or g == "H14": return "Obbligazioni"
    if g.startswith("F") or g.startswith("G"): return "Derivati"
    return "Azioni"

_MESI = {"GEN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAG": 5, "GIU": 6, "LUG": 7, "AGO": 8,
         "SET": 9, "OTT": 10, "NOV": 11, "DIC": 12, "JAN": 1, "MAY": 5, "JUN": 6, "JUL": 7,
         "AUG": 8, "SEP": 9, "OCT": 10, "DEC": 12}

def _scad_anni(nome, al):
    m = re.search(r"(\d{1,2})[-/ ]([A-Za-z]{3})[-/ ](20\d{2})", nome or "")
    if m:
        mo = _MESI.get(m.group(2).upper())
        if mo:
            try:
                dt = datetime.date(int(m.group(3)), mo, int(m.group(1)))
                return max(0.0, (dt - al).days / 365.25)
            except Exception:
                pass
    m2 = re.search(r"(20\d{2})", nome or "")
    if m2:
        return max(0.0, int(m2.group(1)) - al.year)
    return None

def _bond_breakdown(bonds, nav):
    cats = {"Titoli di Stato area euro": 0.0, "Governativi esteri": 0.0, "Sovranazionali e agenzie": 0.0, "Altri": 0.0}
    for b in bonds:
        n = (b["nome"] or "").upper(); ccy = b["ccy"]
        if any(k in n for k in ("IBRD", "EBRD", "EUROPEAN UNION", "STAB.MECH", "STAB MECH", "ESM", "EIB", "BEI")):
            cats["Sovranazionali e agenzie"] += b["val"]
        elif ccy and ccy != "EUR":
            cats["Governativi esteri"] += b["val"]
        elif any(k in n for k in ("BTPS", "BOTS", "CCT", "BUND", "BUNDES", "DEUTSCHLAND", "FRANCE", "BONOS", "OBLIG",
                                   "NETHERLAND", "FRENCH", "REP", "GOVT", "T-BILL", "BUONI", "OAT")):
            cats["Titoli di Stato area euro"] += b["val"]
        else:
            cats["Altri"] += b["val"]
    return [(k, v, v / nav) for k, v in cats.items() if v > 0]

def build_cliente(pf, repo_dir, livello=1):
    meta = pf["meta"]
    info = DL.contract_info(meta["schema"], meta["codcli"])
    ex = DL.comitato_extra(meta["schema"], meta["codcli"], meta.get("data_prec"), meta["data"])
    nav = float(ex.get("nav_al") or meta.get("nav") or 0) or 1.0
    base = ex.get("nav_base")
    ytd_p = (ex["tcli_al"] / ex["tcli_base"] - 1) if ex.get("tcli_base") else None
    ytd_b = (ex["tbmk_al"] / ex["tbmk_base"] - 1) if ex.get("tbmk_base") else None
    extra = (ytd_p - ytd_b) if (ytd_p is not None and ytd_b is not None) else None
    gain = (base * ytd_p) if (base and ytd_p is not None) else None
    try:
        al_date = datetime.date.fromisoformat(meta["data"])
        giorni = (al_date - datetime.date(2025, 12, 31)).days
    except Exception:
        al_date = None; giorni = None
    # categorie posizioni
    cats = {}; smap = L._build_sector_map(repo_dir)
    for p in pf["positions"]:
        v = p.get("valmer", 0.0)
        if not v: continue
        cat = _categoria(p)
        cats.setdefault(cat, []).append({"nome": (p.get("des") or p.get("codabi") or "").strip().title(),
                                         "isin": p.get("isin") or "", "ccy": p.get("ccy") or "EUR",
                                         "val": v, "pct": v / nav,
                                         "sett": L._sector_of(p.get("des"), smap) if cat == "Azioni" else cat})
    # ESPOSIZIONE AZIONARIA (da Oracle): azioni dirette + ETF azionari/REIT + fondi UCITS - derivati azionari (delta, VALOREFUT)
    EQK = ("S&P", "STOXX", "DAX", "FTSE", "SMI", "MSCI", "NASDAQ", "NIKKEI")
    az_dir = az_etf = fondi_v = der_eq = 0.0
    for p in pf["positions"]:
        g = (p.get("grutit") or "").upper(); cod = p.get("codabi") or ""
        v = p.get("valmer", 0.0); vf = p.get("valorefut", v)
        if g.startswith("E"): az_dir += v
        elif g in ("H10", "H16", "H18", "H23"): az_etf += v
        elif cod in _FUNDS or g in ("H06", "H20"): fondi_v += v
    der_eq = ex.get("der_eq", 0.0)
    esp_az = az_dir + az_etf + fondi_v + der_eq  # azioni + ETF az + fondi + future S&P (delta)
    bond_dir = sum(r["val"] for r in cats.get("Obbligazioni", []))
    gold = sum(r["val"] for r in cats.get("Oro", []))
    cashv = sum(r["val"] for r in cats.get("Liquidità", []))
    base = (nav + der_eq) if (nav + der_eq) else nav  # base gestionale: patrimonio al netto del nozionale derivati azionari
    alloc = [("Azioni", esp_az, esp_az / base), ("Obbligazioni", bond_dir, bond_dir / base),
             ("Alternativi (Oro)", gold, gold / base), ("Liquidità", cashv, cashv / base)]
    # parte obbligazionaria
    bonds = cats.get("Obbligazioni", [])
    durata = None
    if bonds and al_date:
        ws = sum(b["val"] for b in bonds); acc = 0.0; cov = 0.0
        for b in bonds:
            yy = _scad_anni(b["nome"], al_date)
            if yy is not None: acc += b["val"] * yy; cov += b["val"]
        durata = (acc / cov) if cov else None
    bond_break = _bond_breakdown(bonds, nav)
    # esposizione valutaria look-through
    mat = L.build_matrix(pf, repo_dir)
    fx = [{"ccy": cc, "pct": val / nav} for cc, val in mat["totale"].items() if cc != "Altro (<1%)"]
    fx.append({"ccy": "Oro", "pct": mat["oro"] / nav})
    fx = sorted([r for r in fx if abs(r["pct"]) > 0.004], key=lambda r: -r["pct"])
    # azioni per settore
    sett = {}
    for r in cats.get("Azioni", []):
        sett.setdefault(r["sett"], []).append(r)
    sett_sorted = sorted(sett.items(), key=lambda kv: -sum(x["val"] for x in kv[1]))
    for s in sett: sett[s].sort(key=lambda r: -r["val"])
    # Derivati: usa le posizioni con esposizione delta (VALOREFUT), incluso il future S&P (VALMER=0)
    dpz = ex.get("deriv_pos", [])
    if dpz:
        cats["Derivati"] = [{"nome": (x["nome"] or "").title(), "isin": x.get("isin") or "",
                             "ccy": ("USD" if any(k in (x["nome"] or "").upper() for k in ("S&P", "US ", "ULTRA", "TREAS", "NOTE", "USD")) else "EUR"),
                             "val": x["valorefut"], "pct": x["valorefut"] / nav, "sett": "Derivati"} for x in dpz]
    n_pos = sum(len(v) for v in cats.values())
    val_titoli = sum(r["val"] for c, rows in cats.items() if c != "Liquidità" for r in rows)
    return {"descli": info["descli"], "codcli": meta["codcli"], "linea": info["linea"] or "—",
            "bench": ex.get("bench", ""), "data": DL._fmt_it(meta["data"]), "iso": meta["data"],
            "nav": nav, "nav_base": base, "giorni": giorni,
            "ytd_p": ytd_p, "ytd_b": ytd_b, "extra": extra, "gain": gain,
            "alloc": alloc, "bonds_pct": bond_dir / nav, "durata": durata, "bond_break": bond_break,
            "fx": fx, "cats": cats, "sett": sett_sorted, "n_pos": n_pos, "val_titoli": val_titoli}

# ============================== grafici (matplotlib) ==============================
def _charts(d, tmp):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager  # noqa
    plt.rcParams.update({"font.size": 9, "font.family": "sans-serif", "svg.fonttype": "none"})
    out = {}
    # 1) barre performance
    fig, ax = plt.subplots(figsize=(3.0, 2.2), dpi=200)
    vals = [(d["ytd_p"] or 0) * 100, (d["ytd_b"] or 0) * 100]
    bars = ax.bar(["Linea " + d["linea"], "Benchmark"], vals, color=[VERDE if vals[0] >= 0 else ROSSO, "#B9B9B9"], width=0.6)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.2, ("+%.2f%%" % v).replace(".", ","), ha="center", va="bottom",
                fontsize=9, fontweight="bold", color=BLU)
    ax.set_ylabel("Performance da inizio 2026", fontsize=7.5, color=GRIGIO)
    ax.spines[["top", "right"]].set_visible(False); ax.spines[["left", "bottom"]].set_color(RIGA)
    ax.tick_params(colors=GRIGIO, labelsize=7.5); ax.margins(y=0.25)
    fig.tight_layout(); p = os.path.join(tmp, "perf.png"); fig.savefig(p, transparent=True); plt.close(fig); out["perf"] = p
    # 2) ciambella allocazione
    fig, ax = plt.subplots(figsize=(2.5, 2.5), dpi=200)
    labels = [a[0] for a in d["alloc"]]; sizes = [max(a[1], 0) for a in d["alloc"]]
    cols = [BLU, BLU2, ORO, "#B9B9B9"]
    ax.pie(sizes, colors=cols[:len(sizes)], startangle=90, counterclock=False,
           wedgeprops=dict(width=0.42, edgecolor="white", linewidth=1.5))
    ax.text(0, 0, "€ %.2fM" % (d["nav"] / 1e6), ha="center", va="center", fontsize=11, fontweight="bold", color=BLU)
    ax.set(aspect="equal"); fig.tight_layout(); p = os.path.join(tmp, "donut.png"); fig.savefig(p, transparent=True); plt.close(fig); out["donut"] = p
    # 3) barre settori (top 9)
    ss = d["sett"][:9]
    if ss:
        fig, ax = plt.subplots(figsize=(3.0, 2.5), dpi=200)
        names = [s for s, _ in ss][::-1]
        vals = [sum(x["val"] for x in rows) / d["nav"] * 100 for _, rows in ss][::-1]
        ax.barh(names, vals, color=BLU2, height=0.7)
        for i, v in enumerate(vals):
            ax.text(v + 0.05, i, ("%.1f%%" % v).replace(".", ","), va="center", fontsize=7, color=BLU)
        ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
        ax.tick_params(colors=GRIGIO, labelsize=7); ax.set_xticks([]); ax.margins(x=0.18)
        fig.tight_layout(); p = os.path.join(tmp, "sett.png"); fig.savefig(p, transparent=True); plt.close(fig); out["sett"] = p
    # 4) duration gauge
    if d["durata"] is not None:
        fig, ax = plt.subplots(figsize=(3.0, 0.7), dpi=200)
        ax.barh([0], [10], color="#EFEDE6", height=0.5)
        ax.barh([0], [min(d["durata"], 10)], color=VERDE, height=0.5)
        ax.plot([min(d["durata"], 10)], [0], "o", color=BLU, ms=7)
        ax.text(0, 0.6, "rischio tasso basso", fontsize=6.5, color=GRIGIO)
        ax.text(10, 0.6, "alto", fontsize=6.5, color=GRIGIO, ha="right")
        ax.text(min(d["durata"], 10), -0.7, ("%.2f anni" % d["durata"]).replace(".", ","), ha="center", fontsize=8, fontweight="bold", color=BLU)
        ax.set_xlim(0, 10); ax.set_ylim(-1, 1.1); ax.axis("off")
        fig.tight_layout(); p = os.path.join(tmp, "dur.png"); fig.savefig(p, transparent=True); plt.close(fig); out["dur"] = p
    return out

# ============================== PDF (reportlab) ==============================
def cliente_pdf(d, path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
                                    Table, TableStyle, Image, KeepTogether, PageBreak)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
    blu = colors.HexColor(BLU); blu2 = colors.HexColor(BLU2); gri = colors.HexColor(GRIGIO)
    verde = colors.HexColor(VERDE); rosso = colors.HexColor(ROSSO); riga = colors.HexColor(RIGA); alt = colors.HexColor(ALT)
    pc = verde if (d["ytd_p"] or 0) >= 0 else rosso
    ss = getSampleStyleSheet()
    SUP = ParagraphStyle("SUP", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=8, textColor=blu2, spaceAfter=1)
    TIT = ParagraphStyle("TIT", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=19, textColor=blu, spaceAfter=1, leading=21)
    SUB = ParagraphStyle("SUB", parent=ss["Normal"], fontSize=9.5, textColor=gri, spaceAfter=8)
    H = ParagraphStyle("H", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=12, textColor=blu, spaceBefore=12, spaceAfter=5)
    P = ParagraphStyle("P", parent=ss["Normal"], fontSize=9.5, leading=14)
    Psm = ParagraphStyle("Psm", parent=P, fontSize=7.8, textColor=gri, leading=10.5)
    tmp = tempfile.mkdtemp(prefix="cli_")
    ch = _charts(d, tmp)

    def on_page(canvas, doc):
        canvas.saveState(); w, h = A4
        try: canvas.drawImage(_LOGO_COL, 18 * mm, h - 20 * mm, width=46 * mm, height=46 / 2.99 * mm, preserveAspectRatio=True, mask="auto")
        except Exception: pass
        canvas.setFillColor(blu); canvas.setFont("Helvetica-Bold", 10)
        canvas.drawRightString(w - 18 * mm, h - 12 * mm, d["descli"])
        canvas.setFillColor(gri); canvas.setFont("Helvetica", 8)
        canvas.drawRightString(w - 18 * mm, h - 16.5 * mm, "Linea %s · conto %s · al %s" % (d["linea"], d["codcli"], d["data"]))
        canvas.drawRightString(w - 18 * mm, h - 20 * mm, "Documento riservato e personale")
        canvas.setStrokeColor(riga); canvas.setLineWidth(0.7); canvas.line(18 * mm, h - 23 * mm, w - 18 * mm, h - 23 * mm)
        canvas.setFillColor(gri); canvas.setFont("Helvetica", 6.2)
        canvas.drawCentredString(w / 2, 12.5 * mm, _F1)
        canvas.drawCentredString(w / 2, 10 * mm, _F2[:118]); canvas.drawCentredString(w / 2, 8 * mm, _F2[118:])
        canvas.setFont("Helvetica-Oblique", 5.9); canvas.drawCentredString(w / 2, 5.8 * mm, _DISC)
        # riga propria: il disclaimer centrato è largo abbastanza da coprire il
        # numero di pagina se condividono la stessa riga (erano entrambi a 5.8mm)
        canvas.setFont("Helvetica", 7); canvas.drawRightString(w - 18 * mm, 3.3 * mm, "Pag. %d" % doc.page)
        canvas.restoreState()

    def img(key, wmm, hmm):
        return Image(ch[key], width=wmm * mm, height=hmm * mm) if key in ch else Spacer(1, 1)

    story = []
    story.append(Paragraph("LA TUA GESTIONE PATRIMONIALE", SUP))
    story.append(Paragraph("Linea %s — Sintesi" % d["linea"], TIT))
    story.append(Paragraph("Situazione al %s" % d["data"], SUB))
    # KPI riga (numeri grandi, niente box)
    def kv(val, lbl, color):
        return [Paragraph(val, ParagraphStyle("kvv", parent=P, fontName="Helvetica-Bold", fontSize=15, textColor=color, alignment=TA_LEFT, leading=17)),
                Paragraph(lbl, ParagraphStyle("kll", parent=Psm, fontSize=7.5, alignment=TA_LEFT))]
    kpi = [kv(_eur(d["nav"]), "Valore del portafoglio", blu)
           + kv(_eur(d["gain"]) if d["gain"] is not None else "n.d.", "Guadagno YTD (€)", pc)
           + kv(_pct(d["ytd_p"], True, 2), "Performance YTD", pc)
           + kv(_pct(d["ytd_b"], True, 2), "Benchmark YTD", blu)
           + kv(_pct(d["extra"], True, 2) + " p.p.", "Extra-rendimento", pc)]
    # build a 2-row table: values row, labels row
    vals_row = [kpi[0][0], kpi[0][2], kpi[0][4], kpi[0][6], kpi[0][8]]
    lbls_row = [kpi[0][1], kpi[0][3], kpi[0][5], kpi[0][7], kpi[0][9]]
    kt = Table([vals_row, lbls_row], colWidths=[36 * mm] * 5)
    kt.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
                            ("BOTTOMPADDING", (0, 1), (-1, 1), 6), ("LINEBELOW", (0, 1), (-1, 1), 0.7, riga)]))
    story.append(kt); story.append(Spacer(1, 8))

    # perf chart + narrativa
    verso = "una sovraperformance" if (d["extra"] or 0) >= 0 else "una sottoperformance"
    gg = ("in %d giorni" % d["giorni"]) if d["giorni"] else ""
    narr = Paragraph(
        "Da inizio 2026 la gestione ha reso <b>%s</b> contro il %s del parametro di riferimento: %s di <b>%s p.p.</b><br/><br/>"
        "Il valore è passato da %s a <b>%s</b>, con un risultato di <b>%s</b> %s."
        % (_pct(d["ytd_p"], True, 2), _pct(d["ytd_b"], True, 2), verso,
           _pct(abs(d["extra"]) if d["extra"] is not None else None, False, 2), _eur(d["nav_base"]) if d["nav_base"] else "n.d.",
           _eur(d["nav"]), _eur(d["gain"]) if d["gain"] is not None else "n.d.", gg), P)
    row = Table([[img("perf", 72, 53), narr]], colWidths=[78 * mm, 96 * mm])
    row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (1, 0), (1, 0), 8)]))
    story.append(row)

    # come e' investito: donut + tabella | barre settori
    story.append(Paragraph("Come è investito il portafoglio", H))
    arows = [[Paragraph("Ripartizione", ParagraphStyle("th", parent=Psm, fontName="Helvetica-Bold", textColor=colors.white)),
              Paragraph("%", ParagraphStyle("thr", parent=Psm, fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_RIGHT))]]
    for nome, val, pp in d["alloc"]:
        arows.append([Paragraph(nome, Psm), Paragraph(_pct(pp, False, 0), ParagraphStyle("r", parent=Psm, alignment=TA_RIGHT))])
    atab = Table(arows, colWidths=[33 * mm, 16 * mm])
    atab.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), blu), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, alt]),
                              ("LINEBELOW", (0, 0), (-1, -1), 0.3, riga), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    left = Table([[img("donut", 46, 46), atab]], colWidths=[48 * mm, 51 * mm])
    left.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    inv = Table([[left, img("sett", 74, 56)]], colWidths=[101 * mm, 74 * mm])
    inv.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(inv)
    story.append(Paragraph("«Azioni» = azioni dirette + fondi UCITS azionari (dato Oracle). Il portafoglio detiene inoltre un future S&P short di copertura (esposizione delta −6,9%).", Psm))

    # parte obbligazionaria
    story.append(Paragraph("La parte obbligazionaria: solidità e bassa duration", H))
    bb = " · ".join("%s %s" % (k, _pct(p)) for k, v, p in d["bond_break"])
    durtxt = ("La durata finanziaria media è di circa <b>%s anni</b>: rischio di tasso contenuto. " % (("%.2f" % d["durata"]).replace(".", ","))) if d["durata"] is not None else ""
    btext = Paragraph("Circa il <b>%s</b> del portafoglio è in obbligazioni di elevata qualità (in prevalenza titoli di Stato), "
                      "con scadenze brevi. %s<br/><br/>%s" % (_pct(d["bonds_pct"]), durtxt, bb), P)
    brow = Table([[img("dur", 72, 17), btext]], colWidths=[78 * mm, 96 * mm])
    brow.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (1, 0), (1, 0), 8)]))
    story.append(brow)

    # esposizione valutaria
    story.append(Paragraph("Esposizione valutaria", H))
    story.append(Paragraph(" · ".join("<b>%s</b> %s" % (r["ccy"], _pct(r["pct"])) for r in d["fx"]), P))
    story.append(Paragraph("Esposizione in trasparenza sui fondi (valute sottostanti). La componente in euro è prevalente; "
                           "il dollaro USA è la principale valuta estera. L'oro è considerato a sé.", Psm))

    # ===== ALLEGATO =====
    story.append(PageBreak())
    story.append(Paragraph("ALLEGATO", SUP))
    story.append(Paragraph("Elenco completo delle posizioni", TIT))
    story.append(Paragraph("Tutte le posizioni al %s raggruppate per categoria: ISIN, descrizione, controvalore e peso." % d["data"], SUB))

    def postable(rows, intest, total=True):
        data = [[Paragraph(intest, ParagraphStyle("h", parent=Psm, fontName="Helvetica-Bold", textColor=colors.white)),
                 Paragraph("ISIN", ParagraphStyle("h2", parent=Psm, fontName="Helvetica-Bold", textColor=colors.white)),
                 Paragraph("Controv.", ParagraphStyle("h3", parent=Psm, fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_RIGHT)),
                 Paragraph("%", ParagraphStyle("h4", parent=Psm, fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_RIGHT))]]
        for r in rows:
            data.append([Paragraph(r["nome"][:40], Psm), Paragraph(r["isin"], Psm),
                         Paragraph(_eur(r["val"]), ParagraphStyle("rr", parent=Psm, alignment=TA_RIGHT)),
                         Paragraph(_pct(r["pct"], False, 2), ParagraphStyle("rr2", parent=Psm, alignment=TA_RIGHT))])
        if total:
            sub = sum(r["val"] for r in rows)
            data.append([Paragraph("Totale", ParagraphStyle("tb", parent=Psm, fontName="Helvetica-Bold")), Paragraph("", Psm),
                         Paragraph(_eur(sub), ParagraphStyle("tr", parent=Psm, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
                         Paragraph(_pct(sub / d["nav"], False, 2), ParagraphStyle("tr2", parent=Psm, fontName="Helvetica-Bold", alignment=TA_RIGHT))])
        t = Table(data, colWidths=[82 * mm, 36 * mm, 32 * mm, 16 * mm], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), blu2), ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, alt]),
                               ("TOPPADDING", (0, 0), (-1, -1), 1.6),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6)]))
        return t

    for s, rows in d["sett"]:
        story.append(KeepTogether([Spacer(1, 4), postable(rows, "Azioni · " + s)]))
    for cat in ("ETF", "Obbligazioni", "Fondi UCITS", "Oro", "Derivati", "Liquidità"):
        rows = d["cats"].get(cat)
        if rows: story.append(KeepTogether([Spacer(1, 4), postable(rows, cat, total=(cat != "Derivati"))]))
    story.append(Paragraph("Totale %d posizioni · valore titoli %s (esclusi ratei e liquidità)." % (d["n_pos"], _eur(d["val_titoli"])), Psm))

    frame = Frame(18 * mm, 15 * mm, A4[0] - 36 * mm, A4[1] - 42 * mm, id="f", leftPadding=0, rightPadding=0)
    doc = BaseDocTemplate(path, pagesize=A4, pageTemplates=[PageTemplate(id="t", frames=[frame], onPage=on_page)])
    doc.build(story)
    return path

# ============================== anteprima HTML ==============================
def cliente_html(d):
    pc = "1F7A4D" if (d["ytd_p"] or 0) >= 0 else "B3261E"
    head = ('<div class="rh"><div class="rt">Report Cliente — Rendiconto sintetico</div>'
            f'<div class="rs">{d["descli"]} · conto {d["codcli"]} · linea {d["linea"]} · benchmark {d["bench"]} · al {d["data"]} · export PDF (frontespizio bianco)</div></div>')
    kp = ('<div class="kp">'
          + f'<div class="ki"><div class="kl">Valore portafoglio</div><div class="kv">{_eur(d["nav"])}</div></div>'
          + f'<div class="ki"><div class="kl">Guadagno YTD (€)</div><div class="kv" style="color:#{pc}">{_eur(d["gain"]) if d["gain"] is not None else "n.d."}</div></div>'
          + f'<div class="ki"><div class="kl">Performance YTD</div><div class="kv" style="color:#{pc}">{_pct(d["ytd_p"],True,2)}</div><div class="ks">bench {_pct(d["ytd_b"],True,2)}</div></div>'
          + f'<div class="ki"><div class="kl">Extra-rendimento</div><div class="kv" style="color:#{pc}">{_pct(d["extra"],True,2)} p.p.</div></div>'
          + '</div>')
    def tbl(headers, rows):
        th = "".join((f"<th class=r>{x}</th>" if i else f"<th>{x}</th>") for i, x in enumerate(headers))
        body = "".join("<tr>" + "".join((f"<td class=r>{c}</td>" if i else f"<td>{c}</td>") for i, c in enumerate(r)) + "</tr>" for r in rows)
        return f'<div style="overflow-x:auto"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'
    alloc = tbl(["Ripartizione", "%"], [[a[0], _pct(a[2], False, 0)] for a in d["alloc"]])
    bb = " · ".join("%s %s" % (k, _pct(p)) for k, v, p in d["bond_break"])
    dur = (("durata media ~%s anni" % ("%.2f" % d["durata"]).replace(".", ",")) if d["durata"] is not None else "")
    fx = " · ".join("<b>%s</b> %s" % (r["ccy"], _pct(r["pct"])) for r in d["fx"])
    secs = ""
    for s, rows in d["sett"]:
        secs += f"<h3>Azioni · {s}</h3>" + tbl(["Strumento", "ISIN", "Controvalore", "% ptf"],
                                               [[r["nome"], r["isin"], _eur(r["val"]), _pct(r["pct"],False,2)] for r in rows])
    for cat in ("ETF", "Obbligazioni", "Fondi UCITS", "Oro", "Derivati", "Liquidità"):
        rows = d["cats"].get(cat)
        if not rows: continue
        secs += f"<h3>{cat}</h3>" + tbl(["Strumento", "ISIN", "Controvalore", "% ptf"],
                                        [[r["nome"], r["isin"], _eur(r["val"]), _pct(r["pct"],False,2)] for r in rows])
    return (head + kp
            + "<h3>Come è investito (Azioni = look-through)</h3>" + alloc
            + f"<h3>Parte obbligazionaria</h3><p>Circa il <b>{_pct(d['bonds_pct'])}</b> in obbligazioni · {dur}<br>{bb}</p>"
            + "<h3>Esposizione valutaria (look-through)</h3><p>" + fx + "</p>"
            + "<h3>Allegato — posizioni complete</h3>" + secs
            + '<div class="note">Il PDF ha frontespizio bianco con logo a colori, grafici (performance, ciambella, settori, duration) e footer di legge.</div>')
