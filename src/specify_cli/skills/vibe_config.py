"""Helpers for project-local Mistral Vibe configuration."""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
import json
import logging
import math
import tomllib

from specify_cli.session_presence.writers.markdown_rules import (
    PreparedPresenceFile,
    _atomic_write,
    observe_presence_path,
    presence_state,
    read_presence_bytes,
)
from specify_cli.tool_surface.operations import InputObservation

VIBE_SKILL_PATH = ".agents/skills"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreparedVibeConfig:
    """TOML-owner preparation, with exact bytes and confined input observations."""

    file: PreparedPresenceFile
    observations: tuple[InputObservation, ...]

    @property
    def execution_artifacts(self) -> tuple[tuple[str, str, str], ...]:
        return self.file.execution_artifacts


def prepare_project_skill_path(project_root: Path) -> PreparedVibeConfig:
    """Prepare the owned top-level entry without serializing unrelated TOML."""
    relative = ".vibe/config.toml"
    observations = observe_presence_path(project_root, relative)
    state = presence_state(observations[-1])
    if state.kind not in ("file", "absent"):
        raise ValueError("Native config destination is not a regular file")
    raw = read_presence_bytes(project_root / relative) if state.kind == "file" else b""
    text = raw.decode("utf-8")
    data = tomllib.loads(text)
    paths = data.get("skill_paths")
    if paths is not None and not (isinstance(paths, str) or isinstance(paths, list) and all(isinstance(p, str) for p in paths)):
        raise ValueError("Expected .vibe/config.toml skill_paths to be a string or list")
    if paths == VIBE_SKILL_PATH or isinstance(paths, list) and VIBE_SKILL_PATH in paths:
        desired = raw
    else:
        desired = _add_skill_path(text, paths).encode("utf-8")
        parsed = tomllib.loads(desired.decode("utf-8"))
        expected = dict(data)
        expected["skill_paths"] = ([paths] if isinstance(paths, str) else paths or []) + [VIBE_SKILL_PATH]
        if not _same_toml(parsed, expected):
            raise ValueError("Native config preparation changed an unowned TOML key")
    return PreparedVibeConfig(PreparedPresenceFile(relative, state, desired), observations)


def _same_toml(left: object, right: object) -> bool:
    """Compare validated TOML values, including legal non-reflexive NaNs."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_same_toml(value, right[key]) for key, value in left.items())
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_same_toml(a, b) for a, b in zip(left, right, strict=True))
    if isinstance(left, float) and isinstance(right, float) and math.isnan(left):
        return math.isnan(right)
    return bool(left == right)


def _add_skill_path(text: str, paths: object) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    if paths is None:
        return f'skill_paths = [".agents/skills"]{newline}' + text
    offset = 0
    lines = text.splitlines(keepends=True)
    index = 0
    while index < len(lines):
        statement = lines[index]
        start = offset
        index += 1
        offset += len(statement)
        if not statement.strip() or statement.lstrip().startswith("#"):
            continue
        if statement.lstrip().startswith("["):
            break
        while True:
            try:
                parsed = tomllib.loads(statement)
                break
            except tomllib.TOMLDecodeError:
                if index == len(lines):
                    raise
                statement += lines[index]
                offset += len(lines[index])
                index += 1
        if "skill_paths" not in parsed:
            continue
        value_start = statement.index("=") + 1
        while statement[value_start] in " \t":
            value_start += 1
        value_end = _toml_value_end(statement, value_start)
        if isinstance(paths, list):
            # Insert before the final bracket; retain every existing comment.
            insert = value_end - 1
            prefix = statement[value_start:insert]
            suffix = (" " if paths else "") + '".agents/skills"]'
            value = prefix + suffix
            try:
                tomllib.loads(statement[:value_start] + value + statement[value_end:])
            except tomllib.TOMLDecodeError:
                value = prefix + "," + suffix
        else:
            value = json.dumps([paths, VIBE_SKILL_PATH], ensure_ascii=False)
        return text[: start + value_start] + value + text[start + value_end :]
    raise ValueError("Cannot locate top-level skill_paths entry")


def _toml_value_end(text: str, start: int) -> int:
    """Locate a TOML string/array boundary, respecting quotes and comments."""
    quote = ""
    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if quote:
            if quote.startswith('"') and char == "\\":
                index += 2
                continue
            if text.startswith(quote, index):
                index += len(quote)
                if len(quote) == 3:
                    # TOML permits one/two content quotes adjoining the closing
                    # triple delimiter. The complete document was parsed first.
                    for _ in range(2):
                        if index < len(text) and text[index] == quote[0]:
                            index += 1
                quote = ""
                if depth == 0:
                    return index
                continue
        elif char in "'\"":
            quote = char * 3 if text.startswith(char * 3, index) else char
            index += len(quote)
            continue
        elif char == "#":
            end = text.find("\n", index)
            index = len(text) if end < 0 else end
            continue
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    raise ValueError("Unterminated skill_paths value")


def ensure_project_skill_path(project_root: Path, *, prepared: PreparedVibeConfig | None = None) -> None:
    """Ensure Vibe's project-local config discovers Spec Kitty's shared skills.

    Vibe's official discovery roots are ``.vibe/skills/`` and any custom paths
    listed in ``.vibe/config.toml``. Spec Kitty installs command skills into the
    shared ``.agents/skills/`` tree, so projects that configure Vibe need a
    matching ``skill_paths`` entry.
    """
    batch = prepared if prepared is not None else prepare_project_skill_path(project_root)
    if any(observe_presence_path(project_root, old.name)[-1] != old for old in batch.observations):
        raise ValueError("Native config precondition changed")
    if batch.file.changed:
        _atomic_write(project_root / batch.file.path, batch.file.content.decode("utf-8"), root=project_root, expected=batch.file.before)


def skill_path_configured(project_root: Path) -> bool:
    """Report whether ``.vibe/config.toml`` points ``skill_paths`` at the shared skills.

    The pointer is an independently missable part of the vibe command surface:
    ``.vibe/`` is gitignored with the rest of the agent surface
    (``gitignore_manager``), so a clone can lose it exactly like the shared
    skill files themselves. ``init``'s initialized-project check and ``doctor
    skills`` both read it through this one seam so the two diagnostics agree
    on what "ready" means (#4433).
    """
    config_path = project_root / ".vibe" / "config.toml"
    if not config_path.exists():
        return False

    try:
        raw = config_path.read_text(encoding="utf-8")
        data = tomllib.loads(raw) if raw.strip() else {}
    except Exception as exc:
        logger.debug("Failed to read %s: %s", config_path, exc)
        return False

    skill_paths = data.get("skill_paths")
    if isinstance(skill_paths, str):
        return skill_paths == VIBE_SKILL_PATH
    if isinstance(skill_paths, list):
        return VIBE_SKILL_PATH in [str(path) for path in skill_paths]
    return False
