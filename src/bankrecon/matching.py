"""The heart of it: match statement rows to ledger rows.

We work in three passes, then look for the two things people dread most:
double charges and subscriptions they forgot about.

Pass 1: exact amount + exact day + same words        -> exact
Pass 2: exact amount + exact day (any words)         -> exact
Pass 3: exact amount within a few days window        -> close
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import timedelta

from .models import Finding, Match, Transaction

DEFAULT_DAY_WINDOW = 3

_NOISE = re.compile(r"[^A-Za-z ]+")


def normalize_description(text: str) -> str:
    """Lowercase words up, drop bank reference noise, and match merchants.

    'AMZN MKTP US*2Y34A 12345' and 'amzn mktp us' become the same thing:
    words with digits in them are reduced to their alphabetic fragments
    of 2+ letters (reference codes leave single stray letters behind).
    """
    words = []
    for word in text.upper().split():
        if any(ch.isdigit() for ch in word):
            fragments = [f for f in re.findall(r"[A-Z]+", word) if len(f) >= 2]
            words.extend(fragments)
        else:
            words.extend(w for w in _NOISE.sub(" ", word).split() if w)
    return " ".join(words).strip()


def _dates_close(a: Transaction, b: Transaction, days: int) -> bool:
    return abs((a.when - b.when).days) <= days


def reconcile(
    statement: list[Transaction],
    ledger: list[Transaction],
    *,
    day_window: int = DEFAULT_DAY_WINDOW,
) -> tuple[list[Match], list[Transaction], list[Transaction],
           list[tuple[Transaction, Transaction]], list[tuple[Transaction, Transaction]]]:
    """Run the matching passes.

    Returns:
        matches, statement_only, ledger_only, duplicate_pairs, subscription_rows
    """
    statement = sorted(statement, key=lambda t: (t.when, t.row_number))
    ledger = sorted(ledger, key=lambda t: (t.when, t.row_number))

    matches: list[Match] = []
    ledger_free: set[int] = set(range(len(ledger)))
    statement_claimed: set[int] = set()

    def claim(s_index: int, l_index: int, confidence: str) -> None:
        ledger_free.discard(l_index)
        statement_claimed.add(s_index)
        matches.append(Match(statement[s_index], ledger[l_index], confidence))

    # Pass 1: exact amount, exact date, same normalized description.
    ledger_by_key: dict[tuple[float, str], list[int]] = defaultdict(list)
    ledger_by_amount_date: dict[tuple[float, object], list[int]] = defaultdict(list)
    ledger_by_amount: dict[float, list[int]] = defaultdict(list)
    for j, row in enumerate(ledger):
        ledger_by_key[(row.amount, normalize_description(row.description))].append(j)
        ledger_by_amount_date[(row.amount, row.when)].append(j)
        ledger_by_amount[row.amount].append(j)

    for i, row in enumerate(statement):
        key = (row.amount, normalize_description(row.description))
        for j in ledger_by_key.get(key, []):
            if j in ledger_free and row.when == ledger[j].when:
                claim(i, j, "exact")
                break

    # Pass 2: exact amount, exact date, description ignored.
    for i, row in enumerate(statement):
        if i in statement_claimed:
            continue
        for j in ledger_by_amount_date.get((row.amount, row.when), []):
            if j in ledger_free:
                claim(i, j, "exact")
                break

    # Pass 3: exact amount within the day window, nearest date first.
    for i, row in enumerate(statement):
        if i in statement_claimed:
            continue
        candidates = [
            (abs((row.when - ledger[j].when).days), j)
            for j in ledger_by_amount.get(row.amount, [])
            if j in ledger_free and _dates_close(row, ledger[j], day_window)
        ]
        if candidates:
            candidates.sort()
            claim(i, candidates[0][1], "close")

    statement_only = [
        row for i, row in enumerate(statement) if i not in statement_claimed
    ]
    ledger_only = [ledger[j] for j in sorted(ledger_free)]

    duplicate_pairs = find_double_charges(statement)
    subscription_rows = find_subscription_charges(statement_only)

    return matches, statement_only, ledger_only, duplicate_pairs, subscription_rows


def find_double_charges(statement: list[Transaction]) -> list[tuple[Transaction, Transaction]]:
    """Two charges with the same amount and (roughly) the same words close
    together often mean the merchant charged twice on accident.
    """
    pairs: list[tuple[Transaction, Transaction]] = []
    for i, first in enumerate(statement):
        for second in statement[i + 1:]:
            if first.amount == second.amount \
                    and normalize_description(first.description) == normalize_description(second.description):
                gap = abs((second.when - first.when).days)
                if gap <= 3:
                    pairs.append((first, second))
    return pairs


def find_subscription_charges(unmatched: list[Transaction]) -> list[Transaction]:
    """Repeat charges (same amount+merchant, 5+ days apart) that never made
    it into your ledger usually mark a subscription you forgot about.
    """
    groups: dict[tuple[float, str], list[Transaction]] = defaultdict(list)
    for row in unmatched:
        groups[(row.amount, normalize_description(row.description))].append(row)

    subscription_rows: list[Transaction] = []
    for (_, _), rows in groups.items():
        if len(rows) < 2:
            continue
        spread = (max(r.when for r in rows) - min(r.when for r in rows)).days
        if spread >= 5:
            subscription_rows.extend(sorted(rows, key=lambda r: r.when))
    return subscription_rows


def _days_apart(a: Transaction, b: Transaction) -> int:
    return abs((b.when - a.when).days)


def build_findings(
    matches: list[Match],
    statement_only: list[Transaction],
    ledger_only: list[Transaction],
    duplicate_pairs: list[tuple[Transaction, Transaction]],
    subscription_rows: list[Transaction],
) -> list[Finding]:
    """Turn raw results into human sentences, worst news first."""
    findings: list[Finding] = []

    if duplicate_pairs:
        lines = []
        for first, second in duplicate_pairs:
            lines.append(
                f"Charged {abs(first.amount):.2f} twice "
                f"({_days_apart(first, second)} day(s) apart) - "
                f"{first.label()} and {second.label()}"
            )
        findings.append(Finding(
            "attention",
            f"Possible double charge{'s' if len(duplicate_pairs) > 1 else ''} "
            f"({len(duplicate_pairs)} pair{'s' if len(duplicate_pairs) > 1 else ''}) - "
            "worth a call to the merchant",
            lines,
        ))

    if subscription_rows:
        by_key: dict[tuple[float, str], list[Transaction]] = defaultdict(list)
        for row in subscription_rows:
            by_key[(row.amount, normalize_description(row.description))].append(row)
        lines = []
        for (amount, _), rows in sorted(by_key.items()):
            dates = ", ".join(r.when.isoformat() for r in rows)
            lines.append(
                f"{rows[0].description!r} charged {abs(amount):.2f} on {dates} "
                f"({len(rows)} times) but never appears in your ledger"
            )
        findings.append(Finding(
            "attention",
            f"Possible subscription{'s' if len(by_key) > 1 else ''} your ledger forgot about",
            lines,
        ))

    if statement_only:
        findings.append(Finding(
            "attention",
            f"{len(statement_only)} statement entr{'y' if len(statement_only) == 1 else 'ies'} "
            "with no ledger match",
            [row.label() for row in statement_only],
        ))

    if ledger_only:
        findings.append(Finding(
            "attention",
            f"{len(ledger_only)} ledger entr{'y' if len(ledger_only) == 1 else 'ies'} "
            "not on the statement (still pending? dated ahead?)",
            [row.label() for row in ledger_only],
        ))

    if not findings:
        findings.append(Finding(
            "info",
            "All clear - every statement row matched your ledger.",
        ))
    return findings
