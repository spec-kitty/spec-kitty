"""Contract tests for the three model-built post-mission lifecycle payloads (#6438).

Each of ``emit_mission_reopened``, ``emit_follow_up_recorded`` and
``emit_reviewer_self_approval`` must build its payload through its published
``spec_kitty_events`` model, so that:

* a successful emit persists exactly that model's JSON dump (contract C-1), and
* a payload the model rejects raises *before* anything is appended (contract C-2).

Each emitter gets one shared fixture used by both the positive and the negative
assertion, so "nothing was written" is proven against a log that provably can
receive a line (``acceptance-criteria-non-vacuity``: refusal paired with a
same-fixture positive control).

The negative case per emitter is deliberately a field only the *model*
constrains — never one the emitter's own guard already rejects, which would make
the test pass before the change.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, cast

import pytest
from pydantic import ValidationError
from spec_kitty_events.lifecycle import FollowUpRecordedPayload, MissionReopenedPayload
from spec_kitty_events.project_lifecycle import ReviewerSelfApprovalPayload

from specify_cli.status.lifecycle_events import (
    emit_follow_up_recorded,
    emit_mission_reopened,
    emit_reviewer_self_approval,
    mission_event_log_path,
    read_lifecycle_events,
)

pytestmark = pytest.mark.fast

MISSION_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
REOPENED_AT = "2026-05-01T09:00:00+00:00"


def _completed_mission(tmp_path: Path) -> Path:
    """A mission that has merged, so the post-mission guards let an emit through."""
    feature_dir = tmp_path / "kitty-specs" / "071-completed"
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "created_at": "2026-04-01T10:00:00+00:00",
        "friendly_name": feature_dir.name,
        "merged_at": "2026-04-02T10:00:00+00:00",
        "merged_by": "merger",
        "merged_into": "main",
        "mission_id": MISSION_ID,
        "mission_number": int(feature_dir.name.split("-", 1)[0]),
        "mission_slug": feature_dir.name,
        "mission_type": "software-dev",
        "slug": feature_dir.name,
        "target_branch": "main",
    }
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return feature_dir


def _line_count(feature_dir: Path) -> int:
    log_path = mission_event_log_path(feature_dir)
    if not log_path.exists():
        return 0
    return len(read_lifecycle_events(log_path))


def _last_payload(feature_dir: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", read_lifecycle_events(mission_event_log_path(feature_dir))[-1]["payload"])


# ---------------------------------------------------------------------------
# MissionReopened — MissionReopenedPayload
# ---------------------------------------------------------------------------


def test_mission_reopened_payload_is_the_mission_reopened_model_dump(tmp_path: Path) -> None:
    """A valid re-open persists exactly ``MissionReopenedPayload(...).model_dump()``."""
    feature_dir = _completed_mission(tmp_path)
    before = _line_count(feature_dir)

    event = emit_mission_reopened(
        feature_dir,
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        reason="customer regression 4711",
        reopened_by="tester",
        reopened_at=REOPENED_AT,
        cleared_merge={"merged_at": "2026-04-02T10:00:00+00:00"},
    )

    assert event is not None
    assert _line_count(feature_dir) == before + 1

    persisted = _last_payload(feature_dir)
    expected = MissionReopenedPayload(
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        reason="customer regression 4711",
        reopened_by="tester",
        reopened_at=REOPENED_AT,
        cleared_merge={"merged_at": "2026-04-02T10:00:00+00:00"},
    ).model_dump(mode="json", exclude_none=False)

    assert persisted == expected
    # The row writer serializes with ``sort_keys=True``; what matters here is that
    # the key *set* is exactly the model's field set (no extras, none omitted).
    assert set(persisted) == set(MissionReopenedPayload.model_fields)


def test_mission_reopened_keeps_null_cleared_merge(tmp_path: Path) -> None:
    """The optional ``cleared_merge`` is persisted as ``null``, never omitted."""
    feature_dir = _completed_mission(tmp_path)

    emit_mission_reopened(
        feature_dir,
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        reason="operator re-opened",
        reopened_by="tester",
        reopened_at=REOPENED_AT,
    )

    persisted = _last_payload(feature_dir)
    assert "cleared_merge" in persisted
    assert persisted["cleared_merge"] is None


@pytest.mark.parametrize("bad_reason", ["", None], ids=["empty", "none"])
def test_mission_reopened_rejects_a_reason_the_model_refuses(tmp_path: Path, bad_reason: object) -> None:
    """``MissionReopenedPayload.reason`` is non-empty; a bad reason writes nothing."""
    feature_dir = _completed_mission(tmp_path)
    before = _line_count(feature_dir)

    with pytest.raises(ValidationError):
        emit_mission_reopened(
            feature_dir,
            mission_id=MISSION_ID,
            mission_slug=feature_dir.name,
            reason=cast("str", bad_reason),
            reopened_by="tester",
            reopened_at=REOPENED_AT,
        )

    assert _line_count(feature_dir) == before


# ---------------------------------------------------------------------------
# FollowUpRecorded — FollowUpRecordedPayload
# ---------------------------------------------------------------------------


FollowUpType = Literal["commit", "pr"]


@pytest.mark.parametrize(
    ("follow_up_type", "reference"),
    [("commit", {"commit_sha": "a" * 40}), ("pr", {"pr_number": 4711})],
    ids=["commit", "pr"],
)
def test_follow_up_recorded_payload_is_the_follow_up_recorded_model_dump(tmp_path: Path, follow_up_type: FollowUpType, reference: dict[str, Any]) -> None:
    """Both discriminators persist exactly the ``FollowUpRecordedPayload`` dump."""
    feature_dir = _completed_mission(tmp_path)
    before = _line_count(feature_dir)

    emit_follow_up_recorded(
        feature_dir,
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        follow_up_type=follow_up_type,
        recorded_by="tester",
        recorded_at=REOPENED_AT,
        **reference,
    )

    assert _line_count(feature_dir) == before + 1

    persisted = _last_payload(feature_dir)
    expected = FollowUpRecordedPayload(
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        follow_up_type=follow_up_type,
        recorded_by="tester",
        recorded_at=REOPENED_AT,
        **reference,
    ).model_dump(mode="json", exclude_none=False)

    assert persisted == expected
    assert set(persisted) == set(FollowUpRecordedPayload.model_fields)
    # The unused reference stays an explicit null.
    unused = "pr_number" if follow_up_type == "commit" else "commit_sha"
    assert persisted[unused] is None


def test_follow_up_recorded_rejects_a_recorded_by_the_model_refuses(tmp_path: Path) -> None:
    """An empty ``recorded_by`` is model-invalid and writes nothing.

    The emitter's own guard covers a missing commit/PR reference, so the negative
    case here must be a field only the model constrains.
    """
    feature_dir = _completed_mission(tmp_path)
    before = _line_count(feature_dir)

    with pytest.raises(ValidationError):
        emit_follow_up_recorded(
            feature_dir,
            mission_id=MISSION_ID,
            mission_slug=feature_dir.name,
            follow_up_type="commit",
            commit_sha="b" * 40,
            recorded_by="",
            recorded_at=REOPENED_AT,
        )

    assert _line_count(feature_dir) == before


# ---------------------------------------------------------------------------
# ReviewerSelfApproval — ReviewerSelfApprovalPayload
# ---------------------------------------------------------------------------


def _wp_feature_dir(tmp_path: Path) -> Path:
    """A feature directory for the WP-level emitter (no completion guard)."""
    feature_dir = tmp_path / "kitty-specs" / "072-wp-level"
    feature_dir.mkdir(parents=True, exist_ok=True)
    return feature_dir


def test_reviewer_self_approval_payload_is_the_self_approval_model_dump(tmp_path: Path) -> None:
    """A fallback approval persists exactly the ``ReviewerSelfApprovalPayload`` dump."""
    feature_dir = _wp_feature_dir(tmp_path)
    before = _line_count(feature_dir)

    emit_reviewer_self_approval(
        feature_dir,
        mission_slug=feature_dir.name,
        wp_id="WP01",
        implementing_actor="implementer",
        intended_reviewer="reviewer",
        failure_reason="reviewer unavailable",
        at=REOPENED_AT,
    )

    assert _line_count(feature_dir) == before + 1

    persisted = _last_payload(feature_dir)
    expected = ReviewerSelfApprovalPayload(
        mission_slug=feature_dir.name,
        wp_id="WP01",
        implementing_actor="implementer",
        intended_reviewer="reviewer",
        failure_reason="reviewer unavailable",
        fallback_approved=True,
        timestamp=REOPENED_AT,
    ).model_dump(mode="json", exclude_none=False)

    assert persisted == expected
    assert set(persisted) == set(ReviewerSelfApprovalPayload.model_fields)


def test_reviewer_self_approval_rejects_a_failure_reason_the_model_refuses(tmp_path: Path) -> None:
    """An empty ``failure_reason`` is model-invalid and writes nothing."""
    feature_dir = _wp_feature_dir(tmp_path)
    before = _line_count(feature_dir)

    with pytest.raises(ValidationError):
        emit_reviewer_self_approval(
            feature_dir,
            mission_slug=feature_dir.name,
            wp_id="WP01",
            implementing_actor="implementer",
            intended_reviewer="reviewer",
            failure_reason="",
            at=REOPENED_AT,
        )

    assert _line_count(feature_dir) == before
