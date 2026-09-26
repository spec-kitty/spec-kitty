#!/usr/bin/env python3
"""WP09 mutation matrix: the re-runnable evidence substitute for the ATDD-First exception.

WP09 retires ``tests/status/test_parity.py``. Under the operator-approved charter
exception (plan D-OP-4 / Complexity Tracking; DM-01M3F3T1G2RYW7P0ZVWQS41GEZ)
there is no honest RED-on-base commit, so this script is the evidence: for each
invariant the parity file pinned, it plants a temporary mutation and reports which
test node IDs go RED. A parity test is retired as a duplicate only when its
mutation also reds a named survivor; otherwise it is relocated, and its relocated
node must go RED at the lane head.

Isolation (C-005): every run happens in a throwaway, detached ``git worktree`` of
``--base-root``'s HEAD. Source mutations are edits inside that throwaway tree; the
one site-packages mutation (M1) is a pytest plugin loaded with ``-p`` that
monkeypatches at import time. Nothing is ever written to the checkout under test,
and the throwaway worktree is removed at the end.

Usage (reviewer RED reproduction)::

    git worktree add /tmp/wp09-base <planning-base-sha>
    .venv/bin/python kitty-specs/<mission>/research/wp09_mutation_matrix.py --base-root /tmp/wp09-base
    git worktree remove /tmp/wp09-base
    .venv/bin/python kitty-specs/<mission>/research/wp09_mutation_matrix.py --base-root <lane-head-worktree>

Verdict per row: ``OK`` when every expected node that EXISTS in the tree under
test failed by assertion; ``MISSING`` names an expected node that stayed green;
``ERROR`` flags a row whose reds include setup/collection errors (not valid
evidence for the nodes concerned). Expected nodes absent from the tree (e.g. the
parity file at the lane head, or a relocated test at base) are listed as ``n/a``.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

TEST_FILES = (
    "tests/status/test_parity.py",
    "tests/status/test_reducer.py",
    "tests/status/test_transitions.py",
    "tests/status/test_models.py",
    "tests/status/test_validate.py",
    "tests/architectural/test_no_retired_subsystems.py",
)

P = "tests/status/test_parity.py"
R = "tests/status/test_reducer.py"
T = "tests/status/test_transitions.py"
MOD = "tests/status/test_models.py"
ARCH = "tests/architectural/test_no_retired_subsystems.py"


@dataclass(frozen=True)
class Mutation:
    mid: str
    description: str
    target: str
    expected: tuple[str, ...]
    plugin: str | None = None
    edits: tuple[tuple[str, str, str], ...] = ()
    new_files: tuple[tuple[str, str], ...] = ()
    notes: str = ""


def _recompute(cls: str, extra: str, drop: str = "") -> str:
    """Plugin body for M2-M4: rewire one state's edges, then recompute the frozen projection."""
    return textwrap.dedent(
        f"""
        from specify_cli.status import wp_state as _ws
        from specify_cli.status.models import Lane as _Lane
        _orig = _ws.{cls}.allowed_targets
        def _mut(self):
            return frozenset((_orig(self) - {{{drop}}}) | {{{extra}}})
        _ws.{cls}.allowed_targets = _mut
        import specify_cli.status.transitions as _tr
        import specify_cli.status as _pkg
        _tr.ALLOWED_TRANSITIONS = _tr._derive_allowed_transitions()
        _pkg.ALLOWED_TRANSITIONS = _tr.ALLOWED_TRANSITIONS
        """
    )


def _wrap_reduce(body: str) -> str:
    """Plugin body wrapping the ``reduce_parsed`` binding the status reducer folds through.

    ``body`` sees ``transitions`` / ``annotations`` before the fold and ``state``
    after it; it may rebind ``transitions`` or mutate ``state`` in place.
    """
    return textwrap.dedent(
        """
        import specify_cli.status.reducer as _r
        _orig = _r.reduce_parsed
        def _mut(transitions, annotations=None):
            state = None
        {pre}
            state = _orig(transitions, annotations)
        {post}
            return state
        _r.reduce_parsed = _mut
        """
    ).format(pre=textwrap.indent(body.split("---")[0].strip(), "    "), post=textwrap.indent(body.split("---")[1].strip(), "    "))


MUTATIONS: tuple[Mutation, ...] = (
    Mutation(
        "M1",
        "event sort is a no-op (shadow builtin `sorted` in spec_kitty_events.diary)",
        "spec_kitty_events.diary.reduce_parsed (site-packages)",
        (
            f"{P}::TestReducerDeterminism::test_event_order_does_not_affect_final_state",
            f"{R}::TestReduceOutOfOrder::test_reduce_out_of_order_events",
        ),
        plugin=textwrap.dedent(
            """
            import spec_kitty_events.diary as _d
            _d.sorted = lambda it, key=None, reverse=False: list(it)
            """
        ),
    ),
    Mutation(
        "M2",
        "add done -> planned edge (DoneState.allowed_targets) + recompute ALLOWED_TRANSITIONS",
        "wp_state.DoneState + transitions.ALLOWED_TRANSITIONS",
        (
            f"{P}::TestTransitionMatrixParity::test_terminal_lanes_have_no_outbound_transitions",
            f"{T}::TestConstants::test_allowed_transitions_count",
            f"{T}::TestIllegalTransitions::test_illegal_transition_rejected[done-planned]",
            f"{T}::TestBehaviorPreservationParity::test_validate_transition_matches_baseline",
            f"{T}::TestTerminalForceExitParity::test_terminal_exit_without_force_is_illegal[done]",
            f"{T}::TestBehaviorPreservationParity::test_collapsed_matrix_catches_planted_row",
        ),
        plugin=_recompute("DoneState", "_Lane.PLANNED"),
    ),
    Mutation(
        "M3",
        "add claimed -> claimed self-edge + recompute ALLOWED_TRANSITIONS",
        "wp_state.ClaimedState + transitions.ALLOWED_TRANSITIONS",
        (
            f"{P}::TestTransitionMatrixParity::test_no_self_transitions_in_matrix",
            f"{T}::TestConstants::test_allowed_transitions_count",
            f"{T}::TestBehaviorPreservationParity::test_validate_transition_matches_baseline",
            f"{T}::TestBehaviorPreservationParity::test_collapsed_matrix_catches_planted_row",
        ),
        plugin=_recompute("ClaimedState", "_Lane.CLAIMED"),
    ),
    Mutation(
        "M4",
        "add planned -> uninitialized (non-canonical target) + recompute ALLOWED_TRANSITIONS",
        "wp_state.PlannedState + transitions.ALLOWED_TRANSITIONS",
        (
            f"{P}::TestTransitionMatrixParity::test_transition_pairs_use_canonical_lanes",
            f"{T}::TestConstants::test_allowed_transitions_count",
        ),
        plugin=_recompute("PlannedState", "_Lane.UNINITIALIZED"),
    ),
    Mutation(
        "M4b",
        "count-preserving swap: planned -> blocked replaced by planned -> uninitialized + recompute",
        "wp_state.PlannedState + transitions.ALLOWED_TRANSITIONS",
        (
            f"{P}::TestTransitionMatrixParity::test_transition_pairs_use_canonical_lanes",
            f"{T}::TestBehaviorPreservationParity::test_validate_transition_matches_baseline",
        ),
        plugin=_recompute("PlannedState", "_Lane.UNINITIALIZED", drop="_Lane.BLOCKED"),
        notes="records whether the golden baseline (not the count test) catches a count-preserving swap",
    ),
    Mutation(
        "M5",
        'rename CANONICAL_LANES entry "in_review" -> "under_review" (count-preserving)',
        "src/specify_cli/status_lanes.py",
        (
            f"{P}::TestTransitionMatrixParity::test_all_canonical_lanes_in_enum",
            f"{T}::TestConstants::test_all_canonical_lanes_in_enum",
        ),
        edits=(("src/specify_cli/status_lanes.py", '    "in_review",\n    "approved",', '    "under_review",\n    "approved",'),),
        notes='"reviewing" is avoided: test_validate.py::test_non_canonical_to_lane probes that literal, a coincidental (non-survivor) red',
    ),
    Mutation(
        "M6",
        "append display member Lane.SHADOW='shadow' (not in CANONICAL_LANES; zero-edge factory entry)",
        "src/specify_cli/status/models.py (+ wp_state._STATE_MAP so import succeeds)",
        (
            f"{P}::TestTransitionMatrixParity::test_all_enum_values_in_canonical_lanes",
            f"{MOD}::TestLaneEnum::test_lane_member_names_exact",
        ),
        edits=(
            ("src/specify_cli/status/models.py", '    CANCELED = "canceled"\n', '    CANCELED = "canceled"\n    SHADOW = "shadow"\n'),
            ("src/specify_cli/status/wp_state.py", '    "canceled": CanceledState,\n}', '    "canceled": CanceledState,\n    "shadow": UninitializedState,\n}'),
        ),
    ),
    Mutation(
        "M7",
        "materialize_to_json drops sort_keys=True",
        "src/specify_cli/status/reducer.py::materialize_to_json",
        (
            f"{P}::TestReducerDeterminism::test_sorted_keys_in_json_output",
            f"{R}::TestByteIdenticalOutput::test_sorted_keys_in_json_output",
        ),
        edits=(("src/specify_cli/status/reducer.py", "            snapshot.to_dict(),\n            sort_keys=True,", "            snapshot.to_dict(),\n            sort_keys=False,"),),
    ),
    Mutation(
        "M8",
        "StatusSnapshot.from_dict drops last_event_id",
        "src/specify_cli/status/models.py::StatusSnapshot.from_dict",
        (
            f"{P}::TestReducerDeterminism::test_reduce_then_serialize_roundtrip",
            f"{P}::TestFullEventLogParity::test_realistic_log_json_roundtrip_stable",
            f"{R}::TestRealisticEventLog::test_realistic_log_json_roundtrip_stable",
        ),
        edits=(("src/specify_cli/status/models.py", '            event_count=data["event_count"],\n            last_event_id=data.get("last_event_id"),', '            event_count=data["event_count"],\n            last_event_id=None,'),),
    ),
    Mutation(
        "M9",
        "materialize_to_json injects a per-call random key",
        "src/specify_cli/status/reducer.py::materialize_to_json",
        (
            f"{P}::TestFullEventLogParity::test_realistic_log_identical_across_runs",
            f"{R}::TestByteIdenticalOutput::test_byte_identical_across_reduce_calls",
        ),
        edits=(("src/specify_cli/status/reducer.py", "            snapshot.to_dict(),\n            sort_keys=True,", '            {**snapshot.to_dict(), "_nonce": __import__("uuid").uuid4().hex},\n            sort_keys=True,'),),
    ),
    Mutation(
        "M10",
        "plant top-level `from specify_cli.sync import x` in status/emit.py (+ stub package so imports resolve)",
        "src/specify_cli/status/emit.py",
        (
            f"{P}::TestBackportReadiness::test_emit_module_has_no_toplevel_sync_import",
            f"{P}::TestBackportReadiness::test_no_status_module_directly_imports_sync_at_toplevel",
            f"{P}::TestBackportReadiness::test_module_importable_without_sync[specify_cli.status.emit]",
            f"{ARCH}::test_no_retired_import_targets_exist",
        ),
        edits=(("src/specify_cli/status/emit.py", "from __future__ import annotations\n", "from __future__ import annotations\n\nfrom specify_cli.sync import x  # WP09 M10 planted mutation\n"),),
        new_files=(("src/specify_cli/sync/__init__.py", "x = None\n"),),
        notes="the stub package also trips test_no_retired_paths_exist; the import scan is the named survivor",
    ),
    Mutation(
        "M11",
        "dedup keeps the LAST occurrence of a duplicated event_id",
        "specify_cli.status.reducer.reduce_parsed binding (wrapper)",
        (
            f"{P}::TestReducerDeterminism::test_duplicate_events_deduplicated_deterministically",
            f"{R}::TestReduceDeduplication::test_reduce_deduplication",
        ),
        plugin=_wrap_reduce("transitions = list({e.event_id: e for e in transitions}.values())\n---\npass"),
    ),
    Mutation(
        "M12",
        "force_count is never accumulated (zeroed after the fold)",
        "specify_cli.status.reducer.reduce_parsed binding (wrapper)",
        (
            f"{P}::TestReducerDeterminism::test_force_events_tracked_in_force_count",
            f"{R}::TestReduceForceCount::test_reduce_force_count_tracked",
        ),
        plugin=_wrap_reduce("pass\n---\nfor _wp in state.work_packages.values():\n    _wp['force_count'] = 0"),
    ),
    Mutation(
        "M13",
        "invert rollback classification (spec_kitty_events.diary._is_rollback_event)",
        "spec_kitty_events.diary rollback precedence (site-packages)",
        (
            f"{P}::TestReducerDeterminism::test_concurrent_events_rollback_precedence",
            f"{R}::TestReduceConcurrentRollbackPrecedence::test_in_review_to_in_progress_rollback_beats_concurrent_approval",
        ),
        plugin=textwrap.dedent(
            """
            import spec_kitty_events.diary as _d
            _orig = _d._is_rollback_event
            _d._is_rollback_event = lambda event: not _orig(event)
            """
        ),
        notes="precedence REMOVAL (_should_apply_event -> True) is invisible to the parity test (its rollback also sorts last); see M13b",
    ),
    Mutation(
        "M13b",
        "remove rollback precedence entirely (_should_apply_event always applies)",
        "spec_kitty_events.diary._should_apply_event (site-packages)",
        (f"{R}::TestReduceConcurrentRollbackPrecedence::test_in_review_to_in_progress_rollback_beats_concurrent_approval",),
        plugin=textwrap.dedent(
            """
            import spec_kitty_events.diary as _d
            _d._should_apply_event = lambda current, event, all_events: True
            """
        ),
        notes="expected: survivor RED, parity test GREEN (parity is strictly weaker than the survivor)",
    ),
    Mutation(
        "M14",
        "reduce() is per-call nondeterministic (random slot in every WP state)",
        "specify_cli.status.reducer.reduce_parsed binding (wrapper)",
        (
            f"{P}::TestReducerDeterminism::test_same_events_produce_identical_snapshots",
            f"{R}::TestByteIdenticalOutput::test_byte_identical_across_reduce_calls",
        ),
        plugin=_wrap_reduce("pass\n---\nimport uuid as _uuid\nfor _wp in state.work_packages.values():\n    _wp['_nonce'] = _uuid.uuid4().hex"),
    ),
    Mutation(
        "M15",
        "summary under-counts canceled WPs",
        "specify_cli.status.reducer.reduce_parsed binding (wrapper)",
        (
            f"{P}::TestFullEventLogParity::test_realistic_log_produces_expected_summary",
            f"{R}::TestRealisticEventLog::test_realistic_log_produces_expected_summary",
        ),
        plugin=_wrap_reduce("pass\n---\nif 'canceled' in state.summary:\n    state.summary['canceled'] = 0"),
    ),
    Mutation(
        "M16",
        "re-create module specify_cli.status.phase",
        "src/specify_cli/status/phase.py (new file)",
        (f"{P}::TestPhaseCap::test_phase_module_deleted",),
        new_files=(("src/specify_cli/status/phase.py", '"""WP09 M16 planted module."""\n'),),
        notes="scaffold proof: the tombstone can only fail if a module of that name is re-created; it pins no behaviour",
    ),
)


@dataclass
class RunResult:
    collected: set[str] = field(default_factory=set)
    failed: set[str] = field(default_factory=set)
    errored: set[str] = field(default_factory=set)
    returncode: int = 0


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def _nodeid(tree: Path, classname: str, name: str) -> str:
    parts = classname.split(".")
    for cut in range(len(parts), 0, -1):
        candidate = Path(*parts[:cut]).with_suffix(".py")
        if (tree / candidate).is_file():
            return "::".join([candidate.as_posix(), *parts[cut:], name])
    return f"{classname}::{name}"


def _parse_junit(tree: Path, xml_path: Path) -> RunResult:
    result = RunResult()
    if not xml_path.exists():
        return result
    for case in ET.parse(xml_path).getroot().iter("testcase"):
        node = _nodeid(tree, case.get("classname", ""), case.get("name", ""))
        result.collected.add(node)
        if case.find("failure") is not None:
            result.failed.add(node)
        if case.find("error") is not None:
            result.errored.add(node)
    return result


def _apply(tree: Path, mutation: Mutation) -> None:
    for rel, old, new in mutation.edits:
        path = tree / rel
        text = path.read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise SystemExit(f"{mutation.mid}: anchor not unique/absent in {rel} (count={text.count(old)})")
        path.write_text(text.replace(old, new), encoding="utf-8")
    for rel, content in mutation.new_files:
        path = tree / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _reset(tree: Path) -> None:
    _git(tree, "checkout", "--", ".")
    _git(tree, "clean", "-fdq", "--", "src")


def _run(tree: Path, mutation: Mutation | None, scratch: Path, python: str, workers: int) -> RunResult:
    files = [f for f in TEST_FILES if (tree / f).is_file()]
    tag = mutation.mid if mutation else "BASELINE"
    xml_path = scratch / f"{tag}.xml"
    env = dict(os.environ)
    pythonpath = [str(tree / "src"), str(scratch)]
    cmd = [python, "-m", "pytest", *files, "-q", "-p", "no:cacheprovider", "-o", "addopts=", f"--junitxml={xml_path}"]
    if workers > 0:
        cmd += ["-n", str(workers), "--dist", "loadfile"]
    if mutation and mutation.plugin:
        plugin_name = f"wp09_mutplug_{mutation.mid.lower()}"
        (scratch / f"{plugin_name}.py").write_text(mutation.plugin, encoding="utf-8")
        cmd += ["-p", plugin_name]
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    proc = subprocess.run(cmd, cwd=tree, env=env, capture_output=True, text=True)
    result = _parse_junit(tree, xml_path)
    result.returncode = proc.returncode
    if not result.collected:
        sys.stderr.write(proc.stdout[-4000:] + proc.stderr[-4000:])
    return result


def _row(mutation: Mutation, res: RunResult) -> tuple[str, list[str]]:
    lines: list[str] = []
    missing = []
    for node in mutation.expected:
        if node not in res.collected:
            lines.append(f"    n/a     {node}")
        elif node in res.failed:
            lines.append(f"    RED     {node}")
        elif node in res.errored:
            lines.append(f"    ERROR   {node}")
            missing.append(node)
        else:
            lines.append(f"    GREEN!  {node}")
            missing.append(node)
    present = [n for n in mutation.expected if n in res.collected]
    if not present:
        verdict = "NO-EXPECTED-NODE-PRESENT"
    elif missing:
        verdict = "MISSING"
    else:
        verdict = "OK"
    if res.errored:
        verdict += " (+errors)"
    return verdict, lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-root", type=Path, default=Path(__file__).resolve().parents[3], help="checkout under test (its HEAD is used)")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--workers", type=int, default=2, help="pytest-xdist workers (0 = serial)")
    parser.add_argument("--only", default="", help="comma-separated mutation ids, e.g. M1,M7")
    args = parser.parse_args()

    base_root = args.base_root.resolve()
    head = _git(base_root, "rev-parse", "HEAD").strip()
    selected = [m for m in MUTATIONS if not args.only or m.mid in args.only.split(",")]
    scratch = Path(tempfile.mkdtemp(prefix="wp09-matrix-"))
    tree = scratch / "tree"
    _git(base_root, "worktree", "add", "--detach", "--quiet", str(tree), head)
    try:
        print(f"# WP09 mutation matrix @ {head[:12]} (base-root {base_root})")
        baseline = _run(tree, None, scratch, args.python, args.workers)
        print(f"BASELINE: collected={len(baseline.collected)} failed={len(baseline.failed)} errored={len(baseline.errored)} rc={baseline.returncode}")
        for node in sorted(baseline.failed | baseline.errored):
            print(f"    baseline-red {node}")
        print()
        for mutation in selected:
            _reset(tree)
            _apply(tree, mutation)
            res = _run(tree, mutation, scratch, args.python, args.workers)
            new_red = (res.failed | res.errored) - (baseline.failed | baseline.errored)
            verdict, lines = _row(mutation, res)
            print(f"{mutation.mid} | {mutation.description}")
            print(f"    target: {mutation.target}")
            if mutation.notes:
                print(f"    note:   {mutation.notes}")
            print(f"    verdict: {verdict}  (red={len(new_red)} of collected={len(res.collected)}, rc={res.returncode})")
            print("    expected:")
            print("\n".join(lines))
            print("    all red node IDs (mutation-induced):")
            for node in sorted(new_red):
                kind = "error" if node in res.errored else "fail"
                print(f"      [{kind}] {node}")
            print()
    finally:
        subprocess.run(["git", "-C", str(base_root), "worktree", "remove", "--force", str(tree)], check=False)
        shutil.rmtree(scratch, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
