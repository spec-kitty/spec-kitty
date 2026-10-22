"""Unit tests for UpgradeHint and build_upgrade_hint (T013 — hint catalog coverage).

Every InstallMethod value must yield a valid hint satisfying the invariant
(exactly one of command / note is non-None).  Security properties are tested
by attempting to construct an UpgradeHint with a disallowed command string.
"""

from __future__ import annotations

import pytest

from kernel.site_urls import INSTALL_AND_UPGRADE_URL
from specify_cli.compat._detect.install_method import InstallMethod
from specify_cli.compat.provider import NoNetworkProvider
from specify_cli.compat.upgrade_hint import UpgradeHint, build_upgrade_hint
from specify_cli.distribution.profile import DegradedDistributionProfile


# ---------------------------------------------------------------------------
# Invariant: exactly one of command / note is non-None
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]

class TestInvariant:
    @pytest.mark.parametrize("method", list(InstallMethod))
    def test_every_method_produces_valid_hint(self, method: InstallMethod) -> None:
        """build_upgrade_hint must return a hint satisfying the invariant."""
        hint = build_upgrade_hint(method)
        assert hint.install_method == method
        # Exactly one of command/note is non-None.
        assert (hint.command is None) != (hint.note is None), (
            f"{method}: expected exactly one of command/note to be set; command={hint.command!r}, note={hint.note!r}"
        )

    @pytest.mark.parametrize("method", list(InstallMethod))
    def test_hint_is_frozen(self, method: InstallMethod) -> None:
        """UpgradeHint is frozen — mutation must raise."""
        hint = build_upgrade_hint(method)
        with pytest.raises((AttributeError, TypeError)):
            hint.command = "new value"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Command-bearing hints (PIPX, PIP_USER, PIP_SYSTEM, BREW)
# ---------------------------------------------------------------------------


class TestCommandHints:
    @pytest.mark.parametrize(
        "method,expected_fragment",
        [
            (InstallMethod.PIPX, "pipx upgrade"),
            (InstallMethod.UV_TOOL, "uv tool install --force"),
            (InstallMethod.PIP_USER, "pip install --user --upgrade"),
            (InstallMethod.PIP_SYSTEM, "pip install --upgrade"),
            (InstallMethod.BREW, "brew upgrade"),
        ],
    )
    def test_command_contains_expected_fragment(self, method: InstallMethod, expected_fragment: str) -> None:
        hint = build_upgrade_hint(method)
        assert hint.command is not None
        assert expected_fragment in hint.command
        assert hint.note is None

    @pytest.mark.parametrize(
        "method",
        [
            InstallMethod.PIPX,
            InstallMethod.UV_TOOL,
            InstallMethod.PIP_USER,
            InstallMethod.PIP_SYSTEM,
            InstallMethod.BREW,
        ],
    )
    def test_command_does_not_contain_ansi(self, method: InstallMethod) -> None:
        hint = build_upgrade_hint(method)
        assert hint.command is not None
        assert "\x1b" not in hint.command
        assert "\033" not in hint.command


def test_degraded_profile_suppresses_remediation_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = DegradedDistributionProfile(
        package_name="",
        upgrade_provider=NoNetworkProvider(),
        disable_public_pypi_notifier=True,
    )
    monkeypatch.setattr(
        "specify_cli.distribution.resolve_distribution_profile",
        lambda: profile,
    )

    hint = build_upgrade_hint(InstallMethod.UV_TOOL)

    assert hint.command is None
    assert hint.note is not None
    assert "distribution profile" in hint.note


# ---------------------------------------------------------------------------
# Note-only hints (SOURCE, SYSTEM_PACKAGE, UNKNOWN)
# ---------------------------------------------------------------------------


class TestNoteHints:
    @pytest.mark.parametrize(
        "method",
        [InstallMethod.SOURCE, InstallMethod.SYSTEM_PACKAGE, InstallMethod.UNKNOWN],
    )
    def test_note_hints_have_no_command(self, method: InstallMethod) -> None:
        """SOURCE, SYSTEM_PACKAGE, UNKNOWN MUST NOT carry a runnable command (CHK031)."""
        hint = build_upgrade_hint(method)
        assert hint.command is None, f"{method}: command must be None for security (CHK031); got {hint.command!r}"
        assert hint.note is not None
        assert len(hint.note) > 0

    def test_unknown_note_mentions_docs_or_upgrade(self) -> None:
        hint = build_upgrade_hint(InstallMethod.UNKNOWN)
        # The note should be informative, not a bare runnable command.
        assert hint.command is None
        assert "install" in hint.note.lower() or "upgrade" in hint.note.lower()

    def test_source_note_mentions_source_or_workflow(self) -> None:
        hint = build_upgrade_hint(InstallMethod.SOURCE)
        assert hint.command is None
        text = hint.note.lower()
        assert "source" in text or "dev" in text or "pip install" in text


# ---------------------------------------------------------------------------
# Security: disallowed characters in command field
# ---------------------------------------------------------------------------


class TestCommandSanitisation:
    @pytest.mark.parametrize(
        "bad_command",
        [
            "\x1b[31mevil\x1b[0m",  # ANSI escape sequence
            "$(whoami)",  # shell subshell injection
            "cmd; other",  # semicolon (shell separator)
            "cmd && other",  # && (shell AND) — & not in allowed set
            "cmd | cat",  # pipe — | not in allowed set
            "a" * 513,  # too long (>COMMAND_ALLOWLIST_MAX_LEN = 512 chars)
            "",  # empty string
            "cmd\nnewline",  # embedded newline
            "cmd\ttab",  # embedded tab
            "cmd `backtick`",  # backtick — ` not in allowed set
            "cmd#comment",  # hash — # not in allowed set
        ],
    )
    def test_disallowed_command_raises_value_error(self, bad_command: str) -> None:
        """Constructing an UpgradeHint with a disallowed command must raise ValueError."""
        with pytest.raises(ValueError, match="disallowed"):
            UpgradeHint(
                install_method=InstallMethod.PIPX,
                command=bad_command,
                note=None,
            )

    def test_allowed_command_passes(self) -> None:
        hint = UpgradeHint(
            install_method=InstallMethod.PIPX,
            command="pipx upgrade spec-kitty-cli",
            note=None,
        )
        assert hint.command == "pipx upgrade spec-kitty-cli"

    def test_none_command_with_note_passes(self) -> None:
        hint = UpgradeHint(
            install_method=InstallMethod.UNKNOWN,
            command=None,
            note="Some manual instructions.",
        )
        assert hint.note == "Some manual instructions."
        assert hint.command is None


# ---------------------------------------------------------------------------
# Invariant enforcement at construction time
# ---------------------------------------------------------------------------


class TestInvariantEnforcement:
    def test_both_command_and_note_raises(self) -> None:
        with pytest.raises(ValueError):
            UpgradeHint(
                install_method=InstallMethod.PIPX,
                command="pipx upgrade spec-kitty-cli",
                note="Some note",
            )

    def test_neither_command_nor_note_raises(self) -> None:
        with pytest.raises(ValueError):
            UpgradeHint(
                install_method=InstallMethod.PIPX,
                command=None,
                note=None,
            )


# ---------------------------------------------------------------------------
# build_upgrade_hint with package argument (reserved path)
# ---------------------------------------------------------------------------


class TestBuildUpgradeHintPackageArg:
    def test_package_arg_is_accepted_without_error(self) -> None:
        """The *package* kwarg is accepted (reserved for future use)."""
        hint = build_upgrade_hint(InstallMethod.PIPX, package="spec-kitty-cli")
        assert hint.install_method == InstallMethod.PIPX

    def test_uv_tool_target_version_overrides_receipt_pin(self) -> None:
        hint = build_upgrade_hint(InstallMethod.UV_TOOL, target_version="3.2.2")
        assert hint.command == "uv tool install --force spec-kitty-cli==3.2.2"

    def test_uv_tool_invalid_target_version_falls_back_to_unpinned(self) -> None:
        hint = build_upgrade_hint(InstallMethod.UV_TOOL, target_version="3.2.2;rm")
        assert hint.command == "uv tool install --force spec-kitty-cli"


# ---------------------------------------------------------------------------
# FIX 4 — SOURCE note must not blank in render_human (P3)
# ---------------------------------------------------------------------------


class TestSourceHintRendersWithoutUnavailable:
    """FIX 4: SOURCE note must not contain parentheses that trip _safe() regex.

    messages._safe() applies ^[A-Za-z0-9.\\-+_ /:]{1,256}$ to all interpolated
    values; parentheses are excluded.  The old SOURCE note contained '(' and ')'
    so render_human produced 'Upgrade the CLI: <unavailable>'.  After FIX 4 the
    note must pass the regex and render verbatim.
    """

    def test_source_note_has_no_parentheses(self) -> None:
        """After FIX 4 the SOURCE note must not contain ( or ) characters."""
        hint = build_upgrade_hint(InstallMethod.SOURCE)
        assert hint.note is not None
        assert "(" not in hint.note, (
            f"SOURCE note still contains '(': {hint.note!r}. "
            "Parentheses cause render_human to substitute <unavailable>."
        )
        assert ")" not in hint.note, (
            f"SOURCE note still contains ')': {hint.note!r}."
        )

    def test_source_hint_renders_without_unavailable(self) -> None:
        """render_human for PROJECT_TOO_NEW_FOR_CLI + SOURCE install must not produce <unavailable>."""
        from kernel.clock import UTC, datetime
        from pathlib import Path

        from specify_cli.compat.messages import render_human
        from specify_cli.compat.planner import (
            CliStatus,
            Decision,
            Fr023Case,
            Plan,
            ProjectState,
            ProjectStatus,
        )
        from specify_cli.compat.safety import Safety

        _now = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
        hint = build_upgrade_hint(InstallMethod.SOURCE)
        cli_status = CliStatus(
            installed_version="2.0.11",
            latest_version="2.0.14",
            latest_source="pypi",
            is_outdated=True,
            fetched_at=_now,
        )
        project_status = ProjectStatus(
            state=ProjectState.TOO_NEW,
            project_root=Path("/nonexistent/testproj"),
            schema_version=9,
            min_supported=3,
            max_supported=3,
            metadata_error=None,
        )
        plan = Plan(
            decision=Decision.BLOCK_CLI_UPGRADE,
            cli_status=cli_status,
            project_status=project_status,
            safety=Safety.UNSAFE,
            pending_migrations=(),
            install_method=InstallMethod.SOURCE,
            upgrade_hint=hint,
            fr023_case=Fr023Case.PROJECT_TOO_NEW_FOR_CLI,
            exit_code=5,
            rendered_human="",
            rendered_json={},
        )
        rendered = render_human(plan)
        assert "<unavailable>" not in rendered, (
            f"render_human produced '<unavailable>' for SOURCE hint: {rendered!r}. "
            "The SOURCE note must not contain characters excluded by the _safe() regex."
        )
        assert rendered.strip() != "", "render_human returned empty string for SOURCE hint."


def test_unknown_install_hint_links_the_install_guide() -> None:
    note = build_upgrade_hint(InstallMethod.UNKNOWN).note
    assert note is not None
    assert INSTALL_AND_UPGRADE_URL in note
