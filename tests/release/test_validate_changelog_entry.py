"""Regression tests for FR-603: CHANGELOG-presence check in branch mode.

Test T7.3 from WP07 mission 079-post-555-release-hardening.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from scripts.release.extract_changelog import extract_changelog_section
from scripts.release.validate_release import changelog_has_entry

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "release" / "validate_release.py"


def _write_release_files(
    tmp_path: Path,
    version: str,
    changelog: str,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        dedent(
            f"""\
            [project]
            name = "spec-kitty-cli"
            version = "{version}"
            description = "Test project"
            """
        ),
        encoding="utf-8",
    )
    (tmp_path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify" / "metadata.yaml").write_text(
        f"spec_kitty:\n  version: {version}\n",
        encoding="utf-8",
    )
    (tmp_path / "uv.lock").write_text(
        dedent(
            f"""\
            version = 1
            revision = 3
            requires-python = ">=3.11"

            [[package]]
            name = "spec-kitty-cli"
            version = "{version}"
            source = {{ editable = "." }}
            """
        ),
        encoding="utf-8",
    )


def _init_git_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "add", "."],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# changelog_has_entry unit tests
# ---------------------------------------------------------------------------


def test_changelog_has_entry_returns_true_when_present() -> None:
    changelog = "# Changelog\n\n## [3.1.1] - 2026-04-09\n\n### Fixed\n- The fix\n"
    assert changelog_has_entry(changelog, "3.1.1") is True


@pytest.mark.parametrize("version", ["3.2.6.1", "3.2.6.1rc1"])
def test_extract_hotfix_notes_excludes_adjacent_releases(version: str) -> None:
    changelog = f"## [3.2.6.2] - 2026-09-09\n- Later fix\n\n## [{version}] - 2026-09-08\n- First-run fix\n\n## [3.2.6] - 2026-09-01\n- Older release\n"

    assert extract_changelog_section(changelog, version) == "- First-run fix"
    assert extract_changelog_section(changelog, "3.2.6.2") == "- Later fix"


def test_changelog_has_entry_returns_false_when_absent() -> None:
    changelog = "# Changelog\n\n## [3.0.0] - 2025-01-01\n\n### Fixed\n- Old fix\n"
    assert changelog_has_entry(changelog, "3.1.1") is False


def test_changelog_has_entry_returns_false_for_empty_section() -> None:
    changelog = "# Changelog\n\n## [3.1.1] - 2026-04-09\n\n"
    assert changelog_has_entry(changelog, "3.1.1") is False


def test_changelog_has_entry_prerelease_version() -> None:
    changelog = "# Changelog\n\n## [3.1.1a3] - 2026-04-07\n\n### Changed\n- Alpha release\n"
    assert changelog_has_entry(changelog, "3.1.1a3") is True
    assert changelog_has_entry(changelog, "3.1.1") is False


def test_changelog_has_entry_unreleased_version_tranche() -> None:
    changelog = "# Changelog\n\n## [Unreleased - 3.2.0]\n\n### Changed\n- The tranche\n\n## [3.2.0rc29] - 2026-05-28\n\n### Fixed\n- Old release candidate\n"
    assert changelog_has_entry(changelog, "3.2.0") is True
    assert changelog_has_entry(changelog, "3.2.0rc29") is True


def test_extract_changelog_section_unreleased_version_tranche() -> None:
    changelog = "# Changelog\n\n## [Unreleased - 3.2.0]\n\n### Changed\n- The tranche\n\n## [3.2.0rc29] - 2026-05-28\n\n### Fixed\n- Old release candidate\n"
    section = extract_changelog_section(changelog, "3.2.0")
    assert "The tranche" in section
    assert "Old release candidate" not in section


# ---------------------------------------------------------------------------
# T7.3 — Branch mode CHANGELOG presence check (integration)
# ---------------------------------------------------------------------------


@pytest.mark.git_repo
def test_missing_changelog_entry_fails_in_branch_mode(tmp_path: Path) -> None:
    """Validator exits non-zero in branch mode when CHANGELOG entry is missing."""
    changelog = "# Changelog\n\n## [3.0.0] - 2025-01-01\n\n### Fixed\n- Old fix\n"
    _write_release_files(tmp_path, "3.1.1", changelog)
    _init_git_repo(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--mode",
            "branch",
            "--pyproject",
            str(tmp_path / "pyproject.toml"),
            "--changelog",
            str(tmp_path / "CHANGELOG.md"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "3.1.1" in combined


@pytest.mark.git_repo
def test_present_changelog_entry_passes_in_branch_mode(tmp_path: Path) -> None:
    """Validator exits 0 in branch mode when CHANGELOG entry exists."""
    changelog = "# Changelog\n\n## [3.1.1] - 2026-04-09\n\n### Fixed\n- The fix\n\n## [3.0.0] - 2025-01-01\n\n### Fixed\n- Old fix\n"
    _write_release_files(tmp_path, "3.1.1", changelog)
    _init_git_repo(tmp_path)

    # Tag v3.0.0 so progression check passes
    subprocess.run(["git", "tag", "v3.0.0"], cwd=tmp_path, check=True, capture_output=True)

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--mode",
            "branch",
            "--pyproject",
            str(tmp_path / "pyproject.toml"),
            "--changelog",
            str(tmp_path / "CHANGELOG.md"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
