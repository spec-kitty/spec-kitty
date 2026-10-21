"""Single-source authority tests for the skill-only agent roster (#1941).

The skill-only roster (``codex``, ``vibe``, ``pi``, ``letta``) used to be
duplicated as three byte-identical literals. WP03 collapsed them onto the leaf
module :mod:`specify_cli.skills._agent_roster`. These tests prove the collapse
is a *derivation*, not a coincidental equal literal:

* an identity/equality check that the installer and renderer rosters resolve to
  the leaf authority, and
* a monkeypatch-derivation test that patches the leaf and reloads the dependent
  modules, asserting the change propagates to
  ``config.SKILL_ONLY_AGENTS``/``VALID_AGENTS`` and
  ``command_renderer.SUPPORTED_AGENTS``. A coincidental equal literal would NOT
  reflect the patched value and would fail this test.
"""

from __future__ import annotations

import importlib

import pytest

from specify_cli.skills import _agent_roster, command_installer, command_renderer
from specify_cli.cli.commands.agent import config as agent_config
from specify_cli.upgrade.migrations.m_0_9_1_complete_lane_migration import (
    AGENT_DIR_TO_KEY,
)

pytestmark = pytest.mark.fast


def test_leaf_roster_is_the_expected_tuple() -> None:
    """The leaf authority pins the canonical, ordered roster."""
    assert _agent_roster.SUPPORTED_AGENTS == ("codex", "vibe", "pi", "letta", "antigravity")


def test_installer_roster_is_the_leaf_authority() -> None:
    """``command_installer.SUPPORTED_AGENTS`` IS the leaf object (no copy)."""
    assert command_installer.SUPPORTED_AGENTS is _agent_roster.SUPPORTED_AGENTS


def test_renderer_roster_is_the_leaf_authority() -> None:
    """``command_renderer.SUPPORTED_AGENTS`` IS the leaf object (no copy)."""
    assert command_renderer.SUPPORTED_AGENTS is _agent_roster.SUPPORTED_AGENTS


def test_config_skill_only_agents_derive_from_leaf() -> None:
    """``config.SKILL_ONLY_AGENTS`` equals the leaf roster as a set."""
    assert set(_agent_roster.SUPPORTED_AGENTS) == agent_config.SKILL_ONLY_AGENTS


def test_valid_agents_is_the_derived_union() -> None:
    """``VALID_AGENTS`` is exactly the dir-keys union the leaf roster."""
    assert set(AGENT_DIR_TO_KEY.values()) | set(
        _agent_roster.SUPPORTED_AGENTS
    ) == agent_config.VALID_AGENTS


def test_monkeypatch_derivation_propagates_into_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Patch the leaf, reload ``config``, assert the change flows through.

    This is the anti-coincidence guard for ``config.py``: if it still carried
    its own ``{"codex", ...}`` literal, the reloaded module would NOT reflect
    the patched roster and this test would fail. (Installer and renderer share
    the *same object* as the leaf — proved by the ``is``-identity tests above,
    which a coincidental equal literal can never satisfy. ``config`` derives a
    new ``set`` each import, so it needs the reload to re-evaluate.)

    Only ``config`` is reloaded: reloading ``command_renderer`` /
    ``command_installer`` would rebind their exception/dataclass *types*, which
    other already-imported modules catch via ``except``/``isinstance`` — an
    identity hazard unrelated to the roster. The leaf-identity tests cover them.
    """
    sentinel = ("codex", "vibe", "pi", "letta", "sentinel-tool")
    monkeypatch.setattr(_agent_roster, "SUPPORTED_AGENTS", sentinel)

    try:
        reloaded_config = importlib.reload(agent_config)

        # Derivation, not coincidence: config reflects the patched roster.
        assert set(sentinel) == reloaded_config.SKILL_ONLY_AGENTS
        assert "sentinel-tool" in reloaded_config.VALID_AGENTS
    finally:
        # Restore the real roster and reload config off it so no later test
        # observes the sentinel value.
        monkeypatch.undo()
        importlib.reload(agent_config)
