"""Charter-level activation registry (context-scoped mode).

This module defines the runtime surface for the *activation registry* —
the operator-authored block in `governance.yaml` that pairs an
``activation_context`` (mission_type + action) with a specific
``(doctrine_pack_id, artifact_id, artifact_kind)`` triple to fetch.

Canonical vocabulary
--------------------
The closed vocabularies for ``activation_context.mission_type`` and
``activation_context.action`` are pinned by ``tests/charter/test_activations.py``
(``test_allowed_actions_is_the_canonical_10_token_set`` and
``test_registered_triggers_is_superset_of_allowed_actions``), against the
token lists in data-model.md §7. This module is the single runtime home of
``ALLOWED_ACTIONS`` and ``REGISTERED_TRIGGERS``, so runtime callers
(resolvers, prompt builders, validators) import them and never copy/paste a
divergent literal.

Action vocabulary boundaries
----------------------------
There are TWO related but distinct vocabularies in this module:

* ``ALLOWED_ACTIONS`` (10 tokens) — the strict closed set of mission
  verbs and charter-loop verbs that the prompt builder emits as action
  labels.  Used by ``charter.activation.context`` to drive runtime action filtering.
* ``REGISTERED_TRIGGERS`` (14 tokens) — the strict superset that also
  includes the four fine-grained sub-action tokens (``write_comment``,
  ``write_docstring``, ``rename_identifier``, ``add_dependency``).
  This is the vocabulary an operator may write in
  ``activation_context.action`` and that artifacts may declare in
  ``triggers:`` blocks.

The :class:`ActivationEntry` validator (WP05) accepts the full
``REGISTERED_TRIGGERS`` vocabulary on the ``action`` slot (plus
wildcards) so the FR-007 user story works: ``action: write_comment`` is
operator-authorable even though ``write_comment`` is not a mission verb.
The resolver treats those fine-grained tokens as wildcards for runtime
matching (they may occur during any mission verb) and the renderer maps
them to natural prose ("write a code comment").  See data-model.md §7's
mutation rule for the canonical contract.

Layer rule
----------
``src/charter/`` MUST NOT import from ``specify_cli`` (C-001, hard
ratchet pinned by ``tests/architectural/test_layer_rules.py`` and
``test_runtime_charter_doctrine_boundary.py``). This module stays
self-contained accordingly.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, field_validator

from charter.offering.artifact_kinds import (
    CHARTER_ACTIVATABLE_PLURAL_TO_SINGULAR,
    CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL,
)
from charter.offering.missions.mission_type_repository import builtin_mission_type_id_set

__all__ = [
    "ActivationEntry",
    "ALLOWED_MISSION_TYPES",
    "ALLOWED_ACTIONS",
    "REGISTERED_TRIGGERS",
    "normalize_artifact_kind",
    "resolve_for_context",
]


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------


#: Canonical closed vocabulary for ``activation_context.mission_type``.
#: Derived from the canonical accessor
#: :func:`charter.offering.missions.mission_type_repository.builtin_mission_type_id_set`
#: (single source of truth, #2669 IC-1a) plus the wildcard tokens ``any`` /
#: ``generic``. This triggers one cached ``mission_types/`` filesystem read
#: at import of this module — the accepted NFR-001 carve-out for a
#: module-level derived value (C-012); the import is layer-legal
#: (charter -> doctrine) and cycle-free (doctrine never imports charter).
#: Mirrors the expected vocabulary pinned in
#: ``tests/architectural/test_activation_registry_schema.py``.
ALLOWED_MISSION_TYPES: frozenset[str] = frozenset(
    builtin_mission_type_id_set() | {"any", "generic"}
)


#: 10-token operator-side closed vocabulary for ``activation_context.action``.
#: The tokens are the data-model.md §7 list, pinned by
#: ``tests/charter/test_activations.py::test_allowed_actions_is_the_canonical_10_token_set``.
ALLOWED_ACTIONS: frozenset[str] = frozenset(
    {
        # Mission-type verbs (the prompt builder emits these as action labels).
        "specify",
        "plan",
        "tasks",
        "implement",
        "review",
        "merge",
        "accept",
        # Charter-loop verbs (charter context resolution itself is an action).
        "charter.interview",
        "charter.generate",
        "charter.context",
    }
)


#: 15-token artifact-side closed vocabulary for the ``triggers:`` field on
#: rendered artifact stanzas.
#: ``_REGISTERED_TRIGGERS = _ALLOWED_ACTIONS ∪ {fine-grained tokens}`` —
#: the formula's only authoritative definition lives in data-model.md §7.
#: Pinned by
#: ``tests/charter/test_activations.py::test_registered_triggers_is_superset_of_allowed_actions``.
REGISTERED_TRIGGERS: frozenset[str] = ALLOWED_ACTIONS | frozenset(
    {
        "write_comment",
        "write_docstring",
        "rename_identifier",
        "add_dependency",
    }
)


#: Wildcard tokens accepted on either slot of ``activation_context``.
#: The validator layers these on top of the action vocabulary
#: (``REGISTERED_TRIGGERS``) so an operator can write ``action: any``
#: (or ``action: generic``) to mean "every action".
_ACTION_WILDCARDS: frozenset[str] = frozenset({"any", "generic"})


#: Allowed values for the optional ``artifact_kind`` disambiguator. Mirrors
#: the artifact-kind properties exposed by ``DoctrineService``. ``templates``
#: and ``assets`` are node-declarable org-pack DRG kinds (see
#: ``charter.offering.drg.org_pack_loader._ORG_DRG_CANONICAL_KINDS``) and must move in
#: lockstep with this set and ``charter.activation.pack_context._BUILTIN_ARTIFACT_KINDS`` —
#: the drift guard in ``tests/doctrine/test_org_pack_augmentation.py`` fails if
#: any one of the three mirrors is updated alone.
_ALLOWED_KINDS: frozenset[str] = frozenset(
    {
        "directives",
        "tactics",
        "styleguides",
        "toolguides",
        "paradigms",
        "procedures",
        "agent_profiles",
        "mission_step_contracts",
        "templates",
        "assets",
        "glossary_packs",
    }
)


#: Mapping of operator-friendly singular ``artifact_kind`` tokens to the
#: canonical plural form used by ``DoctrineService`` repositories.  The
#: contract example in ``contracts/activation-registry.md`` uses the
#: singular form (``artifact_kind: styleguide``) and the rendered
#: ``--include <kind>:<id>`` selector also uses the singular per the
#: pattern set by every other fetch stanza (``directive:...``,
#: ``tactic:...``).  Accepting both forms keeps the validator strict on
#: typos while remaining ergonomic for operators.
#:
#: Derived (not restated) from the single charter-activatable kind authority
#: :data:`doctrine.artifact_kinds.CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL`
#: (FR-004) — the 10 activatable kinds including ``anti_pattern`` (C-003/FR-005).
#: The prior hand-copied literal was value-identical to the derived map, so this
#: collapse is behaviour-preserving here while making drift structurally
#: impossible (the two ``_activation_render`` copies had drifted two kinds
#: behind — #2981).
_SINGULAR_TO_PLURAL_KIND: dict[str, str] = CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL


#: Inverse lookup: canonical plural -> singular form used when rendering
#: the ``--include <kind>:<id>`` fetch selector. Derived from the same authority.
_PLURAL_TO_SINGULAR_KIND: dict[str, str] = CHARTER_ACTIVATABLE_PLURAL_TO_SINGULAR


def normalize_artifact_kind(kind: str | None) -> str | None:
    """Normalise *kind* to the canonical plural form.

    Returns ``None`` when *kind* is ``None``.  Accepts both the operator
    singular tokens (``styleguide``, ``directive``, ...) and the canonical
    plural property names (``styleguides``, ``directives``, ...).
    Unknown values are returned unchanged so the validator can raise.
    """
    if kind is None:
        return None
    return _SINGULAR_TO_PLURAL_KIND.get(kind, kind)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class ActivationEntry(BaseModel):
    """One entry in the charter-level activation registry.

    Shape (per data-model.md §3 and contracts/activation-registry.md)::

        activations:
          - activation_context:
              mission_type: software-dev   # optional, defaults to wildcard
              action: implement            # optional, defaults to wildcard
            doctrine_pack_id: very-serious-developers
            artifact_id: caveman-comments
            artifact_kind: styleguides     # optional disambiguator

    Wildcards
    ---------
    Absence of a slot in ``activation_context`` is equivalent to the
    explicit wildcard tokens ``any`` / ``generic`` — both forms match every
    concrete value. This keeps operator-authored entries terse while still
    allowing the explicit wildcard for clarity.
    """

    model_config = ConfigDict(extra="forbid")

    activation_context: dict[str, str]
    doctrine_pack_id: str
    artifact_id: str
    artifact_kind: str | None = None

    @field_validator("activation_context")
    @classmethod
    def _validate_context(cls, value: dict[str, str]) -> dict[str, str]:
        # ``ALLOWED_MISSION_TYPES`` already includes the wildcard tokens
        # (``any`` / ``generic``).  Mission types are constrained to that
        # closed set; typos raise.
        mission_type = value.get("mission_type")
        if mission_type is not None and mission_type not in ALLOWED_MISSION_TYPES:
            raise ValueError(
                f"activation_context.mission_type={mission_type!r} is not in "
                f"ALLOWED_MISSION_TYPES={sorted(ALLOWED_MISSION_TYPES)}"
            )
        # Per data-model.md §7 the operator-side action vocabulary for
        # ``activation_context.action`` is the FULL ``REGISTERED_TRIGGERS``
        # set (10 mission-type/charter-loop verbs + 4 fine-grained
        # sub-action tokens such as ``write_comment``).  Restricting to
        # the strict 10-token ``ALLOWED_ACTIONS`` would forbid the
        # operator UX showcased by the FR-007 ATDD test
        # (``action: write_comment``) and contradict the contract example
        # in ``contracts/activation-registry.md``.  Wildcards layer on
        # top so an operator can write ``action: any`` for "every
        # action".
        action = value.get("action")
        if (
            action is not None
            and action not in REGISTERED_TRIGGERS
            and action not in _ACTION_WILDCARDS
        ):
            raise ValueError(
                f"activation_context.action={action!r} is not in "
                f"REGISTERED_TRIGGERS={sorted(REGISTERED_TRIGGERS)} "
                f"and is not one of the wildcards {sorted(_ACTION_WILDCARDS)}"
            )
        return value

    @field_validator("artifact_kind")
    @classmethod
    def _validate_kind(cls, value: str | None) -> str | None:
        if value is None:
            return None
        # Accept both the canonical plural form (``styleguides`` — the
        # ``DoctrineService`` property name) and the operator-friendly
        # singular form (``styleguide`` — used in the contract example
        # and in the rendered ``--include <kind>:<id>`` fetch selector).
        # Normalise to plural on the way in so internal lookups stay
        # single-form; the renderer re-singularises for the selector.
        normalised = normalize_artifact_kind(value)
        if normalised not in _ALLOWED_KINDS:
            raise ValueError(
                f"artifact_kind={value!r} is not a known DoctrineService kind. "
                f"Accepted (plural): {sorted(_ALLOWED_KINDS)}. "
                f"Accepted (singular alias): {sorted(_SINGULAR_TO_PLURAL_KIND)}."
            )
        return normalised


def _activation_identity_key(entry: ActivationEntry) -> tuple[str, str, str, str]:
    """Return the dedup identity key for an :class:`ActivationEntry`.

    Per data-model.md §5, the identity tuple for activation de-dup is
    ``(activation_context, doctrine_pack_id, artifact_id, artifact_kind)``.
    ``activation_context`` is itself a ``dict[str, str]`` — we serialise
    it with sorted keys so structurally equal contexts produce identical
    hash keys regardless of insertion order.

    Relocated here (FR-003, WP01) from
    ``specify_cli.doctrine.org_charter`` so the org-pack fold
    (:func:`specify_cli.doctrine.org_charter._fold_policies`) and the
    charter-layer resolve-time union
    (:func:`charter.activation.context._union_activations`) share ONE identity-key
    implementation and cannot drift. This module has no
    ``org_charter``-local dependency (only ``ActivationEntry`` + stdlib
    ``json``), so the move is behavior-preserving.
    """
    return (
        json.dumps(entry.activation_context, sort_keys=True),
        entry.doctrine_pack_id,
        entry.artifact_id,
        entry.artifact_kind or "",
    )


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


#: Tokens in ``REGISTERED_TRIGGERS`` that are *not* runtime mission-type
#: verbs — they describe finer-grained agent sub-actions (e.g.
#: ``write_comment``) which can occur during any mission verb.  The
#: resolver treats them as wildcards for matching purposes (the entry
#: still matches the current runtime action) and the renderer uses the
#: declared label verbatim in the prose ("When you write_comment, ...").
_FINE_GRAINED_TRIGGERS: frozenset[str] = REGISTERED_TRIGGERS - ALLOWED_ACTIONS


def resolve_for_context(
    entries: list[ActivationEntry],
    *,
    mission_type: str,
    action: str,
) -> list[ActivationEntry]:
    """Return the subset of ``entries`` matching the given runtime context.

    Slot-match semantics:
      * ``mission_type`` — matches when declared is absent, is a wildcard
        (``any`` / ``generic``), or equals the runtime mission type.
      * ``action`` — matches when declared is absent, is a wildcard, equals
        the runtime action, OR is a fine-grained trigger token (per
        :data:`REGISTERED_TRIGGERS` minus :data:`ALLOWED_ACTIONS`).  The
        fine-grained tokens describe sub-actions (``write_comment``,
        ``write_docstring``, ``rename_identifier``, ``add_dependency``)
        that may occur during any mission verb, so they always match the
        current runtime context.  The label is preserved verbatim by the
        renderer so the prompt reads "When you write a code comment, ...".

    Returns entries in input order; callers wanting deduplication or
    priority ordering must layer that on top.
    """

    def _mission_type_matches(declared: str | None, current: str) -> bool:
        return (
            declared is None
            or declared in ("generic", "any")
            or declared == current
        )

    def _action_matches(declared: str | None, current: str) -> bool:
        return (
            declared is None
            or declared in ("generic", "any")
            or declared == current
            or declared in _FINE_GRAINED_TRIGGERS
        )

    return [
        entry
        for entry in entries
        if _mission_type_matches(entry.activation_context.get("mission_type"), mission_type)
        and _action_matches(entry.activation_context.get("action"), action)
    ]
