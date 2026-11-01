from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "release" / "validate_release.py"

pytestmark = pytest.mark.git_repo


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )


def run_validator(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(VALIDATOR),
        "--pyproject",
        str(tmp_path / "pyproject.toml"),
        "--changelog",
        str(tmp_path / "CHANGELOG.md"),
        *args,
    ]
    return subprocess.run(
        cmd,
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )


def init_repo(tmp_path: Path) -> None:
    run(["git", "init"], tmp_path)
    run(["git", "config", "user.email", "maintainer@example.com"], tmp_path)
    run(["git", "config", "user.name", "Spec Kitty"], tmp_path)


def write_release_files(tmp_path: Path, version: str, changelog_body: str) -> None:
    (tmp_path / "pyproject.toml").write_text(
        dedent(
            f"""
            [project]
            name = "spec-kitty-cli"
            version = "{version}"
            description = "Spec Kitty CLI"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "CHANGELOG.md").write_text(changelog_body, encoding="utf-8")
    # FR-601/FR-602: keep .kittify/metadata.yaml in sync so validate_release.py passes
    kittify_dir = tmp_path / ".kittify"
    kittify_dir.mkdir(exist_ok=True)
    (kittify_dir / "metadata.yaml").write_text(
        f"spec_kitty:\n  version: {version}\n",
        encoding="utf-8",
    )
    write_uv_lock(tmp_path, version)


def write_uv_lock(tmp_path: Path, version: str) -> None:
    (tmp_path / "uv.lock").write_text(
        dedent(
            f"""
            version = 1
            revision = 3
            requires-python = ">=3.11"

            [[package]]
            name = "spec-kitty-cli"
            version = "{version}"
            source = {{ editable = "." }}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def stage_and_commit(tmp_path: Path, message: str) -> None:
    run(["git", "add", "."], tmp_path)
    run(["git", "commit", "-m", message], tmp_path)


def tag(tmp_path: Path, tag_name: str) -> None:
    run(["git", "tag", tag_name], tmp_path)


def changelog_for_versions(*versions: tuple[str, str]) -> str:
    sections = []
    for version, body in versions:
        sections.append(f"## {version}\n{body}\n")
    return "\n".join(sections)


def unreleased_changelog(version: str, body: str, *prior: tuple[str, str]) -> str:
    """Changelog whose top section is an Unreleased-marked heading for *version*."""
    sections = [f"## [Unreleased] - {version}\n{body}\n"]
    for prior_version, prior_body in prior:
        sections.append(f"## {prior_version}\n{prior_body}\n")
    return "\n".join(sections)


def write_migration(tmp_path: Path, filename: str, target_version: str) -> None:
    migrations_dir = tmp_path / "src" / "specify_cli" / "upgrade" / "migrations"
    migrations_dir.mkdir(parents=True, exist_ok=True)
    (migrations_dir / filename).write_text(
        dedent(
            f"""
            from specify_cli.upgrade.registry import MigrationRegistry
            from .base import BaseMigration

            TARGET_VERSION = "{target_version}"

            @MigrationRegistry.register
            class ExampleMigration(BaseMigration):
                migration_id = "{filename.removesuffix(".py")}"
                description = "test migration"
                target_version = TARGET_VERSION
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def test_branch_mode_succeeds_with_version_bump(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_release_files(
        tmp_path,
        "0.2.3",
        changelog_for_versions(("0.2.3", "- Initial release")),
    )
    stage_and_commit(tmp_path, "chore: bootstrap project")
    tag(tmp_path, "v0.2.3")

    write_release_files(
        tmp_path,
        "0.2.4",
        changelog_for_versions(
            ("0.2.4", "- Add automation"),
            ("0.2.3", "- Initial release"),
        ),
    )
    stage_and_commit(tmp_path, "chore: prep 0.2.4")

    result = run_validator(tmp_path, "--mode", "branch")

    assert result.returncode == 0, result.stderr
    assert "All required checks passed." in result.stdout


@pytest.mark.parametrize(
    ("previous", "candidate", "succeeds"),
    [
        ("3.2.6", "3.2.6.1", True),
        ("3.2.6.1", "3.2.6.2", True),
        ("3.2.6.2", "3.2.6.1", False),
        ("3.2.6.1", "3.2.7rc1", True),
        ("3.2.7rc1", "3.2.6.1", False),
        ("3.2.7rc1", "3.2.7", True),
        ("3.2.6.0", "3.2.6", False),
        ("3.2.6", "3.2.6.0", False),
        ("3.2.6.1beta2", "3.2.6.1rc1", True),
        ("3.2.6.1rc1", "3.2.6.1", True),
    ],
)
def test_hotfix_version_progression(tmp_path: Path, previous: str, candidate: str, succeeds: bool) -> None:
    init_repo(tmp_path)
    write_release_files(tmp_path, previous, changelog_for_versions((previous, "- Prior release")))
    stage_and_commit(tmp_path, "Prior release")
    tag(tmp_path, f"v{previous}")
    write_release_files(tmp_path, candidate, changelog_for_versions((candidate, "- Candidate")))

    result = run_validator(tmp_path, "--mode", "branch")

    assert result.returncode == (0 if succeeds else 1), result.stderr
    if not succeeds:
        assert "does not advance beyond latest tag" in result.stderr


@pytest.mark.parametrize("tag_source", ["argument", "environment"])
def test_hotfix_tag_publish_accepts_finalized_notes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tag_source: str) -> None:
    init_repo(tmp_path)
    write_release_files(tmp_path, "3.2.6.1", "## [3.2.6.1] - 2026-09-08\n- Fix first run\n")
    stage_and_commit(tmp_path, "Hotfix release")
    tag(tmp_path, "v3.2.6")
    tag(tmp_path, "v3.2.6.1")
    if tag_source == "environment":
        monkeypatch.setenv("GITHUB_REF_NAME", "v3.2.6.1")
        args = ("--mode", "tag")
    else:
        args = ("--mode", "tag", "--tag", "v3.2.6.1")

    result = run_validator(tmp_path, *args)

    assert result.returncode == 0, result.stderr
    assert "Tag: v3.2.6.1" in result.stdout


def test_hotfix_tag_rejects_unfinalized_notes(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_release_files(tmp_path, "3.2.6.1", unreleased_changelog("3.2.6.1", "- Fix first run"))
    stage_and_commit(tmp_path, "Pending hotfix")

    result = run_validator(tmp_path, "--mode", "tag", "--tag", "v3.2.6.1")

    assert result.returncode == 1
    assert "still marked 'Unreleased'" in result.stderr


def test_hotfix_release_rejects_newer_migration_target(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_release_files(tmp_path, "3.2.6.1", changelog_for_versions(("3.2.6.1", "- Fix first run")))
    write_migration(tmp_path, "m_later_hotfix.py", "3.2.6.2")
    stage_and_commit(tmp_path, "Hotfix with unreachable migration")

    result = run_validator(tmp_path, "--mode", "tag", "--tag", "v3.2.6.1")

    assert result.returncode == 1
    assert "Release 3.2.6.1 is behind migration target(s): 3.2.6.2" in result.stderr


def test_prerelease_fails_when_migration_target_is_newer_than_package(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_release_files(
        tmp_path,
        "3.2.0rc34",
        changelog_for_versions(("3.2.0rc34", "- Prior candidate")),
    )
    stage_and_commit(tmp_path, "chore: bootstrap 3.2.0rc34")
    tag(tmp_path, "v3.2.0rc34")

    write_release_files(
        tmp_path,
        "3.2.0rc35",
        changelog_for_versions(
            ("3.2.0rc35", "- Candidate"),
            ("3.2.0rc34", "- Prior candidate"),
        ),
    )
    write_migration(tmp_path, "m_3_2_0_final_repair.py", "3.2.0")
    stage_and_commit(tmp_path, "chore: prep 3.2.0rc35")

    result = run_validator(tmp_path, "--mode", "branch")

    assert result.returncode == 1
    assert "Release 3.2.0rc35 is behind migration target(s): 3.2.0" in result.stderr
    assert "A user upgrading to 3.2.0rc35 will not run migrations targeted after 3.2.0rc35" in result.stderr


def test_prerelease_accepts_migration_targets_at_candidate_version(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_release_files(
        tmp_path,
        "3.2.0rc34",
        changelog_for_versions(("3.2.0rc34", "- Prior candidate")),
    )
    stage_and_commit(tmp_path, "chore: bootstrap 3.2.0rc34")
    tag(tmp_path, "v3.2.0rc34")

    write_release_files(
        tmp_path,
        "3.2.0rc35",
        changelog_for_versions(
            ("3.2.0rc35", "- Candidate"),
            ("3.2.0rc34", "- Prior candidate"),
        ),
    )
    write_migration(tmp_path, "m_3_2_0rc35_late_repair.py", "3.2.0rc35")
    stage_and_commit(tmp_path, "chore: prep 3.2.0rc35")

    result = run_validator(tmp_path, "--mode", "branch")

    assert result.returncode == 0, result.stderr
    assert "All required checks passed." in result.stdout


def test_branch_mode_accepts_prerelease_version_bump(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_release_files(
        tmp_path,
        "3.0.3",
        changelog_for_versions(("3.0.3", "- Stable release")),
    )
    stage_and_commit(tmp_path, "chore: bootstrap 3.0.3")
    tag(tmp_path, "v3.0.3")

    write_release_files(
        tmp_path,
        "3.1.0a0",
        changelog_for_versions(
            ("3.1.0a0", "- Testing prerelease"),
            ("3.0.3", "- Stable release"),
        ),
    )
    stage_and_commit(tmp_path, "chore: prep 3.1.0a0")

    result = run_validator(tmp_path, "--mode", "branch")

    assert result.returncode == 0, result.stderr
    assert "All required checks passed." in result.stdout


def test_branch_mode_fails_without_changelog_entry(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_release_files(
        tmp_path,
        "0.2.3",
        changelog_for_versions(("0.2.3", "- Initial release")),
    )
    stage_and_commit(tmp_path, "chore: bootstrap project")
    tag(tmp_path, "v0.2.3")

    write_release_files(
        tmp_path,
        "0.2.4",
        changelog_for_versions(("0.2.3", "- Initial release")),
    )
    stage_and_commit(tmp_path, "chore: prep 0.2.4 without changelog entry")

    result = run_validator(tmp_path, "--mode", "branch")

    assert result.returncode == 1
    assert "CHANGELOG.md lacks a populated section for 0.2.4" in result.stderr


def test_branch_mode_fails_when_uv_lock_version_drifts(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_release_files(
        tmp_path,
        "0.2.3",
        changelog_for_versions(("0.2.3", "- Initial release")),
    )
    stage_and_commit(tmp_path, "chore: bootstrap project")
    tag(tmp_path, "v0.2.3")

    write_release_files(
        tmp_path,
        "0.2.4",
        changelog_for_versions(
            ("0.2.4", "- Add automation"),
            ("0.2.3", "- Initial release"),
        ),
    )
    write_uv_lock(tmp_path, "0.2.3")
    stage_and_commit(tmp_path, "chore: prep 0.2.4 with stale lockfile")

    result = run_validator(tmp_path, "--mode", "branch")

    assert result.returncode == 1
    assert "uv.lock" in result.stderr
    assert "0.2.4" in result.stderr
    assert "0.2.3" in result.stderr


def test_default_lockfile_uses_target_repo_when_called_from_elsewhere(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    caller = tmp_path / "caller"
    target.mkdir()
    caller.mkdir()
    init_repo(target)

    write_release_files(
        target,
        "0.2.3",
        changelog_for_versions(("0.2.3", "- Initial release")),
    )
    stage_and_commit(target, "chore: bootstrap project")
    tag(target, "v0.2.3")

    write_release_files(
        target,
        "0.2.4",
        changelog_for_versions(
            ("0.2.4", "- Add automation"),
            ("0.2.3", "- Initial release"),
        ),
    )
    write_uv_lock(target, "0.2.3")
    write_uv_lock(caller, "0.2.4")
    stage_and_commit(target, "chore: prep 0.2.4 with stale target lockfile")

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--mode",
            "branch",
            "--pyproject",
            str(target / "pyproject.toml"),
            "--changelog",
            str(target / "CHANGELOG.md"),
        ],
        cwd=caller,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert str(target / "uv.lock") in result.stdout
    assert str(caller / "uv.lock") not in result.stdout
    assert "uv.lock" in result.stderr
    assert "0.2.4" in result.stderr
    assert "0.2.3" in result.stderr


def test_consistency_only_skips_release_progression(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_release_files(
        tmp_path,
        "0.2.3",
        changelog_for_versions(("0.2.3", "- Initial release")),
    )
    stage_and_commit(tmp_path, "chore: bootstrap project")
    tag(tmp_path, "v0.2.3")

    result = run_validator(tmp_path, "--mode", "branch", "--consistency-only")

    assert result.returncode == 0, result.stderr
    assert "All required checks passed." in result.stdout


@pytest.mark.parametrize(("version", "newer"), [("1.2.3", "1.2.4"), ("3.2.6.1", "3.2.6.2")])
def test_consistency_only_rejects_stale_top_changelog_release(
    tmp_path: Path,
    version: str,
    newer: str,
) -> None:
    init_repo(tmp_path)
    write_release_files(
        tmp_path,
        version,
        changelog_for_versions(
            (newer, "- Drifted future entry"),
            (version, "- Historical matching entry"),
        ),
    )
    stage_and_commit(tmp_path, "chore: bootstrap drifted changelog")
    tag(tmp_path, f"v{version}")

    result = run_validator(tmp_path, "--mode", "branch", "--consistency-only")

    assert result.returncode == 1
    assert f"CHANGELOG.md latest release entry is '{newer}'" in result.stderr
    assert f"pyproject.toml declares '{version}'" in result.stderr


@pytest.mark.parametrize(
    ("pyproject_version", "lockfile_version"),
    [
        ("1.0.0alpha", "1.0.0a0"),
        ("1.0.0alpha1", "1.0.0a1"),
        ("1.0.0beta", "1.0.0b0"),
        ("1.0.0beta1", "1.0.0b1"),
        ("3.2.6.1alpha", "3.2.6.1a0"),
        ("3.2.6.1beta2", "3.2.6.1b2"),
    ],
)
def test_uv_lock_sync_accepts_canonical_prerelease_aliases(
    tmp_path: Path,
    pyproject_version: str,
    lockfile_version: str,
) -> None:
    init_repo(tmp_path)
    write_release_files(
        tmp_path,
        pyproject_version,
        changelog_for_versions((pyproject_version, "- Prerelease")),
    )
    write_uv_lock(tmp_path, lockfile_version)

    result = run_validator(tmp_path, "--mode", "branch", "--consistency-only")

    assert result.returncode == 0, result.stderr
    assert "All required checks passed." in result.stdout


def test_malformed_uv_lock_reports_validation_issue(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_release_files(
        tmp_path,
        "0.2.4",
        changelog_for_versions(("0.2.4", "- Add automation")),
    )
    (tmp_path / "uv.lock").write_text("not = [valid\n", encoding="utf-8")

    result = run_validator(tmp_path, "--mode", "branch", "--consistency-only")

    assert result.returncode == 1
    assert "Unable to parse uv.lock" in result.stderr
    assert "Issues detected:" in result.stdout


@pytest.mark.parametrize("version", ["3.2.6.1.2", "3.2.6.", "3.2.6.hotfix1"])
def test_hotfix_grammar_rejects_extra_or_invalid_components(tmp_path: Path, version: str) -> None:
    init_repo(tmp_path)
    write_release_files(tmp_path, version, changelog_for_versions((version, "- Invalid version")))

    result = run_validator(tmp_path, "--mode", "branch", "--consistency-only")

    assert result.returncode == 1
    assert "not a supported release version" in result.stderr


def test_tag_mode_validates_tag_alignment(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_release_files(
        tmp_path,
        "0.2.3",
        changelog_for_versions(("0.2.3", "- Initial release")),
    )
    stage_and_commit(tmp_path, "chore: bootstrap project")
    tag(tmp_path, "v0.2.3")

    write_release_files(
        tmp_path,
        "0.2.4",
        changelog_for_versions(
            ("0.2.4", "- Add automation"),
            ("0.2.3", "- Initial release"),
        ),
    )
    stage_and_commit(tmp_path, "chore: prep 0.2.4")
    tag(tmp_path, "v0.2.4")

    env = os.environ.copy()
    env.pop("GITHUB_REF", None)
    env.pop("GITHUB_REF_NAME", None)

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--mode",
            "tag",
            "--tag",
            "v0.2.4",
            "--pyproject",
            str(tmp_path / "pyproject.toml"),
            "--changelog",
            str(tmp_path / "CHANGELOG.md"),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "Tag: v0.2.4" in result.stdout


def test_tag_mode_fails_on_regression(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_release_files(
        tmp_path,
        "0.2.3",
        changelog_for_versions(("0.2.3", "- Initial release")),
    )
    stage_and_commit(tmp_path, "chore: bootstrap project")
    tag(tmp_path, "v0.2.3")

    write_release_files(
        tmp_path,
        "0.2.2",
        changelog_for_versions(
            ("0.2.2", "- Regression build"),
            ("0.2.3", "- Initial release"),
        ),
    )
    stage_and_commit(tmp_path, "chore: regress version")

    result = run_validator(tmp_path, "--mode", "tag", "--tag", "v0.2.2")

    assert result.returncode == 1
    assert "does not advance beyond latest tag v0.2.3" in result.stderr


def test_tag_mode_accepts_prerelease_versions(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_release_files(
        tmp_path,
        "0.2.3",
        changelog_for_versions(("0.2.3", "- Initial release")),
    )
    stage_and_commit(tmp_path, "chore: bootstrap project")
    tag(tmp_path, "v0.2.3")

    write_release_files(
        tmp_path,
        "0.3.0a0",
        changelog_for_versions(
            ("0.3.0a0", "- Testing prerelease"),
            ("0.2.3", "- Initial release"),
        ),
    )
    stage_and_commit(tmp_path, "chore: prep 0.3.0a0")

    result = run_validator(tmp_path, "--mode", "tag", "--tag", "v0.3.0a0")

    assert result.returncode == 0, result.stderr
    assert "Tag: v0.3.0a0" in result.stdout


def test_branch_mode_honors_tag_pattern_scope(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_release_files(
        tmp_path,
        "2.0.0",
        changelog_for_versions(("2.0.0", "- Initial 2.x release")),
    )
    stage_and_commit(tmp_path, "chore: bootstrap 2.0.0")
    tag(tmp_path, "v2.0.0")

    write_release_files(
        tmp_path,
        "3.0.0",
        changelog_for_versions(
            ("3.0.0", "- Different release line"),
            ("2.0.0", "- Initial 2.x release"),
        ),
    )
    stage_and_commit(tmp_path, "chore: create unrelated major line")
    tag(tmp_path, "v3.0.0")

    write_release_files(
        tmp_path,
        "2.0.1",
        changelog_for_versions(
            ("2.0.1", "- Patch release"),
            ("3.0.0", "- Different release line"),
            ("2.0.0", "- Initial 2.x release"),
        ),
    )
    stage_and_commit(tmp_path, "chore: prep 2.0.1")

    result_scoped = run_validator(tmp_path, "--mode", "branch", "--tag-pattern", "v2.*.*")
    assert result_scoped.returncode == 0, result_scoped.stderr

    result_unscoped = run_validator(tmp_path, "--mode", "branch")
    assert result_unscoped.returncode == 1
    assert "does not advance beyond latest tag v3.0.0" in result_unscoped.stderr


def test_tag_mode_rejects_prerelease_regression(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_release_files(
        tmp_path,
        "1.0.0",
        changelog_for_versions(("1.0.0", "- Initial stable release")),
    )
    stage_and_commit(tmp_path, "chore: bootstrap 1.0.0")
    tag(tmp_path, "v1.0.0")

    write_release_files(
        tmp_path,
        "1.0.1a1",
        changelog_for_versions(
            ("1.0.1a1", "- Later prerelease"),
            ("1.0.0", "- Initial stable release"),
        ),
    )
    stage_and_commit(tmp_path, "chore: prep 1.0.1a1")
    tag(tmp_path, "v1.0.1a1")

    write_release_files(
        tmp_path,
        "1.0.1a0",
        changelog_for_versions(
            ("1.0.1a0", "- Earlier prerelease"),
            ("1.0.1a1", "- Later prerelease"),
            ("1.0.0", "- Initial stable release"),
        ),
    )
    stage_and_commit(tmp_path, "chore: regress to 1.0.1a0")

    result = run_validator(tmp_path, "--mode", "tag", "--tag", "v1.0.1a0")

    assert result.returncode == 1
    assert "does not advance beyond latest tag v1.0.1a1" in result.stderr


def test_branch_mode_accepts_final_release_after_prerelease_tag(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_release_files(
        tmp_path,
        "1.0.0",
        changelog_for_versions(("1.0.0", "- Initial stable release")),
    )
    stage_and_commit(tmp_path, "chore: bootstrap 1.0.0")
    tag(tmp_path, "v1.0.0")

    write_release_files(
        tmp_path,
        "1.0.1a1",
        changelog_for_versions(
            ("1.0.1a1", "- Release candidate"),
            ("1.0.0", "- Initial stable release"),
        ),
    )
    stage_and_commit(tmp_path, "chore: prep 1.0.1a1")
    tag(tmp_path, "v1.0.1a1")

    write_release_files(
        tmp_path,
        "1.0.1",
        changelog_for_versions(
            ("1.0.1", "- Stable patch release"),
            ("1.0.1a1", "- Release candidate"),
            ("1.0.0", "- Initial stable release"),
        ),
    )
    stage_and_commit(tmp_path, "chore: prep 1.0.1")

    result = run_validator(tmp_path, "--mode", "branch", "--tag-pattern", "v*.*.*")

    assert result.returncode == 0, result.stderr
    assert "All required checks passed." in result.stdout


# ---------------------------------------------------------------------------
# Pre-release "Unreleased - X.Y.Z" heading tolerance (branch mode) vs.
# tag-mode finalization strictness.
# ---------------------------------------------------------------------------


def test_branch_consistency_only_accepts_unreleased_marked_section(tmp_path: Path) -> None:
    """Branch + --consistency-only must accept '## [Unreleased] - X.Y.Z' for the pyproject version."""
    init_repo(tmp_path)
    write_release_files(
        tmp_path,
        "3.2.3",
        unreleased_changelog(
            "3.2.3",
            "- Pending release notes",
            ("3.2.2", "- Prior release"),
        ),
    )
    stage_and_commit(tmp_path, "chore: prep 3.2.3 (unreleased heading)")
    tag(tmp_path, "v3.2.2")

    result = run_validator(tmp_path, "--mode", "branch", "--consistency-only")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "All required checks passed." in result.stdout


def test_branch_mode_accepts_unreleased_marked_section(tmp_path: Path) -> None:
    """Full branch mode must accept '## [Unreleased] - X.Y.Z' for the pyproject version."""
    init_repo(tmp_path)
    write_release_files(
        tmp_path,
        "3.2.3",
        unreleased_changelog(
            "3.2.3",
            "- Pending release notes",
            ("3.2.2", "- Prior release"),
        ),
    )
    stage_and_commit(tmp_path, "chore: prep 3.2.3 (unreleased heading)")
    tag(tmp_path, "v3.2.2")

    result = run_validator(tmp_path, "--mode", "branch")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "All required checks passed." in result.stdout


@pytest.mark.parametrize(
    "heading",
    [
        "## [Unreleased] - 3.2.3",
        "## [3.2.3] - Unreleased",
        "## 3.2.3 - Unreleased",
        "## Unreleased - 3.2.3",
    ],
)
def test_branch_mode_accepts_all_unreleased_heading_variations(tmp_path: Path, heading: str) -> None:
    """Every documented Unreleased+version heading variation parses to the version in branch mode."""
    init_repo(tmp_path)
    changelog = f"{heading}\n- Pending release notes\n\n## 3.2.2\n- Prior release\n"
    write_release_files(tmp_path, "3.2.3", changelog)
    stage_and_commit(tmp_path, "chore: prep 3.2.3 variation")
    tag(tmp_path, "v3.2.2")

    result = run_validator(tmp_path, "--mode", "branch")

    assert result.returncode == 0, f"{heading!r}: {result.stdout}{result.stderr}"
    assert "All required checks passed." in result.stdout


def test_tag_mode_rejects_unreleased_marked_section(tmp_path: Path) -> None:
    """Tag mode must STILL fail on an Unreleased-marked section — release not finalized."""
    init_repo(tmp_path)
    write_release_files(
        tmp_path,
        "3.2.3",
        unreleased_changelog(
            "3.2.3",
            "- Pending release notes",
            ("3.2.2", "- Prior release"),
        ),
    )
    stage_and_commit(tmp_path, "chore: prep 3.2.3 (unreleased heading)")
    tag(tmp_path, "v3.2.2")
    tag(tmp_path, "v3.2.3")

    result = run_validator(tmp_path, "--mode", "tag", "--tag", "v3.2.3")

    assert result.returncode == 1, result.stdout + result.stderr
    combined = result.stdout + result.stderr
    assert "3.2.3" in combined
    assert "finalized" in combined.lower()


def test_tag_mode_accepts_finalized_section(tmp_path: Path) -> None:
    """Tag mode passes for a finalized '## [X.Y.Z]' section (regression guard)."""
    init_repo(tmp_path)
    write_release_files(
        tmp_path,
        "3.2.3",
        changelog_for_versions(
            ("[3.2.3]", "- Final release notes"),
            ("[3.2.2]", "- Prior release"),
        ),
    )
    stage_and_commit(tmp_path, "chore: finalize 3.2.3")
    tag(tmp_path, "v3.2.2")
    tag(tmp_path, "v3.2.3")

    result = run_validator(tmp_path, "--mode", "tag", "--tag", "v3.2.3")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Tag: v3.2.3" in result.stdout


def test_versionless_unreleased_above_finalized_section_unchanged(tmp_path: Path) -> None:
    """Classic version-less '## [Unreleased]' above a finalized '## [3.2.2]' still behaves as before."""
    init_repo(tmp_path)
    changelog = "## [Unreleased]\n- Work in progress\n\n## [3.2.2]\n- Prior release\n"
    write_release_files(tmp_path, "3.2.2", changelog)
    stage_and_commit(tmp_path, "chore: bootstrap 3.2.2 with unreleased placeholder")
    tag(tmp_path, "v3.2.1")

    result = run_validator(tmp_path, "--mode", "branch")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "All required checks passed." in result.stdout


def test_tag_mode_refuses_unassembled_changelog_fragments(tmp_path: Path) -> None:
    """A tag must not ship while per-PR fragments still sit outside the finalized notes."""
    init_repo(tmp_path)
    write_release_files(tmp_path, "3.2.6.1", "## [3.2.6.1] - 2026-09-08\n- Fix first run\n")
    fragments = tmp_path / "docs" / "changelog" / "unreleased"
    fragments.mkdir(parents=True)
    (fragments / "README.md").write_text("How to write a fragment.\n", encoding="utf-8")
    (fragments / "7001.fixed.md").write_text("- **Left behind** (#7001).\n", encoding="utf-8")
    stage_and_commit(tmp_path, "Hotfix release with a stray fragment")
    tag(tmp_path, "v3.2.6")
    tag(tmp_path, "v3.2.6.1")

    result = run_validator(tmp_path, "--mode", "tag", "--tag", "v3.2.6.1")

    assert result.returncode == 1
    assert "7001.fixed.md" in result.stderr
    assert "changelog_fragments assemble --write" in result.stderr


def test_a_release_cut_branch_refuses_unassembled_fragments(tmp_path: Path) -> None:
    """Branch mode on a finalized section (the release-cut PR) catches a leftover before the tag."""
    init_repo(tmp_path)
    write_release_files(tmp_path, "3.2.6.1", "## [3.2.6.1] - 2026-09-08\n- Fix first run\n")
    fragments = tmp_path / "docs" / "changelog" / "unreleased"
    fragments.mkdir(parents=True)
    (fragments / "7001.fixed.md").write_text("- **Left behind** (#7001).\n", encoding="utf-8")
    stage_and_commit(tmp_path, "Release cut with a stray fragment")
    tag(tmp_path, "v3.2.6")

    result = run_validator(tmp_path, "--mode", "branch", "--tag-pattern", "v*.*.*")

    assert result.returncode == 1
    assert "7001.fixed.md" in result.stderr


def test_an_open_cycle_branch_accepts_fragments(tmp_path: Path) -> None:
    """While the section is still [Unreleased], fragments are the normal state."""
    init_repo(tmp_path)
    write_release_files(tmp_path, "3.2.6.1", unreleased_changelog("3.2.6.1", "- Fix first run"))
    fragments = tmp_path / "docs" / "changelog" / "unreleased"
    fragments.mkdir(parents=True)
    (fragments / "7001.fixed.md").write_text("- **Pending** (#7001).\n", encoding="utf-8")
    stage_and_commit(tmp_path, "Open cycle with a fragment")
    tag(tmp_path, "v3.2.6")

    result = run_validator(tmp_path, "--mode", "branch", "--tag-pattern", "v*.*.*")

    assert result.returncode == 0, result.stderr
