import streamlit as st

from lexilog import db, stats
from views.common import get_conn, highlight, lang_name, language_picker

conn = get_conn()
st.title("Word list")

lang = language_picker("browse_lang", include_all=True)
lex = stats.with_status(db.lexemes_df(conn))
if lang:
    lex = lex[lex.language == lang]

c1, c2, c3 = st.columns([2, 1, 1])
q = c1.text_input("Search", placeholder="word, meaning or tag", label_visibility="collapsed")
status = c2.multiselect("Status", ["new", "learning", "known"], placeholder="Any status",
                        label_visibility="collapsed")
kind = c3.multiselect("Type", ["word", "expression"], placeholder="Words and expressions",
                      label_visibility="collapsed")
if q:
    m = (lex.lemma.str.contains(q, case=False, na=False)
         | lex.gloss.str.contains(q, case=False, na=False)
         | lex.tags.str.contains(q, case=False, na=False))
    lex = lex[m]
if status:
    lex = lex[lex.status.isin(status)]
if kind:
    lex = lex[lex.kind.isin(kind)]

st.caption(f"{len(lex)} entries")
view = lex.assign(Language=lex.language.map(lang_name),
                  type=lex.pos.map(lambda p: db.POS_LABELS.get(p, p) if p else ""),
                  sources=lex.sources.fillna("").str.replace(",", ", "))[
    ["id", "Language", "lemma", "type", "gender", "plural", "gloss", "verb_forms", "notes",
     "tags", "status", "encounters", "sources", "first_seen", "due"]]
text_cols = ["gender", "plural", "gloss", "verb_forms", "notes", "tags"]
view[text_cols] = view[text_cols].fillna("")
edited = st.data_editor(
    view, hide_index=True, width="stretch", key="browse_editor",
    disabled=["id", "Language", "type", "status", "encounters", "sources", "first_seen", "due"],
    column_config={
        "id": None, "lemma": "Word or expression", "gloss": "Meaning",
        "gender": st.column_config.SelectboxColumn("Gender", options=["", "m", "f", "n"]),
        "type": "Type", "plural": "Plural", "verb_forms": "Verb forms", "status": "Status",
        "notes": "Word parts / notes", "tags": "Tags",
        "encounters": "Times met", "sources": st.column_config.TextColumn("Appeared in", width="medium"),
        "first_seen": "First met", "due": "Next review",
    })

changes = st.session_state.get("browse_editor", {}).get("edited_rows", {})
if changes and st.button("Save changes", type="primary"):
    for idx, fields in changes.items():
        db.update_lexeme(conn, int(view.iloc[int(idx)].id), **fields)
    st.toast("Changes saved", icon=":material/check:")
    st.rerun()

st.divider()
pick = st.selectbox("Show contexts for", view.lemma.tolist(), index=None,
                    placeholder="Choose a word")
if pick:
    row = view[view.lemma == pick].iloc[0]
    for e in db.contexts_for(conn, int(row.id)):
        link = f" · [link]({e['url']})" if e["url"] else ""
        st.markdown(f"> {highlight(e['sentence'], e['surface']) or '_no sentence_'}  \n"
                    f"<small>{e['source_type']} · {e['source_title'] or ''} · "
                    f"{e['locator'] or ''} · {e['seen_at']}</small>{link}",
                    unsafe_allow_html=True)
    if st.button("Delete this entry and all its contexts"):
        db.delete_lexeme(conn, int(row.id))
        st.rerun()
