"""Cron schedule helpers (5-field expressions, no external deps)."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone


class CronError(ValueError):
    """Invalid cron expression."""


def _parse_field(field: str, minimum: int, maximum: int) -> set[int]:
    field = field.strip()
    if field == "*":
        return set(range(minimum, maximum + 1))

    values: set[int] = set()
    for part in field.split(","):
        part = part.strip()
        step = 1
        if "/" in part:
            base, step_s = part.split("/", 1)
            step = int(step_s)
            if step < 1:
                raise CronError(f"Invalid step in '{field}'")
        else:
            base = part

        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            a, b = base.split("-", 1)
            start, end = int(a), int(b)
        else:
            start = end = int(base)

        if start < minimum or end > maximum or start > end:
            raise CronError(f"Out of range in '{field}' ({minimum}-{maximum})")
        values.update(range(start, end + 1, step))
    return values


@dataclass(frozen=True)
class CronSchedule:
    """Parsed 5-field cron: minute hour day month weekday."""

    minute: set[int]
    hour: set[int]
    day: set[int]
    month: set[int]
    weekday: set[int]
    expression: str

    @classmethod
    def parse(cls, expression: str) -> CronSchedule:
        parts = expression.split()
        if len(parts) != 5:
            raise CronError(
                f"Cron must have 5 fields (min hour dom month dow), got: {expression!r}"
            )
        return cls(
            minute=_parse_field(parts[0], 0, 59),
            hour=_parse_field(parts[1], 0, 23),
            day=_parse_field(parts[2], 1, 31),
            month=_parse_field(parts[3], 1, 12),
            weekday=_parse_field(parts[4], 0, 6),  # 0=Sunday
            expression=expression,
        )

    def matches(self, dt: datetime) -> bool:
        # cron weekday: 0=Sunday … 6=Saturday; Python: Mon=0 … Sun=6
        py_wd = dt.weekday()
        cron_wd = 0 if py_wd == 6 else py_wd + 1
        return (
            dt.minute in self.minute
            and dt.hour in self.hour
            and dt.day in self.day
            and dt.month in self.month
            and cron_wd in self.weekday
        )


def next_matches(
    schedule: CronSchedule,
    start: datetime | None = None,
    *,
    limit: int = 60 * 24 * 8,
) -> datetime:
    """Find the next matching minute at or after start."""
    dt = (start or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
    for _ in range(limit):
        if schedule.matches(dt):
            return dt
        ts = dt.timestamp() + 60
        dt = datetime.fromtimestamp(ts, tz=dt.tzinfo or timezone.utc)
    raise CronError(f"No match for {schedule.expression} within {limit} minutes")


def sleep_until(dt: datetime) -> None:
    now = datetime.now(tz=dt.tzinfo or timezone.utc)
    delay = (dt - now).total_seconds()
    if delay > 0:
        time.sleep(delay)


def run_schedule_loop(
    expression: str,
    tick: Callable[[], None],
    *,
    once: bool = False,
    should_stop: Callable[[], bool] | None = None,
) -> None:
    """Block and invoke tick() each time the cron matches."""
    schedule = CronSchedule.parse(expression)
    last_fired: datetime | None = None
    while True:
        if should_stop and should_stop():
            return
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        candidate = now
        if last_fired and candidate <= last_fired:
            candidate = datetime.fromtimestamp(last_fired.timestamp() + 60, tz=timezone.utc)
        nxt = next_matches(schedule, candidate)
        sleep_until(nxt)
        if should_stop and should_stop():
            return
        last_fired = nxt
        tick()
        if once:
            return
