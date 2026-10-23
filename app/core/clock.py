"""Time helpers.

Rules the whole codebase follows:

* instants are timezone-aware and stored in UTC;
* working hours are wall-clock times in the clinic timezone;
* a slot is the half-open interval ``[starts_at, ends_at)`` so adjacent slots
  never overlap and a 30-minute slot is never counted twice.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc


class NaiveDateTimeError(ValueError):
    """Raised when an incoming datetime carries no timezone."""


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


def require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise NaiveDateTimeError("datetime must include a timezone offset")
    return value


def to_utc(value: datetime) -> datetime:
    return require_aware(value).astimezone(UTC)


def local_midnight_utc(day: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, time(0, 0), tzinfo=tz).astimezone(UTC)


def local_day_bounds_utc(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """UTC range covering one local calendar day (end exclusive)."""
    start = local_midnight_utc(day, tz)
    end = local_midnight_utc(day + timedelta(days=1), tz)
    return start, end


def wall_clock(day: date, at: time, tz: ZoneInfo) -> datetime:
    """Combine a local date and wall-clock time into an aware instant.

    Using ``combine`` rather than arithmetic on UTC keeps DST transitions
    honest: the resulting instant is whatever that wall-clock time means on
    that day. (Africa/Nairobi has no DST, but the code should not depend on it.)
    """
    return datetime.combine(day, at, tzinfo=tz)
