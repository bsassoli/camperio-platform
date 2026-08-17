"""Client Oracle read-only con fallback DEMO (pattern da Comitato_App/data_layer.py).

LIVE se la Config ha ORA_USER/ORA_PWD/ORA_DSN e oracledb è installato; altrimenti
DEMO: query() serve fixture JSON SINTETICHE (mai dati reali di clienti nel repo).
"""
import json
from pathlib import Path

from camperio_core import config as _config

FIXTURES = Path(__file__).parent / "fixtures"


class OracleClient:
    def __init__(self, cfg=None, fixtures_dir=None):
        self._cfg = cfg or _config.from_env()
        self._fixtures = Path(fixtures_dir) if fixtures_dir else FIXTURES
        self._conn = None

    def mode(self):
        return "LIVE" if self._connect() else "DEMO"

    def _connect(self):
        if self._conn is not None:
            return self._conn
        if not self._cfg.live:
            return None
        try:
            import oracledb
            self._conn = oracledb.connect(
                user=self._cfg.ora_user, password=self._cfg.ora_pwd, dsn=self._cfg.ora_dsn)
        except Exception as e:
            print("[camperio_core.oracle] connessione fallita, resto in DEMO:", e)
            return None
        return self._conn

    def query(self, sql, params=None, fixture=None):
        """SELECT su Oracle (LIVE) o contenuto della fixture (DEMO). Ritorna list[dict]."""
        conn = self._connect()
        if conn is None:
            if not fixture:
                raise ValueError(
                    "Modalità DEMO: indicare il nome della fixture per questa query.")
            path = self._fixtures / (fixture + ".json")
            if not path.exists():
                raise FileNotFoundError(f"Fixture DEMO mancante: {path}")
            return json.loads(path.read_text(encoding="utf-8"))
        cur = conn.cursor()
        cur.execute(sql, params or {})
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
        return rows
