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
import json
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "ci" / "capture_shard_timings.py"


def _load_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    spec = importlib.util.spec_from_file_location("capture_shard_timings", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register BEFORE exec: `@dataclass` resolves `sys.modules[cls.__module__]`
    # while processing the class body, and an unregistered by-path module makes
    # that lookup return None (AttributeError at import, on 3.11).
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def capture_shard_timings() -> Iterator[ModuleType]:
    with pytest.MonkeyPatch.context() as mp:
        yield _load_module(mp)


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


def test_resolution_delegates_to_the_shard_select_authority(capture_shard_timings: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    """C-010: the recorder resolves through ``shard_select.resolve_module_test_dirs``, never a copy."""
    calls: list[tuple[str, str]] = []

    def _spy(module: str, registry_test_dirs_json: str) -> list[str]:
        calls.append((module, registry_test_dirs_json))
        return ["tests/unit"]

    monkeypatch.setattr(capture_shard_timings, "resolve_module_test_dirs", _spy)
    registry = {"modules": [{"module": "alpha", "test_dirs": ["tests/a", "tests/b"]}]}

    assert capture_shard_timings.resolve_test_dirs(registry, "alpha") == ("tests/unit",)
    assert calls == [("alpha", json.dumps(["tests/a", "tests/b"]))]


def test_vanished_declared_dirs_fall_back_to_the_mirror_like_the_consumer(capture_shard_timings: ModuleType) -> None:
    """The consumer's precedence, not a private one: no existing declared dir -> the ``tests/<module>`` mirror."""
    registry = {"modules": [{"module": "unit", "test_dirs": ["tests/does-not-exist"]}]}
    assert capture_shard_timings.resolve_test_dirs(registry, "unit") == ("tests/unit",)


def test_resolution_is_independent_of_the_working_directory(capture_shard_timings: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The shared resolver tests ``os.path.isdir`` relative to cwd; the recorder anchors it at the repo root."""
    monkeypatch.chdir(tmp_path)
    assert capture_shard_timings.resolve_test_dirs({"modules": [{"module": "unit"}]}, "unit") == ("tests/unit",)


def test_every_registry_row_resolves_exactly_as_the_shard_does(capture_shard_timings: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    """Live: for every registry row the recorder's dirs equal what ``module-tests.yml`` collects."""
    from scripts.ci.shard_select import resolve_module_test_dirs

    registry = yaml.safe_load((_REPO_ROOT / ".github" / "ci-module-registry.yml").read_text(encoding="utf-8"))
    monkeypatch.chdir(_REPO_ROOT)
    rows = registry["modules"]
    assert rows, "non-vacuity: the registry must carry module rows"
    for row in rows:
        expected = tuple(resolve_module_test_dirs(row["module"], json.dumps(row.get("test_dirs") or [])))
        assert capture_shard_timings.resolve_test_dirs(registry, row["module"]) == expected, row["module"]


# ---------------------------------------------------------------------------
# merge_capture — the three parallel tables stay in lockstep
# ---------------------------------------------------------------------------
def _capture(capture_shard_timings: ModuleType, module: str, durations: tuple[float, ...]) -> Any:
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
    assert "--suite" in result.stdout
    assert "--from-junit" in result.stdout


def test_capture_selects_with_the_shared_marker_constant(capture_shard_timings: ModuleType) -> None:
    """Capture and ``module-tests.yml`` share one marker authority (C-010, #5510).

    The drifted ``"not performance"`` copy recorded lists the consumer never
    collects for any module with ``stress`` tests, degrading it to uniform weights.
    """
    from scripts.ci.shard_select import MODULE_SELECTION_MARKER_EXPR

    assert capture_shard_timings.SELECTION_MARKER_EXPR == MODULE_SELECTION_MARKER_EXPR
    argv = capture_shard_timings._pytest_argv(("tests/x",))
    assert argv[argv.index("-m") + 1] == MODULE_SELECTION_MARKER_EXPR


# ---------------------------------------------------------------------------
# WP05 / T022 -- battery per-file timings from CI junit (D-29)
# ---------------------------------------------------------------------------
_BASE = (
    "tests/architectural/test_a.py",
    "tests/architectural/test_b.py",
    "tests/architectural/sub/test_c.py",
)
_BATTERY_PRODUCER = "scripts/ci/capture_shard_timings.py"


def _junit_xml(*cases: tuple[str, float]) -> str:
    body = "".join(f'<testcase classname="{classname}" name="test_x" time="{seconds}"/>' for classname, seconds in cases)
    return f'<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest">{body}</testsuite></testsuites>'


def _write_junit(directory: Path, name: str, *cases: tuple[str, float]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(_junit_xml(*cases), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("classname", "expected"),
    [
        ("tests.architectural.test_a", "tests/architectural/test_a.py"),
        ("tests.architectural.test_a.TestY", "tests/architectural/test_a.py"),
        ("tests.architectural.test_a.TestY.TestInner", "tests/architectural/test_a.py"),
        ("tests.architectural.sub.test_c", "tests/architectural/sub/test_c.py"),
        ("tests.architectural.sub.test_c.TestZ", "tests/architectural/sub/test_c.py"),
        ("tests.architectural.test_unknown", None),
        ("tests.architectural", None),
        ("", None),
        ("other.test_a", None),
    ],
)
def test_classname_resolves_to_the_longest_dotted_prefix_in_the_base(capture_shard_timings: ModuleType, classname: str, expected: str | None) -> None:
    assert capture_shard_timings.resolve_junit_classname(classname, set(_BASE)) == expected


def test_classname_prefers_the_longest_prefix_when_both_match(capture_shard_timings: ModuleType) -> None:
    base = {"tests/x.py", "tests/x/y.py"}
    assert capture_shard_timings.resolve_junit_classname("tests.x.y", base) == "tests/x/y.py"
    assert capture_shard_timings.resolve_junit_classname("tests.x.TestY", base) == "tests/x.py"


def test_junit_capture_sums_testcase_time_per_file(capture_shard_timings: ModuleType, tmp_path: Path) -> None:
    one = _write_junit(
        tmp_path, "one.xml", ("tests.architectural.test_a", 1.5), ("tests.architectural.test_a.TestY", 0.25), ("tests.architectural.sub.test_c", 2.0)
    )
    two = _write_junit(tmp_path, "two.xml", ("tests.architectural.test_a", 0.5), ("tests.architectural.test_b", 3.0))
    capture = capture_shard_timings.junit_capture([one, two], _BASE)
    assert capture.unresolved == 0
    assert capture.seconds == {"tests/architectural/test_a.py": 2.25, "tests/architectural/sub/test_c.py": 2.0, "tests/architectural/test_b.py": 3.0}


def test_unresolved_testcases_are_counted_never_guessed(capture_shard_timings: ModuleType, tmp_path: Path) -> None:
    xml = _write_junit(tmp_path, "r.xml", ("tests.architectural.test_a", 1.0), ("tests.architectural.test_ghost", 9.0), ("tests.elsewhere.test_q", 4.0))
    capture = capture_shard_timings.junit_capture([xml], _BASE)
    assert capture.seconds == {"tests/architectural/test_a.py": 1.0}
    assert capture.unresolved == 2


def test_median_across_runs_uses_only_the_runs_a_file_appears_in(capture_shard_timings: ModuleType) -> None:
    runs = [{"a": 1.0, "b": 10.0}, {"a": 3.0}, {"a": 5.0, "b": 20.0, "c": 0.12345}]
    merged = capture_shard_timings.median_across_runs(runs)
    assert merged == {"a": 3.0, "b": 15.0, "c": 0.1235}


def test_median_of_no_runs_is_empty(capture_shard_timings: ModuleType) -> None:
    assert capture_shard_timings.median_across_runs([]) == {}


def _battery_provenance(**overrides: object) -> dict[str, object]:
    provenance: dict[str, object] = {
        "producer": _BATTERY_PRODUCER,
        "captured_at": "2026-10-01T00:00:00+00:00",
        "selection": "not performance and not stress and not timing",
        "workers": 4,
        "files_measured": 2,
        "source": "junit",
        "run_ids": ["1", "2"],
        "unresolved_testcases": 0,
    }
    provenance.update(overrides)
    return provenance


def test_merge_battery_capture_replaces_both_battery_tables_together(capture_shard_timings: ModuleType) -> None:
    payload: dict[str, Any] = {
        "module_test_durations": {"unit": [1.0]},
        "module_capture_provenance": {"unit": {"run_id": "x"}},
        "battery_file_durations": {"architectural": {"old.py": 9.0}, "other": {"k": 1.0}},
        "battery_capture_provenance": {"architectural": {"producer": "census-seed"}, "other": {"producer": "p"}},
        "run_id": "keep",
    }
    merged = capture_shard_timings.merge_battery_capture(payload, "architectural", {"a.py": 1.0, "b.py": 2.0}, _battery_provenance())
    assert merged["battery_file_durations"] == {"architectural": {"a.py": 1.0, "b.py": 2.0}, "other": {"k": 1.0}}
    assert merged["battery_capture_provenance"]["architectural"] == _battery_provenance()
    assert merged["battery_capture_provenance"]["other"] == {"producer": "p"}
    assert merged["module_test_durations"] == {"unit": [1.0]}
    assert merged["module_capture_provenance"] == {"unit": {"run_id": "x"}}
    assert merged["run_id"] == "keep"
    assert payload["battery_file_durations"]["architectural"] == {"old.py": 9.0}, "merge_battery_capture mutated its input"


def test_merge_battery_capture_is_idempotent_and_starts_from_an_empty_payload(capture_shard_timings: ModuleType) -> None:
    provenance = _battery_provenance(files_measured=1)
    once = capture_shard_timings.merge_battery_capture({}, "architectural", {"a.py": 1.0}, provenance)
    twice = capture_shard_timings.merge_battery_capture(once, "architectural", {"a.py": 1.0}, provenance)
    assert once == twice
    assert set(once) == {"battery_file_durations", "battery_capture_provenance"}


@pytest.mark.parametrize("missing", ["producer", "captured_at", "selection", "workers", "files_measured"])
def test_merge_battery_capture_requires_the_provenance_fields(capture_shard_timings: ModuleType, missing: str) -> None:
    provenance = _battery_provenance()
    del provenance[missing]
    with pytest.raises(ValueError, match=missing):
        capture_shard_timings.merge_battery_capture({}, "architectural", {"a.py": 1.0}, provenance)


def test_merge_battery_capture_rejects_a_count_that_disagrees_with_the_table(capture_shard_timings: ModuleType) -> None:
    with pytest.raises(ValueError, match="files_measured"):
        capture_shard_timings.merge_battery_capture({}, "architectural", {"a.py": 1.0}, _battery_provenance(files_measured=5))


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--module", "unit", "--suite", "architectural", "--write"],
        ["--suite", "architectural", "--write"],
        ["--module", "unit", "--from-junit", "d", "--write"],
        ["--suite", "architectural", "--from-junit", "d", "--run-id", "a", "--run-id", "b", "--write"],
        ["--suite", "architectural", "--from-junit", "d"],
        ["--suite", "architectural", "--from-junit", "d", "--write", "--output", "o.json"],
        ["--module", "unit", "--run-id", "a", "--run-id", "b", "--write"],
        ["--suite", "nonsense", "--from-junit", "d", "--write"],
    ],
)
def test_cli_argument_combinations_are_validated(capture_shard_timings: ModuleType, argv: list[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        capture_shard_timings._parse_args(argv)
    assert excinfo.value.code == 2


@pytest.mark.parametrize(
    "argv",
    [
        ["--module", "unit", "--write"],
        ["--module", "unit", "--module", "merge", "--run-id", "r", "--output", "o.json"],
        ["--suite", "architectural", "--from-junit", "d", "--write"],
        ["--suite", "architectural", "--from-junit", "d", "--from-junit", "e", "--run-id", "a", "--run-id", "b", "--output", "o.json"],
        ["--suite", "architectural", "--from-junit", "d", "--from-junit", "e", "--output", "o.json"],
    ],
)
def test_cli_accepts_the_documented_combinations(capture_shard_timings: ModuleType, argv: list[str]) -> None:
    capture_shard_timings._parse_args(argv)


def _battery_registry() -> dict[str, object]:
    return {
        "special_tiers": {
            "architectural": {
                "trigger": "code_scoped",
                "deserialized": True,
                "workers": 4,
                "base": {
                    "paths": ["tests/architectural"],
                    "marker": "not performance and not stress and not timing",
                    "deselect": ["tests/architectural/test_b.py"],
                },
                "fast_gate": {
                    "job": "architectural-fast",
                    "max_file_budget_seconds": 90,
                    "max_total_measured_seconds": 300,
                    "roster": [{"path": "tests/architectural/test_a.py", "budget_seconds": 10, "reason": "r"}],
                },
                "shards": {"job": "architectural-heavy", "shard_count": 2, "granularity": "file", "timings_key": "architectural"},
            }
        }
    }


def test_two_run_junit_capture_end_to_end_through_main(capture_shard_timings: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    for rel in ("tests/architectural/test_a.py", "tests/architectural/test_b.py", "tests/architectural/sub/test_c.py"):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text("", encoding="utf-8")
    (repo / "registry.yml").write_text(yaml.safe_dump(_battery_registry()), encoding="utf-8")
    committed = {"module_test_durations": {"unit": [1.0]}, "battery_file_durations": {"architectural": {"stale.py": 1.0}}}
    (repo / "timings.json").write_text(json.dumps(committed), encoding="utf-8")
    monkeypatch.setattr(capture_shard_timings, "REPO_ROOT", repo)
    monkeypatch.setattr(capture_shard_timings, "REGISTRY_PATH", repo / "registry.yml")
    monkeypatch.setattr(capture_shard_timings, "TIMINGS_PATH", repo / "timings.json")
    run1, run2 = tmp_path / "run1", tmp_path / "run2"
    _write_junit(run1, "a.xml", ("tests.architectural.test_a", 2.0), ("tests.architectural.sub.test_c", 4.0), ("tests.architectural.test_ghost", 7.0))
    _write_junit(run2, "a.xml", ("tests.architectural.test_a", 4.0))
    _write_junit(run2, "b.xml", ("tests.architectural.sub.test_c", 8.0))
    out = tmp_path / "out.json"

    code = capture_shard_timings.main(
        ["--suite", "architectural", "--from-junit", str(run1), "--from-junit", str(run2), "--run-id", "101", "--run-id", "102", "--output", str(out)]
    )

    assert code == 0
    merged = json.loads(out.read_text(encoding="utf-8"))
    assert merged["battery_file_durations"]["architectural"] == {"tests/architectural/test_a.py": 3.0, "tests/architectural/sub/test_c.py": 6.0}
    provenance = merged["battery_capture_provenance"]["architectural"]
    assert provenance["source"] == "junit"
    assert provenance["run_ids"] == ["101", "102"]
    assert provenance["unresolved_testcases"] == 1
    assert provenance["files_measured"] == 2
    assert provenance["workers"] == 4
    assert provenance["selection"] == "not performance and not stress and not timing"
    assert provenance["producer"] == _BATTERY_PRODUCER
    assert merged["module_test_durations"] == {"unit": [1.0]}
    assert json.loads((repo / "timings.json").read_text(encoding="utf-8")) == committed, "--output must leave the committed artefact alone"


def test_junit_capture_without_matching_testcases_is_an_error(capture_shard_timings: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "tests/architectural").mkdir(parents=True)
    (repo / "tests/architectural/test_a.py").write_text("", encoding="utf-8")
    (repo / "registry.yml").write_text(yaml.safe_dump(_battery_registry()), encoding="utf-8")
    monkeypatch.setattr(capture_shard_timings, "REPO_ROOT", repo)
    monkeypatch.setattr(capture_shard_timings, "REGISTRY_PATH", repo / "registry.yml")
    monkeypatch.setattr(capture_shard_timings, "TIMINGS_PATH", repo / "timings.json")
    _write_junit(tmp_path / "run", "a.xml", ("tests.elsewhere.test_q", 1.0))
    code = capture_shard_timings.main(["--suite", "architectural", "--from-junit", str(tmp_path / "run"), "--output", str(tmp_path / "out.json")])
    assert code == 1
    assert not (tmp_path / "out.json").exists(), "an empty capture must never be written as if measured"
