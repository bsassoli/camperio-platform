# -*- coding: utf-8 -*-
"""Report al cliente: Sintetica (1 pagina) e Sintesi Cliente (3 pagine).

Layout "Comitato Investimenti" (motore condiviso in `pdf_comune`): banda dei cinque
numeri, grafico piu' narrativa, blocco composizione con le classi di esposizione e i
tre reparti, allegato con tutte le posizioni.

I rendimenti esposti sono al **lordo** delle commissioni (`camperio_core.portfolio.rendimento`):
`SRE.TCLI` e' netto e non e' quello che si mostra al cliente. I testi editoriali
(ruoli dei reparti, convinzioni, perche') stanno in `contenuti/<linea>.json`.

Il Rendiconto periodico e' in `report_rendiconto.py`.
"""
import os, re, datetime, tempfile
import contenuti as CONT
import data_layer as DL
import lookthrough as L
import pdf_comune as PC
from camperio_core.portfolio import methodology as M
from camperio_core.portfolio import rendimento as RD

HERE = os.path.dirname(os.path.abspath(__file__))
_LOGO_W = os.path.join(HERE, "static", "logo-bianco.png")
_LOGO_COL = os.path.join(HERE, "static", "logo-colori.png")  # logo ufficiale a colori (blu+arancio) su fondo bianco
BLU = "#151F6D"; BLU2 = "#2E5A9E"; ARANCIO = "#FF8200"; GRIGIO = "#666666"
VERDE = "#1F7A4D"; ROSSO = "#B3261E"; RIGA = "#D9D6CE"; ALT = "#F4F2EC"; ORO = "#C9A66B"

_FUNDS = {"95ZYC2", "8W8C01", "54OPLF", "8W8C34", "8W8C45", "50QNF8", "52PZG8"}
_DEV = {"EUR", "USD", "GBP", "CHF", "JPY", "NOK", "DKK", "SEK", "CAD"}

_F1 = ("Camperio SIM S.p.A. — Via Camperio, 9 — 20123 Milano — Tel +39 02.50020918 — Fax +39 02.50020917 — "
       "camperioSIM@camperiosim.com — www.camperiosim.com")
_F2A = ("Consob delibera d'iscrizione n. 11761 del 22/12/1998 — albo n. 48 — Gestione di portafogli, Consulenza in materia di "
        "investimenti, Ricezione e trasmissione di ordini")
_F2B = ("Cap. Soc. € 3.079.083 — C.F. 02342760275 — P.IVA 11791000158 — REA MI-1409117 — Codice Banca d'Italia 16206/5 — "
        "Fondo Nazionale di Garanzia SIM0077.")
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
    nav_inizio = ex.get("nav_base")
    # Rendimento: al cliente si espone il LORDO, restituendo al montante le commissioni
    # Camperio IVA inclusa (MOV.CTVREG). TCLI e' netto: e' l'errore piu' facile da fare.
    data_base = ex.get("data_base") or (str(int(meta["data"][:4]) - 1) + "-12-31")
    comm = DL.commissioni(meta["schema"], meta["codcli"], data_base, meta["data"])
    ytd_n = RD.rendimento_netto(ex.get("tcli_base"), ex.get("tcli_al"))
    ytd_p = RD.rendimento_lordo(ex.get("tcli_base"), ex.get("tcli_al"), comm)
    ytd_b = RD.rendimento_benchmark(ex.get("tbmk_base"), ex.get("tbmk_al"))
    extra = (ytd_p - ytd_b) if (ytd_p is not None and ytd_b is not None) else None
    comm_tot = RD.totale_commissioni(comm)
    patr = DL.quadro_patrimoniale(meta["schema"], meta["codcli"], data_base, meta["data"]) or {}
    gain = RD.risultato_lordo(patr.get("risultato_netto"), comm) if patr.get("risultato_netto") is not None \
        else ((nav_inizio * ytd_p) if (nav_inizio and ytd_p is not None) else None)
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
    base_alloc = (nav + der_eq) if (nav + der_eq) else nav  # base delle allocazioni: patrimonio al netto del nozionale dei derivati azionari
    alloc = [("Azioni", esp_az, esp_az / base_alloc), ("Obbligazioni", bond_dir, bond_dir / base_alloc),
             ("Alternativi (Oro)", gold, gold / base_alloc), ("Liquidità", cashv, cashv / base_alloc)]
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
    # I tre reparti (Difesa / Centro Campo / Attacco) dal framework di camperio_core:
    # guardano gli strumenti per come sono detenuti, non l'esposizione economica.
    rep = {}
    for p in pf["positions"]:
        v = p.get("valmer", 0.0)
        if not v:
            continue
        r = rep.setdefault(p.get("macro") or "Altro", {"val": 0.0, "n": 0, "pos": [], "sub": {}})
        r["val"] += v
        r["n"] += 1
        r["pos"].append({"nome": PC.nome(p.get("des")), "val": v, "pct": v / nav,
                         "isin": p.get("isin") or "", "ccy": p.get("ccy") or "EUR",
                         "sub": p.get("sub") or "", "divisa": p.get("divisa") or "",
                         "quanti": p.get("quanti"), "costmed": p.get("costmed"),
                         "unimer": p.get("unimer"), "camuni": p.get("camuni")})
        r["sub"][p.get("sub") or ""] = r["sub"].get(p.get("sub") or "", 0.0) + v
    for r in rep.values():
        r["pct"] = r["val"] / nav if nav else None
        r["pos"].sort(key=lambda x: -x["val"])
    reparti = [(k, rep[k]) for k in M.MACRO_ORDER if k in rep]
    testi = CONT.carica(info["linea"])
    convinzioni = CONT.convinzioni_con_peso(testi, pf["positions"], nav)
    # Al cliente il parametro si scrive per esteso: il codice interno (CMP21) non dice nulla.
    # La descrizione sta nei contenuti della linea; in mancanza si usa quello che da' il gestionale.
    bench = (testi.get("parametro") or (pf.get("sre") or {}).get("benchmark")
             or ex.get("bench", "") or "")
    return {"descli": info["descli"], "codcli": meta["codcli"], "linea": info["linea"] or "—",
            "bench": bench, "bench_codice": ex.get("bench", ""), "data": DL._fmt_it(meta["data"]), "iso": meta["data"],
            "nav": nav, "nav_inizio": nav_inizio, "base_alloc": base_alloc,
            "patrimoniale": patr, "giorni": giorni,
            "ytd_p": ytd_p, "ytd_b": ytd_b, "extra": extra, "gain": gain,
            "alloc": alloc, "bonds_pct": bond_dir / nav, "durata": durata, "bond_break": bond_break,
            "fx": fx, "cats": cats, "sett": sett_sorted, "n_pos": n_pos, "val_titoli": val_titoli,
            "ytd_n": ytd_n, "comm": comm, "comm_tot": comm_tot, "data_base": data_base,
            "reparti": reparti, "testi": testi, "convinzioni": convinzioni,
            "schema": meta["schema"], "der_eq": der_eq,
            "tcli_al": ex.get("tcli_al"), "tbmk_al": ex.get("tbmk_al")}

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
    bars = ax.bar(["Linea " + d["linea"], "Parametro"], vals, color=[VERDE if vals[0] >= 0 else ROSSO, "#B9B9B9"], width=0.6)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.2, ("+%.2f%%" % v).replace(".", ","), ha="center", va="bottom",
                fontsize=9, fontweight="bold", color=BLU)
    ax.set_ylabel("Rendimento da inizio anno, al lordo", fontsize=7.5, color=GRIGIO)
    ax.spines[["top", "right"]].set_visible(False); ax.spines[["left", "bottom"]].set_color(RIGA)
    ax.tick_params(colors=GRIGIO, labelsize=7.5); ax.margins(y=0.25)
    fig.tight_layout(); p = os.path.join(tmp, "perf.png"); fig.savefig(p, transparent=True); plt.close(fig); out["perf"] = p
    # 2) ciambella allocazione
    fig, ax = plt.subplots(figsize=(2.5, 2.5), dpi=200)
    labels = [a[0] for a in d["alloc"]]; sizes = [max(a[1], 0) for a in d["alloc"]]
    cols = [ARANCIO, BLU2, VERDE, "#8C93A8"]
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

# ============================== PDF: elementi condivisi ==============================
def _img(ch, key, wmm, hmm):
    from reportlab.platypus import Image, Spacer
    from reportlab.lib.units import mm
    return Image(ch[key], width=wmm * mm, height=hmm * mm) if key in ch else Spacer(1, 1)


def _banda(d, cw):
    """La banda dei cinque numeri: valore, risultato, rendimento lordo, parametro, extra."""
    c = PC.colore_segno(d["ytd_p"])
    return PC.banda(cw, [
        ("€ " + PC.eur(d["nav"]), "Valore del portafoglio", PC.BLU),
        ("€ " + PC.eur(d["gain"]) if d["gain"] is not None else "—", "Risultato lordo del periodo", c),
        (PC.sg(d["ytd_p"]), "Rendimento lordo", c),
        (PC.sg(d["ytd_b"]), "Parametro di riferimento", PC.BLU),
        (PC.sg(d["extra"]).replace("%", "") + " p.p.", "Extra-rendimento", c)])


def _perf_e_narrativa(d, cw, s, ch):
    """Grafico performance a sinistra, due paragrafi e la nota metodologica a destra."""
    from reportlab.platypus import Paragraph
    gg = (" in %d giorni di gestione" % d["giorni"]) if d.get("giorni") else ""
    testo = [
        Paragraph("Da inizio anno la gestione ha reso <b>%s</b> contro il <b>%s</b> del parametro di "
                  "riferimento: <b>%s punti percentuali</b> in più."
                  % (PC.sg(d["ytd_p"]), PC.sg(d["ytd_b"]), PC.sg(d["extra"]).replace("%", "")), s["body"]),
        Paragraph("Il valore del portafoglio è passato da € %s a <b>€ %s</b>, con un risultato di "
                  "<b>€ %s</b>%s." % (PC.eur(d["nav_inizio"]), PC.eur(d["nav"]),
                                      PC.eur(d["gain"]) if d["gain"] is not None else "—", gg), s["body"]),
        Paragraph("Rendimento al lordo delle commissioni, calcolato con metodologia time-weighted. "
                  "Parametro di riferimento della linea: %s." % (PC.esc(d["bench"]) or "—"), s["nota"])]
    return PC.affianca(_img(ch, "perf", 60, 44), testo, cw, quota=0.33)


def _composizione(d, cw, s, ch):
    """Ciambella, tabella delle classi, tabella dei tre reparti, barre dei settori."""
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    # Il grafico dei settori ha senso solo se i settori sono davvero mappati: in DEMO,
    # senza il Repository_Fondi, finiscono tutti in "n.d." e una barra sola non dice nulla.
    tutti = d.get("sett") or []
    settori = [(k, r) for k, r in tutti if k and k.lower() not in ("n.d.", "altro")]
    val_noti = sum(x["val"] for _k, r in settori for x in r)
    val_tot = sum(x["val"] for _k, r in tutti for x in r)
    con_settori = ("sett" in ch and len(settori) >= 2
                   and val_noti >= 0.5 * (val_tot or 1))
    larg = (cw * 0.39) if con_settori else (cw * 0.62)
    rip = [[Paragraph("Ripartizione", s["th"]), Paragraph("Controvalore €", s["thr"]),
            Paragraph("%", s["thr"])]]
    for nome_, val, pp in d["alloc"]:
        rip.append([Paragraph(nome_, s["cell"]), PC.eur(val, 2), PC.pct(pp)])
    t1 = PC.tabella(rip, [larg * 0.50, larg * 0.32, larg * 0.18], destra=[1, 2], fs=7.6, pad=3.4)
    tre = [[Paragraph("I tre reparti", s["th"]), Paragraph("Controvalore €", s["thr"]),
            Paragraph("%", s["thr"])]]
    for k, r in d["reparti"]:
        tre.append([Paragraph("<b>%s</b>" % k, s["cellb"]), PC.eur(r["val"], 2), PC.pct(r["pct"])])
    t2 = PC.tabella(tre, [larg * 0.50, larg * 0.32, larg * 0.18], destra=[1, 2], fs=7.6, pad=3.4)
    pila = Table([[t1], [Spacer(1, 7)], [t2]], colWidths=[larg])
    pila.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                              ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    if con_settori:
        celle = [[_img(ch, "donut", 40, 40), pila, _img(ch, "sett", 62, 47)]]
        larghezze = [cw * 0.24, cw * 0.40, cw * 0.36]
    else:
        celle = [[_img(ch, "donut", 44, 44), pila]]
        larghezze = [cw * 0.30, cw * 0.70]
    tri = Table(celle, colWidths=larghezze)
    tri.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("LEFTPADDING", (0, 0), (0, 0), 0), ("LEFTPADDING", (1, 0), (-1, 0), 5),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                             ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return tri


def _nota_composizione(d, s):
    from reportlab.platypus import Paragraph
    cop = ""
    if d.get("der_eq"):
        cop = (" al netto delle coperture in derivati su indice (esposizione delta %s)"
               % PC.sg(d["der_eq"] / d["nav"] if d["nav"] else None, 1))
    return Paragraph("«Azioni» comprende le azioni dirette, gli ETF azionari e i comparti UCITS scomposti "
                     "nelle loro componenti%s. I tre reparti guardano invece gli strumenti per come sono "
                     "detenuti: è la logica con cui il portafoglio viene costruito." % cop, s["nota"])


def _obbligazionaria(d, cw, s, ch):
    from reportlab.platypus import Paragraph
    dur = (("La vita residua media del comparto è di <b>%s anni</b>. "
            % PC.eur(d["durata"], 2)) if d.get("durata") is not None else "")
    bb = " · ".join("%s %s" % (k, PC.pct(p)) for k, v, p in d["bond_break"])
    testo = [Paragraph("Il <b>%s</b> del patrimonio è investito in obbligazioni, in prevalenza titoli di "
                       "Stato e sovranazionali a scadenza breve. %s" % (PC.pct(d["bonds_pct"]), dur), s["body"]),
             Paragraph(bb, s["body"])]
    return PC.affianca(_img(ch, "dur", 60, 14), testo, cw, quota=0.36)


def _posizioni_principali(d, cw, s, n=5):
    """Prime cinque posizioni e prime cinque azioni, affiancate."""
    from reportlab.platypus import Paragraph, Table, TableStyle
    tutte = sorted((r for rows in d["cats"].values() for r in rows), key=lambda r: -r["val"])
    azioni = sorted(d["cats"].get("Azioni", []), key=lambda r: -r["val"])

    def mini(titolo, righe):
        dati = [[Paragraph(titolo, s["th"]), Paragraph("Controvalore €", s["thr"]),
                 Paragraph("%", s["thr"])]]
        for r in righe[:n]:
            dati.append([Paragraph(PC.nome(r["nome"]), s["cell"]), PC.eur(r["val"]), PC.pct(r["pct"])])
        return PC.tabella(dati, [cw * 0.255, cw * 0.14, cw * 0.075], destra=[1, 2], fs=7.4, pad=3.0)

    due = Table([[mini("Prime cinque posizioni", tutte), mini("Prime cinque azioni", azioni)]],
                colWidths=[cw * 0.50, cw * 0.50])
    due.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                             ("LEFTPADDING", (0, 0), (0, 0), 0), ("RIGHTPADDING", (0, 0), (0, 0), 12),
                             ("LEFTPADDING", (1, 0), (1, 0), 12), ("RIGHTPADDING", (1, 0), (1, 0), 0),
                             ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return due


def _testata(d):
    return {"descli": d["descli"], "linea": d["linea"], "codcli": d["codcli"], "data": d["data"]}


# ============================== Sintetica (1 pagina) ==============================
def sintetica_pdf(d, path):
    """Una pagina: banda, performance, composizione, posizioni principali."""
    from reportlab.platypus import Paragraph, Spacer
    s = PC.stili()
    doc, cw = PC.documento(path, _testata(d), "Linea %s — Sintetica · conto %s" % (d["linea"], d["codcli"]))
    ch = _charts(d, tempfile.mkdtemp(prefix="sint_"))
    E = [Paragraph("LA TUA GESTIONE PATRIMONIALE", s["ey"]),
         Paragraph("Linea %s — Sintesi" % d["linea"], s["h1"]),
         Paragraph("Situazione al %s" % d["data"], s["sub"]), Spacer(1, 9),
         _banda(d, cw), Spacer(1, 11),
         _perf_e_narrativa(d, cw, s, ch),
         Paragraph("Come è investito il portafoglio", s["sec"]),
         _composizione(d, cw, s, ch), _nota_composizione(d, s),
         Paragraph("Le posizioni principali", s["sec"]),
         _posizioni_principali(d, cw, s),
         Paragraph("L'elenco completo delle %d posizioni è riportato nella Sintesi Cliente e nel Rendiconto."
                   % d["n_pos"], s["nota"])]
    doc.build(E)
    return path


# ============================== Sintesi Cliente (3 pagine) ==============================
def sintesi_pdf(d, path):
    """Tre pagine: sintesi, perché e convinzioni, allegato con tutte le posizioni."""
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import PageBreak, Paragraph, Spacer, Table, TableStyle
    s = PC.stili()
    t = d["testi"]
    doc, cw = PC.documento(path, _testata(d), "Linea %s — Sintesi Cliente · conto %s" % (d["linea"], d["codcli"]))
    ch = _charts(d, tempfile.mkdtemp(prefix="sint3_"))

    E = [Paragraph("LA TUA GESTIONE PATRIMONIALE", s["ey"]),
         Paragraph("Linea %s — Sintesi" % d["linea"], s["h1"]),
         Paragraph("Situazione al %s" % d["data"], s["sub"]), Spacer(1, 9),
         _banda(d, cw), Spacer(1, 11),
         _perf_e_narrativa(d, cw, s, ch),
         Paragraph("Come è investito il portafoglio", s["sec"]),
         _composizione(d, cw, s, ch), _nota_composizione(d, s)]
    if d["bonds_pct"]:
        E += [Paragraph("La parte obbligazionaria", s["sec"]), _obbligazionaria(d, cw, s, ch)]
    if d["fx"]:
        E += [Paragraph("Esposizione valutaria", s["sec"]),
              Paragraph(" · ".join("<b>%s</b> %s" % (r["ccy"], PC.pct(r["pct"])) for r in d["fx"]), s["body"]),
              Paragraph("Esposizione in trasparenza sui comparti UCITS (valute sottostanti). L'oro è "
                        "considerato una classe a sé.", s["nota"])]

    # ---- pagina 2: perché e convinzioni ----
    E.append(PageBreak())
    E += [Paragraph("IL NOSTRO MODO DI LAVORARE", s["ey"]),
          Paragraph("Perché il portafoglio è fatto così", s["h1"]), Spacer(1, 9)]
    for par in t.get("perche") or []:
        E.append(Paragraph(par, s["body"]))
    kpi = [("%d" % d["n_pos"], "strumenti detenuti direttamente")]
    az = d["cats"].get("Azioni") or []
    if az:
        kpi.append(("%d" % len(az), "azioni scelte una per una"))
        kpi.append((PC.pct(max(r["pct"] for r in az)), "peso della prima azione"))
    dif = dict(d["reparti"]).get("Difesa")
    if dif:
        kpi.append((PC.pct(dif["pct"]), "del patrimonio ha il compito di proteggere"))
    NB = ParagraphStyle("nb", fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=PC.BLU)
    kt = Table([[[Paragraph(v, NB), Paragraph(l, s["kl"])] for v, l in kpi]],
               colWidths=[cw / len(kpi)] * len(kpi))
    kt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PC.ALT), ("BOX", (0, 0), (-1, -1), 0.5, PC.RIGA),
                            ("INNERGRID", (0, 0), (-1, -1), 0.5, PC.RIGA),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    E.append(kt)
    if d["convinzioni"]:
        E.append(Paragraph("Le nostre convinzioni", s["sec"]))
        if t.get("convinzioni_premessa"):
            E.append(Paragraph(t["convinzioni_premessa"], s["body"]))
        CN = ParagraphStyle("cn", fontName="Helvetica-Bold", fontSize=8, leading=10.8, textColor=PC.BLU)
        CP = ParagraphStyle("cp", fontName="Helvetica-Bold", fontSize=8, leading=10.8,
                            textColor=PC.VERDE, alignment=TA_RIGHT)
        CV = ParagraphStyle("cv", fontName="Helvetica", fontSize=8, leading=10.8, textColor=PC.TESTO)
        righe = [[Paragraph("Posizione", s["th"]), Paragraph("Peso", s["thr"]),
                  Paragraph("Perché è in portafoglio", s["th"])]]
        for c in d["convinzioni"]:
            righe.append([Paragraph(c["titolo"], CN), Paragraph(PC.pct(c["pct"]), CP),
                          Paragraph(c["perche"], CV)])
        tc = PC.tabella(righe, [cw * 0.21, cw * 0.09, cw * 0.70], destra=[1], fs=8, pad=3.6, zebra=False)
        E.append(tc)
        E.append(Paragraph("Le note di gestione esprimono la posizione di Camperio SIM alla data del "
                           "documento e possono cambiare nel tempo.", s["nota"]))

    # ---- pagina 3: allegato, tutte le posizioni su una pagina in tre colonne ----
    E.append(PageBreak())
    E += [Paragraph("ALLEGATO", s["ey"]),
          Paragraph("Elenco completo delle posizioni", s["h1"]),
          Paragraph("Tutte le %d posizioni al %s, raggruppate per reparto e per comparto"
                    % (d["n_pos"], d["data"]), s["sub"]), Spacer(1, 7)]
    E.append(_allegato_tre_colonne(d, cw))
    E.append(Paragraph("Percentuali calcolate sul patrimonio complessivo di € %s. Quantità, prezzi e ISIN "
                       "di ogni posizione sono nel prospetto analitico del Rendiconto." % PC.eur(d["nav"], 2),
                       s["nota"]))
    doc.build(E)
    return path


def _allegato_tre_colonne(d, cw):
    """Tutte le posizioni su una sola pagina, tre colonne, raggruppate per reparto e comparto.

    Il punto di taglio fra le colonne arretra finche' l'ultima riga non e' un'intestazione:
    altrimenti un titolo di reparto o di comparto resta orfano a pie' di colonna.
    """
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, Table, TableStyle
    F = 6.5
    RN = ParagraphStyle("rn", fontName="Helvetica", fontSize=F, leading=F * 1.25,
                        textColor=colors.HexColor("#1A1A1A"))
    RV = ParagraphStyle("rv", fontName="Helvetica", fontSize=F, leading=F * 1.25,
                        alignment=TA_RIGHT, textColor=colors.HexColor("#444444"))
    RP = ParagraphStyle("rp", fontName="Helvetica-Bold", fontSize=F, leading=F * 1.25,
                        alignment=TA_RIGHT, textColor=PC.BLU)
    HS = ParagraphStyle("hs", fontName="Helvetica-Bold", fontSize=F - 0.1, leading=F * 1.3,
                        textColor=PC.GRIGIO)
    HR = ParagraphStyle("hr", fontName="Helvetica-Bold", fontSize=F + 0.9, leading=F * 1.5,
                        textColor=colors.white)
    HRP = ParagraphStyle("hrp", fontName="Helvetica-Bold", fontSize=F + 0.9, leading=F * 1.5,
                         textColor=colors.white, alignment=TA_RIGHT)

    righe = []
    for k, r in d["reparti"]:
        righe.append(("rep", k, r["pct"]))
        for sub, val in sorted(r["sub"].items(), key=lambda kv: -kv[1]):
            righe.append(("set", sub or "Altro", val / d["nav"] if d["nav"] else 0))
            for p in r["pos"]:
                if (p["sub"] or "") == sub:
                    righe.append(("tit", p["nome"], p["pct"]))
    n = len(righe)
    per = -(-n // 3)
    tagli = []
    start = 0
    for _ in range(2):
        k = min(start + per, n)
        while k < n and righe[k - 1][0] in ("rep", "set"):
            k -= 1
        tagli.append((start, k))
        start = k
    tagli.append((start, n))
    CWc = cw / 3.0 - 4

    def colonna(fetta):
        dati, st = [], []
        for i, (tipo, testo, v) in enumerate(fetta):
            if tipo == "rep":
                dati.append([Paragraph(testo.upper(), HR), Paragraph(PC.pct(v), HRP)])
                st += [("BACKGROUND", (0, i), (-1, i), PC.COLORE_REPARTO.get(testo, PC.BLU)),
                       ("TOPPADDING", (0, i), (-1, i), 2.4), ("BOTTOMPADDING", (0, i), (-1, i), 2.6)]
            elif tipo == "set":
                dati.append([Paragraph(testo.upper(), HS), Paragraph(PC.pct(v), RP)])
                st += [("BACKGROUND", (0, i), (-1, i), PC.ALT),
                       ("TOPPADDING", (0, i), (-1, i), 2.2), ("BOTTOMPADDING", (0, i), (-1, i), 2.2)]
            else:
                dati.append([Paragraph(testo, RN), Paragraph(PC.pct(v), RV)])
                st += [("LINEBELOW", (0, i), (-1, i), 0.2, colors.HexColor("#EFEDE7")),
                       ("TOPPADDING", (0, i), (-1, i), 1.5), ("BOTTOMPADDING", (0, i), (-1, i), 1.5)]
        t = Table(dati or [[Paragraph("", RN), Paragraph("", RV)]],
                  colWidths=[CWc * 0.70, CWc * 0.30])
        t.setStyle(TableStyle(st + [("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                                    ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
        return t

    gr = Table([[colonna(righe[a:b]) for a, b in tagli]], colWidths=[cw / 3.0] * 3)
    gr.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return gr

# ============================== anteprima HTML ==============================
def cliente_html(d, titolo="Report al cliente"):
    pc = "1F7A4D" if (d["ytd_p"] or 0) >= 0 else "B3261E"
    head = (f'<div class="rh"><div class="rt">{titolo} — Linea {d["linea"]}</div>'
            f'<div class="rs">{d["descli"]} · conto {d["codcli"]} · parametro {d["bench"]} · '
            f'al {d["data"]} · rendimenti al lordo delle commissioni</div></div>')
    kp = ('<div class="kp">'
          + f'<div class="ki"><div class="kl">Valore portafoglio</div><div class="kv">{_eur(d["nav"])}</div></div>'
          + f'<div class="ki"><div class="kl">Risultato lordo</div><div class="kv" style="color:#{pc}">{_eur(d["gain"]) if d["gain"] is not None else "n.d."}</div></div>'
          + f'<div class="ki"><div class="kl">Rendimento lordo</div><div class="kv" style="color:#{pc}">{_pct(d["ytd_p"],True,2)}</div><div class="ks">netto {_pct(d["ytd_n"],True,2)} · parametro {_pct(d["ytd_b"],True,2)}</div></div>'
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
