"""Seam unit tests for the upgrade commit-decision helpers (C2/C7, D-10).

Covers ``should_auto_commit`` (main scope), ``should_auto_commit_for_worktree``
(worktree scope, D-10), and the FR-013 fail-safe branch-detection regression
(C7) — kept alongside the decision matrix per the seam-contract's test note.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.upgrade import autocommit

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# should_auto_commit (main scope, C2)
# ---------------------------------------------------------------------------


def test_should_auto_commit_false_when_config_disabled(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(autocommit, "get_auto_commit_default", lambda _repo_root: False)
    assert autocommit.should_auto_commit(tmp_path, dry_run=False) is False


def test_should_auto_commit_true_when_config_enabled(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(autocommit, "get_auto_commit_default", lambda _repo_root: True)
    assert autocommit.should_auto_commit(tmp_path, dry_run=False) is True


def test_should_auto_commit_false_on_dry_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(autocommit, "get_auto_commit_default", lambda _repo_root: True)
    assert autocommit.should_auto_commit(tmp_path, dry_run=True) is False


def test_should_auto_commit_has_no_manual_review_gate(tmp_path: Path, monkeypatch) -> None:
    """#5443: files held for manual review are not commit candidates, so they no longer
    disable committing; the parameter is gone (a caller passing it fails loudly)."""
    monkeypatch.setattr(autocommit, "get_auto_commit_default", lambda _repo_root: True)
    assert autocommit.should_auto_commit(tmp_path, dry_run=False) is True
    with pytest.raises(TypeError):
        autocommit.should_auto_commit(tmp_path, dry_run=False, **{"manual_review": True})


def test_should_auto_commit_never_reads_home_guard(tmp_path: Path, monkeypatch) -> None:
    """C-001/D-7: the decision must not duplicate the ``$HOME`` eligibility
    guard — verified by never touching ``Path.home`` at all."""
    monkeypatch.setattr(autocommit, "get_auto_commit_default", lambda _repo_root: True)

    def _boom() -> Path:
        raise AssertionError("should_auto_commit must not consult Path.home()")

    monkeypatch.setattr(Path, "home", staticmethod(_boom))
    assert autocommit.should_auto_commit(tmp_path, dry_run=False) is True


# ---------------------------------------------------------------------------
# should_auto_commit_for_worktree (worktree scope, D-10)
# ---------------------------------------------------------------------------


def test_worktree_scope_false_when_config_disabled(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(autocommit, "get_auto_commit_default", lambda _repo_root: False)
    assert autocommit.should_auto_commit_for_worktree(tmp_path, dry_run=False) is False


def test_worktree_scope_true_when_config_enabled(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(autocommit, "get_auto_commit_default", lambda _repo_root: True)
    assert autocommit.should_auto_commit_for_worktree(tmp_path, dry_run=False) is True


def test_worktree_scope_false_on_dry_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(autocommit, "get_auto_commit_default", lambda _repo_root: True)
    assert autocommit.should_auto_commit_for_worktree(tmp_path, dry_run=True) is False


def test_worktree_scope_ignores_main_manual_review(tmp_path: Path, monkeypatch) -> None:
    """D-10/NFR-002 observable (e): the worktree-scope decision has no
    ``manual_review`` parameter at all — a main-checkout manual-review must
    never suppress every worktree commit. Assert the signature itself has no
    such parameter (the strongest possible regression guard)."""
    import inspect

    params = inspect.signature(autocommit.should_auto_commit_for_worktree).parameters
    assert "manual_review" not in params

    monkeypatch.setattr(autocommit, "get_auto_commit_default", lambda _repo_root: True)
    assert autocommit.should_auto_commit_for_worktree(tmp_path, dry_run=False) is True


# ---------------------------------------------------------------------------
# FR-013 fail-safe commit branch (C7) — no fabricated "main"
# ---------------------------------------------------------------------------


def test_branch_detection_failure_skips_commit_with_warning(tmp_path: Path, monkeypatch) -> None:
    """When ``git branch --show-current`` raises, never fabricate a ``main``
    destination ref — skip the commit and surface a warning instead."""
    monkeypatch.setattr(
        autocommit,
        "prepare_upgrade_commit_files",
        lambda _checkout, baseline_paths: [Path(".kittify/metadata.yaml")],
    )
    monkeypatch.setattr(
        autocommit,
        "safe_commit",
        lambda **_kw: (_ for _ in ()).throw(AssertionError("safe_commit must not run when branch detection fails")),
    )
    monkeypatch.setattr(
        subprocess,
        "check_output",
        lambda *_a, **_kw: (_ for _ in ()).throw(subprocess.CalledProcessError(1, "git")),
    )

    committed, committed_paths, warning = autocommit.commit_touched_checkout(
        checkout=tmp_path,
        baseline_paths=set(),
        from_version="3.2.3",
        to_version="3.2.4",
    )

    assert committed is False
    assert committed_paths == [".kittify/metadata.yaml"]
    assert warning == autocommit.BRANCH_DETECTION_FAILED_WARNING
