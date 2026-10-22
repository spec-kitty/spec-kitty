"""Gate-integrity + "delivered nothing" harness for the terminal-state mission.

WP06 / T021–T022 (mission ``mission-completion-terminal-state``). Spec faces
NFR-001 (no gate regression), SC-005, and the SC-004 gate-integrity face.

The canceled-terminal acceptability change (WP01–WP04) lives in the SAME
``_check_lane_gates`` / ``_evaluate_acceptance_matrix`` path that classifies
lanes. The danger this file fences is a *short-circuit*: a mission whose only
non-``approved``/``done`` work package is an acceptable, operator-provenance
cancellation must STILL run — and still be able to FAIL on — the sibling
acceptance-matrix (and issue-matrix) verdict gates. Terminality, acceptability,
and the matrix verdict are independent decisions; an acceptable cancellation
must never buy a bypass of a failing matrix.

"0 regressions" for the NFR-001 suites is measured against the pinned baseline
commit ``a59460ec15`` (research.md R7). Per the repo's baseline-red gotcha,
classify any red against that base before attributing it here; the known-P0
reds are not this mission's.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from kernel.clock import now_utc_iso
from ulid import ULID

from specify_cli.acceptance import AcceptanceSummary, collect_feature_summary
from specify_cli.acceptance.matrix import (
    AcceptanceCriterion,
    AcceptanceMatrix,
    write_acceptance_matrix,
)
from specify_cli.status.models import (
    InnerStateChanged,
    Lane,
    StatusEvent,
    WPInnerStateDelta,
)
from specify_cli.status.reducer import materialize
from specify_cli.status.store import append_annotations_atomic_verified
from tests._support.status_seed import seed_status_event
from specify_cli.task_utils import LANES
from tests.lane_test_utils import write_single_lane_manifest

# Real ``git`` + subprocess CLI invocation — excluded from the mutmut sandbox.
pytestmark = [pytest.mark.non_sandbox, pytest.mark.git_repo]

_MISSION_SLUG = "099-terminal-state-gate-integrity"
_OPERATOR_REASON = "Descoped by the maintainer after re-homing the work."


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo_root), *args], check=True, capture_output=True)


def _append_transition_chain(feature_dir: Path, wp_id: str, target: Lane) -> None:
    """Append a valid planned -> ... -> ``target`` chain for one WP.

    The ``planned -> claimed`` leg carries the ``agent`` sidecar (the reducer's
    sole claim-writer, FR-004) so the resolved snapshot satisfies the strict
    metadata gate without a separate annotation.
    """
    chain: list[tuple[Lane, Lane]] = [
        (Lane.PLANNED, Lane.CLAIMED),
        (Lane.CLAIMED, Lane.IN_PROGRESS),
        (Lane.IN_PROGRESS, Lane.FOR_REVIEW),
        (Lane.FOR_REVIEW, Lane.APPROVED),
    ]
    if target == Lane.DONE:
        chain.append((Lane.APPROVED, Lane.DONE))
    for index, (from_lane, to_lane) in enumerate(chain):
        policy_metadata = {"agent": "test-agent"} if from_lane == Lane.PLANNED and to_lane == Lane.CLAIMED else None
        seed_status_event(
            feature_dir,
            StatusEvent(
                event_id=str(ULID()),
                mission_slug=feature_dir.name,
                wp_id=wp_id,
                from_lane=from_lane,
                to_lane=to_lane,
                at=f"2026-08-27T{12 + index:02d}:00:00+00:00",
                actor="test-agent",
                force=False,
                execution_mode="worktree",
                policy_metadata=policy_metadata,
            ),
        )
        if to_lane == target:
            break


def _append_cancellation(feature_dir: Path, wp_id: str, *, operator: bool) -> None:
    """Append a ``planned -> canceled`` event.

    ``operator=True`` stamps ``reason_source="operator"`` so the reducer projects
    operator-authored provenance (FR-001) — the acceptable case. ``operator=False``
    leaves a synthetic (provenance-free) cancellation — the blocker case (FR-003).
    """
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=str(ULID()),
            mission_slug=feature_dir.name,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane.CANCELED,
            at="2026-08-27T20:00:00+00:00",
            actor="maintainer" if operator else "test-agent",
            force=True,
            execution_mode="worktree",
            reason=_OPERATOR_REASON if operator else None,
            reason_source="operator" if operator else None,
        ),
    )
    # Stamp ``agent`` so the strict metadata gate is satisfied for the terminal
    # canceled WP (no claim leg ran to write it).
    append_annotations_atomic_verified(
        feature_dir,
        [
            InnerStateChanged(
                event_id=str(ULID()),
                wp_id=wp_id,
                at=now_utc_iso(),
                actor="test-agent",
                delta=WPInnerStateDelta(agent="test-agent"),
            )
        ],
    )


def _write_wp_file(tasks_dir: Path, wp_id: str) -> None:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{wp_id}-fixture.md").write_text(
        f'---\nwork_package_id: "{wp_id}"\ntitle: "{wp_id}"\nassignee: "test-agent"\nagent: "test-agent"\nsubtasks: []\n---\n# {wp_id}\nDone.\n',
        encoding="utf-8",
    )


def _build_mission(
    tmp_path: Path,
    *,
    wp_states: dict[str, str],
    matrix_pass_fail: str | None,
) -> tuple[Path, Path]:
    """Scaffold a real-git mission whose WPs land at ``wp_states``.

    ``wp_states`` maps a WP id to one of ``approved`` / ``done`` /
    ``canceled_operator`` / ``canceled_synthetic``. When ``matrix_pass_fail`` is
    ``"pass"`` / ``"fail"`` an ``acceptance-matrix.json`` with that single-criterion
    verdict is authored and committed; ``None`` writes no matrix.
    """
    repo_root = tmp_path
    _git(repo_root, "init", str(repo_root))
    _git(repo_root, "config", "user.email", "test@test.com")
    _git(repo_root, "config", "user.name", "Test")

    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    for convention_dir in ("src", "tests", "docs"):
        (repo_root / convention_dir).mkdir(parents=True, exist_ok=True)
        (repo_root / convention_dir / ".gitkeep").write_text("")
    (feature_dir / "contracts").mkdir(parents=True, exist_ok=True)
    (feature_dir / "contracts" / ".gitkeep").write_text("")

    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_number": "099",
                "slug": _MISSION_SLUG,
                "mission_slug": _MISSION_SLUG,
                "friendly_name": "Terminal State Gate Integrity",
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-08-27T00:00:00Z",
            },
            indent=2,
        )
        + "\n"
    )
    for fname in ("spec.md", "plan.md", "tasks.md"):
        (feature_dir / fname).write_text(f"# {fname}\nDone.\n")

    for wp_id, state in wp_states.items():
        _write_wp_file(tasks_dir, wp_id)
        if state == "canceled_operator":
            _append_cancellation(feature_dir, wp_id, operator=True)
        elif state == "canceled_synthetic":
            _append_cancellation(feature_dir, wp_id, operator=False)
        else:
            _append_transition_chain(feature_dir, wp_id, Lane(state))

    materialize(feature_dir)
    write_single_lane_manifest(feature_dir, wp_ids=tuple(wp_states))
    if matrix_pass_fail is not None:
        write_acceptance_matrix(
            feature_dir,
            AcceptanceMatrix(
                mission_slug=_MISSION_SLUG,
                criteria=[
                    AcceptanceCriterion(
                        criterion_id="AC-01",
                        description="Acceptance proof",
                        proof_type="automated_test",
                        evidence="pytest",
                        pass_fail=matrix_pass_fail,
                        verified_by="ci",
                    )
                ],
            ),
        )

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "scaffold terminal-state gate-integrity mission")
    _git(repo_root, "checkout", "-b", f"kitty/mission-{_MISSION_SLUG}")
    return repo_root, feature_dir


def _summary(repo_root: Path) -> AcceptanceSummary:
    # ``mutate_matrix=False``: read-only diagnose, so the matrix is never
    # rewritten and the tree stays clean (git_dirty must not mask the verdict).
    return collect_feature_summary(repo_root, _MISSION_SLUG, mutate_matrix=False)


# ---------------------------------------------------------------------------
# T021 — gate-integrity: an acceptable cancellation must NOT short-circuit the
# acceptance-matrix verdict gate.
# ---------------------------------------------------------------------------


def test_operator_canceled_wp_does_not_short_circuit_failing_matrix(tmp_path: Path) -> None:
    """A failing acceptance matrix blocks acceptance even when the only
    non-``approved`` WP is an acceptable operator cancellation.

    This is the non-short-circuit proof (SC-004 gate-integrity face): the
    canceled WP is classified as an *acceptable ending* (``all_done`` stays True,
    it is reported under ``canceled_wps`` and is NOT a lane blocker), yet the
    sibling matrix gate still runs and still bites — ``ok`` is False and the
    verdict issue is surfaced. A test that only walked the happy path would not
    prove the gate was actually exercised, so this asserts a genuinely FAILING
    matrix.
    """
    repo_root, _feature_dir = _build_mission(
        tmp_path,
        wp_states={"WP01": "approved", "WP02": "canceled_operator"},
        matrix_pass_fail="fail",
    )

    summary = _summary(repo_root)

    # The cancellation was recognised as an acceptable ending — not a blocker.
    assert summary.all_done is True
    assert [entry["wp_id"] for entry in summary.canceled_wps] == ["WP02"]
    assert not any("WP02" in blocker for blocker in summary.outstanding().get("lane_blockers", []))

    # ...yet the sibling matrix gate still ran and still failed acceptance.
    assert summary.ok is False
    assert any("Acceptance matrix verdict is 'fail'" in issue for issue in summary.activity_issues)
    assert any(item.check == "activity" and "verdict is 'fail'" in item.detail for item in summary.failed_checks())


def test_operator_canceled_wp_accepts_only_when_matrix_passes(tmp_path: Path) -> None:
    """The matrix verdict — not the cancellation — is the sole differentiator.

    Same mission shape as the failing case, but with a PASSING matrix: it now
    accepts. Pairing this with the failing case proves the block came from the
    matrix gate, not from the presence of the canceled WP (which is identical in
    both) — i.e. the gate is genuinely exercised, not incidentally satisfied.
    """
    repo_root, _feature_dir = _build_mission(
        tmp_path,
        wp_states={"WP01": "approved", "WP02": "canceled_operator"},
        matrix_pass_fail="pass",
    )

    summary = _summary(repo_root)

    assert summary.all_done is True
    assert [entry["wp_id"] for entry in summary.canceled_wps] == ["WP02"]
    assert not any("Acceptance matrix verdict" in issue for issue in summary.activity_issues)
    assert summary.ok is True, f"expected acceptance, outstanding={summary.outstanding()}"


def test_synthetic_cancellation_is_a_blocker_independent_of_matrix(tmp_path: Path) -> None:
    """A provenance-free cancellation blocks on its own (FR-003), and does so
    even alongside a PASSING matrix — the two gates are independent.

    This is the negative control for :func:`test_operator_canceled_wp_accepts_only_when_matrix_passes`:
    swap operator provenance for a synthetic cancellation and the same
    matrix-passing mission is refused, with the FR-003 provenance diagnostic —
    never reported as an accept-eligible cancellation.
    """
    repo_root, _feature_dir = _build_mission(
        tmp_path,
        wp_states={"WP01": "approved", "WP02": "canceled_synthetic"},
        matrix_pass_fail="pass",
    )

    summary = _summary(repo_root)

    assert summary.all_done is False
    assert summary.canceled_wps == []
    lane_blockers = summary.outstanding().get("lane_blockers", [])
    assert any("WP02" in blocker and "operator-authored cancellation provenance required" in blocker for blocker in lane_blockers)
    assert summary.ok is False


# ---------------------------------------------------------------------------
# T022 — "every WP canceled -> not complete" guard. The "delivered nothing"
# refusal is an EXPLICIT check, not an accident of terminal-lane classification.
# ---------------------------------------------------------------------------


def test_all_operator_canceled_mission_is_not_complete(tmp_path: Path) -> None:
    """A mission whose WPs are ALL (acceptably) canceled delivered nothing and
    must not be reported complete (spec Edge Case).

    Every cancellation carries operator provenance, so each is an acceptable
    ending *on its own* — yet the mission reached neither ``approved`` nor
    ``done``. ``all_done`` must be False and the explicit "delivered nothing"
    guard must fire, distinct from a per-WP lane blocker.
    """
    repo_root, _feature_dir = _build_mission(
        tmp_path,
        wp_states={"WP01": "canceled_operator", "WP02": "canceled_operator"},
        matrix_pass_fail="pass",
    )

    summary = _summary(repo_root)

    assert summary.all_done is False
    outstanding = summary.outstanding()
    assert outstanding.get("delivered_nothing"), outstanding
    assert any("delivered nothing" in message for message in outstanding["delivered_nothing"])
    # The acceptable cancellations are not re-reported as lane blockers — the
    # refusal is the dedicated "delivered nothing" guard, not lane classification.
    assert "lane_blockers" not in outstanding
    assert summary.ok is False


def test_all_canceled_guard_is_explicit_at_summary_level() -> None:
    """The "delivered nothing" guard is a first-class predicate, provable without
    any git/filesystem scaffolding.

    Constructs an ``AcceptanceSummary`` whose only WP is an operator-provenance
    cancellation and asserts the guard fires — pinning that the refusal lives on
    ``AcceptanceSummary`` itself (an explicit check) rather than emerging from
    the matrix or lane-gate machinery.
    """
    summary = _acceptance_summary_with_states(
        lanes={"canceled": ["WP01"]},
        provenance={"WP01": True},
    )

    assert summary.all_done is False
    assert summary.outstanding().get("delivered_nothing")
    # An operator cancellation is acceptable, so it is NOT a lane blocker...
    assert "lane_blockers" not in summary.outstanding()
    # ...the ONLY refusal is the explicit delivered-nothing guard.
    assert set(summary.outstanding()) == {"delivered_nothing"}


# ---------------------------------------------------------------------------
# Summary-construction helper (no I/O) for the explicit-guard unit proof.
# ---------------------------------------------------------------------------


def _acceptance_summary_with_states(
    *,
    lanes: dict[str, list[str]],
    provenance: dict[str, bool],
) -> AcceptanceSummary:
    from specify_cli.acceptance.summary_core import WorkPackageState

    full_lanes = {lane: list(lanes.get(lane, [])) for lane in LANES}
    work_packages = [
        WorkPackageState(
            work_package_id=wp_id,
            lane=lane,
            title=wp_id,
            path=f"tasks/{wp_id}.md",
            has_lane_entry=True,
            latest_lane=lane,
            metadata={"agent": "test-agent"},
            has_operator_provenance=provenance.get(wp_id, False),
        )
        for lane, wp_ids in full_lanes.items()
        for wp_id in wp_ids
    ]
    return AcceptanceSummary(
        feature=_MISSION_SLUG,
        repo_root=Path("."),
        feature_dir=Path("."),
        tasks_dir=Path("."),
        branch="main",
        worktree_root=Path("."),
        primary_repo_root=Path("."),
        lanes=full_lanes,
        work_packages=work_packages,
        metadata_issues=[],
        activity_issues=[],
        unchecked_tasks=[],
        needs_clarification=[],
        missing_artifacts=[],
        optional_missing=[],
        git_dirty=[],
        path_violations=[],
        warnings=[],
    )
