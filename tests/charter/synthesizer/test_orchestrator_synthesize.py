"""End-to-end synthesis tests via orchestrator.synthesize() (T014).

Verifies:
- synthesize() delegates to synthesize_pipeline.run() after WP02 merges.
- run_all() returns the full list of (body, ProvenanceEntry) tuples.
- Tuple count matches expected targets for the minimal interview snapshot.
- Idempotency: identical inputs produce byte-identical inputs_hash and
  artifact_content_hash (FR-014, NFR-006).
- Duplicate target → DuplicateTargetError (EC-7).
- Dangling source URN → ProjectDRGValidationError (EC-2).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from collections.abc import Mapping

import pytest

from charter.activation.synthesizer import (
    DuplicateTargetError,
    FixtureAdapter,
    ProjectDRGValidationError,
    SynthesisRequest,
    SynthesisTarget,
    synthesize,
)
from charter.activation.synthesizer.synthesize_pipeline import ProvenanceEntry, run_all


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit]

@pytest.fixture
def full_interview_snapshot() -> dict[str, Any]:
    """Interview snapshot that drives all target kinds in the minimal DRG."""
    return {
        "mission_type": "software_dev",
        "language_scope": ["python"],
        "testing_philosophy": "test-driven development with high coverage",
        "neutrality_posture": "balanced",
        "selected_directives": ["DIRECTIVE_003"],
        "risk_appetite": "moderate",
    }


@pytest.fixture
def minimal_doctrine_snapshot() -> dict[str, Any]:
    return {
        "directives": {
            "DIRECTIVE_003": {
                "id": "DIRECTIVE_003",
                "title": "Decision Documentation",
                "body": "Document significant architectural decisions via ADRs.",
            }
        },
        "tactics": {},
        "styleguides": {},
    }


@pytest.fixture
def minimal_drg_snapshot() -> dict[str, Any]:
    return {
        "nodes": [
            {"urn": "directive:DIRECTIVE_003", "kind": "directive"}
        ],
        "edges": [],
        "schema_version": "1",
    }


@pytest.fixture
def fixture_root() -> Path:
    return Path(__file__).parent.parent / "fixtures" / "synthesizer"


@pytest.fixture
def adapter(fixture_root: Path) -> FixtureAdapter:
    return FixtureAdapter(fixture_root=fixture_root)


@pytest.fixture
def full_request(
    full_interview_snapshot: dict,
    minimal_doctrine_snapshot: dict,
    minimal_drg_snapshot: dict,
) -> SynthesisRequest:
    """A SynthesisRequest with a direct target (for orchestrator.synthesize())."""
    target = SynthesisTarget(
        kind="directive",
        slug="mission-type-scope-directive",
        title="Mission Type Scope Directive",
        artifact_id="PROJECT_001",
        source_section="mission_type",
    )
    return SynthesisRequest(
        target=target,
        interview_snapshot=full_interview_snapshot,
        doctrine_snapshot=minimal_doctrine_snapshot,
        drg_snapshot=minimal_drg_snapshot,
        run_id="01KPE222CD1MMCYEGB3ZCY51VR",
        adapter_hints={"language": "python"},
    )


# ---------------------------------------------------------------------------
# run_all() — tuple count and content
# ---------------------------------------------------------------------------


class TestRunAllTupleCount:
    """run_all() returns one tuple per synthesized target."""

    def test_run_all_returns_nonempty(
        self,
        full_request: SynthesisRequest,
        adapter: FixtureAdapter,
    ) -> None:
        """run_all() returns at least one tuple for the full interview snapshot."""
        results = run_all(full_request, adapter=adapter)
        assert len(results) >= 1

    def test_run_all_expected_count(
        self,
        full_request: SynthesisRequest,
        adapter: FixtureAdapter,
    ) -> None:
        """run_all() returns exactly the right number of (body, provenance) pairs.

        The minimal interview snapshot drives:
        - 3 directives (mission_type, neutrality_posture, risk_appetite)
        - 2 tactics (how-we-apply-DIRECTIVE_003, testing-philosophy-tactic)
        - 2 styleguides (python-style-guide, testing-style-guide)
        = 7 targets total.
        """
        results = run_all(full_request, adapter=adapter)
        assert len(results) == 7, (
            f"Expected 7 targets; got {len(results)}. "
            f"Targets: {[(p.artifact_kind, p.artifact_slug) for _, p in results]}"
        )

    def test_run_all_tuples_are_body_provenance_pairs(
        self,
        full_request: SynthesisRequest,
        adapter: FixtureAdapter,
    ) -> None:
        """Each element of run_all() is a (Mapping, ProvenanceEntry) tuple."""
        results = run_all(full_request, adapter=adapter)
        for body, provenance in results:
            assert isinstance(body, Mapping)
            assert isinstance(provenance, ProvenanceEntry)

    def test_run_all_provenance_urn_matches_kind_slug(
        self,
        full_request: SynthesisRequest,
        adapter: FixtureAdapter,
    ) -> None:
        """ProvenanceEntry.artifact_urn uses artifact_id for directives, slug otherwise."""
        results = run_all(full_request, adapter=adapter)
        for body, prov in results:
            expected_urn = (
                f"{prov.artifact_kind}:{body['id']}"
                if prov.artifact_kind == "directive"
                else f"{prov.artifact_kind}:{prov.artifact_slug}"
            )
            assert prov.artifact_urn == expected_urn, (
                f"Expected urn '{expected_urn}', got '{prov.artifact_urn}'"
            )


# ---------------------------------------------------------------------------
# synthesize() entry point — delegates to pipeline
# ---------------------------------------------------------------------------


class TestSynthesizeEntryPoint:
    """orchestrator.synthesize() delegates to synthesize_pipeline.run()."""

    def test_synthesize_result_has_target_kind(
        self,
        full_request: SynthesisRequest,
        adapter: FixtureAdapter,
        tmp_path: Path,
    ) -> None:
        """SynthesisResult.target_kind matches the request's primary target."""
        result = synthesize(full_request, adapter=adapter, repo_root=tmp_path)
        assert result.target_kind in {"directive", "tactic", "styleguide"}

    def test_synthesize_result_has_inputs_hash(
        self,
        full_request: SynthesisRequest,
        adapter: FixtureAdapter,
        tmp_path: Path,
    ) -> None:
        """SynthesisResult.inputs_hash is a non-empty hex string."""
        result = synthesize(full_request, adapter=adapter, repo_root=tmp_path)
        assert result.inputs_hash
        assert all(c in "0123456789abcdef" for c in result.inputs_hash)

    def test_synthesize_no_adapter_raises(
        self,
        full_request: SynthesisRequest,
    ) -> None:
        """synthesize() without an adapter raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            synthesize(full_request, adapter=None)


# ---------------------------------------------------------------------------
# Regression: importlib.metadata.PackageNotFoundError must not be mislabeled
# as "synthesize_pipeline.py is missing" (PackageNotFoundError subclasses
# ModuleNotFoundError, which subclasses ImportError).
# ---------------------------------------------------------------------------


class TestSynthesizeSurvivesPackageMetadataFailure:
    """orchestrator.synthesize() must not raise NotImplementedError when
    package metadata for ``spec-kitty-cli`` is unresolvable (e.g. an
    editable/src-layout install without discoverable dist-info)."""

    def test_synthesize_does_not_raise_notimplementederror(
        self,
        full_request: SynthesisRequest,
        adapter: FixtureAdapter,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A PackageNotFoundError from version lookup must not surface as
        NotImplementedError; synthesize() must complete normally."""
        from importlib.metadata import PackageNotFoundError

        def _raise_package_not_found(name: str) -> str:
            raise PackageNotFoundError(name)

        monkeypatch.setattr("importlib.metadata.version", _raise_package_not_found)

        result = synthesize(full_request, adapter=adapter, repo_root=tmp_path)
        assert result.target_kind in {"directive", "tactic", "styleguide"}


# ---------------------------------------------------------------------------
# FR-014 / NFR-006: Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    """Identical inputs produce byte-identical hashes (FR-014, NFR-006)."""

    def test_run_all_same_inputs_hash_twice(
        self,
        full_request: SynthesisRequest,
        adapter: FixtureAdapter,
    ) -> None:
        """Running run_all() twice produces byte-identical inputs_hash values."""
        results_a = run_all(full_request, adapter=adapter)
        results_b = run_all(full_request, adapter=adapter)

        assert len(results_a) == len(results_b)
        for (_, prov_a), (_, prov_b) in zip(results_a, results_b, strict=True):
            assert prov_a.inputs_hash == prov_b.inputs_hash, (
                f"inputs_hash diverged for {prov_a.artifact_urn}: "
                f"{prov_a.inputs_hash!r} != {prov_b.inputs_hash!r}"
            )

    def test_run_all_same_artifact_content_hash_twice(
        self,
        full_request: SynthesisRequest,
        adapter: FixtureAdapter,
    ) -> None:
        """Running run_all() twice produces byte-identical artifact_content_hash values."""
        results_a = run_all(full_request, adapter=adapter)
        results_b = run_all(full_request, adapter=adapter)

        for (_, prov_a), (_, prov_b) in zip(results_a, results_b, strict=True):
            assert prov_a.artifact_content_hash == prov_b.artifact_content_hash, (
                f"artifact_content_hash diverged for {prov_a.artifact_urn}: "
                f"{prov_a.artifact_content_hash!r} != {prov_b.artifact_content_hash!r}"
            )

    def test_different_run_id_produces_same_hashes(
        self,
        full_interview_snapshot: dict,
        minimal_doctrine_snapshot: dict,
        minimal_drg_snapshot: dict,
        adapter: FixtureAdapter,
    ) -> None:
        """Different run_ids with identical semantic inputs produce identical hashes."""
        target = SynthesisTarget(
            kind="directive",
            slug="mission-type-scope-directive",
            title="Mission Type Scope Directive",
            artifact_id="PROJECT_001",
            source_section="mission_type",
        )
        req_a = SynthesisRequest(
            target=target,
            interview_snapshot=full_interview_snapshot,
            doctrine_snapshot=minimal_doctrine_snapshot,
            drg_snapshot=minimal_drg_snapshot,
            run_id="01AAAAAAAAAAAAAAAAAAAAAAAAA",
            adapter_hints={"language": "python"},
        )
        req_b = SynthesisRequest(
            target=target,
            interview_snapshot=full_interview_snapshot,
            doctrine_snapshot=minimal_doctrine_snapshot,
            drg_snapshot=minimal_drg_snapshot,
            run_id="01BBBBBBBBBBBBBBBBBBBBBBBBB",
            adapter_hints={"language": "python"},
        )

        results_a = run_all(req_a, adapter=adapter)
        results_b = run_all(req_b, adapter=adapter)

        assert len(results_a) == len(results_b)
        for (_, prov_a), (_, prov_b) in zip(results_a, results_b, strict=True):
            assert prov_a.inputs_hash == prov_b.inputs_hash
            assert prov_a.artifact_content_hash == prov_b.artifact_content_hash


# ---------------------------------------------------------------------------
# #1912: No-op-stable synthesis — repeated synthesis of an unchanged pack
# must not churn provenance/manifest bytes (no spurious timestamp/version
# rewrites that dirty the tree on every governed run).
# ---------------------------------------------------------------------------


class TestNoOpStableSynthesis:
    """#1912: re-synthesizing an unchanged pack leaves provenance/manifest bytes intact."""

    def _request_with_run_id(
        self,
        run_id: str,
        full_interview_snapshot: dict,
        minimal_doctrine_snapshot: dict,
        minimal_drg_snapshot: dict,
    ) -> SynthesisRequest:
        target = SynthesisTarget(
            kind="directive",
            slug="mission-type-scope-directive",
            title="Mission Type Scope Directive",
            artifact_id="PROJECT_001",
            source_section="mission_type",
        )
        return SynthesisRequest(
            target=target,
            interview_snapshot=full_interview_snapshot,
            doctrine_snapshot=minimal_doctrine_snapshot,
            drg_snapshot=minimal_drg_snapshot,
            run_id=run_id,
            adapter_hints={"language": "python"},
        )

    def test_resynthesis_leaves_provenance_and_manifest_byte_identical(
        self,
        full_interview_snapshot: dict,
        minimal_doctrine_snapshot: dict,
        minimal_drg_snapshot: dict,
        adapter: FixtureAdapter,
        tmp_path: Path,
    ) -> None:
        """Synthesize, capture bytes, re-synthesize an unchanged pack → no churn.

        A second governed run carries a different ``run_id`` (as every real
        invocation does) but identical semantic inputs. The committed provenance
        sidecars and synthesis manifest must remain byte-for-byte unchanged so
        the working tree stays clean (#1912).
        """
        from charter.activation.synthesizer.manifest import MANIFEST_PATH

        req_a = self._request_with_run_id(
            "01AAAAAAAAAAAAAAAAAAAAAAAAA",
            full_interview_snapshot,
            minimal_doctrine_snapshot,
            minimal_drg_snapshot,
        )
        synthesize(req_a, adapter=adapter, repo_root=tmp_path)

        prov_dir = tmp_path / ".kittify" / "charter" / "provenance"
        manifest_file = tmp_path / MANIFEST_PATH

        before = {p.name: p.read_bytes() for p in sorted(prov_dir.glob("*.yaml"))}
        before["__manifest__"] = manifest_file.read_bytes()

        req_b = self._request_with_run_id(
            "01BBBBBBBBBBBBBBBBBBBBBBBBB",
            full_interview_snapshot,
            minimal_doctrine_snapshot,
            minimal_drg_snapshot,
        )
        synthesize(req_b, adapter=adapter, repo_root=tmp_path)

        after = {p.name: p.read_bytes() for p in sorted(prov_dir.glob("*.yaml"))}
        after["__manifest__"] = manifest_file.read_bytes()

        assert after.keys() == before.keys(), "artifact set changed on no-op re-synthesis"
        churned = [name for name in before if before[name] != after[name]]
        assert churned == [], (
            f"No-op re-synthesis churned files (#1912): {churned}. "
            "Provenance/manifest bytes must be stable when nothing changed."
        )


# ---------------------------------------------------------------------------
# EC-7: Duplicate target detection
# ---------------------------------------------------------------------------


class TestDuplicateTargetError:
    """EC-7: DuplicateTargetError when (kind, slug) appears twice."""

    def test_duplicate_target_raises(
        self,
        full_interview_snapshot: dict,
        minimal_doctrine_snapshot: dict,
        minimal_drg_snapshot: dict,
        adapter: FixtureAdapter,
    ) -> None:
        """A SynthesisRequest whose interview produces duplicate targets raises."""
        # Create an interview that would produce the same target twice via
        # a custom adapter patched to inject a duplicate.
        # Instead, we test via targets.detect_duplicates directly with an
        # explicit duplicate.
        from charter.activation.synthesizer.targets import detect_duplicates

        target_a = SynthesisTarget(
            kind="tactic",
            slug="my-tactic",
            title="My Tactic",
            artifact_id="my-tactic",
            source_section="testing_philosophy",
        )
        target_b = SynthesisTarget(
            kind="tactic",
            slug="my-tactic",
            title="My Tactic (duplicate)",
            artifact_id="my-tactic",
            source_section="review_policy",
        )

        with pytest.raises(DuplicateTargetError) as exc_info:
            detect_duplicates([target_a, target_b])

        err = exc_info.value
        assert err.kind == "tactic"
        assert err.slug == "my-tactic"
        assert err.occurrences == 2

    def test_duplicate_target_error_message(
        self,
    ) -> None:
        """DuplicateTargetError message contains kind, slug, and occurrence count."""
        from charter.activation.synthesizer.targets import detect_duplicates

        target = SynthesisTarget(
            kind="directive",
            slug="dup-directive",
            title="Dup",
            artifact_id="PROJECT_001",
            source_section="mission_type",
        )

        with pytest.raises(DuplicateTargetError) as exc_info:
            detect_duplicates([target, target])

        msg = str(exc_info.value)
        assert "directive" in msg
        assert "dup-directive" in msg
        assert "2" in msg


# ---------------------------------------------------------------------------
# EC-2: Dangling source URN detection
# ---------------------------------------------------------------------------


class TestDanglingURNValidation:
    """EC-2: ProjectDRGValidationError when source URN is not in drg_snapshot."""

    def test_dangling_urn_raises_project_drg_validation_error(
        self,
        full_interview_snapshot: dict,
        minimal_doctrine_snapshot: dict,
        adapter: FixtureAdapter,
    ) -> None:
        """A source URN that doesn't exist in the DRG snapshot raises."""
        # DRG with no nodes — any URN reference will be dangling.
        empty_drg = {"nodes": [], "edges": [], "schema_version": "1"}

        # Interview with selected_directives references a URN not in the DRG.
        snapshot_with_selection = dict(full_interview_snapshot)
        snapshot_with_selection["selected_directives"] = ["DIRECTIVE_003"]

        target = SynthesisTarget(
            kind="directive",
            slug="mission-type-scope-directive",
            title="Mission Type Scope Directive",
            artifact_id="PROJECT_001",
            source_section="mission_type",
        )
        request = SynthesisRequest(
            target=target,
            interview_snapshot=snapshot_with_selection,
            doctrine_snapshot=minimal_doctrine_snapshot,
            drg_snapshot=empty_drg,
            run_id="01KPE222CD1MMCYEGB3ZCY51VR",
            adapter_hints={"language": "python"},
        )

        with pytest.raises(ProjectDRGValidationError) as exc_info:
            run_all(request, adapter=adapter)

        err = exc_info.value
        assert len(err.errors) >= 1
        assert "DIRECTIVE_003" in " ".join(err.errors)

    def test_dangling_urn_error_has_merged_graph_summary(
        self,
        full_interview_snapshot: dict,
        minimal_doctrine_snapshot: dict,
    ) -> None:
        """ProjectDRGValidationError.merged_graph_summary is non-empty."""
        empty_drg = {"nodes": [], "edges": [], "schema_version": "1"}
        snapshot = {"selected_directives": ["DIRECTIVE_003"]}

        target = SynthesisTarget(
            kind="tactic",
            slug="how-we-apply-directive-003",
            title="How We Apply DIRECTIVE_003",
            artifact_id="how-we-apply-directive-003",
            source_section="selected_directives",
        )
        request = SynthesisRequest(
            target=target,
            interview_snapshot=snapshot,
            doctrine_snapshot=minimal_doctrine_snapshot,
            drg_snapshot=empty_drg,
            run_id="01KPE222",
        )
        adapter = FixtureAdapter()

        with pytest.raises(ProjectDRGValidationError) as exc_info:
            run_all(request, adapter=adapter)

        assert exc_info.value.merged_graph_summary


# ---------------------------------------------------------------------------
# Ordering (FR-014)
# ---------------------------------------------------------------------------


class TestTargetOrdering:
    """Verify deterministic ordering: directive → tactic → styleguide, then slug."""

    def test_run_all_order_is_directive_tactic_styleguide(
        self,
        full_request: SynthesisRequest,
        adapter: FixtureAdapter,
    ) -> None:
        """Targets are ordered: all directives first, then tactics, then styleguides."""
        results = run_all(full_request, adapter=adapter)
        kinds = [prov.artifact_kind for _, prov in results]

        # Find indices of first occurrence of each kind
        directive_indices = [i for i, k in enumerate(kinds) if k == "directive"]
        tactic_indices = [i for i, k in enumerate(kinds) if k == "tactic"]
        styleguide_indices = [i for i, k in enumerate(kinds) if k == "styleguide"]

        if directive_indices and tactic_indices:
            assert max(directive_indices) < min(tactic_indices), (
                "Directives must all appear before tactics"
            )
        if tactic_indices and styleguide_indices:
            assert max(tactic_indices) < min(styleguide_indices), (
                "Tactics must all appear before styleguides"
            )

    def test_slugs_within_kind_are_lexicographic(
        self,
        full_request: SynthesisRequest,
        adapter: FixtureAdapter,
    ) -> None:
        """Within each kind, slugs are in lexicographic order."""
        results = run_all(full_request, adapter=adapter)

        for kind in ("directive", "tactic", "styleguide"):
            slugs = [
                prov.artifact_slug for _, prov in results if prov.artifact_kind == kind
            ]
            assert slugs == sorted(slugs), (
                f"{kind} slugs are not in lexicographic order: {slugs}"
            )


# ---------------------------------------------------------------------------
# T018 integration: synthesize() writes artifacts + manifest to disk
# ---------------------------------------------------------------------------


class TestSynthesizeWritesToDisk:
    """T018: synthesize() calls write_pipeline.promote and lands artifacts on disk."""

    def test_synthesize_writes_manifest(
        self,
        full_request: SynthesisRequest,
        adapter: FixtureAdapter,
        tmp_path: Path,
    ) -> None:
        """synthesize() produces .kittify/charter/synthesis-manifest.yaml on disk."""
        from charter.activation.synthesizer.manifest import MANIFEST_PATH

        result = synthesize(full_request, adapter=adapter, repo_root=tmp_path)

        manifest_file = tmp_path / MANIFEST_PATH
        assert manifest_file.exists(), (
            f"synthesis-manifest.yaml not found at {manifest_file}; "
            "write_pipeline.promote was not called from synthesize()"
        )
        # The result is still a SynthesisResult
        from charter.activation.synthesizer.orchestrator import SynthesisResult
        assert isinstance(result, SynthesisResult)

    def test_synthesize_writes_artifacts_to_doctrine(
        self,
        full_request: SynthesisRequest,
        adapter: FixtureAdapter,
        tmp_path: Path,
    ) -> None:
        """synthesize() places artifact YAML files under .kittify/doctrine/."""
        synthesize(full_request, adapter=adapter, repo_root=tmp_path)

        doctrine_root = tmp_path / ".kittify" / "doctrine"
        all_artifacts = list(doctrine_root.rglob("*.yaml"))
        assert len(all_artifacts) >= 1, (
            f"No artifact files found under {doctrine_root}; "
            "expected at least one directive/tactic/styleguide YAML"
        )

    def test_synthesize_writes_project_graph(
        self,
        full_request: SynthesisRequest,
        adapter: FixtureAdapter,
        tmp_path: Path,
    ) -> None:
        """FR-007: synthesize() lands the additive project DRG overlay."""
        synthesize(full_request, adapter=adapter, repo_root=tmp_path)

        graph_path = tmp_path / ".kittify" / "doctrine" / "graph.yaml"
        assert graph_path.exists(), (
            f"Expected project DRG overlay at {graph_path}; "
            "synthesize() did not wire project_drg.persist into promote()"
        )

    def test_synthesize_writes_provenance_sidecars(
        self,
        full_request: SynthesisRequest,
        adapter: FixtureAdapter,
        tmp_path: Path,
    ) -> None:
        """synthesize() places provenance sidecars under .kittify/charter/provenance/."""
        synthesize(full_request, adapter=adapter, repo_root=tmp_path)

        prov_dir = tmp_path / ".kittify" / "charter" / "provenance"
        prov_files = list(prov_dir.glob("*.yaml"))
        assert len(prov_files) >= 1, (
            f"No provenance files found under {prov_dir}; "
            "write_pipeline.promote did not write provenance sidecars"
        )

    def test_synthesize_staging_wiped_after_success(
        self,
        full_request: SynthesisRequest,
        adapter: FixtureAdapter,
        tmp_path: Path,
    ) -> None:
        """Staging dir is wiped after a successful promote (KD-2 step 5)."""
        synthesize(full_request, adapter=adapter, repo_root=tmp_path)

        staging_root = tmp_path / ".kittify" / "charter" / ".staging"
        active_staging = [
            d for d in staging_root.iterdir()
            if d.is_dir() and not d.name.endswith(".failed")
        ] if staging_root.exists() else []
        assert active_staging == [], (
            f"Staging dir not wiped after promote: {active_staging}"
        )

    def test_synthesize_validation_failure_stays_in_failed_staging(
        self,
        full_request: SynthesisRequest,
        adapter: FixtureAdapter,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """FR-008: validation runs before promote and preserves diagnostics on failure."""
        from charter.activation.synthesizer.errors import ProjectDRGValidationError
        from charter.activation.synthesizer.manifest import MANIFEST_PATH

        def fail_validate(
            _staging_dir: Path, _shipped_drg: object, conflicts: object = (), org_drg: object = None
        ) -> None:
            # WP02: validate() now takes an optional `conflicts` kwarg
            # (orchestrator._validation_callback passes
            # outcome.delta.conflicts) -- accept and ignore it here so this
            # forced-failure stub still matches the real call signature.
            # #4121 (MAJOR 2) added the org-chain `org_drg` kwarg the same way.
            del conflicts, org_drg
            raise ProjectDRGValidationError(
                errors=("synthetic validation failure",),
                merged_graph_summary="forced by test",
            )

        monkeypatch.setattr("charter.activation.synthesizer.validation_gate.validate", fail_validate)

        with pytest.raises(ProjectDRGValidationError, match="synthetic validation failure"):
            synthesize(full_request, adapter=adapter, repo_root=tmp_path)

        assert not (tmp_path / MANIFEST_PATH).exists()
        assert not (tmp_path / ".kittify" / "doctrine" / "graph.yaml").exists()

        staging_root = tmp_path / ".kittify" / "charter" / ".staging"
        failed_dirs = sorted(
            d for d in staging_root.iterdir() if d.is_dir() and d.name.endswith(".failed")
        )
        assert failed_dirs, "Expected validation failure to preserve a .failed staging directory"
        assert (failed_dirs[0] / "doctrine" / "graph.yaml").exists(), (
            "Expected staged project graph to be preserved for debugging when validation fails"
        )

    def test_synthesize_surfaces_reference_warnings_on_result(
        self,
        full_request: SynthesisRequest,
        adapter: FixtureAdapter,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """#4121 (MAJOR 2): unresolved-reference warnings from the overlay
        emission ride on ``SynthesisResult.reference_warnings`` so CLI callers
        can surface them instead of them living only in ``logging`` output."""
        from charter.activation.synthesizer import project_drg as project_drg_module

        real_emit = project_drg_module.emit_project_layer

        def _emit_with_warning(*args: object, **kwargs: object) -> object:
            sink = kwargs.get("warnings_out")
            if isinstance(sink, list):
                sink.append("agent_profile:ops-responder references unresolved procedure:gone")
            return real_emit(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(project_drg_module, "emit_project_layer", _emit_with_warning)
        result = synthesize(full_request, adapter=adapter, repo_root=tmp_path)
        assert result.reference_warnings == (
            "agent_profile:ops-responder references unresolved procedure:gone",
        )
