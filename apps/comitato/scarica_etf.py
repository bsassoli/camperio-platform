# -*- coding: utf-8 -*-
"""Scarica i 9 CSV holdings degli ETF benchmark da iShares nel Repository_Fondi.
Eseguito a mano o dall'attivita' pianificata (giovedì 11:00)."""
import os, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data_layer as DL

res = DL.download_etf()
ok = sum(1 for r in res if r.get("ok"))
riga = (datetime.datetime.now().isoformat(timespec="seconds") + " | scaricati " + str(ok) + "/" + str(len(res)) +
        " | " + "; ".join(r["ticker"] + ":" + ("OK" if r.get("ok") else str(r.get("msg", "KO"))) for r in res))
with open(os.path.join(DL.REPO, "_download_etf.log"), "a", encoding="utf-8") as f:
    f.write(riga + "\n")
print("ETF scaricati:", ok, "/", len(res))
for r in res:
    print("  ", r["ticker"], "->", "OK" if r.get("ok") else r.get("msg"))
