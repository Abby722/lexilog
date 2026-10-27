"""Shared helpers for the Streamlit views."""
import os

import streamlit as st

from lexilog import db

LANG_COLORS = {"German": "#2E6B5E", "French": "#6B4C9A"}


def db_path():
    return os.environ.get("LEXILOG_DB", db.DEFAULT_DB)


@st.cache_resource
def get_conn():
    return db.connect(db_path())


def lang_name(code: str) -> str:
    return db.LANGUAGES.get(code, code)


def language_picker(key: str, include_all: bool = False, horizontal: bool = True):
    options = (["all"] if include_all else []) + list(db.LANGUAGES)
    fmt = lambda c: "Both" if c == "all" else db.LANGUAGES[c]
    choice = st.segmented_control("Language", options, format_func=fmt, key=key,
                                  default=options[0], label_visibility="collapsed")
    return None if choice in (None, "all") else choice


def highlight(sentence: str, surface: str) -> str:
    """Bold the captured form inside its sentence (case-insensitive, first match)."""
    if not sentence:
        return ""
    if surface:
        i = sentence.lower().find(surface.lower())
        if i >= 0:
            return f"{sentence[:i]}**{sentence[i:i + len(surface)]}**{sentence[i + len(surface):]}"
    return sentence
