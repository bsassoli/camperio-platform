"""File dei nomi dei referenti: ripiego sul codice e avvisi chiari per chi lo mantiene."""
from promotori import nomi as N


def test_file_mancante_solo_codici_e_avviso(tmp_path):
    percorso = tmp_path / "nomi-referenti.json"
    nomi = N.carica(percorso)
    assert nomi.stato == "mancante"
    assert nomi.etichetta("A1") == "A1"
    assert len(nomi.avvisi) == 1
    assert "non trovato" in nomi.avvisi[0] and str(percorso) in nomi.avvisi[0]
    assert "README" in nomi.avvisi[0]
    assert N.avvisi_copertura(nomi, ["A1"]) == []      # niente elenco di "senza nome" se il file manca


def test_json_non_valido_indica_riga_e_colonna(tmp_path):
    percorso = tmp_path / "nomi.json"
    percorso.write_text('{\n  "A1": "Uno",\n  "A2": \n}', encoding="utf-8")
    nomi = N.carica(percorso)
    assert nomi.stato == "illeggibile"
    assert "riga 4" in nomi.avvisi[0]
    assert nomi.etichetta("A1") == "A1"


def test_file_non_utf8(tmp_path):
    percorso = tmp_path / "nomi.json"
    percorso.write_bytes(b'{"A1": "Nicol\xf2"}')
    nomi = N.carica(percorso)
    assert nomi.stato == "illeggibile" and "UTF-8" in nomi.avvisi[0]


def test_formato_lista_rifiutato(tmp_path):
    percorso = tmp_path / "nomi.json"
    percorso.write_text('[["A1", "Uno"]]', encoding="utf-8")
    nomi = N.carica(percorso)
    assert nomi.stato == "formato" and "oggetto" in nomi.avvisi[0]


def test_voci_valide_commenti_e_voci_scartate(tmp_path):
    percorso = tmp_path / "nomi.json"
    percorso.write_text('{"_aggiornato": "2026-09-15", "A1": " Uno ", " A2 ": "Due", '
                        '"A3": "", "A4": 42}', encoding="utf-8")
    nomi = N.carica(percorso)
    assert nomi.stato == "ok"
    assert nomi.nomi == {"A1": "Uno", "A2": "Due"}
    assert nomi.etichetta("A1") == "A1 — Uno"
    assert nomi.etichetta("A9") == "A9"
    assert len(nomi.avvisi) == 1 and "2 voci ignorate" in nomi.avvisi[0] and "A3, A4" in nomi.avvisi[0]


def test_copertura_codici_senza_nome_e_voci_orfane(tmp_path):
    percorso = tmp_path / "nomi.json"
    percorso.write_text('{"A1": "Uno", "VECCHIO": "Non più su Oracle"}', encoding="utf-8")
    avvisi = N.avvisi_copertura(N.carica(percorso), ["A1", "A2", "A3"])
    assert len(avvisi) == 2
    assert avvisi[0].startswith("2 referenti su Oracle non hanno un nome") and "A2, A3" in avvisi[0]
    assert avvisi[1].startswith("1 voce del file non corrisponde") and "VECCHIO" in avvisi[1]
