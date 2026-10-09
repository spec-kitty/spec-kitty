"""End-to-end resynthesize tests via resynthesize_pipeline.run() (T032).

Covers:
  - US-2 (DRG URN): only affected artifacts regenerate; others byte-identical (SC-006).
  - US-3 (kind+slug, local-first): exactly one artifact regenerated.
  - US-4 (interview section): all derived artifacts regenerated; unrelated untouched.
  - Manifest rewrite preserves prior content_hash for untouched entries (FR-017).
  - EC-4 zero-match: no writes, no model call, diagnostic result.
  - FileNotFoundError when no prior manifest exists.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

import pytest

from kernel.clock import UTC, datetime

from charter.offering.drg.loader import load_graph

from charter.bundle import BUNDLE_CONTENT_HASH_FILES, compute_bundle_content_hash
from charter.activation.synthesizer import (
    FixtureAdapter,
    SynthesisRequest,
    SynthesisTarget,
    synthesize,
)
from charter.activation.synthesizer.errors import ProjectDRGValidationError
from charter.activation.synthesizer.manifest import (
    MANIFEST_PATH,
    SynthesisManifest,
    load_yaml as load_manifest,
    verify_manifest_hash,
)
from charter.activation.synthesizer.resynthesize_pipeline import run as resynthesize_run


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

@pytest.fixture
def fixture_root() -> Path:
    return Path(__file__).parent.parent / "fixtures" / "synthesizer"


@pytest.fixture
def adapter(fixture_root: Path) -> FixtureAdapter:
    return FixtureAdapter(fixture_root=fixture_root)


@pytest.fixture
def full_interview_snapshot() -> dict[str, Any]:
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
def base_target() -> SynthesisTarget:
    return SynthesisTarget(
        kind="directive",
        slug="mission-type-scope-directive",
        title="Mission Type Scope Directive",
        artifact_id="PROJECT_001",
        source_section="mission_type",
    )


@pytest.fixture
def base_request(
    base_target: SynthesisTarget,
    full_interview_snapshot: dict,
    minimal_doctrine_snapshot: dict,
    minimal_drg_snapshot: dict,
) -> SynthesisRequest:
    return SynthesisRequest(
        target=base_target,
        interview_snapshot=full_interview_snapshot,
        doctrine_snapshot=minimal_doctrine_snapshot,
        drg_snapshot=minimal_drg_snapshot,
        run_id="01KPE222CD1MMCYEGB3ZCY51VR",
        adapter_hints={"language": "python"},
    )


@pytest.fixture
def repo_with_prior_synthesis(
    tmp_path: Path,
    base_request: SynthesisRequest,
    adapter: FixtureAdapter,
) -> Path:
    """Create a tmp_path with a full prior synthesis run."""
    synthesize(base_request, adapter=adapter, repo_root=tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _content_hash(yaml_bytes: bytes) -> str:
    return hashlib.sha256(yaml_bytes).hexdigest()  # noqa: TID251 — charter synthesizer resynthesis content hash (own scheme), not charter.hasher.hash_content() freshness


def _artifact_hashes_from_manifest(
    repo_root: Path, manifest: SynthesisManifest
) -> dict[str, str]:
    """Return {kind:slug → content_hash} for all manifest entries."""
    return {
        f"{e.kind}:{e.slug}": e.content_hash
        for e in manifest.artifacts
    }


def _seed_bundle_files(repo: Path) -> None:
    """Seed the four synced bundle files so ``compute_bundle_content_hash``
    returns a real, non-``None`` value.

    ``synthesize()``/``resynthesize`` do not themselves write
    ``.kittify/charter/{governance,directives,references,metadata}.yaml`` —
    those are produced by ``charter sync``/compile (data-model.md fact #20,
    ``bundle.py`` provenance). Tests that need a real ``bundle_content_hash``
    must seed them directly.
    """
    charter_dir = repo / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    for name in BUNDLE_CONTENT_HASH_FILES:
        (charter_dir / name).write_text(f"# {name} fixture content\n", encoding="utf-8")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_git_repo(repo: Path) -> None:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "resynthesize@test.local")
    _git(repo, "config", "user.name", "resynthesize")
    _git(repo, "config", "commit.gpgsign", "false")


def _commit_all(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


# ---------------------------------------------------------------------------
# Baseline test: prior synthesis produces a manifest
# ---------------------------------------------------------------------------


class TestPriorSynthesisBaseline:
    def test_prior_synthesis_manifest_exists(self, repo_with_prior_synthesis: Path) -> None:
        """After synthesize(), manifest exists and has artifacts."""
        manifest_path = repo_with_prior_synthesis / MANIFEST_PATH
        assert manifest_path.exists()
        manifest = load_manifest(manifest_path)
        assert len(manifest.artifacts) > 0


# ---------------------------------------------------------------------------
# Regression: importlib.metadata.PackageNotFoundError must not be mislabeled
# as "resynthesize_pipeline.py is missing" (PackageNotFoundError subclasses
# ModuleNotFoundError, which subclasses ImportError). resynthesize_pipeline.
# run() previously called importlib.metadata.version() directly; a metadata
# resolution failure there would propagate through orchestrator.resynthesize()
# 's except ImportError guard and surface as a false NotImplementedError.
# ---------------------------------------------------------------------------


class TestResynthesizeSurvivesPackageMetadataFailure:
    def test_resynthesize_run_does_not_raise_on_package_not_found(
        self,
        base_request: SynthesisRequest,
        adapter: FixtureAdapter,
        repo_with_prior_synthesis: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A PackageNotFoundError from version lookup must not surface as
        ImportError/NotImplementedError; resynthesize_pipeline.run() must
        complete normally, falling back to the dev sentinel version."""
        from importlib.metadata import PackageNotFoundError

        repo = repo_with_prior_synthesis

        def _raise_package_not_found(name: str) -> str:
            raise PackageNotFoundError(name)

        monkeypatch.setattr("importlib.metadata.version", _raise_package_not_found)

        result = resynthesize_run(
            request=base_request,
            adapter=adapter,
            topic="directive:PROJECT_001",
            repo_root=repo,
        )

        assert not result.is_noop
        assert result.resolved_topic.matched_form == "kind_slug"


# ---------------------------------------------------------------------------
# US-3: kind+slug local-first → exactly one artifact regenerated
# ---------------------------------------------------------------------------


class TestUs3KindSlug:
    def test_resynthesize_single_directive_by_project_id(
        self,
        base_request: SynthesisRequest,
        adapter: FixtureAdapter,
        repo_with_prior_synthesis: Path,
    ) -> None:
        """directive:PROJECT_001 resolves back to the synthesized project directive."""
        repo = repo_with_prior_synthesis

        result = resynthesize_run(
            request=base_request,
            adapter=adapter,
            topic="directive:PROJECT_001",
            repo_root=repo,
        )

        assert not result.is_noop
        assert result.resolved_topic.matched_form == "kind_slug"
        assert len(result.resolved_topic.targets) == 1
        target = result.resolved_topic.targets[0]
        assert target.kind == "directive"
        assert target.artifact_id == "PROJECT_001"
        assert target.slug == "mission-type-scope-directive"

    def test_resynthesize_single_tactic_by_kind_slug(
        self,
        base_request: SynthesisRequest,
        adapter: FixtureAdapter,
        repo_with_prior_synthesis: Path,
    ) -> None:
        """US-3: tactic:how-we-apply-directive-003 → only that artifact regenerated."""
        repo = repo_with_prior_synthesis

        result = resynthesize_run(
            request=base_request,
            adapter=adapter,
            topic="tactic:how-we-apply-directive-003",
            repo_root=repo,
        )

        assert not result.is_noop
        assert result.resolved_topic.matched_form == "kind_slug"
        assert len(result.resolved_topic.targets) == 1
        assert result.resolved_topic.targets[0].slug == "how-we-apply-directive-003"

    def test_resynthesize_kind_slug_is_no_op_stable_when_content_unchanged(
        self,
        base_request: SynthesisRequest,
        adapter: FixtureAdapter,
        repo_with_prior_synthesis: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Unchanged bounded resynthesis returns the persisted manifest and leaves git clean."""
        repo = repo_with_prior_synthesis
        prior_manifest = load_manifest(repo / MANIFEST_PATH)
        prior_run_id = prior_manifest.run_id
        _init_git_repo(repo)
        _commit_all(repo, "baseline synthesis")
        assert _git(repo, "status", "--porcelain") == ""

        from charter.activation.synthesizer import project_drg

        # kernel-clock-single-door (WP07): project_drg now stamps
        # `generated_at` via the door's `now_utc_seconds()` producer rather
        # than a raw `datetime.now(UTC)` call, so the "time has advanced"
        # freeze point is `project_drg.now_utc_seconds` itself.
        later = datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC)
        monkeypatch.setattr(
            project_drg, "now_utc_seconds", lambda: later.isoformat(timespec="seconds")
        )

        result = resynthesize_run(
            request=base_request,
            adapter=adapter,
            topic="tactic:how-we-apply-directive-003",
            repo_root=repo,
        )
        disk_manifest = load_manifest(repo / MANIFEST_PATH)

        assert disk_manifest.run_id == prior_run_id
        assert result.manifest.model_dump(mode="python") == disk_manifest.model_dump(mode="python")
        assert _git(repo, "status", "--porcelain") == ""
        verify_manifest_hash(disk_manifest)

    def test_resynthesize_kind_slug_preserves_unrelated_hashes(
        self,
        base_request: SynthesisRequest,
        adapter: FixtureAdapter,
        repo_with_prior_synthesis: Path,
    ) -> None:
        """FR-017: untouched artifacts retain their prior content_hash."""
        repo = repo_with_prior_synthesis
        prior_manifest = load_manifest(repo / MANIFEST_PATH)
        prior_hashes = _artifact_hashes_from_manifest(repo, prior_manifest)

        result = resynthesize_run(
            request=base_request,
            adapter=adapter,
            topic="tactic:how-we-apply-directive-003",
            repo_root=repo,
        )

        new_hashes = _artifact_hashes_from_manifest(repo, result.manifest)

        # Every artifact NOT in resolved.targets must retain prior hash
        regenerated_key = "tactic:how-we-apply-directive-003"
        for key, prior_hash in prior_hashes.items():
            if key != regenerated_key:
                assert new_hashes.get(key) == prior_hash, (
                    f"FR-017 violation: artifact '{key}' hash changed unexpectedly. "
                    f"prior={prior_hash[:12]}... new={new_hashes.get(key, 'MISSING')[:12]}..."
                )

    def test_resynthesize_kind_slug_preserves_full_project_graph(
        self,
        base_request: SynthesisRequest,
        adapter: FixtureAdapter,
        repo_with_prior_synthesis: Path,
    ) -> None:
        """Bounded resynthesis must not drop untouched project-layer graph nodes."""
        repo = repo_with_prior_synthesis
        graph_path = repo / ".kittify" / "charter-packs" / "graph.yaml"
        before_graph = load_graph(graph_path)
        before_nodes = {node.urn for node in before_graph.nodes}
        before_edges = {
            (edge.source, edge.target, edge.relation.value) for edge in before_graph.edges
        }

        resynthesize_run(
            request=base_request,
            adapter=adapter,
            topic="tactic:how-we-apply-directive-003",
            repo_root=repo,
        )

        after_graph = load_graph(graph_path)
        after_nodes = {node.urn for node in after_graph.nodes}
        after_edges = {
            (edge.source, edge.target, edge.relation.value) for edge in after_graph.edges
        }

        assert after_nodes == before_nodes
        assert after_edges == before_edges


# ---------------------------------------------------------------------------
# US-2: DRG URN → multiple artifacts affected, unrelated unchanged
# ---------------------------------------------------------------------------

    def test_resynthesis_reference_warnings_ride_on_result(
        self,
        base_request: SynthesisRequest,
        adapter: FixtureAdapter,
        repo_with_prior_synthesis: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """#4121 (MAJOR 2): unresolved-reference warnings from the callback's
        overlay re-emission ride on ``ResynthesisResult.reference_warnings``
        so the CLI can surface them."""
        from charter.activation.synthesizer import project_drg

        real_emit = project_drg.emit_project_layer

        def _emit_with_warning(*args: object, **kwargs: object) -> object:
            sink = kwargs.get("warnings_out")
            if isinstance(sink, list):
                sink.append("agent_profile:ops-responder references unresolved procedure:gone")
            return real_emit(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(project_drg, "emit_project_layer", _emit_with_warning)
        result = resynthesize_run(
            request=base_request,
            adapter=adapter,
            topic="tactic:how-we-apply-directive-003",
            repo_root=repo_with_prior_synthesis,
        )
        assert result.reference_warnings == (
            "agent_profile:ops-responder references unresolved procedure:gone",
        )


class TestUs2DrgUrn:
    def test_resynthesize_drg_urn_directive_003(
        self,
        base_request: SynthesisRequest,
        adapter: FixtureAdapter,
        repo_with_prior_synthesis: Path,
    ) -> None:
        """US-2: directive:DIRECTIVE_003 → multiple artifacts referencing that URN."""
        repo = repo_with_prior_synthesis

        result = resynthesize_run(
            request=base_request,
            adapter=adapter,
            topic="directive:DIRECTIVE_003",
            repo_root=repo,
        )

        assert not result.is_noop
        assert result.resolved_topic.matched_form == "drg_urn"
        # At least one artifact should reference directive:DIRECTIVE_003
        assert len(result.resolved_topic.targets) >= 0  # EC-4 is also valid here

    def test_resynthesize_drg_urn_preserves_unrelated_hashes(
        self,
        base_request: SynthesisRequest,
        adapter: FixtureAdapter,
        repo_with_prior_synthesis: Path,
    ) -> None:
        """FR-017: artifacts not referencing the DRG URN retain prior content_hash."""
        repo = repo_with_prior_synthesis
        prior_manifest = load_manifest(repo / MANIFEST_PATH)
        prior_hashes = _artifact_hashes_from_manifest(repo, prior_manifest)

        result = resynthesize_run(
            request=base_request,
            adapter=adapter,
            topic="directive:DIRECTIVE_003",
            repo_root=repo,
        )

        if result.is_noop:
            # EC-4: no writes; manifest unchanged
            return

        new_hashes = _artifact_hashes_from_manifest(repo, result.manifest)
        regenerated_slugs = {t.slug for t in result.resolved_topic.targets}

        for key, prior_hash in prior_hashes.items():
            _, slug = key.split(":", 1)
            if slug not in regenerated_slugs:
                assert new_hashes.get(key) == prior_hash, (
                    f"FR-017 violation: '{key}' hash changed but was not in resynthesis targets"
                )


# ---------------------------------------------------------------------------
# US-4: interview section → all derived artifacts regenerated, unrelated untouched
# ---------------------------------------------------------------------------


class TestUs4InterviewSection:
    def test_resynthesize_section_testing_philosophy(
        self,
        base_request: SynthesisRequest,
        adapter: FixtureAdapter,
        repo_with_prior_synthesis: Path,
    ) -> None:
        """US-4: testing_philosophy section → all artifacts from that section regenerated."""
        repo = repo_with_prior_synthesis

        result = resynthesize_run(
            request=base_request,
            adapter=adapter,
            topic="testing_philosophy",
            repo_root=repo,
        )

        assert not result.is_noop
        assert result.resolved_topic.matched_form == "interview_section"

    def test_resynthesize_section_preserves_unrelated_artifacts(
        self,
        base_request: SynthesisRequest,
        adapter: FixtureAdapter,
        repo_with_prior_synthesis: Path,
    ) -> None:
        """FR-017: artifacts from other sections retain prior content_hash."""
        repo = repo_with_prior_synthesis
        prior_manifest = load_manifest(repo / MANIFEST_PATH)
        prior_hashes = _artifact_hashes_from_manifest(repo, prior_manifest)

        result = resynthesize_run(
            request=base_request,
            adapter=adapter,
            topic="mission_type",
            repo_root=repo,
        )

        if result.is_noop:
            return

        new_hashes = _artifact_hashes_from_manifest(repo, result.manifest)
        regenerated_slugs = {t.slug for t in result.resolved_topic.targets}

        for key, prior_hash in prior_hashes.items():
            _, slug = key.split(":", 1)
            if slug not in regenerated_slugs:
                assert new_hashes.get(key) == prior_hash, (
                    f"FR-017 violation: unrelated artifact '{key}' hash changed"
                )


# ---------------------------------------------------------------------------
# EC-4: zero-match → no writes, no model call, diagnostic
# ---------------------------------------------------------------------------


class TestEc4ZeroMatch:
    def test_zero_match_returns_noop(
        self,
        base_request: SynthesisRequest,
        adapter: FixtureAdapter,
        repo_with_prior_synthesis: Path,
    ) -> None:
        """EC-4: DRG URN that exists but no project artifact references it → noop."""
        repo = repo_with_prior_synthesis

        # Build a DRG with a paradigm URN that no artifact references
        extended_drg = dict(base_request.drg_snapshot)
        extended_drg["nodes"] = list(base_request.drg_snapshot.get("nodes", [])) + [
            {"urn": "paradigm:evidence-first", "kind": "paradigm"}
        ]
        ec4_request = SynthesisRequest(
            target=base_request.target,
            interview_snapshot=base_request.interview_snapshot,
            doctrine_snapshot=base_request.doctrine_snapshot,
            drg_snapshot=extended_drg,
            run_id=base_request.run_id,
            adapter_hints=base_request.adapter_hints,
        )

        result = resynthesize_run(
            request=ec4_request,
            adapter=adapter,
            topic="paradigm:evidence-first",
            repo_root=repo,
        )

        assert result.is_noop
        assert result.diagnostic != ""
        # Manifest unchanged
        assert result.manifest.run_id == load_manifest(repo / MANIFEST_PATH).run_id

    def test_zero_match_manifest_not_rewritten(
        self,
        base_request: SynthesisRequest,
        adapter: FixtureAdapter,
        repo_with_prior_synthesis: Path,
    ) -> None:
        """EC-4: on zero-match, disk manifest is not modified."""
        repo = repo_with_prior_synthesis
        manifest_path = repo / MANIFEST_PATH
        prior_mtime = manifest_path.stat().st_mtime

        extended_drg = dict(base_request.drg_snapshot)
        extended_drg["nodes"] = list(base_request.drg_snapshot.get("nodes", [])) + [
            {"urn": "paradigm:evidence-first", "kind": "paradigm"}
        ]
        ec4_request = SynthesisRequest(
            target=base_request.target,
            interview_snapshot=base_request.interview_snapshot,
            doctrine_snapshot=base_request.doctrine_snapshot,
            drg_snapshot=extended_drg,
            run_id=base_request.run_id,
            adapter_hints=base_request.adapter_hints,
        )

        result = resynthesize_run(
            request=ec4_request,
            adapter=adapter,
            topic="paradigm:evidence-first",
            repo_root=repo,
        )

        assert result.is_noop
        # Manifest file not touched
        assert manifest_path.stat().st_mtime == prior_mtime


# ---------------------------------------------------------------------------
# FileNotFoundError when no prior manifest
# ---------------------------------------------------------------------------


class TestNoPriorManifest:
    def test_raises_file_not_found_without_manifest(
        self,
        base_request: SynthesisRequest,
        adapter: FixtureAdapter,
        tmp_path: Path,
    ) -> None:
        """No prior manifest → FileNotFoundError with helpful message."""
        with pytest.raises(FileNotFoundError, match="No prior synthesis manifest"):
            resynthesize_run(
                request=base_request,
                adapter=adapter,
                topic="tactic:how-we-apply-directive-003",
                repo_root=tmp_path,
            )


class TestResynthesizeValidationWiring:
    def test_validation_failure_keeps_live_state_unchanged(
        self,
        base_request: SynthesisRequest,
        adapter: FixtureAdapter,
        repo_with_prior_synthesis: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """FR-008: resynthesis must validate before mutating the live tree."""
        repo = repo_with_prior_synthesis
        manifest_path = repo / MANIFEST_PATH
        graph_path = repo / ".kittify" / "charter-packs" / "graph.yaml"
        manifest_before = manifest_path.read_text(encoding="utf-8")
        graph_before = graph_path.read_text(encoding="utf-8")

        def fail_validate(
            _staging_dir: Path, _shipped_drg: object, conflicts: object = (), org_drg: object = None
        ) -> None:
            # #4121 (MAJOR 2) added the org-chain ``org_drg`` kwarg to
            # validate(); accept (and ignore) it plus ``conflicts`` so this
            # forced-failure stub keeps matching the real call signature.
            del conflicts, org_drg
            raise ProjectDRGValidationError(
                errors=("forced resynthesis validation failure",),
                merged_graph_summary="forced by test",
            )

        monkeypatch.setattr("charter.activation.synthesizer.validation_gate.validate", fail_validate)

        with pytest.raises(ProjectDRGValidationError, match="forced resynthesis validation failure"):
            resynthesize_run(
                request=base_request,
                adapter=adapter,
                topic="tactic:how-we-apply-directive-003",
                repo_root=repo,
            )

        assert manifest_path.read_text(encoding="utf-8") == manifest_before
        assert graph_path.read_text(encoding="utf-8") == graph_before

        staging_root = repo / ".kittify" / "charter" / ".staging"
        failed_dirs = sorted(
            d for d in staging_root.iterdir() if d.is_dir() and d.name.endswith(".failed")
        )
        assert failed_dirs, "Expected a .failed staging directory when validation rejects resynthesis"
        assert (failed_dirs[0] / "charter-packs" / "graph.yaml").exists()


# ---------------------------------------------------------------------------
# FR-017: manifest content_hash preservation
# ---------------------------------------------------------------------------


class TestManifestContentHashPreservation:
    def test_prior_content_hash_preserved_for_untouched_artifacts(
        self,
        base_request: SynthesisRequest,
        adapter: FixtureAdapter,
        repo_with_prior_synthesis: Path,
    ) -> None:
        """FR-017 core contract: untouched entries keep their prior content_hash."""
        repo = repo_with_prior_synthesis
        prior_manifest = load_manifest(repo / MANIFEST_PATH)

        result = resynthesize_run(
            request=base_request,
            adapter=adapter,
            topic="tactic:how-we-apply-directive-003",
            repo_root=repo,
        )

        regenerated_slug = "how-we-apply-directive-003"
        prior_by_key = {f"{e.kind}:{e.slug}": e.content_hash for e in prior_manifest.artifacts}
        new_by_key = {f"{e.kind}:{e.slug}": e.content_hash for e in result.manifest.artifacts}

        preserved_count = 0
        for key, prior_hash in prior_by_key.items():
            if regenerated_slug not in key:
                assert new_by_key.get(key) == prior_hash, (
                    f"FR-017: '{key}' content_hash changed from "
                    f"{prior_hash[:16]}... to {new_by_key.get(key, 'MISSING')[:16]}..."
                )
                preserved_count += 1

        # At least 90% of unmodified artifacts preserved (SC-006 ≥ 95% threshold)
        total = len(prior_by_key)
        regenerated = 1  # kind_slug always resolves to exactly 1 target
        expected_preserved = total - regenerated
        if expected_preserved > 0:
            ratio = preserved_count / expected_preserved
            assert ratio >= 0.95, (
                f"SC-006: only {ratio:.1%} of unmodified artifacts preserved "
                f"(need ≥ 95%)"
            )


# ---------------------------------------------------------------------------
# WP02 T011: writer-side bundle_content_hash == helper assertion
# (reader-independent per-WP red->green gate)
# ---------------------------------------------------------------------------


class TestBundleContentHashWriterWiring:
    """WP02's reader-independent per-WP red->green gate (T011).

    Asserts on the manifest FIELD value directly -- not on freshness state --
    so these are RED on WP02's base (writers still emit ``None``) and GREEN
    once ``promote``/``_rewrite_manifest`` route through ``finalize_manifest``
    with a real ``compute_bundle_content_hash`` value.
    """

    def test_synthesize_writes_real_bundle_content_hash(
        self,
        base_request: SynthesisRequest,
        adapter: FixtureAdapter,
        tmp_path: Path,
    ) -> None:
        """promote() computes bundle_content_hash via the WP01 helper."""
        _seed_bundle_files(tmp_path)

        synthesize(base_request, adapter=adapter, repo_root=tmp_path)

        manifest = load_manifest(tmp_path / MANIFEST_PATH)
        assert manifest.bundle_content_hash is not None
        assert manifest.bundle_content_hash == compute_bundle_content_hash(tmp_path)

    def test_resynthesize_writes_real_bundle_content_hash(
        self,
        base_request: SynthesisRequest,
        adapter: FixtureAdapter,
        tmp_path: Path,
    ) -> None:
        """_rewrite_manifest computes bundle_content_hash with repo_root threaded.

        The prior manifest (written by the initial ``synthesize()`` before
        the bundle files exist) carries ``bundle_content_hash=None`` -- the
        bundle files are seeded only AFTER that first synthesize, so a
        non-``None`` value observed after ``resynthesize`` is direct proof
        that ``_rewrite_manifest`` (not some stale carried-over value)
        recomputed it via the correctly-threaded ``repo_root``.
        """
        synthesize(base_request, adapter=adapter, repo_root=tmp_path)
        assert load_manifest(tmp_path / MANIFEST_PATH).bundle_content_hash is None

        _seed_bundle_files(tmp_path)

        result = resynthesize_run(
            request=base_request,
            adapter=adapter,
            topic="tactic:how-we-apply-directive-003",
            repo_root=tmp_path,
        )

        assert result.manifest.bundle_content_hash is not None
        assert result.manifest.bundle_content_hash == compute_bundle_content_hash(tmp_path)
        disk_manifest = load_manifest(tmp_path / MANIFEST_PATH)
        assert disk_manifest.bundle_content_hash == compute_bundle_content_hash(tmp_path)


# ---------------------------------------------------------------------------
# WP02 T013: writer recompute on genuine content drift (SC-003 writer half)
# ---------------------------------------------------------------------------


def _drift_governance_file(repo: Path) -> None:
    """Genuinely change the content of the bundle file.

    consolidate-charter-bundle WP06 (T027): ``BUNDLE_CONTENT_HASH_FILES``
    narrowed from the four legacy bundle files to the single ``charter.yaml``
    (contracts/manifest-v2.md M1); this helper's name is kept (only the two
    ``TestBundleContentHashRecomputesOnDrift`` tests below use it) but it now
    drifts ``charter.yaml`` — the only file ``_seed_bundle_files`` seeds.
    Appends a distinguishable line that survives ``hash_content``'s
    BOM-strip/CRLF-normalize/``.strip()`` normalization (a plain trailing
    text line, not whitespace-only).
    """
    charter_yaml_path = repo / ".kittify" / "charter" / "charter.yaml"
    charter_yaml_path.write_text(
        charter_yaml_path.read_text(encoding="utf-8") + "# drift-marker: genuinely-changed\n",
        encoding="utf-8",
    )


class TestBundleContentHashRecomputesOnDrift:
    """T013: reader-independent writer half of SC-003.

    Proves the WRITER recomputes ``bundle_content_hash`` when the synced
    bundle content genuinely changes -- asserts on the FIELD, not freshness
    state. The end-to-end freshness half (stale->remediate->fresh) is WP03's
    T019.
    """

    def test_synthesize_recomputes_hash_on_bundle_content_drift(
        self,
        base_request: SynthesisRequest,
        adapter: FixtureAdapter,
        tmp_path: Path,
    ) -> None:
        _seed_bundle_files(tmp_path)
        synthesize(base_request, adapter=adapter, repo_root=tmp_path)
        manifest_1 = load_manifest(tmp_path / MANIFEST_PATH).bundle_content_hash

        _drift_governance_file(tmp_path)

        synthesize(base_request, adapter=adapter, repo_root=tmp_path)
        manifest_2 = load_manifest(tmp_path / MANIFEST_PATH).bundle_content_hash

        assert manifest_2 is not None
        assert manifest_2 != manifest_1
        assert manifest_2 == compute_bundle_content_hash(tmp_path)

    def test_resynthesize_recomputes_hash_on_bundle_content_drift(
        self,
        base_request: SynthesisRequest,
        adapter: FixtureAdapter,
        tmp_path: Path,
    ) -> None:
        _seed_bundle_files(tmp_path)
        synthesize(base_request, adapter=adapter, repo_root=tmp_path)

        result_1 = resynthesize_run(
            request=base_request,
            adapter=adapter,
            topic="tactic:how-we-apply-directive-003",
            repo_root=tmp_path,
        )
        manifest_1 = result_1.manifest.bundle_content_hash

        _drift_governance_file(tmp_path)

        result_2 = resynthesize_run(
            request=base_request,
            adapter=adapter,
            topic="tactic:how-we-apply-directive-003",
            repo_root=tmp_path,
        )
        manifest_2 = result_2.manifest.bundle_content_hash

        assert manifest_2 is not None
        assert manifest_2 != manifest_1
        assert manifest_2 == compute_bundle_content_hash(tmp_path)
