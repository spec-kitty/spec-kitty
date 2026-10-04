"""CI entry point for the shared test-universe collection (mission
shared-collection-and-shard-recapture-01M42V58, WP02: FR-010, FR-011, NFR-005).

Run as ``python -m scripts.ci.collect_universe_prestep <command>`` from the repository root
checkout. The script holds no key, dirty-check or record logic of its own: it calls
``tests.architectural._universe_store`` (key, record, report format) and
``tests.architectural._gate_coverage`` (the collector), so the pre-step and the tests can never
disagree about what a stored universe is. Both are imported inside the commands, which keeps
``--help`` fast.

Commands (``contracts/collection-store.md``):

``key [--with-commit]``
    Print the collection key of the clean checkout. With ``--with-commit`` print
    ``<key>-<commit>`` instead: that is the CI cache key, because a stored record is valid for one
    commit only and a cache key is immutable, so a key shared by two commits would keep a record
    that one of them rejects. Exit 2 when git cannot describe the checkout or it is dirty.
``collect``
    Call ``collect_universe()`` once as caller ``prestep`` and print the report line it produced.
    Exit 0 only when that line is acceptable (``prestep_acceptable``): ``reused``, ``collected``
    with the record stored, or ``bypassed`` / ``unsupported-platform`` without a ``detail``. Every
    other outcome (dirty checkout, git unavailable, lock or store failure, a record that was not
    stored, a failed collection, no report line) exits non-zero and says why on stderr.
``check``
    Read the report file named by ``SK_GATE_REUSE_REPORT`` and write a Markdown table to
    ``GITHUB_STEP_SUMMARY`` (stdout when unset). Exit 1 when the pre-step's own line is not
    acceptable, and when the pre-step stored or reused a record and a later request in the job
    collected afresh or was bypassed for any reason other than ``root-override`` (research D-07,
    D-14); also exit 1 on a malformed report line. Fallback mode (exit 0 with a note) applies only
    to a missing or empty report, a report with no pre-step line, or the acceptable platform bypass.
``consumers --battery-part <part>``
    Print ``true`` when the battery partition ``<part>`` (``1/2``, ``2/2``) holds a test file that
    requests the universe through ``collect_universe()``, else ``false``; the architectural-heavy
    job runs the key, restore, collect, save and check steps only on a leg that prints ``true``.
    The files are found by scanning ``tests/architectural/test_*.py`` for a call
    (:func:`universe_consumers`), so the answer follows the tests. Exit 1 and no answer on stdout
    for an unknown part or any other failure: the workflow step fails the job rather than skip the
    pre-step on a leg that may hold a consumer.
``compare``
    Perform one fresh collection with the store bypassed and diff it against the stored record
    (the nightly freshness check). Exit 1 on any difference or when nothing usable is stored.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

PRESTEP_CALLER = "prestep"
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_DIRTY = 2
MAX_DIFFERENCES_SHOWN = 20

CONSUMER_GLOB = "test_*.py"
CONSUMER_DIR = "tests/architectural"
# Test files that call ``collect_universe()`` but never collect for real: they replace the
# collector with a fake (pinned by tests/ci/test_collect_universe_prestep.py), so a leg that
# holds only them gains nothing from the pre-test step.
NOT_CONSUMERS = frozenset({"tests/architectural/test_universe_store.py"})
_UNIVERSE_CALL = "collect_universe"

FALLBACK_NOTE = "pre-test step did not store a collection; reuse not expected"
_REUSED = "reused"
_COLLECTED = "collected"
_BYPASSED = "bypassed"
_ROOT_OVERRIDE = "root-override"
_UNSUPPORTED_PLATFORM = "unsupported-platform"
_NOT_STORED_PREFIX = "not stored"
_SUMMARY_ENV_VAR = "GITHUB_STEP_SUMMARY"
_TABLE_COLUMNS = ("caller", "outcome", "reason", "detail", "dirty paths", "seconds")

Line = Mapping[str, Any]
Signature = tuple[str, str, tuple[str, ...]]


class ReportError(ValueError):
    """The reuse report holds a line that is not a JSON object."""


# ---------------------------------------------------------------------------
# Report reading (shared by ``collect`` and ``check``)
# ---------------------------------------------------------------------------


def parse_report(text: str) -> list[dict[str, Any]]:
    """Parse the JSON-lines report; a malformed line is an error, a blank line is ignored."""
    lines: list[dict[str, Any]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            parsed = json.loads(raw)
        except ValueError as failure:
            raise ReportError(f"report line {number} is not valid JSON ({failure})") from failure
        if not isinstance(parsed, dict):
            raise ReportError(f"report line {number} is not a JSON object")
        lines.append(parsed)
    return lines


def _read_report(path: str | None) -> str:
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


# ---------------------------------------------------------------------------
# check: the verdict is a pure function of the report lines
# ---------------------------------------------------------------------------


def prestep_acceptable(line: Line) -> bool:
    """The single rule for a pre-step's own line, shared by ``collect`` and ``check``.

    Acceptable: ``reused``; ``collected`` with the record stored; ``bypassed`` /
    ``unsupported-platform`` with no ``detail`` (a genuine platform bypass). Anything else means
    reuse is silently disabled for the whole job and must turn the job red.
    """
    outcome = line.get("outcome")
    detail = str(line.get("detail") or "")
    if outcome == _REUSED:
        return True
    if outcome == _COLLECTED:
        return not detail.startswith(_NOT_STORED_PREFIX)
    return outcome == _BYPASSED and line.get("reason") == _UNSUPPORTED_PLATFORM and not detail


def _breaks_reuse(line: Line) -> bool:
    outcome = line.get("outcome")
    if outcome == _COLLECTED:
        return True
    return outcome == _BYPASSED and line.get("reason") != _ROOT_OVERRIDE


def _describe(line: Line) -> str:
    text = f"{line.get('caller')}: {line.get('outcome')} ({line.get('reason')})"
    if line.get("detail"):
        text += f", detail: {line['detail']}"
    paths = line.get("dirty_paths")
    if paths:
        text += f", dirty paths: {_join(paths)}"
    return text


def _join(paths: object) -> str:
    return ", ".join(str(path) for path in paths) if isinstance(paths, list) else str(paths)


def verdict(lines: Sequence[Line]) -> tuple[int, str]:
    """Decide ``check``: ``(exit status, plain-words verdict)`` (research D-07, D-14)."""
    start = next((index for index, line in enumerate(lines) if line.get("caller") == PRESTEP_CALLER), None)
    if start is None:
        return EXIT_OK, f"Fallback mode: {FALLBACK_NOTE}."
    if not prestep_acceptable(lines[start]):
        return EXIT_FAILED, f"Reuse broken: the pre-test step did not store a usable collection, so no later request can reuse one: {_describe(lines[start])}."
    if lines[start].get("outcome") == _BYPASSED:
        return EXIT_OK, f"Fallback mode: {FALLBACK_NOTE}."
    later = lines[start + 1 :]
    offenders = [line for line in later if _breaks_reuse(line)]
    if not offenders:
        return EXIT_OK, f"Reuse held: the pre-test step {lines[start].get('outcome')} the universe and {len(later)} later request(s) reused it or were exempt."
    bullets = "\n".join(f"- {_describe(line)}" for line in offenders)
    return EXIT_FAILED, f"Reuse broken: {len(offenders)} request(s) after the pre-test step did not reuse its collection.\n{bullets}"


def _cell(value: object) -> str:
    return str(value if value is not None else "").replace("|", "\\|")


def render_table(lines: Sequence[Line]) -> str:
    """Markdown table of the report lines (caller, outcome, reason, detail, dirty paths, seconds)."""
    rows = ["| " + " | ".join(_TABLE_COLUMNS) + " |", "|" + " --- |" * len(_TABLE_COLUMNS)]
    for line in lines:
        cells = (
            line.get("caller"),
            line.get("outcome"),
            line.get("reason"),
            line.get("detail"),
            _join(line["dirty_paths"]) if line.get("dirty_paths") else "",
            line.get("seconds"),
        )
        rows.append("| " + " | ".join(_cell(cell) for cell in cells) + " |")
    return "\n".join(rows)


def _publish_summary(text: str) -> None:
    """Append to the job summary file when set, else print; a closing newline is added."""
    target = os.environ.get(_SUMMARY_ENV_VAR)
    if not target:
        print(text)
        return
    with Path(target).open("a", encoding="utf-8") as stream:
        stream.write(f"{text}\n")


def cmd_check() -> int:
    from tests.architectural import _universe_store as store

    try:
        lines = parse_report(_read_report(os.environ.get(store.REPORT_ENV_VAR)))
    except ReportError as failure:
        message = f"Reuse report is corrupt: {failure}."
        _publish_summary(f"### Universe reuse\n\n{message}")
        print(message, file=sys.stderr)
        return EXIT_FAILED
    code, message = verdict(lines)
    table = f"{render_table(lines)}\n\n" if lines else ""
    _publish_summary(f"### Universe reuse\n\n{table}{message}")
    if os.environ.get(_SUMMARY_ENV_VAR):
        print(message)
    return code


# ---------------------------------------------------------------------------
# key and collect
# ---------------------------------------------------------------------------


def cmd_key(*, with_commit: bool = False) -> int:
    from tests.architectural import _gate_coverage as coverage
    from tests.architectural import _universe_store as store

    state = store.checkout_state(coverage.REPO_ROOT)
    if state is None:
        print("cannot compute a collection key: git could not describe the checkout", file=sys.stderr)
        return EXIT_DIRTY
    if state.dirty_paths:
        print(f"cannot compute a collection key: the checkout has uncommitted changes ({', '.join(state.dirty_paths[:5])})", file=sys.stderr)
        return EXIT_DIRTY
    key = store.compute_key(state.tree)
    print(f"{key}-{state.commit}" if with_commit else key)
    return EXIT_OK


@contextmanager
def _report_path(variable: str) -> Iterator[str]:
    """The report file for this process: the caller's, or a temporary one removed afterwards."""
    configured = os.environ.get(variable)
    if configured:
        yield configured
        return
    with tempfile.TemporaryDirectory(prefix="sk-prestep-") as scratch:
        path = str(Path(scratch) / "reuse-report.jsonl")
        os.environ[variable] = path
        try:
            yield path
        finally:
            os.environ.pop(variable, None)


def cmd_collect() -> int:
    from tests.architectural import _gate_coverage as coverage
    from tests.architectural import _universe_store as store

    with _report_path(store.REPORT_ENV_VAR) as path:
        seen = len(parse_report(_read_report(path)))
        coverage.collect_universe(caller=PRESTEP_CALLER)
        new_lines = parse_report(_read_report(path))[seen:]
    for line in new_lines:
        print(json.dumps(line))
    if not new_lines:
        print("collect failed: no report line was written, so the pre-step outcome is unknown", file=sys.stderr)
        return EXIT_FAILED
    if not prestep_acceptable(new_lines[-1]):
        print(f"collect failed: the pre-step did not store a usable collection ({_describe(new_lines[-1])})", file=sys.stderr)
        return EXIT_FAILED
    if new_lines[-1].get("outcome") == _BYPASSED:
        print(f"warning: the platform is unsupported by the store; jobs collect for themselves ({_describe(new_lines[-1])})", file=sys.stderr)
    return EXIT_OK


# ---------------------------------------------------------------------------
# consumers
# ---------------------------------------------------------------------------


def _calls_collect_universe(source: str) -> bool:
    """True when the module calls ``collect_universe`` (``gc.collect_universe()`` or the bare name)."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            target = node.func
            if (isinstance(target, ast.Attribute) and target.attr == _UNIVERSE_CALL) or (isinstance(target, ast.Name) and target.id == _UNIVERSE_CALL):
                return True
    return False


def universe_consumers(root: Path | None = None) -> frozenset[str]:
    """Repository-relative test files under ``tests/architectural/`` that request the universe.

    An AST scan, so a docstring or a string that mentions the call does not count. Files in
    :data:`NOT_CONSUMERS` are left out. This is the one authority the workflow reads (through
    ``consumers``); no file name is written in YAML.
    """
    if root is None:
        from tests.architectural import _gate_coverage as coverage

        root = coverage.REPO_ROOT
    found = set()
    for path in sorted((root / CONSUMER_DIR).glob(CONSUMER_GLOB)):
        relpath = path.relative_to(root).as_posix()
        if relpath not in NOT_CONSUMERS and _calls_collect_universe(path.read_text(encoding="utf-8")):
            found.add(relpath)
    return frozenset(found)


def cmd_consumers(part: str) -> int:
    from tests.architectural import _gate_coverage as coverage

    try:
        files = coverage.battery_part_files(part)
    except ValueError as failure:
        print(f"consumers failed: {failure}", file=sys.stderr)
        return EXIT_FAILED
    print("true" if files & universe_consumers() else "false")
    return EXIT_OK


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------


def _signature(record: Mapping[str, Any]) -> Signature:
    return (str(record["nodeid"]), str(record["relpath"]), tuple(record["markers"]))


def diff_universes(stored: Sequence[Mapping[str, Any]], fresh: Sequence[Mapping[str, Any]]) -> list[str]:
    """Differing records as ``-``/``+`` lines (only in stored / only in fresh), sorted."""
    left = Counter(_signature(record) for record in stored)
    right = Counter(_signature(record) for record in fresh)
    only_stored = sorted((left - right).elements())
    only_fresh = sorted((right - left).elements())
    return [f"- only in stored: {nodeid} [{', '.join(markers)}]" for nodeid, _relpath, markers in only_stored] + [
        f"+ only in fresh: {nodeid} [{', '.join(markers)}]" for nodeid, _relpath, markers in only_fresh
    ]


def cmd_compare() -> int:
    from tests.architectural import _gate_coverage as coverage
    from tests.architectural import _universe_store as store

    repo = coverage.REPO_ROOT
    state = store.checkout_state(repo)
    if state is None or state.dirty_paths:
        print("cannot compare: the checkout is dirty or git could not describe it, so no stored record can match", file=sys.stderr)
        return EXIT_FAILED
    key = store.compute_key(state.tree)
    stored, reason = store.load_record(store.store_dir(repo), key, commit=state.commit, tree=state.tree)
    if stored is None:
        print(f"no usable stored record for key {key} ({reason})")
        return EXIT_FAILED
    fresh = coverage._collect_universe_fresh(repo)  # fresh collection with the store bypassed, by design
    differences = diff_universes(stored, fresh)
    print(f"stored: {len(stored)} records, fresh: {len(fresh)} records, differing: {len(differences)}")
    for line in differences[:MAX_DIFFERENCES_SHOWN]:
        print(line)
    return EXIT_FAILED if differences else EXIT_OK


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_COMMANDS: dict[str, Callable[[], int]] = {
    "key": cmd_key,
    "collect": cmd_collect,
    "check": cmd_check,
    "compare": cmd_compare,
}
_CONSUMERS = "consumers"  # takes --battery-part, so main() dispatches it rather than the table


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="collect_universe_prestep", description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("command", choices=sorted([*_COMMANDS, _CONSUMERS]))
    parser.add_argument("--with-commit", action="store_true", help="key only: append the checkout commit, for a cache key that cannot go stale")
    parser.add_argument("--battery-part", help="consumers only: the battery partition to ask about, e.g. 1/2")
    args = parser.parse_args(argv)
    command = args.command
    if args.with_commit and command != "key":
        parser.error("--with-commit applies to the key command only")
    if (args.battery_part is not None) != (command == _CONSUMERS):
        parser.error("--battery-part is required by the consumers command and applies to it only")
    try:
        if command == "key":
            return cmd_key(with_commit=args.with_commit)
        if command == _CONSUMERS:
            return cmd_consumers(args.battery_part)
        return _COMMANDS[command]()
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as failure:
        print(f"{command} failed: {failure}", file=sys.stderr)
        return EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
