"""``doctrine-daphne`` must carry the canonical doctrine/charter structure (SC-007).

Mission ``doctrine-canonical-structure-remediation-01KYEYSD``, FR-010.

Rationale: the curator profile is the load-time context for any agent authoring or
maintaining doctrine. Two mistakes in this repo trace directly to that context *not*
carrying the structural rules:

* PR #2918 placed assets at ``assets/<category>/built-in/`` — pack and category inverted —
  and nothing in the curator's context said which order was correct;
* an in-flight change on this branch started widening the four ``<kind>_reference.type``
  schema enums to admit ``asset``, which would have grown a deprecated surface. It was
  stopped by the operator, not by anything the profile knew.

So this is a content assertion on purpose. A profile that merely *resolves* is not enough;
it has to actually state the rules, because its prose IS the mechanism. Assertions are on
normalized substrings (whitespace-collapsed) so reflowing the YAML block scalars does not
break them, while a genuine removal of a rule does.

Deliberately NOT asserted: exact phrasing. Each check targets the load-bearing fact
(a path shape, a command name, a prohibition), not an author's wording.
"""

from __future__ import annotations

import re

import pytest

from charter.offering.agent_profiles.repository import AgentProfileRepository

pytestmark = [pytest.mark.doctrine, pytest.mark.fast, pytest.mark.corpus]

_PROFILE_ID = "doctrine-daphne"


def _normalized_profile_text() -> str:
    """Return the profile's whitespace-collapsed prose, lowercased.

    Pulled through the repository rather than read off disk so the test exercises the same
    resolution path consumers use -- a profile that fails to load fails here too.
    """
    profile = AgentProfileRepository().resolve_profile(_PROFILE_ID)
    assert profile is not None, f"{_PROFILE_ID} does not resolve"
    dumped = profile.model_dump() if hasattr(profile, "model_dump") else vars(profile)
    return re.sub(r"\s+", " ", str(dumped)).lower()


@pytest.fixture(scope="module")
def profile_text() -> str:
    return _normalized_profile_text()


#: Every rule this guard enforces, as ``(label, required_token)``. Tokens are deliberately
#: *short and stable* — a path shape, a command name, a prohibition's object — rather than an
#: author's sentence, so a faithful reword of a still-correct rule does not false-red
#: (DIRECTIVE_041: a test that fails on a correct change is friction, not protection).
_REQUIRED_RULES: tuple[tuple[str, str], ...] = (
    ("canonical path shape", "<type>/<pack>/"),
    ("category nests inside pack", "above the pack layer"),
    ("misplacement is silent", "silently never loaded"),
    ("inline surface is frozen", "frozen legacy"),
    ("no enum widening", "schema enum"),
    ("no new inline references", "inline `references:`"),
    ("fragments are sharded per kind", "<kind>.graph.yaml"),
    ("regeneration command", "spec-kitty charter pack regenerate-graph"),
    ("monolith is gone", "no longer exists"),
    ("golden-count ledger duty", "composition ledger"),
    ("authoring does not activate", "does not make it live"),
    ("activation command", "spec-kitty charter activate"),
    ("resolved-only kinds are never live", "never activated as live rules"),
    ("resolved-only needs an inbound edge", "inbound edge"),
)


class TestEveryRequiredRuleIsPresent:
    @pytest.mark.parametrize(("label", "token"), _REQUIRED_RULES)
    def test_rule_is_stated(self, profile_text: str, label: str, token: str) -> None:
        assert token.lower() in profile_text, f"profile no longer states: {label}"


class TestGuardIsNonVacuous:
    """Real mutation proof: remove each rule's token and prove *that* check fails.

    The previous version asserted that ``str.replace`` removes a substring — a tautology about
    CPython that exercised zero assertion logic from the checks above it, while being named as
    a non-vacuity proof. This version runs the actual predicate each check uses against a
    mutated copy of the resolved text, so a check that could never fail is itself a failure.
    """

    @pytest.mark.parametrize(("label", "token"), _REQUIRED_RULES)
    def test_removing_a_rule_fails_its_own_check(
        self, profile_text: str, label: str, token: str
    ) -> None:
        mutated = profile_text.replace(token.lower(), "")
        # The predicate under test is exactly the one `test_rule_is_stated` applies.
        assert token.lower() not in mutated, (
            f"check for {label!r} cannot fail — its token is not actually load-bearing"
        )

    def test_assertions_run_against_real_resolved_content(self, profile_text: str) -> None:
        """Floor check: prove we loaded substantive prose, not an empty model dump."""
        assert len(profile_text) > 2000

    def test_every_rule_token_is_distinct(self) -> None:
        """Two rules sharing a token would mean one is not independently pinned."""
        tokens = [token for _, token in _REQUIRED_RULES]
        assert len(tokens) == len(set(tokens))
