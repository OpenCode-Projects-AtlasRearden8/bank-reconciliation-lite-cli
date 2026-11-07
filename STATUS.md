# STATUS.md - bank-reconciliation-lite

## What was built

`bankrecon`, a Python 3 CLI (pure standard library) that turns bank-CSV
reconciliation into a calm monthly ritual:

- Imports a bank statement CSV (single `amount` column, or separate
  `debit`/`credit` columns; `$`, commas, `(parens)`, trailing minus, and
  several common date formats all accepted).
- Matches rows against your own ledger/export CSV (`date`, `description`,
  `amount` with money-out negative) in three passes: exact amount + day +
  description, exact amount + day, amount within a day window (flagged as
  "close" so you double-check).
- Prints a plain-English report flagging:
  - **forgotten subscriptions** (same merchant/amount charged twice or more,
    5+ days apart, never in your ledger),
  - **possible double charges** (identical charges within 3 days),
  - **unmatched statement entries** and **unmatched ledger entries**.
- Friendly, actionable errors for missing files, unreadable amounts/dates,
  empty files, unrecognizable headers, and bad options - each with a
  "How to fix it" hint. Works fully offline; no bank logins, no network code.

Layout: `src/bankrecon/{cli,csvio,matching,parsing,report,models}.py`,
console script `bankrecon` plus `python -m bankrecon`, tests in `tests/`.

## How to run it

```bash
pip install .            # then:
bankrecon statement.csv ledger.csv
bankrecon statement.csv ledger.csv --day-window 0 --output report.txt

# without installing:
python -m bankrecon statement.csv ledger.csv
```

## Verification results

- `pytest` (Python 3.13.5, pytest 9.1.1): **49 passed, 0 failed**,
  covering parsing, column detection, all three matching passes,
  double-charge and subscription detection, report output, the CLI
  (exit codes, `--output`, friendly errors), and `python -m`.
- Clean-venv check: `python -m venv` + `pip install -e ".[dev]"` +
  `pip wheel` all succeed; `bankrecon --version` -> `0.1.0`
  (wheel: `bankrecon-0.1.0-py3-none-any.whl`).
- End-to-end demo (dataset with a forgotten Netflix subscription, an Uber
  double charge, an unmatched charge, and a scheduled ledger row dated
  ahead): report correctly matched 3 of 6 statement rows and flagged all
  four issues with sensible wording.
- Deliberately broken inputs (missing file, unaligned columns, garbage
  amount) each produced the intended plain-English error and exit code 2.

## Known gaps

- Date parsing assumes US month-first order for numeric dates
  (2/3/2026 = Feb 3); ISO `YYYY-MM-DD` is unambiguous and recommended.
- No running balance check, account filtering, multi-statement merging,
  fuzzy amount matching (e.g., currency conversion), or Markdown output;
  `--output` writes plain text only.
- Duplicate detection compares normalized descriptions, so very different
  merchant labels for the same double charge can be missed.
- Only CSV; no `.xlsx`, QIF, or OFX (the error hint explains how to convert).
- No persistence of matched marks between runs - each run is a fresh report.
- Each CSV is read as one account; mixed multi-account exports are not split.
