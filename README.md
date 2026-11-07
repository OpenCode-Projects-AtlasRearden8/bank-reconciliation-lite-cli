# bank-reconciliation-lite

Turn bank-CSV dread into a calm monthly ritual. `bankrecon` imports a bank
statement CSV, matches the rows against your own ledger or spreadsheet export,
and prints a clear, plain-English reconciliation report.

It flags the three things people dread finding:

- **Forgotten subscriptions** - the same merchant quietly charging you
  month after month while your ledger never mentions it
- **Possible double charges** - two identical charges a day or two apart
- **Unmatched entries** - rows that exist only in the statement or only in
  your ledger (forgotten to record, or still pending)

Everything works **offline on plain CSV files**. No bank logins, no accounts,
no network. If something goes wrong, the error tells you what happened and
how to fix it - in plain English, like a friend would explain it.

Built by [Asdale Dynamics, LLC](https://dylanasdale.github.io) as one of our
beginner-friendly, local-first tools.

## Install

You just need Python 3.10+:

```bash
pip install .
```

That gives you the `bankrecon` command. Prefer not to install anything?

```bash
python -m bankrecon <statement.csv> <ledger.csv>
```

Both styles do exactly the same thing. To run the tests instead:

```bash
pip install .[dev]
pytest
```

## Usage

```bash
bankrecon may-statement.csv my-ledger.csv
```

Example output:

```
BANK RECONCILIATION REPORT
============================================================
Statement: may-statement.csv (6 rows)
Ledger:    my-ledger.csv (4 rows)
Matched:   4 of 6 statement rows

Matched 4 rows:
  Matched: 2026-05-01  'AMZN MKTP US'  -39.99 == 2026-05-01  'Amazon order'  -39.99
  ...

WHAT NEEDS YOUR ATTENTION
------------------------------------------------------------
! Possible double charge(s) - worth a call to the merchant
    Charged 23.40 twice (1 day(s) apart) - ...
! Possible subscription(s) your ledger forgot about
    'NETFLIX' charged 15.49 on 2026-05-03, 2026-05-05 (2 times) ...
! 1 statement entry with no ledger match
    ...
```

### Options

| Flag | What it does |
| --- | --- |
| `-d, --day-window DAYS` | Max days between two rows matched by amount alone (default 3). `0` = same day only. |
| `-o, --output FILE` | Also save the report to a text file. |
| `--version` | Show the version. |

## What your CSVs need

**Statement** (from your bank): columns named `date`, `description`, and
`amount` - or `debit` and `credit` columns, which many banks use.

**Ledger** (yours): columns named `date`, `description`, `amount`, where
money out is negative and money in is positive.

Header names are matched case-insensitively, and common aliases like
`posted date`, `payee`, or `detail` work too. Amounts may include `$`,
commas, `(parentheses)`, or a trailing minus, all common bank styles. Dates
may be `2026-01-15`, `1/15/2026` (US month-first), or `Jan 15 2026`.

If a column or a row cannot be read, the tool stops and tells you which row
and what to rename or fix - it never silently skips data.

## How the matching works

The matcher runs in three passes, and a statement row can only match one
ledger row:

1.Amount + day + similar description -> exact
2. Amount + day -> exact
3. Amount within `--day-window` days -> close (flagged in the report so you
   can double-check)

Then it looks for double charges (same amount and merchant within 3 days)
and forgotten subscriptions (same amount and merchant, 5+ days apart,
appearing at least twice, never in your ledger).

## Privacy

Your CSVs never leave your computer. There is no network code in this tool
at all - you can run it on a machine with Wi-Fi turned off.

## Related tools from Asdale Dynamics, LLC

- **cashflow-simple-ledger** - keep an income/expense ledger (this tool's
  perfect pairing: ledger there, reconcile here)
- **csv-cleanup-companion** - clean messy CSVs before bringing them here

## License

MIT - see [LICENSE](LICENSE). Copyright (c) 2026 Asdale Dynamics, LLC.
