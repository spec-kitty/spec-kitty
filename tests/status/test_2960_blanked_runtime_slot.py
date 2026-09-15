"""#2960 (FR-014, WP10) — an ``agent: ""`` annotation must not silently blank
recorded runtime attribution, and ``status doctor`` must not report Healthy over
a blanked runtime slot.

Three coupled guards, each red-first:

1. **Write-boundary normalization** (``WPInnerStateDelta``): an empty-string
   scalar slot is normalized to ``None`` at construction, so the append-only log
   never records a blanking delta (the durable net).
2. **Reducer no-op** (``_apply_annotation_delta`` replace-slot fold and the
   ``planned -> claimed`` claim-exception arm): an empty string is a no-op for a
   string replace-slot, so prior attribution survives even when a legacy log
   already carries an ``agent: ""`` delta / claim sidecar.
3. **Doctor net** (``check_blanked_runtime_slots``): a non-terminal WP whose
   runtime slot is an empty string is flagged (no false Healthy).

Topology-agnostic (Scope B / NFR-004): pure reducer + doctor unit proofs, no
coord fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.status.doctor import (
    Category,
    Severity,
    check_blanked_runtime_slots,
    run_doctor,
)
from specify_cli.status.models import (
    InnerStateChanged,
    Lane,
    StatusEvent,
    WPInnerStateDelta,
)
from specify_cli.status.reducer import reduce

pytestmark = [pytest.mark.fast]

_MISSION_SLUG = "2960-blanked-slot"


def _ulid(suffix: str) -> str:
    return ("01M02" + suffix).ljust(26, "0")[:26]


def _annotation(event_id: str, at: str, delta: WPInnerStateDelta) -> InnerStateChanged:
    return InnerStateChanged(
        event_id=event_id, wp_id="WP01", at=at, actor="claude", delta=delta
    )


# ---------------------------------------------------------------------------
# Part 1 — write-boundary normalization (models.py durable net)
# ---------------------------------------------------------------------------


def test_empty_agent_normalized_to_none_at_write_boundary() -> None:
    """``WPInnerStateDelta(agent="")`` records no agent — the log never carries a
    blanking delta (the durable net)."""
    delta = WPInnerStateDelta(agent="")
    assert delta.agent is None
    assert "agent" not in delta.to_dict()
    assert delta.is_empty() is True


def test_empty_string_normalized_for_every_scalar_slot() -> None:
    """Every ``str | None`` scalar runtime slot normalizes ``""`` -> ``None`` so
    no attribution slot can be blanked on the wire."""
    delta = WPInnerStateDelta(
        agent="",
        assignee="",
        role="",
        agent_profile="",
        agent_profile_version="",
        model="",
        provider="",
        shell_pid_created_at="",
    )
    assert delta.is_empty() is True
    assert delta.to_dict() == {}


def test_nonempty_scalar_slots_are_preserved() -> None:
    """Non-vacuity guard: a real value is untouched by the normalization."""
    delta = WPInnerStateDelta(agent="claude", role="reviewer")
    assert delta.agent == "claude"
    assert delta.role == "reviewer"


# ---------------------------------------------------------------------------
# Part 2 — reducer no-op (survival of prior attribution)
# ---------------------------------------------------------------------------


def test_empty_agent_delta_does_not_blank_prior_attribution() -> None:
    """Folding an ``agent: ""`` annotation over a real ``agent: "claude"`` leaves
    the recorded attribution intact (survival)."""
    ann_real = _annotation(
        _ulid("A1"), "2026-08-15T00:00:01+00:00", WPInnerStateDelta(agent="claude")
    )
    ann_blank = _annotation(
        _ulid("A2"), "2026-08-15T00:00:02+00:00", WPInnerStateDelta(agent="")
    )

    wp = reduce([], [ann_real, ann_blank]).work_packages["WP01"]

    assert wp["agent"] == "claude"


def test_empty_agent_delta_is_noop_in_apply_even_from_legacy_log() -> None:
    """Defense for an already-persisted legacy ``agent: ""`` delta: even when the
    fold receives a delta whose ``agent`` slot is empty (constructed via the wire
    decoder), the reducer treats it as a no-op rather than blanking the slot."""
    from spec_kitty_events.diary import _apply_annotation_delta

    state: dict[str, object] = {"lane": str(Lane.IN_PROGRESS), "agent": "claude"}
    # Simulate a legacy on-disk delta carrying an explicit empty string: bypass
    # the write-boundary normalization by injecting into the wire dict directly.
    legacy = WPInnerStateDelta.from_dict({"agent": ""})
    # Even if a legacy log somehow persisted the empty string, force the fold to
    # observe it and assert the reducer guard holds.
    object.__setattr__(legacy, "agent", "")

    _apply_annotation_delta(state, legacy)

    assert state["agent"] == "claude"


def test_empty_agent_in_claim_sidecar_is_noop() -> None:
    """The ``planned -> claimed`` claim-exception arm treats an empty ``agent``
    policy-metadata sidecar as a no-op (does not write a blank slot)."""
    claim = StatusEvent(
        event_id=_ulid("C1"),
        mission_slug=_MISSION_SLUG,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at="2026-08-15T00:00:01+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
        policy_metadata={"agent": ""},
    )

    wp = reduce([claim], []).work_packages["WP01"]

    assert wp.get("agent", None) != ""


# ---------------------------------------------------------------------------
# Part 3 — doctor net (no false Healthy over a blanked slot)
# ---------------------------------------------------------------------------


def _write_snapshot(feature_dir: Path, wp_state: dict[str, object]) -> None:
    status_data = {
        "mission_slug": _MISSION_SLUG,
        "materialized_at": "2026-08-15T00:00:01+00:00",
        "event_count": 1,
        "last_event_id": _ulid("E1"),
        "work_packages": {"WP01": wp_state},
        "summary": {},
    }
    (feature_dir / "status.json").write_text(json.dumps(status_data), encoding="utf-8")
    event = {
        "event_id": _ulid("E1"),
        "mission_slug": _MISSION_SLUG,
        "wp_id": "WP01",
        "from_lane": "planned",
        "to_lane": str(wp_state.get("lane", "in_progress")),
        "at": "2026-08-15T00:00:01+00:00",
        "actor": "claude",
        "force": False,
        "execution_mode": "worktree",
    }
    (feature_dir / "status.events.jsonl").write_text(
        json.dumps(event) + "\n", encoding="utf-8"
    )


def test_check_blanked_runtime_slots_flags_empty_agent_on_active_wp() -> None:
    """Unit: the new check flags an empty-string runtime slot on a non-terminal
    WP as an error finding."""
    snapshot = {
        "work_packages": {
            "WP01": {"lane": str(Lane.IN_PROGRESS), "agent": ""},
        }
    }
    findings = check_blanked_runtime_slots(snapshot)
    assert len(findings) == 1
    assert findings[0].category == Category.BLANKED_RUNTIME_SLOT
    assert findings[0].severity == Severity.ERROR
    assert findings[0].wp_id == "WP01"


def test_check_blanked_runtime_slots_ignores_terminal_wp() -> None:
    """A terminal WP (done/canceled) with a blank slot is not flagged."""
    snapshot = {
        "work_packages": {
            "WP01": {"lane": str(Lane.DONE), "agent": ""},
            "WP02": {"lane": str(Lane.CANCELED), "model": ""},
        }
    }
    assert check_blanked_runtime_slots(snapshot) == []


def test_check_blanked_runtime_slots_clean_when_populated() -> None:
    """A populated attribution slot yields no finding."""
    snapshot = {
        "work_packages": {
            "WP01": {"lane": str(Lane.IN_PROGRESS), "agent": "claude"},
        }
    }
    assert check_blanked_runtime_slots(snapshot) == []


def test_status_doctor_not_healthy_over_blanked_agent_slot(tmp_path: Path) -> None:
    """End-to-end: ``run_doctor`` over a snapshot with a blanked runtime slot on
    an active WP reports non-Healthy (was falsely Healthy before FR-014)."""
    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    _write_snapshot(
        feature_dir,
        {
            "lane": str(Lane.IN_PROGRESS),
            "actor": "claude",
            "last_transition_at": "2026-08-15T00:00:01+00:00",
            "last_event_id": _ulid("E1"),
            "force_count": 0,
            "agent": "",
        },
    )

    result = run_doctor(
        feature_dir=feature_dir, mission_slug=_MISSION_SLUG, repo_root=tmp_path
    )

    assert result.is_healthy is False
    blanked = result.findings_by_category(Category.BLANKED_RUNTIME_SLOT)
    assert len(blanked) == 1
    assert blanked[0].wp_id == "WP01"


def test_status_doctor_healthy_when_attribution_present(tmp_path: Path) -> None:
    """Control: a populated attribution slot leaves the mission Healthy."""
    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    _write_snapshot(
        feature_dir,
        {
            "lane": str(Lane.IN_PROGRESS),
            "actor": "claude",
            "last_transition_at": "2026-08-15T00:00:01+00:00",
            "last_event_id": _ulid("E1"),
            "force_count": 0,
            "agent": "claude",
        },
    )

    result = run_doctor(
        feature_dir=feature_dir, mission_slug=_MISSION_SLUG, repo_root=tmp_path
    )

    assert result.findings_by_category(Category.BLANKED_RUNTIME_SLOT) == []
