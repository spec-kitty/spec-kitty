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
import shutil
from pathlib import Path
from typing import Any

import pytest

from specify_cli.migration.backfill_runtime_state import LegacyWPRuntime
from specify_cli.status import (
    PRE_ACCEPT_EXEMPT_NOTE,
    REASON_ABSENT_MISSION_ID,
    REASON_LEGACY_FRONTMATTER,
    REASON_LEGACY_UNDECIDABLE,
    REASON_META_DUPLICATE_KEYS,
    REASON_PHASE_MALFORMED,
    REASON_TERMINAL_MALFORMED,
    REASON_TERMINAL_UNSTAMPED,
    Lane,
    ReviewOverride,
    StatusEvent,
    build_claim_policy_metadata,
    is_cut_over,
)
from specify_cli.status.cutover_eligibility import eligible_runtime_missions, mission_carries_event_log_runtime
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
#: A WP filled the way tasks-packages step 4a fills it at PLANNING time (no claim yet).
_STEP_4A_WP = (
    'work_package_id: "WP01"\ntitle: "Demo"\nagent_profile: "implementer-ivan"\nrole: "implementer"\n'
    'agent: "claude"\nmodel: "claude-sonnet-4-6"\ntracker_refs: [\'#5835\']\n'
)


def _born_mission(
    root: Path,
    *,
    meta_extra: dict[str, Any] | None = None,
    wp_frontmatter: str = _EMPTY_WP,
    claim: bool = True,
    raw_meta: str | None = None,
    mission_id: str | None = _MISSION_ID,
    tasks_is_file: bool = False,
    tasks_md: bytes = b"# Tasks\n\n## WP01 X\n\n- [x] T001 ref\n",
) -> Path:
    mission_dir = root / "m-01KZMATRIX"
    (mission_dir / "tasks").mkdir(parents=True)
    meta: dict[str, Any] = {"mission_slug": mission_dir.name, **(meta_extra or {})}
    if mission_id is not None:
        meta["mission_id"] = mission_id
    (mission_dir / "meta.json").write_text(raw_meta if raw_meta is not None else json.dumps(meta), encoding="utf-8")
    (mission_dir / "tasks" / "WP01-x.md").write_text(f"---\n{wp_frontmatter}---\n\n# WP01\n", encoding="utf-8")
    (mission_dir / "tasks.md").write_bytes(tasks_md)
    if tasks_is_file:
        shutil.rmtree(mission_dir / "tasks")
        (mission_dir / "tasks").write_text("not a directory", encoding="utf-8")
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
        pytest.param({"meta_extra": {"accepted_at": 1700000000}}, False, REASON_TERMINAL_MALFORMED, id="accepted-at-integer"),
        pytest.param({"meta_extra": {"accepted_at": True}}, False, REASON_TERMINAL_MALFORMED, id="accepted-at-boolean"),
        pytest.param({"meta_extra": {"merged_at": 123}}, False, REASON_TERMINAL_MALFORMED, id="merged-at-integer"),
        pytest.param({"meta_extra": {"accept_commit": "a" * 40}}, False, REASON_TERMINAL_UNSTAMPED, id="accept-commit-without-timestamp"),
        pytest.param({"meta_extra": {"merged_commit": "b" * 40}}, False, REASON_TERMINAL_UNSTAMPED, id="merged-commit-without-timestamp"),
        pytest.param({"meta_extra": {"acceptance_history": [{"accept_commit": "a" * 40}]}}, False, REASON_TERMINAL_UNSTAMPED, id="history-without-timestamp"),
        pytest.param(
            {"meta_extra": {"accepted_at": None, "accept_commit": None, "acceptance_history": []}},
            True,
            PRE_ACCEPT_EXEMPT_NOTE,
            id="null-terminal-fields-pre-accept",
        ),
        pytest.param(
            {"raw_meta": f'{{"mission_id": "{_MISSION_ID}", "accepted_at": "2026-02-01T00:00:00Z", "accepted_at": null}}'},
            False,
            REASON_META_DUPLICATE_KEYS,
            id="meta-duplicate-key-last-wins-hides-acceptance",
        ),
        pytest.param({"meta_extra": {"mission_number": 0}}, False, REASON_TERMINAL_UNSTAMPED, id="mission-number-zero"),
        pytest.param({"wp_frontmatter": _EMPTY_WP.replace('agent: ""', 'agent: "claude"')}, True, PRE_ACCEPT_EXEMPT_NOTE, id="planning-time-agent"),
        pytest.param({"wp_frontmatter": _STEP_4A_WP}, True, PRE_ACCEPT_EXEMPT_NOTE, id="tasks-packages-step-4a-fill"),
        pytest.param({"wp_frontmatter": _EMPTY_WP.replace('shell_pid: ""', "shell_pid: 4242")}, False, REASON_LEGACY_FRONTMATTER, id="legacy-shell-pid"),
        pytest.param({"wp_frontmatter": _EMPTY_WP.replace('assignee: ""', 'assignee: "x"')}, False, REASON_LEGACY_FRONTMATTER, id="legacy-assignee"),
        pytest.param({"wp_frontmatter": _EMPTY_WP + 'tracker_refs:\n  - "X-1"\n'}, True, PRE_ACCEPT_EXEMPT_NOTE, id="authored-tracker-refs"),
        pytest.param({"meta_extra": {"status_phase": "abc"}}, False, REASON_PHASE_MALFORMED, id="phase-malformed"),
        pytest.param({"meta_extra": {"status_phase": "-5"}}, False, REASON_PHASE_MALFORMED, id="phase-negative-malformed"),
        pytest.param({"raw_meta": "{not json"}, False, REASON_ABSENT_MISSION_ID, id="meta-invalid-json"),
        pytest.param({"wp_frontmatter": 'work_package_id: "WP01"\nagent: [unclosed\n'}, False, REASON_LEGACY_UNDECIDABLE, id="wp-unparsable"),
        pytest.param({"mission_id": None}, False, REASON_ABSENT_MISSION_ID, id="absent-mission-id"),
        pytest.param({"tasks_is_file": True}, False, REASON_LEGACY_UNDECIDABLE, id="tasks-is-a-file"),
        pytest.param({"tasks_md": b"# Tasks \xff\xfe"}, False, REASON_LEGACY_UNDECIDABLE, id="tasks-md-not-utf8"),
    ],
)
def test_is_cut_over_pre_accept_matrix(tmp_path: Path, kwargs: dict[str, Any], cut_over: bool, reasons_prefix: str | None) -> None:
    """Each cell pins the verdict and the reason constant (or the exemption note) that decided it."""
    verdict = is_cut_over(_born_mission(tmp_path, **kwargs))

    assert verdict.cut_over is cut_over, verdict.reasons
    assert verdict.exempt is (reasons_prefix == PRE_ACCEPT_EXEMPT_NOTE)
    if reasons_prefix is None:
        assert verdict.reasons == ()
    elif cut_over:
        assert verdict.reasons == (reasons_prefix,)
    else:
        assert verdict.reasons
        assert verdict.reasons[0].startswith(reasons_prefix)


@pytest.mark.parametrize(
    ("kwargs", "names"),
    [
        pytest.param({"tasks_is_file": True}, "tasks", id="tasks-dir"),
        pytest.param({"tasks_md": b"# Tasks \xff\xfe"}, "tasks.md", id="tasks-md"),
        pytest.param({"wp_frontmatter": 'work_package_id: "WP01"\nagent: [unclosed\n'}, "WP01-x.md", id="wp-file"),
    ],
)
def test_undecidable_reason_names_the_failing_file(tmp_path: Path, kwargs: dict[str, Any], names: str) -> None:
    """CI shows which file broke the legacy read and why, not only that it was undecidable."""
    reason = is_cut_over(_born_mission(tmp_path, **kwargs)).reasons[0]

    assert reason.startswith(REASON_LEGACY_UNDECIDABLE)
    assert names in reason.removeprefix(REASON_LEGACY_UNDECIDABLE)


def test_bom_prefixed_meta_is_still_exempt(tmp_path: Path) -> None:
    """#1440: a BOM-prefixed ``meta.json`` must not be read as unreadable."""
    mission_dir = _born_mission(tmp_path)
    meta = (mission_dir / "meta.json").read_text(encoding="utf-8")
    (mission_dir / "meta.json").write_bytes(b"\xef\xbb\xbf" + meta.encode("utf-8"))

    assert is_cut_over(mission_dir).reasons == (PRE_ACCEPT_EXEMPT_NOTE,)


def test_stamped_mission_keeps_strict_path(tmp_path: Path) -> None:
    """A stamped mission is never exempt: it still needs a snapshot that verifies."""
    mission_dir = _born_mission(tmp_path, meta_extra={"status_phase": "1"})

    verdict = is_cut_over(mission_dir)

    assert verdict.cut_over is False
    assert verdict.exempt is False


@pytest.mark.parametrize(
    ("runtime", "frontmatter_runtime", "legacy_claim"),
    [
        pytest.param(LegacyWPRuntime(wp_id="WP01"), False, False, id="empty"),
        pytest.param(LegacyWPRuntime(wp_id="WP01", subtasks={"T001": Lane.DONE}), False, False, id="subtasks-only"),
        pytest.param(LegacyWPRuntime(wp_id="WP01", agent="claude"), True, False, id="agent"),
        pytest.param(LegacyWPRuntime(wp_id="WP01", shell_pid=7), True, True, id="shell-pid"),
        pytest.param(LegacyWPRuntime(wp_id="WP01", shell_pid_created_at="t"), True, True, id="shell-pid-created-at"),
        pytest.param(LegacyWPRuntime(wp_id="WP01", assignee="x"), True, True, id="assignee"),
        pytest.param(LegacyWPRuntime(wp_id="WP01", tracker_refs=("X-1",)), True, False, id="tracker-refs"),
        pytest.param(
            LegacyWPRuntime(wp_id="WP01", review=ReviewOverride(at="t", actor="a", wp_id="WP01", reason="r")),
            True,
            True,
            id="complete-review",
        ),
        pytest.param(
            LegacyWPRuntime(wp_id="WP01", review=ReviewOverride(at="", actor="", wp_id="WP01", reason="")),
            False,
            False,
            id="incomplete-review",
        ),
    ],
)
def test_legacy_runtime_predicates(runtime: LegacyWPRuntime, frontmatter_runtime: bool, legacy_claim: bool) -> None:
    """The exemption's narrower predicate ignores the planning-time ``agent``/``tracker_refs``; backfill's does not."""
    assert runtime.has_frontmatter_runtime() is frontmatter_runtime
    assert runtime.has_legacy_claim_runtime() is legacy_claim


def test_absent_mission_id_stays_eligible_and_fails_while_control_is_exempt(tmp_path: Path) -> None:
    """Both consumers agree: no ``mission_id`` withholds the exemption (FR-005).

    The same pre-accept fixture WITH a ``mission_id`` is exempt and not eligible
    (positive control), so the absent-id cell is not vacuous.
    """
    no_id = _born_mission(tmp_path / "a", mission_id=None)
    with_id = _born_mission(tmp_path / "b")

    assert eligible_runtime_missions(no_id.parent) == [no_id]
    assert is_cut_over(no_id).cut_over is False
    assert eligible_runtime_missions(with_id.parent) == []
    assert is_cut_over(with_id).reasons == (PRE_ACCEPT_EXEMPT_NOTE,)
