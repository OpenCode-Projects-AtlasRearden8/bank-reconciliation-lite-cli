"""Plain-English reconciliation report."""

from __future__ import annotations

import os

from .models import Finding, Match, Transaction


def format_report(
    *,
    statement_label: str,
    ledger_label: str,
    day_window: int,
    matches: list[Match],
    findings: list[Finding],
    statement_count: int,
    ledger_count: int,
) -> str:
    """Build the whole report as a single string."""
    lines: list[str] = []
    add = lines.append

    add("BANK RECONCILIATION REPORT")
    add("=" * 60)
    add(f"Statement: {os.path.basename(statement_label)} ({statement_count} rows)")
    add(f"Ledger:    {os.path.basename(ledger_label)} ({ledger_count} rows)")
    add(f"Matched:   {len(matches)} of {statement_count} statement rows")

    matched = statement_matches(matches)
    if matched:
        close = sum(1 for m in matches if m.confidence == "close")
        add("")
        add(f"Matched {len(matched)} row{'s' if len(matched) != 1 else ''}:")
        for m in matched:
            add(f"  {m.describe()}")
        if close:
            add(f"  ({close} matched by amount + nearby date only - "
                "double-check those)")

    add("")
    add("WHAT NEEDS YOUR ATTENTION")
    add("-" * 60)

    for i, finding in enumerate(findings):
        if i:
            add("")
        mark = "!" if finding.severity == "attention" else "-"
        add(f"{mark} {finding.title}")
        for line in finding.lines:
            add(f"    {line}")

    add("")
    add("-" * 60)
    add(f"Date tolerance: {day_window} day(s). "
        "Rows within this many days of each other can match on amount alone.")
    add("Nothing left your computer. No bank logins were used.")
    return "\n".join(lines) + "\n"


def statement_matches(matches: list[Match]) -> list[Match]:
    return sorted(matches, key=lambda m: (m.statement.when, m.statement.row_number))


def write_report(text: str, path: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
