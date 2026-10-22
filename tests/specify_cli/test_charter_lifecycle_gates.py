"""Lifecycle gate tests for charter activation checks (WP10 / FR-017, FR-018).

Tests verify that:
- ``finalize-tasks`` hard-fails when a WP's agent_profile is not activated (FR-017)
- ``agent action implement`` hard-fails before worktree creation when the WP's
  agent_profile is not activated (FR-018 / C-006)
- Both gates silently skip when ``activated_agent_profiles`` is None (backward-compat)
- Error messages include the exact resolution command
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator, Set as AbstractSet
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from charter.activation.exceptions import CharterActivationError
from charter.activation.pack_context import PackContext
from charter.drg import ArtifactKind
from specify_cli.cli.commands.agent.mission import app as mission_app
from specify_cli.cli.commands.agent.workflow import app as workflow_app

pytestmark = pytest.mark.fast

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

runner = CliRunner()


def _make_pack_context(
    *,
    activated_agent_profiles: frozenset[str] | None,
) -> PackContext:
    """Build a real PackContext with the given activated_agent_profiles.

    A real instance, not a mock: the gates ask ``admits()`` / ``allow_for()``,
    and a MagicMock answers ``admits()`` with a truthy mock, so the gate would
    never fire (#6581).
    """
    return PackContext(
        activated_kinds=frozenset(),
        activated_mission_types=frozenset(),
        pack_roots=(),
        org_pack_names=(),
        repo_root=Path(),
        activated_agent_profiles=activated_agent_profiles,
    )


def _make_project_context(
    *,
    activated_agent_profiles: frozenset[str] | None,
) -> MagicMock:
    """Build a mock ProjectContext whose require_pack_context() returns a PackContext."""
    proj_ctx = MagicMock()
    proj_ctx.require_pack_context.return_value = _make_pack_context(
        activated_agent_profiles=activated_agent_profiles
    )
    return proj_ctx


@contextlib.contextmanager
def _record_profile_verdicts() -> Iterator[list[tuple[str, bool]]]:
    """Record every agent-profile ``PackContext.admits`` verdict.

    A let-through test asserts the gate ran and admitted the profile, so it
    cannot pass merely because the command failed earlier for another reason.
    """
    verdicts: list[tuple[str, bool]] = []
    real_admits = PackContext.admits

    def _spy(self: PackContext, kind: ArtifactKind, token: str, *, available: AbstractSet[str]) -> bool:
        admitted: bool = real_admits(self, kind, token, available=available)
        if kind is ArtifactKind.AGENT_PROFILE:
            verdicts.append((token, admitted))
        return admitted

    with patch.object(PackContext, "admits", _spy):
        yield verdicts


def _make_implement_wp(tmp_path: Path, agent_profile: str) -> MagicMock:
    """Build a WorkPackage stand-in whose ``path`` is a real WP file.

    ``frontmatter`` feeds the charter precondition; ``path`` points at a file
    with the same frontmatter, so a step that reads the WP from disk sees real
    content instead of ``MagicMock().path`` (#6581).
    """
    frontmatter = f"work_package_id: WP01\nagent_profile: {agent_profile}\ntitle: Test WP\n"
    wp_file = tmp_path / "kitty-specs" / "099-test" / "tasks" / "WP01-test.md"
    wp_file.parent.mkdir(parents=True, exist_ok=True)
    wp_file.write_text(f"---\n{frontmatter}---\n\n# WP01\n", encoding="utf-8")
    wp = MagicMock()
    wp.frontmatter = frontmatter
    wp.path = wp_file
    return wp


def _build_finalize_tasks_feature(
    tmp_path: Path,
    *,
    agent_profile: str | None = None,
) -> tuple[Path, Path]:
    """Create a minimal feature directory for finalize-tasks tests.

    Returns (feature_dir, tasks_dir).
    """
    feature_dir = tmp_path / "kitty-specs" / "099-test"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    (feature_dir / "meta.json").write_text('{"target_branch": "main"}\n', encoding="utf-8")
    (feature_dir / "spec.md").write_text(
        "# Spec\n"
        "## Functional Requirements\n"
        "| ID | Requirement | Acceptance Criteria | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| FR-001 | Test requirement | Covered by WP01. | proposed |\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "## Work Package WP01\n**Requirement Refs**: FR-001\n",
        encoding="utf-8",
    )

    profile_line = f"agent_profile: {agent_profile}\n" if agent_profile else ""
    (tasks_dir / "WP01-test.md").write_text(
        f"---\n"
        f"work_package_id: WP01\n"
        f"{profile_line}"
        f"execution_mode: code_change\n"
        f"owned_files:\n  - src/module_a/\n"
        f"authoritative_surface: src/module_a/\n"
        f"---\n\n# WP01\n",
        encoding="utf-8",
    )
    return feature_dir, tasks_dir


@contextlib.contextmanager
def _finalize_tasks_context(
    tmp_path: Path,
    feature_dir: Path,
    mock_proj_ctx: MagicMock,
) -> Iterator[None]:
    """Context manager that patches all infrastructure for finalize-tasks tests."""
    with (
        patch(
            "specify_cli.cli.commands.agent.mission.locate_project_root",
            return_value=tmp_path,
        ),
        patch(
            "specify_cli.cli.commands.agent.mission._find_feature_directory",
            return_value=feature_dir,
        ),
        patch(
            "specify_cli.cli.commands.agent.mission._show_branch_context",
            return_value=(None, "main"),
        ),
        # WP05 (T014): the ``mission.safe_commit`` re-export shim is gone; suppress
        # git I/O at the canonical commit boundary (``commit_for_mission``) instead.
        patch(
            "specify_cli.coordination.commit_router.commit_for_mission",
            return_value=True,
        ),
        patch(
            "specify_cli.cli.commands.agent.mission.run_command",
            return_value=(0, "", ""),
        ),
        patch(
            "charter.activation.invocation_context.ProjectContext.from_repo",
            return_value=mock_proj_ctx,
        ),
    ):
        yield


@contextlib.contextmanager
def _implement_context(
    tmp_path: Path,
    mock_wp: object,
    mock_proj_ctx: MagicMock,
) -> Iterator[None]:
    """Context manager that patches all infrastructure for implement gate tests."""
    with (
        patch(
            "specify_cli.cli.commands.agent.workflow.locate_project_root",
            return_value=tmp_path,
        ),
        patch(
            "specify_cli.cli.commands.agent.workflow._find_mission_slug",
            return_value="099-test",
        ),
        patch(
            "specify_cli.cli.commands.agent.workflow.get_main_repo_root",
            return_value=tmp_path,
        ),
        patch(
            "specify_cli.git.sparse_checkout.require_no_sparse_checkout",
        ),
        patch(
            "specify_cli.cli.commands.agent.workflow._ensure_target_branch_checked_out",
            return_value=(tmp_path, "main"),
        ),
        patch(
            "specify_cli.cli.commands.agent.workflow.locate_work_package",
            return_value=mock_wp,
        ),
        patch(
            "charter.activation.invocation_context.ProjectContext.from_repo",
            return_value=mock_proj_ctx,
        ),
    ):
        yield


# ---------------------------------------------------------------------------
# Test 1 — finalize-tasks hard-fails when profile not activated (FR-017)
# ---------------------------------------------------------------------------


class TestFinalizatTasksProfileGate:
    """FR-017: finalize-tasks exits 1 when WP agent_profile is not activated."""

    def test_hard_fails_when_profile_not_activated(
        self,
        tmp_path: Path,
    ) -> None:
        """finalize-tasks exits 1 when WP agent_profile is not in activated set."""
        # Arrange: WP with researcher-robbie profile (not in activated set)
        feature_dir, _ = _build_finalize_tasks_feature(
            tmp_path,
            agent_profile="researcher-robbie",
        )
        mock_proj_ctx = _make_project_context(
            activated_agent_profiles=frozenset({"python-pedro", "reviewer-renata"})
        )

        with _finalize_tasks_context(tmp_path, feature_dir, mock_proj_ctx):
            result = runner.invoke(mission_app, ["finalize-tasks", "--mission", "099-test"])

        # Assert: exits non-zero
        assert result.exit_code != 0, (
            f"Expected exit code != 0, got: {result.exit_code}\n{result.stdout}"
        )
        # Assert: the gate refused, naming the profile
        assert "Charter activation gate FAILED" in result.stdout
        assert "researcher-robbie" in result.stdout

    def test_passes_when_profile_is_activated(
        self,
        tmp_path: Path,
    ) -> None:
        """finalize-tasks does not fail when WP agent_profile IS in activated set."""
        # Arrange: WP with researcher-robbie profile (IN activated set this time)
        feature_dir, _ = _build_finalize_tasks_feature(
            tmp_path,
            agent_profile="researcher-robbie",
        )
        mock_proj_ctx = _make_project_context(
            activated_agent_profiles=frozenset({"python-pedro", "researcher-robbie"})
        )

        with _finalize_tasks_context(tmp_path, feature_dir, mock_proj_ctx), _record_profile_verdicts() as verdicts:
            result = runner.invoke(mission_app, ["finalize-tasks", "--mission", "099-test"])

        # The gate ran and admitted the profile; the command may still fail
        # later for other reasons, but not at the charter gate.
        assert ("researcher-robbie", True) in verdicts
        assert "Charter activation gate FAILED" not in result.stdout

    def test_skips_check_when_activated_profiles_is_none(
        self,
        tmp_path: Path,
    ) -> None:
        """finalize-tasks skips the gate when activated_agent_profiles is None."""
        # Arrange: WP with a profile, but config has no activated_agent_profiles key
        feature_dir, _ = _build_finalize_tasks_feature(
            tmp_path,
            agent_profile="researcher-robbie",
        )
        mock_proj_ctx = _make_project_context(
            activated_agent_profiles=None  # None means no restriction
        )

        with _finalize_tasks_context(tmp_path, feature_dir, mock_proj_ctx), _record_profile_verdicts() as verdicts:
            result = runner.invoke(mission_app, ["finalize-tasks", "--mission", "099-test"])

        # The gate ran and admitted the profile
        assert ("researcher-robbie", True) in verdicts
        assert "Charter activation gate FAILED" not in result.stdout


# ---------------------------------------------------------------------------
# Test 4 — implement hard-fails when profile not activated (FR-018 / C-006)
# ---------------------------------------------------------------------------


class TestImplementProfileGate:
    """FR-018 / C-006: agent action implement exits 1 before worktree creation."""

    def test_hard_fails_when_profile_not_activated(
        self,
        tmp_path: Path,
    ) -> None:
        """agent action implement exits 1 when WP profile not in activated set."""
        mock_wp = _make_implement_wp(tmp_path, "researcher-robbie")
        mock_proj_ctx = _make_project_context(
            activated_agent_profiles=frozenset({"python-pedro", "reviewer-renata"})
        )

        with _implement_context(tmp_path, mock_wp, mock_proj_ctx):
            result = runner.invoke(
                workflow_app,
                ["implement", "WP01", "--agent", "claude", "--mission", "099-test"],
            )

        # Assert: exits non-zero
        assert result.exit_code != 0, (
            f"Expected exit code != 0, got: {result.exit_code}\n{result.stdout}"
        )
        assert "charter precondition FAILED" in result.stdout
        # Assert: no worktree created
        assert not (tmp_path / ".worktrees").exists(), (
            ".worktrees directory must NOT be created when gate fires"
        )

    def test_skips_check_when_no_explicit_activation(
        self,
        tmp_path: Path,
    ) -> None:
        """Backward-compat: implement skips gate when activated_agent_profiles is None."""
        mock_wp = _make_implement_wp(tmp_path, "researcher-robbie")
        mock_proj_ctx = _make_project_context(
            activated_agent_profiles=None  # No restriction
        )

        with _implement_context(tmp_path, mock_wp, mock_proj_ctx), _record_profile_verdicts() as verdicts:
            result = runner.invoke(
                workflow_app,
                ["implement", "WP01", "--agent", "claude", "--mission", "099-test"],
            )

        # The gate ran and admitted the profile
        assert ("researcher-robbie", True) in verdicts
        assert "charter precondition FAILED" not in result.stdout


# ---------------------------------------------------------------------------
# Test 6 — error message contains exact resolution command
# ---------------------------------------------------------------------------


class TestResolutionCommandInErrorMessage:
    """Error message must contain the exact charter activate resolution command."""

    def test_finalize_tasks_error_contains_resolution_command(
        self,
        tmp_path: Path,
    ) -> None:
        """Error message from finalize-tasks contains 'charter activate agent-profile'."""
        feature_dir, _ = _build_finalize_tasks_feature(
            tmp_path,
            agent_profile="researcher-robbie",
        )
        mock_proj_ctx = _make_project_context(
            activated_agent_profiles=frozenset({"python-pedro"})
        )

        with _finalize_tasks_context(tmp_path, feature_dir, mock_proj_ctx):
            result = runner.invoke(mission_app, ["finalize-tasks", "--mission", "099-test"])

        assert result.exit_code != 0
        assert "charter activate agent-profile researcher-robbie" in result.stdout

    def test_implement_error_contains_resolution_command(
        self,
        tmp_path: Path,
    ) -> None:
        """Error message from implement contains 'charter activate agent-profile'."""
        mock_wp = _make_implement_wp(tmp_path, "researcher-robbie")
        mock_proj_ctx = _make_project_context(
            activated_agent_profiles=frozenset({"python-pedro"})
        )

        with _implement_context(tmp_path, mock_wp, mock_proj_ctx):
            result = runner.invoke(
                workflow_app,
                ["implement", "WP01", "--agent", "claude", "--mission", "099-test"],
            )

        assert result.exit_code != 0
        assert "charter activate agent-profile researcher-robbie" in result.stdout


# ---------------------------------------------------------------------------
# Test 7 — CharterActivationError is raised (FR-019)
# ---------------------------------------------------------------------------


class TestCharterActivationErrorRaised:
    """FR-019: CharterActivationError must be raised (not just printed) when the gate fires."""

    def test_finalize_tasks_raises_charter_activation_error(
        self,
        tmp_path: Path,
    ) -> None:
        """finalize-tasks gate raises CharterActivationError for deactivated profile.

        Intercepts CharterActivationError at the module level so the locally-
        imported name inside the gate function resolves to the tracking subclass.
        """
        feature_dir, _ = _build_finalize_tasks_feature(
            tmp_path,
            agent_profile="researcher-robbie",
        )
        mock_proj_ctx = _make_project_context(
            activated_agent_profiles=frozenset({"python-pedro"})
        )

        instances_raised: list[CharterActivationError] = []

        class _TrackingError(CharterActivationError):
            def __init__(self, *args: object, **kwargs: object) -> None:
                super().__init__(*args, **kwargs)
                instances_raised.append(self)

        with (
            _finalize_tasks_context(tmp_path, feature_dir, mock_proj_ctx),
            patch("charter.activation.exceptions.CharterActivationError", _TrackingError),
        ):
            result = runner.invoke(mission_app, ["finalize-tasks", "--mission", "099-test"])

        assert result.exit_code != 0, (
            f"Expected non-zero exit, got {result.exit_code}\n{result.stdout}"
        )
        assert instances_raised, (
            "CharterActivationError was never raised by the finalize-tasks gate; "
            "the gate must raise it (FR-019), not just call typer.Exit(1)"
        )

    def test_implement_raises_charter_activation_error(
        self,
        tmp_path: Path,
    ) -> None:
        """agent action implement gate raises CharterActivationError for deactivated profile."""
        mock_wp = _make_implement_wp(tmp_path, "researcher-robbie")
        mock_proj_ctx = _make_project_context(
            activated_agent_profiles=frozenset({"python-pedro"})
        )

        instances_raised: list[CharterActivationError] = []

        class _TrackingError(CharterActivationError):
            def __init__(self, *args: object, **kwargs: object) -> None:
                super().__init__(*args, **kwargs)
                instances_raised.append(self)

        with (
            _implement_context(tmp_path, mock_wp, mock_proj_ctx),
            patch("charter.activation.exceptions.CharterActivationError", _TrackingError),
        ):
            result = runner.invoke(
                workflow_app,
                ["implement", "WP01", "--agent", "claude", "--mission", "099-test"],
            )

        assert result.exit_code != 0, (
            f"Expected non-zero exit, got {result.exit_code}\n{result.stdout}"
        )
        assert instances_raised, (
            "CharterActivationError was never raised by the implement gate; "
            "the gate must raise it (FR-019), not just call typer.Exit(1)"
        )
