"""Scope: init non interactive unit tests — no real git or subprocesses."""

from __future__ import annotations

import sys

import pytest

from specify_cli.cli.commands import init as init_module
from specify_cli.core.env import is_truthy

pytestmark = pytest.mark.fast


def test_is_truthy_env():
    """Truthy strings return True; falsy/empty/None return False."""
    # Arrange
    truthy = ["1", "true", "YES", "on", "y"]
    falsy = ["0", "false", "", None]
    # Assumption check
    assert len(truthy) == 5
    # Act / Assert
    for val in truthy:
        assert is_truthy(val) is True
    for val in falsy:
        assert is_truthy(val) is False


def test_non_interactive_env_override(monkeypatch: pytest.MonkeyPatch):
    """Env var SPEC_KITTY_NON_INTERACTIVE=1 forces non-interactive mode."""
    # Arrange
    monkeypatch.setenv("SPEC_KITTY_NON_INTERACTIVE", "1")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    # Assumption check
    assert is_truthy("1") is True
    # Act
    result = init_module._is_non_interactive_mode(False)
    # Assert
    assert result is True


def test_non_interactive_non_tty(monkeypatch: pytest.MonkeyPatch):
    """Non-TTY stdin forces non-interactive mode regardless of env var."""
    # Arrange
    monkeypatch.delenv("SPEC_KITTY_NON_INTERACTIVE", raising=False)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    # Assumption check
    assert is_truthy(None) is False
    # Act
    result = init_module._is_non_interactive_mode(False)
    # Assert
    assert result is True


def test_force_interactive_overrides_non_interactive_env(monkeypatch: pytest.MonkeyPatch):
    """#2912: SPEC_KITTY_FORCE_INTERACTIVE now reaches init (the old local matrix
    omitted the escape hatch), overriding NON_INTERACTIVE and a non-TTY stdin."""
    # Arrange
    monkeypatch.setenv("SPEC_KITTY_FORCE_INTERACTIVE", "1")
    monkeypatch.setenv("SPEC_KITTY_NON_INTERACTIVE", "1")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    # Act
    result = init_module._is_non_interactive_mode(False)
    # Assert
    assert result is False


def test_explicit_flag_forces_non_interactive_even_with_force_interactive(
    monkeypatch: pytest.MonkeyPatch,
):
    """The explicit ``--non-interactive`` flag wins over the env escape hatch."""
    # Arrange
    monkeypatch.setenv("SPEC_KITTY_FORCE_INTERACTIVE", "1")
    # Act
    result = init_module._is_non_interactive_mode(True)
    # Assert
    assert result is True


# _resolve_preferred_agents() was removed in feature 076-init-command-overhaul.
# The preferred-implementer / preferred-reviewer system was deleted entirely.
