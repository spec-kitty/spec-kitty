"""Focused unit tests for the tested-helper extractions made by
charter-sync-sonar-remediation-01KZPPZW WP02 ("Charter complexity group A").

Each Sonar S3776 (Cognitive Complexity) finding in this WP's six owned files
was resolved by extracting deterministic, independently-testable helpers out
of the over-complex function. The originating functions' existing behaviour
is already pinned by each module's own test suite (exercised end-to-end
before/after this WP's refactor); this file adds narrow, direct coverage of
the NEW helper functions themselves, per the WP's "every new
branch/helper needs tests in the same PR" discipline.

Covered helpers, one section per owning file:

* ``charter.activation.evidence.code_reader`` — ``_scan_tree`` / ``_detect_frameworks`` /
  ``_detect_test_frameworks`` / ``_build_stack_id`` (extracted from
  ``CodeReadingCollector._detect``, Sonar complexity 33 -> <=15).
* ``specify_cli.charter_runtime.lint.checks.org_layer`` —
  ``_check_item_overrides_builtin`` / ``_scan_artifact_type_for_overrides``
  (extracted from ``OrgOverridesBuiltinChecker.run``, complexity 29 -> <=15).
* ``charter.activation.context_result_builders`` — ``build_missing_charter_context_result``
  (extracted from ``build_charter_context``, complexity 19 -> <=15).
* ``charter.activation.context_renderers.template_include`` — ``_resolve_include_kind``
  (extracted from ``build_charter_context_include``, complexity 19 -> <=15).
* ``charter.activation.context_renderers.catalog_diagnosis`` — ``_ids_via_listing_attr`` /
  ``_ids_from_items_dict`` (extracted from ``_available_catalog_ids``,
  complexity 20 -> <=15).
* ``charter.activation.compiler`` — ``_detect_local_support_overlap`` /
  ``_local_support_summary`` / ``_local_support_content_lines`` (extracted
  from ``_build_local_support_references``, complexity 20 -> <=15).
* ``charter.activation.consistency_check`` — ``_find_owning_kind`` /
  ``_check_kind_violation_for_artifact`` (extracted from
  ``_check_kind_violations``, complexity 22 -> <=15).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# charter.activation.evidence.code_reader
# ---------------------------------------------------------------------------


class TestCodeReaderHelpers:
    def _make_file(self, path: Path, content: str = "") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def test_scan_tree_buckets_source_and_test_files(self, tmp_path: Path) -> None:
        from charter.activation.evidence.code_reader import CodeReadingCollector

        self._make_file(tmp_path / "pyproject.toml", "")
        self._make_file(tmp_path / "pkg" / "mod.py", "# source")
        self._make_file(tmp_path / "tests" / "test_mod.py", "# test")
        self._make_file(tmp_path / "src" / "index.ts", "export const x = 1;")

        collector = CodeReadingCollector(tmp_path)
        scan = collector._scan_tree()

        assert "pyproject.toml" in scan.indicator_files
        assert any(f.endswith("mod.py") for f in scan.source_files)
        assert any(f.endswith("test_mod.py") for f in scan.test_files)
        assert scan.ts_files == 1
        assert scan.js_files == 0

    def test_scan_tree_prunes_excluded_dirs(self, tmp_path: Path) -> None:
        from charter.activation.evidence.code_reader import CodeReadingCollector

        self._make_file(tmp_path / "node_modules" / "heavy.js", "// dep")
        self._make_file(tmp_path / "keep.py", "# kept")

        scan = CodeReadingCollector(tmp_path)._scan_tree()

        assert not any("node_modules" in f for f in scan.source_files)
        assert any(f.endswith("keep.py") for f in scan.source_files)

    def test_detect_frameworks_matches_indicator_files(self) -> None:
        from charter.activation.evidence.code_reader import CodeReadingCollector

        frameworks = CodeReadingCollector._detect_frameworks(
            {"manage.py", "next.config.ts", "unrelated.txt"}
        )

        assert set(frameworks) == {"django", "nextjs"}

    def test_detect_frameworks_empty_when_no_match(self) -> None:
        from charter.activation.evidence.code_reader import CodeReadingCollector

        assert CodeReadingCollector._detect_frameworks({"README.md"}) == []

    def test_detect_test_frameworks_from_indicator(self) -> None:
        from charter.activation.evidence.code_reader import CodeReadingCollector

        test_fws = CodeReadingCollector._detect_test_frameworks(
            {"jest.config.js"}, [], "javascript"
        )

        assert test_fws == ["jest"]

    def test_detect_test_frameworks_python_pytest_fallback(self) -> None:
        from charter.activation.evidence.code_reader import CodeReadingCollector

        test_fws = CodeReadingCollector._detect_test_frameworks(
            set(), ["tests/test_thing.py"], "python"
        )

        assert test_fws == ["pytest"]

    def test_detect_test_frameworks_no_fallback_for_non_python(self) -> None:
        from charter.activation.evidence.code_reader import CodeReadingCollector

        test_fws = CodeReadingCollector._detect_test_frameworks(
            set(), ["tests/thing.test.ts"], "typescript"
        )

        assert test_fws == []

    def test_build_stack_id_unknown_language_short_circuits(self) -> None:
        from charter.activation.evidence.code_reader import CodeReadingCollector

        assert (
            CodeReadingCollector._build_stack_id("unknown", ["django"], ["pytest"])
            == "unknown"
        )

    def test_build_stack_id_composes_language_framework_test(self) -> None:
        from charter.activation.evidence.code_reader import CodeReadingCollector

        stack_id = CodeReadingCollector._build_stack_id(
            "python", ["django"], ["pytest"]
        )

        assert stack_id == "python+django+pytest"

    def test_build_stack_id_language_only(self) -> None:
        from charter.activation.evidence.code_reader import CodeReadingCollector

        assert CodeReadingCollector._build_stack_id("go", [], []) == "go"


# ---------------------------------------------------------------------------
# specify_cli.charter_runtime.lint.checks.org_layer
# ---------------------------------------------------------------------------


class _StubOverrideRepo:
    def __init__(self, provenance: dict[str, str]) -> None:
        self._provenance = provenance

    def get_provenance(self, item_id: str) -> str | None:
        return self._provenance.get(item_id)


class _StubBuiltinRepo:
    def __init__(self, ids: set[str]) -> None:
        self._ids = ids

    def get(self, item_id: str) -> object | None:
        return object() if item_id in self._ids else None


class _StubArtifact:
    def __init__(self, artifact_id: str) -> None:
        self.id = artifact_id


class TestOrgLayerHelpers:
    def test_check_item_overrides_builtin_reports_org_shadowing(self) -> None:
        from specify_cli.charter_runtime.lint.checks.org_layer import (
            _check_item_overrides_builtin,
        )

        org_repo = _StubOverrideRepo({"DIRECTIVE_001": "org"})
        built_in_repo = _StubBuiltinRepo({"DIRECTIVE_001"})

        finding = _check_item_overrides_builtin(
            "directives", _StubArtifact("DIRECTIVE_001"), org_repo, built_in_repo
        )

        assert finding is not None
        assert finding.type == "org_overrides_builtin"
        assert finding.severity == "low"
        assert finding.id == "directives:DIRECTIVE_001"

    def test_check_item_overrides_builtin_skips_non_org_provenance(self) -> None:
        from specify_cli.charter_runtime.lint.checks.org_layer import (
            _check_item_overrides_builtin,
        )

        org_repo = _StubOverrideRepo({"DIRECTIVE_001": "built_in"})
        built_in_repo = _StubBuiltinRepo({"DIRECTIVE_001"})

        finding = _check_item_overrides_builtin(
            "directives", _StubArtifact("DIRECTIVE_001"), org_repo, built_in_repo
        )

        assert finding is None

    def test_check_item_overrides_builtin_skips_missing_builtin_match(self) -> None:
        from specify_cli.charter_runtime.lint.checks.org_layer import (
            _check_item_overrides_builtin,
        )

        org_repo = _StubOverrideRepo({"ORG_ONLY": "org"})
        built_in_repo = _StubBuiltinRepo(set())

        finding = _check_item_overrides_builtin(
            "directives", _StubArtifact("ORG_ONLY"), org_repo, built_in_repo
        )

        assert finding is None

    def test_check_item_overrides_builtin_skips_non_string_id(self) -> None:
        from specify_cli.charter_runtime.lint.checks.org_layer import (
            _check_item_overrides_builtin,
        )

        class _NoId:
            id = None

        finding = _check_item_overrides_builtin(
            "directives", _NoId(), _StubOverrideRepo({}), _StubBuiltinRepo(set())
        )

        assert finding is None

    def test_scan_artifact_type_for_overrides_aggregates_findings(self) -> None:
        from specify_cli.charter_runtime.lint.checks.org_layer import (
            _scan_artifact_type_for_overrides,
        )

        class _StubService:
            def __init__(self, org_repo: object, built_in_repo: object) -> None:
                self._org_repo = org_repo
                self._built_in_repo = built_in_repo

            def raw_repository(self, _artifact_type: str) -> object:
                return self._org_repo

        class _StubListingRepo(_StubOverrideRepo):
            def list_all(self) -> list[_StubArtifact]:
                return [_StubArtifact("DIRECTIVE_001"), _StubArtifact("DIRECTIVE_002")]

        org_repo = _StubListingRepo(
            {"DIRECTIVE_001": "org", "DIRECTIVE_002": "builtin"}
        )
        built_in_repo = _StubBuiltinRepo({"DIRECTIVE_001", "DIRECTIVE_002"})

        service = _StubService(org_repo, org_repo)
        built_in_only = _StubService(built_in_repo, built_in_repo)

        findings = _scan_artifact_type_for_overrides(
            "directives", service, built_in_only
        )

        assert len(findings) == 1
        assert findings[0].id == "directives:DIRECTIVE_001"

    def test_scan_artifact_type_for_overrides_missing_repo_returns_empty(self) -> None:
        from specify_cli.charter_runtime.lint.checks.org_layer import (
            _scan_artifact_type_for_overrides,
        )

        class _NoRepoService:
            def raw_repository(self, _artifact_type: str) -> object | None:
                return None

        findings = _scan_artifact_type_for_overrides(
            "directives", _NoRepoService(), _NoRepoService()
        )

        assert findings == []


# ---------------------------------------------------------------------------
# charter.activation.context_result_builders
# ---------------------------------------------------------------------------


class TestContextResultBuilders:
    def test_build_missing_charter_context_result(self, tmp_path: Path) -> None:
        from charter.activation.context_result_builders import build_missing_charter_context_result
        from charter.activation.context_state import _ContextStateBundle

        state_bundle = _ContextStateBundle(
            state_path=tmp_path / "context-state.json",
            state={"schema_version": "1.0.0", "actions": {}},
            first_load=True,
            effective_depth=2,
        )

        result = build_missing_charter_context_result(
            "specify", state_bundle, augment=lambda text: text
        )

        assert result.mode == "missing"
        assert result.action == "specify"
        assert result.first_load is True
        assert result.depth == 2
        assert "Charter file not found" in result.text

    def test_build_missing_charter_context_result_applies_augment(self, tmp_path: Path) -> None:
        from charter.activation.context_result_builders import build_missing_charter_context_result
        from charter.activation.context_state import _ContextStateBundle

        state_bundle = _ContextStateBundle(
            state_path=tmp_path / "context-state.json",
            state={"schema_version": "1.0.0", "actions": {}},
            first_load=False,
            effective_depth=1,
        )

        result = build_missing_charter_context_result(
            "plan",
            state_bundle,
            augment=lambda text: "PREFIX\n\n" + text,
        )

        assert result.text.startswith("PREFIX\n\n")
        assert result.first_load is False


# ---------------------------------------------------------------------------
# charter.activation.context_renderers.template_include
# ---------------------------------------------------------------------------


class TestResolveIncludeKind:
    def test_resolve_include_kind_normalises_hyphenated_token(self) -> None:
        from charter.offering.artifact_kinds import ArtifactKind

        from charter.activation.context_renderers.template_include import _resolve_include_kind

        resolved = _resolve_include_kind("agent-profile", "agent-profile:x")

        assert resolved is ArtifactKind.AGENT_PROFILE

    def test_resolve_include_kind_rejects_mission_type(self) -> None:
        from charter.activation.context_renderers.template_include import _resolve_include_kind

        with pytest.raises(ValueError, match="mission-type"):
            _resolve_include_kind("mission-type", "mission-type:software-dev")

    def test_resolve_include_kind_unknown_token_fails_closed(self) -> None:
        from charter.activation.context_renderers.template_include import _resolve_include_kind

        with pytest.raises(Exception):  # noqa: B017 -- canonical vocabulary error, class not re-exported here
            _resolve_include_kind("not-a-real-kind", "not-a-real-kind:x")


# ---------------------------------------------------------------------------
# charter.activation.context_renderers.catalog_diagnosis
# ---------------------------------------------------------------------------


class TestCatalogDiagnosisHelpers:
    def test_ids_via_listing_attr_uses_list_all(self) -> None:
        from charter.activation.context_renderers.catalog_diagnosis import _ids_via_listing_attr

        class _Item:
            def __init__(self, id_: str) -> None:
                self.id = id_

        class _Repo:
            def list_all(self) -> list[_Item]:
                return [_Item("a"), _Item("b")]

        ids = _ids_via_listing_attr(_Repo(), "list_all")

        assert ids == ["a", "b"]

    def test_ids_via_listing_attr_returns_none_when_not_callable(self) -> None:
        from charter.activation.context_renderers.catalog_diagnosis import _ids_via_listing_attr

        class _Repo:
            list_all = "not callable"

        assert _ids_via_listing_attr(_Repo(), "list_all") is None

    def test_ids_via_listing_attr_returns_none_on_exception(self) -> None:
        from charter.activation.context_renderers.catalog_diagnosis import _ids_via_listing_attr

        class _Repo:
            def list_all(self) -> list[str]:
                raise RuntimeError("boom")

        assert _ids_via_listing_attr(_Repo(), "list_all") is None

    def test_ids_from_items_dict_filters_string_keys(self) -> None:
        from charter.activation.context_renderers.catalog_diagnosis import _ids_from_items_dict

        class _Repo:
            _items = {"a": object(), "b": object()}

        assert sorted(_ids_from_items_dict(_Repo())) == ["a", "b"]

    def test_ids_from_items_dict_returns_empty_without_items(self) -> None:
        from charter.activation.context_renderers.catalog_diagnosis import _ids_from_items_dict

        assert _ids_from_items_dict(object()) == []


# ---------------------------------------------------------------------------
# charter.activation.compiler
# ---------------------------------------------------------------------------


class TestLocalSupportHelpers:
    def test_detect_local_support_overlap_records_diagnostic(self) -> None:
        from charter.activation.compiler import _detect_local_support_overlap
        from charter.activation.interview import LocalSupportDeclaration

        decl = LocalSupportDeclaration(
            path="docs/x.md", target_kind="directive", target_id="DIRECTIVE_001"
        )
        diagnostics: list[str] = []

        # built_in_ids carries "<KIND>:<ID>" keys (see
        # charter.activation.compiler._build_built_in_concept_ids), not bare artifact ids.
        warning = _detect_local_support_overlap(
            decl, frozenset({"DIRECTIVE:DIRECTIVE_001"}), diagnostics
        )

        assert warning is not None
        assert "overlaps built-in" in warning
        assert len(diagnostics) == 1  # (records exactly one)

    def test_detect_local_support_overlap_no_target_returns_none(self) -> None:
        from charter.activation.compiler import _detect_local_support_overlap
        from charter.activation.interview import LocalSupportDeclaration

        decl = LocalSupportDeclaration(path="docs/x.md")
        diagnostics: list[str] = []

        assert _detect_local_support_overlap(decl, frozenset(), diagnostics) is None
        assert diagnostics == []

    def test_detect_local_support_overlap_no_overlap_returns_none(self) -> None:
        from charter.activation.compiler import _detect_local_support_overlap
        from charter.activation.interview import LocalSupportDeclaration

        decl = LocalSupportDeclaration(
            path="docs/x.md", target_kind="directive", target_id="DIRECTIVE_999"
        )
        diagnostics: list[str] = []

        assert (
            _detect_local_support_overlap(
                decl, frozenset({"DIRECTIVE:DIRECTIVE_001"}), diagnostics
            )
            is None
        )
        assert diagnostics == []

    def test_local_support_summary_includes_target_and_action(self) -> None:
        from charter.activation.compiler import _local_support_summary
        from charter.activation.interview import LocalSupportDeclaration

        decl = LocalSupportDeclaration(
            path="docs/x.md",
            action="implement",
            target_kind="directive",
            target_id="DIRECTIVE_001",
        )

        summary = _local_support_summary(decl)

        assert "supplements directive DIRECTIVE_001" in summary
        assert "(action: implement)" in summary

    def test_local_support_summary_bare_declaration(self) -> None:
        from charter.activation.compiler import _local_support_summary
        from charter.activation.interview import LocalSupportDeclaration

        decl = LocalSupportDeclaration(path="docs/x.md")

        assert _local_support_summary(decl) == "Local support file."

    def test_local_support_content_lines_includes_warning(self) -> None:
        from charter.activation.compiler import _local_support_content_lines
        from charter.activation.interview import LocalSupportDeclaration

        decl = LocalSupportDeclaration(
            path="docs/x.md",
            action="implement",
            target_kind="directive",
            target_id="DIRECTIVE_001",
        )

        lines = _local_support_content_lines(decl, "x.md", "overlap warning")

        assert "- Warning: overlap warning" in lines
        assert "- Action scope: `implement`" in lines
        assert "- Target kind: `directive`" in lines
        assert "- Target ID: `DIRECTIVE_001`" in lines

    def test_local_support_content_lines_no_warning_omits_line(self) -> None:
        from charter.activation.compiler import _local_support_content_lines
        from charter.activation.interview import LocalSupportDeclaration

        decl = LocalSupportDeclaration(path="docs/x.md")

        lines = _local_support_content_lines(decl, "x.md", None)

        assert not any(line.startswith("- Warning:") for line in lines)


# ---------------------------------------------------------------------------
# charter.activation.consistency_check
# ---------------------------------------------------------------------------


class TestKindViolationHelpers:
    def test_find_owning_kind_returns_first_match(self) -> None:
        from charter.activation.consistency_check import _find_owning_kind

        all_ids = {
            "directives": frozenset({"X"}),
            "tactics": frozenset({"Y"}),
        }

        assert _find_owning_kind("Y", "directives", all_ids) == "tactics"

    def test_find_owning_kind_excludes_own_kind(self) -> None:
        from charter.activation.consistency_check import _find_owning_kind

        all_ids = {"directives": frozenset({"X"})}

        assert _find_owning_kind("X", "directives", all_ids) is None

    def test_find_owning_kind_returns_none_when_unowned(self) -> None:
        from charter.activation.consistency_check import _find_owning_kind

        all_ids = {"directives": frozenset({"X"}), "tactics": frozenset({"Y"})}

        assert _find_owning_kind("Z", "directives", all_ids) is None

    def test_check_kind_violation_for_artifact_records_mismatch(self) -> None:
        from charter.activation.consistency_check import _check_kind_violation_for_artifact

        all_ids = {"directives": frozenset(), "tactics": frozenset({"X"})}
        kind_violations: list[str] = []

        _check_kind_violation_for_artifact(
            "directives", "X", frozenset(), all_ids, [], kind_violations
        )

        assert len(kind_violations) == 1
        assert "belongs to kind 'tactics', not 'directives'" in kind_violations[0]

    def test_check_kind_violation_for_artifact_skips_already_flagged(self) -> None:
        from charter.activation.consistency_check import _check_kind_violation_for_artifact

        all_ids = {"directives": frozenset(), "tactics": frozenset({"X"})}
        kind_violations: list[str] = []

        _check_kind_violation_for_artifact(
            "directives",
            "X",
            frozenset(),
            all_ids,
            ["directives/X"],
            kind_violations,
        )

        assert kind_violations == []

    def test_check_kind_violation_for_artifact_skips_correct_kind(self) -> None:
        from charter.activation.consistency_check import _check_kind_violation_for_artifact

        all_ids = {"directives": frozenset({"X"})}
        kind_violations: list[str] = []

        _check_kind_violation_for_artifact(
            "directives", "X", frozenset({"X"}), all_ids, [], kind_violations
        )

        assert kind_violations == []
