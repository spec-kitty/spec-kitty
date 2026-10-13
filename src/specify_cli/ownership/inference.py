"""Best-effort inference of ownership manifest fields from WP content.

All inferred values can be overridden by the user via manual frontmatter edits.
Inference runs at finalization time; it does not block finalization when uncertain.
"""

from __future__ import annotations

import re

from specify_cli.ownership.models import WorkProductKind, OwnershipManifest

__all__ = [
    "infer_execution_mode",
    "infer_owned_files",
    "infer_authoritative_surface",
    "infer_ownership",
    "score_execution_mode_signals",
    "detect_post_integration_acceptance",
    "SRC_FALLBACK_GLOB",
    "SRC_FALLBACK_WARNING",
]

# Constant so callers can detect / test the fallback value.
SRC_FALLBACK_GLOB = "src/**"
SRC_FALLBACK_WARNING = "No file paths found in WP body text; using broad fallback 'src/**'. Consider adding explicit owned_files to WP frontmatter."

# Patterns that strongly suggest planning artifact deliverables.
_PLANNING_SIGNALS = [
    r"\bkitty-specs/",
    r"\bspec\.md\b",
    r"\bplan\.md\b",
    r"\btasks\.md\b",
    r"\bdata-model\.md\b",
    r"\bquickstart\.md\b",
]

# Patterns that strongly suggest code change deliverables.
_CODE_SIGNALS = [
    r"\bsrc/",
    r"\btests?/",
    r"\.py\b",
    r"\.ts\b",
    r"\.js\b",
]

# Regex to extract path-like tokens from WP content.
# Matches things like: src/foo/bar.py, tests/specify_cli/..., kitty-specs/001-feature/...
_PATH_PATTERN = re.compile(
    r"""
    (?:
        (?:src|tests?|kitty-specs|docs)   # known top-level dirs
        /
        [^\s`'")\]>]+                     # rest of path
    )
    """,
    re.VERBOSE,
)


def infer_execution_mode(wp_content: str, wp_files: list[str]) -> WorkProductKind:
    """Infer whether a WP is a code_change or planning_artifact.

    Heuristic (in order of precedence):
    1. If the WP body mentions planning artifact keywords as primary deliverables
       (kitty-specs/, spec.md, plan.md, tasks.md, data-model.md) → planning_artifact.
    2. If the WP body mentions src/, test files, or source-code extensions → code_change.
    3. Default → code_change.

    Args:
        wp_content: Full text of the WP prompt file (frontmatter + body).
        wp_files: Optional list of file paths explicitly listed as WP deliverables.

    Returns:
        Inferred WorkProductKind.
    """
    planning_score, code_score = score_execution_mode_signals(wp_content, wp_files)

    if planning_score > 0 and code_score == 0:
        return WorkProductKind.PLANNING_ARTIFACT

    # Default: code_change
    return WorkProductKind.CODE_CHANGE


def score_execution_mode_signals(wp_content: str, wp_files: list[str]) -> tuple[int, int]:
    """Return ``(planning_score, code_score)`` for execution-mode inference."""
    combined = wp_content + "\n" + "\n".join(wp_files)
    planning_score = sum(1 for p in _PLANNING_SIGNALS if re.search(p, combined))
    code_score = sum(1 for p in _CODE_SIGNALS if re.search(p, combined))
    return planning_score, code_score


_POST_INTEGRATION_MARKERS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bpost[-\s]?merge\b",
        r"\bafter (?:the )?merge\b",
        r"\bonce merged\b",
        r"\bpost[-\s]?integration\b",
        r"\bafter integration\b",
        r"\bonce integrated\b",
        r"\bafter (?:the )?deploy(?:ment)?\b",
        r"\bonce deployed\b",
    )
)
_ACCEPTANCE_HEADING = re.compile(r"(?i)(?:acceptance|success\s+crit|review\s+guidance)")
_HEADING_LINE = re.compile(r"^#{1,6}\s")


def _heading_level(line: str) -> int:
    """Return a Markdown heading line's depth (number of leading ``#``)."""
    return len(line) - len(line.lstrip("#"))


def _acceptance_criteria_scope(wp_body: str) -> str:
    """Return text under acceptance/success-criteria headings.

    Tracks heading depth: once an acceptance heading opens the scope, a
    sub-heading nested deeper than it (e.g. ``### Notes`` under
    ``## Acceptance Criteria``) stays inside scope. The scope only closes on
    a heading at or above the opening heading's level.
    """
    scoped: list[str] = []
    capturing = False
    scope_level = 0
    for line in wp_body.splitlines():
        if _HEADING_LINE.match(line):
            level = _heading_level(line)
            if capturing and level > scope_level:
                continue
            capturing = bool(_ACCEPTANCE_HEADING.search(line))
            if capturing:
                scope_level = level
            continue
        if capturing:
            scoped.append(line)
    return "\n".join(scoped)


def detect_post_integration_acceptance(wp_content: str, wp_files: list[str]) -> list[str]:
    """Warn when a code WP's acceptance criteria are post-integration only."""
    if infer_execution_mode(wp_content, wp_files) is not WorkProductKind.CODE_CHANGE:
        return []
    scope = _acceptance_criteria_scope(wp_content)
    if not scope:
        return []
    matched = sorted({match.group(0).strip().lower() for pattern in _POST_INTEGRATION_MARKERS for match in pattern.finditer(scope)})
    if not matched:
        return []
    phrases = ", ".join(f"'{phrase}'" for phrase in matched)
    return [
        "acceptance criteria appear observable only post-integration "
        f"({phrases}) -- an action, not a diff. The work package cannot be "
        "honestly reviewed while its lane is open; re-home this observation at "
        "planning time so the WP can terminate on a diff-inspectable criterion."
    ]


def infer_owned_files(wp_content: str, mission_slug: str) -> tuple[list[str], list[str]]:
    """Infer owned_files glob patterns from WP body text.

    For planning_artifact WPs: defaults to ``kitty-specs/<mission_slug>/**``.
    For code_change WPs: extracts path prefixes found in the WP body.

    Args:
        wp_content: Full text of the WP prompt file.
        mission_slug: Feature slug (e.g. ``"057-canonical-context-architecture-cleanup"``).

    Returns:
        A 2-tuple of ``(globs, warnings)`` where *globs* is a deduplicated
        list of glob patterns and *warnings* is a list of human-readable
        warning strings (may be empty).
    """
    execution_mode = infer_execution_mode(wp_content, [])

    if execution_mode == WorkProductKind.PLANNING_ARTIFACT:
        return [f"kitty-specs/{mission_slug}/**"], []

    # Extract path tokens mentioned in the WP
    found_paths = set(_PATH_PATTERN.findall(wp_content))

    # Normalise: strip trailing punctuation, deduplicate directory prefixes
    globs: list[str] = []
    seen_prefixes: set[str] = set()

    for path in sorted(found_paths):
        # Convert a path like src/foo/bar.py → src/foo/bar.py (keep as-is)
        # Convert a path like src/foo/ → src/foo/**
        if path.endswith("/"):
            glob = path + "**"
        else:
            # If it looks like a directory (no extension), append /**
            if "." not in path.split("/")[-1]:
                glob = path.rstrip("/") + "/**"
            else:
                glob = path

        # Deduplicate: skip if a parent prefix already captured this path
        parts = glob.split("/")
        skip = False
        for i in range(1, len(parts)):
            candidate = "/".join(parts[:i]) + "/**"
            if candidate in seen_prefixes:
                skip = True
                break
        if not skip:
            seen_prefixes.add(glob)
            globs.append(glob)

    # Fall back to a broad pattern if we couldn't extract anything specific.
    # Warn so operators know the scope is synthetic.
    warnings: list[str] = []
    if not globs:
        globs = [SRC_FALLBACK_GLOB]
        warnings.append(SRC_FALLBACK_WARNING)

    return globs, warnings


def infer_authoritative_surface(owned_files: list[str]) -> str:
    """Derive the authoritative_surface from a list of owned_files patterns.

    Returns the longest common path prefix shared by all owned_files entries.
    If they have no common directory, use the first entry's directory as a
    valid narrow surface. An empty list has no inferable surface.
    A glob-bearing final path segment (whole-wildcard tokens like ``/**``/``/*``
    *and* filename globs like ``*.py``, ``data_?.json`` or ``[abc].py``) is
    reduced to its containing directory before comparison. Literal files are
    likewise reduced to their containing directory.

    Args:
        owned_files: List of glob patterns.

    Returns:
        A path prefix string (empty only when owned_files is empty).
    """
    if not owned_files:
        return ""

    def _strip_glob(pattern: str) -> str:
        """Reduce a glob pattern to its containing directory prefix.

        When the *last* path segment carries a glob metacharacter (``*``,
        ``?`` or ``[``) — covering both whole-wildcard tokens (``**``, ``*``)
        and filename globs (``*.py``, ``data_?.json``, ``[abc].py``) — drop
        that segment and keep its directory. Literal filenames are handled the
        same way. In every case the result carries no trailing ``/``: the
        single-entry branch re-appends one and the multi-entry branch splits
        on ``/``, so a trailing slash would create a spurious empty segment.
        """
        head, _, tail = pattern.rpartition("/")
        if any(ch in tail for ch in "*?[") or "." in tail:
            return head
        return pattern.rstrip("/")

    stripped = [_strip_glob(p) for p in owned_files]

    if len(stripped) == 1:
        candidate = stripped[0].rstrip("/") + "/"
        return candidate if owned_files[0].startswith(candidate) else owned_files[0]

    # Split by "/" and find common prefix segments
    split = [s.split("/") for s in stripped]
    common: list[str] = []
    for segments in zip(*split):
        if len(set(segments)) == 1:
            common.append(segments[0])
        else:
            break

    candidate = "/".join(common or split[0]).rstrip("/") + "/"
    return candidate if any(p.startswith(candidate) for p in owned_files) else owned_files[0]


def infer_ownership(
    wp_content: str,
    mission_slug: str,
    wp_files: list[str] | None = None,
) -> tuple[OwnershipManifest, list[str]]:
    """Convenience function: infer a complete OwnershipManifest from WP content.

    Args:
        wp_content: Full text of the WP prompt file.
        mission_slug: Feature slug string.
        wp_files: Optional explicit list of file paths.

    Returns:
        A 2-tuple of ``(manifest, warnings)`` where *manifest* is a
        best-effort OwnershipManifest and *warnings* is a list of
        human-readable warning strings (may be empty).

    Note on ``scope`` (FR-029, stated contract — not a gap):
        ``scope`` has **no inference path** and is intentionally omitted from
        the returned manifest. ``scope: "codebase-wide"`` is a deliberate,
        human-authored exemption that relaxes ownership overlap and
        authoritative-surface checks (see
        :mod:`specify_cli.ownership.validation`). Inferring it would silently
        widen a WP's blast radius, so inferred manifests always remain narrow
        (``scope=None``). The only way ``scope`` enters the system is via
        :meth:`OwnershipManifest.from_frontmatter` reading a human-authored
        frontmatter value — the single canonical owner of the field.
    """
    from specify_cli.ownership.models import OwnershipManifest  # local import avoids circularity

    files = wp_files or []
    execution_mode = infer_execution_mode(wp_content, files)
    owned_files, warnings = infer_owned_files(wp_content, mission_slug)
    authoritative_surface = infer_authoritative_surface(owned_files)

    # ``scope`` is left at its default (None): human-authored only, never inferred.
    manifest = OwnershipManifest(
        execution_mode=execution_mode,
        owned_files=tuple(owned_files),
        authoritative_surface=authoritative_surface,
    )
    return manifest, warnings
