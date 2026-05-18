#!/usr/bin/env python3
# Copyright Advanced Micro Devices, Inc.
# SPDX-License-Identifier: MIT

"""
Detects failed teatime build logs, renames them so they sort first in CI
artifacts/log listings, and appends a concise failure summary to the
GitHub Actions job summary.

A log is considered failed if it contains an END line with a non-zero
exit code, matching the same behavior previously implemented with grep.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

# Same meaning as:
# grep -l $'END\t[0-9.]*\t[0-9.]*\t[1-9][0-9]*$' "$LOGS"/*.log
FAILED_END_RE = re.compile(r"^END\t[0-9.]*\t[0-9.]*\t[1-9][0-9]*$")


def find_failed_logs(log_dir: Path) -> list[Path]:
    """Return all *.log files whose contents include a failed END line."""
    failed: list[Path] = []

    for path in sorted(log_dir.glob("*.log")):
        try:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if FAILED_END_RE.match(line.rstrip("\n")):
                        failed.append(path)
                        break
        except OSError:
            # Match the shell behavior of ignoring unreadable files.
            continue

    return failed


def rename_with_sudo(src: Path, dst: Path) -> None:
    """
    Rename like: sudo mv src dst
    Falls back to a normal rename if sudo is unavailable or not needed.
    """
    try:
        subprocess.run(
            ["sudo", "mv", str(src), str(dst)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        src.rename(dst)


def main() -> int:
    logs_dir = Path(os.environ["OUTPUT_DIR"]) / "build" / "logs"
    summary_path = Path(os.environ["GITHUB_STEP_SUMMARY"])

    failed_logs = find_failed_logs(logs_dir)

    if not failed_logs:
        print("No failed log found.")
        return 0

    with summary_path.open("a", encoding="utf-8") as summary:
        summary.write("## Build failure\n")
        summary.write(f"**Error logs:** {len(failed_logs)}\n")
        summary.write("\n")

        for src in failed_logs:
            dst = src.with_name(f"0.error.{src.name}")
            try:
                rename_with_sudo(src, dst)
                print(f"Renamed {src.name} -> {dst.name}")
                summary.write(f"- `{dst.name}`\n")
                summary.write("\n")
            except OSError as e:
                print(f"Failed to rename {src}: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
