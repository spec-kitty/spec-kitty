"""Mission identity inputs: slug validation, friendly name and purpose.

Moved verbatim from ``mission_creation.py`` (#5634); the identity seam
:func:`_mint_mission_id` was added here afterwards. ``mission_creation`` re-exports every
name defined here. A call to a name tests patch on ``mission_creation``, or to a function
another ``mission_creation*`` module owns, goes through a lazy in-function
``from specify_cli.core import mission_creation as _mc`` import (never at module scope).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ulid import ULID

from specify_cli.core.mission_payload import (
    default_mission_display_name,
    default_mission_purpose_context,
)
from specify_cli.mission_metadata import validate_purpose_summary
from specify_cli.core.mission_creation_errors import MissionCreationError


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


KEBAB_CASE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9]*(-[a-z0-9]+)*$")
# Note: Intentionally permissive — bare-digit slugs like "069" are accepted.
# create_mission_core() always prefixes the mission number, so "069" becomes "070-069" in practice.


def _validate_create_inputs(mission_slug: str, friendly_name: str | None) -> str:
    """Validate ``mission_slug``/``friendly_name`` and return the resolved friendly name.

    Section 1 of the pre-decomposition body (FR-026 / T051): the kebab-case
    slug check, the explicitly-empty-``friendly_name`` refusal, and the
    default-to-``default_mission_display_name(mission_slug)`` fallback. The
    fallback is a pure computation with no observable side effect before it,
    so folding it in here (rather than leaving it at its original later call
    site) does not change what raises or when.
    """
    if not KEBAB_CASE_PATTERN.match(mission_slug):
        raise MissionCreationError(
            f"Invalid mission slug '{mission_slug}'. "
            "Must be kebab-case (lowercase letters, numbers, hyphens only)."
            "\n\nValid examples:"
            "\n  - user-auth"
            "\n  - fix-bug-123"
            "\n  - 068-feature-name"
            "\n  - new-dashboard"
            "\n\nInvalid examples:"
            "\n  - User-Auth (uppercase)"
            "\n  - user_auth (underscores)"
        )

    friendly_name_was_provided = friendly_name is not None
    normalized_friendly_name = " ".join((friendly_name or "").split())
    if friendly_name_was_provided and not normalized_friendly_name:
        raise MissionCreationError("Mission creation requires a non-empty friendly_name.")
    if not normalized_friendly_name:
        normalized_friendly_name = default_mission_display_name(mission_slug)
    return normalized_friendly_name


@dataclass(frozen=True, slots=True)
class _Purpose:
    """Normalized, validated purpose fields for one create call (section 3, T051)."""

    tldr: str
    context: str


def _resolve_purpose(
    normalized_friendly_name: str,
    purpose_tldr: str | None,
    purpose_context: str | None,
    planning_branch: str,
) -> _Purpose:
    """Normalize and validate the purpose TL;DR/context (section 3, T051)."""
    normalized_purpose_tldr = " ".join((purpose_tldr or "").split()) if purpose_tldr is not None else normalized_friendly_name
    normalized_purpose_context = (
        " ".join((purpose_context or "").split()) if purpose_context is not None else default_mission_purpose_context(normalized_friendly_name, planning_branch)
    )
    purpose_errors = validate_purpose_summary(normalized_purpose_tldr, normalized_purpose_context)
    if purpose_errors:
        raise MissionCreationError(" ".join(purpose_errors))
    return _Purpose(tldr=normalized_purpose_tldr, context=normalized_purpose_context)


def _mint_mission_id() -> str:
    """Mint the canonical ``mission_id`` of a new mission: a fresh ULID.

    The one place a create mints its identity (#5634). ``mid8`` and the
    mission directory name derive from it. Callers that need a fixed identity
    pass ``_mission_id`` to :func:`~specify_cli.core.mission_creation._create_mission_core_failure_atomic`
    instead of patching this function or ``ULID``.
    """
    return str(ULID())
