# -*- coding: utf-8 -*-
"""Rendimento della gestione: netto, lordo, benchmark (metodologia validata in produzione).

`SRE.TCLI` e' il montante **netto** commissioni: e' il rendimento che il gestionale
calcola per il cliente dopo gli addebiti. Camperio espone invece al cliente il
rendimento **lordo**, cioe' quanto ha reso la gestione prima del costo del servizio,
restituendo al montante le commissioni Camperio **IVA inclusa** (`MOV.CTVREG`).

    lordo = TCLI(al) / TCLI(dal) * PRODOTTO_t (1 + commissione_t / NAV_t) - 1

dove `t` sono i giorni di addebito nel periodo e `NAV_t` e' il patrimonio del
**giorno dell'addebito** (`SRE.CONSFIN`, quindi post-commissione). Usare il NAV del
giorno precedente sposta il risultato di circa 0,001 punti: non e' equivalente.

Il benchmark (`SRE.TBMK`) e' gia' lordo e non si rettifica.

Non entrano nel riaccredito: commissioni di negoziazione, Tobin tax, ritenute sui
dividendi, imposta di bollo. Il bollo e' un onere fiscale che il gestionale registra
come prelievo mensile, quindi e' gia' fuori dal calcolo del rendimento.

Riferimento verificato (contratto S9060, 31/12/2025 -> 15/09/2026): netto 8,8083%,
commissioni IVA inclusa 26.260,14 EUR, lordo 9,1462% (Antana espone 9,146%),
benchmark 7,0291%.
"""

# TIPOPE di MOV che rappresentano commissioni Camperio da restituire al montante.
TIPI_COMMISSIONE = ("CDG", "RSP", "CTR", "CPE")


def fattore_commissioni(commissioni):
    """Prodotto di (1 + importo / nav) sugli addebiti passati.

    `commissioni` e' una sequenza di dizionari con almeno `importo` (IVA inclusa) e
    `nav` (patrimonio del giorno di addebito). Gli addebiti senza NAV positivo sono
    ignorati: senza denominatore il riaccredito non e' calcolabile e inventarlo
    falserebbe il rendimento.
    """
    f = 1.0
    for c in commissioni or ():
        try:
            nav = float(c.get("nav") or 0.0)
            imp = float(c.get("importo") or 0.0)
        except (TypeError, ValueError):
            continue
        if nav > 0:
            f *= 1.0 + imp / nav
    return f


def nel_periodo(commissioni, dal, al):
    """Filtra gli addebiti con dal < data <= al (date ISO 'YYYY-MM-DD')."""
    return [c for c in (commissioni or ()) if dal < (c.get("data") or "") <= al]


def rendimento_netto(tcli_dal, tcli_al):
    """Rendimento netto commissioni, in frazione (0,088 = 8,8%). None se non calcolabile."""
    try:
        tcli_dal = float(tcli_dal); tcli_al = float(tcli_al)
    except (TypeError, ValueError):
        return None
    if tcli_dal <= 0:
        return None
    return tcli_al / tcli_dal - 1.0


def rendimento_lordo(tcli_dal, tcli_al, commissioni):
    """Rendimento al lordo delle commissioni Camperio, in frazione."""
    netto = rendimento_netto(tcli_dal, tcli_al)
    if netto is None:
        return None
    return (1.0 + netto) * fattore_commissioni(commissioni) - 1.0


def rendimento_benchmark(tbmk_dal, tbmk_al):
    """Rendimento del parametro di riferimento, in frazione. Gia' lordo, nessuna rettifica."""
    return rendimento_netto(tbmk_dal, tbmk_al)


def totale_commissioni(commissioni):
    """Somma degli importi IVA inclusa."""
    tot = 0.0
    for c in commissioni or ():
        try:
            tot += float(c.get("importo") or 0.0)
        except (TypeError, ValueError):
            pass
    return tot


def risultato_lordo(risultato_netto, commissioni):
    """Risultato in euro al lordo: delta di PLUSMIN piu' le commissioni restituite."""
    try:
        return float(risultato_netto) + totale_commissioni(commissioni)
    except (TypeError, ValueError):
        return None


def rendimenti_mensili(serie, commissioni):
    """Rendimenti mensili lordi del portafoglio e del parametro.

    `serie` e' la sequenza ordinata dei fine-mese [{data, tcli, tbmk}, ...]: il primo
    elemento e' la base e non produce una riga. Ritorna
    [{anno, mese, lordo, bench}, ...] con i valori in frazione.
    """
    out = []
    serie = list(serie or ())
    for prec, corr in zip(serie, serie[1:]):
        d0 = prec.get("data") or ""
        d1 = corr.get("data") or ""
        lordo = rendimento_lordo(prec.get("tcli"), corr.get("tcli"),
                                 nel_periodo(commissioni, d0, d1))
        bench = rendimento_benchmark(prec.get("tbmk"), corr.get("tbmk"))
        try:
            anno, mese = int(d1[:4]), int(d1[5:7])
        except (ValueError, IndexError):
            continue
        out.append({"anno": anno, "mese": mese, "lordo": lordo, "bench": bench})
    return out


def componi(valori):
    """Composizione di rendimenti frazionari: (1+r1)(1+r2)... - 1. None se un valore manca."""
    f = 1.0
    visto = False
    for r in valori or ():
        if r is None:
            return None
        f *= 1.0 + float(r)
        visto = True
    return (f - 1.0) if visto else None


def media_annua(cumulato, anni):
    """Rendimento medio annuo composto. None sotto l'anno: annualizzare un periodo
    infrannuale produce un numero che non significa nulla."""
    if cumulato is None:
        return None
    try:
        anni = float(anni)
    except (TypeError, ValueError):
        return None
    if anni < 1.0 or 1.0 + cumulato <= 0:
        return None
    return (1.0 + cumulato) ** (1.0 / anni) - 1.0
