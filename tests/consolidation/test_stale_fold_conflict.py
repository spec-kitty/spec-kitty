"""Red-first #5967 — the event-log merge driver must REFUSE (conflict) a fold
whose concurrent transitions diverge, instead of silently LWW-folding them.

Two teammates on two clones of one lanes Mission. A status transition made in a
clone that has not pulled is folded OVER a transition the other teammate already
pushed, once ``git pull`` runs the union merge driver on the two
``status.events.jsonl`` logs and the wall-clock LWW reducer applies the stale
row last. Two shapes land unwanted code on the target at exit 0:

* **cancel** — the lead cancels WP02 (``in_progress -> canceled``, force); the
  implementer (not pulled) submits it (``in_progress -> for_review``). The fold
  buries the cancel; the board shows ``for_review`` and a reviewer approves the
  descoped work.
* **rework** — a reviewer rejects WP01 (``in_review -> planned``, force) and the
  implementer reclaims it; a second reviewer (not pulled) approves it
  (``in_review -> approved``). The fold buries the rejection.

The true causal-ordering root is ``spec_kitty_events.diary._should_apply_event``
(out of this repo; a sibling upstream PR tightens it). The in-repo backstop: the
union driver (``run_event_log_driver``) must detect that both sides independently
departed the SAME lane to DIFFERENT lanes for one WP — a concurrent fork no
union can silently resolve — and FAIL the merge so ``git`` leaves a conflict for
the user, the safe pre-#5759 behaviour. A one-sided extension, the same decision
on both sides, or concurrent work on DIFFERENT work packages must still merge
cleanly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.consolidation.drivers import MergeDriverError, run_event_log_driver
from specify_cli.status.event_log_merge import detect_concurrent_fork

pytestmark = pytest.mark.fast

_SLUG = "team-5967"


def _ev(seq: int, wp: str, frm: str, to: str, *, force: bool = False) -> dict[str, object]:
    return {
        "actor": "claude",
        "at": f"2026-10-09T00:{seq // 60:02d}:{seq % 60:02d}+00:00",
        "event_id": f"01E5967{seq:019d}",
        "execution_mode": "worktree",
        "feature_slug": _SLUG,
        "force": force,
        "from_lane": frm,
        "mission_slug": _SLUG,
        "reason": None,
        "review_ref": None,
        "to_lane": to,
        "wp_id": wp,
    }


_BASE_WP02 = [_ev(0, "WP02", "genesis", "planned"), _ev(1, "WP02", "planned", "claimed"), _ev(2, "WP02", "claimed", "in_progress")]
_BASE_WP01_FR = [
    _ev(0, "WP01", "genesis", "planned"),
    _ev(1, "WP01", "planned", "claimed"),
    _ev(2, "WP01", "claimed", "in_progress"),
    _ev(3, "WP01", "in_progress", "for_review"),
]


def _write(tmp: Path, name: str, rows: list[dict[str, object]]) -> Path:
    path = tmp / name
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# the pure detector
# --------------------------------------------------------------------------- #


def test_detect_fork_flags_the_cancel_shape() -> None:
    ours = _BASE_WP02 + [_ev(3, "WP02", "in_progress", "canceled", force=True)]  # lead descopes
    theirs = _BASE_WP02 + [_ev(4, "WP02", "in_progress", "for_review")]  # stale implementer submit
    assert detect_concurrent_fork(_BASE_WP02, ours, theirs) is not None


def test_detect_fork_flags_the_rework_shape() -> None:
    ours = _BASE_WP01_FR + [_ev(4, "WP01", "for_review", "in_review"), _ev(5, "WP01", "in_review", "approved")]  # stale approve
    theirs = _BASE_WP01_FR + [
        _ev(6, "WP01", "for_review", "in_review"),
        _ev(7, "WP01", "in_review", "planned", force=True),  # pushed rejection
        _ev(8, "WP01", "planned", "claimed"),
        _ev(9, "WP01", "claimed", "in_progress"),
    ]
    assert detect_concurrent_fork(_BASE_WP01_FR, ours, theirs) is not None


def test_detect_fork_ignores_one_sided_extension() -> None:
    ours = _BASE_WP02 + [_ev(3, "WP02", "in_progress", "for_review")]
    theirs = list(_BASE_WP02)  # no concurrent WP02 departure
    assert detect_concurrent_fork(_BASE_WP02, ours, theirs) is None


def test_detect_fork_ignores_the_same_decision_on_both_sides() -> None:
    ours = _BASE_WP02 + [_ev(3, "WP02", "in_progress", "for_review")]
    theirs = _BASE_WP02 + [_ev(4, "WP02", "in_progress", "for_review")]  # same to_lane, different event
    assert detect_concurrent_fork(_BASE_WP02, ours, theirs) is None


def test_detect_fork_ignores_concurrent_work_on_different_wps() -> None:
    ours = _BASE_WP02 + [_ev(3, "WP02", "in_progress", "for_review")]
    theirs = _BASE_WP02 + [_ev(10, "WP01", "genesis", "planned"), _ev(11, "WP01", "planned", "claimed")]
    assert detect_concurrent_fork(_BASE_WP02, ours, theirs) is None


# --------------------------------------------------------------------------- #
# the git merge driver entrypoint
# --------------------------------------------------------------------------- #


def test_driver_conflicts_on_the_cancel_fold(tmp_path: Path) -> None:
    base = _write(tmp_path, "base", _BASE_WP02)
    ours = _write(tmp_path, "ours", _BASE_WP02 + [_ev(3, "WP02", "in_progress", "canceled", force=True)])
    theirs = _write(tmp_path, "theirs", _BASE_WP02 + [_ev(4, "WP02", "in_progress", "for_review")])
    with pytest.raises(MergeDriverError):
        run_event_log_driver(str(base), str(ours), str(theirs))


def test_driver_conflicts_on_the_rework_fold(tmp_path: Path) -> None:
    base = _write(tmp_path, "base", _BASE_WP01_FR)
    ours = _write(tmp_path, "ours", _BASE_WP01_FR + [_ev(4, "WP01", "for_review", "in_review"), _ev(5, "WP01", "in_review", "approved")])
    theirs = _write(
        tmp_path,
        "theirs",
        _BASE_WP01_FR + [_ev(6, "WP01", "for_review", "in_review"), _ev(7, "WP01", "in_review", "planned", force=True)],
    )
    with pytest.raises(MergeDriverError):
        run_event_log_driver(str(base), str(ours), str(theirs))


def test_driver_still_folds_a_clean_concurrent_merge(tmp_path: Path) -> None:
    """Different-WP concurrent work merges cleanly (no false conflict)."""
    base = _write(tmp_path, "base", _BASE_WP02)
    ours = _write(tmp_path, "ours", _BASE_WP02 + [_ev(3, "WP02", "in_progress", "for_review")])
    theirs = _write(tmp_path, "theirs", _BASE_WP02 + [_ev(10, "WP01", "genesis", "planned")])
    run_event_log_driver(str(base), str(ours), str(theirs))  # no raise
    merged = [json.loads(line) for line in ours.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = {row["event_id"] for row in merged}
    assert len(ids) == len(merged)  # union, deduped
