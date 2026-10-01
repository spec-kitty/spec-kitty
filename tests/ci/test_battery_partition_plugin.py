"""Behaviour tests for ``scripts/ci/battery_partition_plugin.py`` (mission
ci-runtime-stabilisation-01M3TZH6, WP05 / T018; research D-02, D-23, D-26).

The plugin makes ONE pytest invocation execute exactly one part of the
architectural battery (``--battery-part fast|i/n``). Two layers are pinned:

* **Production path** -- pytest is driven in a *subprocess* over a synthetic
  ``tests/architectural`` tree (``pytester`` is not enabled in this repository,
  see ``tests/architectural/test_home_owner_behaviour.py``). The subprocess runs
  with ``cwd = REPO_ROOT`` and **no** ``PYTHONPATH`` -- the CI condition -- so
  ``-p scripts.ci.battery_partition_plugin`` must import exactly as it does on a
  runner, in the controller *and* in every xdist worker (``-n 2`` really
  executes the trivial tests: xdist does not distribute under ``--collect-only``).
  The executed-file oracle is the junit file, resolved through
  ``capture_shard_timings.resolve_junit_classname`` (one resolver, T022).
* **Pure helpers** -- ``parse_part``, the registry loader, the invocation-vs-base
  comparison, the digest, the out-of-part detector, the worker-count check, the
  summary renderer and the hooks' decision code, called directly.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pytest
import yaml

from scripts.ci import battery_partition_plugin as plugin
from scripts.ci.capture_shard_timings import junit_capture
from scripts.ci.shard_select import battery_parts, enumerate_base_files

_REPO_ROOT = Path(__file__).resolve().parents[2]

_BASE_MARKER = "not performance and not stress and not timing"
_TESTS_DIR = "tests/architectural"
_DESELECTED = f"{_TESTS_DIR}/test_deselected.py"
_ROSTER = (f"{_TESTS_DIR}/test_alpha.py", f"{_TESTS_DIR}/test_charlie.py", f"{_TESTS_DIR}/sub/test_india.py")
_NON_ROSTER = ("bravo", "delta", "echo", "foxtrot", "golf", "hotel", "juliet")
_TIMINGS = {
    f"{_TESTS_DIR}/test_bravo.py": 5.0,
    f"{_TESTS_DIR}/test_delta.py": 3.0,
    f"{_TESTS_DIR}/test_echo.py": 2.0,
    f"{_TESTS_DIR}/test_foxtrot.py": 1.0,
    f"{_TESTS_DIR}/test_golf.py": 1.0,
    f"{_TESTS_DIR}/test_hotel.py": 1.0,
    f"{_TESTS_DIR}/test_juliet.py": 1.0,
}
_WARNING_PREFIX = "::warning title=shard timings::"
_USAGE_ERROR = 4
_TESTS_FAILED = 1
_PARTS = ("fast", "1/2", "2/2")
_TRIVIAL_TEST = "def test_ok():\n    assert True\n"
_EXTRA_CHECK_CONFTEST_HOOK = """

def pytest_collect_file(parent, file_path):
    if file_path.name == 'extra_check.py':
        return pytest.Module.from_parent(parent, path=file_path)
"""
_TAMPER_PLUGIN = """\
import pytest

from scripts.ci import battery_partition_plugin as plugin


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    if hasattr(config, "workerinput"):
        plugin.part_digest = lambda files: "tampered"
"""


# ---------------------------------------------------------------------------
# Synthetic tree + registry
# ---------------------------------------------------------------------------
def _registry_payload(*, workers: int = 2, shard_count: int = 2, roster: Sequence[str] = _ROSTER, budget: int = 10) -> dict[str, Any]:
    return {
        "special_tiers": {
            "architectural": {
                "trigger": "code_scoped",
                "deserialized": True,
                "workers": workers,
                "base": {"paths": [_TESTS_DIR], "marker": _BASE_MARKER, "deselect": [_DESELECTED]},
                "fast_gate": {
                    "job": "architectural-fast",
                    "max_file_budget_seconds": 90,
                    "max_total_measured_seconds": 300,
                    "roster": [{"path": path, "budget_seconds": budget, "reason": "synthetic"} for path in roster],
                },
                "shards": {"job": "architectural-heavy", "shard_count": shard_count, "granularity": "file", "timings_key": "architectural"},
            }
        }
    }


def _build_tree(root: Path, *, extra_check: bool = False, timings: Mapping[str, float] = _TIMINGS, slow_alpha: float = 0.0, budget: int = 10) -> tuple[Path, Path]:
    tests = root / _TESTS_DIR
    (tests / "sub").mkdir(parents=True)
    (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    conftest = "import pytest\n\n\n@pytest.fixture\ndef shared_value():\n    return 7\n"
    if extra_check:
        conftest += _EXTRA_CHECK_CONFTEST_HOOK
        (tests / "extra_check.py").write_text(_TRIVIAL_TEST, encoding="utf-8")
    (tests / "conftest.py").write_text(conftest, encoding="utf-8")
    (tests / "_helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    uses_fixture = "def test_ok(shared_value):\n    assert shared_value == 7\n"
    slow_fixture = f"import time\n\n\ndef test_ok(shared_value):\n    time.sleep({slow_alpha})\n    assert shared_value == 7\n"
    uses_helper = "from _helper import VALUE\n\n\ndef test_ok():\n    assert VALUE == 1\n"
    names = ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "juliet", "deselected")
    for name in names:
        body = uses_helper if name == "charlie" else uses_fixture if name in {"alpha", "bravo"} else _TRIVIAL_TEST
        if name == "alpha" and slow_alpha:
            body = slow_fixture
        (tests / f"test_{name}.py").write_text(body, encoding="utf-8")
    (tests / "sub" / "test_india.py").write_text(_TRIVIAL_TEST, encoding="utf-8")
    registry = root / "registry.yml"
    registry.write_text(yaml.safe_dump(_registry_payload(budget=budget)), encoding="utf-8")
    timings_path = root / "timings.json"
    timings_path.write_text(json.dumps({"battery_file_durations": {"architectural": dict(timings)}}), encoding="utf-8")
    return registry, timings_path


@dataclass(frozen=True)
class _Tree:
    root: Path
    registry: Path
    timings: Path

    @property
    def base_files(self) -> tuple[str, ...]:
        return enumerate_base_files([_TESTS_DIR], deselect=[_DESELECTED], root=self.root)

    def expected_part(self, part: str, timings: Mapping[str, float] = _TIMINGS) -> frozenset[str]:
        return battery_parts(self.base_files, list(_ROSTER), 2, timings).parts[part]


@dataclass(frozen=True)
class _Run:
    proc: subprocess.CompletedProcess[str]
    junit: Path

    @property
    def output(self) -> str:
        return self.proc.stdout + self.proc.stderr

    def executed(self, base_files: Sequence[str]) -> frozenset[str]:
        return frozenset(junit_capture([self.junit], base_files).seconds)


def _make_tree(root: Path, **kwargs: Any) -> _Tree:
    registry, timings = _build_tree(root, **kwargs)
    return _Tree(root, registry, timings)


def _run(
    tree: _Tree,
    part: str | None,
    *,
    n: int = 0,
    marker: str | None = _BASE_MARKER,
    deselect_args: Sequence[str] | None = None,
    extra: Sequence[str] = (),
    env: Mapping[str, str] | None = None,
    collect_only: bool = False,
    explicit_files: bool = True,
    tag: str = "run",
) -> _Run:
    """One pytest subprocess over the synthetic tree, from the REAL repo root with no PYTHONPATH."""
    junit = tree.root / f"{tag}.xml"
    deselects = [f"--deselect={_DESELECTED}"] if deselect_args is None else list(deselect_args)
    argv = [sys.executable, "-m", "pytest", str(tree.root / _TESTS_DIR)]
    if marker is not None:
        argv += ["-m", marker]
    argv += deselects
    argv += ["-p", "scripts.ci.battery_partition_plugin"]
    if part is not None:
        argv += ["--battery-part", part]
    if explicit_files:
        argv += ["--battery-registry", str(tree.registry), "--battery-timings", str(tree.timings)]
    argv += ["--rootdir", str(tree.root), "-c", str(tree.root / "pytest.ini"), "-p", "no:cacheprovider", "-q"]
    if n:
        argv += ["-n", str(n), "--dist", "loadfile"]
    if collect_only:
        argv += ["--collect-only"]
    else:
        argv += ["--junitxml", str(junit)]
    argv += list(extra)
    environment = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "GITHUB_ACTIONS", "GITHUB_STEP_SUMMARY"}}
    environment.update(env or {})
    proc = subprocess.run(argv, cwd=_REPO_ROOT, env=environment, capture_output=True, text=True, timeout=120, check=False)
    return _Run(proc, junit)


@pytest.fixture(scope="module")
def tree(tmp_path_factory: pytest.TempPathFactory) -> _Tree:
    return _make_tree(tmp_path_factory.mktemp("battery"))


@pytest.fixture(scope="module")
def executed_sets(tree: _Tree) -> Iterator[dict[tuple[str, int], frozenset[str]]]:
    """Run each part at ``-n 0`` and ``-n 2`` once; the executed-file sets, keyed ``(part, n)``."""
    results: dict[tuple[str, int], frozenset[str]] = {}
    for part in _PARTS:
        for n in (0, 2):
            run = _run(tree, part, n=n, tag=f"{part.replace('/', '-')}-n{n}")
            assert run.proc.returncode == 0, f"{part} -n {n}: {run.output}"
            results[(part, n)] = run.executed(tree.base_files)
    yield results


# ---------------------------------------------------------------------------
# Production path: each part executes exactly its files, in the controller and in xdist workers
# ---------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.parametrize("n", [0, 2])
@pytest.mark.parametrize("part", _PARTS)
def test_each_part_executes_exactly_its_files(tree: _Tree, executed_sets: dict[tuple[str, int], frozenset[str]], part: str, n: int) -> None:
    assert executed_sets[(part, n)] == tree.expected_part(part)
    assert executed_sets[(part, n)], "a part must execute at least one file (non-vacuous)"


@pytest.mark.slow
@pytest.mark.parametrize("n", [0, 2])
def test_parts_are_complete_and_pairwise_disjoint(tree: _Tree, executed_sets: dict[tuple[str, int], frozenset[str]], n: int) -> None:
    sets = [executed_sets[(part, n)] for part in _PARTS]
    assert frozenset().union(*sets) == frozenset(tree.base_files)
    assert sum(len(s) for s in sets) == len(tree.base_files), "a file ran in two parts"
    assert _DESELECTED not in frozenset().union(*sets)


@pytest.mark.slow
def test_conftest_and_private_helpers_are_never_ignored(tree: _Tree) -> None:
    """The fixture-bearing conftest and the ``_helper`` import still resolve in a part that excludes alpha/bravo's siblings."""
    run = _run(tree, "2/2", tag="helpers")
    assert run.proc.returncode == 0, run.output
    assert "fixture 'shared_value' not found" not in run.output


@pytest.mark.slow
def test_part_without_flag_is_inert(tree: _Tree) -> None:
    run = _run(tree, None, tag="inert")
    assert run.proc.returncode == 0, run.output
    assert run.executed(tree.base_files) == frozenset(tree.base_files)


@pytest.mark.slow
def test_collect_only_collects_only_the_part(tree: _Tree) -> None:
    run = _run(tree, "1/2", collect_only=True, tag="collect")
    assert run.proc.returncode == 0, run.output
    collected = {line.split("::")[0] for line in run.proc.stdout.splitlines() if "::" in line}
    assert collected == set(tree.expected_part("1/2"))


# ---------------------------------------------------------------------------
# Production path: fail-closed validation
# ---------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.parametrize("part", ["3/2", "1/3", "0/2", "fast/2", "x"])
def test_bad_part_is_a_usage_error_naming_the_registry(tree: _Tree, part: str) -> None:
    run = _run(tree, part, tag="badpart")
    assert run.proc.returncode == _USAGE_ERROR, run.output
    assert "registry" in run.output


@pytest.mark.slow
def test_registry_and_timings_default_to_the_rootpath_github_files(tmp_path: Path) -> None:
    tree = _make_tree(tmp_path)
    github = tmp_path / ".github"
    github.mkdir()
    (github / "ci-module-registry.yml").write_text(tree.registry.read_text(encoding="utf-8"), encoding="utf-8")
    (github / "ci-shard-timings.json").write_text(tree.timings.read_text(encoding="utf-8"), encoding="utf-8")
    run = _run(tree, "1/2", explicit_files=False, tag="defaults")
    assert run.proc.returncode == 0, run.output
    assert run.executed(tree.base_files) == tree.expected_part("1/2")


@pytest.mark.slow
def test_a_missing_registry_file_is_a_usage_error(tmp_path: Path) -> None:
    tree = _make_tree(tmp_path)
    run = _run(tree, "fast", explicit_files=False, tag="no-registry")
    assert run.proc.returncode == _USAGE_ERROR, run.output
    assert "registry file not found" in run.output


@pytest.mark.slow
def test_a_missing_timings_file_is_a_usage_error(tmp_path: Path) -> None:
    tree = _make_tree(tmp_path)
    github = tmp_path / ".github"
    github.mkdir()
    (github / "ci-module-registry.yml").write_text(tree.registry.read_text(encoding="utf-8"), encoding="utf-8")
    run = _run(tree, "fast", explicit_files=False, tag="no-timings")
    assert run.proc.returncode == _USAGE_ERROR, run.output
    assert "timings file not found" in run.output


@pytest.mark.slow
def test_timings_under_another_key_do_not_count_as_timings(tmp_path: Path) -> None:
    """The plugin reads ``battery_file_durations[timings_key]`` -- a table under another key is 'no timings'."""
    tree = _make_tree(tmp_path)
    tree.timings.write_text(json.dumps({"battery_file_durations": {"other": dict(_TIMINGS)}}), encoding="utf-8")
    run = _run(tree, "1/2", tag="other-key")
    assert run.proc.returncode == 0, run.output
    assert "no timings for this key" in run.output


@pytest.mark.slow
def test_missing_marker_is_a_usage_error(tree: _Tree) -> None:
    run = _run(tree, "fast", marker=None, tag="nomarker")
    assert run.proc.returncode == _USAGE_ERROR, run.output
    assert "marker" in run.output


@pytest.mark.slow
def test_different_marker_is_a_usage_error(tree: _Tree) -> None:
    run = _run(tree, "fast", marker="not performance", tag="othermarker")
    assert run.proc.returncode == _USAGE_ERROR, run.output


@pytest.mark.slow
@pytest.mark.parametrize(
    "deselect_args",
    [
        [],
        [f"--deselect={_DESELECTED}", f"--deselect={_TESTS_DIR}/test_alpha.py::test_ok"],
        [f"--deselect={_DESELECTED}", f"--deselect={_TESTS_DIR}/test_bravo.py"],
    ],
    ids=["missing-deselect", "extra-node-level-deselect", "extra-whole-file-deselect"],
)
def test_deselect_set_differing_from_the_registry_base_is_a_usage_error(tree: _Tree, deselect_args: list[str]) -> None:
    run = _run(tree, "fast", deselect_args=deselect_args, tag="deselect")
    assert run.proc.returncode == _USAGE_ERROR, run.output
    assert "deselect" in run.output


@pytest.mark.slow
def test_different_path_is_a_usage_error(tree: _Tree) -> None:
    run = _run(tree, "fast", extra=[str(tree.root / _TESTS_DIR / "sub")], tag="otherpath")
    assert run.proc.returncode == _USAGE_ERROR, run.output
    assert "paths" in run.output


@pytest.mark.slow
def test_ignore_of_the_whole_file_is_an_accepted_deselect_equivalent(tree: _Tree) -> None:
    """The gate model's ``collect_job_nodeids`` passes the base deselects as ``--ignore=<file>``."""
    run = _run(tree, "1/2", deselect_args=[f"--ignore={tree.root / _DESELECTED}"], tag="ignore-eq")
    assert run.proc.returncode == 0, run.output
    assert run.executed(tree.base_files) == tree.expected_part("1/2")


@pytest.mark.slow
def test_ignore_of_a_directory_is_still_rejected(tree: _Tree) -> None:
    deselect_args = [f"--deselect={_DESELECTED}", f"--ignore={tree.root / _TESTS_DIR / 'sub'}"]
    run = _run(tree, "fast", deselect_args=deselect_args, tag="ignore-dir")
    assert run.proc.returncode == _USAGE_ERROR, run.output


@pytest.mark.slow
def test_worker_count_must_match_the_registry_on_ci(tree: _Tree) -> None:
    run = _run(tree, "1/2", n=1, env={"GITHUB_ACTIONS": "true"}, tag="workers-ci")
    assert run.proc.returncode == _USAGE_ERROR, run.output
    assert "workers" in run.output


@pytest.mark.slow
def test_matching_worker_count_is_accepted_on_ci(tree: _Tree) -> None:
    run = _run(tree, "1/2", n=2, env={"GITHUB_ACTIONS": "true"}, tag="workers-ci-ok")
    assert run.proc.returncode == 0, run.output


@pytest.mark.slow
def test_worker_count_is_not_enforced_off_ci(tree: _Tree) -> None:
    run = _run(tree, "1/2", n=1, tag="workers-local")
    assert run.proc.returncode == 0, run.output


@pytest.mark.slow
def test_worker_check_is_skipped_under_collect_only_on_ci(tree: _Tree) -> None:
    """``collect_job_nodeids`` collects a part without ``-n``; on CI ``GITHUB_ACTIONS`` is set for it too."""
    run = _run(tree, "1/2", collect_only=True, env={"GITHUB_ACTIONS": "true"}, tag="collect-ci")
    assert run.proc.returncode == 0, run.output


# ---------------------------------------------------------------------------
# Production path: the runtime self-check and the digest cross-check
# ---------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.parametrize("n", [0, 2])
@pytest.mark.parametrize("part", _PARTS)
def test_self_check_fails_the_session_when_a_non_enumerated_file_executes(tmp_path: Path, part: str, n: int) -> None:
    """Positive control: a conftest-collected ``extra_check.py`` is outside the enumeration -- the realistic gap."""
    tree = _make_tree(tmp_path, extra_check=True)
    run = _run(tree, part, n=n, tag="selfcheck")
    assert run.proc.returncode == _TESTS_FAILED, run.output
    error_lines = [line for line in run.output.splitlines() if line.startswith("::error")]
    assert error_lines, run.output
    assert "extra_check.py" in error_lines[0]
    assert "passed" in run.output, "the offending test itself passed: only the self-check fails the session"


@pytest.mark.slow
def test_self_check_is_silent_when_every_executed_file_is_in_the_part(tree: _Tree) -> None:
    run = _run(tree, "fast", n=2, tag="selfcheck-clean")
    assert run.proc.returncode == 0
    assert "::error" not in run.output


@pytest.mark.slow
def test_a_worker_computing_a_different_part_fails_the_run(tree: _Tree, tmp_path: Path) -> None:
    """D-23: workers cross-check the controller's digest from ``workerinput`` -- a tampered worker is refused."""
    (tmp_path / "tamper_plugin.py").write_text(_TAMPER_PLUGIN, encoding="utf-8")
    env = {"PYTHONPATH": f"{tmp_path}"}
    tampered = _run(tree, "1/2", n=2, extra=["-p", "tamper_plugin"], env=env, tag="tamper")
    control = _run(tree, "1/2", n=2, env=env, tag="tamper-control")
    assert control.proc.returncode == 0, control.output
    assert tampered.proc.returncode != 0, tampered.output
    assert "digest" in tampered.output


@pytest.mark.slow
def test_missing_timing_is_reported_once_by_the_plugin_not_per_worker(tmp_path: Path) -> None:
    """FR-005, production path: the plugin's own annotation and ONE step-summary line, controller only."""
    missing = f"{_TESTS_DIR}/test_juliet.py"
    tree = _make_tree(tmp_path, timings={k: v for k, v in _TIMINGS.items() if k != missing})
    summary = tmp_path / "step-summary.md"
    run = _run(tree, "1/2", n=2, env={"GITHUB_STEP_SUMMARY": str(summary)}, tag="fr005")
    assert run.proc.returncode == 0, run.output
    warnings = [line for line in run.proc.stdout.splitlines() if line.startswith(_WARNING_PREFIX)]
    assert len(warnings) == 1, run.output
    assert missing in warnings[0]
    mismatch_lines = [line for line in summary.read_text(encoding="utf-8").splitlines() if line.startswith("- shard timings")]
    assert len(mismatch_lines) == 1, summary.read_text(encoding="utf-8")
    assert missing in mismatch_lines[0]


@pytest.mark.slow
def test_a_roster_file_over_its_budget_warns_once_and_never_fails_the_fast_part(tmp_path: Path) -> None:
    """Runtime overruns are warnings only (runner spread would make a hard budget a flake class)."""
    tree = _make_tree(tmp_path, slow_alpha=1.3, budget=1)
    summary = tmp_path / "step-summary-budget.md"
    run = _run(tree, "fast", n=2, env={"GITHUB_STEP_SUMMARY": str(summary)}, tag="budget")
    assert run.proc.returncode == 0, run.output
    warnings = [line for line in run.proc.stdout.splitlines() if line.startswith("::warning title=battery budget::")]
    assert len(warnings) == 1, run.output
    assert f"{_TESTS_DIR}/test_alpha.py" in warnings[0]
    assert "1s roster budget" in warnings[0]
    assert "::warning title=battery budget::" in summary.read_text(encoding="utf-8")


@pytest.mark.slow
def test_complete_timings_emit_no_mismatch_annotation(tree: _Tree) -> None:
    run = _run(tree, "1/2", tag="fr005-clean")
    assert _WARNING_PREFIX not in run.output


@pytest.mark.slow
def test_the_part_summary_reaches_the_log_and_the_step_summary(tree: _Tree, tmp_path: Path) -> None:
    summary = tmp_path / "step-summary-part.md"
    run = _run(tree, "2/2", n=2, env={"GITHUB_STEP_SUMMARY": str(summary)}, tag="summary")
    assert run.proc.returncode == 0, run.output
    expected = tree.expected_part("2/2")
    for text in (run.output, summary.read_text(encoding="utf-8")):
        assert "battery part 2/2" in text
        assert f"{len(expected)} files" in text
        assert "gw0" in text
        assert "gw1" in text
        assert "slowest test" in text
    assert "test_ok" in run.output


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------
@pytest.mark.fast
@pytest.mark.parametrize(
    ("value", "key", "fast"),
    [("fast", "fast", True), ("1/2", "1/2", False), ("2/2", "2/2", False), ("3/7", "3/7", False)],
)
def test_parse_part_accepts_fast_and_numbered_parts(value: str, key: str, fast: bool) -> None:
    part = plugin.parse_part(value)
    assert part.key == key
    assert part.is_fast is fast


@pytest.mark.fast
def test_parse_part_exposes_index_and_total() -> None:
    part = plugin.parse_part("2/5")
    assert (part.index, part.total) == (2, 5)
    fast = plugin.parse_part("fast")
    assert (fast.index, fast.total) == (None, None)


@pytest.mark.fast
@pytest.mark.parametrize("value", ["", "0/2", "3/2", "1/0", "-1/2", "a/b", "1/2/3", "FAST", "1", "/2", "1/"])
def test_parse_part_rejects_everything_else(value: str) -> None:
    with pytest.raises(ValueError, match="battery-part"):
        plugin.parse_part(value)


@pytest.mark.fast
def test_load_battery_spec_mirrors_the_registry_schema() -> None:
    spec = plugin.load_battery_spec(_registry_payload(workers=4, shard_count=3))
    assert spec.workers == 4
    assert spec.shard_count == 3
    assert spec.timings_key == "architectural"
    assert spec.base.paths == (_TESTS_DIR,)
    assert spec.base.marker == _BASE_MARKER
    assert spec.base.deselect == (_DESELECTED,)
    assert spec.roster_paths == _ROSTER
    assert [entry.budget_seconds for entry in spec.roster] == [10, 10, 10]
    assert spec.fast_job == "architectural-fast"
    assert spec.shards_job == "architectural-heavy"
    assert spec.max_file_budget_seconds == 90
    assert spec.max_total_measured_seconds == 300


def _drop(payload: dict[str, Any], *path: str) -> dict[str, Any]:
    node = payload["special_tiers"]["architectural"]
    for key in path[:-1]:
        node = node[key]
    del node[path[-1]]
    return payload


def _set(payload: dict[str, Any], value: Any, *path: str) -> dict[str, Any]:
    node = payload["special_tiers"]["architectural"]
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return payload


_BROKEN_REGISTRIES = [
    ({}, "special_tiers"),
    ({"special_tiers": {}}, "special_tiers.architectural"),
    (_drop(_registry_payload(), "workers"), "special_tiers.architectural.workers"),
    (_set(_registry_payload(), 0, "workers"), "special_tiers.architectural.workers"),
    (_set(_registry_payload(), True, "workers"), "special_tiers.architectural.workers"),
    (_drop(_registry_payload(), "base"), "special_tiers.architectural.base"),
    (_set(_registry_payload(), [], "base", "paths"), "special_tiers.architectural.base.paths"),
    (_set(_registry_payload(), [""], "base", "paths"), "special_tiers.architectural.base.paths"),
    (_set(_registry_payload(), [1], "base", "paths"), "special_tiers.architectural.base.paths"),
    (_set(_registry_payload(), "", "base", "marker"), "special_tiers.architectural.base.marker"),
    (_set(_registry_payload(), "x", "base", "deselect"), "special_tiers.architectural.base.deselect"),
    (_drop(_registry_payload(), "fast_gate", "roster"), "special_tiers.architectural.fast_gate.roster"),
    (_set(_registry_payload(), [{"path": "a.py"}], "fast_gate", "roster"), "special_tiers.architectural.fast_gate.roster[0]"),
    (_set(_registry_payload(), [{"path": "", "budget_seconds": 1, "reason": "r"}], "fast_gate", "roster"), "special_tiers.architectural.fast_gate.roster[0].path"),
    (_drop(_registry_payload(), "shards", "shard_count"), "special_tiers.architectural.shards.shard_count"),
    (_set(_registry_payload(), 0, "shards", "shard_count"), "special_tiers.architectural.shards.shard_count"),
    (_set(_registry_payload(), "", "shards", "timings_key"), "special_tiers.architectural.shards.timings_key"),
]


@pytest.mark.fast
@pytest.mark.parametrize(("registry", "key_path"), _BROKEN_REGISTRIES, ids=[path for _, path in _BROKEN_REGISTRIES])
def test_load_battery_spec_names_the_key_path_of_any_schema_problem(registry: dict[str, Any], key_path: str) -> None:
    with pytest.raises(ValueError, match=key_path.replace("[", r"\[").replace("]", r"\]")):
        plugin.load_battery_spec(registry)


@pytest.mark.fast
def test_load_battery_timings_returns_the_key_or_nothing() -> None:
    payload = {"battery_file_durations": {"architectural": {"a.py": 1.5}}}
    assert plugin.load_battery_timings(payload, "architectural") == {"a.py": 1.5}
    assert plugin.load_battery_timings(payload, "other") == {}
    assert plugin.load_battery_timings({}, "architectural") == {}
    assert plugin.load_battery_timings({"battery_file_durations": {"architectural": {"a.py": 2}}}, "architectural") == {"a.py": 2.0}


@pytest.mark.fast
@pytest.mark.parametrize("bad", ["slow", True, None, [1.0]])
def test_load_battery_timings_rejects_a_non_numeric_entry(bad: object) -> None:
    with pytest.raises(ValueError, match="battery_file_durations"):
        plugin.load_battery_timings({"battery_file_durations": {"architectural": {"a.py": bad}}}, "architectural")


def _spec() -> Any:
    return plugin.load_battery_spec(_registry_payload())


@pytest.mark.fast
def test_invocation_matching_the_base_has_no_mismatch() -> None:
    assert plugin.invocation_mismatches([_TESTS_DIR], _BASE_MARKER, [_DESELECTED], [], _spec()) == []


@pytest.mark.fast
def test_invocation_accepts_whole_file_ignore_as_deselect_and_their_union() -> None:
    assert plugin.invocation_mismatches([_TESTS_DIR], _BASE_MARKER, [], [_DESELECTED], _spec()) == []
    spec = plugin.load_battery_spec(_set(_registry_payload(), [_DESELECTED, f"{_TESTS_DIR}/test_x.py"], "base", "deselect"))
    assert plugin.invocation_mismatches([_TESTS_DIR], _BASE_MARKER, [_DESELECTED], [f"{_TESTS_DIR}/test_x.py"], spec) == []


@pytest.mark.fast
@pytest.mark.parametrize(
    ("paths", "marker", "deselects", "ignores", "word"),
    [
        (["tests"], _BASE_MARKER, [_DESELECTED], [], "paths"),
        ([_TESTS_DIR, "tests/other"], _BASE_MARKER, [_DESELECTED], [], "paths"),
        ([], _BASE_MARKER, [_DESELECTED], [], "paths"),
        ([_TESTS_DIR], None, [_DESELECTED], [], "marker"),
        ([_TESTS_DIR], "not performance", [_DESELECTED], [], "marker"),
        ([_TESTS_DIR], _BASE_MARKER, [], [], "deselect"),
        ([_TESTS_DIR], _BASE_MARKER, [_DESELECTED, f"{_TESTS_DIR}/test_alpha.py::test_ok"], [], "deselect"),
        ([_TESTS_DIR], _BASE_MARKER, [_DESELECTED], [f"{_TESTS_DIR}/sub"], "deselect"),
    ],
)
def test_invocation_mismatches_name_the_differing_aspect(paths: list[str], marker: str | None, deselects: list[str], ignores: list[str], word: str) -> None:
    problems = plugin.invocation_mismatches(paths, marker, deselects, ignores, _spec())
    assert len(problems) == 1
    assert word in problems[0]


@pytest.mark.fast
def test_invocation_mismatches_reports_every_differing_aspect() -> None:
    assert len(plugin.invocation_mismatches(["tests"], None, [], [], _spec())) == 3


@pytest.mark.fast
def test_invocation_path_comparison_ignores_order_and_duplicates() -> None:
    spec = plugin.load_battery_spec(_set(_registry_payload(), ["tests/b", "tests/a"], "base", "paths"))
    assert plugin.invocation_mismatches(["tests/a", "tests/b", "tests/a"], _BASE_MARKER, [_DESELECTED], [], spec) == []


@pytest.mark.fast
def test_relativize_arg_resolves_against_the_invocation_dir_and_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / "tests").mkdir(parents=True)
    assert plugin.relativize_arg(str(root / "tests"), base_dir=tmp_path, root=root) == "tests"
    assert plugin.relativize_arg("root/tests/", base_dir=tmp_path, root=root) == "tests"
    assert plugin.relativize_arg("tests", base_dir=root, root=root) == "tests"
    assert plugin.relativize_arg("./tests/x.py", base_dir=root, root=root) == "tests/x.py"
    assert plugin.relativize_arg("tests/x.py::test_a", base_dir=root, root=root) == "tests/x.py::test_a"
    assert plugin.relativize_arg(str(tmp_path / "elsewhere"), base_dir=root, root=root) == str(tmp_path / "elsewhere")
    assert plugin.relativize_arg("../elsewhere", base_dir=root, root=root) == "../elsewhere"


@pytest.mark.fast
def test_normalise_node_prefix_strips_dot_slash_and_absolute_root(tmp_path: Path) -> None:
    assert plugin.normalise_deselect("./tests/x.py", root=tmp_path) == "tests/x.py"
    assert plugin.normalise_deselect(str(tmp_path / "tests" / "x.py"), root=tmp_path) == "tests/x.py"
    assert plugin.normalise_deselect("tests/x.py::t", root=tmp_path) == "tests/x.py::t"


@pytest.mark.fast
def test_compute_partition_uses_the_one_enumeration_and_selector(tmp_path: Path) -> None:
    tree = _make_tree(tmp_path)
    partition = plugin.compute_partition(_spec(), tree.root, dict(_TIMINGS))
    reference = battery_parts(tree.base_files, list(_ROSTER), 2, _TIMINGS)
    assert partition.parts == reference.parts
    assert partition.loads == reference.loads


@pytest.mark.fast
def test_part_digest_is_order_independent_and_content_sensitive() -> None:
    assert plugin.part_digest(["b", "a"]) == plugin.part_digest(["a", "b"])
    assert plugin.part_digest(frozenset({"a", "b"})) == plugin.part_digest(["a", "b"])
    assert plugin.part_digest(["a"]) != plugin.part_digest(["a", "b"])
    assert plugin.part_digest([]) != plugin.part_digest(["a"])
    assert len(plugin.part_digest(["a"])) == 64


def _partition_of_the_synthetic_base() -> Any:
    base = [*_ROSTER, *(f"{_TESTS_DIR}/test_{name}.py" for name in _NON_ROSTER)]
    return base, battery_parts(base, list(_ROSTER), 2, _TIMINGS)


@pytest.mark.fast
def test_build_state_for_the_fast_part() -> None:
    base, partition = _partition_of_the_synthetic_base()
    state = plugin.build_state(plugin.parse_part("fast"), _spec(), partition)
    assert state.part_files == frozenset(_ROSTER)
    assert state.enumerated == frozenset(base)
    assert state.foreign == frozenset(base) - frozenset(_ROSTER)
    assert state.digest == plugin.part_digest(_ROSTER)
    assert state.predicted_load is None
    assert state.budgets == dict.fromkeys(_ROSTER, 10)


@pytest.mark.fast
@pytest.mark.parametrize("key", ["1/2", "2/2"])
def test_build_state_for_a_numbered_part(key: str) -> None:
    base, partition = _partition_of_the_synthetic_base()
    state = plugin.build_state(plugin.parse_part(key), _spec(), partition)
    assert state.part_files == partition.parts[key]
    assert state.enumerated == frozenset(base)
    assert state.digest == plugin.part_digest(partition.parts[key])
    assert state.predicted_load == partition.loads[key]
    assert state.budgets == {}


@pytest.mark.fast
def test_files_outside_part_lists_only_the_foreign_files_sorted() -> None:
    assert plugin.files_outside_part({"b.py", "a.py", "c.py"}, frozenset({"a.py"})) == ["b.py", "c.py"]
    assert plugin.files_outside_part({"a.py"}, frozenset({"a.py", "b.py"})) == []
    assert plugin.files_outside_part(set(), frozenset({"a.py"})) == []


@pytest.mark.fast
@pytest.mark.parametrize(
    ("numprocesses", "workers", "github_actions", "collect_only", "problem"),
    [
        (4, 4, True, False, False),
        (2, 4, True, False, True),
        (None, 4, True, False, True),
        (0, 4, True, False, True),
        (2, 4, False, False, False),
        (None, 4, False, False, False),
        (None, 4, True, True, False),
        (1, 4, True, True, False),
    ],
)
def test_worker_count_problem_applies_on_ci_only_and_never_under_collect_only(
    numprocesses: int | None, workers: int, github_actions: bool, collect_only: bool, problem: bool
) -> None:
    message = plugin.worker_count_problem(numprocesses, workers, github_actions=github_actions, collect_only=collect_only)
    assert (message is not None) is problem
    if message:
        assert "workers" in message
        assert str(workers) in message


@pytest.mark.fast
@pytest.mark.parametrize(("value", "expected"), [("true", True), ("True", False), ("false", False), ("", False), (None, False)])
def test_running_on_github_actions_reads_the_env_literal(value: str | None, expected: bool) -> None:
    env = {} if value is None else {"GITHUB_ACTIONS": value}
    assert plugin.running_on_github_actions(env) is expected


@pytest.mark.fast
@pytest.mark.parametrize(
    ("current", "outside", "expected"),
    [
        (0, ["a.py"], 1),
        (0, [], 0),
        (1, ["a.py"], 1),
        (2, ["a.py"], 2),
        (3, ["a.py"], 3),
        (4, ["a.py"], 4),
        (5, ["a.py"], 5),
        (1, [], 1),
    ],
)
def test_escalated_exitstatus_only_turns_a_pass_into_a_failure(current: int, outside: list[str], expected: int) -> None:
    assert int(plugin.escalated_exitstatus(current, outside)) == expected


@pytest.mark.fast
def test_run_stats_accumulates_phases_per_file_and_test() -> None:
    stats = plugin.RunStats()
    for nodeid, seconds in (("t/a.py::t1", 1.0), ("t/a.py::t1", 0.5), ("t/a.py::t2", 4.0), ("t/b.py::t1", 2.0)):
        stats.record(nodeid, seconds)
    assert stats.file_seconds == {"t/a.py": 5.5, "t/b.py": 2.0}
    assert stats.test_seconds["t/a.py::t1"] == 1.5
    assert stats.executed_files == {"t/a.py", "t/b.py"}
    assert stats.slowest() == ("t/a.py::t2", 4.0)
    assert plugin.RunStats().slowest() is None


@pytest.mark.fast
def test_summary_lines_list_part_files_load_workers_slowest_and_top_files() -> None:
    stats = plugin.RunStats()
    for index in range(12):
        stats.record(f"t/f{index:02}.py::t", float(index))
    stats.workers.update({f"gw{index}" for index in (7, 3, 5, 1, 6, 0, 4, 2)})
    lines = plugin.summary_lines(plugin.parse_part("1/2"), file_count=12, predicted_load=33.5, stats=stats)
    text = "\n".join(lines)
    assert "battery part 1/2" in text
    assert "12 files" in text
    assert "predicted load 33.5s" in text
    assert "gw0, gw1, gw2, gw3, gw4, gw5, gw6, gw7" in text
    assert "slowest test: t/f11.py::t" in text
    assert "t/f11.py: 11.0s" in text
    assert "t/f02.py: 2.0s" in text
    assert "t/f01.py" not in text, "only the top 10 files are listed"
    assert text.index("t/f11.py: ") < text.index("t/f10.py: ")


@pytest.mark.fast
def test_summary_lines_for_fast_part_omit_the_predicted_load_and_name_a_local_run() -> None:
    lines = plugin.summary_lines(plugin.parse_part("fast"), file_count=3, predicted_load=None, stats=plugin.RunStats())
    text = "\n".join(lines)
    assert "battery part fast" in text
    assert "predicted load" not in text
    assert "main" in text, "no worker ids -> the single process"


@pytest.mark.fast
def test_overrun_warnings_cover_roster_budgets_and_slow_tests() -> None:
    stats = plugin.RunStats()
    stats.record("t/a.py::t1", 95.0)
    stats.record("t/b.py::t1", 10.0)
    stats.record("t/c.py::t1", 181.0)
    budgets = {"t/a.py": 90, "t/b.py": 10, "t/c.py": 500}
    warnings = plugin.overrun_warnings(stats, budgets)
    assert [w for w in warnings if w.startswith("::warning title=battery budget::")] == [
        "::warning title=battery budget::t/a.py: 95.0s exceeds its 90s roster budget"
    ]
    slow = [w for w in warnings if w.startswith("::warning title=slow test::")]
    assert len(slow) == 1
    assert "t/c.py::t1" in slow[0]
    assert plugin.overrun_warnings(stats, {}) == slow


@pytest.mark.fast
def test_slow_test_threshold_is_exclusive() -> None:
    stats = plugin.RunStats()
    stats.record("t/a.py::t1", 180.0)
    assert plugin.overrun_warnings(stats, {}) == []


@pytest.mark.fast
def test_write_step_summary_appends_only_when_the_env_names_a_file(tmp_path: Path) -> None:
    target = tmp_path / "summary.md"
    plugin.write_step_summary(["a", "b"], env={})
    plugin.write_step_summary(["a", "b"], env={"GITHUB_STEP_SUMMARY": str(target)})
    plugin.write_step_summary(["c"], env={"GITHUB_STEP_SUMMARY": str(target)})
    assert target.read_text(encoding="utf-8") == "a\nb\nc\n"


# ---------------------------------------------------------------------------
# Hook decision code, called directly
# ---------------------------------------------------------------------------
def _state(part_files: set[str], enumerated: set[str], digest: str = "d") -> Any:
    return plugin.PartitionState(
        part=plugin.parse_part("1/2"),
        part_files=frozenset(part_files),
        enumerated=frozenset(enumerated),
        digest=digest,
        predicted_load=1.0,
        budgets={},
    )


def _config(tmp_path: Path, state: Any | None) -> Any:
    stash = pytest.Stash()
    if state is not None:
        stash[plugin.PARTITION_STATE_KEY] = state
    return types.SimpleNamespace(stash=stash, rootpath=tmp_path)


@pytest.mark.fast
def test_ignore_collect_ignores_only_enumerated_files_outside_the_part(tmp_path: Path) -> None:
    for name in ("in_part.py", "outside.py", "other.py", "conftest.py", "_helper.py"):
        (tmp_path / name).write_text("", encoding="utf-8")
    (tmp_path / "pkg").mkdir()
    config = _config(tmp_path, _state({"in_part.py"}, {"in_part.py", "outside.py", "pkg"}))
    ignored = plugin.pytest_ignore_collect(tmp_path / "outside.py", config)
    assert ignored is True
    for kept in ("in_part.py", "other.py", "conftest.py", "_helper.py", "pkg"):
        assert plugin.pytest_ignore_collect(tmp_path / kept, config) is None, f"{kept} must not be ignored"


@pytest.mark.fast
def test_ignore_collect_never_returns_false_and_is_inert_without_state(tmp_path: Path) -> None:
    (tmp_path / "outside.py").write_text("", encoding="utf-8")
    assert plugin.pytest_ignore_collect(tmp_path / "outside.py", _config(tmp_path, None)) is None
    config = _config(tmp_path, _state(set(), {"x.py"}))
    assert plugin.pytest_ignore_collect(tmp_path / "outside.py", config) is None
    assert plugin.pytest_ignore_collect(tmp_path.parent / "elsewhere.py", config) is None


@pytest.mark.fast
def test_ignore_collect_does_not_ignore_a_directory_named_like_an_enumerated_file(tmp_path: Path) -> None:
    (tmp_path / "outside.py").mkdir()
    config = _config(tmp_path, _state(set(), {"outside.py"}))
    assert plugin.pytest_ignore_collect(tmp_path / "outside.py", config) is None


@pytest.mark.fast
def test_configure_node_ships_the_digest_to_the_worker() -> None:
    runtime = plugin.BatteryRuntime(_state({"a.py"}, {"a.py"}, digest="abc123"))
    node = types.SimpleNamespace(workerinput={})
    runtime.pytest_configure_node(node)
    assert node.workerinput == {plugin.WORKERINPUT_DIGEST_KEY: "abc123"}


@pytest.mark.fast
def test_testnodeready_records_the_worker_id() -> None:
    runtime = plugin.BatteryRuntime(_state({"a.py"}, {"a.py"}))
    runtime.pytest_testnodeready(types.SimpleNamespace(gateway=types.SimpleNamespace(id="gw3")))
    assert runtime.stats.workers == {"gw3"}


@pytest.mark.fast
def test_verify_worker_digest_accepts_equal_and_refuses_different() -> None:
    state = _state({"a.py"}, {"a.py"}, digest="same")
    plugin.verify_worker_digest(state, {plugin.WORKERINPUT_DIGEST_KEY: "same"})
    with pytest.raises(pytest.UsageError, match="digest"):
        plugin.verify_worker_digest(state, {plugin.WORKERINPUT_DIGEST_KEY: "other"})
    with pytest.raises(pytest.UsageError, match="digest"):
        plugin.verify_worker_digest(state, {})


_Phase = Literal["setup", "call", "teardown"]


def _FakeReport(nodeid: str, duration: float = 0.1, when: _Phase = "call") -> pytest.TestReport:
    """A real ``TestReport`` carrying only what the runtime hook reads (nodeid, duration, phase)."""
    return pytest.TestReport(
        nodeid=nodeid,
        location=(nodeid.split("::")[0], 0, nodeid),
        keywords={},
        outcome="passed",
        longrepr=None,
        when=when,
        duration=duration,
    )


@pytest.mark.fast
def test_runtime_records_every_report_phase_under_the_file() -> None:
    runtime = plugin.BatteryRuntime(_state({"a.py"}, {"a.py"}))
    phases: tuple[_Phase, ...] = ("setup", "call", "teardown")
    for when in phases:
        runtime.pytest_runtest_logreport(_FakeReport("a.py::t", 1.0, when))
    assert runtime.stats.file_seconds == {"a.py": 3.0}


@pytest.mark.fast
def test_runtime_outside_files_compares_against_the_part() -> None:
    runtime = plugin.BatteryRuntime(_state({"a.py"}, {"a.py", "b.py"}))
    runtime.pytest_runtest_logreport(_FakeReport("a.py::t"))
    assert runtime.outside_files() == []
    runtime.pytest_runtest_logreport(_FakeReport("b.py::t"))
    runtime.pytest_runtest_logreport(_FakeReport("extra.py::t"))
    assert runtime.outside_files() == ["b.py", "extra.py"]
