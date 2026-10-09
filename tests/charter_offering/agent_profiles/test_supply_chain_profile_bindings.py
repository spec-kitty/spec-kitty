"""Profile-binding for the supply-chain security layer (WP05, T018).

Mission ``supply-chain-security-checks-layer-01KZBFBS``. Proves the 7 targeted
profiles (``reviewer-renata``, ``implementer-ivan``, ``node-norris``,
``frontend-freddy``, ``python-pedro``, ``java-jenny``, ``architect-alphonso``)
resolve -- through :meth:`AgentProfileRepository.resolve_profile`, the same
inheritance-aware resolution path production code uses, not a raw YAML read --
with a substantive reference to directive ``051`` (Supply-Chain Install
Safety) and to a tactic that actually carries supply-chain content
(``dependency-hygiene``, extended by WP01, or the new
``supply-chain-install-safety`` tactic). It also proves ``reviewer-renata``
specifically cites the ``adversarial-squad-deployment`` procedure -- the
single owner of the findings-disposition contract -- so that a contested
supply-chain finding can never be dropped silently during review, without
restating the disposition vocabulary (``accepted`` / ``changed`` /
``deferred_with_rationale``) that the procedure already states once.
"""

from __future__ import annotations

import re

import pytest

from charter.offering.agent_profiles.profile import AgentProfile
from charter.offering.agent_profiles.repository import AgentProfileRepository
from charter.offering.directives.repository import DirectiveRepository

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]

_TARGETED_PROFILES = (
    "reviewer-renata",
    "implementer-ivan",
    "node-norris",
    "frontend-freddy",
    "python-pedro",
    "java-jenny",
    "architect-alphonso",
)
_DIRECTIVE_CODE = "051"
_SUPPLY_CHAIN_DIRECTIVE_TITLE = "Supply-Chain Install Safety"
_SUPPLY_CHAIN_TACTIC_IDS = frozenset({"dependency-hygiene", "supply-chain-install-safety"})
_SUPPLY_CHAIN_KEYWORDS = ("supply-chain",)
_DISPOSITION_OWNER_PROCEDURE = "adversarial-squad-deployment"


@pytest.fixture(scope="module")
def repo() -> AgentProfileRepository:
    return AgentProfileRepository()


@pytest.fixture(scope="module")
def directive_repo() -> DirectiveRepository:
    return DirectiveRepository()


class TestTargetedProfilesReferenceSupplyChainDirective:
    """Every targeted profile resolves with a substantive directive-051 reference."""

    @pytest.mark.parametrize("profile_id", _TARGETED_PROFILES)
    def test_resolves_and_references_directive_051(self, repo: AgentProfileRepository, profile_id: str) -> None:
        profile = repo.resolve_profile(profile_id)
        codes = [ref.code for ref in profile.directive_references]
        assert _DIRECTIVE_CODE in codes, f"{profile_id}: expected directive code '{_DIRECTIVE_CODE}' in directive_references, got {codes}"

        matching = next(ref for ref in profile.directive_references if ref.code == _DIRECTIVE_CODE)
        assert matching.rationale.strip(), f"{profile_id}: directive 051 rationale is empty"

    @pytest.mark.parametrize("profile_id", _TARGETED_PROFILES)
    def test_directive_051_resolves_to_supply_chain_title(
        self,
        repo: AgentProfileRepository,
        directive_repo: DirectiveRepository,
        profile_id: str,
    ) -> None:
        """Guard against a repeat of the 047/051 code-vs-directive mismatch:

        resolve the bound code through the real ``DirectiveRepository`` and
        assert the resolved directive's title is actually "Supply-Chain
        Install Safety" -- not merely that some code string matches. A future
        renumber that updates the code but points at the wrong directive
        would still fail this test.
        """
        profile = repo.resolve_profile(profile_id)
        matching = next(ref for ref in profile.directive_references if ref.code == _DIRECTIVE_CODE)

        directive = directive_repo.get(matching.code)
        assert directive is not None, f"{profile_id}: directive code '{matching.code}' did not resolve to a known directive via DirectiveRepository"
        assert directive.title == _SUPPLY_CHAIN_DIRECTIVE_TITLE, (
            f"{profile_id}: directive code '{matching.code}' resolved to '{directive.title}', expected '{_SUPPLY_CHAIN_DIRECTIVE_TITLE}'"
        )


class TestTargetedProfilesReferenceSupplyChainTactic:
    """Every targeted profile resolves with a tactic reference that actually
    carries supply-chain content in its rationale -- not just a coincidental
    id match.
    """

    @pytest.mark.parametrize("profile_id", _TARGETED_PROFILES)
    def test_references_supply_chain_capable_tactic_with_substantive_rationale(self, repo: AgentProfileRepository, profile_id: str) -> None:
        profile = repo.resolve_profile(profile_id)
        candidates = [ref for ref in profile.tactic_references if ref.id in _SUPPLY_CHAIN_TACTIC_IDS]
        assert candidates, f"{profile_id}: expected a tactic reference in {sorted(_SUPPLY_CHAIN_TACTIC_IDS)}, got {[ref.id for ref in profile.tactic_references]}"

        assert any(keyword in ref.rationale.lower() for ref in candidates for keyword in _SUPPLY_CHAIN_KEYWORDS), (
            f"{profile_id}: matched tactic reference(s) {[c.id for c in candidates]} do not mention supply-chain content"
        )


class TestReviewerRenataCarriesAdversarialEvidenceVocabulary:
    """reviewer-renata specifically must cite the disposition-owning procedure --
    not merely reference the directive/tactic like the other 6 profiles, and
    never restate the disposition vocabulary the procedure already owns.
    """

    @pytest.fixture(scope="class")
    def profile(self, repo: AgentProfileRepository) -> AgentProfile:
        return repo.resolve_profile("reviewer-renata")

    def test_disposition_owner_procedure_cited_in_resolved_profile(self, profile: AgentProfile) -> None:
        haystacks: list[str] = []
        haystacks.extend(mode.description for mode in profile.mode_defaults)
        haystacks.extend(ref.rationale for ref in profile.tactic_references)
        haystacks.extend(ref.rationale for ref in profile.directive_references)
        combined = "\n".join(haystacks).lower()

        assert _DISPOSITION_OWNER_PROCEDURE in combined, (
            f"reviewer-renata: expected a citation of the "
            f"{_DISPOSITION_OWNER_PROCEDURE!r} procedure across resolved "
            "mode-defaults/tactic-references/directive-references"
        )

    def test_disposition_obligation_stated_not_just_pointed_to(self, profile: AgentProfile) -> None:
        """A bare citation of adversarial-squad-deployment is not enough: the
        served text must itself state the obligation -- every contested
        finding gets a recorded disposition and is never dropped silently --
        so an operator reading renata's profile (without also opening the
        procedure doc) still sees the binding rule. Regression guard for a
        rewrite that swaps the obligation sentence for a bare pointer."""
        haystacks: list[str] = []
        haystacks.extend(mode.description for mode in profile.mode_defaults)
        haystacks.extend(ref.rationale for ref in profile.tactic_references)
        haystacks.extend(ref.rationale for ref in profile.directive_references)
        combined = "\n".join(haystacks).lower()

        assert "disposition" in combined, "reviewer-renata: expected the served text to say 'disposition', not just cite the owning procedure"
        assert re.search(r"never\b.{0,40}\b(dropped?|drop)\b.{0,20}\bsilently\b", combined) or re.search(r"\brecorded\b.{0,60}\bdisposition\b", combined), (
            "reviewer-renata: expected the served text to state the obligation in "
            "meaning -- 'never dropped silently' or 'recorded disposition' -- not "
            "merely point at the procedure that owns it"
        )

    def test_no_restatement_of_owned_disposition_vocabulary(self, profile: AgentProfile) -> None:
        """The disposition vocabulary (accepted/changed/
        deferred_with_rationale) is owned once by adversarial-squad-deployment.
        reviewer-renata must reference the procedure, not restate the three
        terms as if it were an independent source of truth."""
        haystacks: list[str] = []
        haystacks.extend(mode.description for mode in profile.mode_defaults)
        haystacks.extend(ref.rationale for ref in profile.tactic_references)
        haystacks.extend(ref.rationale for ref in profile.directive_references)
        combined = "\n".join(haystacks).lower()

        restated = [term for term in ("accepted", "changed", "deferred_with_rationale") if term in combined]
        assert not restated, f"reviewer-renata: restates disposition term(s) {restated} instead of citing the {_DISPOSITION_OWNER_PROCEDURE!r} procedure"

    def test_adversarial_squad_deployment_binding_present_on_tactic_reference(self, profile: AgentProfile) -> None:
        """The adversarial-evidence-disposition binding is re-homed onto a
        canonical reference rationale.

        Mission doctrine-drg-silent-drop-boundary-01M0PE7E retired the
        ``context-sources.additional`` surface where this binding used to live.
        It is NOT silently dropped: the ``supply-chain-install-safety``
        tactic-reference rationale names the ``adversarial-squad-deployment``
        procedure explicitly, which this test now pins.
        """
        rationales = "\n".join(ref.rationale for ref in profile.tactic_references).lower()
        assert _DISPOSITION_OWNER_PROCEDURE in rationales, (
            "reviewer-renata: expected the adversarial-squad-deployment "
            "procedure citation to survive on a tactic-reference rationale "
            "after the context-sources consolidation"
        )
