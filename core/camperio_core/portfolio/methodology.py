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
