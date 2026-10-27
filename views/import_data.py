import streamlit as st

from lexilog import db, importers
from views.common import get_conn

conn = get_conn()
st.title("Import")
st.markdown(
    "Bring in words in bulk from any CSV, TSV or Excel file: Language Reactor saved-word "
    "exports, highlights exported from a PDF reader, or a list you kept in a spreadsheet. "
    "Words you already have get a new context rather than a duplicate.")

file = st.file_uploader("File", type=["csv", "tsv", "txt", "xlsx"])
if not file:
    st.stop()

try:
    df = importers.read_table(file.getvalue(), file.name)
except Exception as exc:
    st.error(f"Couldn't read {file.name}: {exc}. Check that it is a CSV, TSV or Excel file.")
    st.stop()

st.dataframe(df.head(10), width="stretch")

guess = importers.guess_mapping(df.columns)
st.markdown("#### Match the columns")
cols = ["(none)"] + list(df.columns)
mapping = {}
labels = {"lemma": "Word or expression (required)", "sentence": "Sentence",
          "gloss": "Meaning", "source_title": "Title", "url": "Link",
          "locator": "Page or timestamp", "seen_at": "Date", "gender": "Gender (m/f/n)",
          "notes": "Word parts or notes", "tags": "Tags"}
grid = st.columns(3)
for i, (field, label) in enumerate(labels.items()):
    default = guess.get(field, "(none)")
    choice = grid[i % 3].selectbox(label, cols, index=cols.index(default), key=f"map_{field}")
    if choice != "(none)":
        mapping[field] = choice

c1, c2, c3, c4 = st.columns(4)
lang = c1.selectbox("Language", list(db.LANGUAGES), format_func=db.LANGUAGES.get)
source = c2.selectbox("Source", db.SOURCE_TYPES, index=db.SOURCE_TYPES.index("youtube"))
title = c3.text_input("Title for rows without one")
tags = c4.text_input("Tags for rows without any", placeholder="energy")

if st.button(f"Import {len(df)} rows", type="primary", disabled="lemma" not in mapping):
    res = importers.import_rows(conn, df, mapping, language=lang, source_type=source,
                                default_title=title, default_tags=tags)
    st.success(f"Imported: {res['new']} new, {res['repeat']} new contexts for existing words"
               + (f", {res['skipped']} empty rows skipped." if res["skipped"] else "."))
