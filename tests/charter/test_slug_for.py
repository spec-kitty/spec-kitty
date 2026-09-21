"""Unit tests for the pure ``slug_for`` slug-authority helper (WP01 / T004).

``slug_for`` is the single producer-side slug derivation. These tests pin:

- directive case-folding + underscore→hyphen normalization,
- non-directive identifier preservation (no case-folding),
- the load-bearing ``quote(..., safe="")`` that collapses a slash-bearing URN
  identity into one safe path component (no provenance-directory path escape),
- determinism, and the directive leading-letter guarantee.

The **equivalence-to-old-inline** table (``test_equivalence_to_old_inline``) is
what makes WP03's extraction *provably* byte-identical to the pre-refactor
inline expression, rather than a post-refactor tautology.
"""

from __future__ import annotations

from urllib.parse import quote

import pytest

from charter.offering.artifact_kinds import slug_for

pytestmark = [pytest.mark.unit]


def _old_inline(kind: str, identifier: str) -> str:
    """The pre-refactor inline expression from ``project_registration.py``.

    Verbatim reproduction — the equivalence guard below compares ``slug_for``
    against this to prove the extraction did not drift.
    """
    return quote(
        identifier.lower().replace("_", "-") if kind == "directive" else identifier,
        safe="",
    )


def test_directive_case_folds_and_kebabs() -> None:
    assert slug_for("directive", "LOVE_THY_ENEMY") == "love-thy-enemy"


def test_non_directive_kebab_id_is_preserved() -> None:
    # Already-kebab id; ``quote`` is a no-op, no case-folding for non-directives.
    assert slug_for("agent_profile", "retrospective-facilitator") == "retrospective-facilitator"


def test_namespaced_id_is_quoted_with_no_path_escape() -> None:
    # The slash is encoded so the identity collapses to one safe path component.
    assert slug_for("agent_profile", "team/ops-responder") == "team%2Fops-responder"


def test_slug_for_is_deterministic() -> None:
    assert slug_for("directive", "DIRECTIVE_025") == slug_for("directive", "DIRECTIVE_025")


def test_directive_slug_never_starts_with_pure_digit_segment() -> None:
    # Directive ids match ``^[A-Z][A-Z0-9_-]*$``; the leading letter guarantees
    # the slug never begins with a pure-digit segment, so a downstream ``NNN-``
    # prefix strip cannot truncate it.
    result = slug_for("directive", "DIRECTIVE_025")
    assert result == "directive-025"
    assert not result.split("-")[0].isdigit()


@pytest.mark.parametrize(
    ("kind", "identifier"),
    [
        ("directive", "DIRECTIVE_025"),  # digit-bearing directive → directive-025
        ("directive", "LOVE_THY_ENEMY"),  # underscore directive
        ("tactic", "bug-fixing-checklist"),  # kebab non-directive
        ("agent_profile", "team/ops-responder"),  # namespaced profile (quoted)
    ],
)
def test_equivalence_to_old_inline(kind: str, identifier: str) -> None:
    assert slug_for(kind, identifier) == _old_inline(kind, identifier)
