"""Client Oracle read-only con fallback DEMO (pattern da Comitato_App/data_layer.py).

LIVE se la Config ha ORA_USER/ORA_PWD/ORA_DSN e oracledb è installato; altrimenti
DEMO: query() serve fixture JSON SINTETICHE (mai dati reali di clienti nel repo).
Con config LIVE un Oracle irraggiungibile NON degrada mai a DEMO: solleva
OracleIndisponibileError, perché un job dichiara le sue fonti e se una manca FALLISCE
invece di pubblicare un report che sembra completo.
"""
import json
from pathlib import Path

from camperio_core import config as _config

FIXTURES = Path(__file__).parent / "fixtures"


class OracleIndisponibileError(RuntimeError):
    """Connessione Oracle richiesta dalla configurazione LIVE ma non riuscita."""


class OracleClient:
    def __init__(self, cfg=None, fixtures_dir=None):
        self._cfg = cfg or _config.from_env()
        self._fixtures = Path(fixtures_dir) if fixtures_dir else FIXTURES
        self._conn = None

    def mode(self):
        """Riporta la modalità CONFIGURATA (intento), non quella verificata.

        Con config LIVE, un Oracle irraggiungibile solleva OracleIndisponibileError
        al momento della query, invece di degradare silenziosamente a DEMO.
        """
        return self._cfg.mode

    def _connect(self):
        if self._conn is not None:
            return self._conn
        try:
            import oracledb
            self._conn = oracledb.connect(
                user=self._cfg.ora_user, password=self._cfg.ora_pwd, dsn=self._cfg.ora_dsn)
        except Exception as e:
            raise OracleIndisponibileError(
                "Connessione Oracle richiesta dalla configurazione LIVE ma non riuscita."
            ) from e
        return self._conn

    def query(self, sql, params=None, fixture=None):
        """SELECT su Oracle (LIVE) o contenuto della fixture (DEMO). Ritorna list[dict]."""
        if not self._cfg.live:
            if not fixture:
                raise ValueError(
                    "Modalità DEMO: indicare il nome della fixture per questa query.")
            path = self._fixtures / (fixture + ".json")
            if not path.exists():
                raise FileNotFoundError(f"Fixture DEMO mancante: {path}")
            return json.loads(path.read_text(encoding="utf-8"))
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute(sql, params or {})
            cols = [c[0] for c in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        finally:
            cur.close()
        return rows

    def close(self):
        """Chiude la connessione se aperta (idempotente)."""
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False
