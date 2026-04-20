"""Resolve (origin, date) to the statement cycle it belongs to.

Amex bills on the 19th (new cycle starts the 20th). BBVA/Nu/GBM use calendar
months in this household. `close_month` is the calendar month the cycle closes
in — it's what rolls up into the monthly Excel.
"""

from __future__ import annotations

import datetime as dt
from typing import Union

from schema import Cycle


DateLike = Union[str, dt.date, dt.datetime]


def _to_date(d: DateLike) -> dt.date:
    if isinstance(d, dt.datetime):
        return d.date()
    if isinstance(d, dt.date):
        return d
    return dt.date.fromisoformat(str(d)[:10])


def _last_day_of_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (dt.date(year, month + 1, 1) - dt.timedelta(days=1)).day


def resolve_cycle(origin: str, date: DateLike) -> Cycle:
    d = _to_date(date)
    origin = (origin or "").upper()

    if origin == "AMEX":
        # Cycle ends on the 19th. If the txn is on/after the 20th, it's in the
        # cycle that closes on the 19th of the following month.
        if d.day >= 20:
            start = d.replace(day=20)
            if d.month == 12:
                end = dt.date(d.year + 1, 1, 19)
            else:
                end = dt.date(d.year, d.month + 1, 19)
        else:
            end = d.replace(day=19)
            if d.month == 1:
                start = dt.date(d.year - 1, 12, 20)
            else:
                start = dt.date(d.year, d.month - 1, 20)
        close_month = f"{end.year:04d}-{end.month:02d}"
        return Cycle(start.isoformat(), end.isoformat(), close_month)

    # Calendar month for everything else
    start = d.replace(day=1)
    end = d.replace(day=_last_day_of_month(d.year, d.month))
    close_month = f"{d.year:04d}-{d.month:02d}"
    return Cycle(start.isoformat(), end.isoformat(), close_month)
