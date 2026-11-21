"""The plan week is Sunday to Saturday."""

from datetime import date

import pytest

from src.services.plan_week import week_days, week_start_of


@pytest.mark.parametrize("day, expected", [
    (date(2026, 11, 15), date(2026, 11, 15)),  # Sunday starts its own week
    (date(2026, 11, 16), date(2026, 11, 15)),  # Monday
    (date(2026, 11, 21), date(2026, 11, 15)),  # Saturday ends it
    (date(2026, 11, 22), date(2026, 11, 22)),  # the next Sunday starts the next
    (date(2027, 1, 1), date(2026, 12, 27)),    # across a year end
])
def test_week_start_of(day, expected):
    assert week_start_of(day) == expected
    assert expected.strftime("%A") == "Sunday"


def test_week_days_are_seven_consecutive_days():
    days = week_days(date(2026, 11, 29))
    assert days[0] == date(2026, 11, 29)
    assert days[-1] == date(2026, 12, 5)
    assert len(days) == 7
