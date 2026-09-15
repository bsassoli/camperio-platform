"""Query Oracle del Monitoraggio Promotori, portate 1:1 dall'artifact cowork.

Unica differenza voluta: referente e date sono bind variable (:ref, :data, :dal, :al).
Nell'artifact finivano concatenati nel testo SQL. Gli schemi arrivano solo dalle
costanti di questo modulo. Le ragioni dei filtri (storico a 5 anni, ultimo PERIODO per
singolo contratto, tabelle base WCTDD, esclusione dei contratti chiusi) sono state
verificate su Oracle dall'autore e sono riassunte accanto a ogni query.

RTO = ANTASIMN / ANTALOCN · GPM = ANTASIMGEST / ANTALOCGEST.
"""

_SCHEMI = {"RTO": ("ANTASIMN", "ANTALOCN"), "GPM": ("ANTASIMGEST", "ANTALOCGEST")}


def _unione(modello, ordine=("RTO", "GPM")):
    """Ripete la stessa SELECT sui due schemi e le unisce, nell'ordine dell'originale."""
    return "\nUNION ALL\n".join(
        modello.format(ambito=a, sim=_SCHEMI[a][0], loc=_SCHEMI[a][1]) for a in ordine)


# Attribuzione al referente: tag ufficiale ANTALOC.TAGS_VALUE (NN_TGT=1019), non CNT.CODOPE.
ELENCO_REFERENTI = """SELECT REFCOM, COUNT(*) N FROM (
  SELECT t.VALITEM_DES REFCOM FROM ANTASIMN.CNT n JOIN ANTALOC.TAGS_VALUE t ON t.CODICE=n.CODCLI AND t.NN_TGT=1019
  UNION ALL
  SELECT t.VALITEM_DES FROM ANTASIMGEST.CNT n JOIN ANTALOC.TAGS_VALUE t ON t.CODICE=n.CODCLI AND t.NN_TGT=1019
) GROUP BY REFCOM ORDER BY REFCOM"""

CONTRATTI = _unione("""SELECT '{ambito}' AMBITO, n.CODCLI, n.DESCLI, n.TIPOGE,
       TO_CHAR(n.DATAPER,'YYYY-MM-DD') DATAPER, TO_CHAR(n.DATCHIU,'YYYY-MM-DD') DATCHIU
FROM {sim}.CNT n JOIN ANTALOC.TAGS_VALUE t ON t.CODICE=n.CODCLI AND t.NN_TGT=1019
WHERE t.VALITEM_DES=:ref""")

# Snapshot di fine anno più l'ultimo PERIODO del singolo contratto (non il massimo di
# schema: le rivalutazioni GPM arrivano a lotti in giorni diversi). Ultimi 5 anni: la
# query completa dal 1999 superava il limite di risposta sui referenti più grandi.
SRE = _unione("""SELECT '{ambito}' AMBITO, s.CODCLI, TO_CHAR(s.PERIODO,'YYYY-MM-DD') PERIODO,
       s.CONSFIN, s.APPORTI, s.PRELIEVI, s.TCLI
FROM {sim}.SRE s JOIN ANTALOC.TAGS_VALUE t ON t.CODICE=s.CODCLI AND t.NN_TGT=1019
WHERE t.VALITEM_DES=:ref
  AND (TO_CHAR(s.PERIODO,'MMDD')='1231'
       OR s.PERIODO=(SELECT MAX(s2.PERIODO) FROM {sim}.SRE s2 WHERE s2.CODCLI=s.CODCLI))
  AND EXTRACT(YEAR FROM s.PERIODO) >= EXTRACT(YEAR FROM SYSDATE) - 4""")

# Fotografia "alla data": per ogni contratto l'ultimo snapshot con PERIODO <= :data.
SRE_ALLA_DATA = _unione("""SELECT '{ambito}' AMBITO, s.CODCLI, TO_CHAR(s.PERIODO,'YYYY-MM-DD') PERIODO,
       s.CONSFIN, s.APPORTI, s.PRELIEVI, s.TCLI
FROM {sim}.SRE s JOIN ANTALOC.TAGS_VALUE t ON t.CODICE=s.CODCLI AND t.NN_TGT=1019
WHERE t.VALITEM_DES=:ref
  AND s.PERIODO=(SELECT MAX(s2.PERIODO) FROM {sim}.SRE s2
                 WHERE s2.CODCLI=s.CODCLI AND s2.PERIODO<=TO_DATE(:data,'YYYY-MM-DD'))""")

# Commissioni = MOV.CTVCNO nette in EUR (storni, ONE e RSP esclusi). Tre aggregazioni
# separate invece di una a grana fine, che sui referenti grandi veniva troncata.
_IMPORTO_EUR = ("ROUND(SUM(DECODE(NVL(l.DIVI,'242'),'242', NVL(v.CTVCNO,0), "
                "ROUND(NVL(v.CTVCNO,0)/DECODE(NVL(v.CAMUNI,0),0,1,v.CAMUNI),2))),2)")
_MOV_COMMISSIONI = """FROM {sim}.MOV v JOIN {sim}.CNT n ON n.CODCLI=v.CODCLI
JOIN ANTALOC.TAGS_VALUE t ON t.CODICE=v.CODCLI AND t.NN_TGT=1019
LEFT JOIN {sim}.TIT l ON l.CODABI=v.CODABI
WHERE t.VALITEM_DES=:ref AND NVL(v.FBOSTO,0)=0 AND NVL(v.OPESTO,0)=0 AND v.TIPOPE NOT IN ('ONE','RSP')"""

COMMISSIONI_PER_CONTRATTO = _unione(
    "SELECT '{ambito}' AMBITO, v.CODCLI, EXTRACT(YEAR FROM v.DATOPE) ANNO, " + _IMPORTO_EUR + " IMPORTO\n"
    + _MOV_COMMISSIONI + "\n"
    "  AND EXTRACT(YEAR FROM v.DATOPE) >= EXTRACT(YEAR FROM SYSDATE) - 4\n"
    "GROUP BY v.CODCLI, EXTRACT(YEAR FROM v.DATOPE)\n"
    "HAVING SUM(NVL(v.CTVCNO,0))<>0")

COMMISSIONI_PER_TRIMESTRE = _unione(
    "SELECT EXTRACT(YEAR FROM v.DATOPE) ANNO, TO_CHAR(v.DATOPE,'Q') TRIM, " + _IMPORTO_EUR + " IMPORTO\n"
    + _MOV_COMMISSIONI + "\n"
    "GROUP BY EXTRACT(YEAR FROM v.DATOPE), TO_CHAR(v.DATOPE,'Q')\n"
    "HAVING SUM(NVL(v.CTVCNO,0))<>0")

COMMISSIONI_PER_TIPO = _unione(
    "SELECT EXTRACT(YEAR FROM v.DATOPE) ANNO, v.TIPOPE, " + _IMPORTO_EUR + " IMPORTO\n"
    + _MOV_COMMISSIONI + "\n"
    "GROUP BY EXTRACT(YEAR FROM v.DATOPE), v.TIPOPE\n"
    "HAVING SUM(NVL(v.CTVCNO,0))<>0")

# Compravendite eseguite: MOV e non ORD (ORD contiene anche ordini mai eseguiti).
# Solo titoli/fondi (AV%), derivati Exx a due cifre, OPF/OCF. Solo RTO/Consulenza.
OPERAZIONI = """SELECT v.CODCLI, EXTRACT(YEAR FROM v.DATOPE) ANNO, COUNT(*) N
FROM ANTASIMN.MOV v JOIN ANTALOC.TAGS_VALUE t ON t.CODICE=v.CODCLI AND t.NN_TGT=1019
WHERE t.VALITEM_DES=:ref AND NVL(v.FBOSTO,0)=0 AND NVL(v.OPESTO,0)=0
  AND (v.TIPOPE LIKE 'AV%' OR REGEXP_LIKE(v.TIPOPE,'^E[0-9]{2}$') OR v.TIPOPE IN ('OPF','OCF'))
GROUP BY v.CODCLI, EXTRACT(YEAR FROM v.DATOPE)"""

# Fondi alla data "Al": tabelle BASE ANTALOC*.WCTDD (storico giornaliero in DTUNIMER), non
# le VIEW ANTASIM*.WCTDD che valorizzano sempre a oggi. ROW_NUMBER e non subquery
# correlata (~188M righe: timeout). L'hint parte dai pochi CODCLI del referente. Esclusi i
# contratti chiusi prima di Al: senza, un contratto chiuso rientrava nel totale.
_FAMIGLIA_FONDO = """CASE WHEN UPPER(b.DESTITB) LIKE '%DELTA DEFENSIVE%' THEN 'defensive'
    WHEN UPPER(b.DESTITB) LIKE '%DELTA UCITS%' THEN 'delta'
    WHEN UPPER(b.DESTITB) LIKE '%SUPERDISCOVERY%' OR UPPER(b.DESTITB) LIKE '%SUPER DISCOVERY%' THEN 'super'
    WHEN UPPER(b.DESTITB) LIKE '%ALPHA GREEN%' THEN 'alpha' ELSE 'altro' END"""
_CONTRATTI_APERTI_AL = """SELECT DISTINCT t.CODICE FROM ANTALOC.TAGS_VALUE t WHERE t.NN_TGT=1019 AND t.VALITEM_DES=:ref
    MINUS
    SELECT c.CODCLI FROM {sim}.CNT c WHERE c.DATCHIU IS NOT NULL AND c.DATCHIU<TO_DATE(:al,'YYYY-MM-DD')"""
_FINESTRA_20_GIORNI = "w.DTUNIMER<=TO_DATE(:al,'YYYY-MM-DD') AND w.DTUNIMER>TO_DATE(:al,'YYYY-MM-DD')-20"

# Perimetro Controlfida: codice emittente SOCEMI='CON', non il nome del fondo.
FONDI = _unione(
    "SELECT '{ambito}' AMBITO, x.* FROM (\n"
    "SELECT b.CODCLI, b.CODABI, b.DESTITB, " + _FAMIGLIA_FONDO + " FONDO, ROUND(b.VALMER) VALMER\n"
    "FROM (\n"
    "  SELECT /*+ LEADING(r w) USE_NL(w) */ w.CODCLI, w.CODABI, w.DESTITB, w.VALMER,\n"
    "         ROW_NUMBER() OVER (PARTITION BY w.CODCLI, w.CODABI ORDER BY w.DTUNIMER DESC) rn\n"
    "  FROM (\n    " + _CONTRATTI_APERTI_AL + "\n  ) r\n"
    "  JOIN {loc}.WCTDD w ON w.CODCLI=r.CODICE\n"
    "  WHERE w.SOCEMI='CON' AND NVL(w.VALMER,0)<>0\n"
    "    AND " + _FINESTRA_20_GIORNI + "\n"
    ") b WHERE b.rn=1\n"
    ") x", ordine=("GPM", "RTO"))

# Riconciliazione: tutti gli OICR in portafoglio (FONDI='S'), stessa storicizzazione.
FONDI_TOTALE = _unione(
    "SELECT b.CODCLI, ROUND(SUM(b.VALMER)) VALMER FROM (\n"
    "  SELECT /*+ LEADING(r w) USE_NL(w) */ w.CODCLI, w.CODABI, w.VALMER,\n"
    "         ROW_NUMBER() OVER (PARTITION BY w.CODCLI, w.CODABI ORDER BY w.DTUNIMER DESC) rn\n"
    "  FROM (\n    " + _CONTRATTI_APERTI_AL + "\n  ) r\n"
    "  JOIN {loc}.WCTDD w ON w.CODCLI=r.CODICE\n"
    "  WHERE w.FONDI='S' AND NVL(w.VALMER,0)<>0\n"
    "    AND " + _FINESTRA_20_GIORNI + "\n"
    ") b WHERE b.rn=1 GROUP BY b.CODCLI", ordine=("GPM", "RTO"))

# Apporti/prelievi reali: MOV.QUANTI per VBG/VBI (+) e PBG/PBI (-), CTVTIT per GCT.
# I cumulati SRE includono anche addebiti automatici (commissioni, bolli).
FLUSSI_REALI = _unione("""SELECT v.CODCLI,
  ROUND(SUM(CASE WHEN v.TIPOPE IN ('VBG','VBI') THEN NVL(v.QUANTI,0)
                 WHEN v.TIPOPE IN ('PBG','PBI') THEN -NVL(v.QUANTI,0)
                 WHEN v.TIPOPE='GCT' THEN NVL(v.CTVTIT,0)
                 ELSE 0 END),2) FLUSSO
FROM {sim}.MOV v JOIN ANTALOC.TAGS_VALUE t ON t.CODICE=v.CODCLI AND t.NN_TGT=1019
WHERE t.VALITEM_DES=:ref AND v.DATVAL BETWEEN TO_DATE(:dal,'YYYY-MM-DD') AND TO_DATE(:al,'YYYY-MM-DD')
  AND v.TIPOPE IN ('VBG','VBI','PBG','PBI','GCT')
GROUP BY v.CODCLI""", ordine=("GPM", "RTO"))

# Rendiconto ufficiale giornaliero composto sul periodo. L'artifact la interrogava ma non
# mostrava più il risultato (la tabella usa SRE, scelta dell'utente su R1427): qui resta
# definita e NON viene eseguita. Vedi DOMANDE-EDOARDO.md.
RENDIMENTO_UFFICIALE = _unione("""SELECT '{ambito}' AMBITO, g.CODCLI,
  ROUND(SUM(g.PLUSMIN_LORDO),2) PLUSLORDO, ROUND(SUM(g.PLUSMIN_NETTO),2) PLUSNETTO,
  ROUND((EXP(SUM(LN(GREATEST(1+g.REND_CLIENTE_LORDO/100,0.0001))))-1)*100,4) RENDLORDO,
  ROUND((EXP(SUM(LN(GREATEST(1+g.REND_CLIENTE_NETTO/100,0.0001))))-1)*100,4) RENDNETTO
FROM {loc}.GES_RENDI_STORICO g JOIN ANTALOC.TAGS_VALUE t ON t.CODICE=g.CODCLI AND t.NN_TGT=1019
WHERE t.VALITEM_DES=:ref AND g.AL BETWEEN TO_DATE(:dal,'YYYY-MM-DD') AND TO_DATE(:al,'YYYY-MM-DD')
GROUP BY g.CODCLI""")
