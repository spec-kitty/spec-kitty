"""Pack assembly for org doctrine packs.

Merges multiple input packs into a single distributable pack directory.

Public surface:

* :class:`ConflictItem`
* :class:`AssemblyResult`
* :func:`assemble_pack`
* :func:`render_assembly_result`

Conflict semantics:

* Artifact-ID conflict: same ``id`` declared by two input packs in the same
  artifact-type directory.
* DRG-edge conflict: same ``(source, target, relation)`` declared by two
  input packs' graph fragments.
* Sanction conflict: same URN listed in two input packs' pack-root
  ``replaceable-builtins.yaml`` with different reasons (FR-015). The assembled
  pack carries the union of the inputs' sanctions.

When conflicts are present and ``force=False``, the assembler refuses to
write anything and returns ``ok=False``.  With ``force=True``, last-pack-
wins for artifact IDs (an advisory is recorded for each override) and
duplicate DRG edges are dropped (kept once); the same holds for a sanction
reason conflict (last pack's reason wins).
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.offering.drg.override_policy import (
    PACK_POLICY_FILENAME,
    OverridePolicyError,
    ReplaceableBuiltin,
    dump_pack_sanction,
    load_pack_sanction,
    pack_sanction_present,
)

from .pack_validator import validate_pack
from .snapshot import write_pack_manifest
from .sources.protocol import FetchResult

if TYPE_CHECKING:
    # Type-checking-only: this module has no static top-level runtime
    # doctrine import (see ``_copy_drg_fragments``'s dynamic
    # ``DRGLoadError``/``load_graph`` import below) so it stays importable
    # when the doctrine package is stripped from a test environment. A
    # ``TYPE_CHECKING``-guarded import never executes at runtime, so it does
    # not reintroduce that hard dependency.
    from charter.offering.drg.models import DRGGraph

__all__ = [
    "ConflictItem",
    "AssemblyResult",
    "assemble_pack",
    "render_assembly_result",
]


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass
class ConflictItem:
    """A single artifact-ID or DRG-edge collision between input packs."""

    artifact_type: str
    artifact_id: str
    conflicting_packs: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": self.artifact_type,
            "artifact_id": self.artifact_id,
            "conflicting_packs": list(self.conflicting_packs),
        }


@dataclass
class AssemblyResult:
    """Aggregate outcome of an assemble operation."""

    ok: bool
    artifacts_written: int = 0
    conflicts: list[ConflictItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "artifacts_written": self.artifacts_written,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "errors": list(self.errors),
        }


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


_ARTIFACT_DIRS_AND_GLOBS: dict[str, str] = {
    "directives": "*.directive.yaml",
    "tactics": "*.tactic.yaml",
    "styleguides": "*.styleguide.yaml",
    "toolguides": "*.toolguide.yaml",
    "paradigms": "*.paradigm.yaml",
    "procedures": "*.procedure.yaml",
    "agent_profiles": "*.agent.yaml",
    "mission_step_contracts": "*.step-contract.yaml",
}


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------


def _yaml() -> YAML:
    return YAML(typ="safe")


def _read_id(path: Path) -> str | None:
    """Return the ``id`` field of a YAML artifact file, or ``None`` on failure."""
    try:
        data = _yaml().load(path)
    except (YAMLError, OSError):
        return None
    if isinstance(data, dict):
        raw_id = data.get("id")
        if isinstance(raw_id, str):
            return raw_id
    return None


def _scan_artifacts(pack_dir: Path, plural: str, glob: str) -> list[Path]:
    type_dir = pack_dir / plural
    if not type_dir.is_dir():
        return []
    if plural == "styleguides":
        return sorted(type_dir.rglob(glob))
    return sorted(type_dir.glob(glob))


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


def _detect_artifact_conflicts(
    input_packs: list[Path],
) -> tuple[
    list[ConflictItem],
    dict[str, dict[str, tuple[Path, Path]]],  # plural -> id -> (pack_dir, src_file)
]:
    """Scan all input packs and report ID collisions.

    Returns ``(conflicts, last_owner)`` where ``last_owner`` records, for each
    plural/id, the *last* pack that declared it (used by ``force=True``
    last-pack-wins resolution).
    """
    conflicts: list[ConflictItem] = []
    # plural -> id -> list of (pack_name, source_file)
    seen: dict[str, dict[str, list[tuple[str, Path]]]] = {}
    last_owner: dict[str, dict[str, tuple[Path, Path]]] = {}

    for pack in input_packs:
        pack_name = pack.name
        for plural, glob in _ARTIFACT_DIRS_AND_GLOBS.items():
            for artifact_file in _scan_artifacts(pack, plural, glob):
                artifact_id = _read_id(artifact_file)
                if artifact_id is None:
                    continue
                seen.setdefault(plural, {}).setdefault(artifact_id, []).append(
                    (pack_name, artifact_file)
                )
                last_owner.setdefault(plural, {})[artifact_id] = (pack, artifact_file)

    for plural, id_map in seen.items():
        for artifact_id, occurrences in sorted(id_map.items()):
            if len(occurrences) > 1:
                conflicts.append(
                    ConflictItem(
                        artifact_type=plural,
                        artifact_id=artifact_id,
                        conflicting_packs=[name for name, _ in occurrences],
                    )
                )

    return conflicts, last_owner


def _detect_drg_conflicts(
    input_packs: list[Path],
) -> tuple[list[ConflictItem], dict[Path, list[Path]]]:
    """Scan ``drg/`` directories for duplicate edges across packs.

    Returns ``(conflicts, fragments_by_pack)``.
    """
    conflicts: list[ConflictItem] = []
    fragments_by_pack: dict[Path, list[Path]] = {}
    # edge_key -> list of pack names
    edge_owners: dict[tuple[str, str, str], list[str]] = {}

    try:
        from charter.offering.drg.loader import DRGLoadError, load_graph
    except ModuleNotFoundError:  # pragma: no cover
        return conflicts, fragments_by_pack

    for pack in input_packs:
        drg_dir = pack / "drg"
        if not drg_dir.is_dir():
            continue
        fragments = sorted(drg_dir.glob("*.graph.yaml"))
        fragments_by_pack[pack] = fragments
        for fragment in fragments:
            try:
                graph = load_graph(fragment)
            except DRGLoadError:
                continue
            for edge in graph.edges:
                key = (edge.source, edge.target, edge.relation.value)
                edge_owners.setdefault(key, []).append(pack.name)

    for key, owners in edge_owners.items():
        unique = list(dict.fromkeys(owners))
        if len(unique) > 1:
            source, target, relation = key
            conflicts.append(
                ConflictItem(
                    artifact_type="drg",
                    artifact_id=f"{source} -[{relation}]-> {target}",
                    conflicting_packs=unique,
                )
            )

    return conflicts, fragments_by_pack


#: ``ConflictItem.artifact_type`` used for a sanction reason conflict.
_SANCTION_CONFLICT_TYPE = "replaceable_builtins"


def _detect_sanction_conflicts(
    input_packs: list[Path],
) -> tuple[list[ConflictItem], dict[str, str] | None, list[str]]:
    """Union the input packs' sanction files and report reason conflicts (FR-015).

    Returns ``(conflicts, merged, errors)``. ``merged`` maps URN to reason (the
    last pack's reason wins) and is ``None`` when no input ships a sanction file.
    A malformed input yields an error and no merge, so the caller aborts before
    any write. Parsing is delegated to ``load_pack_sanction``.
    """
    merged: dict[str, str] = {}
    owners: dict[str, list[tuple[str, str]]] = {}
    errors: list[str] = []
    any_file = False
    for pack in input_packs:
        if not pack_sanction_present(pack):
            continue
        any_file = True
        try:
            policy = load_pack_sanction(pack.name, pack)
        except OverridePolicyError as exc:
            errors.append(str(exc))
            continue
        for entry in policy.entries:
            merged[entry.urn] = entry.reason
            owners.setdefault(entry.urn, []).append((pack.name, entry.reason))
    if errors:
        return [], None, errors
    conflicts = [
        ConflictItem(
            artifact_type=_SANCTION_CONFLICT_TYPE,
            artifact_id=urn,
            conflicting_packs=[name for name, _ in declared],
        )
        for urn, declared in sorted(owners.items())
        if len({reason for _, reason in declared}) > 1
    ]
    return conflicts, (merged if any_file else None), []


def _write_pack_sanctions(output_dir: Path, merged: dict[str, str] | None) -> None:
    """Write the unioned sanction to ``<output>/replaceable-builtins.yaml``."""
    if merged is None:
        return
    entries = [ReplaceableBuiltin(urn=urn, reason=merged[urn]) for urn in sorted(merged)]
    (output_dir / PACK_POLICY_FILENAME).write_text(dump_pack_sanction(entries), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def assemble_pack(
    input_packs: list[Path],
    output_dir: Path,
    *,
    force: bool = False,
    conflicts_out: Path | None = None,
) -> AssemblyResult:
    """Merge *input_packs* into *output_dir*.

    Args:
        input_packs: Ordered list of pack directories to merge. Later packs
            win for last-pack-wins (only relevant when ``force=True``).
        output_dir: Destination directory. Must be empty unless ``force=True``.
        force: When ``True``, ID conflicts are resolved by last-pack-wins
            (advisory) and duplicate DRG edges are dropped silently.
        conflicts_out: When given, write the conflict list as JSON to this
            path *before* returning (even on success — the list is just
            empty in that case).

    Returns:
        An :class:`AssemblyResult` summarising the operation.
    """
    if not input_packs:
        result = AssemblyResult(
            ok=False, errors=["no input packs provided"]
        )
        _maybe_write_conflicts(conflicts_out, result)
        return result

    # Validate every input pack exists.
    missing = [str(p) for p in input_packs if not p.is_dir()]
    if missing:
        result = AssemblyResult(
            ok=False,
            errors=[f"input pack not found: {m}" for m in missing],
        )
        _maybe_write_conflicts(conflicts_out, result)
        return result

    artifact_conflicts, last_owner = _detect_artifact_conflicts(input_packs)
    drg_conflicts, fragments_by_pack = _detect_drg_conflicts(input_packs)
    sanction_conflicts, merged_sanctions, sanction_errors = _detect_sanction_conflicts(
        input_packs
    )
    if sanction_errors:
        result = AssemblyResult(ok=False, errors=sanction_errors)
        _maybe_write_conflicts(conflicts_out, result)
        return result
    all_conflicts = artifact_conflicts + drg_conflicts + sanction_conflicts

    if all_conflicts and not force:
        result = AssemblyResult(ok=False, conflicts=all_conflicts)
        _maybe_write_conflicts(conflicts_out, result)
        return result

    # Prepare output directory.
    if output_dir.exists():
        if any(output_dir.iterdir()):
            if not force:
                result = AssemblyResult(
                    ok=False,
                    errors=[
                        f"output directory {output_dir} exists and is non-empty; "
                        "use --force to overwrite"
                    ],
                )
                _maybe_write_conflicts(conflicts_out, result)
                return result
            if not _has_recognisable_pack_manifest(output_dir):
                result = AssemblyResult(
                    ok=False,
                    errors=[
                        f"refusing to delete non-pack output directory {output_dir}; "
                        "with --force, the directory must contain a recognisable "
                        "pack-manifest.yaml"
                    ],
                )
                _maybe_write_conflicts(conflicts_out, result)
                return result
            shutil.rmtree(output_dir)
            output_dir.mkdir(parents=True)
    else:
        output_dir.mkdir(parents=True)

    # Copy artifact files.
    artifacts_written = _copy_artifacts(
        input_packs, output_dir, last_owner, force=force
    )

    # Copy DRG fragments (re-numbered to preserve global alphabetical order).
    drg_written = _copy_drg_fragments(fragments_by_pack, output_dir, force=force)
    artifacts_written += drg_written

    # Merge org-charter.yaml (T045 — best-effort).
    _merge_org_charters_to_output(input_packs, output_dir)

    # FR-015: carry the union of the inputs' sanctions (before validation).
    _write_pack_sanctions(output_dir, merged_sanctions)

    # Validate assembled output.
    # The assembler never writes a pack-root *.graph.yaml (_copy_drg_fragments
    # only writes output_dir/drg/*.graph.yaml) — this carve-out is structural,
    # unconditional, and does not depend on any caller's output shape.
    validation = validate_pack(output_dir, check_drg_root=False)
    if not validation.ok:
        # Roll back partial output.
        shutil.rmtree(output_dir, ignore_errors=True)
        result = AssemblyResult(
            ok=False,
            artifacts_written=0,
            conflicts=all_conflicts if force else [],
            errors=[
                "assembled pack failed validation: "
                + "; ".join(issue.message for issue in validation.errors[:3])
                + ("; ..." if len(validation.errors) > 3 else "")
            ],
        )
        _maybe_write_conflicts(conflicts_out, result)
        return result

    result = AssemblyResult(
        ok=True,
        artifacts_written=artifacts_written,
        conflicts=all_conflicts if force else [],
    )
    write_pack_manifest(
        output_dir,
        FetchResult(
            ok=True,
            artifacts_written=artifacts_written,
            pack_version=None,
            errors=[],
        ),
        source_url=",".join(str(p) for p in input_packs),
        source_type="assemble",
    )
    _maybe_write_conflicts(conflicts_out, result)
    return result


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _read_authored_pack_version(pack_root: Path) -> str | None:
    """Read ``pack_version`` from an authored ``pack.yaml`` sibling, if any.

    IC-06 / FR-008 (pack-metadata-manifest-unification-01M052PT, WP04):
    the built-in pack's ``pack_version`` is authored in ``pack.yaml`` and its
    generator never writes it to the generated ``pack-manifest.yaml``.
    Fetched/org packs have no ``pack.yaml`` (yet — backfill is deferred, Q2)
    and keep ``pack_version`` as generated provenance. Returns ``None`` when
    no authored descriptor exists, it fails to parse, or it carries no
    ``pack_version`` field — callers fall back to the generated value
    (derive-else-fallback).
    """
    descriptor = pack_root / "pack.yaml"
    if not descriptor.is_file():
        return None
    try:
        data = _yaml().load(descriptor)
    except (YAMLError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    version = data.get("pack_version")
    return str(version) if version else None


def _has_recognisable_pack_manifest(output_dir: Path) -> bool:
    manifest = output_dir / "pack-manifest.yaml"
    if not manifest.is_file():
        return False
    try:
        payload = _yaml().load(manifest)
    except (YAMLError, OSError):
        return False
    if not isinstance(payload, dict):
        return False
    required_keys = {
        "artifact_counts",
        "fetched_at",
        "source_type",
        "source_url",
    }
    if not required_keys.issubset(payload):
        return False
    if not isinstance(payload.get("artifact_counts"), dict):
        return False
    # pack_version is derive-else-fallback (IC-06/FR-008): an authored
    # pack.yaml sibling (the built-in split) satisfies recognisability even
    # when the generated manifest omits the key; fetched/org packs still
    # carry it on the generated file (snapshot.py's writer is unchanged), so
    # this is additive — it never makes a previously-recognisable manifest
    # unrecognisable.
    if "pack_version" not in payload and _read_authored_pack_version(output_dir) is None:
        return False
    return payload.get("source_type") in {
        "assemble",
        "git",
        "https",
        "artifactory",
        "api",
    }


def _copy_artifacts(
    input_packs: list[Path],
    output_dir: Path,
    last_owner: dict[str, dict[str, tuple[Path, Path]]],
    *,
    force: bool,
) -> int:
    """Copy artifact files from input packs into ``output_dir``.

    When ``force=True``, only the last-pack-wins source file is copied for
    any given ``(plural, id)`` pair.  Otherwise every input pack's files are
    copied (callers guarantee no conflicts in this branch).
    """
    count = 0
    if force:
        for plural, id_to_owner in last_owner.items():
            type_out = output_dir / plural
            for _artifact_id, (_pack, source_file) in id_to_owner.items():
                # Preserve relative path under styleguides/ to keep nesting.
                if plural == "styleguides":
                    try:
                        rel = source_file.relative_to(_pack / plural)
                    except ValueError:
                        rel = Path(source_file.name)
                    dest = type_out / rel
                else:
                    dest = type_out / source_file.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, dest)
                count += 1
        return count

    # No-force path: copy every file from every input pack in order.
    for pack in input_packs:
        for plural, glob in _ARTIFACT_DIRS_AND_GLOBS.items():
            for artifact_file in _scan_artifacts(pack, plural, glob):
                type_out = output_dir / plural
                if plural == "styleguides":
                    try:
                        rel = artifact_file.relative_to(pack / plural)
                    except ValueError:
                        rel = Path(artifact_file.name)
                    dest = type_out / rel
                else:
                    dest = type_out / artifact_file.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(artifact_file, dest)
                count += 1
    return count


def _document_dict(graph: DRGGraph) -> dict[str, Any]:
    """Serialise a whole ``DRGGraph`` document via the canonical derived writer.

    T020/T021 (#3075): standalone/addressable wrapper around
    ``graph_document_to_dict``, registered as this module's ``DocumentWriter``
    in ``specify_cli.drg_writers.registry`` and used by the force-dedup path
    in :func:`_copy_drg_fragments` below. Replaces that path's old raw
    ``n.model_dump()`` / ``e.model_dump()`` calls, which bypassed
    ``model_to_graph_dict`` entirely and so emitted ``provenance`` (which the
    canonical path withholds via ``FIELDS_WITHHELD_FROM_GRAPH_OUTPUT``) and
    skipped the omit-when-empty rule.

    Imports ``graph_document_to_dict`` lazily so this module keeps its
    existing graceful-degradation shape (importable when the doctrine
    package is stripped from a test environment) -- mirrors
    ``_copy_drg_fragments``'s own dynamic ``DRGLoadError``/``load_graph``
    import.
    """
    from charter.offering.drg.migration.extractor import graph_document_to_dict

    document: dict[str, Any] = graph_document_to_dict(graph)
    return document


def _copy_drg_fragments(
    fragments_by_pack: dict[Path, list[Path]],
    output_dir: Path,
    *,
    force: bool,
) -> int:
    """Copy DRG fragments to ``output_dir/drg/`` with renumbered filenames.

    Each fragment becomes ``<seq>-<pack>-<orig-name>`` so global alphabetical
    order across packs is preserved.  Returns the count of fragments written.
    """
    if not fragments_by_pack:
        return 0
    drg_out = output_dir / "drg"
    drg_out.mkdir(parents=True, exist_ok=True)
    count = 0
    seq = 0
    seen_edges: set[tuple[str, str, str]] = set()
    load_graph_fn: Callable[[Path], Any] | None = None
    drg_load_error: type[Exception] = Exception

    if force:
        # Drop duplicate edges across packs; preserve unique ones in order.
        try:
            from charter.offering.drg.loader import DRGLoadError, load_graph
        except ModuleNotFoundError:
            pass
        else:
            load_graph_fn = load_graph
            drg_load_error = DRGLoadError

    for pack, fragments in fragments_by_pack.items():
        for fragment in fragments:
            seq += 1
            dest_name = f"{seq:03d}-{pack.name}-{fragment.name}"
            dest = drg_out / dest_name
            if force and load_graph_fn is not None:
                try:
                    graph = load_graph_fn(fragment)
                except drg_load_error:
                    shutil.copy2(fragment, dest)
                    count += 1
                    continue
                # Drop duplicate edges.
                kept_edges = []
                for edge in graph.edges:
                    key = (edge.source, edge.target, edge.relation.value)
                    if key in seen_edges:
                        continue
                    seen_edges.add(key)
                    kept_edges.append(edge)
                # Re-emit pruned fragment as YAML via the canonical document
                # serialiser (T020, #2977/#3075) instead of the raw
                # .model_dump() this used to call directly on each node/edge.
                pruned_graph = graph.model_copy(update={"edges": kept_edges})
                pruned = _document_dict(pruned_graph)
                import yaml as pyyaml

                dest.write_text(
                    pyyaml.safe_dump(pruned, sort_keys=False), encoding="utf-8"
                )
            else:
                shutil.copy2(fragment, dest)
            count += 1
    return count


def _merge_org_charters_to_output(
    input_packs: list[Path], output_dir: Path
) -> None:
    """Merge ``org-charter.yaml`` from input packs into ``output_dir``.

    Skipped silently if no input pack provides one or if the OrgCharterPolicy
    model is not yet shipped (WP09).  Merge semantics:

    * ``interview_defaults``: dict update (last pack wins on key collision).
    * ``required_directives``: union, deduplicated, order preserved.
    * ``governance_policies``: concatenated, deduplicated by
      ``(field, value)``.
    """
    charter_files = [p / "org-charter.yaml" for p in input_packs]
    charter_files = [f for f in charter_files if f.exists()]
    if not charter_files:
        return

    # Lazy import — model may not exist yet.
    try:
        from specify_cli.doctrine.org_charter import (
            OrgCharterPolicy,
        )
    except ModuleNotFoundError:
        # Concatenate raw YAMLs naively: copy the *last* pack's file as a
        # best-effort placeholder.  WP09's full merge will replace this.
        shutil.copy2(charter_files[-1], output_dir / "org-charter.yaml")
        return
    except ImportError:  # pragma: no cover
        return

    merged = _merge_org_charters(charter_files, OrgCharterPolicy)
    if merged is None:
        return
    import yaml as pyyaml

    out_path = output_dir / "org-charter.yaml"
    out_path.write_text(
        pyyaml.safe_dump(merged.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )


def _merge_org_charters(
    charter_files: list[Path],
    policy_cls: type[Any],
) -> Any | None:
    """Apply the merge semantics described above; returns a policy instance."""
    interview_defaults: dict[str, Any] = {}
    required_directives: list[str] = []
    governance_policies: list[dict[str, Any]] = []
    schema_version: str | None = None

    for path in charter_files:
        try:
            data = _yaml().load(path)
        except (YAMLError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        schema_version = data.get("schema_version", schema_version)
        interview_defaults.update(data.get("interview_defaults") or {})
        for rd in data.get("required_directives") or []:
            if rd not in required_directives:
                required_directives.append(rd)
        for gp in data.get("governance_policies") or []:
            if isinstance(gp, dict):
                governance_policies.append(gp)

    # Dedupe governance_policies by (field, value).
    seen: set[tuple[Any, Any]] = set()
    deduped: list[dict[str, Any]] = []
    for gp in governance_policies:
        key = (gp.get("field"), gp.get("value"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(gp)

    payload: dict[str, Any] = {
        "schema_version": schema_version or "1.0",
        "interview_defaults": interview_defaults,
        "required_directives": required_directives,
        "governance_policies": deduped,
    }
    try:
        return policy_cls.model_validate(payload)
    except Exception:  # pragma: no cover - validation error returns None
        return None


def _maybe_write_conflicts(
    conflicts_out: Path | None, result: AssemblyResult
) -> None:
    """Write ``result.conflicts`` to *conflicts_out* as JSON when requested."""
    if conflicts_out is None:
        return
    conflicts_out.parent.mkdir(parents=True, exist_ok=True)
    conflicts_out.write_text(
        json.dumps(
            [c.to_dict() for c in result.conflicts],
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_assembly_result(
    result: AssemblyResult,
    *,
    output_dir: Path,
    input_packs: list[Path],
    json_output: bool = False,
) -> None:
    """Render *result* to stdout."""
    if json_output:
        print(json.dumps(result.to_dict(), sort_keys=True))
        return

    if result.ok:
        print(
            f"Assembled {len(input_packs)} pack"
            f"{'s' if len(input_packs) != 1 else ''} → "
            f"{output_dir}/ ({result.artifacts_written} artifacts)"
        )
        for conflict in result.conflicts:
            print(
                f"⚠ advisory: last-pack-wins for {conflict.artifact_type}/"
                f"{conflict.artifact_id} from "
                f"{conflict.conflicting_packs[-1]}"
            )
        return

    for conflict in result.conflicts:
        names = " and ".join(repr(n) for n in conflict.conflicting_packs)
        print(
            f"✗ Conflict: artifact id {conflict.artifact_id!r} "
            f"({conflict.artifact_type}) declared in {names}"
        )
    for err in result.errors:
        print(f"✗ {err}")
    if result.conflicts:
        print(
            "Resolve conflicts and re-run, or use --force to let last pack win."
        )
