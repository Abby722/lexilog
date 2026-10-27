"""Aggregations for the dashboard. Pure pandas, no Streamlit."""
from datetime import date

import pandas as pd

from .scheduler import status


def with_status(lex: pd.DataFrame) -> pd.DataFrame:
    lex = lex.copy()
    lex["status"] = [status(i, r, l) for i, r, l in zip(lex.interval_days, lex.reps, lex.lapses)]
    return lex


def weekly_new(lex: pd.DataFrame) -> pd.DataFrame:
    """New lexemes per ISO week and language."""
    if lex.empty:
        return pd.DataFrame(columns=["week", "language", "count"])
    d = lex.assign(week=pd.to_datetime(lex.first_seen).dt.to_period("W").dt.start_time)
    return d.groupby(["week", "language"]).size().reset_index(name="count")


def by_source(enc: pd.DataFrame) -> pd.DataFrame:
    if enc.empty:
        return pd.DataFrame(columns=["source_type", "language", "count"])
    return enc.groupby(["source_type", "language"]).size().reset_index(name="count")


def known_over_time(lex: pd.DataFrame, reviews: pd.DataFrame) -> pd.DataFrame:
    """Cumulative count of lexemes whose interval first reached 21+ days, per language."""
    if reviews.empty:
        return pd.DataFrame(columns=["day", "language", "known"])
    r = reviews[reviews.interval_days >= 21].copy()
    r["day"] = pd.to_datetime(r.reviewed_at).dt.normalize()
    first = r.groupby(["lexeme_id", "language"]).day.min().reset_index()
    daily = first.groupby(["day", "language"]).size().groupby(level="language").cumsum()
    return daily.reset_index(name="known")


def retention(reviews: pd.DataFrame, days: int = 30) -> pd.DataFrame:
    """Share of reviews in the last `days` days that were not 'again', per language."""
    if reviews.empty:
        return pd.DataFrame(columns=["language", "retention", "reviews"])
    r = reviews[pd.to_datetime(reviews.reviewed_at) >= pd.Timestamp.now() - pd.Timedelta(days=days)]
    g = r.groupby("language")
    return pd.DataFrame({"retention": g.rating.apply(lambda s: (s > 1).mean()),
                         "reviews": g.size()}).reset_index()


def goal_progress(goal: pd.Series, lex: pd.DataFrame, today: date | None = None) -> dict:
    """Compare actual known count to a straight-line pace from start to deadline."""
    today = today or date.today()
    start, end = date.fromisoformat(goal.start_on), date.fromisoformat(goal.deadline)
    known = int(((lex.language == goal.language) & (lex.status == "known")).sum())
    total_days = max((end - start).days, 1)
    elapsed = min(max((today - start).days, 0), total_days)
    expected = goal.target * elapsed / total_days
    days_left = max((end - today).days, 0)
    return {
        "known": known, "target": int(goal.target), "expected_now": round(expected),
        "days_left": days_left, "on_track": known >= expected,
        "needed_per_week": round((goal.target - known) / max(days_left / 7, 1), 1),
    }
