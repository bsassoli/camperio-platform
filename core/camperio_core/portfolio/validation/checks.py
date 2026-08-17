"""Controlli deterministici sui report di portafoglio Camperio.

Questo modulo NON usa il modello: è aritmetica pura. È il "layer di controllo
deterministico" richiesto in riunione (requisiti A2.1, Parte C) — l'unico modo
per sterilizzare le allucinazioni del modello sui numeri.

Ogni funzione ritorna un `ValidationResult`. Due livelli di severità:
  - ERROR   → blocca l'emissione del report (un report al cliente non può essere sbagliato)
  - WARNING → segnalazione (es. soglie di concentrazione): NON blocca

Le funzioni operano su strutture Python semplici (dict, list di dict) così da
essere prive di dipendenze e banali da testare con dati sintetici.

ATTENZIONE — i valori in CONFIG (tolleranze) sono DECISIONI DI DOMINIO:
vanno confermati con Edoardo/Bernardino. Sono il punto in cui si bilancia
"rigore del controllo" vs "falsi allarmi da arrotondamento".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# --- CONFIG (decisioni di dominio — rivedere) --------------------------------

# Tolleranze sui controlli aritmetici.
TOL_FX_SUM_REL = 0.005        # 0,5% del NAV: scarto massimo sulla somma valute
TOL_FUND_QUOTA_REL = 0.005    # 0,5% della quota: somma valute del fondo vs quota Camperio
TOL_CROSS_PAGE = 0.0001       # 0,01 p.p.: stesso valore deve coincidere tra pagine diverse

# Soglie di concentrazione (da skill §B8) — generano AVVISI, non errori.
THR_SINGLE_FLAG = 0.015       # >1,5% NAV → flag Comitato
THR_SINGLE_BLOCK = 0.020      # >2,0% NAV → bloccare nuovi acquisti
THR_CLUSTER_TOP5 = 0.080      # cluster top 5 di un tema >8% NAV → escalation
THR_AI_TOTAL = 0.250          # tema AI totale >25% NAV → revisione tilt
THR_USD_TOTAL = 0.350         # USD totale >35% NAV → revisione hedge FX

# Mapping FX speciali (da skill §B4). Lo strumento DEVE stare nella valuta attesa.
SPECIAL_FX_BY_TICKER = {
    "SMSN LI": "KRW",       # Samsung GDR: sottostante coreano, non USD
    "IEEM": "Other EM",     # ETF MSCI EM: paniere diversificato, non USD
}
SPECIAL_FX_BY_ISIN = {
    "US912810US59": "USD",  # US Treasury 2056 (TIPS)
}
GOLD_TICKERS = {"IGLN", "4ND360"}  # oro fisico: asset class autonoma, fuori FX

# Aggregazioni obbligatorie (da skill §B5).
ALPHABET_TICKERS = {"GOOGL US", "GOOG US"}          # vanno sempre aggregati
SAMSUNG_FORBIDDEN = {"009150 KS", "006400 KS", "207940 KS"}  # Electro-Mech, SDI, Biologics


# --- Tipi di risultato --------------------------------------------------------

class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class Finding:
    severity: Severity
    code: str
    message: str


@dataclass
class ValidationResult:
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.WARNING]

    @property
    def ok(self) -> bool:
        """Il report è emettibile se non ci sono ERROR (i WARNING sono ammessi)."""
        return not self.errors

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        return ValidationResult(self.findings + other.findings)


def _error(code: str, message: str) -> ValidationResult:
    return ValidationResult([Finding(Severity.ERROR, code, message)])


def _warning(code: str, message: str) -> ValidationResult:
    return ValidationResult([Finding(Severity.WARNING, code, message)])


def _ok() -> ValidationResult:
    return ValidationResult([])


# --- C: coerenza aritmetica ---------------------------------------------------

def check_fx_sums_to_nav(fx: dict[str, float], nav: float,
                         tol: float = TOL_FX_SUM_REL) -> ValidationResult:
    """La somma di tutte le voci della matrice valutaria deve essere = NAV.

    `fx` include eventuale "Oro" (asset class autonoma ma parte del 100% NAV).
    """
    total = sum(fx.values())
    if nav == 0:
        return _error("fx_nav_zero", "NAV nullo: impossibile validare la matrice valutaria.")
    scarto_rel = abs(total - nav) / abs(nav)
    if scarto_rel > tol:
        return _error(
            "fx_sum_mismatch",
            f"La somma valute (€{total:,.0f}) non torna col NAV (€{nav:,.0f}): "
            f"scarto {scarto_rel:.2%} > tolleranza {tol:.2%}.",
        )
    return _ok()


def check_fund_sum_equals_quota(fund_fx: dict[str, float], quota: float,
                                tol: float = TOL_FUND_QUOTA_REL) -> ValidationResult:
    """La somma delle valute di un fondo deve essere = quota Camperio nel fondo."""
    total = sum(fund_fx.values())
    if quota == 0:
        return _error("fund_quota_zero", "Quota del fondo nulla: impossibile validare.")
    scarto_rel = abs(total - quota) / abs(quota)
    if scarto_rel > tol:
        return _error(
            "fund_sum_mismatch",
            f"La somma valute del fondo (€{total:,.0f}) non torna con la quota "
            f"Camperio (€{quota:,.0f}): scarto {scarto_rel:.2%} > {tol:.2%}.",
        )
    return _ok()


def check_cross_page_consistency(occurrences: dict[str, list[float]],
                                 tol: float = TOL_CROSS_PAGE) -> ValidationResult:
    """Lo stesso valore deve coincidere ovunque compaia nel report.

    `occurrences`: per ogni metrica, la lista dei valori trovati nelle varie pagine.
    Es. {"USD_pct": [0.2549, 0.229]} → incoerenza (il bug della riunione).
    """
    result = _ok()
    for metrica, valori in occurrences.items():
        if len(valori) < 2:
            continue
        if max(valori) - min(valori) > tol:
            result = result.merge(_error(
                "cross_page_mismatch",
                f"'{metrica}' assume valori diversi nelle pagine: {valori} "
                f"(scarto {max(valori) - min(valori):.4f} > {tol}).",
            ))
    return result


# --- B4: mapping strumenti speciali ------------------------------------------

def check_special_mappings(positions: list[dict]) -> ValidationResult:
    """Verifica i mapping FX tassativi (Samsung→KRW, IEEM→Other EM, TIPS→USD, oro fuori FX)."""
    result = _ok()
    for p in positions:
        ticker = p.get("ticker")
        isin = p.get("isin")
        currency = p.get("currency")
        nome = p.get("name", ticker or isin or "?")

        # Oro: asset class autonoma, nessuna valuta FX.
        if p.get("asset_class") == "Oro" or ticker in GOLD_TICKERS:
            if currency:
                result = result.merge(_error(
                    "oro_in_fx",
                    f"'{nome}' è oro (asset class autonoma): non deve avere valuta FX "
                    f"(trovata '{currency}').",
                ))
            continue

        if ticker in SPECIAL_FX_BY_TICKER:
            attesa = SPECIAL_FX_BY_TICKER[ticker]
            if currency != attesa:
                result = result.merge(_error(
                    "fx_mapping_errato",
                    f"'{nome}' ({ticker}) deve stare in {attesa}, trovato '{currency}'.",
                ))
        if isin in SPECIAL_FX_BY_ISIN:
            attesa = SPECIAL_FX_BY_ISIN[isin]
            if currency != attesa:
                result = result.merge(_error(
                    "fx_mapping_errato",
                    f"'{nome}' (ISIN {isin}) deve stare in {attesa}, trovato '{currency}'.",
                ))
    return result


# --- B5: aggregazioni ---------------------------------------------------------

def check_aggregations(positions: list[dict]) -> ValidationResult:
    """Verifica le aggregazioni obbligatorie (Alphabet A+C, controllate Samsung, fondo 21st)."""
    result = _ok()
    tickers_standalone = [p.get("ticker") for p in positions]

    # Alphabet: GOOGL US e GOOG US non devono comparire come due posizioni separate.
    if ALPHABET_TICKERS.issubset(set(tickers_standalone)):
        result = result.merge(_error(
            "alphabet_non_aggregato",
            "Alphabet Class A (GOOGL US) e Class C (GOOG US) compaiono separate: "
            "vanno sempre aggregate in un'unica posizione.",
        ))

    for p in positions:
        nome = p.get("name", "")
        # Samsung Electronics non deve includere le controllate del gruppo.
        if "samsung electronics" in nome.lower():
            componenti = set(p.get("components", []))
            vietate = componenti & SAMSUNG_FORBIDDEN
            if vietate:
                result = result.merge(_error(
                    "samsung_controllate",
                    f"'{nome}' include controllate separate {sorted(vietate)}: "
                    "Electro-Mechanics/SDI/Biologics sono società distinte, vanno escluse.",
                ))
        # Fondo 21st: replica il model portfolio, non va conteggiato come posizione.
        if "21st" in nome.lower() or p.get("ticker") == "21ST":
            result = result.merge(_error(
                "fondo_21st_doppio_conteggio",
                f"'{nome}' è il fondo 21st (replica del model portfolio azionario): "
                "non va conteggiato come posizione (doppio conteggio ~€84M equity).",
            ))
    return result


# --- B8: concentrazione (avvisi) ---------------------------------------------

def check_concentration(positions: list[dict]) -> ValidationResult:
    """Segnala (NON blocca) i superamenti delle soglie di concentrazione single-name."""
    result = _ok()
    for p in positions:
        peso = p.get("weight")
        if peso is None:
            continue
        # La soglia §B8 è sui SINGLE-NAME azionari (post look-through). Fondi, bond,
        # oro ed ETF non sono single-name: si saltano. Una posizione senza asset_class
        # esplicita è trattata come single-name (per i test sintetici).
        if p.get("is_fund") or p.get("asset_class") not in (None, "Equity"):
            continue
        nome = p.get("name", p.get("ticker", "?"))
        if peso > THR_SINGLE_BLOCK:
            result = result.merge(_warning(
                "concentr_block",
                f"'{nome}' al {peso:.2%} NAV supera il {THR_SINGLE_BLOCK:.1%}: "
                "bloccare nuovi acquisti, valutare alleggerimento.",
            ))
        elif peso > THR_SINGLE_FLAG:
            result = result.merge(_warning(
                "concentr_flag",
                f"'{nome}' al {peso:.2%} NAV supera il {THR_SINGLE_FLAG:.1%}: "
                "flag per il Comitato Investimenti.",
            ))
    return result
