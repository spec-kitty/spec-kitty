"""The one language authority: observed and declared languages from one catalog (#6444, FR-009, FR-013).

``charter.offering.shared.language_catalog`` holds the vocabulary; this module applies it:

* :func:`resolve_languages` decides the primary language and the full language list of a repository from its manifests and source counts;
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
    "ObservedLanguages",
    "resolve_languages",
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

#: A language whose files make up at least this share of the counted source files is listed
#: in ``languages`` even without a top-depth manifest (D-06, FR-010). 20% keeps a few
#: config scripts (a handful of ``.js`` files in a Python repository) out of the evidence.
_LANGUAGE_SHARE_THRESHOLD = 0.2

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


def _top_depth_candidates(observation: TreeObservation, top: int | None) -> tuple[list[str], tuple[str, ...]]:
    """Return the candidate languages at manifest depth *top* (every depth when ``None``), and the shared JVM-style group.

    A manifest several languages share (the JVM manifests) contributes its first language
    as a placeholder and its whole group, so the caller can split it by source counts.
    """
    languages: list[str] = []
    shared: tuple[str, ...] = ()
    for spec in LANGUAGES:
        for manifest in spec.manifests:
            depth = observation.indicator_depths.get(manifest)
            if depth is None or (top is not None and depth != top):
                continue
            owners = languages_for_manifest(manifest)
            lang = _js_or_ts(observation, depth) if manifest == PACKAGE_JSON else owners[0]
            if lang not in languages:
                languages.append(lang)
            if len(owners) > 1:
                shared = owners
    return languages, shared


@dataclass(frozen=True, slots=True)
class ObservedLanguages:
    """Observed languages of a repository: the primary one, then every other listed one.

    ``languages`` is empty when nothing was observed (``primary == "unknown"``);
    otherwise ``languages[0] == primary`` (FR-010).
    """

    primary: str
    languages: tuple[str, ...] = ()


def _source_share_languages(counts: Mapping[str, int]) -> list[str]:
    """Return languages whose share of all counted sources reaches ``_LANGUAGE_SHARE_THRESHOLD``."""
    total = sum(counts.values())
    if total <= 0:
        return []
    return [lang for lang, count in counts.items() if count / total >= _LANGUAGE_SHARE_THRESHOLD]


def _order_languages(primary: str, included: set[str], counts: Mapping[str, int]) -> tuple[str, ...]:
    """Order *included*: primary first, then source count descending, then catalog order."""
    catalog_order = {spec.token: index for index, spec in enumerate(LANGUAGES)}
    rest = sorted(included - {primary}, key=lambda lang: (-counts.get(lang, 0), catalog_order.get(lang, len(catalog_order))))
    return (primary, *rest)


def resolve_languages(
    observation: TreeObservation,
    count_sources: Callable[[], Counter[str]],
) -> ObservedLanguages:
    """Return the primary language and every language the repository carries (FR-010).

    Included: every language with a manifest at the shallowest manifest depth, plus any
    language holding at least ``_LANGUAGE_SHARE_THRESHOLD`` of the counted sources. The
    primary language is chosen as before: manifests at the shallowest depth win; a JVM
    manifest picks ``java`` or ``kotlin`` by source counts (ties stay ``java``); several
    languages at that depth are resolved by source counts, then catalog order.

    *count_sources* is the uncapped walk (JVM sources sit deeper than the scan depth).
    It runs only when a JVM manifest is seen or the manifests at any scanned depth name two
    or more languages, and at most once (NFR-005); a single-language, non-JVM repository
    never triggers it.
    """
    manifest_hits = [depth for name, depth in observation.indicator_depths.items() if languages_for_manifest(name)]
    if not manifest_hits:
        return ObservedLanguages("unknown")

    candidates, shared = _top_depth_candidates(observation, min(manifest_hits))
    if len(candidates) == 1 and not shared:
        # One manifest language at the shallowest depth: the share rule still needs the
        # uncapped count when a manifest for another language sits deeper (FR-010).
        any_depth, any_shared = _top_depth_candidates(observation, None)
        if len(any_depth) == 1 and not any_shared:
            return ObservedLanguages(candidates[0], (candidates[0],))

    counts = count_sources()
    if shared:
        candidates = [_best_by_count(shared, counts) if lang == shared[0] else lang for lang in candidates]
    primary = _best_by_count(candidates, counts)
    included = set(candidates) | set(_source_share_languages(counts))
    return ObservedLanguages(primary, _order_languages(primary, included, counts))


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
