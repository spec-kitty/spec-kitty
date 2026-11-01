"""Scope: compat unit tests — no real git or subprocesses."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.upgrade.compat import uses_centralized_runtime

pytestmark = pytest.mark.fast


@pytest.mark.usefixtures("canonical_home")  # R1b (#3121): the canonical owner pins SPEC_KITTY_HOME=tmp_path/home
def test_uses_centralized_runtime_does_not_assume_metadata_less_repo_is_2x(
    tmp_path: Path,
) -> None:
    """Repo with .kittify but no metadata.yaml is not treated as 2.x managed."""
    # Arrange
    home = tmp_path / "home"
    (home / "cache").mkdir(parents=True, exist_ok=True)
    (home / "cache" / "version.lock").write_text("2.0.6", encoding="utf-8")

    project = tmp_path / "project"
    (project / ".kittify").mkdir(parents=True)
    (project / "kitty-specs").mkdir()

    # Assumption check
    assert not (project / ".kittify" / "metadata.yaml").exists(), "must have no metadata file"

    # Act
    result = uses_centralized_runtime(project)

    # Assert
    assert result is False


@pytest.mark.usefixtures("canonical_home")  # R1b (#3121): the canonical owner pins SPEC_KITTY_HOME=tmp_path/home
def test_uses_centralized_runtime_treats_metadata_less_worktree_as_runtime_managed(
    tmp_path: Path,
) -> None:
    """Worktree path without metadata is treated as runtime-managed (no project-local config needed)."""
    # Arrange
    home = tmp_path / "home"
    (home / "cache").mkdir(parents=True, exist_ok=True)
    (home / "cache" / "version.lock").write_text("2.0.6", encoding="utf-8")

    worktree = tmp_path / "repo" / ".worktrees" / "001-feature-lane-a"
    (worktree / "kitty-specs").mkdir(parents=True)

    # Assumption check
    assert ".worktrees" in str(worktree), "path must be a worktree path"

    # Act
    result = uses_centralized_runtime(worktree)

    # Assert
    assert result is True


_METADATA_YAML = (
    "spec_kitty:\n"
    "  version: '{version}'\n"
    "  initialized_at: '2026-01-01T00:00:00'\n"
    "environment:\n"
    "  python_version: '3.12'\n"
    "  platform: linux\n"
    "  platform_version: ''\n"
)


def _stamped_project(tmp_path: Path, version: str) -> Path:
    """A project carrying its own ``.kittify/metadata.yaml`` stamp."""
    project = tmp_path / "project"
    (project / ".kittify").mkdir(parents=True)
    (project / "kitty-specs").mkdir()
    (project / ".kittify" / "metadata.yaml").write_text(_METADATA_YAML.format(version=version), encoding="utf-8")
    return project


@pytest.mark.usefixtures("canonical_home")  # R1b (#3121): the canonical owner pins SPEC_KITTY_HOME=tmp_path/home
def test_uses_centralized_runtime_reads_the_project_stamp_not_the_home(
    tmp_path: Path,
) -> None:
    """#6551: a 4.x project is centralized even when the home has never been bootstrapped.

    ``canonical_home`` creates ``tmp_path/home`` and sets ``SPEC_KITTY_HOME`` to
    it, so the directory exists but carries no ``cache/version.lock`` — exactly a
    machine whose first spec-kitty command is ``upgrade``. All three assertions
    live in one test so a future re-widening of the predicate fails in one place.
    """
    from specify_cli.upgrade.migrations.m_0_12_0_documentation_mission import InstallDocumentationMission
    from specify_cli.upgrade.migrations.m_0_6_7_ensure_missions import EnsureMissionsMigration

    project = _stamped_project(tmp_path, "4.0.0rc8")

    # Assumption check: this home is not bootstrapped.
    assert not (tmp_path / "home" / "cache" / "version.lock").exists()

    assert uses_centralized_runtime(project) is True
    assert EnsureMissionsMigration().detect(project) is False
    assert InstallDocumentationMission().detect(project) is False


@pytest.mark.usefixtures("canonical_home")  # R1b (#3121): the canonical owner pins SPEC_KITTY_HOME=tmp_path/home
def test_uses_centralized_runtime_still_repairs_a_pre_two_x_project(
    tmp_path: Path,
) -> None:
    """Positive control for the test above: a 1.x stamp is *not* centralized.

    Same fixture shape, pre-2.0 stamp: the answer must stay ``False`` so the
    legacy mission migration still runs. Without this, "4.x is skipped" could be
    satisfied by a predicate that simply always says yes.
    """
    from specify_cli.upgrade.migrations.m_0_6_7_ensure_missions import EnsureMissionsMigration

    home = tmp_path / "home"
    (home / "cache").mkdir(parents=True, exist_ok=True)
    (home / "cache" / "version.lock").write_text("2.0.6", encoding="utf-8")

    project = _stamped_project(tmp_path, "1.2.0")

    assert uses_centralized_runtime(project) is False
    assert EnsureMissionsMigration().detect(project) is True


@pytest.mark.usefixtures("canonical_home")  # R1b (#3121): the canonical owner pins SPEC_KITTY_HOME=tmp_path/home
def test_uses_centralized_runtime_keeps_pre_two_x_answer_without_a_bootstrapped_home(
    tmp_path: Path,
) -> None:
    """A pre-2.0 stamp under an unbootstrapped home stays legacy.

    "No home" must not be read as "modern": a project we can date as 1.x is still
    legacy whichever machine runs the upgrade.
    """
    project = _stamped_project(tmp_path, "1.2.0")

    assert not (tmp_path / "home" / "cache" / "version.lock").exists()
    assert uses_centralized_runtime(project) is False


@pytest.mark.usefixtures("canonical_home")  # R1b (#3121): the canonical owner pins SPEC_KITTY_HOME=tmp_path/home
def test_uses_centralized_runtime_fails_closed_on_a_non_string_stamp(
    tmp_path: Path,
) -> None:
    """An unquoted numeric stamp must not raise now that it is read unbootstrapped.

    ``version: 2.0`` is valid YAML and loads as a float, so ``Version(2.0)``
    raises ``TypeError`` rather than ``InvalidVersion``. Reading the stamp before
    the home check puts that shape on a path it could not reach before (#6551),
    so it has to fail closed like any other undatable project.
    """
    project = _stamped_project(tmp_path, "2.0")
    # Write the stamp unquoted, which is what a hand-edited metadata.yaml holds.
    (project / ".kittify" / "metadata.yaml").write_text(
        "spec_kitty:\n  version: 2.0\n  initialized_at: '2026-01-01T00:00:00'\n",
        encoding="utf-8",
    )
    assert "version: 2.0\n" in (project / ".kittify" / "metadata.yaml").read_text(encoding="utf-8")

    assert not (tmp_path / "home" / "cache" / "version.lock").exists()
    assert uses_centralized_runtime(project) is False
