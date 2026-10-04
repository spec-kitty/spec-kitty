"""Skill verification and repair — detects missing/drifted installed files."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from kernel.content_digest import sha256_digest
from specify_cli.skills.manifest import (
    ManagedFileEntry,
    compute_content_hash,
    load_manifest,
)
from specify_cli.skills.paths import get_primary_global_skill_root as get_primary_global_skill_root
from specify_cli.skills.paths import skill_path_observations
from specify_cli.skills.catalog import PackSkillCatalogError, resolve_project_skill_catalog
from specify_cli.skills.registry import SkillRegistry
from specify_cli.skills.command_renderer import ensure_skill_frontmatter
from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot

logger = logging.getLogger(__name__)

SKILL_MANIFEST_FILENAME = "SKILL.md"


@dataclass
class VerifyResult:
    """Structured result of a skill verification pass."""

    ok: bool
    missing: list[ManagedFileEntry] = field(default_factory=list)
    drifted: list[tuple[ManagedFileEntry, str]] = field(default_factory=list)  # (entry, actual_hash)
    unmanaged: list[str] = field(default_factory=list)  # paths not in manifest
    errors: list[str] = field(default_factory=list)

    @property
    def total_issues(self) -> int:
        return len(self.missing) + len(self.drifted) + len(self.errors)


def verify_installed_skills(project_path: Path) -> VerifyResult:
    """Verify all installed skill files against the manifest.

    If no manifest exists, returns ``VerifyResult(ok=True)`` — nothing to check.
    Otherwise, checks each manifest entry for existence and content hash match.
    """
    try:
        manifest = load_manifest(project_path, strict=True)
    except ValueError as exc:
        return VerifyResult(ok=False, errors=[str(exc)])
    if manifest is None:
        return VerifyResult(ok=True)

    missing: list[ManagedFileEntry] = []
    drifted: list[tuple[ManagedFileEntry, str]] = []
    errors: list[str] = []
    try:
        registry = _discover_registry(project_path)
    except PackSkillCatalogError as exc:
        return VerifyResult(ok=False, errors=[str(exc)])

    for entry in manifest.entries:
        installed = project_path / entry.installed_path
        try:
            observed = skill_path_observations(project_path, installed)[-1].state
        except (OSError, ValueError) as exc:
            errors.append(f"Unsafe path {entry.installed_path}: {exc}")
            continue
        if observed.kind == "absent":
            missing.append(entry)
            continue
        if observed.kind == "symlink":
            drifted.append((entry, f"symlink:{observed.target}"))
            continue
        if observed.kind != "file":
            errors.append(f"Cannot read {entry.installed_path}: not a regular skill file")
            continue
        actual_hash = f"sha256:{observed.sha256}"
        expected_hash = _expected_hash(entry, registry) or entry.content_hash
        if actual_hash != expected_hash:
            drifted.append((entry, actual_hash))

    ok = len(missing) == 0 and len(drifted) == 0 and len(errors) == 0
    return VerifyResult(ok=ok, missing=missing, drifted=drifted, errors=errors)


def repair_skills(
    project_path: Path,
    verify_result: VerifyResult,
    registry: SkillRegistry,
    *,
    consent: ApplyConsent = ApplyConsent(automatic=True),
) -> tuple[int, int]:
    """Apply one project-only preparation; drift needs exact-path consent."""
    from specify_cli.skills.installer import assess_project_skills, apply_project_skills, recheck_project_skills

    requested = tuple(verify_result.missing) + tuple(entry for entry, _ in verify_result.drifted)
    try:
        manifest = load_manifest(project_path, strict=True)
    except ValueError as exc:
        logger.warning("Cannot repair skills: %s", exc)
        return 0, max(1, len(requested))
    recorded = manifest.entries if manifest is not None else []
    agents = tuple(sorted({entry.agent_key for entry in (*requested, *recorded)}))
    inputs = AssessmentInputs(OperationRoot("project", "project", project_path.absolute()), consent=consent)
    assessment = assess_project_skills(inputs, registry, agents,
                                       selected_paths=tuple(entry.installed_path for entry in requested))
    if not assessment.complete:
        for diagnostic in assessment.diagnostics:
            logger.warning("Cannot repair skills: %s", diagnostic.message)
        return 0, max(1, len(requested))
    with recheck_project_skills(assessment) as diagnostics:
        if diagnostics:
            return 0, max(1, len(requested))
        result = apply_project_skills(assessment, consent)
    file_effects = {effect.id: effect for effect in assessment.effects if
                    effect.path != ".kittify/skills-manifest.json" and
                    not effect.path.startswith(".kittify/.migration-backup/") and
                    effect.before.kind != "directory" and effect.after.kind != "directory"}
    repaired = sum(effect_id in file_effects for effect_id in result.succeeded)
    failed_paths = {item.path for item in assessment.dispositions if item.state in {"preserve", "consent_required"}}
    failed = len(failed_paths) + len(result.failed) + sum(effect_id in file_effects for effect_id in result.skipped)
    if result.outcome in {"skipped", "precondition_changed"}:
        failed = max(1, len(requested))
    unresolved = {entry.installed_path for entry in requested} - {
        effect.path for effect in file_effects.values()
    } - {item.path for item in assessment.dispositions}
    return repaired, failed + len(unresolved)


def _find_source_file(skill_dir: Path, source_file: str) -> Path | None:
    """Locate a source file within a canonical skill directory.

    *source_file* is relative within the skill dir (e.g. ``"SKILL.md"`` or
    ``"references/agent-path-matrix.md"``).  The resolved path must remain
    within *skill_dir* to prevent path traversal.
    """
    candidate = skill_dir / source_file
    try:
        state = skill_path_observations(skill_dir, candidate)[-1].state
    except (OSError, ValueError):
        return None
    return candidate if state.kind == "file" else None


def _discover_registry(project_path: Path) -> SkillRegistry | None:
    """Resolve the project's skill catalog (built-in plus pack skills) for drift detection."""
    return resolve_project_skill_catalog(project_path, stage=False)


def _expected_hash(entry: ManagedFileEntry, registry: SkillRegistry | None) -> str | None:
    """Return the current canonical hash for an entry when available."""
    if registry is None:
        return None

    skill = registry.get_skill(entry.skill_name)
    if skill is None:
        return None

    source_path = _find_source_file(skill.skill_dir, entry.source_file)
    if source_path is None:
        return None

    return _expected_content_hash(source_path, entry.skill_name, entry.source_file)


def _expected_content_hash(source: Path, skill_name: str, source_file: str) -> str:
    """Return the hash that install/repair should produce for a source file."""
    if source_file != SKILL_MANIFEST_FILENAME:
        return compute_content_hash(source)
    content = source.read_text(encoding="utf-8")
    normalized = ensure_skill_frontmatter(content, skill_name).encode("utf-8")
    return sha256_digest(normalized)
