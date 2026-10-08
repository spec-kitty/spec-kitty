"""Unit tests for :mod:`charter.activation._activation_render` — the WP05 body of
the activation-stanza renderer.

Coverage (per WP05 T025):

* One entry matching ``(software-dev, implement)`` renders one stanza
  with both qualifiers.
* One entry with only ``action: write_comment`` renders without the
  mission-type qualifier and uses the fine-grained prose.
* One entry with ``mission_type: generic`` renders without the
  mission-type qualifier.
* Two entries matching the same context render two stanzas in
  declaration order (concatenation policy from
  ``contracts/activation-registry.md`` -> "Failure Modes").
* Zero matches -> no ``Selected activations:`` header emitted (empty
  string).
* Wildcard-only entry (``activation_context: {}``) matches every
  context.
"""

from __future__ import annotations

import re

import pytest

from charter.activation._activation_render import render_activation_stanza
from charter.activation.activations import ALLOWED_ACTIONS, ActivationEntry, REGISTERED_TRIGGERS


pytestmark = [pytest.mark.unit]


_CANONICAL_WHEN_DOING_RE = re.compile(
    r"when\s+you\s+(are\s+about\s+to|need\s+to|encounter|introduce|rename|review)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Tiny in-memory DoctrineService stand-in.
# ---------------------------------------------------------------------------


class _FakeRepo:
    """Mimics the ``__contains__`` / ``get`` surface of a doctrine repo."""

    def __init__(self, ids: set[str]) -> None:
        self._ids = ids

    def __contains__(self, key: str) -> bool:
        return key in self._ids

    def get(self, key: str) -> object | None:
        return key if key in self._ids else None


class _FakeService:
    """Doctrine-service stand-in: only exposes the eight kind properties."""

    def __init__(self, *, styleguide_ids: set[str] | None = None) -> None:
        self.styleguides = _FakeRepo(styleguide_ids or set())
        self.directives = _FakeRepo(set())
        self.tactics = _FakeRepo(set())
        self.toolguides = _FakeRepo(set())
        self.paradigms = _FakeRepo(set())
        self.procedures = _FakeRepo(set())
        self.agent_profiles = _FakeRepo(set())
        self.mission_step_contracts = _FakeRepo(set())


@pytest.fixture
def service_with_caveman() -> _FakeService:
    return _FakeService(styleguide_ids={"caveman-comments"})


# ---------------------------------------------------------------------------
# Single-match rendering — both qualifiers
# ---------------------------------------------------------------------------


def test_single_entry_with_both_qualifiers_renders_one_stanza(
    service_with_caveman: _FakeService,
) -> None:
    """An entry pinned to ``(software-dev, implement)`` matching the
    runtime context renders one fetch + when-doing stanza with both
    qualifiers in the prose."""
    entry = ActivationEntry(
        activation_context={"mission_type": "software-dev", "action": "implement"},
        charter_pack_id="project",
        artifact_id="caveman-comments",
        artifact_kind="styleguide",
    )

    rendered = render_activation_stanza(
        [entry],
        service_with_caveman,
        mission_type="software-dev",
        action="implement",
    )

    assert rendered.startswith("Selected activations:"), rendered
    assert (
        "Run: spec-kitty charter context --include styleguide:caveman-comments"
        in rendered
    ), rendered
    assert (
        "When you are about to implement in a software-dev mission" in rendered
    ), rendered


# ---------------------------------------------------------------------------
# Fine-grained action token (write_comment) — qualifier dropped, prose mapped
# ---------------------------------------------------------------------------


def test_entry_with_fine_grained_action_only_renders_without_mission_qualifier(
    service_with_caveman: _FakeService,
) -> None:
    """An entry with only ``action: write_comment`` (no mission_type)
    renders WITHOUT the mission-type qualifier and uses the natural-prose
    label ``"write a code comment"`` (pinned by the FR-007 ATDD test
    ``test_case_1_styleguide_render_includes_trigger_stanza``).
    """
    entry = ActivationEntry(
        activation_context={"action": "write_comment"},
        charter_pack_id="project",
        artifact_id="caveman-comments",
        artifact_kind="styleguide",
    )

    rendered = render_activation_stanza(
        [entry],
        service_with_caveman,
        mission_type="software-dev",
        action="implement",
    )

    assert "Selected activations:" in rendered
    assert "When you are about to write a code comment," in rendered, rendered
    # Mission-type qualifier MUST be dropped (the entry's mission_type is
    # absent, which is wildcard).
    assert "in a software-dev mission" not in rendered, rendered
    assert "in a generic mission" not in rendered, rendered


@pytest.mark.parametrize("declared_action", sorted(REGISTERED_TRIGGERS))
def test_activation_when_clauses_match_canonical_when_doing_contract(
    service_with_caveman: _FakeService,
    declared_action: str,
) -> None:
    """Every activation trigger must emit a fetch stanza whose conditional
    satisfies the canonical prompt-governance ``_WHEN_DOING_RE``.
    """
    runtime_action = (
        declared_action if declared_action in ALLOWED_ACTIONS else "implement"
    )
    entry = ActivationEntry(
        activation_context={"action": declared_action},
        charter_pack_id="project",
        artifact_id="caveman-comments",
        artifact_kind="styleguide",
    )

    rendered = render_activation_stanza(
        [entry],
        service_with_caveman,
        mission_type="software-dev",
        action=runtime_action,
    )

    assert (
        "spec-kitty charter context --include styleguide:caveman-comments" in rendered
    )
    assert _CANONICAL_WHEN_DOING_RE.search(rendered), rendered


# ---------------------------------------------------------------------------
# mission_type = 'generic' wildcard — qualifier dropped
# ---------------------------------------------------------------------------


def test_entry_with_generic_mission_type_renders_without_qualifier(
    service_with_caveman: _FakeService,
) -> None:
    entry = ActivationEntry(
        activation_context={"mission_type": "generic", "action": "implement"},
        charter_pack_id="project",
        artifact_id="caveman-comments",
        artifact_kind="styleguide",
    )

    rendered = render_activation_stanza(
        [entry],
        service_with_caveman,
        mission_type="software-dev",
        action="implement",
    )

    assert "Selected activations:" in rendered
    assert "When you are about to implement," in rendered, rendered
    assert "in a generic mission" not in rendered, rendered
    assert "in a software-dev mission" not in rendered, rendered


# ---------------------------------------------------------------------------
# Multiple matches — concatenation in declaration order
# ---------------------------------------------------------------------------


def test_two_matching_entries_render_two_stanzas_in_declaration_order(
    service_with_caveman: _FakeService,
) -> None:
    """Concatenation policy (``contracts/activation-registry.md`` ->
    "Failure Modes"): two entries matching the same context render two
    stanzas in declaration order.
    """
    first = ActivationEntry(
        activation_context={"action": "implement"},
        charter_pack_id="project",
        artifact_id="caveman-comments",
        artifact_kind="styleguide",
    )
    second = ActivationEntry(
        activation_context={"action": "write_comment"},
        charter_pack_id="project",
        artifact_id="caveman-comments",
        artifact_kind="styleguide",
    )

    rendered = render_activation_stanza(
        [first, second],
        service_with_caveman,
        mission_type="software-dev",
        action="implement",
    )

    assert rendered.count("Selected activations:") == 1, rendered
    # Two distinct stanzas.
    fetch_count = rendered.count(
        "Run: spec-kitty charter context --include styleguide:caveman-comments"
    )
    assert fetch_count == 2, rendered
    # Declaration order: ``implement`` clause appears before
    # ``write a code comment`` clause.
    first_idx = rendered.find("When you are about to implement,")
    second_idx = rendered.find("When you are about to write a code comment,")
    assert first_idx != -1 and second_idx != -1, rendered
    assert first_idx < second_idx, (
        "Stanzas must render in declaration order (concatenation policy). "
        f"Got: implement at {first_idx}, write_comment at {second_idx}.\n"
        f"Rendered:\n{rendered}"
    )


# ---------------------------------------------------------------------------
# Zero matches — empty string (no header emitted)
# ---------------------------------------------------------------------------


def test_zero_matches_returns_empty_string(
    service_with_caveman: _FakeService,
) -> None:
    """If no entry matches, the renderer returns an empty string so the
    caller can skip the leading blank line without emitting a stray
    header."""
    entry = ActivationEntry(
        activation_context={"action": "review"},
        charter_pack_id="project",
        artifact_id="caveman-comments",
        artifact_kind="styleguide",
    )

    rendered = render_activation_stanza(
        [entry],
        service_with_caveman,
        mission_type="software-dev",
        action="implement",
    )

    assert rendered == "", rendered


def test_empty_entries_list_returns_empty_string() -> None:
    rendered = render_activation_stanza(
        [],
        _FakeService(),
        mission_type="software-dev",
        action="implement",
    )
    assert rendered == ""


# ---------------------------------------------------------------------------
# Pure-wildcard entry — matches every context
# ---------------------------------------------------------------------------


def test_wildcard_only_entry_matches_every_context(
    service_with_caveman: _FakeService,
) -> None:
    """An entry with ``activation_context: {}`` (both slots absent ->
    both wildcards) matches every runtime context.  Renders without
    either qualifier and uses the runtime action label.
    """
    entry = ActivationEntry(
        activation_context={},
        charter_pack_id="project",
        artifact_id="caveman-comments",
        artifact_kind="styleguide",
    )

    # Software-dev / implement
    rendered_a = render_activation_stanza(
        [entry],
        service_with_caveman,
        mission_type="software-dev",
        action="implement",
    )
    assert "Selected activations:" in rendered_a
    assert "When you are about to implement," in rendered_a
    assert "in a" not in rendered_a, rendered_a

    # Documentation / review
    rendered_b = render_activation_stanza(
        [entry],
        service_with_caveman,
        mission_type="documentation",
        action="review",
    )
    assert "Selected activations:" in rendered_b
    assert "When you are about to review," in rendered_b
    assert "in a" not in rendered_b, rendered_b


# ---------------------------------------------------------------------------
# Kind inference — artifact_kind omitted, service provides the kind
# ---------------------------------------------------------------------------


def test_kind_inference_via_service_when_artifact_kind_omitted(
    service_with_caveman: _FakeService,
) -> None:
    """When ``artifact_kind`` is omitted the renderer scans the service
    for a repository owning the id and uses that kind in the selector.
    """
    entry = ActivationEntry(
        activation_context={"action": "implement"},
        charter_pack_id="project",
        artifact_id="caveman-comments",
    )

    rendered = render_activation_stanza(
        [entry],
        service_with_caveman,
        mission_type="software-dev",
        action="implement",
    )

    assert (
        "Run: spec-kitty charter context --include styleguide:caveman-comments"
        in rendered
    ), rendered


def test_kind_inference_falls_back_to_artifact_when_service_is_none() -> None:
    """If ``service`` is ``None`` and the entry omits ``artifact_kind``,
    the renderer still emits a stanza but with a generic ``artifact:``
    selector (best-effort, no crash)."""
    entry = ActivationEntry(
        activation_context={"action": "implement"},
        charter_pack_id="project",
        artifact_id="caveman-comments",
    )

    rendered = render_activation_stanza(
        [entry],
        None,
        mission_type="software-dev",
        action="implement",
    )

    assert "Selected activations:" in rendered
    assert "artifact:caveman-comments" in rendered, rendered


# ---------------------------------------------------------------------------
# Singular / plural artifact_kind acceptance
# ---------------------------------------------------------------------------


def test_singular_artifact_kind_renders_singular_selector(
    service_with_caveman: _FakeService,
) -> None:
    """The operator may write ``artifact_kind: styleguide`` (singular);
    the validator normalises internally and the renderer surfaces the
    singular form in the selector — matching the convention used by
    every other fetch stanza (``directive:...``, ``tactic:...``)."""
    entry = ActivationEntry(
        activation_context={"action": "implement"},
        charter_pack_id="project",
        artifact_id="caveman-comments",
        artifact_kind="styleguide",  # singular accepted
    )

    rendered = render_activation_stanza(
        [entry],
        service_with_caveman,
        mission_type="software-dev",
        action="implement",
    )

    assert (
        "Run: spec-kitty charter context --include styleguide:caveman-comments"
        in rendered
    ), rendered


def test_plural_artifact_kind_renders_singular_selector(
    service_with_caveman: _FakeService,
) -> None:
    entry = ActivationEntry(
        activation_context={"action": "implement"},
        charter_pack_id="project",
        artifact_id="caveman-comments",
        artifact_kind="styleguides",  # plural also accepted
    )

    rendered = render_activation_stanza(
        [entry],
        service_with_caveman,
        mission_type="software-dev",
        action="implement",
    )

    assert (
        "Run: spec-kitty charter context --include styleguide:caveman-comments"
        in rendered
    ), rendered
