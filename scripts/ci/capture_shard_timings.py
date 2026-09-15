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
``module-tests.yml`` cannot join durations to node ids (the committed file drops
node ids for compactness), so it pairs them **positionally** against its own
``pytest <test_dirs> -m "not performance" --collect-only -q`` order, and falls
back to **uniform weights for the whole module** when
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

``--write`` merges in place; ``--output PATH`` writes the merged payload elsewhere
(a dry run that leaves the committed artefact alone). Exactly one is required --
the payload is never written to stdout, which ``pytest.main`` shares with the
captured run's own report. ``--run-id`` overrides the generated provenance id (the
default follows the committed ``<label>-durations-<UTC timestamp>`` convention).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

__all__ = [
    "REGISTRY_PATH",
    "REPO_ROOT",
    "SELECTION_MARKER_EXPR",
    "TIMINGS_PATH",
    "DurationRecorder",
    "ModuleCapture",
    "capture_module",
    "generate_run_id",
    "main",
    "merge_capture",
    "resolve_test_dirs",
]

REPO_ROOT = Path(__file__).resolve().parents[2]
# Like select_source_artifacts.py, support direct checkout execution before
# installing the package. Resolve the canonical clock from this script's repo.
sys.path.insert(0, str(REPO_ROOT / "src"))
from kernel.clock import datetime, now_utc_compact_stamp, now_utc_iso  # noqa: E402

REGISTRY_PATH = REPO_ROOT / ".github" / "ci-module-registry.yml"
TIMINGS_PATH = REPO_ROOT / ".github" / "ci-shard-timings.json"

#: The marker expression ``module-tests.yml`` collects its shard under. Capturing
#: under any other selection produces a length mismatch and silently degrades the
#: consumer to uniform weights.
SELECTION_MARKER_EXPR = "not performance"

#: Known dual-test-tree modules, mirroring ``module-tests.yml``'s own fallback
#: (the doctrine test tree did not move when ``src/doctrine/`` was absorbed into
#: ``src/charter/offering/``).
_EXTRA_TEST_DIRS: dict[str, tuple[str, ...]] = {"charter": ("tests/doctrine",)}

_MODULE_DURATIONS_KEY = "module_test_durations"
_MODULE_COUNT_KEY = "module_test_count"
_MODULE_SECONDS_KEY = "module_duration_seconds"
_PROVENANCE_KEY = "module_capture_provenance"

_ROUNDING_PLACES = 4


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

    Mirrors the consumer's precedence exactly: an explicit registry ``test_dirs``
    list is **preferred over** — never unioned with — the ``tests/{module}``
    default, and only existing directories survive.
    """
    row = next((entry for entry in registry.get("modules", []) if entry.get("module") == module), None)
    if row is None:
        msg = f"module {module!r} is not a row in {REGISTRY_PATH.name}"
        raise KeyError(msg)

    declared = [str(entry) for entry in (row.get("test_dirs") or [])]
    candidates = declared or [f"tests/{module}", *_EXTRA_TEST_DIRS.get(module, ())]
    resolved = tuple(entry for entry in candidates if (REPO_ROOT / entry).is_dir())
    if not resolved:
        msg = f"module {module!r} resolves to no existing test directory (candidates: {candidates})"
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


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module", action="append", dest="modules", required=True, help="registry module to capture (repeatable)")
    parser.add_argument("--run-id", default=None, help="provenance run id (default: <label>-durations-<UTC timestamp>)")
    parser.add_argument("--write", action="store_true", help="merge into .github/ci-shard-timings.json in place")
    parser.add_argument("--output", type=Path, default=None, help="write the merged payload here instead (dry run)")
    args = parser.parse_args(argv)
    if bool(args.write) == bool(args.output):
        parser.error("pass exactly one of --write or --output (stdout is shared with pytest's own report)")
    return args


def _capture_all(modules: Iterable[str], *, run_id: str) -> list[ModuleCapture]:
    registry = _load_registry()
    return [capture_module(module, resolve_test_dirs(registry, module), run_id=run_id) for module in modules]


def main(argv: Sequence[str] | None = None) -> int:
    """Capture the requested modules and merge them into the timings artefact."""
    args = _parse_args(argv)
    run_id = args.run_id or generate_run_id()

    payload: dict[str, Any] = json.loads(TIMINGS_PATH.read_text(encoding="utf-8")) if TIMINGS_PATH.exists() else {}
    captures = _capture_all(args.modules, run_id=run_id)
    for capture in captures:
        payload = merge_capture(payload, capture)

    destination: Path = TIMINGS_PATH if args.write else args.output
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
