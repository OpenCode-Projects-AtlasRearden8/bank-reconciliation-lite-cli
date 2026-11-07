"""End-to-end tests: the CLI a real person would run."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from bankrecon import cli
STATEMENT_OK = """Date,Description,Debit,Credit
2026-05-01,AMZN MKTP US,39.99,
2026-05-03,NETFLIX,15.49,
2026-05-05,NETFLIX,15.49,
2026-05-07,UBER TRIP,23.40,
2026-05-08,UBER TRIP,23.40,
2026-05-10,Paycheck,,1500.00
"""

LEDGER_OK = """date,description,amount
2026-05-01,Amazon order,-39.99
2026-05-03,Netflix,-15.49
2026-05-07,Uber,-23.40
2026-05-10,Paycheck,1500.00
"""


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def statement(tmp_path):
    return write(tmp_path, "statement.csv", STATEMENT_OK)


@pytest.fixture
def ledger(tmp_path):
    return write(tmp_path, "ledger.csv", LEDGER_OK)


class TestRun:
    def test_returns_report(self, statement, ledger):
        report, args = cli.run([str(statement), str(ledger)])
        assert "BANK RECONCILIATION REPORT" in report
        assert "Netflix" in report  # subscription finding
        assert "double charge" in report.lower()
        assert "no ledger match" in report.lower()

    def test_counts_in_report(self, statement, ledger):
        report, _ = cli.run([str(statement), str(ledger)])
        assert "Statement: statement.csv (6 rows)" in report

    def test_output_file(self, tmp_path, statement, ledger):
        out = tmp_path / "report.txt"
        code = cli.main([str(statement), str(ledger), "--output", str(out)])
        assert code == 0
        assert out.read_text(encoding="utf-8").count("\n") > 1

    def test_day_window_flag(self, statement, ledger):
        report, _ = cli.run(
            [str(statement), str(ledger), "--day-window", "0"]
        )
        assert "Date tolerance: 0 day(s)" in report

    def test_negative_window_is_friendly(self, statement, ledger):
        with pytest.raises(cli.FriendlyError):
            cli.run([str(statement), str(ledger), "--day-window", "-1"])

    def test_missing_file_is_friendly(self):
        with pytest.raises(cli.FriendlyError) as excinfo:
            cli.run(["ghost.csv", "also-ghost.csv"])
        assert "could not find" in str(excinfo.value.headline).lower()

    def test_bad_headers_are_friendly(self, tmp_path):
        bad = write(tmp_path, "weird.csv", "col1,col2\na,b\n")
        with pytest.raises(cli.FriendlyError) as excinfo:
            cli.run([str(bad), str(bad)])
        assert "column" in str(excinfo.value.headline).lower()

    def test_bad_amount_row_is_friendly(self, tmp_path):
        bad = write(
            tmp_path, "broken.csv",
            "date,description,amount\n2026-05-01,Coffee,nantucket\n",
        )
        ledger = write(tmp_path, "ledger.csv", LEDGER_OK)
        with pytest.raises(cli.FriendlyError) as excinfo:
            cli.run([str(bad), str(ledger)])
        assert "amount" in str(excinfo.value.headline).lower()


class TestMainExitCodes:
    def test_success_is_zero(self, statement, ledger, capsys):
        assert cli.main([str(statement), str(ledger)]) == 0
        out = capsys.readouterr().out
        assert "BANK RECONCILIATION REPORT" in out

    def test_error_is_two(self, capsys):
        assert cli.main(["ghost.csv", "ghost2.csv"]) == 2
        err_text = capsys.readouterr().out
        assert "How to fix it" in err_text


class TestInstalledConsoleScript:
    def test_python_dash_m(self, statement, ledger):
        proc = subprocess.run(
            [sys.executable, "-m", "bankrecon", str(statement), str(ledger)],
            capture_output=True, text=True,
            cwd=Path(__file__).resolve().parents[1] / "src",
        )
        assert proc.returncode == 0
        assert "BANK RECONCILIATION REPORT" in proc.stdout

    def test_version(self):
        proc = subprocess.run(
            [sys.executable, "-m", "bankrecon", "--version"],
            capture_output=True, text=True,
            cwd=Path(__file__).resolve().parents[1] / "src",
        )
        assert proc.returncode == 0
        assert proc.stdout.strip() == cli.__version__
