"""Unit tests for write_pipeline neutrality gate — WP06 (T035–T039).

Tests:
- _is_generic_scoped: no evidence, language-scoped slug, generic slug
- _run_neutrality_gate: biased content raises NeutralityGateViolation
- _run_neutrality_gate: language-scoped artifact skipped
- _run_neutrality_gate: neutral content passes
- Gate timing < 5s
- Fixture helpers for staged content
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from charter.activation.synthesizer.errors import NeutralityGateViolation
from charter.activation.synthesizer.artifact_naming import artifact_filename, extract_directive_number
from charter.activation.synthesizer.manifest import (
    MANIFEST_PATH,
    SynthesisManifest,
    finalize_manifest,
    load_yaml,
    verify_manifest_hash,
)
from charter.activation.synthesizer.path_guard import PathGuard
from charter.activation.synthesizer.write_pipeline import _is_generic_scoped, _write_manifest_file


def _manifest(**overrides: str) -> SynthesisManifest:
    fields = {
        "created_at": "2026-01-01T00:00:00+00:00", "run_id": "first",
        "adapter_id": "fixture", "adapter_version": "1.0.0", "synthesizer_version": "3.2.6",
        "manifest_hash": "0" * 64, "bundle_content_hash": "sha256:" + "a" * 64,
    }
    return finalize_manifest(SynthesisManifest(**{**fields, **overrides}))


@pytest.mark.parametrize(
    "bump",
    [
        {"synthesizer_version": "3.2.7"},
        {"adapter_version": "1.1.0"},
        {"synthesizer_version": "3.2.7", "adapter_version": "1.1.0"},
    ],
    ids=["cli-only", "adapter-only", "both"],
)
def test_manifest_version_only_run_preserves_committed_bytes(tmp_path: Path, bump: dict[str, str]) -> None:
    """A new CLI/adapter release must not restamp unchanged synthesized content (#5089)."""
    guard = PathGuard(tmp_path, extra_allowed_prefixes=[tmp_path])
    original = _manifest()
    _write_manifest_file(guard, tmp_path, original)
    path = tmp_path / MANIFEST_PATH
    before = path.read_bytes()

    upgraded = _manifest(created_at="2026-01-02T00:00:00+00:00", run_id="second", **bump)
    persisted = _write_manifest_file(guard, tmp_path, upgraded)

    assert path.read_bytes() == before
    assert persisted.synthesizer_version == original.synthesizer_version
    assert persisted.adapter_version == original.adapter_version


@pytest.mark.parametrize("existing", ["valid-newer", "corrupt"])
def test_manifest_content_change_records_version_that_ran(tmp_path: Path, existing: str) -> None:
    """A content-changing run records the versions that ran and self-verifies,
    even over a newer-versioned or unparseable committed manifest."""
    guard = PathGuard(tmp_path, extra_allowed_prefixes=[tmp_path])
    path = tmp_path / MANIFEST_PATH
    if existing == "valid-newer":
        _write_manifest_file(guard, tmp_path, _manifest(synthesizer_version="3.2.7"))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not: valid: yaml: [", encoding="utf-8")

    changed = _manifest(run_id="second", bundle_content_hash="sha256:" + "b" * 64)
    written = _write_manifest_file(guard, tmp_path, changed)

    assert written.synthesizer_version == "3.2.6"
    assert written.bundle_content_hash == changed.bundle_content_hash
    on_disk = load_yaml(path)
    assert on_disk.synthesizer_version == "3.2.6"
    verify_manifest_hash(on_disk)


# ---------------------------------------------------------------------------
# Test fixture helpers — inline staged directories (T038)
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit]

def _staged_generic_with_pytest_bias(tmp_path: Path) -> Path:
    """A generic tactic body containing 'pytest' — should trigger gate."""
    staged_dir = tmp_path / "staging" / "generic"
    staged_dir.mkdir(parents=True)
    (staged_dir / "testing-philosophy.tactic.yaml").write_text(
        "title: Testing Philosophy\n"
        "body: |\n"
        "  Always run pytest to verify your code.\n"
        "  Configure pytest.ini for test discovery.\n"
    )
    return staged_dir


def _staged_language_scoped(tmp_path: Path) -> Path:
    """A python-scoped tactic containing 'pytest' — should NOT trigger gate."""
    staged_dir = tmp_path / "staging" / "python-scoped"
    staged_dir.mkdir(parents=True)
    (staged_dir / "python-style-guide.tactic.yaml").write_text(
        "title: Python Style Guide\n"
        "body: |\n"
        "  Use pytest for Python test discovery.\n"
    )
    return staged_dir


def _staged_neutral_generic(tmp_path: Path) -> Path:
    """A generic tactic with no language-specific terms — should pass gate."""
    staged_dir = tmp_path / "staging" / "neutral"
    staged_dir.mkdir(parents=True)
    (staged_dir / "testing-philosophy.tactic.yaml").write_text(
        "title: Testing Philosophy\n"
        "body: |\n"
        "  Test at multiple levels: unit, integration, and end-to-end.\n"
        "  Fast tests should run frequently; slow tests in CI.\n"
    )
    return staged_dir


# ---------------------------------------------------------------------------
# artifact_naming tests
# ---------------------------------------------------------------------------


def test_extract_directive_number_returns_padded_digits() -> None:
    assert extract_directive_number("PROJECT_7") == "007"


def test_extract_directive_number_falls_back_for_malformed_ids() -> None:
    assert extract_directive_number("project_007") == "000"
    assert extract_directive_number("PROJECT_") == "000"
    assert extract_directive_number(None) == "000"


def test_artifact_filename_builds_directive_filename_without_regex() -> None:
    assert (
        artifact_filename("directive", "mission-type-scope-directive", "PROJECT_001")
        == "001-mission-type-scope-directive.directive.yaml"
    )


# ---------------------------------------------------------------------------
# _is_generic_scoped tests (T036, T039)
# ---------------------------------------------------------------------------


def test_is_generic_scoped_no_evidence() -> None:
    """Without evidence, all artifacts are generic-scoped."""
    assert _is_generic_scoped("tactic", "testing-philosophy", None) is True


def test_is_generic_scoped_no_code_signals() -> None:
    """With evidence but no code_signals, all artifacts are generic-scoped."""
    from charter.activation.synthesizer.evidence import EvidenceBundle

    bundle = EvidenceBundle()
    assert _is_generic_scoped("tactic", "testing-philosophy", bundle) is True


def test_is_generic_scoped_unknown_scope_tag() -> None:
    """scope_tag == 'unknown' → generic-scoped even with code_signals."""
    from charter.activation.synthesizer.evidence import CodeSignals, EvidenceBundle

    cs = CodeSignals(
        stack_id="unknown",
        primary_language="unknown",
        frameworks=(),
        test_frameworks=(),
        scope_tag="unknown",
        representative_files=(),
        detected_at="2026-01-01T00:00:00+00:00",
    )
    bundle = EvidenceBundle(code_signals=cs)
    assert _is_generic_scoped("tactic", "unknown-style-guide", bundle) is True


def test_is_generic_scoped_python_scoped_slug_is_not_generic() -> None:
    """With scope_tag='python', a slug containing 'python' is NOT generic-scoped."""
    from charter.activation.synthesizer.evidence import CodeSignals, EvidenceBundle

    cs = CodeSignals(
        stack_id="python",
        primary_language="python",
        frameworks=(),
        test_frameworks=(),
        scope_tag="python",
        representative_files=(),
        detected_at="2026-01-01T00:00:00+00:00",
    )
    bundle = EvidenceBundle(code_signals=cs)
    assert _is_generic_scoped("tactic", "python-style-guide", bundle) is False


def test_is_generic_scoped_python_scope_but_generic_slug() -> None:
    """With scope_tag='python', a slug without 'python' IS generic-scoped."""
    from charter.activation.synthesizer.evidence import CodeSignals, EvidenceBundle

    cs = CodeSignals(
        stack_id="python",
        primary_language="python",
        frameworks=(),
        test_frameworks=(),
        scope_tag="python",
        representative_files=(),
        detected_at="2026-01-01T00:00:00+00:00",
    )
    bundle = EvidenceBundle(code_signals=cs)
    assert _is_generic_scoped("tactic", "testing-philosophy", bundle) is True


def test_is_generic_scoped_different_kinds() -> None:
    """_is_generic_scoped works for directives and styleguides (target_kind ignored for now)."""
    from charter.activation.synthesizer.evidence import CodeSignals, EvidenceBundle

    cs = CodeSignals(
        stack_id="python",
        primary_language="python",
        frameworks=(),
        test_frameworks=(),
        scope_tag="python",
        representative_files=(),
        detected_at="2026-01-01T00:00:00+00:00",
    )
    bundle = EvidenceBundle(code_signals=cs)
    # directive: slug doesn't contain scope_tag → generic
    assert _is_generic_scoped("directive", "commit-message-format", bundle) is True
    # styleguide: slug contains scope_tag → language-scoped
    assert _is_generic_scoped("styleguide", "python-docstrings", bundle) is False


# ---------------------------------------------------------------------------
# _run_neutrality_gate via full staging setup (T039)
# ---------------------------------------------------------------------------


def _make_staging_dir_with_artifact(
    tmp_path: Path,
    kind: str,
    slug: str,
    content: str,
    artifact_id: str | None = None,
) -> tuple[object, object]:
    """Create a StagingDir and a matching ProvenanceEntry for testing the gate."""
    import hashlib

    from charter.activation.synthesizer.staging import StagingDir
    from charter.activation.synthesizer.synthesize_pipeline import ProvenanceEntry, canonical_yaml

    run_id = "01KPWP06TESTGATE00000001"
    stage = StagingDir.create(tmp_path, run_id)

    body: dict[str, str] = {"title": slug, "body": content}
    yaml_bytes = canonical_yaml(body)
    content_hash = hashlib.sha256(yaml_bytes).hexdigest()  # noqa: TID251 — charter synthesizer write-pipeline content hash (own scheme), not charter.hasher.hash_content() freshness

    # Determine artifact_id / urn
    effective_artifact_id = artifact_id or slug
    urn = f"{kind}:{effective_artifact_id}"

    # Write content to staged location
    filename = artifact_filename(kind, slug, effective_artifact_id)

    staged_path = stage.path_for_content(kind, filename)
    staged_path.write_text(content)

    prov = ProvenanceEntry(
        schema_version="2",
        artifact_urn=urn,
        artifact_kind=kind,  # type: ignore[arg-type]
        artifact_slug=slug,
        artifact_content_hash=content_hash,
        inputs_hash="a" * 64,
        adapter_id="fixture",
        adapter_version="1.0.0",
        synthesizer_version="3.2.0a5",
        source_section=None,
        source_urns=["directive:DIRECTIVE_003"],
        source_input_ids=["directive:DIRECTIVE_003"],
        generated_at="2026-04-19T00:00:00+00:00",
        produced_at="2026-01-01T00:00:00+00:00",
        corpus_snapshot_id="(none)",
        synthesis_run_id="01HTEST00000000000000TEST01",
    )

    return stage, prov


def test_gate_fires_on_biased_generic_content(tmp_path: Path) -> None:
    """Generic artifact with 'pytest' triggers NeutralityGateViolation."""
    from charter.activation.synthesizer.write_pipeline import _run_neutrality_gate

    biased_content = (
        "Always run pytest to verify your code.\n"
        "Configure pytest.ini for test discovery.\n"
    )
    stage, prov = _make_staging_dir_with_artifact(
        tmp_path, "tactic", "testing-philosophy", biased_content
    )

    with pytest.raises(NeutralityGateViolation) as exc_info:
        _run_neutrality_gate(stage, [({"title": "test"}, prov)], evidence=None)

    err = exc_info.value
    assert err.artifact_urn == "tactic:testing-philosophy"
    assert len(err.detected_terms) > 0
    assert any("pytest" in t for t in err.detected_terms)
    # Staging dir preserved (points to staging root)
    assert err.staging_dir == stage.root


def test_gate_skips_language_scoped_artifact(tmp_path: Path) -> None:
    """Language-scoped artifact with 'pytest' does NOT trigger NeutralityGateViolation."""
    from charter.activation.synthesizer.evidence import CodeSignals, EvidenceBundle
    from charter.activation.synthesizer.write_pipeline import _run_neutrality_gate

    cs = CodeSignals(
        stack_id="python",
        primary_language="python",
        frameworks=(),
        test_frameworks=(),
        scope_tag="python",
        representative_files=(),
        detected_at="2026-04-19T00:00:00+00:00",
    )
    bundle = EvidenceBundle(code_signals=cs)

    biased_content = "Use pytest for Python test discovery.\n"
    # Slug contains "python" → language-scoped → gate must skip
    stage, prov = _make_staging_dir_with_artifact(
        tmp_path, "tactic", "python-style-guide", biased_content
    )

    # Should not raise
    _run_neutrality_gate(stage, [({"title": "test"}, prov)], evidence=bundle)


def test_gate_passes_on_neutral_generic_content(tmp_path: Path) -> None:
    """Clean generic artifact passes the neutrality gate without raising."""
    from charter.activation.synthesizer.write_pipeline import _run_neutrality_gate

    neutral_content = (
        "Test at multiple levels: unit, integration, and end-to-end.\n"
        "Fast tests should run frequently; slow tests in CI.\n"
    )
    stage, prov = _make_staging_dir_with_artifact(
        tmp_path, "tactic", "testing-philosophy", neutral_content
    )

    # Should not raise
    _run_neutrality_gate(stage, [({"title": "test"}, prov)], evidence=None)


def test_gate_passes_on_empty_results(tmp_path: Path) -> None:
    """Gate with no results raises nothing."""
    from charter.activation.synthesizer.staging import StagingDir
    from charter.activation.synthesizer.write_pipeline import _run_neutrality_gate

    stage = StagingDir.create(tmp_path, "01KPWP06EMPTY000000001")
    _run_neutrality_gate(stage, [], evidence=None)


@pytest.mark.performance
def test_gate_timing(tmp_path: Path) -> None:
    """Neutrality gate completes in under 5 seconds on neutral content."""
    from charter.activation.synthesizer.write_pipeline import _run_neutrality_gate

    neutral_content = (
        "Test at multiple levels: unit, integration, and end-to-end.\n"
        "Fast tests should run frequently; slow tests in CI.\n"
    )
    stage, prov = _make_staging_dir_with_artifact(
        tmp_path, "tactic", "testing-philosophy", neutral_content
    )

    start = time.monotonic()
    _run_neutrality_gate(stage, [({"title": "test"}, prov)], evidence=None)
    elapsed = time.monotonic() - start

    assert elapsed < 5.0, f"Gate took {elapsed:.2f}s (must be < 5s)"


def test_gate_preserves_staging_on_violation(tmp_path: Path) -> None:
    """Staging dir root is preserved (not wiped) when the gate raises."""
    from charter.activation.synthesizer.write_pipeline import _run_neutrality_gate

    biased_content = "Always run pytest to verify your code.\n"
    stage, prov = _make_staging_dir_with_artifact(
        tmp_path, "tactic", "testing-philosophy", biased_content
    )

    staging_root = stage.root
    assert staging_root.exists()

    with pytest.raises(NeutralityGateViolation):
        _run_neutrality_gate(stage, [({"title": "test"}, prov)], evidence=None)

    # Staging root must still exist — gate must NOT wipe it
    assert staging_root.exists(), "Gate must not wipe staging dir on violation"


def test_promote_writes_manifest_with_valid_self_hash(tmp_path: Path) -> None:
    """promote() writes a manifest whose self-hash verifies after reload."""
    from charter.activation.synthesizer.manifest import MANIFEST_PATH, load_yaml, verify_manifest_hash
    from charter.activation.synthesizer.request import SynthesisRequest, SynthesisTarget
    from charter.activation.synthesizer.staging import StagingDir
    from charter.activation.synthesizer.synthesize_pipeline import ProvenanceEntry
    from charter.activation.synthesizer.write_pipeline import promote

    target = SynthesisTarget(
        kind="tactic",
        slug="testing-philosophy",
        title="Testing Philosophy",
        artifact_id="testing-philosophy",
        source_urns=("directive:DIRECTIVE_003",),
    )
    request = SynthesisRequest(
        target=target,
        interview_snapshot={"testing_philosophy": "layered tests"},
        doctrine_snapshot={},
        drg_snapshot={"nodes": [], "edges": [], "schema_version": "1"},
        run_id="01KMANIFESTHASH000000000001",
    )
    provenance = ProvenanceEntry(
        schema_version="2",
        artifact_urn="tactic:testing-philosophy",
        artifact_kind="tactic",
        artifact_slug="testing-philosophy",
        artifact_content_hash="a" * 64,
        inputs_hash="b" * 64,
        adapter_id="fixture",
        adapter_version="1.0.0",
        synthesizer_version="3.2.0a5",
        source_section="testing_philosophy",
        source_urns=["directive:DIRECTIVE_003"],
        source_input_ids=["directive:DIRECTIVE_003"],
        generated_at="2026-04-19T00:00:00+00:00",
        produced_at="2026-04-19T00:00:00+00:00",
        corpus_snapshot_id="(none)",
        synthesis_run_id="01KMANIFESTHASH000000000001",
    )
    stage = StagingDir.create(tmp_path, "01KMANIFESTHASH000000000001")

    promote(
        request=request,
        staging_dir=stage,
        results=[({"title": "Testing Philosophy", "body": "Use layered tests."}, provenance)],
        validation_callback=lambda _stage: None,
        repo_root=tmp_path,
    )

    loaded = load_yaml(tmp_path / MANIFEST_PATH)
    verify_manifest_hash(loaded)
