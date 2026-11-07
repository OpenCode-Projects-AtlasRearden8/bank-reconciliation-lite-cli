"""bankrecon - a calm monthly bank-reconciliation ritual.

Import a bank statement CSV, match it against your own ledger CSV,
and print a plain-English report flagging:
  * forgotten subscriptions
  * possible double charges
  * entries that only exist in one place

Everything happens offline on plain CSV files. No bank logins, ever.

Copyright (c) 2026 Asdale Dynamics, LLC
"""

__version__ = "0.1.0"
