"""Tests for the matching brain and the report words."""

from __future__ import annotations

from datetime import date

from bankrecon.matching import (
    build_findings,
    find_double_charges,
    find_subscription_charges,
    normalize_description,
    reconcile,
)
from bankrecon.models import Transaction


def txn(day, desc, amount, row=1, month=5):
    return Transaction(date(2026, month, day), desc, amount, row, "s.csv")


def ledger_txn(day, desc, amount, row=1, month=5):
    return Transaction(date(2026, month, day), desc, amount, row, "l.csv")


class TestNormalize:
    def test_strips_bank_noise(self):
        assert normalize_description("AMZN MKTP US*2Y34A 12345") == \
            normalize_description("amzn mktp us")

    def test_simple(self):
        assert normalize_description("Netflix") == "NETFLIX"


class TestReconcile:
    def test_all_matched(self):
        statement = [txn(1, "GROCERY STORE", -42.10),
                     txn(2, "Paycheck DEP", 1500.00)]
        ledger = [ledger_txn(1, "Groceries", -42.10),
                  ledger_txn(2, "Paycheck", 1500.00)]
        matches, s_only, l_only, dupes, subs = reconcile(statement, ledger)
        assert len(matches) == 2
        assert not s_only and not l_only and not dupes and not subs
        assert all(m.confidence == "exact" for m in matches)

    def test_close_match_within_window(self):
        statement = [txn(3, "COFFEE SHOP", -4.50)]
        ledger = [ledger_txn(5, "Coffee", -4.50)]
        matches, s_only, l_only, _, _ = reconcile(statement, ledger, day_window=3)
        assert len(matches) == 1
        assert matches[0].confidence == "close"
        assert not s_only and not l_only

    def test_no_match_beyond_window(self):
        statement = [txn(3, "COFFEE", -4.50)]
        ledger = [ledger_txn(15, "Coffee", -4.50)]
        matches, s_only, l_only, _, _ = reconcile(statement, ledger, day_window=3)
        assert not matches
        assert len(s_only) == 1 and len(l_only) == 1

    def test_each_row_used_once(self):
        statement = [txn(1, "COFFEE", -4.50), txn(5, "COFFEE", -4.50)]
        ledger = [ledger_txn(4, "Coffee", -4.50)]
        matches, s_only, l_only, _, _ = reconcile(statement, ledger)
        assert len(matches) == 1
        assert len(s_only) == 1 and len(l_only) == 0

    def test_description_not_required_for_exact(self):
        statement = [txn(1, "TOTALLY DIFFERENT WORDS", -10.00)]
        ledger = [ledger_txn(1, "same day other words", -10.00)]
        matches, s_only, l_only, _, _ = reconcile(statement, ledger)
        assert len(matches) == 1 and not s_only and not l_only


class TestDoubleCharges:
    def test_same_amount_close_dates(self):
        first, second = txn(10, "UBER", -23.40, row=1), txn(11, "UBER", -23.40, row=2)
        pairs = find_double_charges([first, second])
        assert pairs == [(first, second)]

    def test_same_day(self):
        pairs = find_double_charges(
            [txn(10, "UBER", -23.40, row=1), txn(10, "UBER", -23.40, row=2)]
        )
        assert len(pairs) == 1

    def test_far_apart_is_not_double(self):
        pairs = find_double_charges(
            [txn(1, "UBER", -23.40, row=1), txn(20, "UBER", -23.40, row=2)]
        )
        assert not pairs

    def test_different_merchant_is_not_double(self):
        pairs = find_double_charges(
            [txn(10, "UBER", -23.40, row=1), txn(11, "LYFT", -23.40, row=2)]
        )
        assert not pairs


class TestSubscriptions:
    def test_two_repeats_flagged(self):
        rows = [txn(3, "NETFLIX", -15.49, row=1),
                txn(28, "NETFLIX", -15.49, row=2)]
        flagged = find_subscription_charges(rows)
        assert flagged == rows

    def test_single_charge_not_flagged(self):
        assert not find_subscription_charges([txn(3, "NETFLIX", -15.49, row=1)])

    def test_repeats_close_together_not_flagged(self):
        # two repeats within one 5-day span look like one billing cycle, not a habit
        rows = [txn(3, "NETFLIX", -15.49, row=1),
                txn(6, "NETFLIX", -15.49, row=2)]
        assert not find_subscription_charges(rows)


class TestFindings:
    def test_clean_report(self):
        findings = build_findings(
            matches=[], statement_only=[], ledger_only=[],
            duplicate_pairs=[], subscription_rows=[],
        )
        assert findings[0].title.startswith("All clear")

    def test_attention_severities_present(self):
        findings = build_findings(
            matches=[],
            statement_only=[txn(3, "MYSTERY", -9.99)],
            ledger_only=[ledger_txn(4, "PENDING", -50)],
            duplicate_pairs=[(txn(10, "UBER", -23.40, row=1),
                              txn(11, "UBER", -23.40, row=2))],
            subscription_rows=[txn(3, "NETFLIX", -15.49, row=3),
                               txn(28, "NETFLIX", -15.49, row=4)],
        )
        titles = " ".join(f.title for f in findings)
        assert "double charge" in titles.lower()
        assert "subscription" in titles.lower()
        assert "no ledger match" in titles.lower()
        assert "not on the statement" in titles.lower()
        assert all(f.severity == "attention" for f in findings)
