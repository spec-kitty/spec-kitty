"""WP05 (IC-05) — display prose-consumer re-point tests (T023).

These tests pin the **INV-3** invariant from ``data-model.md``: the
display-only ``charter.md`` prose consumers (``_extract_policy_summary``,
``render_critical_section_bodies`` and its call sites in ``context.py`` /
``compact.py``) feed DISPLAY strings only. No governance DECISION
(directive/tactic resolution) reads ``charter.md`` prose — governance
authority lives entirely in ``charter.yaml`` (WP04's re-pointed loaders,
``charter.activation.sync.load_governance_config`` / ``load_directives_config``).

Coverage:

* Bootstrap text still renders the Policy Summary + Action-Critical Charter
  Sections bodies sourced from the companion ``charter.md`` (T021).
* Governance/decision output (resolved directive IDs) is invariant to
  ``charter.md`` prose content — flipping the companion's Policy Summary /
  section bodies does not change which directives resolve, because
  directive resolution is driven by the DRG graph + ``charter.yaml``'s
  ``governance.charter.selected_directives``, never by parsing
  ``charter.md`` (T021, INV-3).
* The compact-mode section-block renderer (``context._compact_section_block``)
  and the compact anchor extractor (``compact.render_compact_view``) degrade
  gracefully -- no crash, empty display block -- when ``charter.md`` is
  absent or unreadable, because a project's governance authority is
  ``charter.yaml`` and the companion prose file is an optional display
  surface (T022).
* Static (grep-style / AST) proof that the governance-decision functions in
  ``context.py`` / ``compact.py`` never reference the prose-parsing surface
  (INV-3, T023).
"""

from __future__ import annotations

import ast
import inspect
import subprocess
import textwrap
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from ruamel.yaml import YAML

from charter.activation import compact as compact_module
from charter.activation import context as context_module
from charter.activation.context import CharterContextResult, build_charter_context
from charter.activation.context_renderers.section_bodies import render_critical_section_bodies
from charter.activation.compact import extract_section_anchors, render_compact_view
from charter.offering.drg.models import DRGGraph

# Uses subprocess `git init` (see below), so it must carry ``git_repo`` and
# must NOT be ``fast`` (fast excludes subprocess users) per the marker-correctness
# arch gate (docs/context/testing-taxonomy.md).
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_GRAPH_WITH_DIRECTIVE_001 = textwrap.dedent("""\
    schema_version: "1.0"
    generated_at: "2026-07-18T10:00:00+00:00"
    generated_by: "test"
    nodes:
      - urn: "action:software-dev/implement"
        kind: action
        label: implement
      - urn: "directive:DIRECTIVE_001"
        kind: directive
        label: Architectural Integrity Standard
    edges:
      - source: "action:software-dev/implement"
        target: "directive:DIRECTIVE_001"
        relation: scope
""")

_CHARTER_YAML_WITH_DIRECTIVE_001 = textwrap.dedent("""\
    schema_version: "2.0.0"
    governance:
      doctrine:
        selected_directives:
          - DIRECTIVE_001
    """)

_CHARTER_MD_WITH_PROSE = textwrap.dedent("""\
    # Project Charter

    ## Policy Summary

    - Intent: deterministic delivery
    - Testing: pytest + coverage

    ## Terminology Canon

    - The canonical term is **Mission**.

    ## Code Review Checklist

    - Tests added for new functionality.

    ## Regression Vigilance (2026-04-06)

    Reviewers MUST grep the diff for the old term before approving.
    """)

_CHARTER_MD_WITH_DIFFERENT_PROSE = textwrap.dedent("""\
    # Project Charter

    ## Policy Summary

    - Intent: something completely different
    """)


def _write_fixture_repo(tmp_path: Path, *, charter_md: str | None) -> None:
    """Write a minimal repo with ``charter.yaml`` and (optionally) ``charter.md``.

    ``charter.yaml`` always carries ``governance.charter.selected_directives``
    so the WP04-repointed loader (``charter.activation.sync.load_governance_config``)
    resolves ``DIRECTIVE_001`` regardless of whether -- or what -- the
    companion ``charter.md`` says.
    """
    # Git-init explicitly (rather than relying solely on the autouse
    # conftest fixture, which only initializes the top-level ``tmp_path``):
    # two independent fixture roots in the same test must each resolve
    # their OWN canonical root, not bleed into an enclosing parent repo
    # via ``git rev-parse --git-common-dir``.
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=False, capture_output=True)
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.yaml").write_text(_CHARTER_YAML_WITH_DIRECTIVE_001, encoding="utf-8")
    if charter_md is not None:
        (charter_dir / "charter.md").write_text(charter_md, encoding="utf-8")
    # No ``charter:`` pointer is written to config.yaml here, so PackContext
    # reads activation directly from config.yaml (legacy/un-migrated path).
    # ``mission_type_activations`` is provisioned so ``PackContext.from_config``
    # (WP04, C-A1: the provisioned charter is the sole activation authority)
    # does not hard-fail on a genuinely absent key.
    (tmp_path / ".kittify" / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )


def _mock_graph() -> DRGGraph:
    yaml = YAML(typ="safe")
    graph_data = yaml.load(StringIO(_GRAPH_WITH_DIRECTIVE_001))
    return DRGGraph.model_validate(graph_data)


def _build_bootstrap_context(tmp_path: Path, *, charter_md: str | None) -> CharterContextResult:
    """Call ``build_charter_context`` at bootstrap depth with the DRG graph
    seam patched to a fixture graph that scopes ``DIRECTIVE_001`` to the
    ``implement`` action (mirrors the pattern in ``test_context.py``)."""
    _write_fixture_repo(tmp_path, charter_md=charter_md)
    mock_graph = _mock_graph()

    with (
        patch("charter.activation._drg_helpers.load_validated_graph", return_value=mock_graph),
        patch("charter.activation.catalog.resolve_doctrine_root", return_value=tmp_path),
        patch("charter.offering.drg.validator.assert_valid"),
    ):
        return build_charter_context(
            tmp_path,
            action="implement",
            depth=2,
            mark_loaded=False,
            mission_type="software-dev",
        )


# ---------------------------------------------------------------------------
# T021 -- bootstrap text renders companion charter.md prose (display)
# ---------------------------------------------------------------------------


class TestBootstrapRendersCompanionProse:
    """Bootstrap text still surfaces the Policy Summary and the
    Action-Critical Charter Sections bodies sourced from ``charter.md``."""

    def test_policy_summary_renders_from_charter_md(self, tmp_path: Path) -> None:
        result = self._call(tmp_path)
        assert "Policy Summary:" in result.text
        assert "Intent: deterministic delivery" in result.text

    def test_critical_section_bodies_render_from_charter_md(self, tmp_path: Path) -> None:
        result = self._call(tmp_path)
        assert "Action-Critical Charter Sections (implement):" in result.text
        assert "### Terminology Canon" in result.text
        assert "The canonical term is **Mission**." in result.text
        assert "### Regression Vigilance" in result.text
        assert "Reviewers MUST grep the diff" in result.text

    def _call(self, tmp_path: Path) -> CharterContextResult:
        return _build_bootstrap_context(tmp_path, charter_md=_CHARTER_MD_WITH_PROSE)


# ---------------------------------------------------------------------------
# T021 -- governance resolution is invariant to charter.md prose (INV-3)
# ---------------------------------------------------------------------------


class TestGovernanceResolutionIndependentOfProse:
    """Directive resolution comes from the DRG graph + charter.yaml's
    ``governance.charter.selected_directives`` -- never from parsing
    ``charter.md``. Swapping the companion's prose changes only the
    DISPLAY blocks, never which directives resolve."""

    def test_directive_resolves_regardless_of_charter_md_prose(self, tmp_path: Path) -> None:
        with_prose = _build_bootstrap_context(tmp_path, charter_md=_CHARTER_MD_WITH_PROSE)
        assert "DIRECTIVE_001" in with_prose.text

        # A second, disjoint tmp_path with DIFFERENT charter.md prose (no
        # Terminology Canon / Regression Vigilance sections at all) must
        # still resolve the same directive: the decision path never reads
        # the prose that changed.
        other_root = tmp_path / "other-repo"
        other_root.mkdir()
        other = _build_bootstrap_context(other_root, charter_md=_CHARTER_MD_WITH_DIFFERENT_PROSE)
        assert "DIRECTIVE_001" in other.text

    def test_display_blocks_change_with_prose_while_directive_is_stable(
        self, tmp_path: Path
    ) -> None:
        with_prose = _build_bootstrap_context(tmp_path, charter_md=_CHARTER_MD_WITH_PROSE)

        other_root = tmp_path / "other-repo"
        other_root.mkdir()
        without_sections = _build_bootstrap_context(
            other_root, charter_md=_CHARTER_MD_WITH_DIFFERENT_PROSE
        )

        # Display content genuinely differs (proves the assertions above
        # are not vacuous): the second charter.md carries no critical
        # sections, so the verbatim body is absent and only the
        # fetch-stanza degrade path renders (the ``### <heading>`` marker
        # itself is emitted unconditionally by
        # ``render_critical_section_bodies`` -- it is the BODY that is
        # conditional, per section_bodies.py's two-arm contract).
        assert "The canonical term is **Mission**." in with_prose.text
        assert "The canonical term is **Mission**." not in without_sections.text
        assert "section:terminology-canon" in without_sections.text

        # ...yet the governance decision (directive resolution) is
        # unaffected by that difference.
        assert "DIRECTIVE_001" in with_prose.text
        assert "DIRECTIVE_001" in without_sections.text


# ---------------------------------------------------------------------------
# T022 -- graceful degradation when charter.md is absent/unreadable
# ---------------------------------------------------------------------------


class TestCompactDisplayGracefulAbsence:
    """The compact-mode section renderer and the anchor extractor never
    crash when the companion ``charter.md`` is missing -- a project's
    governance authority is ``charter.yaml``; the prose companion is
    optional display sugar."""

    def test_compact_section_block_empty_when_charter_md_absent(self, tmp_path: Path) -> None:
        _write_fixture_repo(tmp_path, charter_md=None)
        assert not (tmp_path / ".kittify" / "charter" / "charter.md").exists()

        block = context_module._compact_section_block(tmp_path, "implement")
        assert block == ""

    def test_compact_section_block_renders_when_charter_md_present(self, tmp_path: Path) -> None:
        _write_fixture_repo(tmp_path, charter_md=_CHARTER_MD_WITH_PROSE)

        block = context_module._compact_section_block(tmp_path, "implement")
        assert "Action-Critical Charter Sections (implement):" in block
        assert "### Terminology Canon" in block

    def test_compact_section_block_empty_when_action_is_none(self, tmp_path: Path) -> None:
        _write_fixture_repo(tmp_path, charter_md=_CHARTER_MD_WITH_PROSE)
        assert context_module._compact_section_block(tmp_path, None) == ""

    def test_compact_section_block_graceful_on_unreadable_file(self, tmp_path: Path) -> None:
        _write_fixture_repo(tmp_path, charter_md=_CHARTER_MD_WITH_PROSE)
        with patch.object(Path, "read_text", side_effect=OSError("boom")):
            block = context_module._compact_section_block(tmp_path, "implement")
        assert block == ""

    def test_compact_view_anchors_empty_when_charter_md_absent(self, tmp_path: Path) -> None:
        _write_fixture_repo(tmp_path, charter_md=None)

        view = render_compact_view(tmp_path)
        assert view.section_anchors == ()
        # No crash; the rest of the compact block still renders.
        assert "Governance:" in view.text

    def test_compact_view_anchors_present_when_charter_md_present(self, tmp_path: Path) -> None:
        _write_fixture_repo(tmp_path, charter_md=_CHARTER_MD_WITH_PROSE)

        view = render_compact_view(tmp_path)
        assert "Terminology Canon" in view.section_anchors

    def test_extract_section_anchors_pure_on_empty_string(self) -> None:
        # The pure renderer never touches the filesystem; feeding it the
        # empty string (what a missing/unreadable companion degrades to)
        # is always safe.
        assert extract_section_anchors("") == []

    def test_render_critical_section_bodies_pure_on_empty_string(self) -> None:
        # render_critical_section_bodies is a pure text transform: an
        # absent charter.md degrades to "" content upstream, and the
        # renderer still produces the fetch-stanza degrade path per
        # section instead of crashing (NFR-005).
        result = render_critical_section_bodies("", "implement")
        assert "Action-Critical Charter Sections (implement):" in result
        assert "section:terminology-canon" in result
        assert "section:code-review-checklist" in result
        assert "section:regression-vigilance" in result


# ---------------------------------------------------------------------------
# T023 -- INV-3 static proof: decision paths never reference the prose seam
# ---------------------------------------------------------------------------


class TestNoGovernanceDecisionReadsCharterMdProse:
    """Grep/AST-style proof that the functions responsible for resolving
    *which* directives/tactics/paradigms apply never reference the
    ``charter.md`` prose-parsing surface (``charter_content``,
    ``_extract_policy_summary``, ``render_critical_section_bodies``, or the
    shared ``CHARTER_MD`` path constant used to locate the companion file).
    """

    #: functions that decide governance content (directive/tactic/paradigm
    #: selection); none of these may reference the prose seam.
    _DECISION_FUNCTIONS = (
        context_module._load_action_doctrine_bundle,
        context_module._load_doctrine_selection,
        context_module._classify_artifact_urns,
        context_module._build_doctrine_service,
    )

    #: identifiers that mark a reference to the charter.md prose-parsing
    #: surface. Presence of any of these inside a decision function's body
    #: would indicate the decision now depends on prose content.
    _PROSE_SEAM_NAMES = frozenset(
        {
            "charter_content",
            "_extract_policy_summary",
            "render_critical_section_bodies",
            "render_critical_section_include",
            "CHARTER_MD",
        }
    )

    def test_decision_functions_do_not_reference_prose_seam(self) -> None:
        for func in self._DECISION_FUNCTIONS:
            source = inspect.getsource(func)
            tree = ast.parse(textwrap.dedent(source))
            referenced = {
                node.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Name)
            } | {
                node.attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Attribute)
            }
            leaked = referenced & self._PROSE_SEAM_NAMES
            assert not leaked, (
                f"{func.__qualname__} references the charter.md prose seam "
                f"({sorted(leaked)}); governance decisions must resolve from "
                "charter.yaml only (INV-3)."
            )

    def test_load_action_doctrine_bundle_signature_excludes_prose(self) -> None:
        # Structural proof: the decision entry point cannot read prose
        # because it is never handed the companion file's content or path.
        params = set(inspect.signature(context_module._load_action_doctrine_bundle).parameters)
        assert not params & {"charter_content", "charter_path", "summary"}

    def test_compact_governance_summary_resolver_does_not_reference_prose_seam(self) -> None:
        source = inspect.getsource(compact_module._resolve_governance_summary)
        tree = ast.parse(textwrap.dedent(source))
        referenced = {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        } | {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        assert not referenced & self._PROSE_SEAM_NAMES

    def test_sync_governance_loader_docstring_declares_inv3(self) -> None:
        # WP04's loader is the canonical proof that governance now comes
        # exclusively from charter.yaml; pin its self-documented contract
        # so a future regression that silently re-adds a charter.md read
        # is caught here too.
        from charter.activation.sync import load_governance_config

        doc = inspect.getdoc(load_governance_config) or ""
        assert "charter.yaml" in doc
        assert "INV-3" in doc
