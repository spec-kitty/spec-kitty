"""Focused unit coverage for the #2709/#2711 ephemeral merge-driver seeding seams.

The squash mission->target integration seeds the custom drivers into
``$GIT_COMMON_DIR/info/attributes`` for exactly one merge and tears the seeding
down afterwards (so a later ``auto_rebase`` in the same repo does not find the
git driver pre-activated — the #2709/#2711 regression). The end-to-end merge
tests exercise the happy path; this module pins the fast NON-git / absent-file
no-op branches those integration tests never reach, plus the empty-input guard of
the ``bookkeeping_projection`` event-log union helper.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.consolidation import (
    _ensure_info_attributes,
    _ephemeral_merge_driver_activation,
    _git_common_dir,
    _remove_info_attributes,
)
from specify_cli.consolidation.bookkeeping_projection import _union_event_logs

pytestmark = [pytest.mark.git_repo]


def _init_git(repo: Path) -> None:
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)


# ---------------------------------------------------------------------------
# lanes/merge.py driver-seeding no-op branches
# ---------------------------------------------------------------------------


def test_git_common_dir_none_outside_repo(tmp_path: Path) -> None:
    """A non-git directory yields ``None`` (git rev-parse returns non-zero)."""
    assert _git_common_dir(tmp_path) is None


def test_ensure_info_attributes_noop_outside_repo(tmp_path: Path) -> None:
    """No common dir -> nothing seeded (empty added-lines list)."""
    assert _ensure_info_attributes(tmp_path) == []


def test_remove_info_attributes_noop_outside_repo(tmp_path: Path) -> None:
    """No common dir -> teardown is a safe no-op even with added_lines given."""
    _remove_info_attributes(tmp_path, ["kitty-specs/**/meta.json merge=spec-kitty-meta"])
    # No exception, nothing written.
    assert not (tmp_path / ".git").exists()


def test_remove_info_attributes_noop_when_attributes_absent(tmp_path: Path) -> None:
    """A git repo whose ``info/attributes`` was never seeded -> teardown no-op."""
    _init_git(tmp_path)
    _remove_info_attributes(tmp_path, ["kitty-specs/**/meta.json merge=spec-kitty-meta"])
    common = _git_common_dir(tmp_path)
    assert common is not None
    assert not (common / "info" / "attributes").exists()


def test_ephemeral_activation_noop_outside_repo(tmp_path: Path) -> None:
    """Entering the activation context outside a git repo yields without seeding."""
    with _ephemeral_merge_driver_activation(tmp_path):
        pass
    assert not (tmp_path / ".gitattributes").exists()


# ---------------------------------------------------------------------------
# bookkeeping_projection._union_event_logs empty-input guard
# ---------------------------------------------------------------------------


def test_union_event_logs_returns_none_when_both_empty() -> None:
    """Both sides absent -> the union is ``None`` (no log to write)."""
    assert _union_event_logs(None, None) is None


def test_union_event_logs_unions_present_sides() -> None:
    """A present source and a present original union through the canonical reducer."""
    line = (
        '{"actor":"claude","at":"2026-02-08T12:00:00+00:00",'
        '"event_id":"01HXYZ00000000000000000001","evidence":null,'
        '"execution_mode":"worktree","feature_slug":"m-01ab","force":false,'
        '"from_lane":"in_review","reason":null,"review_ref":null,'
        '"to_lane":"approved","wp_id":"WP01"}\n'
    )
    merged = _union_event_logs(line.encode("utf-8"), b"")
    assert merged is not None
    assert b"01HXYZ00000000000000000001" in merged
