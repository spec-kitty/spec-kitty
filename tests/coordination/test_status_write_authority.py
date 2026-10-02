"""WP04 (FR-004) — single status write-authority.

Pins the topology-conditional non-transactional fallback (contract rows 7-8):

* **Coord topology** — a status write in the ``_transaction_topology_available``
  False arm materializes/targets the coord worktree via
  ``CoordinationWorkspace.resolve`` and COMMITS the event there (never a
  primary-only-uncommitted write that leaves the coord log stale).
* **Coord-less topology** (``SINGLE_BRANCH``/``LANES``/flat, or a coord mission
  whose worktree cannot be materialized) — the primary-uncommitted write path is
  PRESERVED; no coord path is forced and no error is raised.

Plus the T015 campsite: the auto-rebase lane-sync ``_git_stdout`` helper must
tolerate a not-yet-materialized lane worktree (its documented "Returns None when
... no lane worktree exists" contract) instead of crashing with a raw
``FileNotFoundError``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination import status_transition as st
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.mission_metadata import load_meta
from specify_cli.status.models import Lane, TransitionRequest
from tests.characterization.test_trio_json_envelope import _build_mission_repo

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git_show(repo_root: Path, ref: str, rel_path: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"{ref}:{rel_path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else ""


def _claim_request(
    feature_dir: Path, repo_root: Path, mission_slug: str
) -> TransitionRequest:
    return TransitionRequest(
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        wp_id="WP01",
        to_lane=Lane.CLAIMED,
        actor="claude",
        reason="write-authority test claim",
        execution_mode="worktree",
        repo_root=repo_root,
    )


# ---------------------------------------------------------------------------
# (a) Coord topology → the fallback commits the event to the coord worktree.
# ---------------------------------------------------------------------------


@pytest.mark.git_repo
def test_fallback_commits_status_to_coord_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-004 row 7: a coord-topology fallback write lands on the coord branch."""
    repo_root, mission_slug = _build_mission_repo(
        tmp_path,
        monkeypatch,
        coord=True,
        mission_slug="write-authority-coord",
        wp_lane="planned",
        materialize_coord=True,
    )
    feature_dir = repo_root / "kitty-specs" / mission_slug
    # Reads meta.json directly for test-setup assertions (not exercising
    # status_transition's internal routing) — use the canonical reader rather
    # than reaching through the module under test, which no longer imports
    # load_meta at module scope after FR-007 routing to load_meta_fail_closed.
    coord_branch = load_meta(feature_dir)["coordination_branch"]

    request = _claim_request(feature_dir, repo_root, mission_slug)
    identity = st._identity_for_request(request)
    # Precondition: this IS a coord topology the fallback recognizes.
    assert identity.coordination_branch is not None

    event = st._fallback_emit_single(
        identity,
        request,
        mission_slug,
    )

    assert str(event.to_lane) == str(Lane.CLAIMED)
    # The event is COMMITTED to the coord branch (not merely written to a
    # primary-uncommitted working copy).
    committed_log = _git_show(
        repo_root, coord_branch, f"kitty-specs/{mission_slug}/status.events.jsonl"
    )
    assert "claimed" in committed_log, committed_log
    assert event.event_id in committed_log, committed_log


# ---------------------------------------------------------------------------
# (b) Two-sided coord-less coverage: the primary write path is PRESERVED.
# ---------------------------------------------------------------------------


@pytest.mark.git_repo
def test_fallback_preserves_primary_for_flat_topology(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-004 row 8: a coord-LESS (flat) mission keeps the primary write path."""
    repo_root, mission_slug = _build_mission_repo(
        tmp_path,
        monkeypatch,
        coord=False,
        mission_slug="write-authority-flat",
        wp_lane="planned",
    )
    feature_dir = repo_root / "kitty-specs" / mission_slug

    request = _claim_request(feature_dir, repo_root, mission_slug)
    identity = st._identity_for_request(request)
    # A flat mission declares no coordination branch → coord-less.
    assert identity.coordination_branch is None
    assert st._resolve_fallback_coord_worktree(identity, mission_slug) is None

    event = st._fallback_emit_single(
        identity,
        request,
        mission_slug,
    )

    # The primary event log records the transition (primary write path), and no
    # coord worktree was forced into existence.
    assert str(event.to_lane) == str(Lane.CLAIMED)
    primary_log = (feature_dir / "status.events.jsonl").read_text(encoding="utf-8")
    assert event.event_id in primary_log
    assert not (repo_root / ".worktrees").exists()


@pytest.mark.git_repo
def test_fallback_fails_loud_for_stored_coord_when_worktree_unresolvable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """US1 Edge Case (was silent-primary): a stored-COORD mission whose coord
    worktree genuinely cannot be materialized must FAIL LOUD, NOT degrade to a
    primary-uncommitted write that would strand the coord event log.

    This replaces the prior ``test_fallback_does_not_force_coord_when_worktree_
    unresolvable`` which pinned the old silent-primary degradation. The operator's
    binding directive: coord-routing resolves to COORD/lanes-with-coord whenever a
    coord branch exists; only a genuinely coord-less topology may take the primary
    path. The coord-less primary path is still covered by
    ``test_fallback_preserves_primary_for_flat_topology`` above.

    WP07 re-pin (coord-artifact-single-home-01M3V4BE): the coordination arm
    now resolves through the single write-location accessor
    (``placement_seam(...).write_dir``), whose MATERIALIZED fast path never
    calls ``CoordinationWorkspace.resolve`` at all when the coord Mission dir
    already has tracked content (the ``materialize_coord=True`` shape this
    test previously built: a worktree eagerly resolved from a branch whose
    tip already carries the committed Mission dir). The monkeypatched
    ``resolve`` failure below is only reachable while the coord state is
    genuinely UNMATERIALIZED, so this fixture no longer pre-materializes.
    """
    repo_root, mission_slug = _build_mission_repo(
        tmp_path,
        monkeypatch,
        coord=True,
        mission_slug="write-authority-unresolvable",
        wp_lane="planned",
    )
    feature_dir = repo_root / "kitty-specs" / mission_slug

    request = _claim_request(feature_dir, repo_root, mission_slug)
    identity = st._identity_for_request(request)
    assert identity.coordination_branch is not None

    # Force the coord worktree resolution to fail with a production-shaped git
    # failure (``git worktree add`` exit 128 — the "repo root is not a work tree"
    # class this fallback is reached under).
    def _boom(*_a: object, **_k: object) -> Path:
        raise subprocess.CalledProcessError(
            128, ["git", "worktree", "add"], stderr="fatal: not a working tree"
        )

    monkeypatch.setattr(CoordinationWorkspace, "resolve", staticmethod(_boom))

    # The decision helper FAILS LOUD (stored-COORD shape, unmaterializable worktree).
    with pytest.raises(st.FallbackCoordWorktreeUnresolved):
        st._resolve_fallback_coord_worktree(identity, mission_slug)

    # The higher-level emit fails loud too — and leaks NO event to the primary log.
    with pytest.raises(st.FallbackCoordWorktreeUnresolved):
        st._fallback_emit_single(
            identity,
            request,
            mission_slug,
        )
    primary_events = feature_dir / "status.events.jsonl"
    if primary_events.exists():
        assert "claimed" not in primary_events.read_text(encoding="utf-8")


@pytest.mark.git_repo
def test_fallback_routes_coord_from_stored_topology_not_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SC-001 (remediation #1): the coord-vs-primary SHAPE is decided by the
    STORED-topology SSOT, NOT a ``coordination_branch is not None`` surface test.

    A mission that carries a ``coordination_branch`` on its surface but whose
    stored ``topology`` is coord-less (``single_branch``) must resolve to the
    PRIMARY path — proving the fallback consults the SSOT, not the surface. Were
    the old surface test still in force, the present ``coordination_branch`` would
    (wrongly) force a coord route.
    """
    repo_root, mission_slug = _build_mission_repo(
        tmp_path,
        monkeypatch,
        coord=True,
        mission_slug="write-authority-ssot",
        wp_lane="planned",
    )
    feature_dir = repo_root / "kitty-specs" / mission_slug

    request = _claim_request(feature_dir, repo_root, mission_slug)
    identity = st._identity_for_request(request)
    # Surface: a coord branch IS declared.
    assert identity.coordination_branch is not None

    # SSOT: stamp the stored topology coord-LESS on the meta the resolver reads.
    meta_path = identity.feature_dir / "meta.json"
    assert meta_path.exists(), meta_path
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["topology"] = "single_branch"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    # Stored-topology SSOT wins over the surface coordination_branch → primary.
    assert st._resolve_fallback_coord_worktree(identity, mission_slug) is None


@pytest.mark.git_repo
def test_fallback_routes_coord_for_stored_lanes_with_coord(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stored ``lanes_with_coord`` topology routes through coordination — the
    coord worktree is targeted, not primary (``routes_through_coordination`` maps
    both ``COORD`` and ``LANES_WITH_COORD`` to the coordination surface).
    """
    repo_root, mission_slug = _build_mission_repo(
        tmp_path,
        monkeypatch,
        coord=True,
        mission_slug="write-authority-lanes-coord",
        wp_lane="planned",
        materialize_coord=True,
    )
    feature_dir = repo_root / "kitty-specs" / mission_slug

    request = _claim_request(feature_dir, repo_root, mission_slug)
    identity = st._identity_for_request(request)

    # Stamp the stored topology lanes_with_coord on the resolved-primary meta.
    meta_path = identity.feature_dir / "meta.json"
    assert meta_path.exists(), meta_path
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["topology"] = "lanes_with_coord"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    resolved = st._resolve_fallback_coord_worktree(identity, mission_slug)
    # ``mid8`` is a non-deterministic ULID slice — read it from the resolved
    # identity, never recompute via ``derive_mission_id``.
    expected = CoordinationWorkspace.worktree_path(repo_root, mission_slug, identity.mid8)
    assert resolved == expected


@pytest.mark.git_repo
def test_coord_fallback_commit_failure_rolls_back_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Remediation #4: the coord fallback arm is rollback-symmetric — if the coord
    commit fails, the just-emitted event is truncated back rather than left
    stranded uncommitted on the coord worktree.
    """
    repo_root, mission_slug = _build_mission_repo(
        tmp_path,
        monkeypatch,
        coord=True,
        mission_slug="write-authority-rollback",
        wp_lane="planned",
        materialize_coord=True,
    )
    feature_dir = repo_root / "kitty-specs" / mission_slug

    request = _claim_request(feature_dir, repo_root, mission_slug)
    identity = st._identity_for_request(request)
    assert identity.coordination_branch is not None

    # ``mid8`` is a non-deterministic ULID slice — read it from the resolved
    # identity, never recompute via ``derive_mission_id``.
    mission_dirname = st._transaction_dir_name(mission_slug, identity.mid8)
    coord_worktree = CoordinationWorkspace.worktree_path(repo_root, mission_slug, identity.mid8)
    coord_events = (
        coord_worktree / "kitty-specs" / mission_dirname / "status.events.jsonl"
    )
    before = coord_events.read_bytes() if coord_events.exists() else b""

    def _commit_boom(**_k: object) -> None:
        raise RuntimeError("simulated: coord commit refused")

    monkeypatch.setattr(st, "_commit_status_artifacts_to_coord", _commit_boom)

    with pytest.raises(RuntimeError, match="coord commit refused"):
        st._fallback_emit_single(
            identity,
            request,
            mission_slug,
        )

    # The event log was truncated back to its pre-emit content (rollback).
    after = coord_events.read_bytes() if coord_events.exists() else b""
    assert after == before


# ---------------------------------------------------------------------------
# T015 campsite: auto-rebase lane-sync must not crash on an absent lane worktree.
# ---------------------------------------------------------------------------


def test_git_stdout_tolerates_missing_worktree_cwd(tmp_path: Path) -> None:
    """A non-existent ``cwd`` yields ``None`` (documented contract), not a raw
    ``FileNotFoundError`` — the crash that surfaced once #2861's empty second
    commit no longer short-circuited the auto-rebase sync.
    """
    from specify_cli.lanes import lifecycle_sync

    missing = tmp_path / "does-not-exist-lane-worktree"
    assert not missing.exists()
    assert lifecycle_sync._git_stdout(missing, "rev-parse", "--abbrev-ref", "HEAD") is None
