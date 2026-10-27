import streamlit as st

from lexilog import db, nlp
from views.common import get_conn, highlight

conn = get_conn()
qp = st.query_params

st.title("Add a word")

# Values arriving from the browser bookmarklet (see "Goals & capture")
if "prefilled" not in st.session_state and qp.get("text"):
    st.session_state.update({
        "cap_text": qp.get("text", ""), "cap_sentence": qp.get("sentence", ""),
        "cap_url": qp.get("url", ""), "cap_title": qp.get("title", ""),
        "cap_source": qp.get("source", "news"),
    })
    if qp.get("lang") in db.LANGUAGES:
        st.session_state["cap_lang"] = qp["lang"]
    st.session_state["prefilled"] = True

st.session_state.setdefault("cap_lang", "de")
lang = st.segmented_control("Language", list(db.LANGUAGES), format_func=db.LANGUAGES.get,
                            key="cap_lang")
lang = lang or "de"

text = st.text_input("Word or expression, as you saw it", key="cap_text",
                     placeholder="schließt ... ab   /   en revanche")
sentence = st.text_area("Sentence it appeared in", key="cap_sentence", height=80)

suggestion = nlp.suggest(lang, text, sentence) if text else {}
existing = None
if text:
    lemma = st.text_input(
        "Dictionary form", value=suggestion.get("lemma", text), key=f"cap_lemma_{text}",
        help="Encounters are grouped under this form. "
             + ("Suggested by spaCy." if nlp.available(lang)
                else "Install spaCy models for automatic suggestions."))
    existing = conn.execute("SELECT * FROM lexemes WHERE language=? AND lemma=?",
                            (lang, lemma.strip())).fetchone()
    if existing:
        prev = db.contexts_for(conn, existing["id"])
        st.info(f"You've met **{existing['lemma']}** {len(prev)} time"
                f"{'s' if len(prev) != 1 else ''} before. This adds another context.")
        with st.expander("Earlier contexts"):
            for e in prev[:5]:
                st.markdown(f"> {highlight(e['sentence'], e['surface'])}  \n"
                            f"<small>{e['source_type']} · {e['source_title'] or ''} · "
                            f"{e['seen_at']}</small>", unsafe_allow_html=True)

c1, c2 = st.columns(2)
source = c1.selectbox("Source", db.SOURCE_TYPES, key="cap_source")
title = c2.text_input("Title", key="cap_title", placeholder="DW Nachrichten, book title, video")
c1, c2 = st.columns(2)
url = c1.text_input("Link", key="cap_url")
locator = c2.text_input("Page or timestamp", key="cap_locator")

with st.expander("Meaning and grammar", expanded=not existing):
    gloss = st.text_input("Meaning, in your own words",
                          value=existing["gloss"] if existing and existing["gloss"] else "")
    c1, c2, c3 = st.columns(3)
    genders = ["", "m", "f", "n"] if lang == "de" else ["", "m", "f"]
    g_default = (suggestion.get("gender") or "") if suggestion else ""
    gender = c1.selectbox("Gender", genders,
                          index=genders.index(g_default) if g_default in genders else 0)
    plural = c2.text_input("Plural")
    tags = c3.text_input("Tags", placeholder="B1, politics")

if st.button("Save", type="primary", disabled=not text):
    _, created = db.add_encounter(
        conn, lang, lemma, sentence=sentence, surface=text, source_type=source,
        source_title=title, url=url, locator=locator, gloss=gloss, gender=gender,
        plural=plural, tags=tags, pos=suggestion.get("pos"),
        kind=suggestion.get("kind", "word"))
    st.toast(f"Saved {'new word' if created else 'new context for'} “{lemma}”",
             icon=":material/check:")
    for k in ["cap_text", "cap_sentence", "cap_url", "cap_locator"]:
        st.session_state.pop(k, None)
    st.query_params.clear()
    st.rerun()
