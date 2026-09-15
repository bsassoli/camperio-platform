"""Decodifica codice referente → nome, da un file JSON mantenuto a mano sulla VM.

I nomi dei referenti sono dati reali e nel repo non entrano. Il file vive in
<CAMPERIO_DATA>/promotori/nomi-referenti.json (in DEMO: fixtures/nomi-referenti.json) e si
rilegge a ogni richiesta, così una correzione si vede senza riavviare l'app. Ogni problema
(file assente, JSON rotto, voci non valide, codici scoperti) diventa un avviso leggibile in
pagina, e il menu ripiega sempre sul solo codice.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

GUIDA = "apps/promotori/README.md, sezione «File dei nomi dei referenti»"


@dataclass
class Nomi:
    percorso: Path
    stato: str                      # "ok", "mancante", "illeggibile", "formato"
    nomi: dict = field(default_factory=dict)
    avvisi: list = field(default_factory=list)

    def etichetta(self, codice):
        nome = self.nomi.get(codice)
        return f"{codice} — {nome}" if nome else codice


def _solo_codici(percorso, stato, motivo):
    return Nomi(percorso, stato, avvisi=[
        f"{motivo} Finché non viene sistemato, nel menu compaiono solo i codici dei referenti "
        f"(vedi {GUIDA})."])


def carica(percorso):
    percorso = Path(percorso)
    try:
        testo = percorso.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _solo_codici(percorso, "mancante",
                            f"File dei nomi dei referenti non trovato: {percorso}. "
                            "Va creato a mano sulla VM.")
    except UnicodeDecodeError:
        return _solo_codici(percorso, "illeggibile",
                            f"Il file dei nomi dei referenti ({percorso}) non è in UTF-8.")
    except OSError as e:
        return _solo_codici(percorso, "illeggibile",
                            f"Il file dei nomi dei referenti ({percorso}) non si può leggere: "
                            f"{e.strerror or e.__class__.__name__}. Controllare i permessi.")
    try:
        dati = json.loads(testo)
    except json.JSONDecodeError as e:
        return _solo_codici(percorso, "illeggibile",
                            f"Il file dei nomi dei referenti ({percorso}) non è JSON valido: "
                            f"{e.msg} alla riga {e.lineno}, colonna {e.colno}.")
    if not isinstance(dati, dict):
        return _solo_codici(percorso, "formato",
                            f"Il file dei nomi dei referenti ({percorso}) deve contenere un oggetto "
                            '{"CODICE": "Nome", ...}, non una lista o un valore singolo.')

    nomi, scartate = {}, []
    for chiave, valore in dati.items():
        if chiave.startswith("_"):          # "_nota", "_aggiornato": commenti di chi lo mantiene
            continue
        codice = chiave.strip()
        if codice and isinstance(valore, str) and valore.strip():
            nomi[codice] = valore.strip()
        else:
            scartate.append(chiave)
    avvisi = []
    if scartate:
        avvisi.append(f"Nel file dei nomi {_quanti(len(scartate), 'voce ignorata', 'voci ignorate')} "
                      f"perché il nome è vuoto o non è un testo: {', '.join(sorted(scartate))}.")
    return Nomi(percorso, "ok", nomi, avvisi)


def avvisi_copertura(nomi, codici):
    """Codici su Oracle senza nome nel file e voci del file senza referente su Oracle."""
    if nomi.stato != "ok":
        return []
    codici = set(codici)
    avvisi = []
    senza_nome = sorted(codici - set(nomi.nomi))
    if senza_nome:
        avvisi.append(f"{_quanti(len(senza_nome), 'referente su Oracle non ha', 'referenti su Oracle non hanno')} "
                      f"un nome nel file: {', '.join(senza_nome)}. Nel menu compaiono con il solo "
                      "codice: aggiungerli al file sulla VM.")
    orfani = sorted(set(nomi.nomi) - codici)
    if orfani:
        avvisi.append(f"{_quanti(len(orfani), 'voce del file non corrisponde', 'voci del file non corrispondono')} "
                      f"a nessun referente su Oracle: {', '.join(orfani)}. Codice sbagliato o "
                      "referente senza contratti: verificare.")
    return avvisi


def _quanti(n, singolare, plurale):
    return f"{n} {singolare if n == 1 else plurale}"
