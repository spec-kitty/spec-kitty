"""Pack-skill repository (ADR 2026-09-27-1, FR-005).

Loads ``*.skill.yaml`` from the built-in, org and project tiers through the
shared :class:`~charter.offering.base.BaseArtifactRepository` and adds the
pack-skill rules the base cannot express:

* tier validation (reserved prefixes, no ``scripts/``, no ``allowed-tools``);
* the same id in two *sibling* org packs is a hard :class:`PackSkillConflictError`;
* ``enhances: <id>`` tunes a lower-tier skill (never its body/expansion) and
  ``overrides: <id>`` replaces it. Either way the augmenting record is folded
  into the catalog under the *target* id, so ``skill:<target>`` stays stable.
  A built-in target may not be overridden here (the replaceable-builtins
  allowlist is not wired for skills).
"""

from __future__ import annotations

import warnings
from pathlib import Path

from pydantic import ValidationError
from pydantic_core import InitErrorDetails

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.base import BaseArtifactRepository
from charter.offering.pack_paths import built_in_dir
from charter.offering.pack_skills.models import PackSkill
from charter.offering.pack_skills.validation import (
    PackSkillViolation,
    Tier,
    apply_enhancement,
    validate_pack_skill,
)

_TIER_RANK: dict[str, int] = {"builtin": 0, "org": 1, "project": 2}


class PackSkillConflictError(RuntimeError):
    """The same skill id is declared by two sibling org packs (hard conflict)."""


def _violation_as_validation_error(message: str) -> ValidationError:
    """Wrap *message* in a pydantic ``ValidationError`` the base loader skips-and-warns on."""
    detail = InitErrorDetails(type="value_error", loc=(), input=None, ctx={"error": ValueError(message)})
    return ValidationError.from_exception_data("PackSkill", [detail])


class PackSkillRepository(BaseArtifactRepository[PackSkill]):
    """Repository for pack skills across the three Charter Pack tiers."""

    def __init__(
        self,
        built_in_dir: Path | None = None,
        *,
        org_dirs: list[Path] | None = None,
        project_dir: Path | None = None,
        skill_namespace: str | None = None,
    ) -> None:
        self._namespace = skill_namespace
        self._sources: dict[str, Path] = {}
        self._org_origin: dict[str, Path] = {}
        resolved_built_in = built_in_dir or self._default_built_in_dir()
        super().__init__(built_in_dir=resolved_built_in, org_dirs=org_dirs, project_dir=project_dir)

    @staticmethod
    def _default_built_in_dir() -> Path:
        """Default built-in pack-skills directory (empty at MVP)."""
        return built_in_dir(ArtifactKind.SKILL)

    @property
    def _schema(self) -> type[PackSkill]:
        return PackSkill

    @property
    def _glob(self) -> str:
        return "*.skill.yaml"

    @property
    def _kind(self) -> str:
        return "pack-skill"

    # -- tier bookkeeping -------------------------------------------------

    def _tier_of(self, yaml_file: Path) -> Tier:
        if yaml_file.is_relative_to(self._built_in_dir):
            return "builtin"
        if self._project_dir is not None and yaml_file.is_relative_to(self._project_dir):
            return "project"
        return "org"

    def _org_root_of(self, yaml_file: Path) -> Path:
        for org_dir in self._org_dirs:
            if yaml_file.is_relative_to(org_dir):
                return org_dir
        return yaml_file.parent

    def _post_validate(self, obj: PackSkill, yaml_file: Path) -> None:
        tier = self._tier_of(yaml_file)
        try:
            validate_pack_skill(obj, yaml_file, tier=tier, namespace=self._namespace)
        except PackSkillViolation as exc:
            raise _violation_as_validation_error(str(exc)) from exc
        if tier == "org":
            self._record_org_origin(obj.id, yaml_file)
        self._sources[obj.id] = yaml_file

    def _record_org_origin(self, skill_id: str, yaml_file: Path) -> None:
        root = self._org_root_of(yaml_file)
        previous = self._org_origin.setdefault(skill_id, root)
        if previous != root:
            raise PackSkillConflictError(f"skill id {skill_id!r} is declared by two org packs ({previous} and {root}); sibling packs must not share a skill id")

    # -- augmentation -----------------------------------------------------

    def _load(self) -> None:
        super()._load()
        self._resolve_augmentations()

    def _resolve_augmentations(self) -> None:
        augmenters = [item for item in self.list_all() if item.is_augmentation]
        for augmenter in augmenters:
            self._items.pop(augmenter.id, None)
        for augmenter in augmenters:
            layer = self._provenance.pop(augmenter.id, "unknown")
            source = self._sources.pop(augmenter.id, Path(augmenter.id))
            try:
                self._fold_augmenter(augmenter, layer, source)
            except PackSkillViolation as exc:
                warnings.warn(f"Skipping invalid {layer} {self._kind} {source.name}: {exc}", UserWarning, stacklevel=2)

    def _fold_augmenter(self, augmenter: PackSkill, layer: str, source: Path) -> None:
        target_id = augmenter.overrides or augmenter.enhances or ""
        base = self._items.get(target_id)
        if base is None:
            raise PackSkillViolation(f"skill {augmenter.id!r}: target skill {target_id!r} is not loaded from a lower tier")
        base_layer = self._provenance.get(target_id, "unknown")
        if _TIER_RANK.get(base_layer, 0) >= _TIER_RANK.get(layer, 0):
            raise PackSkillViolation(f"skill {augmenter.id!r}: target {target_id!r} ({base_layer}) must come from a lower tier than {layer}")
        if augmenter.enhances:
            resolved = apply_enhancement(base, augmenter)
        else:
            if base_layer == "builtin":
                raise PackSkillViolation(
                    f"skill {augmenter.id!r}: overriding built-in skill {target_id!r} requires the replaceable-builtins allowlist, which skills do not support yet"
                )
            resolved = augmenter.model_copy(update={"id": target_id, "overrides": None})
        self._items[target_id] = resolved
        self._provenance[target_id] = layer
        if augmenter.overrides:
            # An enhancement keeps the base's file as the body source.
            self._sources[target_id] = source

    # -- accessors ----------------------------------------------------------

    def source_path(self, skill_id: str) -> Path | None:
        """Return the ``*.skill.yaml`` file a loaded skill came from."""
        return self._sources.get(skill_id)

    def provenance_of(self, skill_id: str) -> str | None:
        """Return the tier (``builtin``/``org``/``project``) a loaded skill resolved from."""
        return self._provenance.get(skill_id)

    def body_text(self, skill_id: str) -> str | None:
        """Return the prompt body of a loaded prompt-form skill, or ``None``."""
        skill = self._items.get(skill_id)
        source = self._sources.get(skill_id)
        if skill is None or source is None or not skill.body_path:
            return None
        return (source.parent / skill.body_path).read_text(encoding="utf-8")


__all__ = ["PackSkillConflictError", "PackSkillRepository"]
