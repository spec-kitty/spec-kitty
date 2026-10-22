"""Actor boundary-normalize (WP02 / FR-005/FR-006, #2861).

Pins the two surviving seams of the emit-side actor identity fix:

* :func:`~specify_cli.status.emit.parse_agent_boundary_string` — a THIN,
  non-synthesizing boundary parser for the compact ``--agent
  tool:model:profile:role`` CLI value. Unlike the persisted-frontmatter
  parser (``wp_metadata._resolve_agent_from_colon_string``), an absent
  segment stays ``None`` rather than falling back to a tool-derived
  synthetic default (``"unknown-model"`` / ``"{tool}-default"``) — a
  self-asserted actor must never fabricate identity it was never given
  (C-002/C-007).
* :func:`~specify_cli.status.emit.build_resolved_actor` widened with
  ``self_profile``/``self_model`` kwargs: a genuine dispatch-resolved
  ``binding`` value always wins; the self-asserted value only fills a gap
  the binding leaves open; absent-on-both-sides stays ``None``.

(The third pinned seam — the sync emitter's ``_is_actor_field``
``Union[str, Dict]`` acceptance gate for fan-out payload validators — died
with the sync transport, issue #5. The resolved-actor dict still rides the
transition verbatim via :func:`~specify_cli.status.emit._status_fan_out`.)
"""

from __future__ import annotations

import pytest

from specify_cli.status.emit import (
    build_resolved_actor,
    build_self_asserting_actor,
    parse_agent_boundary_string,
)
from specify_cli.status.resolved_binding import ResolvedBinding

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# parse_agent_boundary_string — thin, non-synthesizing boundary parser
# ---------------------------------------------------------------------------


def test_parse_agent_boundary_string_bare_tool() -> None:
    """A bare tool name (no colons) parses to just the tool; every other
    segment stays None — no synthetic model/profile/role is fabricated."""
    assert parse_agent_boundary_string("claude") == ("claude", None, None, None)


def test_parse_agent_boundary_string_full_compact_form() -> None:
    """The full ``tool:model:profile:role`` form parses every segment
    verbatim; the compact string never lands whole in any single field."""
    assert parse_agent_boundary_string("claude:opus:reviewer-renata:reviewer") == (
        "claude",
        "opus",
        "reviewer-renata",
        "reviewer",
    )


def test_parse_agent_boundary_string_partial_segments_stay_none() -> None:
    """Empty interior segments (``tool::profile:``) normalize to None on
    both the missing model and the missing trailing role — NOT a
    tool-derived synthetic default."""
    tool, model, profile, role = parse_agent_boundary_string("codex::planner-priti:")
    assert tool == "codex"
    assert model is None
    assert profile == "planner-priti"
    assert role is None


def test_parse_agent_boundary_string_trailing_segments_missing() -> None:
    """``tool:model`` (fewer than 4 segments) pads the missing trailing
    segments to None rather than defaulting them."""
    assert parse_agent_boundary_string("claude:sonnet") == ("claude", "sonnet", None, None)


def test_parse_agent_boundary_string_empty_tool_raises() -> None:
    """An empty tool segment is a hard error — a tool is required to
    identify the agent at all."""
    with pytest.raises(ValueError, match="Empty agent tool"):
        parse_agent_boundary_string("")


def test_parse_agent_boundary_string_no_synthetic_default_values() -> None:
    """Regression pin: neither of the frontmatter parser's synthetic
    fallback strings ever appears from this boundary parser."""
    _, model, profile, role = parse_agent_boundary_string("claude:::")
    assert model is None
    assert profile is None
    assert role is None
    assert model != "unknown-model"


# ---------------------------------------------------------------------------
# build_resolved_actor — self-asserted profile/model kwargs
# ---------------------------------------------------------------------------


def test_build_resolved_actor_self_asserted_when_no_binding() -> None:
    """No dispatch binding: the self-asserted profile/model (parsed from
    --agent) carry the actor identity instead of a synthetic default."""
    actor = build_resolved_actor(
        role="reviewer",
        tool="claude",
        binding=None,
        self_profile="reviewer-renata",
        self_model="opus",
    )
    assert actor == {
        "role": "reviewer",
        "profile": "reviewer-renata",
        "tool": "claude",
        "model": "opus",
    }


def test_build_resolved_actor_binding_wins_over_self_asserted() -> None:
    """A genuine dispatch-resolved binding always takes precedence over the
    self-asserted --agent segments (the binding is the higher-trust source)."""
    actor = build_resolved_actor(
        role="implementer",
        tool="claude",
        binding=ResolvedBinding(agent_profile="python-pedro", model="claude-opus-4-8"),
        self_profile="stale-self-asserted-profile",
        self_model="stale-self-asserted-model",
    )
    assert actor["profile"] == "python-pedro"
    assert actor["model"] == "claude-opus-4-8"


def test_build_resolved_actor_self_asserted_fills_binding_gap() -> None:
    """A binding that resolved only one field (e.g. model but no profile)
    still lets the self-asserted value fill the other, absent field."""
    actor = build_resolved_actor(
        role="implementer",
        tool="claude",
        binding=ResolvedBinding(agent_profile=None, model="claude-opus-4-8"),
        self_profile="python-pedro",
        self_model="stale-self-asserted-model",
    )
    assert actor["profile"] == "python-pedro"  # binding left profile empty -> self fills it
    assert actor["model"] == "claude-opus-4-8"  # binding's own model still wins


def test_build_resolved_actor_absent_both_stays_none() -> None:
    """No binding and no self-asserted value: absent segments stay a plain
    None — never a synthetic '{tool}-default' or 'unknown-model'."""
    actor = build_resolved_actor(role="implementer", tool="codex", binding=None)
    assert actor == {"role": "implementer", "profile": None, "tool": "codex", "model": None}


# ---------------------------------------------------------------------------
# build_self_asserting_actor — the one-shot boundary-parse + actor build helper
# that collapses the three claim seams (workflow_executor x2, tasks_move_task)
# ---------------------------------------------------------------------------


def test_build_self_asserting_actor_parses_compact_agent_to_bare_tool() -> None:
    """A compact ``tool:model:profile:role`` --agent is parsed at the boundary:
    the bare tool lands in actor.tool (never the whole string) and the parsed
    profile/model become self-asserted — no synthetic default, no minted binding."""
    actor = build_self_asserting_actor(
        role="reviewer",
        agent="claude:opus:reviewer-renata:reviewer",
        fallback_tool="claude",
        binding=None,
    )
    assert actor["tool"] == "claude"  # bare, NOT the whole compact string
    assert actor["profile"] == "reviewer-renata"
    assert actor["model"] == "opus"
    assert actor["role"] == "reviewer"


def test_build_self_asserting_actor_uses_fallback_tool_when_agent_absent() -> None:
    """With no --agent value the fallback tool is used and profile/model stay
    None (absent segments never become a synthetic '{tool}-default')."""
    actor = build_self_asserting_actor(
        role="implementer",
        agent=None,
        fallback_tool="codex",
        binding=None,
    )
    assert actor == {"role": "implementer", "profile": None, "tool": "codex", "model": None}


def test_build_self_asserting_actor_binding_wins_over_parsed_agent() -> None:
    """A resolved binding's profile/model take precedence over the self-asserted
    parse (provenance: the binding is the authoritative record, C-002/C-007)."""
    actor = build_self_asserting_actor(
        role="implementer",
        agent="claude:self-model:self-profile:implementer",
        fallback_tool="claude",
        binding=ResolvedBinding(agent_profile="python-pedro", model="claude-opus-4-8"),
    )
    assert actor["tool"] == "claude"
    assert actor["profile"] == "python-pedro"  # binding wins
    assert actor["model"] == "claude-opus-4-8"  # binding wins
