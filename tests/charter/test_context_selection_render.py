"""WP04 unit tests — charter-level global selection renderers.

This module pins the behaviour of the ``_render_selected_<kind>``
helpers introduced by WP04 of mission
``charter-mediated-doctrine-selection-01KRTZCA``.

Coverage (per the WP04 task file → "T021 Unit tests"):

* One-artifact-per-kind: each kind renders its artifact ID + body when
  the budget allows.
* Token-budget overflow: a large body triggers fetch + when-doing
  stanza substitution.
* Org-provenance: a styleguide loaded via the org layer carries
  ``source: org`` in the rendered output.
* Empty selection: no output line emitted (no leading header, no
  trailing artifact section).
* Catalog miss: an ID that the repository does not carry surfaces the
  placeholder body + fetch stanza (no crash).

The renderers are pure functions over a ``ActiveCharterService``-shaped
object; tests stub the repository surface rather than load the real
shipped tree so failures isolate to the renderer logic.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import pytest

import charter.activation.context as context_module
from charter.activation.context import (
    _default_agent_profile_repository,
    _jsonable_artifact_value,
    _load_agent_profile,
    _render_doctrine_artifact_include,
)
from charter.activation.context_renderers.artifact_bodies import (
    _format_full_artifact_payload_body,
    _format_inline_directive_body,
    _format_profile_directive_code,
)
from charter.activation.context_renderers.selection_block import (
    _SELECTED_AGENT_PROFILES_HEADER,
    _SELECTED_MISSION_STEP_CONTRACTS_HEADER,
    _SELECTED_PROCEDURES_HEADER,
    _SELECTED_STYLEGUIDES_HEADER,
    _SELECTED_TOOLGUIDES_HEADER,
    _collect_org_source_map,
    _provenance_suffix,
    _render_selected_agent_profiles,
    _render_selected_mission_step_contracts,
    _render_selected_procedures,
    _render_selected_styleguides,
    _render_selected_toolguides,
    _render_selection_block,
)
from charter.activation.context_renderers.token_budget import _PROFILE_INLINE_BODY_LIMIT_CHARS
from charter.activation.profile_resolution import _reset_agent_profile_cache
from charter.activation.schemas import DoctrineSelectionConfig
from charter.offering.pack_skills.models import PackSkill

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Stub doubles for the ActiveCharterService repositories
# ---------------------------------------------------------------------------


class _StubRepo:
    """Minimal repository stub mirroring :meth:`BaseArtifactRepository.get`."""

    def __init__(
        self,
        items: dict[str, Any] | None = None,
        provenance: dict[str, str] | None = None,
    ) -> None:
        self._items = items or {}
        self._provenance = provenance or {}

    def get(self, item_id: str) -> Any | None:  # noqa: ANN401 — duck-typed
        return self._items.get(item_id)

    def get_provenance(self, item_id: str) -> str | None:
        return self._provenance.get(item_id)


class _StubService:
    """Minimal ActiveCharterService stand-in carrying the 5 selection repos."""

    def __init__(
        self,
        *,
        paradigms: _StubRepo | None = None,
        directives: _StubRepo | None = None,
        tactics: _StubRepo | None = None,
        styleguides: _StubRepo | None = None,
        toolguides: _StubRepo | None = None,
        procedures: _StubRepo | None = None,
        agent_profiles: _StubRepo | None = None,
        mission_step_contracts: _StubRepo | None = None,
        skills: _StubRepo | None = None,
    ) -> None:
        self.paradigms = paradigms or _StubRepo()
        self.directives = directives or _StubRepo()
        self.tactics = tactics or _StubRepo()
        self.styleguides = styleguides or _StubRepo()
        self.toolguides = toolguides or _StubRepo()
        self.procedures = procedures or _StubRepo()
        self.agent_profiles = agent_profiles or _StubRepo()
        self.mission_step_contracts = mission_step_contracts or _StubRepo()
        self.skills = skills or _StubRepo()


class _DummyStyleguide:
    def __init__(self, *, title: str, principles: list[str], scope: str = "code") -> None:
        self.title = title
        self.scope = scope
        self.principles = principles


class _DummyParadigm:
    def __init__(self, *, name: str, summary: str) -> None:
        self.name = name
        self.summary = summary


class _DummyDirective:
    def __init__(self, *, title: str, intent: str) -> None:
        self.title = title
        self.intent = intent


class _DummyTactic:
    def __init__(self, *, name: str, purpose: str, steps: list[Any]) -> None:
        self.name = name
        self.purpose = purpose
        self.steps = steps


class _DummyToolguide:
    def __init__(self, *, title: str, tool: str, summary: str) -> None:
        self.title = title
        self.tool = tool
        self.summary = summary


class _DummyProcedure:
    def __init__(
        self,
        *,
        name: str,
        purpose: str,
        entry: str,
        exit_: str,
        steps: list[Any],
    ) -> None:
        self.name = name
        self.purpose = purpose
        self.entry_condition = entry
        self.exit_condition = exit_
        self.steps = steps


class _DummyStep:
    def __init__(self, *, title: str, id_: str | None = None, description: str = "") -> None:
        self.title = title
        self.id = id_
        self.description = description


class _DummyAgentProfile:
    def __init__(self, *, name: str, purpose: str, roles: list[str]) -> None:
        self.name = name
        self.purpose = purpose
        self.roles = roles


class _DummyContract:
    def __init__(
        self,
        *,
        action: str,
        mission: str,
        steps: list[_DummyStep],
    ) -> None:
        self.action = action
        self.mission = mission
        self.steps = steps


# ---------------------------------------------------------------------------
# Empty-selection contract — no header, no body
# ---------------------------------------------------------------------------


class TestEmptySelection:
    """An empty selection MUST NOT emit a header, body line, or stray block."""

    def test_render_selected_styleguides_returns_empty_when_no_selection(self) -> None:
        assert _render_selected_styleguides([], _StubService()) == []

    def test_render_selected_toolguides_returns_empty_when_no_selection(self) -> None:
        assert _render_selected_toolguides([], _StubService()) == []

    def test_render_selected_procedures_returns_empty_when_no_selection(self) -> None:
        assert _render_selected_procedures([], _StubService()) == []

    def test_render_selected_agent_profiles_returns_empty_when_no_selection(self) -> None:
        assert _render_selected_agent_profiles([], _StubService()) == []

    def test_render_selected_mission_step_contracts_returns_empty_when_no_selection(
        self,
    ) -> None:
        assert _render_selected_mission_step_contracts([], _StubService()) == []

    def test_selection_block_returns_empty_string_when_all_empty(self) -> None:
        selection = DoctrineSelectionConfig()
        assert _render_selection_block(selection, _StubService()) == ""


# ---------------------------------------------------------------------------
# Inline-body rendering (one artifact per kind, budget allows)
# ---------------------------------------------------------------------------


class TestInlineBodyRendering:
    """Each renderer emits the ID + verbatim body when under the budget."""

    def test_styleguide_inline_body(self) -> None:
        sg = _DummyStyleguide(
            title="Caveman Comments",
            principles=["UGG STYLE", "VERBS ONLY"],
        )
        service = _StubService(styleguides=_StubRepo(items={"caveman-comments": sg}))
        lines = _render_selected_styleguides(["caveman-comments"], service)
        joined = "\n".join(lines)
        assert _SELECTED_STYLEGUIDES_HEADER in joined
        assert "caveman-comments" in joined
        assert "Caveman Comments" in joined
        assert "UGG STYLE" in joined
        # No fetch stanza when body fits.
        assert "spec-kitty charter context --include" not in joined

    def test_toolguide_inline_body(self) -> None:
        tg = _DummyToolguide(title="Pytest Runner", tool="pytest", summary="Run the suite.")
        service = _StubService(toolguides=_StubRepo(items={"runner": tg}))
        lines = _render_selected_toolguides(["runner"], service)
        joined = "\n".join(lines)
        assert _SELECTED_TOOLGUIDES_HEADER in joined
        assert "runner" in joined
        assert "Pytest Runner" in joined
        assert "Run the suite." in joined

    def test_procedure_inline_body(self) -> None:
        proc = _DummyProcedure(
            name="Onboarding",
            purpose="Bring a new contributor up to speed.",
            entry="Contributor opens repo",
            exit_="Contributor merges first PR",
            steps=[_DummyStep(title="Clone repo"), _DummyStep(title="Read CONTRIBUTING")],
        )
        service = _StubService(procedures=_StubRepo(items={"onboarding": proc}))
        lines = _render_selected_procedures(["onboarding"], service)
        joined = "\n".join(lines)
        assert _SELECTED_PROCEDURES_HEADER in joined
        assert "onboarding" in joined
        assert "Onboarding" in joined
        assert "Clone repo" in joined

    def test_agent_profile_inline_body(self) -> None:
        ap = _DummyAgentProfile(
            name="Python Pedro",
            purpose="Implement Python work with TDD discipline.",
            roles=["implementer"],
        )
        service = _StubService(agent_profiles=_StubRepo(items={"python-pedro": ap}))
        lines = _render_selected_agent_profiles(["python-pedro"], service)
        joined = "\n".join(lines)
        assert _SELECTED_AGENT_PROFILES_HEADER in joined
        assert "python-pedro" in joined
        assert "Python Pedro" in joined
        assert "implementer" in joined

    def test_mission_step_contract_inline_body(self) -> None:
        contract = _DummyContract(
            action="implement",
            mission="software-dev",
            steps=[_DummyStep(title="t", id_="s1", description="First step")],
        )
        service = _StubService(
            mission_step_contracts=_StubRepo(items={"impl-contract": contract})
        )
        lines = _render_selected_mission_step_contracts(["impl-contract"], service)
        joined = "\n".join(lines)
        assert _SELECTED_MISSION_STEP_CONTRACTS_HEADER in joined
        assert "impl-contract" in joined
        assert "implement" in joined
        assert "s1" in joined


# ---------------------------------------------------------------------------
# Token-budget overflow — body too large triggers fetch + when-doing stanza
# ---------------------------------------------------------------------------


class TestTokenBudgetOverflow:
    """Bodies above ``_PROFILE_INLINE_BODY_LIMIT_CHARS`` collapse to fetch."""

    def test_oversized_styleguide_body_emits_fetch_stanza(self) -> None:
        # Build a styleguide whose principle text alone blows the budget.
        bloat = "X" * (_PROFILE_INLINE_BODY_LIMIT_CHARS + 100)
        sg = _DummyStyleguide(title="Big Styleguide", principles=[bloat])
        service = _StubService(styleguides=_StubRepo(items={"big-sg": sg}))
        lines = _render_selected_styleguides(["big-sg"], service)
        joined = "\n".join(lines)
        assert "big-sg" in joined
        # The body line should NOT appear; the fetch stanza should.
        assert bloat not in joined
        assert "spec-kitty charter context --include styleguide:big-sg" in joined
        assert "When you are about to write a code comment" in joined

    def test_oversized_procedure_body_emits_fetch_stanza(self) -> None:
        # Many steps each rendered as one line — pushes total over budget.
        steps = [_DummyStep(title="X" * 80) for _ in range(60)]
        proc = _DummyProcedure(
            name="Bloated", purpose="bloat", entry="in", exit_="out", steps=steps
        )
        service = _StubService(procedures=_StubRepo(items={"bloated-proc": proc}))
        lines = _render_selected_procedures(["bloated-proc"], service)
        joined = "\n".join(lines)
        assert "spec-kitty charter context --include procedure:bloated-proc" in joined


# ---------------------------------------------------------------------------
# Fetch-selector recovery — emitted selectors must round-trip through --include
# ---------------------------------------------------------------------------


class TestFetchSelectorRecovery:
    """Every selection kind that can emit a fetch stanza is recoverable."""

    def test_malformed_include_selector_fails_closed(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Expected --include selector"):
            context_module.build_charter_context_include(tmp_path, "not-a-selector")

    def test_section_selector_round_trips_through_context_include(
        self,
        tmp_path: Path,
    ) -> None:
        charter_dir = tmp_path / ".kittify" / "charter"
        charter_dir.mkdir(parents=True)
        (charter_dir / "charter.md").write_text(
            "# Project Charter\n\n"
            "## Regression Vigilance\n\n"
            "Consult docs/context before approving a terminology cutover.\n",
            encoding="utf-8",
        )

        text = context_module.build_charter_context_include(
            tmp_path,
            "section:regression-vigilance",
        )

        assert "### Regression Vigilance" in text
        assert "Consult docs/context" in text

    def test_section_selector_fails_closed_without_charter(
        self,
        tmp_path: Path,
    ) -> None:
        with pytest.raises(ValueError, match="No charter.md found"):
            context_module.build_charter_context_include(
                tmp_path,
                "section:regression-vigilance",
            )

    def test_section_selector_resolves_to_honest_placeholder_on_missing_heading(
        self,
        tmp_path: Path,
    ) -> None:
        """A recognized critical slug never dead-ends (FR-010/#3095/#3094/#2552).

        The old contract raised ``ValueError("No charter section found")``
        when a *recognized* critical-section slug (``regression-vigilance``)
        was advertised but the charter did not carry that heading. WP05
        removed that dead-end: the advertised selector now always resolves
        to a usable, non-empty string — an honest placeholder pointing at
        the real authoring surface — instead of raising.
        """
        charter_dir = tmp_path / ".kittify" / "charter"
        charter_dir.mkdir(parents=True)
        (charter_dir / "charter.md").write_text(
            "# Project Charter\n\n## Purpose\n\nNo critical sections.\n",
            encoding="utf-8",
        )

        text = context_module.build_charter_context_include(
            tmp_path,
            "section:regression-vigilance",
        )

        assert isinstance(text, str)
        assert text.strip()
        assert "Regression Vigilance" in text
        assert ".kittify/charter/charter.md" in text

    def test_selected_styleguide_include_recovers_body(self) -> None:
        sg = _DummyStyleguide(title="Caveman", principles=["Prefer concrete names."])
        service = _StubService(styleguides=_StubRepo(items={"caveman-comments": sg}))

        text = _render_doctrine_artifact_include(service, "styleguide", "caveman-comments")

        assert text is not None
        assert "Styleguide caveman-comments: Caveman" in text
        assert "Prefer concrete names." in text

    def test_unknown_doctrine_artifact_include_fails_closed(self) -> None:
        with pytest.raises(ValueError, match="No styleguide found"):
            _render_doctrine_artifact_include(
                _StubService(),
                "styleguide",
                "does-not-exist",
            )

    def test_selected_procedure_include_recovers_body(self) -> None:
        procedure = _DummyProcedure(
            name="Review",
            purpose="keep merge checks honest",
            entry="diff ready",
            exit_="review complete",
            steps=[_DummyStep(title="Run focused tests")],
        )
        service = _StubService(procedures=_StubRepo(items={"review-before-merge": procedure}))

        text = _render_doctrine_artifact_include(
            service, "procedure", "review-before-merge"
        )

        assert text is not None
        assert "Procedure review-before-merge: Review" in text
        assert "Run focused tests" in text

    def test_doctrine_artifact_include_recovers_fields_outside_inline_summary(self) -> None:
        sg = _DummyStyleguide(title="Caveman", principles=["Prefer concrete names."])
        sg.anti_patterns = [
            {"name": "soft recovery", "description": "Do not drop governance."}
        ]
        toolguide = _DummyToolguide(title="Pytest", tool="pytest", summary="Run tests.")
        toolguide.commands = ["pytest tests/charter"]
        procedure = _DummyProcedure(
            name="Review",
            purpose="keep merge checks honest",
            entry="diff ready",
            exit_="review complete",
            steps=[_DummyStep(title="Run focused tests")],
        )
        procedure.anti_patterns = [{"name": "skip repro", "description": "No repro."}]
        profile = _DummyAgentProfile(
            name="Python Pedro",
            purpose="Implement Python work with TDD discipline.",
            roles=["implementer"],
        )
        profile.initialization_declaration = "Acknowledge governance before coding."
        contract_step = _DummyStep(
            title="t",
            id_="s1",
            description="First step",
        )
        contract_step.guidance = "Recover contract guidance."
        contract = _DummyContract(
            action="implement",
            mission="software-dev",
            steps=[contract_step],
        )
        paradigm = _DummyParadigm(name="SPDD", summary="Use structured prompts.")
        paradigm.directive_refs = ["DIRECTIVE_039"]
        ship_skill = PackSkill.model_validate(
            {
                "schema_version": "1.0",
                "id": "ship",
                "title": "Ship",
                "description": "Consolidate the mission.",
                "triggers": ["ship the mission"],
                "form": "wrapper",
                "expands_to": {"target": "builtin:spec-kitty.consolidate"},
            }
        )
        service = _StubService(
            paradigms=_StubRepo(items={"structured-prompt-driven-development": paradigm}),
            styleguides=_StubRepo(items={"caveman-comments": sg}),
            toolguides=_StubRepo(items={"pytest-runner": toolguide}),
            procedures=_StubRepo(items={"review-before-merge": procedure}),
            agent_profiles=_StubRepo(items={"python-pedro": profile}),
            mission_step_contracts=_StubRepo(items={"implement-contract": contract}),
            skills=_StubRepo(items={"ship": ship_skill}),
        )

        cases = (
            ("paradigm", "structured-prompt-driven-development", "DIRECTIVE_039"),
            ("styleguide", "caveman-comments", "Do not drop governance."),
            ("toolguide", "pytest-runner", "pytest tests/charter"),
            ("procedure", "review-before-merge", "No repro."),
            ("agent_profile", "python-pedro", "Acknowledge governance before coding."),
            ("mission_step_contract", "implement-contract", "Recover contract guidance."),
            ("skill", "ship", "builtin:spec-kitty.consolidate"),
        )
        for kind, artifact_id, marker in cases:
            text = _render_doctrine_artifact_include(service, kind, artifact_id)
            assert text is not None
            assert "Full artifact:" in text
            assert marker in text
        # A skill that exists is rendered, not reported as "not found" (#5193).
        assert "Skill ship: Ship" in _render_doctrine_artifact_include(service, "skill", "ship")

    def test_directive_and_tactic_include_recovers_fields_outside_inline_summary(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        directive = _DummyDirective(
            title="Security Baseline",
            intent="Never leak secrets.",
        )
        directive.enforcement = "lenient-adherence"
        directive.explicit_allowances = ["Documented exception marker."]
        step = _DummyStep(title="Map trust boundaries")
        step.description = "Full tactic step marker."
        step.examples = ["Run a concrete abuse-path check."]
        tactic = _DummyTactic(
            name="Threat Model First",
            purpose="Find attacker paths before coding.",
            steps=[step],
        )
        service = _StubService(
            directives=_StubRepo(items={"DIRECTIVE_999": directive}),
            tactics=_StubRepo(items={"threat-model-first": tactic}),
        )
        monkeypatch.setattr(
            context_module,
            "_build_doctrine_service",
            lambda repo_root, org_roots=None: service,
        )

        directive_text = context_module.build_charter_context_include(
            tmp_path,
            "directive:DIRECTIVE_999",
        )
        tactic_text = context_module.build_charter_context_include(
            tmp_path,
            "tactic:threat-model-first",
        )

        assert "Full artifact:" in directive_text
        assert "Documented exception marker." in directive_text
        assert "Full artifact:" in tactic_text
        assert "Run a concrete abuse-path check." in tactic_text

    def test_generic_artifact_selector_recovers_activation_fallback(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        sg = _DummyStyleguide(title="Caveman", principles=["Prefer concrete names."])
        service = _StubService(styleguides=_StubRepo(items={"caveman-comments": sg}))
        monkeypatch.setattr(
            context_module,
            "_build_doctrine_service",
            lambda repo_root, org_roots=None: service,
        )

        text = context_module.build_charter_context_include(
            tmp_path,
            "artifact:caveman-comments",
        )

        assert "Styleguide caveman-comments: Caveman" in text
        assert "Prefer concrete names." in text

    def test_generic_artifact_selector_fails_closed_on_ambiguous_match(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        service = _StubService(
            styleguides=_StubRepo(
                items={"shared-id": _DummyStyleguide(title="Style", principles=["One"])}
            ),
            toolguides=_StubRepo(
                items={
                    "shared-id": _DummyToolguide(
                        title="Tool",
                        tool="pytest",
                        summary="Run tests.",
                    )
                }
            ),
        )
        monkeypatch.setattr(
            context_module,
            "_build_doctrine_service",
            lambda repo_root, org_roots=None: service,
        )

        with pytest.raises(ValueError, match="Ambiguous artifact selector"):
            context_module.build_charter_context_include(
                tmp_path,
                "artifact:shared-id",
            )

    def test_generic_artifact_selector_fails_closed_on_missing_match(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setattr(
            context_module,
            "_build_doctrine_service",
            lambda repo_root, org_roots=None: _StubService(),
        )

        with pytest.raises(ValueError, match="No artifact found"):
            context_module.build_charter_context_include(
                tmp_path,
                "artifact:missing-id",
            )

    def test_unknown_include_kind_fails_closed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setattr(
            context_module,
            "_build_doctrine_service",
            lambda repo_root, org_roots=None: _StubService(),
        )

        # WP17 (FR-034): ``template`` is now a supported kind routed through
        # the canonical ArtifactKind resolver, so an unknown selector kind must
        # use a token that is genuinely outside the vocabulary. The resolver
        # fails closed with the canonical "Unknown artifact kind token" error
        # (no silent fallback) instead of the old per-surface message.
        with pytest.raises(ValueError, match="Unknown artifact kind token"):
            context_module.build_charter_context_include(
                tmp_path,
                "bogus-kind:mission",
            )

    def test_styleguide_selector_round_trips_through_context_include(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        sg = _DummyStyleguide(title="Caveman", principles=["Prefer concrete names."])
        service = _StubService(styleguides=_StubRepo(items={"caveman-comments": sg}))
        monkeypatch.setattr(
            context_module,
            "_build_doctrine_service",
            lambda repo_root, org_roots=None: service,
        )

        text = context_module.build_charter_context_include(
            tmp_path,
            "styleguide:caveman-comments",
        )

        assert "Styleguide caveman-comments: Caveman" in text
        assert "Prefer concrete names." in text

    def test_full_payload_json_conversion_covers_nested_values(self) -> None:
        class _Mode(Enum):
            STRICT = "strict"

        class _Dumpable:
            def model_dump(self, **kwargs: object) -> dict[str, object]:
                return {"kind": "modern", "kwargs": sorted(kwargs)}

        class _LegacyDumpable:
            def model_dump(self) -> dict[str, object]:
                return {"kind": "legacy"}

        payload = {
            "mode": _Mode.STRICT,
            "items": [{"name": "rule", "skip": None}],
            "none": None,
        }

        assert _jsonable_artifact_value(payload) == {
            "mode": "strict",
            "items": [{"name": "rule"}],
        }
        assert _jsonable_artifact_value({"tags": {"beta", "alpha"}}) == {
            "tags": ["alpha", "beta"]
        }
        assert _jsonable_artifact_value(_Dumpable()) == {
            "kind": "modern",
            "kwargs": ["by_alias", "exclude_none", "mode"],
        }
        assert _jsonable_artifact_value(_LegacyDumpable()) == {"kind": "legacy"}
        assert isinstance(_jsonable_artifact_value(object()), str)

    def test_full_payload_empty_scalar_emits_no_payload(self) -> None:
        assert _format_full_artifact_payload_body("scalar") == []

    def test_directive_include_renders_list_fields(self) -> None:
        directive = _DummyDirective(
            title="Security Baseline",
            intent="Never leak secrets.",
        )
        directive.scope = "security-sensitive code"
        directive.procedures = ["Map trust boundaries."]
        directive.integrity_rules = ["Do not hide failures."]
        directive.validation_criteria = ["Focused repro exists."]

        lines = _format_inline_directive_body(directive)

        joined = "\n".join(lines)
        assert "Scope: security-sensitive code" in joined
        assert "Procedures:" in joined
        assert "Map trust boundaries." in joined
        assert "Integrity rules:" in joined
        assert "Validation criteria:" in joined

    def test_profile_lookup_helpers_fail_softly(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        class _BoomRepo:
            def get(self, profile_id: str) -> object:
                raise RuntimeError(profile_id)

        class _EmptyRepo:
            def get(self, profile_id: str) -> None:
                return None

        _reset_agent_profile_cache()
        assert _default_agent_profile_repository() is not None
        _reset_agent_profile_cache()
        monkeypatch.setattr(
            context_module,
            "_default_agent_profile_repository",
            lambda: _BoomRepo(),
        )
        assert _load_agent_profile("missing-profile") is None
        monkeypatch.setattr(
            context_module,
            "_default_agent_profile_repository",
            lambda: _EmptyRepo(),
        )
        assert _load_agent_profile("missing-profile") is None
        assert _format_profile_directive_code("7") == "DIRECTIVE_007"


# ---------------------------------------------------------------------------
# Org-provenance — org-sourced artifacts carry a suffix; project does not
# ---------------------------------------------------------------------------


class TestOrgProvenance:
    """``(source: org, pack: <name>)`` MUST appear ONLY for org-sourced IDs."""

    def test_org_sourced_styleguide_carries_source_suffix(self) -> None:
        sg = _DummyStyleguide(title="Caveman", principles=["UGG"])
        repo = _StubRepo(
            items={"caveman-comments": sg},
            provenance={"caveman-comments": "org"},
        )
        service = _StubService(styleguides=repo)
        org_map = _collect_org_source_map(repo, ["caveman-comments"])
        lines = _render_selected_styleguides(
            ["caveman-comments"], service, org_source_map=org_map
        )
        joined = "\n".join(lines)
        assert "source: org" in joined

    def test_org_source_map_with_pack_name_emits_pack_suffix(self) -> None:
        # Direct check of the suffix helper — the pack-name path collapses
        # to "(source: org, pack: <name>)" when the map carries a pack.
        suffix = _provenance_suffix(
            "caveman-comments", {"caveman-comments": "very-serious-developers"}
        )
        assert suffix == " (source: org, pack: very-serious-developers)"

    def test_project_sourced_styleguide_carries_no_suffix(self) -> None:
        sg = _DummyStyleguide(title="Caveman", principles=["UGG"])
        repo = _StubRepo(
            items={"caveman-comments": sg},
            provenance={"caveman-comments": "project"},
        )
        service = _StubService(styleguides=repo)
        # Project sources are NOT in the org map.
        org_map = _collect_org_source_map(repo, ["caveman-comments"])
        assert org_map == {}
        lines = _render_selected_styleguides(
            ["caveman-comments"], service, org_source_map=org_map
        )
        joined = "\n".join(lines)
        assert "source: org" not in joined
        assert "source: project" not in joined

    def test_builtin_sourced_styleguide_carries_no_suffix(self) -> None:
        sg = _DummyStyleguide(title="Built-in", principles=["BI"])
        repo = _StubRepo(
            items={"builtin-sg": sg},
            provenance={"builtin-sg": "builtin"},
        )
        org_map = _collect_org_source_map(repo, ["builtin-sg"])
        assert org_map == {}


# ---------------------------------------------------------------------------
# Catalog miss — unknown ID does not crash, renders fetch stanza
# ---------------------------------------------------------------------------


class TestCatalogMiss:
    """An ID that the repository does not carry MUST surface a placeholder."""

    def test_unknown_styleguide_id_emits_placeholder_and_fetch(self) -> None:
        service = _StubService(styleguides=_StubRepo(items={}))
        lines = _render_selected_styleguides(["does-not-exist"], service)
        joined = "\n".join(lines)
        assert "does-not-exist" in joined
        assert "catalog entry not found" in joined
        assert "spec-kitty charter context --include styleguide:does-not-exist" in joined


# ---------------------------------------------------------------------------
# Deduplication — same ID twice in a selection renders once
# ---------------------------------------------------------------------------


class TestDeduplication:
    """R-4 mitigation: duplicate IDs in a selection MUST render once."""

    def test_duplicate_styleguide_id_rendered_once(self) -> None:
        sg = _DummyStyleguide(title="Caveman", principles=["UGG"])
        service = _StubService(styleguides=_StubRepo(items={"caveman-comments": sg}))
        lines = _render_selected_styleguides(
            ["caveman-comments", "caveman-comments"], service
        )
        joined = "\n".join(lines)
        # The ID + body should appear exactly once even though it was listed twice.
        assert joined.count("- caveman-comments") == 1


# ---------------------------------------------------------------------------
# Combined block — selected sections compose correctly
# ---------------------------------------------------------------------------


class TestCombinedSelectionBlock:
    """``_render_selection_block`` composes selected sections in fixed order."""

    def test_directives_tactics_and_paradigms_render_from_global_selection(self) -> None:
        paradigm = _DummyParadigm(name="SPDD", summary="Use structured prompts.")
        directive = _DummyDirective(title="Security Baseline", intent="Never leak secrets.")
        tactic = _DummyTactic(
            name="Threat Model First",
            purpose="Find attacker paths before coding.",
            steps=[_DummyStep(title="Map trust boundaries")],
        )
        service = _StubService(
            paradigms=_StubRepo(items={"structured-prompt-driven-development": paradigm}),
            directives=_StubRepo(items={"DIRECTIVE_999": directive}),
            tactics=_StubRepo(items={"threat-model-first": tactic}),
        )
        selection = DoctrineSelectionConfig(
            selected_paradigms=["structured-prompt-driven-development"],
            selected_directives=["DIRECTIVE_999"],
            selected_tactics=["threat-model-first"],
        )

        block = _render_selection_block(selection, service)

        assert "Selected paradigms:" in block
        assert "structured-prompt-driven-development" in block
        assert "Use structured prompts." in block
        assert "Selected directives:" in block
        assert "DIRECTIVE_999" in block
        assert "Never leak secrets." in block
        assert "Selected tactics:" in block
        assert "threat-model-first" in block
        assert "Find attacker paths before coding." in block

    def test_all_five_kinds_appear_in_order(self) -> None:
        sg = _DummyStyleguide(title="SG", principles=["a"])
        tg = _DummyToolguide(title="TG", tool="t", summary="s")
        proc = _DummyProcedure(
            name="P", purpose="p", entry="i", exit_="o", steps=[_DummyStep(title="s")]
        )
        ap = _DummyAgentProfile(name="A", purpose="p", roles=["implementer"])
        contract = _DummyContract(
            action="implement",
            mission="software-dev",
            steps=[_DummyStep(title="t", id_="s1", description="d")],
        )
        service = _StubService(
            styleguides=_StubRepo(items={"sg-id": sg}),
            toolguides=_StubRepo(items={"tg-id": tg}),
            procedures=_StubRepo(items={"proc-id": proc}),
            agent_profiles=_StubRepo(items={"ap-id": ap}),
            mission_step_contracts=_StubRepo(items={"msc-id": contract}),
        )
        selection = DoctrineSelectionConfig(
            selected_styleguides=["sg-id"],
            selected_toolguides=["tg-id"],
            selected_procedures=["proc-id"],
            selected_agent_profiles=["ap-id"],
            selected_mission_step_contracts=["msc-id"],
        )
        block = _render_selection_block(selection, service)
        # Stable section order: styleguides → toolguides → procedures →
        # agent_profiles → mission_step_contracts.
        idx_sg = block.index(_SELECTED_STYLEGUIDES_HEADER)
        idx_tg = block.index(_SELECTED_TOOLGUIDES_HEADER)
        idx_proc = block.index(_SELECTED_PROCEDURES_HEADER)
        idx_ap = block.index(_SELECTED_AGENT_PROFILES_HEADER)
        idx_msc = block.index(_SELECTED_MISSION_STEP_CONTRACTS_HEADER)
        assert idx_sg < idx_tg < idx_proc < idx_ap < idx_msc

    def test_only_populated_kinds_emit_headers(self) -> None:
        sg = _DummyStyleguide(title="SG", principles=["a"])
        service = _StubService(styleguides=_StubRepo(items={"sg-id": sg}))
        selection = DoctrineSelectionConfig(selected_styleguides=["sg-id"])
        block = _render_selection_block(selection, service)
        assert _SELECTED_STYLEGUIDES_HEADER in block
        assert _SELECTED_TOOLGUIDES_HEADER not in block
        assert _SELECTED_PROCEDURES_HEADER not in block
        assert _SELECTED_AGENT_PROFILES_HEADER not in block
        assert _SELECTED_MISSION_STEP_CONTRACTS_HEADER not in block
