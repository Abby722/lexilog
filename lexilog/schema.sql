-- One row per word or expression you are learning (the "lexeme").
CREATE TABLE IF NOT EXISTS lexemes (
    id          INTEGER PRIMARY KEY,
    language    TEXT NOT NULL CHECK (language IN ('de', 'fr')),
    lemma       TEXT NOT NULL,               -- dictionary form: "abschließen", "avoir beau"
    kind        TEXT NOT NULL DEFAULT 'word' CHECK (kind IN ('word', 'expression')),
    pos         TEXT,                        -- NOUN, VERB, ADJ ...
    gender      TEXT,                        -- m / f / n
    plural      TEXT,
    gloss       TEXT,                        -- meaning in your own words
    notes       TEXT,
    tags        TEXT,                        -- comma separated, e.g. "B1,politics"
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (language, lemma)
);

-- One row each time you meet a lexeme somewhere. This is the heart of the system.
CREATE TABLE IF NOT EXISTS encounters (
    id           INTEGER PRIMARY KEY,
    lexeme_id    INTEGER NOT NULL REFERENCES lexemes(id) ON DELETE CASCADE,
    surface      TEXT,                       -- the form as it appeared: "schließt ... ab"
    sentence     TEXT,                       -- the full context sentence
    source_type  TEXT NOT NULL,              -- news, duolingo, pdf, podcast, youtube, web, other
    source_title TEXT,                       -- "DW Nachrichten", book title, video title
    url          TEXT,
    locator      TEXT,                       -- page number, timestamp, chapter
    seen_at      TEXT NOT NULL DEFAULT (date('now'))
);

-- Spaced-repetition state, one card per lexeme.
CREATE TABLE IF NOT EXISTS cards (
    lexeme_id     INTEGER PRIMARY KEY REFERENCES lexemes(id) ON DELETE CASCADE,
    due           TEXT NOT NULL DEFAULT (date('now')),
    interval_days REAL NOT NULL DEFAULT 0,
    ease          REAL NOT NULL DEFAULT 2.5,
    reps          INTEGER NOT NULL DEFAULT 0,
    lapses        INTEGER NOT NULL DEFAULT 0,
    last_review   TEXT
);

-- Every review, kept for retention statistics.
CREATE TABLE IF NOT EXISTS review_log (
    id            INTEGER PRIMARY KEY,
    lexeme_id     INTEGER NOT NULL REFERENCES lexemes(id) ON DELETE CASCADE,
    reviewed_at   TEXT NOT NULL DEFAULT (datetime('now')),
    rating        INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 4),  -- 1 again, 2 hard, 3 good, 4 easy
    interval_days REAL NOT NULL
);

-- Goals with a deadline, e.g. "600 German words known before the B1 exam".
CREATE TABLE IF NOT EXISTS goals (
    id        INTEGER PRIMARY KEY,
    language  TEXT NOT NULL,
    label     TEXT NOT NULL,
    target    INTEGER NOT NULL,
    start_on  TEXT NOT NULL DEFAULT (date('now')),
    deadline  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_enc_lexeme ON encounters(lexeme_id);
CREATE INDEX IF NOT EXISTS idx_cards_due ON cards(due);
