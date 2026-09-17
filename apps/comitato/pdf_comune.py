# -*- coding: utf-8 -*-
"""Motore comune dei PDF al cliente — layout "Comitato Investimenti".

I tre report (Sintetica, Sintesi Cliente, Rendiconto) montano gli stessi elementi:
testata disegnata sul canvas con il nome del cliente a destra, banda dei cinque numeri
fra due filetti blu, blocco composizione, footer legale centrato. Qui stanno una volta
sola, cosi' i tre documenti non divergono.

Font Helvetica: e' interno a reportlab e non richiede file nell'immagine di deploy.
"""
import os
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, Image, PageTemplate,  # noqa: F401
                                Paragraph, Spacer, Table, TableStyle)

from camperio_core.branding.palette import MACRO_COLOR

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "static", "logo-colori.png")

BLU = colors.HexColor("#151F6D")
BLU2 = colors.HexColor("#2E5A9E")
ARANCIO = colors.HexColor("#FF8200")
VERDE = colors.HexColor("#1F7A4D")
ROSSO = colors.HexColor("#B03A2E")
GRIGIO = colors.HexColor("#666666")
RIGA = colors.HexColor("#D9D6CE")
ALT = colors.HexColor("#F4F2EC")
TESTO = colors.HexColor("#2A2A2A")

COLORE_REPARTO = {k: colors.HexColor(v) for k, v in MACRO_COLOR.items()}

_F1 = ("Camperio SIM S.p.A. — Via Camperio, 9 — 20123 Milano — Tel +39 02.50020918 — "
       "Fax +39 02.50020917 — camperioSIM@camperiosim.com — www.camperiosim.com")
_F2 = ("Consob delibera d'iscrizione n. 11761 del 22/12/1998 — albo n. 48 — Gestione di portafogli, "
       "Consulenza in materia di investimenti, Ricezione e trasmissione di ordini — Cap. Soc. € 3.079.083 — "
       "C.F. 02342760275 — P.IVA 11791000158 — Codice Banca d'Italia 16206/5 — Fondo Nazionale di Garanzia SIM0077")
DISCLAIMER_INFO = ("Documento informativo personale, non costituisce raccomandazione personalizzata ai sensi "
                   "del Reg. Consob 20307/2018. I rendimenti passati non sono indicativi di quelli futuri.")
DISCLAIMER_REND = ("Rendiconto periodico redatto ai sensi dell'art. 60 del Regolamento delegato (UE) 2017/565. "
                   "I rendimenti passati non sono indicativi di quelli futuri.")


# ---------------------------------------------------------------- numeri
def eur(x, dec=0):
    """1.234.567,89 senza simbolo: il simbolo lo mette chi compone la riga."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "—"
    return ("{:,." + str(dec) + "f}").format(x).replace(",", "§").replace(".", ",").replace("§", ".")


def pct(x, dec=2):
    """Frazione -> percentuale senza segno (0,0914 -> '9,14%')."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "—"
    return ("{:." + str(dec) + "f}").format(x * 100).replace(".", ",") + "%"


def sg(x, dec=2):
    """Frazione -> percentuale col segno, meno tipografico (0,0914 -> '+9,14%')."""
    if x is None:
        return "—"
    return ("+" if x >= 0 else "−") + pct(abs(x), dec)


def sg_eur(x, dec=2):
    if x is None:
        return "—"
    return ("+" if x >= 0 else "−") + eur(abs(x), dec)


def colore_segno(x):
    return VERDE if (x or 0) >= 0 else ROSSO


# ------------------------------------------------- nomi dei titoli leggibili
# Le descrizioni del gestionale sono in maiuscolo: title() piu' queste correzioni.
_FIX = [("Btps", "BTP"), ("Cct", "CCT"), ("Bots", "BOT"), ("Us ", "US "), ("Ibrd", "IBRD"),
        ("Ebrd", "EBRD"), ("Stab.Mech.", "Stability Mechanism "), ("I/l", "I/L"),
        (" Zc", " zero coupon"), ("Ishares", "iShares"), ("Ucits", "UCITS"), ("Etc", "ETC"),
        ("Etf", "ETF"), ("Mdax", "MDAX"), ("Msci", "MSCI"), ("Adr", "ADR"), ("Asml", "ASML"),
        ("Lvmh", "LVMH"), ("Axa", "AXA"), ("Rtx", "RTX"), ("Cvs", "CVS"), ("Hca", "HCA"),
        ("Bae", "BAE"), ("Aena", "AENA"), ("Nvidia", "NVIDIA"), ("Fedex", "FedEx"),
        ("Abbvie", "AbbVie"), (" Amd", " AMD"), (" Plc", " PLC"), (" Ag", " AG"), (" Sa", " SA"),
        (" Se", " SE"), (" Nv", " NV"), (" Spa", " SpA"), (" Kgaa", " KGaA"),
        ("Liquidita'", "Liquidità"), ("Imi", "IMI"), (" Usd", " USD"), (" Eur", " EUR"),
        (" Eu", " EU"), ("E. On", "E.ON"), ("Sme", "SME"),
        ("Essilorluxottica", "EssilorLuxottica"), ("Delta UCITS", "DELTA UCITS")]


def esc(t):
    """Testo pronto per un Paragraph di reportlab: la & va scritta &amp;,
    altrimenti "S&P 500" viene reso "S&; 500"."""
    return (t or "").replace("&", "&amp;")


def nome(des):
    x = (des or "").strip().title()
    for a, b in _FIX:
        x = x.replace(a, b)
    x = re.sub(r"\bInc\b", "Inc.", x).replace("Inc..", "Inc.")
    x = re.sub(r"(\d)\.(\d+)%", r"\1,\2%", x)          # cedole: 2.7% -> 2,7%
    return esc(re.sub(r"\s+", " ", x))


# ---------------------------------------------------------------- stili
def stili():
    s = {}
    s["ey"] = ParagraphStyle("ey", fontName="Helvetica-Bold", fontSize=7.6, leading=10,
                             textColor=BLU2, spaceAfter=1)
    s["h1"] = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=BLU)
    s["sub"] = ParagraphStyle("sub", fontName="Helvetica", fontSize=8.2, leading=11,
                              textColor=GRIGIO, spaceAfter=2)
    s["sec"] = ParagraphStyle("sec", fontName="Helvetica-Bold", fontSize=11.5, leading=14,
                              textColor=BLU, spaceBefore=13, spaceAfter=5)
    s["body"] = ParagraphStyle("body", fontName="Helvetica", fontSize=8.6, leading=12.4,
                               textColor=TESTO, spaceAfter=6)
    s["nota"] = ParagraphStyle("nota", fontName="Helvetica", fontSize=6.6, leading=8.8,
                               textColor=GRIGIO, spaceBefore=3)
    s["cell"] = ParagraphStyle("cell", fontName="Helvetica", fontSize=7.8, leading=10)
    s["cellb"] = ParagraphStyle("cellb", fontName="Helvetica-Bold", fontSize=7.8, leading=10)
    s["cellr"] = ParagraphStyle("cellr", fontName="Helvetica", fontSize=7.8, leading=10, alignment=TA_RIGHT)
    s["th"] = ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=7.8, leading=10,
                             textColor=colors.white)
    s["thr"] = ParagraphStyle("thr", fontName="Helvetica-Bold", fontSize=7.8, leading=10,
                              textColor=colors.white, alignment=TA_RIGHT)
    s["kl"] = ParagraphStyle("kl", fontName="Helvetica", fontSize=6.8, leading=9, textColor=GRIGIO)
    return s


# ---------------------------------------------------------------- documento
def documento(path, testata, titolo_pdf, disclaimer=DISCLAIMER_INFO):
    """A4 verticale con la testata "Comitato" su ogni pagina.

    `testata` = {descli, linea, codcli, data}. Ritorna (doc, larghezza_utile).
    """
    def _hf(canvas, doc):
        canvas.saveState()
        w, h = A4
        try:
            canvas.drawImage(LOGO, 20 * mm, h - 21 * mm, width=40 * mm, height=40 / 2.99 * mm,
                             preserveAspectRatio=True, mask="auto")
        except Exception:
            pass
        canvas.setFillColor(BLU)
        canvas.setFont("Helvetica-Bold", 9.6)
        canvas.drawRightString(w - 20 * mm, h - 15 * mm, testata.get("descli") or "")
        canvas.setFont("Helvetica", 6.9)
        canvas.setFillColor(GRIGIO)
        canvas.drawRightString(w - 20 * mm, h - 18.6 * mm, "Linea %s · conto %s · al %s" % (
            testata.get("linea") or "—", testata.get("codcli") or "", testata.get("data") or ""))
        canvas.drawRightString(w - 20 * mm, h - 21.6 * mm, "Documento riservato e personale")
        canvas.setStrokeColor(RIGA)
        canvas.setLineWidth(0.7)
        canvas.line(20 * mm, h - 24.5 * mm, w - 20 * mm, h - 24.5 * mm)
        p = Paragraph(_F1 + "<br/>" + _F2 + "<br/><i>" + disclaimer + "</i>",
                      ParagraphStyle("f", fontName="Helvetica", fontSize=5.3, leading=7.0,
                                     textColor=GRIGIO, alignment=TA_CENTER))
        p.wrapOn(canvas, w - 40 * mm, 20 * mm)
        p.drawOn(canvas, 20 * mm, 11 * mm)
        canvas.setFont("Helvetica", 6.4)
        canvas.setFillColor(GRIGIO)
        canvas.drawRightString(w - 20 * mm, 8 * mm, "Pag. %d" % doc.page)
        canvas.restoreState()

    doc = BaseDocTemplate(path, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                          topMargin=29 * mm, bottomMargin=25 * mm, title=titolo_pdf,
                          author="Camperio SIM S.p.A.")
    doc.addPageTemplates([PageTemplate(id="std", onPage=_hf, frames=[
        Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="n")])])
    return doc, doc.width


def banda(cw, numeri):
    """Banda dei cinque numeri fra due filetti blu. `numeri` = [(valore, etichetta, colore), ...]."""
    s = stili()
    celle = []
    for val, lbl, col in numeri:
        st = ParagraphStyle("kv", fontName="Helvetica-Bold", fontSize=14.5, leading=18, textColor=col)
        celle.append([Paragraph(val, st), Paragraph(lbl, s["kl"])])
    n = len(celle) or 1
    t = Table([celle], colWidths=[cw / n] * n)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LEFTPADDING", (0, 0), (0, 0), 0),
                           ("LEFTPADDING", (1, 0), (-1, 0), 2),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                           ("TOPPADDING", (0, 0), (-1, -1), 7),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                           ("LINEABOVE", (0, 0), (-1, 0), 0.8, BLU),
                           ("LINEBELOW", (0, 0), (-1, 0), 0.8, BLU)]))
    return t


def tabella(dati, widths, destra=(), fs=7.8, pad=3.4, zebra=True, intestazione=True):
    """Tabella con intestazione blu e righe alternate. `dati[0]` e' l'intestazione."""
    st = [("FONTNAME", (0, 0), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), fs),
          ("TEXTCOLOR", (0, 1), (-1, -1), TESTO), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("LINEBELOW", (0, 0), (-1, -2), 0.4, RIGA),
          ("TOPPADDING", (0, 0), (-1, -1), pad), ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
          ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
    if intestazione:
        st += [("BACKGROUND", (0, 0), (-1, 0), BLU),
               ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
               ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
               ("LINEBELOW", (0, 0), (-1, 0), 0, colors.white)]
    if zebra:
        for r in range(1 if intestazione else 0, len(dati)):
            if (r % 2) == (0 if intestazione else 1):
                st.append(("BACKGROUND", (0, r), (-1, r), ALT))
    for c in destra:
        st.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
    t = Table(dati, colWidths=widths, repeatRows=1 if intestazione else 0)
    t.setStyle(TableStyle(st))
    return t


def affianca(sinistra, destra, cw, quota=0.35, spazio=12):
    """Due elementi sulla stessa riga: `quota` e' la larghezza di sinistra."""
    t = Table([[sinistra, destra]], colWidths=[cw * quota, cw * (1 - quota)])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("LEFTPADDING", (0, 0), (0, 0), 0),
                           ("LEFTPADDING", (1, 0), (1, 0), spazio),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return t
