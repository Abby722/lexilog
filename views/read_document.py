import hashlib
import re
from datetime import date

import pandas as pd
import streamlit as st

from lexilog import db, dictionary, extract, nlp
from views.common import db_path, get_conn

conn = get_conn()
LISTS = db.lists_dir(db_path())
CSV_COLUMNS = ["word", "gender", "translation", "parts", "context", "page", "count",
               "title", "tags"]

st.title("Read a document")
st.markdown("Drop in a PDF, a screenshot or a text file. The app lists the words in it "
            "that you don't have yet, with a meaning, word parts and the place each one "
            "appears. Tick the ones worth learning and save.")

c1, c2 = st.columns([3, 1])
file = c1.file_uploader("Document", type=["pdf", "png", "jpg", "jpeg", "txt"],
                        label_visibility="collapsed")
lang = c2.segmented_control("Language", list(db.LANGUAGES), format_func=db.LANGUAGES.get,
                            key="doc_lang", default="de") or "de"

missing = []
if not nlp.available(lang):
    missing.append("the spaCy model (dictionary forms)")
if dictionary.load(lang, str(LISTS.parent)) is None:
    missing.append("the offline dictionary (meanings and gender)")
if missing:
    st.caption("Working without " + " and ".join(missing) + ". See the README to add them.")


@st.cache_data(show_spinner="Reading the document…")
def analyse(data: bytes, name: str, language: str, known: frozenset, data_dir: str):
    pages = extract.pages_from_file(data, name, language)
    segs = extract.segment(pages)
    cands = extract.candidates(segs, language, known=known, data_dir=data_dir)
    rows = []
    for c in cands:
        ctx, page = c.best_context()
        rows.append({"add": False, "word": c.lemma, "gender": c.gender or "",
                     "translation": c.gloss, "parts": c.parts, "context": ctx,
                     "page": page, "count": c.count, "pos": c.pos or ""})
    words = sum(len(s.text.split()) for s in segs)
    return pd.DataFrame(rows), words


if not file:
    saved = sorted(LISTS.glob("*.csv"), reverse=True)
    if saved:
        st.markdown("#### Saved lists")
        for f in saved[:30]:
            a, b = st.columns([4, 1])
            a.markdown(f"`{f.name}` · {sum(1 for _ in open(f, encoding='utf-8')) - 1} words")
            b.download_button("Download", f.read_bytes(), file_name=f.name, mime="text/csv",
                              key=f"dl_{f.name}")
    st.stop()

data = file.getvalue()
known = frozenset(r["lemma"] for r in conn.execute(
    "SELECT lemma FROM lexemes WHERE language=?", (lang,)))
try:
    df, n_words = analyse(data, file.name, lang, known, str(LISTS.parent))
except (ValueError, RuntimeError) as exc:
    st.error(str(exc))
    st.stop()

if df.empty:
    st.warning("No new words found. If this is a scanned PDF, save a page as an image "
               "and drop that in instead, so the app can read it with OCR.")
    st.stop()

c1, c2, c3 = st.columns(3)
title = c1.text_input("Title", value=re.sub(r"\.[^.]+$", "", file.name))
tags = c2.text_input("Tags", placeholder="energy, report")
source = c3.selectbox("Source", db.SOURCE_TYPES, index=db.SOURCE_TYPES.index("pdf"))

f1, f2, f3 = st.columns([1, 1, 2])
min_count = f1.number_input("Appears at least", 1, 50, 1, help="times in the document")
only_dict = f2.toggle("Only words with a meaning", value=False)
q = f3.text_input("Filter", placeholder="search words", label_visibility="collapsed")
view = df[df["count"] >= min_count]
if only_dict:
    view = view[view.translation != ""]
if q:
    view = view[view.word.str.contains(q, case=False)]

st.caption(f"{len(df)} new words in about {n_words:,} words of text. Words already in "
           f"your list are left out. Showing {len(view)}.")

edited = st.data_editor(
    view.drop(columns=["pos"]), hide_index=True, width="stretch", height=480,
    key=f"doc_editor_{hashlib.md5(data).hexdigest()[:8]}_{min_count}_{only_dict}_{q}",
    disabled=["count", "page", "context"],
    column_config={
        "add": st.column_config.CheckboxColumn("Add", width="small"),
        "word": st.column_config.TextColumn("Word", help="Edit if the dictionary form is wrong"),
        "gender": st.column_config.SelectboxColumn("Gender", options=["", "m", "f", "n"],
                                                   width="small"),
        "translation": st.column_config.TextColumn("Meaning", width="medium"),
        "parts": st.column_config.TextColumn("Word parts", width="medium"),
        "context": st.column_config.TextColumn("Where it appears", width="large"),
        "count": st.column_config.NumberColumn("Times", width="small"),
        "page": st.column_config.NumberColumn("Page", width="small"),
    })

chosen = edited[edited["add"]]
stem = f"{date.today().isoformat()}_{re.sub(r'[^A-Za-z0-9ÄÖÜäöüß]+', '-', title).strip('-')[:40]}"


def to_csv(frame: pd.DataFrame) -> bytes:
    out = frame.assign(title=title, tags=tags)
    return out[CSV_COLUMNS].to_csv(index=False).encode("utf-8")


b1, b2, b3 = st.columns(3)
if b1.button(f"Add {len(chosen)} words and save the list", type="primary",
             disabled=chosen.empty):
    new = 0
    for r in chosen.itertuples():
        _, created = db.add_encounter(
            conn, lang, r.word, sentence=r.context, surface=r.word, source_type=source,
            source_title=title, locator=f"p. {r.page}" if pd.notna(r.page) else "",
            gloss=r.translation, gender=r.gender or None, notes=r.parts, tags=tags,
            kind="expression" if " " in r.word else "word")
        new += created
    path = LISTS / f"{stem}.csv"
    path.write_bytes(to_csv(chosen))
    st.cache_data.clear()
    st.success(f"Added {new} new words ({len(chosen) - new} were already there). "
               f"List saved as {path.name}.")
if b2.button("Save the full list without adding"):
    path = LISTS / f"{stem}_all.csv"
    path.write_bytes(to_csv(edited))
    st.success(f"Saved {len(edited)} words as {path.name}.")
b3.download_button("Download this list", to_csv(edited), file_name=f"{stem}.csv",
                   mime="text/csv")
