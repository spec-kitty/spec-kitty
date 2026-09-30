"""Architectural dependency test fixtures."""
from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import pytest
from pytestarch import LayeredArchitecture, get_evaluable_architecture

SRC = Path(__file__).resolve().parents[2] / "src"


# ---------------------------------------------------------------------------
# Whole-tree source/AST cache (WP03/T011, FR-009, NFR-007)
# ---------------------------------------------------------------------------
#
# Many architectural boundary tests independently ``rglob("*.py")`` the whole
# ``src/`` tree, then ``read_text`` and/or ``ast.parse`` every file. This
# session fixture does that ONCE and exposes the result as a *read-only* map so
# read-only consumers stop re-walking and re-parsing the tree per test.
#
# READ-ONLY by construction: the public maps are ``MappingProxyType`` (cannot
# be reassigned/popped) and the per-file ``source`` text is an immutable ``str``.
# The cached AST objects are intentionally NOT exposed for mutation — consumers
# read them only. This prevents the classic shared-cache cross-test bleed.
#
# CARVE-OUTS (must NOT use this cache — they need fresh/independent state):
#   * idempotency / "run twice" ratchet tests,
#   * file-existence and freshness tests that assert the tree's on-disk shape,
#   * ``test_real_home_isolation_guard.py`` and ``test_no_prompt_filtering_added.py``
#     (owned by WP02 / WP06 — not touched here).


@dataclass(frozen=True)
class SourceFile:
    """Immutable cached view of one ``src/**/*.py`` file."""

    path: Path
    source: str
    tree: ast.AST


def _build_source_tree_cache() -> Mapping[Path, SourceFile]:
    """Walk ``src/`` once, reading + parsing every ``*.py`` (excluding caches)."""
    entries: dict[Path, SourceFile] = {}
    for path in sorted(SRC.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        entries[path] = SourceFile(path=path, source=source, tree=ast.parse(source))
    return MappingProxyType(entries)


@pytest.fixture(scope="session")
def src_source_tree() -> Mapping[Path, SourceFile]:
    """Read-only ``{path: SourceFile}`` map for every active ``src/**/*.py``.

    Keys are absolute ``Path``s under ``SRC``; values carry the file's source
    text and parsed AST. The returned mapping is a ``MappingProxyType`` —
    consumers can read but not mutate the shared cache (T011 read-only guard).
    """
    return _build_source_tree_cache()


@pytest.fixture(scope="session")
def evaluable():
    """Session-scoped evaluable architecture for all src/ packages.

    Uses SRC as both root and module path so that top-level package names
    are ``src.kernel``, ``src.doctrine``, etc.

    ``exclude_external_libraries`` is **False** so that cross-package
    imports (e.g. ``from specify_cli import X`` inside charter) are
    visible in the dependency graph.  The mypy_cache directory is excluded
    to avoid polluting the graph with cached stubs.
    """
    return get_evaluable_architecture(
        root_path=str(SRC),
        module_path=str(SRC),
        exclude_external_libraries=False,
        exclusions=("*__pycache__*", "*mypy_cache*"),
    )


@pytest.fixture(scope="session")
def landscape():
    """2.x C4 landscape: kernel <- charter <- glossary/runtime/mission_runtime <- specify_cli.

    Each layer includes both the ``src.``-prefixed module path (local source)
    and the bare module name (as seen when the package is installed), so that
    imports resolved through either path are correctly attributed.

    Note (charter-code-topology-01M152G1, S5): the former top-level
    ``doctrine`` layer was dropped. ``src/doctrine`` relocated to
    ``src/charter/offering`` (S2a), so the offering/activation split is now
    an intra-``charter`` sub-package boundary, not a separate landscape
    layer/LayerRule. The single-file ``src/doctrine.py`` CR-06 deprecation
    shim was deleted past its 3.3.0 removal release (#805); no "doctrine"
    layer is mapped here.
    """
    return (
        LayeredArchitecture()
        .layer("kernel")  # type: ignore[attr-defined]
        .containing_modules(["src.kernel", "kernel"])
        .layer("charter")
        .containing_modules(["src.charter", "charter"])
        .layer("glossary")
        .containing_modules(["src.glossary", "glossary"])
        .layer("runtime")
        .containing_modules(["src.runtime", "runtime"])
        .layer("mission_runtime")
        .containing_modules(["src.mission_runtime", "mission_runtime"])
        .layer("specify_cli")
        .containing_modules(["src.specify_cli", "specify_cli"])
    )
