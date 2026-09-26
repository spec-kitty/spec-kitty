"""Scope: #2945 — merge WP-granular exclusion of canceled work packages (WP03).

FR-004 / FR-009 merge face. A canceled work package has no review artifact and
never reaches ``done``; before this WP a canceled WP anywhere in ``lanes.json``
broke ``spec-kitty merge`` — it was driven through the invalid ``canceled ->
done`` bookkeeping and demanded a review/done state it can never hold. This WP
excludes canceled-with-provenance WPs from BOTH per-WP derivations
(``executor.py``'s ``all_wp_ids`` AND the independent per-lane loop in
``done_bookkeeping._record_merged_wps_done_for_merge``), skips a lane branch only
when EVERY WP in it is canceled, and routes the merge gates' dependency/evidence
acceptability through the single ``is_acceptable_ending`` authority.

``test_merge_excludes_canceled_wps_and_lands_survivor`` is the SC-001 proof: it
drives the REAL ``_run_lane_based_merge`` against an on-disk coordination-topology
git repository (the #2945 shape — a WP canceled mid-mission AFTER finalize, its
lane branch existing for a mixed lane and absent for a fully-canceled lane). It
leaves the done-bookkeeping seam UNMOCKED (``_record_merged_wps_done_for_merge``
/ ``_mark_wp_merged_done`` / ``_assert_merged_wps_reached_done`` all real) so the
exclusion is observed end-to-end, never through an isolated seam call. All
in-diff assertions read the committed coordination ref; there is no post-merge
manual observation.

The gate tests exercise the REAL ``evaluate_merge_gates`` / ``_evaluate_*_gate``
over real on-disk files (a flat mission), proving the FR-009 merge-face routing:
a canceled-with-provenance dependency does not strand a surviving dependent, and
a synthetic (non-provenance) cancellation still fails — so the routing honors
provenance rather than blanket-accepting ``canceled``.

Harness note: the coord-worktree materialization + real done-bookkeeping seam is
modeled on the proven coord-topology full-merge harness in
``tests/merge/test_issue_2711_merge_rollback_resume_coherence.py`` and
``tests/specify_cli/cli/commands/test_merge_coord_topology_1772.py``. The seeded
canceled event carries ``reason_source: "operator"`` — the exact durable byte the
canonical ``move-task --to canceled --note "<reason>"`` persists (the
``_mt_hop_reason_source`` operator branch): the reduced snapshot the merge reads
is therefore byte-identical to the post-move-task state, so the fixture stays on
the real-git merge path rather than layering a CliRunner cancel onto the
subprocess-git coord topology.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from kernel.clock import now_utc_iso

# Import the status package before any coordination submodule (production import
# order) to avoid the known ``coordination -> transaction -> status`` cycle when a
# test module imports ``merge`` first under ``PYTHONPATH=src``.
import specify_cli.status  # noqa: F401  # import-order guard (see comment above)

from specify_cli.cli.commands.merge import _run_lane_based_merge
from specify_cli.coordination.status_service import (
    EventLogReadContract,
    read_event_log,
    wp_lane_actor_from_events,
)
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.merge.config import MergeStrategy
from specify_cli.policy.config import MergeGateConfig
from specify_cli.policy.merge_gates import GateVerdict, evaluate_merge_gates
from specify_cli.status import Lane, StatusEvent

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]


# ---------------------------------------------------------------------------
# Mission identity (slug ends with ``-<mid8>`` so the coordination branch IS the
# lanes-manifest mission branch — the production 083+ coord-topology layout).
# ---------------------------------------------------------------------------

MID8 = "01M2945C"
MISSION_ID = "01M2945C000000000000002945"
MISSION_SLUG = f"merge-canceled-wp-{MID8}"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}"

WP_SURVIVOR = "WP01"  # approved survivor in the mixed lane-a
WP_CANCELED_MIXED = "WP02"  # canceled+provenance in lane-a (mixed lane)
WP_CANCELED_LANE = "WP03"  # canceled+provenance sole WP in lane-b (fully canceled)

LANE_MIXED = "lane-a"
LANE_ALL_CANCELED = "lane-b"
SURVIVOR_CODE = "src/survivor_code.py"

_OPERATOR_CANCEL_NOTE = "operator replan: descoped after finalize (#2945)"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args])


def _init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", "main", str(repo)])
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


def _file_on_branch(repo: Path, branch: str, relpath: str) -> bool:
    """Return True iff *relpath* exists on *branch* (via ``git ls-tree``)."""
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "--name-only", "-r", branch, "--", relpath],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and relpath in result.stdout.splitlines()


def _branch_exists(repo: Path, branch: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", branch],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Coord-topology fixture (local fusion helpers — see module docstring)
# ---------------------------------------------------------------------------


def _write_meta(feature_dir: Path) -> None:
    meta = {
        "mission_slug": MISSION_SLUG,
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "coordination_branch": COORD_BRANCH,
        "purpose_tldr": "merge WP-granular canceled-WP exclusion (#2945)",
        "purpose_context": "a canceled WP must not break merge of surviving work",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_manifest(feature_dir: Path) -> LanesManifest:
    """Two lanes: a MIXED lane (survivor + canceled) and a FULLY-canceled lane."""
    manifest = LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        # ``mission_id`` MUST be the ULID ``MISSION_ID`` (never the slug -- see
        # ``LanesManifest.mission_id``'s docstring, "ULID or None; never a
        # slug"). The prior comment here ("mission_id == slug => legacy
        # lane_branch_name form") was WRONG: ``lane_branch_name`` takes the
        # NEW mid8-based naming branch whenever ``mission_id is not None`` --
        # passing the slug derived a MANGLED lane branch
        # (``...-merge-ca-lane-mixed``) that never matched the real one this
        # fixture creates below, so the reconciliation claim builder silently
        # resolved empty authorship on every run (Epic #5001 landing
        # remediation; invisible before FIX C's new fail-closed
        # squash-vacuous-authorship guard surfaced it). ``mission_id=None``
        # would resolve the same (legacy) branch name here too, since the
        # slug already carries the ``-<mid8>`` suffix, but the real ULID is
        # the contract-correct value.
        mission_id=MISSION_ID,
        mission_branch=COORD_BRANCH,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id=LANE_MIXED,
                wp_ids=(WP_SURVIVOR, WP_CANCELED_MIXED),
                write_scope=(SURVIVOR_CODE,),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            ),
            ExecutionLane(
                lane_id=LANE_ALL_CANCELED,
                wp_ids=(WP_CANCELED_LANE,),
                write_scope=("src/never_built.py",),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            ),
        ],
        computed_at=now_utc_iso(),
        computed_from="test-fixture",
    )
    write_lanes_json(feature_dir, manifest)
    return manifest


def _write_wp_file(feature_dir: Path, wp_id: str) -> None:
    (feature_dir / "tasks" / f"{wp_id}-work.md").write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: {wp_id} work\nagent: implementer-bot\n---\n# {wp_id}\n",
        encoding="utf-8",
    )


def _approved_event(wp_id: str) -> dict[str, object]:
    return {
        "actor": "reviewer-renata",
        "at": now_utc_iso(),
        "event_id": f"01HXYZAPPR0000000000000{wp_id}",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": MISSION_SLUG,
        "force": False,
        "from_lane": "in_review",
        "reason": None,
        "review_ref": f"review-{wp_id}",
        "to_lane": "approved",
        "wp_id": wp_id,
    }


def _canceled_operator_event(wp_id: str) -> dict[str, object]:
    """A canceled event with operator-authored provenance.

    ``reason_source: "operator"`` is exactly what ``move-task --to canceled
    --note "<reason>"`` persists (``_mt_hop_reason_source`` operator branch), so
    the reduced snapshot the merge reads is byte-identical to the post-move-task
    state.
    """
    return {
        "actor": "operator-alice",
        "at": now_utc_iso(),
        "event_id": f"01HXYZCANC0000000000000{wp_id}",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": MISSION_SLUG,
        "force": False,
        "from_lane": "in_progress",
        "reason": _OPERATOR_CANCEL_NOTE,
        "reason_source": "operator",
        "review_ref": None,
        "to_lane": "canceled",
        "wp_id": wp_id,
    }


def _bootstrap_coord_mission(repo: Path) -> Path:
    """Bootstrap the #2945 coord-topology mission.

    lane-a is MIXED: ``WP01`` approved (survivor, its lane branch exists) and
    ``WP02`` canceled-with-provenance. lane-b is FULLY canceled: ``WP03``
    canceled-with-provenance and its lane branch is deliberately NEVER created
    (the #2945 shape — a canceled WP whose lane never got a branch).

    Returns the primary-checkout feature_dir.
    """
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    _write_meta(feature_dir)
    _write_manifest(feature_dir)
    for wp_id in (WP_SURVIVOR, WP_CANCELED_MIXED, WP_CANCELED_LANE):
        _write_wp_file(feature_dir, wp_id)

    # Pre-record the per-WP state the merge reads: the survivor at ``approved``
    # (so the real bookkeeping emits a genuine ``approved -> done``) and the two
    # canceled WPs at ``canceled`` with operator provenance.
    events = [
        _approved_event(WP_SURVIVOR),
        _canceled_operator_event(WP_CANCELED_MIXED),
        _canceled_operator_event(WP_CANCELED_LANE),
    ]
    (feature_dir / "status.events.jsonl").write_text(
        "".join(json.dumps(e, sort_keys=True) + "\n" for e in events),
        encoding="utf-8",
    )

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({MISSION_SLUG}): bootstrap coord mission")

    # Coordination/mission branch at the current tip.
    _git(repo, "branch", COORD_BRANCH)

    # MIXED lane branch with a REAL survivor diff not on the mission branch nor
    # main. The FULLY-canceled lane-b branch is intentionally NOT created.
    lane_branch = f"kitty/mission-{MISSION_SLUG}-{LANE_MIXED}"
    _git(repo, "branch", lane_branch, COORD_BRANCH)
    _git(repo, "checkout", lane_branch)
    code_path = repo / SURVIVOR_CODE
    code_path.parent.mkdir(parents=True, exist_ok=True)
    code_path.write_text("def survivor() -> int:\n    return 2945\n", encoding="utf-8")
    _git(repo, "add", SURVIVOR_CODE)
    _git(repo, "commit", "-m", f"feat({MISSION_SLUG}): survivor code for {WP_SURVIVOR}")
    _git(repo, "checkout", "main")

    # Materialize the coordination worktree with the mission branch CHECKED OUT
    # (production topology): the real per-WP ``done`` transaction commits through
    # this worktree.
    CoordinationWorkspace.resolve(repo, MISSION_SLUG, MID8)

    return feature_dir


@contextlib.contextmanager
def _merge_external_mocks() -> Iterator[dict[str, MagicMock]]:
    """Mock side effects OUTSIDE git/status bookkeeping.

    Deliberately LEFT REAL (the #2945 seam under test): the lane-skip decision in
    ``_phase_merge_lanes``, the ``all_wp_ids`` filter, and the whole
    done-bookkeeping trio (``_record_merged_wps_done_for_merge`` /
    ``_mark_wp_merged_done`` / ``_assert_merged_wps_reached_done``). The real
    ``consolidate_lane_into_mission`` / ``integrate_mission_into_target`` run real
    ``git merge`` so the survivor genuinely lands on the target branch.
    """
    patches = {
        "run_check": patch("specify_cli.merge.executor.run_check"),
        "sparse": patch("specify_cli.merge.executor.require_no_sparse_checkout"),
        "preflight": patch("specify_cli.cli.commands.merge._enforce_git_preflight"),
        "review_consistency": patch("specify_cli.merge.executor._enforce_review_artifact_consistency"),
        "status_history": patch("specify_cli.merge.executor._enforce_canonical_status_history"),
        "hollow": patch("specify_cli.merge.executor._warn_or_confirm_hollow_reviews"),
        "bake": patch(
            "specify_cli.merge.executor._bake_mission_number_into_mission_branch",
            return_value=None,
        ),
        "baseline_record": patch(
            "specify_cli.merge.executor._record_baseline_merge_commit",
            return_value=None,
        ),
        "baseline_assert": patch("specify_cli.merge.executor._assert_baseline_merge_commit_on_target"),
        "done_on_target": patch("specify_cli.merge.executor._assert_merged_wps_done_on_target"),
        "safe_commit": patch("specify_cli.merge.executor.commit_merge_bookkeeping"),
        "refresh_primary": patch("specify_cli.merge.executor._refresh_primary_checkout_after_merge"),
        "porcelain": patch(
            "specify_cli.merge.executor._classify_porcelain_lines",
            return_value=([], 0),
        ),
        "gates": patch("specify_cli.policy.merge_gates.evaluate_merge_gates"),
        "policy": patch("specify_cli.policy.config.load_policy_config"),
        "remote": patch("specify_cli.merge.executor.has_remote", return_value=False),
    }
    with contextlib.ExitStack() as stack:
        mocks = {name: stack.enter_context(p) for name, p in patches.items()}
        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        mocks["gates"].return_value = gate_eval
        policy = MagicMock()
        policy.merge_gates = []
        mocks["policy"].return_value = policy
        stale_report = MagicMock()
        stale_report.findings = []
        mocks["run_check"].return_value = stale_report
        yield mocks


def _committed_coord_events(repo: Path, feature_dir: Path) -> list[StatusEvent]:
    """Reduce the events COMMITTED to the coordination branch (contract-routed)."""
    return cast(
        "list[StatusEvent]",
        read_event_log(
            EventLogReadContract.coordination_branch_ref(
                repo_root=repo,
                destination_ref=COORD_BRANCH,
                feature_dir=feature_dir,
                parser_feature_dir=feature_dir,
            )
        ),
    )


# ---------------------------------------------------------------------------
# SC-001 — the merge excludes canceled WPs and lands the survivor (real git)
# ---------------------------------------------------------------------------


def test_merge_excludes_canceled_wps_and_lands_survivor(tmp_path: Path) -> None:
    """#2945 / FR-004 / FR-009 / SC-001: a mission with a canceled WP in a mixed
    lane and a fully-canceled lane merges — the survivor lands on the target, the
    canceled WPs are excluded from the done/review derivations (never driven
    ``canceled -> done``), their audit records are retained, and the branchless
    fully-canceled lane is skipped."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    feature_dir = _bootstrap_coord_mission(repo)

    # --- Preconditions (fixture health, asserted BEFORE the act). ---
    assert not _file_on_branch(repo, "main", SURVIVOR_CODE), "precondition: survivor code must NOT be on main before the merge"
    assert not _branch_exists(repo, f"kitty/mission-{MISSION_SLUG}-{LANE_ALL_CANCELED}"), (
        "precondition: the fully-canceled lane-b branch must NOT exist (the #2945 "
        "shape — a canceled WP whose lane never got a branch); the merge must not "
        "attempt to integrate it"
    )

    with _merge_external_mocks():
        _run_lane_based_merge(
            repo_root=repo,
            mission_slug=MISSION_SLUG,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            allow_sparse_checkout=True,
        )

    # --- Survivor integration (SC-001): the mixed lane still integrated its
    # surviving approved WP even though it also held a canceled WP. ---
    assert _file_on_branch(repo, "main", SURVIVOR_CODE), (
        "#2945 regression: the surviving approved WP's code did not reach the target branch — a canceled WP in the same lane must not drop the survivor."
    )

    committed = _committed_coord_events(repo, feature_dir)

    # --- The survivor reached ``done``; NEITHER canceled WP was driven
    # ``canceled -> done`` (the honest-ending record is intact). ---
    assert wp_lane_actor_from_events(committed, WP_SURVIVOR).lane == Lane.DONE, "the surviving approved WP must reach done in the committed coordination log"
    for canceled_wp in (WP_CANCELED_MIXED, WP_CANCELED_LANE):
        done_events = [e for e in committed if e.wp_id == canceled_wp and str(e.to_lane) == "done"]
        assert not done_events, (
            f"#2945 regression: {canceled_wp} was driven through an invalid "
            "``canceled -> done`` transition — the done-bookkeeping per-lane loop "
            "did not exclude the canceled WP, corrupting the honest-ending record."
        )
        assert wp_lane_actor_from_events(committed, canceled_wp).lane == Lane.CANCELED, f"{canceled_wp} must remain canceled after the merge"

    # --- The cancellation audit records are RETAINED (not rewritten away). ---
    for canceled_wp in (WP_CANCELED_MIXED, WP_CANCELED_LANE):
        canceled_events = [e for e in committed if e.wp_id == canceled_wp and str(e.to_lane) == "canceled"]
        assert canceled_events, (
            f"#2945 regression: the cancellation audit record for {canceled_wp} was lost — the merge must retain it, not erase the honest ending."
        )

    # --- The fully-canceled lane-b was skipped: its branch never existed, so a
    # completed merge is itself proof the all-canceled lane-skip guard fired
    # (otherwise ``consolidate_lane_into_mission`` would have exited on the
    # missing branch). Its would-be code never reached the target. ---
    assert not _file_on_branch(repo, "main", "src/never_built.py"), "the fully-canceled lane must not integrate any code onto the target"


# ---------------------------------------------------------------------------
# FR-009 merge face — the dependency gate does not strand a survivor whose
# dependency is a canceled-with-provenance WP (real ``evaluate_merge_gates``).
# ---------------------------------------------------------------------------


def _seed_flat_mission_with_canceled_dep(tmp_path: Path, *, reason_source: str) -> tuple[Path, Path]:
    """Flat mission: ``WP02`` (approved survivor) depends on ``WP01`` (canceled).

    ``WP01``'s cancellation provenance is set by *reason_source* so the caller can
    contrast operator-authored (acceptable → gate PASS) against synthetic
    (not acceptable → gate FAIL). Returns ``(repo, feature_dir)``.
    """
    slug = "flat-canceled-dep-01M2945F"
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", "main", str(repo)])
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir(exist_ok=True)

    feature_dir = repo / "kitty-specs" / slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01M2945F0000000000000000FL",
                "mission_slug": slug,
                "slug": slug,
                "mission_type": "software-dev",
                "target_branch": "main",
                "vcs": "git",
                "topology": "single_branch",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (tasks_dir / "WP01.md").write_text(
        "---\nwork_package_id: WP01\ntitle: WP01 canceled dep\ndependencies: []\nsubtasks: []\n---\n# WP01\n",
        encoding="utf-8",
    )
    (tasks_dir / "WP02.md").write_text(
        "---\nwork_package_id: WP02\ntitle: WP02 survivor\ndependencies:\n- WP01\nsubtasks: []\n---\n# WP02\n",
        encoding="utf-8",
    )

    events = [
        {
            "event_id": "evt-WP01-canceled",
            "mission_slug": slug,
            "wp_id": "WP01",
            "from_lane": "in_progress",
            "to_lane": "canceled",
            "at": "2026-08-01T00:00:00+00:00",
            "actor": "operator",
            "force": False,
            "execution_mode": "worktree",
            "reason": _OPERATOR_CANCEL_NOTE,
            "reason_source": reason_source,
        },
        {
            "event_id": "evt-WP02-approved",
            "mission_slug": slug,
            "wp_id": "WP02",
            "from_lane": "in_review",
            "to_lane": "approved",
            "at": "2026-08-01T00:01:00+00:00",
            "actor": "reviewer",
            "force": False,
            "execution_mode": "worktree",
        },
    ]
    (feature_dir / "status.events.jsonl").write_text(
        "".join(json.dumps(e, sort_keys=True) + "\n" for e in events),
        encoding="utf-8",
    )

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "bootstrap flat mission")
    return repo, feature_dir


def _gate(evaluation, name: str):  # noqa: ANN001, ANN202
    return next(g for g in evaluation.gates if g.gate_name == name)


def test_merge_gates_do_not_strand_survivor_on_canceled_provenance_dep(
    tmp_path: Path,
) -> None:
    """#2945 / FR-009: a survivor depending on a canceled-WITH-provenance WP is
    NOT stranded by the merge dependency/evidence gates — routed through
    ``is_acceptable_ending``, an operator-authored cancellation counts as an
    acceptable ending, so the gates PASS."""
    repo, feature_dir = _seed_flat_mission_with_canceled_dep(tmp_path, reason_source="operator")

    evaluation = evaluate_merge_gates(
        feature_dir,
        feature_dir.name,
        ["WP02"],
        MergeGateConfig(mode="block"),
        repo,
    )

    assert _gate(evaluation, "dependency").verdict == GateVerdict.PASS, (
        "#2945 regression: the merge dependency gate stranded a surviving WP whose only dependency is a canceled-with-provenance (acceptable-ending) WP."
    )
    assert _gate(evaluation, "evidence").verdict == GateVerdict.PASS, "the evidence gate must accept the surviving WP (it is approved)"


def test_merge_dependency_gate_still_fails_on_synthetic_canceled_dep(
    tmp_path: Path,
) -> None:
    """Falsifiability: a SYNTHETIC (non-provenance) cancellation is NOT an
    acceptable ending, so a dependency on it still FAILS the merge dependency
    gate — the routing honors provenance, it does not blanket-accept ``canceled``."""
    repo, feature_dir = _seed_flat_mission_with_canceled_dep(tmp_path, reason_source="synthetic")

    evaluation = evaluate_merge_gates(
        feature_dir,
        feature_dir.name,
        ["WP02"],
        MergeGateConfig(mode="block"),
        repo,
    )

    dependency = _gate(evaluation, "dependency")
    assert dependency.verdict == GateVerdict.FAIL, (
        "a synthetic (non-provenance) canceled dependency must still FAIL the merge dependency gate — canceled-without-provenance is not an acceptable ending."
    )
    assert "WP01" in dependency.details
