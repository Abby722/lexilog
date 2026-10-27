"""Offline dictionary built from Wiktionary data (kaikki.org).

Build it once per language with scripts/build_dictionary.py. Lookups then run
locally, with no network and no API key. If no dictionary has been built,
the app simply leaves meanings blank.
"""
import json
import re
import sqlite3
from functools import lru_cache
from pathlib import Path

from .db import DEFAULT_DB

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    word TEXT NOT NULL, word_lc TEXT NOT NULL, pos TEXT,
    gender TEXT, plural TEXT, gloss TEXT
);
CREATE TABLE IF NOT EXISTS forms (form_lc TEXT NOT NULL, base TEXT NOT NULL);
"""
INDEXES = """
CREATE INDEX IF NOT EXISTS idx_entries_lc ON entries(word_lc);
CREATE INDEX IF NOT EXISTS idx_forms_lc ON forms(form_lc);
"""
POS_ORDER = {"noun": 0, "verb": 1, "adj": 2, "adv": 3}


def path_for(language: str, data_dir: Path | None = None) -> Path:
    return Path(data_dir or DEFAULT_DB.parent) / f"dictionary_{language}.sqlite"


# ---------- building from kaikki.org JSONL ----------

def parse_entry(entry: dict) -> tuple[dict | None, list[tuple[str, str]]]:
    """Turn one wiktextract entry into (dictionary row or None, [(form, base word)])."""
    word = entry.get("word", "")
    forms, glosses = [], []
    for s in entry.get("senses") or []:
        if s.get("form_of"):
            forms += [(word.lower(), f["word"]) for f in s["form_of"] if f.get("word")]
            continue
        g = (s.get("glosses") or [None])[-1]  # last item is the most specific gloss
        if g and g not in glosses:
            glosses.append(g)
    if not glosses:
        return None, forms

    gender = plural = None
    for ht in entry.get("head_templates") or []:
        exp = ht.get("expansion") or ""
        rest = exp[len(word):].strip() if exp.startswith(word) else ""
        first = rest.split(" ")[0].strip(",") if rest else ""
        if first in ("m", "f", "n"):
            gender = first
        m = re.search(r"plural ([^,)]+)", exp)
        if m:
            plural = m.group(1).strip()
        if gender or plural:
            break

    gloss = "; ".join(glosses[:3])
    if len(gloss) > 160:
        gloss = gloss[:157].rsplit(" ", 1)[0] + "…"
    return ({"word": word, "word_lc": word.lower(), "pos": entry.get("pos"),
             "gender": gender, "plural": plural, "gloss": gloss}, forms)


def build(jsonl_lines, out_path: Path) -> int:
    """Build a dictionary database from an iterable of JSON lines. Returns the entry count."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.unlink(missing_ok=True)
    conn = sqlite3.connect(out_path)
    conn.executescript(SCHEMA)
    n = 0
    for line in jsonl_lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        row, forms = parse_entry(entry)
        if row:
            conn.execute("INSERT INTO entries VALUES (:word,:word_lc,:pos,:gender,:plural,:gloss)", row)
            n += 1
        if forms:
            conn.executemany("INSERT INTO forms VALUES (?, ?)", forms)
    conn.executescript(INDEXES)
    conn.commit()
    conn.close()
    return n


# ---------- lookups ----------

class Dictionary:
    def __init__(self, path: Path):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def has(self, word: str) -> bool:
        return self.conn.execute("SELECT 1 FROM entries WHERE word_lc=? LIMIT 1",
                                 (word.lower(),)).fetchone() is not None

    def base_form(self, word: str) -> str | None:
        """For an inflected form ('angepasst'), return the dictionary word ('anpassen')."""
        r = self.conn.execute("SELECT base FROM forms WHERE form_lc=? LIMIT 1",
                              (word.lower(),)).fetchone()
        return r["base"] if r else None

    def lookup(self, word: str, prefer_pos: str | None = None) -> dict | None:
        rows = self.conn.execute("SELECT * FROM entries WHERE word_lc=?", (word.lower(),)).fetchall()
        if not rows:
            return None
        rows = sorted(rows, key=lambda r: (r["word"] != word, r["pos"] != prefer_pos,
                                           POS_ORDER.get(r["pos"], 9)))
        return dict(rows[0])


@lru_cache(maxsize=4)
def load(language: str, data_dir: str | None = None) -> "Dictionary | None":
    p = path_for(language, data_dir)
    return Dictionary(p) if p.exists() else None
