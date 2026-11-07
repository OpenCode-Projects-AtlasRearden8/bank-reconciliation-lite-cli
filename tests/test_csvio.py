"""Tests for picking columns and reading rows, the boring-but-vital part."""

from __future__ import annotations

from datetime import date

import pytest

from bankrecon.csvio import load_transactions, _pick_columns
from bankrecon.models import FriendlyError
from bankrecon.parsing import parse_amount, parse_date


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


class TestAmount:
    def test_plain(self):
        assert parse_amount("15.49", 2, "f.csv") == 15.49

    def test_negative(self):
        assert parse_amount("-15.49", 2, "f.csv") == -15.49

    def test_trailing_minus(self):
        assert parse_amount("15.49-", 2, "f.csv") == -15.49

    def test_parentheses(self):
        assert parse_amount("(15.49)", 2, "f.csv") == -15.49

    def test_dollar_and_commas(self):
        assert parse_amount("$1,234.56", 2, "f.csv") == 1234.56

    def test_blank_is_friendly(self):
        with pytest.raises(FriendlyError):
            parse_amount("   ", 3, "ledger.csv")


class TestDate:
    def test_iso(self):
        assert parse_date("2026-01-15", 2, "f.csv") == date(2026, 1, 15)

    def test_us_slashes(self):
        assert parse_date("1/15/2026", 2, "f.csv") == date(2026, 1, 15)

    def test_two_digit_year(self):
        assert parse_date("3/2/96", 2, "f.csv") == date(1996, 3, 2)

    def test_month_name(self):
        assert parse_date("Jan 15 2026", 2, "f.csv") == date(2026, 1, 15)

    def test_garbage_is_friendly(self):
        with pytest.raises(FriendlyError) as excinfo:
            parse_date("yesterday", 5, "statement.csv")
        assert "row 5" in str(excinfo.value.headline).lower()


class TestColumnPicking:
    def test_standard(self):
        assert _pick_columns(
            ["Date", "Description", "Amount"], "f.csv", allow_split=True
        ) == (0, 1, 2, -1)

    def test_debit_credit_statement(self):
        date_col, desc_col, amount_col, credit_col = _pick_columns(
            ["Posted Date", "Payee", "Debit", "Credit"], "f.csv", allow_split=True
        )
        assert date_col == 0
        assert desc_col == 1
        assert amount_col == 2  # the debit side
        assert credit_col == 3

    def test_ledger_rejects_split(self):
        with pytest.raises(FriendlyError):
            _pick_columns(["Date", "Desc", "Debit", "Credit"], "f.csv",
                          allow_split=False)

    def test_missing_amount_is_friendly(self):
        with pytest.raises(FriendlyError) as excinfo:
            _pick_columns(["Date", "Description", "Notes"], "f.csv",
                          allow_split=True)
        assert "amount" in str(excinfo.value.headline).lower()


class TestLoadTransactions:
    def test_statement_with_debit_credit(self, tmp_path):
        path = write(
            tmp_path, "statement.csv",
            "Date,Description,Debit,Credit\n"
            "2026-05-01,GROCERY STORE,42.10,\n"
            "05/02/2026,Paycheck,,1500.00\n",
        )
        rows = load_transactions(path, split_debit_credit=True)
        assert len(rows) == 2
        assert rows[0].amount == -42.10
        assert rows[0].when == date(2026, 5, 1)
        assert rows[1].amount == 1500.00

    def test_ledger_single_column(self, tmp_path):
        path = write(
            tmp_path, "ledger.csv",
            "date,description,amount\n"
            "2026-05-01,Groceries,-42.10\n"
            "2026-05-02,Paycheck,1500.00\n",
        )
        rows = load_transactions(path, split_debit_credit=False)
        assert [r.amount for r in rows] == [-42.10, 1500.00]

    def test_missing_file_is_friendly(self):
        with pytest.raises(FriendlyError) as excinfo:
            load_transactions("/nowhere/no.csv", split_debit_credit=True)
        assert "could not find" in str(excinfo.value.headline).lower()

    def test_empty_file_is_friendly(self, tmp_path):
        path = write(tmp_path, "empty.csv", "")
        with pytest.raises(FriendlyError):
            load_transactions(path, split_debit_credit=True)

    def test_only_header_is_friendly(self, tmp_path):
        path = write(tmp_path, "h.csv", "date,description,amount\n")
        with pytest.raises(FriendlyError):
            load_transactions(path, split_debit_credit=True)

    def test_bom_survives(self, tmp_path):
        path = write(
            tmp_path, "bom.csv",
            "date,description,amount\n2026-05-01,Coffee,-4.50\n",
        )
        rows = load_transactions(path, split_debit_credit=True)
        assert rows[0].amount == -4.50
