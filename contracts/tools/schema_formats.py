"""The one date-time format policy for every validating contract tool (plan D-P14).

``jsonschema`` enforces ``format: date-time`` only when the optional
``rfc3339-validator`` package is importable, and a bare ``FormatChecker()`` also
switches on other formats (uri, json-pointer, duration, ...) exactly when other
optional packages are present. Relying on that would give different verdicts for
one example in different environments. ``FORMAT_CHECKER`` therefore starts empty
and registers only the formats the contract uses, as explicit standard-library
checks. A later use of any other format registers its own check here.

Library only: standard library plus ``jsonschema``; no pytest, nothing from
``tests/`` or ``scripts/``.
"""

from __future__ import annotations

import calendar
import re
from datetime import datetime
from typing import Any

from jsonschema import FormatChecker

# RFC 3339 section 5.6 date-time: a date, "T" (or "t"), a time with optional
# fractional seconds, and a mandatory offset.
_DATE_TIME = re.compile(
    r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})[Tt]"
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(?:\.\d+)?"
    r"(?:[Zz]|[+-](?P<offset_hour>\d{2}):(?P<offset_minute>\d{2}))$"
)
_MAX_LEAP_SECOND = 60


def is_rfc3339_date_time(instance: Any) -> bool:
    """True when ``instance`` is an RFC 3339 date-time string. Non-strings are not format-checked."""
    if not isinstance(instance, str):
        return True
    match = _DATE_TIME.match(instance)
    if match is None:
        return False
    parts = {name: int(value) for name, value in match.groupdict().items() if value is not None}
    if not 1 <= parts["month"] <= 12 or not 1 <= parts["day"] <= calendar.monthrange(parts["year"], parts["month"])[1]:
        return False
    if parts.get("offset_hour", 0) > 23 or parts.get("offset_minute", 0) > 59:
        return False
    if parts["second"] > _MAX_LEAP_SECOND:
        return False
    try:
        datetime(parts["year"], parts["month"], parts["day"], parts["hour"], parts["minute"], min(parts["second"], 59))
    except ValueError:
        return False
    return True


FORMAT_CHECKER = FormatChecker(formats=())
FORMAT_CHECKER.checks("date-time")(is_rfc3339_date_time)
