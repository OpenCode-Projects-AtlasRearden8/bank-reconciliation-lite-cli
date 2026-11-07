"""Command-line interface: python -m bankrecon statement.csv ledger.csv"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .csvio import load_transactions
from .matching import DEFAULT_DAY_WINDOW, build_findings, reconcile
from .models import FriendlyError
from .report import format_report, write_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bankrecon",
        description=(
            "Reconcile a bank statement CSV against your own ledger CSV. "
            "Works offline on plain files; no bank logins, ever."
        ),
        epilog=(
            "Example: bankrecon may-statement.csv my-ledger.csv\n"
            "Statement rows want: date, description, amount "
            "(or debit/credit). Ledger rows want: date, description, amount."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("statement", help="your bank's exported CSV")
    parser.add_argument("ledger", help="your own ledger or spreadsheet export CSV")
    parser.add_argument(
        "-d", "--day-window", type=int, default=DEFAULT_DAY_WINDOW,
        metavar="DAYS",
        help=f"max days between an amount-only match (default {DEFAULT_DAY_WINDOW})",
    )
    parser.add_argument(
        "-o", "--output", metavar="FILE",
        help="also save the report to a text file",
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def run(argv: list[str] | None = None) -> tuple[str, argparse.Namespace]:
    """Do the whole job. Returns (report text, parsed args)."""
    args = build_parser().parse_args(argv)

    if args.day_window < 0:
        raise FriendlyError(
            "--day-window cannot be negative.",
            hint="0 means 'only match rows dated the same day'. "
                 "3 (the default) is usually right.",
        )

    statement = load_transactions(args.statement, split_debit_credit=True)
    ledger = load_transactions(args.ledger, split_debit_credit=False)

    if not statement:
        raise FriendlyError(
            f"{args.statement} has no transaction rows.",
            hint="Download a fresh CSV from your bank (with rows!) and retry.",
        )
    if not ledger:
        raise FriendlyError(
            f"{args.ledger} has no transaction rows.",
            hint="Export your ledger with at least one row and retry.",
        )

    matches, statement_only, ledger_only, dupes, subs = reconcile(
        statement, ledger, day_window=args.day_window
    )
    findings = build_findings(matches, statement_only, ledger_only, dupes, subs)

    return format_report(
        statement_label=args.statement,
        ledger_label=args.ledger,
        day_window=args.day_window,
        matches=matches,
        findings=findings,
        statement_count=len(statement),
        ledger_count=len(ledger),
    ), args


def main(argv: list[str] | None = None) -> int:
    try:
        report, args = run(argv)
    except FriendlyError as error:
        print(f"\n{error.headline}")
        if error.hint:
            print(f"\nHow to fix it: {error.hint}")
        return 2
    print(report)
    if args.output:
        try:
            write_report(report, args.output)
            print(f"Report saved to {args.output}")
        except OSError as error:
            print(f"Could not save {args.output}: {error}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
