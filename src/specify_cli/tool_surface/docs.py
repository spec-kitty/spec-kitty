"""Docs contract lint for the tool surface contract bounded context.

Documentation files reference generated/native tool surface paths such as
``.agents/skills/spec-kitty-plan/SKILL.md`` or ``.claude/agents/architect.md``.
These paths are derived from the :class:`ToolSurfaceRegistry` path patterns. If a
pattern changes, the doc references silently drift and mislead operators.

:class:`DocsLinter` enforces the invariant (FR-017): every documented
*generated/native tool surface* path must match a registered ``path_pattern``.

The linter is deliberately conservative. It only inspects a backtick-quoted path
when that path shares the static prefix of a registered pattern (the literal text
before the first ``{`` placeholder). This means ordinary dot-paths that the
contract does not own -- ``.kittify/config.yaml``, ``.github/workflows/...`` --
are never flagged. Documentation wildcards such as ``spec-kitty.*/SKILL.md`` or
``spec-kitty.<command>/SKILL.md`` are placeholder forms and are skipped too.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .registry import ToolSurfaceRegistry

#: Finding emitted when a doc path looks like a tool surface path but matches no
#: registered pattern.
FINDING_UNREGISTERED_PATH = "UNREGISTERED_PATH"

#: Inline suppression annotation; placing it on a line silences findings there.
IGNORE_ANNOTATION = "<!-- tool-surface: ignore -->"

#: Default glob(s) used when linting a directory.
_DEFAULT_DOC_GLOBS = ("**/*.md",)

#: Backtick-quoted token extractor for Markdown inline code spans.
_BACKTICK_TOKEN = re.compile(r"`([^`]+)`")

#: Placeholder markers that mark a reference as a documentation wildcard rather
#: than a concrete path. Such references are intentionally not validated.
_PLACEHOLDER_MARKERS = ("*", "<", ">", "{", "}")

#: A pattern is only treated as a validatable filesystem path when it begins with
#: a leading ``.`` (a dotfile tool directory) and carries no sentinel syntax.
_SENTINEL_MARKERS = ("<", ">", ":")


@dataclass(frozen=True)
class DocsLintFinding:
    """A single drifted documentation path reference."""

    doc_path: Path
    line_number: int
    referenced_path: str
    finding: str
    detail: str


@dataclass(frozen=True)
class _RegisteredPattern:
    """A registered path pattern compiled for doc-reference validation."""

    raw: str
    static_prefix: str
    matcher: re.Pattern[str]


def _is_validatable_pattern(path_pattern: str) -> bool:
    """Return True if ``path_pattern`` describes a concrete relative file path.

    Sentinel patterns (``<session-presence>``, ``<user-global>/...``) and
    manifest-embedded patterns (``.kittify/...:{installed_path}``) are not real
    filesystem paths and are excluded from doc validation.
    """
    if not path_pattern.startswith("."):
        return False
    return not any(marker in path_pattern for marker in _SENTINEL_MARKERS)


def _static_prefix(path_pattern: str) -> str:
    """Return the literal *directory* prefix of ``path_pattern``.

    The prefix is used to decide which doc references "look like" a tool surface
    path and therefore warrant validation. It is the literal directory portion
    that precedes the first placeholder segment:

    - ``.agents/skills/spec-kitty.{command}/SKILL.md`` -> ``.agents/skills/``
    - ``.claude/agents/{profile_id}.md`` -> ``.claude/agents/``
    - ``.vibe/config.toml`` (no placeholder) -> ``.vibe/config.toml``

    Anchoring on the surface *directory* (not down to a partial segment such as
    ``spec-kitty.``) means a mistyped path under that directory -- e.g.
    ``.agents/skills/nonexistent/SKILL.md`` -- is still validated and flagged,
    while unrelated dot-paths under other directories are left alone.
    """
    brace = path_pattern.find("{")
    if brace == -1:
        return path_pattern
    last_sep = path_pattern.rfind("/", 0, brace)
    if last_sep == -1:
        return path_pattern[:brace]
    return path_pattern[: last_sep + 1]


def _compile_pattern(path_pattern: str) -> re.Pattern[str]:
    """Compile a ``path_pattern`` into an anchored regex.

    ``{placeholder}`` segments expand to ``[^/]+`` (a single path segment); all
    other characters are matched literally.
    """
    parts: list[str] = []
    for token in re.split(r"(\{[^}]*\})", path_pattern):
        if token.startswith("{") and token.endswith("}"):
            parts.append(r"[^/]+")
        else:
            parts.append(re.escape(token))
    return re.compile("".join(parts) + r"\Z")


class RegistryPathIndex:
    """Indexes registry path patterns for fast doc-reference validation."""

    def __init__(self, registry: ToolSurfaceRegistry) -> None:
        self._patterns: list[_RegisteredPattern] = self._build(registry)

    @staticmethod
    def _build(registry: ToolSurfaceRegistry) -> list[_RegisteredPattern]:
        seen: set[str] = set()
        patterns: list[_RegisteredPattern] = []
        for tool_key in registry.all_tool_keys():
            for definition in registry.get_definitions(tool_key):
                raw = definition.path_pattern
                if raw in seen or not _is_validatable_pattern(raw):
                    continue
                seen.add(raw)
                patterns.append(
                    _RegisteredPattern(
                        raw=raw,
                        static_prefix=_static_prefix(raw),
                        matcher=_compile_pattern(raw),
                    )
                )
        return patterns

    def looks_like_surface_path(self, path: str) -> bool:
        """Return True if ``path`` is a concrete reference under a known surface.

        A reference qualifies only when it *extends* a registered pattern's
        static directory prefix with at least one further path segment. Bare
        directory references that merely name the surface root (``.agents/skills/``)
        do not name a concrete surface and are therefore left alone. An exact,
        placeholder-free pattern (``.vibe/config.toml``) qualifies on equality.
        """
        for pattern in self._patterns:
            if path == pattern.raw and "{" not in pattern.raw:
                return True
            if self._extends_prefix(path, pattern.static_prefix):
                return True
        return False

    @staticmethod
    def _extends_prefix(path: str, prefix: str) -> bool:
        if not path.startswith(prefix):
            return False
        remainder = path[len(prefix) :].strip("/")
        return bool(remainder)

    def is_registered_path(self, path: str) -> bool:
        """Return True if ``path`` matches any registered path pattern."""
        return any(p.matcher.match(path) for p in self._patterns)

    def suggest_correction(self, path: str) -> str | None:
        """Return the registered pattern whose static prefix the path shares."""
        for pattern in self._patterns:
            if path.startswith(pattern.static_prefix):
                return pattern.raw
        return None


class DocsLinter:
    """Validates doc path references against the ToolSurfaceContract registry."""

    def __init__(self, registry: ToolSurfaceRegistry) -> None:
        self._index = RegistryPathIndex(registry)

    def lint_file(self, doc_path: Path) -> list[DocsLintFinding]:
        """Lint a single doc file, returning findings for any drifted paths."""
        findings: list[DocsLintFinding] = []
        text = doc_path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if IGNORE_ANNOTATION in line:
                continue
            findings.extend(self._lint_line(doc_path, line_number, line))
        return findings

    def lint_directory(
        self, docs_dir: Path, patterns: list[str] | None = None
    ) -> list[DocsLintFinding]:
        """Lint every matching file under ``docs_dir`` (recursively)."""
        globs = patterns if patterns is not None else list(_DEFAULT_DOC_GLOBS)
        findings: list[DocsLintFinding] = []
        for doc_path in self._iter_docs(docs_dir, globs):
            findings.extend(self.lint_file(doc_path))
        return findings

    @staticmethod
    def _iter_docs(docs_dir: Path, globs: Iterable[str]) -> list[Path]:
        seen: set[Path] = set()
        ordered: list[Path] = []
        for glob in globs:
            for path in sorted(docs_dir.glob(glob)):
                if path.is_file() and path not in seen:
                    seen.add(path)
                    ordered.append(path)
        return ordered

    def _lint_line(
        self, doc_path: Path, line_number: int, line: str
    ) -> list[DocsLintFinding]:
        findings: list[DocsLintFinding] = []
        for token in _BACKTICK_TOKEN.findall(line):
            candidate = token.strip()
            if not self._is_concrete_candidate(candidate):
                continue
            if self._index.is_registered_path(candidate):
                continue
            findings.append(
                DocsLintFinding(
                    doc_path=doc_path,
                    line_number=line_number,
                    referenced_path=candidate,
                    finding=FINDING_UNREGISTERED_PATH,
                    detail=self._unregistered_detail(candidate),
                )
            )
        return findings

    def _is_concrete_candidate(self, candidate: str) -> bool:
        """Return True if ``candidate`` should be validated against the registry."""
        if any(marker in candidate for marker in _PLACEHOLDER_MARKERS):
            return False
        return self._index.looks_like_surface_path(candidate)

    def _unregistered_detail(self, candidate: str) -> str:
        suggestion = self._index.suggest_correction(candidate)
        if suggestion is None:
            return f"'{candidate}' matches no registered tool surface path pattern"
        return (
            f"'{candidate}' does not match registered pattern '{suggestion}'. "
            "Update the doc to a registered path or add "
            f"'{IGNORE_ANNOTATION}' on the line if it is intentionally non-standard"
        )


def format_findings(findings: Iterable[DocsLintFinding]) -> str:
    """Render findings as a human-readable, multi-line report block."""
    lines = [
        f"{f.doc_path}:{f.line_number}: {f.finding} {f.referenced_path} -- {f.detail}"
        for f in findings
    ]
    return "\n".join(lines)
