from datetime import date

import pytest

from lexilog.scheduler import CardState, due_date, schedule, status


def test_first_good_review_is_one_day():
    s = schedule(CardState(), 3)
    assert s.interval_days == 1 and s.reps == 1


def test_intervals_grow_with_good_reviews():
    s = CardState()
    intervals = []
    for _ in range(5):
        s = schedule(s, 3)
        intervals.append(s.interval_days)
    assert intervals == sorted(intervals) and intervals[-1] > 21


def test_forgetting_resets_and_counts_lapse():
    s = schedule(schedule(schedule(CardState(), 3), 3), 1)
    assert s.interval_days == 0 and s.reps == 0 and s.lapses == 1
    assert status(s.interval_days, s.reps, s.lapses) == "learning"


def test_ease_never_below_minimum():
    s = CardState()
    for _ in range(20):
        s = schedule(s, 1)
    assert s.ease >= 1.3


def test_invalid_rating():
    with pytest.raises(ValueError):
        schedule(CardState(), 5)


def test_due_date():
    assert due_date(CardState(interval_days=6), date(2026, 1, 1)) == date(2026, 1, 7)
