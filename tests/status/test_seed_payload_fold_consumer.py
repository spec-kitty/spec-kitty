"""#6058 consumer guard: a losing reconstruction seed still fills the claim slots.

``migration:backfill_runtime_state`` writes a ``planned -> claimed`` seed whose
``policy_metadata`` sidecar carries the agent and process attribution of a
legacy claim. When a real claim sits at the same ``at`` and sorts first, the
seed loses the lane contest. ``spec-kitty-events`` 10.4.2 dropped such a seed
whole, so its ``agent`` / ``shell_pid`` / ``shell_pid_created_at`` never reached
the snapshot and 47 archived Missions reduced to a different ``status.json``
than the one frozen in the repository (the SNAPSHOT_DRIFT audit blockers).
``spec-kitty-events`` 10.4.4 folds a losing seed's sidecar into the slots no
real event wrote, and leaves the lane to the real event.

The fold lives upstream. This file is the CLI's own guard that its reducer
entry point (``materialize_snapshot``, the read-only twin of ``materialize``)
keeps delivering it, so a later events release cannot regress the attribution
unseen. It lives in ``tests/status`` because ``tests/contract/
spec_kitty_events_consumer/`` is outside the per-PR matrix.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specify_cli.status import EVENTS_FILENAME, materialize_snapshot

pytestmark = pytest.mark.fast

_SLUG = "058-seed-payload-fold-consumer"
_SEED_ACTOR = "migration:backfill_runtime_state"

_REAL_CLAIM_ID = "01JAAAA0000000000000000042"
# Sorts after the real claim at an equal ``at``: the seed is the loser of the
# contest for the lane, which is the shape the fold exists for.
_SEED_ID = "01JZZZZ0000000000000000044"

_SEED_SIDECAR: dict[str, Any] = {"agent": "codex", "shell_pid": 4242, "shell_pid_created_at": "1790000000.5"}


def _row(
    *,
    event_id: str,
    from_lane: str,
    to_lane: str,
    at: str,
    actor: str = "claude",
    policy_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "actor": actor,
        "at": at,
        "event_id": event_id,
        "evidence": None,
        "execution_mode": "worktree",
        "force": False,
        "from_lane": from_lane,
        "mission_slug": _SLUG,
        "reason": None,
        "review_ref": None,
        "to_lane": to_lane,
        "wp_id": "WP01",
    }
    if policy_metadata is not None:
        row["policy_metadata"] = policy_metadata
    return row


def _mission(tmp_path: Path, *, real_claim_sidecar: dict[str, Any] | None) -> Path:
    """A mission whose seed ties the real claim on ``at`` and sorts after it."""
    feature_dir = tmp_path / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    rows = [
        _row(
            event_id="01JAAAA0000000000000000041",
            from_lane="genesis",
            to_lane="planned",
            at="2026-08-26T10:00:00+00:00",
        ),
        _row(
            event_id=_REAL_CLAIM_ID,
            from_lane="planned",
            to_lane="claimed",
            at="2026-08-26T10:01:00+00:00",
            policy_metadata=real_claim_sidecar,
        ),
        _row(
            event_id=_SEED_ID,
            from_lane="planned",
            to_lane="claimed",
            at="2026-08-26T10:01:00+00:00",
            actor=_SEED_ACTOR,
            policy_metadata=_SEED_SIDECAR,
        ),
        _row(
            event_id="01JAAAA0000000000000000043",
            from_lane="claimed",
            to_lane="in_progress",
            at="2026-08-26T10:02:00+00:00",
        ),
    ]
    (feature_dir / EVENTS_FILENAME).write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_number": 58, "mission_slug": _SLUG, "mission_type": "software-dev"}) + "\n",
        encoding="utf-8",
    )
    return feature_dir


def test_losing_seed_supplies_attribution_the_real_claim_left_empty(tmp_path: Path) -> None:
    """A real claim with no sidecar plus a losing seed: the seed's slots survive."""
    feature_dir = _mission(tmp_path, real_claim_sidecar=None)

    wp = materialize_snapshot(feature_dir).work_packages["WP01"]

    assert wp["lane"] == "in_progress"
    assert wp["agent"] == "codex"
    assert wp["shell_pid"] == 4242
    assert wp["shell_pid_created_at"] == "1790000000.5"


def test_real_claim_sidecar_wins_over_a_losing_seed(tmp_path: Path) -> None:
    """Where the real claim wrote its own sidecar, the seed fills nothing."""
    real = {"agent": "claude", "shell_pid": 99, "shell_pid_created_at": "1800000000.25"}
    feature_dir = _mission(tmp_path, real_claim_sidecar=real)

    wp = materialize_snapshot(feature_dir).work_packages["WP01"]

    assert wp["lane"] == "in_progress"
    assert wp["agent"] == "claude"
    assert wp["shell_pid"] == 99
    assert wp["shell_pid_created_at"] == "1800000000.25"


def test_losing_seed_never_moves_the_lane(tmp_path: Path) -> None:
    """The fold is attribution only: the lane is the real events' lane, with or without the seed."""
    with_seed = _mission(tmp_path / "with-seed", real_claim_sidecar=None)
    without_seed = _mission(tmp_path / "without-seed", real_claim_sidecar=None)
    kept = [line for line in (without_seed / EVENTS_FILENAME).read_text(encoding="utf-8").splitlines() if _SEED_ID not in line]
    (without_seed / EVENTS_FILENAME).write_text("\n".join(kept) + "\n", encoding="utf-8")

    lane_with = materialize_snapshot(with_seed).work_packages["WP01"]["lane"]
    lane_without = materialize_snapshot(without_seed).work_packages["WP01"]["lane"]

    assert lane_with == lane_without == "in_progress"
