import altair as alt
import pandas as pd
import streamlit as st

from lexilog import db, stats
from views.common import LANG_COLORS, get_conn, lang_name

conn = get_conn()
lex = stats.with_status(db.lexemes_df(conn))
enc = db.encounters_df(conn)
rev = db.reviews_df(conn)
goals = db.goals_df(conn)

st.title("Progress")

if lex.empty:
    st.info("Nothing logged yet. Add your first word, import a CSV, "
            "or run `python scripts/seed_demo.py` to explore with sample data.")
    st.page_link("views/capture.py", label="Add a word", icon=":material/add_circle:")
    st.stop()

for df in (lex, enc, rev):
    if "language" in df:
        df["Language"] = df.language.map(lang_name)
color = alt.Color("Language:N", scale=alt.Scale(domain=list(LANG_COLORS),
                                                range=list(LANG_COLORS.values())))

# ---- headline numbers, one column per language ----
cols = st.columns(len(db.LANGUAGES))
for col, (code, name) in zip(cols, db.LANGUAGES.items()):
    l = lex[lex.language == code]
    due = int((pd.to_datetime(l.due) <= pd.Timestamp.today()).sum())
    with col:
        st.subheader(name)
        a, b, c = st.columns(3)
        a.metric("Known", int((l.status == "known").sum()))
        b.metric("Learning", int((l.status == "learning").sum()))
        c.metric("Due today", due)
        g = goals[goals.language == code]
        for _, goal in g.iterrows():
            p = stats.goal_progress(goal, l)
            st.progress(min(p["known"] / p["target"], 1.0),
                        text=f"{goal.label}: {p['known']} of {p['target']} known, "
                             f"{p['days_left']} days left")
            if p["days_left"] > 0:
                msg = (f"On pace. Keep adding about {p['needed_per_week']} known words a week."
                       if p["on_track"] else
                       f"Behind pace by {p['expected_now'] - p['known']}. "
                       f"You need about {p['needed_per_week']} newly known words a week.")
                st.caption(msg)

st.divider()

# ---- activity ----
left, right = st.columns([3, 2])
with left:
    st.markdown("#### New words and expressions per week")
    w = stats.weekly_new(lex)
    w["Language"] = w.language.map(lang_name)
    st.altair_chart(
        alt.Chart(w).mark_bar(cornerRadiusEnd=2).encode(
            x=alt.X("yearmonthdate(week):O", title=None,
                    axis=alt.Axis(format="%d %b", labelAngle=0)),
            y=alt.Y("count:Q", title=None),
            color=color, xOffset="Language:N",
            tooltip=["week:T", "Language:N", "count:Q"]),
        width="stretch")
with right:
    st.markdown("#### Where you meet them")
    s = stats.by_source(enc)
    s["Language"] = s.language.map(lang_name)
    st.altair_chart(
        alt.Chart(s).mark_bar().encode(
            y=alt.Y("source_type:N", title=None, sort="-x"), x=alt.X("count:Q", title=None),
            color=color, yOffset="Language:N",
            tooltip=["source_type:N", "Language:N", "count:Q"]),
        width="stretch")

left, right = st.columns([3, 2])
with left:
    st.markdown("#### Words known over time")
    k = stats.known_over_time(lex, rev)
    if k.empty:
        st.caption("A word counts as known once its review interval reaches three weeks.")
    else:
        k["Language"] = k.language.map(lang_name)
        st.altair_chart(
            alt.Chart(k).mark_line(interpolate="step-after", strokeWidth=2.5).encode(
                x=alt.X("day:T", title=None), y=alt.Y("known:Q", title=None), color=color),
            width="stretch")
with right:
    st.markdown("#### Status")
    st_ = lex.groupby(["Language", "status"]).size().reset_index(name="count")
    st.altair_chart(
        alt.Chart(st_).mark_bar().encode(
            x=alt.X("count:Q", title=None, stack="normalize", axis=alt.Axis(format="%")),
            y=alt.Y("Language:N", title=None),
            color=alt.Color("status:N", sort=["new", "learning", "known"],
                            scale=alt.Scale(domain=["new", "learning", "known"],
                                            range=["#CBD4CB", "#C08A2E", "#2E6B5E"])),
            order=alt.Order("status_order:Q"),
            tooltip=["Language:N", "status:N", "count:Q"]
        ).transform_calculate(
            status_order="indexof(['new','learning','known'], datum.status)"),
        width="stretch")
    r = stats.retention(rev)
    if not r.empty:
        st.caption("Recall in the last 30 days: " + ", ".join(
            f"{lang_name(x.language)} {x.retention:.0%} of {x.reviews} reviews"
            for x in r.itertuples()))

st.divider()
st.markdown("#### Met most often, still not known")
hard = (lex[lex.status != "known"].sort_values(["encounters", "lapses"], ascending=False)
        .head(10)[["Language", "lemma", "gloss", "encounters", "source_types", "lapses"]])
st.dataframe(hard, hide_index=True, width="stretch",
             column_config={"lemma": "Word or expression", "gloss": "Meaning",
                            "encounters": "Times met", "source_types": "Different sources",
                            "lapses": "Times forgotten"})
