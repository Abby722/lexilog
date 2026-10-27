"""Spaced-repetition scheduling (a compact SM-2 variant).

Kept deliberately small and pure so it is easy to test and to swap for FSRS later.
Ratings: 1 = again, 2 = hard, 3 = good, 4 = easy.
"""
from dataclasses import dataclass, replace
from datetime import date, timedelta

MIN_EASE = 1.3


@dataclass(frozen=True)
class CardState:
    interval_days: float = 0.0
    ease: float = 2.5
    reps: int = 0
    lapses: int = 0


def schedule(state: CardState, rating: int) -> CardState:
    """Return the new card state after a review."""
    if rating not in (1, 2, 3, 4):
        raise ValueError("rating must be 1, 2, 3 or 4")

    if rating == 1:  # forgot: start over, make it a little harder
        return replace(
            state,
            interval_days=0.0,
            ease=max(MIN_EASE, state.ease - 0.2),
            reps=0,
            lapses=state.lapses + 1,
        )

    ease = state.ease + {2: -0.15, 3: 0.0, 4: 0.15}[rating]
    ease = max(MIN_EASE, ease)

    if state.reps == 0:
        interval = {2: 1, 3: 1, 4: 4}[rating]
    elif state.reps == 1:
        interval = {2: 3, 3: 6, 4: 8}[rating]
    else:
        factor = {2: 1.2, 3: ease, 4: ease * 1.3}[rating]
        interval = max(state.interval_days + 1, state.interval_days * factor)

    return CardState(interval_days=round(interval, 2), ease=round(ease, 3),
                     reps=state.reps + 1, lapses=state.lapses)


def due_date(state: CardState, today: date | None = None) -> date:
    today = today or date.today()
    return today + timedelta(days=round(state.interval_days))


def status(interval_days: float, reps: int, lapses: int = 0) -> str:
    """Bucket a card for the dashboard: new, learning, known."""
    if reps == 0 and lapses == 0:
        return "new"
    if interval_days >= 21:
        return "known"
    return "learning"
