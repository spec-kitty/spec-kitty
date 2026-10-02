"""Reproducible capture of ``.github/ci-shard-timings.json`` (mission
sonar-per-pr-coverage-reuse-01M2FR32, WP02 / T007).

``.github/ci-shard-timings.json`` is the measured-duration authority the module
registry's ``shard_count`` balancing is derived from
(``tests/architectural/test_module_shard_registry.py``) and the per-shard test
selection is weighted by (``.github/workflows/module-tests.yml`` — greedy LPT
over ``module_test_durations``). It was originally produced by an **ad-hoc**
pytest plugin that was never committed, so regenerating it — or extending it
with a new registry row — was archaeology. This module is that producer, made
reproducible.

Why the captured shape must match the consumer exactly
------------------------------------------------------
``module-tests.yml`` (through ``scripts/ci/shard_select.py``) cannot join durations
to node ids (the committed file drops node ids for compactness), so it pairs them
**positionally** against its own
``pytest <test_dirs> -m "not performance and not stress" --collect-only -q`` order,
and falls back to **uniform weights for the whole module** when
``len(durations) != len(node_ids)``. That fallback is silent and no gate
notices it: the skew guard re-reads the same committed list, so a list of the
right length always passes whether or not it was ever measured. Therefore this
capture runs pytest with the consumer's *own* selection
(:data:`SELECTION_MARKER_EXPR`) over the consumer's *own* test directories,
**serially** — so the recorded order is the collection order the consumer pairs
against — and records one duration per collected test.

Usage
-----
::

    python scripts/ci/capture_shard_timings.py --module unit --module specify_cli_runtime --write

Battery per-file timings (mission ci-runtime-stabilisation-01M3TZH6, WP05 / T022, D-29)
-------------------------------------------------------------------------------------
The architectural battery is partitioned by *file* (``battery_partition_plugin``), so its
timing table is ``battery_file_durations[<suite>]`` -- repo-relative test file to seconds --
with ``battery_capture_provenance[<suite>]`` beside it. Battery timings are never captured
by a local battery run (charter C-009): they are summed from the junit artefacts of CI runs
(``gh run download``), one directory per run::

    python scripts/ci/capture_shard_timings.py --suite architectural \\
        --from-junit run-1/ --from-junit run-2/ --run-id 101 --run-id 102 --write

Across several runs a file's value is the median of the runs it appears in.
:func:`merge_battery_capture` is the one writer of those two tables; the census seed
(WP14) calls it too.

``--write`` merges in place; ``--output PATH`` writes the merged payload elsewhere
(a dry run that leaves the committed artefact alone). Exactly one is required --
the payload is never written to stdout, which ``pytest.main`` shares with the
captured run's own report. ``--run-id`` overrides the generated provenance id (the
default follows the committed ``<label>-durations-<UTC timestamp>`` convention).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import statistics
import sys
import xml.etree.ElementTree as ET
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

__all__ = [
    "REGISTRY_PATH",
    "REPO_ROOT",
    "SELECTION_MARKER_EXPR",
    "TIMINGS_PATH",
    "BATTERY_PRODUCER",
    "DurationRecorder",
    "JunitCapture",
    "ModuleCapture",
    "capture_module",
    "generate_run_id",
    "junit_capture",
    "main",
    "median_across_runs",
    "merge_battery_capture",
    "merge_capture",
    "resolve_junit_classname",
    "resolve_test_dirs",
]

REPO_ROOT = Path(__file__).resolve().parents[2]
# Like select_source_artifacts.py, support direct checkout execution before
# installing the package. Resolve the canonical clock from this script's repo.
sys.path.insert(0, str(REPO_ROOT / "src"))
from kernel.clock import datetime, now_utc_compact_stamp, now_utc_iso  # noqa: E402

# ``scripts.ci`` resolves as a namespace package only with the repo root on the
# path; this script also runs bare (``python -I -S``), where cwd is not on it.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from scripts.ci.shard_select import MODULE_SELECTION_MARKER_EXPR, resolve_module_test_dirs  # noqa: E402

REGISTRY_PATH = REPO_ROOT / ".github" / "ci-module-registry.yml"
TIMINGS_PATH = REPO_ROOT / ".github" / "ci-shard-timings.json"

#: The marker expression ``module-tests.yml`` collects its shard under. Capturing
#: under any other selection produces a length mismatch and silently degrades the
#: consumer to uniform weights. ``scripts/ci/shard_select.py`` is the authority;
#: this name is kept for the recapture script, the tests and the provenance field.
SELECTION_MARKER_EXPR = MODULE_SELECTION_MARKER_EXPR

_MODULE_DURATIONS_KEY = "module_test_durations"
_MODULE_COUNT_KEY = "module_test_count"
_MODULE_SECONDS_KEY = "module_duration_seconds"
_PROVENANCE_KEY = "module_capture_provenance"

_ROUNDING_PLACES = 4

_BATTERY_DURATIONS_KEY = "battery_file_durations"
_BATTERY_PROVENANCE_KEY = "battery_capture_provenance"
_BATTERY_REQUIRED_PROVENANCE = ("producer", "captured_at", "selection", "workers", "files_measured")
_BATTERY_SUITES = ("architectural",)

#: The ``producer`` recorded for junit-derived battery timings.
BATTERY_PRODUCER = "scripts/ci/capture_shard_timings.py"


class _Report(Protocol):
    """The subset of ``pytest``'s ``TestReport`` this recorder reads."""

    @property
    def nodeid(self) -> str: ...

    @property
    def duration(self) -> float: ...


class DurationRecorder:
    """Accumulate each test's total wall time, in first-seen (collection) order.

    A pytest run emits three reports per test — ``setup``, ``call`` and
    ``teardown``. The committed file records ONE number per test, so the three
    phases are summed: the consumer weights a whole test's cost, and a suite
    whose cost is dominated by fixture setup (``tests/upgrade`` is the standing
    example in the registry's own comments) is badly mis-weighted by the call
    phase alone.

    Insertion order is the execution order, which for a **serial** run is the
    collection order ``module-tests.yml`` pairs positionally against.
    """

    def __init__(self) -> None:
        self._durations: dict[str, float] = {}

    def record(self, nodeid: str, duration: float) -> None:
        """Add *duration* to the running total for *nodeid*."""
        self._durations[nodeid] = self._durations.get(nodeid, 0.0) + float(duration)

    # pytest plugin hook — one call per phase report.
    def pytest_runtest_logreport(self, report: _Report) -> None:
        self.record(report.nodeid, report.duration)

    @property
    def node_ids(self) -> tuple[str, ...]:
        """The recorded node ids, in first-seen order."""
        return tuple(self._durations)

    @property
    def durations(self) -> tuple[float, ...]:
        """The per-test totals, in first-seen order, rounded like the committed file."""
        return tuple(round(value, _ROUNDING_PLACES) for value in self._durations.values())


@dataclass(frozen=True)
class ModuleCapture:
    """One module's measured durations plus the provenance that produced them."""

    module: str
    test_dirs: tuple[str, ...]
    durations: tuple[float, ...]
    run_id: str
    command: str
    captured_at: str
    exit_code: int

    @property
    def total_seconds(self) -> float:
        return round(sum(self.durations), 3)


def generate_run_id(label: str = "wp02", *, now: datetime | None = None) -> str:
    """A run id in the committed ``<label>-durations-<UTC timestamp>`` convention."""
    stamp = now_utc_compact_stamp() if now is None else now.strftime("%Y%m%dT%H%M%SZ")
    return f"{label}-durations-{stamp}"


def resolve_test_dirs(registry: dict[str, Any], module: str) -> tuple[str, ...]:
    """The test directories ``module-tests.yml`` would select for *module*.

    Resolution is delegated to ``shard_select.resolve_module_test_dirs`` -- the
    resolver the shard itself runs (C-010: one authority, never a mirrored copy).
    This adapter only finds the registry row, anchors the resolver's
    cwd-relative ``isdir`` checks at the repository root, and refuses a module
    that resolves to nothing rather than capturing an empty list.
    """
    row = next((entry for entry in registry.get("modules", []) if entry.get("module") == module), None)
    if row is None:
        msg = f"module {module!r} is not a row in {REGISTRY_PATH.name}"
        raise KeyError(msg)

    declared = [str(entry) for entry in (row.get("test_dirs") or [])]
    with contextlib.chdir(REPO_ROOT):
        resolved = tuple(resolve_module_test_dirs(module, json.dumps(declared)))
    if not resolved:
        msg = f"module {module!r} resolves to no existing test directory (declared: {declared}, mirror: tests/{module})"
        raise FileNotFoundError(msg)
    return resolved


def _load_registry() -> dict[str, Any]:
    import yaml  # local import: the merge/aggregation paths need no YAML

    payload = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"{REGISTRY_PATH} did not parse to a mapping"
        raise TypeError(msg)
    return payload


def _pytest_argv(test_dirs: Sequence[str]) -> list[str]:
    """The consumer's own selection, run serially (no xdist) so order is stable."""
    return [*test_dirs, "-m", SELECTION_MARKER_EXPR, "-p", "no:randomly", "-q"]


def capture_module(module: str, test_dirs: Sequence[str], *, run_id: str) -> ModuleCapture:
    """Run *test_dirs* under the consumer's selection and record per-test durations."""
    import pytest

    recorder = DurationRecorder()
    argv = _pytest_argv(test_dirs)
    # pytest.main() splices `[tool.pytest.ini_options] addopts` into the list it is
    # handed, IN PLACE -- hand it a copy so the recorded command stays the
    # reproducible invocation rather than that run's post-addopts residue.
    exit_code = int(pytest.main(list(argv), plugins=[recorder]))
    return ModuleCapture(
        module=module,
        test_dirs=tuple(test_dirs),
        durations=recorder.durations,
        run_id=run_id,
        command=f"python scripts/ci/capture_shard_timings.py --module {module} --run-id {run_id} --write  # pytest {' '.join(argv)}",
        captured_at=now_utc_iso(),
        exit_code=exit_code,
    )


def merge_capture(payload: dict[str, Any], capture: ModuleCapture) -> dict[str, Any]:
    """Return *payload* with *capture* folded into the per-module timing tables.

    Additive and idempotent: an existing module's three parallel tables are
    replaced together (they must never disagree — a count that does not match the
    duration list is exactly the stale-data defect this producer exists to close)
    and a provenance record is written under
    ``module_capture_provenance[<module>]``.
    """
    merged = dict(payload)
    for key in (_MODULE_DURATIONS_KEY, _MODULE_COUNT_KEY, _MODULE_SECONDS_KEY, _PROVENANCE_KEY):
        merged[key] = dict(merged.get(key) or {})

    merged[_MODULE_DURATIONS_KEY][capture.module] = list(capture.durations)
    merged[_MODULE_COUNT_KEY][capture.module] = len(capture.durations)
    merged[_MODULE_SECONDS_KEY][capture.module] = capture.total_seconds
    merged[_PROVENANCE_KEY][capture.module] = {
        "run_id": capture.run_id,
        "command": capture.command,
        "captured_at": capture.captured_at,
        "test_dirs": list(capture.test_dirs),
        "selection": SELECTION_MARKER_EXPR,
        "unique_tests_measured": len(capture.durations),
        "exit_code": capture.exit_code,
        "producer": "scripts/ci/capture_shard_timings.py",
    }
    return merged


@dataclass(frozen=True)
class JunitCapture:
    """Per-file seconds summed from junit testcases, plus how many testcases resolved to no base file."""

    seconds: dict[str, float]
    unresolved: int


def resolve_junit_classname(classname: str, base_files: Collection[str]) -> str | None:
    """The base file a junit ``classname`` belongs to, or ``None`` (never guessed).

    xunit2 writes the dotted module path of the test file followed by any class
    names (``tests.architectural.test_x.TestY``); the file is the **longest dotted
    prefix** whose ``/``-joined ``.py`` path is in *base_files*.
    """
    parts = classname.split(".") if classname else []
    for length in range(len(parts), 0, -1):
        candidate = "/".join(parts[:length]) + ".py"
        if candidate in base_files:
            return candidate
    return None


def junit_capture(xml_paths: Iterable[Path], base_files: Collection[str]) -> JunitCapture:
    """Sum testcase ``time`` per base file over *xml_paths*; count the testcases no file claims."""
    seconds: dict[str, float] = {}
    unresolved = 0
    for path in xml_paths:
        # Our own CI junit artefacts, never third-party input; expat resolves no external entities.
        for case in ET.parse(path).getroot().iter("testcase"):  # noqa: S314
            file = resolve_junit_classname(case.get("classname", ""), base_files)
            if file is None:
                unresolved += 1
                continue
            seconds[file] = seconds.get(file, 0.0) + float(case.get("time", 0.0))
    return JunitCapture({file: round(value, _ROUNDING_PLACES) for file, value in seconds.items()}, unresolved)


def median_across_runs(runs: Sequence[Mapping[str, float]]) -> dict[str, float]:
    """Per-file median over the runs a file appears in, rounded like the module tables."""
    samples: dict[str, list[float]] = {}
    for run in runs:
        for file, value in run.items():
            samples.setdefault(file, []).append(value)
    return {file: round(float(statistics.median(values)), _ROUNDING_PLACES) for file, values in samples.items()}


def merge_battery_capture(
    payload: dict[str, Any],
    suite: str,
    durations: Mapping[str, float],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Return *payload* with the battery tables for *suite* replaced together (pure, additive, idempotent).

    ``battery_file_durations[suite]`` and ``battery_capture_provenance[suite]`` are
    written as a pair; every other key -- the module tables and any other suite --
    is left untouched. *provenance* must carry :data:`_BATTERY_REQUIRED_PROVENANCE`
    and a ``files_measured`` that equals the table length (a count that disagrees
    with the table is the stale-data defect this producer exists to close).
    """
    missing = [key for key in _BATTERY_REQUIRED_PROVENANCE if key not in provenance]
    if missing:
        msg = f"battery provenance is missing required fields: {', '.join(missing)}"
        raise ValueError(msg)
    if provenance["files_measured"] != len(durations):
        msg = f"battery provenance files_measured={provenance['files_measured']} but the table holds {len(durations)} files"
        raise ValueError(msg)
    merged = dict(payload)
    merged[_BATTERY_DURATIONS_KEY] = {**(merged.get(_BATTERY_DURATIONS_KEY) or {}), suite: dict(durations)}
    merged[_BATTERY_PROVENANCE_KEY] = {**(merged.get(_BATTERY_PROVENANCE_KEY) or {}), suite: dict(provenance)}
    return merged


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--module", action="append", dest="modules", help="registry module to capture (repeatable)")
    target.add_argument("--suite", choices=_BATTERY_SUITES, help="battery suite to capture per-file timings for, from CI junit (needs --from-junit)")
    parser.add_argument("--from-junit", action="append", type=Path, dest="junit_dirs", help="directory of one CI run's junit artefacts (repeatable, with --suite)")
    parser.add_argument(
        "--run-id",
        action="append",
        dest="run_ids",
        help="provenance run id (module mode: default <label>-durations-<UTC timestamp>; --suite: one per --from-junit, default the directory name)",
    )
    parser.add_argument("--write", action="store_true", help="merge into .github/ci-shard-timings.json in place")
    parser.add_argument("--output", type=Path, default=None, help="write the merged payload here instead (dry run)")
    return parser


def _validate_mode_options(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    run_ids = args.run_ids or []
    if args.suite:
        if not args.junit_dirs:
            parser.error("--suite requires at least one --from-junit DIR")
        if run_ids and len(run_ids) != len(args.junit_dirs):
            parser.error(f"--run-id must be given once per --from-junit ({len(run_ids)} run ids for {len(args.junit_dirs)} directories)")
    else:
        if args.junit_dirs:
            parser.error("--from-junit is only valid with --suite")
        if len(run_ids) > 1:
            parser.error("--run-id may be given once in --module mode")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if bool(args.write) == bool(args.output):
        parser.error("pass exactly one of --write or --output (stdout is shared with pytest's own report)")
    _validate_mode_options(parser, args)
    args.run_id = args.run_ids[0] if args.suite is None and args.run_ids else None
    return args


def _capture_all(modules: Iterable[str], *, run_id: str) -> list[ModuleCapture]:
    registry = _load_registry()
    return [capture_module(module, resolve_test_dirs(registry, module), run_id=run_id) for module in modules]


def _junit_files(directory: Path) -> list[Path]:
    files = sorted(directory.rglob("*.xml"))
    if not files:
        msg = f"no junit *.xml files under {directory}"
        raise FileNotFoundError(msg)
    return files


def _battery_provenance(spec: Any, durations: Mapping[str, float], run_ids: Sequence[str], unresolved: int) -> dict[str, Any]:
    return {
        "producer": BATTERY_PRODUCER,
        "source": "junit",
        "captured_at": now_utc_iso(),
        "selection": spec.base.marker,
        "workers": spec.workers,
        "files_measured": len(durations),
        "run_ids": list(run_ids),
        "unresolved_testcases": unresolved,
    }


def _capture_suite(args: argparse.Namespace, payload: dict[str, Any]) -> tuple[dict[str, Any], str] | None:
    """Fold the junit directories of ``--suite`` into *payload*; ``None`` when nothing resolved."""
    from scripts.ci.battery_partition_plugin import load_battery_spec
    from scripts.ci.shard_select import enumerate_base_files

    spec = load_battery_spec(_load_registry())
    base_files = enumerate_base_files(spec.base.paths, deselect=spec.base.deselect, root=REPO_ROOT)
    captures = [junit_capture(_junit_files(directory), base_files) for directory in args.junit_dirs]
    durations = median_across_runs([capture.seconds for capture in captures])
    if not durations:
        print(f"capture_shard_timings: no junit testcase resolved to a {args.suite} base file -- nothing written", file=sys.stderr)
        return None
    run_ids = args.run_ids or [directory.name for directory in args.junit_dirs]
    unresolved = sum(capture.unresolved for capture in captures)
    provenance = _battery_provenance(spec, durations, run_ids, unresolved)
    merged = merge_battery_capture(payload, spec.timings_key, durations, provenance)
    summary = f"{spec.timings_key} -> {len(durations)} files from {len(captures)} runs ({unresolved} unresolved testcases)"
    return merged, summary


def main(argv: Sequence[str] | None = None) -> int:
    """Capture the requested modules (or battery suite) and merge them into the timings artefact."""
    args = _parse_args(argv)
    payload: dict[str, Any] = json.loads(TIMINGS_PATH.read_text(encoding="utf-8")) if TIMINGS_PATH.exists() else {}
    destination: Path = TIMINGS_PATH if args.write else args.output

    if args.suite:
        suite_result = _capture_suite(args, payload)
        if suite_result is None:
            return 1
        merged, summary = suite_result
        destination.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        print(f"capture_shard_timings: {summary} -> {destination}", file=sys.stderr)
        return 0

    run_id = args.run_id or generate_run_id()
    captures = _capture_all(args.modules, run_id=run_id)
    for capture in captures:
        payload = merge_capture(payload, capture)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    for capture in captures:
        print(
            f"capture_shard_timings: {capture.module} -> {len(capture.durations)} tests, {capture.total_seconds}s "
            f"(run_id={capture.run_id}, exit={capture.exit_code}) -> {destination}",
            file=sys.stderr,
        )
    return 0 if all(capture.exit_code == 0 for capture in captures) else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
