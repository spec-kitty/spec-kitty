"""DD-3 / INV-3 fail-loud guards for ``commit_router`` (coord-commit-surface-authority WP04).

The commit router formerly carried FOUR silent ``return repo_root, files`` /
``return repo_root, paths`` fallbacks that misrouted a coordination-kind artifact
onto the PRIMARY checkout whenever a coordination-routed mission reached the commit
seam in a corrupt state (unresolvable ``mission_id`` or a coordination-worktree
resolution failure). Per the authoritative-surface contract (rule 5 / INV-3 "no
silent misroute") and research D-004, ALL FOUR now fail loud by raising
:class:`~specify_cli.coordination.commit_router.CoordWorktreeResolutionError` — a
``RuntimeError`` subclass the command boundary maps to a non-zero JSON-mode exit
(``spec_commit_cmd.py``'s ``except (RuntimeError, ValueError, ...)`` → ``typer.Exit(1)``).

The two CORRECT primary-routing early-returns in ``_resolve_commit_worktree_for_kind``
(a primary-kind commit; a coord-less topology) are INTENTIONAL and are NOT hardened —
they are exercised here to prove they still route to primary without raising.

This file also:
- proves the T016 protected-primary refusal now derives from the shared rule
  (``resolve_surface_authority`` → ``Refuse`` → ``no_op_wrong_surface`` → exit 1),
- proves a HEALTHY coord mission still commits to its coordination surface, and
- re-locks the #2739 typed genuine-no-op (``unchanged``) exit-0 contract.

JSON-mode exit codes are asserted via the SAME status/exception → exit mapping the
CLI (``spec_commit_cmd.py``) uses, mirroring the WP01 golden harness's
``_cli_exit_code`` approach (``committed`` / ``unchanged`` → 0; ``no_op_wrong_surface``
/ ``error`` → 1; a ``RuntimeError`` from the router → the CLI's exit-1 arm).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from mission_runtime import CommitTarget, MissionArtifactKind, MissionTopology
from specify_cli.coordination import commit_router
from specify_cli.git.protection_policy import ProtectionPolicy

# NB: reference ``commit_router.CoordWorktreeResolutionError`` /
# ``commit_router.commit_for_mission`` through the MODULE, never a top-level
# ``from ... import`` binding: a sibling test (``test_commit_router.py::
# test_1718_no_materialisation_at_read_time``) ``importlib.reload``s this module,
# which rebinds its classes to fresh objects. A stale import binding would then make
# ``pytest.raises(commit_router.CoordWorktreeResolutionError)`` miss the reloaded class it actually
# raises. Module-attribute access always resolves the current object.

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_PRIMARY_BRANCH = "main"
_COORD_REF = "kitty/mission-my-slug-ABCD1234"
_MISSION_SLUG = "001-my-mission"
_VALID_MID8 = "ABCD1234"
# A coordination (non-PRIMARY-partition) kind: routes through coordination under a
# coord topology, so it reaches the coord-staging helpers under test.
_COORD_KIND = MissionArtifactKind.ACCEPTANCE_MATRIX


# ---------------------------------------------------------------------------
# CLI status/exception → exit mapping (mirrors spec_commit_cmd.py; see module docstring).
# ---------------------------------------------------------------------------


def _cli_exit_code(status: str) -> int:
    """The CLI's status→exit mapping (``committed`` / ``unchanged`` → 0; else 1)."""
    return 0 if status in ("committed", "unchanged") else 1


def _cli_exit_for_router_exception(exc: BaseException) -> int:
    """The CLI's exception→exit mapping.

    ``spec_commit_cmd.py`` catches ``(RuntimeError, ValueError,
    subprocess.CalledProcessError)`` raised from ``commit_for_mission`` and maps it
    to ``typer.Exit(1)`` with a JSON error payload. A ``CoordWorktreeResolutionError``
    is a ``RuntimeError`` subclass, so it lands in that exit-1 arm.
    """
    return 1 if isinstance(exc, (RuntimeError, ValueError, subprocess.CalledProcessError)) else 0


def _policy(*, protected: bool) -> ProtectionPolicy:
    branches = frozenset({_PRIMARY_BRANCH}) if protected else frozenset()
    return ProtectionPolicy(protected_branches=branches, operator_hatch_active=False)


def _coord_router_context():
    """Patch the router legs so a COORD-kind commit routes through coordination.

    ``resolve_placement_only`` returns the coord ref (``!= primary_target``) so
    ``use_coord`` is True and the router reaches ``_materialise_coord_worktree``.
    ``is_coord_residue_churn`` is pinned True so ``_group_files_by_partition`` keeps
    the (unrecognised-path) test artifact in the COORD bucket — otherwise the
    partition grouper would re-home it to PRIMARY and flip the effective kind.
    """
    return (
        patch.object(commit_router, "resolve_topology", return_value=MissionTopology.COORD),
        patch.object(commit_router, "resolve_placement_only", return_value=CommitTarget(ref=_COORD_REF)),
        patch.object(commit_router, "_resolve_mission_target_branch", return_value=_PRIMARY_BRANCH),
        patch.object(commit_router, "is_coord_residue_churn", return_value=True),
    )


class _FakeCommitResult:
    sha = "abc1234567890"


# ---------------------------------------------------------------------------
# Site 1 — _materialise_coord_worktree, unresolvable mid8 (was `:700-701`).
# ---------------------------------------------------------------------------


def test_site1_materialise_mid8_none_fails_loud_not_primary(tmp_path: Path) -> None:
    """Coord-routed mission + unresolvable mission_id → raise, never a silent primary commit."""
    artifact = tmp_path / "acceptance-matrix.json"
    artifact.write_text("{}\n", encoding="utf-8")
    topo, placement, target, residue = _coord_router_context()
    safe_commit_calls: list[object] = []

    with (
        topo,
        placement,
        target,
        residue,
        patch.object(commit_router, "_resolve_mid8", return_value=None),
        patch.object(
            commit_router,
            "safe_commit",
            side_effect=lambda **kw: safe_commit_calls.append(kw),
        ),
        pytest.raises(commit_router.CoordWorktreeResolutionError) as excinfo,
    ):
        commit_router.commit_for_mission(
            repo_root=tmp_path,
            mission_slug=_MISSION_SLUG,
            files=(artifact,),
            message="commit acceptance matrix",
            policy=_policy(protected=True),
            kind=_COORD_KIND,
        )

    assert _MISSION_SLUG in str(excinfo.value)
    # JSON-mode exit code: the CLI maps this RuntimeError to exit 1.
    assert _cli_exit_for_router_exception(excinfo.value) == 1
    # It must NOT have silently committed to the primary checkout.
    assert safe_commit_calls == []


# ---------------------------------------------------------------------------
# Site 2 — _materialise_coord_worktree, CoordinationWorkspace.resolve raises (was `:705-711`).
# ---------------------------------------------------------------------------


def test_site2_materialise_resolve_raises_fails_loud_not_primary(tmp_path: Path) -> None:
    """Coord-routed mission + coord-worktree resolution failure → raise, never primary."""
    artifact = tmp_path / "acceptance-matrix.json"
    artifact.write_text("{}\n", encoding="utf-8")
    topo, placement, target, residue = _coord_router_context()
    safe_commit_calls: list[object] = []

    with (
        topo,
        placement,
        target,
        residue,
        patch.object(commit_router, "_resolve_mid8", return_value=_VALID_MID8),
        patch(
            "specify_cli.coordination.workspace.CoordinationWorkspace.resolve",
            side_effect=RuntimeError("branch mismatch under divergent worktree"),
        ),
        patch.object(
            commit_router,
            "safe_commit",
            side_effect=lambda **kw: safe_commit_calls.append(kw),
        ),
        pytest.raises(commit_router.CoordWorktreeResolutionError) as excinfo,
    ):
        commit_router.commit_for_mission(
            repo_root=tmp_path,
            mission_slug=_MISSION_SLUG,
            files=(artifact,),
            message="commit acceptance matrix",
            policy=_policy(protected=True),
            kind=_COORD_KIND,
        )

    assert _MISSION_SLUG in str(excinfo.value)
    assert _cli_exit_for_router_exception(excinfo.value) == 1
    assert safe_commit_calls == []


# ---------------------------------------------------------------------------
# Site 3 — _resolve_commit_worktree_for_kind, unresolvable mid8 (was `:939-940`).
# The `paths`-family sites the bare `files` grep misses (Reviewer Guidance).
# ---------------------------------------------------------------------------


def test_site3_resolve_worktree_mid8_none_fails_loud(tmp_path: Path) -> None:
    """Coord-partition kind + unresolvable mission_id → raise, not a primary fallback."""
    artifact = tmp_path / "acceptance-matrix.json"
    artifact.write_text("{}\n", encoding="utf-8")

    with (
        patch.object(commit_router, "resolve_topology", return_value=MissionTopology.COORD),
        patch.object(commit_router, "_resolve_mid8", return_value=None),
        pytest.raises(commit_router.CoordWorktreeResolutionError) as excinfo,
    ):
        commit_router._resolve_commit_worktree_for_kind(
            tmp_path,
            _MISSION_SLUG,
            (artifact,),
            kind=_COORD_KIND,
        )

    assert _MISSION_SLUG in str(excinfo.value)
    assert _cli_exit_for_router_exception(excinfo.value) == 1


# ---------------------------------------------------------------------------
# Site 4 — _resolve_commit_worktree_for_kind, CoordinationWorkspace.resolve raises (was `:950-954`).
# ---------------------------------------------------------------------------


def test_site4_resolve_worktree_resolve_raises_fails_loud(tmp_path: Path) -> None:
    """Coord-partition kind + coord-worktree resolution failure → raise, not primary."""
    artifact = tmp_path / "acceptance-matrix.json"
    artifact.write_text("{}\n", encoding="utf-8")

    with (
        patch.object(commit_router, "resolve_topology", return_value=MissionTopology.COORD),
        patch.object(commit_router, "_resolve_mid8", return_value=_VALID_MID8),
        patch(
            "specify_cli.coordination.workspace.CoordinationWorkspace.resolve",
            side_effect=RuntimeError("resolve failed"),
        ),
        pytest.raises(commit_router.CoordWorktreeResolutionError) as excinfo,
    ):
        commit_router._resolve_commit_worktree_for_kind(
            tmp_path,
            _MISSION_SLUG,
            (artifact,),
            kind=_COORD_KIND,
        )

    assert _MISSION_SLUG in str(excinfo.value)
    assert _cli_exit_for_router_exception(excinfo.value) == 1


# ---------------------------------------------------------------------------
# Intentional exclusions (NOT hardened): the two correct primary-routing early-returns.
# ---------------------------------------------------------------------------


def test_intentional_exclusion_primary_kind_routes_to_primary_no_raise(tmp_path: Path) -> None:
    """A PRIMARY kind returns the primary checkout directly — never a misroute, never raises."""
    artifact = tmp_path / "spec.md"
    artifact.write_text("# Spec\n", encoding="utf-8")

    worktree_root, paths = commit_router._resolve_commit_worktree_for_kind(
        tmp_path,
        _MISSION_SLUG,
        (artifact,),
        kind=MissionArtifactKind.SPEC,
    )

    assert worktree_root == tmp_path
    assert paths == (artifact,)


def test_intentional_exclusion_coordless_topology_routes_to_primary_no_raise(
    tmp_path: Path,
) -> None:
    """A coord-less topology routes a coord-partition kind to primary — intentional, no raise."""
    artifact = tmp_path / "acceptance-matrix.json"
    artifact.write_text("{}\n", encoding="utf-8")

    with patch.object(commit_router, "resolve_topology", return_value=MissionTopology.SINGLE_BRANCH):
        worktree_root, paths = commit_router._resolve_commit_worktree_for_kind(
            tmp_path,
            _MISSION_SLUG,
            (artifact,),
            kind=_COORD_KIND,
        )

    assert worktree_root == tmp_path
    assert paths == (artifact,)


# ---------------------------------------------------------------------------
# Positive path — a HEALTHY coord mission still commits to its coordination surface.
# ---------------------------------------------------------------------------


def test_healthy_coord_mission_commits_to_coord_surface(tmp_path: Path) -> None:
    """No corruption: valid mid8 + resolvable worktree → real commit lands on the coord ref."""
    artifact = tmp_path / "acceptance-matrix.json"
    artifact.write_text("{}\n", encoding="utf-8")
    coord_worktree = tmp_path / ".worktrees" / "coord"
    staged = coord_worktree / "acceptance-matrix.json"
    staged.parent.mkdir(parents=True)
    staged.write_text("{}\n", encoding="utf-8")

    topo, placement, target, residue = _coord_router_context()

    with (
        topo,
        placement,
        target,
        residue,
        patch.object(commit_router, "_resolve_mid8", return_value=_VALID_MID8),
        patch(
            "specify_cli.coordination.workspace.CoordinationWorkspace.resolve",
            return_value=coord_worktree,
        ),
        patch.object(
            commit_router,
            "_stage_artifacts_in_coord_worktree",
            return_value=[staged],
        ),
        patch.object(commit_router, "safe_commit", return_value=_FakeCommitResult()),
        patch.object(commit_router, "_try_advance_ref"),
    ):
        result = commit_router.commit_for_mission(
            repo_root=tmp_path,
            mission_slug=_MISSION_SLUG,
            files=(artifact,),
            message="commit acceptance matrix",
            policy=_policy(protected=True),
            kind=_COORD_KIND,
        )

    assert result.status == "committed"
    assert result.placement_ref == _COORD_REF
    assert _cli_exit_code(result.status) == 0


# ---------------------------------------------------------------------------
# T016 — protected-primary refusal now DERIVES from the shared rule (Refuse → exit 1).
# ---------------------------------------------------------------------------


def test_t016_protected_primary_refusal_via_shared_rule_exit1(tmp_path: Path) -> None:
    """A primary kind on a protected primary → Refuse (shared rule) → no_op_wrong_surface, exit 1."""
    artifact = tmp_path / "spec.md"
    artifact.write_text("# Spec\n", encoding="utf-8")

    with (
        patch.object(commit_router, "resolve_topology", return_value=MissionTopology.SINGLE_BRANCH),
        patch.object(commit_router, "resolve_placement_only", return_value=CommitTarget(ref=_PRIMARY_BRANCH)),
        patch.object(commit_router, "_resolve_mission_target_branch", return_value=_PRIMARY_BRANCH),
    ):
        result = commit_router.commit_for_mission(
            repo_root=tmp_path,
            mission_slug=_MISSION_SLUG,
            files=(artifact,),
            message="Add spec",
            policy=_policy(protected=True),
            kind=MissionArtifactKind.SPEC,
        )

    assert result.status == commit_router._STATUS_NO_OP_WRONG_SURFACE
    assert _cli_exit_code(result.status) == 1
    # The refusal diagnostic is pinned (test_finalize_tasks_commit_surface.py depends on it).
    assert result.diagnostic is not None
    assert "Refusing to commit planning artifacts to the protected branch" in result.diagnostic


# ---------------------------------------------------------------------------
# #2739 regression guard — typed GENUINE no-op stays exit 0 (not collapsed to a refuse).
# ---------------------------------------------------------------------------


def test_2739_genuine_no_op_unchanged_stays_exit0(tmp_path: Path) -> None:
    """A genuine ``unchanged`` no-op (nothing to commit) still exits 0 with a typed reason."""
    artifact = tmp_path / "spec.md"
    artifact.write_text("# Spec\n", encoding="utf-8")

    exc = subprocess.CalledProcessError(1, ["git", "commit"])
    exc.stderr = "nothing to commit, working tree clean"

    with (
        patch.object(commit_router, "resolve_topology", return_value=MissionTopology.SINGLE_BRANCH),
        patch.object(commit_router, "resolve_placement_only", return_value=CommitTarget(ref=_PRIMARY_BRANCH)),
        patch.object(commit_router, "_resolve_mission_target_branch", return_value=_PRIMARY_BRANCH),
        patch.object(commit_router, "safe_commit", side_effect=exc),
    ):
        result = commit_router.commit_for_mission(
            repo_root=tmp_path,
            mission_slug=_MISSION_SLUG,
            files=(artifact,),
            message="Add spec",
            policy=_policy(protected=False),
            kind=MissionArtifactKind.SPEC,
        )

    assert result.status == "unchanged"
    assert result.reason == "no_op_no_changes"
    assert _cli_exit_code(result.status) == 0
