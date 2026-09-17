# -*- coding: utf-8 -*-
"""Rendiconto periodico della gestione (PDF, 9 pagine) — layout "Comitato Investimenti".

Sostituisce il rendiconto storico da 24 pagine, di cui la gran parte era il ledger dei
movimenti: quello resta allegato contabile separato e qui viene solo richiamato in nota.

Le pagine: sintesi con il ponte patrimoniale, il risultato nel tempo (matrice mensile e
cumulati), la composizione, i tre reparti, il perche' e le convinzioni, il prospetto
analitico di tutte le posizioni, gli oneri e le note metodologiche.

Regola non negoziabile: **tutti** i rendimenti sono al lordo delle commissioni; il netto
compare una volta sola, nel ponte patrimoniale, dove la differenza si legge come riga di
commissioni. Vedi `camperio_core.portfolio.rendimento`.
"""
import datetime
import os
import tempfile

import data_layer as DL
import pdf_comune as PC
import report_cliente as RC
from camperio_core.portfolio import rendimento as RD

MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]


# ============================== dati ==============================
def build_rendiconto(pf, repo_dir):
    """Il dizionario della Sintesi Cliente piu' serie storiche, ponte patrimoniale e oneri."""
    d = RC.build_cliente(pf, repo_dir)
    schema, codcli, al = d["schema"], d["codcli"], d["iso"]
    dal = d["data_base"]

    serie = DL.serie_mensile(schema, codcli, al)
    d["serie_mensile"] = serie
    d["serie_giornaliera"] = DL.serie_giornaliera(schema, codcli, dal, al)
    d["oneri"] = DL.oneri(schema, codcli, dal, al) or {}

    # Matrice dei rendimenti mensili al lordo. L'ultimo mese e' parziale: la serie
    # arriva all'ultimo fine-mese chiuso, la coda fino ad `al` si calcola a parte.
    comm = DL.commissioni(schema, codcli, (serie[0]["data"] if serie else dal), al)
    mens = RD.rendimenti_mensili(serie, comm)
    if serie and serie[-1]["data"] < al:
        coda = serie[-1]
        m = {"anno": int(al[:4]), "mese": int(al[5:7]), "parziale": True,
             "lordo": RD.rendimento_lordo(coda["tcli"], d["tcli_al"], RD.nel_periodo(comm, coda["data"], al)),
             "bench": RD.rendimento_benchmark(coda["tbmk"], d["tbmk_al"])}
        if m["lordo"] is not None:
            mens.append(m)
    d["mensili"] = mens
    d["matrice"] = _matrice(mens)
    d["anni"] = _per_anno(mens)
    d["cumulati"] = _cumulati(serie, comm, d, al)
    d["fasi"] = _fasi(mens, int(al[:4]))
    return d


def _matrice(mens):
    """{anno: {mese: (lordo, bench)}} per la tabella dei rendimenti mensili."""
    out = {}
    for m in mens:
        out.setdefault(m["anno"], {})[m["mese"]] = (m["lordo"], m["bench"])
    return out


def _per_anno(mens):
    """[(anno, lordo_anno, bench_anno, parziale), ...] componendo i mesi di ciascun esercizio."""
    per = {}
    for m in mens:
        a = per.setdefault(m["anno"], {"l": [], "b": [], "coda": False})
        a["l"].append(m["lordo"])
        a["b"].append(m["bench"])
        a["coda"] = a["coda"] or bool(m.get("parziale"))
    # L'esercizio e' parziale se non ha dodici mesi pieni: va segnalato con l'asterisco.
    return [(a, RD.componi(v["l"]), RD.componi(v["b"]), v["coda"] or len(v["l"]) < 12)
            for a, v in sorted(per.items())]


def _cumulati(serie, comm, d, al):
    """Rendimenti cumulati dal 31/12 di ciascun esercizio base, con la media annua."""
    dic = {}
    for r in serie or ():
        if r["data"][5:7] == "12":
            dic[int(r["data"][:4])] = r
    anno = int(al[:4])
    try:
        fine = datetime.date.fromisoformat(al)
    except ValueError:
        return []
    out = []
    for etichetta, indietro in (("Da inizio anno", 1), ("Ultimi due esercizi", 2),
                                ("Ultimi tre esercizi", 3), ("Ultimi cinque esercizi", 5)):
        base = dic.get(anno - indietro)
        if not base:
            continue
        cp = RD.rendimento_lordo(base["tcli"], d["tcli_al"], RD.nel_periodo(comm, base["data"], al))
        cb = RD.rendimento_benchmark(base["tbmk"], d["tbmk_al"])
        if cp is None or cb is None:
            continue
        anni = (fine - datetime.date.fromisoformat(base["data"])).days / 365.25
        out.append({"etichetta": etichetta, "dal": base["data"], "pf": cp, "bmk": cb,
                    "diff": cp - cb, "media": RD.media_annua(cp, anni)})
    return out


_FASI = [("Primo trimestre", (1, 2, 3)), ("Secondo trimestre", (4, 5, 6)),
         ("Terzo trimestre", (7, 8, 9)), ("Quarto trimestre", (10, 11, 12))]


def _fasi(mens, anno):
    """L'anno in corso per trimestri: i quattro tempi della prima pagina."""
    per = {m["mese"]: m for m in mens if m["anno"] == anno}
    out = []
    for nome, mesi in _FASI:
        dentro = [per[x] for x in mesi if x in per]
        if not dentro:
            continue
        etichetta = "%s — %s" % (MESI[dentro[0]["mese"] - 1], MESI[dentro[-1]["mese"] - 1])
        out.append({"nome": nome, "periodo": etichetta,
                    "lordo": RD.componi([x["lordo"] for x in dentro]),
                    "bench": RD.componi([x["bench"] for x in dentro])})
    return out


# ============================== grafici ==============================
def _grafici(d, tmp):
    """Grafico lineare dell'anno e istogramma per esercizio, oltre a quelli della Sintesi."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out = RC._charts(d, tmp)
    verde, grigio, rosso = RC.VERDE, "#8C93A8", RC.ROSSO

    serie = d.get("serie_giornaliera") or []
    if len(serie) > 5:
        comm = d.get("comm") or []
        t0, b0, d0 = serie[0]["tcli"], serie[0]["tbmk"], serie[0]["data"]
        pf = [RD.rendimento_lordo(t0, r["tcli"], RD.nel_periodo(comm, d0, r["data"])) * 100 for r in serie]
        bm = [(r["tbmk"] / b0 - 1) * 100 for r in serie]
        x = list(range(len(serie)))
        fig, ax = plt.subplots(figsize=(5.5, 2.05), dpi=200)
        ax.axhline(0, color="#CFCBC0", lw=0.8)
        ax.fill_between(x, bm, pf, where=[p >= q for p, q in zip(pf, bm)], color=verde, alpha=0.10, lw=0)
        ax.fill_between(x, bm, pf, where=[p < q for p, q in zip(pf, bm)], color=RC.ARANCIO, alpha=0.10, lw=0)
        ax.plot(x, bm, color=grigio, lw=1.15, label="Parametro di riferimento")
        ax.plot(x, pf, color=verde, lw=1.7, label="Linea %s (lordo)" % d["linea"])
        ax.plot([x[-1]], [pf[-1]], "o", ms=4, color=verde)
        ax.annotate(PC.sg(pf[-1] / 100), (x[-1], pf[-1]), xytext=(6, -3), textcoords="offset points",
                    ha="left", fontsize=8, fontweight="bold", color=verde)
        ax.annotate(PC.sg(bm[-1] / 100), (x[-1], bm[-1]), xytext=(6, -3), textcoords="offset points",
                    ha="left", fontsize=7.4, color="#6A6A6A")
        tick, lab, visti = [], [], set()
        for i, r in enumerate(serie):
            mm = r["data"][5:7]
            if r["data"][:4] == d["iso"][:4] and mm not in visti:
                visti.add(mm)
                tick.append(i)
                lab.append(MESI[int(mm) - 1])
        ax.set_xticks(tick)
        ax.set_xticklabels(lab, fontsize=6.8, color="#555555")
        ax.set_xlim(-2, len(x) + max(14, len(x) * 0.09))
        ax.tick_params(axis="y", labelsize=6.6, colors="#999999", length=0)
        ax.tick_params(axis="x", length=0)
        ax.yaxis.set_major_formatter(lambda v, p: ("%+.0f%%" % v).replace("+0%", "0%"))
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.spines["left"].set_color("#E6E3DB")
        ax.spines["bottom"].set_color("#E6E3DB")
        ax.yaxis.grid(True, color="#F2F0EA", lw=0.7)
        ax.set_axisbelow(True)
        ax.legend(loc="upper left", frameon=False, fontsize=6.9, handlelength=1.5, borderpad=0)
        fig.tight_layout(pad=0.25)
        p = os.path.join(tmp, "ytd.png")
        fig.savefig(p, transparent=True)
        plt.close(fig)
        out["ytd"] = p

    anni = [a for a in (d.get("anni") or []) if a[1] is not None and a[2] is not None]
    if len(anni) >= 2:
        fig, ax = plt.subplots(figsize=(3.35, 1.72), dpi=200)
        xx = range(len(anni))
        vp = [a[1] * 100 for a in anni]
        vb = [a[2] * 100 for a in anni]
        ax.bar([i - 0.19 for i in xx], vp, width=0.36, color=verde, label="Linea %s" % d["linea"])
        ax.bar([i + 0.19 for i in xx], vb, width=0.36, color="#C4C4C4", label="Parametro")
        for i, (p_, b_) in enumerate(zip(vp, vb)):
            ax.text(i - 0.19, p_ + (0.4 if p_ >= 0 else -1.4), PC.sg(p_ / 100, 1).replace("%", ""),
                    ha="center", fontsize=5.9, fontweight="bold", color=verde if p_ >= 0 else rosso)
            ax.text(i + 0.19, b_ + (0.4 if b_ >= 0 else -1.4), PC.sg(b_ / 100, 1).replace("%", ""),
                    ha="center", fontsize=5.9, color="#6A6A6A")
        ax.axhline(0, color="#9A9A9A", lw=0.8)
        ax.set_xticks(list(xx))
        ax.set_xticklabels([str(a[0]) + ("*" if a[3] else "") for a in anni], fontsize=6.6, color="#444444")
        lo, hi = min(vb + vp), max(vb + vp)
        ax.set_ylim(lo - 3.5, hi + 3.5)
        ax.set_yticks([])
        ax.tick_params(length=0)
        for sp in ("top", "right", "left", "bottom"):
            ax.spines[sp].set_visible(False)
        ax.legend(loc="lower center", ncol=2, frameon=False, fontsize=6.3, handlelength=1.2,
                  bbox_to_anchor=(0.5, -0.30))
        fig.tight_layout(pad=0.2)
        p = os.path.join(tmp, "anni.png")
        fig.savefig(p, transparent=True)
        plt.close(fig)
        out["anni"] = p
    return out


# ============================== PDF ==============================
def rendiconto_pdf(d, path):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Image, PageBreak, Paragraph, Spacer, Table, TableStyle

    s = PC.stili()
    t = d["testi"]
    doc, cw = PC.documento(path, RC._testata(d),
                           "Rendiconto della gestione · conto %s" % d["codcli"],
                           disclaimer=PC.DISCLAIMER_REND)
    ch = _grafici(d, tempfile.mkdtemp(prefix="rend_"))
    pat = d["patrimoniale"]
    E = []

    # ---------------- pagina 1: sintesi e ponte patrimoniale ----------------
    periodo = "%s — %s" % (DL._fmt_it(d["data_base"]), d["data"])
    E += [Paragraph("RENDICONTO DELLA GESTIONE PATRIMONIALE", s["ey"]),
          Paragraph("Linea %s — Rendiconto" % d["linea"], s["h1"]),
          Paragraph("Periodo %s%s" % (periodo, (" · %d giorni di gestione" % d["giorni"]) if d.get("giorni") else ""),
                    s["sub"]), Spacer(1, 9),
          RC._banda(d, cw), Spacer(1, 10)]
    if "ytd" in ch:
        E.append(Image(ch["ytd"], width=cw, height=cw * (2.05 / 5.5)))
        E.append(Paragraph("Andamento del portafoglio al lordo delle commissioni (verde) confrontato con il "
                           "parametro di riferimento (grigio). L'area colorata misura giorno per giorno la "
                           "distanza fra i due: al %s il portafoglio è avanti di <b>%s punti percentuali</b>."
                           % (d["data"], PC.sg(d["extra"]).replace("%", "")), s["nota"]))

    if d.get("fasi"):
        E.append(Paragraph("Il periodo trimestre per trimestre", s["sec"]))
        FV = ParagraphStyle("fv", fontName="Helvetica-Bold", fontSize=11.5, leading=14, textColor=PC.VERDE)
        FVR = ParagraphStyle("fvr", parent=FV, textColor=PC.ROSSO)
        FN = ParagraphStyle("fn", fontName="Helvetica-Bold", fontSize=7, leading=9.4, textColor=PC.BLU)
        celle = []
        for f in d["fasi"]:
            celle.append([Paragraph(PC.sg(f["lordo"], 1), FV if (f["lordo"] or 0) >= 0 else FVR),
                          Paragraph(f["nome"], FN),
                          Paragraph(f["periodo"], s["kl"]),
                          Paragraph("parametro " + PC.sg(f["bench"], 1), s["kl"])])
        n = len(celle)
        tf = Table([[Table([[c] for c in col], colWidths=[cw / n - 8]) for col in celle]],
                   colWidths=[cw / n] * n)
        tf.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (0, 0), 0), ("LEFTPADDING", (1, 0), (-1, 0), 8),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                                ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        E.append(tf)

    if pat:
        E.append(Paragraph("Il quadro patrimoniale del periodo", s["sec"]))
        ris_l = RD.risultato_lordo(pat.get("risultato_netto"), d["comm"])
        righe = [[Paragraph("Movimenti del patrimonio", s["th"]), Paragraph("Importo €", s["thr"]),
                  Paragraph("Rendimento", s["thr"])],
                 [Paragraph("Consistenza iniziale al %s" % DL._fmt_it(d["data_base"]), s["cell"]),
                  PC.eur(pat.get("cons_ini"), 2), ""],
                 [Paragraph("Apporti del periodo", s["cell"]), PC.eur(pat.get("apporti"), 2), ""],
                 [Paragraph("Prelievi del periodo (imposta di bollo)", s["cell"]),
                  PC.sg_eur(pat.get("prelievi"), 2), ""],
                 [Paragraph("<b>Risultato lordo della gestione</b>", s["cellb"]),
                  PC.sg_eur(ris_l, 2), PC.sg(d["ytd_p"])],
                 [Paragraph("Commissioni di gestione e amministrative (IVA inclusa)", s["cell"]),
                  PC.sg_eur(-d["comm_tot"], 2), ""],
                 [Paragraph("<b>Risultato netto della gestione</b>", s["cellb"]),
                  PC.sg_eur(pat.get("risultato_netto"), 2), PC.sg(d["ytd_n"])],
                 [Paragraph("<b>Consistenza finale al %s</b>" % d["data"], s["cellb"]),
                  PC.eur(pat.get("cons_fin"), 2), ""]]
        tp = PC.tabella(righe, [cw * 0.58, cw * 0.24, cw * 0.18], destra=[1, 2], fs=8.2, pad=4.0, zebra=False)
        tp.setStyle(TableStyle([("LINEABOVE", (0, 4), (-1, 4), 0.7, PC.BLU2),
                                ("LINEABOVE", (0, 6), (-1, 6), 0.7, PC.BLU2),
                                ("BACKGROUND", (0, 6), (-1, 6), colors.HexColor("#EDEFF6")),
                                ("LINEABOVE", (0, 7), (-1, 7), 0.9, PC.BLU),
                                ("BACKGROUND", (0, 7), (-1, 7), PC.ALT)]))
        E.append(tp)
        E.append(Paragraph("<b>Lordo e netto.</b> Il rendimento che leggi in questo rendiconto è sempre al "
                           "<b>lordo</b> delle commissioni: è la misura di quanto ha reso la gestione. Le "
                           "commissioni del periodo, € %s IVA inclusa, sono indicate separatamente e portano il "
                           "risultato netto accreditato sul conto a € %s. L'imposta di bollo è un onere fiscale "
                           "prelevato dal patrimonio e non incide sul calcolo del rendimento. Metodologia "
                           "time-weighted."
                           % (PC.eur(d["comm_tot"], 2), PC.eur(pat.get("risultato_netto"), 2)), s["nota"]))

    # ---------------- pagina 2: il risultato nel tempo ----------------
    if d["matrice"]:
        E.append(PageBreak())
        anni = sorted(d["matrice"])
        E += [Paragraph("IL RISULTATO NEL TEMPO", s["ey"]),
              Paragraph("%d esercizi di gestione" % len(anni), s["h1"]),
              Paragraph("Rendimenti mensili al lordo delle commissioni, confrontati mese per mese con il "
                        "parametro di riferimento", s["sub"]), Spacer(1, 9),
              _tabella_matrice(d, cw, s, anni)]
        E.append(Paragraph("Valori in percentuale. Per ogni esercizio la prima riga è la Linea %s al lordo "
                           "delle commissioni, la seconda il parametro di riferimento. L'esercizio in corso è "
                           "calcolato fino al %s." % (d["linea"], d["data"]), s["nota"]))
    if d["cumulati"]:
        E.append(Paragraph("I rendimenti cumulati", s["sec"]))
        righe = [[Paragraph("Periodo", s["th"]), Paragraph("Dal", s["thr"]),
                  Paragraph("Linea %s" % d["linea"], s["thr"]), Paragraph("Parametro", s["thr"]),
                  Paragraph("Differenza", s["thr"]), Paragraph("Media annua", s["thr"])]]
        for c in d["cumulati"]:
            righe.append([Paragraph(c["etichetta"], s["cell"]), DL._fmt_it(c["dal"]),
                          PC.sg(c["pf"]), PC.sg(c["bmk"]),
                          PC.sg(c["diff"]).replace("%", "") + " p.p.",
                          PC.sg(c["media"]) if c["media"] is not None else "—"])
        E.append(PC.tabella(righe, [cw * 0.235, cw * 0.13, cw * 0.165, cw * 0.145, cw * 0.16, cw * 0.145],
                            destra=[1, 2, 3, 4, 5], fs=8.0, pad=4.0))
    if "anni" in ch:
        pos = [a for a in d["anni"] if a[1] is not None and a[2] is not None and a[1] >= a[2]]
        testo = [Paragraph("Su %d esercizi la gestione ha fatto meglio del parametro di riferimento in "
                           "<b>%d</b>." % (len(d["anni"]), len(pos)), s["body"])]
        for par in t.get("insieme") or []:
            testo.append(Paragraph(par, s["body"]))
        E.append(PC.affianca(Image(ch["anni"], width=cw * 0.46, height=cw * 0.46 * (1.72 / 3.35)),
                             testo, cw, quota=0.47))
    E.append(Paragraph("Parametro di riferimento della linea: %s. I rendimenti passati non sono indicativi "
                       "di quelli futuri." % (PC.esc(d["bench"]) or "—"), s["nota"]))

    # ---------------- pagina 3: composizione ----------------
    E.append(PageBreak())
    E += [Paragraph("LA COMPOSIZIONE DEL PORTAFOGLIO", s["ey"]),
          Paragraph("Come è investito il patrimonio", s["h1"]),
          Paragraph("Situazione al %s · %d strumenti detenuti direttamente" % (d["data"], d["n_pos"]), s["sub"]),
          Spacer(1, 9),
          RC._composizione(d, cw, s, ch), RC._nota_composizione(d, s)]
    if d["bonds_pct"]:
        E += [Paragraph("La parte obbligazionaria", s["sec"]), RC._obbligazionaria(d, cw, s, ch)]
    if d["fx"]:
        E += [Paragraph("Esposizione valutaria", s["sec"]),
              Paragraph(" · ".join("<b>%s</b> %s" % (r["ccy"], PC.pct(r["pct"])) for r in d["fx"]), s["body"]),
              Paragraph("Esposizione in trasparenza sui comparti UCITS. L'oro è considerato una classe a sé.",
                        s["nota"])]

    # ---------------- pagina 4: i tre reparti ----------------
    E.append(PageBreak())
    E += [Paragraph(" · ".join(k.upper() for k, _ in d["reparti"]), s["ey"]),
          Paragraph("I tre reparti, uno per uno", s["h1"]),
          Paragraph("Come il patrimonio si divide fra chi protegge, chi partecipa e chi cerca la crescita",
                    s["sub"]), Spacer(1, 10),
          _schede_reparti(d, cw, s, t)]
    E.append(Paragraph("Percentuali calcolate sul patrimonio complessivo. L'elenco analitico di tutte le %d "
                       "posizioni è alle pagine seguenti." % d["n_pos"], s["nota"]))
    if t.get("insieme"):
        E.append(Paragraph("Come lavorano insieme i tre reparti", s["sec"]))
        for par in t["insieme"]:
            E.append(Paragraph(par, s["body"]))

    # ---------------- pagina 5: perche' e convinzioni ----------------
    if t.get("perche") or d["convinzioni"]:
        E.append(PageBreak())
        E += [Paragraph("IL NOSTRO MODO DI LAVORARE", s["ey"]),
              Paragraph("Perché il portafoglio è fatto così", s["h1"]), Spacer(1, 9)]
        for par in t.get("perche") or []:
            E.append(Paragraph(par, s["body"]))
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
            E.append(PC.tabella(righe, [cw * 0.21, cw * 0.09, cw * 0.70], destra=[1], fs=8, pad=3.6, zebra=False))
            E.append(Paragraph("Le note di gestione esprimono la posizione di Camperio SIM alla data del "
                               "documento e possono cambiare nel tempo.", s["nota"]))

    # ---------------- pagine 6-8: prospetto analitico ----------------
    E.append(PageBreak())
    E += [Paragraph("SITUAZIONE PATRIMONIALE ANALITICA", s["ey"]),
          Paragraph("Il portafoglio titolo per titolo", s["h1"]),
          Paragraph("Tutte le %d posizioni al %s, raggruppate per reparto e per comparto"
                    % (d["n_pos"], d["data"]), s["sub"]), Spacer(1, 7),
          _prospetto(d, cw, s)]
    E.append(Paragraph("Prezzi e cambi di chiusura del %s. Il costo medio è espresso nella divisa di "
                       "denominazione dello strumento; il controvalore è convertito in euro al cambio "
                       "indicato. Per gli strumenti obbligazionari la quantità è il valore nominale e i "
                       "prezzi sono espressi in percentuale." % d["data"], s["nota"]))

    # ---------------- pagina 9: oneri e metodologia ----------------
    E.append(PageBreak())
    E += [Paragraph("COSTI, ONERI E METODOLOGIA", s["ey"]),
          Paragraph("Che cosa hai pagato nel periodo", s["h1"]),
          Paragraph("Tutti gli oneri addebitati nel periodo %s" % periodo, s["sub"]), Spacer(1, 9),
          _tabella_oneri(d, cw, s)]
    E.append(Paragraph("Le commissioni di gestione addebitate si riferiscono ai periodi di competenza già "
                       "chiusi: la quota del periodo in corso sarà addebitata alla scadenza successiva e non "
                       "è compresa né in questa tabella né nel calcolo del rendimento netto.", s["nota"]))
    E.append(Paragraph("Come leggere i rendimenti di questo rendiconto", s["sec"]))
    NM = ParagraphStyle("nm", fontName="Helvetica", fontSize=8.0, leading=11.2,
                        textColor=PC.TESTO, spaceAfter=5)
    for titolo, testo in t.get("note_metodologiche") or []:
        E.append(Paragraph("<b>%s.</b> %s" % (titolo, testo), NM))
    if t.get("chiusura"):
        E.append(Spacer(1, 6))
        E.append(Paragraph(t["chiusura"], s["nota"]))
    doc.build(E)
    return path


def _tabella_matrice(d, cw, s, anni):
    """Matrice mensile: due righe per esercizio, la Linea in grassetto e il parametro sotto."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, Table, TableStyle
    MH = ParagraphStyle("mh", fontName="Helvetica-Bold", fontSize=6.3, leading=8,
                        textColor=colors.white, alignment=TA_CENTER)
    MC = ParagraphStyle("mc", fontName="Helvetica", fontSize=6.3, leading=8, alignment=TA_RIGHT)
    MCB = ParagraphStyle("mcb", fontName="Helvetica-Bold", fontSize=6.4, leading=8, alignment=TA_RIGHT)
    MR = ParagraphStyle("mr", fontName="Helvetica-Bold", fontSize=6.6, leading=8, textColor=PC.BLU)
    MRS = ParagraphStyle("mrs", fontName="Helvetica", fontSize=6.0, leading=8, textColor=PC.GRIGIO)
    per_anno = {a: (p, b) for a, p, b, _ in d["anni"]}

    dati = [[Paragraph("Anno", MH)] + [Paragraph(m, MH) for m in MESI] + [Paragraph("Anno", MH)]]
    stile, r = [], 1
    for a in anni:
        for quale in (0, 1):
            celle = [Paragraph(str(a) if quale == 0 else "parametro", MR if quale == 0 else MRS)]
            for m in range(1, 13):
                v = d["matrice"].get(a, {}).get(m)
                if v is None or v[quale] is None:
                    celle.append(Paragraph("", MC))
                    continue
                col = (PC.VERDE if v[quale] >= 0 else PC.ROSSO) if quale == 0 else colors.HexColor("#7A7A7A")
                st = ParagraphStyle("x%d%d%d" % (a, m, quale), parent=MCB if quale == 0 else MC, textColor=col)
                celle.append(Paragraph(PC.sg(v[quale], 1).replace("%", ""), st))
            va = per_anno.get(a, (None, None))[quale]
            col = (PC.VERDE if (va or 0) >= 0 else PC.ROSSO) if quale == 0 else colors.HexColor("#7A7A7A")
            celle.append(Paragraph(PC.sg(va, 1).replace("%", "") if va is not None else "",
                                   ParagraphStyle("y%d%d" % (a, quale), parent=MCB, textColor=col)))
            dati.append(celle)
            if quale == 1:
                stile.append(("LINEBELOW", (0, r), (-1, r), 0.4, PC.RIGA))
            r += 1
    larg = [cw * 0.112] + [cw * 0.0645] * 12 + [cw * 0.114]
    t = Table(dati, colWidths=larg)
    t.setStyle(TableStyle(stile + [
        ("BACKGROUND", (0, 0), (-1, 0), PC.BLU),
        ("BACKGROUND", (13, 1), (13, -1), PC.ALT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.5), ("RIGHTPADDING", (0, 0), (-1, -1), 2.5)]))
    return t


def _schede_reparti(d, cw, s, testi):
    """Una scheda per reparto, affiancate: ruolo, controvalore, peso e prime posizioni.

    Affiancate e non in colonna perche' l'Attacco, elencato in verticale, sfonda la pagina.
    """
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    rep = [(k, r) for k, r in d["reparti"] if k in ("Difesa", "Centro Campo", "Attacco")] or d["reparti"]
    n = max(1, len(rep))
    CWc = cw / n - 6
    RH = ParagraphStyle("rh", fontName="Helvetica-Bold", fontSize=9.6, leading=12, textColor=colors.white)
    RD_ = ParagraphStyle("rd", fontName="Helvetica", fontSize=6.9, leading=9.4, textColor=PC.TESTO)
    RP = ParagraphStyle("rp", fontName="Helvetica", fontSize=6.8, leading=9, textColor=PC.GRIGIO)
    TC = ParagraphStyle("tc", fontName="Helvetica", fontSize=6.4, leading=8.4)
    TV = ParagraphStyle("tv", fontName="Helvetica", fontSize=6.4, leading=8.4, alignment=TA_RIGHT,
                        textColor=colors.HexColor("#444444"))
    TH = ParagraphStyle("th2", fontName="Helvetica-Bold", fontSize=6.3, leading=8.4, textColor=PC.GRIGIO)

    def scheda(nome_rep, r):
        col = PC.COLORE_REPARTO.get(nome_rep, PC.BLU)
        barra = Table([[Paragraph(nome_rep.upper(), RH)]], colWidths=[CWc])
        barra.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), col),
                                   ("TOPPADDING", (0, 0), (-1, -1), 4),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 6),
                                   ("RIGHTPADDING", (0, 0), (-1, -1), 6)]))
        righe = [[Paragraph("Posizioni principali", TH), Paragraph("% patrim.", TH)]]
        st = [("BACKGROUND", (0, 0), (-1, 0), PC.ALT), ("LINEBELOW", (0, 0), (-1, 0), 0.5, col)]
        prime = r["pos"][:7]
        for i, p in enumerate(prime, start=1):
            righe.append([Paragraph(p["nome"], TC), Paragraph(PC.pct(p["pct"]), TV)])
            st.append(("LINEBELOW", (0, i), (-1, i), 0.2, colors.HexColor("#EFEDE7")))
        resto = r["pos"][7:]
        if resto:
            righe.append([Paragraph("<i>altre %d posizioni</i>" % len(resto), TC),
                          Paragraph(PC.pct(sum(x["pct"] for x in resto)), TV)])
            st.append(("BACKGROUND", (0, len(righe) - 1), (-1, len(righe) - 1), colors.HexColor("#FAF9F5")))
        mini = Table(righe, colWidths=[CWc * 0.70, CWc * 0.30])
        mini.setStyle(TableStyle(st + [("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                       ("TOPPADDING", (0, 0), (-1, -1), 2.0),
                                       ("BOTTOMPADDING", (0, 0), (-1, -1), 2.0),
                                       ("LEFTPADDING", (0, 0), (-1, -1), 3),
                                       ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
        grande = ParagraphStyle("bg" + nome_rep, fontName="Helvetica-Bold", fontSize=13, leading=16,
                                textColor=col)
        dentro = Table([[barra], [Spacer(1, 5)],
                        [Paragraph("€ " + PC.eur(r["val"]), grande)],
                        [Paragraph("%s del patrimonio · %d strumenti" % (PC.pct(r["pct"]), r["n"]), RP)],
                        [Spacer(1, 5)],
                        [Paragraph((testi.get("reparti") or {}).get(nome_rep, ""), RD_)],
                        [Spacer(1, 6)], [mini]], colWidths=[CWc])
        dentro.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                                    ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return dentro

    t = Table([[scheda(k, r) for k, r in rep]], colWidths=[cw / n] * n)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LEFTPADDING", (0, 0), (0, 0), 0), ("LEFTPADDING", (1, 0), (-1, 0), 9),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return t


def _q(v):
    """Quantita': niente decimali se e' un intero (nominali e numeri di azioni)."""
    if v is None:
        return ""
    return PC.eur(v, 0) if abs(v - round(v)) < 0.005 else PC.eur(v, 2)


def _p4(v):
    """Prezzi e costi medi: 2 decimali sopra 100, 4 sotto."""
    if v is None:
        return ""
    return PC.eur(v, 2) if abs(v) >= 100 else PC.eur(v, 4)


def _prospetto(d, cw, s):
    """Tutte le posizioni in una tabella a otto colonne, per reparto e comparto."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, Table, TableStyle
    F = 6.1
    AN = ParagraphStyle("an", fontName="Helvetica", fontSize=F, leading=F * 1.30,
                        textColor=colors.HexColor("#1A1A1A"))
    AV = ParagraphStyle("av", fontName="Helvetica", fontSize=F, leading=F * 1.30, alignment=TA_RIGHT,
                        textColor=colors.HexColor("#444444"))
    AP = ParagraphStyle("ap", fontName="Helvetica-Bold", fontSize=F, leading=F * 1.30,
                        alignment=TA_RIGHT, textColor=PC.BLU)
    AH = ParagraphStyle("ah", fontName="Helvetica-Bold", fontSize=F, leading=F * 1.35, textColor=colors.white)
    AHR = ParagraphStyle("ahr", parent=AH, alignment=TA_RIGHT)
    ASH = ParagraphStyle("ash", fontName="Helvetica-Bold", fontSize=F - 0.2, leading=F * 1.32,
                         textColor=PC.GRIGIO)
    intest = ["Strumento", "Div.", "Quantità", "Costo medio", "Prezzo", "Cambio", "Controvalore €", "% patrim."]
    larg = [cw * 0.335, cw * 0.055, cw * 0.105, cw * 0.095, cw * 0.095, cw * 0.075, cw * 0.145, cw * 0.095]
    dati = [[Paragraph(intest[0], AH)] + [Paragraph(h, AHR) for h in intest[1:]]]
    st = [("BACKGROUND", (0, 0), (-1, 0), PC.BLU)]
    i = 1
    for nome_rep, r in d["reparti"]:
        dati.append([Paragraph(nome_rep.upper(), AH), "", "", "", "", "",
                     Paragraph(PC.eur(r["val"], 2), AHR), Paragraph(PC.pct(r["pct"]), AHR)])
        st += [("BACKGROUND", (0, i), (-1, i), PC.COLORE_REPARTO.get(nome_rep, PC.BLU)),
               ("SPAN", (0, i), (5, i)), ("TOPPADDING", (0, i), (-1, i), 3),
               ("BOTTOMPADDING", (0, i), (-1, i), 3.2)]
        i += 1
        for sub, val in sorted(r["sub"].items(), key=lambda kv: -kv[1]):
            dentro = [p for p in r["pos"] if (p["sub"] or "") == sub]
            dati.append([Paragraph("%s  (%d)" % ((sub or "Altro").upper(), len(dentro)), ASH),
                         "", "", "", "", "",
                         Paragraph(PC.eur(val, 2), AP),
                         Paragraph(PC.pct(val / d["nav"] if d["nav"] else 0), AP)])
            st += [("BACKGROUND", (0, i), (-1, i), PC.ALT), ("SPAN", (0, i), (5, i)),
                   ("TOPPADDING", (0, i), (-1, i), 2.4), ("BOTTOMPADDING", (0, i), (-1, i), 2.4)]
            i += 1
            for p in dentro:
                dati.append([Paragraph(p["nome"], AN), Paragraph(p.get("divisa") or "", AV),
                             Paragraph(_q(p.get("quanti")), AV), Paragraph(_p4(p.get("costmed")), AV),
                             Paragraph(_p4(p.get("unimer")), AV),
                             Paragraph(PC.eur(p["camuni"], 4) if p.get("camuni") else "", AV),
                             Paragraph(PC.eur(p["val"], 2), AV), Paragraph(PC.pct(p["pct"]), AV)])
                st += [("LINEBELOW", (0, i), (-1, i), 0.2, colors.HexColor("#EFEDE7")),
                       ("TOPPADDING", (0, i), (-1, i), 1.5), ("BOTTOMPADDING", (0, i), (-1, i), 1.5)]
                i += 1
    dati.append([Paragraph("TOTALE PATRIMONIO IN GESTIONE", AH), "", "", "", "", "",
                 Paragraph(PC.eur(d["nav"], 2), AHR), Paragraph("100,00%", AHR)])
    st += [("BACKGROUND", (0, i), (-1, i), PC.BLU), ("SPAN", (0, i), (5, i)),
           ("TOPPADDING", (0, i), (-1, i), 3.4), ("BOTTOMPADDING", (0, i), (-1, i), 3.6)]
    t = Table(dati, colWidths=larg, repeatRows=1)
    t.setStyle(TableStyle(st + [("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 3.5),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 3.5)]))
    return t


_ETICHETTA_ONERE = {"CDG": ("Commissioni di gestione", "addebito periodico posticipato — IVA inclusa"),
                    "RSP": ("Spese di rendicontazione e amministrative", "canone periodico — IVA inclusa"),
                    "CTR": ("Altri oneri contrattuali", "spese di gestione del rapporto — IVA inclusa"),
                    "CPE": ("Commissione di incentivo", "sulla parte di rendimento eccedente il parametro — IVA inclusa")}


def _tabella_oneri(d, cw, s):
    from reportlab.platypus import Paragraph, TableStyle
    o = d.get("oneri") or {}
    pat = d.get("patrimoniale") or {}
    nav = d["nav"] or 1.0
    righe = [[Paragraph("Voce", s["th"]), Paragraph("Base di calcolo", s["th"]),
              Paragraph("Importo €", s["thr"]), Paragraph("% patrim.", s["thr"])]]

    def riga(voce, base, imp):
        righe.append([Paragraph(voce, s["cell"]), Paragraph(base, s["nota"]),
                      PC.eur(imp, 2), PC.pct(imp / nav)])

    tot = 0.0
    for tipo in ("CDG", "RSP", "CTR", "CPE"):
        imp = (o.get("per_tipo") or {}).get(tipo)
        if not imp:
            continue
        voce, base = _ETICHETTA_ONERE[tipo]
        riga(voce, base, imp)
        tot += imp
    neg = o.get("spese_negoziazione") or 0.0
    if neg:
        riga("Commissioni di negoziazione", "oneri riconosciuti ai broker sugli ordini eseguiti", neg)
        tot += neg
    n_tot = len(righe)
    righe.append([Paragraph("<b>Totale costi della gestione</b>", s["cellb"]), "",
                  PC.eur(tot, 2), PC.pct(tot / nav)])
    bollo = abs(pat.get("prelievi") or 0.0)
    if bollo:
        riga("Imposta di bollo", "prelievo periodico — onere fiscale di legge", bollo)
    rit = o.get("ritenute") or 0.0
    if rit:
        riga("Ritenute su dividendi e cedole", "imposte estere e sostitutive trattenute alla fonte", rit)
    t = PC.tabella(righe, [cw * 0.30, cw * 0.38, cw * 0.17, cw * 0.15], destra=[2, 3],
                   fs=8.0, pad=3.6, zebra=False)
    t.setStyle(TableStyle([("LINEABOVE", (0, n_tot), (-1, n_tot), 0.8, PC.BLU),
                           ("BACKGROUND", (0, n_tot), (-1, n_tot), PC.ALT),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return t


# ============================== anteprima HTML ==============================
def rendiconto_html(d):
    """Anteprima nel browser: gli stessi numeri del PDF, senza grafici."""
    import html as H
    pat = d.get("patrimoniale") or {}
    ris_l = RD.risultato_lordo(pat.get("risultato_netto"), d["comm"])
    testa = ('<div class="rh"><div class="rt">Rendiconto della gestione — Linea %s</div>'
             '<div class="rs">%s · conto %s · periodo %s — %s · parametro %s</div></div>'
             % (H.escape(d["linea"]), H.escape(d["descli"]), H.escape(d["codcli"]),
                DL._fmt_it(d["data_base"]), d["data"], H.escape(PC.esc(d["bench"]) or "—")))
    kp = ('<div class="kp">'
          + '<div class="ki"><div class="kl">Valore del portafoglio</div><div class="kv">€ %s</div></div>' % PC.eur(d["nav"])
          + '<div class="ki"><div class="kl">Risultato lordo</div><div class="kv">%s</div></div>' % PC.sg_eur(ris_l, 0)
          + '<div class="ki"><div class="kl">Rendimento lordo</div><div class="kv">%s</div><div class="ks">netto %s</div></div>' % (PC.sg(d["ytd_p"]), PC.sg(d["ytd_n"]))
          + '<div class="ki"><div class="kl">Parametro</div><div class="kv">%s</div></div>' % PC.sg(d["ytd_b"])
          + '<div class="ki"><div class="kl">Extra-rendimento</div><div class="kv">%s p.p.</div></div>' % PC.sg(d["extra"]).replace("%", "")
          + '</div>')

    def tab(intest, righe):
        th = "".join(("<th class=r>%s</th>" if i else "<th>%s</th>") % x for i, x in enumerate(intest))
        tb = "".join("<tr>" + "".join(("<td class=r>%s</td>" if i else "<td>%s</td>") % c
                                      for i, c in enumerate(r)) + "</tr>" for r in righe)
        return '<div style="overflow-x:auto"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (th, tb)

    ponte = tab(["Movimenti del patrimonio", "Importo €"], [
        ["Consistenza iniziale al " + DL._fmt_it(d["data_base"]), PC.eur(pat.get("cons_ini"), 2)],
        ["Apporti", PC.eur(pat.get("apporti"), 2)],
        ["Prelievi (imposta di bollo)", PC.sg_eur(pat.get("prelievi"), 2)],
        ["<b>Risultato lordo della gestione</b>", PC.sg_eur(ris_l, 2)],
        ["Commissioni (IVA inclusa)", PC.sg_eur(-d["comm_tot"], 2)],
        ["<b>Risultato netto della gestione</b>", PC.sg_eur(pat.get("risultato_netto"), 2)],
        ["<b>Consistenza finale al %s</b>" % d["data"], PC.eur(pat.get("cons_fin"), 2)]])
    anni = tab(["Esercizio", "Linea " + d["linea"], "Parametro", "Differenza"],
               [[str(a) + ("*" if parz else ""), PC.sg(p), PC.sg(b),
                 PC.sg((p - b) if (p is not None and b is not None) else None).replace("%", "") + " p.p."]
                for a, p, b, parz in d["anni"]])
    rep = tab(["Reparto", "Controvalore €", "% patrim.", "Strumenti"],
              [[k, PC.eur(r["val"], 2), PC.pct(r["pct"]), str(r["n"])] for k, r in d["reparti"]])
    cum = tab(["Periodo", "Dal", "Linea", "Parametro", "Differenza", "Media annua"],
              [[c["etichetta"], DL._fmt_it(c["dal"]), PC.sg(c["pf"]), PC.sg(c["bmk"]),
                PC.sg(c["diff"]).replace("%", "") + " p.p.",
                PC.sg(c["media"]) if c["media"] is not None else "—"] for c in d["cumulati"]])
    return (testa + kp
            + "<h3>Quadro patrimoniale del periodo</h3>" + ponte
            + "<h3>Rendimenti per esercizio (al lordo)</h3>" + anni
            + "<h3>Rendimenti cumulati</h3>" + cum
            + "<h3>I tre reparti</h3>" + rep
            + '<div class="note">Il PDF ha 9 pagine: sintesi con il ponte patrimoniale, matrice dei '
              'rendimenti mensili, composizione, i tre reparti, convinzioni, prospetto analitico di tutte le '
              'posizioni, oneri e note metodologiche. Il prospetto dei movimenti resta allegato contabile '
              'separato.</div>')
