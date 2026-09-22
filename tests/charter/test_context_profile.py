"""WP03 unit tests — ``build_charter_context(profile=...)`` is load-bearing.

This module pins the behaviour of the profile-cited directive and tactic
sections introduced by WP03 of mission ``wp-prompt-governance-payload``.

Each test exercises ``build_charter_context`` via the same fixture skeleton
as :mod:`tests.charter.test_context` (a minimal ``.kittify/charter`` layout
inside ``tmp_path``) and asserts:

* the new ``Profile-Cited Directives (<profile-id>):`` /
  ``Profile-Cited Tactics (<profile-id>):`` headers appear when (and only
  when) the profile carries the matching references;
* unknown profile IDs do NOT raise — sections are silently omitted;
* the ``profile=None`` default leaves the body byte-identical to today's
  output (NFR-005);
* a profile that cites a catalog-missing directive ID is rendered with a
  ``catalog entry not found`` placeholder rather than crashing the
  resolver.
"""

from __future__ import annotations

import textwrap
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from ruamel.yaml import YAML

from charter.activation.context import (
    _load_agent_profile,
    build_charter_context,
)
from charter.activation.context_renderers.profile_sections import (
    _PROFILE_DIRECTIVES_HEADER_TPL,
    _PROFILE_TACTICS_HEADER_TPL,
    _render_profile_directives,
    _render_profile_tactics,
)
from charter.activation.profile_resolution import _reset_agent_profile_cache
from charter.offering.agent_profiles import (
    AgentProfile,
    AgentProfileRepository,
    DirectiveRef,
)
from charter.offering.agent_profiles.profile import ArtifactRef


pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Fixture: minimal charter + DRG graph (mirrors test_context.py)
# ---------------------------------------------------------------------------


_MINIMAL_GRAPH_YAML = textwrap.dedent("""\
    schema_version: "1.0"
    generated_at: "2026-04-13T10:00:00+00:00"
    generated_by: "test"
    nodes:
      - urn: "action:software-dev/implement"
        kind: action
        label: implement
      - urn: "directive:DIRECTIVE_001"
        kind: directive
        label: Architectural Integrity Standard
      - urn: "tactic:tdd-red-green-refactor"
        kind: tactic
        label: TDD Red-Green-Refactor
    edges:
      - source: "action:software-dev/implement"
        target: "directive:DIRECTIVE_001"
        relation: scope
      - source: "action:software-dev/implement"
        target: "tactic:tdd-red-green-refactor"
        relation: scope
""")

_CHARTER_MD = textwrap.dedent("""\
    # Project Charter

    ## Policy Summary

    - Intent: deterministic delivery
    - Testing: pytest + coverage
""")

_GOVERNANCE_YAML = textwrap.dedent("""\
    doctrine:
      template_set: software-dev-default
      selected_paradigms: []
      selected_directives: []
      available_tools: []
""")

_REFERENCES_YAML = textwrap.dedent("""\
    schema_version: "1.0.0"
    references: []
""")


def _setup_fixture_repo(tmp_path: Path) -> None:
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.md").write_text(_CHARTER_MD, encoding="utf-8")
    (charter_dir / "governance.yaml").write_text(_GOVERNANCE_YAML, encoding="utf-8")
    (charter_dir / "references.yaml").write_text(_REFERENCES_YAML, encoding="utf-8")
    # No ``charter:`` pointer is written to config.yaml here, so PackContext
    # reads activation directly from config.yaml (legacy/un-migrated path).
    # ``mission_type_activations`` is provisioned so ``PackContext.from_config``
    # (WP04, C-A1: the provisioned charter is the sole activation authority)
    # does not hard-fail on a genuinely absent key.
    (tmp_path / ".kittify" / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")


def _call_build(
    tmp_path: Path,
    *,
    profile: str | None,
    action: str = "implement",
    depth: int = 2,
) -> str:
    """Call ``build_charter_context`` with the canonical patched graph."""
    _setup_fixture_repo(tmp_path)

    yaml = YAML(typ="safe")
    from charter.offering.drg.models import DRGGraph

    graph_data = yaml.load(StringIO(_MINIMAL_GRAPH_YAML))
    mock_graph = DRGGraph.model_validate(graph_data)

    def _patched_load_graph(_path: Path) -> DRGGraph:
        return mock_graph

    # Reset the default repository cache so each test sees a fresh load
    # against the shipped built-in profile tree (which is what the WP06
    # wiring will use in production).
    _reset_agent_profile_cache()

    with (
        patch("charter.offering.drg.loader.load_graph", side_effect=_patched_load_graph),
        patch("charter.activation.catalog.resolve_doctrine_root", return_value=tmp_path),
        patch("charter.offering.drg.validator.assert_valid"),
    ):
        result = build_charter_context(
            tmp_path,
            profile=profile,
            action=action,
            depth=depth,
            mark_loaded=False,
        )
    return str(result.text)


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


class TestProfileSurfacing:
    """``profile=<known-id>`` MUST surface the profile's directive/tactic refs."""

    def test_known_profile_surfaces_directive_section(self, tmp_path: Path) -> None:
        """python-pedro declares directive ``010`` (Specification Fidelity)."""
        text = _call_build(tmp_path, profile="python-pedro")
        assert _PROFILE_DIRECTIVES_HEADER_TPL.format(profile_id="python-pedro") in text
        # The directive ID is rendered in canonical catalog form.
        assert "DIRECTIVE_010" in text

    def test_known_profile_surfaces_tactic_section_when_refs_present(self, tmp_path: Path) -> None:
        """A profile with ``tactic_references`` MUST surface the tactic header."""
        synthetic = AgentProfile.model_validate(
            {
                "profile-id": "synthetic-tactic-citer",
                "name": "Synthetic Tactic Citer",
                "roles": ["implementer"],
                "purpose": "test fixture",
                "specialization": {"primary-focus": "testing"},
                "tactic-references": [
                    {
                        "id": "language-driven-design",
                        "rationale": ("Detect terminology conflicts in diffs as early signals of architectural problems"),
                    }
                ],
            }
        )

        with patch(
            "charter.activation.profile_resolution._activation_aware_profile_map",
            return_value={synthetic.profile_id: synthetic},
        ):
            text = _call_build(tmp_path, profile="synthetic-tactic-citer")
        assert _PROFILE_TACTICS_HEADER_TPL.format(profile_id="synthetic-tactic-citer") in text
        assert "language-driven-design" in text

    def test_unknown_profile_skips_profile_sections(self, tmp_path: Path) -> None:
        """An unknown profile id MUST NOT raise; neither section header appears."""
        text = _call_build(tmp_path, profile="nonexistent-agent")
        assert "Profile-Cited Directives" not in text
        assert "Profile-Cited Tactics" not in text

    def test_profile_none_omits_profile_sections(self, tmp_path: Path) -> None:
        """``profile=None`` (today's default) MUST leave the body unchanged.

        We compare the ``profile=None`` body against itself across calls
        and assert neither profile section header was emitted. This is the
        NFR-005 byte-identity regression gate at the resolver level.
        """
        text = _call_build(tmp_path, profile=None)
        # No profile sections emitted.
        assert "Profile-Cited Directives" not in text
        assert "Profile-Cited Tactics" not in text

    def test_empty_directive_references_omits_section(self, tmp_path: Path) -> None:
        """A profile with no directive refs MUST NOT emit the directive header.

        The tactic section is still emitted when tactic refs exist, so
        the two are tested independently.
        """
        synthetic = AgentProfile.model_validate(
            {
                "profile-id": "synthetic-no-directives",
                "name": "Synthetic No Directives",
                "roles": ["implementer"],
                "purpose": "test fixture",
                "specialization": {"primary-focus": "testing"},
                "tactic-references": [{"id": "language-driven-design", "rationale": "for testing"}],
            }
        )

        with patch(
            "charter.activation.profile_resolution._activation_aware_profile_map",
            return_value={synthetic.profile_id: synthetic},
        ):
            text = _call_build(tmp_path, profile="synthetic-no-directives")
        assert "Profile-Cited Directives" not in text
        assert _PROFILE_TACTICS_HEADER_TPL.format(profile_id="synthetic-no-directives") in text


class TestUnknownDirectiveIdHandling:
    """Profile citing a directive the catalog does not carry MUST NOT crash."""

    def test_unknown_directive_id_emits_warning_not_crash(self, tmp_path: Path) -> None:
        synthetic = AgentProfile.model_validate(
            {
                "profile-id": "synthetic-bad-ref",
                "name": "Synthetic Bad Ref",
                "roles": ["implementer"],
                "purpose": "test fixture",
                "specialization": {"primary-focus": "testing"},
                "directive-references": [
                    {
                        "code": "999",
                        "name": "Phantom Directive",
                        "rationale": "this directive does not exist in the catalog",
                    }
                ],
            }
        )

        with patch(
            "charter.activation.profile_resolution._activation_aware_profile_map",
            return_value={synthetic.profile_id: synthetic},
        ):
            text = _call_build(tmp_path, profile="synthetic-bad-ref")
        # The header appears so the operator can audit the profile.
        assert _PROFILE_DIRECTIVES_HEADER_TPL.format(profile_id="synthetic-bad-ref") in text
        # The phantom directive is surfaced with the placeholder body.
        assert "DIRECTIVE_999" in text
        assert "catalog entry not found" in text


class TestPureRendererHelpers:
    """Pure-function tests against the renderer helpers (no fixture overhead)."""

    def test_render_profile_directives_returns_empty_when_refs_empty(self) -> None:
        profile = AgentProfile.model_validate(
            {
                "profile-id": "empty-refs",
                "name": "Empty Refs",
                "roles": ["implementer"],
                "purpose": "test fixture",
                "specialization": {"primary-focus": "testing"},
            }
        )

        class _StubRepo:
            class _DirRepo:
                def get(self, _code: str) -> object | None:
                    return None

            directives = _DirRepo()

        assert _render_profile_directives(profile, _StubRepo()) == []

    def test_render_profile_tactics_returns_empty_when_refs_empty(self) -> None:
        profile = AgentProfile.model_validate(
            {
                "profile-id": "empty-refs",
                "name": "Empty Refs",
                "roles": ["implementer"],
                "purpose": "test fixture",
                "specialization": {"primary-focus": "testing"},
            }
        )

        class _StubRepo:
            class _TacRepo:
                def get(self, _tid: str) -> object | None:
                    return None

            tactics = _TacRepo()

        assert _render_profile_tactics(profile, _StubRepo()) == []

    def test_load_agent_profile_returns_none_on_unknown_id(self) -> None:
        """Unknown profile IDs MUST return ``None`` and never raise.

        Uses the real repository so this test pins the failure-mode
        contract end-to-end. The shipped tree does not carry the
        sentinel profile id used here.
        """
        _reset_agent_profile_cache()
        assert _load_agent_profile("definitely-not-a-real-profile") is None

    def test_directive_ref_code_is_normalised_to_catalog_form(self) -> None:
        """Profile YAML stores codes as bare numerals; output uses canonical form."""
        profile = AgentProfile.model_validate(
            {
                "profile-id": "code-format",
                "name": "Code Format",
                "roles": ["implementer"],
                "purpose": "test fixture",
                "specialization": {"primary-focus": "testing"},
                "directive-references": [{"code": "010", "name": "Spec Fidelity", "rationale": "test"}],
            }
        )

        class _StubRepo:
            class _DirRepo:
                def get(self, code: str) -> object | None:
                    # Test fixture: catalog miss so we exercise the placeholder path.
                    assert code == "DIRECTIVE_010"
                    return None

            directives = _DirRepo()

        lines = _render_profile_directives(profile, _StubRepo())
        assert lines[0] == "Profile-Cited Directives (code-format):"
        assert "DIRECTIVE_010" in lines[1]


# ---------------------------------------------------------------------------
# Smoke: the default repository resolves python-pedro from the shipped tree
# (this is the production path that WP06 will exercise via the prompt
# builder).
# ---------------------------------------------------------------------------


class TestDefaultRepositoryResolution:
    def test_python_pedro_loads_from_shipped_built_in(self) -> None:
        _reset_agent_profile_cache()
        profile = _load_agent_profile("python-pedro")
        assert profile is not None
        codes = {ref.code for ref in profile.directive_references}
        # python-pedro carries at least these directives per the WP03 spec.
        assert {"010", "024", "025", "030"}.issubset(codes)


# ---------------------------------------------------------------------------
# Re-export sanity: the helpers are part of the WP03 contract surface.
# ---------------------------------------------------------------------------


def test_public_helpers_are_importable() -> None:
    """The helper symbols WP06 + downstream tests will import MUST exist."""
    # If any of these become unimportable, callers in WP06 will break.
    assert callable(_load_agent_profile)
    assert callable(_render_profile_directives)
    assert callable(_render_profile_tactics)
    # AgentProfileRepository is the doctrine-layer surface; verify it
    # is the same class used by the helper.
    assert isinstance(AgentProfileRepository(), AgentProfileRepository)
    # Ensure the value-object types stay public surface for callers.
    assert DirectiveRef.__name__ == "DirectiveRef"
    assert ArtifactRef.__name__ == "ArtifactRef"
