"""OS-family tier model of the static gate model (mission ci-runtime-stabilisation-01M3TZH6 WP06, D-14).

The same-tier relation used to key tiers on the job-name prefixes ``fast-tests`` /
``integration-tests``, which no live job carries, so it was vacuous. Tiers are now keyed
on the **OS family of ``runs-on`` only**: module rows run on Python 3.11 and the router /
Packs jobs on 3.12, so an interpreter-keyed tier would hide exactly the router-vs-module
duplicates the per-change uniqueness check (FR-010) exists to find.

Everything here is static (no collection): synthetic gates, tmp workflows, and the live
workflow files parsed by ``gc.parse_workflow``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.architectural import _gate_coverage as gc

pytestmark = [pytest.mark.architectural]

_LINUX = "ubuntu-24.04"
_WINDOWS = "windows-latest"
_TEST_CALL = "      - run: pytest tests/architectural -m fast\n"


def _record(nodeid: str = "tests/architectural/test_a.py::test_one") -> gc.TestRecord:
    return {"nodeid": nodeid, "relpath": nodeid.partition("::")[0], "markers": ["fast"]}


def _gate(job: str, *, runs_on: str | None, shard: str | None = None) -> gc.Gate:
    return gc.Gate("w.yml", job, shard, paths=["tests/architectural"], runs_on=runs_on)


def _write_caller_and_delegate(tmp_path: Path, *, caller_runs_on: str | None, delegate_runs_on: str | None = _LINUX) -> Path:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    delegate_header = f"    runs-on: {delegate_runs_on}\n" if delegate_runs_on else ""
    (workflows / "delegate.yml").write_text(
        f"on: workflow_call\njobs:\n  test:\n{delegate_header}    steps:\n{_TEST_CALL}",
        encoding="utf-8",
    )
    caller_header = f"    runs-on: {caller_runs_on}\n" if caller_runs_on else ""
    caller = workflows / "caller.yml"
    caller.write_text(
        f"on: push\njobs:\n  call:\n{caller_header}    uses: ./.github/workflows/delegate.yml\n",
        encoding="utf-8",
    )
    return caller


def _only_gate(workflow: Path) -> gc.Gate:
    [gate] = gc.parse_workflow(workflow)
    return gate


# ---------------------------------------------------------------------------
# os_family / gate_os_tier
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("runs_on", "family"),
    [
        ("ubuntu-24.04", "linux"),
        ("ubuntu-latest", "linux"),
        ("windows-latest", "windows"),
        ("windows-2022", "windows"),
        ("macos-14", "macos"),
        ("macos-latest", "macos"),
        ("ubuntu", None),
        ("windows", None),
        ("macos", None),
        ("${{ matrix.os }}", None),
        ("self-hosted", None),
        ("", None),
        (None, None),
    ],
)
def test_os_family_table(runs_on: str | None, family: str | None) -> None:
    assert gc.os_family(runs_on) == family


def test_gate_os_tier_is_the_os_family_of_runs_on() -> None:
    assert gc.gate_os_tier(_gate("j", runs_on=_LINUX)) == "linux"
    assert gc.gate_os_tier(_gate("j", runs_on=_WINDOWS)) == "windows"
    assert gc.gate_os_tier(_gate("j", runs_on=None)) is None


def test_gate_os_tier_ignores_the_job_name_prefix() -> None:
    """The dead ``fast-tests`` / ``integration-tests`` prefixes no longer decide the tier."""
    assert gc.gate_os_tier(_gate("fast-tests-core", runs_on=None)) is None
    assert gc.gate_os_tier(_gate("integration-tests-x", runs_on=_WINDOWS)) == "windows"


def test_runs_on_does_not_take_part_in_gate_equality() -> None:
    assert _gate("j", runs_on=_LINUX) == _gate("j", runs_on=_WINDOWS)
    assert gc.Gate("w.yml", "j", None) == gc.Gate("w.yml", "j", None, runs_on=_LINUX)


# ---------------------------------------------------------------------------
# runs-on parsed from the workflow (matrix-substituted)
# ---------------------------------------------------------------------------
def test_parse_workflow_reads_runs_on(tmp_path: Path) -> None:
    workflow = tmp_path / "w.yml"
    workflow.write_text(f"on: push\njobs:\n  j:\n    runs-on: {_LINUX}\n    steps:\n{_TEST_CALL}", encoding="utf-8")
    assert _only_gate(workflow).runs_on == _LINUX


def test_parse_workflow_substitutes_the_matrix_into_runs_on(tmp_path: Path) -> None:
    workflow = tmp_path / "w.yml"
    workflow.write_text(
        "on: push\njobs:\n  j:\n    runs-on: ${{ matrix.os }}\n    strategy:\n      matrix:\n        include:\n"
        f"          - os: {_LINUX}\n          - os: {_WINDOWS}\n    steps:\n{_TEST_CALL}",
        encoding="utf-8",
    )
    assert [gate.runs_on for gate in gc.parse_workflow(workflow)] == [_LINUX, _WINDOWS]


def test_unresolvable_or_non_string_runs_on_is_untiered(tmp_path: Path) -> None:
    unresolved = tmp_path / "unresolved.yml"
    unresolved.write_text(f"on: push\njobs:\n  j:\n    runs-on: ${{{{ matrix.os }}}}\n    steps:\n{_TEST_CALL}", encoding="utf-8")
    listed = tmp_path / "listed.yml"
    listed.write_text(f"on: push\njobs:\n  j:\n    runs-on: [self-hosted, linux]\n    steps:\n{_TEST_CALL}", encoding="utf-8")
    absent = tmp_path / "absent.yml"
    absent.write_text(f"on: push\njobs:\n  j:\n    steps:\n{_TEST_CALL}", encoding="utf-8")
    assert [gc.gate_os_tier(_only_gate(path)) for path in (unresolved, listed, absent)] == [None, None, None]


# ---------------------------------------------------------------------------
# Reusable-workflow splice carries the delegate's runs-on
# ---------------------------------------------------------------------------
def test_splice_carries_the_delegate_runs_on_when_the_caller_has_none(tmp_path: Path) -> None:
    caller = _write_caller_and_delegate(tmp_path, caller_runs_on=None)
    spliced: dict[str, Any] = gc.load_spliced_workflow(caller)
    assert spliced["jobs"]["call"]["runs-on"] == _LINUX
    gate = _only_gate(caller)
    assert gate.runs_on == _LINUX
    assert gc.gate_os_tier(gate) == "linux"


def test_splice_never_overwrites_a_caller_runs_on(tmp_path: Path) -> None:
    caller = _write_caller_and_delegate(tmp_path, caller_runs_on=_WINDOWS)
    assert gc.load_spliced_workflow(caller)["jobs"]["call"]["runs-on"] == _WINDOWS
    assert gc.gate_os_tier(_only_gate(caller)) == "windows"


def test_splice_without_any_runs_on_leaves_the_gate_untiered(tmp_path: Path) -> None:
    caller = _write_caller_and_delegate(tmp_path, caller_runs_on=None, delegate_runs_on=None)
    assert "runs-on" not in gc.load_spliced_workflow(caller)["jobs"]["call"]
    assert gc.gate_os_tier(_only_gate(caller)) is None


# ---------------------------------------------------------------------------
# Per-OS-tier counting
# ---------------------------------------------------------------------------
def test_os_tier_counts_flag_a_same_os_double_run() -> None:
    gates = [_gate("a", runs_on=_LINUX, shard="1/2"), _gate("b", runs_on=_LINUX, shard="2/2")]
    counts = gc.os_tier_shard_counts(gates, [_record()])
    assert counts == {"tests/architectural/test_a.py::test_one": {"linux": 2}}


def test_os_tier_counts_separate_tiers() -> None:
    gates = [_gate("a", runs_on=_LINUX), _gate("b", runs_on=_WINDOWS)]
    counts = gc.os_tier_shard_counts(gates, [_record()])
    assert counts == {"tests/architectural/test_a.py::test_one": {"linux": 1, "windows": 1}}


def test_os_tier_counts_ignore_untiered_and_non_selecting_gates() -> None:
    selecting = _gate("a", runs_on=_LINUX)
    elsewhere = gc.Gate("w.yml", "b", None, paths=["tests/unit"], runs_on=_LINUX)
    untiered = _gate("c", runs_on=None)
    counts = gc.os_tier_shard_counts([selecting, elsewhere, untiered], [_record(), _record("tests/unit/test_u.py::t")])
    assert counts == {"tests/architectural/test_a.py::test_one": {"linux": 1}, "tests/unit/test_u.py::t": {"linux": 1}}


def test_os_tier_counts_report_a_test_no_gate_selects_as_empty() -> None:
    assert gc.os_tier_shard_counts([_gate("a", runs_on=_LINUX)], [_record("tests/other/test_o.py::t")]) == {"tests/other/test_o.py::t": {}}


def test_os_tier_counts_respect_a_partitioned_gate() -> None:
    inside = sorted(gc.battery_part_files("1/2"))[0]
    outside = sorted(gc.battery_part_files("2/2"))[0]
    gate = gc.Gate("w.yml", "heavy", "1/2", paths=["tests/architectural"], partition="1/2", runs_on=_LINUX)
    counts = gc.os_tier_shard_counts([gate], [_record(f"{inside}::t"), _record(f"{outside}::t")])
    assert counts == {f"{inside}::t": {"linux": 1}, f"{outside}::t": {}}


# ---------------------------------------------------------------------------
# Live workflows
# ---------------------------------------------------------------------------
def _live_gates(workflow: str) -> list[gc.Gate]:
    return gc.parse_workflow(gc.WORKFLOWS_DIR / workflow)


def test_every_live_module_row_gate_has_runs_on_and_tiers_linux() -> None:
    gates = [gate for gate in _live_gates("ci-modules.yml") if gate.job == "test"]
    assert gates, "ci-modules.yml::test yields no gate"
    assert [gate.runs_on for gate in gates if not gate.runs_on] == []
    assert {gc.gate_os_tier(gate) for gate in gates} == {"linux"}


def _setup_python_versions(workflow: str, job: str) -> set[str]:
    steps = gc.load_spliced_workflow(gc.WORKFLOWS_DIR / workflow)["jobs"][job].get("steps") or []
    return {str(step["with"]["python-version"]) for step in steps if isinstance(step, dict) and "python-version" in (step.get("with") or {})}


def test_module_rows_on_311_and_router_packs_on_312_share_one_os_tier() -> None:
    """D-14: the interpreters differ (3.11 vs 3.12) but the OS family is one tier."""
    default_interpreter = (gc.REPO_ROOT / ".python-version").read_text(encoding="utf-8").strip()
    assert default_interpreter.startswith("3.11"), "module rows run on the repository default interpreter (3.11)"
    router_packs = [(name, gate) for name in ("ci-router.yml", "packs.yml") for gate in _live_gates(name)]
    module_rows = [gate for gate in _live_gates("ci-modules.yml") if gate.job == "test"]
    assert router_packs
    assert {versions for name, gate in router_packs for versions in _setup_python_versions(name, gate.job)} == {"3.12"}
    assert {gc.gate_os_tier(gate) for _, gate in router_packs} == {"linux"}
    assert {gc.gate_os_tier(gate) for gate in module_rows} == {"linux"}
