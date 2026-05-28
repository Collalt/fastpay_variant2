from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LOG_PATH = ROOT / "docs" / "test-log.txt"


def run_and_stream(command: list[str], *, append: bool) -> int:
    mode = "a" if append else "w"
    with LOG_PATH.open(mode, encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            log_file.write(line)
        return process.wait()


def print_banner() -> None:
    print()
    print("+" + "-" * 86 + "+")
    print("| FASTPAY VARIANT 2 DEMO RUN".ljust(87) + "|")
    print("| Integration tests: real HTTP API + mocked external bank gateway".ljust(87) + "|")
    print("| Output is also saved to docs/test-log.txt".ljust(87) + "|")
    print("+" + "-" * 86 + "+")
    print()


def main() -> int:
    LOG_PATH.parent.mkdir(exist_ok=True)
    print_banner()

    checklist_status = run_and_stream([sys.executable, "-m", "tests.demo_checklist"], append=False)
    if checklist_status != 0:
        return checklist_status

    pytest_status = run_and_stream(
        [sys.executable, "-m", "pytest", "-vv", "-s", "--tb=short"],
        append=True,
    )

    print()
    print("+" + "-" * 86 + "+")
    if pytest_status == 0:
        print("| DEMO RESULT: all FastPay checks passed".ljust(87) + "|")
    else:
        print("| DEMO RESULT: some FastPay checks failed".ljust(87) + "|")
    print(f"| Full log: {LOG_PATH}".ljust(87) + "|")
    print("+" + "-" * 86 + "+")
    return pytest_status


if __name__ == "__main__":
    raise SystemExit(main())
