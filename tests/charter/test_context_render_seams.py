"""WP05 (#2532) — focused unit tests for the 5 render seams extracted from
``charter.activation.context`` into ``charter.activation.context_renderers``: ``template_include``,
``selection_block``, ``activation_block``, ``bootstrap_text``, and
``compact_governance``.

These tests are narrower than the byte-parity fixture
(``tests/charter/test_context_parity.py``, which pins the composed OUTPUT):
this module pins two things the parity fixture cannot see by construction:

1. **Standalone importability** — each new seam module must be importable as
   the FIRST charter import in a fresh interpreter, without raising, proving
   the module-load cycle each of them shares with ``charter.activation.context`` (for a
   collaborator that has not yet been relocated) is broken by a
   function-local import rather than a top-level one (data-model.md's
   cycle-dissolution invariant, NFR-001 acyclicity).
2. **Focused unit coverage** of a handful of pure helpers in each seam,
   plus the ``suppress_project_resolver`` contract threaded through
   ``compact_governance`` (WP03/#3064), so a future regression in these
   specific seams is caught here rather than only via the much larger
   parity corpus.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from charter.activation.activations import ActivationEntry
from charter.activation.context_renderers import (
    activation_block,
    bootstrap_text,
    compact_governance,
    selection_block,
    template_include,
)
from charter.activation.schemas import DoctrineSelectionConfig

#: One test in this module (``test_seam_module_imports_standalone_without_
#: charter_context``) spawns a subprocess to verify standalone importability,
#: which disqualifies the whole file from the `fast` lane's no-subprocess
#: contract (docs/context/testing-taxonomy.md -> 'Fast'). The module is
#: otherwise a "focused unit tests" suite per the module docstring, so
#: `unit` is the correct category marker.
pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Standalone importability (cycle dissolution)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module_name",
    [
        "charter.activation.context_renderers.template_include",
        "charter.activation.context_renderers.selection_block",
        "charter.activation.context_renderers.activation_block",
        "charter.activation.context_renderers.bootstrap_text",
        "charter.activation.context_renderers.compact_governance",
    ],
)
def test_seam_module_imports_standalone_without_charter_context(
    module_name: str,
) -> None:
    """Each seam module must import cleanly as the FIRST charter import.

    A subprocess is used (not a plain ``import`` in-process) so the check
    is genuinely independent of whichever charter modules pytest's own
    collection has already warmed into ``sys.modules`` — a top-level
    ``charter.activation.context`` import inside one of these seams would only show up
    as a failure here, never in the full suite (where ``charter.activation.context``
    is always already loaded by the time these modules import).

    ``PYTHONPATH`` is pinned to THIS worktree's ``src/`` (mirroring
    ``pytest.ini``'s own ``pythonpath = src``) rather than relying on
    whatever ``charter`` package happens to already be installed/editable
    on ``sys.executable`` — a lane worktree's bare interpreter can resolve
    a *different* checkout's ``src/charter`` entirely (the documented
    "lane bare-python imports primary" footgun), which would silently test
    the wrong file.
    """
    repo_src = Path(__file__).resolve().parents[2] / "src"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_src)
    result = subprocess.run(
        [sys.executable, "-c", f"import {module_name}"],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert result.returncode == 0, (
        f"{module_name} failed to import standalone (module-load cycle?):\n"
        f"{result.stderr}"
    )


# ---------------------------------------------------------------------------
# template_include.py
# ---------------------------------------------------------------------------


class TestTemplateIncludeSeam:
    def test_default_missions_root_resolves_an_existing_directory(self) -> None:
        root = template_include._default_missions_root()
        assert isinstance(root, Path)
        assert root.is_dir()

    def test_render_doctrine_artifact_include_returns_none_for_unrouted_kind(
        self,
    ) -> None:
        # "directive"/"tactic" are routed by the caller BEFORE this helper;
        # every other unrecognised kind token returns None (never raises),
        # letting the caller (or the generic-artifact fan-out) decide.
        assert (
            template_include._render_doctrine_artifact_include(
                object(), "not-a-real-kind", "some-id"
            )
            is None
        )

    def test_render_doctrine_artifact_include_raises_structured_miss(self) -> None:
        class _EmptyRepo:
            def get(self, _artifact_id: str) -> None:
                return None

        service = type("Service", (), {"paradigms": _EmptyRepo()})()
        with pytest.raises(ValueError, match="No paradigm found"):
            template_include._render_doctrine_artifact_include(
                service, "paradigm", "missing-id"
            )


# ---------------------------------------------------------------------------
# selection_block.py
# ---------------------------------------------------------------------------


class TestSelectionBlockSeam:
    def test_provenance_suffix_empty_when_no_map(self) -> None:
        assert selection_block._provenance_suffix("some-id", None) == ""
        assert selection_block._provenance_suffix("some-id", {}) == ""

    def test_provenance_suffix_bare_org_sentinel(self) -> None:
        # Empty-string pack name is the documented sentinel that collapses
        # to a bare "(source: org)" suffix (no per-pack attribution known).
        assert (
            selection_block._provenance_suffix("some-id", {"some-id": ""})
            == " (source: org)"
        )

    def test_provenance_suffix_names_the_pack(self) -> None:
        assert (
            selection_block._provenance_suffix(
                "some-id", {"some-id": "example-org"}
            )
            == " (source: org, pack: example-org)"
        )

    def test_collect_org_source_map_empty_without_repository_or_ids(self) -> None:
        assert selection_block._collect_org_source_map(None, ["a"]) == {}
        assert selection_block._collect_org_source_map(object(), []) == {}

    def test_collect_org_source_map_flags_org_provenance(self) -> None:
        class _Repo:
            def get_provenance(self, artifact_id: str) -> str:
                return "org" if artifact_id == "org-one" else "builtin"

        result = selection_block._collect_org_source_map(
            _Repo(), ["org-one", "builtin-one"]
        )
        assert result == {"org-one": ""}

    def test_render_selection_block_empty_without_selection_or_service(
        self,
    ) -> None:
        assert selection_block._render_selection_block(None, object()) == ""
        assert selection_block._render_selection_block(object(), None) == ""  # type: ignore[arg-type]

    def test_extend_named_artifact_lines_noop_on_empty_ids(self) -> None:
        lines: list[str] = []
        selection_block._extend_named_artifact_lines(
            lines, "Heading", [], None, "title", "summary"
        )
        assert lines == []

    def test_build_action_org_source_map_empty_without_ids(self, tmp_path: Path) -> None:
        assert selection_block._build_action_org_source_map(tmp_path, []) == {}


# ---------------------------------------------------------------------------
# activation_block.py
# ---------------------------------------------------------------------------


class TestActivationBlockSeam:
    @staticmethod
    def _entry(pack: str, artifact: str, mission_type: str = "software-dev") -> ActivationEntry:
        return ActivationEntry(
            activation_context={"mission_type": mission_type, "action": "implement"},
            doctrine_pack_id=pack,
            artifact_id=artifact,
        )

    def test_union_activations_dedups_by_identity_project_first(self) -> None:
        shared = self._entry("pack-a", "styleguide-one")
        project_only = self._entry("pack-a", "styleguide-two")
        org_only = self._entry("pack-b", "styleguide-three")
        # A structurally-identical duplicate (same identity tuple) appended
        # on the org side must NOT produce a second entry.
        duplicate_of_shared = self._entry("pack-a", "styleguide-one")

        merged = activation_block._union_activations(
            project_activations=[shared, project_only],
            org_activations=[duplicate_of_shared, org_only],
        )

        assert merged == [shared, project_only, org_only]

    def test_union_activations_empty_inputs_yield_empty_output(self) -> None:
        assert activation_block._union_activations([], []) == []

    def test_render_activation_block_empty_without_repo_root(self) -> None:
        assert (
            activation_block._render_activation_block(
                None, None, object(), mission_type="software-dev", action="implement"
            )
            == ""
        )

    def test_render_activation_block_empty_when_no_activations_configured(
        self, tmp_path: Path
    ) -> None:
        # No governance.yaml / org packs at all under tmp_path: both the
        # project and org reads collapse to [], so the union is empty and
        # the renderer short-circuits before ever calling the WP05 stanza
        # renderer.
        assert (
            activation_block._render_activation_block(
                None,
                tmp_path,
                object(),
                mission_type="software-dev",
                action="implement",
            )
            == ""
        )


# ---------------------------------------------------------------------------
# bootstrap_text.py
# ---------------------------------------------------------------------------


class TestBootstrapTextSeam:
    def test_action_render_rows_cover_the_six_delivered_kinds(self) -> None:
        headings = [row.heading for row in bootstrap_text._ACTION_RENDER_ROWS]
        assert headings == [
            "Directives",
            "Tactics",
            "Styleguides",
            "Toolguides",
            "Procedures",
            "Assets",
        ]

    def test_action_render_rows_progressive_kind_only_on_disclosure_cadenced_kinds(
        self,
    ) -> None:
        # Procedure/Asset stay always-inline (pre-D2c behaviour); the other
        # four carry the progressive-disclosure kind prefix.
        by_heading = {
            row.heading: row.progressive_kind
            for row in bootstrap_text._ACTION_RENDER_ROWS
        }
        assert by_heading["Directives"] == "directive"
        assert by_heading["Tactics"] == "tactic"
        assert by_heading["Styleguides"] == "styleguide"
        assert by_heading["Toolguides"] == "toolguide"
        assert by_heading["Procedures"] is None
        assert by_heading["Assets"] is None

    def test_append_guidelines_lines_never_raises_on_unknown_mission(self) -> None:
        lines: list[str] = []
        # A nonsense mission/action pair resolves no guidelines; the helper
        # is best-effort and must not raise (matches the pre-move contract).
        bootstrap_text._append_guidelines_lines(
            lines, "not-a-real-mission-type", "not-a-real-action"
        )
        assert lines == []

    def test_render_action_doctrine_lines_empty_bundle_emits_nothing(self) -> None:
        class _EmptyBundle:
            directive_ids: list[str] = []
            tactic_ids: list[str] = []
            styleguide_ids: list[str] = []
            toolguide_ids: list[str] = []
            procedure_ids: list[str] = []
            asset_ids: list[str] = []
            service = object()
            merged = None
            roots: tuple[str, ...] = ()

        lines: list[str] = []
        bootstrap_text._render_action_doctrine_lines(
            lines, _EmptyBundle(), repo_root=None  # type: ignore[arg-type]
        )
        assert lines == []

    # -- S3776 decomposition helpers (bootstrap_text.py:165 -> 19, WP03) --

    def test_append_policy_summary_lines_with_summary_caps_at_eight(self) -> None:
        lines: list[str] = []
        bootstrap_text._append_policy_summary_lines(lines, [f"item-{i}" for i in range(12)])
        assert len(lines) == 8  # (caps at eight)
        assert lines[0] == "  - item-0"
        assert lines[-1] == "  - item-7"

    def test_append_policy_summary_lines_empty_summary_uses_fallback(self) -> None:
        lines: list[str] = []
        bootstrap_text._append_policy_summary_lines(lines, [])
        assert lines == [bootstrap_text.NO_POLICY_SUMMARY_MESSAGE]

    def test_append_block_non_empty_adds_separator_and_block(self) -> None:
        lines: list[str] = ["existing"]
        bootstrap_text._append_block(lines, "new block")
        assert lines == ["existing", "", "new block"]

    def test_append_block_empty_is_a_no_op(self) -> None:
        lines: list[str] = ["existing"]
        bootstrap_text._append_block(lines, "")
        assert lines == ["existing"]

    def test_resolve_authority_block_missing_repo_root_returns_empty(self) -> None:
        selection = DoctrineSelectionConfig()
        assert bootstrap_text._resolve_authority_block(None, selection) == ""

    def test_resolve_authority_block_missing_selection_returns_empty(self, tmp_path: Path) -> None:
        assert bootstrap_text._resolve_authority_block(tmp_path, None) == ""

    def test_resolve_authority_block_delegates_to_renderer(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        selection = DoctrineSelectionConfig()
        captured: dict[str, Any] = {}

        def _fake_render(repo_root: Path, doctrine_selection: DoctrineSelectionConfig) -> str:
            captured["repo_root"] = repo_root
            captured["doctrine_selection"] = doctrine_selection
            return "authority-block-sentinel"

        monkeypatch.setattr(bootstrap_text, "render_authority_paths", _fake_render)

        result = bootstrap_text._resolve_authority_block(tmp_path, selection)

        assert result == "authority-block-sentinel"
        assert captured == {"repo_root": tmp_path, "doctrine_selection": selection}

    def test_resolve_reference_block_missing_repo_root_returns_empty(self) -> None:
        selection = DoctrineSelectionConfig()
        assert bootstrap_text._resolve_reference_block(None, selection) == ""

    def test_resolve_reference_block_missing_selection_returns_empty(self, tmp_path: Path) -> None:
        assert bootstrap_text._resolve_reference_block(tmp_path, None) == ""

    def test_resolve_reference_block_delegates_to_renderer(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        selection = DoctrineSelectionConfig(governance_references=["spec/constitution.md"])
        captured: dict[str, Any] = {}

        def _fake_render(repo_root: Path, references: list[str]) -> str:
            captured["repo_root"] = repo_root
            captured["references"] = references
            return "reference-block-sentinel"

        monkeypatch.setattr(bootstrap_text, "render_governance_references", _fake_render)

        result = bootstrap_text._resolve_reference_block(tmp_path, selection)

        assert result == "reference-block-sentinel"
        assert captured == {"repo_root": tmp_path, "references": ["spec/constitution.md"]}

    def test_append_reference_docs_lines_empty_uses_fallback(self) -> None:
        lines: list[str] = []
        bootstrap_text._append_reference_docs_lines(lines, [])
        assert lines == [bootstrap_text.MISSING_REFERENCES_MESSAGE]

    def test_append_reference_docs_lines_renders_each_pointer(self, tmp_path: Path) -> None:
        lines: list[str] = []
        selected = [
            ({"id": "DIRECTIVE_001", "title": "Some Directive"}, tmp_path / "directive.md"),
            ({"title": "No Id"}, tmp_path / "other.md"),
        ]
        bootstrap_text._append_reference_docs_lines(lines, selected)
        assert lines == [
            f"  - DIRECTIVE_001: Some Directive ({tmp_path / 'directive.md'})",
            f"  - unknown: No Id ({tmp_path / 'other.md'})",
        ]


# ---------------------------------------------------------------------------
# compact_governance.py
# ---------------------------------------------------------------------------


class TestCompactGovernanceSeam:
    def test_compact_section_block_empty_without_action(self, tmp_path: Path) -> None:
        assert compact_governance._compact_section_block(tmp_path, None) == ""

    def test_compact_section_block_empty_without_charter_md(self, tmp_path: Path) -> None:
        assert compact_governance._compact_section_block(tmp_path, "implement") == ""

    def test_render_compact_from_bundle_threads_suppress_project_resolver(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """WP03/#3064 contract: ``suppress_project_resolver`` must reach
        ``render_compact_view`` unchanged through BOTH wrapper layers
        (``_render_compact_from_bundle`` -> ``_render_compact_governance``
        -> ``charter.activation.compact.render_compact_view``) — this is the exact
        seam the reviewer guidance calls out as the highest-risk part of
        this move.
        """
        captured: dict[str, Any] = {}

        class _FakeView:
            text = "compact-view-body"

        def _fake_render_compact_view(_repo_root: Path, **kwargs: Any) -> _FakeView:
            captured.update(kwargs)
            return _FakeView()

        monkeypatch.setattr(
            "charter.activation.compact.render_compact_view", _fake_render_compact_view
        )
        monkeypatch.setattr(
            "charter.activation.context._load_doctrine_selection",
            lambda _repo_root: DoctrineSelectionConfig(),
        )

        class _Bundle:
            directive_ids: list[str] = []
            tactic_ids: list[str] = []
            styleguide_ids: list[str] = []
            toolguide_ids: list[str] = []
            procedure_ids: list[str] = []
            asset_ids: list[str] = []

        compact_governance._render_compact_from_bundle(
            tmp_path,
            action="implement",
            profile=None,
            bundle=_Bundle(),  # type: ignore[arg-type]
            suppress_project_resolver=True,
        )

        assert captured["suppress_project_resolver"] is True

    def test_render_compact_from_bundle_default_does_not_suppress(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, Any] = {}

        class _FakeView:
            text = "compact-view-body"

        def _fake_render_compact_view(_repo_root: Path, **kwargs: Any) -> _FakeView:
            captured.update(kwargs)
            return _FakeView()

        monkeypatch.setattr(
            "charter.activation.compact.render_compact_view", _fake_render_compact_view
        )
        monkeypatch.setattr(
            "charter.activation.context._load_doctrine_selection",
            lambda _repo_root: DoctrineSelectionConfig(),
        )

        class _Bundle:
            directive_ids: list[str] = []
            tactic_ids: list[str] = []
            styleguide_ids: list[str] = []
            toolguide_ids: list[str] = []
            procedure_ids: list[str] = []
            asset_ids: list[str] = []

        compact_governance._render_compact_from_bundle(
            tmp_path,
            action="implement",
            profile=None,
            bundle=_Bundle(),  # type: ignore[arg-type]
        )

        assert captured["suppress_project_resolver"] is False
