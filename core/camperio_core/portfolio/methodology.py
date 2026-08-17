"""Metodologia Camperio (ex skill camperio-portfolio, corpo da Comitato_App — voce 18).

Regole validate dall'uso in produzione: VALOREFUT = esposizione delta-adjusted;
framework Difesa/Centro Campo/Attacco; oro = asset class autonoma fuori FX;
fondi UCITS → look-through. Formati numerici in render/, colori in branding/.
"""

MACRO_ORDER = ['Difesa', 'Centro Campo', 'Attacco', 'Overlay', 'Altro']


def macro(grutit):
    """Mappa il GRUTIT Oracle in (macro, sottoclasse) del framework Camperio."""
    g = (grutit or "").upper()
    if g.startswith('A'): return ('Difesa', 'Obbligazionario')
    if g.startswith('Z'): return ('Difesa', 'Liquidità & margini')
    if g == 'H19':        return ('Difesa', 'Oro fisico')
    if g == 'H14':        return ('Difesa', 'ETF obbligazionari')
    if g in ('H06', 'H20'): return ('Centro Campo', 'Fondi UCITS')
    if g in ('H10', 'H16', 'H18'): return ('Attacco', 'ETF azionari')
    if g == 'H23':        return ('Attacco', 'REIT')
    if g.startswith('E') or g.startswith('B'): return ('Attacco', 'Azioni dirette')
    if g.startswith('F'): return ('Overlay', 'Derivati (opzioni)')
    if g.startswith('H'): return ('Centro Campo', 'Fondi/ETF')
    return ('Altro', 'Altro')


# ---------- valuta dal ticker Bloomberg (vista FX look-through, regole skill) ----------
# suffisso borsa -> valuta di negoziazione
_EXCH = {
    'US': 'USD', 'LN': 'GBP', 'GY': 'EUR', 'GR': 'EUR', 'FP': 'EUR', 'NA': 'EUR',
    'IM': 'EUR', 'SM': 'EUR', 'SW': 'CHF', 'VX': 'CHF', 'DC': 'DKK', 'SS': 'SEK',
    'NO': 'NOK', 'JT': 'JPY', 'JP': 'JPY', 'TT': 'TWD', 'KS': 'KRW', 'HK': 'HKD',
    'CH': 'CNY', 'C1': 'CNY', 'AU': 'AUD', 'CN': 'CAD', 'CT': 'CAD', 'BZ': 'BRL', 'IN': 'INR',
}
# eccezioni single-name validate (skill matrice-valutaria.md)
_OVERRIDE_BBG = {
    'SMSN LI': 'KRW',   # Samsung GDR: sottostante coreano
}


def _ccy_from_isin(isin):
    if not isin: return None
    cc = isin[:2].upper()
    eur_area = {'DE','FR','IT','ES','NL','EU','AT','BE','PT','IE','FI','LU','GR'}
    m = {'US':'USD','GB':'GBP','NO':'NOK','SE':'SEK','DK':'DKK','CH':'CHF','JP':'JPY','CA':'CAD','AU':'AUD'}
    if cc in eur_area: return 'EUR'
    if cc in m: return m[cc]
    return None  # XS supranational e altri -> da DESTITB


_NAME_CCY = [
    ('NORWEGIAN', 'NOK'), ('NORWAY', 'NOK'), ('US TREAS', 'USD'), ('UNITED STATES', 'USD'),
    ('UNITED KINGDOM', 'GBP'), ('GILT', 'GBP'), ('JAPAN', 'JPY'),
]


def _ccy_from_descr(descr):
    d = (descr or '').upper()
    # tag valuta esplicito tra parentesi (es. supranational "... (BRL)")
    for tag in ('BRL','INR','MXN','ZAR','TRY','PLN','HUF','CNY','CNH','IDR','KRW','USD','GBP','NOK','SEK','DKK','CHF','JPY'):
        if '(' + tag + ')' in d: return tag
    # emittente/paese nel nome del titolo (bond)
    for kw, ccy in _NAME_CCY:
        if kw in d: return ccy
    return None


def currency_of(pos):
    """Valuta di esposizione di una posizione. pos: dict con grutit, bloomberg, codisin, des.
    Ritorna codice ISO, None per asset fuori FX (oro), 'LOOKTHROUGH' per i fondi."""
    g = (pos.get('grutit') or '').upper()
    des = pos.get('des') or pos.get('destitb') or ''
    bbg = (pos.get('bbg') or pos.get('bloomberg') or '').strip()
    # oro: asset class autonoma, fuori dal computo FX
    if g == 'H19': return None
    # fondi UCITS: richiedono look-through (file repository) -> marcati a parte
    if g in ('H06', 'H20'): return 'LOOKTHROUGH'
    # liquidità/margini: dal nome (EUR/USD)
    if g.startswith('Z'):
        u = des.upper()
        if 'USD' in u or 'USA' in u: return 'USD'
        return 'EUR'
    # ticker Bloomberg "TICKER EXCH ..."
    key = ' '.join(bbg.split()[:2]) if bbg else ''
    if key in _OVERRIDE_BBG: return _OVERRIDE_BBG[key]
    parts = bbg.split()
    if len(parts) >= 2:
        ex = parts[1].upper()
        if ex in _EXCH:
            # ETF EM diversificato -> Other EM (skill)
            if 'EMERGING' in des.upper() or 'MSCI EM' in des.upper(): return 'EM'
            return _EXCH[ex]
    # bond / titoli senza suffisso utile -> ISIN poi descrizione
    c = _ccy_from_isin(pos.get('codisin') or pos.get('isin'))
    if c: return c
    c = _ccy_from_descr(des)
    if c: return c
    return 'EUR'  # default prudenziale (govt area EUR)


CCY_LABEL = {'EM': 'Other EM', 'LOOKTHROUGH': 'Fondi (look-through)'}
