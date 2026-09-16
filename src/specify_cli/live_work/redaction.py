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
  secret-named environment assignments, ``Bearer`` tokens (bare or inside
  ``-H``/``--header`` header values), basic-auth ``user:pass`` values after
  ``-u``/``--user``, JWT-shaped dotted tokens, and URL userinfo
  (``https://user:token@host``) are replaced with ``[redacted]``; raw output
  never enters at all.

Every adapter routes paths and command text through here before building an
:class:`~live_work.models.Observation`; the publisher additionally asserts
the redaction invariants on the projected wire attrs (defense in depth).
"""

from __future__ import annotations

import re
import shlex
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
    "secret_material_reason",
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
# JWT shape: dotted base64url segments (header.payload.signature). Dots stay
# out of _HIGH_ENTROPY_RE's alphabet on purpose — ordinary dotted paths
# (src/pkg/module.py) share it — while a JWT never carries a path separator.
_JWT_SHAPE_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2,}$")
# `Bearer <token>` in any position (squad fix round, #4353: the leading quote
# and the JWT's dots defeated every earlier branch).
_BEARER_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"(?i)\bbearer\s+\S+")
# Basic-auth `user:pass` — only ever redacted as the value of -u/--user,
# never as a bare token (host:port and key:value args share the shape).
_BASIC_AUTH_RE: Final[re.Pattern[str]] = re.compile(r"^[^/\s:]+:[^/\s]+$")
# URL userinfo (https://user:token@host/) — the credential travels before
# the `@`, so only that slice is replaced.
_URL_USERINFO_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9._~%-]+:[^/@\s]+@")
# Secret-bearing header names: the whole value after the colon is a
# credential, so none of it survives.
_SECRET_HEADER_NAMES: Final[frozenset[str]] = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "x-auth-token",
        "x-session-token",
    }
)
# curl-style flags whose next/inline value is credentials (-u/--user) or a
# header (-H/--header) — classified by shape, not unconditionally.
_CREDENTIAL_VALUE_FLAGS: Final[frozenset[str]] = frozenset({"u", "user"})
_HEADER_VALUE_FLAGS: Final[frozenset[str]] = frozenset({"h", "header"})

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


def _strip_quotes(token: str) -> str:
    """Drop one pair of matching surrounding quotes (shell-quoted argument)."""
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    return token


def _is_high_entropy(value: str) -> bool:
    if len(set(value)) < 8:
        return False
    if _HIGH_ENTROPY_RE.match(value):
        return True
    return bool(_JWT_SHAPE_RE.match(value)) and len(value) >= 24


def _is_credential_shaped(value: str) -> bool:
    for prefix in _CREDENTIAL_PREFIXES:
        if value.startswith(prefix):
            return True
    return _is_high_entropy(value)


def _is_basic_auth_shaped(value: str) -> bool:
    return bool(_BASIC_AUTH_RE.match(value))


def _sanitize_header_value(value: str) -> str:
    """Redact the credential inside one header value; benign headers survive.

    A secret-named header (``Authorization: …``) keeps its name but loses the
    whole value after the colon; a Bearer token anywhere else in the value
    redacts the value outright.
    """
    name, sep, _rest = value.partition(":")
    if sep and name.strip().lower() in _SECRET_HEADER_NAMES:
        return f"{name.strip()}: {REDACTED}"
    if _BEARER_TOKEN_RE.search(value):
        return REDACTED
    return value


def _redact_url_userinfo(token: str) -> str:
    """Replace ``user:pass@`` inside a URL with ``[redacted]@``; the rest survives."""
    return _URL_USERINFO_RE.sub(f"{REDACTED}@", token)


def _tokenize(command: str | Sequence[str]) -> list[str]:
    """Shell-faithful tokenization: a quoted argument arrives as one token."""
    if not isinstance(command, str):
        return [str(part) for part in command]
    try:
        return shlex.split(command)
    except ValueError:
        # Unbalanced quotes: redaction itself must never fail. Whitespace
        # splitting still classifies every fragment on its quote-stripped form.
        return command.split()


def _sanitize_assignment(bare: str, assignment: re.Match[str]) -> str:
    """``KEY=value``: a secret-named key or credential-shaped value redacts."""
    key, value = assignment.group(1), assignment.group(2)
    if _is_secret_arg_name(key) or _is_credential_shaped(_strip_quotes(value)):
        return f"{key}={REDACTED}"
    return bare


def _sanitize_inline_flag(bare: str, token: str) -> str:
    """``--flag=value``: secret/credential values redact, header values sanitize."""
    name, value = bare.split("=", 1)
    flag = name.lstrip("-").lower()
    if flag in _HEADER_VALUE_FLAGS:
        return f"{name}={_sanitize_header_value(value)}"
    if flag in _CREDENTIAL_VALUE_FLAGS and _is_basic_auth_shaped(_strip_quotes(value)):
        return f"{name}={REDACTED}"
    if _is_secret_arg_name(name) or _is_credential_shaped(_strip_quotes(value)):
        return f"{name}={REDACTED}"
    return _redact_url_userinfo(token)


def _flag_expectation(bare: str) -> str | None:
    """The value-state a bare flag arms: ``secret`` / ``credential`` / ``header``."""
    flag = bare.lstrip("-").lower()
    if _is_secret_arg_name(bare):
        return "secret"
    if flag in _CREDENTIAL_VALUE_FLAGS:
        return "credential"
    if flag in _HEADER_VALUE_FLAGS:
        return "header"
    return None


def _sanitize_expected_credential(token: str, bare: str) -> str:
    """The value after ``-u``/``--user``: redact only when it looks like ``user:pass``."""
    if _is_basic_auth_shaped(bare) or _is_credential_shaped(bare):
        return REDACTED
    return token


def _sanitize_bare_token(token: str, bare: str) -> str:
    """One non-flag token: Bearer, secret header, entropy, or URL userinfo."""
    if _BEARER_TOKEN_RE.match(bare):
        return REDACTED
    header = _sanitize_header_value(bare)
    if header != bare:
        return header
    if _is_credential_shaped(bare):
        return REDACTED
    return _redact_url_userinfo(token)


def redact_command_summary(command: str | Sequence[str]) -> RedactionResult:
    """Build a bounded, sanitized command summary from a command string/list.

    The program name and safe arguments survive; values of secret-named
    options, secret-named environment assignments, ``Bearer`` tokens (bare,
    quoted, or inside ``-H``/``--header`` values), basic-auth ``user:pass``
    values after ``-u``/``--user``, JWT-shaped dotted tokens, and URL
    userinfo become ``[redacted]``. The summary is bounded to
    :data:`MAX_SUMMARY_CHARS` (truncation marks its own tail with ``…`` so a
    fragment is never mistaken for the whole).
    """
    tokens = _tokenize(command)
    if not tokens:
        return RedactionResult(None, excluded=True, reason="empty command")

    sanitized: list[str] = []
    expect_secret_value = False
    expect_credential_value = False
    expect_header_value = False
    for token in tokens:
        bare = _strip_quotes(token)
        # A value consumed by a previous secret-named flag (or bare Bearer).
        if expect_secret_value:
            sanitized.append(REDACTED)
            expect_secret_value = False
            continue
        # A value consumed by -u/--user — redacted only when credential-shaped.
        if expect_credential_value:
            sanitized.append(_sanitize_expected_credential(token, bare))
            expect_credential_value = False
            continue
        # A header value consumed by -H/--header.
        if expect_header_value:
            sanitized.append(_sanitize_header_value(bare))
            expect_header_value = False
            continue
        # A bare `Bearer` marks the token that follows as a credential.
        if bare.lower() == "bearer":
            sanitized.append(token)
            expect_secret_value = True
            continue
        # Environment-assignment prefix (FOO=bar cmd): keep a secret-named
        # assignment's key, redact its value; keep a benign one whole.
        assignment = _ENV_ASSIGNMENT_RE.match(bare)
        if assignment is not None:
            sanitized.append(_sanitize_assignment(bare, assignment))
            continue
        # --flag=value form (incl. --header=… / --user=…).
        if bare.startswith("-") and "=" in bare:
            sanitized.append(_sanitize_inline_flag(bare, token))
            continue
        # Secret-named / credential / header flag: arm the matching value state.
        if bare.startswith("-") and (expectation := _flag_expectation(bare)) is not None:
            sanitized.append(token)
            if expectation == "secret":
                expect_secret_value = True
            elif expectation == "credential":
                expect_credential_value = True
            else:
                expect_header_value = True
            continue
        sanitized.append(_sanitize_bare_token(token, bare))

    summary = " ".join(sanitized)
    if len(summary) > MAX_SUMMARY_CHARS:
        summary = summary[: MAX_SUMMARY_CHARS - 1] + "…"
    return RedactionResult(summary)


def secret_material_reason(text: str) -> str | None:
    """Why ``text`` may not be published as authored prose, or ``None``.

    The authored-message gate (#4269): a human or agent deliberately
    publishing a bounded message is different from a command summary, where
    redaction silently replaces the secret and the summary ships anyway —
    an authored message whose *content* is a secret is refused outright
    (publishing ``[redacted]`` as someone's authored words would be a false
    message, not a safe one). This classifier reuses the same detectors
    :func:`redact_command_summary` applies per token — Bearer prefixes,
    secret-named assignments, credential-shaped/high-entropy/JWT tokens,
    basic-auth shapes, URL userinfo — but reports a category instead of
    rewriting. The category never echoes the matched text, so the refusal
    message itself cannot leak what it refused.

    Whitespace-delimited tokens only: this is a prose gate, not a parser,
    and a secret the author split across tokens is indistinguishable from
    prose by construction — the relay's bounded-attr world has no room for
    a tighter scan to matter.
    """
    if not isinstance(text, str):
        return None
    expect_secret_value = False
    for token in text.split():
        bare = _strip_quotes(token)
        if expect_secret_value:
            return "bearer credential"
        if bare.lower() == "bearer":
            expect_secret_value = True
            continue
        assignment = _ENV_ASSIGNMENT_RE.match(bare)
        if assignment is not None:
            key, value = assignment.group(1), assignment.group(2)
            if _is_secret_arg_name(key) or _is_credential_shaped(_strip_quotes(value)):
                return "secret-named assignment or credential-shaped value"
            continue
        if bare.startswith("-") and "=" in bare:
            name, value = bare.split("=", 1)
            if _is_secret_arg_name(name) or _is_credential_shaped(_strip_quotes(value)):
                return "secret-named flag value"
            if _BEARER_TOKEN_RE.search(value):
                return "bearer credential"
            continue
        if _BEARER_TOKEN_RE.match(bare):
            return "bearer credential"
        if _is_basic_auth_shaped(bare) and ":" in bare:
            return "basic-auth credential"
        if _is_credential_shaped(bare):
            return "credential-shaped or high-entropy token"
        if _URL_USERINFO_RE.search(bare):
            return "URL userinfo credential"
    return None
