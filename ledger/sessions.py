"""The ledger's own NYSE session calendar: which New York dates the market is open.

The full-day closures are the same list as trading-lab-research `src/wt/options/levels.py` (`HOLIDAYS`), which the
card's pick (`olib.is_session`) also uses: NYSE's published holidays through 2028, and 2029 by the exchange's rules.
Half days (13:00 close) are sessions like any other here. The ledger's history cross-checks the list: from 4 Mar
2026 every weekday without records is one of these closures or is listed in missed_sessions.json, and
`ledger validate --gaps` keeps it that way.
"""
from __future__ import annotations

from datetime import date, timedelta

HOLIDAYS = frozenset({
    # 2024
    "2024-01-01", "2024-01-15", "2024-02-19", "2024-03-29", "2024-05-27", "2024-06-19", "2024-07-04",
    "2024-09-02", "2024-11-28", "2024-12-25",
    # 2025 (9 Jan: national day of mourning for President Carter)
    "2025-01-01", "2025-01-09", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26", "2025-06-19",
    "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25",
    # 2026
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03",
    "2026-09-07", "2026-11-26", "2026-12-25",
    # 2027
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18", "2027-07-05",
    "2027-09-06", "2027-11-25", "2027-12-24",
    # 2028 (1 January is a Saturday: no New Year's Day holiday is observed)
    "2028-01-17", "2028-02-21", "2028-04-14", "2028-05-29", "2028-06-19", "2028-07-04", "2028-09-04",
    "2028-11-23", "2028-12-25",
    # 2029 (expected: NYSE has not published 2029)
    "2029-01-01", "2029-01-15", "2029-02-19", "2029-03-30", "2029-05-28", "2029-06-19", "2029-07-04",
    "2029-09-03", "2029-11-22", "2029-12-25",
})
CALENDAR_FROM = date(2024, 1, 1)
CALENDAR_THROUGH = date(2029, 12, 31)


def covered(d: date) -> bool:
    return CALENDAR_FROM <= d <= CALENDAR_THROUGH


def is_session(d: date | str) -> bool:
    """True if NYSE is open on this New York date. Raises outside the calendar instead of guessing."""
    if isinstance(d, str):
        s, d = d, date.fromisoformat(d)
        if d.isoformat() != s:
            raise ValueError(f"{s!r}: write sessions as YYYY-MM-DD")
    if not covered(d):
        raise ValueError(f"{d}: the session calendar covers {CALENDAR_FROM} to {CALENDAR_THROUGH}; extend ledger/sessions.py")
    return d.weekday() < 5 and d.isoformat() not in HOLIDAYS


def sessions_between(start: date, end: date) -> list[str]:
    """Every NYSE session from start to end, both included, as ISO dates."""
    out, d = [], start
    while d <= end:
        if is_session(d):
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out
