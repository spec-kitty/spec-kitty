"""Tests for ActionRouter — deterministic request → (profile_id, action) routing.

ADR-3 (Option A): pure function, no I/O, no LLM call, no network.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.invocation.errors import RouterAmbiguityError

if TYPE_CHECKING:  # EXP-side typing adaptation (PR #1066): annotation-only import
    from specify_cli.invocation.registry import ProfileRegistry

from specify_cli.invocation.router import (
    CANONICAL_VERB_MAP,
    STOP_WORDS,
    ActionRouter,
    ActionRouterPlugin,
    RouterDecision,
    _normalize_tokens,
)

# ---------------------------------------------------------------------------
# Fixtures: local profiles directory
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "profiles"


def _make_registry(tmp_path: Path, profiles: list[str] | None = None) -> ProfileRegistry:
    """Build a ProfileRegistry from the fixture profiles directory.

    Args:
        tmp_path: pytest tmp_path fixture.
        profiles: Optional list of fixture yaml stems (e.g. ['implementer', 'reviewer']).
                  If None, copy all *.agent.yaml files from FIXTURES_DIR.
    """
    from specify_cli.invocation.registry import ProfileRegistry

    profiles_dir = tmp_path / ".kittify" / "profiles"
    profiles_dir.mkdir(parents=True)

    if profiles is None:
        files = list(FIXTURES_DIR.glob("*.agent.yaml"))
    else:
        files = [FIXTURES_DIR / f"{name}.agent.yaml" for name in profiles]

    for f in files:
        if f.exists():
            shutil.copy(f, profiles_dir / f.name)

    return ProfileRegistry(tmp_path)


def _make_mock_registry(profile_specs: list[dict[str, Any]]) -> MagicMock:
    """Build a lightweight mock ProfileRegistry returning synthetic profiles.

    Each dict in *profile_specs* should have:
        profile_id, role_value, routing_priority, domain_keywords (list)

    This bypasses the shipped-profile merge issue for pure unit tests.
    """
    from charter.offering.agent_profiles.profile import Role

    mock_profiles = []
    for spec in profile_specs:
        p = MagicMock()
        p.profile_id = spec["profile_id"]
        p.role = Role(spec["role_value"])
        p.routing_priority = spec.get("routing_priority", 50)

        sc = MagicMock()
        sc.domain_keywords = spec.get("domain_keywords", [])
        p.specialization_context = sc

        collab = MagicMock()
        collab.canonical_verbs = spec.get("collab_verbs", [])
        p.collaboration = collab

        mock_profiles.append(p)

    registry = MagicMock()
    registry.list_all.return_value = mock_profiles

    def _get(pid: str):
        return next((p for p in mock_profiles if p.profile_id == pid), None)

    def _resolve(pid: str):
        from specify_cli.invocation.errors import ProfileNotFoundError

        profile = _get(pid)
        if profile is None:
            raise ProfileNotFoundError(pid, [p.profile_id for p in mock_profiles])
        return profile

    registry.get.side_effect = _get
    registry.resolve.side_effect = _resolve
    return registry


# ---------------------------------------------------------------------------
# ADR-3 entry gate: document must exist and contain required text
# ---------------------------------------------------------------------------


def test_adr3_document_exists() -> None:
    """ADR-3 document is committed — required entry gate for WP02 review."""
    # The path is relative to the main repo root, not the worktree.
    # Try worktree-relative first, then go up two directories (worktree → repo root).
    here = Path(__file__).parent

    # Walk up until we find the kitty-specs directory
    search = here
    for _ in range(10):
        candidate = search / "kitty-specs" / "profile-invocation-runtime-audit-trail-01KPQRX2" / "adr-3-deterministic-action-router.md"
        if candidate.exists():
            adr_path = candidate
            break
        search = search.parent
    else:
        pytest.fail(
            "ADR-3 document not found under kitty-specs/profile-invocation-runtime-audit-trail-01KPQRX2/"
            " — searched from repo root upward"
        )

    content = adr_path.read_text(encoding="utf-8")
    assert "Option A" in content, "ADR-3 must document Option A as the accepted decision"
    assert "no lm" in content.lower() or "no llm" in content.lower() or "no external" in content.lower(), (
        "ADR-3 must document that no LLM call is made in the routing path"
    )


# ---------------------------------------------------------------------------
# Unit tests: _normalize_tokens
# ---------------------------------------------------------------------------


class TestNormalizeTokens:
    def test_lowercases_and_splits(self) -> None:
        result = _normalize_tokens("Implement the Feature")
        assert "implement" in result
        assert "feature" in result
        assert "the" not in result  # stop-word

    def test_strips_stop_words(self) -> None:
        tokens = _normalize_tokens("please do an implement")
        assert "please" not in tokens
        assert "an" not in tokens
        assert "implement" in tokens

    def test_handles_punctuation(self) -> None:
        tokens = _normalize_tokens("fix: the auth-bug now")
        assert "fix" in tokens
        assert "auth" in tokens
        assert "bug" in tokens

    def test_empty_string(self) -> None:
        assert _normalize_tokens("") == []


# ---------------------------------------------------------------------------
# Unit tests: CANONICAL_VERB_MAP coverage
# ---------------------------------------------------------------------------


class TestCanonicalVerbMap:
    def test_implement_maps_to_implementer_role(self) -> None:
        from charter.offering.agent_profiles.profile import Role

        action, role = CANONICAL_VERB_MAP["implement"]
        assert action == "implement"
        assert role == Role.IMPLEMENTER

    def test_review_maps_to_reviewer_role(self) -> None:
        from charter.offering.agent_profiles.profile import Role

        action, role = CANONICAL_VERB_MAP["review"]
        assert action == "review"
        assert role == Role.REVIEWER

    def test_plan_maps_to_planner_role(self) -> None:
        from charter.offering.agent_profiles.profile import Role

        action, role = CANONICAL_VERB_MAP["plan"]
        assert action == "plan"
        assert role == Role.PLANNER

    def test_fix_maps_to_implementer_role(self) -> None:
        from charter.offering.agent_profiles.profile import Role

        action, role = CANONICAL_VERB_MAP["fix"]
        assert action == "implement"
        assert role == Role.IMPLEMENTER

    def test_no_lm_import_in_module(self) -> None:
        """Router module must not import any LLM client library."""
        import specify_cli.invocation.router as router_mod

        source = Path(router_mod.__file__).read_text(encoding="utf-8")
        for forbidden in ("import anthropic", "import openai", "import httpx", "from anthropic"):
            assert forbidden not in source, f"LLM import found in router.py: {forbidden}"


# ---------------------------------------------------------------------------
# Table-driven success cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "request_text,profile_hint,expected_profile,expected_action,expected_confidence",
    [
        # Case 1: Explicit hint bypasses all routing logic
        ("fix the auth bug", "implementer-fixture", "implementer-fixture", "implement", "exact"),
        # Case 2: Canonical verb match — "implement" → IMPLEMENTER
        ("implement the payment module", None, "implementer-fixture", "implement", "canonical_verb"),
        # Case 3: Canonical verb match — "review" → REVIEWER
        ("review WP03", None, "reviewer-fixture", "review", "canonical_verb"),
        # Case 4: "build" maps to IMPLEMENTER canonical verb
        ("build something for code quality", None, "implementer-fixture", "implement", "canonical_verb"),
        # Case 5: Stop-word stripping — "please do an implement" → "implement" token remains
        ("please do an implement", None, "implementer-fixture", "implement", "canonical_verb"),
    ],
)
def test_router_success(
    request_text: str,
    profile_hint: str | None,
    expected_profile: str,
    expected_action: str,
    expected_confidence: str,
) -> None:
    """Router returns correct RouterDecision for unambiguous inputs."""
    # Use a mock registry with only two profiles to avoid ambiguity
    registry = _make_mock_registry([
        {
            "profile_id": "implementer-fixture",
            "role_value": "implementer",
            "routing_priority": 50,
            "domain_keywords": ["implement", "build", "code"],
        },
        {
            "profile_id": "reviewer-fixture",
            "role_value": "reviewer",
            "routing_priority": 50,
            "domain_keywords": ["review", "audit", "assess"],
        },
    ])

    router = ActionRouter(registry)
    decision = router.route(request_text, profile_hint=profile_hint)

    assert isinstance(decision, RouterDecision)
    assert decision.profile_id == expected_profile
    assert decision.action == expected_action
    assert decision.confidence == expected_confidence


# ---------------------------------------------------------------------------
# Ambiguity case: two profiles with equal priority and overlapping verbs
# ---------------------------------------------------------------------------


def test_router_ambiguity_two_profiles_same_score() -> None:
    """Two profiles with equal routing_priority and overlapping verbs → ROUTER_AMBIGUOUS."""
    registry = _make_mock_registry([
        {
            "profile_id": "implementer-a",
            "role_value": "implementer",
            "routing_priority": 50,  # same priority
            "domain_keywords": [],
        },
        {
            "profile_id": "implementer-b",
            "role_value": "implementer",
            "routing_priority": 50,  # same priority
            "domain_keywords": [],
        },
    ])

    router = ActionRouter(registry)
    with pytest.raises(RouterAmbiguityError) as exc_info:
        router.route("implement the feature")

    err = exc_info.value
    assert err.error_code == "ROUTER_AMBIGUOUS"
    candidate_ids = [c["profile_id"] for c in err.candidates]
    assert "implementer-a" in candidate_ids
    assert "implementer-b" in candidate_ids


# ---------------------------------------------------------------------------
# No match: vague request with no canonical verbs or domain keywords
# ---------------------------------------------------------------------------


def test_router_no_match_vague_request() -> None:
    """'help me' → ROUTER_NO_MATCH (no canonical verb, no keyword)."""
    registry = _make_mock_registry([
        {
            "profile_id": "implementer-fixture",
            "role_value": "implementer",
            "routing_priority": 50,
            "domain_keywords": [],
        },
    ])

    router = ActionRouter(registry)
    with pytest.raises(RouterAmbiguityError) as exc_info:
        router.route("help me")

    assert exc_info.value.error_code == "ROUTER_NO_MATCH"


def test_router_no_match_empty_catalog_suggestion_names_activation() -> None:
    """#4114: an empty catalog suggests charter activation, not synthesis.

    Built-ins always ship, so an empty catalog means the activation gate
    admitted nothing — the remedy is ``charter activate agent-profile``, and
    the suggestion must say so (the pre-#4114 "Run 'spec-kitty charter
    synthesize'" text pointed at a repair that does not address activation).
    """
    registry = _make_mock_registry([])

    router = ActionRouter(registry)
    with pytest.raises(RouterAmbiguityError) as exc_info:
        router.route("Implement the tax module")

    err = exc_info.value
    assert err.error_code == "ROUTER_NO_MATCH"
    assert "charter activate agent-profile" in err.suggestion
    assert "charter synthesize" not in err.suggestion


# ---------------------------------------------------------------------------
# Missing profile hint → PROFILE_NOT_FOUND
# ---------------------------------------------------------------------------


def test_router_missing_profile_hint() -> None:
    """profile_hint='nonexistent' → RouterAmbiguityError(PROFILE_NOT_FOUND)."""
    registry = _make_mock_registry([
        {
            "profile_id": "implementer-fixture",
            "role_value": "implementer",
            "routing_priority": 50,
            "domain_keywords": [],
        },
    ])

    router = ActionRouter(registry)
    with pytest.raises(RouterAmbiguityError) as exc_info:
        router.route("implement something", profile_hint="nonexistent-profile")

    assert exc_info.value.error_code == "PROFILE_NOT_FOUND"


# ---------------------------------------------------------------------------
# Priority tiebreaker: higher routing_priority wins
# ---------------------------------------------------------------------------


def test_router_priority_tiebreaker_selects_higher_priority() -> None:
    """When two profiles match the same verb, the one with higher routing_priority wins."""
    registry = _make_mock_registry([
        {
            "profile_id": "implementer-low",
            "role_value": "implementer",
            "routing_priority": 10,
            "domain_keywords": [],
        },
        {
            "profile_id": "implementer-high",
            "role_value": "implementer",
            "routing_priority": 80,
            "domain_keywords": [],
        },
    ])

    router = ActionRouter(registry)
    decision = router.route("implement the feature")

    assert decision.profile_id == "implementer-high"
    assert decision.confidence == "canonical_verb"
    assert "routing_priority" in decision.match_reason


# ---------------------------------------------------------------------------
# ActionRouterPlugin: no-op stub
# ---------------------------------------------------------------------------


def test_action_router_plugin_is_noop() -> None:
    """ActionRouterPlugin has no methods in v1 — it is a pure no-op stub."""
    plugin = ActionRouterPlugin()
    # Verify no public methods beyond dunder
    public_methods = [
        m for m in dir(plugin)
        if not m.startswith("_")
    ]
    assert public_methods == [], f"ActionRouterPlugin should have no public methods; got {public_methods}"


# ---------------------------------------------------------------------------
# No LLM call: verify via mock that route() is pure
# ---------------------------------------------------------------------------


def test_router_makes_no_external_calls() -> None:
    """route() must never call any LLM or I/O. Verified by asserting no httpx/anthropic usage."""
    import specify_cli.invocation.router as router_mod

    source = Path(router_mod.__file__).read_text(encoding="utf-8")
    forbidden_imports = ["import anthropic", "from anthropic", "import openai", "from openai"]
    for fi in forbidden_imports:
        assert fi not in source, f"Found forbidden import '{fi}' in router.py"


# ---------------------------------------------------------------------------
# WP2/#3840 (T007) — RouterDecision.alternatives, threaded to dry-run and
# real dispatch (FR-005, SC-003). RED on WP01's final commit: `alternatives`
# does not exist yet on RouterDecision/InvocationPayload -- every assertion
# below fails with TypeError/AttributeError/KeyError until WP02's
# implementation commit lands.
# ---------------------------------------------------------------------------

_COMPACT_CTX = MagicMock()
_COMPACT_CTX.mode = "compact"
_COMPACT_CTX.text = "compact governance context"


def _setup_executor_project(tmp_path: Path) -> Path:
    """Copy the real fixture profiles onto disk.

    ``ProfileInvocationExecutor`` builds its own ``ProfileRegistry`` fresh
    from ``repo_root`` (independent of any mocked router registry), so the
    *winning* candidate's ``profile_id`` must resolve against real files on
    disk for ``invoke()``/``dry_run()`` to succeed past routing. A losing
    candidate's profile_id is never resolved this way (see router.py's
    ``alternatives=`` construction), so it does not need a matching file.
    """
    profiles_dir = tmp_path / ".kittify" / "profiles"
    profiles_dir.mkdir(parents=True)
    for yaml_file in FIXTURES_DIR.glob("*.agent.yaml"):
        shutil.copy(yaml_file, profiles_dir / yaml_file.name)
    return tmp_path


def test_alternatives_empty_on_single_candidate(tmp_path: Path) -> None:
    """A request matching exactly one profile: alternatives == [] on the
    router decision itself, on dry-run, and on real dispatch (SC-003,
    Acceptance Scenario 1) -- an explicit empty list, never None/absent."""
    from specify_cli.invocation.executor import ProfileInvocationExecutor

    registry = _make_mock_registry([
        {
            "profile_id": "implementer-fixture",
            "role_value": "implementer",
            "routing_priority": 50,
            "domain_keywords": [],
        },
    ])
    router = ActionRouter(registry)

    decision = router.route("implement the payment module")
    assert decision.alternatives == []

    project = _setup_executor_project(tmp_path)
    executor = ProfileInvocationExecutor(project, router=router)
    with (
        patch("specify_cli.invocation.executor.build_charter_context", return_value=_COMPACT_CTX),
        patch("specify_cli.invocation.executor.resolve_generic_fallback", return_value=None),
    ):
        dry_payload = executor.dry_run("implement the payment module")
        real_payload = executor.invoke("implement the payment module", actor="test")

    assert dry_payload.alternatives == []
    assert real_payload.alternatives == []


def test_alternatives_empty_on_explicit_profile_hint(tmp_path: Path) -> None:
    """--profile <id> bypasses the router entirely (Level 1): router_confidence
    is "exact" and alternatives is [] on dry-run (FR-008, Acceptance Scenario 2)."""
    from specify_cli.invocation.executor import ProfileInvocationExecutor

    project = _setup_executor_project(tmp_path)
    executor = ProfileInvocationExecutor(project)
    with patch("specify_cli.invocation.executor.build_charter_context", return_value=_COMPACT_CTX):
        payload = executor.dry_run("implement the feature", profile_hint="implementer-fixture")

    assert payload.router_confidence == "exact"
    assert payload.alternatives == []


def test_alternatives_nonempty_on_two_candidate_tiebreak(tmp_path: Path) -> None:
    """A request matching two profiles (one canonical-verb, one domain-keyword,
    so routing_priority decides today, pre-WP03): alternatives is non-empty and
    carries the losing candidate's profile_id/action/confidence/match_reason
    (User Story 2's own Independent Test; SC-003) -- on the router decision
    itself and on dry-run."""
    from specify_cli.invocation.executor import ProfileInvocationExecutor

    registry = _make_mock_registry([
        {
            "profile_id": "implementer-fixture",
            "role_value": "implementer",
            "routing_priority": 80,
            "domain_keywords": [],
        },
        {
            "profile_id": "reviewer-fixture",
            "role_value": "reviewer",
            "routing_priority": 10,
            # "gizmo" is not in CANONICAL_VERB_MAP -- a genuine domain-keyword
            # match, not shadowed by a verb match on this profile's role.
            "domain_keywords": ["gizmo"],
        },
    ])
    router = ActionRouter(registry)

    decision = router.route("implement and gizmo the module")
    assert decision.profile_id == "implementer-fixture"
    assert decision.confidence == "canonical_verb"
    assert len(decision.alternatives) == 1  # the tiebreak must surface exactly one alternative
    alt = decision.alternatives[0]
    assert alt["profile_id"] == "reviewer-fixture"
    assert alt["confidence"] == "domain_keyword"
    assert alt["action"]
    assert alt["match_reason"]

    project = _setup_executor_project(tmp_path)
    executor = ProfileInvocationExecutor(project, router=router)
    with (
        patch("specify_cli.invocation.executor.build_charter_context", return_value=_COMPACT_CTX),
        patch("specify_cli.invocation.executor.resolve_generic_fallback", return_value=None),
    ):
        dry_payload = executor.dry_run("implement and gizmo the module")

    assert dry_payload.profile_id == "implementer-fixture"
    assert len(dry_payload.alternatives) == 1  # the dry-run payload mirrors the one-alternative tiebreak
    assert dry_payload.alternatives[0]["profile_id"] == "reviewer-fixture"


def test_router_ambiguous_candidates_carry_confidence_key() -> None:
    """WP01 fixed the post-tiebreaker ROUTER_AMBIGUOUS raise's candidate-dict
    shape to carry a `confidence` key; this WP's edits to the surrounding
    route() code (alternatives= population) must not regress it -- re-confirms
    it holds, does not re-implement the fix. Also confirms the dry-run
    ambiguous-branch alternatives (built from err.candidates) carry the same
    key (FR-009)."""
    from specify_cli.invocation.executor import build_ambiguous_dry_run_payload

    registry = _make_mock_registry([
        {
            "profile_id": "implementer-a",
            "role_value": "implementer",
            "routing_priority": 50,
            "domain_keywords": [],
        },
        {
            "profile_id": "implementer-b",
            "role_value": "implementer",
            "routing_priority": 50,
            "domain_keywords": [],
        },
    ])
    router = ActionRouter(registry)

    with pytest.raises(RouterAmbiguityError) as exc_info:
        router.route("implement the feature")

    err = exc_info.value
    assert err.error_code == "ROUTER_AMBIGUOUS"
    # PR-TESTS-001 (pre-merge squad, mission dispatch-dry-run-route-only-01M1HKV2):
    # pin the collection to non-empty/exact-size BEFORE the loop below, mirroring
    # test_two_plus_domain_keyword_candidates_tied_priority_still_ambiguous's
    # set-equality guard -- otherwise a future regression that empties
    # err.candidates while keeping error_code == "ROUTER_AMBIGUOUS" would pass
    # this loop vacuously.
    candidate_ids = {c["profile_id"] for c in err.candidates}
    assert candidate_ids == {"implementer-a", "implementer-b"}
    for candidate in err.candidates:
        assert "confidence" in candidate

    dry_run_payload = build_ambiguous_dry_run_payload("implement the feature", err)
    alternatives = dry_run_payload["alternatives"]
    assert isinstance(alternatives, list)
    # Same vacuity guard for the dry-run-payload mirror of err.candidates.
    assert len(alternatives) == 2  # both ambiguous candidates must be listed
    for alt in alternatives:
        assert "confidence" in alt


def test_invocation_payload_to_dry_run_dict_raises_if_alternatives_missing() -> None:
    """T009 step 5: unlike RouterDecision (a real frozen dataclass), nothing
    at the type level stops a construction site from omitting alternatives=
    on InvocationPayload -- to_dry_run_dict()'s explicit fail-fast guard is
    the real backstop. Confirms it actually fires (not just described)."""
    from specify_cli.invocation.executor import InvocationPayload

    payload = InvocationPayload(
        invocation_id="",
        profile_id="implementer-fixture",
        profile_friendly_name="Implementer (fixture)",
        action="implement",
        governance_context_text="compact governance context",
        governance_context_hash="deadbeef01234567",
        governance_context_available=True,
        router_confidence="canonical_verb",
        glossary_observations=None,
        mode_of_work=None,
        recommendation=None,
        empty_charter_fallback=False,
        # alternatives= deliberately omitted -- this is the missed-site case.
    )

    with pytest.raises(RuntimeError, match="alternatives"):
        payload.to_dry_run_dict()


# ---------------------------------------------------------------------------
# WP3/#3840 (T011) -- SK-08 rerank: canonical-verb outranks domain-keyword
# (FR-006). RED on WP02's final commit: today's route() lets routing_priority
# decide across tiers, so a domain-keyword candidate can outrank a
# canonical-verb candidate.
#
# NOTE (operator ruling, narrowing WP03's originally-shipped scope): WP03's
# first implementation also made zero-verb-tier resolution unconditionally
# raise ROUTER_AMBIGUOUS -- including the no-competition case (a request with
# no canonical verb at all, resolving on a unique or priority-ranked
# domain-keyword match). That broke a real shipped profile,
# test_writing_comms_routing.py::test_diagram_as_code_still_routes_to_diagram_daisy,
# and was reverted: SK-08 (SPEC-KITTY-LEDGER.md:2727) and issue #3840 both
# describe only the *competition* case (a domain-keyword candidate outranking
# the request's own verb), not the no-competition case. The tests below
# reflect the narrowed, in-scope behavior: cross-tier verb-beats-keyword
# reranking is fixed (kept); zero-verb-tier resolution falls back to the
# pre-WP03 behavior unchanged (a unique keyword-tier candidate still
# auto-selects, and routing_priority still breaks ties among multiple
# keyword-tier-only candidates -- ROUTER_AMBIGUOUS is reserved for a genuine
# tie at the top priority, exactly as before this fix).
# ---------------------------------------------------------------------------


def test_canonical_verb_beats_domain_keyword_regardless_of_priority() -> None:
    """SC-004 / AC-1: a canonical-verb candidate beats a domain-keyword
    candidate regardless of routing_priority, cross-tier. Today's code lets
    the higher-priority domain-keyword profile ("reviewer-weak-verb", 80)
    outrank the canonical-verb profile ("implementer-low-priority", 10) --
    this is the exact SK-08 misroute. After WP03, the canonical-verb
    candidate always wins."""
    registry = _make_mock_registry([
        {
            "profile_id": "implementer-low-priority",
            "role_value": "implementer",
            "routing_priority": 10,
            "domain_keywords": [],
        },
        {
            "profile_id": "reviewer-weak-verb",
            "role_value": "reviewer",
            "routing_priority": 80,
            # "gizmo" is not in CANONICAL_VERB_MAP -- a genuine domain-keyword
            # match, not shadowed by a verb match on this profile's role.
            "domain_keywords": ["gizmo"],
        },
    ])
    router = ActionRouter(registry)

    decision = router.route("implement and gizmo the module")

    assert decision.profile_id == "implementer-low-priority"
    assert decision.confidence == "canonical_verb"
    assert len(decision.alternatives) == 1
    alt = decision.alternatives[0]
    assert alt["profile_id"] == "reviewer-weak-verb"
    assert alt["confidence"] == "domain_keyword"


def test_lone_domain_keyword_candidate_auto_selects() -> None:
    """Operator ruling (narrowing WP03): a request matching no canonical verb
    for any profile, but exactly one profile's domain keyword -- the
    no-competition case -- still auto-selects that lone candidate, exactly as
    before WP03. This is the direct unit-level counterpart of
    test_writing_comms_routing.py::test_diagram_as_code_still_routes_to_diagram_daisy
    (a real shipped profile relying on this).

    Formerly `test_lone_domain_keyword_candidate_is_ambiguous`, which
    asserted the opposite (ROUTER_AMBIGUOUS) -- that assertion encoded WP03's
    originally-shipped zero-verb-tier-always-ambiguous behavior, which the
    operator ruling reverts for the no-competition case. Inverted rather than
    deleted: it pins the restored behavior at the same mock-registry
    granularity the original regression test used."""
    registry = _make_mock_registry([
        {
            "profile_id": "reviewer-lone-keyword",
            "role_value": "reviewer",
            "routing_priority": 50,
            "domain_keywords": ["gizmo"],
        },
    ])
    router = ActionRouter(registry)

    decision = router.route("gizmo the widget")

    assert decision.profile_id == "reviewer-lone-keyword"
    assert decision.confidence == "domain_keyword"
    assert decision.alternatives == []


def test_lone_domain_keyword_with_explicit_profile_still_works() -> None:
    """AC-3: the same lone-domain-keyword request, with an explicit
    --profile hint, still routes successfully -- the explicit-hint path
    (Level 1) bypasses the candidate-selection logic entirely and is
    unaffected by WP03's rerank."""
    registry = _make_mock_registry([
        {
            "profile_id": "reviewer-lone-keyword",
            "role_value": "reviewer",
            "routing_priority": 50,
            "domain_keywords": ["gizmo"],
        },
    ])
    router = ActionRouter(registry)

    decision = router.route("gizmo the widget", profile_hint="reviewer-lone-keyword")

    assert decision.profile_id == "reviewer-lone-keyword"
    assert decision.confidence == "exact"
    assert decision.alternatives == []


def test_two_plus_domain_keyword_candidates_priority_tiebreak_selects_higher_priority() -> None:
    """Operator ruling (narrowing WP03): zero verb-tier candidates, two
    keyword-tier candidates at different routing_priority values (80 and
    10) -- the no-competition case -- resolves by routing_priority exactly
    as before WP03; the priority-80 candidate wins and the priority-10
    candidate appears in `alternatives`.

    Formerly
    `test_two_plus_domain_keyword_candidates_still_ambiguous_regardless_of_priority_spread`,
    which asserted the opposite (ROUTER_AMBIGUOUS regardless of the priority
    spread) -- that assertion encoded WP03's originally-shipped
    zero-verb-tier-always-ambiguous behavior (FR-007 as originally scoped),
    which the operator ruling reverts for the no-competition case: FR-007's
    scope is now understood to be about the genuinely-tied case, not every
    zero-verb-tier resolution. Inverted rather than deleted: it pins the
    restored routing_priority-tiebreak behavior at the same mock-registry
    granularity the original regression test used. ROUTER_AMBIGUOUS is still
    reserved for a real tie -- see
    test_two_plus_domain_keyword_candidates_tied_priority_still_ambiguous
    below."""
    registry = _make_mock_registry([
        {
            "profile_id": "reviewer-high-priority-keyword",
            "role_value": "reviewer",
            "routing_priority": 80,
            "domain_keywords": ["gizmo"],
        },
        {
            "profile_id": "curator-low-priority-keyword",
            "role_value": "curator",
            "routing_priority": 10,
            "domain_keywords": ["widget"],
        },
    ])
    router = ActionRouter(registry)

    decision = router.route("gizmo and widget stuff")

    assert decision.profile_id == "reviewer-high-priority-keyword"
    assert decision.confidence == "domain_keyword"
    assert "routing_priority" in decision.match_reason
    assert len(decision.alternatives) == 1
    assert decision.alternatives[0]["profile_id"] == "curator-low-priority-keyword"


def test_two_plus_domain_keyword_candidates_tied_priority_still_ambiguous() -> None:
    """Genuine tie among keyword-tier-only candidates (zero verb-tier
    candidates, both at routing_priority=50) still raises ROUTER_AMBIGUOUS --
    unchanged from pre-WP03 behavior. Distinguishes "no competition, priority
    decides" (the test above) from "no competition, still genuinely tied"
    (this test): the operator ruling narrows FR-007 to the latter, not every
    zero-verb-tier resolution."""
    registry = _make_mock_registry([
        {
            "profile_id": "reviewer-tied-keyword",
            "role_value": "reviewer",
            "routing_priority": 50,
            "domain_keywords": ["gizmo"],
        },
        {
            "profile_id": "curator-tied-keyword",
            "role_value": "curator",
            "routing_priority": 50,
            "domain_keywords": ["widget"],
        },
    ])
    router = ActionRouter(registry)

    with pytest.raises(RouterAmbiguityError) as exc_info:
        router.route("gizmo and widget stuff")

    err = exc_info.value
    assert err.error_code == "ROUTER_AMBIGUOUS"
    candidate_ids = {c["profile_id"] for c in err.candidates}
    assert candidate_ids == {"reviewer-tied-keyword", "curator-tied-keyword"}
    for candidate in err.candidates:
        assert "confidence" in candidate


def test_no_op_opened_on_tied_keyword_tier_ambiguous_raise(tmp_path: Path) -> None:
    """Dispatch-level companion to the surviving genuinely-tied-keyword-tier
    ROUTER_AMBIGUOUS raise: running that scenario through
    ProfileInvocationExecutor.invoke() (the real, non-dry-run path) without a
    --profile hint raises RouterAmbiguityError before any kitty-ops/ write --
    no Op opened. invoke() calls self._router.route() before any
    write_started()/write_glossary_observation() call, so a raised
    RouterAmbiguityError here is proof no write occurred. Uses the real
    on-disk fixture profile_ids (reviewer-fixture/implementer-fixture) as the
    mock candidates' profile_id, so a ProfileNotFoundError on a synthetic
    non-existent profile_id can't mask a false pass.

    Formerly `test_no_op_opened_on_new_ambiguous_raise_sites`, whose two
    scenarios (a lone keyword candidate, and two keyword candidates at
    different routing_priority values) both encoded WP03's
    originally-shipped zero-verb-tier-always-ambiguous behavior; the operator
    ruling reverts both to auto-select (see
    test_lone_domain_keyword_candidate_auto_selects and
    test_two_plus_domain_keyword_candidates_priority_tiebreak_selects_higher_priority
    above), so neither scenario raises RouterAmbiguityError any more and the
    "no Op opened" assertion no longer applies to them. Replaced with the one
    scenario that is still genuinely ambiguous after the narrowing: two
    keyword-tier candidates tied at the same routing_priority (zero verb-tier
    candidates, a real tie -- not merely "zero verb-tier candidates
    present")."""
    from specify_cli.invocation.executor import ProfileInvocationExecutor

    project = _setup_executor_project(tmp_path)

    tied_registry = _make_mock_registry([
        {
            "profile_id": "implementer-fixture",
            "role_value": "implementer",
            "routing_priority": 50,
            "domain_keywords": ["gizmo"],
        },
        {
            "profile_id": "reviewer-fixture",
            "role_value": "reviewer",
            "routing_priority": 50,
            "domain_keywords": ["widget"],
        },
    ])
    tied_router = ActionRouter(tied_registry)
    tied_executor = ProfileInvocationExecutor(project, router=tied_router)
    with (
        patch("specify_cli.invocation.executor.build_charter_context", return_value=_COMPACT_CTX),
        patch("specify_cli.invocation.executor.resolve_generic_fallback", return_value=None),
        pytest.raises(RouterAmbiguityError),
    ):
        tied_executor.invoke("gizmo and widget stuff", actor="test")
    assert not (project / "kitty-ops").exists()
