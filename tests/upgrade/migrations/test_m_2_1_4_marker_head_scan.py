"""Tests for the version-marker head-scan helper in m_2_1_4.

These tests pin down the contract that the migration's marker detection
helper recognizes spec-kitty-authored command files using the *new* layout
(YAML frontmatter on line 1, marker on line 4) as well as the legacy
layout (marker on line 1).  Without head scanning, the doctor and the
enforce-state migration would treat newly generated files as stale and
rewrite them on every upgrade.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from tests._support.eacces import deny_path_method

from specify_cli.upgrade.migrations.m_2_1_4_enforce_command_file_state import (
    _VERSION_MARKER_HEAD_LINES,
    _expected_version_marker,
    _file_has_current_version_marker,
)

pytestmark = pytest.mark.fast


@pytest.fixture
def expected_marker() -> str:
    return _expected_version_marker()


def test_recognizes_marker_on_line_one(tmp_path: Path, expected_marker: str) -> None:
    """Legacy layout (marker on line 1) must still be detected."""
    target = tmp_path / "legacy.md"
    target.write_text(f"{expected_marker}\n# body\n", encoding="utf-8")
    assert _file_has_current_version_marker(target) is True


def test_recognizes_marker_after_yaml_frontmatter(tmp_path: Path, expected_marker: str) -> None:
    """New layout (frontmatter on line 1, marker on line 4) must be detected."""
    target = tmp_path / "new_layout.md"
    target.write_text(
        "---\n"
        "description: Demo Command\n"
        "---\n"
        f"{expected_marker}\n"
        "Body.\n",
        encoding="utf-8",
    )
    assert _file_has_current_version_marker(target) is True


def test_rejects_stale_version(tmp_path: Path) -> None:
    """A marker for a *different* version is treated as stale."""
    target = tmp_path / "stale.md"
    target.write_text(
        "---\n"
        "description: Demo Command\n"
        "---\n"
        "<!-- spec-kitty-command-version: 0.0.1-stale -->\n"
        "Body.\n",
        encoding="utf-8",
    )
    assert _file_has_current_version_marker(target) is False


def test_rejects_marker_buried_below_head_window(tmp_path: Path, expected_marker: str) -> None:
    """A marker beyond the head window is intentionally not detected."""
    filler = "\n".join(["filler line"] * (_VERSION_MARKER_HEAD_LINES + 5))
    target = tmp_path / "deep.md"
    target.write_text(f"{filler}\n{expected_marker}\n", encoding="utf-8")
    assert _file_has_current_version_marker(target) is False


def test_rejects_user_authored_file(tmp_path: Path) -> None:
    """No marker anywhere → not generated."""
    target = tmp_path / "user.md"
    target.write_text(
        "---\n"
        "description: A custom user command\n"
        "---\n"
        "Do my custom thing.\n",
        encoding="utf-8",
    )
    assert _file_has_current_version_marker(target) is False


class _FakeCliStatus:
    """Minimal ``_CliStatusLike`` double for exercising the FR-010 injection seam."""

    installed_version = "9.9.9-test"
    latest_version: str | None = None
    latest_source = "none"


def test_expected_marker_routes_injected_cli_status(expected_marker: str) -> None:
    """Injecting a ``_CliStatusLike`` must route its version into the marker (FR-010).

    Proves the injection branch in ``_get_cli_version``/``_expected_version_marker``
    is live: deleting it would fall back to the real ``importlib.metadata`` lookup,
    this assertion would fail, while every other test in this module stays green.
    """
    marker = _expected_version_marker(_FakeCliStatus())
    assert marker == "<!-- spec-kitty-command-version: 9.9.9-test -->"
    assert marker != expected_marker


def test_handles_oserror_gracefully(tmp_path: Path) -> None:
    """A read failure must return False rather than raising."""
    target = tmp_path / "blocked.md"
    target.write_text("doesn't matter\n", encoding="utf-8")

    with patch.object(Path, "read_text", side_effect=OSError("permission denied")):
        assert _file_has_current_version_marker(target) is False


# ---------------------------------------------------------------------------
# T002 — red-first reproduction of #3651
# ---------------------------------------------------------------------------
#
# ``EnforceCommandFileStateMigration.apply()`` writes ALL command files for
# ALL configured agents unconditionally (see the module docstring), which
# means every re-run tries to overwrite files it previously wrote and made
# read-only.  Before T003, the bare ``output_path.write_text(...)`` calls at
# ``m_2_1_4_enforce_command_file_state.py:370,387`` raise ``PermissionError``
# against a pre-existing 0o444 target, which the surrounding
# ``try/except OSError`` swallows into ``errors[]`` and returns
# ``success=False`` — so "no PermissionError propagated" is a false green.
# The correct positive observable is: content was actually rewritten AND
# ``errors`` is empty AND ``success is True``.


def _setup_project_with_config(tmp_path: Path, agents: list[str] | None = None) -> Path:
    """Create a minimal project with ``.kittify/config.yaml``."""
    project = tmp_path / "project"
    project.mkdir()
    kittify = project / ".kittify"
    kittify.mkdir()

    selected_agents = agents if agents is not None else ["claude"]
    config_content = "agents:\n  available:\n"
    for agent in selected_agents:
        config_content += f"  - {agent}\n"
    (kittify / "config.yaml").write_text(config_content, encoding="utf-8")

    return project


def test_apply_rewrites_preexisting_read_only_command_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#3651: re-running the migration over its own read-only output must
    rewrite the file, report zero errors, and report ``success=True``.

    RED pre-fix (T003 not yet applied): the bare ``write_text`` raises
    ``PermissionError``, the ``except OSError`` catches it, ``errors`` gets an
    entry, and ``success`` is ``False`` — this assertion fails.
    GREEN post-fix: the migration routes through ``write_generated_file``,
    which restores the write bit before writing, so the rewrite succeeds.
    """
    from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS
    from specify_cli.upgrade.migrations.m_2_1_4_enforce_command_file_state import (
        EnforceCommandFileStateMigration,
        _compute_output_filename,
    )

    project = _setup_project_with_config(tmp_path, agents=["claude"])
    claude_dir = project / ".claude" / "commands"
    claude_dir.mkdir(parents=True)

    # The real, exact write-site path for the "specify" prompt-driven command.
    filename = _compute_output_filename("specify", "claude")
    output_path = claude_dir / filename
    output_path.write_text(
        "<!-- spec-kitty-command-version: 0.0.1-stale -->\nstale content\n",
        encoding="utf-8",
    )
    output_path.chmod(0o444)
    # Root writes through a 0o444 file, so deny an in-place Path write of it
    # for every uid (#5691). The managed writer's contract is to replace the
    # file, never to rewrite it in place, so the denial does not lift.
    for attr in ("write_text", "write_bytes"):
        deny_path_method(monkeypatch, attr, output_path)

    # Real templates dir with a file for every prompt-driven command so the
    # migration does not warn-and-skip any of them for a missing template.
    templates_dir = tmp_path / "command-templates"
    templates_dir.mkdir()
    for cmd in PROMPT_DRIVEN_COMMANDS:
        (templates_dir / f"{cmd}.md").write_text(
            f"# {cmd} workflow\n" + "Step details.\n" * 20, encoding="utf-8"
        )

    rendered = "<!-- spec-kitty-command-version: 9.9.9-test -->\n# specify\nfresh content\n"

    with (
        patch(
            "specify_cli.upgrade.migrations.m_2_1_4_enforce_command_file_state"
            "._get_runtime_command_templates_dir",
            return_value=templates_dir,
        ),
        patch(
            "specify_cli.upgrade.migrations.m_2_1_4_enforce_command_file_state._render_full_prompt",
            return_value=rendered,
        ),
    ):
        result = EnforceCommandFileStateMigration().apply(project)

    assert result.errors == [], f"expected no errors, got: {result.errors}"
    assert result.success is True
    assert output_path.read_text(encoding="utf-8") == rendered
