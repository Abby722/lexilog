"""Batch imports: CSV exports (Language Reactor, PDF highlight exports, spreadsheets)."""
import io

import pandas as pd

from .db import POS_LABELS, add_encounter

_POS_CODES = {**{v: k for k, v in POS_LABELS.items()}, "adj": "ADJ", "adv": "ADV"}


def pos_code(value: str) -> str | None:
    """Accept 'noun', 'Noun' or 'NOUN' and store spaCy's code."""
    v = (value or "").strip()
    return _POS_CODES.get(v.lower()) or (v.upper() if v.upper() in POS_LABELS else None)

# Column names we recognise automatically, lower-cased.
ALIASES = {
    "lemma": ["lemma", "word", "term", "expression", "front", "highlight", "text"],
    "sentence": ["sentence", "context", "subtitle", "example", "quote"],
    "gloss": ["gloss", "translation", "meaning", "definition", "back", "note"],
    "source_title": ["source_title", "title", "book", "video", "article"],
    "url": ["url", "link"],
    "locator": ["locator", "page", "timestamp", "time", "location"],
    "seen_at": ["seen_at", "date", "created", "added"],
    "gender": ["gender", "genus"],
    "plural": ["plural"],
    "pos": ["pos", "part of speech", "word class"],
    "verb_forms": ["verb_forms", "verb forms", "forms"],
    "notes": ["notes", "parts", "word parts"],
    "tags": ["tags", "tag"],
}


def read_table(data: bytes, filename: str) -> pd.DataFrame:
    if filename.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(data))
    sep = "\t" if filename.lower().endswith((".tsv", ".txt")) else None
    return pd.read_csv(io.BytesIO(data), sep=sep, engine="python")


def guess_mapping(columns) -> dict:
    lower = {c.lower().strip(): c for c in columns}
    mapping = {}
    for field, names in ALIASES.items():
        for n in names:
            if n in lower and lower[n] not in mapping.values():
                mapping[field] = lower[n]
                break
    return mapping


def import_rows(conn, df: pd.DataFrame, mapping: dict, *, language: str,
                source_type: str, default_title: str = "", default_tags: str = "") -> dict:
    """Import rows. `mapping` maps our field names to the table's column names."""
    new, repeat, skipped = 0, 0, 0
    for _, row in df.iterrows():
        get = lambda f: (str(row[mapping[f]]).strip()
                         if f in mapping and pd.notna(row[mapping[f]]) else "")
        lemma = get("lemma")
        if not lemma:
            skipped += 1
            continue
        seen = get("seen_at")
        try:
            seen = pd.to_datetime(seen).date().isoformat() if seen else None
        except (ValueError, TypeError):
            seen = None
        _, created = add_encounter(
            conn, language, lemma,
            sentence=get("sentence"), source_type=source_type,
            source_title=get("source_title") or default_title,
            url=get("url"), locator=get("locator"), seen_at=seen,
            gloss=get("gloss"), gender=get("gender") if get("gender") in ("m", "f", "n") else None,
            notes=get("notes"), tags=get("tags") or default_tags,
            plural=get("plural"), pos=pos_code(get("pos")), verb_forms=get("verb_forms"),
            kind="expression" if len(lemma.split()) > 1 else "word",
        )
        new += created
        repeat += not created
    return {"new": new, "repeat": repeat, "skipped": skipped}
