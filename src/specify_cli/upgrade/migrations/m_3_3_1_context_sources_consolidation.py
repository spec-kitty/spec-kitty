"""Migration: consolidate agent-profile ``context-sources`` onto ``*-references``.

Mission ``doctrine-drg-silent-drop-boundary-01M0PE7E`` (WP02, #3629 p1) retired
the redundant, mostly-inert ``context-sources.*`` bare-string surface from the
agent-profile schema. The canonical, DRG-provisioned home is the top-level
``*-references`` surface (``directive-references`` / ``tactic-references`` /
``toolguide-references`` / ``styleguide-references``). Because the model now
declares ``extra="forbid"`` without a ``context-sources`` field, any profile
that still authors the block fails to LOAD — so a consumer project that
authored custom profiles with ``context-sources`` must be migrated in lockstep.

This migration **set-merges** every ``context-sources`` reference id onto the
matching ``*-references`` field (deduplicating by id — never appending a
duplicate), then removes the ``context-sources`` block. Bare-string
``additional`` names and ``doctrine-layers`` layer names have no DRG edge shape
(no ``NodeKind``), so they are dropped with a logged note rather than
silently vanished. The data-moving branch (ids present in ``context-sources``
but absent from ``*-references``) is exercised by
``tests/charter_offering/agent_profiles/test_context_sources_migration.py`` — the 25
shipped profiles already duplicate every id onto ``*-references`` (the migration
is deletion-only for them), so a divergent user-profile fixture is the only
falsifiable witness of the merge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

#: Rationale stamped onto a reference entry synthesised from a bare
#: ``context-sources`` id that had no matching ``*-references`` entry.
_MIGRATED_RATIONALE = "Migrated from the retired context-sources surface (mission doctrine-drg-silent-drop-boundary-01M0PE7E)."

#: ``context-sources`` key -> (canonical ``*-references`` field, id key on that
#: field's entries). ``directive-references`` entries key on ``code``; the other
#: three key on ``id``.
_MERGE_MAP: tuple[tuple[str, str, str], ...] = (
    ("directives", "directive-references", "code"),
    ("tactics", "tactic-references", "id"),
    ("toolguides", "toolguide-references", "id"),
    ("styleguides", "styleguide-references", "id"),
)

#: ``context-sources`` keys with no DRG edge shape — dropped with a note.
_NON_EDGE_KEYS: tuple[str, ...] = ("doctrine-layers", "additional")

_PROFILE_GLOB = "*.agent.yaml"
#: Directories never walked for consumer profiles (VCS, envs, nested worktrees).
_SKIP_DIR_PARTS = frozenset({".git", ".venv", "node_modules", ".worktrees"})


@dataclass
class ConsolidationOutcome:
    """Result of consolidating one profile mapping in place."""

    changed: bool = False
    #: ``*-references`` field -> ids newly moved off ``context-sources``.
    merged: dict[str, list[str]] = field(default_factory=dict)
    #: ``context-sources`` non-edge entries dropped (``key:value``).
    dropped: list[str] = field(default_factory=list)


def _synthesise_reference(id_key: str, ref_id: str) -> dict[str, str]:
    """Build a minimal ``*-references`` entry for a bare migrated id."""
    if id_key == "code":
        return {"code": ref_id, "name": ref_id, "rationale": _MIGRATED_RATIONALE}
    return {"id": ref_id, "rationale": _MIGRATED_RATIONALE}


def _existing_ids(refs: list[Any], id_key: str) -> set[str]:
    return {str(r.get(id_key)) for r in refs if isinstance(r, dict) and r.get(id_key) is not None}


def _merge_one_field(
    data: dict[str, Any],
    context_sources: dict[str, Any],
    cs_key: str,
    ref_field: str,
    id_key: str,
) -> list[str]:
    """Set-merge ``context-sources[cs_key]`` into ``data[ref_field]``.

    Returns the ids newly appended (empty when every id was already present —
    the shipped-profile, deletion-only case).
    """
    raw_ids = context_sources.get(cs_key) or []
    if not raw_ids:
        return []
    refs = data.get(ref_field)
    if not isinstance(refs, list):
        refs = []
    seen = _existing_ids(refs, id_key)
    newly: list[str] = []
    for raw in raw_ids:
        ref_id = str(raw)
        if ref_id in seen:
            continue
        refs.append(_synthesise_reference(id_key, ref_id))
        seen.add(ref_id)
        newly.append(ref_id)
    if newly:
        data[ref_field] = refs
        # Dup-guard: the set-merge must never leave a duplicate id behind.
        merged_ids = [str(r.get(id_key)) for r in refs if isinstance(r, dict)]
        if len(merged_ids) != len(set(merged_ids)):
            raise ValueError(f"context-sources consolidation produced duplicate ids in {ref_field!r}: {merged_ids}")
    return newly


def consolidate_profile_context_sources(data: dict[str, Any]) -> ConsolidationOutcome:
    """Set-merge ``context-sources`` onto ``*-references`` in *data* in place.

    Mutates *data*: every reference id is moved onto its canonical
    ``*-references`` field (deduped), non-edge keys are dropped with a note, and
    the ``context-sources`` block is removed. A profile without a
    ``context-sources`` block is left untouched (``changed=False``).
    """
    context_sources = data.get("context-sources")
    if not isinstance(context_sources, dict):
        return ConsolidationOutcome(changed=False)

    outcome = ConsolidationOutcome(changed=True)
    for cs_key, ref_field, id_key in _MERGE_MAP:
        newly = _merge_one_field(data, context_sources, cs_key, ref_field, id_key)
        if newly:
            outcome.merged[ref_field] = newly
    for key in _NON_EDGE_KEYS:
        for value in context_sources.get(key) or []:
            outcome.dropped.append(f"{key}:{value}")
    del data["context-sources"]
    return outcome


def _iter_profile_paths(project_path: Path) -> list[Path]:
    """Return consumer-authored ``*.agent.yaml`` files under *project_path*."""
    paths: list[Path] = []
    for path in project_path.rglob(_PROFILE_GLOB):
        if _SKIP_DIR_PARTS & set(path.parts):
            continue
        paths.append(path)
    return sorted(paths)


def _round_trip_yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    return yaml


def _load_profile_mapping(path: Path, yaml: YAML) -> dict[str, Any] | None:
    """Round-trip load *path* as a mapping; ``None`` on read/parse failure or a
    non-mapping payload (a malformed profile is skipped, not fatal, at scan
    time)."""
    try:
        data = yaml.load(path.read_text(encoding="utf-8"))
    except (OSError, YAMLError):
        return None
    return data if isinstance(data, dict) else None


@MigrationRegistry.register
class ContextSourcesConsolidationMigration(BaseMigration):
    """Consolidate agent-profile ``context-sources`` onto ``*-references``."""

    migration_id = "3_3_1_context_sources_consolidation"
    description = "Consolidate agent-profile context-sources onto *-references"
    target_version = "3.2.6rc2"

    def detect(self, project_path: Path) -> bool:
        """True when any consumer profile still authors ``context-sources``."""
        yaml = _round_trip_yaml()
        for path in _iter_profile_paths(project_path):
            data = _load_profile_mapping(path, yaml)
            if data is not None and isinstance(data.get("context-sources"), dict):
                return True
        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002 — BaseMigration interface signature; this migration is always applicable (apply() is a safe no-op when no profile authors context-sources)
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Consolidate ``context-sources`` in every consumer profile found."""
        changes: list[str] = []
        errors: list[str] = []
        yaml = _round_trip_yaml()

        for path in _iter_profile_paths(project_path):
            try:
                data = yaml.load(path.read_text(encoding="utf-8"))
            except (OSError, YAMLError) as exc:
                errors.append(f"Failed to read {path}: {exc}")
                continue
            if not isinstance(data, dict) or not isinstance(data.get("context-sources"), dict):
                continue

            try:
                outcome = consolidate_profile_context_sources(data)
            except ValueError as exc:
                errors.append(f"Consolidation failed for {path}: {exc}")
                continue
            if not outcome.changed:
                continue

            rel = str(path.relative_to(project_path))
            summary = _summarise(outcome)
            if dry_run:
                changes.append(f"Would consolidate context-sources in {rel} ({summary})")
                continue
            try:
                with path.open("w", encoding="utf-8") as handle:
                    yaml.dump(data, handle)
                changes.append(f"Consolidated context-sources in {rel} ({summary})")
            except OSError as exc:
                errors.append(f"Failed to write {rel}: {exc}")

        if not changes and not errors:
            changes.append("No consumer profile authored context-sources")

        return MigrationResult(
            success=len(errors) == 0,
            changes_made=changes,
            errors=errors,
        )


def _summarise(outcome: ConsolidationOutcome) -> str:
    merged = sum(len(ids) for ids in outcome.merged.values())
    if not outcome.dropped:
        return f"merged {merged} refs, dropped 0 non-edge entries"
    # Name each dropped entry so an author who set a custom `additional:` /
    # `doctrine-layers:` binding sees exactly which id was discarded, not just a
    # count (audit F5 observability nit).
    dropped = ", ".join(sorted(outcome.dropped))
    return f"merged {merged} refs, dropped {len(outcome.dropped)} non-edge entries ({dropped})"
