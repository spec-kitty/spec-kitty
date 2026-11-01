"""Single authority for "which ``docs/**/*.md`` files are docs pages".

Every page needs frontmatter, a row in ``docs/development/page-inventory.yaml`` and an entry in
``docs/development/docs-retrieval-index.yaml``. Per-PR changelog fragments in
``docs/changelog/unreleased/`` are not pages: they are entries waiting to be assembled into
``docs/changelog/CHANGELOG.md`` at release time. If they counted as pages, every PR would edit the
two shared generated files again, which is the merge conflict the fragments exist to remove.

Every scanner that walks the docs tree for pages goes through :func:`iter_docs_pages`. The spelling
check is the one deliberate exception: it walks Markdown files, not pages, so it keeps checking
fragments.

Standard library only (plus the fragment directory constant it mirrors).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Final, TypeVar

from scripts.release.changelog_fragments import FRAGMENT_DIR_REL

__all__ = ["FRAGMENT_PAGE_DIR", "is_docs_page", "iter_docs_pages", "lint_config_without_fragments"]

#: The structural lint's frozen config dataclass (loaded from the packs asset at run time).
_LintConfig = TypeVar("_LintConfig", bound=Any)

#: The fragment directory relative to the docs root.
FRAGMENT_PAGE_DIR: Final[str] = FRAGMENT_DIR_REL.removeprefix("docs/")
_NON_PAGE_DIRS: Final[tuple[str, ...]] = (FRAGMENT_PAGE_DIR,)


def is_docs_page(md_path: Path, docs_root: Path) -> bool:
    """Whether *md_path* (a Markdown file under *docs_root*) is a docs page."""
    try:
        relative = md_path.resolve().relative_to(docs_root.resolve()).as_posix()
    except ValueError:
        return True
    return not any(relative == prefix or relative.startswith(f"{prefix}/") for prefix in _NON_PAGE_DIRS)


def iter_docs_pages(docs_root: Path) -> list[Path]:
    """Every docs page under *docs_root*, sorted: ``rglob("*.md")`` minus the non-page directories."""
    return [path for path in sorted(docs_root.rglob("*.md")) if is_docs_page(path, docs_root)]


def lint_config_without_fragments(config: _LintConfig) -> _LintConfig:
    """Overlay the fragment directory onto the structural lint's frontmatter exclusions.

    The lint and its config ship from ``spec-kitty-open-packs`` (``packs/``, not edited in core),
    so core adds the one exclusion it owns here. Once the upstream styleguide lists the directory,
    this overlay is a no-op.
    """
    pattern = f"{FRAGMENT_PAGE_DIR}/**"
    exclusions: tuple[str, ...] = config.frontmatter_in_scope_exclusions
    if pattern in exclusions:
        return config
    return dataclasses.replace(config, frontmatter_in_scope_exclusions=(*exclusions, pattern))
