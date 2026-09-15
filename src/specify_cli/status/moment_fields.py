"""#4327 creation-time validation of the inline ``WPStatusChanged`` moment fields.

The scope clarification on spec-kitty/spec-kitty#4327 (2026-09-14) splits the
human-readable gist of a transition from its pointer slot:

- ``summary`` — a NEW, optional, one-line, human-readable gist for the NOW
  view. Prose may travel on the relay (a team is an established trust
  boundary), but the relay enforces a 240-UTF-8-byte per-attr bound
  (zeitgeist ``managed_live.schema.json``), so an over-bound or multi-line
  gist would drop the whole moment (#3954). New explicit input is therefore
  REJECTED when it is not one printable line of at most 240 UTF-8 bytes —
  never silently truncated; only the sanctioned legacy-prose interim (the
  #4319 bridge bound, already retired) ever normalized/truncated.
- ``review_ref`` — pointer-only. The note's prose no longer rides the
  pointer slot; it stays local in ``reason``/``--note``. The pointer forms
  actually in use are the ``review-cycle://``/``feedback://`` (and the older
  ``rev://``/``approval://``/``review://``) scheme pointers, the
  ``action-review-claim``/``force-override`` sentinels, ``auto-approval:``/
  ``review:``/``approval:`` synthetic tokens, ``PR#N`` refs, and
  repo-relative artifact paths.

Both validators are enforced twice by design: at the CLI boundary (the
``--summary``/``--review-ref``/``--approval-ref`` Typer options, before any
review-cycle artifact or status write) and at the shared creation boundary
(``status/transition_pipeline._validated_inline_fields``, which every
emission shell funnels through), so a programmatic caller constructing a
:class:`~specify_cli.status.models.TransitionRequest` directly cannot bypass
them. This module is the single definition of both rules.

Legacy decoding stays compatible by construction: validators only run on NEW
writes. A persisted event that already holds prose in ``review_ref`` (written
before #4327) decodes unchanged — rewriting Git history is out of scope — and
the one re-threading path that could copy such prose into a new transition
(``tasks_move_task._run_arbiter_override``) substitutes the synthetic
``review:<WP>`` token when the legacy value fails validation here.

Pointer classification never uses absence of whitespace as its sole signal:
legitimate repo-relative paths may contain spaces, so a slash-bearing value
is treated as a path candidate (whitespace and all), while prose — words with
whitespace and no separator — is refused. Windows drive-letter
(``C:\\…``/``C:/…``) and UNC (``\\\\server\\share\\…``) spellings are
classified as absolute paths BEFORE the scheme arms, so a single-letter drive
can never masquerade as scheme ``C``, and scheme-shaped values are accepted
only from the pointer families actually in use. Pointers are NEVER truncated,
and they carry no byte bound here: they are short by construction once prose
is excluded.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

__all__ = [
    "ReviewRefValidationError",
    "SummaryValidationError",
    "validate_review_ref",
    "validate_summary",
]

#: The relay-enforced per-attr bound (zeitgeist ``managed_live.schema.json``
#: ``maxUtf8Bytes: 240``), mirrored by SaaS and the events codec. Kept in one
#: place so the validator and its error message quote one number; module-
#: private (the dead-symbol gate owns the public surface -- no src/ consumer
#: needs the constant itself, the validators carry the number).
_SUMMARY_MAX_UTF8_BYTES = 240

# Horizontal whitespace is NORMALIZED (collapsed to one space), never
# rejected: a trailing tab or a double space in an operator's gist is a
# formatting accident, not a smuggling attempt. Everything else that is not
# printable — newline, carriage return, other control characters, format
# characters, surrogates, private-use and unassigned code points — is
# rejected with the offending codepoint named.
_NORMALIZED_WHITESPACE = (" ", "\t")
_WHITESPACE_RUN_RE = re.compile(r"[ \t]+")

# ``<scheme>:`` prefix (RFC 3986 scheme shape). Two pointer families use it:
# URI-style pointers with an authority (``review-cycle://``, ``feedback://``,
# ``rev://``, ``approval://``, ``review://``) and synthetic tokens with a bare
# colon (``review:<WP>``, ``approval:<WP>``, ``auto-approval:<WP>:<date>``).
# Both arms are ALLOWLISTED to those exact families — never "any scheme that
# happens to look RFC 3986-shaped": a ``file:///home/…``/``https://…`` URI is
# an absolute-location pointer in URI clothing, and the error message
# promises "one of the pointer forms in use", so an unknown scheme is refused
# with that message instead of riding the wire verbatim.
_SCHEME_PREFIX_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
_SCHEME_URI_PREFIX_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*://")
#: URI pointer families actually in use (the scheme IS the pointer grammar).
_URI_POINTER_SCHEMES = frozenset(
    {
        "review-cycle",
        "feedback",
        "rev",
        "approval",
        "review",
    }
)
#: Synthetic colon-token prefixes actually written by the workflow/orchestrator
#: paths (``review:<WP>``, ``approval:<WP>``, ``auto-approval:<WP>:<date>``).
_SYNTHETIC_TOKEN_PREFIXES = frozenset(
    {
        "review",
        "approval",
        "auto-approval",
    }
)

# PR refs: ``PR#42`` plus the verdict-suffixed live form (``PR#42-changes-
# requested``) and the bare issue/PR number form (``#1298``).
_PR_REF_RE = re.compile(r"^(?:PR#\d+(?:-\S+)?|#\d+)$")

# Sentinels actually written by the workflow/orchestrator paths
# (``specify_cli.review.cycle.REVIEW_FEEDBACK_SENTINELS`` and
# ``status/work_package_lifecycle.py``'s ``action-review-claim`` default).
# Duplicated rather than imported so the CORE ``status`` layer does not grow a
# dependency on the ``review`` package (the import-boundary guards own that
# seam); if the review set grows, this frozenset grows with it.
_SYNTHETIC_SENTINELS = frozenset(
    {
        "action-review-claim",
        "force-override",
    }
)

# Windows drive-letter prefix and UNC device prefix: both are absolute PATH
# spellings, classified BEFORE the scheme arms in ``validate_review_ref`` (a
# single-letter drive would otherwise masquerade as scheme ``C``) and treated
# as an absolute path for the repo-relative conversion below — never passed
# through as-is.
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
#: A leading ``\\`` (or ``//``) names a UNC device path (``\\server\share\…``).
_UNC_PREFIXES = ("\\", "//")

_POINTER_FORMS_HELP = (
    "one of the pointer forms in use: review-cycle://…, feedback://…, "
    "rev://…, approval://…, review://…, auto-approval:<WP>:<date>, "
    "review:<WP>, approval:<WP>, action-review-claim, force-override, "
    "PR#N, or a repo-relative path"
)


class SummaryValidationError(ValueError):
    """A ``--summary`` value failed the one-printable-line/240-byte rules."""


class ReviewRefValidationError(ValueError):
    """A ``--review-ref``/``--approval-ref`` value was not pointer-shaped."""


def validate_summary(value: str) -> str:
    """Validate and normalise a NEW inline ``summary`` (#4327).

    Returns the normalized gist: horizontal whitespace (spaces, tabs) is
    collapsed to single spaces and the ends are trimmed.

    Raises:
        SummaryValidationError: when *value* contains a non-printable
            character other than space/tab (the codepoint is named, e.g.
            ``U+000A`` for a newline), is empty after trimming, or encodes
            to more than :data:`_SUMMARY_MAX_UTF8_BYTES` UTF-8 bytes (the
            message names the field, the actual size, and the bound).
            Nothing is ever silently truncated.
    """
    for ch in value:
        if ch in _NORMALIZED_WHITESPACE:
            continue
        if not ch.isprintable():
            raise SummaryValidationError(
                f"--summary contains the non-printable character U+{ord(ch):04X}; "
                "the inline summary must be one printable line — put the full "
                "multi-line note in --note/--reason instead"
            )

    normalized = _WHITESPACE_RUN_RE.sub(" ", value).strip()
    if not normalized:
        raise SummaryValidationError("--summary is empty after trimming whitespace; omit the option rather than passing a blank gist")

    size = len(normalized.encode("utf-8"))
    if size > _SUMMARY_MAX_UTF8_BYTES:
        raise SummaryValidationError(
            f"--summary is {size} UTF-8 bytes; the inline summary is bounded "
            f"to {_SUMMARY_MAX_UTF8_BYTES} UTF-8 bytes — shorten the gist and "
            "keep the full note in --note/--reason (nothing is truncated)"
        )
    return normalized


def validate_review_ref(value: str, *, repo_root: Path | None = None) -> str:
    """Validate a NEW ``review_ref``/approval ref as pointer-only (#4327).

    Returns the validated pointer: stripped of surrounding whitespace, with
    an in-repo absolute path converted to its repo-relative form. Pointers
    are never truncated and carry no byte bound here.

    Args:
        value: The candidate pointer.
        repo_root: The repository root used to convert absolute local paths
            to repo-relative ones and to refuse paths that escape the
            repository. ``None`` (a caller with no resolved root) refuses
            absolute paths outright rather than leaking them.

    Raises:
        ReviewRefValidationError: when *value* is prose (whitespace-bearing
            words with no path separator), a scheme-shaped value outside the
            pointer families in use, an absolute path outside the repository
            (or any absolute path when *repo_root* is ``None`` — including
            the Windows drive-letter and UNC spellings, classified as paths
            before the scheme arms), or a relative path whose ``..``
            components escape the repository root. The message names the
            accepted pointer forms.
    """
    if not isinstance(value, str) or not value.strip():
        raise ReviewRefValidationError(f"--review-ref must be a non-empty pointer ({_POINTER_FORMS_HELP}); got an empty value")
    pointer = value.strip()

    if pointer in _SYNTHETIC_SENTINELS:
        return pointer
    if _WINDOWS_DRIVE_RE.match(pointer) is not None or pointer.startswith(_UNC_PREFIXES):
        # Windows drive-letter absolute paths (``C:\Users\…``, ``C:/Users/…``)
        # and UNC device paths (``\\fileserver\share\…``, ``//server/share/…``)
        # are PATHS, and are classified BEFORE the scheme arms: the
        # single-letter drive prefix also matches ``_SCHEME_PREFIX_RE`` (scheme
        # ``C``), so scheme-first ordering would return the absolute local
        # path verbatim instead of converting or refusing it.
        return _validated_path_pointer(pointer, repo_root=repo_root)
    scheme_match = _SCHEME_PREFIX_RE.match(pointer)
    if scheme_match is not None:
        scheme = scheme_match.group()[:-1].lower()
        if _SCHEME_URI_PREFIX_RE.match(pointer) is not None:
            # URI-shaped pointer (review-cycle://, feedback://, rev://,
            # approval://, review://): the scheme IS the pointer grammar —
            # allowlisted to exactly those families; the payload is owned by
            # the emitting subsystem, not re-validated here.
            if scheme not in _URI_POINTER_SCHEMES:
                raise ReviewRefValidationError(
                    f"--review-ref uses the scheme {scheme!r}, which is not one of the pointer families in use — {_POINTER_FORMS_HELP}. Got: {pointer!r}"
                )
            return pointer
        # Synthetic token (review:<WP>, approval:<WP>,
        # auto-approval:<WP>:<date>): the remainder must be one
        # whitespace-free token — a colon followed by prose is still prose.
        if scheme in _SYNTHETIC_TOKEN_PREFIXES:
            remainder = pointer.split(":", 1)[1]
            if remainder and not any(ch.isspace() for ch in remainder):
                return pointer
        raise ReviewRefValidationError(f"--review-ref must be pointer-shaped, never prose — {_POINTER_FORMS_HELP}. Got: {pointer!r}")
    if _PR_REF_RE.match(pointer) is not None:
        return pointer

    has_separator = "/" in pointer or "\\" in pointer
    has_whitespace = any(ch.isspace() for ch in pointer)
    if not has_separator and not has_whitespace:
        # Bare whitespace-free token (``ref-123``, ``review-001``, the
        # legacy corpus' short handles): pointer-shaped by construction —
        # the one loose form the pre-#4327 corpus depends on.
        if pointer in (".", ".."):
            raise ReviewRefValidationError(f"--review-ref must be pointer-shaped — {_POINTER_FORMS_HELP}. Got: {pointer!r}")
        return pointer
    if not has_separator:
        # Words with whitespace and no path separator: prose.
        raise ReviewRefValidationError(
            f"--review-ref must be pointer-shaped, never prose — {_POINTER_FORMS_HELP}; the human note belongs in --note/--reason. Got: {pointer!r}"
        )

    # Slash-bearing value: a path candidate — legitimate paths may contain
    # spaces, so whitespace alone never disqualifies it.
    return _validated_path_pointer(pointer, repo_root=repo_root)


def _validated_path_pointer(pointer: str, *, repo_root: Path | None) -> str:
    """Normalise a slash-bearing pointer; refuse absolute/out-of-repo paths.

    An absolute path inside *repo_root* is returned as its repo-relative
    form (never the absolute local path — that must not reach the wire).
    Any other absolute path, and any relative path whose ``..`` components
    escape the repository root, is refused with a clear message.

    Classification runs on the forward-slash spelling: ``\\fileserver\\share\\…``
    converted to ``//fileserver/share/…`` is a UNC device path on every
    platform, while the raw backslash spelling is a *relative* filename on
    POSIX — classifying the converted form is what keeps the UNC prefix from
    slipping through the absolute-path refusal on non-Windows hosts.
    """
    fwd = pointer.replace("\\", "/")
    is_absolute = fwd.startswith("/") or _WINDOWS_DRIVE_RE.match(pointer) is not None
    if is_absolute:
        if repo_root is None:
            raise ReviewRefValidationError(
                f"--review-ref is an absolute local path and no repository root "
                "was resolved to make it repo-relative; use a repo-relative path "
                f"or an explicit safe reference (e.g. review:<WP>) — got: {pointer!r}"
            )
        root = Path(repo_root).resolve()
        candidate = Path(fwd)
        if not candidate.is_absolute():
            # A Windows drive-letter spelling on a non-Windows host
            # (``C:/Users/…`` is a *relative* path on POSIX): resolve() would
            # ground it under the process CWD, which can sit inside the repo
            # root and smuggle the drive path through as a repo-relative-
            # looking pointer — refuse instead, fail-closed.
            raise ReviewRefValidationError(
                "--review-ref points outside the repository root (absolute "
                "local paths and UNC device paths are never put on the wire); "
                "use a repo-relative path or an explicit safe reference (e.g. "
                f"review:<WP>). Got: {pointer!r}"
            )
        try:
            resolved = candidate.resolve()
            relative = resolved.relative_to(root)
        except ValueError as exc:
            raise ReviewRefValidationError(
                "--review-ref points outside the repository root (absolute "
                "local paths and UNC device paths are never put on the wire); "
                "use a repo-relative path or an explicit safe reference (e.g. "
                f"review:<WP>). Got: {pointer!r}"
            ) from exc
        return relative.as_posix()

    # Relative path: normalise '.' components and refuse '..' traversal that
    # would escape the repository root. Spaces are preserved — never truncated.
    parts: list[str] = []
    for part in PurePosixPath(fwd).parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                raise ReviewRefValidationError(
                    "--review-ref escapes the repository root with '..'; use a "
                    "path inside the repository or an explicit safe reference "
                    f"(e.g. review:<WP>) — got: {pointer!r}"
                )
            parts.pop()
        else:
            parts.append(part)
    if not parts:
        raise ReviewRefValidationError(f"--review-ref must be pointer-shaped — {_POINTER_FORMS_HELP}. Got: {pointer!r}")
    return "/".join(parts)
