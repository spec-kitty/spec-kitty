"""Unit tests for ``scripts/ci/capture_shard_timings.py`` (mission
sonar-per-pr-coverage-reuse-01M2FR32, WP02 / T007).

Scope is deliberately the script's **aggregation** logic — the parts that decide
what number lands in ``.github/ci-shard-timings.json`` — not an end-to-end pytest
capture (that is what the committed artefact's own provenance record evidences).

The three properties pinned here are the ones a silent regression would cost:

* per-test durations sum the ``setup``/``call``/``teardown`` phases, so a suite
  whose cost is fixture setup is not recorded as near-zero (the defect that made
  the committed ``merge`` row read 1.1s against a ~138s wall clock);
* the recorded order is first-seen (== serial execution == collection) order,
  because ``module-tests.yml`` pairs durations to node ids **positionally**;
* ``merge_capture`` keeps the three parallel per-module tables in lockstep, since
  ``len(durations) != collected`` silently degrades that consumer to uniform
  weights with no gate noticing.

The module is loaded by file path (``scripts/ci`` is not an importable package
from the test's own import root), mirroring
``tests/ci/test_sonar_project_version.py``.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "ci" / "capture_shard_timings.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("capture_shard_timings", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register BEFORE exec: `@dataclass` resolves `sys.modules[cls.__module__]`
    # while processing the class body, and an unregistered by-path module makes
    # that lookup return None (AttributeError at import, on 3.11).
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def capture_shard_timings() -> ModuleType:
    return _load_module()


@dataclass(frozen=True)
class _FakeReport:
    """The two attributes ``DurationRecorder`` reads off a pytest ``TestReport``."""

    nodeid: str
    duration: float


# ---------------------------------------------------------------------------
# DurationRecorder — phase summing and ordering
# ---------------------------------------------------------------------------
def test_recorder_sums_every_phase_of_one_test(capture_shard_timings: ModuleType) -> None:
    """setup + call + teardown land in ONE number, not just the call phase."""
    recorder = capture_shard_timings.DurationRecorder()
    for report in (
        _FakeReport("tests/x.py::test_a", 1.5),  # setup (the expensive fixture)
        _FakeReport("tests/x.py::test_a", 0.25),  # call
        _FakeReport("tests/x.py::test_a", 0.125),  # teardown
    ):
        recorder.pytest_runtest_logreport(report)

    assert recorder.node_ids == ("tests/x.py::test_a",)
    assert recorder.durations == (1.875,)


def test_recorder_preserves_first_seen_order(capture_shard_timings: ModuleType) -> None:
    """Order is first-seen, not sorted — the consumer pairs positionally."""
    recorder = capture_shard_timings.DurationRecorder()
    for nodeid, duration in (("t::c", 0.3), ("t::a", 0.1), ("t::b", 0.2), ("t::a", 0.05)):
        recorder.record(nodeid, duration)

    assert recorder.node_ids == ("t::c", "t::a", "t::b")
    assert recorder.durations == (0.3, 0.15, 0.2)


def test_recorder_is_empty_before_any_report(capture_shard_timings: ModuleType) -> None:
    """A capture that ran nothing records nothing — never a fabricated list."""
    recorder = capture_shard_timings.DurationRecorder()
    assert recorder.node_ids == ()
    assert recorder.durations == ()


# ---------------------------------------------------------------------------
# resolve_test_dirs — mirrors module-tests.yml's precedence exactly
# ---------------------------------------------------------------------------
def test_declared_test_dirs_are_preferred_over_the_default(capture_shard_timings: ModuleType) -> None:
    """An explicit ``test_dirs`` replaces ``tests/{module}``; it is not unioned."""
    registry = {"modules": [{"module": "specify_cli_runtime", "test_dirs": ["tests/specify_cli/runtime"]}]}
    assert capture_shard_timings.resolve_test_dirs(registry, "specify_cli_runtime") == ("tests/specify_cli/runtime",)


def test_missing_test_dirs_falls_back_to_the_module_mirror(capture_shard_timings: ModuleType) -> None:
    registry = {"modules": [{"module": "unit"}]}
    assert capture_shard_timings.resolve_test_dirs(registry, "unit") == ("tests/unit",)


def test_unknown_module_raises_rather_than_capturing_nothing(capture_shard_timings: ModuleType) -> None:
    with pytest.raises(KeyError):
        capture_shard_timings.resolve_test_dirs({"modules": []}, "no_such_module")


def test_module_resolving_to_no_existing_directory_raises(capture_shard_timings: ModuleType) -> None:
    registry = {"modules": [{"module": "ghost", "test_dirs": ["tests/does-not-exist"]}]}
    with pytest.raises(FileNotFoundError):
        capture_shard_timings.resolve_test_dirs(registry, "ghost")


# ---------------------------------------------------------------------------
# merge_capture — the three parallel tables stay in lockstep
# ---------------------------------------------------------------------------
def _capture(capture_shard_timings: ModuleType, module: str, durations: tuple[float, ...]):
    return capture_shard_timings.ModuleCapture(
        module=module,
        test_dirs=("tests/unit",),
        durations=durations,
        run_id="wp02-durations-20260101T000000Z",
        command="python scripts/ci/capture_shard_timings.py --module unit --write",
        captured_at="2026-01-01T00:00:00+00:00",
        exit_code=0,
    )


def test_merge_writes_count_seconds_and_durations_together(capture_shard_timings: ModuleType) -> None:
    merged = capture_shard_timings.merge_capture({}, _capture(capture_shard_timings, "unit", (0.5, 0.25, 0.25)))

    assert merged["module_test_durations"]["unit"] == [0.5, 0.25, 0.25]
    assert merged["module_test_count"]["unit"] == len(merged["module_test_durations"]["unit"])
    assert merged["module_duration_seconds"]["unit"] == 1.0


def test_merge_records_provenance_for_the_module(capture_shard_timings: ModuleType) -> None:
    """A reviewer must be able to ask "which run produced this list?" and get an answer."""
    merged = capture_shard_timings.merge_capture({}, _capture(capture_shard_timings, "unit", (0.5,)))

    provenance = merged["module_capture_provenance"]["unit"]
    assert provenance["run_id"] == "wp02-durations-20260101T000000Z"
    assert provenance["unique_tests_measured"] == 1
    assert provenance["selection"] == capture_shard_timings.SELECTION_MARKER_EXPR
    assert provenance["producer"] == "scripts/ci/capture_shard_timings.py"


def test_merge_leaves_other_modules_and_the_input_payload_untouched(capture_shard_timings: ModuleType) -> None:
    """Merging one module is additive: no other row, and no caller state, changes."""
    payload = {
        "run_id": "wp08-durations-20260907T141640Z",
        "module_test_durations": {"merge": [1.0, 2.0]},
        "module_test_count": {"merge": 2},
        "module_duration_seconds": {"merge": 3.0},
    }
    merged = capture_shard_timings.merge_capture(payload, _capture(capture_shard_timings, "unit", (0.5,)))

    assert merged["module_test_durations"]["merge"] == [1.0, 2.0]
    assert merged["run_id"] == "wp08-durations-20260907T141640Z"
    assert payload["module_test_durations"] == {"merge": [1.0, 2.0]}, "merge_capture mutated its input"


def test_recapturing_a_module_replaces_all_three_tables(capture_shard_timings: ModuleType) -> None:
    """A shorter re-capture must not leave a stale longer list behind."""
    merged = capture_shard_timings.merge_capture({}, _capture(capture_shard_timings, "unit", (0.5, 0.5, 0.5)))
    merged = capture_shard_timings.merge_capture(merged, _capture(capture_shard_timings, "unit", (0.25,)))

    assert merged["module_test_durations"]["unit"] == [0.25]
    assert merged["module_test_count"]["unit"] == 1
    assert merged["module_duration_seconds"]["unit"] == 0.25


# ---------------------------------------------------------------------------
# generate_run_id — the committed provenance convention
# ---------------------------------------------------------------------------
def test_generated_run_id_follows_the_committed_convention(capture_shard_timings: ModuleType) -> None:
    from kernel.clock import UTC, datetime

    run_id = capture_shard_timings.generate_run_id("wp02", now=datetime(2026, 9, 14, 15, 34, 54, tzinfo=UTC))
    assert run_id == "wp02-durations-20260914T153454Z"


def test_capture_timestamps_use_the_canonical_clock(capture_shard_timings: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    from kernel import clock

    instant = clock.datetime(2026, 9, 14, 15, 34, 54, 123456, tzinfo=clock.UTC)
    monkeypatch.setattr(clock, "DEFAULT_CLOCK", clock.FrozenClock(instant))
    monkeypatch.setattr(pytest, "main", lambda *_args, **_kwargs: 0)
    run_id = capture_shard_timings.generate_run_id("qualification")
    result = capture_shard_timings.capture_module("unit", ("tests/unit",), run_id=run_id)
    assert run_id == "qualification-durations-20260914T153454Z"
    assert result.captured_at == "2026-09-14T15:34:54.123456+00:00"


def test_script_help_works_without_installed_package(tmp_path: Path) -> None:
    import subprocess

    result = subprocess.run(
        [sys.executable, "-I", "-S", str(_SCRIPT_PATH), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--run-id" in result.stdout
