"""JSON-builder privates for ``charter context --json`` (WP06 T029, #2532).

Relocated verbatim from ``charter.activation.context`` (single-owner, no-net-growth for
that file). Backs :func:`~charter.activation.context.build_charter_context_json`'s
``project_charter`` / ``all_directives`` blocks: the canonical bundle-root
resolver, the relative-path formatter, the project-local charter metadata
reader, and the project directive enumerator (local charter + resolver
catalog fallback).

Cycle note: :func:`_maybe_build_doctrine_service` calls
:func:`~charter.activation.doctrine_service_builder._build_doctrine_service` via a
function-local ``from charter.activation.context import _build_doctrine_service``
rather than a direct import of ``charter.activation.doctrine_service_builder`` — several
existing tests (``tests/charter/test_context.py::test_project_directive_entries_fallbacks``)
patch only ``charter.activation.context._build_doctrine_service`` and expect
``_project_directive_entries`` (re-exported from this module) to observe it;
routing through ``charter.activation.context`` keeps that single patch-point contract.
:func:`_project_charter_json_block` similarly resolves ``YAML`` via a
function-local import from ``charter.activation.context`` — ``tests/charter/test_context.py``
patches ``charter.activation.context.YAML`` directly.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import charter.offering.service as _doctrine_service_module

from ruamel.yaml.error import YAMLError

from charter.activation import progressive_disclosure as _pd
from charter.bundle import CHARTER_MD, CHARTER_YAML
from charter.activation.context_state import KITTIFY_DIRNAME
from charter.activation.schemas import DirectivesConfig

# ``_load_project_directives`` / ``_relative_json_path`` de-exported after the
# context.py re-export shim retirement (doctrine-built-in-seam-consolidation
# WP06): no external ``src/`` importer remains. Both stay module-internal
# helpers used by the functions below.
__all__ = [
    "_EMPTY_ORG_CHARTER",
    "_bundle_root_for_json",
    "_project_charter_json_block",
    "_project_directive_entries",
    "_project_directive_entries_with_source",
]


def _bundle_root_for_json(repo_root: Path) -> Path:
    """Return the canonical charter bundle root, falling back to *repo_root*."""
    try:
        from charter.activation.sync import ensure_charter_bundle_fresh

        refresh_result = ensure_charter_bundle_fresh(repo_root)
    except Exception:  # noqa: BLE001 - JSON metadata is best-effort
        return repo_root
    if refresh_result is not None and refresh_result.canonical_root is not None:
        return Path(refresh_result.canonical_root)
    return repo_root


def _relative_json_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _project_charter_json_block(repo_root: Path) -> dict[str, object]:
    """Describe the project-local charter loaded by the context renderer.

    FR-006 (charter-pack-usage-journey WP03): ``present``/``path`` key on the
    **authoritative** ``charter.yaml`` bundle (the primary signal, surviving
    ``charter.md`` deletion -- SC-002). ``charter.md``'s own presence/path
    become the secondary display fields ``charter_md_present`` /
    ``charter_md_path`` -- it is a display companion, not the governance
    authority. This is a deliberate ``charter context --json``
    ``project_charter.present`` contract flip; see the second present-signal
    site kept consistent with this producer at
    ``specify_cli/cli/commands/charter/context.py:158`` (cross-ref #2787).
    """
    bundle_root = _bundle_root_for_json(repo_root)
    charter_dir = bundle_root / KITTIFY_DIRNAME / "charter"
    charter_yaml_path = bundle_root / CHARTER_YAML
    charter_md_path = bundle_root / CHARTER_MD
    metadata_path = charter_dir / "metadata.yaml"

    block: dict[str, object] = {
        "present": charter_yaml_path.exists(),
        "path": _relative_json_path(charter_yaml_path, bundle_root),
        "charter_md_present": charter_md_path.exists(),
        "charter_md_path": _relative_json_path(charter_md_path, bundle_root),
    }
    if not charter_yaml_path.exists():
        return block

    block["bytes"] = charter_yaml_path.stat().st_size
    if not metadata_path.exists():
        return block

    # Patch seam, see module docstring.
    from charter.activation.context import YAML  # noqa: PLC0415

    try:
        data = YAML(typ="safe").load(metadata_path.read_text(encoding="utf-8")) or {}
    except (OSError, YAMLError, ValueError):
        return block
    if not isinstance(data, dict):
        return block

    charter_hash = data.get("charter_hash")
    if isinstance(charter_hash, str) and charter_hash:
        block["hash"] = charter_hash
    source_path = data.get("source_path")
    if isinstance(source_path, str) and source_path:
        block["source_path"] = source_path
    bundle_schema_version = data.get("bundle_schema_version")
    if isinstance(bundle_schema_version, int):
        block["bundle_schema_version"] = bundle_schema_version
    schema_version = data.get("schema_version")
    if isinstance(schema_version, str) and schema_version:
        block["schema_version"] = schema_version
    return block


def _load_project_directives_with_source(
    repo_root: Path,
    load_directives_config: Callable[[Path], DirectivesConfig],
) -> tuple[dict[str, object], list[str], str | None]:
    """Resolve project directive IDs **and** the resolution-level
    ``directives_source`` provenance from a *single* governance resolution.

    ``directives_source`` is ``GovernanceResolution.metadata["directives_source"]``
    (e.g. ``"catalog_fallback+project_local"``) — the branch that resolved the
    directive set. It is distinct from the per-entry ``source`` each directive
    entry carries (``"project"``/``"builtin"``/``"org"`` artifact origin); the
    two answer different questions. Returns ``None`` for the source on any
    resolver failure — provenance-unavailable is itself an operator signal, and
    the broad-except degrade sites stay out of scope here (C-002).
    """
    try:
        directives_cfg = load_directives_config(repo_root)
    except Exception:  # noqa: BLE001 - fall through to resolver/catalog path
        local_by_id: dict[str, object] = {}
        directive_ids: list[str] = []
    else:
        local_by_id = {directive.id: directive for directive in directives_cfg.directives}
        directive_ids = [directive.id for directive in directives_cfg.directives]

    try:
        from charter.activation.resolver import resolve_project_governance

        resolution = resolve_project_governance(repo_root)
    except Exception:  # noqa: BLE001 - keep any directly-loaded directive IDs
        return local_by_id, list(dict.fromkeys(directive_ids)), None
    # ``metadata`` is always present on a real ``GovernanceResolution``; the
    # ``getattr``/``isinstance`` guard only tolerates duck-typed resolver stubs
    # in existing seam tests that omit it.
    metadata = getattr(resolution, "metadata", None)
    directives_source = metadata.get("directives_source") if isinstance(metadata, dict) else None
    return (
        local_by_id,
        list(dict.fromkeys(list(resolution.directives) + directive_ids)),
        directives_source,
    )


def _load_project_directives(
    repo_root: Path,
    load_directives_config: Callable[[Path], DirectivesConfig],
) -> tuple[dict[str, object], list[str]]:
    """Backward-compatible 2-tuple wrapper over
    :func:`_load_project_directives_with_source`.

    Existing seam tests pin this arity; the resolution-``directives_source``
    variant threads provenance to the JSON payload builder without a second
    ``resolve_project_governance`` call.
    """
    local_by_id, directive_ids, _ = _load_project_directives_with_source(repo_root, load_directives_config)
    return local_by_id, directive_ids


def _maybe_build_doctrine_service(repo_root: Path) -> _doctrine_service_module.DoctrineService | None:
    try:
        from charter.activation.context import _build_doctrine_service  # noqa: PLC0415

        return _build_doctrine_service(repo_root)
    except Exception:  # noqa: BLE001 - local directive IDs are still useful
        return None


def _local_directive_entry(directive_id: str, local: object) -> dict[str, object]:
    entry: dict[str, object] = {"id": directive_id, "source": "project"}
    title = getattr(local, "title", None)
    description = getattr(local, "description", None)
    if isinstance(title, str) and title:
        entry["title"] = title
    if isinstance(description, str) and description:
        entry["summary"] = description
    return entry


_EMPTY_ORG_CHARTER: dict[str, object] = {"present": False, "packs": []}


def _assemble_directive_entries(
    directive_ids: list[str],
    local_by_id: dict[str, object],
    service: _doctrine_service_module.DoctrineService | None,
) -> list[dict[str, object]]:
    """Build the per-directive ``all_directives`` entries from resolved IDs."""
    entries: list[dict[str, object]] = []
    for directive_id in directive_ids:
        local = local_by_id.get(directive_id)
        if local is not None:
            entries.append(_local_directive_entry(directive_id, local))
            continue
        if service is None:
            entries.append({"id": directive_id, "source": "builtin"})
            continue
        entries.extend(_pd.collect_typed_artifacts(service.directives, [directive_id], kind="directive"))
    return entries


def _project_directive_entries_with_source(
    repo_root: Path,
) -> tuple[list[dict[str, object]], str | None]:
    """Return the project directive entries **and** the resolution-level
    ``directives_source`` provenance from a single governance resolution.

    The JSON payload builder (``build_charter_context_json``) consumes this so
    both ``all_directives`` and the top-level ``directives_source`` key come from
    ONE ``resolve_project_governance`` call — never two per payload.
    """
    from charter.activation.sync import load_directives_config

    local_by_id, directive_ids, directives_source = _load_project_directives_with_source(repo_root, load_directives_config)
    service = _maybe_build_doctrine_service(repo_root)
    return _assemble_directive_entries(directive_ids, local_by_id, service), directives_source


def _project_directive_entries(repo_root: Path) -> list[dict[str, object]]:
    """Return every directive ID that the project-governance resolver exposes."""
    entries, _ = _project_directive_entries_with_source(repo_root)
    return entries
