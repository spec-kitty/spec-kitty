"""The structured status actor and its readers (#6400, FR-004, FR-006, FR-012..FR-014).

Phase split (operator decision 2026-10-27, spec C-006): writers emit the 4-key actor
``{tool, role, profile, model}`` that ``spec_kitty_events`` 11's diary decoder accepts;
the WP-frontmatter fill and ``profile_source`` on the wire wait for the events release.

* :func:`build_status_actor` — exactly four keys; ``profile`` from the dispatch binding,
  else the compact ``--agent`` profile segment, else ``None``; only the bare tool
  reaches ``tool``. ``status.emit``'s builders are thin delegates to it.
* :func:`role_for_hop` — the role comes from the action, never from the profile.
* :func:`decode_actor` — accepts a string, the 4-key dict and the 5-key dict;
  refuses every other shape (no silent ``repr`` flattening).
* :func:`actor_full_identity` — a frontmatter-filled profile is planned, not proven:
  it never takes part in identity, so every legacy identity stays byte-identical.
"""

from __future__ import annotations

import pytest
from spec_kitty_events.diary import decode_actor as diary_decode_actor

from specify_cli.status.actor import ActorRole, build_status_actor, role_for_hop
from specify_cli.status.emit import build_resolved_actor, build_self_asserting_actor
from specify_cli.status.models import Lane, ProfileSource, actor_full_identity, decode_actor
from specify_cli.status.resolved_binding import ResolvedBinding

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_FOUR_KEYS = {"tool", "role", "profile", "model"}

_BINDING = ResolvedBinding(agent_profile="op-profile", model="op-model")
_EMPTY_BINDING = ResolvedBinding()


def test_profile_source_values_are_the_contract_set() -> None:
    assert {member.value for member in ProfileSource} == {"invocation", "flag", "agent_string", "wp_frontmatter"}


# ---------------------------------------------------------------------------
# role_for_hop — the role from the action (FR-006)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("from_lane", "to_lane", "expected"),
    [
        ("in_review", "planned", "reviewer"),
        ("in_review", "in_progress", "reviewer"),
        ("in_review", "blocked", "reviewer"),
        ("in_review", "canceled", "reviewer"),
        ("for_review", "in_review", "reviewer"),
        ("in_review", "approved", "reviewer"),
        ("approved", "done", "reviewer"),
        ("in_progress", "for_review", "implementer"),
        ("planned", "claimed", "implementer"),
        ("claimed", "in_progress", "implementer"),
        ("in_progress", "blocked", "implementer"),
        ("blocked", "planned", "implementer"),
        ("claimed", "doing", "implementer"),
        ("doing", "for_review", "implementer"),
        (None, "planned", "implementer"),
        (Lane.IN_REVIEW, Lane.PLANNED, "reviewer"),
        (Lane.PLANNED, Lane.CLAIMED, "implementer"),
        (" In_Review ", "planned", "reviewer"),
    ],
)
def test_role_for_hop(from_lane: str | Lane | None, to_lane: str | Lane, expected: str) -> None:
    assert role_for_hop(from_lane, to_lane) == expected


def test_actor_role_values() -> None:
    assert {member.value for member in ActorRole} == {"implementer", "reviewer"}


# ---------------------------------------------------------------------------
# build_status_actor — the 4-key value writers emit (FR-004, C-006)
# ---------------------------------------------------------------------------


def test_build_status_actor_parses_compact_agent() -> None:
    actor = build_status_actor(
        role="implementer",
        agent="claude:opus:python-pedro:implementer",
        fallback_tool="user",
        binding=None,
    )
    assert actor == {"tool": "claude", "role": "implementer", "profile": "python-pedro", "model": "opus"}


def test_build_status_actor_binding_wins_over_agent_segments() -> None:
    actor = build_status_actor(role="reviewer", agent="claude:sonnet:seg", fallback_tool=None, binding=_BINDING)
    assert actor == {"tool": "claude", "role": "reviewer", "profile": "op-profile", "model": "op-model"}


def test_build_status_actor_profileless_binding_falls_through_to_agent_segment() -> None:
    actor = build_status_actor(role="implementer", agent="claude::seg", fallback_tool=None, binding=_EMPTY_BINDING)
    assert actor == {"tool": "claude", "role": "implementer", "profile": "seg", "model": None}


def test_build_status_actor_falls_back_to_default_tool() -> None:
    actor = build_status_actor(role="implementer", agent=None, fallback_tool="user", binding=None)
    assert actor == {"tool": "user", "role": "implementer", "profile": None, "model": None}


def test_build_status_actor_empty_tool_segment_raises() -> None:
    with pytest.raises(ValueError, match="Empty agent tool"):
        build_status_actor(role="implementer", agent=":opus", fallback_tool="user", binding=None)


@pytest.mark.parametrize(
    ("binding", "agent"),
    [
        (None, None),
        (None, "claude"),
        (_BINDING, "claude::seg"),
        (_EMPTY_BINDING, "claude"),
        (None, "claude:opus:seg:reviewer"),
    ],
)
def test_build_status_actor_is_what_both_decoders_accept(binding: ResolvedBinding | None, agent: str | None) -> None:
    """Every written actor is the 4-key shape the events diary decoder (every status read) accepts."""
    actor = build_status_actor(role="implementer", agent=agent, fallback_tool="user", binding=binding)
    assert set(actor) == _FOUR_KEYS
    assert decode_actor(actor) == actor
    assert diary_decode_actor(actor) == actor


def test_delegating_builders_emit_the_four_key_value() -> None:
    """``status.emit`` builders are thin delegates: one actor-building authority, same 4 keys and values."""
    resolved = build_resolved_actor(role="implementer", tool="claude", binding=None, self_profile="seg", self_model="opus")
    assert resolved == {"tool": "claude", "role": "implementer", "profile": "seg", "model": "opus"}

    from_binding = build_resolved_actor(role="reviewer", tool="claude", binding=_BINDING, self_profile="seg", self_model="opus")
    assert from_binding == {"tool": "claude", "role": "reviewer", "profile": "op-profile", "model": "op-model"}

    self_asserting = build_self_asserting_actor(role="reviewer", agent="claude:opus:seg", fallback_tool="user", binding=None)
    assert self_asserting == build_status_actor(role="reviewer", agent="claude:opus:seg", fallback_tool="user", binding=None)
    assert self_asserting == {"tool": "claude", "role": "reviewer", "profile": "seg", "model": "opus"}


# ---------------------------------------------------------------------------
# decode_actor — accepts exactly three shapes (FR-012)
# ---------------------------------------------------------------------------


def test_decode_actor_round_trips_the_five_key_dict() -> None:
    value = {"tool": "claude", "role": "implementer", "profile": "python-pedro", "profile_source": "wp_frontmatter", "model": None}
    decoded = decode_actor(value)
    assert decoded == value
    assert decoded is not value


def test_decode_actor_accepts_legacy_four_key_dict_and_strings() -> None:
    legacy = {"tool": "claude", "role": "reviewer", "profile": None, "model": "opus"}
    assert decode_actor(legacy) == legacy
    assert decode_actor("claude") == "claude"
    assert decode_actor("claude:opus:ivan:reviewer") == "claude:opus:ivan:reviewer"


@pytest.mark.parametrize(
    "value",
    [
        pytest.param({"tool": "claude", "role": "implementer", "profile": None}, id="three-keys"),
        pytest.param(
            {"tool": "claude", "role": "implementer", "profile": "p", "profile_source": "flag", "model": None, "extra": None},
            id="six-keys",
        ),
        pytest.param({"tool": "claude", "role": "implementer", "profile": "p", "profile_source": "guess", "model": None}, id="unknown-source"),
        pytest.param({"tool": "claude", "role": "implementer", "profile": None, "profile_source": "flag", "model": None}, id="source-without-profile"),
        pytest.param({"tool": "claude", "role": "implementer", "profile": "p", "profile_source": None, "model": None}, id="profile-without-source"),
        pytest.param({"tool": "claude", "role": "implementer", "profile": "p", "profile_source": "flag", "model": 3}, id="non-string-value"),
        pytest.param({"tool": "claude", "role": 1, "profile": None, "model": None}, id="legacy-non-string-value"),
    ],
)
def test_decode_actor_refuses_malformed_dicts(value: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="structured actor"):
        decode_actor(value)


# ---------------------------------------------------------------------------
# actor_full_identity — frontmatter never asserts identity (FR-013, C-004)
# ---------------------------------------------------------------------------


def _five(profile: str | None, source: str | None) -> dict[str, str | None]:
    return {"tool": "claude", "role": "reviewer", "profile": profile, "profile_source": source, "model": None}


def test_actor_full_identity_drops_a_frontmatter_profile() -> None:
    assert actor_full_identity(_five("python-pedro", "wp_frontmatter")) == "claude::"


@pytest.mark.parametrize("source", ["invocation", "flag", "agent_string"])
def test_actor_full_identity_keeps_an_asserted_profile(source: str) -> None:
    assert actor_full_identity(_five("python-pedro", source)) == "claude::python-pedro"


def test_actor_full_identity_frontmatter_fill_equals_bare_tool() -> None:
    """A same-tool pair: a frontmatter fill compares equal to the bare tool, an asserted profile does not."""
    filled = actor_full_identity(_five("reviewer-renata", "wp_frontmatter"))
    asserted = actor_full_identity(_five("python-pedro", "agent_string"))
    assert filled == actor_full_identity("claude")
    assert asserted != actor_full_identity("claude")


@pytest.mark.parametrize(
    ("actor", "expected"),
    [
        pytest.param({"tool": "claude", "model": "opus", "profile": "ivan", "role": "implementer"}, "claude:opus:ivan", id="dict-drops-role"),
        pytest.param("claude:opus:ivan:reviewer", "claude:opus:ivan", id="compact-drops-role"),
        pytest.param("claude", "claude::", id="bare-tool"),
        pytest.param({"tool": "claude", "role": "reviewer"}, "claude::", id="dict-tool-only"),
        pytest.param(None, None, id="missing"),
    ],
)
def test_actor_full_identity_legacy_shapes_unchanged(actor: object, expected: str | None) -> None:
    """Ratchet copied from the #5340 identity table: legacy identities stay byte-identical."""
    assert actor_full_identity(actor) == expected
