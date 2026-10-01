"""Static three-way proof that the architectural battery split is complete and disjoint.

Mission ``ci-runtime-stabilisation-01M3TZH6`` WP06 (FR-004, US2 AS-2/AS-3, C-001,
C-002, D-02, D-24; contract ``contracts/battery-partition.md``).

The router runs the battery as ``--battery-part fast`` plus one leg per shard. This
module proves, **from the literal commands the workflow runs**, that

* every battery gate carries the registry ``base`` selection (paths, marker, deselects);
* the legs are exactly ``fast`` + ``1/n`` ... ``n/n``, each once (a lone unpartitioned
  battery gate is a violation);
* ``fast`` U every shard == the base files (completeness, checked against an enumeration
  independent of the part sets) and no file is in two legs
  (disjointness); ``fast`` is exactly ``roster & base``;
* the registry ``base.deselect`` is exactly the files the always-on architectural
  lanes own (C-002).

``partition_violations`` is the single production function; the live test and every
positive control call it, so a control that passes can only mean the rule bites.
The part sets come from ``gc.battery_part_files`` (the one shared enumeration and
selector in ``scripts/ci/shard_select.py``, D-24) and are cross-checked here against
the plugin's runtime keep/ignore decision. Nothing in the static proof collects or
spawns pytest; the one collection-based test lives in
``test_battery_partition_proof_collect.py`` (marked ``slow``, off the fast roster).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Final

import pytest
import yaml

from scripts.ci import battery_partition_plugin as plugin
from scripts.ci import shard_select
from scripts.ci.battery_partition_plugin import BaseSelection, BatterySpec
from tests.architectural import _gate_coverage as gc

pytestmark = [pytest.mark.architectural]

_ROUTER: Final = gc.WORKFLOWS_DIR / "ci-router.yml"
_REGISTRY: Final = gc.REPO_ROOT / ".github" / "ci-module-registry.yml"
_TIMINGS: Final = gc.REPO_ROOT / ".github" / "ci-shard-timings.json"
_BATTERY_ROOT: Final = "tests/architectural"
_PLUGIN_ARGS: Final = "-p scripts.ci.battery_partition_plugin"
_INJECTED: Final = "tests/architectural/test_zz_injected_unassigned.py"
_FAST: Final = "fast"
_MAX_REPORTED: Final = 10
_STRING_LITERAL: Final = re.compile(r"'[^']*'|\"[^\"]*\"")
_CONTEXT_REF: Final = re.compile(r"[A-Za-z_][\w-]*(?:\.[\w-]+)*(?:\(\))?")
_FORK_GUARD_REFS: Final = frozenset({"github.repository", "github.event_name", "always()", "cancelled()", "true", "false"})

FilesOf = Callable[[gc.Gate], frozenset[str]]


# ---------------------------------------------------------------------------
# Inputs read independently of the gate model (the reference side of every check)
# ---------------------------------------------------------------------------
def _spec() -> BatterySpec:
    return plugin.load_battery_spec(yaml.safe_load(_REGISTRY.read_text(encoding="utf-8")))


def _timings(spec: BatterySpec) -> dict[str, float]:
    return plugin.load_battery_timings(json.loads(_TIMINGS.read_text(encoding="utf-8")), spec.timings_key)


def _reference_base_files(spec: BatterySpec) -> frozenset[str]:
    base = spec.base
    return frozenset(shard_select.enumerate_base_files(base.paths, deselect=base.deselect, root=gc.REPO_ROOT))


def _reference_parts(spec: BatterySpec) -> Mapping[str, frozenset[str]]:
    result = shard_select.battery_parts(sorted(_reference_base_files(spec)), spec.roster_paths, spec.shard_count, _timings(spec))
    return result.parts


def _expected_partitions(shard_count: int) -> list[str]:
    return [_FAST, *(f"{index}/{shard_count}" for index in range(1, shard_count + 1))]


def _model_files_of(gate: gc.Gate) -> frozenset[str]:
    """The files one gate selects: its part, or the whole (independently enumerated) base when unpartitioned."""
    return gc.battery_part_files(gate.partition) if gate.partition else _reference_base_files(_spec())


def _battery_family(workflow: Path) -> list[gc.Gate]:
    return [gate for gate in gc.parse_workflow(workflow) if gate.paths == [_BATTERY_ROOT]]


def _is_fork_guard_only(condition: object) -> bool:
    """True for no ``if:`` or one that reads only ``github.repository`` / ``github.event_name`` (plus ``always()``/``cancelled()``).

    Any other context reference (``needs.*``, ``inputs.*``, ``github.event.*``, ``steps.*`` ...)
    makes the job conditional, so its files are not owned unconditionally.
    """
    text = str(condition or "")
    refs = _CONTEXT_REF.findall(_STRING_LITERAL.sub("''", text.replace("${{", " ").replace("}}", " ")))
    return all(ref in _FORK_GUARD_REFS for ref in refs)


def _always_on_files(workflow: Path) -> frozenset[str]:
    """Test files the workflow's always-on architectural lanes run (fork-guard ``if:`` only)."""
    jobs = yaml.safe_load(workflow.read_text(encoding="utf-8"))["jobs"]
    owned: set[str] = set()
    for gate in gc.parse_workflow(workflow):
        files_only = bool(gate.paths) and all(p.startswith(f"{_BATTERY_ROOT}/") and p.endswith(".py") for p in gate.paths)
        always_on = _is_fork_guard_only(jobs[gate.job].get("if"))
        if files_only and always_on and gate.partition is None:
            owned.update(gate.paths)
    return frozenset(owned)


# ---------------------------------------------------------------------------
# The one production function
# ---------------------------------------------------------------------------
def _argument_violations(family: Sequence[gc.Gate], base: BaseSelection) -> list[str]:
    problems = []
    for gate in family:
        got = (gate.paths, set(gate.ignores), gate.marker_expr)
        want = (list(base.paths), set(base.deselect), base.marker)
        if got != want:
            problems.append(f"{gate.label()}: (paths, deselects, marker) {got} != registry base {want}")
    return problems


def _shape_violations(family: Sequence[gc.Gate], shard_count: int) -> list[str]:
    if not family:
        return ["no architectural battery gate found in the workflow"]
    partitions = [gate.partition for gate in family]
    if None in partitions:
        kind = (
            "unpartitioned battery gate(s) (every battery run must carry --battery-part)"
            if all(part is None for part in partitions)
            else "mixed partitioned and unpartitioned battery gates"
        )
        return [f"{kind}: {[gate.label() for gate in family]}"]
    expected = _expected_partitions(shard_count)
    problems = [f"battery partition {part} is missing" for part in expected if part not in partitions]
    problems += [f"battery partition {part} appears {partitions.count(part)} times" for part in sorted({p for p in partitions if partitions.count(p) > 1}, key=str)]
    problems += [f"battery partition {part} is not one of {expected}" for part in partitions if part not in expected]
    return problems


def _gate_sets(family: Sequence[gc.Gate], files_of: FilesOf) -> tuple[list[tuple[gc.Gate, frozenset[str]]], list[str]]:
    sets: list[tuple[gc.Gate, frozenset[str]]] = []
    problems: list[str] = []
    for gate in family:
        try:
            sets.append((gate, files_of(gate)))
        except ValueError as error:
            problems.append(f"{gate.label()}: unknown partition ({error})")
    return sets, problems


def _completeness_violations(sets: Sequence[tuple[gc.Gate, frozenset[str]]], base_files: frozenset[str]) -> list[str]:
    covered = frozenset().union(*(files for _, files in sets)) if sets else frozenset()
    missing = sorted(base_files - covered)
    if not missing:
        return []
    return [f"{len(missing)} battery files are in no leg: {', '.join(missing[:_MAX_REPORTED])}"]


def _disjointness_violations(sets: Sequence[tuple[gc.Gate, frozenset[str]]]) -> list[str]:
    problems = []
    for position, (first, first_files) in enumerate(sets):
        for second, second_files in sets[position + 1 :]:
            for file in sorted(first_files & second_files):
                problems.append(f"{file} is in two legs: {first.label()} and {second.label()}")
    return problems


def _fast_violations(
    sets: Sequence[tuple[gc.Gate, frozenset[str]]],
    base_files: frozenset[str],
    roster: frozenset[str],
) -> list[str]:
    problems = [f"roster file {file} is not a battery base file" for file in sorted(roster - base_files)]
    for gate, files in sets:
        if gate.partition == _FAST and files != roster & base_files:
            problems.append(f"{gate.label()}: fast leg {sorted(files ^ (roster & base_files))} differs from roster & base")
    return problems


def _deselect_ownership_violations(base: BaseSelection, always_on: frozenset[str]) -> list[str]:
    if set(base.deselect) == always_on:
        return []
    return [f"registry base.deselect {sorted(base.deselect)} != always-on lane files {sorted(always_on)} (C-002)"]


def partition_violations(
    family: Sequence[gc.Gate],
    base_files: frozenset[str],
    files_of: FilesOf,
    *,
    shard_count: int,
    roster: frozenset[str],
    base: BaseSelection,
    always_on_files: frozenset[str],
) -> list[str]:
    """One message per broken FR-004 proof obligation (empty when the split is sound)."""
    sets, problems = _gate_sets(family, files_of)
    return [
        *_argument_violations(family, base),
        *_shape_violations(family, shard_count),
        *problems,
        *_completeness_violations(sets, base_files),
        *_disjointness_violations(sets),
        *_fast_violations(sets, base_files, roster),
        *_deselect_ownership_violations(base, always_on_files),
    ]


def _violations_for(family: Sequence[gc.Gate], *, files_of: FilesOf = _model_files_of, base_files: frozenset[str] | None = None) -> list[str]:
    """Completeness is checked against ``_reference_base_files`` (``shard_select.enumerate_base_files``), never the union of the parts."""
    spec = _spec()
    return partition_violations(
        family,
        _reference_base_files(spec) if base_files is None else base_files,
        files_of,
        shard_count=spec.shard_count,
        roster=frozenset(spec.roster_paths),
        base=spec.base,
        always_on_files=_always_on_files(_ROUTER),
    )


# ---------------------------------------------------------------------------
# Live proof
# ---------------------------------------------------------------------------
def test_live_router_battery_partition_is_complete_and_disjoint() -> None:
    family = _battery_family(_ROUTER)
    assert family, "the router runs no architectural battery gate"
    assert _violations_for(family) == []


# ---------------------------------------------------------------------------
# Fixture workflows: the shape WP12 ships, parsed by the same gate model
# ---------------------------------------------------------------------------
def _base_args(spec: BatterySpec) -> str:
    deselects = " ".join(f"--deselect {path}" for path in spec.base.deselect)
    return f'{" ".join(spec.base.paths)} -m "{spec.base.marker}" {deselects}'


def _workflow(tmp_path: Path, *, fast: bool, shards: Sequence[str], unpartitioned_heavy: bool = False) -> Path:
    """A tmp workflow with an optional ``fast`` job and a heavy job (matrix legs or one unpartitioned run)."""
    args = _base_args(_spec())
    lines = ["name: fixture", "on: push", "jobs:"]
    if fast:
        lines += [
            "  architectural-fast:",
            "    runs-on: ubuntu-24.04",
            "    steps:",
            f"      - run: uv run --frozen pytest {args} {_PLUGIN_ARGS} --battery-part fast",
        ]
    lines += ["  architectural-heavy:", "    runs-on: ubuntu-24.04"]
    if unpartitioned_heavy:
        lines += ["    steps:", f"      - run: uv run --frozen pytest {args}"]
    else:
        lines += ["    strategy:", "      matrix:", "        include:"]
        lines += [f"          - shard: '{shard}'" for shard in shards]
        lines += ["    steps:", f"      - run: uv run --frozen pytest {args} -n 4 --dist loadfile {_PLUGIN_ARGS} --battery-part ${{{{ matrix.shard }}}}"]
    path = tmp_path / "fixture.yml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_complete_fixture_workflow_has_no_violations(tmp_path: Path) -> None:
    family = _battery_family(_workflow(tmp_path, fast=True, shards=["1/2", "2/2"]))
    assert [gate.partition for gate in family] == [_FAST, "1/2", "2/2"]
    assert _violations_for(family) == []


def test_missing_leg_is_reported_as_file_in_no_set(tmp_path: Path) -> None:
    family = _battery_family(_workflow(tmp_path, fast=True, shards=["1/2"]))
    problems = _violations_for(family)
    assert any("battery partition 2/2 is missing" in p for p in problems)
    assert any("battery files are in no leg" in p for p in problems)


def test_duplicated_leg_is_reported_as_file_in_two_sets(tmp_path: Path) -> None:
    family = _battery_family(_workflow(tmp_path, fast=True, shards=["1/2", "1/2"]))
    problems = _violations_for(family)
    assert any("partition 1/2 appears 2 times" in p for p in problems)
    duplicated = next(iter(gc.battery_part_files("1/2")))
    assert any(p.startswith(f"{duplicated} is in two legs") for p in problems)


def test_mixed_partitioned_and_unpartitioned_family_is_reported(tmp_path: Path) -> None:
    family = _battery_family(_workflow(tmp_path, fast=True, shards=[], unpartitioned_heavy=True))
    problems = _violations_for(family)
    assert any(p.startswith("mixed partitioned and unpartitioned battery gates") for p in problems)
    assert any("is in two legs" in p for p in problems)


def test_mixed_family_is_reported_whichever_gate_comes_first(tmp_path: Path) -> None:
    family = _battery_family(_workflow(tmp_path, fast=True, shards=[], unpartitioned_heavy=True))
    problems = _violations_for(list(reversed(family)))
    assert any(p.startswith("mixed partitioned and unpartitioned battery gates") for p in problems)


def test_unknown_partition_leg_is_reported_not_raised(tmp_path: Path) -> None:
    family = _battery_family(_workflow(tmp_path, fast=True, shards=["1/2", "2/3"]))
    problems = _violations_for(family)
    assert any("unknown partition" in p for p in problems)
    assert any("battery partition 2/3 is not one of" in p for p in problems)


def test_wrong_base_arguments_are_reported(tmp_path: Path) -> None:
    path = _workflow(tmp_path, fast=True, shards=["1/2", "2/2"])
    path.write_text(path.read_text(encoding="utf-8").replace('-m "', '-m "slow and '), encoding="utf-8")
    problems = _violations_for(_battery_family(path))
    assert sum("!= registry base" in p for p in problems) == 3


def test_removed_deselect_is_reported(tmp_path: Path) -> None:
    path = _workflow(tmp_path, fast=True, shards=["1/2", "2/2"])
    dropped = _spec().base.deselect[0]
    path.write_text(path.read_text(encoding="utf-8").replace(f"--deselect {dropped}", ""), encoding="utf-8")
    problems = _violations_for(_battery_family(path))
    assert sum("!= registry base" in p for p in problems) == 3


def test_extra_path_is_reported() -> None:
    spec = _spec()
    gate = gc.Gate("w.yml", "heavy", None, paths=[*spec.base.paths, "tests/unit"], ignores=list(spec.base.deselect), marker_expr=spec.base.marker)
    assert any("!= registry base" in p for p in _violations_for([gate]))


def test_always_on_lanes_exclude_code_scoped_partitioned_and_directory_gates(tmp_path: Path) -> None:
    run = "      - run: uv run --frozen pytest {args}\n"
    jobs = {
        "lane-owned": ("", "tests/architectural/test_owned.py -q"),
        "lane-fork-guard": ("    if: github.repository == 'o/r'\n", "tests/architectural/test_guarded.py -q"),
        "lane-code-scoped": ("    if: needs.changes.outputs.x == 'true'\n", "tests/architectural/test_scoped.py -q"),
        "lane-partitioned": ("", f"tests/architectural/test_part.py {_PLUGIN_ARGS} --battery-part fast"),
        "lane-directory": ("", "tests/architectural -q"),
        "lane-elsewhere": ("", "tests/unit/test_u.py -q"),
    }
    text = "on: push\njobs:\n" + "".join(f"  {name}:\n    runs-on: ubuntu-24.04\n{cond}    steps:\n" + run.format(args=args) for name, (cond, args) in jobs.items())
    workflow = tmp_path / "lanes.yml"
    workflow.write_text(text, encoding="utf-8")
    assert _always_on_files(workflow) == {"tests/architectural/test_owned.py", "tests/architectural/test_guarded.py"}


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        (None, True),
        ("github.repository == 'o/r'", True),
        ("${{ (github.repository == 'o/r' || github.event_name == 'pull_request') && always() && !cancelled() }}", True),
        ("needs.changes.outputs.x == 'true'", False),
        ("${{ inputs.run_arch }}", False),
        ("github.event.pull_request.draft == false", False),
        ("github.repository == 'o/r' && steps.probe.outputs.ok == 'true'", False),
        ("github.event_name == 'needs.changes'", True),
    ],
)
def test_fork_guard_only_shape(condition: str | None, expected: bool) -> None:
    assert _is_fork_guard_only(condition) is expected


def test_always_on_lanes_exclude_non_needs_conditional_jobs(tmp_path: Path) -> None:
    text = (
        "on: push\njobs:\n"
        "  lane-input:\n    runs-on: ubuntu-24.04\n    if: inputs.run_arch\n    steps:\n      - run: uv run --frozen pytest tests/architectural/test_input.py -q\n"
        "  lane-owned:\n    runs-on: ubuntu-24.04\n    steps:\n      - run: uv run --frozen pytest tests/architectural/test_owned.py -q\n"
    )
    workflow = tmp_path / "lanes.yml"
    workflow.write_text(text, encoding="utf-8")
    assert _always_on_files(workflow) == {"tests/architectural/test_owned.py"}


def test_empty_family_is_reported() -> None:
    assert any("no architectural battery gate" in p for p in _violations_for([]))


def test_lone_unpartitioned_gate_is_a_violation(tmp_path: Path) -> None:
    family = _battery_family(_workflow(tmp_path, fast=False, shards=[], unpartitioned_heavy=True))
    assert [gate.partition for gate in family] == [None]
    problems = _violations_for(family)
    assert any(p.startswith("unpartitioned battery gate(s)") for p in problems)
    assert not any(p.startswith("mixed") for p in problems)


# ---------------------------------------------------------------------------
# Positive controls on the sets themselves
# ---------------------------------------------------------------------------
def test_injected_unassigned_file_is_reported(tmp_path: Path) -> None:
    family = _battery_family(_workflow(tmp_path, fast=True, shards=["1/2", "2/2"]))
    problems = _violations_for(family, base_files=_reference_base_files(_spec()) | {_INJECTED})
    assert any(_INJECTED in p and "are in no leg" in p for p in problems)


def test_part_dropping_bug_in_the_model_cannot_pass_the_live_proof(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mutation: the model drops one file from a shard AND derives its base from those same parts."""
    victim = sorted(gc.battery_part_files("1/2"))[0]
    real_part = gc.battery_part_files
    parts = _expected_partitions(_spec().shard_count)

    def dropping_part(partition: str) -> frozenset[str]:
        return real_part(partition) - {victim}

    monkeypatch.setattr(gc, "battery_part_files", dropping_part)
    monkeypatch.setattr(gc, "battery_base_files", lambda: frozenset().union(*(dropping_part(part) for part in parts)))
    problems = _violations_for(_battery_family(_ROUTER))
    assert any(victim in p and "are in no leg" in p for p in problems)


def test_roster_file_leaked_into_a_shard_is_reported(tmp_path: Path) -> None:
    family = _battery_family(_workflow(tmp_path, fast=True, shards=["1/2", "2/2"]))
    leaked = sorted(_spec().roster_paths)[0]

    def leaky(gate: gc.Gate) -> frozenset[str]:
        files = _model_files_of(gate)
        return files | {leaked} if gate.partition == "1/2" else files

    problems = _violations_for(family, files_of=leaky)
    assert any(p.startswith(f"{leaked} is in two legs") for p in problems)


def test_fast_leg_that_is_not_the_roster_is_reported(tmp_path: Path) -> None:
    family = _battery_family(_workflow(tmp_path, fast=True, shards=["1/2", "2/2"]))
    dropped = sorted(_spec().roster_paths)[0]

    def short(gate: gc.Gate) -> frozenset[str]:
        files = _model_files_of(gate)
        return files - {dropped} if gate.partition == _FAST else files

    assert any("fast leg" in p for p in _violations_for(family, files_of=short))


def test_roster_entry_outside_the_base_is_reported(tmp_path: Path) -> None:
    family = _battery_family(_workflow(tmp_path, fast=True, shards=["1/2", "2/2"]))
    spec = _spec()
    problems = partition_violations(
        family,
        _reference_base_files(spec),
        _model_files_of,
        shard_count=spec.shard_count,
        roster=frozenset(spec.roster_paths) | {_INJECTED},
        base=spec.base,
        always_on_files=_always_on_files(_ROUTER),
    )
    assert f"roster file {_INJECTED} is not a battery base file" in problems


def test_deselect_not_owned_by_an_always_on_lane_is_reported(tmp_path: Path) -> None:
    family = _battery_family(_workflow(tmp_path, fast=True, shards=["1/2", "2/2"]))
    spec = _spec()
    problems = partition_violations(
        family,
        _reference_base_files(spec),
        _model_files_of,
        shard_count=spec.shard_count,
        roster=frozenset(spec.roster_paths),
        base=spec.base,
        always_on_files=_always_on_files(_ROUTER) - {sorted(spec.base.deselect)[0]},
    )
    assert any("(C-002)" in p for p in problems)


def test_always_on_lanes_of_the_live_router_own_exactly_the_registry_deselects() -> None:
    assert _always_on_files(_ROUTER) == frozenset(_spec().base.deselect)


def test_injected_file_without_timing_is_assigned_to_exactly_one_leg() -> None:
    spec = _spec()
    parts = shard_select.battery_parts([*sorted(_reference_base_files(spec)), _INJECTED], spec.roster_paths, spec.shard_count, _timings(spec))
    homes = [key for key, files in parts.parts.items() if _INJECTED in files]
    assert len(homes) == 1
    assert homes[0] != _FAST
    assert _INJECTED in parts.resolution.missing


def test_missing_timing_report_names_the_injected_file(capsys: pytest.CaptureFixture[str]) -> None:
    parts = shard_select.battery_parts(["a.py", "b.py", _INJECTED], [], 2, {"a.py": 5.0, "b.py": 3.0})
    shard_select.report_mismatch(parts.resolution, label="battery")
    assert _INJECTED in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Gate-model support for ``--battery-part`` (D-02)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("uv run --frozen pytest tests/architectural --battery-part fast", "fast"),
        ("uv run --frozen pytest tests/architectural --battery-part 1/2", "1/2"),
        ("uv run --frozen pytest tests/architectural --battery-part=2/2", "2/2"),
        ('uv run --frozen pytest tests/architectural --battery-part "1/2"', "1/2"),
        ("uv run --frozen pytest tests/architectural", None),
        ("echo --battery-part 9/9 && uv run --frozen pytest tests/architectural", None),
        ("uv run --frozen pytest tests/architectural && echo --battery-part 9/9", None),
    ],
)
def test_extract_battery_part_reads_only_the_pytest_command(line: str, expected: str | None) -> None:
    assert gc.extract_battery_part(line) == expected


def test_parse_pytest_invocation_keeps_its_three_tuple_shape() -> None:
    parsed = gc.parse_pytest_invocation(f'pytest tests/architectural -m "fast" {_PLUGIN_ARGS} --battery-part 1/2 --deselect tests/architectural/test_x.py')
    assert parsed == (["tests/architectural"], ["tests/architectural/test_x.py"], "fast")


def test_gate_label_names_its_part() -> None:
    plain = gc.Gate(workflow="w.yml", job="j", shard=None)
    parted = gc.Gate(workflow="w.yml", job="j", shard=None, partition="1/2")
    assert plain.label() == "w.yml::j"
    assert parted.label() == "w.yml::j [part 1/2]"


def test_gate_equality_includes_the_partition() -> None:
    assert gc.Gate("w.yml", "j", None, partition="1/2") != gc.Gate("w.yml", "j", None, partition="2/2")
    assert gc.Gate("w.yml", "j", None) == gc.Gate("w.yml", "j", None)


def test_compiled_partitioned_gate_selects_only_its_part_files() -> None:
    inside = sorted(gc.battery_part_files("1/2"))[0]
    outside = sorted(gc.battery_part_files("2/2"))[0]
    gate = gc.Gate("w.yml", "j", "1/2", paths=[_BATTERY_ROOT], marker_expr=None, partition="1/2")
    compiled = gc.CompiledGate(gate)
    assert compiled.selects(inside, f"{inside}::t", set())
    assert not compiled.selects(outside, f"{outside}::t", set())
    assert gc.CompiledGate(gc.Gate("w.yml", "j", None, paths=[_BATTERY_ROOT])).selects(outside, f"{outside}::t", set())


def test_unknown_partition_fails_closed() -> None:
    with pytest.raises(ValueError, match="9/9"):
        gc.battery_part_files("9/9")


def test_partition_survives_a_script_indirection(tmp_path: Path) -> None:
    script = tmp_path / "run.sh"
    script.write_text(f"pytest tests/architectural {_PLUGIN_ARGS} --battery-part 2/2\n", encoding="utf-8")
    [invocation] = gc.suite_invocations("bash run.sh", repo_root=tmp_path)
    assert invocation.partition == "2/2"


def test_partition_survives_a_make_indirection(tmp_path: Path) -> None:
    makefile = tmp_path / "Makefile"
    makefile.write_text(f"battery:\n\tpytest tests/architectural {_PLUGIN_ARGS} --battery-part fast\n", encoding="utf-8")
    [invocation] = gc.suite_invocations("make battery", makefile=makefile)
    assert invocation.partition == _FAST


def test_matrix_shard_is_resolved_into_the_gate_partition(tmp_path: Path) -> None:
    family = _battery_family(_workflow(tmp_path, fast=False, shards=["1/2", "2/2"]))
    assert sorted(str(gate.partition) for gate in family) == ["1/2", "2/2"]
    assert {gate.shard for gate in family} == {"1/2", "2/2"}


# ---------------------------------------------------------------------------
# D-24: the plugin's runtime keep/ignore decision IS the model's part set
# ---------------------------------------------------------------------------
def enumeration_divergences(
    keeps: Callable[[str, str], bool],
    model_files: Callable[[str], frozenset[str]],
    base_files: frozenset[str],
    parts: Sequence[str],
) -> list[str]:
    """Files whose runtime keep decision differs from the model's part membership, by name."""
    problems = []
    for part in parts:
        members = model_files(part)
        for file in sorted(base_files):
            if keeps(part, file) != (file in members):
                problems.append(f"{file}: plugin keeps={keeps(part, file)} but model membership of {part} is {file in members}")
    return problems


def _plugin_keeps() -> Callable[[str, str], bool]:
    spec = _spec()
    partition = plugin.compute_partition(spec, gc.REPO_ROOT, _timings(spec))
    states = {key: plugin.build_state(plugin.parse_part(key), spec, partition) for key in _expected_partitions(spec.shard_count)}
    return lambda requested, file: not plugin.ignores_file(file, states[requested])


def test_plugin_keep_decision_equals_model_part_sets() -> None:
    spec = _spec()
    parts = _expected_partitions(spec.shard_count)
    base_files = gc.battery_base_files()
    assert base_files == _reference_base_files(spec)
    assert enumeration_divergences(_plugin_keeps(), gc.battery_part_files, base_files, parts) == []
    reference = _reference_parts(spec)
    for part in parts:
        assert gc.battery_part_files(part) == reference[part], part


def test_plugin_and_model_share_the_one_enumeration_function() -> None:
    namespace = vars(plugin)
    assert namespace["enumerate_base_files"] is shard_select.enumerate_base_files
    assert namespace["battery_parts"] is shard_select.battery_parts


def test_divergent_enumeration_is_detected() -> None:
    spec = _spec()
    parts = _expected_partitions(spec.shard_count)
    base_files = gc.battery_base_files()
    victim = sorted(gc.battery_part_files("1/2"))[0]

    def model_dropping_one(part: str) -> frozenset[str]:
        return gc.battery_part_files(part) - {victim}

    problems = enumeration_divergences(_plugin_keeps(), model_dropping_one, base_files, parts)
    assert [p for p in problems if p.startswith(victim)] == [f"{victim}: plugin keeps=True but model membership of 1/2 is False"]

    def model_adding_one(part: str) -> frozenset[str]:
        return gc.battery_part_files(part) | ({victim} if part == "2/2" else set())

    assert any(p.startswith(f"{victim}: plugin keeps=False") for p in enumeration_divergences(_plugin_keeps(), model_adding_one, base_files, parts))
