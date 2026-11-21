"""
The plan week: seven days, Sunday to Saturday.

Everything that needs to know where a week starts asks here, so the day can
be changed in one place.
"""

from datetime import date, timedelta

# date.weekday() numbering: Monday is 0, Sunday is 6.
WEEK_START_WEEKDAY = 6
WEEK_START_NAME = "Sunday"


def week_start_of(day: date) -> date:
    """The first day of the plan week that holds `day`."""
    return day - timedelta(days=(day.weekday() - WEEK_START_WEEKDAY) % 7)


def week_days(week_start: date) -> list[date]:
    """The seven days of the week beginning at `week_start`."""
    return [week_start + timedelta(days=offset) for offset in range(7)]
