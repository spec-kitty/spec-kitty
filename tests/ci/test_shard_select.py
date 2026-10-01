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

import io
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
    BatteryPartition,
    WeightResolution,
    battery_parts,
    enumerate_base_files,
    escape_workflow_command_message,
    lpt_assign,
    lpt_loads,
    main,
    report_mismatch,
    resolve_file_weights,
    resolve_module_test_dirs,
    resolve_positional_weights,
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
    """Pair ids with weights through the SHIPPED ``resolve_positional_weights`` (what the CLI runs).

    Deliberately not a re-implementation: the characterization must fail if the
    shipped weighting drifts from the frozen oracle.
    """
    return list(zip(node_ids, resolve_positional_weights(node_ids, timing_durations).weights, strict=True))


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
# resolve_positional_weights (the production weighting; the fallback is loud since WP02)
# --------------------------------------------------------------------------- #


def test_positional_weights_returns_the_committed_durations_when_the_counts_line_up() -> None:
    durations = [3.5, 0.25, 9.0]
    resolution = resolve_positional_weights(["a::1", "b::2", "c::3"], durations)
    assert list(resolution.weights) == durations
    assert not resolution.mismatch
    assert resolution.reason is None


@pytest.mark.parametrize("durations", [[], [2.0], [2.0, 3.0, 4.0]])
def test_positional_weights_degrades_to_uniform_on_a_length_mismatch(durations: list[float]) -> None:
    resolution = resolve_positional_weights(["a::1", "b::2"], durations)
    assert resolution.weights == (1.0, 1.0)
    assert resolution.mismatch
    assert resolution.reason == f"{len(durations)} committed durations vs 2 collected \N{EM DASH} uniform weights"


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


# --------------------------------------------------------------------------- #
# WP02 / T006 -- FR-005: the mismatch is loud, in both granularities
# --------------------------------------------------------------------------- #

_WARNING_PREFIX = "::warning title=shard timings::"
_SUMMARY_ENV = "GITHUB_STEP_SUMMARY"


def _warning_lines(out: str) -> list[str]:
    return [line for line in out.splitlines() if line.startswith(_WARNING_PREFIX)]


def test_module_mode_length_mismatch_keeps_uniform_weights_but_warns_and_writes_the_step_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    node_ids = [f"tests/alpha/test_a.py::t{i}" for i in range(5)]
    fx = _fixture(tmp_path, monkeypatch, "alpha", node_ids)
    fx.write_timings("alpha", [9.0, 1.0, 5.0])
    summary = tmp_path / "summary.md"
    monkeypatch.setenv(_SUMMARY_ENV, str(summary))

    assert main(fx.argv("alpha", "2/3")) == 0

    # assignment unchanged: uniform weights, exactly the legacy selector's result
    assert fx.out.read_text(encoding="utf-8").splitlines() == _reference_select(node_ids, [1.0] * 5, 3, 2)
    warnings = _warning_lines(capsys.readouterr().out)
    assert len(warnings) == 1
    assert "alpha" in warnings[0]
    assert "3 committed" in warnings[0]
    assert "5 collected" in warnings[0]
    summary_lines = summary.read_text(encoding="utf-8").splitlines()
    assert len(summary_lines) == 1
    assert "alpha" in summary_lines[0]
    assert "3 committed" in summary_lines[0]


def test_module_mode_agreeing_counts_print_no_warning_and_write_no_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    node_ids = [f"tests/alpha/test_a.py::t{i}" for i in range(4)]
    fx = _fixture(tmp_path, monkeypatch, "alpha", node_ids)
    fx.write_timings("alpha", [4.0, 3.0, 2.0, 1.0])
    summary = tmp_path / "summary.md"
    monkeypatch.setenv(_SUMMARY_ENV, str(summary))

    assert main(fx.argv("alpha", "1/2")) == 0

    assert _warning_lines(capsys.readouterr().out) == []
    assert not summary.exists()


def test_module_mode_warns_even_when_no_step_summary_is_configured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    fx = _fixture(tmp_path, monkeypatch, "alpha", [f"tests/alpha/test_a.py::t{i}" for i in range(5)])
    fx.write_timings("alpha", [1.0])
    monkeypatch.delenv(_SUMMARY_ENV, raising=False)

    assert main(fx.argv("alpha", "1/1")) == 0

    assert len(_warning_lines(capsys.readouterr().out)) == 1
    assert sorted(p.name for p in tmp_path.iterdir() if p.suffix == ".md") == []


def test_node_collection_failure_fails_the_selector_instead_of_shipping_a_partial_selection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pins ``check=True`` in ``_collect_node_ids`` (WP01 review carry-over).

    A collection error exits pytest non-zero; its stdout may still list the node
    ids collected before the error, so ignoring the status would silently ship a
    partial selection.
    """
    fx = _fixture(tmp_path, monkeypatch, "alpha", ["tests/alpha/test_a.py::t0"])
    fx.python.write_text("#!/bin/sh\necho 'tests/alpha/test_a.py::t0'\necho 'ERROR collecting tests/alpha/test_b.py'\nexit 2\n", encoding="utf-8")

    with pytest.raises(subprocess.CalledProcessError):
        main(fx.argv("alpha", "1/1"))
    assert not fx.out.exists()


def test_escape_workflow_command_message_escapes_percent_and_line_breaks() -> None:
    assert escape_workflow_command_message("100% a\r\nb\nc") == "100%25 a%0D%0Ab%0Ac"
    assert escape_workflow_command_message("plain") == "plain"


def test_report_mismatch_is_silent_for_an_agreeing_resolution(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv(_SUMMARY_ENV, str(summary))
    stream = io.StringIO()
    report_mismatch(WeightResolution(weights=(1.0,), missing=(), stale=(), reason=None), label="module x", stream=stream)
    assert stream.getvalue() == ""
    assert not summary.exists()


def test_report_mismatch_escapes_the_annotation_and_appends_one_summary_line(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    summary = tmp_path / "summary.md"
    summary.write_text("earlier line\n", encoding="utf-8")
    monkeypatch.setenv(_SUMMARY_ENV, str(summary))
    stream = io.StringIO()
    resolution = WeightResolution(weights=(1.0,), missing=(), stale=(), reason="50% off\nsecond line")

    report_mismatch(resolution, label="module x", stream=stream)

    assert stream.getvalue() == f"{_WARNING_PREFIX}module x: 50%25 off%0Asecond line\n"
    assert summary.read_text(encoding="utf-8").splitlines() == ["earlier line", "- shard timings \N{EM DASH} module x: 50% off second line"]


def test_report_mismatch_lists_at_most_ten_missing_and_stale_names_plus_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_SUMMARY_ENV, raising=False)
    missing = tuple(f"m{i:02d}.py" for i in range(12))
    stale = tuple(f"s{i:02d}.py" for i in range(11))
    stream = io.StringIO()

    report_mismatch(WeightResolution(weights=(), missing=missing, stale=stale, reason="why"), label="battery", stream=stream)

    out = stream.getvalue()
    assert "12 missing" in out
    assert "11 stale" in out
    assert "m09.py" in out
    assert "m10.py" not in out
    assert "s09.py" in out
    assert "s10.py" not in out


def test_report_mismatch_message_is_the_reason_then_missing_then_stale_joined_by_semicolons(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_SUMMARY_ENV, raising=False)
    stream = io.StringIO()

    report_mismatch(WeightResolution(weights=(), missing=("m.py",), stale=("s.py",), reason="why"), label="battery", stream=stream)

    assert stream.getvalue() == f"{_WARNING_PREFIX}battery: why; 1 missing: m.py; 1 stale: s.py\n"


def test_report_mismatch_elides_with_an_ellipsis_only_beyond_ten_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_SUMMARY_ENV, raising=False)
    exactly_ten = tuple(f"m{i:02d}.py" for i in range(10))
    eleven = tuple(f"m{i:02d}.py" for i in range(11))
    ten_stream, eleven_stream = io.StringIO(), io.StringIO()

    report_mismatch(WeightResolution(weights=(), missing=exactly_ten, stale=(), reason="why"), label="battery", stream=ten_stream)
    report_mismatch(WeightResolution(weights=(), missing=eleven, stale=(), reason="why"), label="battery", stream=eleven_stream)

    assert ten_stream.getvalue().endswith("m09.py\n")
    assert eleven_stream.getvalue().endswith("m09.py, ...\n")


def test_report_mismatch_summary_line_is_newline_terminated_so_lines_do_not_run_together(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv(_SUMMARY_ENV, str(summary))
    resolution = WeightResolution(weights=(), missing=(), stale=("s.py",), reason="why")

    report_mismatch(resolution, label="battery", stream=io.StringIO())
    report_mismatch(resolution, label="module x", stream=io.StringIO())

    assert summary.read_text(encoding="utf-8") == (
        "- shard timings \N{EM DASH} battery: why; 1 stale: s.py\n- shard timings \N{EM DASH} module x: why; 1 stale: s.py\n"
    )


# --- file granularity ------------------------------------------------------ #


def test_file_weights_give_untimed_files_the_median_of_the_known_base_file_weights() -> None:
    resolution = resolve_file_weights(["a.py", "b.py", "c.py"], {"a.py": 10.0, "b.py": 30.0, "z.py": 5.0})
    assert resolution.weights == (10.0, 30.0, 20.0)
    assert resolution.missing == ("c.py",)
    assert resolution.stale == ("z.py",)
    assert resolution.mismatch


def test_file_weights_with_no_timings_are_uniform_and_say_so() -> None:
    resolution = resolve_file_weights(["a.py", "b.py"], {})
    assert resolution.weights == (1.0, 1.0)
    assert resolution.reason is not None
    assert "no timings for this key" in resolution.reason
    assert resolution.missing == ("a.py", "b.py")


def test_file_weights_with_only_stale_timings_count_as_no_timings() -> None:
    resolution = resolve_file_weights(["a.py"], {"z.py": 99.0})
    assert resolution.weights == (1.0,)
    assert resolution.stale == ("z.py",)
    assert "no timings for this key" in str(resolution.reason)


def test_file_weights_never_go_uniform_when_some_timings_exist() -> None:
    files = [f"f{i}.py" for i in range(10)]
    resolution = resolve_file_weights(files, {"f3.py": 7.5})
    assert resolution.weights == tuple(7.5 for _ in files)
    assert len(resolution.missing) == 9


def test_file_weights_agreeing_keys_are_not_a_mismatch() -> None:
    resolution = resolve_file_weights(["a.py", "b.py"], {"a.py": 1.0, "b.py": 2.0})
    assert resolution.weights == (1.0, 2.0)
    assert not resolution.mismatch
    assert resolution.missing == ()
    assert resolution.stale == ()


def test_file_weights_fill_is_the_median_not_the_mean_of_a_skewed_known_set() -> None:
    resolution = resolve_file_weights(["a.py", "b.py", "c.py", "d.py"], {"a.py": 1.0, "b.py": 2.0, "c.py": 100.0})
    assert resolution.weights == (1.0, 2.0, 100.0, 2.0)  # mean would give 34.33...


def test_file_weights_flag_stale_only_keys_as_a_mismatch_without_changing_the_weights() -> None:
    resolution = resolve_file_weights(["a.py", "b.py"], {"a.py": 1.0, "b.py": 2.0, "gone.py": 5.0})
    assert resolution.weights == (1.0, 2.0)
    assert resolution.stale == ("gone.py",)
    assert resolution.missing == ()
    assert resolution.mismatch
    assert resolution.reason == "0 files without a timing get the median 1.5s; 1 stale timing keys"


def test_file_weights_flag_missing_only_files_as_a_mismatch_with_no_stale_keys() -> None:
    resolution = resolve_file_weights(["a.py", "b.py", "c.py"], {"a.py": 1.0, "b.py": 3.0})
    assert resolution.weights == (1.0, 3.0, 2.0)
    assert resolution.missing == ("c.py",)
    assert resolution.stale == ()
    assert resolution.mismatch
    assert resolution.reason == "1 files without a timing get the median 2s; 0 stale timing keys"


def test_file_weights_report_stale_keys_sorted_and_missing_files_in_input_order() -> None:
    stale_keys = [f"stale_{i}.py" for i in "jhfdbacegi"]  # set iteration order is hash-random; ten keys make an accidental sort negligible
    resolution = resolve_file_weights(["b.py", "a.py", "d.py", "c.py"], {"a.py": 1.0, "b.py": 1.0, **dict.fromkeys(stale_keys, 1.0)})
    assert resolution.missing == ("d.py", "c.py")
    assert resolution.stale == tuple(sorted(stale_keys))


def test_report_mismatch_names_only_the_stale_keys_for_a_stale_only_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_SUMMARY_ENV, raising=False)
    stream = io.StringIO()

    report_mismatch(resolve_file_weights(["a.py", "b.py"], {"a.py": 1.0, "b.py": 2.0, "gone.py": 5.0}), label="battery", stream=stream)

    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    assert lines[0].startswith(f"{_WARNING_PREFIX}battery: ")
    assert "1 stale: gone.py" in lines[0]
    assert "missing" not in lines[0].replace("without a timing", "")


def test_report_mismatch_names_only_the_missing_files_for_a_missing_only_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_SUMMARY_ENV, raising=False)
    stream = io.StringIO()

    report_mismatch(resolve_file_weights(["a.py", "b.py", "c.py"], {"a.py": 1.0, "b.py": 3.0}), label="battery", stream=stream)

    line = stream.getvalue().strip()
    assert "1 missing: c.py" in line
    assert "stale:" not in line


def test_file_weights_median_ignores_stale_keys() -> None:
    resolution = resolve_file_weights(["a.py", "b.py", "c.py"], {"a.py": 2.0, "b.py": 4.0, "z1.py": 1000.0, "z2.py": 1000.0, "z3.py": 1000.0})
    assert resolution.weights == (2.0, 4.0, 3.0)


# --- enumeration ----------------------------------------------------------- #

_SYNTHETIC_TREE: dict[str, str] = {
    "pkg/test_a.py": "def test_a():\n    pass\n",
    "pkg/b_test.py": "def test_b():\n    pass\n",
    "pkg/sub/test_c.py": "def test_c():\n    pass\n",
    "pkg/conftest.py": "",
    "pkg/_helper.py": "def test_helper_should_not_count():\n    pass\n",
    "pkg/_fixtures/test_fixture_like.py": "def test_fixture_like():\n    pass\n",
    "pkg/.hidden/test_d.py": "def test_d():\n    pass\n",
    "pkg/__pycache__/test_e.cpython-312.pyc": "",
    "pkg/data/test_f.txt": "def test_f():\n    pass\n",
}


def _write_tree(root: Path, tree: dict[str, str]) -> None:
    for rel, body in tree.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")


def _pytest_collected_files(cwd: Path, *args: str) -> list[str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *args, "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=cwd, capture_output=True, text=True, check=False,
    )  # fmt: skip
    return sorted({line.split("::", 1)[0] for line in proc.stdout.splitlines() if "::" in line})


def test_enumerate_base_files_follows_pytests_default_collection_rules(tmp_path: Path) -> None:
    _write_tree(tmp_path, _SYNTHETIC_TREE)

    enumerated = enumerate_base_files(["pkg"], deselect=("pkg/b_test.py",), root=tmp_path)

    assert enumerated == ("pkg/_fixtures/test_fixture_like.py", "pkg/sub/test_c.py", "pkg/test_a.py")
    # encode pytest's behaviour, not our belief about it
    assert list(enumerated) == _pytest_collected_files(tmp_path, "pkg", "--deselect", "pkg/b_test.py")


def test_enumerate_base_files_keeps_suffix_style_test_files_without_a_deselect(tmp_path: Path) -> None:
    _write_tree(tmp_path, _SYNTHETIC_TREE)
    enumerated = enumerate_base_files(["pkg"], root=tmp_path)
    assert "pkg/b_test.py" in enumerated
    assert list(enumerated) == _pytest_collected_files(tmp_path, "pkg")


def test_enumerate_base_files_ignores_node_level_deselects_and_accepts_file_arguments(tmp_path: Path) -> None:
    _write_tree(tmp_path, _SYNTHETIC_TREE)
    enumerated = enumerate_base_files(["pkg/test_a.py", "pkg/_helper.py", "pkg/sub"], deselect=("pkg/test_a.py::test_a",), root=tmp_path)
    assert enumerated == ("pkg/sub/test_c.py", "pkg/test_a.py")


def test_enumerate_base_files_is_sorted_and_deduplicated_across_overlapping_paths(tmp_path: Path) -> None:
    _write_tree(tmp_path, _SYNTHETIC_TREE)
    enumerated = enumerate_base_files(["pkg/sub", "pkg"], root=tmp_path)
    assert list(enumerated) == sorted(set(enumerated))


_BATTERY_PATH = "tests/architectural"
_BATTERY_BASE_DESELECTS = (
    "tests/architectural/test_no_legacy_terminology.py",
    "tests/architectural/test_layer_rules.py",
    "tests/architectural/test_pyproject_shape.py",
    "tests/architectural/test_archive_root_byte_identical.py",
)
#: Enumerated files that legitimately define zero tests (so pytest lists no item for them).
_ENUMERATED_FILES_WITH_NO_TESTS: tuple[str, ...] = ()


@pytest.mark.slow
def test_battery_enumeration_equals_what_pytest_really_collects() -> None:
    """The exact contract the battery partition proof (WP05/WP06) relies on."""
    deselects = [arg for path in _BATTERY_BASE_DESELECTS for arg in ("--deselect", path)]
    collected = set(_pytest_collected_files(_REPO_ROOT, _BATTERY_PATH, *deselects))
    enumerated = set(enumerate_base_files([_BATTERY_PATH], deselect=_BATTERY_BASE_DESELECTS, root=_REPO_ROOT))

    assert enumerated - set(_ENUMERATED_FILES_WITH_NO_TESTS) == collected
    assert collected, "collection produced nothing -- the comparison would be vacuous"


# --- battery_parts --------------------------------------------------------- #


def _battery_inputs() -> tuple[list[str], list[str], dict[str, float]]:
    base = [f"t/test_{i:02d}.py" for i in range(12)]
    roster = ["t/test_00.py", "t/test_05.py"]
    timings = {f"t/test_{i:02d}.py": float(w) for i, w in zip((1, 2, 3, 4, 6, 7, 8, 9), (9, 8, 7, 6, 5, 4, 3, 2), strict=True)}
    return base, roster, timings


def test_battery_parts_partition_the_base_into_fast_and_numbered_shards() -> None:
    base, roster, timings = _battery_inputs()

    result = battery_parts(base, roster, 2, timings)

    assert isinstance(result, BatteryPartition)
    assert set(result.parts) == {"fast", "1/2", "2/2"}
    assert result.parts["fast"] == frozenset(roster)
    parts = list(result.parts.values())
    assert sum(len(p) for p in parts) == len(base), "parts must be pairwise disjoint"
    assert frozenset().union(*parts) == frozenset(base)
    heavy, light = sorted((result.loads["1/2"], result.loads["2/2"]), reverse=True)
    assert (heavy - light) / heavy <= 0.20


def test_battery_parts_are_deterministic_under_shuffled_input_order() -> None:
    base, roster, timings = _battery_inputs()
    expected = battery_parts(base, roster, 3, timings)
    rng = random.Random(_RANDOM_SEED)
    for _ in range(25):
        shuffled_base = rng.sample(base, len(base))
        shuffled_roster = rng.sample(roster, len(roster))
        shuffled_timings = dict(rng.sample(sorted(timings.items()), len(timings)))
        assert battery_parts(shuffled_base, shuffled_roster, 3, shuffled_timings).parts == expected.parts


def test_battery_parts_loads_come_from_the_same_placement_as_the_parts() -> None:
    base, roster, timings = _battery_inputs()
    result = battery_parts(base, roster, 2, timings)
    weight = dict(zip(sorted(set(base) - set(roster)), result.resolution.weights, strict=True))
    for key in ("1/2", "2/2"):
        assert result.loads[key] == pytest.approx(sum(weight[f] for f in result.parts[key]))


def test_battery_parts_reports_the_weight_resolution_loudly_inputs() -> None:
    base, roster, timings = _battery_inputs()
    result = battery_parts(base, roster, 2, {**timings, "t/test_gone.py": 3.0})
    assert result.resolution.stale == ("t/test_gone.py",)
    assert result.resolution.mismatch


def test_battery_parts_reject_a_roster_entry_outside_the_base() -> None:
    base, _, timings = _battery_inputs()
    with pytest.raises(ValueError, match=r"t/test_99\.py"):
        battery_parts(base, ["t/test_99.py"], 2, timings)


@pytest.mark.parametrize("shard_count", [0, -1])
def test_battery_parts_reject_a_shard_count_below_one(shard_count: int) -> None:
    base, roster, timings = _battery_inputs()
    with pytest.raises(ValueError, match="shard_count"):
        battery_parts(base, roster, shard_count, timings)


def test_battery_parts_with_everything_on_the_fast_roster_has_empty_numbered_shards() -> None:
    result = battery_parts(["a.py"], ["a.py"], 2, {})
    assert result.parts == {"fast": frozenset({"a.py"}), "1/2": frozenset(), "2/2": frozenset()}
    assert result.loads == {"1/2": 0.0, "2/2": 0.0}


def test_battery_parts_cli_prints_each_part_with_its_file_count_and_load(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write_tree(tmp_path, {f"t/test_{i}.py": "def test_x():\n    pass\n" for i in range(4)})
    roster = tmp_path / "fast.txt"
    roster.write_text("t/test_0.py\n", encoding="utf-8")
    timings = tmp_path / "file-timings.json"
    timings.write_text(json.dumps({"t/test_1.py": 3.0, "t/test_2.py": 2.0, "t/test_3.py": 1.0}), encoding="utf-8")

    code = main(["battery-parts", "--path", "t", "--roster", str(roster), "--timings", str(timings), "--shards", "2", "--root", str(tmp_path)])

    out = capsys.readouterr().out
    assert code == 0
    assert "fast: 1 files" in out
    assert "1/2: 1 files" in out
    assert "2/2: 2 files" in out


_BATTERY_WARNING_PREFIX = "::warning title=shard timings::battery:"


def _battery_cli_argv(tmp_path: Path, timings: dict[str, float]) -> list[str]:
    _write_tree(tmp_path, {f"t/test_{i}.py": "def test_x():\n    pass\n" for i in range(4)})
    roster = tmp_path / "fast.txt"
    roster.write_text("t/test_0.py\n", encoding="utf-8")
    timings_file = tmp_path / "file-timings.json"
    timings_file.write_text(json.dumps(timings), encoding="utf-8")
    return ["battery-parts", "--path", "t", "--roster", str(roster), "--timings", str(timings_file), "--shards", "2", "--root", str(tmp_path)]


def test_battery_parts_cli_is_loud_on_a_file_timing_mismatch(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    argv = _battery_cli_argv(tmp_path, {"t/test_1.py": 3.0, "t/test_2.py": 2.0, "t/stale_removed.py": 9.0})

    code = main(argv)

    out = capsys.readouterr().out
    assert code == 0
    warnings = [line for line in out.splitlines() if line.startswith(_BATTERY_WARNING_PREFIX)]
    assert len(warnings) == 1
    assert "t/test_3.py" in warnings[0]
    assert "t/stale_removed.py" in warnings[0]
    summary_lines = summary.read_text(encoding="utf-8").splitlines()
    assert len(summary_lines) == 1
    assert summary_lines[0].startswith("- shard timings") and "battery:" in summary_lines[0]
    assert "1/2: " in out  # the partition still prints after the warning


def test_battery_parts_cli_is_loud_on_stale_only_timing_keys(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    argv = _battery_cli_argv(tmp_path, {"t/test_1.py": 3.0, "t/test_2.py": 2.0, "t/test_3.py": 1.0, "t/stale_removed.py": 9.0})

    code = main(argv)

    out = capsys.readouterr().out
    assert code == 0
    warnings = [line for line in out.splitlines() if line.startswith(_BATTERY_WARNING_PREFIX)]
    assert len(warnings) == 1
    assert "1 stale: t/stale_removed.py" in warnings[0]
    assert "missing" not in warnings[0].replace("without a timing", "")
    summary_lines = summary.read_text(encoding="utf-8").splitlines()
    assert len(summary_lines) == 1
    assert "t/stale_removed.py" in summary_lines[0]
    assert "1/2: " in out


def test_battery_parts_cli_is_silent_when_every_file_has_a_timing(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    argv = _battery_cli_argv(tmp_path, {"t/test_1.py": 3.0, "t/test_2.py": 2.0, "t/test_3.py": 1.0})

    code = main(argv)

    out = capsys.readouterr().out
    assert code == 0
    assert "::warning" not in out
    assert not summary.exists()
