"""Calcoli del cruscotto, portati 1:1 dal JavaScript dell'artifact cowork.

Le funzioni lavorano sulle righe grezze delle query (chiavi = colonne Oracle) e ritornano
numeri, mai stringhe formattate: la formattazione resta alla pagina.

Differenze volute rispetto all'originale, tutte senza effetto sui numeri dei casi
normali (dettaglio in DOMANDE-EDOARDO.md):
- un contratto con il solo snapshot "Dal" e nessuna massa nell'anno è trattato come
  senza dato (l'originale sommava `undefined` e il KPI diventava n.d.);
- Dal e Al personalizzati si applicano sempre entrambi, prima Al e poi Dal
  (nell'originale cambiare Al dopo Dal cancellava lo snapshot Dal).
"""
import math
import re
from dataclasses import dataclass

BASE_TCLI = 1000   # indice TCLI di partenza quando manca lo snapshot precedente

SERVIZI = (("rto", "RTO"), ("consulenza", "Consulenza"), ("gestione", "Gestione"))
FAMIGLIE_FONDI = (("delta", "DELTA UCITS"), ("defensive", "Delta Defensive UCITS"),
                  ("super", "Superdiscovery UCITS"), ("alpha", "Alpha Green UCITS"),
                  ("altro", "Altri fondi Controlfida"))


class PeriodoNonValido(ValueError):
    """Anno o date richiesti non utilizzabili: il messaggio è per l'utente."""


def num(v):
    """Numero da una cella Oracle: None, vuoto o non numerico valgono 0 (come num() nel JS)."""
    if v is None or v == "":
        return 0.0
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    return x if math.isfinite(x) else 0.0


def sotto_ambito(ambito, tipoge):
    """GPM → Gestione; su RTO la linea che inizia per L è Consulenza, il resto RTO puro."""
    if ambito == "GPM":
        return "Gestione"
    return "Consulenza" if (tipoge or "").upper().startswith("L") else "RTO"


def _servizio(sotto):
    # come nell'originale, un codice senza contratto noto finisce in Gestione
    return {"RTO": "rto", "Consulenza": "consulenza"}.get(sotto, "gestione")


def categoria_commissione(tipope):
    t = tipope or ""
    if t == "CDG":
        return "Gestione, fee ricorrente (CDG)"
    if t == "CCO":
        return "Consulenza, fee ricorrente (CCO)"
    if t == "CSA":
        return "Servizio, fee ricorrente (CSA)"
    if (t.startswith("AV") or re.fullmatch(r"E[0-9]{2}", t) or t.startswith("FU")
            or t in ("OPF", "OCF")):
        return "Intermediazione/negoziazione (AV*, Exx, FUx, OPF, OCF)"
    if t == "CTC":
        return "Tenuta conto (CTC)"
    return f"Altri oneri, estero/custody/vari ({t})"


@dataclass
class Stato:
    contratti: list            # dict: ambito, codice, intestatario, linea, apertura, chiusura, sotto_ambito
    sre: dict                  # codice -> anno -> snapshot (consfin, apporti, prelievi, tcli, periodo, dal_*)
    anni: list
    commissioni: list          # dict: codice, anno, importo
    comm_per_contratto: dict   # (codice, anno) -> importo
    comm_trimestre: dict       # anno -> [q1, q2, q3, q4]
    comm_tipo: dict            # anno -> {categoria: importo}
    operazioni: dict           # codice -> {anno: n}


@dataclass
class Periodo:
    anno: int
    dal: str
    al: str
    dal_personalizzato: bool
    al_personalizzato: bool
    in_corso: bool


def _snapshot(r):
    return {"consfin": num(r["CONSFIN"]), "apporti": num(r["APPORTI"]),
            "prelievi": num(r["PRELIEVI"]), "tcli": num(r["TCLI"]), "periodo": r["PERIODO"]}


def costruisci_stato(contratti, sre, comm_contratto, comm_trimestre, comm_tipo, operazioni):
    """Equivalente di buildState(): non modifica le righe ricevute."""
    lista = [{"ambito": r["AMBITO"], "codice": r["CODCLI"], "intestatario": r.get("DESCLI") or "",
              "linea": r.get("TIPOGE") or "", "apertura": r.get("DATAPER") or "",
              "chiusura": r.get("DATCHIU") or "",
              "sotto_ambito": sotto_ambito(r["AMBITO"], r.get("TIPOGE"))} for r in contratti]

    per_contratto = {}
    for r in sre:
        per_contratto.setdefault(r["CODCLI"], {})[int(r["PERIODO"][:4])] = _snapshot(r)
    anni = sorted({a for per_anno in per_contratto.values() for a in per_anno})

    commissioni = [{"codice": r["CODCLI"], "anno": int(num(r["ANNO"])), "importo": num(r["IMPORTO"])}
                   for r in comm_contratto]
    mappa = {}
    for c in commissioni:
        chiave = (c["codice"], c["anno"])
        mappa[chiave] = mappa.get(chiave, 0.0) + c["importo"]

    trimestri = {}
    for r in comm_trimestre:
        anno, q = int(num(r["ANNO"])), int(num(r["TRIM"]))
        quattro = trimestri.setdefault(anno, [0.0, 0.0, 0.0, 0.0])
        if 1 <= q <= 4:
            quattro[q - 1] += num(r["IMPORTO"])

    tipi = {}
    for r in comm_tipo:
        per_anno = tipi.setdefault(int(num(r["ANNO"])), {})
        categoria = categoria_commissione(r["TIPOPE"])
        per_anno[categoria] = per_anno.get(categoria, 0.0) + num(r["IMPORTO"])

    ope = {}
    for r in operazioni:
        ope.setdefault(r["CODCLI"], {})[int(num(r["ANNO"]))] = num(r["N"])

    return Stato(lista, per_contratto, anni, commissioni, mappa, trimestri, tipi, ope)


def risolvi_periodo(stato, anno=None, dal=None, al=None):
    """Anno e date effettivi. Senza date: dal 1° gennaio; al 31/12 per gli anni chiusi,
    oppure l'ultimo "aggiornato al" tra i contratti per l'anno in corso."""
    if not stato.anni:
        raise PeriodoNonValido("Nessuna massa disponibile per questo referente negli ultimi 5 anni.")
    ultimo = stato.anni[-1]
    anno = ultimo if anno is None else anno
    if anno not in stato.anni:
        raise PeriodoNonValido(f"Anno {anno} non disponibile per questo referente.")
    if al:
        al_eff = al
    elif anno != ultimo:
        al_eff = f"{anno}-12-31"
    else:
        al_eff = max((s[anno]["periodo"] for s in stato.sre.values()
                      if anno in s and s[anno].get("periodo")), default=f"{anno}-12-31")
    dal_eff = dal or f"{anno}-01-01"
    if dal_eff > al_eff:
        raise PeriodoNonValido("La data Dal non può essere successiva alla data Al.")
    return Periodo(anno, dal_eff, al_eff, bool(dal), bool(al), anno == ultimo)


def applica_al(stato, anno, righe):
    """Sostituisce lo snapshot dell'anno con la fotografia alla data Al (applyCustomAl)."""
    for c in stato.contratti:
        stato.sre.get(c["codice"], {}).pop(anno, None)
    for r in righe:
        stato.sre.setdefault(r["CODCLI"], {})[anno] = _snapshot(r)


def applica_dal(stato, anno, righe):
    """Aggiunge allo snapshot dell'anno la fotografia alla data Dal (applyCustomDal)."""
    for r in righe:
        snap = stato.sre.setdefault(r["CODCLI"], {}).setdefault(anno, {})
        snap.update(dal_consfin=num(r["CONSFIN"]), dal_apporti=num(r["APPORTI"]),
                    dal_prelievi=num(r["PRELIEVI"]), dal_tcli=num(r["TCLI"]),
                    dal_periodo=r["PERIODO"])


def _snap(stato, codice, anno, campo):
    """Snapshot dell'anno solo se contiene il campo richiesto (un solo-Dal non conta)."""
    snap = (stato.sre.get(codice) or {}).get(anno)
    return snap if snap and campo in snap else None


def massa_anno(stato, anno):
    servizi = {k: {"valore": 0.0, "n": 0} for k, _ in SERVIZI}
    totale, n = 0.0, 0
    for c in stato.contratti:
        snap = _snap(stato, c["codice"], anno, "consfin")
        if snap is None:
            continue
        totale += snap["consfin"]
        n += 1
        voce = servizi[_servizio(c["sotto_ambito"])]
        voce["valore"] += snap["consfin"]
        voce["n"] += 1
    return {"totale": totale, "n": n, "servizi": servizi}


def stato_periodo(stato, dal, al):
    """Attivi alla data Al; aperti e chiusi dentro Dal-Al (un contratto può essere entrambi)."""
    attivi = aperti = chiusi = 0
    for c in stato.contratti:
        apertura, chiusura = c["apertura"], c["chiusura"]
        if apertura and apertura <= al and (not chiusura or chiusura > al):
            attivi += 1
        if apertura and dal <= apertura <= al:
            aperti += 1
        if chiusura and dal <= chiusura <= al:
            chiusi += 1
    return {"contratti_attivi": attivi, "contratti_aperti": aperti, "contratti_chiusi": chiusi}


def flusso_contratto(stato, codice, anno):
    """Variazione dei cumulati SRE APPORTI+PRELIEVI rispetto a Dal o al fine anno precedente."""
    snap = _snap(stato, codice, anno, "apporti")
    if snap is None:
        return None
    corrente = snap["apporti"] + snap["prelievi"]
    precedente_anno = _snap(stato, codice, anno - 1, "apporti")
    if "dal_apporti" in snap:
        precedente = snap["dal_apporti"] + snap["dal_prelievi"]
    elif precedente_anno is not None:
        precedente = precedente_anno["apporti"] + precedente_anno["prelievi"]
    else:
        precedente = 0.0
    return corrente - precedente


def rendimento_eur(stato, codice, anno):
    """Variazione di massa al netto del flusso SRE; None se manca la massa di partenza."""
    snap = _snap(stato, codice, anno, "consfin")
    if snap is None:
        return None
    precedente_anno = _snap(stato, codice, anno - 1, "consfin")
    if "dal_consfin" in snap:
        partenza = snap["dal_consfin"]
    elif precedente_anno is not None:
        partenza = precedente_anno["consfin"]
    else:
        return None
    return snap["consfin"] - partenza - (flusso_contratto(stato, codice, anno) or 0.0)


def rendimento_pct(stato, codice, anno):
    """Rapporto tra indici TCLI di fine e inizio periodo, base 1000 se manca l'inizio."""
    snap = (stato.sre.get(codice) or {}).get(anno)
    if not snap or not snap.get("tcli"):
        return None
    if "dal_tcli" in snap:
        partenza = snap["dal_tcli"] or BASE_TCLI
    else:
        partenza = ((stato.sre.get(codice) or {}).get(anno - 1) or {}).get("tcli") or BASE_TCLI
    return (snap["tcli"] / partenza - 1) * 100


def commissioni_anno(stato, anno):
    return sum(c["importo"] for c in stato.commissioni if c["anno"] == anno)


def commissioni_per_servizio(stato, anno):
    sotto = {c["codice"]: c["sotto_ambito"] for c in stato.contratti}
    servizi = {k: {"valore": 0.0, "codici": set()} for k, _ in SERVIZI}
    for c in stato.commissioni:
        if c["anno"] != anno:
            continue
        voce = servizi[_servizio(sotto.get(c["codice"]))]
        voce["valore"] += c["importo"]
        voce["codici"].add(c["codice"])
    return {k: {"valore": v["valore"], "n": len(v["codici"])} for k, v in servizi.items()}


def fondi_per_famiglia(righe, sotto_per_codice):
    """Famiglie di prodotto (n = posizioni, come l'originale) e spaccato per servizio (n = contratti)."""
    famiglie = {k: {"valore": 0.0, "n": 0} for k, _ in FAMIGLIE_FONDI}
    servizi = {k: {"valore": 0.0, "codici": set()} for k, _ in SERVIZI}
    for r in righe:
        chiave = (r.get("FONDO") or "").strip()
        if chiave not in famiglie:
            continue
        valore = num(r["VALMER"])
        famiglie[chiave]["valore"] += valore
        famiglie[chiave]["n"] += 1
        voce = servizi[_servizio(sotto_per_codice.get(r["CODCLI"]))]
        voce["valore"] += valore
        voce["codici"].add(r["CODCLI"])
    return {"famiglie": famiglie,
            "servizi": {k: {"valore": v["valore"], "n": len(v["codici"])} for k, v in servizi.items()}}


def tabella_contratti(stato, anno, dal):
    """Dettaglio: esclusi solo i contratti chiusi prima di Dal."""
    righe = []
    for c in stato.contratti:
        if c["chiusura"] and c["chiusura"] < dal:
            continue
        codice = c["codice"]
        snap = (stato.sre.get(codice) or {}).get(anno) or {}
        righe.append({
            "sotto_ambito": c["sotto_ambito"], "codice": codice, "intestatario": c["intestatario"],
            "linea": c["linea"], "apertura": c["apertura"], "chiusura": c["chiusura"],
            "massa": snap.get("consfin"), "aggiornato_al": snap.get("periodo"),
            "saldo": flusso_contratto(stato, codice, anno),
            "rendimento_eur": rendimento_eur(stato, codice, anno),
            "rendimento_pct": rendimento_pct(stato, codice, anno),
            "commissioni": stato.comm_per_contratto.get((codice, anno), 0.0),
            # le compravendite si contano solo su ANTASIMN: per la Gestione non c'è il dato
            "operazioni": (stato.operazioni.get(codice, {}).get(anno, 0)
                           if c["ambito"] == "RTO" else None),
        })
    return righe


def _quota(parte, totale):
    """Percentuale per composizioni e barre: 0 quando il totale è 0 (pctNum nel JS)."""
    return parte / totale * 100 if totale else 0.0


def _quota_o_nulla(parte, totale):
    """Percentuale che l'originale mostrava come n.d. quando il totale è 0."""
    return parte / totale * 100 if totale else None


def _lista_servizi(servizi, totale):
    return [{"chiave": k, "etichetta": etichetta, "valore": servizi[k]["valore"],
             "quota": _quota(servizi[k]["valore"], totale), "n": servizi[k]["n"]}
            for k, etichetta in SERVIZI]


def componi_cruscotto(stato, periodo, fondi, fondi_totale, flussi):
    """Tutto quello che la pagina mostra, già calcolato: equivalente di render()."""
    anno, dal, al = periodo.anno, periodo.dal, periodo.al
    masse = massa_anno(stato, anno)
    totale = masse["totale"]
    comm = commissioni_anno(stato, anno)
    sotto = {c["codice"]: c["sotto_ambito"] for c in stato.contratti}
    agg_fondi = fondi_per_famiglia(fondi, sotto)
    totale_fondi = sum(f["valore"] for f in agg_fondi["famiglie"].values())
    tipi = stato.comm_tipo.get(anno, {})

    return {
        "anni": stato.anni,
        "anno": anno,
        "anno_in_corso": periodo.in_corso,
        "periodo": {"dal": dal, "al": al, "dal_personalizzato": periodo.dal_personalizzato,
                    "al_personalizzato": periodo.al_personalizzato},
        "kpi": {
            "massa": totale,
            "flusso_reale": sum(num(r["FLUSSO"]) for r in flussi),
            "commissioni": comm,
            "rendimento_commissionale": _quota_o_nulla(comm, totale),
            **stato_periodo(stato, dal, al),
            "contratti_storico": len(stato.contratti),
            "fondi": totale_fondi,
            "fondi_quota_massa": _quota(totale_fondi, totale),
        },
        "masse": _lista_servizi(masse["servizi"], totale),
        "commissioni": {
            "totale": comm,
            "totale_quota_massa": _quota_o_nulla(comm, totale),
            "servizi": _lista_servizi(commissioni_per_servizio(stato, anno), comm),
            "per_trimestre": stato.comm_trimestre.get(anno, [0.0, 0.0, 0.0, 0.0]),
            "per_tipo": [{"categoria": k, "importo": v,
                          "quota_massa": _quota_o_nulla(v, totale),
                          "quota_commissioni": _quota_o_nulla(v, comm)}
                         for k, v in sorted(tipi.items(), key=lambda kv: -kv[1])],
        },
        "fondi": {
            "famiglie": [{"chiave": k, "etichetta": etichetta,
                          "valore": agg_fondi["famiglie"][k]["valore"],
                          "quota_massa": _quota(agg_fondi["famiglie"][k]["valore"], totale),
                          "n": agg_fondi["famiglie"][k]["n"]} for k, etichetta in FAMIGLIE_FONDI],
            "totale": totale_fondi,
            "quota_massa": _quota(totale_fondi, totale),
            "servizi": _lista_servizi(agg_fondi["servizi"], totale_fondi),
            "tutti_oicr": {"valore": sum(num(r["VALMER"]) for r in fondi_totale),
                           "n": len({r["CODCLI"] for r in fondi_totale})},
        },
        "contratti": tabella_contratti(stato, anno, dal),
    }
