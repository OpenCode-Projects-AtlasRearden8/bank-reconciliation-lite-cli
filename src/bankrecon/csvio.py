"""Load bank-statement and ledger CSVs without fuss."""

from __future__ import annotations

import csv
import os

from .models import FriendlyError, Transaction
from .parsing import parse_amount, parse_date

# Header names we understand. The first alias found wins; any-capitalization
# and stray spaces are forgiven.
DATE_HEADERS = ["date", "transaction date", "posted date", "post date",
                "posting date", "when"]
DESC_HEADERS = ["description", "desc", "detail", "details", "payee",
                "memo", "name", "merchant", "narrative", "transaction",
                "what"]
AMOUNT_HEADERS = ["amount", "value", "amt", "transaction amount"]
DEBIT_HEADERS = ["debit", "withdrawal", "withdrawals", "money out", "paid out"]
CREDIT_HEADERS = ["credit", "deposit", "deposits", "money in", "paid in"]


def _read_csv_rows(path: str) -> tuple[str, list[list[str]]]:
    """Open a CSV and return (file_label, rows). Raises FriendlyError on trouble."""
    label = os.path.basename(path)

    if not os.path.exists(path):
        raise FriendlyError(
            f"We could not find the file {path!r}.",
            hint="Check the file name and that you are running this from the "
                 "right folder. Tip: you can drag the file into the terminal "
                 "instead of typing the path.",
        )
    if os.path.isdir(path):
        raise FriendlyError(
            f"{path!r} is a folder, not a CSV file.",
            hint="Point us at the CSV file inside it, for example "
                 f"{os.path.join(path, 'statement.csv')!r}.",
        )

    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with open(path, newline="", encoding=encoding) as handle:
                rows = list(csv.reader(handle))
            break
        except UnicodeDecodeError:
            continue
        except PermissionError:
            raise FriendlyError(
                f"We found {path!r} but could not open it.",
                hint="The file may be open in Excel or another app. Close it "
                     "and try again.",
            ) from None
    else:
        raise FriendlyError(
            f"We could not read {path!r}. It does not look like plain text "
            "in a format we recognize.",
            hint="Bank tools want a plain-text CSV. If your bank gave you a "
                 ".xls or .xlsx file, open it and choose File > Save As > CSV.",
        )

    if not rows:
        raise FriendlyError(
            f"{label} is completely empty - there is nothing to work with.",
            hint="Re-download or re-export the CSV from your bank or "
                 "spreadsheet and try again.",
        )

    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if len(rows) < 2:
        raise FriendlyError(
            f"{label} only has a header row (or is otherwise empty of data).",
            hint="We need at least one transaction row below the header.",
        )

    return label, rows


def _find_column(headers: list[str], aliases: list[str]) -> int:
    lowered = [h.strip().lower() for h in headers]
    for alias in aliases:
        if alias in lowered:
            return lowered.index(alias)
    return -1


def _pick_columns(headers: list[str], label: str, *, allow_split: bool) -> tuple[int, int, int, int]:
    """Return (date_col, desc_col, amount_col, credit_col_or_neg).

    allow_split: bool=True means debit/credit as two columns is OK
    (a ledger usually has one signed amount column).
    """
    date_col = _find_column(headers, DATE_HEADERS)
    desc_col = _find_column(headers, DESC_HEADERS)
    amount_col = _find_column(headers, AMOUNT_HEADERS)
    credit_col = _find_column(headers, CREDIT_HEADERS)
    debit_col = _find_column(headers, DEBIT_HEADERS)

    missing = []
    if date_col == -1:
        missing.append("date")
    if desc_col == -1:
        missing.append("description")
    if amount_col == -1 and debit_col == -1 and credit_col == -1:
        missing.append("amount")

    if missing:
        raise FriendlyError(
            f"We could not find a {'/'.join(missing)} column in {label}.",
            hint="Rename the header so it says exactly one of these: "
                 "date, description, amount (or debit/credit). "
                 f"These are the headers we saw: {', '.join(headers)!r}.",
        )

    if amount_col == -1:
        if credit_col == -1 or debit_col == -1:
            raise FriendlyError(
                f"{label} has one of debit/credit but not the other.",
                hint="Either use a single amount column (debits negative), "
                     "or export with both debit and credit columns.",
            )
        if not allow_split:
            raise FriendlyError(
                f"{label} uses separate debit and credit columns.",
                hint="A ledger works best with a single signed amount column "
                     "(money out is negative, money in is positive).",
            )
        amount_col = debit_col
    return date_col, desc_col, amount_col, credit_col


def load_transactions(path: str, *, split_debit_credit: bool) -> list[Transaction]:
    """Read a CSV into Transactions.

    split_debit_credit=True  -> bank statement (debit/credit columns allowed)
    split_debit_credit=False -> ledger (single signed amount column)
    """
    label, rows = _read_csv_rows(path)
    headers = [h.strip() for h in rows[0]]
    date_col, desc_col, amount_col, credit_col = _pick_columns(
        headers, label, allow_split=split_debit_credit
    )

    transactions: list[Transaction] = []
    for index, row in enumerate(rows[1:], start=2):
        def cell(col: int) -> str:
            try:
                return row[col]
            except IndexError:
                return ""

        try:
            when = parse_date(cell(date_col), index, label)
            description = cell(desc_col).strip() or "(no description)"
            if credit_col == -1:
                amount = parse_amount(cell(amount_col), index, label)
            else:
                debit_text = cell(amount_col).strip()
                credit_text = cell(credit_col).strip()
                if not debit_text and not credit_text:
                    raise FriendlyError(
                        f"Row {index} of {label} has a blank debit and a "
                        "blank credit value.",
                        hint="Fill in one of them (0.00 is fine) and try again.",
                    )
                if debit_text and credit_text:
                    raise FriendlyError(
                        f"Row {index} of {label} has both a debit and a "
                        "credit value. A bank row is one or the other.",
                        hint="Leave the other column blank (or 0.00).",
                    )
                amount = parse_amount(credit_text, index, label) if credit_text \
                    else -abs(parse_amount(debit_text, index, label))
        except FriendlyError:
            raise
        transactions.append(
            Transaction(when=when, description=description,
                        amount=amount, row_number=index, section=label)
        )

    return transactions
