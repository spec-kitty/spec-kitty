"""Routing regressions for the documentation domain (#6970).

Non-fakeable form: the registry is populated from the **real shipped**
``packs/built-in/agent_profiles/`` YAML — not a ``MagicMock`` and not the router-test
``FIXTURES_DIR`` stubs — the same pattern ``test_writing_comms_routing.py`` established.
A mock hand-feeds ``role``/``priority`` and would pass regardless of the shipped YAML.

The first test is the issue's own request text: ``spec-kitty dispatch "mark ADR-0068
Accepted and regenerate the ADR index"`` returned ``ROUTER_NO_MATCH`` on ``main``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from specify_cli.invocation.errors import RouterAmbiguityError
from specify_cli.invocation.registry import ProfileRegistry
from specify_cli.invocation.router import ActionRouter

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# Worktree root: tests/specify_cli/invocation/<this file> → parents[3].
REPO_ROOT = Path(__file__).resolve().parents[3]
SHIPPED_PROFILES_DIR = REPO_ROOT / "packs" / "built-in" / "agent_profiles"

# The profile that owns the documentation domain in the shipped catalog.
DOCS_PROFILE_ID = "curator-carla"


@pytest.fixture(scope="module")
def shipped_registry(tmp_path_factory: pytest.TempPathFactory) -> ProfileRegistry:
    """A real ``ProfileRegistry`` populated from the shipped ``packs/built-in`` YAML.

    Module-scoped: building the activation-aware charter service reads the whole doctrine
    tree (several seconds), and the catalog is read-only, so one build serves the module.
    """
    tmp_path = tmp_path_factory.mktemp("shipped-catalog")
    project_profiles_dir = tmp_path / ".kittify" / "profiles"
    project_profiles_dir.mkdir(parents=True)
    shipped = sorted(SHIPPED_PROFILES_DIR.glob("*.agent.yaml"))
    assert shipped, f"No shipped profiles found under {SHIPPED_PROFILES_DIR}"
    for src in shipped:
        shutil.copy(src, project_profiles_dir / src.name)
    return ProfileRegistry(tmp_path)


# ---------------------------------------------------------------------------
# FR-001 / SC-001 — the reported request routes without --profile
# ---------------------------------------------------------------------------


def test_issue_request_routes_to_the_documentation_profile(shipped_registry: ProfileRegistry) -> None:
    """#6970 repro: the exact reported request must route, not refuse."""
    decision = ActionRouter(shipped_registry).route("mark ADR-0068 Accepted and regenerate the ADR index")

    assert decision.profile_id == DOCS_PROFILE_ID
    assert decision.confidence == "domain_keyword"


@pytest.mark.parametrize(
    "request_text",
    [
        "draft the changelog entry for the release",
        "regenerate the readme badges",
        "refresh the handbook for new contributors",
        "polish the tutorial before the release",
    ],
)
def test_other_documentation_nouns_route_to_the_same_profile(shipped_registry: ProfileRegistry, request_text: str) -> None:
    """Every documentation-artifact noun lands on the same domain, not on a refusal."""
    decision = ActionRouter(shipped_registry).route(request_text)

    assert decision.profile_id == DOCS_PROFILE_ID
    assert decision.confidence == "domain_keyword"


# ---------------------------------------------------------------------------
# FR-002 — bare `index` is not a documentation signal (paired positive/negative)
# ---------------------------------------------------------------------------


def test_adr_index_phrase_routes_but_bare_index_does_not(shipped_registry: ProfileRegistry) -> None:
    """One fixture, both directions: `ADR index` routes; a database index refuses."""
    router = ActionRouter(shipped_registry)

    routed = router.route("regenerate the ADR index")
    assert routed.profile_id == DOCS_PROFILE_ID

    with pytest.raises(RouterAmbiguityError) as exc_info:
        router.route("index the invoice table")

    err = exc_info.value
    assert err.error_code == "ROUTER_NO_MATCH"
    assert DOCS_PROFILE_ID not in [candidate["profile_id"] for candidate in err.candidates]


# ---------------------------------------------------------------------------
# FR-003 — declared multi-token signals match on the shipped catalog
# ---------------------------------------------------------------------------


def test_shipped_phrase_keyword_matches_on_the_shipped_catalog(shipped_registry: ProfileRegistry) -> None:
    """`knowledge base` is a declared curator-carla keyword and was dead before #6970."""
    decision = ActionRouter(shipped_registry).route("refresh the knowledge base article")

    assert decision.profile_id == DOCS_PROFILE_ID
    assert decision.confidence == "domain_keyword"


def test_shipped_hyphenated_verb_matches_on_the_shipped_catalog(shipped_registry: ProfileRegistry) -> None:
    """`transcribe-notes` is a declared scribe-sally canonical verb (hyphenated)."""
    decision = ActionRouter(shipped_registry).route("transcribe notes for the standup")

    assert decision.profile_id == "scribe-sally"


# ---------------------------------------------------------------------------
# FR-011 / SC-006 — new signals are fallback tiers: every today-route is unchanged
# ---------------------------------------------------------------------------

# Captured by routing each request on `main` (287a226cfe) against the shipped catalog.
# Every entry that routed there must still route to the same place.
_TODAY_ROUTES: tuple[tuple[str, str, str], ...] = (
    ("review the authentication change", "reviewer-renata", "review"),
    ("release notes for the sprint", "planner-priti", "plan"),
    ("the guide for the spike", "researcher-robbie", "analyze"),
    ("design the onboarding flow", "designer-dagmar", "design"),
    ("research prior art for the sync endpoint", "researcher-robbie", "analyze"),
    ("curate the glossary terms", "doctrine-daphne", "curate"),
    ("validate the schema version", "doctrine-daphne", "curate"),
    ("document the meeting notes", "scribe-sally", "review"),
    ("summarize the incident report", "researcher-robbie", "analyze"),
    ("plan the sprint backlog", "planner-priti", "plan"),
    ("update the ADR index", "generic-agent", "generate"),
    ("investigate the flaky test", "researcher-robbie", "analyze"),
)


@pytest.mark.parametrize(("request_text", "profile_id", "action"), _TODAY_ROUTES)
def test_every_request_that_routed_before_still_routes_the_same_way(shipped_registry: ProfileRegistry, request_text: str, profile_id: str, action: str) -> None:
    """SC-006: the new vocabulary is additive — no captured route moves."""
    decision = ActionRouter(shipped_registry).route(request_text)

    assert (decision.profile_id, decision.action) == (profile_id, action)


@pytest.mark.parametrize(
    ("request_text", "profile_id"),
    [
        # `comms-cleo` declares the phrase `release-notes`; `planner-priti` owns the
        # literal single token `sprint`. The literal token wins (tier 2 before tier 3).
        ("release notes for the sprint", "planner-priti"),
        # `guide` is a documentation alias; `spike` is a literal single-token keyword of
        # researcher-robbie. The literal keyword wins (tier 2 before tier 4).
        ("the guide for the spike", "researcher-robbie"),
        # `update` is generic-agent's folded canonical verb; the docs alias for `adr`
        # must not outrank it.
        ("update the ADR index", "generic-agent"),
    ],
)
def test_literal_keywords_outrank_the_new_fallback_tiers(shipped_registry: ProfileRegistry, request_text: str, profile_id: str) -> None:
    """FR-011: the tier ladder (single token → phrase → docs alias) is what keeps SC-006."""
    decision = ActionRouter(shipped_registry).route(request_text)

    assert decision.profile_id == profile_id


def test_ambiguous_routes_stay_ambiguous(shipped_registry: ProfileRegistry) -> None:
    """A genuine implementer tie is not resolved by the new vocabulary (FR-006 scope)."""
    with pytest.raises(RouterAmbiguityError) as exc_info:
        ActionRouter(shipped_registry).route("fix the unused eslint-disable lint warning")

    err = exc_info.value
    assert err.error_code == "ROUTER_AMBIGUOUS"
    assert len(err.candidates) >= 2
