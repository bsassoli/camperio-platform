"""Formattazione italiana dei numeri (da Comitato_App/methodology.py, copia validata).

1.234.567,89 — punto per le migliaia, virgola per i decimali; input non numerico → "—".
"""
import math


def eur(x, dec=0):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(x):
        return "—"
    s = f"{x:,.{dec}f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return "€ " + s


def pct(x, dec=2, seg=True):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(x):
        return "—"
    s = f"{x:+.{dec}f}" if seg else f"{x:.{dec}f}"
    return s.replace(".", ",") + "%"


def num(x, dec=0):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(x):
        return "—"
    return f"{x:,.{dec}f}".replace(",", "§").replace(".", ",").replace("§", ".")
