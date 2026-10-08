"""WP02 T008/T012 -- placeholder-text-format and language-set-naming assertions.

New, narrow unit-test file (mission ``charter-generation-drops-scoped-
references-01M3M1KF``, issue #5257; lane-b owned -- deliberately NOT the same
file as WP01's owned test files, ``tests/charter/test_charter_generate_scoped_reference_parity.py``
or ``tests/charter/test_charter_whole_kind_invariants.py``).

Pins two of WP02's binding design decisions (plan.md "WP-CORE reconciliation"):

1. Decision 2 -- a ``SCOPE_FILTERED`` placeholder's ``summary`` keeps the
   pre-existing baseline text (``"Definition unavailable in bundled
   doctrine."``, already committed verbatim in this repo's own
   ``.kittify/charter/charter.yaml`` for still-unresolved ids) byte-for-byte
   as a stable prefix, and appends a reason-bearing suffix sourced from
   ``classify_scope_filtered_miss``'s own suggestion text.
2. T008 (round-8 fix, closes analyze findings D1/C1/U1) -- confirms the
   classify-and-placeholder helper passes the REAL repository object into
   the canonical ``_diagnose_catalog_miss`` gate, so the gate's richer,
   language-set-naming suggestion text (``_catalog_miss.py``'s
   ``classify_scope_filtered_miss``) reaches the emitted placeholder
   ``summary`` end-to-end -- not the generic fallback. There is no
   ``active_languages`` parameter to thread (the gate reads it straight off
   the repository's own ``_active_languages`` attribute), so this is a
   content-level assertion rather than a signature/threading check.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from charter.activation.compiler import _classify_and_placeholder_reference

pytestmark = [pytest.mark.unit]


@dataclass
class _ScopeFilteredRepository:
    """Minimal raw-repository double: one id, scope-filtered, with a real
    active-language set -- mirrors ``BaseArtifactRepository``'s
    ``scope_filtered_ids``/``_active_languages`` shape closely enough for
    ``_diagnose_catalog_miss`` to route to ``classify_scope_filtered_miss``.
    """

    scope_filtered_ids: frozenset[str]
    _active_languages: list[str] = field(default_factory=list)

    def get(self, _artifact_id: str) -> Any | None:
        return None

    def list_all(self) -> list[str]:
        return []


def test_scope_filtered_placeholder_summary_extends_baseline_prefix_verbatim() -> None:
    """Decision 2: the placeholder ``summary`` keeps
    ``"Definition unavailable in bundled doctrine."`` byte-for-byte as a
    prefix and appends ``" Reason: scope_filtered — <suggestion>"``.
    """
    repository = _ScopeFilteredRepository(
        scope_filtered_ids=frozenset({"java-conventions"}),
        _active_languages=["python"],
    )
    diagnostics: list[str] = []
    unresolved_records: list[dict[str, str]] = []

    placeholder = _classify_and_placeholder_reference(
        kind="styleguide",
        raw_id="java-conventions",
        repository=repository,
        diagnostics=diagnostics,
        unresolved_records=unresolved_records,
    )

    assert placeholder is not None, "a SCOPE_FILTERED cause must always produce a placeholder"
    assert placeholder.summary.startswith("Definition unavailable in bundled doctrine."), (
        f"placeholder summary must preserve the existing baseline prefix verbatim, got: {placeholder.summary!r}"
    )
    assert "Reason: scope_filtered" in placeholder.summary, f"placeholder summary must name the scope_filtered reason category, got: {placeholder.summary!r}"
    assert placeholder.id == "STYLEGUIDE:java-conventions"
    assert diagnostics == ["Unresolved reference: styleguide/java-conventions (scope_filtered): " + unresolved_records[0]["detail"]]
    assert unresolved_records == [
        {
            "kind": "styleguide",
            "id": "java-conventions",
            "cause": "scope_filtered",
            "detail": unresolved_records[0]["detail"],
        }
    ]


def test_scope_filtered_placeholder_names_the_real_active_language_set() -> None:
    """T008 (round-8 fix): the emitted detail/suggestion text names the
    ACTUAL active language set the repository carries, matching the
    contract doc's worked example -- proving the classify-and-placeholder
    helper passed the real repository object into ``_diagnose_catalog_miss``
    rather than a stripped/partial view.
    """
    repository = _ScopeFilteredRepository(
        scope_filtered_ids=frozenset({"java-conventions"}),
        _active_languages=["python"],
    )
    diagnostics: list[str] = []
    unresolved_records: list[dict[str, str]] = []

    placeholder = _classify_and_placeholder_reference(
        kind="styleguide",
        raw_id="java-conventions",
        repository=repository,
        diagnostics=diagnostics,
        unresolved_records=unresolved_records,
    )

    assert placeholder is not None
    assert "does not include the active language set ('python')" in placeholder.summary, (
        f"expected the real active-language set to be named in the placeholder summary, got: {placeholder.summary!r}"
    )
    assert any("python" in record.get("detail", "") for record in unresolved_records), (
        f"expected the structured unresolved record's detail to also name the active language set, got: {unresolved_records!r}"
    )


def test_missing_artifact_cause_stays_diagnostics_only_no_placeholder() -> None:
    """Contract C4 companion check: a ``MISSING_ARTIFACT`` cause (no
    ``scope_filtered_ids`` membership, no fuzzy-match candidate) never
    produces a placeholder from this helper -- it is the same gate-driven
    branch ``tests/charter/test_catalog_completeness_4785.py`` pins at the
    ``_render_kind_references`` call-site level; this asserts the helper
    itself directly.
    """
    repository = _ScopeFilteredRepository(scope_filtered_ids=frozenset())
    diagnostics: list[str] = []
    unresolved_records: list[dict[str, str]] = []

    placeholder = _classify_and_placeholder_reference(
        kind="styleguide",
        raw_id="genuinely-nonexistent-id",
        repository=repository,
        diagnostics=diagnostics,
        unresolved_records=unresolved_records,
    )

    assert placeholder is None
    detail = unresolved_records[0]["detail"]
    assert detail.startswith("no artifact with this id in any doctrine layer"), detail
    assert diagnostics == [f"Unresolved reference: styleguide/genuinely-nonexistent-id (missing_artifact): {detail}"]
    assert unresolved_records == [
        {
            "kind": "styleguide",
            "id": "genuinely-nonexistent-id",
            "cause": "missing_artifact",
            "detail": detail,
        }
    ]


def test_unresolved_reference_records_mirrors_diagnostics_for_a_mixed_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T013 (issue #5257): the structured ``unresolved_records`` sink
    carries the same kind/id/cause as the free-text ``diagnostics`` list,
    for a fixture mixing a ``SCOPE_FILTERED`` and a ``MISSING_ARTIFACT``
    cause within the same kind -- proving the new field is populated
    identically in content to ``diagnostics``' per-line reasons, not a
    second, drifting bookkeeping list.
    """
    import charter.activation.compiler as compiler_module
    from charter.activation.compiler import ConfigActivatedRoots
    from charter.offering.drg.query import ResolveTransitiveRefsResult

    class _StubActiveCharterService:
        def raw_repository(self, kind: str) -> Any:
            if kind == "styleguides":
                return _ScopeFilteredRepository(
                    scope_filtered_ids=frozenset({"scope-filtered-id"}),
                    _active_languages=["python"],
                )
            return _ScopeFilteredRepository(scope_filtered_ids=frozenset())

    graph = ResolveTransitiveRefsResult(styleguides=["scope-filtered-id", "genuinely-missing-id"])
    monkeypatch.setattr(compiler_module, "_resolve_transitive_reference_graph", lambda **_kwargs: graph)

    diagnostics: list[str] = []
    unresolved_records: list[dict[str, str]] = []
    config_roots = ConfigActivatedRoots(
        directives=[],
        paradigms=[],
        tactics=[],
        styleguides=[],
        toolguides=[],
        procedures=[],
        agent_profiles=[],
    )

    compiler_module._build_references_from_service(
        mission="software-dev",
        template_set="default",
        config_roots=config_roots,
        offering_root=compiler_module.resolve_offering_root(),
        charter_service=_StubActiveCharterService(),
        repo_root=None,
        diagnostics=diagnostics,
        unresolved_records=unresolved_records,
    )

    assert len(unresolved_records) == 2
    assert {record["cause"] for record in unresolved_records} == {"scope_filtered", "missing_artifact"}
    for record in unresolved_records:
        expected_prefix = f"Unresolved reference: {record['kind']}/{record['id']} ({record['cause']})"
        assert any(line.startswith(expected_prefix) for line in diagnostics), (
            f"no diagnostics line matches structured record {record!r}; diagnostics={diagnostics!r}"
        )
    assert len(diagnostics) == len(unresolved_records)


def test_graph_unresolved_urn_with_scope_filtered_cause_gets_a_real_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T009 companion: a ``graph.unresolved`` URN that maps to one of the six
    tracked kinds AND classifies ``SCOPE_FILTERED`` must get a real
    placeholder ``CharterReference`` appended (not only a diagnostic) --
    ``_route_unresolved_urn`` routes it through the exact same
    ``_classify_and_placeholder_reference`` helper a direct per-kind miss
    uses. This is distinct from
    ``test_whole_kind_graph_unresolved_routing_fails_closed``, which only
    exercises the ``MISSING_ARTIFACT`` (no-placeholder) branch of this same
    routing path.
    """
    import charter.activation.compiler as compiler_module
    from charter.activation.compiler import ConfigActivatedRoots
    from charter.offering.drg.query import ResolveTransitiveRefsResult

    class _StubActiveCharterService:
        def raw_repository(self, kind: str) -> Any:
            if kind == "styleguides":
                return _ScopeFilteredRepository(
                    scope_filtered_ids=frozenset({"scope-filtered-only-id"}),
                    _active_languages=["python"],
                )
            return _ScopeFilteredRepository(scope_filtered_ids=frozenset())

    urn = "styleguide:scope-filtered-only-id"
    graph = ResolveTransitiveRefsResult(unresolved=[(urn, urn)])
    monkeypatch.setattr(compiler_module, "_resolve_transitive_reference_graph", lambda **_kwargs: graph)

    config_roots = ConfigActivatedRoots(
        directives=[],
        paradigms=[],
        tactics=[],
        styleguides=[],
        toolguides=[],
        procedures=[],
        agent_profiles=[],
    )
    diagnostics: list[str] = []

    references = compiler_module._build_references_from_service(
        mission="software-dev",
        template_set="default",
        config_roots=config_roots,
        offering_root=compiler_module.resolve_offering_root(),
        charter_service=_StubActiveCharterService(),
        repo_root=None,
        diagnostics=diagnostics,
    )

    matching = [ref for ref in references if ref.id == "STYLEGUIDE:scope-filtered-only-id"]
    assert len(matching) == 1, f"expected exactly one placeholder for the graph.unresolved SCOPE_FILTERED id, got references: {references!r}"
    assert matching[0].summary.startswith("Definition unavailable in bundled doctrine."), matching[0].summary
    assert "Reason: scope_filtered" in matching[0].summary, matching[0].summary


def test_typo_suspected_detail_names_the_suggested_id_readably() -> None:
    """The classifier's TYPO_SUSPECTED suggestion is a bare id; the recorded
    detail must read as a sentence, not as a stray id after the colon."""

    @dataclass
    class _ListingRepository:
        scope_filtered_ids: frozenset[str] = frozenset()
        _items: dict[str, object] = field(default_factory=lambda: {"java-conventions": object()})

        def get(self, _artifact_id: str) -> Any | None:
            return None

    diagnostics: list[str] = []
    unresolved_records: list[dict[str, str]] = []

    placeholder = _classify_and_placeholder_reference(
        kind="styleguide",
        raw_id="java-convention",
        repository=_ListingRepository(),
        diagnostics=diagnostics,
        unresolved_records=unresolved_records,
    )

    assert placeholder is None
    assert unresolved_records[0]["cause"] == "typo_suspected"
    assert unresolved_records[0]["detail"] == "did you mean 'java-conventions'?"
    assert diagnostics == ["Unresolved reference: styleguide/java-convention (typo_suspected): did you mean 'java-conventions'?"]


def test_classification_uses_the_project_root_like_charter_context(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``charter context`` passes ``repo_root`` to the diagnosis gate; generate
    must too, or the two report different advice for the same miss."""
    from charter.activation import compiler as compiler_module
    from charter.activation._catalog_miss import CatalogMissCause, CatalogMissDiagnosis

    seen: dict[str, object] = {}

    def _spy(missing_id: str, repository: object, *, repo_root: Path | None = None) -> CatalogMissDiagnosis:
        seen["repo_root"] = repo_root
        return CatalogMissDiagnosis(cause=CatalogMissCause.MISSING_ARTIFACT)

    monkeypatch.setattr(compiler_module, "_diagnose_catalog_miss", _spy)

    _classify_and_placeholder_reference(
        kind="styleguide",
        raw_id="whatever",
        repository=_ScopeFilteredRepository(scope_filtered_ids=frozenset()),
        diagnostics=[],
        unresolved_records=[],
        project_root=tmp_path,
    )

    assert seen["repo_root"] == tmp_path
