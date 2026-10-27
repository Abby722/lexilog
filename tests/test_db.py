from datetime import date

import pandas as pd

from lexilog import db, importers, stats


def conn():
    return db.connect(":memory:")


def test_repeat_encounter_groups_under_one_lexeme():
    c = conn()
    a, new_a = db.add_encounter(c, "de", "abschließen", sentence="Wir schließen ab.", source_type="news")
    b, new_b = db.add_encounter(c, "de", "abschließen", sentence="Er schließt die Tür ab.", source_type="podcast")
    assert a == b and new_a and not new_b
    lex = db.lexemes_df(c)
    assert lex.iloc[0].encounters == 2 and lex.iloc[0].source_types == 2


def test_later_encounter_fills_missing_gloss_only():
    c = conn()
    db.add_encounter(c, "fr", "en revanche", gloss="")
    db.add_encounter(c, "fr", "en revanche", gloss="on the other hand")
    db.add_encounter(c, "fr", "en revanche", gloss="something else")
    assert db.lexemes_df(c).iloc[0].gloss == "on the other hand"


def test_new_cards_are_due_and_reviews_move_them():
    c = conn()
    lid, _ = db.add_encounter(c, "de", "Haushalt")
    assert len(db.due_cards(c, "de")) == 1
    db.record_review(c, lid, 3, today=date.today())
    assert len(db.due_cards(c, "de")) == 0


def test_import_maps_columns_and_counts():
    c = conn()
    df = pd.DataFrame({"Word": ["la grève", "la grève", ""], "Context": ["x", "y", "z"],
                       "Translation": ["strike", "", ""]})
    m = importers.guess_mapping(df.columns)
    assert m == {"lemma": "Word", "sentence": "Context", "gloss": "Translation"}
    res = importers.import_rows(c, df, m, language="fr", source_type="youtube")
    assert res == {"new": 1, "repeat": 1, "skipped": 1}


def test_goal_progress_pace():
    c = conn()
    db.add_goal(c, "de", "B1", 100, "2026-03-01", start_on="2026-01-01")
    lex = stats.with_status(db.lexemes_df(c))
    p = stats.goal_progress(db.goals_df(c).iloc[0], lex, today=date(2026, 1, 31))
    assert p["known"] == 0 and not p["on_track"] and p["expected_now"] == 51


def test_has_encounter_detects_same_source_and_sentence():
    c = conn()
    db.add_encounter(c, "de", "Netz", sentence="Netz Industrie", source_title="Tarif A")
    assert db.has_encounter(c, "de", "Netz", "Tarif A", "Netz Industrie")
    assert not db.has_encounter(c, "de", "Netz", "Tarif B", "Netz Industrie")


def test_migration_adds_verb_forms_to_old_databases(tmp_path):
    import sqlite3
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE lexemes (id INTEGER PRIMARY KEY, language TEXT, lemma TEXT, "
                "kind TEXT DEFAULT 'word', pos TEXT, gender TEXT, plural TEXT, gloss TEXT, "
                "notes TEXT, tags TEXT, created_at TEXT DEFAULT (datetime('now')))")
    old.commit(); old.close()
    c = db.connect(path)
    assert "verb_forms" in {r[1] for r in c.execute("PRAGMA table_info(lexemes)")}
