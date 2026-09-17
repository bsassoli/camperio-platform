# -*- coding: utf-8 -*-
"""Testi editoriali dei report al cliente, per linea di gestione.

Sintesi Cliente e Rendiconto contengono parti che non escono da Oracle: il ruolo dei
tre reparti, il perche' della costruzione, le convinzioni di gestione, le note
metodologiche. Stanno in `contenuti/<linea>.json` cosi' si aggiornano senza toccare il
codice; i numeri e i pesi citati restano calcolati dal database.

`contenuti/default.json` e' il ripiego quando per una linea non c'e' un file dedicato.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "contenuti")


def slug(linea):
    """'Camperio Plus' -> 'camperio-plus'. Stringa vuota se la linea non e' nota."""
    s = (linea or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def carica(linea):
    """Testi della linea, con i campi mancanti completati da default.json."""
    base = {}
    p_def = os.path.join(DIR, "default.json")
    if os.path.exists(p_def):
        base = json.load(open(p_def, encoding="utf-8"))
    s = slug(linea)
    if s:
        p = os.path.join(DIR, s + ".json")
        if os.path.exists(p):
            base = dict(base, **json.load(open(p, encoding="utf-8")))
    return base


def convinzioni_con_peso(testi, posizioni, nav):
    """Abbina ogni convinzione alle posizioni in portafoglio e ne calcola il peso.

    L'abbinamento e' per parole chiave (`match`) sulla descrizione del titolo. Una
    convinzione che non trova nessuna posizione **non viene riportata**: e' l'unico modo
    di non raccontare al cliente una tesi su un titolo che non ha piu' in portafoglio.
    """
    out = []
    for c in testi.get("convinzioni") or ():
        chiavi = [k.upper() for k in (c.get("match") or [])]
        if not chiavi:
            continue
        val = 0.0
        for p in posizioni or ():
            des = (p.get("des") or "").upper()
            if any(k in des for k in chiavi):
                val += float(p.get("valmer") or 0.0)
        if val <= 0:
            continue
        out.append({"titolo": c.get("titolo") or "", "perche": c.get("perche") or "",
                    "val": val, "pct": (val / nav) if nav else None})
    return sorted(out, key=lambda r: -r["val"])
