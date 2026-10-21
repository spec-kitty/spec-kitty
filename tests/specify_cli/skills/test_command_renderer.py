"""Tests for the command-skill renderer (WP02 — T011; NFR-004 gate — T052).

Snapshot tests cover all canonical command templates × representative agents.
Snapshots are committed under ``tests/specify_cli/skills/__snapshots__/<agent>/``.

Regenerating snapshots
----------------------
When a template changes intentionally, regenerate the snapshots with::

    PYTEST_UPDATE_SNAPSHOTS=1 pytest tests/specify_cli/skills/test_command_renderer.py -v

This writes updated ``<command>.SKILL.md`` files under the ``__snapshots__``
directories.  Commit the changes together with the template change so reviewers
can see the exact before/after diff.

DO NOT regenerate snapshots to silence a test failure without understanding
why the output changed — the snapshots are the regression guard.

TODO (reconsider this test's design if it keeps causing friction):
    These snapshots pin *byte-identical* rendered ``SKILL.md`` output per agent,
    so any legitimate prose edit to a doctrine source template
    (``src/charter/offering/missions/mission-steps/**``) forces regenerating the
    committed ``__snapshots__/<agent>/<command>.SKILL.md`` copies. The snapshot
    asserts byte-identity, not semantic correctness. Paired with the 12-agent
    baseline guard (``tests/specify_cli/regression/test_twelve_agent_parity``),
    a single one-line source change fans out to ~14 fixture files. If this
    regeneration tax becomes a recurring problem (observed during the
    primary/merge terminology sweep, mission primary-merge-vocabulary-01KXP11C),
    reconsider narrowing to structural/contract assertions plus one canonical
    snapshot instead of a full per-agent byte grid.
"""

from __future__ import annotations


import os
import textwrap
from pathlib import Path

import pytest

from specify_cli.skills._user_input_block import REPLACEMENT_BLOCK, identify, rewrite
from specify_cli.skills.command_renderer import (
    SUPPORTED_AGENTS,
    RenderedSkill,
    SkillRenderError,
    ensure_skill_frontmatter,
    render,
)
from specify_cli.skills.render_versions import FIXTURE_SKILL_RENDER_VERSION

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize("change", ["mission", "selector", "agents", "pointer", "unrelated", "wrong-target", "non-mapping", "null"])
def test_mission_provisioning_render_equivalence(tmp_path: Path, change: str) -> None:
    from specify_cli.skills.command_renderer import validate_mission_provisioning

    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    before = b"agents: {available: [codex]}\nactivated_tactics: []\n"
    config.write_bytes(before)
    after = before + b"mission_type_activations: [software-dev]\n"
    target = config.resolve()
    if change == "selector":
        after = after.replace(b"activated_tactics: []", b"activated_tactics: [reasons-canvas-fill]")
    elif change == "agents":
        after = after.replace(b"[codex]", b"[vibe]")
    elif change == "pointer":
        after += b"charter: another.yaml\n"
    elif change == "unrelated":
        after += b"custom: changed\n"
    elif change == "wrong-target":
        target = tmp_path / "foreign.yaml"
    elif change == "non-mapping":
        after = b"- invalid\n"
    elif change == "null":
        before = b"null\n"
        after = b"mission_type_activations: []\n"
    if change in {"mission", "null"}:
        validate_mission_provisioning(tmp_path, before, after, target)
    else:
        with pytest.raises(ValueError):
            validate_mission_provisioning(tmp_path, before, after, target)


# New doctrine layout: packs/built-in/missions/mission-steps/<mission_type>/
# (relocated from src/charter/offering/missions/mission-steps by mission
# doctrine-consumer-surface-missions-extraction-01KZ6G6H, FR-005).
DOCTRINE_MISSION_STEPS_DIR = Path(__file__).parent.parent.parent.parent / "packs" / "built-in" / "missions" / "mission-steps"

# Default mission type used in most tests.
_DEFAULT_MISSION_TYPE = "software-dev"

TEMPLATES_DIR = DOCTRINE_MISSION_STEPS_DIR / _DEFAULT_MISSION_TYPE

# Old command-templates path — must NOT exist after WP02 migration.
_LEGACY_COMMAND_TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "src" / "specify_cli" / "missions" / "software-dev" / "command-templates"

SNAPSHOTS_DIR = Path(__file__).parent / "__snapshots__"

# Fixed version string used for all snapshot renders so the output is stable.
# Sourced from the shared pin so this suite and `spec-kitty regen` can never
# diverge (#3447, FR-005).
_TEST_VERSION = FIXTURE_SKILL_RENDER_VERSION
SNAPSHOT_AGENTS: tuple[str, ...] = ("codex", "vibe")

# Whether to update snapshots instead of asserting against them.
_UPDATE = os.environ.get("PYTEST_UPDATE_SNAPSHOTS", "0") not in ("", "0", "false", "False")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _all_templates() -> list[Path]:
    """Return sorted list of all canonical command prompt.md paths.

    Under the new doctrine layout each step lives in its own sub-directory:
    ``src/charter/offering/missions/mission-steps/<mission_type>/<step_id>/prompt.md``
    """
    return sorted(TEMPLATES_DIR.glob("*/prompt.md"))


def _snapshot_path(agent: str, command: str) -> Path:
    return SNAPSHOTS_DIR / agent / f"{command}.SKILL.md"


def _command_name(template_path: Path) -> str:
    """Derive the command name from a template path.

    New doctrine layout: ``.../mission-steps/<mission_type>/<step_id>/prompt.md``
    → command = step_id (parent directory name).

    Legacy layout: ``.../command-templates/<command>.md``
    → command = file stem.
    """
    return template_path.parent.name if template_path.name == "prompt.md" else template_path.stem


def _render_and_compare(template_path: Path, agent_key: str) -> None:
    """Render *template_path* for *agent_key* and assert or update snapshot."""
    skill = render(template_path, agent_key, _TEST_VERSION)
    output = skill.to_skill_md()
    snap = _snapshot_path(agent_key, _command_name(template_path))

    if _UPDATE:
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_text(output, encoding="utf-8")
        return

    assert snap.exists(), f"Snapshot missing: {snap}\nRun with PYTEST_UPDATE_SNAPSHOTS=1 to generate it."
    expected = snap.read_text(encoding="utf-8")
    assert output == expected, (
        f"Skill output for {template_path.name} ({agent_key}) differs from snapshot.\nIf the change is intentional, run with PYTEST_UPDATE_SNAPSHOTS=1."
    )


# ---------------------------------------------------------------------------
# Parametrised snapshot tests
# ---------------------------------------------------------------------------


# Narrowed gate (#3447 WP05, SC-005): the full codex/vibe x N snapshot grid is
# replaced by ONE canonical snapshot + the structural coverage of
# ``test_deterministic`` and the NFR path tests, so a source-prompt edit
# regenerates at most one snapshot instead of ~2 per command.
_CANONICAL_SKILL_AGENT = "codex"
_CANONICAL_SKILL_COMMAND = "specify"


def test_wp04_rendering_inputs_preserve_pointer_identity(tmp_path: Path) -> None:
    from specify_cli.skills.command_renderer import rendering_inputs
    from tests.upgrade.preview_support.snapshot import snapshot, assert_unchanged

    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    target = tmp_path / "custom-charter.yaml"
    target.write_text("activated_tactics: []\n", encoding="utf-8")
    config.write_text("charter: custom-charter.yaml\nagents:\n  available: [codex]\n", encoding="utf-8")
    before = snapshot({"project": tmp_path})
    assert rendering_inputs(tmp_path) == (config, target)
    assert_unchanged(before, snapshot({"project": tmp_path}))
    target.unlink()
    with pytest.raises(ValueError, match="unreadable"):
        rendering_inputs(tmp_path)


def test_canonical_skill_snapshot() -> None:
    """The canonical (codex/specify) skill render is byte-stable.

    Regenerate with ``spec-kitty regen`` (or ``PYTEST_UPDATE_SNAPSHOTS=1``) when
    an intended template change alters it.
    """
    template = TEMPLATES_DIR / _CANONICAL_SKILL_COMMAND / "prompt.md"
    assert template.exists(), f"canonical template missing: {template}"
    _render_and_compare(template, _CANONICAL_SKILL_AGENT)


def test_only_canonical_snapshot_is_committed() -> None:
    """Post-narrowing, exactly one canonical skill snapshot is committed."""
    committed = sorted(p.relative_to(SNAPSHOTS_DIR).as_posix() for p in SNAPSHOTS_DIR.rglob("*") if p.is_file() and p.name != "__init__.py")
    assert committed == ["codex/specify.SKILL.md"], f"Expected only the canonical codex/specify.SKILL.md snapshot, found: {committed}"


# ---------------------------------------------------------------------------
# Determinism tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("template_path", _all_templates(), ids=_command_name)
@pytest.mark.parametrize("agent_key", SUPPORTED_AGENTS)
def test_deterministic(template_path: Path, agent_key: str) -> None:
    """Rendering the same template twice produces byte-identical output."""
    first = render(template_path, agent_key, _TEST_VERSION).to_skill_md()
    second = render(template_path, agent_key, _TEST_VERSION).to_skill_md()
    assert first == second, f"Non-deterministic output for {template_path.name} ({agent_key})"


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


def test_unsupported_agent(tmp_path: Path) -> None:
    """Passing an unsupported agent key raises SkillRenderError(unsupported_agent)."""
    # Need a real template file — borrow any canonical one.
    tmpl = _all_templates()[0]
    with pytest.raises(SkillRenderError) as exc_info:
        render(tmpl, "claude", _TEST_VERSION)
    assert exc_info.value.code == "unsupported_agent"
    assert exc_info.value.context["agent_key"] == "claude"


def test_render_includes_agent_upgrade_check() -> None:
    skill = render(_all_templates()[0], "codex", _TEST_VERSION)

    assert skill.body.startswith("## Startup Upgrade Check")
    assert "at most once per active agent session" in skill.body
    assert "spec-kitty upgrade --agent-check --json" in skill.body
    assert "spec-kitty upgrade --agent-choice" in skill.body


def test_template_not_found(tmp_path: Path) -> None:
    """Pointing to a non-existent template raises SkillRenderError(template_not_found)."""
    missing = tmp_path / "nonexistent.md"
    with pytest.raises(SkillRenderError) as exc_info:
        render(missing, "codex", _TEST_VERSION)
    assert exc_info.value.code == "template_not_found"


def test_ensure_skill_frontmatter_adds_metadata_for_plain_markdown() -> None:
    content = "# spec-kitty\n\nGet governance context for an action.\n"

    normalized = ensure_skill_frontmatter(content, "spec-kitty")

    assert normalized.startswith("---\n")
    assert "name: spec-kitty\n" in normalized
    assert "description: Get governance context for an action.\n" in normalized
    assert normalized.endswith(content)


def test_ensure_skill_frontmatter_preserves_existing_frontmatter() -> None:
    content = "---\nname: existing\n---\n# Existing\n"

    assert ensure_skill_frontmatter(content, "spec-kitty") == content


def test_user_input_block_missing(tmp_path: Path) -> None:
    """A template without '## User Input' raises SkillRenderError(user_input_block_missing)."""
    template = tmp_path / "no-user-input.md"
    template.write_text(
        "---\ndescription: A test template\n---\n# Test Template\n\n## Purpose\n\nDoes something useful.\n\n## Steps\n\nDo the thing.\n",
        encoding="utf-8",
    )
    with pytest.raises(SkillRenderError) as exc_info:
        render(template, "codex", _TEST_VERSION)
    assert exc_info.value.code == "user_input_block_missing"


def test_stray_arguments_token(tmp_path: Path) -> None:
    """A template with $ARGUMENTS outside the User-Input block raises stray_arguments_token."""
    template = tmp_path / "stray.md"
    template.write_text(
        "---\ndescription: A stray args template\n---\n"
        "## User Input\n\n```text\n$ARGUMENTS\n```\n\n"
        "You **MUST** consider the user input before proceeding (if not empty).\n\n"
        "## Context\n\n"
        "Use $ARGUMENTS to decide what to do.\n",
        encoding="utf-8",
    )
    with pytest.raises(SkillRenderError) as exc_info:
        render(template, "codex", _TEST_VERSION)
    err = exc_info.value
    assert err.code == "stray_arguments_token"
    assert "line" in err.context
    assert "$ARGUMENTS" in err.context["excerpt"]
    # The line number should be 1-indexed and > 1 (it's after the User Input block).
    assert err.context["line"] >= 1


def test_stray_arguments_token_variant(tmp_path: Path) -> None:
    """Stray token check catches variants like $ARGUMENTS.strip() too."""
    template = tmp_path / "variant.md"
    template.write_text(
        "---\ndescription: Variant test\n---\n"
        "## User Input\n\n```text\n$ARGUMENTS\n```\n\n"
        "You **MUST** consider the user input before proceeding (if not empty).\n\n"
        "## Notes\n\n"
        "Process via $ARGUMENTS.strip() if needed.\n",
        encoding="utf-8",
    )
    with pytest.raises(SkillRenderError) as exc_info:
        render(template, "vibe", _TEST_VERSION)
    assert exc_info.value.code == "stray_arguments_token"
    assert "$ARGUMENTS" in exc_info.value.context["excerpt"]


# ---------------------------------------------------------------------------
# Frontmatter stability tests
# ---------------------------------------------------------------------------


def test_frontmatter_key_order(tmp_path: Path) -> None:
    """Frontmatter keys must appear in the exact order: name, description, metadata (spec-only, #6475)."""
    template = tmp_path / "order-test.md"
    template.write_text(
        "---\ndescription: Order test\n---\n"
        "## User Input\n\n```text\n$ARGUMENTS\n```\n\n"
        "You **MUST** consider the user input before proceeding (if not empty).\n\n"
        "## Purpose\n\nA test command.\n",
        encoding="utf-8",
    )
    skill = render(template, "codex", _TEST_VERSION)
    keys = list(skill.frontmatter.keys())
    assert keys == ["name", "description", "metadata"], f"Unexpected frontmatter key order: {keys}"


def test_frontmatter_user_invocable_true(tmp_path: Path) -> None:
    """``user-invocable`` is always the string ``"true"`` under ``metadata`` for every agent (FR-012)."""
    template = tmp_path / "invocable-test.md"
    template.write_text(
        "---\ndescription: Invocable test\n---\n"
        "## User Input\n\n```text\n$ARGUMENTS\n```\n\n"
        "You **MUST** consider the user input before proceeding (if not empty).\n",
        encoding="utf-8",
    )
    for agent in SUPPORTED_AGENTS:
        skill = render(template, agent, _TEST_VERSION)
        assert skill.frontmatter["metadata"] == {"user-invocable": "true"}
        assert "user-invocable" not in skill.frontmatter


def test_frontmatter_no_extra_keys(tmp_path: Path) -> None:
    """Frontmatter must contain exactly three spec keys — no allowed-tools, license, top-level user-invocable."""
    template = tmp_path / "extra-keys.md"
    template.write_text(
        "---\ndescription: Extra keys test\n---\n"
        "## User Input\n\n```text\n$ARGUMENTS\n```\n\n"
        "You **MUST** consider the user input before proceeding (if not empty).\n",
        encoding="utf-8",
    )
    skill = render(template, "codex", _TEST_VERSION)
    assert set(skill.frontmatter.keys()) == {"name", "description", "metadata"}


def test_frontmatter_serialisation_with_colon_in_description(tmp_path: Path) -> None:
    """A description containing a colon must be emitted without corruption."""
    template = tmp_path / "colon-desc.md"
    # Override description via frontmatter to ensure a colon is present.
    template.write_text(
        "---\ndescription: 'Cross-artifact: consistency and quality'\n---\n"
        "## User Input\n\n```text\n$ARGUMENTS\n```\n\n"
        "You **MUST** consider the user input before proceeding (if not empty).\n",
        encoding="utf-8",
    )
    skill = render(template, "codex", _TEST_VERSION)
    skill_md = skill.to_skill_md()
    # The description value must round-trip faithfully.
    assert "Cross-artifact: consistency and quality" in skill_md
    # Must not produce a broken YAML line like ``description: Cross-artifact:``
    lines = skill_md.splitlines()
    desc_line = next(l for l in lines if l.startswith("description:"))
    # The colon after "Cross-artifact" should be preserved inside quotes or bare.
    assert "Cross-artifact" in desc_line
    assert "consistency and quality" in desc_line


# ---------------------------------------------------------------------------
# Description fallback tests
# ---------------------------------------------------------------------------


def test_description_from_purpose_section(tmp_path: Path) -> None:
    """When a ## Purpose section exists (and no frontmatter description), use its first sentence."""
    template = tmp_path / "purpose.md"
    template.write_text(
        # No YAML frontmatter description field
        "---\n---\n"
        "## User Input\n\n```text\n$ARGUMENTS\n```\n\n"
        "You **MUST** consider the user input before proceeding (if not empty).\n\n"
        "## Purpose\n\nExecute the workflow step by step. This is a long description.\n\n"
        "## Steps\n\nDo work.\n",
        encoding="utf-8",
    )
    skill = render(template, "codex", _TEST_VERSION)
    assert skill.frontmatter["description"] == "Execute the workflow step by step"


def test_description_fallback_to_canonical(tmp_path: Path) -> None:
    """When neither frontmatter description nor ## Purpose exists, fall back to canonical string."""
    template = tmp_path / "fallback.md"
    template.write_text(
        # No description in frontmatter, no ## Purpose section.
        "---\n---\n## User Input\n\n```text\n$ARGUMENTS\n```\n\nYou **MUST** consider the user input before proceeding (if not empty).\n",
        encoding="utf-8",
    )
    skill = render(template, "codex", _TEST_VERSION)
    assert skill.frontmatter["description"] == "Spec Kitty fallback workflow"


def test_description_from_frontmatter_takes_priority(tmp_path: Path) -> None:
    """Frontmatter description takes priority over ## Purpose section."""
    template = tmp_path / "fm-priority.md"
    template.write_text(
        "---\ndescription: Frontmatter wins\n---\n"
        "## User Input\n\n```text\n$ARGUMENTS\n```\n\n"
        "You **MUST** consider the user input before proceeding (if not empty).\n\n"
        "## Purpose\n\nShould not appear in description.\n",
        encoding="utf-8",
    )
    skill = render(template, "codex", _TEST_VERSION)
    assert skill.frontmatter["description"] == "Frontmatter wins"


# ---------------------------------------------------------------------------
# RenderedSkill dataclass tests
# ---------------------------------------------------------------------------


def test_rendered_skill_name(tmp_path: Path) -> None:
    """RenderedSkill.name must be 'spec-kitty-<command>' (Agent Skills grammar, #6475)."""
    template = tmp_path / "my-command.md"
    template.write_text(
        "---\ndescription: A command\n---\n## User Input\n\n```text\n$ARGUMENTS\n```\n\nYou **MUST** consider the user input before proceeding (if not empty).\n",
        encoding="utf-8",
    )
    skill = render(template, "codex", _TEST_VERSION)
    assert skill.name == "spec-kitty-my-command"
    assert skill.frontmatter["name"] == skill.name
    assert skill.to_skill_md().startswith("---\nname: spec-kitty-my-command\n")


def test_rendered_body_rewrites_command_invocations_to_the_skill_name(tmp_path: Path) -> None:
    """Pack sources keep ``/spec-kitty.<cmd>``; a skill body names the skill (#6475, answer A)."""
    template = tmp_path / "my-command.md"
    template.write_text(
        "---\ndescription: A command\n---\n## User Input\n\n```text\n$ARGUMENTS\n```\n\n"
        "## Next\n\nRun `/spec-kitty.plan`, then `$spec-kitty.tasks-outline` or /skill:spec-kitty.review.\n"
        "Keep https://spec-kitty.ai, spec-kitty.analysis-report and .claude/commands/spec-kitty.plan.md.\n",
        encoding="utf-8",
    )
    skill = render(template, "codex", _TEST_VERSION)
    assert "Run `/spec-kitty-plan`, then `$spec-kitty-tasks-outline` or /skill:spec-kitty-review." in skill.body
    assert "Keep https://spec-kitty.ai, spec-kitty.analysis-report and .claude/commands/spec-kitty.plan.md." in skill.body


def test_rendered_body_rewrite_is_agent_independent() -> None:
    """Every command-skill agent gets byte-identical bodies (shared ``.agents/skills`` batch)."""
    from specify_cli.skills.command_renderer import SUPPORTED_AGENTS

    template = TEMPLATES_DIR / "specify" / "prompt.md"
    bodies = {render(template, agent, _TEST_VERSION).body for agent in SUPPORTED_AGENTS}
    assert len(bodies) == 1
    (body,) = bodies
    assert "/spec-kitty-plan" in body
    assert "/spec-kitty.plan`" not in body


def test_rendered_skill_no_arguments_in_body(tmp_path: Path) -> None:
    """The rendered body must not contain $ARGUMENTS."""
    for tmpl in _all_templates():
        skill = render(tmpl, "codex", _TEST_VERSION)
        assert "$ARGUMENTS" not in skill.body, f"$ARGUMENTS found in rendered body for {_command_name(tmpl)}"


def test_rendered_skill_source_hash(tmp_path: Path) -> None:
    """source_hash must be a SHA-256 hex string (64 chars)."""
    template = tmp_path / "hash-test.md"
    template.write_text(
        "---\ndescription: Hash test\n---\n## User Input\n\n```text\n$ARGUMENTS\n```\n\nYou **MUST** consider the user input before proceeding (if not empty).\n",
        encoding="utf-8",
    )
    skill = render(template, "codex", _TEST_VERSION)
    assert len(skill.source_hash) == 64
    assert all(c in "0123456789abcdef" for c in skill.source_hash)


def test_rendered_skill_frozen() -> None:
    """RenderedSkill must be immutable (frozen dataclass)."""
    tmpl = _all_templates()[0]
    skill = render(tmpl, "codex", _TEST_VERSION)
    with pytest.raises((AttributeError, TypeError)):
        skill.name = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _user_input_block module tests
# ---------------------------------------------------------------------------


def test_identify_returns_correct_span() -> None:
    """identify() returns the correct (start, end) span for the block."""
    body = textwrap.dedent("""\
        ## Preamble

        Some text.

        ## User Input

        ```text
        $ARGUMENTS
        ```

        You MUST consider this.

        ## Next Section

        More content.
    """)
    span = identify(body)
    assert span is not None
    start, end = span
    # The block starts at the '## User Input' line.
    assert body[start : start + 14] == "## User Input\n"
    # The block ends just before '## Next Section'.
    assert body[end : end + 16] == "## Next Section\n"


def test_identify_returns_none_when_missing() -> None:
    """identify() returns None when there is no ## User Input heading."""
    body = "## Purpose\n\nDoes stuff.\n\n## Steps\n\nDo work.\n"
    assert identify(body) is None


def test_identify_block_at_end_of_document() -> None:
    """identify() handles a User-Input block that runs to end of file."""
    body = "## Other\n\nContent.\n\n## User Input\n\nContent here.\n"
    span = identify(body)
    assert span is not None
    start, end = span
    assert end == len(body)


def test_rewrite_produces_replacement_block() -> None:
    """rewrite() replaces the User-Input block with REPLACEMENT_BLOCK."""
    body = textwrap.dedent("""\
        ## Before

        Text.

        ## User Input

        ```text
        $ARGUMENTS
        ```

        You MUST consider this.

        ## After

        More text.
    """)
    result = rewrite(body)
    assert REPLACEMENT_BLOCK in result
    assert "$ARGUMENTS" not in result
    assert "## Before" in result
    assert "## After" in result


def test_rewrite_raises_on_missing_block(tmp_path: Path) -> None:
    """rewrite() raises SkillRenderError(user_input_block_missing) when no block exists."""
    body = "## Purpose\n\nDoes stuff.\n"
    with pytest.raises(SkillRenderError) as exc_info:
        rewrite(body)
    assert exc_info.value.code == "user_input_block_missing"


def test_replacement_block_constant_unchanged() -> None:
    """The REPLACEMENT_BLOCK constant matches its locked value (snapshot guard)."""
    expected = (
        "## User Input\n\n"
        "The content of the user's message that invoked this skill "
        "(everything after the skill invocation token, e.g. after "
        "`/spec-kitty-<command>` or `$spec-kitty-<command>`) is the User Input "
        "referenced elsewhere in these instructions.\n\n"
        "You **MUST** consider this user input before proceeding (if not empty).\n\n"
    )
    assert expected == REPLACEMENT_BLOCK, (
        "REPLACEMENT_BLOCK has drifted from its locked value. This is a load-bearing constant — any change requires a deliberate version bump."
    )


# ---------------------------------------------------------------------------
# NFR-004 gate tests: doctrine mission-steps path (T052)
# ---------------------------------------------------------------------------


def test_nfr004_doctrine_path_exists() -> None:
    """NFR-004: The doctrine mission-steps directory must exist after WP02 migration.

    This test is a canary — if the directory is missing, the whole deployment
    pipeline is broken and nothing will render.
    """
    assert DOCTRINE_MISSION_STEPS_DIR.is_dir(), (
        f"doctrine mission-steps directory missing: {DOCTRINE_MISSION_STEPS_DIR}\nWP02 should have moved command-templates into this location."
    )
    assert TEMPLATES_DIR.is_dir(), f"software-dev mission-steps directory missing: {TEMPLATES_DIR}"


def test_nfr004_legacy_command_templates_absent() -> None:
    """NFR-004: The old command-templates/ path must NOT exist after WP02 migration.

    The template source of truth is now ``src/charter/offering/missions/mission-steps/``.
    If the old path still exists, the migration was incomplete.
    """
    assert not _LEGACY_COMMAND_TEMPLATES_DIR.exists(), (
        f"Legacy command-templates directory still exists: {_LEGACY_COMMAND_TEMPLATES_DIR}\n"
        "WP02 should have removed it; template source is now doctrine/missions/mission-steps/."
    )


def test_nfr004_specify_step_renders_from_doctrine() -> None:
    """NFR-004: The 'specify' step renders from the new doctrine path.

    Given the software-dev/specify step at the new doctrine path,
    When render() is called with the doctrine prompt.md path,
    Then the output is the content of that file (not the old command-templates path).
    """
    specify_prompt = TEMPLATES_DIR / "specify" / "prompt.md"
    assert specify_prompt.is_file(), f"software-dev/specify/prompt.md missing at: {specify_prompt}\nWP02 should have created this file."

    skill = render(specify_prompt, "codex", _TEST_VERSION)

    assert skill.name == "spec-kitty-specify", f"Expected name 'spec-kitty-specify', got '{skill.name}'"
    assert skill.source_template == specify_prompt.resolve(), f"source_template mismatch: expected {specify_prompt.resolve()}, got {skill.source_template}"
    assert "$ARGUMENTS" not in skill.body, "Rendered body must not contain $ARGUMENTS"


def test_nfr004_all_canonical_steps_render() -> None:
    """NFR-004: All canonical steps under software-dev render without error.

    This exercises the full deployment pipeline contract: every step that
    command_installer.PROMPT_BACKED_COMMANDS references must be renderable from
    the new doctrine path.
    """
    from specify_cli.skills.command_installer import PROMPT_BACKED_COMMANDS

    missing: list[str] = []
    render_errors: list[str] = []

    for command in PROMPT_BACKED_COMMANDS:
        prompt_path = TEMPLATES_DIR / command / "prompt.md"
        if not prompt_path.is_file():
            missing.append(command)
            continue
        try:
            skill = render(prompt_path, "codex", _TEST_VERSION)
            if skill.name != f"spec-kitty-{command}":
                raise AssertionError(f"Wrong skill name for {command}: {skill.name}")
        except Exception as exc:  # noqa: BLE001
            render_errors.append(f"{command}: {exc}")

    assert not missing, f"Canonical commands missing prompt.md in doctrine path: {missing}\nExpected files under: {TEMPLATES_DIR}"
    assert not render_errors, f"Commands failed to render: {render_errors}"


def test_nfr004_command_installer_resolves_relocated_missions_path() -> None:
    """NFR-004: command_installer._resolve_template resolves the relocated missions path.

    FR-005 moved mission data out of the doctrine package into
    packs/built-in/missions/. Verify the installer's path resolver follows
    that relocation and lands on a real file under the new canonical
    location, and that it never falls back to the old
    specify_cli/missions/software-dev/command-templates/ directory.
    """
    from specify_cli.skills.command_installer import _resolve_template

    template_path = _resolve_template(Path("/unused"), "specify")

    assert template_path.name == "prompt.md", f"Expected template filename 'prompt.md', got '{template_path.name}'"
    assert "packs/built-in/missions" in str(template_path).replace("\\", "/"), (
        f"Resolved template path does not go through the relocated 'packs/built-in/missions' location: {template_path}"
    )
    assert "command-templates" not in str(template_path), f"Resolved template path still references legacy 'command-templates': {template_path}"
    assert template_path.is_file(), f"Resolved template path does not exist on disk: {template_path}"
