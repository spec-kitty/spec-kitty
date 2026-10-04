"""Drift and staleness findings for installed pack skills (FR-012, FR-014).

Two distinct, independently reported conditions per installed pack-skill file:

* **drift** -- the installed rendered copy's bytes no longer hash to the
  manifest ``content_hash`` (a local edit); the remedy is to edit the pack
  source named by ``source_ref`` and re-project, not the rendered copy.
* **staleness** -- the freshly prepared pack source no longer hashes to the
  manifest ``source_hash`` (the pack changed since install); re-project to
  refresh the copy.

Both findings name ``source_ref``. Built-in entries and manifests written
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


@dataclass(frozen=True)
class PackSkillFinding:
    """One drift or staleness finding for an installed pack-skill file."""

    kind: str
    skill_name: str
    installed_path: str
    source_ref: str

    @property
    def message(self) -> str:
        if self.kind == KIND_DRIFT:
            return f"{self.installed_path}: rendered pack skill {self.skill_name!r} was edited locally; edit its source {self.source_ref!r} and re-project instead"
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

    Unreadable manifests, absent files and an unresolvable pack catalog yield no
    finding here: those conditions are reported by the verifier and assessment.
    """
    try:
        manifest = load_manifest(project_path, strict=True)
    except ValueError:
        return ()
    entries = [entry for entry in (manifest.entries if manifest else []) if entry.origin == ORIGIN_PACK]
    if not entries:
        return ()
    current = _current_source_hashes(project_path)
    findings: list[PackSkillFinding] = []
    for entry in entries:
        findings.extend(_entry_findings(project_path, entry, current))
    return tuple(findings)


def _entry_findings(project_path: Path, entry: ManagedFileEntry, current: dict[str, str]) -> list[PackSkillFinding]:
    found: list[PackSkillFinding] = []
    if _installed_hash(project_path, entry) not in (None, entry.content_hash):
        found.append(PackSkillFinding(KIND_DRIFT, entry.skill_name, entry.installed_path, entry.source_ref))
    fresh = current.get(entry.skill_name)
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


def _current_source_hashes(project_path: Path) -> dict[str, str]:
    """Rendered skill name -> freshly prepared ``source_hash`` (read-only resolution)."""
    try:
        registry = resolve_project_skill_catalog(project_path, stage=False)
        skills = registry.discover_skills()
    except PackSkillCatalogError:
        logger.debug("pack skill catalog unresolvable; staleness not assessed", exc_info=True)
        return {}
    return {skill.name: skill.source_hash for skill in skills if skill.origin == ORIGIN_PACK and skill.source_hash}
