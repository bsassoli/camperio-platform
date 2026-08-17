"""Layer di controllo deterministico (voce 18): aritmetica pura, mai il modello.

Regola operativa: PRIMA di emettere qualunque report eseguire validate_report;
se ok è False si corregge e NON si emette. I WARNING si riportano, non bloccano.
"""
from camperio_core.portfolio.validation.checks import Finding, Severity, ValidationResult
from camperio_core.portfolio.validation.gate import validate_report
