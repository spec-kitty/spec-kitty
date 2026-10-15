"""Per-PR check of the test absorption ledger (ADR 2026-10-15-1; no third-party dependency).

``tests/scenarios/absorption-ledger.json`` records every engineering test retired from
``tests/integration`` or ``tests/e2e`` and what now carries its coverage: a gating acceptance
scenario, or a surviving pytest test. It also freezes a ``baseline``: the test files those two
trees held when the ledger was started. The check fails when:

* ``LEDGER_UNREADABLE``: the ledger is missing or is not JSON;
* ``LEDGER_SCHEMA``: a field is missing, of the wrong type, or ``schema_version`` is not 1;
* ``EMPTY_BASELINE``: the baseline lists no file, so the removal rule below would be vacuous;
* ``DUPLICATE_RETIRED``: two rows retire the same test;
* ``RETIRED_NOT_IN_BASELINE``: a row retires a test from a file the baseline does not list;
* ``RETIRED_STILL_PRESENT``: the retired file, or the retired test function, still exists;
* ``REPLACEMENT_MISSING``: a ``replaced_by`` entry names a scenario or a pytest test that does not
  exist;
* ``REPLACEMENT_NOT_GATING``: a replacing scenario is ``@wip`` or ``@manual``, so it does not gate
  the nightly and the coverage would be lost;
* ``UNLEDGERED_REMOVAL``: a baseline file is gone from disk and no row retires the whole file.

A row retires a whole file (``tests/e2e/test_x.py``) or one test (``tests/e2e/test_x.py::test_y``
or ``...::TestClass::test_y``). A ``replaced_by`` entry is a scenario
(``tests/scenarios/<area>/<file>.feature::<scenario name>``) or a pytest test (a node id as above).

What the machine cannot check: that the replacement asserts at least what the retired test
asserted, on an equivalent or stronger arrange. Reviewers check that (ADR 2026-10-15-1, decision 3).
Removing a test function from a kept file without a row is not detected either; only whole-file
removals are, through the baseline.

Usage::

    python -m scripts.ci.absorption_ledger [--root DIR] [--ledger FILE]

Exit status is 1 when any problem is found, otherwise 0.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.ci.scenario_contract import is_gating, parse_feature

REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER = Path("tests") / "scenarios" / "absorption-ledger.json"
SCHEMA_VERSION = 1
SEPARATOR = "::"
FEATURE_SUFFIX = ".feature"

LEDGER_UNREADABLE = "LEDGER_UNREADABLE"
LEDGER_SCHEMA = "LEDGER_SCHEMA"
EMPTY_BASELINE = "EMPTY_BASELINE"
DUPLICATE_RETIRED = "DUPLICATE_RETIRED"
RETIRED_NOT_IN_BASELINE = "RETIRED_NOT_IN_BASELINE"
RETIRED_STILL_PRESENT = "RETIRED_STILL_PRESENT"
REPLACEMENT_MISSING = "REPLACEMENT_MISSING"
REPLACEMENT_NOT_GATING = "REPLACEMENT_NOT_GATING"
UNLEDGERED_REMOVAL = "UNLEDGERED_REMOVAL"


@dataclass(frozen=True)
class Problem:
    """One finding; ``code`` is stable, ``subject`` names the row or file it is about."""

    code: str
    subject: str
    message: str

    def render(self) -> str:
        return f"{self.code}: {self.subject}: {self.message}"


@dataclass(frozen=True)
class Row:
    retired: str
    replaced_by: tuple[str, ...]


@dataclass(frozen=True)
class Ledger:
    baseline: tuple[str, ...]
    rows: tuple[Row, ...]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _string_list(value: Any) -> tuple[str, ...] | None:
    if isinstance(value, list) and all(isinstance(item, str) and item for item in value):
        return tuple(value)
    return None


def _parse_row(index: int, raw: Any) -> tuple[Row | None, list[Problem]]:
    subject = f"retired[{index}]"
    if not isinstance(raw, dict):
        return None, [Problem(LEDGER_SCHEMA, subject, "a row must be an object")]
    retired = raw.get("retired")
    replaced_by = _string_list(raw.get("replaced_by"))
    problems = []
    if not isinstance(retired, str) or not retired.startswith("tests/") or ".py" not in retired:
        problems.append(Problem(LEDGER_SCHEMA, subject, "'retired' must be a tests/ path or pytest node id"))
    if not replaced_by:
        problems.append(Problem(LEDGER_SCHEMA, subject, "'replaced_by' must be a non-empty list of strings"))
    if not isinstance(raw.get("issue"), int) or not isinstance(raw.get("note"), str) or not raw.get("note"):
        problems.append(Problem(LEDGER_SCHEMA, subject, "'issue' (int) and a non-empty 'note' are required"))
    if problems:
        return None, problems
    assert isinstance(retired, str) and replaced_by is not None
    return Row(retired, replaced_by), []


def parse_ledger(data: Any) -> tuple[Ledger | None, list[Problem]]:
    """Validate the decoded JSON document and return the ledger it describes."""
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        return None, [Problem(LEDGER_SCHEMA, "ledger", f"must be an object with schema_version {SCHEMA_VERSION}")]
    baseline = data.get("baseline")
    files = _string_list(baseline.get("files")) if isinstance(baseline, dict) else None
    if files is None:
        return None, [Problem(LEDGER_SCHEMA, "baseline", "'baseline.files' must be a list of paths")]
    raw_rows = data.get("retired")
    if not isinstance(raw_rows, list):
        return None, [Problem(LEDGER_SCHEMA, "retired", "'retired' must be a list")]
    rows: list[Row] = []
    problems: list[Problem] = []
    for index, raw in enumerate(raw_rows):
        row, row_problems = _parse_row(index, raw)
        problems += row_problems
        if row is not None:
            rows.append(row)
    return Ledger(files, tuple(rows)), problems


def load_ledger(path: Path) -> tuple[Ledger | None, list[Problem]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, [Problem(LEDGER_UNREADABLE, str(path), f"cannot read the ledger: {exc}")]
    return parse_ledger(data)


# ---------------------------------------------------------------------------
# Resolving pytest node ids and scenario references
# ---------------------------------------------------------------------------


def split_node(node: str) -> tuple[str, tuple[str, ...]]:
    """``path::Class::test`` -> (``path``, (``Class``, ``test``)); a parametrize id is dropped."""
    path, *names = node.split(SEPARATOR)
    if names:
        names[-1] = names[-1].split("[", 1)[0]
    return path, tuple(names)


def _child(body: Sequence[ast.stmt], name: str) -> ast.stmt | None:
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            return node
    return None


def node_exists(root: Path, node: str) -> bool:
    """Whether the file of ``node`` exists and, for a test id, defines that (nested) name."""
    path, names = split_node(node)
    file = root / path
    if not file.is_file():
        return False
    if not names:
        return True
    try:
        body: Sequence[ast.stmt] = ast.parse(file.read_text(encoding="utf-8")).body
    except (OSError, UnicodeDecodeError, SyntaxError):
        return False
    for name in names:
        found = _child(body, name)
        if found is None:
            return False
        body = found.body if isinstance(found, ast.ClassDef) else []
    return True


def _scenario_problem(root: Path, subject: str, reference: str) -> Problem | None:
    path, _, name = reference.partition(SEPARATOR)
    scenarios, _ = parse_feature(root / path) if (root / path).is_file() else ([], [])
    matching = [s for s in scenarios if s.name == name]
    if not matching:
        return Problem(REPLACEMENT_MISSING, subject, f"no scenario {name!r} in {path}")
    if not any(is_gating(s) for s in matching):
        return Problem(REPLACEMENT_NOT_GATING, subject, f"scenario {name!r} is @wip or @manual and does not gate the nightly")
    return None


def _replacement_problem(root: Path, subject: str, reference: str) -> Problem | None:
    path = reference.partition(SEPARATOR)[0]
    if path.endswith(FEATURE_SUFFIX):
        return _scenario_problem(root, subject, reference)
    if not node_exists(root, reference):
        return Problem(REPLACEMENT_MISSING, subject, f"pytest test {reference!r} does not exist")
    return None


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


def _row_problems(root: Path, row: Row, baseline: frozenset[str]) -> list[Problem]:
    problems: list[Problem] = []
    path, names = split_node(row.retired)
    if path not in baseline:
        problems.append(Problem(RETIRED_NOT_IN_BASELINE, row.retired, "the baseline does not list this file"))
    still_there = (root / path).is_file() if not names else node_exists(root, row.retired)
    if still_there:
        problems.append(Problem(RETIRED_STILL_PRESENT, row.retired, "retire the test in the same change that records it"))
    for reference in row.replaced_by:
        problem = _replacement_problem(root, row.retired, reference)
        if problem is not None:
            problems.append(problem)
    return problems


def _duplicates(rows: Sequence[Row]) -> list[Problem]:
    seen: set[str] = set()
    problems = []
    for row in rows:
        if row.retired in seen:
            problems.append(Problem(DUPLICATE_RETIRED, row.retired, "retired by more than one row"))
        seen.add(row.retired)
    return problems


def _unledgered_removals(root: Path, ledger: Ledger) -> list[Problem]:
    whole_files = {row.retired for row in ledger.rows if SEPARATOR not in row.retired}
    return [
        Problem(UNLEDGERED_REMOVAL, path, "removed from disk without a ledger row retiring the whole file")
        for path in ledger.baseline
        if not (root / path).is_file() and path not in whole_files
    ]


def check_ledger(root: Path, ledger: Ledger) -> list[Problem]:
    """Every rule over a parsed ledger, against the tree at ``root``."""
    if not ledger.baseline:
        return [Problem(EMPTY_BASELINE, "baseline", "lists no file, so a removal could never be detected")]
    baseline = frozenset(ledger.baseline)
    problems = _duplicates(ledger.rows)
    for row in ledger.rows:
        problems += _row_problems(root, row, baseline)
    return problems + _unledgered_removals(root, ledger)


def check(root: Path, ledger_path: Path | None = None) -> list[Problem]:
    """Load the ledger (default ``tests/scenarios/absorption-ledger.json`` under ``root``) and check it."""
    ledger, problems = load_ledger(ledger_path or root / LEDGER)
    if ledger is None:
        return problems
    return problems + check_ledger(root, ledger)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="absorption_ledger", description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root")
    parser.add_argument("--ledger", type=Path, default=None, help="ledger file (default: <root>/tests/scenarios/absorption-ledger.json)")
    args = parser.parse_args(argv)
    problems = check(args.root, args.ledger)
    for problem in problems:
        print(problem.render())
    print(f"absorption ledger: {'ok' if not problems else f'{len(problems)} problem(s)'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
