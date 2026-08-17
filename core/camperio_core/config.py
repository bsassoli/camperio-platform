"""Configurazione di piattaforma: l'unico punto che legge l'ambiente (spec §7).

Il codice legge SOLO variabili d'ambiente. L'assenza delle ORA_* = modalità DEMO:
è un contratto di piattaforma — si sviluppa senza Oracle e i test girano ovunque.
"""
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    ora_user: str | None
    ora_pwd: str | None
    ora_dsn: str | None
    data_dir: Path

    @property
    def live(self) -> bool:
        return bool(self.ora_user and self.ora_pwd and self.ora_dsn)

    @property
    def mode(self) -> str:
        return "LIVE" if self.live else "DEMO"


def from_env(env=os.environ) -> Config:
    return Config(
        ora_user=env.get("ORA_USER"),
        ora_pwd=env.get("ORA_PWD"),
        ora_dsn=env.get("ORA_DSN"),
        data_dir=Path(env.get("CAMPERIO_DATA", "/var/lib/camperio")),
    )
