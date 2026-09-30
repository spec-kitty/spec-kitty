"""Schema conformance gate tests (T012, T014).

Verifies FR-019 / NFR-005 — the schema conformance gate inside
synthesize_pipeline.run_all():

1. An adapter returning an invalid body raises SynthesisSchemaError.
2. SynthesisSchemaError carries artifact_kind, artifact_slug, validation_errors.
3. A valid body passes without raising.
4. Schema gate fires BEFORE provenance assembly (no side effects on failure).

Tests use a custom ControlledAdapter that returns a pre-determined body so
we can inject both valid and invalid YAML body dicts without touching fixtures.

Note on pytest.raises with frozen dataclass exceptions (Python 3.14)
---------------------------------------------------------------------
SynthesisSchemaError is a frozen dataclass + Exception.  In Python 3.14,
``pytest.raises()`` as a context manager tries to set ``exc.__traceback__``,
which fails for frozen dataclasses (FrozenInstanceError).  To work around
this, exception-capture tests use explicit try/except rather than
``with pytest.raises() as exc_info:``.
"""

from __future__ import annotations

from kernel.clock import datetime, UTC
from typing import Any
from collections.abc import Mapping

import pytest

from charter.activation.synthesizer.adapter import AdapterOutput
from charter.activation.synthesizer.errors import SynthesisSchemaError
from charter.activation.synthesizer.request import SynthesisRequest, SynthesisTarget
from charter.activation.synthesizer.synthesize_pipeline import ProvenanceEntry, _assert_schema, run_all


# ---------------------------------------------------------------------------
# Minimal valid bodies for each artifact kind
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit]

VALID_DIRECTIVE_BODY: dict[str, Any] = {
    "id": "PROJECT_001",
    "schema_version": "1.0",
    "title": "Test Directive",
    "intent": "Test intent for schema validation.",
    "enforcement": "required",
}

VALID_TACTIC_BODY: dict[str, Any] = {
    "id": "test-tactic",
    "schema_version": "1.0",
    "name": "Test Tactic",
    "purpose": "For schema conformance testing.",
    "steps": [
        {"title": "Step One", "description": "Do the first thing."},
    ],
}

VALID_STYLEGUIDE_BODY: dict[str, Any] = {
    "id": "test-styleguide",
    "schema_version": "1.0",
    "title": "Test Styleguide",
    "scope": "code",
    "principles": ["Write clear code."],
}

# Invalid bodies — missing required fields
INVALID_DIRECTIVE_BODY: dict[str, Any] = {
    "id": "PROJECT_001",
    # missing: schema_version, title, intent, enforcement
}

INVALID_TACTIC_BODY: dict[str, Any] = {
    "id": "test-tactic",
    # missing: schema_version, name, steps
}

INVALID_STYLEGUIDE_BODY: dict[str, Any] = {
    "id": "test-styleguide",
    # missing: schema_version, title, scope, principles
}

# Valid bodies keyed by kind — used as fallback in KindRouter
_VALID_BY_KIND: dict[str, dict[str, Any]] = {
    "directive": VALID_DIRECTIVE_BODY,
    "tactic": VALID_TACTIC_BODY,
    "styleguide": VALID_STYLEGUIDE_BODY,
}


# ---------------------------------------------------------------------------
# Controlled adapters — return caller-configured bodies
# ---------------------------------------------------------------------------


class KindRouterAdapter:
    """Adapter that routes by artifact kind to a configured body dict.

    For every target whose kind is in ``body_by_kind``, returns that body.
    Falls back to a valid body for kinds not in the mapping.

    Used for tests that want to inject valid bodies for all targets except one.
    """

    id: str = "kind-router-adapter"
    version: str = "1.0.0"

    def __init__(self, body_by_kind: dict[str, Any]) -> None:
        self._body_by_kind = body_by_kind

    def generate(self, request: SynthesisRequest) -> AdapterOutput:
        body = self._body_by_kind.get(
            request.target.kind,
            _VALID_BY_KIND.get(request.target.kind, VALID_DIRECTIVE_BODY),
        )
        return AdapterOutput(
            body=body,
            generated_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        )


class ValidForAllAdapter:
    """Adapter that returns a valid body for every target, keyed by kind."""

    id: str = "valid-for-all-adapter"
    version: str = "1.0.0"

    def generate(self, request: SynthesisRequest) -> AdapterOutput:
        body = _VALID_BY_KIND.get(request.target.kind, VALID_DIRECTIVE_BODY)
        return AdapterOutput(
            body=body,
            generated_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_direct_request(
    kind: str,
    slug: str,
    artifact_id: str,
    source_section: str = "testing_philosophy",
    source_urns: tuple[str, ...] = (),
) -> SynthesisRequest:
    """Build a SynthesisRequest with a specific target and minimal interview.

    The interview snapshot is intentionally minimal: only one section that
    the pipeline will process. The ``mission_type`` section always emits a
    directive (requires_nonempty=False), so the interview must be kept empty
    to avoid spurious targets.  However, the pipeline always falls back to
    ``request.target`` if no targets are produced from the interview — so
    passing an empty snapshot works for injecting a specific target.
    """
    target = SynthesisTarget(
        kind=kind,
        slug=slug,
        title=f"{slug.replace('-', ' ').title()}",
        artifact_id=artifact_id,
        source_section=source_section,
        source_urns=source_urns,
    )
    return SynthesisRequest(
        target=target,
        # Empty interview → pipeline produces no sections → falls back to request.target.
        interview_snapshot={},
        doctrine_snapshot={"directives": {}, "tactics": {}, "styleguides": {}},
        drg_snapshot={"nodes": [], "edges": [], "schema_version": "1"},
        run_id="01TEST000000000000000000001",
    )


# ---------------------------------------------------------------------------
# _assert_schema unit tests
# ---------------------------------------------------------------------------


class TestAssertSchemaUnit:
    """Unit tests for _assert_schema() — the conformance check function."""

    @pytest.mark.parametrize("kind,slug,artifact_id,body", [
        ("directive", "test-directive", "PROJECT_001", VALID_DIRECTIVE_BODY),
        ("tactic", "test-tactic", "test-tactic", VALID_TACTIC_BODY),
        ("styleguide", "test-styleguide", "test-styleguide", VALID_STYLEGUIDE_BODY),
    ])
    def test_valid_body_does_not_raise(
        self, kind: str, slug: str, artifact_id: str, body: dict
    ) -> None:
        """A conformant body does not raise SynthesisSchemaError."""
        target = SynthesisTarget(
            kind=kind,
            slug=slug,
            title="Test",
            artifact_id=artifact_id,
            source_section="testing_philosophy",
        )
        output = AdapterOutput(
            body=body,
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        # Should not raise
        _assert_schema(target, output)

    @pytest.mark.parametrize("kind,slug,artifact_id,body", [
        ("directive", "test-directive", "PROJECT_001", INVALID_DIRECTIVE_BODY),
        ("tactic", "test-tactic", "test-tactic", INVALID_TACTIC_BODY),
        ("styleguide", "test-styleguide", "test-styleguide", INVALID_STYLEGUIDE_BODY),
    ])
    def test_invalid_body_raises_synthesis_schema_error(
        self, kind: str, slug: str, artifact_id: str, body: dict
    ) -> None:
        """An invalid body raises SynthesisSchemaError."""
        target = SynthesisTarget(
            kind=kind,
            slug=slug,
            title="Test",
            artifact_id=artifact_id,
            source_section="testing_philosophy",
        )
        output = AdapterOutput(
            body=body,
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        raised = False
        try:
            _assert_schema(target, output)
        except SynthesisSchemaError:
            raised = True
        assert raised, f"Expected SynthesisSchemaError for {kind}:{slug}"

    def test_schema_error_contains_kind(self) -> None:
        """SynthesisSchemaError carries artifact_kind."""
        target = SynthesisTarget(
            kind="directive",
            slug="bad-directive",
            title="Bad",
            artifact_id="PROJECT_001",
            source_section="mission_type",
        )
        output = AdapterOutput(
            body=INVALID_DIRECTIVE_BODY,
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        caught: SynthesisSchemaError | None = None
        try:
            _assert_schema(target, output)
        except SynthesisSchemaError as e:
            caught = e
        assert caught is not None
        assert caught.artifact_kind == "directive"

    def test_schema_error_contains_slug(self) -> None:
        """SynthesisSchemaError carries artifact_slug."""
        target = SynthesisTarget(
            kind="tactic",
            slug="my-bad-tactic",
            title="Bad Tactic",
            artifact_id="my-bad-tactic",
            source_section="review_policy",
        )
        output = AdapterOutput(
            body=INVALID_TACTIC_BODY,
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        caught: SynthesisSchemaError | None = None
        try:
            _assert_schema(target, output)
        except SynthesisSchemaError as e:
            caught = e
        assert caught is not None
        assert caught.artifact_slug == "my-bad-tactic"

    def test_schema_error_contains_validation_errors(self) -> None:
        """SynthesisSchemaError.validation_errors is a non-empty tuple of strings."""
        target = SynthesisTarget(
            kind="styleguide",
            slug="bad-styleguide",
            title="Bad",
            artifact_id="bad-styleguide",
            source_section="documentation_policy",
        )
        output = AdapterOutput(
            body=INVALID_STYLEGUIDE_BODY,
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        caught: SynthesisSchemaError | None = None
        try:
            _assert_schema(target, output)
        except SynthesisSchemaError as e:
            caught = e
        assert caught is not None
        errs = caught.validation_errors
        assert isinstance(errs, tuple)
        assert len(errs) >= 1
        for err in errs:
            assert isinstance(err, str)

    def test_schema_error_message_contains_kind_and_slug(self) -> None:
        """str(SynthesisSchemaError) contains kind and slug."""
        target = SynthesisTarget(
            kind="directive",
            slug="test-directive-slug",
            title="Test",
            artifact_id="PROJECT_001",
            source_section="mission_type",
        )
        output = AdapterOutput(
            body=INVALID_DIRECTIVE_BODY,
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        caught: SynthesisSchemaError | None = None
        try:
            _assert_schema(target, output)
        except SynthesisSchemaError as e:
            caught = e
        assert caught is not None
        msg = str(caught)
        assert "directive" in msg
        assert "test-directive-slug" in msg

    def test_unknown_kind_raises(self) -> None:
        """An unknown kind raises SynthesisSchemaError (not a bare KeyError)."""
        target = SynthesisTarget(
            kind="tactic",  # valid for SynthesisTarget
            slug="test-slug",
            title="Test",
            artifact_id="test-slug",
            source_section="testing_philosophy",
        )
        # Manually set an invalid kind to test the unknown-kind branch.
        object.__setattr__(target, "kind", "unknown_kind")

        output = AdapterOutput(
            body={"id": "x"},
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        raised = False
        try:
            _assert_schema(target, output)
        except SynthesisSchemaError:
            raised = True
        assert raised, "Expected SynthesisSchemaError for unknown kind"


# ---------------------------------------------------------------------------
# Integration: run_all() with invalid body
# ---------------------------------------------------------------------------


class TestRunAllSchemaConformance:
    """Schema gate fires inside run_all() — no provenance assembled on failure."""

    def test_invalid_directive_body_raises_synthesis_schema_error(self) -> None:
        """run_all() raises SynthesisSchemaError on invalid directive body.

        Uses KindRouterAdapter: returns an invalid body for 'directive' kind,
        valid bodies for all other kinds produced by the empty interview.
        """
        request = _make_direct_request(
            kind="directive",
            slug="mission-type-scope-directive",
            artifact_id="PROJECT_001",
            source_section="mission_type",
        )
        # The empty interview will still produce mission-type-scope-directive
        # (mission_type is requires_nonempty=False). Inject invalid body for directive.
        adapter = KindRouterAdapter({"directive": INVALID_DIRECTIVE_BODY})

        raised = False
        caught: SynthesisSchemaError | None = None
        try:
            run_all(request, adapter=adapter)
        except SynthesisSchemaError as e:
            raised = True
            caught = e
        assert raised, "Expected SynthesisSchemaError"
        assert caught is not None
        assert caught.artifact_kind == "directive"

    def test_invalid_tactic_body_raises_synthesis_schema_error(self) -> None:
        """run_all() raises SynthesisSchemaError on invalid tactic body."""
        target = SynthesisTarget(
            kind="tactic",
            slug="test-tactic",
            title="Test Tactic",
            artifact_id="test-tactic",
            source_section="testing_philosophy",
        )
        request = SynthesisRequest(
            target=target,
            # Interview with testing_philosophy drives: directive + tactic + styleguide.
            # We want the tactic to fail schema.
            interview_snapshot={"testing_philosophy": "tdd"},
            doctrine_snapshot={},
            drg_snapshot={"nodes": [], "edges": [], "schema_version": "1"},
            run_id="01TEST",
        )
        # directive → valid, tactic → invalid, styleguide → valid
        adapter = KindRouterAdapter({"tactic": INVALID_TACTIC_BODY})

        raised = False
        caught: SynthesisSchemaError | None = None
        try:
            run_all(request, adapter=adapter)
        except SynthesisSchemaError as e:
            raised = True
            caught = e
        assert raised, "Expected SynthesisSchemaError for invalid tactic"
        assert caught is not None
        assert caught.artifact_kind == "tactic"

    def test_invalid_styleguide_body_raises_synthesis_schema_error(self) -> None:
        """run_all() raises SynthesisSchemaError on invalid styleguide body."""
        target = SynthesisTarget(
            kind="styleguide",
            slug="test-styleguide",
            title="Test Styleguide",
            artifact_id="test-styleguide",
            source_section="testing_philosophy",
        )
        request = SynthesisRequest(
            target=target,
            interview_snapshot={"testing_philosophy": "tdd"},
            doctrine_snapshot={},
            drg_snapshot={"nodes": [], "edges": [], "schema_version": "1"},
            run_id="01TEST",
        )
        adapter = KindRouterAdapter({"styleguide": INVALID_STYLEGUIDE_BODY})

        raised = False
        caught: SynthesisSchemaError | None = None
        try:
            run_all(request, adapter=adapter)
        except SynthesisSchemaError as e:
            raised = True
            caught = e
        assert raised, "Expected SynthesisSchemaError for invalid styleguide"
        assert caught is not None
        assert caught.artifact_kind == "styleguide"

    def test_valid_directive_body_produces_provenance(self) -> None:
        """run_all() with all-valid bodies returns (body, ProvenanceEntry) tuples."""
        request = _make_direct_request(
            kind="directive",
            slug="mission-type-scope-directive",
            artifact_id="PROJECT_001",
            source_section="mission_type",
        )
        adapter = ValidForAllAdapter()

        results = run_all(request, adapter=adapter)
        assert len(results) >= 1
        body, provenance = results[0]
        assert isinstance(body, Mapping)
        assert isinstance(provenance, ProvenanceEntry)

    def test_valid_tactic_body_produces_provenance(self) -> None:
        """run_all() with valid tactic body returns (body, ProvenanceEntry) tuple."""
        request = SynthesisRequest(
            target=SynthesisTarget(
                kind="tactic",
                slug="testing-philosophy-tactic",
                title="Testing Philosophy Tactic",
                artifact_id="testing-philosophy-tactic",
                source_section="testing_philosophy",
            ),
            interview_snapshot={"testing_philosophy": "tdd"},
            doctrine_snapshot={},
            drg_snapshot={"nodes": [], "edges": [], "schema_version": "1"},
            run_id="01TEST",
        )
        adapter = ValidForAllAdapter()
        results = run_all(request, adapter=adapter)
        tactic_results = [(b, p) for b, p in results if p.artifact_kind == "tactic"]
        assert len(tactic_results) >= 1
        _, prov = tactic_results[0]
        assert isinstance(prov, ProvenanceEntry)
        assert prov.artifact_kind == "tactic"

    def test_valid_styleguide_body_produces_provenance(self) -> None:
        """run_all() with valid styleguide body returns (body, ProvenanceEntry)."""
        request = SynthesisRequest(
            target=SynthesisTarget(
                kind="styleguide",
                slug="testing-style-guide",
                title="Testing Style Guide",
                artifact_id="testing-style-guide",
                source_section="testing_philosophy",
            ),
            interview_snapshot={"testing_philosophy": "tdd"},
            doctrine_snapshot={},
            drg_snapshot={"nodes": [], "edges": [], "schema_version": "1"},
            run_id="01TEST",
        )
        adapter = ValidForAllAdapter()
        results = run_all(request, adapter=adapter)
        styleguide_results = [(b, p) for b, p in results if p.artifact_kind == "styleguide"]
        assert len(styleguide_results) >= 1
        _, prov = styleguide_results[0]
        assert prov.artifact_kind == "styleguide"


# ---------------------------------------------------------------------------
# ProvenanceEntry field completeness
# ---------------------------------------------------------------------------


class TestProvenanceEntryFields:
    """Schema conformance: provenance entries carry all required data-model.md §E-4 fields."""

    def _make_simple_request(self) -> SynthesisRequest:
        """Request whose empty interview falls back to request.target (directive)."""
        return _make_direct_request(
            kind="directive",
            slug="mission-type-scope-directive",
            artifact_id="PROJECT_001",
            source_section="mission_type",
        )

    def test_provenance_has_all_required_fields(self) -> None:
        """A successful run produces ProvenanceEntry with all required fields."""
        request = self._make_simple_request()
        adapter = ValidForAllAdapter()
        results = run_all(request, adapter=adapter)
        _, prov = results[0]

        # All required fields from data-model.md §E-4 (v2)
        assert prov.schema_version == "2"
        assert prov.artifact_urn
        assert prov.artifact_kind in {"directive", "tactic", "styleguide"}
        assert prov.artifact_slug
        assert prov.artifact_content_hash
        assert prov.inputs_hash
        assert prov.adapter_id
        assert prov.adapter_version
        assert prov.synthesizer_version
        assert prov.generated_at
        assert prov.produced_at
        assert prov.corpus_snapshot_id
        assert prov.synthesis_run_id

    def test_provenance_inputs_hash_is_hex(self) -> None:
        """inputs_hash is a full hex string."""
        request = self._make_simple_request()
        adapter = ValidForAllAdapter()
        results = run_all(request, adapter=adapter)
        _, prov = results[0]
        assert all(c in "0123456789abcdef" for c in prov.inputs_hash)

    def test_provenance_content_hash_is_hex(self) -> None:
        """artifact_content_hash is a full hex string."""
        request = self._make_simple_request()
        adapter = ValidForAllAdapter()
        results = run_all(request, adapter=adapter)
        _, prov = results[0]
        assert all(c in "0123456789abcdef" for c in prov.artifact_content_hash)

    def test_provenance_adapter_id_from_override(self) -> None:
        """Override-first: adapter_id comes from AdapterOutput.adapter_id_override."""

        class OverridingAdapter:
            id = "base-adapter"
            version = "1.0.0"

            def generate(self, request: SynthesisRequest) -> AdapterOutput:
                return AdapterOutput(
                    body=_VALID_BY_KIND.get(request.target.kind, VALID_DIRECTIVE_BODY),
                    generated_at=datetime(2026, 1, 1, tzinfo=UTC),
                    adapter_id_override="override-adapter-id",
                )

        request = self._make_simple_request()
        results = run_all(request, adapter=OverridingAdapter())
        _, prov = results[0]
        assert prov.adapter_id == "override-adapter-id"

    def test_provenance_adapter_version_from_override(self) -> None:
        """Override-first: adapter_version comes from AdapterOutput.adapter_version_override."""

        class OverridingAdapter:
            id = "base-adapter"
            version = "1.0.0"

            def generate(self, request: SynthesisRequest) -> AdapterOutput:
                return AdapterOutput(
                    body=_VALID_BY_KIND.get(request.target.kind, VALID_DIRECTIVE_BODY),
                    generated_at=datetime(2026, 1, 1, tzinfo=UTC),
                    adapter_version_override="override-2.0.0",
                )

        request = self._make_simple_request()
        results = run_all(request, adapter=OverridingAdapter())
        _, prov = results[0]
        assert prov.adapter_version == "override-2.0.0"

    def test_provenance_adapter_id_fallback_to_adapter(self) -> None:
        """Without override, adapter_id is taken from adapter.id."""
        request = self._make_simple_request()
        adapter = ValidForAllAdapter()
        results = run_all(request, adapter=adapter)
        _, prov = results[0]
        assert prov.adapter_id == "valid-for-all-adapter"

    def test_provenance_notes_copied_from_output(self) -> None:
        """adapter_notes is copied verbatim from AdapterOutput.notes."""

        class NoteAdapter:
            id = "note-adapter"
            version = "1.0.0"

            def generate(self, request: SynthesisRequest) -> AdapterOutput:
                return AdapterOutput(
                    body=_VALID_BY_KIND.get(request.target.kind, VALID_DIRECTIVE_BODY),
                    generated_at=datetime(2026, 1, 1, tzinfo=UTC),
                    notes="custom note for testing",
                )

        request = self._make_simple_request()
        results = run_all(request, adapter=NoteAdapter())
        _, prov = results[0]
        assert prov.adapter_notes == "custom note for testing"
