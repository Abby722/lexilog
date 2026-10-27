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
    assert n == 13
    z = d.lookup("Zuschlag")
    assert z["gender"] == "m" and z["plural"] == "Zuschläge"
    assert z["gloss"].startswith("surcharge")
    assert d.lookup("Leistung")["gender"] == "f"
    assert d.base_form("angepasst") == "anpassen"
    assert d.lookup("nichtda") is None
    assert d.lookup("Kosten")["gender"] is None             # "pl" is not a gender


def test_verb_forms_and_irregularity(tmp_path):
    _, d = build_dict(tmp_path)
    g = d.lookup("gehen")
    assert g["verb_forms"] == "er geht · ging · ist gegangen"
    assert g["irregular"] == 1
    assert d.lookup("anpassen")["irregular"] == 0
    assert d.lookup("anpassen")["verb_forms"] == "er passt an"   # only what the entry gives


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
    assert by["Gemeinde"].known and not by["Zuschlag"].known
    assert by["Zuschlag"].gender == "m"
    assert "surcharge" in by["Zuschlag"].gloss
    assert by["Netzzuschlag"].parts.startswith("Netz (net)")
    assert by["Netzzuschlag"].best_context()[0].startswith("Abgaben an Gemeinde →")


def test_compounds_take_gender_and_plural_from_their_last_part(tmp_path):
    pytest.importorskip("compound_split")
    build_dict(tmp_path)
    segs = extract.segment([(1, "Bundesgesetzliche Abgaben\nNetzzuschlag Rp./kWh 2.30\n"
                                "Stromreserve Rp./kWh 0.41\nZuschlag Übertragungsnetz Rp./kWh 0.05\n"
                                "Die Messkosten sind enthalten.")])
    by = {c.lemma: c for c in extract.candidates(segs, "de", data_dir=str(tmp_path))}
    nz = by["Netzzuschlag"]
    assert (nz.gender, nz.plural) == ("m", "Netzzuschläge")
    assert nz.gloss == "≈ net + surcharge"
    assert by["Stromreserve"].gender == "f" and by["Stromreserve"].plural == "Stromreserven"
    assert by["Übertragungsnetz"].gender == "n"
    assert "Messkosten" in by                                    # not "Messkost"
    assert by["bundesgesetzlich"].parts.startswith("Bund (federation)")
