#!/usr/bin/env python3
"""Completeness, row-shape and churn-fidelity checker for the #2631 parity verdict catalog.

WP12 of mission ratchet-baseline-census-gate-remediation-01M3EW3Z (FR-018, NFR-006, SC-005).

Stdlib only. Not a committed test: it lives under ``kitty-specs/*/research/**``,
which ``ruff.toml`` excludes and CI never collects.

Usage::

    python kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/parity_catalog_check.py \
        --base 3717c7ea

The **expected set** comes from ``git ls-tree -r <base> -- tests`` (never the
working tree), so later deletions/renames (WP09, WP10) do not move it. The
**churn reference** is the Part 2 table of ``grounding-2631_2972.md`` unless the
catalog header documents a re-measure (a line starting ``Re-measured churn:``
that names both ``window=`` and ``HEAD=``).

Exit 0 and print ``45/45 OK`` only when every check passes.
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_CATALOG = HERE / "parity-verdicts.md"
DEFAULT_GROUNDING = HERE / "grounding-2631_2972.md"
DEFAULT_BASE = "3717c7ea"
EXPECTED_COUNT = 45
EXCLUDED_PREFIX = "tests/_support/coverage_safety/"
SWEEP_PATTERNS = ("*parity*.py", "*equivalence*.py")

CHURN_COLUMNS = ("all", "src", "mass", "pcm", "pcsrc")
NA_CHURN = "n/a (shallow)"
REQUIRED_COLUMNS = (
    "suite",
    "category",
    "pins invariant or shape?",
    *CHURN_COLUMNS,
    "verdict",
    "surviving enforcer / NFR-006 proof",
    "empty-target behaviour",
    "owning WP / follow-up",
    "note",
)
VERDICTS = frozenset(
    {
        "keep",
        "keep (retire 1 test)",
        "keep + consolidate",
        "convert",
        "retire",
        "retire + relocate",
        "split",
        "consolidate (deferred)",
        "fix + retire parts",
    }
)
ENFORCER_TRIGGERS = ("retire", "convert", "split")
EMPTY_TARGET_TRIGGERS = ("ban", "scan")
REMEASURE_MARKER = "Re-measured churn:"


class Report:
    """Collects named failures; one line per failure."""

    def __init__(self) -> None:
        self.failures: list[str] = []

    def fail(self, check: str, detail: str) -> None:
        self.failures.append(f"FAIL [{check}] {detail}")


def _git_repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=HERE, capture_output=True, text=True, check=True
    )
    return Path(out.stdout.strip())


def expected_set(base: str, report: Report) -> set[str]:
    """Sweep set at ``base``: ``*parity*.py`` / ``*equivalence*.py`` under tests/, minus _support helpers."""
    proc = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", base, "--", "tests"],
        cwd=_git_repo_root(),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        report.fail("expected-set", f"git ls-tree {base} failed: {proc.stderr.strip()}")
        return set()
    paths = {
        p
        for p in proc.stdout.splitlines()
        if any(fnmatch.fnmatch(p.rsplit("/", 1)[-1], pat) for pat in SWEEP_PATTERNS)
        and not p.startswith(EXCLUDED_PREFIX)
    }
    if len(paths) != EXPECTED_COUNT:
        report.fail("expected-set", f"sweep at {base} yields {len(paths)} modules, floor/expectation is {EXPECTED_COUNT}")
    return paths


def _split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _normalize_path(cell: str) -> str:
    m = re.search(r"`([^`]+)`", cell)
    raw = (m.group(1) if m else cell).strip().strip("*").strip()
    return raw if raw.startswith("tests/") else f"tests/{raw}"


def parse_table(text: str, header_first_cell: str) -> tuple[list[str], list[list[str]]]:
    """Return (header, rows) of the first markdown table whose first header cell matches."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("|") and _split_row(line)[0] == header_first_cell:
            header = _split_row(line)
            rows: list[list[str]] = []
            for body in lines[i + 2 :]:
                if not body.startswith("|"):
                    break
                rows.append(_split_row(body))
            return header, rows
    return [], []


def grounding_churn(grounding: Path, report: Report) -> dict[str, tuple[str, ...]]:
    """Part 2 table of the grounding report: module path -> (all, src, mass, pcm, pcsrc)."""
    if not grounding.is_file():
        report.fail("churn-reference", f"grounding report missing: {grounding}")
        return {}
    text = grounding.read_text(encoding="utf-8")
    start = text.find("## Part 2")
    end = text.find("## Part 3")
    header, rows = parse_table(text[start:end], "file")
    if tuple(header[1:6]) != CHURN_COLUMNS:
        report.fail("churn-reference", f"grounding Part 2 header unexpected: {header[:6]}")
        return {}
    out: dict[str, tuple[str, ...]] = {}
    for row in rows:
        path = _normalize_path(row[0])
        if "*" in path:  # collapsed `_support/coverage_safety/*equivalence*` line: excluded helpers
            continue
        out[path] = tuple(c.strip("*") for c in row[1:6])
    return out


def _check_churn(path: str, cells: dict[str, str], reference: dict[str, tuple[str, ...]] | None, report: Report) -> bool:
    """Return True when the row uses ``n/a (shallow)`` churn."""
    values = tuple(cells[c] for c in CHURN_COLUMNS)
    if all(v == NA_CHURN for v in values):
        if reference is not None and path in reference:
            report.fail("churn-fidelity", f"{path}: n/a churn but grounding Part 2 has {reference[path]}")
        if "n/a" not in cells["note"].lower() and "shallow" not in cells["note"].lower():
            report.fail("churn-fidelity", f"{path}: n/a churn without a reason in the note column")
        return True
    if not all(v.isdigit() for v in values):
        report.fail("churn-fidelity", f"{path}: churn cells must be integers or '{NA_CHURN}', got {values}")
        return False
    if reference is None:  # documented re-measure: numbers are the reference
        return False
    if path not in reference:
        report.fail("churn-fidelity", f"{path}: numeric churn but module absent from grounding Part 2")
    elif reference[path] != values:
        report.fail("churn-fidelity", f"{path}: catalog churn {values} != grounding Part 2 {reference[path]}")
    return False


def _check_row(path: str, cells: dict[str, str], report: Report) -> None:
    for col in ("category", "pins invariant or shape?", "verdict"):
        if not cells[col]:
            report.fail("row-shape", f"{path}: empty '{col}' cell")
    verdict = cells["verdict"].strip("*").strip()
    if verdict not in VERDICTS:
        report.fail("verdict-enum", f"{path}: verdict {verdict!r} not in {sorted(VERDICTS)}")
    if any(t in verdict for t in ENFORCER_TRIGGERS):
        enforcer = cells["surviving enforcer / NFR-006 proof"]
        if "::" not in enforcer and not ("reason:" in enforcer and "mutation:" in enforcer):
            report.fail("nfr-006-enforcer", f"{path}: verdict {verdict!r} needs a '::' node ID or 'reason:' + 'mutation:'")
    category = cells["category"].lower()
    if any(t in category for t in EMPTY_TARGET_TRIGGERS) and not cells["empty-target behaviour"]:
        report.fail("sc-005-empty-target", f"{path}: ban/scan category without an empty-target behaviour cell")


def check_catalog(catalog: Path, expected: set[str], grounding: Path, report: Report) -> tuple[int, int]:
    """Return (rows passing, n/a churn rows)."""
    if not catalog.is_file():
        report.fail("catalog", f"catalog missing: {catalog} (0/{EXPECTED_COUNT})")
        return 0, 0
    text = catalog.read_text(encoding="utf-8")
    remeasured = any(
        line.startswith(REMEASURE_MARKER) and "window=" in line and "HEAD=" in line for line in text.splitlines()
    )
    reference = None if remeasured else grounding_churn(grounding, report)
    header, rows = parse_table(text, "suite")
    if tuple(header) != REQUIRED_COLUMNS:
        report.fail("row-shape", f"table header {header} != required {list(REQUIRED_COLUMNS)}")
        return 0, 0
    seen: dict[str, int] = {}
    na_rows = 0
    for row in rows:
        if len(row) != len(REQUIRED_COLUMNS):
            report.fail("row-shape", f"row has {len(row)} cells, expected {len(REQUIRED_COLUMNS)}: {row[:1]}")
            continue
        cells = dict(zip(REQUIRED_COLUMNS, row, strict=True))
        path = _normalize_path(cells["suite"])
        seen[path] = seen.get(path, 0) + 1
        _check_row(path, cells, report)
        na_rows += _check_churn(path, cells, reference, report)
    for path, count in sorted(seen.items()):
        if count > 1:
            report.fail("duplicates", f"{path} appears {count} times")
    actual = set(seen)
    for path in sorted(expected - actual):
        report.fail("set-equality", f"missing row: {path}")
    for path in sorted(actual - expected):
        report.fail("set-equality", f"extra row (not in base sweep): {path}")
    return len(actual & expected), na_rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default=DEFAULT_BASE, help="planning-base commit defining the sweep set")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG, help="parity-verdicts.md to check")
    parser.add_argument("--grounding", type=Path, default=DEFAULT_GROUNDING, help="grounding report (Part 2 churn)")
    args = parser.parse_args(argv)

    report = Report()
    expected = expected_set(args.base, report)
    covered, na_rows = check_catalog(args.catalog, expected, args.grounding, report)
    total = len(expected) or EXPECTED_COUNT
    print(f"n/a churn rows: {na_rows}")
    if report.failures:
        print("\n".join(report.failures))
        print(f"{covered}/{total} FAILED ({len(report.failures)} failure(s))")
        return 1
    print(f"{covered}/{total} OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
