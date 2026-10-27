import hashlib
import re
from datetime import date

import pandas as pd
import streamlit as st

from lexilog import db, dictionary, extract, nlp
from views.common import db_path, get_conn

conn = get_conn()
LISTS = db.lists_dir(db_path())
DATA_DIR = str(LISTS.parent)
CSV_COLUMNS = ["word", "pos", "gender", "plural", "translation", "verb_forms", "irregular",
               "parts", "context", "page", "count", "title", "tags"]

st.title("Read a document")
st.markdown("Drop in a PDF, a screenshot or a text file. The app lists the words in it "
            "with meaning, grammar, word parts and the place each one appears. Tick the "
            "ones worth learning and save.")

c1, c2 = st.columns([3, 1])
file = c1.file_uploader("Document", type=["pdf", "png", "jpg", "jpeg", "txt"],
                        label_visibility="collapsed")
lang = c2.segmented_control("Language", list(db.LANGUAGES), format_func=db.LANGUAGES.get,
                            key="doc_lang", default="de") or "de"

d = dictionary.load(lang, DATA_DIR)
notes = []
if not nlp.available(lang):
    notes.append("Working without the spaCy model, so dictionary forms are rough.")
if d is None:
    notes.append("Working without the offline dictionary, so meanings stay blank.")
elif not d.has_verb_forms:
    notes.append("Rebuild the dictionary (see README) to get verb forms.")
for n in notes:
    st.caption(n + " See the README to add it.")


@st.cache_data(show_spinner="Reading the document…")
def analyse(data: bytes, name: str, language: str, known: frozenset, data_dir: str):
    pages = extract.pages_from_file(data, name, language)
    segs = extract.segment(pages)
    cands = extract.candidates(segs, language, known=known, data_dir=data_dir)
    rows = []
    for c in cands:
        ctx, page = c.best_context()
        rows.append({"add": False, "word": c.lemma,
                     "pos": db.POS_LABELS.get(c.pos, c.pos or ""),
                     "gender": c.gender or "", "plural": c.plural or "",
                     "translation": c.gloss, "verb_forms": c.verb_forms,
                     "irregular": {True: "irregular", False: "regular"}.get(c.irregular, ""),
                     "parts": c.parts, "context": ctx, "page": page, "count": c.count,
                     "known": c.known, "pos_code": c.pos or ""})
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
    df, n_words = analyse(data, file.name, lang, known, DATA_DIR)
except (ValueError, RuntimeError) as exc:
    st.error(str(exc))
    st.stop()

if df.empty:
    st.warning("No words found. If this is a scanned PDF, save a page as an image "
               "and drop that in instead, so the app can read it with OCR.")
    st.stop()

c1, c2, c3 = st.columns(3)
title = c1.text_input("Title", value=re.sub(r"\.[^.]+$", "", file.name))
tags = c2.text_input("Tags", placeholder="energy, report")
source = c3.selectbox("Source", db.SOURCE_TYPES, index=db.SOURCE_TYPES.index("pdf"))

f1, f2, f3, f4 = st.columns([1, 1, 1, 2])
min_count = f1.number_input("Appears at least", 1, 50, 1, help="times in the document")
pos_filter = f2.multiselect("Part of speech", ["noun", "verb", "adjective", "adverb"],
                            placeholder="All")
show_known = f3.toggle("Include words I have", value=False)
q = f4.text_input("Filter", placeholder="search words", label_visibility="collapsed")

view = df[df["count"] >= min_count]
if not show_known:
    view = view[~view.known]
if pos_filter:
    view = view[view.pos.isin(pos_filter)]
if q:
    view = view[view.word.str.contains(q, case=False)]

n_new, n_known = int((~df.known).sum()), int(df.known.sum())
st.caption(f"{n_new} new words and {n_known} you already have, in about {n_words:,} words "
           f"of text. Showing {len(view)}.")

edited = st.data_editor(
    view.drop(columns=["pos_code"]), hide_index=True, width="stretch", height=480,
    key=f"doc_editor_{hashlib.md5(data).hexdigest()[:8]}_{min_count}_{show_known}_{pos_filter}_{q}",
    disabled=["count", "page", "context", "known", "irregular"],
    column_config={
        "add": st.column_config.CheckboxColumn("Add", width="small"),
        "word": st.column_config.TextColumn("Word", help="Edit if the dictionary form is wrong"),
        "pos": st.column_config.SelectboxColumn(
            "Type", options=["noun", "verb", "adjective", "adverb", "expression"], width="small"),
        "gender": st.column_config.TextColumn("Gender", width="small", validate=r"^[mfn]?$",
                                              help="m, f or n"),
        "plural": "Plural",
        "translation": st.column_config.TextColumn(
            "Meaning", width="medium",
            help="≈ means the meaning was put together from the word's parts"),
        "verb_forms": st.column_config.TextColumn("Verb forms", width="medium"),
        "irregular": st.column_config.TextColumn("Verb type", width="small"),
        "parts": st.column_config.TextColumn("Word parts", width="medium"),
        "context": st.column_config.TextColumn("Where it appears", width="large"),
        "count": st.column_config.NumberColumn("Times", width="small"),
        "page": st.column_config.NumberColumn("Page", width="small"),
        "known": st.column_config.CheckboxColumn("Have it", width="small"),
    })

chosen = edited[edited["add"] & ~edited["known"]]
stem = f"{date.today().isoformat()}_{re.sub(r'[^A-Za-z0-9ÄÖÜäöüß]+', '-', title).strip('-')[:40]}"
pos_codes = {v: k for k, v in db.POS_LABELS.items()}


def to_csv(frame: pd.DataFrame) -> bytes:
    out = frame.assign(title=title, tags=tags)
    return out[CSV_COLUMNS].to_csv(index=False).encode("utf-8")


def log(row, *, with_details: bool):
    """Record this document as a place where the word appeared (once per sentence)."""
    if db.has_encounter(conn, lang, row.word, title, row.context):
        return None, False
    details = {}
    if with_details:
        details = dict(gloss=row.translation, gender=row.gender or None,
                       plural=row.plural or None, verb_forms=row.verb_forms or None,
                       notes=row.parts, tags=tags, pos=pos_codes.get(row.pos),
                       kind="expression" if " " in row.word or row.pos == "expression"
                       else "word")
    return db.add_encounter(
        conn, lang, row.word, sentence=row.context, surface=row.word, source_type=source,
        source_title=title, locator=f"p. {int(row.page)}" if pd.notna(row.page) else "",
        **details)


also_known = st.checkbox(
    f"Also note this document under the {n_known} words I already have", value=True,
    help="Adds this document to the places where those words appeared. "
         "No duplicates are created.", disabled=n_known == 0)

b1, b2, b3 = st.columns(3)
if b1.button(f"Add {len(chosen)} words and save the list", type="primary",
             disabled=chosen.empty and not (also_known and n_known)):
    new = sum(log(r, with_details=True)[1] for r in chosen.itertuples())
    linked = 0
    if also_known:
        for r in df[df.known].itertuples():
            linked += log(r, with_details=False)[0] is not None
    if not chosen.empty:
        path = LISTS / f"{stem}.csv"
        path.write_bytes(to_csv(chosen))
    st.cache_data.clear()
    st.success(f"Added {new} new words"
               + (f" and saved the list as {path.name}" if not chosen.empty else "")
               + (f". Noted this document under {linked} words you already had." if linked else "."))
if b2.button("Save the full list without adding"):
    path = LISTS / f"{stem}_all.csv"
    path.write_bytes(to_csv(edited))
    st.success(f"Saved {len(edited)} words as {path.name}.")
b3.download_button("Download this list", to_csv(edited), file_name=f"{stem}.csv",
                   mime="text/csv")
