"""RISK-3 (Mission B post-merge) — catalog-miss surfacing tests.

Pins the behaviour added by mission ``layered-doctrine-org-layer`` /
RISK-3 remediation: the renderer must no longer hide catalog misses
behind a generic ``(catalog entry not found; verify charter selection)``
placeholder.  Instead it emits a structured stanza that classifies the
cause (typo / missing / schema-validation-suspected), provides an
actionable suggestion, and routes a warning through both
``warnings.warn`` (so it surfaces in normal stderr) and the module
logger (so it appears in any structured log surface).

Coverage:

* :class:`TestClassifyCatalogMiss` — pure-function classification.
* :class:`TestFormatCatalogMissStanza` — the rendered stanza shape.
* :class:`TestEmitCatalogMissWarning` — warning + logger plumbing.
* :class:`TestRendererIntegration` — end-to-end through
  ``_render_selected_styleguides`` covering the three documented causes
  (typo, missing artifact, schema-failure suggestion).
* :class:`TestProfileRendererIntegration` — same surfacing for profile-
  cited directive misses.
* :class:`TestOncePerProcessEmissionLatch` — #4572: each distinct
  ``(kind, id)`` miss surfaces at most once per process.
* :class:`TestScopeFilteredAgentProfileQuietPolicy` — #4572: a
  scope-filtered ``agent_profile`` is not reported as a catalog miss
  (``agent profile list`` reports it available); other kinds
  unchanged.
* :class:`TestAgentProfileCatalogListReconciliation` — #4572 live
  render path: the agent-profile selection render agrees with the
  profile-list availability surface.
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from charter.activation._catalog_miss import (
    CatalogMissCause,
    CatalogMissDiagnosis,
    CharterCatalogMissError,
    CharterCatalogMissWarning,
    classify_catalog_miss,
    classify_scope_filtered_miss,
    emit_catalog_miss_warning,
    format_catalog_miss_stanza,
)
from charter.activation.context_renderers.profile_sections import _render_profile_directives
from charter.activation.context_renderers.selection_block import (
    _render_selected_agent_profiles,
    _render_selected_styleguides,
)
from charter.offering.agent_profiles import AgentProfile
from charter.offering.agent_profiles.repository import AgentProfileRepository
from charter.offering.styleguides.repository import StyleguideRepository


pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Stubs (intentionally minimal — exercise only the catalog-miss path)
# ---------------------------------------------------------------------------


class _StubRepo:
    """Repository stub that exposes ``get`` and ``list_all``.

    The catalog-miss diagnosis path uses ``list_all`` (preferred) or
    falls back to the stub's ``_items`` dict, so we exercise the
    canonical surface here.
    """

    def __init__(self, items: dict[str, Any] | None = None) -> None:
        self._items = items or {}

    def get(self, item_id: str) -> Any | None:
        return self._items.get(item_id)

    def list_all(self) -> list[Any]:
        return list(self._items.values())


class _Item:
    """Bare object carrying an ``id`` attribute for ``list_all`` iteration."""

    def __init__(self, item_id: str, **extra: Any) -> None:
        self.id = item_id
        for key, value in extra.items():
            setattr(self, key, value)


class _StubService:
    def __init__(self, *, styleguides: _StubRepo | None = None) -> None:
        self.styleguides = styleguides or _StubRepo()


# ---------------------------------------------------------------------------
# Pure-function classification
# ---------------------------------------------------------------------------


class TestClassifyCatalogMiss:
    def test_typo_returns_typo_suspected_with_closest_match(self) -> None:
        diagnosis = classify_catalog_miss(
            "caveman-comemnts",
            ["caveman-comments", "verbose-comments", "tdd-discipline"],
        )
        assert diagnosis.cause is CatalogMissCause.TYPO_SUSPECTED
        assert diagnosis.suggestion == "caveman-comments"

    def test_no_close_match_returns_missing_artifact(self) -> None:
        diagnosis = classify_catalog_miss(
            "completely-unrelated-name",
            ["alpha", "beta", "gamma"],
        )
        assert diagnosis.cause is CatalogMissCause.MISSING_ARTIFACT
        assert diagnosis.suggestion is None

    def test_empty_corpus_returns_missing_artifact(self) -> None:
        diagnosis = classify_catalog_miss("anything", [])
        assert diagnosis.cause is CatalogMissCause.MISSING_ARTIFACT
        assert diagnosis.suggestion is None

    def test_non_string_corpus_entries_ignored(self) -> None:
        # Defensive: the corpus may come from a duck-typed source.
        diagnosis = classify_catalog_miss(
            "caveman-comments",
            ["caveman-comments", 42, None],  # type: ignore[list-item]
        )
        assert diagnosis.cause is CatalogMissCause.TYPO_SUSPECTED


# ---------------------------------------------------------------------------
# T022 — SCOPE_FILTERED classification (FR-013)
# ---------------------------------------------------------------------------


class TestClassifyScopeFilteredMiss:
    """classify_scope_filtered_miss returns SCOPE_FILTERED for a present-but-filtered artifact."""

    def test_returns_scope_filtered_cause(self) -> None:
        """FR-013: cause must be SCOPE_FILTERED, not MISSING_ARTIFACT."""
        diagnosis = classify_scope_filtered_miss("python-style", ["python"])
        assert diagnosis.cause is CatalogMissCause.SCOPE_FILTERED

    def test_suggestion_names_the_active_language(self) -> None:
        """The suggestion should mention the active language set."""
        diagnosis = classify_scope_filtered_miss("python-style", ["python"])
        assert diagnosis.suggestion is not None
        assert "python" in diagnosis.suggestion

    def test_no_active_languages_still_scope_filtered(self) -> None:
        """Even with no active language context, cause is SCOPE_FILTERED."""
        diagnosis = classify_scope_filtered_miss("python-style")
        assert diagnosis.cause is CatalogMissCause.SCOPE_FILTERED
        assert diagnosis.suggestion is not None

    def test_suggestion_mentions_applies_to_languages_field(self) -> None:
        """The suggestion must point at the scope cause (applies_to_languages)."""
        diagnosis = classify_scope_filtered_miss("python-style", ["rust"])
        assert diagnosis.suggestion is not None
        assert "applies_to_languages" in diagnosis.suggestion or "scope" in diagnosis.suggestion

    def test_scope_filtered_is_distinct_from_missing_artifact(self) -> None:
        """SCOPE_FILTERED must not be equal to MISSING_ARTIFACT."""
        assert CatalogMissCause.SCOPE_FILTERED != CatalogMissCause.MISSING_ARTIFACT

    def test_format_stanza_includes_scope_cause(self) -> None:
        """format_catalog_miss_stanza renders a SCOPE_FILTERED cause correctly."""
        diagnosis = classify_scope_filtered_miss("python-style", ["python"])
        lines = format_catalog_miss_stanza(
            selector_kind="styleguide",
            artifact_id="python-style",
            diagnosis=diagnosis,
        )
        joined = "\n".join(lines)
        assert "scope_filtered" in joined
        assert "styleguide:python-style" in joined


# ---------------------------------------------------------------------------
# Stanza formatting
# ---------------------------------------------------------------------------


class TestFormatCatalogMissStanza:
    def test_typo_stanza_includes_did_you_mean(self) -> None:
        diagnosis = CatalogMissDiagnosis(
            cause=CatalogMissCause.TYPO_SUSPECTED,
            suggestion="caveman-comments",
        )
        lines = format_catalog_miss_stanza(
            selector_kind="styleguide",
            artifact_id="caveman-comemnts",
            diagnosis=diagnosis,
        )
        joined = "\n".join(lines)
        assert "styleguide:caveman-comemnts" in joined
        assert "Cause: typo_suspected" in joined
        assert "did you mean 'caveman-comments'?" in joined

    def test_missing_artifact_stanza_suggests_both_paths(self) -> None:
        diagnosis = CatalogMissDiagnosis(cause=CatalogMissCause.MISSING_ARTIFACT)
        lines = format_catalog_miss_stanza(
            selector_kind="tactic",
            artifact_id="ghost-tactic",
            diagnosis=diagnosis,
        )
        joined = "\n".join(lines)
        assert "tactic:ghost-tactic" in joined
        assert "Cause: missing_artifact" in joined
        # Missing-artifact stanza must mention BOTH possible causes.
        assert "doctrine validate" in joined
        assert "project, org, and built-in" in joined

    def test_schema_failure_stanza_cites_doctrine_validate(self) -> None:
        diagnosis = CatalogMissDiagnosis(
            cause=CatalogMissCause.SCHEMA_VALIDATION_SUSPECTED
        )
        lines = format_catalog_miss_stanza(
            selector_kind="styleguide",
            artifact_id="caveman-comments",
            diagnosis=diagnosis,
        )
        joined = "\n".join(lines)
        assert "Cause: schema_validation_suspected" in joined
        assert "spec-kitty doctrine validate" in joined
        assert "Pydantic validation" in joined

    def test_indent_is_respected(self) -> None:
        diagnosis = CatalogMissDiagnosis(cause=CatalogMissCause.MISSING_ARTIFACT)
        lines = format_catalog_miss_stanza(
            selector_kind="procedure",
            artifact_id="x",
            diagnosis=diagnosis,
            indent="        ",
        )
        for line in lines:
            assert line.startswith("        ")


# ---------------------------------------------------------------------------
# Warning + logger plumbing
# ---------------------------------------------------------------------------


class TestEmitCatalogMissWarning:
    def test_warning_class_and_message(self) -> None:
        diagnosis = CatalogMissDiagnosis(
            cause=CatalogMissCause.TYPO_SUSPECTED,
            suggestion="caveman-comments",
        )
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            emit_catalog_miss_warning(
                selector_kind="styleguide",
                artifact_id="caveman-comemnts",
                diagnosis=diagnosis,
            )
        miss_warnings = [
            w for w in captured if issubclass(w.category, CharterCatalogMissWarning)
        ]
        assert len(miss_warnings) == 1
        text = str(miss_warnings[0].message)
        assert "styleguide:caveman-comemnts" in text
        assert "cause=typo_suspected" in text
        assert "suggestion='caveman-comments'" in text

    def test_logger_extra_carries_structured_fields(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        diagnosis = CatalogMissDiagnosis(cause=CatalogMissCause.MISSING_ARTIFACT)
        with (
            caplog.at_level(logging.WARNING, logger="charter.activation._catalog_miss"),
            warnings.catch_warnings(),
        ):
            warnings.simplefilter("ignore", CharterCatalogMissWarning)
            emit_catalog_miss_warning(
                selector_kind="tactic",
                artifact_id="ghost",
                diagnosis=diagnosis,
                context="profile:python-pedro",
            )
        relevant = [
            r for r in caplog.records if r.name == "charter.activation._catalog_miss"
        ]
        assert {
            (r.kind, r.id, r.cause, r.context)  # type: ignore[attr-defined]
            for r in relevant
        } == {("tactic", "ghost", "missing_artifact", "profile:python-pedro")}
        record = relevant[0]
        assert record.kind == "tactic"  # type: ignore[attr-defined]
        assert record.id == "ghost"  # type: ignore[attr-defined]
        assert record.cause == "missing_artifact"  # type: ignore[attr-defined]
        assert record.context == "profile:python-pedro"  # type: ignore[attr-defined]

    def test_exception_class_is_distinct_from_value_error(self) -> None:
        err = CharterCatalogMissError(
            "styleguide:x",
            cause=CatalogMissCause.MISSING_ARTIFACT,
        )
        assert isinstance(err, Exception)
        assert not isinstance(err, ValueError)
        assert err.selector == "styleguide:x"
        assert err.cause is CatalogMissCause.MISSING_ARTIFACT


# ---------------------------------------------------------------------------
# Renderer integration — the three documented cases
# ---------------------------------------------------------------------------


class TestRendererIntegration:
    """End-to-end: catalog-miss flows through the renderer and surfaces."""

    def test_typo_case_renders_suggestion_and_warns(self) -> None:
        # Catalog carries the canonical ID; charter selected a typo.
        sg = _Item("caveman-comments", title="Caveman", principles=["UGG"])
        service = _StubService(
            styleguides=_StubRepo(items={"caveman-comments": sg})
        )
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            lines = _render_selected_styleguides(["caveman-comemnts"], service)
        joined = "\n".join(lines)

        # Stanza content
        assert "styleguide:caveman-comemnts" in joined
        assert "Cause: typo_suspected" in joined
        assert "did you mean 'caveman-comments'?" in joined
        # Fetch stanza still present so the prompt remains actionable.
        assert (
            "spec-kitty charter context --include styleguide:caveman-comemnts"
            in joined
        )

        # Warning surfaced through the standard channel.
        miss = [
            w for w in captured if issubclass(w.category, CharterCatalogMissWarning)
        ]
        assert len(miss) == 1
        assert "typo_suspected" in str(miss[0].message)

    def test_missing_artifact_case_renders_dual_hint_and_warns(self) -> None:
        # No close match available — cause is MISSING_ARTIFACT, stanza
        # suggests both layer-check and `doctrine validate`.
        service = _StubService(
            styleguides=_StubRepo(
                items={
                    "alpha-style": _Item("alpha-style"),
                    "beta-style": _Item("beta-style"),
                }
            )
        )
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            lines = _render_selected_styleguides(
                ["totally-distinct-name"], service
            )
        joined = "\n".join(lines)

        assert "styleguide:totally-distinct-name" in joined
        assert "Cause: missing_artifact" in joined
        assert "doctrine validate" in joined
        assert "project, org, and built-in" in joined

        miss = [
            w for w in captured if issubclass(w.category, CharterCatalogMissWarning)
        ]
        assert len(miss) == 1
        assert "missing_artifact" in str(miss[0].message)

    def test_schema_failure_case_surfaces_validate_hint(self) -> None:
        # Simulates the RISK-2 root cause: the loader silently dropped
        # the artifact because Pydantic ``extra='forbid'`` rejected it.
        # From the renderer's perspective, the catalog simply doesn't
        # carry the ID — but because no close match is available either,
        # the MISSING_ARTIFACT stanza's dual-hint (which includes the
        # `doctrine validate` advice) is exactly the surface we need.
        service = _StubService(styleguides=_StubRepo(items={}))
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            lines = _render_selected_styleguides(
                ["dropped-by-schema-validation"], service
            )
        joined = "\n".join(lines)

        assert "Cause: missing_artifact" in joined
        # The actionable hint pointing at the validate command must be
        # present so an operator hit by a schema-drop has a clear next
        # step (this is the RISK-3 contract).
        assert "spec-kitty doctrine validate" in joined

        miss = [
            w for w in captured if issubclass(w.category, CharterCatalogMissWarning)
        ]
        assert len(miss) == 1


# ---------------------------------------------------------------------------
# Profile-cited renderer integration
# ---------------------------------------------------------------------------


class TestProfileRendererIntegration:
    """Profile-cited directive misses route through the same surface."""

    def test_profile_cited_directive_miss_warns_with_profile_context(
        self,
    ) -> None:
        profile = AgentProfile.model_validate(
            {
                "profile-id": "ghost-cite",
                "name": "Ghost Cite",
                "roles": ["implementer"],
                "purpose": "test fixture",
                "specialization": {"primary-focus": "testing"},
                "directive-references": [
                    {
                        "code": "999",
                        "name": "Nonexistent",
                        "rationale": "force a miss",
                    }
                ],
            }
        )

        class _DirRepoEmpty:
            def get(self, _code: str) -> Any | None:
                return None

            def list_all(self) -> list[Any]:
                return []

        class _ServiceWithDirectives:
            directives = _DirRepoEmpty()

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            lines = _render_profile_directives(profile, _ServiceWithDirectives())
        joined = "\n".join(lines)

        # Structured stanza, not the legacy placeholder.
        assert "directive:DIRECTIVE_999" in joined
        assert "Cause: missing_artifact" in joined

        # Warning carries the profile context so log aggregators can
        # correlate the miss to the offending profile.
        miss = [
            w for w in captured if issubclass(w.category, CharterCatalogMissWarning)
        ]
        assert len(miss) == 1
        assert "profile:ghost-cite" in str(miss[0].message)


# ---------------------------------------------------------------------------
# FR-013 — scope-filtered miss wiring (live render path)
# ---------------------------------------------------------------------------


def _write_styleguide_yaml(directory: Path, filename: str, data: dict) -> None:
    """Write a styleguide YAML fixture into *directory*."""
    directory.mkdir(parents=True, exist_ok=True)
    y = YAML()
    y.default_flow_style = False
    with (directory / filename).open("w") as fh:
        y.dump(data, fh)


class TestScopeFilteredRendererIntegration:
    """FR-013: scope-filtered artifacts surface SCOPE_FILTERED, not MISSING_ARTIFACT.

    Uses a real StyleguideRepository to exercise the full live render path
    (base.py → scope_filtered_ids → context.py → _diagnose_catalog_miss).
    The artifact exists on disk and passes schema validation, but its
    applies_to_languages scope does not include the active language set.
    """

    def test_scope_filtered_styleguide_renders_scope_filtered_cause(
        self, tmp_path: Path
    ) -> None:
        """Artifact present but scope-filtered must emit SCOPE_FILTERED stanza."""
        built_in_dir = tmp_path / "built-in"
        _write_styleguide_yaml(
            built_in_dir,
            "python-style.styleguide.yaml",
            {
                "schema_version": "1.0",
                "id": "python-style",
                "title": "Python Style Guide",
                "scope": "code",
                "principles": ["Follow PEP 8"],
                "applies_to_languages": ["python"],
            },
        )

        # Active language set does NOT include "python" — artifact is scope-filtered.
        repo = StyleguideRepository(
            built_in_dir=built_in_dir, active_languages=["java"]
        )

        # The artifact must be scope-filtered, not in the loaded catalog.
        assert repo.get("python-style") is None
        assert "python-style" in repo.scope_filtered_ids

        class _ServiceWithRealRepo:
            styleguides = repo

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            lines = _render_selected_styleguides(["python-style"], _ServiceWithRealRepo())

        joined = "\n".join(lines)

        # FR-013 contract: stanza must classify as SCOPE_FILTERED, not MISSING_ARTIFACT.
        assert "Cause: scope_filtered" in joined, (
            f"Expected 'Cause: scope_filtered' but got:\n{joined}"
        )
        assert "styleguide:python-style" in joined

        # The suggestion must mention the applies_to_languages scope cause.
        assert "applies_to_languages" in joined or "scope" in joined

        # Warning must also carry scope_filtered.
        miss = [
            w for w in captured if issubclass(w.category, CharterCatalogMissWarning)
        ]
        assert len(miss) == 1
        assert "scope_filtered" in str(miss[0].message)

    def test_genuinely_absent_artifact_still_emits_missing_artifact(
        self, tmp_path: Path
    ) -> None:
        """Unrelated artifact IDs still yield MISSING_ARTIFACT (no regression)."""
        built_in_dir = tmp_path / "built-in"
        _write_styleguide_yaml(
            built_in_dir,
            "alpha-style.styleguide.yaml",
            {
                "schema_version": "1.0",
                "id": "alpha-style",
                "title": "Alpha Style",
                "scope": "code",
                "principles": ["Keep it simple"],
            },
        )

        repo = StyleguideRepository(
            built_in_dir=built_in_dir, active_languages=["python"]
        )

        class _ServiceWithRealRepo:
            styleguides = repo

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            lines = _render_selected_styleguides(
                ["completely-absent-id"], _ServiceWithRealRepo()
            )

        joined = "\n".join(lines)

        # Regression guard: genuinely absent artifact must still be MISSING_ARTIFACT.
        assert "Cause: missing_artifact" in joined
        assert "Cause: scope_filtered" not in joined


# ---------------------------------------------------------------------------
# #4572 — once-per-process emission + agent-profile/list reconciliation
# ---------------------------------------------------------------------------


def _write_agent_profile_yaml(directory: Path, filename: str, data: dict) -> None:
    """Write an agent-profile YAML fixture into *directory*."""
    directory.mkdir(parents=True, exist_ok=True)
    y = YAML()
    y.default_flow_style = False
    with open(directory / filename, "w", encoding="utf-8") as fh:
        y.dump(data, fh)


class TestOncePerProcessEmissionLatch:
    """#4572: each distinct ``(kind, id)`` miss surfaces at most once per process."""

    def test_repeat_emission_of_same_miss_is_suppressed(self) -> None:
        diagnosis = CatalogMissDiagnosis(cause=CatalogMissCause.MISSING_ARTIFACT)
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            for _ in range(3):
                emit_catalog_miss_warning(
                    selector_kind="styleguide",
                    artifact_id="repeat-miss",
                    diagnosis=diagnosis,
                )
        miss = [
            w for w in captured if issubclass(w.category, CharterCatalogMissWarning)
        ]
        assert len(miss) == 1

    def test_distinct_misses_each_still_emit(self) -> None:
        diagnosis = CatalogMissDiagnosis(cause=CatalogMissCause.MISSING_ARTIFACT)
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            emit_catalog_miss_warning(
                selector_kind="styleguide", artifact_id="miss-a", diagnosis=diagnosis
            )
            emit_catalog_miss_warning(
                selector_kind="tactic", artifact_id="miss-a", diagnosis=diagnosis
            )
            emit_catalog_miss_warning(
                selector_kind="styleguide", artifact_id="miss-b", diagnosis=diagnosis
            )
        miss = [
            w for w in captured if issubclass(w.category, CharterCatalogMissWarning)
        ]
        assert len(miss) == 3

    def test_reset_helper_rearms_emission(self) -> None:
        from charter.activation._catalog_miss import _reset_emitted_for_testing

        diagnosis = CatalogMissDiagnosis(cause=CatalogMissCause.MISSING_ARTIFACT)
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            emit_catalog_miss_warning(
                selector_kind="styleguide", artifact_id="latch-reset", diagnosis=diagnosis
            )
            emit_catalog_miss_warning(
                selector_kind="styleguide", artifact_id="latch-reset", diagnosis=diagnosis
            )
            _reset_emitted_for_testing()
            emit_catalog_miss_warning(
                selector_kind="styleguide", artifact_id="latch-reset", diagnosis=diagnosis
            )
        miss = [
            w for w in captured if issubclass(w.category, CharterCatalogMissWarning)
        ]
        assert len(miss) == 2


class TestScopeFilteredAgentProfileQuietPolicy:
    """#4572: a scope-filtered agent profile is not reported as a catalog miss.

    ``agent profile list`` reads the ungated catalog (FR-008) and reports a
    language-scoped profile as available; warning "catalog miss" for the same
    id on the render path contradicted that availability surface. Every other
    kind keeps the FR-013 contract — a scope-filtered miss still warns.
    """

    def test_scope_filtered_agent_profile_emits_no_warning_and_no_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        diagnosis = classify_scope_filtered_miss("java-jenny", ["python"])
        with (
            caplog.at_level(logging.WARNING, logger="charter.activation._catalog_miss"),
            warnings.catch_warnings(record=True) as captured,
        ):
            warnings.simplefilter("always")
            emit_catalog_miss_warning(
                selector_kind="agent_profile",
                artifact_id="java-jenny",
                diagnosis=diagnosis,
            )
        miss = [
            w for w in captured if issubclass(w.category, CharterCatalogMissWarning)
        ]
        assert miss == []
        assert [
            r for r in caplog.records if r.name == "charter.activation._catalog_miss"
        ] == []

    def test_scope_filtered_styleguide_still_warns(self) -> None:
        """FR-013 unchanged for non-profile kinds (regression guard)."""
        diagnosis = classify_scope_filtered_miss("python-style", ["java"])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            emit_catalog_miss_warning(
                selector_kind="styleguide",
                artifact_id="python-style",
                diagnosis=diagnosis,
            )
        miss = [
            w for w in captured if issubclass(w.category, CharterCatalogMissWarning)
        ]
        assert len(miss) == 1
        assert "scope_filtered" in str(miss[0].message)

    def test_missing_agent_profile_still_warns(self) -> None:
        """A genuinely absent profile keeps warning (no over-suppression)."""
        diagnosis = CatalogMissDiagnosis(cause=CatalogMissCause.MISSING_ARTIFACT)
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            emit_catalog_miss_warning(
                selector_kind="agent_profile",
                artifact_id="never-existed",
                diagnosis=diagnosis,
            )
        miss = [
            w for w in captured if issubclass(w.category, CharterCatalogMissWarning)
        ]
        assert len(miss) == 1


class TestAgentProfileCatalogListReconciliation:
    """#4572 live render path: the selection render agrees with profile list.

    A real ``AgentProfileRepository`` language-filtered to the repo's active
    languages silently dropped language-scoped profiles with no
    ``scope_filtered_ids`` record, so a charter that selected them rendered
    ``cause=missing_artifact`` for profiles ``agent profile list`` reports
    available. The repository now records the drop (FR-013 parity) and the
    emitter stays quiet for that class.
    """

    def test_selected_language_scoped_profile_renders_scope_filtered_without_warning(
        self, tmp_path: Path
    ) -> None:
        built_in_dir = tmp_path / "built-in"
        _write_agent_profile_yaml(
            built_in_dir,
            "java-only.agent.yaml",
            {
                "profile-id": "java-only",
                "name": "Java Only",
                "purpose": "Java specialist",
                "roles": ["implementer"],
                "applies_to_languages": ["java"],
                "specialization": {"primary-focus": "Java implementation"},
            },
        )
        _write_agent_profile_yaml(
            built_in_dir,
            "any-lang.agent.yaml",
            {
                "profile-id": "any-lang",
                "name": "Any Language",
                "purpose": "Generic specialist",
                "roles": ["implementer"],
                "specialization": {"primary-focus": "General implementation"},
            },
        )

        repo = AgentProfileRepository(
            built_in_dir=built_in_dir, active_languages=["python"]
        )
        # Repository-level filter contract is unchanged (pinned separately);
        # the drop is now *recorded* rather than silent.
        assert repo.get("java-only") is None
        assert repo.scope_filtered_ids == frozenset({"java-only"})
        assert repo.get("any-lang") is not None

        class _ServiceWithRealRepo:
            agent_profiles = repo

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            lines = _render_selected_agent_profiles(
                ["java-only", "any-lang", "absent-profile"],
                _ServiceWithRealRepo(),
            )
        joined = "\n".join(lines)

        # The scoped profile renders the honest cause — present, excluded by
        # the language scope — never MISSING_ARTIFACT.
        assert "agent_profile:java-only" in joined
        assert "Cause: scope_filtered" in joined
        assert "applies_to_languages" in joined
        # The available profile renders normally; the absent one still misses.
        assert "Cause: missing_artifact" in joined

        # Reconciliation: only the genuinely absent id warns. The listed-
        # available java-only contributes no warning line.
        miss = [
            w for w in captured if issubclass(w.category, CharterCatalogMissWarning)
        ]
        assert len(miss) == 1
        assert "agent_profile:absent-profile" in str(miss[0].message)
        assert "java-only" not in str(miss[0].message)
