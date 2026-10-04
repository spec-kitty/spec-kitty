"""Drift and staleness findings for installed pack skills (FR-012, FR-014).

Distinct, independently reported conditions per installed pack-skill file:

* **drift** -- the installed rendered copy's bytes no longer hash to the
  manifest ``content_hash`` (a local edit); the remedy is to edit the pack
  source named by ``source_ref`` and re-project, not the rendered copy.
* **staleness** -- the freshly prepared pack source no longer hashes to the
  manifest ``source_hash`` (the pack changed since install); re-project to
  refresh the copy.

* **unresolvable** -- the pack catalog could not be resolved at all (e.g. the skill
  namespace was removed), so the installed pack skills could not be checked for
  staleness or orphaning; one finding carries the refusal message.

* **orphaned** -- the manifest names a pack skill the current catalog no longer
  provides (e.g. the skill namespace changed, so it renders under a new name, or
  the skill was deactivated/removed); `spec-kitty upgrade` retires the leftover
  copy, or re-activate the skill.

All findings name ``source_ref``. Built-in entries and manifests written
before pack skills existed (no ``origin``/``source_*``) never produce findings.
Resolution is read-only (``stage=False``): nothing is written to the project.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from specify_cli.skills.catalog import PackSkillCatalogError, resolve_project_skill_catalog
from specify_cli.skills.manifest import ORIGIN_PACK, ManagedFileEntry, compute_content_hash, load_manifest
from specify_cli.skills.paths import skill_path_observations

logger = logging.getLogger(__name__)

__all__ = ["find_pack_skill_findings"]

KIND_DRIFT = "drift"
KIND_STALE = "stale"
KIND_ORPHANED = "orphaned"
KIND_UNRESOLVABLE = "unresolvable"


@dataclass(frozen=True)
class PackSkillFinding:
    """One drift or staleness finding for an installed pack-skill file."""

    kind: str
    skill_name: str
    installed_path: str
    source_ref: str
    detail: str = ""
    """Why the catalog could not be resolved (``unresolvable`` findings only)."""

    @property
    def message(self) -> str:
        if self.kind == KIND_UNRESOLVABLE:
            return f"installed pack skills were not checked for staleness or orphaning: the pack catalog could not be resolved: {self.detail}"
        if self.kind == KIND_DRIFT:
            return f"{self.installed_path}: rendered pack skill {self.skill_name!r} was edited locally; edit its source {self.source_ref!r} and re-project instead"
        if self.kind == KIND_ORPHANED:
            return (
                f"{self.installed_path}: pack skill {self.skill_name!r} (source {self.source_ref!r}) is no longer provided by the current pack catalog "
                "(namespace changed, or the skill was deactivated or removed); run `spec-kitty upgrade` to retire it or re-activate the skill"
            )
        return (
            f"{self.installed_path}: pack skill {self.skill_name!r} is stale, its source {self.source_ref!r} "
            "changed since install; re-project (`spec-kitty upgrade`) to refresh it"
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "skill_name": self.skill_name,
            "installed_path": self.installed_path,
            "source_ref": self.source_ref,
            "message": self.message,
        }


def find_pack_skill_findings(project_path: Path) -> tuple[PackSkillFinding, ...]:
    """Return drift/staleness findings for the project's installed pack skills.

    Unreadable manifests and absent files yield no finding here: those conditions
    are reported by the verifier and assessment. An unresolvable pack catalog yields
    one ``unresolvable`` finding carrying the refusal, because ``doctor skills``
    does not run the verifier and would otherwise report nothing -- also when no pack
    copy is installed yet.
    """
    try:
        manifest = load_manifest(project_path, strict=True)
    except ValueError:
        return ()
    entries = [entry for entry in (manifest.entries if manifest else []) if entry.origin == ORIGIN_PACK]
    current, refusal = _current_source_hashes(project_path)  # current is None: catalog unresolvable
    if not entries:
        # Nothing is installed yet, so there is nothing to check. A skill in force that cannot be resolved is
        # still one finding: resolution only refuses when a skill is in force, so a project with none stays silent.
        return () if current is not None else (PackSkillFinding(KIND_UNRESOLVABLE, "", "", "", refusal),)
    findings: list[PackSkillFinding] = []
    for entry in entries:
        findings.extend(_entry_findings(project_path, entry, current))
    if current is None:
        findings.append(PackSkillFinding(KIND_UNRESOLVABLE, "", "", "", refusal))
    return tuple(findings)


def _entry_findings(project_path: Path, entry: ManagedFileEntry, current: dict[str, str] | None) -> list[PackSkillFinding]:
    if current is not None and entry.skill_name not in current:
        return [PackSkillFinding(KIND_ORPHANED, entry.skill_name, entry.installed_path, entry.source_ref)]
    found: list[PackSkillFinding] = []
    if _installed_hash(project_path, entry) not in (None, entry.content_hash):
        found.append(PackSkillFinding(KIND_DRIFT, entry.skill_name, entry.installed_path, entry.source_ref))
    fresh = current.get(entry.skill_name) if current is not None else None
    # A manifest written before the shared ``sha256:`` digest format carries a bare-hex
    # source_hash; it can never equal a fresh digest, so it is reported stale ONCE and
    # re-projection rewrites it in the current format (no permanent false staleness).
    if entry.source_hash and fresh is not None and fresh != entry.source_hash:
        found.append(PackSkillFinding(KIND_STALE, entry.skill_name, entry.installed_path, entry.source_ref))
    return found


def _installed_hash(project_path: Path, entry: ManagedFileEntry) -> str | None:
    """``sha256:`` of the installed regular file, or ``None`` when absent/unreadable."""
    try:
        state = skill_path_observations(project_path, project_path / entry.installed_path)[-1].state
        if state.kind != "file":
            return None
        return compute_content_hash(project_path / entry.installed_path)
    except (OSError, ValueError):
        return None


def _current_source_hashes(project_path: Path) -> tuple[dict[str, str] | None, str]:
    """Rendered skill name -> freshly prepared ``source_hash`` (read-only resolution), plus the refusal.

    The mapping is ``None`` (with the refusal message) when the catalog is unresolvable.
    """
    try:
        registry = resolve_project_skill_catalog(project_path, stage=False)
        skills = registry.discover_skills()
    except PackSkillCatalogError as exc:
        logger.debug("pack skill catalog unresolvable; staleness not assessed", exc_info=True)
        return None, str(exc)
    return {skill.name: skill.source_hash for skill in skills if skill.origin == ORIGIN_PACK}, ""
