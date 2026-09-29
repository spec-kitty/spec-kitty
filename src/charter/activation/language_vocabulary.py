"""Doctrine-derived vocabulary of language identifiers that have specialist guidance.

Operator decision (2026-09-29, #5284): Spec Kitty doctrine is tech-agnostic.
A language is *known* only when some doctrine artifact is scoped to it via
``applies_to_languages``; ``unknown`` therefore means "no specialist guidance
exists for this project's language", never "the language is bad".  Reading the
vocabulary from the packs (rather than hardcoding a list) keeps the
recogniser in step with whatever doctrine ships, or a project/org extends
(C-001, FR-017).

The provider is a lightweight YAML scan of the ``applies_to_languages`` field
(built-in packs, the project overlay, configured org pack roots).  It
deliberately does not construct a ``DoctrineService`` (sole-door gates) and
never imports :mod:`charter.activation.language_scope`, which calls it.
"""

from __future__ import annotations

import functools
import re
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.activation._doctrine_paths import resolve_project_root
from charter.offering.artifact_kinds import PROJECT_KIND_DIRS, ArtifactKind
from charter.offering.drg.org_pack_config import resolve_existing_org_roots
from charter.offering.pack_paths import built_in_dir
from charter.offering.shared.scoping import (
    RESERVED_LANGUAGE_TOKENS,
    SENTINEL_LANGUAGE_TOKENS,
    normalize_languages,
)

__all__ = ["scoped_language_vocabulary"]

_SCOPE_FIELD = "applies_to_languages"

#: A scope item is a language token only when it is a single word.
_LANGUAGE_WORD = re.compile(r"\w+")

#: Memoised roots kept; a long-lived process sees few distinct repositories.
_VOCABULARY_CACHE_SIZE = 8

#: Artifact kinds whose models carry ``applies_to_languages``.
_LANGUAGE_SCOPED_KINDS: tuple[ArtifactKind, ...] = (
    ArtifactKind.TACTIC,
    ArtifactKind.STYLEGUIDE,
    ArtifactKind.TOOLGUIDE,
    ArtifactKind.PROCEDURE,
    ArtifactKind.AGENT_PROFILE,
)


def _is_language_word(item: object) -> bool:
    """Return True for a ``str`` scope item that is a single word (``None``/numbers/phrases are not languages)."""
    return isinstance(item, str) and _LANGUAGE_WORD.fullmatch(item.strip()) is not None


def _scoped_tokens_in_dir(directory: Path, pattern: str) -> set[str]:
    """Return the raw ``applies_to_languages`` tokens of every artifact under *directory*."""
    if not directory.is_dir():
        return set()
    yaml = YAML(typ="safe")
    tokens: set[str] = set()
    for path in sorted(directory.rglob(pattern)):
        try:
            text = path.read_text(encoding="utf-8")
            if _SCOPE_FIELD not in text:
                continue
            data = yaml.load(text)
        except (OSError, YAMLError, UnicodeDecodeError):
            continue
        scope = data.get(_SCOPE_FIELD) if isinstance(data, dict) else None
        if isinstance(scope, list):
            tokens.update(normalize_languages(item for item in scope if _is_language_word(item)))
    return tokens


def _kind_directories(kind: ArtifactKind, repo_root: Path | None) -> list[Path]:
    """Built-in, project-overlay and org-pack directories that may hold *kind* artifacts."""
    directories = [built_in_dir(kind)]
    if repo_root is None:
        return directories
    project_root = resolve_project_root(repo_root)
    if project_root is not None:
        directories.append(project_root / PROJECT_KIND_DIRS[kind])
    for org_root in resolve_existing_org_roots(repo_root):
        directories.extend(org_root / name for name in dict.fromkeys((kind.plural, PROJECT_KIND_DIRS[kind])))
    return directories


@functools.lru_cache(maxsize=_VOCABULARY_CACHE_SIZE)
def scoped_language_vocabulary(repo_root: Path | None) -> frozenset[str]:
    """Return every language some doctrine artifact is scoped to (``None`` = built-in only).

    Reserved (``unknown``) and sentinel (``any``/``all``) tokens are never
    vocabulary.  Memoised per root (bounded LRU); ``scoped_language_vocabulary.cache_clear()``
    resets it.
    """
    tokens: set[str] = set()
    for kind in _LANGUAGE_SCOPED_KINDS:
        for directory in _kind_directories(kind, repo_root):
            tokens |= _scoped_tokens_in_dir(directory, kind.glob_pattern)
    return frozenset(tokens - RESERVED_LANGUAGE_TOKENS - SENTINEL_LANGUAGE_TOKENS)
