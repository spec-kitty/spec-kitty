"""The one language authority: observed and declared languages from one catalog (#6444, FR-009, FR-013).

``charter.offering.shared.language_catalog`` holds the vocabulary; this module applies it:

* :func:`observe_primary_language` / :func:`resolve_primary_language` decide the primary
  language of a repository from its manifests and source counts;
* :func:`declared_languages` decides which languages a free-form declaration names,
  including the build-token rule (``gradle``/``maven``/``junit`` add ``jvm`` only when no
  JVM language is declared).

Families (``jvm``) are expanded at match time only
(:func:`~charter.offering.shared.language_catalog.expand_language_families`) and are never
persisted as an observed language.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from charter.offering.shared.language_catalog import (
    BUILD_TOOLS,
    COMPOUND_PREFIX_GUARD,
    LANGUAGES,
    expand_language_families,
    language_for_extension,
    languages_for_manifest,
)
from charter.offering.shared.scoping import normalize_languages

__all__ = [
    "EXCLUDED_DIRS",
    "declared_languages",
    "expand_language_families",
    "count_sources_uncapped",
    "resolve_primary_language",
    "TreeObservation",
]

EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        "node_modules",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".git",
        "dist",
        "build",
        ".worktrees",
        ".mypy_cache",
        ".tox",
    }
)

PACKAGE_JSON = "package.json"
TSCONFIG_JSON = "tsconfig.json"

_TYPESCRIPT = "typescript"
_JAVASCRIPT = "javascript"


# ---------------------------------------------------------------------------
# Observed
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class TreeObservation:
    """Manifest depths and TS/JS source counts gathered by a depth-capped walk."""

    indicator_depths: dict[str, int] = field(default_factory=dict)
    ts_files: int = 0
    js_files: int = 0

    def observe(self, filename: str, depth: int) -> None:
        """Record one file: shallowest depth per basename, and the TS/JS counters."""
        known = self.indicator_depths.get(filename)
        if known is None or depth < known:
            self.indicator_depths[filename] = depth
        language = language_for_extension(os.path.splitext(filename)[1])
        if language == _TYPESCRIPT:
            self.ts_files += 1
        elif language == _JAVASCRIPT:
            self.js_files += 1


def _js_or_ts(observation: TreeObservation, package_depth: int) -> str:
    """Pick typescript vs javascript for a ``package.json`` at *package_depth*."""
    if observation.indicator_depths.get(TSCONFIG_JSON) == package_depth:
        return _TYPESCRIPT
    total = observation.ts_files + observation.js_files
    if total > 0 and observation.ts_files / total > 0.5:
        return _TYPESCRIPT
    return _JAVASCRIPT


def count_sources_uncapped(repo_root: Path) -> Counter[str]:
    """Count source files per language across the whole tree, pruning ``EXCLUDED_DIRS``."""
    counts: Counter[str] = Counter()
    for _dirpath, dirnames, filenames in os.walk(str(repo_root)):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for filename in filenames:
            language = language_for_extension(os.path.splitext(filename)[1])
            if language:
                counts[language] += 1
    return counts


def _best_by_count(candidates: tuple[str, ...] | list[str], counts: Mapping[str, int]) -> str:
    """Return the candidate with most sources; ties keep catalog order."""
    return max(candidates, key=lambda lang: (counts[lang], -candidates.index(lang)))


def _top_depth_candidates(observation: TreeObservation, top: int) -> tuple[list[str], tuple[str, ...]]:
    """Return the candidate languages at manifest depth *top*, and the shared JVM-style group.

    A manifest several languages share (the JVM manifests) contributes its first language
    as a placeholder and its whole group, so the caller can split it by source counts.
    """
    languages: list[str] = []
    shared: tuple[str, ...] = ()
    for spec in LANGUAGES:
        for manifest in spec.manifests:
            if observation.indicator_depths.get(manifest) != top:
                continue
            owners = languages_for_manifest(manifest)
            lang = _js_or_ts(observation, top) if manifest == PACKAGE_JSON else owners[0]
            if lang not in languages:
                languages.append(lang)
            if len(owners) > 1:
                shared = owners
    return languages, shared


def resolve_primary_language(
    observation: TreeObservation,
    count_sources: Callable[[], Counter[str]],
) -> str:
    """Return the primary language, preferring the shallowest manifests.

    Manifests at the shallowest depth win. A JVM manifest chooses between ``java`` and
    ``kotlin`` by source counts (ties stay ``java``); several languages at that depth are
    resolved by source counts, then catalog order. *count_sources* is the uncapped walk
    (JVM sources sit deeper than the scan depth); it runs only when a JVM manifest or a
    real tie needs it, and at most once (NFR-005).
    """
    manifest_hits = [depth for name, depth in observation.indicator_depths.items() if languages_for_manifest(name)]
    if not manifest_hits:
        return "unknown"

    languages, shared = _top_depth_candidates(observation, min(manifest_hits))
    if len(languages) == 1 and not shared:
        return languages[0]

    counts = count_sources()
    if shared:
        languages = [_best_by_count(shared, counts) if lang == shared[0] else lang for lang in languages]
    return _best_by_count(languages, counts)


# ---------------------------------------------------------------------------
# Declared
# ---------------------------------------------------------------------------


def _compile(patterns: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(COMPOUND_PREFIX_GUARD + pattern) for pattern in patterns)


_DECLARED_LANGUAGE_PATTERNS: tuple[tuple[int, str, tuple[str, ...], tuple[re.Pattern[str], ...]], ...] = tuple(
    (spec.declared_rank, spec.token, spec.families, _compile(spec.declared_patterns)) for spec in LANGUAGES if spec.declared_patterns
)
_DECLARED_TOOL_PATTERNS: tuple[tuple[int, str, tuple[re.Pattern[str], ...]], ...] = tuple(
    (tool.declared_rank, tool.family, _compile(tool.declared_patterns)) for tool in BUILD_TOOLS
)


def _matches(patterns: tuple[re.Pattern[str], ...], haystack: str) -> bool:
    return any(pattern.search(haystack) for pattern in patterns)


def declared_languages(text: str) -> list[str]:
    """Return the canonical language identifiers a free-form declaration names.

    Output follows ``declared_rank`` (the pre-catalog pattern order), because the
    unsorted fallback path persists it into ``catalog.languages``.

    Build-token rule (FR-013): a declared build or test tool (gradle, maven, junit) adds
    its family (``jvm``) only when no language of that family is declared, so
    "Gradle" alone is ``["jvm"]`` while "Kotlin, Gradle" is ``["kotlin"]``.
    """
    haystack = text.lower()
    matches: list[tuple[int, str]] = []
    families: set[str] = set()
    for rank, token, token_families, patterns in _DECLARED_LANGUAGE_PATTERNS:
        if _matches(patterns, haystack):
            matches.append((rank, token))
            families.update(token_families)
    for rank, family, patterns in _DECLARED_TOOL_PATTERNS:
        if family not in families and _matches(patterns, haystack):
            matches.append((rank, family))
            families.add(family)
    return list(normalize_languages(token for _rank, token in sorted(matches)))
