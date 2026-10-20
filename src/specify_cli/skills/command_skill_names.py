"""Single naming authority for the generated command skills (#6475, FR-002).

The command skills Spec Kitty generates into the shared ``.agents/skills/``
root used to be named ``spec-kitty.<command>``. The Agent Skills specification
only allows ``[a-z0-9-]`` in a skill ``name`` (and the folder name must equal
it), so the canonical name is now ``spec-kitty-<command>``. Every producer and
parser of that name, its ``SKILL.md`` path and the invocation tokens that refer
to it goes through this module; ``tests/architectural/test_command_skill_name_authority.py``
pins that no other module composes them.

Three rules shape the API:

* **Explicit command sets, never a prefix.** The canonical prefix
  ``spec-kitty-`` is shared with shipped charter skills (for example
  ``spec-kitty-implement-review`` sits beside the ``implement`` and ``review``
  commands), so a path or name is only ever recognised by exact match against
  an explicit ``commands`` iterable.
* **The legacy dotted form is a separate parser.** ``spec-kitty.<command>`` is
  recognised only through the ``legacy_*`` helpers, which exist so the rename
  migration and the installer can find and retire the old folders.
* **Agent-independent body rewrite.** :func:`rewrite_command_invocations` keeps
  the sigil of a token and changes only the name, so one rendered body serves
  every command-skill agent (the installer refuses differing bytes for one
  shared path).

Like :mod:`specify_cli.skills._agent_roster` this is a deliberately
**dependency-free leaf**: it imports nothing from ``specify_cli``. The command
tuple itself is owned by ``command_installer.CANONICAL_COMMANDS``; callers pass
it in, so this module never imports the installer (which imports the renderer,
which imports this module).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

__all__ = [
    "COMMAND_SKILLS_ROOT",
    "COMMAND_SKILL_PREFIX",
    "LEGACY_COMMAND_SKILL_PREFIX",
    "CommandSkillNameCollisionError",
    "assert_unique_command_skill_names",
    "command_skill_name",
    "command_skill_rel_path",
    "legacy_command_skill_name",
    "legacy_command_skill_names",
    "legacy_command_skill_rel_path",
    "parse_command_skill_rel_path",
    "parse_legacy_command_skill_rel_path",
    "rewrite_command_invocations",
    "skill_invocation_token",
]

#: Canonical name prefix of a generated command skill (Agent Skills grammar).
COMMAND_SKILL_PREFIX = "spec-kitty-"

#: Prefix of the pre-#6475 dotted command-skill names (read/retire only).
LEGACY_COMMAND_SKILL_PREFIX = "spec-kitty."

#: Shared project skill root the command skills are generated into (POSIX).
COMMAND_SKILLS_ROOT = ".agents/skills"

_SKILL_FILENAME = "SKILL.md"

#: Sigils that introduce an invocation token. ``/skill:`` (Pi) must be tried
#: before the bare ``/`` so the alternation keeps the whole sigil.
_INVOCATION_SIGILS = ("/skill:", "/", "$")

#: Sigils per skill-agent harness for UI tokens; other skill agents use ``/``.
_SKILL_AGENT_SIGILS = {"codex": "$", "pi": "/skill:"}


class CommandSkillNameCollisionError(ValueError):
    """A command-skill name collides with another command or a reserved skill name."""


def command_skill_name(command: str) -> str:
    """Return the canonical skill name ``spec-kitty-<command>``."""
    return f"{COMMAND_SKILL_PREFIX}{command}"


def legacy_command_skill_name(command: str) -> str:
    """Return the pre-#6475 dotted skill name ``spec-kitty.<command>``."""
    return f"{LEGACY_COMMAND_SKILL_PREFIX}{command}"


def legacy_command_skill_names(commands: Iterable[str]) -> frozenset[str]:
    """Return the dotted legacy names of *commands* (the old folder names)."""
    return frozenset(legacy_command_skill_name(command) for command in commands)


def _rel_path(skill_name: str) -> str:
    return f"{COMMAND_SKILLS_ROOT}/{skill_name}/{_SKILL_FILENAME}"


def command_skill_rel_path(command: str) -> str:
    """Return ``.agents/skills/spec-kitty-<command>/SKILL.md`` (POSIX, repo-relative)."""
    return _rel_path(command_skill_name(command))


def legacy_command_skill_rel_path(command: str) -> str:
    """Return ``.agents/skills/spec-kitty.<command>/SKILL.md`` (POSIX, repo-relative)."""
    return _rel_path(legacy_command_skill_name(command))


def parse_command_skill_rel_path(rel_path: str, commands: Iterable[str]) -> str | None:
    """Return the command whose canonical ``SKILL.md`` path is *rel_path*, else ``None``.

    Exact match against *commands* only: a charter skill such as
    ``.agents/skills/spec-kitty-implement-review/SKILL.md`` is never read as a
    command, and the legacy dotted form is not accepted here.
    """
    return next((command for command in commands if command_skill_rel_path(command) == rel_path), None)


def parse_legacy_command_skill_rel_path(rel_path: str, commands: Iterable[str]) -> str | None:
    """Return the command whose legacy dotted ``SKILL.md`` path is *rel_path*, else ``None``."""
    return next((command for command in commands if legacy_command_skill_rel_path(command) == rel_path), None)


def assert_unique_command_skill_names(commands: Iterable[str], reserved: Iterable[str]) -> None:
    """Raise :class:`CommandSkillNameCollisionError` on any command-skill name collision.

    A collision is a command whose canonical name is in *reserved* (shipped
    charter skills, built-in pack skills, retired skill names), or two commands
    mapping to one name.
    """
    reserved_names = frozenset(reserved)
    seen: dict[str, str] = {}
    for command in commands:
        name = command_skill_name(command)
        if name in reserved_names:
            raise CommandSkillNameCollisionError(f"command skill {name!r} (command {command!r}) collides with a reserved skill name")
        if name in seen:
            raise CommandSkillNameCollisionError(f"commands {seen[name]!r} and {command!r} both map to skill name {name!r}")
        seen[name] = command


def _invocation_pattern(commands: Iterable[str]) -> re.Pattern[str] | None:
    # Longest first, so ``tasks`` never claims the start of ``tasks-outline``.
    ordered = sorted(set(commands), key=lambda command: (-len(command), command))
    if not ordered:
        return None
    sigils = "|".join(re.escape(sigil) for sigil in _INVOCATION_SIGILS)
    names = "|".join(re.escape(command) for command in ordered)
    # Before the sigil: not a path/identifier character, so ``commands/spec-kitty.plan.md``,
    # ``https://x/spec-kitty.plan`` and ``foo$spec-kitty.plan`` stay untouched.
    # After the command: not a name character, and not a file extension
    # (``/spec-kitty.plan.md``), while a sentence-ending ``.`` still matches.
    return re.compile(
        rf"(?<![A-Za-z0-9_.:/$-])(?P<sigil>{sigils}){re.escape(LEGACY_COMMAND_SKILL_PREFIX)}"
        rf"(?P<command>{names})(?![A-Za-z0-9_-]|\.[A-Za-z0-9])"
    )


def rewrite_command_invocations(text: str, commands: Iterable[str]) -> str:
    """Rewrite dotted invocation tokens of *commands* in *text* to the skill name.

    ``/spec-kitty.<cmd>``, ``$spec-kitty.<cmd>`` and ``/skill:spec-kitty.<cmd>``
    become the same sigil followed by ``spec-kitty-<cmd>``. Only canonical
    commands on a token boundary are rewritten; ``spec-kitty.ai``,
    ``spec-kitty.analysis-report`` and file names such as
    ``.claude/commands/spec-kitty.plan.md`` are left alone. The result does not
    depend on the agent, so one body serves every command-skill agent.
    """
    pattern = _invocation_pattern(commands)
    if pattern is None:
        return text
    return pattern.sub(lambda match: f"{match['sigil']}{command_skill_name(match['command'])}", text)


def skill_invocation_token(agent_key: str, command: str, *, is_skill_agent: bool) -> str:
    """Return the token a user types to run *command* in *agent_key*'s harness (UI only).

    Skill agents invoke the skill by its canonical name (Codex ``$``, Pi
    ``/skill:``, others ``/``); slash-command agents keep ``/spec-kitty.<cmd>``
    because they invoke command files, whose names are unchanged (C-001).
    """
    if not is_skill_agent:
        return f"/{legacy_command_skill_name(command)}"
    return f"{_SKILL_AGENT_SIGILS.get(agent_key, '/')}{command_skill_name(command)}"
