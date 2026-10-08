"""FR-009: charter synthesize post-condition is atomic.

After synthesis, exactly one of the two states holds:

* ``.kittify/charter-packs/graph.yaml`` exists AND
  ``synthesis-manifest.yaml`` has ``built_in_only: false``.
* ``graph.yaml`` does NOT exist AND ``synthesis-manifest.yaml`` has
  ``built_in_only: true``.

The forbidden state (``built_in_only: true`` AND ``graph.yaml`` present)
must NEVER be reachable from the synthesizer.  Exercises the dedicated
``apply_post_condition`` helper in ``charter.activation.synthesizer.project_drg``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import pytest

from charter.activation.synthesizer.manifest import SynthesisManifest, finalize_manifest
from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_manifest(
    repo: Path,
    *,
    built_in_only: bool,
    bundle_content_hash: str | None = None,
) -> Path:
    """Seed a synthesis manifest on disk.

    ``bundle_content_hash`` defaults to ``None`` -- backward-compatible: no
    ``bundle_content_hash`` key is written at all (a pre-fix v2-shaped
    manifest). When a real value IS supplied, the manifest is built as a
    genuine ``SynthesisManifest`` instance and routed through
    ``finalize_manifest`` so ``manifest_hash`` is internally consistent
    (``verify_manifest_hash`` passes on the SEED itself, per T012).
    """
    manifest_path = repo / ".kittify" / "charter" / "synthesis-manifest.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    if bundle_content_hash is None:
        manifest_data = {
            "schema_version": "2",
            "mission_id": None,
            "created_at": "2099-01-01T00:00:00+00:00",
            "run_id": "01JTESTRUNIDXXXXXXXXXXXXXX",
            "adapter_id": "test",
            "adapter_version": "0.0.0",
            "synthesizer_version": "0.0.0",
            "artifacts": [],
            "built_in_only": built_in_only,
        }
        manifest_hash = hashlib.sha256(canonical_yaml(manifest_data)).hexdigest()  # noqa: TID251 — charter synthesizer manifest self-hash, not charter.hasher.hash_content() freshness
        manifest_path.write_text(
            dedent(
                f"""\
                schema_version: '2'
                mission_id: null
                created_at: '2099-01-01T00:00:00+00:00'
                run_id: 01JTESTRUNIDXXXXXXXXXXXXXX
                adapter_id: test
                adapter_version: '0.0.0'
                synthesizer_version: '0.0.0'
                manifest_hash: {manifest_hash}
                artifacts: []
                built_in_only: {str(built_in_only).lower()}
                """
            ),
            encoding="utf-8",
        )
        return manifest_path

    seeded = finalize_manifest(
        SynthesisManifest(
            mission_id=None,
            created_at="2099-01-01T00:00:00+00:00",
            run_id="01JTESTRUNIDXXXXXXXXXXXXXX",
            adapter_id="test",
            adapter_version="0.0.0",
            synthesizer_version="0.0.0",
            manifest_hash="0" * 64,
            artifacts=[],
            built_in_only=built_in_only,
            bundle_content_hash=bundle_content_hash,
        )
    )
    manifest_path.write_text(
        canonical_yaml(seeded.model_dump(mode="python")).decode("utf-8"),
        encoding="utf-8",
    )
    return manifest_path


def _seed_graph(repo: Path) -> Path:
    p = repo / ".kittify" / "charter-packs" / "graph.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("schema_version: '1.0'\nnodes: []\nedges: []\n", encoding="utf-8")
    return p


def _read_built_in_only(manifest_path: Path) -> bool:
    from ruamel.yaml import YAML

    data = YAML(typ="safe").load(manifest_path.read_text(encoding="utf-8")) or {}
    return bool(data.get("built_in_only", False))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_post_condition_sets_built_in_only_and_removes_graph(tmp_path: Path) -> None:
    """When synthesis produced no project graph, the helper must:

    1. Delete the live ``graph.yaml`` (if any).
    2. Set ``built_in_only=true`` in the manifest.
    """
    from charter.activation.synthesizer.project_drg import apply_post_condition

    _seed_manifest(tmp_path, built_in_only=False)
    graph_path = _seed_graph(tmp_path)

    apply_post_condition(tmp_path, has_project_graph=False)

    manifest_path = tmp_path / ".kittify" / "charter" / "synthesis-manifest.yaml"
    assert manifest_path.exists()
    assert not graph_path.exists(), "graph.yaml should have been deleted"
    assert _read_built_in_only(manifest_path) is True


def test_post_condition_recomputes_hash_when_built_in_only_changes(tmp_path: Path) -> None:
    """Changing built_in_only must also refresh manifest_hash."""
    from charter.activation.synthesizer.manifest import load_yaml, verify_manifest_hash
    from charter.activation.synthesizer.project_drg import apply_post_condition

    _seed_manifest(tmp_path, built_in_only=False)
    _seed_graph(tmp_path)

    apply_post_condition(tmp_path, has_project_graph=False)

    manifest_path = tmp_path / ".kittify" / "charter" / "synthesis-manifest.yaml"
    verify_manifest_hash(load_yaml(manifest_path))


def test_post_condition_preserves_graph_and_clears_built_in_only(tmp_path: Path) -> None:
    """When synthesis emitted a project graph, the helper must leave the
    graph in place and ensure ``built_in_only=false`` in the manifest."""
    from charter.activation.synthesizer.manifest import load_yaml, verify_manifest_hash
    from charter.activation.synthesizer.project_drg import apply_post_condition

    _seed_manifest(tmp_path, built_in_only=True)
    graph_path = _seed_graph(tmp_path)

    apply_post_condition(tmp_path, has_project_graph=True)

    manifest_path = tmp_path / ".kittify" / "charter" / "synthesis-manifest.yaml"
    assert manifest_path.exists()
    assert graph_path.exists(), "graph.yaml must be retained"
    assert _read_built_in_only(manifest_path) is False
    verify_manifest_hash(load_yaml(manifest_path))


def test_post_condition_no_op_when_manifest_already_consistent(tmp_path: Path) -> None:
    """Idempotency: invoking twice must not perturb the state."""
    from charter.activation.synthesizer.project_drg import apply_post_condition

    _seed_manifest(tmp_path, built_in_only=True)
    apply_post_condition(tmp_path, has_project_graph=False)
    manifest_before = (
        tmp_path / ".kittify" / "charter" / "synthesis-manifest.yaml"
    ).read_text(encoding="utf-8")

    apply_post_condition(tmp_path, has_project_graph=False)
    manifest_after = (
        tmp_path / ".kittify" / "charter" / "synthesis-manifest.yaml"
    ).read_text(encoding="utf-8")
    assert manifest_before == manifest_after


def test_post_condition_atomic_on_injected_failure(tmp_path: Path) -> None:
    """If ``os.replace`` fails between the unlink and the manifest rename,
    the manifest on disk must be the *original* (not half-written) and the
    forbidden conflict state must not appear.
    """
    import os

    from charter.activation.synthesizer import project_drg as _pd

    _seed_manifest(tmp_path, built_in_only=False)
    graph_path = _seed_graph(tmp_path)
    manifest_path = tmp_path / ".kittify" / "charter" / "synthesis-manifest.yaml"
    original_text = manifest_path.read_text(encoding="utf-8")

    # Inject a failure on os.replace inside apply_post_condition.
    real_replace = os.replace

    def _exploding_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        raise OSError("simulated replace failure")

    with (
        patch("os.replace", side_effect=_exploding_replace),
        pytest.raises(OSError, match="simulated replace failure"),
    ):
        _pd.apply_post_condition(tmp_path, has_project_graph=False)

    # Restore original os.replace reference (context manager handles unpatch).
    assert os.replace is real_replace

    # Manifest must be unchanged on disk → no half-written content.
    assert manifest_path.read_text(encoding="utf-8") == original_text
    # The unlink may or may not have executed before the replace failure;
    # this is acceptable per the docstring atomicity contract.  What MUST
    # NOT happen is the forbidden state (built_in_only=true in manifest
    # AND graph.yaml present): the manifest on disk still says
    # built_in_only=false, so the conflict state is unreachable.
    assert _read_built_in_only(manifest_path) is False
    # graph_path absence is fine; presence is also fine.  Reference for
    # diagnostic clarity:
    _ = graph_path.exists()


def test_post_condition_no_op_when_manifest_missing(tmp_path: Path) -> None:
    """Defensive: invoking before promote has written the manifest is a
    silent no-op (no exception, no filesystem mutation)."""
    from charter.activation.synthesizer.project_drg import apply_post_condition

    apply_post_condition(tmp_path, has_project_graph=False)

    assert not (tmp_path / ".kittify" / "charter" / "synthesis-manifest.yaml").exists()


def test_post_condition_preserves_bundle_content_hash_through_mutation_branch(
    tmp_path: Path,
) -> None:
    """WP02 T012 -- BLOCKER-1 non-vacuous pin.

    The synthesize-driven post-condition tests above are NOT sufficient to
    catch BLOCKER-1: ``apply_post_condition`` takes a fast-path early-return
    on a normal non-built-in synthesize (``built_in_only`` already matches
    the desired value), so a normal synthesize flow NEVER reaches the
    mutation branch where the field was silently dropped. This test seeds
    the EXACT precondition that drives the mutation branch directly: a REAL
    non-``None`` ``bundle_content_hash`` + ``built_in_only=False`` + a
    project graph present, then calls ``apply_post_condition(has_project_
    graph=False)`` -- ``desired_built_in_only`` becomes ``True`` != the
    seeded ``False``, bypassing the fast path (``project_drg.py:307-310``).

    Pre-fix (explicit-kwarg ``SynthesisManifest(...)`` reconstruction that
    omits ``bundle_content_hash``), the field reverts to ``None`` and
    ``verify_manifest_hash`` raises (the stored self-hash was computed over
    the real value). Post-fix (``model_copy`` + ``finalize_manifest``), the
    field survives the flip and the self-hash still verifies.
    """
    from charter.activation.synthesizer.manifest import load_yaml, verify_manifest_hash
    from charter.activation.synthesizer.project_drg import apply_post_condition

    seeded_hash = "sha256:" + "c" * 64
    _seed_manifest(tmp_path, built_in_only=False, bundle_content_hash=seeded_hash)
    _seed_graph(tmp_path)

    apply_post_condition(tmp_path, has_project_graph=False)

    manifest_path = tmp_path / ".kittify" / "charter" / "synthesis-manifest.yaml"
    reloaded = load_yaml(manifest_path)
    assert reloaded.bundle_content_hash == seeded_hash, (
        "BLOCKER-1: bundle_content_hash did not survive the built_in_only flip"
    )
    verify_manifest_hash(reloaded)
