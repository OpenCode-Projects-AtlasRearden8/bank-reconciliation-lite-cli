"""Shared data types and friendly errors."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


class FriendlyError(Exception):
    """An error we show to the user in plain English."""

    def __init__(self, headline: str, hint: str = ""):
        self.headline = headline
        self.hint = hint
        super().__init__(headline)


@dataclass
class Transaction:
    """One money movement from a CSV row."""

    when: date
    description: str
    amount: float  # positive = money in, negative = money out
    row_number: int  # line in its source file (for error messages)
    section: str = ""  # "statement" or "ledger"

    def __post_init__(self) -> None:
        self.amount = round(self.amount, 2)

    def label(self) -> str:
        """Short human-readable line, e.g. '2026-05-14  NETFLIX  -15.49'."""
        return f"{self.when.isoformat()}  {self.description!r}  {self.amount:+.2f}"


@dataclass
class Match:
    statement: Transaction
    ledger: Transaction
    confidence: str  # "exact" or "close"

    def describe(self) -> str:
        if self.confidence == "exact":
            return f"Matched: {self.statement.label()} == {self.ledger.label()}"
        return f"Close match: statement {self.statement.label()} ~ ledger {self.ledger.label()}"


@dataclass
class Finding:
    """Something the report wants to say to the user."""

    severity: str  # "attention", "info"
    title: str
    lines: list[str] = field(default_factory=list)
