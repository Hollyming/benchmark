from __future__ import annotations

from datetime import datetime, timedelta, timezone


def utc_datetime(year: int, month: int, day: int, hour: int = 9) -> datetime:
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


def add_days(base: datetime, days: int, hour: int | None = None) -> datetime:
    value = base + timedelta(days=days)
    if hour is not None:
        value = value.replace(hour=hour)
    return value

