"""Self-materialization hardening for the S-C coord write gate (WP02, FR-006 / #4970).

The gate :func:`mission_runtime.assert_coord_write_materialized` used to treat ANY
``UNMATERIALIZED`` + local-head coordination branch as the sanctioned
``mission create`` → first-write self-materialization window, regardless of
whether that local head already carried committed matrix content. A stale local
head (worktree pruned, rows committed) was therefore misclassified as a virgin
first-write and allowed to self-materialize over — clobbering — committed
coordination state (the #4970 data-loss shape).

WP02 narrows the window to ``UNMATERIALIZED AND local-head AND NOT
committed-artifact-present``. These tests build the coord shape with REAL git
(no mocking) and exercise every REFUSE branch directly (NFR-001):

* (a) stale local head that carries a committed matrix ⇒ REFUSE.
* (b) genuine first-write (no committed matrix content) ⇒ ALLOW (no false-refusal, NFR-003).
* (c) a **path-drifted** committed matrix (under a non-default sub-path) is still
  detected ⇒ REFUSE (post-plan F2 — a hardcoded prefix would mis-read it as absent).
* (d) an unreadable git context (missing/foreign coord ref) ⇒ treated as present ⇒
  REFUSE (fail-closed), exercised directly on the committed-content probe.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import ActionContextError, CommitTarget, MissionArtifactKind
from mission_runtime.write_target_degrade import assert_coord_write_materialized
from specify_cli.coordination.surface_resolver import (
    coord_branch_has_committed_artifact,
)

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


class TestSelfMaterializationRefusal:
    def test_stale_local_head_with_committed_matrix_refuses(self, tmp_path: Path) -> None:
        """(a) UNMATERIALIZED local head that already carries committed rows ⇒ REFUSE."""
        repo = _build_unmaterialized_coord(tmp_path, matrix_rel=_DEFAULT_MATRIX_REL)
        with pytest.raises(ActionContextError) as exc:
            _assert(repo)
        assert exc.value.code == "COORD_WRITE_SURFACE_UNMATERIALIZED"

    def test_genuine_first_write_is_allowed(self, tmp_path: Path) -> None:
        """(b) UNMATERIALIZED local head with NO committed matrix ⇒ ALLOW (no raise)."""
        repo = _build_unmaterialized_coord(tmp_path, matrix_rel=None)
        # Must NOT raise — a genuine mission-create first-write self-materialization.
        _assert(repo)

    def test_path_drifted_committed_matrix_refuses(self, tmp_path: Path) -> None:
        """(c) A committed matrix under a NON-default sub-path is still detected ⇒ REFUSE."""
        repo = _build_unmaterialized_coord(tmp_path, matrix_rel="drift/issue-matrix.json")
        with pytest.raises(ActionContextError) as exc:
            _assert(repo)
        assert exc.value.code == "COORD_WRITE_SURFACE_UNMATERIALIZED"

    def test_legacy_md_committed_matrix_refuses(self, tmp_path: Path) -> None:
        """Both ``issue-matrix.json`` and ``issue-matrix.md`` map to ISSUE_MATRIX —
        a not-yet-migrated legacy ``.md`` on the coord branch is protected too."""
        repo = _build_unmaterialized_coord(tmp_path, matrix_rel="issue-matrix.md")
        with pytest.raises(ActionContextError) as exc:
            _assert(repo)
        assert exc.value.code == "COORD_WRITE_SURFACE_UNMATERIALIZED"


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
