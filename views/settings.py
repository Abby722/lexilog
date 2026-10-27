from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

import streamlit as st

from lexilog import db
from views.common import get_conn, lang_name

conn = get_conn()
st.title("Goals & capture")

st.markdown("#### Goals")
st.markdown("A goal is a number of known words by a date. The progress page shows whether "
            "you are on pace. A word counts as known once its review interval reaches three weeks.")
goals = db.goals_df(conn)
for g in goals.itertuples():
    c1, c2 = st.columns([5, 1])
    c1.markdown(f"**{g.label}** · {lang_name(g.language)} · {g.target} words by {g.deadline}")
    if c2.button("Remove", key=f"del_goal_{g.id}"):
        conn.execute("DELETE FROM goals WHERE id=?", (g.id,))
        conn.commit()
        st.rerun()

with st.form("goal", clear_on_submit=True):
    c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
    lang = c1.selectbox("Language", list(db.LANGUAGES), format_func=db.LANGUAGES.get)
    label = c2.text_input("Name", placeholder="Goethe B1 exam")
    target = c3.number_input("Known words", min_value=10, value=600, step=50)
    deadline = c4.date_input("By", value=date.today() + timedelta(days=90))
    if st.form_submit_button("Add goal") and label:
        db.add_goal(conn, lang, label, int(target), deadline.isoformat())
        st.rerun()

st.divider()
st.markdown("#### Capture from any web page")
st.markdown(
    "Drag the link below to your bookmarks bar. On a DW, Tagesschau, Le Monde or any other "
    "page, select a word or phrase and click the bookmark: this app opens on *Add a word* "
    "with the word, its sentence, the page link and the language already filled in. "
    "It works while lexilog is running on this computer.")
src = (Path(__file__).resolve().parent.parent / "bookmarklet.js").read_text(encoding="utf-8")
code = " ".join(l.strip() for l in src.splitlines()
                if l.strip() and not l.strip().startswith("//"))
button_html = (
    f'''<a href="javascript:{quote(code)}" onclick="return false"
       style="display:inline-block;padding:.45rem .9rem;border:1.5px solid #2E6B5E;
              border-radius:.4rem;text-decoration:none;color:#2E6B5E;font-weight:600;
              font-family:sans-serif;cursor:grab">+ lexilog</a>''')
if hasattr(st, "iframe"):
    st.iframe(button_html, height=48)
else:
    import streamlit.components.v1 as components
    components.html(button_html, height=48)
st.caption("Some browsers block dragging from a page. If so, create a bookmark by hand "
           "and paste the code below as its address.")
with st.expander("Bookmarklet code"):
    st.code("javascript:" + code, language="javascript")

st.divider()
st.markdown("#### Data")
st.markdown(f"Your database is a single file at `{db.DEFAULT_DB}`. Back it up by copying it.")
enc = db.encounters_df(conn)
st.download_button("Download all contexts as CSV", enc.to_csv(index=False).encode("utf-8"),
                   file_name="lexilog_encounters.csv", mime="text/csv")
