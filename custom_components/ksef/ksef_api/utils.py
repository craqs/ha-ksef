from __future__ import annotations
from datetime import date, datetime, timezone, timedelta
from typing import Tuple


def month_range(year: int, month: int) -> Tuple[str, str]:
    start = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
    return start.isoformat(), end.isoformat()


def parse_month_option(value: str) -> Tuple[str, str]:
    today = date.today()
    if value == "this":
        return month_range(today.year, today.month)
    if value == "last":
        first = date(today.year, today.month, 1)
        prev = first - timedelta(days=1)
        return month_range(prev.year, prev.month)
    parts = value.split("-")
    if len(parts) == 2:
        try:
            year, month = int(parts[0]), int(parts[1])
            if 1 <= month <= 12:
                return month_range(year, month)
        except ValueError:
            pass
    raise ValueError(f"Invalid month value: {value!r}")
