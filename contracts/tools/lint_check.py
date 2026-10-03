"""Run vacuum with the contract lint ruleset over the written bundles, and refuse to pass on nothing (FR-015).

vacuum itself exits 0 when the ruleset is empty, when it loads no rule, or when it was handed no file, so this
wrapper makes each of those a failure instead of a pass. It lints every ``--file`` and every
``<DIR>/bundle/<module>/openapi.yaml`` found under ``--bundles DIR`` with ``--ruleset``
(default ``contracts/lint/ruleset.yaml``), using the ``vacuum`` binary on ``PATH`` (installed from the pinned,
checksum-verified release by ``install_tools.py``; its checksum is verified before it can run).

A result of any severity is a violation (exit 1), printed as
``CONTRACT-CHECK lint_check: LINT_VIOLATION: <file>: <rule>: <path>: <message>``.

Cannot do its job (exit 2): ``RULESET_MISSING``, ``RULESET_EMPTY`` (no rule that is switched on), ``VACUUM_MISSING``,
``ZERO_FILES`` (no file to lint, or a named file is absent), ``ZERO_RULES_LOADED`` (the binary reports zero rules),
``RULES_LOADED_MISMATCH`` (it loaded another number than the ruleset holds) and ``VACUUM_FAILED`` (no report).
The last line is always ``counts: files=N rules=N violations=N``.

Run as a bare script (``python contracts/tools/lint_check.py --bundles DIR``). Standard library and PyYAML.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CHECK_NAME = "lint_check"
DEFAULT_RULESET = Path("contracts/lint/ruleset.yaml")
BUNDLE_DIRECTORY = "bundle"
BUNDLE_FILE = "openapi.yaml"
COMMAND_TIMEOUT_SECONDS = 600
RULES_LOADED = re.compile(r"containing (\d+) rules")
SWITCHED_OFF = (False, "off")
DETAIL_LIMIT = 300

Runner = Callable[[Sequence[str]], tuple[int, str, str]]
Which = Callable[[str], str | None]


def subprocess_runner(command: Sequence[str]) -> tuple[int, str, str]:
    """Run ``command`` (an argument list, never a shell string) and return ``(status, stdout, stderr)``."""
    completed = subprocess.run(  # noqa: S603 -- argument list built here, binary resolved with shutil.which, no shell
        list(command), capture_output=True, text=True, timeout=COMMAND_TIMEOUT_SECONDS, check=False
    )
    return completed.returncode, completed.stdout, completed.stderr


class CannotRun(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass
class Report:
    violations: list[str] = field(default_factory=list)
    files: int = 0
    rules: int = 0

    def counts_line(self) -> str:
        return f"counts: files={self.files} rules={self.rules} violations={len(self.violations)}"


def switched_on_rules(ruleset: Path) -> int:
    """How many rules the ruleset file switches on. Raises ``CannotRun`` when it is missing or holds none."""
    if not ruleset.is_file():
        raise CannotRun("RULESET_MISSING", f"{ruleset} does not exist")
    try:
        loaded: Any = yaml.safe_load(ruleset.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise CannotRun("RULESET_EMPTY", f"{ruleset} is not readable YAML: {type(error).__name__}") from error
    rules = loaded.get("rules") if isinstance(loaded, dict) else None
    count = sum(1 for body in rules.values() if body not in SWITCHED_OFF) if isinstance(rules, dict) else 0
    if count == 0:
        raise CannotRun("RULESET_EMPTY", f"{ruleset} switches on no rule")
    return count


def files_to_lint(bundles: Path | None, listed: Sequence[Path]) -> list[Path]:
    found = sorted((bundles / BUNDLE_DIRECTORY).glob(f"*/{BUNDLE_FILE}")) if bundles is not None else []
    files = [*found, *listed]
    absent = [path for path in files if not path.is_file()]
    if not files or absent:
        where = f"under {bundles / BUNDLE_DIRECTORY}" if bundles is not None else "named"
        raise CannotRun("ZERO_FILES", f"no file to lint {where}" if not files else f"file not found: {absent[0]}")
    return files


def check_rules_loaded(runner: Runner, vacuum: str, ruleset: Path, sample: Path, expected: int) -> None:
    """Ask the binary how many rules it loads from ``ruleset`` and compare with what the file holds."""
    _, stdout, stderr = runner([vacuum, "lint", str(sample), "-r", str(ruleset), "-d", "-b", "-q", "--no-update-check", "-n", "none"])
    match = RULES_LOADED.search(stdout + stderr)
    loaded = int(match.group(1)) if match else 0
    if loaded == 0:
        raise CannotRun("ZERO_RULES_LOADED", f"vacuum loaded no rule from {ruleset}")
    if loaded != expected:
        raise CannotRun("RULES_LOADED_MISMATCH", f"vacuum loaded {loaded} rules from {ruleset}, which switches on {expected}")


def results_for(runner: Runner, vacuum: str, ruleset: Path, file: Path) -> list[dict[str, Any]]:
    status, stdout, stderr = runner([vacuum, "spectral-report", str(file), "-r", str(ruleset), "-o", "-q", "--no-update-check"])
    try:
        results = json.loads(stdout)
    except ValueError as error:
        raise CannotRun("VACUUM_FAILED", f"vacuum exited {status} without a report for {file}: {(stderr or stdout).strip()[:DETAIL_LIMIT]}") from error
    if not isinstance(results, list):
        raise CannotRun("VACUUM_FAILED", f"vacuum printed a report that is not a list for {file}")
    return [result for result in results if isinstance(result, dict)]


def violation_lines(file: Path, results: Sequence[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    seen: set[tuple[str, str]] = set()
    for result in results:
        rule = str(result.get("code", "?"))
        path = "/".join(str(part) for part in result.get("path", []))
        if (rule, path) in seen:
            continue
        seen.add((rule, path))
        message = str(result.get("message", "")).replace("\n", " ")[:DETAIL_LIMIT]
        lines.append(f"CONTRACT-CHECK {CHECK_NAME}: LINT_VIOLATION: {file}: {rule}: {path}: {message}")
    return lines


def run(argv: Sequence[str] | None = None, *, runner: Runner = subprocess_runner, which: Which = shutil.which, out: Callable[[str], None] = print) -> int:
    parser = argparse.ArgumentParser(description="Lint the contract bundles with vacuum.")
    parser.add_argument("--ruleset", default=DEFAULT_RULESET, type=Path)
    parser.add_argument("--bundles", type=Path, default=None, help="a directory holding bundle/<module>/openapi.yaml")
    parser.add_argument("--file", action="append", type=Path, default=[], help="lint this file (repeatable)")
    args = parser.parse_args(argv)

    report = Report()
    try:
        report.rules = switched_on_rules(args.ruleset)
        vacuum = which("vacuum")
        if vacuum is None:
            raise CannotRun("VACUUM_MISSING", "no vacuum on PATH (run install_tools.py --only vacuum first)")
        files = files_to_lint(args.bundles, args.file)
        check_rules_loaded(runner, vacuum, args.ruleset, files[0], report.rules)
        for file in files:
            report.violations.extend(violation_lines(file, results_for(runner, vacuum, args.ruleset, file)))
            report.files += 1
    except CannotRun as error:
        out(f"CONTRACT-CHECK {CHECK_NAME}: {error.code}: {error.detail}")
        out(report.counts_line())
        return 2
    for line in report.violations:
        out(line)
    out(report.counts_line())
    return 1 if report.violations else 0


if __name__ == "__main__":
    sys.exit(run())
