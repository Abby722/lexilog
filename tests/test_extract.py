from pathlib import Path

import pytest

from lexilog import dictionary, extract

FIXTURE = Path(__file__).parent / "fixtures" / "kaikki_sample.jsonl"


def build_dict(tmp_path):
    with open(FIXTURE, encoding="utf-8") as f:
        n = dictionary.build(f, dictionary.path_for("de", tmp_path))
    dictionary.load.cache_clear()
    return n, dictionary.load("de", str(tmp_path))


def test_dictionary_build_and_lookup(tmp_path):
    n, d = build_dict(tmp_path)
    assert n == 5
    z = d.lookup("Zuschlag")
    assert z["gender"] == "m" and z["plural"] == "Zuschläge"
    assert z["gloss"].startswith("surcharge")
    assert d.lookup("Leistung")["gender"] == "f"
    assert d.base_form("angepasst") == "anpassen"
    assert d.lookup("nichtda") is None


def test_segments_keep_table_headings():
    pages = [(3, "Bundesgesetzliche Abgaben\nNetzzuschlag Rp./kWh 2.30 2.49\n\n"
                 "Die Abgaben werden jährlich angepasst. Der Bund legt\nsie fest.")]
    segs = extract.segment(pages)
    contexts = [s.context for s in segs]
    assert "Bundesgesetzliche Abgaben → Netzzuschlag Rp./kWh 2.30 2.49" in contexts
    assert any(c.endswith("Der Bund legt sie fest.") for c in contexts)
    assert all(s.page == 3 for s in segs)


def test_compound_parts_strip_linking_s():
    pytest.importorskip("compound_split")
    assert extract.split_parts("Übertragungsnetz") == ["Übertragung", "Netz"]
    assert extract.split_parts("Netz") == []


def test_candidates_use_dictionary_and_skip_known(tmp_path):
    pytest.importorskip("compound_split")
    build_dict(tmp_path)
    segs = extract.segment([(1, "Abgaben an Gemeinde\nNetzzuschlag Rp./kWh 2.30\n"
                                "Zuschlag Übertragungsnetz Rp./kWh 0.05")])
    cands = extract.candidates(segs, "de", known={"die Gemeinde"}, data_dir=str(tmp_path))
    by = {c.lemma: c for c in cands}
    assert "Gemeinde" not in by                      # already known
    assert by["Zuschlag"].gender == "m"
    assert "surcharge" in by["Zuschlag"].gloss
    assert by["Netzzuschlag"].parts.startswith("Netz (net)")
    assert by["Netzzuschlag"].best_context()[0].startswith("Abgaben an Gemeinde →")
