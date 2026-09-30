"""Integration test: rendered prompt surfaces the resolved agent 4-tuple.

Verifies that WP03 (#833) wiring delivers the colon-formatted ``--agent``
identity (``tool:model:profile_id:role``) all the way through to the
implement-prompt rendering layer instead of silently discarding ``model``,
``profile_id`` and ``role``.

The integration boundary under test is :func:`WPMetadata.resolved_agent` ->
:func:`_render_resolved_agent_identity` -> the prompt-line list that is
ultimately written to the agent prompt file by ``_write_prompt_to_file``.
"""

from __future__ import annotations

import pytest

from specify_cli.cli.commands.agent.workflow_cores import render_resolved_agent_identity as _render_resolved_agent_identity
from specify_cli.status.wp_metadata import WPMetadata

pytestmark = pytest.mark.integration


def _render_prompt_identity_block(agent_string: str) -> str:
    """Render the resolved-identity block for a WP whose ``agent`` is *agent_string*.

    Mirrors the integration that ``workflow.py`` performs when generating
    the implement / review prompt: parse the WP's ``agent`` colon string,
    resolve the 4-tuple, and emit the human-readable identity lines.
    """
    wp = WPMetadata(work_package_id="WP01", title="Integration", agent=agent_string)
    resolved = wp.resolved_agent()
    lines = _render_resolved_agent_identity(resolved)
    return "\n".join(lines)


# ── Full 4-arity case ──────────────────────────────────────────────────────


def test_full_identity_appears_in_rendered_prompt() -> None:
    """Every supplied segment of a 4-arity --agent must appear verbatim."""
    rendered = _render_prompt_identity_block(
        "claude:opus-4-7:reviewer-default:reviewer"
    )

    # Each of the four supplied tokens must appear as a substring of the
    # rendered prompt. This is the regression covered by issue #833 — prior
    # to WP03 only ``claude`` survived this round-trip.
    assert "claude" in rendered
    assert "opus-4-7" in rendered
    assert "reviewer-default" in rendered
    assert "reviewer" in rendered


def test_full_identity_block_contains_all_field_labels() -> None:
    """The rendered identity block labels every field for human readers."""
    rendered = _render_prompt_identity_block(
        "claude:opus-4-7:reviewer-default:reviewer"
    )
    # The renderer must clearly identify which slot each value occupies so
    # an operator reading the prompt can tell tool from model from role.
    assert "tool" in rendered
    assert "model" in rendered
    assert "profile_id" in rendered
    assert "role" in rendered


# ── Partial-string case (defaults visible to operator) ────────────────────


def test_partial_identity_renders_supplied_model_and_default_role() -> None:
    """A 2-arity input renders the supplied model alongside the documented role default."""
    rendered = _render_prompt_identity_block("claude:opus-4-7")

    # Supplied segments survive verbatim.
    assert "claude" in rendered
    assert "opus-4-7" in rendered

    # The trailing ``role`` slot falls back to the documented constant
    # ``"implementer"`` per data-model.md §2.
    assert "implementer" in rendered


def test_three_arity_identity_renders_supplied_profile() -> None:
    """A 3-arity input surfaces the supplied profile_id in the rendered prompt."""
    rendered = _render_prompt_identity_block(
        "claude:opus-4-7:custom-profile-id"
    )
    assert "custom-profile-id" in rendered
    # And the documented role default is still surfaced.
    assert "implementer" in rendered


# ── Empty positional segments fall back to defaults ──────────────────────


def test_empty_model_segment_renders_default_marker() -> None:
    """An empty model segment renders the resolved default in the prompt."""
    rendered = _render_prompt_identity_block(
        "claude::reviewer-default:reviewer"
    )

    # Explicitly supplied segments are surfaced.
    assert "reviewer-default" in rendered
    assert "reviewer" in rendered
    # Empty model slot falls back to the registry default which is
    # represented as ``unknown-model`` when no per-tool entry exists.
    assert "unknown-model" in rendered


# ── Behavioral integration ───────────────────────────────────────────────


def test_resolved_agent_drives_prompt_render_end_to_end() -> None:
    """End-to-end: WPMetadata.resolved_agent() output is what _render_resolved_agent_identity consumes.

    Locks the wiring contract so a future change to either side cannot
    silently drop fields again.
    """
    wp = WPMetadata(
        work_package_id="WP01",
        title="Integration",
        agent="claude:opus-4-7:reviewer-default:reviewer",
    )
    resolved = wp.resolved_agent()

    # Sanity-check the parser preserves all four supplied segments.
    assert resolved.tool == "claude"
    assert resolved.model == "opus-4-7"
    assert resolved.profile_id == "reviewer-default"
    assert resolved.role == "reviewer"

    # And that the renderer surfaces every one of them in the prompt block.
    rendered = "\n".join(_render_resolved_agent_identity(resolved))
    for token in ("claude", "opus-4-7", "reviewer-default", "reviewer"):
        assert token in rendered, f"Token {token!r} missing from rendered identity block:\n{rendered}"
