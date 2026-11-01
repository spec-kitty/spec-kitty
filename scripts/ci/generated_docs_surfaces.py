"""The generated docs surfaces: one definition, standard library only.

The docs retrieval index, the page inventory and the ADR era tables are regenerated on
``main`` after a merge by ``scripts/ci/regen_docs_index.py`` (``docs-index-regen.yml``)
and proposed on :data:`REGEN_BRANCH`; ``scripts/ci/check_generated_docs_untouched.py``
keeps pull requests off them. Both read the definition here. It imports nothing from the
project, so the per-PR guard runs without the project packages (or ``packs/``).
"""

from __future__ import annotations

import re

#: The fixed head branch of the regeneration proposal.
REGEN_BRANCH = "ci/regen-docs-index"

#: The generated files, repo-relative. Pinned against the generators' own constants by
#: ``tests/ci/test_regen_docs_index.py``.
DOCS_INDEX_PATH = "docs/development/docs-retrieval-index.yaml"
PAGE_INVENTORY_PATH = "docs/development/page-inventory.yaml"
GENERATED_FILES = (DOCS_INDEX_PATH, PAGE_INVENTORY_PATH)

#: An ADR era landing page whose index table the regeneration maintains.
ERA_INDEX_RE = re.compile(r"^docs/adr/\d+\.x/(?:index|README)\.md$")


def is_generated_surface(path: str) -> bool:
    """True iff *path* (repo-relative, POSIX) is a surface the regeneration bot owns."""
    return path in GENERATED_FILES or bool(ERA_INDEX_RE.match(path))
