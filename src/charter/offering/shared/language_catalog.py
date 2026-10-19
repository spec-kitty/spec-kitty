"""The one language catalog: tokens, source extensions, manifests, declared patterns, families.

Pure data, no I/O. The activation layer's language authority
(``charter.activation.language_authority``) resolves observed and declared languages
from this table, and :func:`charter.offering.shared.scoping.applies_to_languages_match`
expands families through :func:`expand_language_families`. No other module may hold a
parallel language vocabulary (``tests/architectural/test_single_language_vocabulary.py``).

Specs are listed in tie-break order (``declared_rank`` fixes the declared-output order): when several languages have a manifest at the
same depth and the same source count, the earlier spec wins.

``java`` and ``kotlin`` share the JVM manifests; which of them a repository is comes
from the source counts, never from the manifest alone. Both imply the ``jvm`` family,
which is expanded at match time and never persisted (FR-013).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

__all__ = [
    "BUILD_TOOLS",
    "COMPOUND_PREFIX_GUARD",
    "LANGUAGES",
    "expand_language_families",
    "is_language_family",
    "language_for_extension",
    "languages_for_manifest",
]

#: The family that ``java`` and ``kotlin`` both imply.
JVM_FAMILY = "jvm"

_JVM_MANIFESTS: tuple[str, ...] = (
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "gradlew",
    "mvnw",
)

#: A token preceded by ``word-`` is part of a longer compound name (e.g.
#: ``librespot-java``), not a declaration of that language (#4613). Trailing
#: compounds such as ``Java-based`` still match.
COMPOUND_PREFIX_GUARD = r"(?<!\w-)"


@dataclass(frozen=True, slots=True)
class LanguageSpec:
    """One language: its token, source extensions, manifests, declared patterns and families."""

    token: str
    extensions: tuple[str, ...] = ()
    manifests: tuple[str, ...] = ()
    declared_patterns: tuple[str, ...] = ()
    families: tuple[str, ...] = ()
    #: Position in declared-language output (the order persisted into ``catalog.languages``).
    declared_rank: int = 0


@dataclass(frozen=True, slots=True)
class BuildToolSpec:
    """A build or test tool whose declaration names only a family (never a language)."""

    token: str
    declared_patterns: tuple[str, ...]
    family: str = JVM_FAMILY
    declared_rank: int = 4


LANGUAGES: tuple[LanguageSpec, ...] = (
    LanguageSpec(
        "python",
        declared_rank=0,
        extensions=(".py",),
        manifests=("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"),
        declared_patterns=(r"\bpython\b", r"\bpytest\b", r"\bmypy\b", r"\bruff\b"),
    ),
    LanguageSpec("go", extensions=(".go",), manifests=("go.mod",), declared_rank=9),
    LanguageSpec(
        "rust",
        declared_rank=3,
        extensions=(".rs",),
        manifests=("Cargo.toml",),
        declared_patterns=(r"\brust\b", r"\bcargo\b", r"\brustc\b"),
    ),
    LanguageSpec(
        "java",
        declared_rank=4,
        extensions=(".java",),
        manifests=_JVM_MANIFESTS,
        declared_patterns=(r"\bjava\b",),
        families=(JVM_FAMILY,),
    ),
    LanguageSpec(
        "kotlin",
        declared_rank=5,
        extensions=(".kt",),
        manifests=_JVM_MANIFESTS,
        declared_patterns=(r"\bkotlin\b",),
        families=(JVM_FAMILY,),
    ),
    LanguageSpec(
        "ruby",
        declared_rank=7,
        extensions=(".rb",),
        manifests=("Gemfile",),
        declared_patterns=(r"\bruby\b", r"\brspec\b", r"\brails\b"),
    ),
    LanguageSpec(
        "php",
        declared_rank=8,
        extensions=(".php",),
        manifests=("composer.json",),
        declared_patterns=(r"\bphp\b", r"\bphpunit\b"),
    ),
    LanguageSpec(
        "javascript",
        declared_rank=2,
        extensions=(".js", ".jsx", ".mjs"),
        manifests=("package.json",),
        declared_patterns=(r"\bjavascript\b", r"\bjest\b", r"\bnode(?:\.js)?\b", r"\bnpm\b", r"\bpnpm\b", r"\byarn\b"),
    ),
    LanguageSpec(
        "typescript",
        declared_rank=1,
        extensions=(".ts", ".tsx"),
        declared_patterns=(r"\btypescript\b", r"\btsc\b"),
    ),
    LanguageSpec(
        "swift",
        declared_rank=6,
        extensions=(".swift",),
        declared_patterns=(r"\bswift\b", r"\bxctest\b"),
    ),
)

#: Build and test tools: declared, they add only their family, and only when no
#: language of that family is declared (the build-token rule, FR-013).
BUILD_TOOLS: tuple[BuildToolSpec, ...] = (
    BuildToolSpec("gradle", (r"\bgradle\b",)),
    BuildToolSpec("maven", (r"\bmaven\b",)),
    BuildToolSpec("junit", (r"\bjunit\b",)),
)

#: Family token -> the language tokens that imply it, derived from :data:`LANGUAGES`.
LANGUAGE_FAMILIES: dict[str, tuple[str, ...]] = {
    family: tuple(spec.token for spec in LANGUAGES if family in spec.families) for family in sorted({family for spec in LANGUAGES for family in spec.families})
}

_SPEC_BY_TOKEN: dict[str, LanguageSpec] = {spec.token: spec for spec in LANGUAGES}


def is_language_family(token: str) -> bool:
    """Return True when *token* names a family such as ``jvm``, not a language."""
    return token.strip().lower() in LANGUAGE_FAMILIES


def expand_language_families(tokens: Iterable[str]) -> tuple[str, ...]:
    """Return *tokens* plus the family each language implies (stable order, no duplicates).

    ``["kotlin"]`` becomes ``("kotlin", "jvm")``. A family token never implies its
    members: ``["jvm"]`` stays ``("jvm",)``. Expansion is applied at match time only
    and is never persisted.
    """
    expanded: list[str] = []
    for raw in tokens:
        token = str(raw).strip().lower()
        spec = _SPEC_BY_TOKEN.get(token)
        for item in (token, *(spec.families if spec else ())):
            if item and item not in expanded:
                expanded.append(item)
    return tuple(expanded)


def language_for_extension(extension: str) -> str | None:
    """Return the language token for a source extension (with its leading dot), if any."""
    for spec in LANGUAGES:
        if extension in spec.extensions:
            return spec.token
    return None


def languages_for_manifest(filename: str) -> tuple[str, ...]:
    """Return the languages a manifest filename can belong to, in catalog order."""
    return tuple(spec.token for spec in LANGUAGES if filename in spec.manifests)
