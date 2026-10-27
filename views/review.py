import random

import streamlit as st

from lexilog import db
from views.common import get_conn, highlight, language_picker

conn = get_conn()
st.title("Review")

lang = language_picker("rev_lang", include_all=True)
mode = st.radio("Card front", ["Word → meaning", "Sentence with gap → word"],
                horizontal=True, key="rev_mode")

queue_key = f"queue_{lang}"
if queue_key not in st.session_state:
    st.session_state[queue_key] = [r["id"] for r in db.due_cards(conn, lang)]
queue = st.session_state[queue_key]

if not queue:
    st.success("Nothing due. New cards appear here as soon as you add words.")
    if st.button("Check again"):
        st.session_state.pop(queue_key)
        st.rerun()
    st.stop()

st.caption(f"{len(queue)} card{'s' if len(queue) != 1 else ''} left in this session")
lex = conn.execute("SELECT * FROM lexemes WHERE id=?", (queue[0],)).fetchone()
contexts = db.contexts_for(conn, lex["id"])
ctx = random.Random(lex["id"] + len(queue)).choice(contexts) if contexts else None

with st.container(border=True):
    if mode.startswith("Word") or not ctx or not ctx["sentence"]:
        st.markdown(f"## {lex['lemma']}")
        if ctx and ctx["sentence"]:
            st.markdown(f"> {highlight(ctx['sentence'], ctx['surface'])}")
    else:
        gap = ctx["sentence"]
        i = gap.lower().find((ctx["surface"] or "").lower())
        if ctx["surface"] and i >= 0:
            gap = gap[:i] + "_____" + gap[i + len(ctx["surface"]):]
        st.markdown(f"### {gap}")
        if lex["gloss"]:
            st.caption(f"Hint: {lex['gloss']}")

    revealed = st.session_state.get("revealed") == lex["id"]
    if not revealed:
        if st.button("Show answer", type="primary"):
            st.session_state["revealed"] = lex["id"]
            st.rerun()
    else:
        st.divider()
        g = {"m": "der", "f": "die", "n": "das"}.get(lex["gender"]) if lex["language"] == "de" \
            else {"m": "masc.", "f": "fém."}.get(lex["gender"])
        head = f"**{lex['lemma']}**" + (f"  ({g}" + (f", pl. {lex['plural']}" if lex["plural"] else "")
                                          + ")" if g else "")
        st.markdown(head)
        st.markdown(lex["gloss"] or "_No meaning saved yet. Add one in the word list._")
        if len(contexts) > 1:
            with st.expander(f"All {len(contexts)} places you met it"):
                for e in contexts:
                    st.markdown(f"> {highlight(e['sentence'], e['surface'])}  \n"
                                f"<small>{e['source_type']} · {e['source_title'] or ''} · "
                                f"{e['seen_at']}</small>", unsafe_allow_html=True)
        cols = st.columns(4)
        for col, (rating, label) in zip(cols, [(1, "Forgot"), (2, "Hard"), (3, "Good"), (4, "Easy")]):
            if col.button(label, width="stretch", key=f"r{rating}"):
                db.record_review(conn, lex["id"], rating)
                queue.pop(0)
                if rating == 1:
                    queue.insert(min(3, len(queue)), lex["id"])  # see it again soon
                st.session_state.pop("revealed", None)
                st.rerun()
