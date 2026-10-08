"""Tests for build_charter_context -- DRG-based charter context (T021 + T022)."""

from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from charter.activation.context import (
    CharterContextResult,
    _ActionDoctrineBundle,
    _build_doctrine_service,
    _bundle_root_for_json,
    _project_charter_json_block,
    _project_directive_entries,
    _render_bootstrap_text,
    build_charter_context,
    build_charter_context_json,
)
from charter.activation.context_json import _load_project_directives, _relative_json_path

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Fixtures
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
      - urn: "styleguide:kitty-glossary-writing"
        kind: styleguide
        label: Kitty Glossary Writing
      - urn: "toolguide:efficient-local-tooling"
        kind: toolguide
        label: Efficient Local Tooling
    edges:
      - source: "action:software-dev/implement"
        target: "directive:DIRECTIVE_001"
        relation: scope
      - source: "action:software-dev/implement"
        target: "tactic:tdd-red-green-refactor"
        relation: scope
      - source: "directive:DIRECTIVE_001"
        target: "styleguide:kitty-glossary-writing"
        relation: suggests
      - source: "styleguide:kitty-glossary-writing"
        target: "toolguide:efficient-local-tooling"
        relation: suggests
""")

_CHARTER_MD = textwrap.dedent("""\
    # Project Charter

    ## Policy Summary

    - Intent: deterministic delivery
    - Testing: pytest + coverage
    - Quality: ruff linting
""")

_GOVERNANCE_YAML = textwrap.dedent("""\
    charter:
      template_set: software-dev-default
      selected_paradigms: []
      selected_directives: []
      available_tools: []
""")

# consolidate-charter-bundle (#2773): the reference catalog is the DERIVED
# ``catalog.references`` projection inside the authoritative ``charter.yaml`` —
# the retired ``references.yaml`` is no longer read by ``build_charter_context``.
_CHARTER_YAML = textwrap.dedent("""\
    schema_version: "2.0.0"
    catalog:
      mission: null
      template_set: software-dev-default
      languages: []
      references:
        - id: "USER:PROJECT_PROFILE"
          kind: user_profile
          title: User Project Profile
          local_path: _LIBRARY/user-project-profile.md
    metadata:
      bundle_schema_version: 2
""")


def _setup_fixture_repo(tmp_path: Path) -> None:
    """Create a minimal repo layout for build_charter_context testing."""
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.md").write_text(_CHARTER_MD, encoding="utf-8")
    (charter_dir / "governance.yaml").write_text(_GOVERNANCE_YAML, encoding="utf-8")
    # References are read from charter.yaml's ``catalog.references`` (#2773), not
    # the retired references.yaml — writing charter.yaml here exercises that path.
    (charter_dir / "charter.yaml").write_text(_CHARTER_YAML, encoding="utf-8")
    # No ``charter:`` pointer is written to config.yaml here, so PackContext
    # reads activation directly from config.yaml (legacy/un-migrated path).
    # ``mission_type_activations`` is provisioned so ``PackContext.from_config``
    # (WP04, C-A1: the provisioned charter is the sole activation authority)
    # does not hard-fail on a genuinely absent key.
    (tmp_path / ".kittify" / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )


def _write_graph_fixture(tmp_path: Path) -> None:
    from io import StringIO

    from charter.offering.drg.models import DRGGraph
    from ruamel.yaml import YAML

    yaml = YAML(typ="safe")
    graph_data = yaml.load(StringIO(_MINIMAL_GRAPH_YAML))
    mock_graph = DRGGraph.model_validate(graph_data)

    def patched_load_graph(path: Path) -> DRGGraph:
        return mock_graph

    return patched_load_graph


# ---------------------------------------------------------------------------
# T021: build_charter_context functional tests
# ---------------------------------------------------------------------------


class TestBuildContextV2:
    """Functional tests for the DRG-based context builder."""

    def _call(
        self,
        tmp_path: Path,
        action: str = "implement",
        depth: int = 2,
        profile: str | None = None,
        mark_loaded: bool = True,
    ) -> CharterContextResult:
        """Call build_charter_context with a patched graph loader."""
        _setup_fixture_repo(tmp_path)

        from io import StringIO

        from charter.offering.drg.models import DRGGraph
        from ruamel.yaml import YAML

        yaml = YAML(typ="safe")
        graph_data = yaml.load(StringIO(_MINIMAL_GRAPH_YAML))
        mock_graph = DRGGraph.model_validate(graph_data)

        # Patch the merged-graph seam directly (mission #2680 WP05): the shipped
        # DRG now loads as multiple ``*.graph.yaml`` fragments, so patching the
        # per-file ``load_graph`` would return this fixture once per fragment and
        # ``merge_layers`` would concatenate it into duplicate edges. Replacing
        # ``load_validated_graph`` yields the fixture graph exactly once.
        with (
            patch("charter.activation._drg_helpers.load_validated_graph", return_value=mock_graph),
            patch("charter.activation.catalog.resolve_doctrine_root", return_value=tmp_path),
            patch("charter.offering.drg.validator.assert_valid"),  # fixture may not pass full validation
        ):
            return build_charter_context(
                tmp_path,
                profile=profile,
                action=action,
                depth=depth,
                mark_loaded=mark_loaded,
                # WP04 (#883): the fixture graph is a software-dev graph; the
                # mission type is now declared explicitly rather than inferred
                # from the project-level ``template_set`` proxy (FR-002).
                mission_type="software-dev",
            )

    def test_action_normalized(self, tmp_path: Path) -> None:
        """Action is normalized to lowercase."""
        result = self._call(tmp_path, action="  IMPLEMENT  ")
        assert result.action == "implement"

    def test_mode_is_bootstrap_on_first_load(self, tmp_path: Path) -> None:
        """Mode is 'bootstrap' on first load at depth >= 2."""
        result = self._call(tmp_path)
        assert result.mode == "bootstrap"
        assert result.first_load is True

    def test_mode_is_compact_on_second_load(self, tmp_path: Path) -> None:
        """Mode is 'compact' on second load when depth is state-driven."""
        # First load with depth=None (state decides: first_load -> depth 2)
        _setup_fixture_repo(tmp_path)

        patched_load_graph = _write_graph_fixture(tmp_path)

        with (
            patch("charter.offering.drg.loader.load_graph", side_effect=patched_load_graph),
            patch("charter.activation.catalog.resolve_doctrine_root", return_value=tmp_path),
            patch("charter.offering.drg.validator.assert_valid"),
        ):
            # First load: depth=None -> state decides -> 2 (bootstrap)
            first = build_charter_context(tmp_path, action="implement", depth=None, mark_loaded=True)
            assert first.mode == "bootstrap"
            assert first.first_load is True
            # Second load: depth=None -> state decides -> 1 (compact)
            second = build_charter_context(tmp_path, action="implement", depth=None, mark_loaded=True)
            assert second.mode == "compact"
            assert second.first_load is False

    def test_non_bootstrap_action_returns_compact(self, tmp_path: Path) -> None:
        """Non-bootstrap actions always return compact mode."""
        result = self._call(tmp_path, action="custom-action")
        assert result.mode == "compact"
        assert result.first_load is False

    def test_json_undeclared_action_with_resolved_type_returns_compact(
        self, tmp_path: Path
    ) -> None:
        """AC-2 companion (WP02, #3596, ADR
        2026-08-21-1-charter-gate-predicate-inversion, squad S3).

        Isolates the predicate from type-resolution: ``mission_type`` DOES
        resolve (``software-dev``, matching ``_MINIMAL_GRAPH_YAML``'s only
        node ``action:software-dev/implement``) but the requested action
        (``custom-action``) has no declared ``action:software-dev/custom-action``
        node. The result must still be ``compact`` — proving the gate is
        node-URN membership, not merely "did a type resolve". Exercises the
        ``--json`` entry point (``build_charter_context_json``), the sibling
        surface to ``test_non_bootstrap_action_returns_compact`` above (which
        pins the same invariant on the plain-text entry point) — keep BOTH
        green; this is a companion, not a replacement.
        """
        _setup_fixture_repo(tmp_path)

        from io import StringIO

        from charter.offering.drg.models import DRGGraph
        from ruamel.yaml import YAML

        yaml = YAML(typ="safe")
        graph_data = yaml.load(StringIO(_MINIMAL_GRAPH_YAML))
        mock_graph = DRGGraph.model_validate(graph_data)

        with (
            patch(
                "charter.activation._drg_helpers.load_validated_graph",
                return_value=mock_graph,
            ),
            patch("charter.activation.catalog.resolve_doctrine_root", return_value=tmp_path),
            patch("charter.offering.drg.validator.assert_valid"),
        ):
            payload = build_charter_context_json(
                tmp_path, action="custom-action", mission_type="software-dev"
            )

        assert payload["mode"] == "compact"
        assert payload["directives"] == []

    def test_compact_text_contains_governance_reference_diagnostics(self, tmp_path: Path) -> None:
        """Compact context preserves declared supporting governance docs."""
        _setup_fixture_repo(tmp_path)
        (tmp_path / "spec").mkdir()
        (tmp_path / "spec" / "constitution.md").write_text("# Public Constitution\n", encoding="utf-8")
        # consolidate-charter-bundle (IC-04 / WP04, T028c): the charter.md
        # fenced-YAML -> governance.yaml extraction this fixture used to rely
        # on is retired (sync() no longer scrapes anything); governance is
        # hand-authored directly in charter.yaml now.
        (tmp_path / ".kittify" / "charter" / "charter.yaml").write_text(
            "governance:\n"
            "  charter:\n"
            "    governance_references:\n"
            "      - spec/constitution.md\n",
            encoding="utf-8",
        )

        result = build_charter_context(
            tmp_path,
            action="custom-action",
            mark_loaded=False,
        )

        assert result.mode == "compact"
        assert "Required Governance Reading:" in result.text
        assert "spec/constitution.md" in result.text

    def test_text_contains_charter_context_header(self, tmp_path: Path) -> None:
        """Output text starts with Charter Context header."""
        result = self._call(tmp_path)
        assert "Charter Context (Bootstrap):" in result.text

    def test_text_contains_policy_summary(self, tmp_path: Path) -> None:
        """Output text includes policy summary from charter.md."""
        result = self._call(tmp_path)
        assert "Policy Summary:" in result.text
        assert "deterministic delivery" in result.text

    def test_text_contains_directives_section(self, tmp_path: Path) -> None:
        """Output text includes resolved directives."""
        result = self._call(tmp_path)
        assert "Directives:" in result.text
        assert "DIRECTIVE_001" in result.text

    def test_text_contains_tactics_section(self, tmp_path: Path) -> None:
        """Output text includes resolved tactics."""
        result = self._call(tmp_path)
        assert "Tactics:" in result.text
        assert "tdd-red-green-refactor" in result.text

    def test_text_contains_governance_reference_diagnostics(self, tmp_path: Path) -> None:
        """Declared supporting governance docs appear in rendered context."""
        _setup_fixture_repo(tmp_path)
        (tmp_path / "spec").mkdir()
        (tmp_path / "spec" / "constitution.md").write_text("# Public Constitution\n", encoding="utf-8")
        # consolidate-charter-bundle (IC-04 / WP04, T028c): governance is
        # hand-authored directly in charter.yaml now -- the charter.md
        # fenced-YAML extraction this fixture used to rely on is retired.
        (tmp_path / ".kittify" / "charter" / "charter.yaml").write_text(
            "governance:\n"
            "  charter:\n"
            "    governance_references:\n"
            "      - spec/constitution.md\n"
            "      - docs/missing-governance.md\n",
            encoding="utf-8",
        )

        patched_load_graph = _write_graph_fixture(tmp_path)

        with (
            patch("charter.offering.drg.loader.load_graph", side_effect=patched_load_graph),
            patch("charter.activation.catalog.resolve_doctrine_root", return_value=tmp_path),
            patch("charter.offering.drg.validator.assert_valid"),
        ):
            result = build_charter_context(
                tmp_path,
                action="implement",
                depth=2,
                mark_loaded=False,
            )

        assert "Required Governance Reading:" in result.text
        assert "spec/constitution.md" in result.text
        assert "Missing governance reference docs/missing-governance.md" in result.text

    def test_selected_directive_closure_contributes_action_context(self, tmp_path: Path) -> None:
        """Selected directives contribute their DRG closure even without action-scope edges."""
        _setup_fixture_repo(tmp_path)
        # consolidate-charter-bundle (IC-04 / WP04, T028c): governance is
        # hand-authored directly in charter.yaml now; the retired
        # governance.yaml is never read by load_governance_config.
        (tmp_path / ".kittify" / "charter" / "charter.yaml").write_text(
            textwrap.dedent("""\
                governance:
                  charter:
                    template_set: software-dev-default
                    selected_paradigms: []
                    selected_directives: [DIRECTIVE_039]
                    available_tools: []
            """),
            encoding="utf-8",
        )

        graph_yaml = textwrap.dedent("""\
            schema_version: "1.0"
            generated_at: "2026-04-13T10:00:00+00:00"
            generated_by: "test"
            nodes:
              - urn: "action:software-dev/implement"
                kind: action
                label: implement
              - urn: "directive:DIRECTIVE_039"
                kind: directive
                label: Lynn Cole Engineering Culture
              - urn: "styleguide:boring-code-review"
                kind: styleguide
                label: Boring Code Review
            edges:
              - source: "directive:DIRECTIVE_039"
                target: "styleguide:boring-code-review"
                relation: requires
        """)

        from io import StringIO

        from charter.offering.drg.models import DRGGraph
        from ruamel.yaml import YAML

        yaml = YAML(typ="safe")
        mock_graph = DRGGraph.model_validate(yaml.load(StringIO(graph_yaml)))

        with (
            # WP05 (#2680): patch the merged-graph seam, not per-file load_graph,
            # so the sharded fragment layout does not duplicate the fixture.
            patch("charter.activation._drg_helpers.load_validated_graph", return_value=mock_graph),
            patch("charter.activation.catalog.resolve_doctrine_root", return_value=tmp_path),
            patch("charter.offering.drg.validator.assert_valid"),
            patch("charter.activation.sync.ensure_charter_bundle_fresh", return_value=None),
        ):
            result = build_charter_context(
                tmp_path, action="implement", depth=2, mark_loaded=False,
                mission_type="software-dev",
            )

        assert "DIRECTIVE_039" in result.text
        assert "boring-code-review" in result.text

    def test_org_required_primary_kinds_contribute_to_prompt(self, tmp_path: Path) -> None:
        """Org-required directives, tactics, and paradigms render without project mirroring."""
        _setup_fixture_repo(tmp_path)
        org_pack = tmp_path / "org-pack"
        org_pack.mkdir()
        (org_pack / "org-charter.yaml").write_text(
            textwrap.dedent("""\
                required_directives:
                  - DIRECTIVE_039
                required_tactics:
                  - threat-model-first
                required_paradigms:
                  - structured-prompt-driven-development
            """),
            encoding="utf-8",
        )
        (tmp_path / ".kittify" / "config.yaml").write_text(
            textwrap.dedent(f"""\
                mission_type_activations:
                  - software-dev
                charter_packs:
                  org:
                    packs:
                      - name: security
                        local_path: {org_pack.as_posix()}
            """),
            encoding="utf-8",
        )

        graph_yaml = textwrap.dedent("""\
            schema_version: "1.0"
            generated_at: "2026-04-13T10:00:00+00:00"
            generated_by: "test"
            nodes:
              - urn: "action:software-dev/implement"
                kind: action
                label: implement
              - urn: "directive:DIRECTIVE_039"
                kind: directive
                label: Lynn Cole Engineering Culture
              - urn: "styleguide:boring-code-review"
                kind: styleguide
                label: Boring Code Review
              - urn: "tactic:threat-model-first"
                kind: tactic
                label: Threat Model First
              - urn: "tactic:reasons-canvas-fill"
                kind: tactic
                label: Reasons Canvas Fill
              - urn: "paradigm:structured-prompt-driven-development"
                kind: paradigm
                label: Structured Prompt-Driven Development
            edges:
              - source: "directive:DIRECTIVE_039"
                target: "styleguide:boring-code-review"
                relation: requires
              - source: "paradigm:structured-prompt-driven-development"
                target: "tactic:reasons-canvas-fill"
                relation: requires
        """)

        from io import StringIO

        from charter.offering.drg.models import DRGGraph
        from ruamel.yaml import YAML

        yaml = YAML(typ="safe")
        mock_graph = DRGGraph.model_validate(yaml.load(StringIO(graph_yaml)))

        with (
            patch("charter.activation._drg_helpers.load_validated_graph", return_value=mock_graph),
            patch("charter.activation.catalog.resolve_doctrine_root", return_value=tmp_path),
            patch("charter.offering.drg.validator.assert_valid"),
            patch("charter.activation.sync.ensure_charter_bundle_fresh", return_value=None),
        ):
            result = build_charter_context(
                tmp_path, action="implement", depth=2, mark_loaded=False,
                mission_type="software-dev",
            )

        action_block = result.text.split("Action Doctrine (implement):", 1)[1]
        assert "DIRECTIVE_039" in action_block
        assert "boring-code-review" in action_block
        assert "threat-model-first" in action_block
        assert "reasons-canvas-fill" in action_block
        assert "Selected paradigms:" in result.text
        assert "structured-prompt-driven-development" in result.text
        assert "Selected directives:" in result.text
        assert "DIRECTIVE_039" in result.text
        assert "Selected tactics:" in result.text
        assert "threat-model-first" in result.text

    def test_text_contains_reference_docs(self, tmp_path: Path) -> None:
        """Output text includes Reference Docs section."""
        result = self._call(tmp_path)
        assert "Reference Docs:" in result.text

    def test_profile_none_does_not_crash(self, tmp_path: Path) -> None:
        """profile=None is accepted without error."""
        result = self._call(tmp_path, profile=None)
        assert result.text  # non-empty

    def test_profile_value_ignored(self, tmp_path: Path) -> None:
        """profile value is accepted but does not change output (Phase 0)."""
        result_none = self._call(tmp_path, profile=None)
        result_named = self._call(tmp_path, profile="implementer")
        assert result_none.text == result_named.text

    def test_depth_1_returns_compact(self, tmp_path: Path) -> None:
        """depth=1 returns compact governance (matching legacy behavior)."""
        result = self._call(tmp_path, depth=1)
        assert result.mode == "compact"
        assert result.depth == 1

    def test_depth_3_includes_extended_sections(self, tmp_path: Path) -> None:
        """depth >= 3 renders styleguide and toolguide sections."""
        result = self._call(tmp_path, depth=3)
        assert "Styleguides:" in result.text
        assert "Toolguides:" in result.text

    def test_depth_2_renders_extended_sections(self, tmp_path: Path) -> None:
        """WP11 (T059): the retired ``_EXTENDED_CONTEXT_DEPTH`` gate no longer
        drops styleguides/toolguides at the bootstrap depth (d=2). ``depth`` is
        now purely the DRG hop cap, not a render-verbosity tier, so every
        delivered kind renders on the bootstrap load.
        """
        result = self._call(tmp_path, depth=2)
        assert "Styleguides:" in result.text
        assert "Toolguides:" in result.text

    def test_missing_charter_file(self, tmp_path: Path) -> None:
        """When NEITHER charter.yaml nor charter.md exists, returns mode='missing'.

        FR-005 (charter-pack-usage-journey WP03): the presence gate is now an
        OR across the authoritative ``charter.yaml`` and the legacy
        ``charter.md`` -- "missing" only when the charter is truly absent on
        both surfaces. A strict charter.yaml-only gate was tried first and
        regressed a wide swath of the existing suite whose fixtures seed only
        ``charter.md`` (verified via a full ``-k charter`` sweep, 26
        failures); the OR form still satisfies SC-002 (survives ``charter.md``
        deletion, see ``test_charter_md_deletion_survives_with_charter_yaml_present``)
        without breaking those charter.md-only fixtures (see
        ``test_charter_yaml_absence_does_not_regress_charter_md_only_bootstrap``).
        """
        _setup_fixture_repo(tmp_path)
        (tmp_path / ".kittify" / "charter" / "charter.yaml").unlink()
        (tmp_path / ".kittify" / "charter" / "charter.md").unlink()

        from io import StringIO

        from charter.offering.drg.models import DRGGraph
        from ruamel.yaml import YAML

        yaml = YAML(typ="safe")
        graph_data = yaml.load(StringIO(_MINIMAL_GRAPH_YAML))
        mock_graph = DRGGraph.model_validate(graph_data)

        def patched_load_graph(path: Path) -> DRGGraph:
            return mock_graph

        with (
            patch("charter.offering.drg.loader.load_graph", side_effect=patched_load_graph),
            patch("charter.activation.catalog.resolve_doctrine_root", return_value=tmp_path),
            patch("charter.offering.drg.validator.assert_valid"),
        ):
            result = build_charter_context(tmp_path, action="implement", depth=2)

        assert result.mode == "missing"
        assert "Charter file not found" in result.text

    def test_charter_yaml_absence_does_not_regress_charter_md_only_bootstrap(
        self, tmp_path: Path
    ) -> None:
        """Backward-compat pin: charter.md present, charter.yaml absent still renders.

        This is the shape a large swath of the pre-existing suite seeds
        (charter.md-only fixtures that predate charter.yaml). The OR presence
        gate must not regress this to mode='missing'.
        """
        _setup_fixture_repo(tmp_path)
        (tmp_path / ".kittify" / "charter" / "charter.yaml").unlink()

        from io import StringIO

        from charter.offering.drg.models import DRGGraph
        from ruamel.yaml import YAML

        yaml = YAML(typ="safe")
        graph_data = yaml.load(StringIO(_MINIMAL_GRAPH_YAML))
        mock_graph = DRGGraph.model_validate(graph_data)

        def patched_load_graph(path: Path) -> DRGGraph:
            return mock_graph

        with (
            patch("charter.offering.drg.loader.load_graph", side_effect=patched_load_graph),
            patch("charter.activation.catalog.resolve_doctrine_root", return_value=tmp_path),
            patch("charter.offering.drg.validator.assert_valid"),
        ):
            result = build_charter_context(tmp_path, action="implement", depth=2)

        assert result.mode == "bootstrap"
        assert "Charter file not found" not in result.text

    def test_charter_md_deletion_survives_with_charter_yaml_present(self, tmp_path: Path) -> None:
        """FR-005/SC-002: deleting charter.md alone must not flip mode='missing'.

        charter.yaml is the authority; charter.md is a display-only prose
        companion. With charter.yaml still present, the bootstrap render must
        gracefully degrade (no policy summary) rather than dead-ending.
        """
        _setup_fixture_repo(tmp_path)
        (tmp_path / ".kittify" / "charter" / "charter.md").unlink()

        from io import StringIO

        from charter.offering.drg.models import DRGGraph
        from ruamel.yaml import YAML

        yaml = YAML(typ="safe")
        graph_data = yaml.load(StringIO(_MINIMAL_GRAPH_YAML))
        mock_graph = DRGGraph.model_validate(graph_data)

        def patched_load_graph(path: Path) -> DRGGraph:
            return mock_graph

        with (
            patch("charter.offering.drg.loader.load_graph", side_effect=patched_load_graph),
            patch("charter.activation.catalog.resolve_doctrine_root", return_value=tmp_path),
            patch("charter.offering.drg.validator.assert_valid"),
        ):
            result = build_charter_context(tmp_path, action="implement", depth=2)

        assert result.mode == "bootstrap"
        assert "Charter file not found" not in result.text
        assert "No explicit policy summary section found in charter.md." in result.text

    def test_references_count(self, tmp_path: Path) -> None:
        """references_count reflects filtered references."""
        result = self._call(tmp_path)
        assert result.references_count >= 0

    def test_build_context_uses_fallback_summary_when_policy_section_missing(
        self, tmp_path: Path
    ) -> None:
        _setup_fixture_repo(tmp_path)
        charter_path = tmp_path / ".kittify" / "charter" / "charter.md"
        charter_path.write_text("# Project Charter\n", encoding="utf-8")

        patched_load_graph = _write_graph_fixture(tmp_path)

        with (
            patch("charter.offering.drg.loader.load_graph", side_effect=patched_load_graph),
            patch("charter.activation.catalog.resolve_doctrine_root", return_value=tmp_path),
            patch("charter.offering.drg.validator.assert_valid"),
        ):
            result = build_charter_context(tmp_path, action="implement", depth=2)

        assert "No explicit policy summary section found in charter.md." in result.text

    def test_depth_field_matches_input(self, tmp_path: Path) -> None:
        """The depth field in the result matches the input depth."""
        for d in [1, 2, 3]:
            result = self._call(tmp_path, depth=d)
            assert result.depth == d

    def test_json_compact_mode_reports_project_charter_and_all_directives(
        self, tmp_path: Path
    ) -> None:
        """Compact JSON still exposes project-local charter facts."""
        _setup_fixture_repo(tmp_path)
        charter_dir = tmp_path / ".kittify" / "charter"
        # consolidate-charter-bundle (IC-04 / WP04, T028c):
        # _project_directive_entries -> load_directives_config now reads
        # charter.yaml's directives: section; the retired directives.yaml
        # is never read.
        (charter_dir / "charter.yaml").write_text(
            textwrap.dedent("""\
                directives:
                  directives:
                    - id: DIR-001
                      title: First directive
                      description: First rule
                    - id: DIR-002
                      title: Second directive
                      description: Second rule
            """),
            encoding="utf-8",
        )
        (charter_dir / "metadata.yaml").write_text(
            textwrap.dedent("""\
                schema_version: 1.0.0
                charter_hash: sha256:testhash
                source_path: .kittify/charter/charter.md
                bundle_schema_version: 2
            """),
            encoding="utf-8",
        )

        from charter.activation.sync import SyncResult

        sync_result = SyncResult(
            synced=False,
            stale_before=False,
            files_written=[],
            extraction_mode="",
            canonical_root=tmp_path,
        )
        with patch("charter.activation.sync.ensure_charter_bundle_fresh", return_value=sync_result):
            payload = build_charter_context_json(tmp_path, action="plan", depth=1)

        assert payload["directives"] == []
        # WP01 (#3728) made project-local directives ADDITIVE: DIR-001/DIR-002
        # now UNION onto the resolved catalog base instead of replacing it, so
        # they are the appended tail and every base id survives (SC-001). The
        # retired pre-#3728 replace behaviour asserted equality to just the two
        # locals — do NOT restore it.
        all_ids = [entry["id"] for entry in payload["all_directives"]]
        assert all_ids[-2:] == ["DIR-001", "DIR-002"]
        assert len(all_ids) > 2  # base preserved, not collapsed to the two locals
        assert payload["directives_source"] == "catalog_fallback+project_local"
        # FR-006 (charter-pack-usage-journey WP03): present/path/bytes key on
        # the authoritative charter.yaml; charter.md's own presence/path are
        # the secondary display fields.
        assert payload["project_charter"] == {
            "present": True,
            "path": ".kittify/charter/charter.yaml",
            "bytes": (charter_dir / "charter.yaml").stat().st_size,
            "charter_md_present": True,
            "charter_md_path": ".kittify/charter/charter.md",
            "hash": "sha256:testhash",
            "source_path": ".kittify/charter/charter.md",
            "bundle_schema_version": 2,
            "schema_version": "1.0.0",
        }

    def test_json_project_charter_metadata_fallbacks(self, tmp_path: Path) -> None:
        """Project-charter JSON metadata degrades to explicit presence facts.

        FR-006: the producer keys ``present``/``path``/``bytes`` on the
        authoritative ``charter.yaml`` (SC-002 -- survives ``charter.md``
        deletion); ``charter.md`` itself is reported via the secondary
        ``charter_md_present``/``charter_md_path`` fields.
        """
        assert _relative_json_path(Path("/outside/charter.md"), tmp_path) == "/outside/charter.md"

        with patch("charter.activation.sync.ensure_charter_bundle_fresh", side_effect=RuntimeError("boom")):
            assert _bundle_root_for_json(tmp_path) == tmp_path

        with patch("charter.activation.sync.ensure_charter_bundle_fresh", return_value=None):
            assert _bundle_root_for_json(tmp_path) == tmp_path

        missing = _project_charter_json_block(tmp_path)
        assert missing == {
            "present": False,
            "path": ".kittify/charter/charter.yaml",
            "charter_md_present": False,
            "charter_md_path": ".kittify/charter/charter.md",
        }

        charter_dir = tmp_path / ".kittify" / "charter"
        charter_dir.mkdir(parents=True)
        # charter.yaml present, charter.md absent -- the FR-006 flip: present
        # is already True here, before charter.md ever exists.
        (charter_dir / "charter.yaml").write_text("schema_version: '2.0.0'\n", encoding="utf-8")
        from charter.activation.sync import SyncResult

        sync_result = SyncResult(
            synced=False,
            stale_before=False,
            files_written=[],
            extraction_mode="",
            canonical_root=tmp_path,
        )

        with patch("charter.activation.sync.ensure_charter_bundle_fresh", return_value=sync_result):
            no_metadata = _project_charter_json_block(tmp_path)
        assert no_metadata["present"] is True
        assert no_metadata["charter_md_present"] is False
        assert no_metadata["bytes"] == (charter_dir / "charter.yaml").stat().st_size
        assert "hash" not in no_metadata

        # charter.md reappearing only moves the secondary display fields.
        (charter_dir / "charter.md").write_text("# Charter\n", encoding="utf-8")
        with patch("charter.activation.sync.ensure_charter_bundle_fresh", return_value=sync_result):
            with_md = _project_charter_json_block(tmp_path)
        assert with_md["present"] is True
        assert with_md["charter_md_present"] is True
        assert with_md["charter_md_path"] == ".kittify/charter/charter.md"

        metadata = charter_dir / "metadata.yaml"
        metadata.write_text("[not-a-mapping]\n", encoding="utf-8")
        with patch("charter.activation.sync.ensure_charter_bundle_fresh", return_value=sync_result):
            non_mapping = _project_charter_json_block(tmp_path)
        assert "hash" not in non_mapping

        with (
            patch("charter.activation.sync.ensure_charter_bundle_fresh", return_value=sync_result),
            patch("charter.activation.context.YAML") as yaml_cls,
        ):
            yaml_cls.side_effect = ValueError("bad yaml")
            unreadable = _project_charter_json_block(tmp_path)
        assert "hash" not in unreadable

    def test_project_directive_entries_fallbacks(self, tmp_path: Path) -> None:
        """Directive JSON keeps IDs when optional loaders are unavailable."""
        with (
            patch("charter.activation.sync.load_directives_config", side_effect=RuntimeError("no config")),
            patch(
                "charter.activation.resolver.resolve_project_governance",
                return_value=SimpleNamespace(directives=["DIRECTIVE_001"]),
            ),
            patch("charter.activation.context._build_doctrine_service", side_effect=RuntimeError("no service")),
        ):
            assert _project_directive_entries(tmp_path) == [
                {"id": "DIRECTIVE_001", "source": "builtin"}
            ]

        directive = SimpleNamespace(id="DIR-LOCAL", title="Local", description="")
        with (
            patch(
                "charter.activation.sync.load_directives_config",
                return_value=SimpleNamespace(directives=[directive]),
            ),
            patch("charter.activation.resolver.resolve_project_governance", side_effect=RuntimeError("no resolver")),
            patch("charter.activation.context._build_doctrine_service", side_effect=RuntimeError("no service")),
        ):
            assert _project_directive_entries(tmp_path) == [
                {"id": "DIR-LOCAL", "source": "project", "title": "Local"}
            ]

        repo = SimpleNamespace(
            get=lambda artifact_id: SimpleNamespace(
                id=artifact_id,
                title="Catalog directive",
                intent="Catalog intent",
            ),
            get_provenance=lambda _artifact_id: "builtin",
        )
        with (
            patch(
                "charter.activation.sync.load_directives_config",
                return_value=SimpleNamespace(directives=[]),
            ),
            patch(
                "charter.activation.resolver.resolve_project_governance",
                return_value=SimpleNamespace(directives=["DIRECTIVE_002"]),
            ),
            patch(
                "charter.activation.context._build_doctrine_service",
                return_value=SimpleNamespace(directives=repo),
            ),
        ):
            assert _project_directive_entries(tmp_path) == [
                {
                    "id": "DIRECTIVE_002",
                    "source": "builtin",
                    "title": "Catalog directive",
                    "summary": "Catalog intent",
                }
            ]

    def test_load_project_directives_accepts_callable_loader(self, tmp_path: Path) -> None:
        """Helper keeps local directives and resolver directives in stable order."""
        local = SimpleNamespace(id="DIR-LOCAL")

        with patch(
            "charter.activation.resolver.resolve_project_governance",
            side_effect=RuntimeError("no resolver"),
        ):
            local_by_id, directive_ids = _load_project_directives(
                tmp_path,
                lambda _repo_root: SimpleNamespace(directives=[local]),
            )

        assert local_by_id == {"DIR-LOCAL": local}
        assert directive_ids == ["DIR-LOCAL"]


# ---------------------------------------------------------------------------
# WP04 (#883) — action-path leak closure: key off meta.json mission_type,
# never the project-level ``template_set`` proxy.
# ---------------------------------------------------------------------------

_LEAK_GRAPH_YAML = textwrap.dedent("""\
    schema_version: "1.0"
    generated_at: "2026-07-14T10:00:00+00:00"
    generated_by: "test"
    nodes:
      - urn: "action:software-dev/implement"
        kind: action
        label: implement
      - urn: "action:documentation/implement"
        kind: action
        label: implement
      - urn: "directive:DIRECTIVE_001"
        kind: directive
        label: Software Dev Directive
      - urn: "directive:DIRECTIVE_100"
        kind: directive
        label: Documentation Directive
    edges:
      - source: "action:software-dev/implement"
        target: "directive:DIRECTIVE_001"
        relation: scope
      - source: "action:documentation/implement"
        target: "directive:DIRECTIVE_100"
        relation: scope
""")


def test_action_doctrine_keys_off_meta_json_not_template_set(tmp_path: Path) -> None:
    """A non-software mission must not inherit software-dev action doctrine (FR-002).

    The project's ``template_set`` is ``software-dev-default`` (the legacy
    proxy), but the mission's ``meta.json`` declares ``documentation``.  The
    shared action name ``implement`` exists under BOTH mission types in the
    graph.  The rendered context must resolve the *documentation* action node
    (DIRECTIVE_100), never leak the *software-dev* one (DIRECTIVE_001).

    This is the #883 leak reproduction — RED before the rewire, GREEN after.
    """
    from io import StringIO

    from charter.offering.drg.models import DRGGraph
    from ruamel.yaml import YAML

    _setup_fixture_repo(tmp_path)  # governance.yaml: template_set=software-dev-default

    feature_dir = tmp_path / "kitty-specs" / "883-doc-mission"
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        '{"mission_type": "documentation"}', encoding="utf-8"
    )

    yaml = YAML(typ="safe")
    mock_graph = DRGGraph.model_validate(yaml.load(StringIO(_LEAK_GRAPH_YAML)))

    with (
        # WP05 (#2680): patch the merged-graph seam, not per-file load_graph, so
        # the sharded fragment layout does not duplicate the fixture on merge.
        patch("charter.activation._drg_helpers.load_validated_graph", return_value=mock_graph),
        patch("charter.activation.catalog.resolve_doctrine_root", return_value=tmp_path),
        patch("charter.offering.drg.validator.assert_valid"),
    ):
        result = build_charter_context(
            tmp_path,
            action="implement",
            depth=2,
            mark_loaded=False,
            feature_dir=feature_dir,
        )

    # Documentation mission resolves ITS OWN action doctrine ...
    assert "DIRECTIVE_100" in result.text
    # ... and never leaks the software-dev action doctrine (the #883 defect).
    assert "DIRECTIVE_001" not in result.text


def test_render_bootstrap_uses_fallback_labels_without_summary_or_references() -> None:
    # WP13 (T072): the test-only ``_render_bootstrap`` dead render path was
    # deleted; its fallback-label behaviour lives on the live renderer
    # ``_render_bootstrap_text``, which this assertion now targets.
    bundle = _ActionDoctrineBundle(
        mission="software-dev",
        directive_ids=[],
        tactic_ids=[],
        styleguide_ids=[],
        toolguide_ids=[],
        procedure_ids=[],
        asset_ids=[],
        service=_ProcedureOnlyService(),
    )

    text = _render_bootstrap_text(
        charter_path=Path("/nonexistent/charter.md"),
        action="implement",
        summary=[],
        doctrine_bundle=bundle,
        references=[],
    )

    assert "Policy Summary:" in text
    assert "No explicit policy summary section found in charter.md." in text
    assert "Reference Docs:" in text
    assert "No references manifest found." in text


class _StubRepo:
    """A repository that resolves nothing -- exercises the bare-id fallback."""

    def get(self, _artifact_id: str) -> None:
        return None


class _ProcedureOnlyService:
    """A doctrine service exposing only ``procedures`` (no ``assets`` attr).

    Mirrors the WP10 base: the asset repository/service wiring (WP04/WP05) is
    not on this lane, so the renderer must emit asset ids without a repository
    (``getattr(service, "assets", None)`` → ``None`` → bare-id fallback), while
    procedures resolve through ``service.procedures``.
    """

    directives = _StubRepo()
    tactics = _StubRepo()
    styleguides = _StubRepo()
    toolguides = _StubRepo()
    procedures = _StubRepo()


def test_render_emits_every_kind_the_bundle_resolves() -> None:
    """FR-009/B-2: every id the bundle resolves reaches the rendered output.

    Asserted on the RENDERED text, not the bundle: the procedure and asset ids
    the bundle carries must appear under their own headings. WP11 (T059)
    retired the ``_EXTENDED_CONTEXT_DEPTH`` render gate, so these kinds now
    render on the bootstrap load unconditionally rather than only at depth>=3.
    """
    bundle = _ActionDoctrineBundle(
        mission="software-dev",
        directive_ids=[],
        tactic_ids=[],
        styleguide_ids=[],
        toolguide_ids=[],
        procedure_ids=["onboard-external-agent-to-pack"],
        asset_ids=["common-docs-structural-lint"],
        service=_ProcedureOnlyService(),
    )

    text = _render_bootstrap_text(
        charter_path=Path("/nonexistent/charter.md"),
        action="implement",
        summary=[],
        doctrine_bundle=bundle,
        references=[],
    )

    assert "Procedures:" in text
    assert "onboard-external-agent-to-pack" in text
    assert "Assets:" in text
    assert "common-docs-structural-lint" in text


# ---------------------------------------------------------------------------
# T022: Structural test -- no per-action filtering logic (FR-009)
# ---------------------------------------------------------------------------


class TestNoPerActionFiltering:
    """Structural audit verifying FR-009 compliance.

    build_charter_context must not contain if-statements that branch on
    action names to conditionally filter artifacts. Context size is
    determined entirely by graph topology.
    """

    def test_no_action_name_string_literals_in_function_body(self) -> None:
        """No action-name string literals in build_charter_context body.

        Checks that none of the canonical action names appear as string
        literals in the function's source code (excluding the docstring).
        """
        source = inspect.getsource(build_charter_context)
        tree = ast.parse(textwrap.dedent(source))

        # Find the function definition
        func_def = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "build_charter_context":
                func_def = node
                break

        assert func_def is not None, "Could not find build_charter_context function"

        # Collect all string literals in the function body (skip docstring)
        body_nodes = func_def.body
        # Skip the first statement if it's the docstring
        if (
            body_nodes
            and isinstance(body_nodes[0], ast.Expr)
            and isinstance(body_nodes[0].value, ast.Constant)
            and isinstance(body_nodes[0].value.value, str)
        ):
            body_nodes = body_nodes[1:]

        action_names = {"specify", "plan", "implement", "review", "tasks"}
        found_literals: list[str] = []

        for node in ast.walk(ast.Module(body=body_nodes, type_ignores=[])):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value.lower() in action_names:
                    found_literals.append(node.value)

        assert not found_literals, (
            f"build_charter_context contains action-name string literals: "
            f"{found_literals}. FR-009 prohibits per-action filtering. "
            f"Context size is determined by graph topology, not if-statements."
        )

    def test_no_conditional_on_action_parameter(self) -> None:
        """No if-statements that compare the 'action' parameter to string literals."""
        source = inspect.getsource(build_charter_context)
        tree = ast.parse(textwrap.dedent(source))

        func_def = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "build_charter_context":
                func_def = node
                break

        assert func_def is not None

        # Look for if-statements that test 'action' or 'normalized' against
        # string constants
        for node in ast.walk(func_def):
            if isinstance(node, ast.If):
                test = node.test
                # Check for comparisons like `action == "specify"` or
                # `normalized in {"specify", "plan"}`
                if isinstance(test, ast.Compare):
                    for comparator in [test.left, *test.comparators]:
                        if isinstance(comparator, ast.Name) and comparator.id in (
                            "action",
                            "normalized",
                        ):
                            # Check if other side has string constants matching actions
                            for other in [test.left, *test.comparators]:
                                if isinstance(other, ast.Constant) and isinstance(
                                    other.value, str
                                ):
                                    action_names = {
                                        "specify",
                                        "plan",
                                        "implement",
                                        "review",
                                        "tasks",
                                    }
                                    assert other.value.lower() not in action_names, (
                                        f"Found conditional on action parameter: "
                                        f"comparison with '{other.value}'. "
                                        f"FR-009 prohibits per-action filtering."
                                    )


def test_build_doctrine_service_prefers_repo_src_overlay(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: dict[str, object] = {}

    class StubOfferingService:
        def __init__(
            self, *, built_in_root: Path | None = None, project_root: Path | None, active_languages: list[str]
        ) -> None:
            calls["built_in_root"] = built_in_root
            calls["project_root"] = project_root
            calls["active_languages"] = active_languages

    built_in_root = tmp_path / "shipped-doctrine"
    built_in_root.mkdir()
    project_root = tmp_path / "src" / "charter" / "offering"
    project_root.mkdir(parents=True)

    monkeypatch.setattr("charter.activation.catalog.resolve_doctrine_root", lambda: built_in_root)
    monkeypatch.setattr("charter.activation.context.infer_repo_languages", lambda repo_root: ["python", "typescript"])
    monkeypatch.setattr("charter.offering.service.CharterOfferingService", StubOfferingService)

    service = _build_doctrine_service(tmp_path)

    assert isinstance(service, StubOfferingService)
    # Relocation (WP02, mission doctrine-built-in-seam-consolidation-01KYW3TX):
    # _build_doctrine_service no longer passes a built_in_root kwarg at all --
    # each repository self-resolves the flattened built-in tier via
    # built_in_dir(kind) (packs/built-in/<kind>). Pointing at
    # resolve_doctrine_root() post-relocation would yield the emptied
    # src/charter/offering/<kind>/built-in and silently load nothing. The stub's
    # built_in_root default (None) surfaces the same recorded value as before
    # the kwarg was dropped. The project-root overlay wiring is unchanged.
    assert calls == {
        "built_in_root": None,
        "project_root": project_root,
        "active_languages": ["python", "typescript"],
    }


def test_build_doctrine_service_uses_compiled_charter_languages_end_to_end(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """WP02/T010: the real (non-monkeypatched) infer_repo_languages resolution.

    Writes a real compiled-charter fixture (charter.yaml with the
    ``catalog.languages`` field — WP08 re-pointed tier-1 from the retired
    ``references.yaml`` to this authoritative source) alongside an interview
    transcript that disagrees, then confirms ``_build_doctrine_service``
    receives the compiled value via ``active_languages`` — proving there is
    no separate precedence logic duplicated in ``context.py`` itself.
    """
    from ruamel.yaml import YAML

    from charter.activation.interview import apply_answer_overrides, default_interview, write_interview_answers

    calls: dict[str, object] = {}

    class StubOfferingService:
        def __init__(
            self, *, built_in_root: Path | None = None, project_root: Path | None, active_languages: list[str]
        ) -> None:
            calls["active_languages"] = active_languages

    built_in_root = tmp_path / "shipped-doctrine"
    built_in_root.mkdir()

    # Interview transcript says "python" — this must be ignored once the
    # compiled charter's structured field exists and disagrees.
    answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
    answers_path.parent.mkdir(parents=True, exist_ok=True)
    interview = apply_answer_overrides(
        default_interview(mission="software-dev", profile="minimal"),
        answers={"languages_frameworks": "Python backend with pytest checks"},
    )
    write_interview_answers(answers_path, interview)

    # Compiled charter (charter.yaml catalog.languages) says "rust" — this is
    # the canonical answer once it exists.
    charter_yaml_path = tmp_path / ".kittify" / "charter" / "charter.yaml"
    yaml = YAML()
    yaml.default_flow_style = False
    with charter_yaml_path.open("w", encoding="utf-8") as handle:
        yaml.dump(
            {
                "schema_version": "2.0.0",
                "catalog": {
                    "mission": "software-dev",
                    "template_set": "default",
                    "languages": ["rust"],
                    "references": [],
                },
            },
            handle,
        )

    monkeypatch.setattr("charter.activation.catalog.resolve_doctrine_root", lambda: built_in_root)
    monkeypatch.setattr("charter.offering.service.CharterOfferingService", StubOfferingService)

    service = _build_doctrine_service(tmp_path)

    assert isinstance(service, StubOfferingService)
    assert calls == {"active_languages": ["rust"]}
