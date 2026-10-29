"""The structured status actor and the role rule (#6400).

The one actor-building authority for status transitions and annotations written by
agent and operator commands (FR-004). ``status.emit.build_resolved_actor`` and
``build_self_asserting_actor`` are thin delegates to :func:`compose_status_actor` and
:func:`build_status_actor`.

Phase split (operator decision 2026-10-27, spec C-006): ``spec_kitty_events`` 11.0.0's
``diary.decode_actor`` accepts only ``{tool, role, profile, model}``, so writers emit
that 4-key actor. ``profile`` comes only from the dispatch binding (``--invocation-id``
or ``--profile``) or the profile segment of a compact ``--agent``, else ``None``. The
WP-frontmatter fill and ``profile_source`` on the wire wait for an events release whose
decoder accepts the fifth key. Readers already accept it
(:func:`~specify_cli.status.models.decode_actor`).

* ``role`` comes from the action (:func:`role_for_hop`), never from the profile (FR-006).
* Nothing is synthesized: a value absent everywhere stays ``None`` (C-002/C-007).
* Two builders: :func:`build_status_actor` is strict (an explicit operator ``--agent``
  that does not parse raises) and :func:`actor_from_option` is lenient (free text and
  recorded identities that do not parse are kept whole as ``tool``). Only this module
  decides that fallback; every dict goes through :func:`compose_status_actor`.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from .lane_reader import CanonicalStatusNotFoundError, get_wp_lane
from .models import MIGRATION_ACTOR_PREFIX, Lane, parse_agent_boundary_string
from .resolved_binding import ResolvedBinding
from .transitions import resolve_lane_alias

__all__ = [
    "ActorRole",
    "actor_from_option",
    "build_status_actor",
    "compose_status_actor",
    "role_for_hop",
    "role_for_wp",
]


class ActorRole(StrEnum):
    """The role an actor played on a hop; set by the action (FR-006)."""

    IMPLEMENTER = "implementer"
    REVIEWER = "reviewer"


#: Lanes whose entry is a reviewer act (claiming review, approving, completing).
_REVIEWER_TARGET_LANES: frozenset[str] = frozenset({str(Lane.IN_REVIEW), str(Lane.APPROVED), str(Lane.DONE)})


def role_for_hop(from_lane: str | Lane | None, to_lane: str | Lane) -> str:
    """The actor role for a ``from_lane -> to_lane`` hop.

    ``reviewer`` for a hop into ``in_review``, ``approved`` or ``done`` and for any hop
    leaving ``in_review`` (a rejection, a block or a cancel during review);
    ``implementer`` for every other hop. Lane aliases (``doing``) are resolved first.
    """
    target = resolve_lane_alias(str(to_lane))
    source = resolve_lane_alias(str(from_lane)) if from_lane is not None else None
    if target in _REVIEWER_TARGET_LANES or source == str(Lane.IN_REVIEW):
        return str(ActorRole.REVIEWER)
    return str(ActorRole.IMPLEMENTER)


def role_for_wp(feature_dir: Path, wp_id: str, to_lane: str | Lane | None = None) -> str:
    """The actor role for a write on ``wp_id``, read off its current lane once (FR-006).

    For a transition (``to_lane`` given) this is :func:`role_for_hop` from the current
    lane. For a note (no ``to_lane``) it is ``reviewer`` while the WP is ``in_review``,
    else ``implementer``. A Mission with no event log yet has no current lane (the WP
    cannot be in review).
    """
    try:
        current: str | None = str(get_wp_lane(feature_dir, wp_id))
    except CanonicalStatusNotFoundError:
        current = None
    if to_lane is not None:
        return role_for_hop(current, to_lane)
    return str(ActorRole.REVIEWER) if current == str(Lane.IN_REVIEW) else str(ActorRole.IMPLEMENTER)


def compose_status_actor(
    *,
    role: str,
    tool: str | None,
    binding: ResolvedBinding | None,
    agent_profile: str | None = None,
    agent_model: str | None = None,
) -> dict[str, str | None]:
    """Assemble the 4-key ``{role, profile, tool, model}`` actor from an already-parsed tool.

    The dispatch-resolved ``binding`` wins for ``profile`` and ``model``; the
    self-asserted ``agent_profile`` / ``agent_model`` (parsed from a compact ``--agent``)
    only fill a gap it leaves open. Empty strings count as absent.
    """
    binding_profile = binding.agent_profile if binding is not None else None
    binding_model = binding.model if binding is not None else None
    return {
        "role": role,
        "profile": binding_profile or agent_profile or None,
        "tool": tool,
        "model": binding_model or agent_model or None,
    }


def build_status_actor(
    *,
    role: str,
    agent: str | None,
    fallback_tool: str | None,
    binding: ResolvedBinding | None,
) -> dict[str, str | None]:
    """Build the status actor from a compact ``--agent`` value (FR-004).

    Only the parsed **bare** tool reaches ``tool`` (#2861); ``fallback_tool`` (for
    example ``"user"``) carries the slot when no ``agent`` is given. An ``agent`` with
    an empty tool segment raises :class:`ValueError` (from
    :func:`~specify_cli.status.models.parse_agent_boundary_string`).
    """
    parsed_tool: str | None = None
    agent_model: str | None = None
    agent_profile: str | None = None
    if agent:
        parsed_tool, agent_model, agent_profile, _role = parse_agent_boundary_string(agent)
    return compose_status_actor(
        role=role,
        tool=parsed_tool or fallback_tool,
        binding=binding,
        agent_profile=agent_profile,
        agent_model=agent_model,
    )


#: Segments of the compact ``tool:model:profile:role`` form; a value with more is not one.
_COMPACT_AGENT_SEGMENTS = 4


def actor_from_option(actor: str, role: str, *, binding: ResolvedBinding | None = None) -> dict[str, str | None]:
    """The lenient builder: the structured actor of a free-text or recorded identity (#6400, FR-011).

    Used for ``agent status emit --actor``, the ``orchestrator-api`` ``--actor`` and an
    identity read back from the record (a recorded reviewer or agent). Those values
    were always stored verbatim, so this never refuses. The value is kept whole as
    ``tool`` (``profile`` and ``model`` from ``binding`` only) when it:

    * starts with :data:`~specify_cli.status.models.MIGRATION_ACTOR_PREFIX`, so a
      reconstruction seed stays one (``is_migration_actor`` and the package reducer);
    * has more than four ``:`` segments, so it is not a compact agent string;
    * fails :func:`~specify_cli.status.models.parse_agent_boundary_string` (an empty
      tool segment, e.g. ``":x"``).

    Otherwise it is parsed like a compact ``--agent``: the bare tool, the model and the
    profile segment; the role segment is ignored (``role`` comes from the action).
    """
    if actor.startswith(MIGRATION_ACTOR_PREFIX) or len(actor.split(":")) > _COMPACT_AGENT_SEGMENTS:
        return compose_status_actor(role=role, tool=actor, binding=binding)
    try:
        tool, agent_model, agent_profile, _role = parse_agent_boundary_string(actor)
    except ValueError:
        return compose_status_actor(role=role, tool=actor, binding=binding)
    return compose_status_actor(role=role, tool=tool, binding=binding, agent_profile=agent_profile, agent_model=agent_model)
