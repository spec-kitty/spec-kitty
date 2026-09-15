"""WP15 (T067-T069, FR-015): the review-verdict durability coverage matrix.

FR-015 / US1 Acceptance Scenario 9: for the matrix of **verdict x target lane x
topology x auto-commit**, durability must behave as that cell specifies. Every
automatic positive cell uses a real governed-ref commit and exact byte
read-back. Removing that commit turns the cell into a typed, nonzero refusal;
protected automatic cells likewise fail closed before event emission, while
explicit ``--no-auto-commit`` cells remain intentional local-only outcomes.

**Matrix shape (T067) -- 12 cells, documented so a future dimension addition
is visible as a count change:**

FR-015 names four axes literally. Two of them (verdict, target lane) are not
independent in production: a WP is never simultaneously "rejected" and
"done" -- the real writer produces exactly three non-redundant (verdict,
lane) pairings (:data:`_SCENARIOS`), not the 3x3 = 9 combinations a bare
cross-product would suggest. Excluding the six nonsensical pairings is not
"a subset chosen for convenience" (the WP's own caution) -- it is excluding
combinations the production writer cannot produce. The fourth verdict named
by the mission (an **arbiter override**) is handled in its OWN, separate,
smaller matrix (see "Arbiter override" section below) because WP12 retired
its durability mechanism onto the event-sourced ``commit_status`` seam, not
the ``commit_artifact`` seam every other cell here exercises -- folding it
into the same 12-cell parametrization would silently paper over that
structural difference (exactly the "assertion-specificity" risk the WP
prompt names).

    3 scenarios x 2 topologies x 2 auto-commit settings = 12 cells

* **Scenarios** (:data:`_SCENARIOS`): ``rejected_planned`` (the rollback
  writer), ``approved_approved``, ``approved_done`` (the ordinary approval
  writer, target lane APPROVED or DONE).
* **Topology** (:data:`_TOPOLOGIES`): ``single_branch`` (``skip_target_branch_
  commit=False``) vs ``coord_protected`` (``skip_target_branch_commit=True``,
  the protected-primary-under-coordination-topology shape T050 introduced). Be
  precise about what this axis actually is: **every one of these 12 cells runs
  against a plain, non-coord, single-branch git repo** (``_seed_fixture``'s
  ``_init_repo``); ``"topology"`` here is a directly-patched
  ``_skip_target_branch_commit`` boolean, not a real coord worktree. It
  legitimately proves the ONE topology-mediated behaviour a ``FakeCoordCommit
  Router`` cell can observe at all -- the skip-gate
  (``_resolve_verdict_commit_router``'s own docstring: "a protected-primary-
  coord topology is a SECOND, structurally different cause") -- but it does
  NOT exercise WP04's OTHER topology effect: which git REF the commit lands on
  (PRIMARY vs COORD). That effect needed a genuinely separate, real coord
  worktree, added below as its own section ("T069c -- the real coord-topology
  cell") built on ``tests/integration/coord_topology_fixture.py``'s
  ``_build_coord_topology`` -- not folded into this 12-cell parametrization,
  and not skipped.
* **Auto-commit**: ``True`` / ``False`` (``--no-auto-commit``, FR-013).

**T068 -- the non-vacuity proof.** :func:`test_matrix_is_sensitive_to_commit_
removal` re-drives the 3 cells where a commit is actually attempted
(``auto_commit=True`` AND ``single_branch``) with ``commit_artifact``
monkeypatched to the documented no-op (``CommitArtifactResult(status=
"unchanged", ...)``) and asserts each one now raises. The other 9 cells
(``auto_commit=False``, or ``coord_protected``) never call ``commit_artifact``
at all by design (T050's skip gate fires BEFORE the call). Explicit local-only
cells return normally; protected automatic cells return the exact fail-closed
``persistence_failed/protected_target_branch`` envelope. The dedicated
insulation test pins both outcomes and proves neither emits a verdict event.

**T069a/b -- real router, real git (single_branch), and the SIGKILL cell.**
:func:`test_real_router_commit_lands_on_disk_and_git_history` and
:func:`test_real_router_cell_reds_when_commit_artifact_is_neutered` drive the
REAL ``RealCoordCommitRouter``/``commit_for_mission`` against a real,
git-initialised repo (reusing ``test_move_task_durability.py``'s established
``_FaultInjectableCoordRouter`` fixture rather than duplicating a second real-
git harness) -- like the 12-cell matrix above, this pair is a SINGLE_BRANCH
repo (``_init_repo``), not a coord worktree; it proves the commit is genuinely
real and mutation-sensitive, not that topology is exercised.
:func:`test_sigkill_between_write_and_commit_then_identical_retry_exits_zero`
is the dedicated SC-003 SIGKILL cell (also single_branch): a child OS process
performs ONLY ``_allocate_and_write_review_cycle_locked`` (the write+validate
half -- there is no commit call reachable in the killed function at all, so
the kill window is unambiguous), signals write-complete readiness via a file,
then hangs; the parent SIGKILLs it in that window and re-drives the identical
write from the PARENT process, asserting the retry adopts the exact retained
record, creates no duplicate, and commits those bytes at ``HEAD``. A distinct
retry is separately required to allocate a new cycle. This is scoped to the SPEC's own
named window ("killed between the write and the commit") -- a mid-write kill
is a different, filesystem-dependent hazard this test deliberately does not
simulate (matching WP10's T044 scope note).

**T069c -- the real coord-topology cell (the genuine topology coverage).**
:func:`test_real_coord_topology_review_cycle_commits_to_coord_ref_not_primary`,
:func:`test_real_coord_topology_cell_reds_when_commit_artifact_is_neutered`,
and :func:`test_real_coord_topology_revert_deletes_and_commits_on_coord_ref`
are built on the canonical ``tests/integration/coord_topology_fixture.py``
(``_build_coord_topology``) -- a REAL coord worktree via
``CoordinationWorkspace.resolve``, not a patched flag. They assert on
committed git trees (``git show <ref>:<path>``) that a review-cycle write
lands on the COORD ref and is absent on primary, that this is genuinely
mutation-sensitive, and -- the actual durability-matrix witness for WP13's
fix (DM-01KZ75GBNXC73Q38M43GBH38W7) -- that a transition-emit failure AFTER
a coord-topology write already landed is reverted on the SAME coord ref, not
primary (the live bug WP13's ``_resolve_revert_commit_worktree`` +
``kind=REVIEW_CYCLE`` fix closed; WP11's own tests never caught it because
they exercised only a single_branch fixture). No product defect surfaced
beyond what WP13 already fixed.

**SC-004 -- production-path durability oracle (issue #3235).**
:func:`test_sc004_two_concurrent_processes_never_clobber_a_verdict_over_50_
iterations` now keeps two portable ``spawn`` workers alive for fifty synchronized
rounds and drives the literal Typer ``tasks move-task`` command.  A success is
accepted only after independently resolving its exact returned event id and
``git show``-reading its distinct review-cycle evidence from the placement seam's
governed ref.  The deterministic wait-in-line case holds writer A at the real
commit seam, proves writer B has not entered it, then requires B to complete
after A releases within ten seconds.

The two named mutation controls are independent: one disables the actual
fallback and coordination-transaction lock bindings and orders two stale
``status.events.jsonl`` replacements; the other fabricates a committed evidence
result without touching Git.  They require the exact classifications
``missing_authoritative_event`` and ``missing_committed_evidence`` respectively.
The pre-existing direct writer/manual append probe was removed because it
bypassed the command whose durability is under test.
"""

from __future__ import annotations

import json
import multiprocessing
import os
import subprocess
import sys
import time
from collections.abc import Iterator, Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from queue import Empty
from typing import Any
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.agent_tasks_ports import (
    CommitArtifactResult,
    CoordCommitRouter,
    RealCoordCommitRouter,
    TasksPorts,
)
from specify_cli.cli.commands.agent import app as agent_app
from specify_cli.cli.commands.agent.tasks import _do_move_task, _MoveTaskArgs
from specify_cli.review.artifacts import ReviewCycleArtifact
from specify_cli.review.cycle import (
    _allocate_and_write_review_cycle_locked,
    _review_cycle_wp_dir,
    create_rejected_review_cycle,
)
from specify_cli.status import materialize as _materialize
from specify_cli.status.models import Lane, ReviewResult, StatusEvent
from specify_cli.status.store import append_event, read_events
from specify_cli.status.transitions import validate_transition
from tests.integration.coord_topology_fixture import (
    CoordTopologyContext,
    _build_coord_topology,
)
from tests.mocked_env import setup_mocked_env
from tests.specify_cli.cli.commands.agent.test_move_task_durability import (
    _FaultInjectableCoordRouter,
    _build_wp_file,
    _git_head_has_file,
    _git_status,
    _init_repo,
    _seed_wp_event,
    _unprotect_main,
)
from tests.specify_cli.cli.commands.agent.test_tasks_ports import (
    FakeCoordCommitRouter,
    FakeFsReader,
    FakeGitOps,
    FakeRender,
)

# Architectural convention (test_pytest_marker_convention.py): every test_*.py
# file must declare a module-level marker. Per-test ``@pytest.mark.fast`` /
# ``@pytest.mark.integration`` / ``@pytest.mark.git_repo`` decorators below
# refine individual tests further; this module-level mark satisfies the
# file-level presence check and reflects the file's home (real command
# surface + real git, not pure unit logic).
#
# PR #3211 landing pass (2026-08-05, F6): ``git_repo`` added at module level --
# EVERY cell (including the ``@pytest.mark.fast``-decorated ones above)
# transitively drives a real ``git init``/``git add``/``git commit`` via
# ``_seed_fixture`` -> ``_init_repo`` (see that helper's own docstring: the
# production writer's ``feature_status_lock`` is keyed under the real git
# common dir, so there is no way to exercise it against a non-git
# ``tmp_path``). ``test_pytest_marker_correctness.py``'s Rule 1 requires the
# marker at file scope whenever the file invokes git via subprocess anywhere,
# which this file does.
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# ---------------------------------------------------------------------------
# Shared constants (Sonar S1192: every repeated literal below is named once)
# ---------------------------------------------------------------------------

_MISSION = "durability-matrix"
_WP_ID = "WP01"
_WP_SLUG = f"{_WP_ID}-test"
_REASON_NO_AUTO_COMMIT = "no_auto_commit"
_REASON_PROTECTED_TARGET_BRANCH = "protected_target_branch"
_REVIEW_GATE_BYPASS: dict[str, Any] = {
    "_validate_ready_for_review": (True, []),
    "_check_unchecked_subtasks": [],
}
_SEED_FEEDBACK_BODY = "Needs another pass before the matrix drives it.\n"


@dataclass(frozen=True)
class _Scenario:
    """One non-redundant (verdict, target_lane) pairing the real writer produces."""

    scenario_id: str
    verdict: str
    target_lane: str


_SCENARIOS: tuple[_Scenario, ...] = (
    _Scenario("rejected_planned", "rejected", "planned"),
    _Scenario("approved_approved", "approved", "approved"),
    _Scenario("approved_done", "approved", "done"),
)
_TOPOLOGIES: tuple[str, ...] = ("single_branch", "coord_protected")
_AUTO_COMMIT_SETTINGS: tuple[bool, ...] = (True, False)

_MatrixCell = tuple[_Scenario, str, bool]

_MATRIX_CELLS: tuple[_MatrixCell, ...] = tuple(
    (scenario, topology, auto_commit)
    for scenario in _SCENARIOS
    for topology in _TOPOLOGIES
    for auto_commit in _AUTO_COMMIT_SETTINGS
)
# Pinned per the T067 validation checklist: the count is the DOCUMENTED
# product of the dimension sizes above, so an added scenario/topology/
# auto-commit value changes this number visibly rather than silently.
assert len(_MATRIX_CELLS) == 3 * 2 * 2 == 12

_DURABLE_CELLS: tuple[_MatrixCell, ...] = tuple(
    cell for cell in _MATRIX_CELLS if cell[1] == "single_branch" and cell[2] is True
)
assert len(_DURABLE_CELLS) == 3

_INSULATED_CELLS: tuple[_MatrixCell, ...] = tuple(
    cell for cell in _MATRIX_CELLS if cell not in _DURABLE_CELLS
)
assert len(_INSULATED_CELLS) == 9


def _cell_id(cell: _MatrixCell) -> str:
    scenario, topology, auto_commit = cell
    ac = "auto_commit" if auto_commit else "no_auto_commit"
    return f"{scenario.scenario_id}-{topology}-{ac}"


# ---------------------------------------------------------------------------
# Shared fixture + driver helpers
# ---------------------------------------------------------------------------


def _seed_fixture(
    repo: Path,
    mission: str,
    wp_id: str,
    *,
    old_lane: str,
    seed_rejected_cycle: bool,
) -> Path:
    """Real git repo + WP + status-event seed shared by every matrix cell.

    EVERY cell needs a real ``git init`` regardless of Fake/Real router: the
    production writer (``_allocate_and_write_review_cycle_locked``) always
    acquires ``feature_status_lock``, an inter-process ``FileLock`` keyed
    under the real git common dir (``status/locking.py``) -- there is no way
    to exercise that seam against a non-git ``tmp_path``. This matches the
    house pattern already established in ``test_move_task_durability.py``
    (whose helpers this module reuses below rather than duplicating).
    """
    _init_repo(repo)
    feature_dir, _wp_file = _build_wp_file(repo, mission, wp_id)
    _write_lanes_json(feature_dir, mission, wp_id)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True
    )
    _unprotect_main(repo)
    if seed_rejected_cycle:
        created = create_rejected_review_cycle(
            main_repo_root=repo,
            mission_slug=mission,
            wp_id=wp_id,
            wp_slug=f"{wp_id}-test",
            body=_SEED_FEEDBACK_BODY,
            reviewer_agent="reviewer-matrix",
            verdict="rejected",
            commit_router=None,  # uncommitted seed -- the production "prior rejection" shape
        )
        # WP05 (verdict-seam-write-unification-01KZ9Q35, T023): the writer's
        # own "is the current verdict a rejection" probe
        # (``_persist_approved_review_cycle``) is now event-sourced -- seed
        # the SAME ``review_result`` the real writer produces as a durable
        # event, not just the on-disk artifact above. Appended BEFORE the
        # ``old_lane`` seed event below (never after): ``_mt_current_event_
        # lane`` picks the LAST event IN FILE ORDER for wp_id as "current" --
        # this must stay the historical rejection's PREDECESSOR, not its
        # successor, or production code reads the WP's current lane as
        # ``in_progress`` (this event's own to_lane) instead of ``old_lane``.
        append_event(
            feature_dir,
            StatusEvent(
                event_id=f"test-{wp_id}-seed-rejection-event",
                mission_slug=mission,
                wp_id=wp_id,
                from_lane=Lane.IN_REVIEW,
                to_lane=Lane.IN_PROGRESS,
                at="2025-12-31T00:00:00+00:00",
                actor="reviewer-matrix",
                force=False,
                execution_mode="worktree",
                review_result=created.review_result,
            ),
        )
    _seed_wp_event(feature_dir, wp_id, old_lane, seq=0)
    return feature_dir


#: ``_build_wp_file`` (imported from ``test_move_task_durability.py``) always
#: seeds this fixed mission_id into ``meta.json`` -- reused here so
#: ``lanes.json`` names the SAME identity, matching the production shape
#: ``mission_finalize`` would have written.
_FIXTURE_MISSION_ID = "01HQZZZZZZZZZZZZZZZZZZZZZZ"


def _write_lanes_json(feature_dir: Path, mission: str, wp_id: str) -> None:
    """Minimal, schema-valid ``lanes.json`` (mirrors ``coord_topology_
    fixture._write_lanes_json``'s shape) -- required for the ``done`` target
    lane: ``_mt_done_ancestry_facts`` calls ``resolve_workspace_for_wp``,
    which raises the (uncaught-by-design) ``MissingLanesError`` when no
    ``lanes.json`` exists at all (distinct from the caught ``FileNotFoundError``
    a present-but-nonexistent-worktree resolution raises)."""
    payload = {
        "version": 1,
        "mission_slug": mission,
        "mission_id": _FIXTURE_MISSION_ID,
        "mission_branch": f"kitty/mission-{mission}",
        "target_branch": "main",
        "lanes": [
            {
                "lane_id": "lane-a",
                "wp_ids": [wp_id],
                "write_scope": [],
                "predicted_surfaces": [],
                "depends_on_lanes": [],
                "parallel_group": 0,
            }
        ],
        "computed_at": "2026-01-01T00:00:00+00:00",
        "computed_from": "durability-matrix-fixture",
        "planning_artifact_wps": [],
    }
    (feature_dir / "lanes.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _wp_dir(repo: Path, mission: str, wp_id: str) -> Path:
    return repo / "kitty-specs" / mission / "tasks" / f"{wp_id}-test"


def _assert_body_matches_scenario_verdict(body: str, verdict: str, *, cell: str) -> None:
    """Assert *body* is shaped the way the write path for *verdict* produces
    it (WP06 successor for a removed ``.verdict`` check -- see callers'
    comments for why neither the artifact field nor an event-sourced read is
    available at these particular call sites). ``"approved"`` bodies always
    start with ``"Approved by "`` (:func:`_persist_approved_review_cycle`'s
    own synthesized body); a rejection's body is real reviewer prose and
    never starts that way.
    """
    if verdict == "approved":
        assert body.startswith("Approved by "), (
            f"cell {cell}: expected an 'Approved by ...' body for verdict={verdict!r}, "
            f"got: {body!r}"
        )
    else:
        assert not body.startswith("Approved by "), (
            f"cell {cell}: expected reviewer-prose body for verdict={verdict!r}, "
            f"got an approval-shaped body: {body!r}"
        )


def _assert_committed_frontmatter_has_no_verdict_key(frontmatter_and_body: str) -> None:
    """SC-007 (WP06, FR-003): the REAL committed ``.md`` blob carries no
    ``verdict:`` frontmatter key. Several sites in this file used to assert
    the OPPOSITE (``"verdict: approved"``/``"verdict: rejected"`` present in
    the committed blob) as circumstantial evidence the write landed with the
    expected content -- that assertion is now categorically wrong (the field
    no longer exists), so every one of those sites now asserts its structural
    absence instead, on the SAME real committed git blob."""
    frontmatter = frontmatter_and_body.split("---", 2)[1]
    keys = {
        line.split(":", 1)[0].strip()
        for line in frontmatter.splitlines()
        if line and not line.startswith((" ", "\t", "-"))
    }
    assert "verdict" not in keys, (
        f"committed review-cycle blob must carry no verdict key, found keys "
        f"{sorted(keys)} in:\n{frontmatter_and_body}"
    )


def _run_cell(
    repo: Path,
    *,
    mission: str,
    wp_id: str,
    to: str,
    router: CoordCommitRouter,
    auto_commit: bool,
    skip_target_branch_commit: bool,
    review_feedback_file: Path | None = None,
    note: str | None = None,
    done_override_reason: str | None = None,
    force: bool = False,
) -> None:
    """Drive the REAL ``_do_move_task`` orchestrator (the same entry point
    ``test_move_task_approval_body_collision.py`` and ``test_move_task_
    durability.py`` already establish as the house "real command surface"
    drive), never a hand-assembled call to an internal writer directly.
    """
    ports = TasksPorts(
        fs=FakeFsReader(default_planning_dir=repo / "kitty-specs" / mission),
        coord=router,
        git=FakeGitOps(),
        render=FakeRender(),
    )
    extra_patches = dict(_REVIEW_GATE_BYPASS)
    extra_patches["_skip_target_branch_commit"] = skip_target_branch_commit
    with setup_mocked_env(
        repo,
        mission_slug=mission,
        target_branch="main",
        extra_patches=extra_patches,
    ):
        _do_move_task(
            _MoveTaskArgs(
                task_id=wp_id,
                to=to,
                mission=mission,
                agent=None,
                assignee=None,
                shell_pid=None,
                note=note,
                review_feedback_file=review_feedback_file,
                approval_ref=None,
                reviewer=None,
                self_review_fallback=False,
                intended_reviewer=None,
                reviewer_failure_reason=None,
                done_override_reason=done_override_reason,
                force=force,
                tracker_ref=None,
                skip_review_artifact_check=False,
                auto_commit=auto_commit,
                json_output=True,
            ),
            ports=ports,
        )


def _last_json_payload(capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    out = capsys.readouterr().out.strip()
    last_line = out.splitlines()[-1]
    payload: dict[str, Any] = json.loads(last_line)
    return payload


def _assert_persistence_failure(
    payload: dict[str, Any],
    *,
    reason: str,
    destination_ref: str | None,
) -> str:
    """Pin the fail-closed verdict envelope and return its retained path."""
    assert payload.get("result") == "error", payload
    assert payload.get("verdict_durably_persisted") is False, payload
    assert payload.get("durability_classification") == "persistence_failed", payload
    assert payload.get("durability_reason") == reason, payload
    assert payload.get("destination_ref") == destination_ref, payload
    evidence_ref = payload.get("evidence_ref")
    assert isinstance(evidence_ref, str) and evidence_ref.endswith(".md"), payload
    return evidence_ref


def _assert_no_new_status_event(feature_dir: Path, before_ids: set[str]) -> None:
    """A failed verdict save must stop before authoritative event emission."""
    after_ids = {event.event_id for event in read_events(feature_dir)}
    assert after_ids == before_ids, (
        "a persistence failure emitted a status event: "
        f"before={sorted(before_ids)}, after={sorted(after_ids)}"
    )


def _assert_exact_blob_at_ref(repo: Path, ref: str, evidence_ref: str) -> None:
    """Require the governed Git blob to equal the retained local evidence."""
    local_path = repo / evidence_ref
    shown = subprocess.run(
        ["git", "show", f"{ref}:{evidence_ref}"],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    assert shown.returncode == 0, shown.stderr.decode(errors="replace")
    assert local_path.read_bytes() == shown.stdout


def _drive_scenario(
    repo: Path,
    *,
    mission: str,
    wp_id: str,
    scenario: _Scenario,
    router: CoordCommitRouter,
    auto_commit: bool,
    skip_target_branch_commit: bool,
) -> None:
    """Build the scenario-specific ``_run_cell`` call (the feedback file for a
    rollback, the done-override-reason for a DONE target)."""
    if scenario.target_lane == "planned":
        feedback = repo / "feedback.md"
        feedback.write_text(
            "**Issue**: the matrix's rejection feedback.\n", encoding="utf-8"
        )
        _run_cell(
            repo,
            mission=mission,
            wp_id=wp_id,
            to="planned",
            router=router,
            auto_commit=auto_commit,
            skip_target_branch_commit=skip_target_branch_commit,
            review_feedback_file=feedback,
        )
        return
    done_override = (
        "matrix cell: bypass merge-ancestry check" if scenario.target_lane == "done" else None
    )
    # ``_guard_unsupported_skip_metadata`` refuses a coord-protected commit
    # that ALSO carries a ``note`` (frontmatter activity-log write, which the
    # skip arm cannot land) -- omit it under that topology and rely on
    # ``_mt_approval_facts``'s own ``auto-approval:<wp>:<date>`` default
    # reference instead of reproducing that guard's refusal here.
    note = None if skip_target_branch_commit else "Review passed"
    _run_cell(
        repo,
        mission=mission,
        wp_id=wp_id,
        to=scenario.target_lane,
        router=router,
        auto_commit=auto_commit,
        skip_target_branch_commit=skip_target_branch_commit,
        note=note,
        done_override_reason=done_override,
    )


# ---------------------------------------------------------------------------
# T067 -- the 12-cell matrix through the real command surface
# ---------------------------------------------------------------------------


@pytest.mark.fast
@pytest.mark.parametrize("cell", _MATRIX_CELLS, ids=[_cell_id(c) for c in _MATRIX_CELLS])
def test_durability_matrix_cell(
    tmp_path: Path, cell: _MatrixCell, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every one of the 12 documented cells: durability behaves as specified,
    and every assertion is specific to what THAT cell's own dimensions imply
    (never a shared "no exception raised" catch-all)."""
    scenario, topology, auto_commit = cell
    repo = tmp_path
    seed_rejected = scenario.verdict == "approved"
    feature_dir = _seed_fixture(
        repo, _MISSION, _WP_ID, old_lane="in_review", seed_rejected_cycle=seed_rejected
    )
    wp_dir = _wp_dir(repo, _MISSION, _WP_ID)
    skip_target_branch_commit = topology == "coord_protected"
    expected_durable = auto_commit and not skip_target_branch_commit
    router: CoordCommitRouter = (
        _FaultInjectableCoordRouter(write_dir=feature_dir)
        if expected_durable
        else FakeCoordCommitRouter(write_dir=feature_dir)
    )
    event_ids_before = {event.event_id for event in read_events(feature_dir)}

    if auto_commit and skip_target_branch_commit:
        with pytest.raises(typer.Exit) as exc_info:
            _drive_scenario(
                repo,
                mission=_MISSION,
                wp_id=_WP_ID,
                scenario=scenario,
                router=router,
                auto_commit=auto_commit,
                skip_target_branch_commit=skip_target_branch_commit,
            )
        assert exc_info.value.exit_code == 1
        payload = _last_json_payload(capsys)
        evidence_ref = _assert_persistence_failure(
            payload,
            reason=_REASON_PROTECTED_TARGET_BRANCH,
            destination_ref=None,
        )
        assert (repo / evidence_ref).is_file(), payload
        _assert_no_new_status_event(feature_dir, event_ids_before)
        assert isinstance(router, FakeCoordCommitRouter)
        assert router.artifact_calls == [], "protected routing must fail before commit"
        assert router.status_calls == [], "protected routing must fail before event emission"
        return

    _drive_scenario(
        repo,
        mission=_MISSION,
        wp_id=_WP_ID,
        scenario=scenario,
        router=router,
        auto_commit=auto_commit,
        skip_target_branch_commit=skip_target_branch_commit,
    )

    payload = _last_json_payload(capsys)
    assert payload["verdict_durably_persisted"] is expected_durable, payload
    if expected_durable:
        assert "verdict_durability_skip_reason" not in payload, payload
    else:
        expected_reason = (
            _REASON_NO_AUTO_COMMIT if not auto_commit else _REASON_PROTECTED_TARGET_BRANCH
        )
        assert payload["verdict_durability_skip_reason"] == expected_reason, payload

    latest = ReviewCycleArtifact.latest(wp_dir)
    assert latest is not None, f"cell {_cell_id(cell)}: expected a written review-cycle artifact"
    # WP06 (FR-003/SC-007): ``ReviewCycleArtifact`` no longer carries a
    # ``verdict`` field, and this cell's own mocked harness (``setup_mocked_
    # env``/``_REVIEW_GATE_BYPASS``) deliberately does not append a review_
    # result event for this hop either (it isolates the review-cycle
    # WRITER's own behaviour, not the full transition-emit machinery -- see
    # ``test_uncommitted_rejection_is_visible_to_the_immediately_following_
    # approval``'s own comment for the identical, already-documented
    # limitation) -- so neither successor authority is populated here. The
    # BODY content the two write paths produce is genuinely distinct
    # (``_persist_approved_review_cycle`` always starts with "Approved by ",
    # the rejection path never does), so it is the correct, still-checkable
    # proxy for "which scenario actually wrote this".
    _assert_body_matches_scenario_verdict(latest.body, scenario.verdict, cell=_cell_id(cell))

    if expected_durable:
        evidence_ref = (
            wp_dir / f"review-cycle-{latest.cycle_number}.md"
        ).relative_to(repo).as_posix()
        _assert_exact_blob_at_ref(repo, "main", evidence_ref)
    else:
        assert isinstance(router, FakeCoordCommitRouter)
        assert router.artifact_calls == [], (
            f"cell {_cell_id(cell)}: durability signal reported non-durable "
            f"but commit_artifact was still invoked ({router.artifact_calls}) -- "
            "the skip must prevent the ATTEMPT, not merely mis-report it"
        )


# ---------------------------------------------------------------------------
# T068 -- the committed, automated mutation (non-vacuity) proof
# ---------------------------------------------------------------------------


@pytest.mark.fast
@pytest.mark.parametrize("cell", _DURABLE_CELLS, ids=[_cell_id(c) for c in _DURABLE_CELLS])
def test_matrix_is_sensitive_to_commit_removal(
    tmp_path: Path, cell: _MatrixCell, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    """A neutered automatic evidence router fails closed before emission."""
    scenario, topology, auto_commit = cell
    assert topology == "single_branch" and auto_commit is True  # documents the subset

    repo = tmp_path
    seed_rejected = scenario.verdict == "approved"
    feature_dir = _seed_fixture(
        repo, _MISSION, _WP_ID, old_lane="in_review", seed_rejected_cycle=seed_rejected
    )

    router = FakeCoordCommitRouter(write_dir=feature_dir)
    commit_hits: list[str] = []

    def _neutered_commit(*args: Any, **kwargs: Any) -> CommitArtifactResult:
        commit_hits.append("commit_artifact")
        return CommitArtifactResult(status="unchanged", placement_ref="main")

    router.commit_artifact = _neutered_commit  # type: ignore[method-assign]
    event_ids_before = {event.event_id for event in read_events(feature_dir)}

    with (
        caplog.at_level("WARNING", logger="specify_cli.review.cycle"),
        pytest.raises(typer.Exit) as exc_info,
    ):
        _drive_scenario(
            repo,
            mission=_MISSION,
            wp_id=_WP_ID,
            scenario=scenario,
            router=router,
            auto_commit=True,
            skip_target_branch_commit=False,
        )

    assert exc_info.value.exit_code == 1
    payload = _last_json_payload(capsys)
    evidence_ref = _assert_persistence_failure(
        payload,
        reason="unchanged_unverified",
        destination_ref="main",
    )
    assert commit_hits == ["commit_artifact"]
    assert (repo / evidence_ref).is_file(), payload
    assert subprocess.run(
        ["git", "show", f"main:{evidence_ref}"],
        cwd=repo,
        capture_output=True,
        check=False,
    ).returncode != 0
    _assert_no_new_status_event(feature_dir, event_ids_before)
    assert any("Failed to commit review-cycle" in r.message for r in caplog.records), (
        f"cell {_cell_id(cell)}: the fail-closed evidence error must be logged; "
        f"records={caplog.records}"
    )


@pytest.mark.fast
@pytest.mark.parametrize("cell", _INSULATED_CELLS, ids=[_cell_id(c) for c in _INSULATED_CELLS])
def test_protected_and_no_auto_commit_cells_never_invoke_commit_artifact(
    tmp_path: Path, cell: _MatrixCell, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other half of T068's edge case: for the 9 cells where
    ``auto_commit=False`` or the topology is ``coord_protected``, the skip
    gate (``_resolve_verdict_commit_router``) must prevent ``commit_artifact``
    from ever being called. Explicit local-only cells return their stable skip
    reason; protected automatic cells fail nonzero with retained evidence and
    no event. Mutating an unreachable commit method must alter neither path."""
    scenario, topology, auto_commit = cell
    repo = tmp_path
    seed_rejected = scenario.verdict == "approved"
    feature_dir = _seed_fixture(
        repo, _MISSION, _WP_ID, old_lane="in_review", seed_rejected_cycle=seed_rejected
    )
    router = FakeCoordCommitRouter(write_dir=feature_dir)
    router.commit_artifact = (  # type: ignore[method-assign]
        lambda *args, **kwargs: CommitArtifactResult(
            status="unchanged", placement_ref="main"
        )
    )
    skip_target_branch_commit = topology == "coord_protected"

    event_ids_before = {event.event_id for event in read_events(feature_dir)}
    if auto_commit:
        assert skip_target_branch_commit
        with pytest.raises(typer.Exit) as exc_info:
            _drive_scenario(
                repo,
                mission=_MISSION,
                wp_id=_WP_ID,
                scenario=scenario,
                router=router,
                auto_commit=auto_commit,
                skip_target_branch_commit=skip_target_branch_commit,
            )
        assert exc_info.value.exit_code == 1
        payload = _last_json_payload(capsys)
        evidence_ref = _assert_persistence_failure(
            payload,
            reason=_REASON_PROTECTED_TARGET_BRANCH,
            destination_ref=None,
        )
        assert (repo / evidence_ref).is_file(), payload
        _assert_no_new_status_event(feature_dir, event_ids_before)
    else:
        _drive_scenario(
            repo,
            mission=_MISSION,
            wp_id=_WP_ID,
            scenario=scenario,
            router=router,
            auto_commit=auto_commit,
            skip_target_branch_commit=skip_target_branch_commit,
        )
        payload = _last_json_payload(capsys)
        assert payload["verdict_durably_persisted"] is False, payload
        assert payload["verdict_durability_skip_reason"] == _REASON_NO_AUTO_COMMIT

    assert router.artifact_calls == [], (
        f"cell {_cell_id(cell)}: commit_artifact was invoked even though this "
        "cell is supposed to skip the attempt entirely -- the mutation should "
        "be irrelevant to (and must not have altered) this outcome"
    )
    if auto_commit:
        assert router.status_calls == [], "protected failure must precede event emission"


# ---------------------------------------------------------------------------
# Edge case (T067): an uncommitted --no-auto-commit rejection must still be
# the "latest verdict" the very next approval attempt on the same WP reads.
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_uncommitted_rejection_is_visible_to_the_immediately_following_approval(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path
    feature_dir = _seed_fixture(
        repo, _MISSION, _WP_ID, old_lane="in_review", seed_rejected_cycle=False
    )
    wp_dir = _wp_dir(repo, _MISSION, _WP_ID)

    feedback = repo / "feedback.md"
    feedback.write_text("**Issue**: needs work, --no-auto-commit.\n", encoding="utf-8")
    router1 = FakeCoordCommitRouter(write_dir=feature_dir)
    _run_cell(
        repo,
        mission=_MISSION,
        wp_id=_WP_ID,
        to="planned",
        router=router1,
        auto_commit=False,
        skip_target_branch_commit=False,
        review_feedback_file=feedback,
    )
    payload1 = _last_json_payload(capsys)
    assert payload1["verdict_durably_persisted"] is False
    assert payload1["verdict_durability_skip_reason"] == _REASON_NO_AUTO_COMMIT
    latest_after_reject = ReviewCycleArtifact.latest(wp_dir)
    # No event-sourced review_result exists yet at this point (the comment
    # below explains why -- the mocked harness bypasses the real emit layer
    # for this rejection hop), so the WP06-successor check cannot be the
    # event authority here (unlike every other site in this file). The
    # artifact itself no longer carries a ``verdict`` field either (FR-003/
    # SC-007) -- the genuinely-checkable property at this point is that the
    # WRITE actually happened and carries the reviewer's real feedback body,
    # not a fabricated/wrong one.
    assert latest_after_reject is not None
    assert "needs work" in latest_after_reject.body
    # Genuinely uncommitted -- not merely "reported" as such (the WP's own
    # ``tasks/<wp>/`` dir is untracked-as-a-whole, so ``git status`` collapses
    # it to a single directory line rather than naming the file -- assert on
    # HEAD readability instead, the same idiom WP11's own durability tests use).
    rel = f"kitty-specs/{_MISSION}/tasks/{_WP_ID}-test/review-cycle-1.md"
    assert not _git_head_has_file(repo, rel), "the rejection must NOT be committed at HEAD"

    # Immediately re-open for review and approve -- the ordinary reject->approve
    # flow the rejection's own uncommitted state must not break.
    #
    # WP05 (verdict-seam-write-unification-01KZ9Q35, T023): the writer's own
    # "is the current verdict a rejection" probe is now event-sourced. This
    # test's mocked harness (``setup_mocked_env``'s ``_REVIEW_GATE_BYPASS``)
    # deliberately stubs out the transactional emit layer to isolate the
    # review-cycle WRITER's own behaviour, so step 1's rejection above never
    # appended a real ``review_result`` event (confirmed: only the seed event
    # exists on disk afterward) -- seed it explicitly here, mirroring what the
    # UNMOCKED production ``_mt_hop_review_result`` wiring records for a real
    # ``in_review -> planned`` rejection hop.
    append_event(
        feature_dir,
        StatusEvent(
            event_id=f"test-{_WP_ID}-rejection-review-result",
            mission_slug=_MISSION,
            wp_id=_WP_ID,
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:30+00:00",
            actor="test",
            force=False,
            execution_mode="worktree",
            review_result=ReviewResult(
                reviewer="test",
                verdict="changes_requested",
                reference=f"review-cycle://{_MISSION}/{_WP_ID}-test/review-cycle-1.md",
            ),
        ),
    )
    _seed_wp_event(feature_dir, _WP_ID, "in_review", seq=1)
    router2 = _FaultInjectableCoordRouter(write_dir=feature_dir)
    _run_cell(
        repo,
        mission=_MISSION,
        wp_id=_WP_ID,
        to="approved",
        router=router2,
        auto_commit=True,
        skip_target_branch_commit=False,
        note="Review passed",
    )
    payload2 = _last_json_payload(capsys)
    assert payload2["verdict_durably_persisted"] is True
    latest_after_approve = ReviewCycleArtifact.latest(wp_dir)
    assert latest_after_approve is not None
    assert latest_after_approve.body.startswith("Approved by "), (
        f"expected an 'Approved by ...' body after the approval hop, "
        f"got: {latest_after_approve.body!r}"
    )
    approval_rel = (
        wp_dir / f"review-cycle-{latest_after_approve.cycle_number}.md"
    ).relative_to(repo).as_posix()
    _assert_exact_blob_at_ref(repo, "main", approval_rel)


# ---------------------------------------------------------------------------
# Arbiter override -- a SEPARATE, smaller matrix (event-sourced durability,
# not commit_artifact-based; see the module docstring for why it is not
# folded into the 12-cell parametrization above).
# ---------------------------------------------------------------------------


def _seed_arbiter_fixture(repo: Path, mission: str, wp_id: str) -> Path:
    """A WP that went for_review -> planned via an explicit, on-disk rejected
    review-cycle-1.md (uncommitted) -- the precondition an arbiter override
    supersedes. Mirrors ``test_tasks_cli_contract_coord.py``'s
    ``arbiter_override_to_approved`` scenario recipe (the established house
    pattern for this exact shape) rather than inventing a second one."""
    _init_repo(repo)
    feature_dir, _wp_file = _build_wp_file(repo, mission, wp_id)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True
    )
    _unprotect_main(repo)
    chain: Sequence[tuple[str, str]] = (
        ("planned", "claimed"),
        ("claimed", "in_progress"),
        ("in_progress", "for_review"),
    )
    for seq, (from_lane, to_lane) in enumerate(chain, start=1):
        append_event(
            feature_dir,
            StatusEvent(
                event_id=f"arb-matrix-{seq}",
                mission_slug=mission,
                wp_id=wp_id,
                from_lane=Lane(from_lane),
                to_lane=Lane(to_lane),
                at=f"2026-01-01T00:00:0{seq}+00:00",
                actor="test",
                force=True,
                execution_mode="worktree",
            ),
        )
    append_event(
        feature_dir,
        StatusEvent(
            event_id="arb-matrix-4",
            mission_slug=mission,
            wp_id=wp_id,
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:04+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
            review_ref=f"feedback://arbiter/{wp_id}/review-cycle-1.md",
        ),
    )
    create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=mission,
        wp_id=wp_id,
        wp_slug=f"{wp_id}-test",
        body=_SEED_FEEDBACK_BODY,
        reviewer_agent="reviewer-matrix",
        verdict="rejected",
        commit_router=None,
    )
    return feature_dir


@pytest.mark.fast
@pytest.mark.parametrize("auto_commit", _AUTO_COMMIT_SETTINGS, ids=["auto_commit", "no_auto_commit"])
def test_arbiter_override_cell_suppresses_fabricated_approval(
    tmp_path: Path, auto_commit: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    """T055/FR-011 (WP12) re-verified through THIS WP's own matrix harness:
    an arbiter override targeting ``approved`` must record the ``ReviewOverride``
    (event-sourced) and must NOT also fabricate a fresh ``verdict: approved``
    review-cycle artifact. Durability here rides on ``commit_status`` (the
    status-transition commit), not ``commit_artifact`` -- so this cell
    correctly reports NEITHER of the ``verdict_durably_persisted``/
    ``verdict_durability_skip_reason`` keys at all (there is no review-cycle
    write for `_mt_output` to describe)."""
    repo = tmp_path
    mission = "arbiter-matrix"
    feature_dir = _seed_arbiter_fixture(repo, mission, _WP_ID)
    router = FakeCoordCommitRouter(write_dir=feature_dir)

    _run_cell(
        repo,
        mission=mission,
        wp_id=_WP_ID,
        to="approved",
        router=router,
        auto_commit=auto_commit,
        skip_target_branch_commit=False,
        note="arbiter release: matrix override",
        force=True,
    )
    payload = _last_json_payload(capsys)
    assert "verdict_durably_persisted" not in payload, payload
    assert "verdict_durability_skip_reason" not in payload, payload

    wp_dir = _wp_dir(repo, mission, _WP_ID)
    cycle_artifacts = sorted(p.name for p in wp_dir.glob("review-cycle-*.md"))
    assert cycle_artifacts == ["review-cycle-1.md"], (
        "an arbiter override must not ALSO write a fresh approved review-cycle "
        f"artifact; got {cycle_artifacts}"
    )

    snapshot = _materialize(feature_dir)
    override = snapshot.work_packages.get(_WP_ID, {}).get("review") or {}
    assert override.get("wp_id") == _WP_ID
    assert override.get("actor"), "override must carry a non-empty actor"
    assert "matrix override" in override.get("reason", "")


@pytest.mark.fast
def test_arbiter_override_is_sensitive_to_its_own_commit_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T068's mutation proof, scoped correctly to the arbiter cell's OWN
    durability mechanism (``persist_arbiter_decision``, not ``commit_
    artifact`` -- see this module's docstring). Neutering the persist call to
    a no-op that performs no write must leave the review-override slot
    genuinely empty -- proving the assertion above (not merely "no exception")
    is what would catch the commit call being deleted.

    Patched at the POINT OF USE (``tasks_move_task``'s own module-scope
    ``from ... import persist_arbiter_override_decision``), not at
    ``tasks_verdict_persistence`` (the origin module) -- a ``from X import
    name`` binds the name in the IMPORTING module's namespace at import time,
    so patching the origin module's attribute afterwards would not intercept
    the call ``_run_arbiter_override`` actually makes (research.md D1/D7's
    documented seam-bridge convention this codebase uses throughout)."""
    from specify_cli.cli.commands.agent import tasks_move_task as _tmt

    repo = tmp_path
    mission = "arbiter-matrix-mutation"
    feature_dir = _seed_arbiter_fixture(repo, mission, _WP_ID)
    router = FakeCoordCommitRouter(write_dir=feature_dir)

    def _neutered(**kwargs: object) -> None:
        # The documented no-op shape: skip straight past the real
        # ``persist_arbiter_decision`` call this function would otherwise
        # make -- simulating the commit call having been deleted from
        # production code. Performs NO event append/commit at all.
        del kwargs

    monkeypatch.setattr(_tmt, "persist_arbiter_override_decision", _neutered)
    _run_cell(
        repo,
        mission=mission,
        wp_id=_WP_ID,
        to="approved",
        router=router,
        auto_commit=True,
        skip_target_branch_commit=False,
        note="arbiter release: matrix override",
        force=True,
    )

    snapshot = _materialize(feature_dir)
    override = snapshot.work_packages.get(_WP_ID, {}).get("review") or {}
    assert override == {}, (
        "expected the review-override slot to be EMPTY once the persist call "
        f"is neutered (proving the assertion catches a deleted commit call); "
        f"got {override!r}"
    )


# ---------------------------------------------------------------------------
# T069a -- real CoordCommitRouter, real git: the non-fakeable durability proof
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.git_repo
def test_real_router_commit_lands_on_disk_and_git_history(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """T069: at least one cell runs the REAL ``CoordCommitRouter``
    (``RealCoordCommitRouter``, wrapped by ``test_move_task_durability.py``'s
    established ``_FaultInjectableCoordRouter`` so the transition-emit leg
    stays independently controllable) against a real, git-initialised repo,
    and asserts on ACTUAL git state -- never a fake's in-memory call log
    dressed up to look real."""
    repo = tmp_path
    feature_dir = _seed_fixture(
        repo, _MISSION, _WP_ID, old_lane="in_review", seed_rejected_cycle=True
    )
    router = _FaultInjectableCoordRouter(write_dir=feature_dir)
    ports = TasksPorts(
        fs=FakeFsReader(default_planning_dir=repo / "kitty-specs" / _MISSION),
        coord=router,
        git=FakeGitOps(),
        render=FakeRender(),
    )
    extra_patches = dict(_REVIEW_GATE_BYPASS)
    extra_patches["_skip_target_branch_commit"] = False
    with setup_mocked_env(
        repo, mission_slug=_MISSION, target_branch="main", extra_patches=extra_patches
    ):
        _do_move_task(
            _MoveTaskArgs(
                task_id=_WP_ID,
                to="approved",
                mission=_MISSION,
                agent=None,
                assignee=None,
                shell_pid=None,
                note="Review passed",
                review_feedback_file=None,
                approval_ref=None,
                reviewer=None,
                self_review_fallback=False,
                intended_reviewer=None,
                reviewer_failure_reason=None,
                done_override_reason=None,
                force=False,
                tracker_ref=None,
                skip_review_artifact_check=False,
                auto_commit=True,
                json_output=True,
            ),
            ports=ports,
        )

    payload = _last_json_payload(capsys)
    assert payload["verdict_durably_persisted"] is True

    rel = f"kitty-specs/{_MISSION}/tasks/{_WP_ID}-test/review-cycle-2.md"
    assert _git_head_has_file(repo, rel), "the real commit never reached HEAD"
    status = _git_status(repo)
    assert "review-cycle-2.md" not in status, f"expected a clean tree after a real commit:\n{status}"

    show = subprocess.run(
        ["git", "show", f"HEAD:{rel}"], cwd=repo, capture_output=True, text=True
    )
    assert show.returncode == 0
    assert "Approved by" in show.stdout  # sanity: real body/content landed
    _assert_committed_frontmatter_has_no_verdict_key(show.stdout)


@pytest.mark.integration
@pytest.mark.git_repo
def test_real_router_cell_reds_when_commit_artifact_is_neutered(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    """A real-router evidence no-op becomes a typed, pre-event refusal."""
    repo = tmp_path
    feature_dir = _seed_fixture(
        repo, _MISSION, _WP_ID, old_lane="in_review", seed_rejected_cycle=True
    )

    router = _FaultInjectableCoordRouter(write_dir=feature_dir)
    commit_hits: list[str] = []

    def _neutered_commit(*args: Any, **kwargs: Any) -> CommitArtifactResult:
        commit_hits.append("commit_artifact")
        return CommitArtifactResult(status="unchanged", placement_ref="main")

    router.commit_artifact = _neutered_commit  # type: ignore[method-assign]
    ports = TasksPorts(
        fs=FakeFsReader(default_planning_dir=repo / "kitty-specs" / _MISSION),
        coord=router,
        git=FakeGitOps(),
        render=FakeRender(),
    )
    extra_patches = dict(_REVIEW_GATE_BYPASS)
    extra_patches["_skip_target_branch_commit"] = False
    event_ids_before = {event.event_id for event in read_events(feature_dir)}
    with (
        setup_mocked_env(
            repo, mission_slug=_MISSION, target_branch="main", extra_patches=extra_patches
        ),
        caplog.at_level("WARNING", logger="specify_cli.review.cycle"),
        pytest.raises(typer.Exit) as exc_info,
    ):
        _do_move_task(
            _MoveTaskArgs(
                task_id=_WP_ID,
                to="approved",
                mission=_MISSION,
                agent=None,
                assignee=None,
                shell_pid=None,
                note="Review passed",
                review_feedback_file=None,
                approval_ref=None,
                reviewer=None,
                self_review_fallback=False,
                intended_reviewer=None,
                reviewer_failure_reason=None,
                done_override_reason=None,
                force=False,
                tracker_ref=None,
                skip_review_artifact_check=False,
                auto_commit=True,
                json_output=True,
            ),
            ports=ports,
        )

    assert exc_info.value.exit_code == 1
    payload = _last_json_payload(capsys)
    evidence_ref = _assert_persistence_failure(
        payload,
        reason="unchanged_unverified",
        destination_ref="main",
    )
    assert commit_hits == ["commit_artifact"]
    assert (repo / evidence_ref).is_file(), payload
    assert not _git_head_has_file(repo, evidence_ref)
    _assert_no_new_status_event(feature_dir, event_ids_before)
    assert any("Failed to commit review-cycle" in r.message for r in caplog.records), (
        "fail-closed evidence refusal must still be logged"
    )


# ---------------------------------------------------------------------------
# T069c -- the REAL coord-topology cell (adversarial-review finding: the
# "topology" axis in the 12-cell matrix above is a directly-patched
# ``_skip_target_branch_commit`` boolean, not a real coord worktree -- every
# one of those 12 cells is a SINGLE_BRANCH repo under the hood. WP04's
# ``REVIEW_CYCLE`` routing makes topology load-bearing for durability (it
# changes which git REF the commit lands on, not merely whether a commit is
# attempted), so that dimension needs its OWN genuine coverage, not a second
# coat of the skip-gate proof above. Built on the canonical, un-stubbed
# ``coord_topology_fixture.py`` (``_build_coord_topology``) -- NOT a
# hand-rolled second coord fixture, per the reviewer's explicit instruction.
# ---------------------------------------------------------------------------


def _seed_coord_wp_in_review(ctx: CoordTopologyContext, wp_id: str) -> None:
    """Replace the base fixture's own seed event (a resolver-smoke marker
    event, not meant to be read by the real reducer -- see ``coord_topology_
    fixture.py``'s module docstring) with a single, real, force-seeded
    ``in_review`` event on the COORD husk -- the same single-event seed shape
    every other cell in this file uses (``_seed_wp_event``), just written to
    the coord husk's event log instead of a flat mission's."""
    ctx.status_events_path.unlink()
    _seed_wp_event(ctx.coord_feature_dir, wp_id, "in_review", seq=0)


def _disable_branch_protection_for_coord_cell(repo: Path) -> None:
    """Unprotect ``main`` so the ordinary (non-skip-arm) commit path runs --
    mirrors ``tests/coordination/test_analysis_report_rehome.py``'s
    ``_disable_branch_protection`` (a few lines, reproduced rather than
    cross-imported from a `tests/coordination/` module this file has no other
    dependency on)."""
    config = repo / ".kittify" / "config.yaml"
    config.write_text("protection:\n  protected_branches: []\n", encoding="utf-8")
    subprocess.run(["git", "add", ".kittify/config.yaml"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "test: unprotect main for the coord durability cell"],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _coord_cell_ports(ctx: CoordTopologyContext, router: _FaultInjectableCoordRouter) -> TasksPorts:
    return TasksPorts(
        fs=FakeFsReader(default_planning_dir=ctx.primary_feature_dir),
        coord=router,
        git=FakeGitOps(),
        render=FakeRender(),
    )


def _run_coord_cell_approval(
    ctx: CoordTopologyContext, *, wp_id: str, router: _FaultInjectableCoordRouter
) -> None:
    """Drive the REAL ``_do_move_task`` against the real coord fixture.

    Deliberately does NOT patch ``_skip_target_branch_commit`` (unlike every
    other cell in this file) -- this cell's entire point is to let the REAL
    resolver see the REAL coord worktree ``_build_coord_topology`` created, so
    the topology dimension is genuine, not simulated.
    """
    with setup_mocked_env(
        ctx.repo,
        mission_slug=ctx.slug,
        target_branch="main",
        extra_patches=dict(_REVIEW_GATE_BYPASS),
    ):
        _do_move_task(
            _MoveTaskArgs(
                task_id=wp_id,
                to="approved",
                mission=ctx.slug,
                agent=None,
                assignee=None,
                shell_pid=None,
                note="Review passed",
                review_feedback_file=None,
                approval_ref=None,
                reviewer=None,
                self_review_fallback=False,
                intended_reviewer=None,
                reviewer_failure_reason=None,
                done_override_reason=None,
                force=False,
                tracker_ref=None,
                skip_review_artifact_check=False,
                auto_commit=True,
                json_output=True,
            ),
            ports=_coord_cell_ports(ctx, router),
        )


def _seed_coord_rejected_cycle(ctx: CoordTopologyContext, wp_id: str) -> None:
    created = create_rejected_review_cycle(
        main_repo_root=ctx.repo,
        mission_slug=ctx.slug,
        wp_id=wp_id,
        wp_slug=wp_id,  # the fixture's WP file is literally ``tasks/WP01.md``
        body=_SEED_FEEDBACK_BODY,
        reviewer_agent="reviewer-matrix",
        verdict="rejected",
        commit_router=None,  # uncommitted seed, matching every other cell's precondition
    )
    # WP05 (verdict-seam-write-unification-01KZ9Q35, T023): seed the
    # event-sourced rejection the writer's probe now reads (see
    # ``_seed_fixture``'s identical rationale). Re-issues the ``in_review``
    # seed event AFTER this one so the LAST event in file order stays
    # ``in_review`` (``_mt_current_event_lane`` picks the last one) --
    # this function runs AFTER ``_seed_coord_wp_in_review`` at every call
    # site, so without the re-seed this rejection event would wrongly
    # become "current".
    append_event(
        ctx.coord_feature_dir,
        StatusEvent(
            event_id=f"test-{wp_id}-seed-rejection-event",
            mission_slug=ctx.slug,
            wp_id=wp_id,
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.IN_PROGRESS,
            at="2025-12-31T00:00:00+00:00",
            actor="reviewer-matrix",
            force=False,
            execution_mode="worktree",
            review_result=created.review_result,
        ),
    )
    _seed_wp_event(ctx.coord_feature_dir, wp_id, "in_review", seq=1)


def _coord_review_cycle_rel(ctx: CoordTopologyContext, wp_id: str, cycle: int) -> str:
    return f"kitty-specs/{ctx.slug}/tasks/{wp_id}/review-cycle-{cycle}.md"


def _git_show(repo: Path, ref: str, rel: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "show", f"{ref}:{rel}"], cwd=repo, capture_output=True, text=True
    )


@pytest.mark.integration
@pytest.mark.git_repo
def test_real_coord_topology_review_cycle_commits_to_coord_ref_not_primary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The genuine topology-dimension cell: a real coord worktree (not a
    patched ``skip_target_branch_commit`` boolean), driven through the real
    ``_do_move_task`` orchestrator with the REAL ``CoordCommitRouter``.
    Asserts on committed git TREES (``git show <ref>:<path>``), mirroring
    ``tests/coordination/test_analysis_report_rehome.py``'s placement idiom --
    the artifact must be reachable on the COORD ref and ABSENT on primary."""
    ctx = _build_coord_topology(tmp_path, write_husk_meta=False)
    _disable_branch_protection_for_coord_cell(ctx.repo)
    _seed_coord_wp_in_review(ctx, "WP01")
    _seed_coord_rejected_cycle(ctx, "WP01")

    router = _FaultInjectableCoordRouter(write_dir=ctx.coord_feature_dir)
    _run_coord_cell_approval(ctx, wp_id="WP01", router=router)

    payload = _last_json_payload(capsys)
    assert payload["verdict_durably_persisted"] is True

    rel = _coord_review_cycle_rel(ctx, "WP01", 2)
    coord_show = _git_show(ctx.repo, ctx.coord_branch, rel)
    assert coord_show.returncode == 0, (
        f"review-cycle-2.md is NOT on the coordination ref {ctx.coord_branch!r}: "
        f"{coord_show.stderr}"
    )
    _assert_committed_frontmatter_has_no_verdict_key(coord_show.stdout)

    primary_show = _git_show(ctx.repo, "main", rel)
    assert primary_show.returncode != 0, (
        "review-cycle-2.md WAS committed to the primary ref 'main' -- a stale "
        f"PRIMARY copy was left behind:\n{primary_show.stdout}"
    )


@pytest.mark.integration
@pytest.mark.git_repo
def test_real_coord_topology_cell_reds_when_commit_artifact_is_neutered(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    """The coordination topology also fails closed on a neutered evidence write."""
    ctx = _build_coord_topology(tmp_path, write_husk_meta=False)
    _disable_branch_protection_for_coord_cell(ctx.repo)
    _seed_coord_wp_in_review(ctx, "WP01")
    _seed_coord_rejected_cycle(ctx, "WP01")

    router = _FaultInjectableCoordRouter(write_dir=ctx.coord_feature_dir)
    commit_hits: list[str] = []

    def _neutered_commit(*args: Any, **kwargs: Any) -> CommitArtifactResult:
        commit_hits.append("commit_artifact")
        return CommitArtifactResult(
            status="unchanged", placement_ref=ctx.coord_branch
        )

    router.commit_artifact = _neutered_commit  # type: ignore[method-assign]
    event_ids_before = {
        event.event_id for event in read_events(ctx.coord_feature_dir)
    }
    with (
        caplog.at_level("WARNING", logger="specify_cli.review.cycle"),
        pytest.raises(typer.Exit) as exc_info,
    ):
        _run_coord_cell_approval(ctx, wp_id="WP01", router=router)

    assert exc_info.value.exit_code == 1
    payload = _last_json_payload(capsys)
    evidence_ref = _assert_persistence_failure(
        payload,
        reason="unchanged_unverified",
        destination_ref=ctx.coord_branch,
    )
    assert commit_hits == ["commit_artifact"]
    assert (ctx.repo / evidence_ref).is_file(), payload
    assert _git_show(ctx.repo, ctx.coord_branch, evidence_ref).returncode != 0
    _assert_no_new_status_event(ctx.coord_feature_dir, event_ids_before)
    assert any("Failed to commit review-cycle" in r.message for r in caplog.records), (
        "coord fail-closed evidence refusal must still be logged"
    )


@pytest.mark.integration
@pytest.mark.git_repo
def test_real_coord_topology_revert_deletes_and_commits_on_coord_ref(
    tmp_path: Path,
) -> None:
    """WP13's durability-matrix witness (DM-01KZ75GBNXC73Q38M43GBH38W7): a
    transition-emit failure AFTER a coord-topology verdict write already
    landed must be reverted on the SAME ref the original commit used (COORD),
    not primary -- the exact live bug WP13 fixed
    (``_resolve_revert_commit_worktree`` + ``kind=REVIEW_CYCLE`` in
    ``revert_committed_verdict_write``). Before WP13, this compensator tried
    to commit the deletion onto PRIMARY while the orphan verdict stayed
    fully readable on COORD -- this cell is the regression pin."""
    ctx = _build_coord_topology(tmp_path, write_husk_meta=False)
    _disable_branch_protection_for_coord_cell(ctx.repo)
    _seed_coord_wp_in_review(ctx, "WP01")
    _seed_coord_rejected_cycle(ctx, "WP01")

    rel = _coord_review_cycle_rel(ctx, "WP01", 2)
    router = _FaultInjectableCoordRouter(write_dir=ctx.coord_feature_dir, emit_should_fail=True)

    with pytest.raises(typer.Exit):
        _run_coord_cell_approval(ctx, wp_id="WP01", router=router)

    # The revert must undo the COORD commit -- no readable verdict at the
    # CURRENT tip of the coord ref.
    coord_show_after = _git_show(ctx.repo, ctx.coord_branch, rel)
    assert coord_show_after.returncode != 0, (
        f"review-cycle-2.md is STILL reachable at the coord ref {ctx.coord_branch!r} "
        f"tip after a reverted transition-emit failure -- WP13's revert-worktree "
        f"fix did not take effect:\n{coord_show_after.stdout}"
    )
    # It was never left on primary either (the original write never commits there).
    assert _git_show(ctx.repo, "main", rel).returncode != 0

    # The ORIGINAL commit still exists in history (a revert commit, not a
    # rewrite) -- mirrors test_move_task_durability.py's own idiom.
    log = subprocess.run(
        ["git", "-C", str(ctx.repo), "log", "--all", "--name-only", "--pretty=format:--COMMIT--"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "review-cycle-2.md" in log, (
        "the revert should be a NEW commit undoing the write, not a history "
        f"rewrite -- the original commit should still appear in git log:\n{log}"
    )

    # No readable committed verdict for this WP -- the reverted cycle-2 must
    # not be the reader-visible latest; the pre-existing rejected cycle-1 is.
    # (WP06, FR-003/SC-007: the artifact no longer carries a ``verdict``
    # field to read directly -- ``cycle_number`` is the checkable proxy for
    # "which write is the reader-visible latest", which is exactly what this
    # assertion is about: cycle-2's revert must not promote it over cycle-1.)
    latest = ReviewCycleArtifact.latest(ctx.primary_feature_dir / "tasks" / "WP01")
    assert latest is not None and latest.cycle_number == 1, (
        f"expected the pre-existing rejected cycle 1 to still be the reader-"
        f"visible latest after the coord-ref revert, got {latest!r}"
    )

    # Coord worktree's tasks/ dir is clean after the revert-commit (no
    # partially-reverted state) -- scoped to that subtree, not repo-wide: the
    # fixture's own ``status.events.jsonl`` under the coord husk is
    # deliberately left untracked by the builder (a different, unrelated
    # concern -- see ``_build_coord_topology``'s own docstring) and would
    # otherwise be a false positive here, mirroring ``test_move_task_
    # durability.py``'s identical scoping choice for the single_branch case.
    coord_tasks_rel = f"kitty-specs/{ctx.slug}/tasks"
    coord_status = subprocess.run(
        ["git", "status", "--porcelain", "--", coord_tasks_rel],
        cwd=ctx.coord_feature_dir.parents[1],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert coord_status == "", (
        f"coord worktree's tasks/ dir is not clean after the revert-commit:\n{coord_status}"
    )


# ---------------------------------------------------------------------------
# T069b -- the SIGKILL cell (SC-003 / US1 AC4)
# ---------------------------------------------------------------------------


def _mp_child_write_then_hang(
    repo: str,
    mission: str,
    wp_id: str,
    sub_artifact_dir: str,
    ready_path: str,
    body: str,
) -> None:
    """Multiprocessing worker target: perform ONLY the write+validate half of
    the writer (``_allocate_and_write_review_cycle_locked`` -- there is no
    commit call reachable inside this function AT ALL), signal readiness, then
    hang. The parent's SIGKILL therefore always lands cleanly between a
    COMPLETED write and a NOT-YET-STARTED commit -- the exact window SC-003
    names, never a mid-write kill (a different, filesystem-dependent hazard
    this test does not simulate, matching WP10's T044 scope note)."""
    artifact_path: Path
    _artifact, artifact_path, _filename = _allocate_and_write_review_cycle_locked(
        main_repo_root=Path(repo),
        mission_slug=mission,
        wp_id=wp_id,
        sub_artifact_dir=Path(sub_artifact_dir),
        reviewer_agent="reviewer-sigkill",
        affected_files=[],
        body=body,
    )
    Path(ready_path).write_text(str(artifact_path), encoding="utf-8")
    time.sleep(3600)  # the parent SIGKILLs us long before this could return


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.skipif(
    sys.platform == "win32",
    reason="SIGKILL has no direct Windows equivalent (T069 documented edge case)",
)
def test_sigkill_between_write_and_commit_then_identical_retry_exits_zero(
    tmp_path: Path,
) -> None:
    """SC-003 / US1 AC4, exercised end to end: after a SIGKILL strictly
    between a completed write and a not-yet-started commit, the identical
    retry both completes cleanly AND records the correct verdict, with zero
    manual cleanup -- the literal acceptance criterion.

    Scope note: this drives ``create_rejected_review_cycle`` (the writer WP10's
    own T044 reproduction and this WP's prompt both license as the "real
    move-task writer path" substitute for the full CLI surface) rather than
    the full ``_do_move_task``/CLI stack, to keep the multiprocessing child a
    minimal, single-purpose target. "Exits zero" is therefore the direct-call
    analogue (no exception escapes the retry) rather than a literal process
    exit code -- the git-state assertions below are what actually prove the
    SC-003 guarantee, independent of that framing choice.
    """
    repo = tmp_path
    mission = "sigkill-matrix"
    _init_repo(repo)
    feature_dir, _wp_file = _build_wp_file(repo, mission, _WP_ID)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True
    )
    _unprotect_main(repo)
    sub_dir = _review_cycle_wp_dir(repo, mission, _WP_SLUG)
    ready_path = tmp_path / "ready.txt"
    body = "Killed mid-flight, before any commit was attempted.\n"

    ctx = multiprocessing.get_context("spawn")
    proc = ctx.Process(
        target=_mp_child_write_then_hang,
        args=(str(repo), mission, _WP_ID, str(sub_dir), str(ready_path), body),
    )
    proc.start()
    deadline = time.monotonic() + 10.0
    while not ready_path.exists():
        if time.monotonic() > deadline:
            proc.kill()
            proc.join(timeout=5)
            pytest.fail("child never signaled write-complete readiness within 10s")
        time.sleep(0.02)

    artifact_path = Path(ready_path.read_text(encoding="utf-8").strip())
    assert artifact_path.exists(), "the child's write never landed before the readiness signal"

    # The SIGKILL itself -- sent only once the write is provably complete and
    # the commit has provably not started (there is no commit call reachable
    # in the child target at all).
    proc.kill()
    proc.join(timeout=10)
    assert not proc.is_alive(), "the child process was not reaped after SIGKILL"
    assert proc.exitcode != 0, f"expected a killed child, got exitcode={proc.exitcode}"

    rel = artifact_path.relative_to(repo)
    status_before_retry = subprocess.run(
        ["git", "status", "--porcelain", "--", str(rel)],
        cwd=repo,
        capture_output=True,
        text=True,
    ).stdout
    assert artifact_path.name in status_before_retry, (
        f"expected the orphan {artifact_path.name} to be untracked after the kill:\n"
        f"{status_before_retry}"
    )

    # The identical retry, from the PARENT process -- exactly as an operator's
    # re-invocation would perform it.
    retried = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=mission,
        wp_id=_WP_ID,
        wp_slug=_WP_SLUG,
        body=body,
        reviewer_agent="reviewer-sigkill",
        verdict="rejected",
        commit_router=RealCoordCommitRouter(),
    )
    assert retried.artifact_path == artifact_path, (
        "an identical retry must adopt the exact retained record"
    )
    assert retried.artifact.cycle_number == 1
    assert retried.pointer == (
        f"review-cycle://{mission}/{_WP_SLUG}/{artifact_path.name}"
    )
    assert retried.review_result.reference == retried.pointer
    retried_rel = retried.artifact_path.relative_to(repo)
    show = subprocess.run(
        ["git", "show", f"HEAD:{retried_rel}"], cwd=repo, capture_output=True, text=True
    )
    assert show.returncode == 0, f"retry's write is not committed at HEAD: {show.stderr}"
    _assert_committed_frontmatter_has_no_verdict_key(show.stdout)
    assert body.strip() in show.stdout

    wp_dir = feature_dir / "tasks" / _WP_SLUG
    assert sorted(path.name for path in wp_dir.glob("review-cycle-*.md")) == [
        "review-cycle-1.md"
    ], "identical adoption must not allocate a duplicate cycle"
    latest = ReviewCycleArtifact.latest(wp_dir)
    assert latest is not None and latest.cycle_number == retried.artifact.cycle_number, (
        f"expected the retry ({retried.artifact.cycle_number}) to be the "
        f"reader-visible latest, got {latest!r}"
    )

    # A non-identical retry must not adopt the retained record. It allocates
    # a distinct cycle under the same lock (or production would conflate two
    # different reviewer submissions).
    distinct_body = "A genuinely different retry body.\n"
    distinct = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=mission,
        wp_id=_WP_ID,
        wp_slug=_WP_SLUG,
        body=distinct_body,
        reviewer_agent="reviewer-sigkill",
        verdict="rejected",
        commit_router=RealCoordCommitRouter(),
    )
    assert distinct.artifact_path != artifact_path
    assert distinct.artifact.cycle_number == 2
    assert distinct.review_result.reference == distinct.pointer
    distinct_rel = distinct.artifact_path.relative_to(repo).as_posix()
    _assert_exact_blob_at_ref(repo, "main", distinct_rel)
    assert sorted(path.name for path in wp_dir.glob("review-cycle-*.md")) == [
        "review-cycle-1.md",
        "review-cycle-2.md",
    ]


# ---------------------------------------------------------------------------
# SC-004 -- real multi-process concurrency bar (>= 50 iterations, 2 processes)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Sc004Request:
    round_id: int
    wp_id: str
    body: str


@dataclass(frozen=True)
class _Sc004Result:
    round_id: int
    reviewer: str
    exit_code: int
    payload: dict[str, Any] | None
    output: str
    elapsed_seconds: float
    seam_hits: tuple[str, ...]


@dataclass(frozen=True)
class _Sc004Ready:
    reviewer: str
    pid: int


_SC004_OUTPUT_DIAGNOSTIC_LIMIT = 2_000


def _sc004_json(output: str) -> dict[str, Any] | None:
    """Return the command's final JSON object without trusting its contents."""
    for line in reversed(output.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


@contextmanager
def _sc004_tracked_unlocked(
    hits: list[str], label: str, *_args: Any, **_kwargs: Any
) -> Iterator[None]:
    """Mutation seam: record use while deliberately providing no exclusion."""
    hits.append(f"lock:{label}")
    yield


def _sc004_worker(  # noqa: C901 - one child-local fault-injection boundary
    repo_text: str,
    mission: str,
    reviewer: str,
    requests: multiprocessing.Queue[_Sc004Request | None],
    results: multiprocessing.Queue[_Sc004Result],
    ready: multiprocessing.Queue[_Sc004Ready],
    mode: str,
    captured_self: Any = None,
    captured_peer: Any = None,
    release_self: Any = None,
    at_commit: Any = None,
    release_commit: Any = None,
    real_topology: bool = False,
) -> None:
    """Persistent, spawn-pickleable worker driving the literal Typer command.

    All fault injection is installed in the child so spawn cannot accidentally
    inherit a parent-only patch.  The worker never calls the review-cycle writer
    or status store directly.
    """
    repo = Path(repo_text)
    runner = CliRunner()
    ready.put(_Sc004Ready(reviewer=reviewer, pid=os.getpid()))
    while True:
        request = requests.get()
        if request is None:
            return
        hits: list[str] = []
        feedback = repo / ".sc004-inputs" / f"{request.wp_id}-{reviewer}.md"
        feedback.parent.mkdir(parents=True, exist_ok=True)
        feedback.write_text(request.body, encoding="utf-8")
        start = time.monotonic()
        with ExitStack() as stack:
            if real_topology:
                os.chdir(repo)
                stack.enter_context(
                    patch.dict(os.environ, {"SPECIFY_REPO_ROOT": str(repo)})
                )
            else:
                stack.enter_context(
                    setup_mocked_env(
                        repo,
                        mission_slug=mission,
                        target_branch="main",
                        auto_commit_default=True,
                        extra_patches=dict(_REVIEW_GATE_BYPASS),
                    )
                )
            stack.enter_context(patch("specify_cli.status.emit._saas_fan_out"))

            if mode == "commit_mutant":
                def fake_commit(
                    _router: Any, *_args: Any, _hits: list[str] = hits, **_kwargs: Any
                ) -> CommitArtifactResult:
                    _hits.append("evidence_commit")
                    return CommitArtifactResult(
                        status="committed", placement_ref="main", commit_hash="fabricated"
                    )

                stack.enter_context(
                    patch.object(RealCoordCommitRouter, "commit_artifact", fake_commit)
                )
            elif mode == "hold_commit":
                original_commit = RealCoordCommitRouter.commit_artifact

                def held_commit(
                    router: Any,
                    *args: Any,
                    _hits: list[str] = hits,
                    _original: Any = original_commit,
                    **kwargs: Any,
                ) -> CommitArtifactResult:
                    _hits.append("evidence_commit")
                    if at_commit is not None:
                        at_commit.set()
                    if release_commit is not None and not release_commit.wait(9):
                        raise TimeoutError("test hold exceeded nine seconds")
                    return _original(router, *args, **kwargs)

                stack.enter_context(
                    patch.object(RealCoordCommitRouter, "commit_artifact", held_commit)
                )
            elif mode == "event_mutant":
                lock_targets = (
                    "specify_cli.cli.commands.agent.tasks.feature_status_lock",
                    "specify_cli.status.emit.feature_status_lock",
                    "specify_cli.coordination.transaction.feature_status_lock",
                )
                for target in lock_targets:
                    label = target.rsplit(".", 2)[-2]
                    stack.enter_context(
                        patch(
                            target,
                            lambda *args, _label=label, _hits=hits, **kwargs: _sc004_tracked_unlocked(
                                _hits, _label, *args, **kwargs
                            ),
                        )
                    )
                from specify_cli.status import store as status_store

                original_replace = status_store.os.replace
                first_replace = True

                def ordered_replace(
                    source: Any,
                    destination: Any,
                    _original: Any = original_replace,
                    _hits: list[str] = hits,
                ) -> None:
                    nonlocal first_replace
                    destination_path = Path(destination)
                    if first_replace and destination_path.name == "status.events.jsonl":
                        first_replace = False
                        _hits.append("staged_event_replace")
                        captured_self.set()
                        if not captured_peer.wait(9):
                            raise TimeoutError("peer did not stage its stale event replacement")
                        if release_self is not None and not release_self.wait(9):
                            raise TimeoutError("stale writer was not released")
                        _hits.append("released_replace")
                    _original(source, destination)

                stack.enter_context(
                    patch.object(status_store.os, "replace", ordered_replace)
                )

            result = runner.invoke(
                agent_app,
                [
                    "tasks",
                    "move-task",
                    request.wp_id,
                    "--to",
                    "planned",
                    "--mission",
                    mission,
                    "--agent",
                    reviewer,
                    "--reviewer",
                    reviewer,
                    "--review-feedback-file",
                    str(feedback),
                    "--auto-commit",
                    "--json",
                ],
                catch_exceptions=True,
            )
        output = result.output
        if result.exception is not None:
            output += f"\nexception={result.exception!r}"
        results.put(
            _Sc004Result(
                round_id=request.round_id,
                reviewer=reviewer,
                exit_code=result.exit_code,
                payload=_sc004_json(result.output),
                output=output,
                elapsed_seconds=time.monotonic() - start,
                seam_hits=tuple(hits),
            )
        )


def _sc004_seed(repo: Path, mission: str, count: int) -> list[str]:
    _init_repo(repo)
    wp_ids = [f"WP{i + 100:03d}" for i in range(count)]
    feature_dir: Path | None = None
    for index, wp_id in enumerate(wp_ids):
        feature_dir, _ = _build_wp_file(repo, mission, wp_id)
        _seed_wp_event(feature_dir, wp_id, "in_review", seq=index)
    assert feature_dir is not None
    _write_lanes_json(feature_dir, mission, wp_ids[0])
    lanes_path = feature_dir / "lanes.json"
    lanes = json.loads(lanes_path.read_text(encoding="utf-8"))
    lanes["lanes"][0]["wp_ids"] = wp_ids
    lanes_path.write_text(json.dumps(lanes, indent=2), encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed SC-004 WPs"], cwd=repo, check=True, capture_output=True)
    _unprotect_main(repo)
    return wp_ids


def _sc004_start_workers(
    ctx: multiprocessing.context.SpawnContext,
    repo: Path,
    mission: str,
    *,
    mode: str,
    sync: tuple[tuple[Any, Any, Any], tuple[Any, Any, Any]] | None = None,
    commit_sync: tuple[tuple[Any, Any], tuple[Any, Any]] | None = None,
    real_topology: bool = False,
) -> tuple[list[Any], list[Any], Any]:
    inputs = [ctx.Queue(), ctx.Queue()]
    output = ctx.Queue()
    ready = ctx.Queue()
    processes = []
    for role, reviewer in enumerate(("reviewer-a", "reviewer-b")):
        captured_self, captured_peer, release_self = sync[role] if sync else (None, None, None)
        at_commit, release_commit = commit_sync[role] if commit_sync else (None, None)
        process = ctx.Process(
            target=_sc004_worker,
            args=(
                str(repo), mission, reviewer, inputs[role], output, ready, mode,
                captured_self, captured_peer, release_self, at_commit, release_commit,
                real_topology,
            ),
        )
        process.start()
        processes.append(process)
    readiness: list[_Sc004Ready] = []
    try:
        for _ in processes:
            readiness.append(ready.get(timeout=30))
    except Empty as exc:
        process_state = [
            {"pid": process.pid, "alive": process.is_alive(), "exit": process.exitcode}
            for process in processes
        ]
        raise AssertionError(
            "spawn workers did not complete readiness handshake: "
            f"ready={readiness!r}, processes={process_state!r}"
        ) from exc
    assert {item.reviewer for item in readiness} == {"reviewer-a", "reviewer-b"}, (
        f"invalid spawn readiness handshake: {readiness!r}"
    )
    assert all(item.pid > 0 for item in readiness), readiness
    return processes, inputs, output


def _sc004_stop(processes: list[Any], inputs: list[Any]) -> None:
    for input_queue in inputs:
        input_queue.put(None)
    for process in processes:
        process.join(timeout=15)
        assert not process.is_alive(), f"spawn worker hung: pid={process.pid}"
        assert process.exitcode == 0, f"spawn worker crashed: pid={process.pid}, exit={process.exitcode}"


def _sc004_get_pair(output: Any, round_id: int) -> list[_Sc004Result]:
    results: list[_Sc004Result] = []
    deadline = time.monotonic() + 30
    try:
        while len(results) < 2:
            results.append(output.get(timeout=max(0.01, deadline - time.monotonic())))
    except Empty as exc:
        raise AssertionError(
            f"round {round_id}: timed out waiting for spawned workers; "
            f"partial child results:\n{_sc004_pair_diagnostics(results)}"
        ) from exc
    assert {result.round_id for result in results} == {round_id}, (
        f"round {round_id}: received mismatched child results:\n"
        f"{_sc004_pair_diagnostics(results)}"
    )
    return results


def _sc004_event_mutant_first_result(
    output: Any,
    round_id: int,
    processes: Sequence[Any],
    captured_a: Any,
    captured_b: Any,
) -> _Sc004Result:
    """Wait causally for writer A, then prove both stale preimages existed."""
    try:
        first = output.get(timeout=30)
    except Empty as exc:
        process_state = [
            {"pid": process.pid, "alive": process.is_alive(), "exit": process.exitcode}
            for process in processes
        ]
        raise AssertionError(
            f"round {round_id}: timed out waiting for the first event-mutant result; "
            f"processes={process_state!r}"
        ) from exc

    assert isinstance(first, _Sc004Result), repr(first)
    process_state = [
        {"pid": process.pid, "alive": process.is_alive(), "exit": process.exitcode}
        for process in processes
    ]
    diagnostics = (
        f"child result:\n{_sc004_pair_diagnostics([first])}\n"
        f"processes={process_state!r}"
    )
    assert first.round_id == round_id, diagnostics
    assert captured_a.is_set() and captured_b.is_set(), (
        "writer A returned before both stale event preimages were captured; " + diagnostics
    )
    assert first.reviewer == "reviewer-a", diagnostics
    return first


def _sc004_bounded_output(output: str) -> str:
    if len(output) <= _SC004_OUTPUT_DIAGNOSTIC_LIMIT:
        return output
    half = _SC004_OUTPUT_DIAGNOSTIC_LIMIT // 2
    omitted = len(output) - (half * 2)
    return f"{output[:half]}\n... <{omitted} chars omitted> ...\n{output[-half:]}"


def _sc004_pair_diagnostics(results: Sequence[_Sc004Result]) -> str:
    """Project complete but bounded child evidence for hosted failures."""
    projected = [
        {
            "reviewer": result.reviewer,
            "exit_code": result.exit_code,
            "payload": result.payload,
            "elapsed_seconds": round(result.elapsed_seconds, 6),
            "seam_hits": list(result.seam_hits),
            "output": _sc004_bounded_output(result.output),
        }
        for result in results
    ]
    return json.dumps(projected, indent=2, sort_keys=True, default=repr)


def _sc004_pointer_path(repo: Path, mission: str, pointer: str) -> Path:
    prefix = f"review-cycle://{mission}/"
    assert pointer.startswith(prefix), f"unstable evidence pointer: {pointer!r}"
    return repo / "kitty-specs" / mission / "tasks" / pointer[len(prefix):]


def _sc004_error_payload(result: _Sc004Result) -> dict[str, Any] | None:
    """Return only a structured repository refusal envelope."""
    if result.exit_code == 0 or not isinstance(result.payload, dict):
        return None
    if result.payload.get("result") not in {"error", "refused", "failure"}:
        return None
    error = result.payload.get("error")
    if isinstance(error, dict):
        return error
    return result.payload


def _sc004_refusal_kind(
    result: _Sc004Result,
    *,
    authoritative_lane: str,
    requested_lane: str,
) -> str | None:
    """Validate the allowlisted refusal shapes and their causal evidence."""
    error = _sc004_error_payload(result)
    if error is None:
        return None
    payload = result.payload or {}
    if payload.get("verdict_durably_persisted") is True:
        return None
    if payload.get("durability_classification") == "busy":
        if (
            payload.get("result") != "error"
            or payload.get("durability_reason") != "verdict_save_busy"
            or payload.get("verdict_durably_persisted") is not False
            or payload.get("evidence_ref") is not None
            or payload.get("destination_ref") is not None
            or "event_id" in payload
            or result.elapsed_seconds < 9.5
        ):
            return None
        return "busy"
    if payload.get("durability_classification") == "persistence_failed":
        if (
            payload.get("durability_reason") != "destination_readback_missing"
            or payload.get("verdict_durably_persisted") is not False
            or not isinstance(payload.get("evidence_ref"), str)
            or not isinstance(payload.get("destination_ref"), str)
        ):
            return None
        return "persistence_failed"
    code_value = error.get("code", error.get("error_code", error.get("reason")))
    if not isinstance(code_value, str):
        return None
    code = code_value.lower()
    if code == "ownership_refusal":
        current_lane = error.get("current_lane")
        target_lane = error.get("requested_lane")
        assigned_agent = error.get("assigned_agent")
        requesting_agent = error.get("requesting_agent")
        if (
            payload.get("result") != "error"
            or current_lane != authoritative_lane
            or target_lane != requested_lane
            or not isinstance(assigned_agent, str)
            or not assigned_agent
            or requesting_agent != result.reviewer
            or assigned_agent == requesting_agent
            or payload.get("verdict_durably_persisted") is not False
            or "evidence_ref" not in payload
            or payload.get("evidence_ref") is not None
            or "destination_ref" not in payload
            or payload.get("destination_ref") is not None
            or "event_id" in payload
        ):
            return None
        return "ownership_refusal"
    if code in {"invalid_transition", "state_refusal"}:
        current_lane = error.get("current_lane")
        target_lane = error.get("requested_lane")
        if current_lane != authoritative_lane or target_lane != requested_lane:
            return None
        legal, _reason = validate_transition(str(current_lane), str(target_lane))
        return None if legal else "state_refusal"
    return None


def _sc004_refusal_left_no_authority(
    repo: Path,
    mission: str,
    expected: dict[str, tuple[str, str]],
    result: _Sc004Result,
    events: Sequence[StatusEvent],
) -> bool:
    """Independently prove a refused reviewer emitted neither authority."""
    expected_wp, expected_body = expected[result.reviewer]
    current_events = [event for event in events if event.wp_id == expected_wp]
    if not current_events:
        return False
    if any(
        event.review_result is not None
        and event.review_result.reviewer == result.reviewer
        for event in current_events
    ):
        return False

    wp_dir = repo / "kitty-specs" / mission / "tasks" / f"{expected_wp}-test"
    for path in wp_dir.glob("review-cycle-*.md"):
        artifact = ReviewCycleArtifact.from_file(path)
        if artifact.reviewer_agent == result.reviewer or artifact.body == expected_body:
            return False

    governed_ref = placement_seam(repo, mission).write_target(
        MissionArtifactKind.REVIEW_CYCLE
    ).ref
    relative_wp_dir = wp_dir.relative_to(repo).as_posix()
    listed = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", governed_ref, "--", relative_wp_dir],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if listed.returncode != 0:
        return False
    reviewer_line = f"reviewer_agent: {result.reviewer}"
    for relative_path in listed.stdout.splitlines():
        if not relative_path.endswith(".md"):
            continue
        shown = subprocess.run(
            ["git", "show", f"{governed_ref}:{relative_path}"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        if shown.returncode != 0:
            return False
        if reviewer_line in shown.stdout or expected_body.strip() in shown.stdout:
            return False
    return True


def _sc004_busy_refusal_is_causal(
    repo: Path,
    mission: str,
    expected: dict[str, tuple[str, str]],
    result: _Sc004Result,
    events: Sequence[StatusEvent],
) -> bool:
    """Prove a typed queue timeout emitted neither authority for its reviewer."""
    expected_wp = expected[result.reviewer][0]
    current_events = [event for event in events if event.wp_id == expected_wp]
    if not current_events or (
        _sc004_refusal_kind(
            result,
            authoritative_lane=current_events[-1].to_lane.value,
            requested_lane=Lane.PLANNED.value,
        )
        != "busy"
    ):
        return False
    return _sc004_refusal_left_no_authority(repo, mission, expected, result, events)


def _sc004_ownership_refusal_is_causal(
    repo: Path,
    mission: str,
    expected: dict[str, tuple[str, str]],
    result: _Sc004Result,
    events: Sequence[StatusEvent],
) -> bool:
    """Prove a typed ownership refusal and absence of both verdict authorities."""
    expected_wp = expected[result.reviewer][0]
    current_events = [event for event in events if event.wp_id == expected_wp]
    if not current_events or (
        _sc004_refusal_kind(
            result,
            authoritative_lane=current_events[-1].to_lane.value,
            requested_lane=Lane.PLANNED.value,
        )
        != "ownership_refusal"
    ):
        return False
    return _sc004_refusal_left_no_authority(repo, mission, expected, result, events)


def _sc004_state_refusal_is_causal(
    repo: Path,
    mission: str,
    expected: dict[str, tuple[str, str]],
    result: _Sc004Result,
    events: Sequence[StatusEvent],
) -> bool:
    """Prove a typed invalid-transition refusal emitted neither authority."""
    expected_wp = expected[result.reviewer][0]
    current_events = [event for event in events if event.wp_id == expected_wp]
    if not current_events or (
        _sc004_refusal_kind(
            result,
            authoritative_lane=current_events[-1].to_lane.value,
            requested_lane=Lane.PLANNED.value,
        )
        != "state_refusal"
    ):
        return False
    return _sc004_refusal_left_no_authority(repo, mission, expected, result, events)


def _sc004_missing_evidence_refusal(
    repo: Path,
    mission: str,
    expected: dict[str, tuple[str, str]],
    result: _Sc004Result,
    events: Sequence[StatusEvent],
) -> bool:
    """Prove the canonical fail-closed envelope against both authorities."""
    expected_wp, expected_body = expected[result.reviewer]
    current_events = [event for event in events if event.wp_id == expected_wp]
    if not current_events:
        return False
    if (
        _sc004_refusal_kind(
            result,
            authoritative_lane=current_events[-1].to_lane.value,
            requested_lane=Lane.PLANNED.value,
        )
        != "persistence_failed"
    ):
        return False
    payload = result.payload or {}
    evidence_ref = payload.get("evidence_ref")
    destination_ref = payload.get("destination_ref")
    governed_ref = placement_seam(repo, mission).write_target(
        MissionArtifactKind.REVIEW_CYCLE
    ).ref
    expected_prefix = f"kitty-specs/{mission}/tasks/{expected_wp}-test/review-cycle-"
    if (
        not isinstance(evidence_ref, str)
        or not evidence_ref.startswith(expected_prefix)
        or not evidence_ref.endswith(".md")
        or destination_ref != governed_ref
    ):
        return False
    retained = repo / evidence_ref
    if not retained.is_file():
        return False
    retained_text = retained.read_text(encoding="utf-8")
    if (
        f"reviewer_agent: {result.reviewer}" not in retained_text
        or expected_body.strip() not in retained_text
    ):
        return False
    shown = subprocess.run(
        ["git", "show", f"{governed_ref}:{evidence_ref}"],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    if shown.returncode == 0:
        return False
    return not any(
        event.review_result is not None
        and event.review_result.reviewer == result.reviewer
        for event in current_events
    )


def _sc004_committed_evidence(
    repo: Path,
    mission: str,
    expected: dict[str, tuple[str, str]],
    result: _Sc004Result,
) -> tuple[str, str | None]:
    """Inspect one claimed success's governed-ref evidence without reading events."""
    payload = result.payload or {}
    if (
        result.exit_code != 0
        or payload.get("result") != "success"
        or payload.get("verdict_durably_persisted") is not True
    ):
        return "not_durable_success", None
    pointer = payload.get("review_feedback")
    if not isinstance(pointer, str):
        return "missing_evidence_pointer", None
    evidence_path = _sc004_pointer_path(repo, mission, pointer)
    target_ref = placement_seam(repo, mission).write_target(
        MissionArtifactKind.REVIEW_CYCLE
    ).ref
    shown = subprocess.run(
        ["git", "show", f"{target_ref}:{evidence_path.relative_to(repo).as_posix()}"],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    if shown.returncode != 0:
        return "missing_committed_evidence", pointer
    local_bytes = evidence_path.read_bytes()
    if shown.stdout != local_bytes:
        return "committed_evidence_mismatch", pointer
    artifact = ReviewCycleArtifact.from_file(evidence_path)
    expected_wp, expected_body = expected[result.reviewer]
    if (
        artifact.wp_id != expected_wp
        or artifact.reviewer_agent != result.reviewer
        or artifact.body != expected_body
    ):
        return "committed_evidence_mismatch", pointer
    return "committed_evidence", pointer


def _sc004_complete_evidence_leg(
    repo: Path,
    mission: str,
    expected: dict[str, tuple[str, str]],
    results: list[_Sc004Result],
) -> str:
    """Require two distinct, matching committed blobs independently of events."""
    if len(results) != 2:
        return "not_two_results"
    inspections = [
        _sc004_committed_evidence(repo, mission, expected, result)
        for result in results
    ]
    failures = [
        classification
        for classification, _pointer in inspections
        if classification != "committed_evidence"
    ]
    if failures:
        return failures[0]
    pointers = [pointer for _classification, pointer in inspections]
    if None in pointers or len(set(pointers)) != 2:
        return "duplicate_evidence_pointer"
    return "committed_evidence"


def _sc004_evidence_mutant_classification(
    repo: Path,
    mission: str,
    expected: dict[str, tuple[str, str]],
    results: list[_Sc004Result],
) -> str:
    """Recognise external liar detection or production's structured refusal."""
    events = read_events(
        placement_seam(repo, mission).read_dir(MissionArtifactKind.STATUS_STATE)
    )
    saw_expected_protection = False
    for result in results:
        if result.exit_code == 0 and (result.payload or {}).get("result") == "success":
            evidence_class, _pointer = _sc004_committed_evidence(
                repo, mission, expected, result
            )
            if evidence_class == "missing_committed_evidence":
                saw_expected_protection = True
                continue
            return evidence_class
        if not _sc004_missing_evidence_refusal(
            repo, mission, expected, result, events
        ):
            return "unproven_refusal"
        saw_expected_protection = True
    return "missing_committed_evidence" if saw_expected_protection else "unproven_mutant"


def _sc004_refusal_is_causal(
    kind: str,
    repo: Path,
    mission: str,
    expected: dict[str, tuple[str, str]],
    result: _Sc004Result,
    events: Sequence[StatusEvent],
) -> bool:
    """Dispatch an already-typed refusal to its independent causal proof."""
    if kind == "busy":
        return _sc004_busy_refusal_is_causal(repo, mission, expected, result, events)
    if kind == "ownership_refusal":
        return _sc004_ownership_refusal_is_causal(
            repo, mission, expected, result, events
        )
    if kind == "persistence_failed":
        return _sc004_missing_evidence_refusal(
            repo, mission, expected, result, events
        )
    if kind == "state_refusal":
        return _sc004_state_refusal_is_causal(repo, mission, expected, result, events)
    return False


def _sc004_oracle(
    repo: Path,
    mission: str,
    expected: dict[str, tuple[str, str]],
    results: list[_Sc004Result],
    *,
    event_feature_dir: Path | None = None,
) -> str:
    """Independently verify exact event IDs and governed-ref evidence blobs."""
    authoritative_status_dir = event_feature_dir or placement_seam(repo, mission).read_dir(
        MissionArtifactKind.STATUS_STATE
    )
    events = read_events(authoritative_status_dir)
    successes = [
        result for result in results
        if result.exit_code == 0
        and result.payload is not None
        and result.payload.get("result") == "success"
    ]
    if len(successes) != len(results):
        refusals = [result for result in results if result not in successes]
        if not successes:
            try:
                first_refusal, second_refusal = refusals
            except ValueError:
                return "unclassified_command_outcome"
            protected_refusals = [
                _sc004_missing_evidence_refusal(
                    repo, mission, expected, refusal, events
                )
                for refusal in (first_refusal, second_refusal)
            ]
            return (
                "missing_committed_evidence"
                if all(protected_refusals)
                else "unproven_refusal"
            )
        if len(successes) != 1 or len(refusals) != 1:
            return "unclassified_command_outcome"
        refusal = refusals[0]
        expected_wp = expected[refusal.reviewer][0]
        current_events = [event for event in events if event.wp_id == expected_wp]
        if not current_events:
            return "unproven_refusal"
        refusal_kind = _sc004_refusal_kind(
            refusal,
            authoritative_lane=current_events[-1].to_lane.value,
            requested_lane=Lane.PLANNED.value,
        )
        if refusal_kind is None:
            return "unproven_refusal"
        if not _sc004_refusal_is_causal(
            refusal_kind, repo, mission, expected, refusal, events
        ):
            return "unproven_refusal"
    pointers: list[str] = []
    for result in successes:
        payload = result.payload or {}
        if payload.get("verdict_durably_persisted") is not True:
            return "false_durability_success"
        event_id = payload.get("event_id")
        pointer = payload.get("review_feedback")
        matches = [event for event in events if event.event_id == event_id]
        if len(matches) != 1:
            return "missing_authoritative_event"
        event = matches[0]
        expected_wp, _expected_body = expected[result.reviewer]
        review = event.review_result
        if (
            event.mission_slug != mission
            or event.wp_id != expected_wp
            or review is None
            or review.reviewer != result.reviewer
            or review.verdict != "changes_requested"
            or review.reference != pointer
        ):
            return (
                "authoritative_event_mismatch:"
                f"event=({event.mission_slug},{event.wp_id},{review!r});"
                f"expected=({mission},{expected_wp},{result.reviewer},changes_requested,{pointer})"
            )
        evidence_class, evidence_pointer = _sc004_committed_evidence(
            repo, mission, expected, result
        )
        if evidence_class != "committed_evidence":
            return evidence_class
        assert evidence_pointer == pointer
        pointers.append(pointer)
    if len(pointers) != len(set(pointers)):
        return "duplicate_evidence_pointer"
    return "durable" if len(successes) == 2 else "durable_with_valid_refusal"


def _sc004_synthetic_result(
    *,
    exit_code: int,
    payload: dict[str, Any] | None,
    reviewer: str = "reviewer-b",
    output: str = "",
    elapsed_seconds: float = 10.0,
) -> _Sc004Result:
    return _Sc004Result(
        round_id=0,
        reviewer=reviewer,
        exit_code=exit_code,
        payload=payload,
        output=output,
        elapsed_seconds=elapsed_seconds,
        seam_hits=(),
    )


@pytest.mark.fast
def test_sc004_refusal_oracle_rejects_noncausal_shapes() -> None:
    """Broad text and exit-zero/malformed failures never become refusals."""
    invalid = (
        _sc004_synthetic_result(
            exit_code=0,
            payload={
                "result": "error",
                "error": {"code": "busy", "timeout_seconds": 10},
            },
        ),
        _sc004_synthetic_result(exit_code=1, payload=None),
        _sc004_synthetic_result(
            exit_code=1,
            payload={"result": "error", "error": "state transition busy timeout"},
        ),
        _sc004_synthetic_result(
            exit_code=1,
            payload={"result": "error", "error": {"code": "worker_exception"}},
            output="unrelated exception while reading transition state",
        ),
        _sc004_synthetic_result(
            exit_code=1,
            payload={
                "result": "error",
                "error": {"code": "busy", "timeout_seconds": 10},
            },
            elapsed_seconds=10.0,
        ),
        _sc004_synthetic_result(
            exit_code=1,
            payload={
                "result": "error",
                "verdict_durably_persisted": False,
                "durability_classification": "busy",
                "durability_reason": "verdict_save_busy",
                "evidence_ref": None,
                "destination_ref": None,
            },
            elapsed_seconds=0.1,
        ),
        _sc004_synthetic_result(
            exit_code=1,
            payload={
                "result": "error",
                "error": "destination readback missing",
                "verdict_durably_persisted": False,
            },
        ),
        _sc004_synthetic_result(
            exit_code=1,
            payload={
                "result": "error",
                "error": "evidence failure",
                "verdict_durably_persisted": False,
                "durability_classification": "persistence_failed",
                "durability_reason": "destination_readback_mismatch",
                "evidence_ref": "kitty-specs/m/tasks/WP-test/review-cycle-1.md",
                "destination_ref": "main",
            },
        ),
        _sc004_synthetic_result(
            exit_code=1,
            payload={
                "result": "error",
                "code": "ownership_refusal",
                "current_lane": "planned",
                "requested_lane": "planned",
                "assigned_agent": "reviewer-b",
                "requesting_agent": "reviewer-a",
                "verdict_durably_persisted": False,
                "evidence_ref": None,
                "destination_ref": None,
                "event_id": "fabricated-event",
            },
        ),
        _sc004_synthetic_result(
            exit_code=1,
            payload={
                "result": "error",
                "code": "ownership_refusal",
                "current_lane": "planned",
                "requested_lane": "planned",
                "assigned_agent": "reviewer-a",
                "requesting_agent": "reviewer-b",
                "verdict_durably_persisted": False,
                "destination_ref": None,
            },
        ),
        _sc004_synthetic_result(
            exit_code=1,
            payload={
                "result": "error",
                "code": "ownership_refusal",
                "current_lane": "planned",
                "requested_lane": "planned",
                "assigned_agent": "reviewer-a",
                "requesting_agent": "reviewer-b",
                "verdict_durably_persisted": False,
                "evidence_ref": None,
            },
        ),
        _sc004_synthetic_result(
            exit_code=1,
            payload={
                "result": "error",
                "code": "ownership_refusal",
                "current_lane": "planned",
                "requested_lane": "planned",
                "assigned_agent": "reviewer-a",
                "requesting_agent": "reviewer-b",
                "verdict_durably_persisted": False,
            },
        ),
    )
    assert all(
        _sc004_refusal_kind(
            result,
            authoritative_lane=Lane.PLANNED.value,
            requested_lane=Lane.PLANNED.value,
        )
        is None
        for result in invalid
    )

    busy = _sc004_synthetic_result(
        exit_code=1,
        payload={
            "result": "error",
            "verdict_durably_persisted": False,
            "durability_classification": "busy",
            "durability_reason": "verdict_save_busy",
            "evidence_ref": None,
            "destination_ref": None,
        },
        elapsed_seconds=10.0,
    )
    state = _sc004_synthetic_result(
        exit_code=1,
        payload={
            "result": "refused",
            "error": {
                "code": "invalid_transition",
                "current_lane": "planned",
                "requested_lane": "planned",
            },
        },
    )
    persistence = _sc004_synthetic_result(
        exit_code=1,
        payload={
            "result": "error",
            "error": "exact evidence bytes were not verified",
            "verdict_durably_persisted": False,
            "durability_classification": "persistence_failed",
            "durability_reason": "destination_readback_missing",
            "evidence_ref": "kitty-specs/m/tasks/WP-test/review-cycle-1.md",
            "destination_ref": "main",
        },
    )
    ownership = _sc004_synthetic_result(
        exit_code=1,
        reviewer="reviewer-a",
        payload={
            "result": "error",
            "code": "ownership_refusal",
            "error": "Agent mismatch",
            "current_lane": "planned",
            "requested_lane": "planned",
            "assigned_agent": "reviewer-b",
            "requesting_agent": "reviewer-a",
            "verdict_durably_persisted": False,
            "evidence_ref": None,
            "destination_ref": None,
        },
    )
    assert _sc004_refusal_kind(
        busy,
        authoritative_lane="planned",
        requested_lane="planned",
    ) == "busy"
    assert _sc004_refusal_kind(
        state,
        authoritative_lane="planned",
        requested_lane="planned",
    ) == "state_refusal"
    assert _sc004_refusal_kind(
        persistence,
        authoritative_lane="in_review",
        requested_lane="planned",
    ) == "persistence_failed"
    assert _sc004_refusal_kind(
        ownership,
        authoritative_lane="planned",
        requested_lane="planned",
    ) == "ownership_refusal"


@pytest.mark.integration
@pytest.mark.git_repo
def test_sc004_ownership_refusal_requires_independent_event_and_evidence_absence(
    tmp_path: Path,
) -> None:
    mission = "sc004-ownership-refusal"
    wp_id = _sc004_seed(tmp_path, mission, 1)[0]
    expected = {"reviewer-b": (wp_id, "Refused reviewer body.\n")}
    ownership = _sc004_synthetic_result(
        exit_code=1,
        reviewer="reviewer-b",
        payload={
            "result": "error",
            "code": "ownership_refusal",
            "error": "Agent mismatch",
            "current_lane": "in_review",
            "requested_lane": "planned",
            "assigned_agent": "reviewer-a",
            "requesting_agent": "reviewer-b",
            "verdict_durably_persisted": False,
            "evidence_ref": None,
            "destination_ref": None,
        },
    )
    feature_dir = tmp_path / "kitty-specs" / mission
    events = read_events(feature_dir)
    assert _sc004_ownership_refusal_is_causal(
        tmp_path, mission, expected, ownership, events
    )

    artifact_path = feature_dir / "tasks" / f"{wp_id}-test" / "review-cycle-1.md"
    ReviewCycleArtifact(
        cycle_number=1,
        wp_id=wp_id,
        mission_slug=mission,
        reviewer_agent="reviewer-b",
        reviewed_at="2026-08-24T00:00:00Z",
        body=expected["reviewer-b"][1],
    ).write(artifact_path)
    assert not _sc004_ownership_refusal_is_causal(
        tmp_path, mission, expected, ownership, events
    ), "an ownership refusal cannot hide reviewer evidence in the working tree"


@pytest.mark.integration
@pytest.mark.git_repo
def test_sc004_busy_refusal_requires_independent_event_and_evidence_absence(
    tmp_path: Path,
) -> None:
    mission = "sc004-busy-refusal"
    wp_id = _sc004_seed(tmp_path, mission, 1)[0]
    expected = {"reviewer-b": (wp_id, "Timed-out reviewer body.\n")}
    busy = _sc004_synthetic_result(
        exit_code=1,
        payload={
            "result": "error",
            "verdict_durably_persisted": False,
            "durability_classification": "busy",
            "durability_reason": "verdict_save_busy",
            "evidence_ref": None,
            "destination_ref": None,
        },
        elapsed_seconds=9.75,
    )
    feature_dir = tmp_path / "kitty-specs" / mission
    events = read_events(feature_dir)
    assert _sc004_busy_refusal_is_causal(tmp_path, mission, expected, busy, events)

    artifact_path = (
        feature_dir / "tasks" / f"{wp_id}-test" / "review-cycle-1.md"
    )
    ReviewCycleArtifact(
        cycle_number=1,
        wp_id=wp_id,
        mission_slug=mission,
        reviewer_agent="reviewer-b",
        reviewed_at="2026-08-24T00:00:00Z",
        body=expected["reviewer-b"][1],
    ).write(artifact_path)
    assert not _sc004_busy_refusal_is_causal(
        tmp_path, mission, expected, busy, events
    ), "a busy envelope cannot hide reviewer evidence left in the working tree"

    event_repo = tmp_path / "event-present"
    event_repo.mkdir()
    event_wp = _sc004_seed(event_repo, mission, 1)[0]
    event_expected = {"reviewer-b": (event_wp, expected["reviewer-b"][1])}
    event_feature_dir = event_repo / "kitty-specs" / mission
    append_event(
        event_feature_dir,
        StatusEvent(
            event_id="01SC004BUSYREFUSAL000001",
            mission_slug=mission,
            wp_id=event_wp,
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.PLANNED,
            at="2026-08-24T00:00:01Z",
            actor="reviewer-b",
            force=True,
            execution_mode="worktree",
            review_result=ReviewResult(
                reviewer="reviewer-b",
                verdict="changes_requested",
                reference="review-cycle://unexpected",
            ),
        ),
    )
    assert not _sc004_busy_refusal_is_causal(
        event_repo,
        mission,
        event_expected,
        busy,
        read_events(event_feature_dir),
    ), "a busy envelope cannot hide a correlated authoritative event"


@pytest.mark.integration
def test_sc004_start_workers_waits_for_both_spawned_workers(tmp_path: Path) -> None:
    """The parent cannot start a causal clock before both children are ready."""
    ctx = multiprocessing.get_context("spawn")
    processes, inputs, _output = _sc004_start_workers(
        ctx,
        tmp_path,
        "sc004-readiness",
        mode="baseline",
    )
    try:
        first_process, second_process = processes
        assert all(
            process.is_alive() and process.exitcode is None
            for process in (first_process, second_process)
        )
    finally:
        _sc004_stop(processes, inputs)


@pytest.mark.fast
def test_sc004_pair_diagnostics_are_complete_and_output_bounded() -> None:
    result = _sc004_synthetic_result(
        exit_code=1,
        payload={
            "result": "error",
            "durability_classification": "busy",
            "durability_reason": "verdict_save_busy",
        },
        output="prefix-" + ("x" * 4_000) + "-suffix",
        elapsed_seconds=9.75,
    )
    projected = _sc004_pair_diagnostics([result])
    assert '"reviewer": "reviewer-b"' in projected
    assert '"exit_code": 1' in projected
    assert '"payload": {' in projected
    assert '"elapsed_seconds": 9.75' in projected
    assert '"seam_hits": []' in projected
    assert "prefix-" in projected and "-suffix" in projected
    assert "chars omitted" in projected
    assert len(projected) < 3_000


@pytest.mark.integration
@pytest.mark.git_repo
def test_sc004_two_concurrent_processes_never_clobber_a_verdict_over_50_iterations(
    tmp_path: Path,
) -> None:
    repo = tmp_path
    mission = "sc004-production-command"
    wp_ids = _sc004_seed(repo, mission, 51)
    ctx = multiprocessing.get_context("spawn")
    processes, inputs, output = _sc004_start_workers(ctx, repo, mission, mode="baseline")
    try:
        for round_id, wp_id in enumerate(wp_ids[:50]):
            expected = {
                "reviewer-a": (wp_id, f"Reviewer A feedback round {round_id}.\n"),
                "reviewer-b": (wp_id, f"Reviewer B feedback round {round_id}.\n"),
            }
            inputs[0].put(_Sc004Request(round_id, wp_id, expected["reviewer-a"][1]))
            inputs[1].put(_Sc004Request(round_id, wp_id, expected["reviewer-b"][1]))
            pair = _sc004_get_pair(output, round_id)
            verdict = _sc004_oracle(repo, mission, expected, pair)
            assert verdict in {"durable", "durable_with_valid_refusal"}, (
                f"round {round_id}: {verdict}; child results:\n"
                f"{_sc004_pair_diagnostics(pair)}"
            )
    finally:
        _sc004_stop(processes, inputs)

    # Deterministic same-WP wait-in-line witness. A is held inside the real
    # evidence commit; B must not reach that seam until A clears it, then both
    # production commands must return distinct durable pairs within ten seconds.
    a_at_commit, b_at_commit, release_a = ctx.Event(), ctx.Event(), ctx.Event()
    never_release = ctx.Event()
    processes, inputs, output = _sc004_start_workers(
        ctx,
        repo,
        mission,
        mode="hold_commit",
        commit_sync=((a_at_commit, release_a), (b_at_commit, never_release)),
    )
    wp_id = wp_ids[50]
    expected = {
        "reviewer-a": (wp_id, "Queue holder A.\n"),
        "reviewer-b": (wp_id, "Queue waiter B.\n"),
    }
    try:
        inputs[0].put(_Sc004Request(50, wp_id, expected["reviewer-a"][1]))
        assert a_at_commit.wait(5), "writer A never reached the production commit seam"
        inputs[1].put(_Sc004Request(50, wp_id, expected["reviewer-b"][1]))
        time.sleep(0.25)
        assert not b_at_commit.is_set(), "writer B did not wait behind writer A"
        release_a.set()
        assert b_at_commit.wait(5), "writer B did not win after writer A released"
        never_release.set()
        pair = _sc004_get_pair(output, 50)
        diagnostics = _sc004_pair_diagnostics(pair)
        assert _sc004_oracle(repo, mission, expected, pair) == "durable", diagnostics
        assert all(result.elapsed_seconds < 10 for result in pair), diagnostics
    finally:
        release_a.set()
        never_release.set()
        _sc004_stop(processes, inputs)


@pytest.mark.integration
@pytest.mark.git_repo
def test_sc004_event_serialization_mutant_reports_missing_authoritative_event(
    tmp_path: Path,
) -> None:
    repo = tmp_path
    mission = "sc004-event-mutant"
    wp_id = _sc004_seed(repo, mission, 1)[0]
    ctx = multiprocessing.get_context("spawn")
    captured_a, captured_b, release_b = ctx.Event(), ctx.Event(), ctx.Event()
    processes, inputs, output = _sc004_start_workers(
        ctx,
        repo,
        mission,
        mode="event_mutant",
        sync=((captured_a, captured_b, None), (captured_b, captured_a, release_b)),
    )
    expected = {
        "reviewer-a": (wp_id, "Event mutant A.\n"),
        "reviewer-b": (wp_id, "Event mutant B.\n"),
    }
    try:
        inputs[0].put(_Sc004Request(0, wp_id, expected["reviewer-a"][1]))
        inputs[1].put(_Sc004Request(0, wp_id, expected["reviewer-b"][1]))
        first = _sc004_event_mutant_first_result(
            output, 0, processes, captured_a, captured_b
        )
        release_b.set()
        second = output.get(timeout=30)
        pair = [first, second]
        diagnostics = _sc004_pair_diagnostics(pair)
        assert all(result.exit_code == 0 and result.payload for result in pair), diagnostics
        assert all("staged_event_replace" in result.seam_hits for result in pair), diagnostics
        assert all(
            {"lock:tasks", "lock:emit"}.issubset(result.seam_hits)
            for result in pair
        ), diagnostics
        assert _sc004_complete_evidence_leg(repo, mission, expected, pair) == (
            "committed_evidence"
        ), diagnostics
        assert _sc004_oracle(repo, mission, expected, pair) == (
            "missing_authoritative_event"
        ), diagnostics
    finally:
        release_b.set()
        _sc004_stop(processes, inputs)

    # Repeat through the canonical real coordination topology so mutation of
    # only the fallback command/emit bindings cannot make this control green.
    coord = _build_coord_topology(
        tmp_path / "coordination-transaction-mutant",
        write_husk_meta=False,
    )
    append_event(
        coord.coord_feature_dir,
        StatusEvent(
            event_id="01SC004COORDINREVIEW00001",
            mission_slug=coord.slug,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.IN_REVIEW,
            at="2026-08-23T18:00:00+00:00",
            actor="seed",
            force=True,
            execution_mode="worktree",
        ),
    )
    coord_root = coord.coord_feature_dir.parents[1]
    subprocess.run(["git", "add", "-A"], cwd=coord_root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "seed coord SC-004 review state"],
        cwd=coord_root,
        check=True,
        capture_output=True,
    )
    _unprotect_main(coord.repo)
    captured_a, captured_b, release_b = ctx.Event(), ctx.Event(), ctx.Event()
    processes, inputs, output = _sc004_start_workers(
        ctx,
        coord.repo,
        coord.slug,
        mode="event_mutant",
        sync=((captured_a, captured_b, None), (captured_b, captured_a, release_b)),
        real_topology=True,
    )
    coord_expected = {
        "reviewer-a": ("WP01", "Coord event mutant A.\n"),
        "reviewer-b": ("WP01", "Coord event mutant B.\n"),
    }
    try:
        inputs[0].put(_Sc004Request(1, "WP01", coord_expected["reviewer-a"][1]))
        inputs[1].put(_Sc004Request(1, "WP01", coord_expected["reviewer-b"][1]))
        first = _sc004_event_mutant_first_result(
            output, 1, processes, captured_a, captured_b
        )
        release_b.set()
        pair = [first, output.get(timeout=30)]
        diagnostics = _sc004_pair_diagnostics(pair)
        assert all(result.exit_code == 0 and result.payload for result in pair), diagnostics
        assert all(
            {"lock:tasks", "lock:transaction"}.issubset(result.seam_hits)
            for result in pair
        ), diagnostics
        assert (
            _sc004_complete_evidence_leg(
                coord.repo,
                coord.slug,
                coord_expected,
                pair,
            )
            == "committed_evidence"
        ), diagnostics
        assert (
            _sc004_oracle(
                coord.repo,
                coord.slug,
                coord_expected,
                pair,
                event_feature_dir=coord.coord_feature_dir,
            )
            == "missing_authoritative_event"
        ), diagnostics
    finally:
        release_b.set()
        _sc004_stop(processes, inputs)


@pytest.mark.integration
@pytest.mark.git_repo
def test_sc004_evidence_commit_mutant_reports_missing_committed_evidence(
    tmp_path: Path,
) -> None:
    repo = tmp_path
    mission = "sc004-evidence-mutant"
    wp_id = _sc004_seed(repo, mission, 1)[0]
    ctx = multiprocessing.get_context("spawn")
    processes, inputs, output = _sc004_start_workers(ctx, repo, mission, mode="commit_mutant")
    expected = {
        "reviewer-a": (wp_id, "Evidence mutant A.\n"),
        "reviewer-b": (wp_id, "Evidence mutant B.\n"),
    }
    try:
        inputs[0].put(_Sc004Request(0, wp_id, expected["reviewer-a"][1]))
        inputs[1].put(_Sc004Request(0, wp_id, expected["reviewer-b"][1]))
        pair = _sc004_get_pair(output, 0)
        diagnostics = _sc004_pair_diagnostics(pair)
        assert all("evidence_commit" in result.seam_hits for result in pair), diagnostics
        assert (
            _sc004_evidence_mutant_classification(repo, mission, expected, pair)
            == "missing_committed_evidence"
        ), diagnostics
        assert _sc004_oracle(repo, mission, expected, pair) == (
            "missing_committed_evidence"
        ), diagnostics
    finally:
        _sc004_stop(processes, inputs)


def _assert_durable_event_records_at_least(repo: Path, mission: str, wp_id: str, *, minimum: int) -> None:
    """SC-003/NFR-004 (WP05, T028, D-PLAN-13) re-pointed anchor: assert AT
    LEAST ``minimum`` distinct, durably-committed ``review_result`` event
    records exist for *wp_id* -- the authoritative durability count
    (``emit_status_transition``/``append_events_atomic_verified`` appends),
    never a count of best-effort ``review-cycle-N.md`` files or a clean git
    working tree (the property WP05's demote retires). Counts DISTINCT
    ``event_id``s carrying a ``review_result`` for this WP, read straight
    from the on-disk event log (not the reducer's collapsed per-WP slot,
    which only ever keeps the LATEST) so a dropped/missing append is
    detectable even when a later one overwrites the reducer's view.
    """
    feature_dir = repo / "kitty-specs" / mission
    events = read_events(feature_dir)
    durable_ids = {
        event.event_id
        for event in events
        if event.wp_id == wp_id and event.review_result is not None
    }
    assert len(durable_ids) >= minimum, (
        f"expected >= {minimum} distinct durable review_result event records "
        f"for {wp_id}, found {len(durable_ids)} -- the event log (not the "
        "best-effort .md commit) is this mission's sole durability authority "
        "post-WP05 (NFR-004)"
    )


def test_sc003_durability_negative_control_dropped_event_reds(tmp_path: Path) -> None:
    """SC-003 non-vacuity (T028, squad #4): the re-pointed durability
    assertion above is not vacuously greenable -- deliberately DROP one
    durable event (write only one of two expected records) and assert
    :func:`_assert_durable_event_records_at_least` correctly goes RED. A
    naive re-point that always passes regardless of what actually landed
    would silently defeat SC-003; this proves it does not."""
    from specify_cli.status.models import ReviewResult
    from specify_cli.status.store import append_events_atomic_verified

    repo = tmp_path
    mission = "sc003-negative-control"
    feature_dir = repo / "kitty-specs" / mission
    feature_dir.mkdir(parents=True)

    # Only ONE durable event lands (the second write is simulated as
    # "dropped" -- e.g. a crash between write and event-append).
    append_events_atomic_verified(
        feature_dir,
        [
            StatusEvent(
                event_id="01SC003NEGATIVECONTROL001",
                mission_slug=mission,
                wp_id=_WP_ID,
                from_lane=Lane.IN_REVIEW,
                to_lane=Lane.IN_PROGRESS,
                at="2026-01-01T00:00:00Z",
                actor="reviewer-a",
                force=False,
                execution_mode="worktree",
                review_result=ReviewResult(reviewer="reviewer-a", verdict="changes_requested", reference="x"),
            )
        ],
    )

    with pytest.raises(AssertionError, match="expected >= 2 distinct durable review_result"):
        _assert_durable_event_records_at_least(repo, mission, _WP_ID, minimum=2)

    # Non-vacuity control: the SAME assertion is green when both records land.
    append_events_atomic_verified(
        feature_dir,
        [
            StatusEvent(
                event_id="01SC003NEGATIVECONTROL002",
                mission_slug=mission,
                wp_id=_WP_ID,
                from_lane=Lane.IN_REVIEW,
                to_lane=Lane.APPROVED,
                at="2026-01-01T00:01:00Z",
                actor="reviewer-b",
                force=False,
                execution_mode="worktree",
                review_result=ReviewResult(reviewer="reviewer-b", verdict="approved", reference="y"),
            )
        ],
    )
    _assert_durable_event_records_at_least(repo, mission, _WP_ID, minimum=2)
