"""Unit tests for the bulk edit occurrence classification gate."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.bulk_edit.gate import (
    GateResult,
    check_review_diff_compliance,
    ensure_occurrence_classification_ready,
)


pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


def _write_meta(feature_dir: Path, meta: dict) -> None:
    """Helper to write a meta.json file."""
    meta_path = feature_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _write_occurrence_map(feature_dir: Path, content: str) -> None:
    """Helper to write an occurrence_map.yaml file."""
    omap_path = feature_dir / "occurrence_map.yaml"
    omap_path.write_text(content, encoding="utf-8")


VALID_OCCURRENCE_MAP = """\
target:
  term: oldName
  replacement: newName
  operation: rename
categories:
  code_symbols:
    action: rename
  import_paths:
    action: rename
  filesystem_paths:
    action: manual_review
  serialized_keys:
    action: do_not_change
  cli_commands:
    action: do_not_change
  user_facing_strings:
    action: rename_if_user_visible
  tests_fixtures:
    action: rename
  logs_telemetry:
    action: do_not_change
"""

INVALID_OCCURRENCE_MAP_MISSING_TARGET = """\
categories:
  code_symbols:
    action: rename
"""

# Map that passes validation and has >= 3 categories, but is missing
# several of the 8 standard categories — fails FR-004 admissibility.
INADMISSIBLE_OCCURRENCE_MAP_FEW_CATEGORIES = """\
target:
  term: oldName
  replacement: newName
  operation: rename
categories:
  code_symbols:
    action: rename
  import_paths:
    action: rename
"""


class TestGatePassesNonBulkEdit:
    """Gate should pass for missions that are not bulk_edit."""

    def test_no_change_mode_in_meta(self, tmp_path: Path) -> None:
        _write_meta(tmp_path, {"slug": "my-feature", "mission_slug": "my-feature", "friendly_name": "Test", "mission_type": "software-dev", "target_branch": "main", "created_at": "2026-01-01"})
        result = ensure_occurrence_classification_ready(tmp_path)
        assert result.passed is True
        assert result.change_mode is None
        assert result.errors == []

    def test_different_change_mode(self, tmp_path: Path) -> None:
        _write_meta(tmp_path, {"slug": "my-feature", "mission_slug": "my-feature", "friendly_name": "Test", "mission_type": "software-dev", "target_branch": "main", "created_at": "2026-01-01", "change_mode": "standard"})
        result = ensure_occurrence_classification_ready(tmp_path)
        assert result.passed is True
        # FR-012 alignment: a non-bulk_edit (legacy) value collapses to None so the
        # invariant GateResult.change_mode in {"bulk_edit", None} holds and every
        # reader treats legacy value == absent. Not a behavior regression.
        assert result.change_mode is None


class TestGatePassesNoMeta:
    """Gate should pass when there is no meta.json at all."""

    def test_missing_meta_json(self, tmp_path: Path) -> None:
        result = ensure_occurrence_classification_ready(tmp_path)
        assert result.passed is True
        assert result.change_mode is None
        assert result.errors == []


class TestGateBlocksBulkEditNoMap:
    """Gate should block when change_mode=bulk_edit but no occurrence_map.yaml exists."""

    def test_blocks_with_error(self, tmp_path: Path) -> None:
        _write_meta(tmp_path, {"slug": "my-feature", "mission_slug": "my-feature", "friendly_name": "Test", "mission_type": "software-dev", "target_branch": "main", "created_at": "2026-01-01", "change_mode": "bulk_edit"})
        result = ensure_occurrence_classification_ready(tmp_path)
        assert result.passed is False
        assert result.change_mode == "bulk_edit"
        assert len(result.errors) == 1
        assert "Occurrence map required" in result.errors[0]
        assert "occurrence_map.yaml" in result.errors[0]


class TestGateBlocksBulkEditInvalidMap:
    """Gate should block when occurrence_map.yaml has structural validation errors."""

    def test_blocks_missing_target(self, tmp_path: Path) -> None:
        _write_meta(tmp_path, {"slug": "my-feature", "mission_slug": "my-feature", "friendly_name": "Test", "mission_type": "software-dev", "target_branch": "main", "created_at": "2026-01-01", "change_mode": "bulk_edit"})
        _write_occurrence_map(tmp_path, INVALID_OCCURRENCE_MAP_MISSING_TARGET)
        result = ensure_occurrence_classification_ready(tmp_path)
        assert result.passed is False
        assert result.change_mode == "bulk_edit"
        assert any("target" in e.lower() for e in result.errors)


class TestGateBlocksBulkEditInadmissible:
    """Gate should block when occurrence_map is structurally valid but has <3 categories."""

    def test_blocks_too_few_categories(self, tmp_path: Path) -> None:
        _write_meta(tmp_path, {"slug": "my-feature", "mission_slug": "my-feature", "friendly_name": "Test", "mission_type": "software-dev", "target_branch": "main", "created_at": "2026-01-01", "change_mode": "bulk_edit"})
        _write_occurrence_map(tmp_path, INADMISSIBLE_OCCURRENCE_MAP_FEW_CATEGORIES)
        result = ensure_occurrence_classification_ready(tmp_path)
        assert result.passed is False
        assert result.change_mode == "bulk_edit"
        assert any("at least" in e.lower() or "categories" in e.lower() for e in result.errors)


class TestGatePassesBulkEditValidMap:
    """Gate should pass when change_mode=bulk_edit and a valid, admissible map exists."""

    def test_passes_valid_map(self, tmp_path: Path) -> None:
        _write_meta(tmp_path, {"slug": "my-feature", "mission_slug": "my-feature", "friendly_name": "Test", "mission_type": "software-dev", "target_branch": "main", "created_at": "2026-01-01", "change_mode": "bulk_edit"})
        _write_occurrence_map(tmp_path, VALID_OCCURRENCE_MAP)
        result = ensure_occurrence_classification_ready(tmp_path)
        assert result.passed is True
        assert result.change_mode == "bulk_edit"
        assert result.errors == []


REVIEW_DIFF_OCCURRENCE_MAP = """\
target:
  term: oldName
  operation: rename
categories:
  code_symbols:
    action: rename
  import_paths:
    action: rename
  filesystem_paths:
    action: rename
  serialized_keys:
    action: do_not_change
  cli_commands:
    action: rename
  user_facing_strings:
    action: rename
  tests_fixtures:
    action: rename
  logs_telemetry:
    action: rename
"""


def _run_git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "-m", message)
    return _run_git(repo, "rev-parse", "HEAD")


def _make_review_feature_dir(tmp_path: Path) -> Path:
    feature_dir = tmp_path / "feature"
    feature_dir.mkdir()
    _write_meta(feature_dir, {"change_mode": "bulk_edit"})
    _write_occurrence_map(feature_dir, REVIEW_DIFF_OCCURRENCE_MAP)
    return feature_dir


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test User")
    return repo


def test_review_diff_compliance_bad_base_ref_fails_closed(tmp_path: Path) -> None:
    feature_dir = _make_review_feature_dir(tmp_path)
    repo = _make_repo(tmp_path)
    (repo / "config.yaml").write_text("oldName: true\n", encoding="utf-8")
    _commit(repo, "initial")

    result = check_review_diff_compliance(
        feature_dir=feature_dir,
        repo_root=repo,
        base_ref="does-not-exist",
        head_ref="HEAD",
    )

    assert result is not None
    assert result.passed is False
    assert result.assessments == []
    assert any("git diff failed" in error for error in result.errors)
    assert any("base_ref='does-not-exist'" in error for error in result.errors)


def test_review_diff_compliance_git_failure_includes_stderr(tmp_path: Path) -> None:
    feature_dir = _make_review_feature_dir(tmp_path)
    repo = _make_repo(tmp_path)
    (repo / "config.yaml").write_text("oldName: true\n", encoding="utf-8")
    _commit(repo, "initial")

    result = check_review_diff_compliance(
        feature_dir=feature_dir,
        repo_root=repo,
        base_ref="does-not-exist",
        head_ref="HEAD",
    )

    assert result is not None
    assert result.passed is False
    assert any("returncode=128" in error for error in result.errors)
    assert any("does-not-exist" in error for error in result.errors)


@pytest.mark.parametrize(
    "base_ref,head_ref,missing_ref",
    [
        ("", "HEAD", "base_ref"),
        ("HEAD", "", "head_ref"),
    ],
)
def test_review_diff_compliance_empty_ref_fails_closed(
    tmp_path: Path,
    base_ref: str,
    head_ref: str,
    missing_ref: str,
) -> None:
    feature_dir = _make_review_feature_dir(tmp_path)
    repo = _make_repo(tmp_path)
    (repo / "config.yaml").write_text("oldName: true\n", encoding="utf-8")
    _commit(repo, "initial")

    result = check_review_diff_compliance(
        feature_dir=feature_dir,
        repo_root=repo,
        base_ref=base_ref,
        head_ref=head_ref,
    )

    assert result is not None
    assert result.passed is False
    assert result.assessments == []
    assert any(f"{missing_ref} is empty" in error for error in result.errors)


def test_review_diff_compliance_valid_empty_diff_can_pass(tmp_path: Path) -> None:
    feature_dir = _make_review_feature_dir(tmp_path)
    repo = _make_repo(tmp_path)
    (repo / "config.yaml").write_text("oldName: true\n", encoding="utf-8")
    head = _commit(repo, "initial")

    result = check_review_diff_compliance(
        feature_dir=feature_dir,
        repo_root=repo,
        base_ref=head,
        head_ref=head,
    )

    assert result is not None
    assert result.passed is True
    assert result.assessments == []
    assert result.errors == []


def test_review_diff_compliance_valid_violation_still_blocks(tmp_path: Path) -> None:
    feature_dir = _make_review_feature_dir(tmp_path)
    repo = _make_repo(tmp_path)
    config = repo / "config.yaml"
    config.write_text("oldName: true\n", encoding="utf-8")
    base = _commit(repo, "initial")
    config.write_text("oldName: false\n", encoding="utf-8")
    _commit(repo, "change config")

    result = check_review_diff_compliance(
        feature_dir=feature_dir,
        repo_root=repo,
        base_ref=base,
        head_ref="HEAD",
    )

    assert result is not None
    assert result.passed is False
    assert any(a.path == "config.yaml" and a.violation for a in result.assessments)
    assert any("do_not_change" in error for error in result.errors)
