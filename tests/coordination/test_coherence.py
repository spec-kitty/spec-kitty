"""Owner-level coherence tests for ``coordination.coherence`` (WP02, #2786/#2367-B).

Pins the anti-fakeable strand-derivation contract (FR-009 / SC-007) and the
strand-gated repair primitive at the single coordination-domain owner, plus the
``iter_pending_coord_reconcile_markers`` enumeration seam that the doctor (WP04)
consumes because ``load_state(mission_id=None)`` raises on >=2 states.

Import ``specify_cli.status`` before any coordination submodule to mirror the
production import order (``specify_cli/__init__`` imports ``status`` first) and
avoid the known ``coordination -> transaction -> status`` init-order cycle when a
test module imports coordination first.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import specify_cli.status  # noqa: F401  # import-order guard (see module docstring)
from specify_cli.coordination.coherence import (
    CoordRepairOutcome,
    coord_incoherent_done_wps,
    repair_coord_strand,
)
from specify_cli.merge.state import (
    MergeAmbiguousStateError,
    MergeState,
    iter_pending_coord_reconcile_markers,
    load_state,
    save_state,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

MISSION_SLUG = "coherence-fixture-01KXTM59"
_EVENTS_REL = f"kitty-specs/{MISSION_SLUG}/status.events.jsonl"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-qb", "main", str(repo)], check=True, capture_output=True)
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


def _event(wp_id: str, to_lane: str, *, at: str, event_id: str, from_lane: str) -> dict[str, object]:
    return {
        "actor": "reviewer-renata",
        "at": at,
        "event_id": event_id,
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": MISSION_SLUG,
        "force": False,
        "from_lane": from_lane,
        "reason": None,
        "review_ref": None,
        "to_lane": to_lane,
        "wp_id": wp_id,
    }


def _write_meta(feature_dir: Path) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": MISSION_SLUG,
                "mission_id": "01KXTM59000000000000000000",
                "mission_number": None,
                "mission_type": "software-dev",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_events(feature_dir: Path, events: list[dict[str, object]]) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "status.events.jsonl").write_text(
        "".join(json.dumps(e, sort_keys=True) + "\n" for e in events),
        encoding="utf-8",
    )


def _seed_committed_coord_ref(
    repo: Path, events: list[dict[str, object]], *, branch: str = "coord"
) -> Path:
    """Commit ``events`` onto ``branch`` and return the primary feature_dir."""
    _init_repo(repo)
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    _write_meta(feature_dir)
    _write_events(feature_dir, events)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "seed coord events")
    _git(repo, "branch", branch)
    return feature_dir


# ---------------------------------------------------------------------------
# T007 (a): ≥2-WP anti-fakeable specific-WP derivation
# ---------------------------------------------------------------------------


def test_returns_only_the_stranded_done_wp_not_the_approved_one(tmp_path: Path) -> None:
    """WP-A is done-on-ref, WP-B is only approved. The derivation returns exactly
    ``["WP-A"]`` — falsifying a hardcoded ``["WP01"]`` (wrong id) and an
    ``== candidate_wps`` passthrough (would wrongly include WP-B)."""
    repo = tmp_path / "repo"
    feature_dir = _seed_committed_coord_ref(
        repo,
        [
            _event("WP-A", "approved", at="2026-07-18T10:00:00+00:00", event_id="01A00", from_lane="in_review"),
            _event("WP-A", "done", at="2026-07-18T10:05:00+00:00", event_id="01A01", from_lane="approved"),
            _event("WP-B", "approved", at="2026-07-18T10:00:00+00:00", event_id="01B00", from_lane="in_review"),
        ],
    )

    result = coord_incoherent_done_wps(
        "coord", ["WP-A", "WP-B"], repo_root=repo, feature_dir=feature_dir
    )

    assert result == ["WP-A"]
    # Anti-fakeability: neither a hardcoded literal nor the raw candidate list.
    assert result != ["WP01"]
    assert result != ["WP-A", "WP-B"]


# ---------------------------------------------------------------------------
# T007 (b): pre-existing-done exclusion — the ONLY test distinguishing the
# write-set from ``all_wp_ids``.
# ---------------------------------------------------------------------------


def test_pre_existing_done_wp_outside_write_set_is_excluded(tmp_path: Path) -> None:
    """WP-C is ``done`` on the ref from BEFORE this merge and is NOT in this
    merge's write-set. Deriving over the write-set excludes it — proving that
    passing ``run.all_wp_ids`` (which would include WP-C) is wrong."""
    repo = tmp_path / "repo"
    feature_dir = _seed_committed_coord_ref(
        repo,
        [
            # Pre-existing, legitimately-done WP from a prior merge.
            _event("WP-C", "done", at="2026-07-18T09:00:00+00:00", event_id="01C01", from_lane="approved"),
            # This merge's genuine strand.
            _event("WP-A", "done", at="2026-07-18T10:05:00+00:00", event_id="01A01", from_lane="approved"),
            _event("WP-B", "approved", at="2026-07-18T10:00:00+00:00", event_id="01B00", from_lane="in_review"),
        ],
    )

    # Sanity: WP-C really is done-on-ref (so exclusion is by write-set, not by
    # absence of the done event).
    assert coord_incoherent_done_wps(
        "coord", ["WP-C"], repo_root=repo, feature_dir=feature_dir
    ) == ["WP-C"]

    # The write-set for THIS merge excludes WP-C -> it is not healed.
    write_set = ["WP-A", "WP-B"]
    result = coord_incoherent_done_wps(
        "coord", write_set, repo_root=repo, feature_dir=feature_dir
    )
    assert result == ["WP-A"]
    assert "WP-C" not in result


def test_empty_candidate_and_unresolvable_ref_return_empty(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    feature_dir = _seed_committed_coord_ref(
        repo,
        [_event("WP-A", "done", at="2026-07-18T10:05:00+00:00", event_id="01A01", from_lane="approved")],
    )
    # Empty write-set short-circuits.
    assert coord_incoherent_done_wps("coord", [], repo_root=repo, feature_dir=feature_dir) == []
    # A ref that does not exist -> no events -> empty (non-coord/legacy fallback).
    assert (
        coord_incoherent_done_wps(
            "does-not-exist", ["WP-A"], repo_root=repo, feature_dir=feature_dir
        )
        == []
    )


# ---------------------------------------------------------------------------
# T007 (c): repair strand-gating + idempotency (byte-stable coord log)
# ---------------------------------------------------------------------------


def _committed_events_bytes(repo: Path, branch: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(repo), "show", f"{branch}:{_EVENTS_REL}"],
        check=True,
        capture_output=True,
    )
    return proc.stdout


def test_repair_reverts_strand_then_is_a_byte_stable_noop_on_reapply(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    feature_dir = _seed_committed_coord_ref(
        repo,
        [_event("WP-A", "approved", at="2026-07-18T10:00:00+00:00", event_id="01A00", from_lane="in_review")],
    )
    # captured_sha = coord tip BEFORE the done bake.
    captured_sha = _git(repo, "rev-parse", "coord").stdout.strip()

    # Materialize a coord worktree with the branch checked out and bake the
    # stranding ``done`` commit there (HEAD advances past captured_sha).
    worktree = tmp_path / "coord-wt"
    _git(repo, "worktree", "add", str(worktree), "coord")
    wt_events = worktree / "kitty-specs" / MISSION_SLUG / "status.events.jsonl"
    with wt_events.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                _event("WP-A", "done", at="2026-07-18T10:05:00+00:00", event_id="01A01", from_lane="approved"),
                sort_keys=True,
            )
            + "\n"
        )
    _git(worktree, "add", ".")
    _git(worktree, "commit", "-m", "bake WP-A done (strands on rollback)")

    # Pre-condition: WP-A is stranded done on the committed ref.
    assert coord_incoherent_done_wps(
        "coord", ["WP-A"], repo_root=repo, feature_dir=feature_dir
    ) == ["WP-A"]

    # First repair: performs the git revert.
    first = repair_coord_strand(
        coord_ref="coord",
        captured_sha=captured_sha,
        coord_worktree=worktree,
        candidate_wps=["WP-A"],
        repo_root=repo,
        feature_dir=feature_dir,
    )
    assert isinstance(first, CoordRepairOutcome)
    assert first.healed is True
    assert first.stranded_wp_ids == ["WP-A"]
    assert first.error is None

    # The committed ref is now coherent again (WP-A back to approved).
    assert coord_incoherent_done_wps(
        "coord", ["WP-A"], repo_root=repo, feature_dir=feature_dir
    ) == []
    bytes_after_first = _committed_events_bytes(repo, "coord")

    # Second + third repair: strand-gate short-circuits -> no-op, byte-stable.
    for _ in range(2):
        outcome = repair_coord_strand(
            coord_ref="coord",
            captured_sha=captured_sha,
            coord_worktree=worktree,
            candidate_wps=["WP-A"],
            repo_root=repo,
            feature_dir=feature_dir,
        )
        assert outcome.healed is False
        assert outcome.stranded_wp_ids == []
        assert _committed_events_bytes(repo, "coord") == bytes_after_first


def test_repair_missing_worktree_returns_distinct_outcome(tmp_path: Path) -> None:
    """A marker whose ``coord_worktree`` does not exist → a distinguishable outcome.

    FR-007: the primitive returns ``worktree_missing=True`` (and never touches git)
    so callers can surface a STUCK diagnostic instead of crashing or looping the
    same live-strand error forever. The worktree check short-circuits BEFORE the
    strand gate, so ``stranded_wp_ids`` stays empty.
    """
    repo = tmp_path / "repo"
    feature_dir = _seed_committed_coord_ref(
        repo,
        [_event("WP-A", "done", at="2026-07-18T10:05:00+00:00", event_id="01A01", from_lane="approved")],
    )

    outcome = repair_coord_strand(
        coord_ref="coord",
        captured_sha="deadbeef",
        coord_worktree=tmp_path / "pruned-coord-wt",  # does not exist
        candidate_wps=["WP-A"],
        repo_root=repo,
        feature_dir=feature_dir,
    )

    assert isinstance(outcome, CoordRepairOutcome)
    assert outcome.healed is False
    assert outcome.worktree_missing is True
    assert outcome.stranded_wp_ids == []
    assert outcome.head_advanced is False


def test_repair_refuses_when_head_already_reverted(tmp_path: Path) -> None:
    """HEAD-freshness guard: a concurrent heal already advanced HEAD → refuse.

    Simulates the concurrency TOCTOU: the passed ``coord_ref`` still reduces WP-A
    to ``done`` (a stale view — so the strand gate passes), but the coordination
    worktree HEAD has ALREADY been reverted to a coherent ``approved`` tip. A blind
    ``git revert captured_sha..HEAD`` would then revert that concurrent revert too
    and churn the ref; the guard instead REFUSES (``head_advanced=True``, no revert)
    so a double-heal cannot re-apply ``done``. Without the guard the worktree HEAD
    would advance with fresh revert commits — here it must stay put.
    """
    repo = tmp_path / "repo"
    feature_dir = _seed_committed_coord_ref(
        repo,
        [_event("WP-A", "approved", at="2026-07-18T10:00:00+00:00", event_id="01A00", from_lane="in_review")],
    )
    captured_sha = _git(repo, "rev-parse", "coord").stdout.strip()  # C0 (pre-done)

    worktree = tmp_path / "coord-wt"
    _git(repo, "worktree", "add", str(worktree), "coord")
    wt_events = worktree / "kitty-specs" / MISSION_SLUG / "status.events.jsonl"
    with wt_events.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                _event("WP-A", "done", at="2026-07-18T10:05:00+00:00", event_id="01A01", from_lane="approved"),
                sort_keys=True,
            )
            + "\n"
        )
    _git(worktree, "add", ".")
    _git(worktree, "commit", "-m", "bake WP-A done")
    # Pin a STALE ref at the ``done`` tip (C1) — this is what the gate reads.
    _git(repo, "branch", "coord_done", "coord")

    # A concurrent healer already reverted the ``done`` → worktree HEAD advances to
    # a coherent ``approved`` tip (C2); the ``coord`` branch moves with it.
    _git(worktree, "revert", "--no-edit", "HEAD")
    head_before = _git(worktree, "rev-parse", "HEAD").stdout.strip()

    # Sanity: the stale ref STILL reduces WP-A to done (gate would pass) …
    assert coord_incoherent_done_wps(
        "coord_done", ["WP-A"], repo_root=repo, feature_dir=feature_dir
    ) == ["WP-A"]
    # … while the worktree HEAD is already coherent (approved).
    assert coord_incoherent_done_wps(
        head_before, ["WP-A"], repo_root=repo, feature_dir=feature_dir
    ) == []

    outcome = repair_coord_strand(
        coord_ref="coord_done",  # stale: still reduces to done → gate passes
        captured_sha=captured_sha,
        coord_worktree=worktree,
        candidate_wps=["WP-A"],
        repo_root=repo,
        feature_dir=feature_dir,
    )

    assert outcome.healed is False
    assert outcome.head_advanced is True
    assert outcome.stranded_wp_ids == ["WP-A"]
    # The guard must NOT run a revert — HEAD is unchanged (no re-applied ``done``).
    assert _git(worktree, "rev-parse", "HEAD").stdout.strip() == head_before


def test_repair_refuses_when_worktree_checked_out_a_foreign_branch(tmp_path: Path) -> None:
    """Sibling of #4920: the worktree's checked-out branch must match ``coord_ref``.

    Reproduces the reviewer-reported scenario for ``repair_coord_strand`` (the
    ``git revert`` sibling of the ``git merge --ff-only`` bug #4920 fixed for
    ``doctor coordination --fix``'s branch-mutation path): a pending-reconcile
    marker names a coord worktree, but between capture and heal the worktree is
    switched to a sibling branch created FROM the coord tip (``git switch -c
    scratch``). Both existing content-based guards (``captured_sha`` ancestor of
    HEAD, strand live at HEAD) still pass because ``scratch`` is byte-identical to
    ``coord`` at that point — neither guard inspects which branch is checked out.
    Without a branch-identity check, the ``git revert`` runs inside the worktree
    (i.e. on ``scratch``), mutating a foreign branch while leaving the actual
    ``coord`` ref untouched; the primitive would still report ``healed=True``, and
    the caller (``_heal_one_strand`` / ``_heal_pending_coord_reconcile``) would
    then clear the marker — after which the still-stranded ``coord`` ref is never
    reported again (live-strand findings are enumerated only from markers).
    """
    repo = tmp_path / "repo"
    feature_dir = _seed_committed_coord_ref(
        repo,
        [_event("WP-A", "approved", at="2026-07-18T10:00:00+00:00", event_id="01A00", from_lane="in_review")],
    )
    captured_sha = _git(repo, "rev-parse", "coord").stdout.strip()

    worktree = tmp_path / "coord-wt"
    _git(repo, "worktree", "add", str(worktree), "coord")
    wt_events = worktree / "kitty-specs" / MISSION_SLUG / "status.events.jsonl"
    with wt_events.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                _event("WP-A", "done", at="2026-07-18T10:05:00+00:00", event_id="01A01", from_lane="approved"),
                sort_keys=True,
            )
            + "\n"
        )
    _git(worktree, "add", ".")
    _git(worktree, "commit", "-m", "bake WP-A done (strands on rollback)")

    # Operator (or another process) switches the coord worktree onto a sibling
    # branch created from its current tip. Git permits this freely — ``scratch``
    # is not "the" coord branch, but it descends from it and is byte-identical.
    _git(worktree, "switch", "-c", "scratch")
    scratch_tip_before = _git(worktree, "rev-parse", "scratch").stdout.strip()
    coord_tip_before = _git(repo, "rev-parse", "coord").stdout.strip()

    # Pre-condition: WP-A is genuinely stranded done on the committed coord ref.
    assert coord_incoherent_done_wps(
        "coord", ["WP-A"], repo_root=repo, feature_dir=feature_dir
    ) == ["WP-A"]

    outcome = repair_coord_strand(
        coord_ref="coord",
        captured_sha=captured_sha,
        coord_worktree=worktree,
        candidate_wps=["WP-A"],
        repo_root=repo,
        feature_dir=feature_dir,
    )

    assert outcome.healed is False, (
        "must refuse (not report healed) when the worktree HEAD is not on coord_ref"
    )
    assert outcome.branch_mismatch is True
    # stranded_wp_ids must stay non-empty so neither caller's "clear the marker"
    # branch fires for this outcome (both callers only clear when healed, or when
    # stranded_wp_ids is empty AND worktree_missing is False).
    assert outcome.stranded_wp_ids == ["WP-A"]
    # The foreign branch was NOT mutated by an errant revert.
    assert _git(worktree, "rev-parse", "scratch").stdout.strip() == scratch_tip_before
    # The coord ref itself is untouched — still stranded.
    assert _git(repo, "rev-parse", "coord").stdout.strip() == coord_tip_before
    assert coord_incoherent_done_wps(
        "coord", ["WP-A"], repo_root=repo, feature_dir=feature_dir
    ) == ["WP-A"]


def test_repair_on_already_coherent_ref_is_a_noop(tmp_path: Path) -> None:
    """A ref whose candidate WP is only ever ``approved`` heals to a no-op — the
    repair never reverts the (non-existent) strand."""
    repo = tmp_path / "repo"
    feature_dir = _seed_committed_coord_ref(
        repo,
        [_event("WP-A", "approved", at="2026-07-18T10:00:00+00:00", event_id="01A00", from_lane="in_review")],
    )
    worktree = tmp_path / "coord-wt"
    _git(repo, "worktree", "add", str(worktree), "coord")
    head_before = _git(repo, "rev-parse", "coord").stdout.strip()

    outcome = repair_coord_strand(
        coord_ref="coord",
        captured_sha=head_before,
        coord_worktree=worktree,
        candidate_wps=["WP-A"],
        repo_root=repo,
        feature_dir=feature_dir,
    )
    assert outcome.healed is False
    assert outcome.stranded_wp_ids == []
    # No revert commit was created.
    assert _git(repo, "rev-parse", "coord").stdout.strip() == head_before


# ---------------------------------------------------------------------------
# T004/T007 (d): iter_pending_coord_reconcile_markers enumerates across >=2 dirs
# ---------------------------------------------------------------------------


def _marker() -> dict[str, object]:
    return {
        "coord_ref": "coord",
        "captured_sha": "deadbeef",
        "coord_worktree": "/sentinel/coord-wt",
        "stranded_wp_ids": ["WP-A"],
        "revert_error": None,
        "detected_at": "2026-07-18T10:05:00+00:00",
    }


def _make_state(mission_id: str, *, marker: dict[str, object] | None) -> MergeState:
    return MergeState(
        mission_id=mission_id,
        mission_slug=mission_id,
        target_branch="main",
        wp_order=["WP-A"],
        current_wp="WP-A",
        pending_coord_reconcile=marker,
    )


def test_iter_markers_enumerates_across_multiple_runtime_state_dirs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".kittify").mkdir(parents=True)

    save_state(_make_state("01MID0000000000000000000A0", marker=_marker()), repo)
    save_state(_make_state("01MID0000000000000000000B0", marker=_marker()), repo)
    # A coherent (marker-absent) mission must be skipped.
    save_state(_make_state("01MID0000000000000000000C0", marker=None), repo)

    # load_state(None) cannot be used to enumerate: >=2 active states raise.
    with pytest.raises(MergeAmbiguousStateError):
        load_state(repo, None)

    markers = list(iter_pending_coord_reconcile_markers(repo))
    mission_ids = {s.mission_id for s in markers}
    assert mission_ids == {"01MID0000000000000000000A0", "01MID0000000000000000000B0"}
    assert all(s.pending_coord_reconcile is not None for s in markers)
    # The marker round-trips as a plain dict via save/load.
    assert markers[0].pending_coord_reconcile == _marker()


def test_iter_markers_empty_when_no_runtime_dir(tmp_path: Path) -> None:
    assert list(iter_pending_coord_reconcile_markers(tmp_path)) == []


def test_pending_coord_reconcile_round_trips_and_old_files_rehydrate_to_none(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".kittify").mkdir(parents=True)
    # Old state file: no pending_coord_reconcile key at all.
    old = _make_state("01MIDOLD0000000000000000A0", marker=None)
    data = old.to_dict()
    del data["pending_coord_reconcile"]
    from specify_cli.merge.workspace import get_merge_runtime_dir

    runtime_dir = get_merge_runtime_dir(old.mission_id, repo)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "state.json").write_text(json.dumps(data), encoding="utf-8")

    loaded = load_state(repo, old.mission_id)
    assert loaded is not None
    assert loaded.pending_coord_reconcile is None
