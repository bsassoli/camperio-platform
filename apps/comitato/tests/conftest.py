"""Ambiente di test dell'app: DEMO forzato e matplotlib senza display."""
import os

os.environ.setdefault("MPLBACKEND", "Agg")
for _k in ("ORA_USER", "ORA_PWD", "ORA_DSN"):
    os.environ.pop(_k, None)
