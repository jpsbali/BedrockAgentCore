"""Test Module 5: CLI end-to-end — runs the full pipeline against deployed agents."""

import os
import subprocess
import sys

sys.path.insert(0, ".")
from tests.helpers import (
    console, print_header, print_error, print_assertions_table,
)

PDF_PATH = "sample_data/input/sample_documents.pdf"


def main():
    print_header("Module 5: CLI End-to-End", "remote")

    if not os.path.exists(PDF_PATH):
        print_error(f"PDF not found: {PDF_PATH}")
        sys.exit(1)

    console.print("[bold]Running CLI pipeline (this may take 3-5 minutes)...[/bold]\n")

    result = subprocess.run(
        [sys.executable, "cli/cli.py", PDF_PATH],
        capture_output=True, text=True, timeout=600,
    )

    console.print(result.stdout)
    if result.stderr:
        console.print(f"[dim]{result.stderr}[/dim]")

    checks = []
    checks.append(("CLI exited successfully", result.returncode == 0, f"exit code {result.returncode}"))
    checks.append(("Output contains extraction", "document extraction" in result.stdout.lower() or "extract" in result.stdout.lower(), ""))
    checks.append(("Output contains KYC", "kyc" in result.stdout.lower(), ""))
    checks.append(("Output contains recommendation", "recommend" in result.stdout.lower() or "analysis" in result.stdout.lower(), ""))
    checks.append(("Output contains completion", "complete" in result.stdout.lower(), ""))

    # Check artifacts were saved
    artifacts_exist = "artifacts" in result.stdout.lower() or any(
        d.startswith("artifacts") for d in os.listdir(".") if os.path.isdir(d)
    )
    checks.append(("Artifacts saved", artifacts_exist, ""))

    print_assertions_table(checks)

    if not all(p for _, p, _ in checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
