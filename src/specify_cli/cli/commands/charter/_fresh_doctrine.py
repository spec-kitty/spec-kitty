"""Fresh-project doctrine seed materialisation helpers (WP06 split).

Carved out of ``_synthesis.py`` so the synthesis helper module stays well
under 500 lines. Behaviour is unchanged — these helpers materialise the
minimal ``.kittify/charter-packs/`` artifact set the runtime needs when no
LLM-authored YAMLs are present (see issue #839 / WP06 T031-T033).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kernel.charter_pack_paths import PROJECT_GRAPH_FILENAME, project_pack_path, project_pack_root

#: The human-readable provenance note at the project charter pack root.
_PROVENANCE_FILENAME = "PROVENANCE.md"

# T031 (#839 minimal artifact set): the runtime consumes ``.kittify/charter-packs/``
# via ``ActiveCharterService(project_root=...)``. The candidate-list resolver in
# ``src/charter/activation/_doctrine_paths.py::resolve_project_root`` treats project-root
# discovery as **directory-presence only** — an empty ``.kittify/charter-packs/`` is
# a valid candidate, and the built-in layer (``packs/built-in/``) supplies content
# until the project layer is populated. The minimal artifact set
# ``charter synthesize`` must produce on a fresh project to unblock the runtime
# is therefore:
#
#   1. ``.kittify/charter-packs/``                 — directory marker (REQUIRED)
#   2. ``.kittify/charter-packs/PROVENANCE.md``    — human-readable provenance note
#                                                  describing the seed source
#                                                  (REQUIRED for auditability)
#   3. ``.kittify/charter/synthesis-manifest.yaml`` — machine-readable marker
#                                                  declaring built_in_only=true
#
# Project-layer DRG graph artifacts are produced ONLY when an LLM-authored
# corpus exists under ``.kittify/charter/generated/``. The fresh-seed manifest
# is the authoritative "built-in doctrine fallback is intended" marker used by
# charter freshness/preflight.
# See spec.md FR-015 / Spec Assumption A2 / GitHub issue #839.
_MINIMAL_FRESH_DOCTRINE_PROVENANCE_TEMPLATE = """\
# Spec Kitty Doctrine — Fresh Project Seed

This `.kittify/charter-packs/` tree was materialized by `spec-kitty charter
synthesize` running against a **fresh project** (no LLM-authored YAML under
`.kittify/charter/generated/`). It exists so `ActiveCharterService` discovers a
project layer and the runtime can advance; it is intentionally empty.

The runtime falls back to the packaged built-in doctrine
(`packs/built-in/`) for all artifact lookups until the LLM harness writes
project-local artifacts under `.kittify/charter/generated/` and you re-run
`spec-kitty charter synthesize`.

References
----------
- GitHub issue: https://github.com/spec-kitty/spec-kitty/issues/839
- Spec assumption A2: public CLI synthesize works on a fresh project.
- Project-root resolution: `src/charter/activation/_doctrine_paths.py`.
"""


def _fresh_seed_manifest_text() -> str:
    """Build the deterministic built-in-only synthesis manifest text."""
    from importlib.metadata import version as _pkg_version

    from charter.activation.synthesizer.manifest import SynthesisManifest, finalize_manifest
    from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml

    try:
        synthesizer_version = _pkg_version("spec-kitty-cli")
    except Exception:
        synthesizer_version = "unknown"

    # schema_version STAYS "2" intentionally (data-model.md): the freshness
    # reader short-circuits on built_in_only before any version/hash check,
    # and versioning.py's v2 repair guards on != "2" — bumping here would
    # only perturb test_bundle_validate_fresh_seed.py's golden with no
    # benefit. bundle_content_hash stays None (model default) for the same
    # reason.
    without_hash: dict[str, object] = {
        "schema_version": "2",
        "mission_id": None,
        "created_at": "1970-01-01T00:00:00+00:00",
        "run_id": "fresh-project-seed",
        "adapter_id": "fresh-seed",
        "adapter_version": synthesizer_version,
        "synthesizer_version": synthesizer_version,
        "artifacts": [],
        "built_in_only": True,
    }
    manifest = SynthesisManifest.model_validate({**without_hash, "manifest_hash": "0" * 64})
    manifest = finalize_manifest(manifest)
    # Explicit annotation: the ``charter.*`` mypy override (pyproject.toml
    # [[tool.mypy.overrides]]) sets follow_imports="skip" for intra-package
    # imports, which erases canonical_yaml's declared "-> bytes" return type
    # to Any here (pre-existing, not introduced by this reroute — confirmed
    # present before the finalize_manifest change too). Annotating recovers
    # the real type without a suppression comment.
    text: str = canonical_yaml(manifest.model_dump(mode="python")).decode("utf-8")
    return text


def _materialize_fresh_doctrine(repo_root: Path) -> list[str]:
    """Materialize the minimal ``.kittify/charter-packs/`` artifact set.

    Used on a fresh project where ``.kittify/charter/generated/`` has no
    agent-authored YAML (T032 / #839). Sources the canonical seed text from
    this module's in-package constant — no external file I/O, no new
    dependency, no doctrine-subsystem changes.

    Idempotent: re-runs produce bytewise-identical output (T033). Returns the
    list of repo-relative paths written.
    """
    doctrine_dir = project_pack_root(repo_root)
    charter_dir = repo_root / ".kittify" / "charter"
    doctrine_dir.mkdir(parents=True, exist_ok=True)
    charter_dir.mkdir(parents=True, exist_ok=True)

    provenance_path = doctrine_dir / _PROVENANCE_FILENAME
    # Idempotency: only write if content differs (avoids needless mtime churn,
    # though byte-stability is preserved either way).
    new_bytes = _MINIMAL_FRESH_DOCTRINE_PROVENANCE_TEMPLATE.encode("utf-8")
    if not provenance_path.exists() or provenance_path.read_bytes() != new_bytes:
        provenance_path.write_bytes(new_bytes)

    manifest_path = charter_dir / "synthesis-manifest.yaml"
    manifest_text = _fresh_seed_manifest_text()
    if not manifest_path.exists() or manifest_path.read_text(encoding="utf-8") != manifest_text:
        manifest_path.write_text(manifest_text, encoding="utf-8")

    # #1717 Fix A: the fresh-seed manifest declares built_in_only=true, so any
    # stale project-local graph.yaml the manifest disowns must be removed.
    # Mirrors the synthesizer's own post-condition (project_drg.
    # apply_post_condition, has_project_graph=False) for the path that bypasses
    # the synthesizer. FR-007: both sites route through the one shared helper.
    from charter.activation.synthesizer.graph_residue import unlink_stale_project_graph  # noqa: PLC0415

    unlink_stale_project_graph(doctrine_dir)

    return [
        str(provenance_path.relative_to(repo_root)),
        str(manifest_path.relative_to(repo_root)),
    ]


def _planned_fresh_doctrine_paths(repo_root: Path) -> list[str]:
    """Return the repo-relative paths a fresh-project synthesize would write.

    Used by ``--dry-run`` on a fresh project (#839 follow-up): callers preview
    the materialization without touching the filesystem. Must mirror the write
    output of :func:`_materialize_fresh_doctrine` exactly.
    """
    doctrine_dir = project_pack_root(repo_root)
    charter_dir = repo_root / ".kittify" / "charter"
    return [
        str((doctrine_dir / _PROVENANCE_FILENAME).relative_to(repo_root)),
        str((charter_dir / "synthesis-manifest.yaml").relative_to(repo_root)),
    ]


def _planned_fresh_doctrine_deletes(repo_root: Path) -> list[str]:
    """Return repo-relative paths fresh-project synthesize would delete."""
    graph_path = project_pack_path(repo_root, PROJECT_GRAPH_FILENAME)
    if not graph_path.exists():
        return []
    return [str(graph_path.relative_to(repo_root))]


def _synthesize_project_doctrine(repo_root: Path, *, dry_run: bool) -> dict[str, Any] | None:
    """Preserve a direct-written corpus before considering the empty seed path.

    Absence of generated inputs says nothing about the project doctrine tree.
    Registration owns its graph, provenance and manifest; synthesis only stamps
    the current bundle hash and records that this corpus was preserved.
    """
    from dataclasses import replace
    from importlib.metadata import version

    from charter.activation.project_registration import commit_project_registration, plan_project_registration
    from charter.activation.synthesizer.manifest import (
        MANIFEST_PATH,
        SynthesisManifest,
        finalize_manifest,
        load_yaml,
    )
    from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml
    from charter.bundle import compute_bundle_content_hash
    from charter.drg import scan_project_artifacts
    from ruamel.yaml import YAML

    if not scan_project_artifacts(repo_root):
        return None
    plan = plan_project_registration(repo_root)
    manifest_path = plan.repo_root / MANIFEST_PATH
    prepared = dict(plan.writes)
    manifest = SynthesisManifest.model_validate(YAML(typ="safe").load(prepared[manifest_path])) if manifest_path in prepared else load_yaml(manifest_path)
    manifest = finalize_manifest(
        manifest.model_copy(
            update={
                "schema_version": "3",
                "built_in_only": False,
                "bundle_content_hash": compute_bundle_content_hash(repo_root),
            }
        )
    )
    provenance_path = project_pack_path(plan.repo_root, _PROVENANCE_FILENAME)
    prepared[provenance_path] = (
        "# Project Doctrine Provenance\n\n"
        "This project contains authored doctrine registered by `spec-kitty charter synthesize`.\n"
        "Source YAML remains unchanged. Per-artifact source paths and content hashes are recorded\n"
        "in `.kittify/charter/provenance/` and `.kittify/charter/synthesis-manifest.yaml`.\n"
    )
    # Keep the manifest as the final commit marker, including when registration
    # already prepared an earlier version of that same path.
    prepared.pop(manifest_path, None)
    prepared[manifest_path] = canonical_yaml(manifest.model_dump(mode="python")).decode("utf-8")
    writes = tuple((path, text) for path, text in prepared.items() if not path.exists() or path.read_text(encoding="utf-8") != text)
    if not dry_run:
        commit_project_registration(replace(plan, writes=writes))
    return {
        "result": "dry_run" if dry_run else "success",
        "success": True,
        "mode": "project_direct_write_dry_run" if dry_run else "project_direct_write",
        "adapter": {"id": "project-direct-write", "version": version("spec-kitty-cli")},
        "written_artifacts": [
            {
                "path": artifact.path.relative_to(plan.repo_root).as_posix(),
                "kind": artifact.node.kind.value,
                "slug": artifact.node.urn.split(":", 1)[1],
                "artifact_id": artifact.node.urn.split(":", 1)[1],
            }
            for artifact in plan.artifacts
        ],
        "warnings": list(plan.warnings),
        "files_planned" if dry_run else "files_written": [path.relative_to(plan.repo_root).as_posix() for path, _ in writes],
        "planned_deletes": [],
    }
