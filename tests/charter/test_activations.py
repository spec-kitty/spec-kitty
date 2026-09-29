"""Unit tests for :mod:`charter.activation.activations` — the charter-level
activation registry surface introduced by WP01 of mission
``charter-mediated-doctrine-selection-01KRTZCA``.

Coverage:
  * Schema: required fields exist, defaults behave, ``extra="forbid"``
    rejects typos.
  * Vocabulary closure: invalid mission_type / action / artifact_kind
    values raise ``ValidationError``.
  * Wildcard semantics: ``any`` / ``generic`` / absent slot match every
    concrete value through :func:`resolve_for_context`.
  * Runtime re-export contract (data-model.md §7): ``ALLOWED_ACTIONS`` is
    a 10-token frozenset and ``REGISTERED_TRIGGERS`` is a strict superset
    of exactly four additional fine-grained tokens.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from charter.activation.activations import (
    ALLOWED_ACTIONS,
    ALLOWED_MISSION_TYPES,
    REGISTERED_TRIGGERS,
    ActivationEntry,
    resolve_for_context,
)
from charter.activation._activation_render import render_activation_stanza


pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Schema shape
# ---------------------------------------------------------------------------


def test_activation_entry_constructs_with_minimal_inputs() -> None:
    entry = ActivationEntry(
        activation_context={"action": "implement"},
        doctrine_pack_id="project",
        artifact_id="caveman-comments",
    )
    assert entry.activation_context == {"action": "implement"}
    assert entry.doctrine_pack_id == "project"
    assert entry.artifact_id == "caveman-comments"
    assert entry.artifact_kind is None


def test_activation_entry_accepts_full_payload() -> None:
    entry = ActivationEntry(
        activation_context={"mission_type": "software-dev", "action": "implement"},
        doctrine_pack_id="very-serious-developers",
        artifact_id="caveman-comments",
        artifact_kind="styleguides",
    )
    assert entry.artifact_kind == "styleguides"


def test_activation_entry_forbids_unknown_top_level_fields() -> None:
    with pytest.raises(ValidationError):
        ActivationEntry(  # type: ignore[call-arg]
            activation_context={"action": "implement"},
            doctrine_pack_id="project",
            artifact_id="caveman-comments",
            extra_field="nope",
        )


# ---------------------------------------------------------------------------
# Vocabulary closure
# ---------------------------------------------------------------------------


def test_invalid_mission_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ActivationEntry(
            activation_context={"mission_type": "dev", "action": "implement"},
            doctrine_pack_id="project",
            artifact_id="x",
        )


def test_invalid_action_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ActivationEntry(
            activation_context={"mission_type": "software-dev", "action": "compile"},
            doctrine_pack_id="project",
            artifact_id="x",
        )


def test_invalid_artifact_kind_is_rejected() -> None:
    """A non-vocabulary ``artifact_kind`` (typo, unknown kind) MUST be
    rejected.  WP05 widened the validator to accept BOTH the plural
    canonical form (``styleguides``) AND the operator-friendly singular
    form (``styleguide``) per the contract example in
    ``contracts/activation-registry.md`` and the FR-007 ATDD fixture —
    but truly bogus values still raise.
    """
    with pytest.raises(ValidationError):
        ActivationEntry(
            activation_context={"action": "implement"},
            doctrine_pack_id="project",
            artifact_id="x",
            artifact_kind="totally-bogus-kind",
        )


def test_singular_artifact_kind_is_accepted_and_normalised() -> None:
    """WP05 widened the validator to accept the operator-friendly
    singular form alongside the canonical plural form.  Internally the
    value is normalised to plural so downstream consumers (renderer,
    YAML emitter, identity-key collision detection) work off a single
    canonical form.  Pinned by the FR-007 ATDD test which uses
    ``artifact_kind: styleguide`` (singular) in the fixture charter.
    """
    entry = ActivationEntry(
        activation_context={"action": "implement"},
        doctrine_pack_id="project",
        artifact_id="x",
        artifact_kind="styleguide",
    )
    assert entry.artifact_kind == "styleguides", (
        "Singular `styleguide` must be normalised to the canonical plural "
        f"`styleguides`; observed: {entry.artifact_kind!r}"
    )


def test_valid_artifact_kinds_are_accepted() -> None:
    """Both the eight canonical plural forms AND their singular aliases
    are accepted by the validator (WP05 widening — see
    ``test_singular_artifact_kind_is_accepted_and_normalised``)."""
    for kind in (
        "directives",
        "tactics",
        "styleguides",
        "toolguides",
        "paradigms",
        "procedures",
        "agent_profiles",
        "mission_step_contracts",
    ):
        ActivationEntry(
            activation_context={"action": "implement"},
            doctrine_pack_id="project",
            artifact_id="x",
            artifact_kind=kind,
        )


# ---------------------------------------------------------------------------
# Resolver / wildcard semantics
# ---------------------------------------------------------------------------


def test_resolver_matches_exact_context() -> None:
    entry = ActivationEntry(
        activation_context={"mission_type": "software-dev", "action": "implement"},
        doctrine_pack_id="project",
        artifact_id="x",
    )
    matched = resolve_for_context(
        [entry], mission_type="software-dev", action="implement"
    )
    assert matched == [entry]


def test_resolver_skips_non_matching_action() -> None:
    entry = ActivationEntry(
        activation_context={"mission_type": "software-dev", "action": "implement"},
        doctrine_pack_id="project",
        artifact_id="x",
    )
    matched = resolve_for_context([entry], mission_type="software-dev", action="review")
    assert matched == []


@pytest.mark.parametrize("wildcard", ["any", "generic"])
def test_resolver_wildcard_tokens_match_every_context(wildcard: str) -> None:
    entry = ActivationEntry(
        activation_context={"mission_type": wildcard, "action": wildcard},
        doctrine_pack_id="project",
        artifact_id="x",
    )
    matched = resolve_for_context(
        [entry], mission_type="documentation", action="review"
    )
    assert matched == [entry]


def test_resolver_absent_slot_is_wildcard() -> None:
    entry = ActivationEntry(
        activation_context={"action": "implement"},
        doctrine_pack_id="project",
        artifact_id="x",
    )
    matched = resolve_for_context(
        [entry], mission_type="documentation", action="implement"
    )
    assert matched == [entry]


# ---------------------------------------------------------------------------
# Runtime re-export contract (data-model.md §7)
# ---------------------------------------------------------------------------


def test_allowed_mission_types_is_a_frozenset() -> None:
    assert isinstance(ALLOWED_MISSION_TYPES, frozenset)


@pytest.mark.parametrize("action", ["charter.interview", "charter.generate", "charter.context"])
def test_charter_loop_action_tokens_are_accepted(action: str) -> None:
    """The charter-loop verbs are the short dotted tokens of data-model.md §7."""
    entry = ActivationEntry(
        activation_context={"action": action},
        doctrine_pack_id="project",
        artifact_id="x",
    )
    assert entry.activation_context == {"action": action}


@pytest.mark.parametrize("action", ["charter.activation.interview", "charter.activation.context"])
def test_module_path_shaped_action_tokens_are_rejected(action: str) -> None:
    """The module-path spellings are not action tokens, and no alias maps them
    (single canonical authority)."""
    with pytest.raises(ValidationError, match="activation_context"):
        ActivationEntry(
            activation_context={"action": action},
            doctrine_pack_id="project",
            artifact_id="x",
        )


@pytest.mark.parametrize(
    ("action", "prose"),
    [
        ("charter.interview", "are about to conduct a charter interview"),
        ("charter.generate", "are about to generate a charter"),
        ("charter.context", "are about to load charter context"),
    ],
)
def test_charter_loop_action_renders_operator_prose(action: str, prose: str) -> None:
    entry = ActivationEntry(
        activation_context={"action": action},
        doctrine_pack_id="project",
        artifact_id="caveman-comments",
        artifact_kind="styleguides",
    )
    rendered = render_activation_stanza(
        [entry], None, mission_type="software-dev", action=action
    )
    assert f"When you {prose}," in rendered


def test_allowed_actions_is_the_canonical_10_token_set() -> None:
    assert isinstance(ALLOWED_ACTIONS, frozenset)
    expected_actions = frozenset(
        {
            "specify",
            "plan",
            "tasks",
            "implement",
            "review",
            "merge",
            "accept",
            "charter.interview",
            "charter.generate",
            "charter.context",
        }
    )
    assert expected_actions == ALLOWED_ACTIONS, (
        "data-model.md §7 pins _ALLOWED_ACTIONS at exactly these 10 tokens; "
        f"observed {sorted(ALLOWED_ACTIONS)}"
    )


def test_registered_triggers_is_superset_of_allowed_actions() -> None:
    assert isinstance(REGISTERED_TRIGGERS, frozenset)
    assert ALLOWED_ACTIONS <= REGISTERED_TRIGGERS, (
        "data-model.md §7 union formula violated — "
        "_REGISTERED_TRIGGERS must contain every _ALLOWED_ACTIONS token."
    )
    extra = REGISTERED_TRIGGERS - ALLOWED_ACTIONS
    assert extra == frozenset(
        {"write_comment", "write_docstring", "rename_identifier", "add_dependency"}
    ), (
        "data-model.md §7 fine-grained suffix drifted; "
        f"observed extras: {sorted(extra)}"
    )
    # Note: data-model.md §7 text says "15 tokens" but its embedded formula
    # yields 10 ∪ 4 = 14. We assert the formula (it is the executable
    # definition); the cross-check landed by WP05 is the final ratchet.
    assert len(REGISTERED_TRIGGERS) == len(ALLOWED_ACTIONS) + 4
