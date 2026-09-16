"""Accesso ai dati del cruscotto: query Oracle in LIVE, fixture sintetiche in DEMO.

In DEMO le fixture contengono le righe di tutti i referenti sintetici (colonna REFCOM in
più) e qui si tengono solo quelle del referente chiesto. Per SRE e movimenti si emula
anche il filtro sulle date, così Dal e Al cambiano i numeri pure in DEMO. I fondi
Controlfida invece restano una fotografia fissa, qualunque sia la data Al.
"""
from pathlib import Path

from camperio_core.oracle.client import OracleClient
from promotori import query as Q

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _ultima_per_contratto(righe, entro=None):
    """Per ogni CODCLI la riga con il PERIODO più recente (non oltre `entro`, se dato)."""
    ultime = {}
    for r in righe:
        if entro is not None and r["PERIODO"] > entro:
            continue
        attuale = ultime.get(r["CODCLI"])
        if attuale is None or r["PERIODO"] > attuale["PERIODO"]:
            ultime[r["CODCLI"]] = r
    return ultime


class Sorgente:
    """Le query del cruscotto, una per metodo. Ritornano list[dict] con le colonne Oracle."""

    def __init__(self, client=None):
        self._client = client or OracleClient(fixtures_dir=FIXTURES)

    def mode(self):
        return self._client.mode()

    @property
    def live(self):
        return self.mode() == "LIVE"

    def _query(self, sql, params, fixture):
        righe = self._client.query(sql, params, fixture=fixture)
        if self.live or "ref" not in params:
            return righe
        return [{k: v for k, v in r.items() if k != "REFCOM"}
                for r in righe if r.get("REFCOM") == params["ref"]]

    def elenco_referenti(self):
        return self._query(Q.ELENCO_REFERENTI, {}, "promotori_referenti")

    def contratti(self, ref):
        return self._query(Q.CONTRATTI, {"ref": ref}, "promotori_contratti")

    def sre(self, ref):
        righe = self._query(Q.SRE, {"ref": ref}, "promotori_sre")
        if self.live:
            return righe
        ultime = _ultima_per_contratto(righe)
        return [r for r in righe
                if r["PERIODO"].endswith("-12-31") or r is ultime[r["CODCLI"]]]

    def sre_alla_data(self, ref, data):
        righe = self._query(Q.SRE_ALLA_DATA, {"ref": ref, "data": data}, "promotori_sre")
        if self.live:
            return righe
        return list(_ultima_per_contratto(righe, entro=data).values())

    def commissioni_per_contratto(self, ref):
        return self._query(Q.COMMISSIONI_PER_CONTRATTO, {"ref": ref},
                           "promotori_commissioni_contratto")

    def commissioni_per_trimestre(self, ref):
        return self._query(Q.COMMISSIONI_PER_TRIMESTRE, {"ref": ref},
                           "promotori_commissioni_trimestre")

    def commissioni_per_tipo(self, ref):
        return self._query(Q.COMMISSIONI_PER_TIPO, {"ref": ref}, "promotori_commissioni_tipo")

    def operazioni(self, ref):
        return self._query(Q.OPERAZIONI, {"ref": ref}, "promotori_operazioni")

    def fondi(self, ref, al):
        return self._query(Q.FONDI, {"ref": ref, "al": al}, "promotori_fondi")

    def fondi_totale(self, ref, al):
        return self._query(Q.FONDI_TOTALE, {"ref": ref, "al": al}, "promotori_fondi_totale")

    def flussi_reali(self, ref, dal, al):
        righe = self._query(Q.FLUSSI_REALI, {"ref": ref, "dal": dal, "al": al},
                            "promotori_movimenti")
        if self.live:
            return righe
        per_contratto = {}
        for r in righe:
            if dal <= r["DATVAL"] <= al:
                per_contratto[r["CODCLI"]] = per_contratto.get(r["CODCLI"], 0) + r["FLUSSO"]
        return [{"CODCLI": c, "FLUSSO": round(v, 2)} for c, v in per_contratto.items()]
