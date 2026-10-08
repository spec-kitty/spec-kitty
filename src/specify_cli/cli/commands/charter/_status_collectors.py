"""Status-collection helpers extracted from ``charter status`` (WP06 split).

These helpers are pure data collectors — they build dicts the command body
serialises to JSON or renders to the console. Kept in their own module so
``status.py`` stays under the 500-line WP06 budget.
"""
from __future__ import annotations

from kernel.charter_pack_paths import project_pack_root
from kernel.clock import date
from pathlib import Path
from typing import Any

from specify_cli.task_utils import TaskCliError

from specify_cli.cli.commands.charter._app import (
    CHARTER_YAML_FILENAME,
    METADATA_FILENAME,
)
from specify_cli.cli.commands.charter._common import (
    _display_path,
    _resolve_charter_bundle_path,
    _resolve_charter_path,
)
from specify_cli.cli.commands.charter._synthesis import _collect_evidence_result


def _normalize_last_sync(value: Any) -> str | None:
    """Coerce a metadata timestamp to a JSON-safe ISO string (FR-005).

    ``YAML(typ="safe")`` parses an *unquoted* ISO timestamp in ``metadata.yaml``
    to a ``datetime``/``date`` object, which is not JSON-serializable and
    crashed ``charter status --json`` (``Object of type datetime is not JSON
    serializable``). Normalize to an ISO 8601 string at the collector boundary
    so the payload carries a stable string-typed ``last_sync`` contract.

    ``datetime`` is a subclass of ``date``, so the single ``isinstance`` check
    covers both. Already-string (quoted) timestamps and ``None`` pass through
    unchanged.
    """
    if value is None:
        return None
    if isinstance(value, date):  # covers datetime (date subclass) and date
        return value.isoformat()
    return str(value)


def _collect_charter_sync_status(repo_root: Path) -> dict[str, Any]:
    """Read charter sync status without writing to disk.

    FR-010 / C-IC07: this is a read-only status collector. It MUST NOT call
    ``ensure_charter_bundle_fresh`` (which writes the charter bundle) or
    ``GlossaryEntityPageRenderer.generate_all()`` (which writes entity pages).
    Staleness is determined read-only via ``is_stale``; the canonical root is
    derived read-only as ``repo_root`` (no regeneration required to obtain it).
    """
    try:
        from charter.hasher import is_stale

        # Read-only root derivation: use repo_root directly (no write side-effect).
        # The write commands (charter sync / charter generate) legitimately call
        # ensure_charter_bundle_fresh; the status READ path does not.
        canonical_root = repo_root
        # FR-005: presence keys primarily on charter.yaml (the authoritative
        # bundle) via the CLI sibling resolver, so status survives
        # charter.md deletion (SC-002) -- the old ``_resolve_charter_path``
        # call here used to raise before the charter.yaml-aware staleness
        # logic below ever ran. Fall back to the legacy charter.md gate for
        # a pre-consolidation bundle (no charter.yaml written yet) so this
        # collector keeps reporting available for that shape too; only when
        # NEITHER file exists does the TaskCliError propagate to the
        # outer handler below.
        try:
            output_dir = _resolve_charter_bundle_path(canonical_root).parent
            charter_md_path = output_dir / "charter.md"
            # Header authority: name whichever file is actually present.
            # charter.md is display-only and may be legitimately absent
            # post-consolidation (SC-002); reporting a nonexistent
            # "Charter: .../charter.md" header while charter.yaml (the
            # authoritative bundle) sits right next to it is misleading.
            charter_path = (
                charter_md_path
                if charter_md_path.exists()
                else output_dir / CHARTER_YAML_FILENAME
            )
        except TaskCliError:
            # FR-006 pre-consolidation migration-compat branch (spec Edge
            # Cases + C-001): ``_resolve_charter_bundle_path`` raised because
            # ``charter.yaml`` (the authoritative bundle) does not exist --
            # this is the *only* condition that reaches this branch. Fall
            # back to the legacy ``charter.md``-only resolver so projects
            # created before the ``charter.yaml`` bundle existed keep
            # reporting ``available: True`` instead of erroring out.
            #
            # This shape is explicitly SUPPORTED today and pinned by
            # ``tests/specify_cli/cli/commands/charter/
            # test_status_collectors_legacy_md_shape.py`` (FR-006). Declaring
            # it unsupported (and flipping this branch to a deterministic
            # error path) is a support-scope product decision that MUST be
            # routed through the human-in-charge + issue-matrix (DIR-012 /
            # C-005) -- it is not an implementer-unilateral call. Do not
            # remove or narrow this branch without that recorded decision.
            charter_path = _resolve_charter_path(canonical_root)
            output_dir = charter_path.parent
        metadata_path = output_dir / METADATA_FILENAME
        charter_yaml_path = output_dir / CHARTER_YAML_FILENAME

        # consolidate-charter-bundle (#2773): the charter.md<->metadata.yaml hash
        # staleness model is retired (metadata.yaml folded into charter.yaml).
        # charter.yaml is the authoritative bundle and freshness is reported
        # separately (read-only) via compute_freshness. When metadata.yaml is
        # absent (post-migration), report presence of charter.yaml rather than a
        # misleading perpetual "stale".
        if metadata_path.exists():
            stale, current_hash, stored_hash = is_stale(charter_path, metadata_path)
        else:
            stale, current_hash, stored_hash = (not charter_yaml_path.exists()), "", ""

        files_info: list[dict[str, str | bool | float]] = []
        for filename in [CHARTER_YAML_FILENAME, "charter.md"]:
            file_path = output_dir / filename
            if file_path.exists():
                size = file_path.stat().st_size
                size_kb = size / 1024
                files_info.append(
                    {"name": filename, "exists": True, "size_kb": size_kb}
                )
            else:
                files_info.append(
                    {"name": filename, "exists": False, "size_kb": 0.0}
                )

        library_count = (
            len(list((output_dir / "library").glob("*.md")))
            if (output_dir / "library").exists()
            else 0
        )

        last_sync = None
        if metadata_path.exists():
            from ruamel.yaml import YAML

            yaml = YAML(typ="safe")
            metadata = yaml.load(metadata_path.read_text(encoding="utf-8")) or {}
            if isinstance(metadata, dict):
                last_sync = _normalize_last_sync(
                    metadata.get("timestamp_utc") or metadata.get("extracted_at")
                )

        return {
            "available": True,
            "charter_path": _display_path(charter_path, canonical_root),
            "status": "stale" if stale else "synced",
            "current_hash": current_hash,
            "stored_hash": stored_hash,
            "last_sync": last_sync,
            "library_docs": library_count,
            "files": files_info,
        }
    except TaskCliError as exc:
        return {
            "available": False,
            "error": str(exc),
        }


def _collect_governance_reference_status(repo_root: Path) -> dict[str, Any]:
    """Collect charter-declared supporting governance doc diagnostics."""
    try:
        from charter.activation.governance_references import collect_governance_reference_status
        from charter.activation.sync import load_governance_config

        governance = load_governance_config(repo_root)
        statuses = collect_governance_reference_status(
            repo_root,
            governance.charter.governance_references,
        )
    except Exception as exc:  # noqa: BLE001 - status diagnostics must degrade
        return {
            "available": False,
            "references": [],
            "warnings": [f"Could not inspect governance references: {exc}"],
        }

    warnings = [status.warning for status in statuses if status.warning]
    return {
        "available": True,
        "references": [status.to_dict() for status in statuses],
        "warnings": warnings,
    }


def _collect_generated_input_status(repo_root: Path) -> dict[str, Any]:
    input_root = repo_root / ".kittify" / "charter" / "generated"
    counts = {
        "directive": len(list((input_root / "directives").glob("*.yaml"))),
        "tactic": len(list((input_root / "tactics").glob("*.yaml"))),
        "styleguide": len(list((input_root / "styleguides").glob("*.yaml"))),
    }
    return {
        "path": _display_path(input_root, repo_root),
        "exists": input_root.exists(),
        "counts": counts,
        "total": sum(counts.values()),
    }


def _collect_manifest_status(repo_root: Path) -> tuple[dict[str, Any], Any | None]:
    from charter.activation.synthesizer.manifest import MANIFEST_PATH, load_yaml, verify

    manifest_path = repo_root / MANIFEST_PATH
    doctrine_root = project_pack_root(repo_root)
    provenance_root = repo_root / ".kittify" / "charter" / "provenance"
    from charter.activation.kind_vocabulary import ArtifactKind, PROJECT_KIND_DIRS

    live_artifact_count = sum(
        len(list((doctrine_root / PROJECT_KIND_DIRS[kind]).rglob(kind.glob_pattern)))
        for kind in (ArtifactKind.DIRECTIVE, ArtifactKind.TACTIC, ArtifactKind.STYLEGUIDE,
                     ArtifactKind.PROCEDURE, ArtifactKind.AGENT_PROFILE)
    )
    live_provenance_count = len(list(provenance_root.glob("*.yaml")))

    if not manifest_path.exists():
        state = "partial" if live_artifact_count or live_provenance_count else "missing"
        return (
            {
                "path": _display_path(manifest_path, repo_root),
                "exists": False,
                "state": state,
                "artifact_count": 0,
                "live_artifact_count": live_artifact_count,
                "live_provenance_count": live_provenance_count,
                "run_id": None,
                "created_at": None,
                "adapter_id": None,
                "adapter_version": None,
                "missing_provenance_paths": [],
                "error": None,
            },
            None,
        )

    try:
        manifest = load_yaml(manifest_path)
        try:
            verify(manifest, repo_root)
            state = "valid"
            error = None
        except Exception as exc:  # noqa: BLE001 — manifest verification errors are non-fatal; record as invalid state
            state = "invalid"
            error = str(exc)
    except Exception as exc:  # noqa: BLE001 — manifest YAML load failure is non-fatal; return invalid status dict
        return (
            {
                "path": _display_path(manifest_path, repo_root),
                "exists": True,
                "state": "invalid",
                "artifact_count": 0,
                "live_artifact_count": live_artifact_count,
                "live_provenance_count": live_provenance_count,
                "run_id": None,
                "created_at": None,
                "adapter_id": None,
                "adapter_version": None,
                "missing_provenance_paths": [],
                "error": f"manifest could not be parsed: {exc}",
            },
            None,
        )

    missing_provenance_paths = [
        entry.provenance_path
        for entry in manifest.artifacts
        if not (repo_root / entry.provenance_path).exists()
    ]

    return (
        {
            "path": _display_path(manifest_path, repo_root),
            "exists": True,
            "state": state,
            "artifact_count": len(manifest.artifacts),
            "live_artifact_count": live_artifact_count,
            "live_provenance_count": live_provenance_count,
            "run_id": manifest.run_id,
            "created_at": manifest.created_at,
            "adapter_id": manifest.adapter_id,
            "adapter_version": manifest.adapter_version,
            "missing_provenance_paths": missing_provenance_paths,
            "error": error,
        },
        manifest,
    )


def _collect_provenance_status(
    repo_root: Path,
    manifest: Any | None,
    *,
    include_entries: bool,
) -> dict[str, Any]:
    from charter.activation.synthesizer.provenance import load_yaml as load_provenance

    provenance_root = repo_root / ".kittify" / "charter" / "provenance"
    paths = sorted(provenance_root.glob("*.yaml"))
    warnings: list[str] = []
    entries: list[dict[str, Any]] = []
    visible_paths = {_display_path(path, repo_root) for path in paths}
    manifest_paths = (
        {entry.provenance_path for entry in manifest.artifacts}
        if manifest is not None
        else set()
    )
    corpus_snapshot_ids: set[str] = set()
    adapters: set[str] = set()

    for path in paths:
        rel_path = _display_path(path, repo_root)
        try:
            entry = load_provenance(path)
        except Exception as exc:  # noqa: BLE001 — per-provenance-file failure must not abort the full provenance scan
            warnings.append(f"{rel_path}: {exc}")
            continue

        if entry.corpus_snapshot_id:
            corpus_snapshot_ids.add(entry.corpus_snapshot_id)
        adapters.add(f"{entry.adapter_id}@{entry.adapter_version}")

        if include_entries:
            entries.append(
                {
                    "path": rel_path,
                    "kind": entry.artifact_kind,
                    "slug": entry.artifact_slug,
                    "artifact_urn": entry.artifact_urn,
                    "adapter_id": entry.adapter_id,
                    "adapter_version": entry.adapter_version,
                    "synthesizer_version": getattr(entry, "synthesizer_version", None),  # v2
                    "produced_at": getattr(entry, "produced_at", None),  # v2
                    "corpus_snapshot_id": entry.corpus_snapshot_id,
                    "evidence_bundle_hash": entry.evidence_bundle_hash,
                    "generated_at": entry.generated_at,
                }
            )

    missing_for_manifest = sorted(manifest_paths - visible_paths)
    return {
        "path": _display_path(provenance_root, repo_root),
        "count": len(paths),
        "parsed_count": len(paths) - len(warnings),
        "manifest_artifact_count": len(manifest_paths),
        "missing_for_manifest_count": len(missing_for_manifest),
        "missing_for_manifest": missing_for_manifest,
        "corpus_snapshot_ids": sorted(corpus_snapshot_ids),
        "adapters": sorted(adapters),
        "warnings": warnings,
        "entries": entries,
    }


def _summarize_evidence(repo_root: Path) -> dict[str, Any]:
    evidence_result = _collect_evidence_result(
        repo_root,
        skip_code_evidence=False,
        skip_corpus=False,
    )
    bundle = evidence_result.bundle
    code_summary: dict[str, Any] | None = None
    if bundle.code_signals is not None:
        code_summary = {
            "stack_id": bundle.code_signals.stack_id,
            "primary_language": bundle.code_signals.primary_language,
            "frameworks": list(bundle.code_signals.frameworks),
            "test_frameworks": list(bundle.code_signals.test_frameworks),
            "representative_files_count": len(
                bundle.code_signals.representative_files
            ),
            "representative_files_preview": list(
                bundle.code_signals.representative_files[:5]
            ),
        }

    return {
        "warnings": evidence_result.warnings,
        "code": code_summary,
        "configured_urls": list(bundle.url_list),
        "configured_url_count": len(bundle.url_list),
        "corpus_snapshot_id": (
            bundle.corpus_snapshot.snapshot_id
            if bundle.corpus_snapshot is not None
            else None
        ),
        "corpus_entry_count": (
            len(bundle.corpus_snapshot.entries)
            if bundle.corpus_snapshot is not None
            else 0
        ),
    }


def _collect_synthesis_status(
    repo_root: Path,
    *,
    include_provenance: bool,
) -> dict[str, Any]:
    generated_inputs = _collect_generated_input_status(repo_root)
    manifest_status, manifest = _collect_manifest_status(repo_root)
    provenance_status = _collect_provenance_status(
        repo_root,
        manifest,
        include_entries=include_provenance,
    )
    evidence_summary = _summarize_evidence(repo_root)

    if (
        manifest_status["state"] == "valid"
        and provenance_status["missing_for_manifest_count"] == 0
        and not provenance_status["warnings"]
    ):
        generation_state = "promoted"
    elif (
        manifest_status["state"] in {"invalid", "partial"}
        or provenance_status["missing_for_manifest_count"] > 0
        or provenance_status["warnings"]
    ):
        generation_state = "needs_attention"
    elif generated_inputs["total"] > 0:
        generation_state = "ready_for_validation"
    else:
        generation_state = "not_started"

    return {
        "generation_state": generation_state,
        "generated_inputs": generated_inputs,
        "manifest": manifest_status,
        "provenance": provenance_status,
        "evidence": evidence_summary,
    }


def _collect_org_layer_status(repo_root: Path) -> dict[str, Any]:
    """Collect org-layer state for ``charter status`` (FR-002).

    Returns a structured dict describing the configured organisation-tier
    DRG packs, their fetched/missing state, node/edge counts, any collision
    warnings surfaced by ``merge_three_layers``, and — because this collector
    merges the COMPLETE graph — any org edge endpoint that binds to nothing.

    Dangling endpoints land in the existing ``errors`` array rather than a
    dedicated key. ``doctor doctrine``'s collector keeps a separate
    ``dangling_endpoints`` list because its renderer reads it; nothing renders
    such a key here, and an unread payload slot is the inert-schema-slot defect
    this mission ratchets elsewhere. ``status`` already prints every ``errors``
    entry, so one channel serves both the human and the JSON view.

    When no packs are configured, returns ``{"packs": [], "has_built_in": True}``.
    The caller (``status``) always emits this key in JSON output so operators
    and ATDD assertions can rely on its presence.

    NFR-001: this function is always called but the packs list is empty
    for repos without org pack configuration — no spurious section added.

    Per the charter layer architectural boundary (kernel <- doctrine <-
    charter <- specify_cli), we use ``charter.activation.drg_activation.load_org_drg`` directly
    rather than the ``specify_cli`` config path.  The caller may also pass
    the repo root to ``charter.offering.drg.org_pack_config`` for richer pack metadata;
    this implementation stays purely charter-layer.
    """
    from charter.drg import (
        OrgDRGConflictError,
        OrgPackMissingError,
        load_built_in_graph,
        validate_dangling_references,
    )
    from charter.activation.drg_activation import (
        load_org_drg,
        merge_three_layers,
    )

    result: dict[str, Any] = {
        "has_built_in": True,  # built-in layer is always present
        "packs": [],
        "collision_warnings": [],
        "errors": [],
    }

    try:
        fragments = load_org_drg(repo_root)
    except OrgPackMissingError as exc:
        result["errors"].append(str(exc))
        return result
    except Exception as exc:  # noqa: BLE001 — best-effort; status must not crash
        result["errors"].append(f"org-DRG load error: {exc}")
        return result

    for frag in fragments:
        pack_entry: dict[str, Any] = {
            "name": frag.pack_name,
            "source_kind": frag.source_kind,
            "source_ref": frag.source_ref,
            "layer_index": frag.layer_index,
            "fetched": True,
            "node_count": len(frag.nodes),
            "edge_count": len(frag.edges),
        }
        result["packs"].append(pack_entry)

    if not fragments:
        return result

    # Run merge to surface collision warnings AND graph completeness. The merge
    # is the only statement in the try: the completeness check below needs an
    # assembled graph, and leaving it inside meant a hard-fail raise aborted the
    # block before it ran — so a pack with BOTH a refused endpoint and a dangling
    # one reported strictly fewer findings than the dangling one alone.
    merged = None
    try:
        built_in = load_built_in_graph()
        merged = merge_three_layers(
            built_in=built_in, org_fragments=fragments, project=None
        )
    except OrgDRGConflictError as exc:
        # The typed records go to ``collision_warnings``; the subset that made
        # the merge REFUSE also goes to ``errors``. A conflict resolved by
        # precedence is a warning, but a conflict the merge refused to resolve
        # means there is no merged graph at all — reporting that as an advisory
        # is how ``charter status`` came to print a clean org layer for a pack
        # ``charter lint`` rejects outright. The partition is read from
        # ``OrgDRGConflictError`` so the three collectors cannot drift.
        for conflict in exc.conflicts:
            result["collision_warnings"].append(
                {
                    "kind": conflict.kind,
                    "target_id": conflict.target_id,
                    "conflicting_layers": conflict.conflicting_layers,
                    "resolution": conflict.resolution_applied,
                }
            )
        result["errors"].extend(exc.hard_failure_messages)
    except Exception as exc:  # noqa: BLE001 — status must not crash on a bad pack
        # A check that could not RUN is not a check that PASSED. This handler
        # used to be a bare ``pass``, so a crashed merge left ``errors: []`` —
        # indistinguishable from a verified-clean org layer. Report it on the
        # same channel the load failure above already uses (``status`` renders
        # every entry and never gates on it), so the read degrades loudly.
        result["errors"].append(f"org-layer merge check failed: {exc}")

    if merged is None:
        # No graph to inspect; ``errors`` already says why.
        return result

    try:
        # This merge is the real shipped built-in against every configured pack
        # — the COMPLETE graph — which is exactly the predicate under which
        # ``validate_dangling_references`` may escalate a dangling endpoint from
        # the merge's WARNING to a reported error (see its docstring; ``charter
        # lint`` merges against an intentionally EMPTY built-in and must not).
        # Without this, ``charter status --json`` returned ``org_layer.errors:
        # []`` for a graph whose edge named nothing — a machine-readable clean
        # bill for an unclean graph, on the very array built to carry the
        # finding, while ``doctor doctrine`` reported it from identical inputs.
        result["errors"].extend(validate_dangling_references(merged))
    except Exception as exc:  # noqa: BLE001 — status must not crash on a bad pack
        # Attributed separately from the merge above: the merge succeeded, so
        # naming it here would point the operator at the wrong artefact.
        result["errors"].append(f"org-layer completeness check failed: {exc}")

    return result
