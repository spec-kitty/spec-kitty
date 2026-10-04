"""Pure validation for pack skills (ADR 2026-09-27-1, FR-004, FR-005).

Everything here is a pure function over an already schema-valid
:class:`~charter.offering.pack_skills.models.PackSkill` plus the file it came
from. Violations raise :class:`PackSkillViolation`; the repository turns them
into skipped-file diagnostics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final, Literal

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.offering.pack_skills.models import PackSkill, SkillInvocation, SkillParameter

Tier = Literal["builtin", "org", "project"]

#: Name prefixes reserved for built-in skills (ADR "Namespaces and trust").
RESERVED_PREFIXES: Final[tuple[str, ...]] = ("spk-", "spec-kitty-", "spec-kitty.")

#: Frontmatter keys that would widen the host tool's permissions.
_FORBIDDEN_FRONTMATTER_KEYS: Final[frozenset[str]] = frozenset({"allowed-tools", "allowed_tools"})

_FRONTMATTER_FENCE = "---"


class PackSkillViolation(ValueError):
    """A pack skill breaks a tier, trust or augmentation rule."""


def rendered_name(skill_id: str, namespace: str | None) -> str:
    """Name a skill renders under: ``<namespace>-<id>`` or the bare id."""
    return f"{namespace}-{skill_id}" if namespace else skill_id


def validate_pack_skill(
    skill: PackSkill,
    skill_file: Path,
    *,
    tier: Tier,
    namespace: str | None = None,
) -> None:
    """Validate *skill* for the tier it was loaded from.

    Every tier: a prompt-form body must exist next to the skill file and stay
    inside its directory. Org and project tiers additionally refuse reserved
    built-in name prefixes, a ``scripts/`` directory beside the skill, and
    permission-widening frontmatter in the body.
    """
    # An ``enhances`` record restates the base's body_path but never carries the
    # body itself; the base skill's own file is validated when it loads.
    needs_body = skill.form == "prompt" and not skill.enhances
    body_text = _read_body(skill, skill_file) if needs_body else None
    if tier == "builtin":
        return
    _check_reserved_prefix(skill, namespace)
    _check_no_scripts_dir(skill, skill_file)
    if body_text is not None:
        _check_frontmatter(skill, body_text)


def _read_body(skill: PackSkill, skill_file: Path) -> str:
    base = skill_file.parent.resolve()
    body_file = (base / (skill.body_path or "")).resolve()
    if not body_file.is_relative_to(base):
        raise PackSkillViolation(f"skill {skill.id!r}: body_path {skill.body_path!r} escapes the skill directory")
    if not body_file.is_file():
        raise PackSkillViolation(f"skill {skill.id!r}: body file {skill.body_path!r} not found")
    return body_file.read_text(encoding="utf-8")


def _check_reserved_prefix(skill: PackSkill, namespace: str | None) -> None:
    for candidate in (skill.id, rendered_name(skill.id, namespace)):
        if candidate.startswith(RESERVED_PREFIXES):
            raise PackSkillViolation(f"skill {skill.id!r}: name {candidate!r} uses a prefix reserved for built-in skills {list(RESERVED_PREFIXES)}")


def _check_no_scripts_dir(skill: PackSkill, skill_file: Path) -> None:
    for scripts_dir in (skill_file.parent / "scripts", skill_file.parent / skill.id / "scripts"):
        if scripts_dir.is_dir():
            raise PackSkillViolation(f"skill {skill.id!r}: a 'scripts/' directory is not allowed for org/project skills ({scripts_dir})")


def _frontmatter_keys(text: str) -> frozenset[str]:
    """Return the top-level keys of a leading ``---`` YAML frontmatter block.

    A body without frontmatter yields an empty set; frontmatter that is not a
    parseable mapping raises :class:`PackSkillViolation`.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_FENCE:
        return frozenset()
    for end, line in enumerate(lines[1:], start=1):
        if line.strip() == _FRONTMATTER_FENCE:
            return _parse_frontmatter_block("\n".join(lines[1:end]))
    raise PackSkillViolation("body frontmatter is not closed")


def _parse_frontmatter_block(block: str) -> frozenset[str]:
    try:
        data: Any = YAML(typ="safe").load(block)
    except YAMLError as exc:
        raise PackSkillViolation(f"body frontmatter is not valid YAML: {exc}") from exc
    if data is None:
        return frozenset()
    if not isinstance(data, dict):
        raise PackSkillViolation("body frontmatter must be a mapping")
    return frozenset(str(key).lower() for key in data)


def _check_frontmatter(skill: PackSkill, body_text: str) -> None:
    forbidden = sorted(_FORBIDDEN_FRONTMATTER_KEYS & _frontmatter_keys(body_text))
    if forbidden:
        raise PackSkillViolation(f"skill {skill.id!r}: permission-widening frontmatter key(s) {forbidden} are not allowed for org/project skills")


# ---------------------------------------------------------------------------
# overrides / enhances
# ---------------------------------------------------------------------------


def apply_enhancement(base: PackSkill, enhancer: PackSkill) -> PackSkill:
    """Return *base* narrowed/tuned by *enhancer* or raise :class:`PackSkillViolation`.

    An enhancement may change parameter defaults, triggers, tool targeting and
    descriptive metadata, and may narrow invocation. It restates the base
    ``form`` / ``body_path`` / ``expands_to`` unchanged -- it never changes the
    body or the expansion, never adds/removes/re-requires a parameter, and
    never widens invocation or drops a declared side effect.
    """
    _require_same_substance(base, enhancer)
    _require_same_parameter_shape(base, enhancer)
    _require_narrowing(base.invocation, enhancer.invocation)
    # Rebuild (rather than ``model_copy``) so the merged record is re-validated,
    # including the side-effects => not model-invocable rule.
    return PackSkill(
        schema_version=base.schema_version,
        id=base.id,
        title=enhancer.title,
        description=enhancer.description,
        triggers=enhancer.triggers,
        form=base.form,
        body_path=base.body_path,
        expands_to=base.expands_to,
        parameters=enhancer.parameters,
        invocation=SkillInvocation(
            user_invocable=enhancer.invocation.user_invocable,
            model_invocable=enhancer.invocation.model_invocable,
            side_effects=list(enhancer.invocation.side_effects),
        ),
        tools=enhancer.tools,
        version=enhancer.version,
        maintainers=enhancer.maintainers,
        overrides=None,
        enhances=None,
    )


def _require_same_substance(base: PackSkill, enhancer: PackSkill) -> None:
    if (enhancer.form, enhancer.body_path, enhancer.expands_to) != (base.form, base.body_path, base.expands_to):
        raise PackSkillViolation(f"skill {enhancer.id!r}: 'enhances' may not change the body or expansion of {base.id!r}")


def _parameter_shape(parameters: list[SkillParameter]) -> dict[str, bool]:
    return {parameter.name: parameter.required for parameter in parameters}


def _require_same_parameter_shape(base: PackSkill, enhancer: PackSkill) -> None:
    if _parameter_shape(base.parameters) != _parameter_shape(enhancer.parameters):
        raise PackSkillViolation(f"skill {enhancer.id!r}: 'enhances' may only change parameter defaults, not add, remove or re-require parameters")


def _require_narrowing(base: SkillInvocation, enhancer: SkillInvocation) -> None:
    widened = (
        (enhancer.user_invocable and not base.user_invocable)
        or (enhancer.model_invocable and not base.model_invocable)
        or not set(base.side_effects) <= set(enhancer.side_effects)
    )
    if widened:
        raise PackSkillViolation("'enhances' may only narrow invocation (never widen it or drop a declared side effect)")


__all__ = [
    "RESERVED_PREFIXES",
    "PackSkillViolation",
    "Tier",
    "apply_enhancement",
    "rendered_name",
    "validate_pack_skill",
]
