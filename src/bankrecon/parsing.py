"""Helpers so users can write amounts and dates the way banks do.

Accepted amounts:
    -15.49        plain negative
    15.49-        trailing minus (some banks)
    (15.49), 15.49-, $15.49   all count as a debit
    $1,234.56     thousands separators are fine

Accepted dates:
    2026-01-15, 2026/01/15          ISO style (recommended)
    1/15/2026, 01-15-2026           US month/day/year
    Jan 15 2026, 15 Jan 2026        month names
"""

from __future__ import annotations

import re
from datetime import date, datetime

from .models import FriendlyError

MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_DATE_FORMATS = [
    "%Y-%m-%d", "%Y/%m/%d",
    "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y",
    "%b %d %Y", "%b %d,%Y", "%b %d, %Y",
    "%d %b %Y", "%B %d %Y", "%B %d, %Y",
    "%d %B %Y",
]


def parse_amount(raw: str, row_number: int, file_label: str) -> float:
    """Turn a cell like '$(1,234.56)' into -1234.56.

    Raises FriendlyError if the cell is not a number we can read.
    """
    text = (raw or "").strip()
    if not text:
        raise FriendlyError(
            f"A blank amount stopped the fun. Row {row_number} of "
            f"{file_label} has no amount.",
            hint="Every row needs an amount, even 0.00. Fill it in and try again.",
        )

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    if text.endswith("-"):
        negative = True
        text = text[:-1]
    if text.startswith("-"):
        if negative:  # e.g. "-(12.34)" already handled above, rare double sign
            pass
        negative = True
        text = text[1:]
    if text.endswith("+"):
        text = text[:-1]

    text = text.replace("$", "").replace(",", "").replace(" ", "")
    try:
        value = float(text)
    except ValueError:
        raise FriendlyError(
            f"We could not read the amount {raw.strip()!r} on row {row_number} "
            f"of {file_label}.",
            hint="Amounts should look like -15.49, 15.49-, (15.49) or $1,234.56.",
        ) from None

    return -abs(value) if negative else value


def parse_date(raw: str, row_number: int, file_label: str) -> date:
    """Turn a cell like '2026-01-15' or '1/15/2026' into a real date.

    Two-digit years are read as 2000-2068. Month-first (US) order is used
    for numeric slashes/dashes, which matches most US bank exports.
    """
    text = (raw or "").strip()
    if not text:
        raise FriendlyError(
            f"A blank date stopped the fun. Row {row_number} of {file_label} "
            "has no date.",
            hint="Every row needs a date, like 2026-01-15 or 1/15/2026.",
        )

    for fmt in _DATE_FORMATS:
        try:
            stamp = datetime.strptime(text, fmt)
            return stamp.date()
        except ValueError:
            continue

    raise FriendlyError(
        f"We could not read the date {text!r} on row {row_number} of {file_label}.",
        hint="Dates should look like 2026-01-15, 1/15/2026 or Jan 15 2026. "
             "Right now we read month first (US style).",
    )
