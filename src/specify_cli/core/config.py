"""Configuration constants shared across the Spec Kitty CLI.

Also the single authority for agents' documented user-global config roots
(``agent_user_config_root``), which read the environment at call time.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from pathlib import Path

from kernel.errors import GuardedReadError
from kernel.paths import is_windows

AI_CHOICES = {
    "copilot": "GitHub Copilot",
    "claude": "Claude Code",
    "gemini": "Gemini CLI",
    "cursor": "Cursor",
    "qwen": "Qwen Code",
    "opencode": "opencode",
    "codex": "Codex CLI",
    "windsurf": "Windsurf",
    "kilocode": "Kilo Code",
    "auggie": "Auggie CLI",
    # "roo" was removed — Roo Code shut down on 2026-05-15 (C-007)
    "q": "Amazon Q Developer CLI (legacy; use 'kiro')",
    "kiro": "Kiro CLI (formerly Amazon Q Developer CLI)",
    "antigravity": "Google Antigravity",
    "vibe": "Mistral Vibe",
    "pi": "Pi",
    "letta": "Letta Code",
    "llxprt": "LLxprt Code",
}

MISSION_CHOICES = {
    "software-dev": "Software Dev Kitty",
    "research": "Deep Research Kitty",
}

DEFAULT_MISSION_KEY: str = "software-dev"

AGENT_TOOL_REQUIREMENTS: dict[str, tuple[str, str]] = {
    "claude": ("claude", "https://docs.anthropic.com/en/docs/claude-code/setup"),
    "gemini": ("gemini", "https://github.com/google-gemini/gemini-cli"),
    "qwen": ("qwen", "https://github.com/QwenLM/qwen-code"),
    "opencode": ("opencode", "https://opencode.ai"),
    "codex": ("codex", "https://github.com/openai/codex"),
    "auggie": ("auggie", "https://docs.augmentcode.com/cli/setup-auggie/install-auggie-cli"),
    "q": ("q", "https://aws.amazon.com/developer/learning/q-developer-cli/"),
    "vibe": ("vibe", "https://github.com/mistralai/mistral-vibe"),
    "kiro": ("kiro-cli", "https://kiro.dev/docs/cli/"),
    "pi": ("pi", "https://pi.dev/docs/latest"),
    "letta": ("letta", "https://docs.letta.com/letta-code/cli/"),
    "llxprt": ("llxprt", "https://github.com/vybestack/llxprt-code"),
}

SCRIPT_TYPE_CHOICES = {"sh": "POSIX Shell (bash/zsh)", "ps": "PowerShell"}

DEFAULT_TEMPLATE_REPO = "spec-kitty/spec-kitty"

# IDE-integrated agents that don't require CLI installation
IDE_AGENTS = {"cursor", "windsurf", "copilot", "kilocode", "antigravity"}

AGENT_COMMAND_CONFIG: dict[str, dict[str, str]] = {
    "claude": {"dir": ".claude/commands", "ext": "md", "arg_format": "$ARGUMENTS"},
    "gemini": {"dir": ".gemini/commands", "ext": "toml", "arg_format": "{{args}}"},
    "copilot": {"dir": ".github/prompts", "ext": "prompt.md", "arg_format": "$ARGUMENTS"},
    "cursor": {"dir": ".cursor/commands", "ext": "md", "arg_format": "$ARGUMENTS"},
    "qwen": {"dir": ".qwen/commands", "ext": "toml", "arg_format": "{{args}}"},
    "opencode": {"dir": ".opencode/command", "ext": "md", "arg_format": "$ARGUMENTS"},
    "windsurf": {"dir": ".windsurf/workflows", "ext": "md", "arg_format": "$ARGUMENTS"},
    "kilocode": {"dir": ".kilocode/workflows", "ext": "md", "arg_format": "$ARGUMENTS"},
    "auggie": {"dir": ".augment/commands", "ext": "md", "arg_format": "$ARGUMENTS"},
    # "roo" removed — Roo Code shut down on 2026-05-15 (C-007)
    "q": {"dir": ".amazonq/prompts", "ext": "md", "arg_format": "$ARGUMENTS"},
    "kiro": {"dir": ".kiro/prompts", "ext": "md", "arg_format": "$ARGUMENTS"},
    # "antigravity" removed (#6470) — Antigravity stopped reading .agent/workflows on
    # 2026-10-19; it is a command-skill agent (skills._agent_roster) served from
    # .agents/skills/ and keeps its AI_CHOICES / IDE_AGENTS / AGENT_SKILL_CONFIG rows.
    "llxprt": {"dir": ".llxprt/commands", "ext": "toml", "arg_format": "{{args}}"},
}


#: Project-local config directory of each agent that documents its own
#: user-global config root. Only paths beneath this directory move with the
#: root; a shared root such as ``.agents/skills`` always stays under ``$HOME``.
AGENT_PROJECT_CONFIG_DIRS: dict[str, str] = {
    "claude": ".claude",
    "opencode": ".opencode",
    "llxprt": ".llxprt",
}
CLAUDE_CONFIG_DIR_ENV = "CLAUDE_CONFIG_DIR"
OPENCODE_CONFIG_DIR_ENV = "OPENCODE_CONFIG_DIR"
LLXPRT_CONFIG_HOME_ENV = "LLXPRT_CONFIG_HOME"
_XDG_CONFIG_HOME_ENV = "XDG_CONFIG_HOME"


class RelativeAgentConfigRootError(GuardedReadError):
    """An agent config-root variable holds a relative path (#7709).

    A relative value would resolve against the directory the command runs in,
    so a run inside a project would write a stray tree into that project.
    Subclasses ``GuardedReadError`` so the CLI error hook prints it as one line
    and exits 1, never a traceback.
    """

    def __init__(self, name: str, value: str) -> None:
        super().__init__(
            f"{name} is set to the relative path {value!r}; set it to an absolute path "
            f"(for example {name}=$HOME/{value}) or unset it."
        )
        self.name = name
        self.value = value


_STRICT_ROOT_ENVS = frozenset({CLAUDE_CONFIG_DIR_ENV, OPENCODE_CONFIG_DIR_ENV, LLXPRT_CONFIG_HOME_ENV})


def _env_dir(name: str) -> Path | None:
    value = os.environ.get(name)
    if not value:
        return None
    path = Path(value).expanduser()
    if name in _STRICT_ROOT_ENVS and not path.is_absolute():
        raise RelativeAgentConfigRootError(name, value)
    return path


def _llxprt_user_config_root() -> Path:
    # LLxprt resolves its root via envPaths('llxprt-code')
    # (packages/storage/src/config/path-resolver.ts); ~/.llxprt is migrated away.
    custom = _env_dir(LLXPRT_CONFIG_HOME_ENV)
    if custom is not None:
        return custom
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Preferences" / "llxprt-code"
    if is_windows():
        return Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / "llxprt-code" / "Config"
    xdg = _env_dir(_XDG_CONFIG_HOME_ENV)
    return (xdg if xdg is not None else Path.home() / ".config") / "llxprt-code"


def _claude_user_config_root() -> Path:
    custom = _env_dir(CLAUDE_CONFIG_DIR_ENV)
    return custom if custom is not None else Path.home() / AGENT_PROJECT_CONFIG_DIRS["claude"]


def _opencode_user_config_root() -> Path:
    custom = _env_dir(OPENCODE_CONFIG_DIR_ENV)
    if custom is not None:
        return custom
    xdg = _env_dir(_XDG_CONFIG_HOME_ENV)
    return (xdg if xdg is not None else Path.home() / ".config") / "opencode"


def agent_user_config_root(agent_key: str) -> Path | None:
    """Return the agent's documented user-global config root, or ``None`` when it has none.

    The single authority for these roots (#7701): user-global commands and the
    agent's own skill roots resolve beneath it.

    - ``claude``: ``$CLAUDE_CONFIG_DIR``, else ``~/.claude``
    - ``opencode``: ``$OPENCODE_CONFIG_DIR``, else ``$XDG_CONFIG_HOME/opencode``, else ``~/.config/opencode``
    - ``llxprt``: ``$LLXPRT_CONFIG_HOME``, else the platform config directory for ``llxprt-code``

    An empty variable counts as unset. Agents without a documented root
    return ``None``; their user-global paths mirror the project path under ``$HOME``.
    """
    if agent_key == "claude":
        return _claude_user_config_root()
    if agent_key == "opencode":
        return _opencode_user_config_root()
    if agent_key == "llxprt":
        return _llxprt_user_config_root()
    return None


def user_global_path_for_project_path(agent_key: str, project_rel: str) -> Path:
    """Map an agent's project-relative path (``.claude/skills``) to its user-global location.

    A path beneath the agent's own project config directory moves under
    :func:`agent_user_config_root`; any other path (a shared root such as
    ``.agents/skills``) mirrors the project path under ``$HOME``.
    """
    parts = Path(project_rel.strip("/")).parts
    root = agent_user_config_root(agent_key)
    if root is not None and parts and parts[0] == AGENT_PROJECT_CONFIG_DIRS.get(agent_key):
        return root.joinpath(*parts[1:])
    return Path.home().joinpath(*parts)


def configured_slash_agents(agent_keys: Iterable[str]) -> tuple[str, ...]:
    """Return the slash-command agents among *agent_keys*, in input order, without duplicates.

    A slash-command agent is one with an :data:`AGENT_COMMAND_CONFIG` row. Use it to
    split a configured agent *list* into its slash-command half (#6470:
    ``antigravity`` is configured but has no row, so it is never routed to a
    command-file writer). Code that asks about a single key (a lookup, a guard that
    raises, a render branch) tests membership in ``AGENT_COMMAND_CONFIG`` directly,
    which is the same rule. Unknown keys are dropped.
    """
    return tuple(dict.fromkeys(key for key in agent_keys if key in AGENT_COMMAND_CONFIG))


# Skill installation classes (PRD section 6)
SKILL_CLASS_SHARED: str = "shared-root-capable"
SKILL_CLASS_NATIVE: str = "native-root-required"
SKILL_CLASS_WRAPPER: str = "wrapper-only"

AGENT_SKILL_CONFIG: dict[str, dict[str, str | list[str] | None]] = {
    "claude":       {"class": SKILL_CLASS_NATIVE,  "skill_roots": [".claude/skills/"]},
    "copilot":      {"class": SKILL_CLASS_SHARED,  "skill_roots": [".agents/skills/", ".github/skills/"]},
    "gemini":       {"class": SKILL_CLASS_SHARED,  "skill_roots": [".agents/skills/", ".gemini/skills/"]},
    "cursor":       {"class": SKILL_CLASS_SHARED,  "skill_roots": [".agents/skills/", ".cursor/skills/"]},
    "qwen":         {"class": SKILL_CLASS_NATIVE,  "skill_roots": [".qwen/skills/"]},
    "opencode":     {"class": SKILL_CLASS_SHARED,  "skill_roots": [".agents/skills/", ".opencode/skills/"]},
    "windsurf":     {"class": SKILL_CLASS_SHARED,  "skill_roots": [".agents/skills/", ".windsurf/skills/"]},
    "codex":        {"class": SKILL_CLASS_SHARED,  "skill_roots": [".agents/skills/"]},
    "vibe":         {"class": SKILL_CLASS_SHARED,  "skill_roots": [".agents/skills/"]},
    "pi":           {"class": SKILL_CLASS_SHARED,  "skill_roots": [".agents/skills/", ".pi/skills/"]},
    "letta":        {"class": SKILL_CLASS_SHARED,  "skill_roots": [".agents/skills/"]},
    "kilocode":     {"class": SKILL_CLASS_NATIVE,  "skill_roots": [".kilocode/skills/"]},
    "auggie":       {"class": SKILL_CLASS_SHARED,  "skill_roots": [".agents/skills/", ".augment/skills/"]},
    # "roo" removed — Roo Code shut down on 2026-05-15 (C-007)
    "q":            {"class": SKILL_CLASS_WRAPPER, "skill_roots": None},
    "kiro":         {"class": SKILL_CLASS_SHARED,  "skill_roots": [".agents/skills/", ".kiro/skills/"]},
    "antigravity":  {"class": SKILL_CLASS_SHARED,  "skill_roots": [".agents/skills/", ".agent/skills/"]},
    # LLxprt Code reads the cross-tool .agents/skills/ standard alongside its own
    # .llxprt/skills/ root at the project tier (.agents/skills/ wins), and
    # ~/.agents/skills/ plus <global-config>/skills/ (macOS:
    # ~/Library/Preferences/llxprt-code/skills/) at the user-global tier.
    "llxprt":       {"class": SKILL_CLASS_SHARED,  "skill_roots": [".agents/skills/", ".llxprt/skills/"]},
}

BANNER = """
`````````````````````````````````````````````````````````

           ▄█▄_                            ╓▄█_
          ▐█ └▀█▄_                      ▄█▀▀ ╙█
          █"    `▀█▄                  ▄█▀     █▌
         ▐█        ▀█▄▄▄██████████▄▄▄█"       ▐█
         ║█          "` ╟█  ╫▌  █" '"          █
         ║█              ▀  ╚▀  ▀             J█
          █                                   █▌
          █▀   ,▄█████▄           ,▄█████▄_   █▌
         █▌  ▄█"      "██       ╓█▀      `▀█_  █▌
        ▐█__▐▌    ▄██▄  ╙█_____╒█   ▄██,   '█__'█
        █▀▀▀█M    ████   █▀╙\"\"\"██  ▐████    █▀▀"█▌
        █─  ╟█    ╙▀▀"  ██      █╕  ╙▀▀    ╓█   ║▌
   ╓▄▄▄▄█▌,_ ╙█▄_    _▄█▀╒██████ ▀█╥     ▄█▀ __,██▄▄▄▄
        ╚█'`"  `╙▀▀▀▀▀"   `▀██▀    "▀▀▀▀▀"   ""▐█
     _,▄▄███▀               █▌              ▀▀███▄▄,_
    ▀"`   ▀█_         '▀█▄▄█▀▀█▄▄█▀          ▄█"  '"▀"
           ╙██_                            ▄█▀
             └▀█▄_                      ,▓█▀
                └▀▀██▄,__        __╓▄██▀▀
                     `"▀▀▀▀▀▀▀▀▀▀▀╙"`

`````````````````````````````````````````````````````````
"""

__all__ = [
    "AI_CHOICES",
    "MISSION_CHOICES",
    "DEFAULT_MISSION_KEY",
    "AGENT_TOOL_REQUIREMENTS",
    "SCRIPT_TYPE_CHOICES",
    "DEFAULT_TEMPLATE_REPO",
    "AGENT_COMMAND_CONFIG",
    "configured_slash_agents",
    "IDE_AGENTS",
    "SKILL_CLASS_SHARED",
    "SKILL_CLASS_NATIVE",
    "SKILL_CLASS_WRAPPER",
    "AGENT_SKILL_CONFIG",
    "BANNER",
]
