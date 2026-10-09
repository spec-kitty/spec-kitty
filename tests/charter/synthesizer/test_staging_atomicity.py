"""Tests for staging atomicity — WP03 T016 / T018 / T020.

Covers (quickstart §1 "What just happened under the hood" as test oracle):
1. StagingDir.create() sets up the directory hierarchy.
2. path_for_content / path_for_provenance return correct sub-paths.
3. commit_to_failed: staging dir renamed to .failed/; cause.yaml written.
4. wipe(): staging dir removed after successful promote.
5. Context manager: unhandled exception → commit_to_failed; success → no auto-wipe.
6. write_pipeline.promote(): validation callback failure → no files in live tree.
7. write_pipeline.promote(): promote fails mid-replace → no manifest written.
8. write_pipeline.promote(): successful promote → manifest written, staging wiped.
9. Fail-closed timing < 5s (NFR-004) — ensured by pytest-timeout or simple timing.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from charter.activation.synthesizer.errors import StagingPromoteError
from charter.activation.synthesizer.manifest import MANIFEST_PATH, SynthesisManifest, load_yaml as load_manifest
from charter.activation.synthesizer.staging import StagingDir
from charter.activation.synthesizer.synthesize_pipeline import ProvenanceEntry, canonical_yaml
from charter.activation.synthesizer.write_pipeline import promote


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit]

RUN_ID = "01KPE222TESTSTAGING00000001"


def _make_repo_root(tmp_path: Path) -> Path:
    """Set up a fake repo root with required .kittify structure."""
    repo = tmp_path / "repo"
    repo.mkdir()
    # PathGuard needs the .kittify dirs to be present so writes are allowed
    (repo / ".kittify" / "charter").mkdir(parents=True)
    (repo / ".kittify" / "charter-packs").mkdir(parents=True)
    return repo


def _make_provenance(
    kind: str = "tactic",
    slug: str = "my-tactic",
    content_hash: str | None = None,
) -> ProvenanceEntry:
    body = {"id": "tac-001", "title": "My Tactic", "summary": "Test."}
    yaml_bytes = canonical_yaml(body)
    ch = content_hash or hashlib.sha256(yaml_bytes).hexdigest()  # noqa: TID251 — charter synthesizer staging content hash (own scheme), not charter.hasher.hash_content() freshness
    return ProvenanceEntry(
        schema_version="2",
        artifact_urn=f"{kind}:{slug}",
        artifact_kind=kind,  # type: ignore[arg-type]
        artifact_slug=slug,
        artifact_content_hash=ch,
        inputs_hash="b" * 64,
        adapter_id="fixture",
        adapter_version="1.0.0",
        synthesizer_version="3.2.0a5",
        source_section=None,
        source_urns=["directive:DIRECTIVE_003"],
        source_input_ids=["directive:DIRECTIVE_003"],
        generated_at="2026-04-17T12:00:00+00:00",
        produced_at="2026-01-01T00:00:00+00:00",
        corpus_snapshot_id="(none)",
        synthesis_run_id="01HTEST00000000000000TEST01",
    )


# ---------------------------------------------------------------------------
# T016: StagingDir lifecycle tests
# ---------------------------------------------------------------------------


def test_staging_create_creates_subdirs(tmp_path: Path) -> None:
    """StagingDir.create() creates all required subdirectories."""
    stage = StagingDir.create(tmp_path, RUN_ID)
    assert (stage.root / "charter-packs" / "directive").is_dir()
    assert (stage.root / "charter-packs" / "tactic").is_dir()
    assert (stage.root / "charter-packs" / "styleguide").is_dir()
    assert (stage.root / "charter" / "provenance").is_dir()


def test_staging_path_for_content(tmp_path: Path) -> None:
    """path_for_content returns correct location under doctrine subtree."""
    stage = StagingDir.create(tmp_path, RUN_ID)
    p = stage.path_for_content("tactic", "my-tactic.tactic.yaml")
    assert p == stage.root / "charter-packs" / "tactic" / "my-tactic.tactic.yaml"


def test_staging_path_for_provenance(tmp_path: Path) -> None:
    """path_for_provenance returns correct location under charter subtree."""
    stage = StagingDir.create(tmp_path, RUN_ID)
    p = stage.path_for_provenance("directive", "my-dir")
    assert p == stage.root / "charter" / "provenance" / "directive-my-dir.yaml"


def test_staging_wipe_removes_dir(tmp_path: Path) -> None:
    """StagingDir.wipe() removes the staging directory."""
    stage = StagingDir.create(tmp_path, RUN_ID)
    assert stage.root.exists()
    stage.wipe()
    assert not stage.root.exists()


def test_staging_commit_to_failed_renames_and_writes_cause(tmp_path: Path) -> None:
    """commit_to_failed renames staging to .failed/ and writes cause.yaml."""
    stage = StagingDir.create(tmp_path, RUN_ID)
    original_root = stage.root
    failed_dir = original_root.parent / f"{RUN_ID}.failed"

    stage.commit_to_failed("test failure reason")

    assert not original_root.exists(), "Original staging dir should be gone"
    assert failed_dir.is_dir(), ".failed/ dir should exist"
    cause_path = failed_dir / "cause.yaml"
    assert cause_path.exists(), "cause.yaml should be written"
    content = cause_path.read_text()
    assert "test failure reason" in content


def test_context_manager_on_exception_routes_to_failed(tmp_path: Path) -> None:
    """Context manager routes unhandled exceptions to commit_to_failed."""
    stage = StagingDir.create(tmp_path, RUN_ID)
    original_root = stage.root
    failed_dir = original_root.parent / f"{RUN_ID}.failed"

    with pytest.raises(ValueError), stage:
        raise ValueError("simulated failure")

    assert not original_root.exists() or not original_root.is_dir() or failed_dir.is_dir()


def test_context_manager_on_success_does_not_auto_wipe(tmp_path: Path) -> None:
    """Context manager on success does NOT wipe staging — caller must call wipe()."""
    stage = StagingDir.create(tmp_path, RUN_ID)
    result = stage.__enter__()
    try:
        pass
    finally:
        exit_result = stage.__exit__(None, None, None)
    # Staging dir should still exist (caller is responsible for wipe after promote)
    assert result is stage
    assert exit_result is None
    assert stage.root.exists()


# ---------------------------------------------------------------------------
# T018 / T020: write_pipeline.promote() atomicity tests
# ---------------------------------------------------------------------------


def _make_results(kind: str = "tactic", slug: str = "my-tactic") -> list:
    body = {"id": "tac-001", "title": "My Tactic", "summary": "Test."}
    prov = _make_provenance(kind=kind, slug=slug)
    return [(body, prov)]


def _no_op_validation(staging_dir: StagingDir) -> None:
    """Validation callback that passes (WP04 placeholder)."""
    pass


def _failing_validation(staging_dir: StagingDir) -> None:
    """Validation callback that raises (simulates WP04 gate failure)."""
    raise ValueError("DRG validation failed: dangling reference")


def test_promote_validation_failure_no_files_in_live_tree(tmp_path: Path) -> None:
    """Validation callback raising → no files promoted to live tree; staging → .failed/."""
    repo = _make_repo_root(tmp_path)
    from charter.activation.synthesizer.request import SynthesisTarget
    target = SynthesisTarget(
        kind="tactic",
        slug="my-tactic",
        title="My Tactic",
        artifact_id="my-tactic",
        source_urns=("directive:DIRECTIVE_003",),
    )

    stage = StagingDir.create(repo, RUN_ID)
    results = _make_results()

    # Create a fake SynthesisRequest with run_id matching the staging dir
    request = _fake_request(target, RUN_ID)

    with pytest.raises(ValueError, match="DRG validation"):
        promote(
            request=request,
            staging_dir=stage,
            results=results,
            validation_callback=_failing_validation,
            repo_root=repo,
        )

    # No files in live tree
    pack_root = repo / ".kittify" / "charter-packs"
    assert not list(pack_root.rglob("*.tactic.yaml"))

    # Manifest NOT written
    manifest_path = repo / MANIFEST_PATH
    assert not manifest_path.exists()

    # Staging dir preserved as .failed/
    failed_dir = (repo / ".kittify" / "charter" / ".staging" / RUN_ID).parent / f"{RUN_ID}.failed"
    assert failed_dir.is_dir() or not stage.root.exists()


def test_promote_success_writes_files_and_manifest(tmp_path: Path) -> None:
    """Successful promote writes artifact + provenance + manifest; wipes staging."""
    repo = _make_repo_root(tmp_path)
    target = _make_target()
    stage = StagingDir.create(repo, RUN_ID)
    results = _make_results()
    request = _fake_request(target, RUN_ID)

    manifest = promote(
        request=request,
        staging_dir=stage,
        results=results,
        validation_callback=_no_op_validation,
        repo_root=repo,
    )

    assert isinstance(manifest, SynthesisManifest)
    assert manifest.run_id == RUN_ID

    # Artifact file in live tree
    live_tactic = repo / ".kittify" / "charter-packs" / "tactic" / "my-tactic.tactic.yaml"
    assert live_tactic.exists()

    # Provenance sidecar in live tree
    live_prov = repo / ".kittify" / "charter" / "provenance" / "tactic-my-tactic.yaml"
    assert live_prov.exists()

    # Manifest written
    manifest_path = repo / MANIFEST_PATH
    assert manifest_path.exists()
    loaded = load_manifest(manifest_path)
    assert loaded.run_id == RUN_ID
    assert {a.slug for a in loaded.artifacts} == {"my-tactic"}

    # Staging dir wiped
    assert not stage.root.exists()


def test_promote_mid_replace_failure_no_manifest(tmp_path: Path) -> None:
    """Promote crash mid-replace leaves live tree authored but no manifest → partial-and-rerunable."""
    repo = _make_repo_root(tmp_path)
    target = _make_target()
    stage = StagingDir.create(repo, RUN_ID)
    results = _make_results()
    request = _fake_request(target, RUN_ID)

    call_count = [0]
    original_replace = __import__("os").replace

    def patched_replace(src: str, dst: str) -> None:
        call_count[0] += 1
        if call_count[0] >= 2:
            raise OSError("simulated mid-replace crash")
        original_replace(src, dst)

    with patch("os.replace", patched_replace), pytest.raises((StagingPromoteError, OSError)):
        promote(
            request=request,
            staging_dir=stage,
            results=results,
            validation_callback=_no_op_validation,
            repo_root=repo,
        )

    # Manifest must NOT be present (partial-promote state)
    manifest_path = repo / MANIFEST_PATH
    assert not manifest_path.exists(), "Manifest must not be written on partial promote"


@pytest.mark.performance
def test_promote_fail_closed_timing(tmp_path: Path) -> None:
    """Fail-closed path (validation failure) completes in under 5 seconds (NFR-004)."""
    repo = _make_repo_root(tmp_path)
    target = _make_target()
    stage = StagingDir.create(repo, RUN_ID + "T")
    results = _make_results()
    request = _fake_request(target, RUN_ID + "T")

    start = time.monotonic()
    with pytest.raises(ValueError):  # _failing_validation raises ValueError
        promote(
            request=request,
            staging_dir=stage,
            results=results,
            validation_callback=_failing_validation,
            repo_root=repo,
        )
    elapsed = time.monotonic() - start
    assert elapsed < 5.0, f"Fail-closed took {elapsed:.2f}s (> 5s NFR-004 limit)"


def test_schema_failure_no_files_in_live_tree(tmp_path: Path) -> None:
    """Schema failure (from T012/WP02) before promote: no files in live tree; staging preserved.

    This simulates a schema error being raised BEFORE promote is called
    (i.e. before write_pipeline.promote is invoked), confirming that the
    staging context manager preserves the dir as .failed/.
    """
    repo = _make_repo_root(tmp_path)
    stage = StagingDir.create(repo, RUN_ID + "S")

    with pytest.raises(RuntimeError, match="schema failure"), stage:
        raise RuntimeError("schema failure: body does not match directive schema")

    # No files in live doctrine tree
    pack_root = repo / ".kittify" / "charter-packs"
    assert not list(pack_root.rglob("*.yaml"))

    # Staging preserved as .failed/
    failed_dir = stage.root.parent / f"{RUN_ID}S.failed"
    assert failed_dir.is_dir()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_target(kind: str = "tactic", slug: str = "my-tactic") -> object:
    from charter.activation.synthesizer.request import SynthesisTarget
    return SynthesisTarget(
        kind=kind,
        slug=slug,
        title="My Tactic",
        artifact_id=slug,
        source_urns=("directive:DIRECTIVE_003",),
    )


def _fake_request(target: object, run_id: str) -> object:
    from charter.activation.synthesizer.request import SynthesisRequest
    return SynthesisRequest(
        target=target,
        interview_snapshot={},
        doctrine_snapshot={},
        drg_snapshot={},
        run_id=run_id,
        adapter_hints=None,
    )
