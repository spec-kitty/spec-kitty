"""Pack-skill domain model (ADR 2026-09-27-1, FR-003).

A *pack skill* is a thin, parameterised entry point shared through a charter
pack. Two forms exist, discriminated by :attr:`PackSkill.form`:

* ``prompt`` -- carries a Markdown prompt body (``body_path``, relative to the
  ``*.skill.yaml`` file).
* ``wrapper`` -- a shorthand that expands to an existing command
  (``expands_to``), either a ``builtin:`` command or a ``cli:`` argv that must
  start with ``spec-kitty``.

Relationships to procedures/directives are DRG edges in the pack fragment, never
fields here (ADR 2026-07-26-1); ``overrides`` / ``enhances`` only name the
skill being replaced or narrowed.
"""

from __future__ import annotations

import re
import shlex
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SKILL_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")

#: Grammar of a skill namespace (the ``<namespace>-`` prefix a non-built-in skill
#: renders under): lowercase ASCII, starting with a letter, ``[a-z0-9]`` segments
#: joined by single ``-``, no trailing ``-``. Match with ``fullmatch``.
SKILL_NAMESPACE_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")

#: Longest accepted namespace; ``<namespace>-<id>`` stays far below a 255-byte file name.
SKILL_NAMESPACE_MAX_LENGTH = 32
BUILTIN_TARGET_PREFIX = "builtin:"
CLI_TARGET_PREFIX = "cli:"
CLI_ALLOWED_PROGRAM = "spec-kitty"
_SHELL_METACHARACTERS = frozenset(";&|<>$`\n\r")


def skill_namespace_violation(value: str) -> str | None:
    """Return why *value* is not a valid skill namespace, or ``None`` when it is.

    The namespace becomes a directory-name prefix in every project skill root, so
    it is refused -- never normalised -- unless it matches
    :data:`SKILL_NAMESPACE_PATTERN` within :data:`SKILL_NAMESPACE_MAX_LENGTH`.
    """
    if len(value) <= SKILL_NAMESPACE_MAX_LENGTH and SKILL_NAMESPACE_PATTERN.fullmatch(value):
        return None
    return (
        f"skill namespace {value!r} is not valid: it must be lowercase ASCII kebab-case "
        f"(letters and digits joined by single '-', starting with a letter, at most {SKILL_NAMESPACE_MAX_LENGTH} characters)"
    )


class SkillParameter(BaseModel):
    """One declared parameter of a pack skill."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    required: bool = False
    description: str = ""
    default: str | None = None


class SkillInvocation(BaseModel):
    """Who may invoke the skill; ``model_invocable`` is forced off by side effects."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_invocable: bool = True
    model_invocable: bool = True
    side_effects: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _force_model_invocable_off(cls, data: Any) -> Any:
        """A skill with declared side effects is never model-invocable."""
        if isinstance(data, dict) and data.get("side_effects"):
            return {**data, "model_invocable": False}
        return data


class SkillExpansion(BaseModel):
    """Expansion of a ``wrapper``-form skill."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    target: str = Field(min_length=1)
    args: str = ""

    @model_validator(mode="after")
    def _validate_target(self) -> SkillExpansion:
        """Accept ``builtin:<command>`` or ``cli:spec-kitty ...`` targets only."""
        if self.target.startswith(BUILTIN_TARGET_PREFIX):
            if not self.target.removeprefix(BUILTIN_TARGET_PREFIX).strip():
                raise ValueError("expands_to.target 'builtin:' needs a command name")
            return self
        if self.target.startswith(CLI_TARGET_PREFIX):
            self._validate_cli_target(self.target.removeprefix(CLI_TARGET_PREFIX))
            return self
        raise ValueError(f"expands_to.target {self.target!r} must start with '{BUILTIN_TARGET_PREFIX}' or '{CLI_TARGET_PREFIX}'")

    @staticmethod
    def _validate_cli_target(argv_text: str) -> None:
        if _SHELL_METACHARACTERS & set(argv_text):
            raise ValueError("expands_to cli target must be a plain argv (no shell metacharacters)")
        try:
            argv = shlex.split(argv_text)
        except ValueError as exc:
            raise ValueError(f"expands_to cli target is not a valid argv: {exc}") from exc
        if not argv or argv[0] != CLI_ALLOWED_PROGRAM:
            raise ValueError(f"expands_to cli target must be a '{CLI_ALLOWED_PROGRAM}' argv")


class PackSkill(BaseModel):
    """The aggregate root: one ``*.skill.yaml`` pack skill (URN ``skill:<id>``)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1.0"]
    id: str
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    triggers: list[str] = Field(default_factory=list)
    form: Literal["prompt", "wrapper"]
    body_path: str | None = None
    expands_to: SkillExpansion | None = None
    parameters: list[SkillParameter] = Field(default_factory=list)
    invocation: SkillInvocation = Field(default_factory=SkillInvocation)
    tools: list[str] = Field(default_factory=lambda: ["*"])
    version: str = "1.0.0"
    maintainers: list[str] = Field(default_factory=list)
    overrides: str | None = None
    enhances: str | None = None

    @model_validator(mode="after")
    def _validate_shape(self) -> PackSkill:
        """Enforce id shape, the form discriminator and augmentation exclusivity."""
        if not SKILL_ID_PATTERN.match(self.id):
            raise ValueError(f"skill id {self.id!r} must be lowercase kebab-case")
        self._validate_form()
        if self.overrides and self.enhances:
            raise ValueError("a skill may declare 'overrides' or 'enhances', not both")
        if self.id in (self.overrides, self.enhances):
            raise ValueError("'overrides'/'enhances' must name a different skill than the skill's own id")
        names = [parameter.name for parameter in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate parameter name(s) in skill {self.id!r}")
        return self

    def _validate_form(self) -> None:
        if self.form == "prompt":
            if not self.body_path:
                raise ValueError("prompt-form skill requires 'body_path'")
            if self.expands_to is not None:
                raise ValueError("prompt-form skill must not declare 'expands_to'")
        else:
            if self.expands_to is None:
                raise ValueError("wrapper-form skill requires 'expands_to'")
            if self.body_path:
                raise ValueError("wrapper-form skill must not declare 'body_path'")

    @property
    def is_augmentation(self) -> bool:
        """Whether this record augments another skill instead of standing alone."""
        return bool(self.overrides or self.enhances)


__all__ = [
    "PackSkill",
    "SkillExpansion",
    "SkillInvocation",
    "SkillParameter",
    "skill_namespace_violation",
]
