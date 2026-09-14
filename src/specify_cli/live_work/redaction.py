"""Live Work content safety — redaction, path policy, secret exclusion.

The content-safety rule (``decisions/HIC-LIVE-WORK-DURABLE-ZEITGEIST-2026-09-13.md``,
preserved by the 2026-09-14 NOW/DONE supersession): no secrets, credentials,
secret-bearing arguments, environment values, arbitrary terminal streams, or
private model reasoning are ever captured. This module is the single owner
of that policy for the capture layer:

* :func:`relativize_path` — repository-relative paths only; absolute paths,
  traversal, backslash separators, and control characters fail closed; and
  secret files (credential/key material by name) are *excluded* — they never
  enter a published frame or a log line, not even as a redacted placeholder.
* :func:`redact_command_summary` — a bounded, sanitized command summary:
  the program name and safe flags survive; token-bearing arguments,
  secret-named environment assignments, and high-entropy credential-shaped
  values are replaced with ``[redacted]``; raw output never enters at all.

Every adapter routes paths and command text through here before building an
:class:`~live_work.models.Observation`; the publisher additionally asserts
the redaction invariants on the projected wire attrs (defense in depth).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final
from collections.abc import Sequence

__all__ = [
    "EXCLUDED_FILE_PATTERNS",
    "MAX_SUMMARY_CHARS",
    "REDACTED",
    "RedactionResult",
    "is_excluded_path",
    "redact_command_summary",
    "relativize_path",
]


REDACTED: Final[str] = "[redacted]"
"""The one placeholder substituted for redacted content."""

MAX_SUMMARY_CHARS: Final[int] = 240
"""A sanitized command summary never exceeds the wire's per-attr bound."""


# Secret/credential files, matched against the path's basename and each
# segment. A path that matches is excluded outright (never observed, never
# logged, never published) — a redacted placeholder would still confirm the
# file exists and was touched.
_EXCLUDED_EXACT_NAMES: frozenset[str] = frozenset(
    {
        ".env",
        ".netrc",
        ".pypirc",
        ".npmrc",
        "credentials",
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "secrets.json",
        "secrets.yaml",
        "secrets.yml",
        "secrets.toml",
    }
)
_EXCLUDED_GLOBS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern)
    for pattern in (
        r"^\.env\..+$",
        r"^.*\.(pem|key|p12|pfx|kdbx|keystore|jks)$",
        r"^id_(rsa|dsa|ecdsa|ed25519)[^/]*$",
        r"^credentials\.(json|ya?ml|toml|ini)$",
        r"^.*\.secret$",
        r"^service[-_]?account[^/]*\.json$",
    )
)
EXCLUDED_FILE_PATTERNS: Final[tuple[str, ...]] = (
    ".env and .env.*",
    "*.pem / *.key / *.p12 / *.pfx / *.kdbx / *.keystore / *.jks",
    "id_rsa / id_dsa / id_ecdsa / id_ed25519 (and openSSH suffix forms)",
    "credentials.{json,yaml,toml,ini}, secrets.{json,yaml,toml}",
    "*.secret, service-account*.json",
    ".netrc / .pypirc / .npmrc",
)
"""Human-readable record of the excluded-file policy (capability matrix)."""


# Secret-shaped argument names: `--token=…`, `-p …` is too generic to treat
# as secret (it is also `--publish`-style prefixes), so only unambiguous
# long names and assignments are matched.
_SECRET_ARG_NAME_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)(?:^|[-_])(token|secret|password|passwd|pwd|api[_-]?key|auth|bearer|"
    r"credential|private[_-]?key|access[_-]?key|session[_-]?id)(?:$|[-_=])"
)
_ENV_ASSIGNMENT_RE: Final[re.Pattern[str]] = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
# Credential-shaped bare values: known prefixes plus high-entropy blobs.
_CREDENTIAL_PREFIXES: Final[tuple[str, ...]] = (
    "sk-",
    "ghp_",
    "gho_",
    "ghu_",
    "ghs_",
    "ghr_",
    "github_pat_",
    "xoxb-",
    "xoxp-",
    "AKIA",
    "AIza",
)
_HIGH_ENTROPY_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9+/_=-]{24,}$")

_FILE_PATH_MAX: Final[int] = 240


@dataclass(frozen=True)
class RedactionResult:
    """The outcome of one redaction/policy decision.

    ``value`` is the sanitized result when ``excluded`` is false; when
    ``excluded`` is true the value is ``None`` and ``reason`` names the
    policy that excluded it (for the caller's *aggregate* accounting only —
    an excluded item's own content is never carried anywhere).
    """

    value: str | None
    excluded: bool = False
    reason: str | None = None


def is_excluded_path(relative_path: str) -> bool:
    """True when *relative_path* is secret/credential material by name."""
    segments = relative_path.split("/")
    for segment in segments:
        if segment in _EXCLUDED_EXACT_NAMES:
            return True
        for pattern in _EXCLUDED_GLOBS:
            if pattern.match(segment):
                return True
    return False


def relativize_path(path: str, repo_root: Path) -> RedactionResult:
    """Project one filesystem path onto a safe repository-relative name.

    Fails closed (excluded) on: absolute paths outside the repository,
    traversal (``..``), backslash separators, control characters, and the
    excluded (secret) file set. Accepts real filenames — spaces and
    Unicode included.
    """
    if not path or any(ord(char) < 0x20 or ord(char) == 0x7F for char in path):
        return RedactionResult(None, excluded=True, reason="empty or control-character path")
    if "\\" in path:
        return RedactionResult(None, excluded=True, reason="backslash path separator")
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            relative = candidate.resolve().relative_to(Path(repo_root).resolve())
        except ValueError:
            return RedactionResult(None, excluded=True, reason="absolute path outside repository")
        relative_str = relative.as_posix()
    else:
        relative_str = PurePosixPath(path).as_posix()
    if relative_str in ("", "."):
        return RedactionResult(None, excluded=True, reason="empty relative path")
    if any(segment in ("", ".", "..") for segment in relative_str.split("/")):
        return RedactionResult(None, excluded=True, reason="traversal segment in path")
    if len(relative_str) > _FILE_PATH_MAX:
        return RedactionResult(None, excluded=True, reason="path exceeds the 240-char bound")
    if is_excluded_path(relative_str):
        return RedactionResult(None, excluded=True, reason="secret/credential file excluded by policy")
    return RedactionResult(relative_str)


def _is_secret_arg_name(token: str) -> bool:
    stripped = token.lstrip("-")
    return bool(_SECRET_ARG_NAME_RE.search(stripped)) or stripped.lower() in {
        "authorization",
        "proxy-authorization",
        "cookie",
    }


def _is_credential_shaped(value: str) -> bool:
    for prefix in _CREDENTIAL_PREFIXES:
        if value.startswith(prefix):
            return True
    return bool(_HIGH_ENTROPY_RE.match(value)) and len(set(value)) >= 8


def redact_command_summary(command: str | Sequence[str]) -> RedactionResult:
    """Build a bounded, sanitized command summary from a command string/list.

    The program name and safe arguments survive; values of secret-named
    options, secret-named environment assignments, and credential-shaped
    bare values become ``[redacted]``. The summary is bounded to
    :data:`MAX_SUMMARY_CHARS` (truncation marks its own tail with ``…`` so a
    fragment is never mistaken for the whole).
    """
    tokens = command.split() if isinstance(command, str) else [str(part) for part in command]
    if not tokens:
        return RedactionResult(None, excluded=True, reason="empty command")

    sanitized: list[str] = []
    expect_value_redaction = False
    for token in tokens:
        # A value consumed by a previous secret-named flag.
        if expect_value_redaction:
            sanitized.append(REDACTED)
            expect_value_redaction = False
            continue
        # Environment-assignment prefix (FOO=bar cmd): keep a secret-named
        # assignment's key, redact its value; keep a benign one whole.
        assignment = _ENV_ASSIGNMENT_RE.match(token)
        if assignment is not None:
            key, value = assignment.group(1), assignment.group(2)
            if _is_secret_arg_name(key) or "=" not in token or _is_credential_shaped(value):
                sanitized.append(f"{key}={REDACTED}")
            else:
                sanitized.append(token)
            continue
        # --flag=value form.
        if token.startswith("-") and "=" in token:
            name, value = token.split("=", 1)
            if _is_secret_arg_name(name) or _is_credential_shaped(value):
                sanitized.append(f"{name}={REDACTED}")
            else:
                sanitized.append(token)
            continue
        # Secret-named flag: redact the value whether inline or next token.
        if token.startswith("-") and _is_secret_arg_name(token):
            sanitized.append(token)
            expect_value_redaction = True
            continue
        if _is_credential_shaped(token):
            sanitized.append(REDACTED)
            continue
        sanitized.append(token)

    summary = " ".join(sanitized)
    if len(summary) > MAX_SUMMARY_CHARS:
        summary = summary[: MAX_SUMMARY_CHARS - 1] + "…"
    return RedactionResult(summary)
