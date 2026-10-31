"""The system status actor and the reader invariants it must not move (#6722).

#6400 gave every agent and operator status write the structured 4-key actor and, by
operator decision, left the system writers on bare strings. This module pins the
decision that closes that boundary:

* :func:`build_system_actor` — the one builder: exactly the four keys, ``role``
  ``system``, ``profile``/``model`` always ``None``, the identity kept whole in
  ``tool`` (a ``migration:<id>`` identity is never split as a compact ``--agent``).
* The decoder pin — ``role: "system"`` crosses both ``specify_cli.status.models
  .decode_actor`` and the shared ``spec_kitty_events.diary.decode_actor``, and the
  event survives a ``to_dict`` / ``from_dict`` round-trip. A future events release
  that enumerates ``role`` fails here rather than at a user's log.
* The reader invariants — the shape never decides a verdict: every seed gate answers
  the same for a string seed and for the structured actor of the same identity, and a
  log that mixes the two shapes reduces to exactly the snapshot of the all-string log.

Nothing here calls a writer. WP02–WP04 own the emit sites; this module owns the
authority and the readers.
"""

from __future__ import annotations

import pytest
from spec_kitty_events.diary import decode_actor as diary_decode_actor

from specify_cli.status.actor import ActorRole, build_system_actor
from specify_cli.status.models import (
    Lane,
    StatusEvent,
    actor_identity_str,
    decode_actor,
    is_migration_actor,
)
from specify_cli.status.reducer import reduce
from specify_cli.status.review_roles import latest_implementer_event
from specify_cli.status.validate import validate_timestamp_continuity
from specify_cli.status.work_package_lifecycle import _actor_key

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_FOUR_KEYS = {"tool", "role", "profile", "model"}
_SEED_IDENTITY = "migration:backfill_runtime_state"


# ---------------------------------------------------------------------------
# T003 — the builder contract
# ---------------------------------------------------------------------------


def test_system_actor_has_exactly_the_four_written_keys() -> None:
    actor = build_system_actor("merge")
    assert set(actor) == _FOUR_KEYS
    assert actor == {"tool": "merge", "role": "system", "profile": None, "model": None}


@pytest.mark.parametrize(
    "identity",
    [
        pytest.param("merge", id="merge"),
        pytest.param("recovery", id="recovery"),
        pytest.param("finalize-tasks", id="finalize-tasks"),
        pytest.param(_SEED_IDENTITY, id="migration-identity"),
        pytest.param("Ivan Melck", id="resolved-operator-identity"),
    ],
)
def test_system_actor_keeps_the_identity_whole(identity: str) -> None:
    """`tool` is the identity verbatim: a colon-carrying seed id must not be split."""
    assert build_system_actor(identity)["tool"] == identity


def test_system_actor_never_carries_a_profile_or_model() -> None:
    actor = build_system_actor(_SEED_IDENTITY)
    assert actor["profile"] is None
    assert actor["model"] is None


def test_system_actor_role_is_the_new_third_value() -> None:
    assert ActorRole.SYSTEM == "system"
    assert {member.value for member in ActorRole} == {"implementer", "reviewer", "system"}


@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_system_actor_refuses_a_blank_identity(blank: str) -> None:
    """An actor that names nobody is refused, never recorded."""
    with pytest.raises(ValueError, match="non-blank tool identity"):
        build_system_actor(blank)


def test_system_builder_takes_no_role_profile_or_model() -> None:
    """`profile`/`model` are literals, so "nothing invented" is a signature guarantee."""
    with pytest.raises(TypeError):
        build_system_actor("merge", profile="someone")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# T004 — the decoder pin (no events release, no frozen path)
# ---------------------------------------------------------------------------


def test_cli_decoder_keeps_a_system_actor() -> None:
    actor = build_system_actor(_SEED_IDENTITY)
    assert decode_actor(actor) == actor


def test_shared_events_decoder_keeps_a_system_actor() -> None:
    """`spec_kitty_events` 11.x validates keys and value types, never a role vocabulary."""
    actor = build_system_actor(_SEED_IDENTITY)
    assert diary_decode_actor(actor) == actor


def test_system_actor_survives_the_event_round_trip() -> None:
    event = _seed_event(build_system_actor(_SEED_IDENTITY))
    reread = StatusEvent.from_dict(event.to_dict())
    assert reread.actor == build_system_actor(_SEED_IDENTITY)
    assert set(reread.actor) == _FOUR_KEYS


def test_five_key_actor_stays_a_reader_only_shape() -> None:
    """The mission adds no fifth key: the package decoder still refuses it (#6721)."""
    five_key = {**build_system_actor("merge"), "profile_source": None}
    assert decode_actor(five_key) == five_key
    with pytest.raises(ValueError, match="exactly"):
        diary_decode_actor(five_key)


# ---------------------------------------------------------------------------
# T005 — the reader invariants: the shape never decides
# ---------------------------------------------------------------------------


def _seed_event(actor: object, *, event_id: str = "01SEED000000000000000000001", at: str = "2026-01-01T00:00:00+00:00") -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug="m",
        wp_id="WP01",
        from_lane=Lane.GENESIS,
        to_lane=Lane.PLANNED,
        at=at,
        actor=actor,  # type: ignore[arg-type]
        force=False,
        execution_mode="worktree",
    )


def _claim_event(actor: object, *, event_id: str, at: str, policy_metadata: dict[str, str] | None = None) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug="m",
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at=at,
        actor=actor,  # type: ignore[arg-type]
        force=False,
        execution_mode="worktree",
        policy_metadata=policy_metadata,
    )


@pytest.mark.parametrize("identity", ["merge", "recovery", "finalize-tasks"])
def test_identity_projection_is_shape_blind(identity: str) -> None:
    """The tool-scoped comparison key is the same for a system identity and its string."""
    assert actor_identity_str(identity) == identity
    assert actor_identity_str(build_system_actor(identity)) == identity
    assert _actor_key(identity) == _actor_key(build_system_actor(identity))


def test_a_seed_is_never_the_implementer_of_record_however_it_is_shaped() -> None:
    """A `migration:<id>` seed is excluded before any comparison key is taken.

    ``_actor_key`` is a *tool-scoped* key: a compact string is parsed down to its bare
    tool (``"migration:x"`` -> ``"migration"``) while a dict keeps its whole ``tool``,
    so the two shapes disagree for a colon-carrying identity. That difference is
    unobservable because every consumer of the key skips seeds first
    (:func:`is_migration_actor`). Proven behaviourally here: a claim made by a seed is
    not the implementer of record in either shape, so no identity comparison ever runs
    on one.
    """
    for actor in (_SEED_IDENTITY, build_system_actor(_SEED_IDENTITY)):
        seeded_claim = _claim_event(actor, event_id="01SEED00000000000000000003", at="2026-01-01T00:00:01+00:00")
        assert latest_implementer_event([seeded_claim], "WP01") is None
        assert _actor_key(actor) is not None


def test_migration_prefix_gate_is_shape_blind() -> None:
    assert is_migration_actor(_SEED_IDENTITY) is True
    assert is_migration_actor(build_system_actor(_SEED_IDENTITY)) is True
    assert is_migration_actor(build_system_actor("merge")) is False


def test_reducer_seed_arm_is_shape_blind() -> None:
    """A seed claim counts only when no real claim is at or after it — for either shape.

    The corpus case (#6093): the seed re-stamps the real claim's ``at`` and its
    ``event_id`` sorts after it, so only the seed exclusion keeps the real claimant.
    """
    real_claim = _claim_event("claude", event_id="01REAL00000000000000000001", at="2026-01-01T00:00:05+00:00", policy_metadata={"agent": "claude"})
    for actor in (_SEED_IDENTITY, build_system_actor(_SEED_IDENTITY)):
        seed = _claim_event(actor, event_id="01SEED00000000000000000002", at="2026-01-01T00:00:05+00:00", policy_metadata={"agent": "migration"})
        snapshot = reduce([real_claim, seed])
        assert snapshot.work_packages["WP01"]["implementer_of_record"] == "claude"


def test_timestamp_continuity_exemption_is_shape_blind() -> None:
    """The #6271 exemption is on the identity, so a dict seed is exempt too."""
    for actor in (_SEED_IDENTITY, build_system_actor(_SEED_IDENTITY)):
        rows = [
            {
                "event_id": "01A00000000000000000000001",
                "wp_id": "WP01",
                "from_lane": "planned",
                "to_lane": "in_progress",
                "at": "2026-01-01T00:00:00+00:00",
                "actor": "claude",
            },
            {
                "event_id": "01A00000000000000000000002",
                "wp_id": "WP01",
                # Skewed: claims to come from `planned` while the lane is `in_progress`.
                "from_lane": "planned",
                "to_lane": "claimed",
                "at": "2026-01-01T00:00:01+00:00",
                "actor": actor,
            },
        ]
        assert validate_timestamp_continuity(rows) == []


def test_mixed_shape_log_reduces_to_the_all_string_snapshot() -> None:
    """The load-bearing proof: the actor's shape is unobservable in the reduced state."""
    string_seeds = [
        _seed_event(_SEED_IDENTITY, event_id="01SEED00000000000000000001", at="2026-01-01T00:00:00+00:00"),
        _claim_event(_SEED_IDENTITY, event_id="01SEED00000000000000000002", at="2026-01-01T00:00:02+00:00"),
    ]
    structured_seeds = [
        _seed_event(build_system_actor(_SEED_IDENTITY), event_id="01SEED00000000000000000001", at="2026-01-01T00:00:00+00:00"),
        _claim_event(build_system_actor(_SEED_IDENTITY), event_id="01SEED00000000000000000002", at="2026-01-01T00:00:02+00:00"),
    ]
    # The mixed log is the shape a real upgrade produces: rows already in the log keep
    # the string, rows written after this change carry the dict.
    mixed_seeds = [string_seeds[0], structured_seeds[1]]

    assert reduce(structured_seeds).to_dict() == reduce(string_seeds).to_dict()
    assert reduce(mixed_seeds).to_dict() == reduce(string_seeds).to_dict()


def test_system_actor_and_string_seed_share_the_snapshot_actor_slot() -> None:
    """The display identity the board reads is unchanged by the shape."""
    string_snapshot = reduce([_seed_event(_SEED_IDENTITY, event_id="01SEED00000000000000000001")])
    dict_snapshot = reduce([_seed_event(build_system_actor(_SEED_IDENTITY), event_id="01SEED00000000000000000001")])
    assert string_snapshot.work_packages["WP01"]["actor"] == dict_snapshot.work_packages["WP01"]["actor"]
