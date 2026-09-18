"""Run user-configured commands without ``shell=True``.

POSIX commands keep their historical shell semantics through an explicit
``sh -c`` argv. Windows runs simple commands without ``cmd.exe`` and fails
closed when POSIX shell syntax is detected.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from collections.abc import Mapping
from pathlib import Path

from kernel.paths import is_windows


class ConfiguredCommandUnsupported(RuntimeError):
    """Raised when a configured command cannot run on the current platform."""


_ENV_ASSIGNMENT_RE = re.compile(r"^\s*[A-Za-z_][A-Za-z0-9_]*=")


def _has_unquoted_posix_shell_syntax(command: str) -> bool:
    """Return True when command uses operators that require a POSIX shell."""
    in_single = False
    in_double = False
    escaped = False

    for index, char in enumerate(command):
        if escaped:
            escaped = False
            continue
        if char == "\\" and not in_single:
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if in_single:
            continue
        if char == "$":
            next_char = command[index + 1] if index + 1 < len(command) else ""
            if next_char in "({" or next_char == "_" or next_char.isalpha():
                return True
        if in_double:
            continue
        if char in "\n|&;<>`!*?[":
            return True
    return bool(_ENV_ASSIGNMENT_RE.match(command))


def _uses_posix_single_quotes(command: str) -> bool:
    """Detect single-quoted argv syntax that ``cmd.exe`` does not honor."""
    in_double = False
    escaped = False
    for char in command:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_double = not in_double
            continue
        if char == "'" and not in_double:
            return True
    return False


def _unsupported_windows_message() -> str:
    return (
        "Configured command uses POSIX shell syntax that is not supported on Windows. "
        "Use a native Windows command or a simple argv-style command without pipes, "
        "redirection, environment assignments, control operators, command expansion, "
        "backticks, or single-quoted arguments."
    )


def _run_args(
    args: str | list[str],
    *,
    cwd: str | Path,
    capture_output: bool,
    text: bool,
    check: bool,
    timeout: float | None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - command is explicit user/project configuration.
        args,
        cwd=str(cwd),
        capture_output=capture_output,
        text=text,
        check=check,
        timeout=timeout,
        env=dict(env) if env is not None else None,
    )


def _substitution_env_name(key: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]", "_", key).upper()
    return f"SPEC_KITTY_CMD_{normalized}"


def _format_shell_template_with_env(
    command_template: str,
    substitutions: Mapping[str, str],
) -> tuple[str, dict[str, str]]:
    """Replace ``{name}`` placeholders with shell-safe environment references."""
    env_names = {key: _substitution_env_name(key) for key in substitutions}
    env = {env_names[key]: value for key, value in substitutions.items()}
    placeholders = {f"{{{key}}}": key for key in substitutions}

    formatted: list[str] = []
    index = 0
    in_single = False
    in_double = False
    escaped = False
    while index < len(command_template):
        matched_key: str | None = None
        matched_placeholder = ""
        for placeholder, key in placeholders.items():
            if command_template.startswith(placeholder, index):
                matched_key = key
                matched_placeholder = placeholder
                break

        if matched_key is not None:
            env_name = env_names[matched_key]
            if in_single:
                formatted.append(f"'\"${{{env_name}}}\"'")
            elif in_double:
                formatted.append(f"${{{env_name}}}")
            else:
                formatted.append(f'"${{{env_name}}}"')
            index += len(matched_placeholder)
            escaped = False
            continue

        char = command_template[index]
        formatted.append(char)
        if escaped:
            escaped = False
        elif char == "\\" and not in_single:
            escaped = True
        elif char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        index += 1

    return "".join(formatted), env


def run_configured_command(
    command: str,
    *,
    cwd: str | Path,
    capture_output: bool = True,
    text: bool = True,
    check: bool = False,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a user/config-authored command without ``shell=True``."""
    if is_windows():
        requires_posix_shell = _has_unquoted_posix_shell_syntax(command)
        if requires_posix_shell or _uses_posix_single_quotes(command):
            raise ConfiguredCommandUnsupported(_unsupported_windows_message())
        args: str | list[str] = command
    else:
        args = ["sh", "-c", command]

    return _run_args(
        args,
        cwd=cwd,
        capture_output=capture_output,
        text=text,
        check=check,
        timeout=timeout,
    )


def build_shell_command_with_substitutions(
    command_template: str,
    substitutions: Mapping[str, str | Path],
) -> list[str]:
    """Render a configured command template into a self-contained ``["sh", "-c", ...]`` argv.

    For callers that can only return a plain argv (no side channel for an
    ``env=`` mapping alongside it) — e.g. ``ScopeSource.test_command() ->
    list[str] | None`` (issue #3612): ``{name}`` placeholders are substituted
    with safely shell-quoted literal values via inline ``export`` statements
    prepended to the rendered command, rather than requiring the caller to
    also thread a separate environment dict through to ``subprocess.run``.
    Running the result through ``sh -c`` (POSIX only — see
    :func:`run_configured_command_template` for the Windows fallback shape)
    also means ``$VAR``/``~`` already present in the configured command
    itself expand normally, matching the shell semantics
    :func:`run_configured_command` already gives POSIX callers.

    Reuses :func:`_format_shell_template_with_env`'s placeholder-scanning
    (the same quote-aware scanner ``run_configured_command_template`` uses)
    so both callers agree on placeholder syntax and quoting — only how the
    substituted values are DELIVERED to the shell (inline ``export`` vs. a
    separate ``env=`` mapping) differs.

    Raises :class:`ConfiguredCommandUnsupported` on ``win32`` — there is no
    ``sh`` to hand a self-contained argv to; callers there must fall back to
    :func:`run_configured_command_template`'s ``.format()`` shape instead.
    """
    if is_windows():
        raise ConfiguredCommandUnsupported(
            "build_shell_command_with_substitutions requires a POSIX shell (sh -c) and has no Windows equivalent; use run_configured_command_template instead."
        )
    # Only feed keys the template actually references to the scanner — a
    # substitution the template never uses (e.g. a plain command with no
    # {output_file} placeholder at all) must not grow an unused `export`
    # prefix onto every rendered command.
    raw_substitutions = {key: str(value) for key, value in substitutions.items() if f"{{{key}}}" in command_template}
    if not raw_substitutions:
        return ["sh", "-c", command_template]
    shell_command, substitution_env = _format_shell_template_with_env(command_template, raw_substitutions)
    exports = "; ".join(f"export {name}={shlex.quote(value)}" for name, value in substitution_env.items())
    return ["sh", "-c", f"{exports}; {shell_command}"]


def run_configured_command_template(
    command_template: str,
    substitutions: Mapping[str, str | Path],
    *,
    cwd: str | Path,
    capture_output: bool = True,
    text: bool = True,
    check: bool = False,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a configured command template with shell-safe placeholder handling."""
    raw_substitutions = {key: str(value) for key, value in substitutions.items()}
    env: Mapping[str, str] | None = None
    if is_windows():
        requires_posix_shell = _has_unquoted_posix_shell_syntax(command_template)
        if requires_posix_shell or _uses_posix_single_quotes(command_template):
            raise ConfiguredCommandUnsupported(_unsupported_windows_message())
        try:
            template_args = shlex.split(command_template)
        except ValueError as exc:
            raise ConfiguredCommandUnsupported(f"Configured command could not be parsed: {exc}") from exc
        args: str | list[str] = [arg.format(**raw_substitutions) for arg in template_args]
    else:
        shell_command, substitution_env = _format_shell_template_with_env(
            command_template,
            raw_substitutions,
        )
        env = {**os.environ, **substitution_env}
        args = ["sh", "-c", shell_command]

    return _run_args(
        args,
        cwd=cwd,
        capture_output=capture_output,
        text=text,
        check=check,
        timeout=timeout,
        env=env,
    )
