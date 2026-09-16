"""Regression parity test: twelve non-migrated agents produce stable output.

Asserts that the command-file renderer produces byte-identical output to the
committed baseline under ``_twelve_agent_baseline/`` for every agent in
``AGENT_COMMAND_CONFIG`` (the twelve agents whose command-delivery mechanism
was not changed by mission 083-agent-skills-codex-vibe).

Codex, Vibe, Pi, and Letta are intentionally excluded — they use the Agent
Skills pipeline (``tests/specify_cli/skills/__snapshots__/`` covers them).

Baseline note
-------------
This baseline was captured post-mission-083 (after WP01–WP06), not from a
pre-mission checkout.  Pre-vs-post byte-identity is infeasible because WP02
edited source templates, changing rendered output for all agents.  The
baseline locks in post-mission state; future unintended drift is caught here.

Regenerating
------------
When a template change is intentional::

    PYTEST_UPDATE_SNAPSHOTS=1 pytest tests/specify_cli/regression/ -v

Commit the updated baseline files alongside the template change.

RESOLVED (was a TODO above this line): the churn this TODO warned about was
observed (primary/merge terminology sweep, mission
primary-merge-vocabulary-01KXP11C T009) and addressed by mission
``twelve-agent-parity-narrowing`` #3447 WP05 (SC-005, see
``CANONICAL_BASELINES`` below): the full 12-agent byte grid was replaced by
exactly two per-render-branch canonical snapshots plus a structural invariant
over every (agent, command) pair, so an intended one-line prompt edit no
longer fans out to ~12-20 baseline-file diffs. Mission
``ci-pipeline-reinstatement-01M1X35E`` WP16 (P2 shape-guard demotion,
FR-014/C-007/NFR-007, #3458) classifies this suite ``behavioral`` — not
``shape-guard`` — in ``tests/architectural/shape_guard_membership.yaml``: it
is a real content/structural check derived from the ``AGENT_COMMAND_CONFIG``
src SSOT, not the low-ROI byte-frozen grid NFR-007 targets, so no further
demotion is needed here.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.core.config import AGENT_COMMAND_CONFIG
from specify_cli.skills.command_installer import PROMPT_BACKED_COMMANDS
from specify_cli.skills.render_versions import FIXTURE_COMMAND_RENDER_VERSION
from specify_cli.template.asset_generator import render_command_template

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# Mission doctrine-consumer-surface-missions-extraction-01KZ6G6H (FR-005)
# relocated mission-steps/ from src/charter/offering/missions/mission-steps to
# packs/built-in/missions/mission-steps.
TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev"

BASELINE_DIR = Path(__file__).parent / "_twelve_agent_baseline"

# Agents covered by this regression suite — all keys in AGENT_COMMAND_CONFIG.
# Command-skill agents are absent: they use the Agent Skills pipeline.
NON_MIGRATED_AGENTS: tuple[str, ...] = tuple(AGENT_COMMAND_CONFIG.keys())

# Canonical prompt-backed command templates to test (one prompt.md source file per command).
#
# ``command_installer.CANONICAL_COMMANDS`` also includes thin CLI-wrapper
# Agent Skills such as ``dashboard``, ``merge``, and ``status``. Those do not
# have software-dev prompt templates and are covered by command-skill tests,
# not by this non-migrated command-file renderer regression.
CANONICAL_COMMANDS: tuple[str, ...] = PROMPT_BACKED_COMMANDS

# Fixed version for rendering (must match what was used when capturing the
# baseline; see _twelve_agent_baseline/__init__.py). Sourced from the shared
# pin so this suite and `spec-kitty regen` can never diverge (#3447, FR-005).
_BASELINE_VERSION = FIXTURE_COMMAND_RENDER_VERSION

# Whether to update baselines instead of asserting.
_UPDATE = os.environ.get("PYTEST_UPDATE_SNAPSHOTS", "0") not in ("", "0", "false", "False")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _baseline_path(agent: str, command: str) -> Path:
    """Return the committed baseline file path for *agent* / *command*."""
    config = AGENT_COMMAND_CONFIG[agent]
    ext = config["ext"]
    return BASELINE_DIR / agent / f"{command}.{ext}"


def _render_for_agent(agent: str, command: str) -> str:
    """Render *command* for *agent* using the production render path.

    Patches ``_get_cli_version`` in the asset generator so the version
    marker in the output is stable across CLI upgrades and matches the
    committed baseline exactly.
    """
    template_path = TEMPLATES_DIR / command / "prompt.md"
    if not template_path.exists():
        pytest.skip(f"Template file missing: {template_path}")

    config = AGENT_COMMAND_CONFIG[agent]
    with patch(
        "specify_cli.template.asset_generator._get_cli_version",
        return_value=_BASELINE_VERSION,
    ):
        return render_command_template(
            template_path=template_path,
            script_type="sh",
            agent_key=agent,
            arg_format=config["arg_format"],
            extension=config["ext"],
        )


# ---------------------------------------------------------------------------
# Parametrized regression test
# ---------------------------------------------------------------------------


# Narrowed gate (#3447 WP05, SC-005): the full 12x12 byte grid is replaced by ONE
# canonical byte snapshot PER DISTINCT RENDER BRANCH + a structural invariant over
# every rendering, so a one-line source-prompt edit regenerates at most one
# canonical fixture per branch instead of ~14. There are exactly two render
# branches (adversarial-review finding): the markdown serialization (claude et al.)
# and the TOML serialization (gemini/qwen, a distinct code path in asset_generator).
# Both are byte-pinned so a TOML-only serialization regression cannot slip through
# as "parseable but wrong".
CANONICAL_BASELINES: tuple[tuple[str, str], ...] = (
    ("claude", "specify"),  # markdown render branch
    ("gemini", "specify"),  # TOML render branch
)


@pytest.mark.parametrize(("agent", "command"), CANONICAL_BASELINES)
def test_canonical_command_snapshot(agent: str, command: str) -> None:
    """Each render branch's canonical rendered command is byte-stable.

    Regenerate with ``spec-kitty regen`` (or ``PYTEST_UPDATE_SNAPSHOTS=1``) when
    an intended template change alters it.
    """
    snap = _baseline_path(agent, command)
    produced = _render_for_agent(agent, command)

    if _UPDATE:
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_text(produced, encoding="utf-8")
        return

    assert snap.exists(), f"Canonical baseline missing at {snap}.\nRun: spec-kitty regen"
    assert produced == snap.read_text(encoding="utf-8"), (
        f"Canonical command render ({agent}/{command}) drifted from its committed "
        "snapshot.\nIf the change is intentional, run: spec-kitty regen"
    )


@pytest.mark.parametrize("agent", NON_MIGRATED_AGENTS)
@pytest.mark.parametrize("command", CANONICAL_COMMANDS)
def test_command_renders_with_expected_structure(agent: str, command: str) -> None:
    """Structural invariant for every (agent, command): a well-formed render.

    Replaces the per-(agent,command) byte grid — it catches a broken render
    (empty output, a missing version marker, an unsubstituted placeholder) for
    every agent without pinning bytes, so an intended source edit does not fan
    out to ~14 fixture diffs.
    """
    produced = _render_for_agent(agent, command)
    assert produced.strip(), f"Empty render for {agent}/{command}"
    assert "spec-kitty-command-version:" in produced, (
        f"Render for {agent}/{command} is missing the version marker"
    )
    # An unsubstituted template placeholder is a real render regression the old
    # byte grid caught (adversarial-review F3); assert none leaked through.
    for placeholder in ("__AGENT__", "{SCRIPT}", "{AGENT_SCRIPT}"):
        assert placeholder not in produced, (
            f"Render for {agent}/{command} leaked an unsubstituted {placeholder}"
        )


def test_structural_gate_rejects_a_broken_render(monkeypatch: pytest.MonkeyPatch) -> None:
    """WP05 T001: the narrowed gate still catches a BROKEN render (empty / no
    version marker / leftover placeholder). Note it does not — and cannot —
    prove a valid-but-wrong render is caught for a non-canonical agent; that
    content-drift coverage is provided by the per-branch canonical snapshots."""
    monkeypatch.setattr(
        "tests.specify_cli.regression.test_twelve_agent_parity.render_command_template",
        lambda **kwargs: "prompt body with no version marker",
    )
    with pytest.raises(AssertionError):
        test_command_renders_with_expected_structure("claude", "specify")


@pytest.mark.parametrize(
    "agent",
    tuple(agent for agent in NON_MIGRATED_AGENTS if AGENT_COMMAND_CONFIG[agent]["ext"] == "toml"),
)
@pytest.mark.parametrize("command", CANONICAL_COMMANDS)
def test_toml_command_output_is_parseable(agent: str, command: str) -> None:
    """Rendered TOML command files must remain valid TOML."""
    produced = _render_for_agent(agent, command)
    try:
        tomllib.loads(produced)
    except tomllib.TOMLDecodeError as exc:
        raise AssertionError(f"Rendered TOML for {agent}/{command} is invalid: {exc}") from exc


# ---------------------------------------------------------------------------
# Structural invariants
# ---------------------------------------------------------------------------


def test_non_migrated_agents_count() -> None:
    """Exactly 13 agents are in AGENT_COMMAND_CONFIG.

    Count rose to 13 when PR #626 registered Kiro as a first-class slash-command
    agent, then fell back to 12 when Mission #136 deprecated Roo (Roo Code shut
    down 2026-05-15, constraint C-007 — see ``specify_cli.core.config``), and rose
    to 13 again when LLxprt Code registered as a TOML slash-command agent.
    Command-skill agents remain absent (they use the Agent Skills pipeline — see
    AGENT_SKILL_CONFIG).
    """
    assert len(NON_MIGRATED_AGENTS) == 13, f"Expected 13 non-migrated agents, got {len(NON_MIGRATED_AGENTS)}: {NON_MIGRATED_AGENTS}"


def test_codex_not_in_agent_command_config() -> None:
    """codex must NOT be in AGENT_COMMAND_CONFIG (migrated to Agent Skills)."""
    assert "codex" not in AGENT_COMMAND_CONFIG, (
        "codex was found in AGENT_COMMAND_CONFIG. Mission 083 migrated codex to the Agent Skills pipeline; it must not appear in the command-file registry."
    )


def test_vibe_not_in_agent_command_config() -> None:
    """vibe must NOT be in AGENT_COMMAND_CONFIG (uses Agent Skills pipeline)."""
    assert "vibe" not in AGENT_COMMAND_CONFIG, "vibe was found in AGENT_COMMAND_CONFIG. Vibe uses the Agent Skills pipeline, not the command-file pipeline."


def test_only_canonical_baseline_is_committed() -> None:
    """Post-narrowing, exactly one canonical command baseline is committed.

    The full 12-agent byte grid was retired (WP05); only the canonical
    ``claude/specify`` fixture remains under version control. A stray extra
    baseline file means a leftover from the old grid or an ungated drift source.
    """
    committed = sorted(
        p.relative_to(BASELINE_DIR).as_posix()
        for p in BASELINE_DIR.rglob("*")
        if p.is_file()
        and p.name != "__init__.py"
        # Python bytecode cache for this package's __init__.py — a local
        # runtime artifact of importing it during collection, never
        # committed (standard-gitignored), not a baseline fixture.
        and "__pycache__" not in p.parts
    )
    assert committed == ["claude/specify.md", "gemini/specify.toml"], (
        f"Expected only the per-branch canonical baselines, found: {committed}"
    )


@pytest.mark.parametrize("agent", NON_MIGRATED_AGENTS)
def test_agent_outputs_contain_arg_placeholder(agent: str) -> None:
    """Non-migrated agents' outputs must preserve the agent's arg placeholder.

    Verifies that $ARGUMENTS or {{args}} is present in at least one rendered
    command for the agent (the skill-renderer transformation must NOT have
    been applied to these agents — that transformation is command-skill only).
    """
    config = AGENT_COMMAND_CONFIG[agent]
    expected_placeholder = config["arg_format"]
    # Render fresh (WP05: the per-agent baseline grid was retired) and verify at
    # least one prompt-backed command carries the agent's arg placeholder.
    found_any = False
    for command in CANONICAL_COMMANDS:
        if expected_placeholder in _render_for_agent(agent, command):
            found_any = True
            break
    assert found_any, (
        f"Agent '{agent}' has arg_format '{expected_placeholder}' "
        f"but no baseline file contains that placeholder. "
        f"This suggests the skill-renderer transformation was incorrectly "
        f"applied to this non-migrated agent."
    )
