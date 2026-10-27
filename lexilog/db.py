"""SQLite access layer. Every function takes an open connection."""
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from .scheduler import CardState, due_date, schedule

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "lexilog.db"
POS_LABELS = {"NOUN": "noun", "VERB": "verb", "ADJ": "adjective", "ADV": "adverb",
              "EXPR": "expression", "PROPN": "name"}
SOURCE_TYPES = ["news", "web", "duolingo", "pdf", "podcast", "youtube", "class", "other"]
LANGUAGES = {"de": "German", "fr": "French"}


def lists_dir(db_path: str | Path = DEFAULT_DB) -> Path:
    """Folder for saved vocabulary lists (CSV), next to the database."""
    d = Path(db_path).parent / "lists"
    d.mkdir(parents=True, exist_ok=True)
    return d


def connect(path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    path = Path(path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript((Path(__file__).parent / "schema.sql").read_text(encoding="utf-8"))
    _migrate(conn)
    return conn


def _migrate(conn):
    """Add columns introduced after a database was first created."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(lexemes)")}
    if "verb_forms" not in cols:
        conn.execute("ALTER TABLE lexemes ADD COLUMN verb_forms TEXT")
        conn.commit()


# ---------- writing ----------

def get_or_create_lexeme(conn, language: str, lemma: str, **fields) -> tuple[int, bool]:
    """Return (lexeme_id, created). Fills empty fields on an existing lexeme."""
    lemma = lemma.strip()
    row = conn.execute("SELECT * FROM lexemes WHERE language=? AND lemma=?",
                       (language, lemma)).fetchone()
    fields = {k: v for k, v in fields.items() if v not in (None, "")}
    if row:
        updates = {k: v for k, v in fields.items() if not row[k]}
        if updates:
            cols = ", ".join(f"{k}=?" for k in updates)
            conn.execute(f"UPDATE lexemes SET {cols} WHERE id=?", (*updates.values(), row["id"]))
        return row["id"], False
    cols = ["language", "lemma", *fields]
    cur = conn.execute(
        f"INSERT INTO lexemes ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        (language, lemma, *fields.values()),
    )
    conn.execute("INSERT INTO cards (lexeme_id) VALUES (?)", (cur.lastrowid,))
    return cur.lastrowid, True


def add_encounter(conn, language: str, lemma: str, *, sentence: str = "", surface: str = "",
                  source_type: str = "other", source_title: str = "", url: str = "",
                  locator: str = "", seen_at: str | None = None, **lexeme_fields) -> tuple[int, bool]:
    """Record that you met `lemma` somewhere. Creates the lexeme and card if new."""
    lexeme_id, created = get_or_create_lexeme(conn, language, lemma, **lexeme_fields)
    conn.execute(
        """INSERT INTO encounters (lexeme_id, surface, sentence, source_type, source_title,
                                   url, locator, seen_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(?, date('now')))""",
        (lexeme_id, surface or lemma, sentence, source_type, source_title, url, locator, seen_at),
    )
    conn.commit()
    return lexeme_id, created


def has_encounter(conn, language: str, lemma: str, source_title: str, sentence: str) -> bool:
    """True if this word is already recorded with this source and sentence."""
    return conn.execute(
        """SELECT 1 FROM encounters e JOIN lexemes l ON l.id = e.lexeme_id
           WHERE l.language=? AND l.lemma=? AND e.source_title=? AND COALESCE(e.sentence,'')=?
           LIMIT 1""", (language, lemma.strip(), source_title or "", sentence or "")).fetchone() is not None


def record_review(conn, lexeme_id: int, rating: int, today: date | None = None) -> CardState:
    today = today or date.today()
    row = conn.execute("SELECT * FROM cards WHERE lexeme_id=?", (lexeme_id,)).fetchone()
    old = CardState(row["interval_days"], row["ease"], row["reps"], row["lapses"])
    new = schedule(old, rating)
    conn.execute(
        """UPDATE cards SET interval_days=?, ease=?, reps=?, lapses=?, due=?, last_review=?
           WHERE lexeme_id=?""",
        (new.interval_days, new.ease, new.reps, new.lapses,
         due_date(new, today).isoformat(), today.isoformat(), lexeme_id),
    )
    conn.execute(
        "INSERT INTO review_log (lexeme_id, rating, interval_days, reviewed_at) VALUES (?, ?, ?, ?)",
        (lexeme_id, rating, new.interval_days,
         datetime.combine(today, datetime.now().time()).isoformat(timespec="seconds")),
    )
    conn.commit()
    return new


def update_lexeme(conn, lexeme_id: int, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE lexemes SET {cols} WHERE id=?", (*fields.values(), lexeme_id))
    conn.commit()


def delete_lexeme(conn, lexeme_id: int):
    conn.execute("DELETE FROM lexemes WHERE id=?", (lexeme_id,))
    conn.commit()


def add_goal(conn, language: str, label: str, target: int, deadline: str, start_on: str | None = None):
    conn.execute(
        "INSERT INTO goals (language, label, target, deadline, start_on) "
        "VALUES (?, ?, ?, ?, COALESCE(?, date('now')))",
        (language, label, target, deadline, start_on),
    )
    conn.commit()


# ---------- reading ----------

def lexemes_df(conn) -> pd.DataFrame:
    return pd.read_sql_query(
        """SELECT l.*, c.due, c.interval_days, c.ease, c.reps, c.lapses, c.last_review,
                  COUNT(e.id) AS encounters,
                  GROUP_CONCAT(DISTINCT e.source_title) AS sources,
                  COUNT(DISTINCT e.source_type) AS source_types,
                  MIN(e.seen_at) AS first_seen, MAX(e.seen_at) AS last_seen
           FROM lexemes l
           JOIN cards c ON c.lexeme_id = l.id
           LEFT JOIN encounters e ON e.lexeme_id = l.id
           GROUP BY l.id ORDER BY l.created_at DESC""",
        conn,
    )


def encounters_df(conn) -> pd.DataFrame:
    return pd.read_sql_query(
        """SELECT e.*, l.language, l.lemma, l.kind FROM encounters e
           JOIN lexemes l ON l.id = e.lexeme_id ORDER BY e.seen_at DESC, e.id DESC""",
        conn,
    )


def reviews_df(conn) -> pd.DataFrame:
    return pd.read_sql_query(
        """SELECT r.*, l.language FROM review_log r JOIN lexemes l ON l.id = r.lexeme_id""", conn)


def goals_df(conn) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM goals ORDER BY deadline", conn)


def due_cards(conn, language: str | None = None, limit: int = 50, today: date | None = None):
    today = (today or date.today()).isoformat()
    sql = """SELECT l.*, c.due, c.reps, c.interval_days FROM cards c
             JOIN lexemes l ON l.id = c.lexeme_id WHERE c.due <= ?"""
    params: list = [today]
    if language:
        sql += " AND l.language = ?"
        params.append(language)
    sql += " ORDER BY c.reps > 0 DESC, c.due, RANDOM() LIMIT ?"  # reviews before new cards
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def contexts_for(conn, lexeme_id: int):
    return conn.execute(
        "SELECT * FROM encounters WHERE lexeme_id=? ORDER BY seen_at DESC", (lexeme_id,)
    ).fetchall()
