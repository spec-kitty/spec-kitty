"""#6061 consumer guard: a rollback-shaped seed never takes a lane it does not continue.

``migration:verdict_provenance_backfill`` appends a reconstruction seed per
reviewed WP: a rollback seed (``in_review -> in_progress``, verdict
``changes_requested``) or its bare sibling, an approval seed (``in_review ->
approved``). ``spec-kitty-events`` 10.4.4 let a rollback seed take the lane even
when the WP's real lifecycle had not been in review (079 WP03/WP07 read
``in_progress`` instead of ``planned``) or had already moved on (a merged
``done`` WP could read ``in_progress``). Since 10.4.6 a rollback seed needs lane
continuity, except against its bare sibling approval.

The rule lives upstream. This file is the CLI's own guard that its reducer entry
point (``materialize_snapshot``, the read-only twin of ``materialize``) keeps
delivering it, so a later events release cannot regress it unseen. The first two
cases are red on 10.4.4; the third is a ratchet whose positive control is the
first.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specify_cli.status import EVENTS_FILENAME, materialize_snapshot

pytestmark = pytest.mark.fast

_SLUG = "061-seed-lane-authority-consumer"
_WP = "WP01"
# Literal on purpose: the constant is not importable on every base.
_COMPAT_ACTOR = "migration:backfill_runtime_state:compatibility"
_BACKFILL_ACTOR = "migration:backfill_runtime_state"
_VERDICT_ACTOR = "migration:verdict_provenance_backfill"

_ROLLBACK_VERDICT = {"reviewer": "unknown", "verdict": "changes_requested", "reference": "review-cycle://x/WP01/review-cycle-1.md"}
_APPROVAL_VERDICT = {"reviewer": "unknown", "verdict": "approved", "reference": "review-cycle://x/WP01/approval.md"}


def _row(
    n: int,
    *,
    from_lane: str,
    to_lane: str,
    at: str,
    actor: str = "claude",
    force: bool = False,
    reason: str | None = None,
    policy_metadata: dict[str, Any] | None = None,
    review_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "actor": actor,
        "at": at,
        "event_id": f"01JAAAA00000000000000000{n:02d}",
        "evidence": None,
        "execution_mode": "worktree",
        "force": force,
        "from_lane": from_lane,
        "mission_slug": _SLUG,
        "policy_metadata": policy_metadata,
        "reason": reason,
        "review_ref": None,
        "review_result": review_result,
        "to_lane": to_lane,
        "wp_id": _WP,
    }


def _rollback_seed(n: int, at: str) -> dict[str, Any]:
    return _row(n, from_lane="in_review", to_lane="in_progress", at=at, actor=_VERDICT_ACTOR, review_result=_ROLLBACK_VERDICT)


def _approval_seed(n: int, at: str) -> dict[str, Any]:
    return _row(n, from_lane="in_review", to_lane="approved", at=at, actor=_VERDICT_ACTOR, review_result=_APPROVAL_VERDICT)


def _mission(tmp_path: Path, rows: list[dict[str, Any]]) -> Path:
    feature_dir = tmp_path / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / EVENTS_FILENAME).write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_number": 61, "mission_slug": _SLUG, "mission_type": "software-dev"}) + "\n",
        encoding="utf-8",
    )
    return feature_dir


def _verdict(wp: dict[str, Any]) -> str | None:
    result = wp.get("review_result")
    return result.get("verdict") if isinstance(result, dict) else None


@pytest.mark.regression
def test_rollback_seed_after_real_done_leaves_the_lane_and_verdict(tmp_path: Path) -> None:
    """A real approved -> done lifecycle is not rolled back by a later rollback seed."""
    rows = [
        _row(1, from_lane="genesis", to_lane="planned", at="2026-08-26T10:00:00+00:00"),
        _row(2, from_lane="planned", to_lane="claimed", at="2026-08-26T10:01:00+00:00"),
        _row(3, from_lane="claimed", to_lane="in_progress", at="2026-08-26T10:02:00+00:00"),
        _row(4, from_lane="in_progress", to_lane="in_review", at="2026-08-26T10:03:00+00:00"),
        _row(5, from_lane="in_review", to_lane="approved", at="2026-08-26T10:04:00+00:00", review_result=_APPROVAL_VERDICT),
        _row(6, from_lane="approved", to_lane="done", at="2026-08-26T10:05:00+00:00"),
        _rollback_seed(7, "2026-08-26T10:06:00+00:00"),
    ]

    wp = materialize_snapshot(_mission(tmp_path, rows)).work_packages[_WP]

    assert wp["lane"] == "done"
    assert _verdict(wp) == "approved"


@pytest.mark.regression
def test_079_shape_rollback_seed_does_not_take_a_lane_the_wp_never_reached(tmp_path: Path) -> None:
    """finalize-tasks planned->planned, a reverted backfill seed pair, then a rollback seed: planned."""
    rows = [
        _row(1, from_lane="planned", to_lane="planned", at="2026-04-09T07:43:40.886696+00:00", actor="finalize-tasks", force=True, reason="canonical bootstrap"),
        _row(
            2,
            from_lane="planned",
            to_lane="claimed",
            at="2026-04-09T07:43:40.886696+00:00",
            actor=_BACKFILL_ACTOR,
            policy_metadata={"agent": "claude:opus:reviewer:reviewer", "shell_pid": 98850},
        ),
        _row(
            3,
            from_lane="claimed",
            to_lane="planned",
            at="2026-04-09T07:43:40.886697+00:00",
            actor=_COMPAT_ACTOR,
            reason="append-only repair for persisted pre-floor seed",
        ),
        _rollback_seed(4, "2026-04-09T08:53:16+00:00"),
    ]

    wp = materialize_snapshot(_mission(tmp_path, rows)).work_packages[_WP]

    assert wp["lane"] == "planned"
    assert _verdict(wp) == "changes_requested"


@pytest.mark.parametrize("approval_first", [True, False], ids=["approval-first", "rollback-first"])
def test_bare_sibling_pair_keeps_the_rollback_in_either_order(tmp_path: Path, approval_first: bool) -> None:
    """Ratchet: the rollback seed still wins against its bare sibling approval, whichever sorts first."""
    at = "2026-08-26T10:04:00+00:00"
    pair = [_approval_seed(5, at), _rollback_seed(6, at)]
    if not approval_first:
        pair = [_rollback_seed(5, at), _approval_seed(6, at)]
    rows = [
        _row(1, from_lane="genesis", to_lane="planned", at="2026-08-26T10:00:00+00:00"),
        _row(2, from_lane="planned", to_lane="claimed", at="2026-08-26T10:01:00+00:00"),
        _row(3, from_lane="claimed", to_lane="in_progress", at="2026-08-26T10:02:00+00:00"),
        _row(4, from_lane="in_progress", to_lane="in_review", at="2026-08-26T10:03:00+00:00"),
        *pair,
    ]

    wp = materialize_snapshot(_mission(tmp_path, rows)).work_packages[_WP]

    assert wp["lane"] == "in_progress"
    assert _verdict(wp) == "changes_requested"
