"""Characterization + shape tests for ``scripts/ci/shard_select.py`` (mission
ci-runtime-stabilisation-01M3TZH6, WP01 / T001).

WP01 is a behaviour-preserving extraction: the greedy-LPT shard selector moves
out of an inline ``module-tests.yml`` heredoc into an importable module. The
only real risk is a silent reshuffle of some module row's shard assignment, so
this file pins the extracted algorithm against a **frozen oracle** — the
heredoc's algorithm copied verbatim — for every registry row at its
``shard_count`` over the committed ``.github/ci-shard-timings.json``.
"""

from __future__ import annotations

import json
import os
import random
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci.shard_select import (
    EXIT_NO_TESTS,
    MODULE_SELECTION_MARKER_EXPR,
    lpt_assign,
    lpt_loads,
    main,
    positional_weights,
    resolve_module_test_dirs,
)

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY_PATH = _REPO_ROOT / ".github" / "ci-module-registry.yml"
_TIMINGS_PATH = _REPO_ROOT / ".github" / "ci-shard-timings.json"
_MODULE_TESTS_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "module-tests.yml"

_RANDOM_SEED = 5510
_RANDOM_CASES = 200
_TIE_HEAVY_DURATIONS = [0.0, 0.5, 1.0, 1.0, 2.5]
_MISMATCH_EXTRA_TESTS = 7


def _reference_select(node_ids: list[str], timing_durations: list[float], total: int, idx: int) -> list[str]:
    """FROZEN ORACLE -- the legacy inline selector, copied verbatim.

    Origin: ``.github/workflows/module-tests.yml`` step ``id: select`` (the
    ``<<'PY'`` heredoc, lines 244-262) at lane base ``75f5137d4e``. Only
    the surrounding I/O was dropped and ``strict=True`` was added to ``zip`` (ruff B905; lengths are equal by construction); the uniform fallback, the
    ``sorted(zip(...), reverse=True)`` pairing and the ``min(range(total))``
    least-loaded loop are untouched. Never "tidy" this function: its whole
    value is that it is *not* the code under test.
    """
    durations = list(timing_durations)
    if len(durations) != len(node_ids):
        durations = [1.0] * len(node_ids)

    paired = sorted(zip(node_ids, durations, strict=True), key=lambda pair: pair[1], reverse=True)
    bins: list[list[str]] = [[] for _ in range(total)]
    loads = [0.0] * total
    for node_id, duration in paired:
        least_loaded = min(range(total), key=lambda k: loads[k])
        bins[least_loaded].append(node_id)
        loads[least_loaded] += duration

    return bins[idx - 1]


def _production_items(node_ids: list[str], timing_durations: list[float]) -> list[tuple[str, float]]:
    """Pair ids with weights through the SHIPPED ``positional_weights`` (what the CLI runs).

    Deliberately not a re-implementation: the characterization must fail if the
    shipped weighting drifts from the frozen oracle.
    """
    return list(zip(node_ids, positional_weights(node_ids, timing_durations), strict=True))


def _registry_rows() -> list[dict[str, Any]]:
    payload = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8"))
    return list(payload["modules"])


def _timings() -> dict[str, list[float]]:
    payload = json.loads(_TIMINGS_PATH.read_text(encoding="utf-8"))
    return {k: [float(v) for v in vs] for k, vs in payload["module_test_durations"].items()}


def _row_ids() -> list[str]:
    return [row["module"] for row in _registry_rows()]


@pytest.mark.parametrize("module", _row_ids())
def test_every_registry_row_shard_assignment_is_identical_to_the_legacy_selector(module: str) -> None:
    row = next(r for r in _registry_rows() if r["module"] == module)
    total = int(row["shard_count"])
    durations = _timings()[module]
    node_ids = [f"{module}::t{i}" for i in range(len(durations))]

    for idx in range(1, total + 1):
        expected = _reference_select(node_ids, durations, total, idx)
        actual = lpt_assign(_production_items(node_ids, durations), total)[idx - 1]
        assert actual == expected, f"{module} shard {idx}/{total} diverged from the legacy selector"


@pytest.mark.parametrize("module", ["kernel", "next", "charter"])
def test_length_mismatch_uniform_fallback_assignment_is_identical(module: str) -> None:
    """The silent uniform-weight fallback is pinned too (WP02 makes it loud)."""
    durations = _timings()[module]
    node_ids = [f"{module}::t{i}" for i in range(len(durations) + _MISMATCH_EXTRA_TESTS)]
    total = 3

    for idx in range(1, total + 1):
        expected = _reference_select(node_ids, durations, total, idx)
        actual = lpt_assign(_production_items(node_ids, durations), total)[idx - 1]
        assert actual == expected


def test_randomized_tie_heavy_assignments_match_the_legacy_selector() -> None:
    rng = random.Random(_RANDOM_SEED)
    for case in range(_RANDOM_CASES):
        size = rng.randint(1, 400)
        total = rng.randint(1, 8)
        durations = [rng.choice(_TIE_HEAVY_DURATIONS) for _ in range(size)]
        node_ids = [f"case{case}::t{i}" for i in range(size)]
        expected = [_reference_select(node_ids, durations, total, idx) for idx in range(1, total + 1)]
        assert lpt_assign(list(zip(node_ids, durations, strict=True)), total) == expected, f"case {case}"


def test_lpt_loads_matches_the_bin_loads_of_lpt_assign() -> None:
    rng = random.Random(_RANDOM_SEED)
    for _ in range(_RANDOM_CASES):
        size = rng.randint(1, 120)
        total = rng.randint(1, 8)
        durations = [rng.choice(_TIE_HEAVY_DURATIONS) for _ in range(size)]
        ids = [str(i) for i in range(size)]
        weight = dict(zip(ids, durations, strict=True))
        loads_from_assignment = [sum(weight[i] for i in shard) for shard in lpt_assign(list(zip(ids, durations, strict=True)), total)]
        assert lpt_loads(durations, total) == pytest.approx(loads_from_assignment)


def test_lpt_assign_rejects_fewer_than_one_bin() -> None:
    with pytest.raises(ValueError, match="bins"):
        lpt_assign([("a", 1.0)], 0)
    with pytest.raises(ValueError, match="bins"):
        lpt_loads([1.0], 0)


def _workflow_step(step_id: str) -> dict[str, Any]:
    workflow = yaml.safe_load(_MODULE_TESTS_WORKFLOW.read_text(encoding="utf-8"))
    for step in workflow["jobs"]["test"]["steps"]:
        if step.get("id") == step_id:
            return dict(step)
    raise AssertionError(f"module-tests.yml job `test` has no step with id {step_id!r}")


def test_select_step_calls_the_module_and_carries_no_inline_heredoc() -> None:
    run = str(_workflow_step("select")["run"])
    assert "-m scripts.ci.shard_select module" in run
    assert "<<'PY'" not in run


def test_runner_step_marker_equals_the_shared_selection_constant() -> None:
    """Selector and runner can never drift apart again (C-010)."""
    run = str(_workflow_step("pytest-run")["run"])
    assert f'-m "{MODULE_SELECTION_MARKER_EXPR}"' in run


def test_marker_constant_value() -> None:
    assert MODULE_SELECTION_MARKER_EXPR == "not performance and not stress"


# --------------------------------------------------------------------------- #
# positional_weights (the production weighting, incl. the silent fallback)
# --------------------------------------------------------------------------- #


def test_positional_weights_returns_the_committed_durations_when_the_counts_line_up() -> None:
    durations = [3.5, 0.25, 9.0]
    assert positional_weights(["a::1", "b::2", "c::3"], durations) == durations


def test_positional_weights_does_not_alias_the_input_list() -> None:
    durations = [1.0, 2.0]
    weights = positional_weights(["a::1", "b::2"], durations)
    weights.append(99.0)
    assert durations == [1.0, 2.0]


@pytest.mark.parametrize("durations", [[], [2.0], [2.0, 3.0, 4.0]])
def test_positional_weights_degrades_to_uniform_on_a_length_mismatch(durations: list[float]) -> None:
    assert positional_weights(["a::1", "b::2"], durations) == [1.0, 1.0]


# --------------------------------------------------------------------------- #
# resolve_module_test_dirs
# --------------------------------------------------------------------------- #


def test_resolve_falls_back_to_the_mirrored_tests_directory_when_json_is_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "tests" / "alpha").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    assert resolve_module_test_dirs("alpha", "") == ["tests/alpha"]


def test_resolve_falls_back_to_the_mirror_when_no_declared_directory_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "tests" / "alpha").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    assert resolve_module_test_dirs("alpha", json.dumps(["tests/ghost"])) == ["tests/alpha"]


def test_resolve_keeps_only_declared_directories_that_exist_and_ignores_the_mirror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("tests/alpha", "tests/extra_one", "tests/extra_two"):
        (tmp_path / name).mkdir(parents=True)
    (tmp_path / "tests" / "not_a_dir.py").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    declared = json.dumps(["tests/extra_one", "tests/ghost", "tests/not_a_dir.py", "tests/extra_two"])
    assert resolve_module_test_dirs("alpha", declared) == ["tests/extra_one", "tests/extra_two"]


def test_resolve_returns_an_empty_list_when_neither_declared_nor_mirror_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "alpha").write_text("a file, not a directory", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert resolve_module_test_dirs("alpha", "") == []
    assert resolve_module_test_dirs("alpha", json.dumps(["tests/ghost"])) == []


def test_every_registry_row_resolves_to_existing_test_directories_from_the_repo_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real registry rows, fed the way the workflow feeds ``--test-dirs``."""
    monkeypatch.chdir(_REPO_ROOT)
    for row in _registry_rows():
        declared = row.get("test_dirs") or []
        resolved = resolve_module_test_dirs(row["module"], json.dumps(declared) if declared else "")
        assert resolved, f"{row['module']}: no test directory resolves"
        assert all(Path(d).is_dir() for d in resolved)
        if declared:
            assert resolved == declared, f"{row['module']}: declared test_dirs must be used verbatim"


# --------------------------------------------------------------------------- #
# The CLI path module-tests.yml runs: main(["module", ...])
# --------------------------------------------------------------------------- #

_COLLECT_NOISE = ("", "5 tests collected in 0.01s")


class _Fixture:
    """A throwaway repo root with a stub ``--python`` that fakes ``pytest --collect-only -q``."""

    def __init__(self, root: Path, node_ids: list[str]) -> None:
        self.root = root
        self.out = root / "shard_tests.txt"
        self.argv_log = root / "stub-argv.txt"
        self.timings = root / "timings.json"
        ids_file = root / "stub-ids.txt"
        ids_file.write_text("\n".join([*node_ids[:2], _COLLECT_NOISE[0], *node_ids[2:], _COLLECT_NOISE[1]]) + "\n", encoding="utf-8")
        self.python = root / "stub-python"
        self.python.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$@\" > '{self.argv_log}'\ncat '{ids_file}'\n", encoding="utf-8")
        self.python.chmod(self.python.stat().st_mode | stat.S_IXUSR)

    def write_timings(self, module: str, durations: list[float]) -> None:
        self.timings.write_text(json.dumps({"module_test_durations": {module: durations}}), encoding="utf-8")

    def argv(self, module: str, shard: str, *, test_dirs: str = "", timings: Path | None = None) -> list[str]:
        return [
            "module",
            "--module", module,
            "--shard", shard,
            "--test-dirs", test_dirs,
            "--python", str(self.python),
            "--timings", str(timings or self.timings),
            "--out", str(self.out),
        ]  # fmt: skip


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module: str, node_ids: list[str]) -> _Fixture:
    (tmp_path / "tests" / module).mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    return _Fixture(tmp_path, node_ids)


def test_main_writes_the_oracle_selection_byte_exact_with_no_trailing_newline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    node_ids = [f"tests/alpha/test_a.py::t{i}" for i in range(9)]
    durations = [5.0, 1.0, 1.0, 4.0, 2.0, 2.0, 3.0, 0.5, 0.5]
    fx = _fixture(tmp_path, monkeypatch, "alpha", node_ids)
    fx.write_timings("alpha", durations)

    assert main(fx.argv("alpha", "2/3")) == 0

    expected = _reference_select(node_ids, durations, 3, 2)
    assert expected, "fixture must give shard 2 some tests"
    assert fx.out.read_bytes() == "\n".join(expected).encode()
    assert not fx.out.read_bytes().endswith(b"\n")
    assert capsys.readouterr().out == f"module-tests: selected {len(expected)}/9 tests for alpha shard 2/3\n"


def test_main_shards_partition_the_collected_tests_exactly_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    node_ids = [f"tests/alpha/test_a.py::t{i}" for i in range(11)]
    durations = [float(i % 4) for i in range(11)]
    fx = _fixture(tmp_path, monkeypatch, "alpha", node_ids)
    fx.write_timings("alpha", durations)

    seen: list[str] = []
    for idx in (1, 2, 3):
        assert main(fx.argv("alpha", f"{idx}/3")) == 0
        assert fx.out.read_text(encoding="utf-8").splitlines() == _reference_select(node_ids, durations, 3, idx)
        seen += fx.out.read_text(encoding="utf-8").splitlines()
    assert sorted(seen) == sorted(node_ids)


def test_main_keeps_only_collected_node_lines_and_runs_the_shared_marker_over_the_resolved_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    node_ids = ["tests/alpha/test_a.py::t0", "tests/alpha/test_a.py::t1", "tests/alpha/test_b.py::t2"]
    fx = _fixture(tmp_path, monkeypatch, "alpha", node_ids)

    assert main(fx.argv("alpha", "1/1", timings=tmp_path / "absent.json")) == 0

    # blank and summary lines (no "::") are not node ids and must not be selected
    assert fx.out.read_text(encoding="utf-8").splitlines() == node_ids
    assert fx.argv_log.read_text(encoding="utf-8").splitlines() == [
        "-m", "pytest", "tests/alpha", "-m", MODULE_SELECTION_MARKER_EXPR, "--collect-only", "-q",
    ]  # fmt: skip


@pytest.mark.parametrize("timings", ["missing", "wrong-length", "module-absent"])
def test_main_falls_back_to_uniform_weights_when_timings_are_unusable(timings: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    node_ids = [f"tests/alpha/test_a.py::t{i}" for i in range(7)]
    fx = _fixture(tmp_path, monkeypatch, "alpha", node_ids)
    if timings == "wrong-length":
        fx.write_timings("alpha", [9.0, 8.0, 7.0])
    elif timings == "module-absent":
        fx.write_timings("other", [9.0] * 7)
    # "missing": no file at all

    assert main(fx.argv("alpha", "2/3")) == 0
    assert fx.out.read_text(encoding="utf-8").splitlines() == _reference_select(node_ids, [1.0] * len(node_ids), 3, 2)


def test_main_uses_declared_test_dirs_and_drops_missing_ones(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fx = _fixture(tmp_path, monkeypatch, "alpha", ["tests/alpha/test_a.py::t0"])
    (tmp_path / "tests" / "extra").mkdir()

    declared = json.dumps(["tests/extra", "tests/ghost"])
    assert main(fx.argv("alpha", "1/1", test_dirs=declared)) == 0
    assert fx.argv_log.read_text(encoding="utf-8").splitlines()[2:3] == ["tests/extra"]


def test_main_reports_a_missing_test_directory_with_the_error_annotation_and_exit_64(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fx = _fixture(tmp_path, monkeypatch, "alpha", ["tests/alpha/test_a.py::t0"])

    code = main(fx.argv("ghost", "1/1"))

    assert code == EXIT_NO_TESTS == 64
    assert capsys.readouterr().out == ("::error::module-tests: no test directory found for module 'ghost' (looked for tests/ghost or the registry's test_dirs)\n")
    assert not fx.out.exists()
    assert not fx.argv_log.exists(), "must not run the collector when there is nothing to collect"


def test_main_reports_zero_collected_tests_with_the_error_annotation_and_exit_64(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fx = _fixture(tmp_path, monkeypatch, "alpha", [])
    fx.python.write_text("#!/bin/sh\necho 'no tests collected in 0.01s'\n", encoding="utf-8")

    code = main(fx.argv("alpha", "1/1"))

    assert code == 64
    assert capsys.readouterr().out == ("::error::module-tests: pytest collected zero tests for module 'alpha' under ['tests/alpha']\n")
    assert not fx.out.exists()


def test_main_over_a_real_registry_row_matches_the_oracle_for_every_shard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Real row (shard_count, test_dirs) + real committed timings, end to end through ``main``."""
    row = next(r for r in _registry_rows() if r["module"] == "next")
    total = int(row["shard_count"])
    assert total > 1, "the multi-shard fixture row must stay multi-shard"
    durations = _timings()["next"]
    node_ids = [f"tests/next/test_x.py::t{i}" for i in range(len(durations))]
    fx = _fixture(tmp_path, monkeypatch, "next", node_ids)
    fx.timings.write_bytes(_TIMINGS_PATH.read_bytes())

    for idx in range(1, total + 1):
        assert main(fx.argv("next", f"{idx}/{total}")) == 0
        assert fx.out.read_text(encoding="utf-8").splitlines() == _reference_select(node_ids, durations, total, idx)


def test_the_module_entry_point_exits_with_the_selector_status(tmp_path: Path) -> None:
    """``python -m scripts.ci.shard_select`` -- the literal workflow invocation -- propagates the exit code."""
    (tmp_path / "tests").mkdir()
    env = {**os.environ, "PYTHONPATH": str(_REPO_ROOT)}
    result = subprocess.run(
        [sys.executable, "-m", "scripts.ci.shard_select", "module", "--module", "ghost", "--shard", "1/1", "--out", "o.txt"],
        cwd=tmp_path, env=env, capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert result.returncode == 64
    assert result.stdout.startswith("::error::module-tests: no test directory found for module 'ghost'")
