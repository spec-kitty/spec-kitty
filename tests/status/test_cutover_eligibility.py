"""Tests for ``status.cutover_eligibility.mission_carries_event_log_runtime`` (WP03 campsite, T014).

FR-001 of mission ``mixed-lane-authorship-soundness-01M3M7Y0`` started
stamping a best-effort ``lane_head`` key onto ``policy_metadata`` for EVERY
persisted lane-mapped transition -- independent of claim state. Before this
WP, :func:`mission_carries_event_log_runtime` treated any non-empty
``policy_metadata`` as runtime-carrying evidence, which a bare stamp on a
never-claimed mission would have misclassified.

**Conservative fix (orchestrator decision, review-feedback-1 Issue 5):**
rather than re-keying on the claim triple alone (which would also have
stopped counting approval/pre-review-gate/migration ``policy_metadata``
shapes that carried no claim keys, a broader narrowing than intended), the
predicate excludes ONLY a ``policy_metadata`` dict whose keys are entirely
``lane_head`` (or empty). Every other shape -- a real claim, an
APPROVED/DONE hop's ``tool``/``profile``/``model``/``shell_pid``
(``tasks_move_task._mt_approval_policy_metadata``), etc. -- keeps counting
exactly as it did before WP03.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specify_cli.migration.backfill_runtime_state import LegacyWPRuntime
from specify_cli.status.cutover_eligibility import (
    PRE_ACCEPT_EXEMPT_NOTE,
    REASON_LEGACY_FRONTMATTER,
    REASON_LEGACY_UNDECIDABLE,
    REASON_PHASE_MALFORMED,
    REASON_TERMINAL_UNSTAMPED,
    is_cut_over,
    mission_carries_event_log_runtime,
)
from specify_cli.status.emit import build_claim_policy_metadata
from specify_cli.status.models import Lane, ReviewOverride, StatusEvent
from specify_cli.status.store import append_event

pytestmark = pytest.mark.fast

_MISSION_SLUG = "cutover-eligibility-wp03"
_MISSION_ID = "01CUTOVERWP03000000000001"


def _genesis_to_planned(*, event_id: str) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.GENESIS,
        to_lane=Lane.PLANNED,
        at="2026-01-01T00:00:00+00:00",
        actor="seed",
        force=False,
        reason="seed",
        execution_mode="worktree",
    )


def test_no_event_log_is_not_detected(tmp_path: Path) -> None:
    assert mission_carries_event_log_runtime(tmp_path) is False


def test_bootstrap_only_events_are_not_detected(tmp_path: Path) -> None:
    """A ``genesis -> planned`` bootstrap anchor carries no runtime signal at all."""
    append_event(tmp_path, _genesis_to_planned(event_id="01BOOTSTRAPONLYAAAAAAAAAA1"))

    assert mission_carries_event_log_runtime(tmp_path) is False


def test_claim_policy_metadata_is_detected(tmp_path: Path) -> None:
    """A real ``planned -> claimed`` claim (``shell_pid``/``agent`` keys) IS evidence."""
    append_event(tmp_path, _genesis_to_planned(event_id="01CLAIMDETECTEDAAAAAAAAA1"))
    claim = StatusEvent(
        event_id="01CLAIMDETECTEDAAAAAAAAA2",
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at="2026-01-01T00:01:00+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
        policy_metadata=build_claim_policy_metadata(
            shell_pid=1234,
            shell_pid_created_at="2026-01-01T00:00:30+00:00",
            agent="claude",
        ),
    )
    append_event(tmp_path, claim)

    assert mission_carries_event_log_runtime(tmp_path) is True


def test_approval_only_policy_metadata_is_detected(tmp_path: Path) -> None:
    """Conservative fix (Issue 5): an APPROVED/DONE hop's ``tool``/``profile``/``model``
    sidecar (``tasks_move_task._mt_approval_policy_metadata``) carries no claim keys at
    all, yet must still count as runtime evidence -- the exact shape a claim-keys-only
    re-key (the rejected alternative) would have stopped detecting.
    """
    append_event(tmp_path, _genesis_to_planned(event_id="01APPROVALONLYAAAAAAAAA01"))
    approval_only = StatusEvent(
        event_id="01APPROVALONLYAAAAAAAAA02",
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.IN_REVIEW,
        to_lane=Lane.APPROVED,
        at="2026-01-01T00:02:00+00:00",
        actor="reviewer-1",
        force=False,
        execution_mode="worktree",
        policy_metadata={"tool": "reviewer-1", "profile": None, "model": None},
    )
    append_event(tmp_path, approval_only)

    assert mission_carries_event_log_runtime(tmp_path) is True


def test_lane_head_only_policy_metadata_is_not_detected(tmp_path: Path) -> None:
    """FR-001 regression guard: a bare ``lane_head`` stamp is NOT runtime evidence.

    A transition that carries only the WP03 lane-head stamp (no other keys)
    must not flip a never-claimed mission to "runtime-carrying" -- the exact
    misclassification a bare ``bool(policy_metadata)`` check would produce.
    """
    append_event(tmp_path, _genesis_to_planned(event_id="01LANEHEADONLYAAAAAAAAA1"))
    stamped_but_unclaimed = StatusEvent(
        event_id="01LANEHEADONLYAAAAAAAAA2",
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.PLANNED,
        at="2026-01-01T00:01:00+00:00",
        actor="claude",
        force=True,
        reason="re-anchor",
        execution_mode="worktree",
        policy_metadata={"lane_head": "d" * 40},
    )
    append_event(tmp_path, stamped_but_unclaimed)

    assert mission_carries_event_log_runtime(tmp_path) is False


def test_empty_policy_metadata_is_not_detected(tmp_path: Path) -> None:
    append_event(tmp_path, _genesis_to_planned(event_id="01EMPTYMETADATAAAAAAAAA01"))
    empty_metadata = StatusEvent(
        event_id="01EMPTYMETADATAAAAAAAAA02",
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.PLANNED,
        at="2026-01-01T00:01:00+00:00",
        actor="claude",
        force=True,
        reason="re-anchor",
        execution_mode="worktree",
        policy_metadata={},
    )
    append_event(tmp_path, empty_metadata)

    assert mission_carries_event_log_runtime(tmp_path) is False


# --- pre-accept exemption (#5835 / #5300) ------------------------------------

_EMPTY_WP = 'work_package_id: "WP01"\ntitle: "Demo"\nagent: ""\nassignee: ""\nshell_pid: ""\n'
_NOT_FLIPPED = "status_phase not flipped despite event-log runtime evidence"


def _born_mission(
    root: Path,
    *,
    meta_extra: dict[str, Any] | None = None,
    wp_frontmatter: str = _EMPTY_WP,
    claim: bool = True,
    raw_meta: str | None = None,
    mission_id: str | None = _MISSION_ID,
) -> Path:
    mission_dir = root / "m-01KZMATRIX"
    (mission_dir / "tasks").mkdir(parents=True)
    meta: dict[str, Any] = {"mission_slug": mission_dir.name, **(meta_extra or {})}
    if mission_id is not None:
        meta["mission_id"] = mission_id
    (mission_dir / "meta.json").write_text(raw_meta if raw_meta is not None else json.dumps(meta), encoding="utf-8")
    (mission_dir / "tasks" / "WP01-x.md").write_text(f"---\n{wp_frontmatter}---\n\n# WP01\n", encoding="utf-8")
    (mission_dir / "tasks.md").write_text("# Tasks\n\n## WP01 X\n\n- [x] T001 ref\n", encoding="utf-8")
    append_event(mission_dir, _genesis_to_planned(event_id="01MATRIXBOOTSTRAPAAAAAA1"))
    if claim:
        append_event(
            mission_dir,
            StatusEvent(
                event_id="01MATRIXCLAIMAAAAAAAAAA2",
                mission_slug=_MISSION_SLUG,
                mission_id=_MISSION_ID,
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.CLAIMED,
                at="2026-01-01T00:01:00+00:00",
                actor="claude",
                force=False,
                execution_mode="worktree",
                policy_metadata=build_claim_policy_metadata(shell_pid=1234, shell_pid_created_at="2026-01-01T00:00:30+00:00", agent="claude"),
            ),
        )
    return mission_dir


_PASS_NOTE = (True, (PRE_ACCEPT_EXEMPT_NOTE,))
_PASS_QUIET = (True, ())


@pytest.mark.parametrize(
    ("kwargs", "cut_over", "reasons_prefix"),
    [
        pytest.param({"claim": False}, True, None, id="no-evidence-passes-quietly"),
        pytest.param({}, True, PRE_ACCEPT_EXEMPT_NOTE, id="pre-accept-template-frontmatter"),
        pytest.param({"meta_extra": {"status_phase": "0"}}, True, PRE_ACCEPT_EXEMPT_NOTE, id="phase-zero-pre-accept"),
        pytest.param({"meta_extra": {"accepted_at": "2026-02-01T00:00:00Z"}}, False, REASON_TERMINAL_UNSTAMPED, id="accepted"),
        pytest.param({"meta_extra": {"merged_at": "2026-02-01T00:00:00Z"}}, False, REASON_TERMINAL_UNSTAMPED, id="merged"),
        pytest.param({"meta_extra": {"mission_number": 0}}, False, REASON_TERMINAL_UNSTAMPED, id="mission-number-zero"),
        pytest.param({"wp_frontmatter": _EMPTY_WP.replace('agent: ""', 'agent: "claude"')}, False, REASON_LEGACY_FRONTMATTER, id="legacy-agent"),
        pytest.param({"wp_frontmatter": _EMPTY_WP.replace('assignee: ""', 'assignee: "x"')}, False, REASON_LEGACY_FRONTMATTER, id="legacy-assignee"),
        pytest.param({"wp_frontmatter": _EMPTY_WP + 'tracker_refs:\n  - "X-1"\n'}, False, REASON_LEGACY_FRONTMATTER, id="legacy-tracker-refs"),
        pytest.param({"meta_extra": {"status_phase": "abc"}}, False, REASON_PHASE_MALFORMED, id="phase-malformed"),
        pytest.param({"raw_meta": "{not json"}, False, "absent mission_id", id="meta-invalid-json"),
        pytest.param({"wp_frontmatter": 'work_package_id: "WP01"\nagent: [unclosed\n'}, False, REASON_LEGACY_UNDECIDABLE, id="wp-unparsable"),
        pytest.param({"mission_id": None}, False, "absent mission_id", id="absent-mission-id"),
    ],
)
def test_is_cut_over_pre_accept_matrix(tmp_path: Path, kwargs: dict[str, Any], cut_over: bool, reasons_prefix: str | None) -> None:
    """Only the first exempt cells change verdict versus the pre-fix predicate (NFR-001)."""
    verdict = is_cut_over(_born_mission(tmp_path, **kwargs))

    assert verdict.cut_over is cut_over, verdict.reasons
    if reasons_prefix is None:
        assert verdict.reasons == ()
    elif cut_over:
        assert verdict.reasons == (reasons_prefix,)
    else:
        assert verdict.reasons
        assert verdict.reasons[0].startswith(reasons_prefix) or reasons_prefix in verdict.reasons[0]


def test_bom_prefixed_meta_is_still_exempt(tmp_path: Path) -> None:
    """#1440: a BOM-prefixed ``meta.json`` must not be read as unreadable."""
    mission_dir = _born_mission(tmp_path)
    meta = (mission_dir / "meta.json").read_text(encoding="utf-8")
    (mission_dir / "meta.json").write_bytes(b"\xef\xbb\xbf" + meta.encode("utf-8"))

    assert is_cut_over(mission_dir).reasons == (PRE_ACCEPT_EXEMPT_NOTE,)


def test_legacy_reasons_keep_historical_prefix(tmp_path: Path) -> None:
    mission_dir = _born_mission(tmp_path, meta_extra={"accepted_at": "2026-02-01T00:00:00Z"})

    assert is_cut_over(mission_dir).reasons[0].startswith(_NOT_FLIPPED)


def test_stamped_mission_keeps_strict_path(tmp_path: Path) -> None:
    """A stamped mission is never exempt: it still needs a snapshot that verifies."""
    mission_dir = _born_mission(tmp_path, meta_extra={"status_phase": "1"})

    verdict = is_cut_over(mission_dir)

    assert PRE_ACCEPT_EXEMPT_NOTE not in verdict.reasons


@pytest.mark.parametrize(
    ("runtime", "expected"),
    [
        pytest.param(LegacyWPRuntime(wp_id="WP01"), False, id="empty"),
        pytest.param(LegacyWPRuntime(wp_id="WP01", subtasks={"T001": Lane.DONE}), False, id="subtasks-only"),
        pytest.param(LegacyWPRuntime(wp_id="WP01", agent="claude"), True, id="agent"),
        pytest.param(LegacyWPRuntime(wp_id="WP01", assignee="x"), True, id="assignee"),
        pytest.param(LegacyWPRuntime(wp_id="WP01", tracker_refs=("X-1",)), True, id="tracker-refs"),
        pytest.param(
            LegacyWPRuntime(wp_id="WP01", review=ReviewOverride(at="t", actor="a", wp_id="WP01", reason="r")),
            True,
            id="complete-review",
        ),
        pytest.param(
            LegacyWPRuntime(wp_id="WP01", review=ReviewOverride(at="", actor="", wp_id="WP01", reason="")),
            False,
            id="incomplete-review",
        ),
    ],
)
def test_has_frontmatter_runtime(runtime: LegacyWPRuntime, expected: bool) -> None:
    assert runtime.has_frontmatter_runtime() is expected


def test_pre_accept_exemption_declines_on_unreadable_meta(tmp_path: Path) -> None:
    """Fail closed: a malformed ``meta.json`` reads empty (no ``mission_id``) and never yields the exemption."""
    from specify_cli.status.cutover_eligibility import REASON_ABSENT_MISSION_ID, pre_accept_exemption

    mission_dir = _born_mission(tmp_path, raw_meta="{not json")

    decision = pre_accept_exemption(mission_dir)

    assert decision.exempt is False
    assert decision.block_reason == REASON_ABSENT_MISSION_ID


def test_absent_mission_id_stays_eligible_and_fails_while_control_is_exempt(tmp_path: Path) -> None:
    """Both consumers agree: no ``mission_id`` withholds the exemption (FR-005).

    The same pre-accept fixture WITH a ``mission_id`` is exempt and not eligible
    (positive control), so the absent-id cell is not vacuous.
    """
    from specify_cli.status.cutover_eligibility import eligible_runtime_missions

    no_id = _born_mission(tmp_path / "a", mission_id=None)
    with_id = _born_mission(tmp_path / "b")

    assert eligible_runtime_missions(no_id.parent) == [no_id]
    assert is_cut_over(no_id).cut_over is False
    assert eligible_runtime_missions(with_id.parent) == []
    assert is_cut_over(with_id).reasons == (PRE_ACCEPT_EXEMPT_NOTE,)
