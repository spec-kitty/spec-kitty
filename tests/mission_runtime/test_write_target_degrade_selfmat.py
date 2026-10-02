"""Self-materialization hardening for the S-C coord write gate (WP02, FR-006 / #4970).

**Re-pinned deliberately (coord-artifact-single-home-01M3V4BE WP03, research D22).**
The gate :func:`mission_runtime.assert_coord_write_materialized` used to REFUSE an
``UNMATERIALIZED`` local-head coordination branch that already carried committed
matrix content (classifying it as a "stale local head" that self-materializing
would clobber). D22 found that reasoning over-matches: once seeding ships, EVERY
post-fix coordination branch carries committed content by the time it is a local
head again, so that refusal would fire for the Mission's *normal* post-fix shape,
not only a genuinely stale one. ``assert_coord_write_materialized`` is now a thin
delegate to the single write authority
(:func:`specify_cli.coordination.coord_seed.establish_coord_write_location`),
which materializes/seeds/restores instead of refusing a local head on content
alone — the former REFUSE cases below (a)/(c)/(d-via-the-gate) are re-pinned to
ALLOW (self-materialize, no raise). The remote-only refusal is UNCHANGED (ruling
Q1, #4970 parity) and lives in the sibling round-trip file
(``tests/specify_cli/cli/commands/test_coordination_remedy_5113.py``).

``TestCommittedContentProbeFailClosed`` is UNCHANGED: it exercises
:func:`coord_branch_has_committed_artifact` directly (not through the gate), and
that probe's own fail-closed behaviour is untouched by D22 -- only the GATE
stopped consulting it for the local-head arm.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import CommitTarget, MissionArtifactKind
from mission_runtime.write_target_degrade import assert_coord_write_materialized
from specify_cli.coordination.surface_resolver import (
    coord_branch_has_committed_artifact,
)
from specify_cli.coordination.workspace import CoordinationWorkspace

# Pure-git, tmp_path-only — same fast/unit tier as the sibling
# ``tests/mission_runtime/test_write_target_degrade.py``.
pytestmark = [pytest.mark.fast]

_SLUG = "terminus-01M4970A"
_MID8 = "01M4970A"
_MISSION_ID = (_MID8 + "0" * 26)[:26]
_COORD_BRANCH = f"kitty/mission-{_SLUG}"
_WORK_BRANCH = "mission-work"
_DEFAULT_MATRIX_REL = "issue-matrix.json"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _build_unmaterialized_coord(
    tmp_path: Path,
    *,
    matrix_rel: str | None,
) -> Path:
    """Return a repo whose coord branch is a LOCAL HEAD with NO coord worktree.

    ``matrix_rel`` (relative to ``kitty-specs/<slug>/``) — when given — is the
    path at which a committed ``issue-matrix.json`` lives ON THE COORD BRANCH; when
    ``None`` the coord branch carries no matrix at all (the genuine first-write
    shape). The primary ``meta.json`` declares the ``coordination_branch`` so the
    gate routes through the coord arm; the coord worktree is deliberately NOT
    materialized (``probe_coord_state`` ⇒ ``UNMATERIALIZED``).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-qb", _WORK_BRANCH)
    _git(repo, "config", "user.email", "t@t.co")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")

    feature_dir = repo / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": _SLUG,
                "mission_id": _MISSION_ID,
                "mid8": _MID8,
                "coordination_branch": _COORD_BRANCH,
                "topology": "coord",
            }
        ),
        encoding="utf-8",
    )
    if matrix_rel is not None:
        matrix_path = feature_dir / matrix_rel
        matrix_path.parent.mkdir(parents=True, exist_ok=True)
        matrix_path.write_text(json.dumps({"rows": {"#1111": {"verdict": "fixed"}}}), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "seed mission")

    # The coord branch is a LOCAL HEAD carrying whatever was committed above; the
    # working checkout stays on ``_WORK_BRANCH`` and the coord worktree is never
    # materialized.
    _git(repo, "branch", _COORD_BRANCH)
    return repo


def _assert(repo: Path) -> None:
    assert_coord_write_materialized(
        repo,
        _SLUG,
        MissionArtifactKind.ISSUE_MATRIX,
        CommitTarget(ref=_COORD_BRANCH),
    )


class TestSelfMaterializationNowAllowed:
    """D22 re-pin: a local-head UNMATERIALIZED branch is now self-materialized
    regardless of whether it already carries committed content -- the single
    write authority (``establish_coord_write_location``) decides, and a
    post-fix Mission with committed COORD content at its tip is the NORMAL
    shape, not a stale/forked one. All four cases below previously diverged
    ((a)/(c)/(d) REFUSEd, (b) ALLOWed); they now all ALLOW uniformly.
    """

    def _assert_matrix_survives(self, repo: Path, matrix_rel: str) -> None:
        """L5 (review cycle 2): the #4970 no-clobber control -- self-materializing
        over committed content must never discard it."""
        worktree = CoordinationWorkspace.worktree_path(repo, _SLUG, _MID8)
        matrix_path = worktree / "kitty-specs" / _SLUG / matrix_rel
        assert matrix_path.exists(), f"committed matrix {matrix_rel!r} did not survive materialization"
        assert json.loads(matrix_path.read_text(encoding="utf-8")) == {"rows": {"#1111": {"verdict": "fixed"}}}

    def test_stale_local_head_with_committed_matrix_now_allowed(self, tmp_path: Path) -> None:
        """(a) UNMATERIALIZED local head that already carries committed rows ⇒ ALLOW (re-pinned)."""
        repo = _build_unmaterialized_coord(tmp_path, matrix_rel=_DEFAULT_MATRIX_REL)
        _assert(repo)  # must NOT raise
        self._assert_matrix_survives(repo, _DEFAULT_MATRIX_REL)

    def test_genuine_first_write_is_allowed(self, tmp_path: Path) -> None:
        """(b) UNMATERIALIZED local head with NO committed matrix ⇒ ALLOW (unchanged)."""
        repo = _build_unmaterialized_coord(tmp_path, matrix_rel=None)
        # Must NOT raise — a genuine mission-create first-write self-materialization.
        _assert(repo)

    def test_path_drifted_committed_matrix_now_allowed(self, tmp_path: Path) -> None:
        """(c) A committed matrix under a NON-default sub-path ⇒ ALLOW (re-pinned)."""
        repo = _build_unmaterialized_coord(tmp_path, matrix_rel="drift/issue-matrix.json")
        _assert(repo)  # must NOT raise
        self._assert_matrix_survives(repo, "drift/issue-matrix.json")

    def test_legacy_md_committed_matrix_now_allowed(self, tmp_path: Path) -> None:
        """Both ``issue-matrix.json`` and ``issue-matrix.md`` map to ISSUE_MATRIX —
        a not-yet-migrated legacy ``.md`` on the coord branch ⇒ ALLOW (re-pinned)."""
        repo = _build_unmaterialized_coord(tmp_path, matrix_rel="issue-matrix.md")
        _assert(repo)  # must NOT raise
        self._assert_matrix_survives(repo, "issue-matrix.md")


class TestCommittedContentProbeFailClosed:
    """(d) The committed-content probe fails CLOSED — an unreadable git context
    (missing/foreign ref) is treated as content-present so the gate refuses,
    mirroring ``_coord_branch_is_local_head``'s fail-closed posture."""

    def test_missing_branch_ref_reads_as_present(self, tmp_path: Path) -> None:
        repo = _build_unmaterialized_coord(tmp_path, matrix_rel=None)
        # A ref that does not resolve ⇒ ls-tree errors ⇒ fail-closed present.
        assert (
            coord_branch_has_committed_artifact(
                repo,
                "kitty/mission-does-not-exist",
                _SLUG,
                MissionArtifactKind.ISSUE_MATRIX,
            )
            is True
        )

    def test_clean_absent_subtree_reads_as_absent(self, tmp_path: Path) -> None:
        """A readable coord branch whose subtree holds no matrix ⇒ absent (False)."""
        repo = _build_unmaterialized_coord(tmp_path, matrix_rel=None)
        assert (
            coord_branch_has_committed_artifact(
                repo,
                _COORD_BRANCH,
                _SLUG,
                MissionArtifactKind.ISSUE_MATRIX,
            )
            is False
        )

    def test_committed_matrix_reads_as_present(self, tmp_path: Path) -> None:
        repo = _build_unmaterialized_coord(tmp_path, matrix_rel=_DEFAULT_MATRIX_REL)
        assert (
            coord_branch_has_committed_artifact(
                repo,
                _COORD_BRANCH,
                _SLUG,
                MissionArtifactKind.ISSUE_MATRIX,
            )
            is True
        )
