"""S-C fail-closed WRITE gate (WP03 / FR-006; traces #4970 #4969).

The READ side (``surface_resolver.resolve_status_surface_with_anchor``) is
correct as-is: a coord-empty / unmaterialized surface degrades LOUDLY to the
primary checkout (Option B, D1). The WRITE side had no such gate, so a
terminus WRITE that resolves to the coordination branch while the coordination
worktree is absent-and-not-a-local-head (the fresh-clone / CI shape where the
lane exists only on ``origin/<lane>``) would degrade to the primary directory
and overwrite committed coordination state — the mechanism behind #4970
(``issue-verdict`` overwrites teammates' verdicts).

These tests exercise the REAL write chain and the REAL resolver seam with real
git fixtures (no mocked-away seams):

* a coord-surface WRITE with an unresolved/unmaterialized coord surface
  REFUSES (structured ``"refused"`` result), and — because the refusal happens
  BEFORE staging — leaves ZERO residue in the primary directory;
* the same fixture READ still degrades permissively (the loud-primary-fallback
  read posture is unchanged — reads are fine, D1);
* the sanctioned ``mission create`` → first-write bootstrap (coord branch is a
  LOCAL head, worktree not yet materialized) is NOT refused;
* a materialized coordination surface write still succeeds.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import pytest

from mission_runtime import ActionContextError, CommitTarget, MissionArtifactKind
from specify_cli.coordination.surface_resolver import (
    resolve_for_write,
    resolve_status_surface_with_anchor,
)
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.coordination.write_seam import write_artifact

pytestmark = pytest.mark.git_repo

# Production-shaped identity (Mission Identity Model 083+): a real 26-char ULID.
MISSION_ID = "01KTDVHZKGCHCW6HQ4V577PNES"
MID8 = MISSION_ID[:8]
BARE_SLUG = "surface-write-gate-mission"
SLUG_WITH_MID8 = f"{BARE_SLUG}-{MID8}"
COORD_BRANCH = f"kitty/mission-{SLUG_WITH_MID8}"

_ISSUE_MATRIX = MissionArtifactKind.ISSUE_MATRIX
_UNMATERIALIZED_CODE = "COORD_WRITE_SURFACE_UNMATERIALIZED"
_LOGGER_NAME = "specify_cli.coordination.surface_resolver"


class _Policy:
    """Duck-typed ``is_protected(ref) -> bool`` policy (never protected)."""

    def is_protected(self, _ref: str) -> bool:
        return False


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(repo_root: Path) -> None:
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "gate@example.test")
    _git(repo_root, "config", "user.name", "Surface Write Gate")
    _git(repo_root, "commit", "--allow-empty", "-qm", "init")
    _git(repo_root, "branch", "-M", "main")


def _write_meta(feature_dir: Path, **fields: object) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(fields), encoding="utf-8")


def _primary_dir(repo_root: Path, slug: str) -> Path:
    return repo_root / "kitty-specs" / slug


def _base_coord_mission(repo_root: Path, slug: str = BARE_SLUG) -> Path:
    """Init a repo + a coord-topology primary ``meta.json`` (no coord branch yet).

    Returns the primary mission dir. The caller decides the coordination-branch
    shape (local head / remote-only / materialized worktree) to model the state
    under test.
    """
    _init_repo(repo_root)
    primary_dir = _primary_dir(repo_root, slug)
    _write_meta(
        primary_dir,
        mission_id=MISSION_ID,
        mid8=MID8,
        coordination_branch=COORD_BRANCH,
        topology="coord",
        target_branch="main",
    )
    return primary_dir


def _current_sha(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _make_remote_only_coord_branch(repo_root: Path) -> None:
    """Create ``refs/remotes/origin/<coord>`` with NO local head, worktree absent.

    The #4970 fresh-clone / CI shape: the coordination branch exists only as a
    remote-tracking ref, so it cannot be checked out into a coordination worktree
    without forking from the primary branch.
    """
    _git(repo_root, "update-ref", f"refs/remotes/origin/{COORD_BRANCH}", _current_sha(repo_root))


def _make_local_coord_branch(repo_root: Path) -> None:
    """Create the coordination branch as a LOCAL head, worktree NOT materialized.

    The sanctioned ``mission create`` → first-coord-write bootstrap window on the
    creating host: the local branch exists and can be checked out into a
    coordination worktree on demand.
    """
    _git(repo_root, "branch", COORD_BRANCH)


def _materialize_coord_worktree(repo_root: Path, slug: str = BARE_SLUG) -> Path:
    """Create a real, MATERIALIZED coordination worktree with the mission dir.

    Returns the coordination worktree root.
    """
    _make_local_coord_branch(repo_root)
    coord_root = CoordinationWorkspace.worktree_path(repo_root, slug, MID8)
    _git(repo_root, "worktree", "add", str(coord_root), COORD_BRANCH)
    coord_mission_dir = coord_root / "kitty-specs" / SLUG_WITH_MID8
    coord_mission_dir.mkdir(parents=True, exist_ok=True)
    (coord_mission_dir / ".keep").write_text("", encoding="utf-8")
    _git(coord_root, "add", "-A")
    _git(coord_root, "commit", "-qm", "materialize coord mission dir")
    return coord_root


# ---------------------------------------------------------------------------
# WRITE gate: fail-closed on an unresolved / unmaterialized coord surface (#4970)
# ---------------------------------------------------------------------------


def test_write_seam_refuses_unmaterialized_coord_surface_and_leaves_no_residue(
    tmp_path: Path,
) -> None:
    """The real write chain REFUSES a coord write onto a remote-only coord surface.

    RED on base: the write degraded to the primary dir (or raised a
    materialization error), overwriting the coordination branch. GREEN on the
    fix: a structured ``"refused"`` result, and — because the refusal precedes
    staging — the staged artifact was never even written to disk (zero residue).
    """
    primary_dir = _base_coord_mission(tmp_path)
    _make_remote_only_coord_branch(tmp_path)

    staged_path = primary_dir / "issue-matrix.json"

    def _stage() -> tuple[Path, ...]:
        staged_path.write_text('{"schema_version": 1, "rows": {}}\n', encoding="utf-8")
        return (staged_path,)

    result = write_artifact(
        repo_root=tmp_path,
        mission_slug=BARE_SLUG,
        kind=_ISSUE_MATRIX,
        stage=_stage,
        message="chore: issue-matrix",
        policy=_Policy(),
        entry_id="#4970",
    )

    assert result.status == "refused", f"a coord-surface WRITE with an unmaterialized coord surface must fail closed, not degrade to primary. Got: {result!r}"
    assert result.destination_surface is None
    assert result.diagnostic is not None and "#4970" in result.diagnostic
    # FR-005 probe/gate-before-stage: the refused write never materialized the
    # artifact, so the primary directory carries no residue.
    assert not staged_path.exists(), (
        f"a refused coord write must leave ZERO residue in the primary directory (the stage thunk must never run). Found: {staged_path}"
    )


def test_resolve_for_write_refuses_remote_only_coord(tmp_path: Path) -> None:
    """``resolve_for_write`` raises the structured unmaterialized-surface refusal."""
    _base_coord_mission(tmp_path)
    _make_remote_only_coord_branch(tmp_path)

    with pytest.raises(ActionContextError) as exc_info:
        resolve_for_write(tmp_path, BARE_SLUG, _ISSUE_MATRIX)

    assert exc_info.value.code == _UNMATERIALIZED_CODE
    assert COORD_BRANCH in str(exc_info.value)


# ---------------------------------------------------------------------------
# WRITE gate: allow the sanctioned states (no over-refusal / bootstrap intact)
# ---------------------------------------------------------------------------


def test_resolve_for_write_allows_local_branch_bootstrap(tmp_path: Path) -> None:
    """A LOCAL coord branch (worktree not yet materialized) is NOT refused.

    The ``mission create`` → first-coord-write bootstrap on the creating host
    self-materializes the worktree from the local branch; refusing it would break
    the legitimate first write.
    """
    _base_coord_mission(tmp_path)
    _make_local_coord_branch(tmp_path)

    resolved = resolve_for_write(tmp_path, BARE_SLUG, _ISSUE_MATRIX)

    assert isinstance(resolved, CommitTarget)
    assert resolved.ref == COORD_BRANCH


def test_resolve_for_write_allows_materialized_coord(tmp_path: Path) -> None:
    """A materialized coordination worktree resolves cleanly (no refusal)."""
    _base_coord_mission(tmp_path)
    _materialize_coord_worktree(tmp_path)

    resolved = resolve_for_write(tmp_path, BARE_SLUG, _ISSUE_MATRIX)

    assert isinstance(resolved, CommitTarget)
    assert resolved.ref == COORD_BRANCH


def test_materialized_coord_write_succeeds(tmp_path: Path) -> None:
    """A normal write onto a materialized coordination surface still succeeds."""
    primary_dir = _base_coord_mission(tmp_path)
    _materialize_coord_worktree(tmp_path)

    staged_path = primary_dir / "issue-matrix.json"

    def _stage() -> tuple[Path, ...]:
        staged_path.write_text('{"schema_version": 1, "rows": {}}\n', encoding="utf-8")
        return (staged_path,)

    result = write_artifact(
        repo_root=tmp_path,
        mission_slug=BARE_SLUG,
        kind=_ISSUE_MATRIX,
        stage=_stage,
        message="chore: issue-matrix",
        policy=_Policy(),
        entry_id="#4970",
        primary_paths_created_this_invocation=frozenset({staged_path}),
    )

    assert result.status in ("committed", "unchanged"), (
        f"a normal materialized coordination write must still succeed, not be refused by the fail-closed gate. Got: {result!r}"
    )


# ---------------------------------------------------------------------------
# READ path unchanged: the loud-primary-fallback is correct for reads (D1)
# ---------------------------------------------------------------------------


def test_read_path_still_degrades_on_unmaterialized_coord(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """The READ resolver stays permissive on the SAME fixture the WRITE refuses.

    D1: only writes get the fail-closed posture; the loud-primary-fallback read
    is correct and must not regress. On the remote-only / unmaterialized coord
    fixture the read resolver returns a surface without raising.
    """
    _base_coord_mission(tmp_path)
    _make_remote_only_coord_branch(tmp_path)

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        resolved = resolve_status_surface_with_anchor(tmp_path, BARE_SLUG)

    # The read never fails closed on this fixture (contrast the WRITE, which does).
    assert resolved.surface_path.name == "status.events.jsonl"
