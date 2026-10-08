"""Discovery gate for DRG graph-document emitters that bypass the canonical serializer.

Mission ``doctrine-delivery-activation`` WP05 (contract
``drg-writer-discovery-gate.md`` C3, closes #3075/#2977 iff WP04's C4 also
lands). Complements -- does NOT replace -- the per-member completeness gate
at ``tests/specify_cli/drg_writers/test_registry_completeness.py``: that gate
iterates the *registered* ``DOCUMENT_WRITERS``/``MAPPING_WRITERS`` tuples and
proves every member is field-complete. This gate answers a different
question: are there graph-document emitters in ``src/`` that never joined the
registry at all -- the exact blind spot this WP closes (the registry is
fail-open by design; a writer nobody remembers to add is simply invisible to
the completeness gate)?

This scans ``src/`` **directly** via ``ast`` -- not the registry tuples -- for
two known bypass shapes:

- **Shape (i)** -- a dict literal that hand-restates ``DRGGraph``'s five
  declared top-level keys (``schema_version``, ``generated_at``,
  ``generated_by``, ``nodes``, ``edges``) instead of delegating to
  ``graph_document_to_dict``. The pre-WP05 ``rewrite_opposed_by.py`` /
  ``project_drg.py`` / ``pack_assembler.py`` sites were all this shape.
- **Shape (ii)** -- a ``[x.model_dump() for x in <node/edge collection>]``
  comprehension feeding a hand-built document, bypassing
  ``model_to_graph_dict`` entirely (the ``pack_assembler.py`` variant: it
  also silently emitted ``provenance``, which the canonical path withholds,
  and skipped the omit-when-empty rule).

**Bounded claim** (contract C3, explicit): this gate closes the KNOWN
dict-literal shape and the known ``.model_dump()``-comprehension shape, and
regressions of those two shapes. Graph-document construction via
``merge``/dict-comprehension/``**spread`` remains uncovered -- residual note,
not a defect to chase in this WP.

**Precision-vs-recall scoping note.** Shape (i) requires ALL FIVE of
``DRGGraph``'s declared fields as literal dict keys (not merely
``schema_version``+``nodes``+``edges``): a 3-key superset check also matched
two unrelated ``src/`` sites (``charter/synthesizer/resynthesize_pipeline.py``
and ``specify_cli/cli/commands/charter/_synthesis.py``) that build minimal
*request/response snapshot* dicts from scratch -- never a live ``DRGGraph``
model instance -- and so are outside C1's "serializes a ``DRGGraph``" scope.
Requiring the full 5-key set (verified empirically against the real
pre-fix ``src/`` tree) catches exactly the three real hand-restating sites
and excludes both non-``DRGGraph`` snapshot builders, since a genuine
document-restating bug restates the *whole* document shape (that is
definitionally what "hand-restates the document" means), not just three of
its five fields.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_SRC = Path(__file__).resolve().parents[2] / "src"

#: The canonical serializer's own module. ``graph_document_to_dict`` builds
#: its output via ``data[field_name] = value`` (dynamic subscript
#: assignment), never an ``ast.Dict`` literal naming all five keys, so this
#: exclusion is defensive/future-proofing rather than load-bearing against
#: today's implementation.
_CANONICAL_MODULE = (_SRC / "doctrine" / "drg" / "migration" / "extractor.py").resolve()

#: All five of ``DRGGraph``'s declared fields (``src/charter/offering/drg/models.py``).
#: See the module docstring's "Precision-vs-recall scoping note" for why this
#: is the full 5-key set rather than a 3-key subset.
_DOCUMENT_KEYS: frozenset[str] = frozenset(
    {"schema_version", "generated_at", "generated_by", "nodes", "edges"}
)


# ---------------------------------------------------------------------------
# AST plumbing shared by both detectors
# ---------------------------------------------------------------------------


def _iter_python_sources(root: Path) -> list[tuple[Path, ast.AST]]:
    """Parse every ``*.py`` under *root* once.

    Standalone helper for the self-mutation fixture scans below. The
    real-``src/`` scans reuse the session-scoped ``src_source_tree`` fixture
    (``tests/architectural/conftest.py``) instead, per this repo's
    collect-universe-once discipline -- this helper exists only for the
    small, independent ``tmp_path`` fixture trees the mutation battery
    writes.
    """
    sources: list[tuple[Path, ast.AST]] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        sources.append((path, ast.parse(text, filename=str(path))))
    return sources


class _ParentLinks(ast.NodeVisitor):
    """Builds an ``id(child) -> parent`` map for one module's AST."""

    def __init__(self) -> None:
        self.parents: dict[int, ast.AST] = {}

    def generic_visit(self, node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            self.parents[id(child)] = node
        super().generic_visit(node)


def _enclosing_qualname(node: ast.AST, parents: dict[int, ast.AST]) -> str | None:
    """Dotted qualname of the nearest enclosing function/class, or ``None`` at module scope."""
    parts: list[str] = []
    current = parents.get(id(node))
    while current is not None:
        if isinstance(current, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            parts.append(current.name)
        current = parents.get(id(current))
    return ".".join(reversed(parts)) if parts else None


def _module_dotted_name(path: Path, root: Path) -> str:
    """``src/charter/offering/packs/pack_assembler.py`` -> ``charter.offering.packs.pack_assembler``."""
    rel_parts = path.relative_to(root).with_suffix("").parts
    if rel_parts and rel_parts[-1] == "__init__":
        rel_parts = rel_parts[:-1]
    return ".".join(rel_parts)


def registered_writer_qualnames() -> frozenset[str]:
    """``module.qualname`` for every live registry member's backing callable.

    Cross-referenced by qualified name (T022 step 3/4) instead of a
    hand-maintained second "known writers" allowlist, so this gate cannot
    drift from ``specify_cli.drg_writers.registry`` the way the three
    bypassed sites drifted from the completeness gate before this WP.
    """
    from specify_cli.drg_writers.registry import DOCUMENT_WRITERS, MAPPING_WRITERS

    names: set[str] = set()
    for doc_writer in DOCUMENT_WRITERS:
        fn = getattr(doc_writer, "document_fn", None)
        if fn is not None:
            names.add(f"{fn.__module__}.{fn.__qualname__}")
    for mapping_writer in MAPPING_WRITERS:
        for attr_name in ("node_fn", "edge_fn"):
            fn = getattr(mapping_writer, attr_name, None)
            if fn is not None:
                names.add(f"{fn.__module__}.{fn.__qualname__}")
    return frozenset(names)


def _is_excluded(path: Path, qualname: str | None, module_dotted: str, registered: frozenset[str]) -> bool:
    if path.resolve() == _CANONICAL_MODULE:
        return True
    full_name = f"{module_dotted}.{qualname}" if qualname else module_dotted
    return full_name in registered


# ---------------------------------------------------------------------------
# Shape (i) -- dict literal hand-restating the document's five top-level keys
# ---------------------------------------------------------------------------


def _dict_literal_keys(node: ast.Dict) -> set[str]:
    """Literal string keys of *node*; dynamic/spread keys are ignored (not restatements)."""
    return {
        key.value
        for key in node.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }


def find_dict_literal_document_emitters(
    sources: Iterable[tuple[Path, ast.AST]],
    *,
    module_root: Path,
    registered: frozenset[str],
) -> list[str]:
    """Shape (i): flag dict literals restating all five ``DRGGraph`` document keys.

    Returns one ``"path:line: <reason>"`` string per offending literal that is
    neither inside the canonical serializer's own module nor attributed (by
    qualified enclosing-function name) to a registered writer.
    """
    offenders: list[str] = []
    for path, tree in sources:
        parents = _ParentLinks()
        parents.visit(tree)
        module_dotted = _module_dotted_name(path, module_root)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            if not (_dict_literal_keys(node) >= _DOCUMENT_KEYS):
                continue
            qualname = _enclosing_qualname(node, parents.parents)
            if _is_excluded(path, qualname, module_dotted, registered):
                continue
            offenders.append(
                f"{path}:{node.lineno}: dict literal restates DRGGraph's document "
                f"keys {sorted(_DOCUMENT_KEYS)} instead of delegating to "
                "graph_document_to_dict"
            )
    return offenders


# ---------------------------------------------------------------------------
# Shape (ii) -- raw .model_dump() over a node/edge collection
# ---------------------------------------------------------------------------


def _is_model_dump_call(expr: ast.expr) -> bool:
    return (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Attribute)
        and expr.func.attr == "model_dump"
    )


def _comprehension_looks_node_or_edge_shaped(comp: ast.comprehension) -> bool:
    """Bounded heuristic: the comprehension's iterable name mentions node/edge.

    Pure ``ast`` cannot type-infer whether an arbitrary expression is a
    ``DRGNode``/``DRGEdge`` collection, so this matches on the unparsed
    source text of the iterable containing "node" or "edge"
    (case-insensitive) -- e.g. ``graph.nodes``, ``kept_edges``. This is the
    exact shape of the real ``pack_assembler.py`` bypass this gate was
    written to catch (residual note: a differently-named local variable
    would not be caught -- see the module docstring's bounded claim).
    """
    text = ast.unparse(comp.iter).lower()
    return "node" in text or "edge" in text


def find_model_dump_document_emitters(
    sources: Iterable[tuple[Path, ast.AST]],
    *,
    module_root: Path,
    registered: frozenset[str],
) -> list[str]:
    """Shape (ii): flag ``[x.model_dump() for x in <node/edge-like>]`` comprehensions.

    This is the ``pack_assembler.py`` bypass shape: raw ``.model_dump()``
    calls over a node/edge collection feeding a hand-built document,
    dropping ``FIELDS_WITHHELD_FROM_GRAPH_OUTPUT`` and the omit-when-empty
    rule that ``model_to_graph_dict`` applies. Independent of
    :func:`find_dict_literal_document_emitters` -- proven separately by the
    self-mutation battery below (NFR-006).
    """
    offenders: list[str] = []
    for path, tree in sources:
        parents = _ParentLinks()
        parents.visit(tree)
        module_dotted = _module_dotted_name(path, module_root)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ListComp | ast.SetComp | ast.GeneratorExp):
                continue
            if not _is_model_dump_call(node.elt):
                continue
            if not any(
                _comprehension_looks_node_or_edge_shaped(gen) for gen in node.generators
            ):
                continue
            qualname = _enclosing_qualname(node, parents.parents)
            if _is_excluded(path, qualname, module_dotted, registered):
                continue
            offenders.append(
                f"{path}:{node.lineno}: raw .model_dump() comprehension over a "
                "node/edge-shaped collection instead of delegating through "
                "model_to_graph_dict"
            )
    return offenders


# ---------------------------------------------------------------------------
# Live gate -- the real src/ tree must be green (T023 step 3)
# ---------------------------------------------------------------------------


def test_dict_literal_gate_is_green_against_the_real_src_tree(
    src_source_tree: Mapping[Path, object],
) -> None:
    """A1: after T020/T021, no ``src/`` site hand-restates the document dict."""
    sources = [(path, sf.tree) for path, sf in src_source_tree.items()]  # type: ignore[attr-defined]
    offenders = find_dict_literal_document_emitters(
        sources, module_root=_SRC, registered=registered_writer_qualnames()
    )
    assert offenders == [], (
        "graph-document dict-literal bypass(es) found -- route through "
        "graph_document_to_dict and register the site as a DocumentWriter in "
        "specify_cli.drg_writers.registry:\n  " + "\n  ".join(offenders)
    )


def test_model_dump_gate_is_green_against_the_real_src_tree(
    src_source_tree: Mapping[Path, object],
) -> None:
    """A1: after T020/T021, no ``src/`` site raw-``model_dump()``s a node/edge collection."""
    sources = [(path, sf.tree) for path, sf in src_source_tree.items()]  # type: ignore[attr-defined]
    offenders = find_model_dump_document_emitters(
        sources, module_root=_SRC, registered=registered_writer_qualnames()
    )
    assert offenders == [], (
        "raw .model_dump() graph-document bypass(es) found -- route through "
        "graph_document_to_dict/model_to_graph_dict and register the site as "
        "a DocumentWriter:\n  " + "\n  ".join(offenders)
    )


# ---------------------------------------------------------------------------
# Self-mutation battery (NFR-006 non-vacuity) -- BOTH shapes, independently
# ---------------------------------------------------------------------------
#
# D-M5/C3 (binding): a single dict-literal mutation would leave clause (ii) --
# the shape that actually motivated this gate (pack_assembler.py) -- unproven.
# Each fixture below is deliberately shaped so it trips ONLY its own
# detector: fixture (i) never calls .model_dump(); fixture (ii) builds its
# document via subscript assignment on an EMPTY dict literal (zero keys), not
# a keyed literal, so the dict-literal detector cannot accidentally catch it.
# Each test asserts both directions -- its own detector reds, the sibling
# detector stays silent -- so a regression in either detector's teeth is
# caught by name, not just by an overall true/false signal (memory: "gate-
# unmask can't self-validate" / "no RecursionError is not no cycle").
#
# Fixtures are written to `tmp_path`, never to real `src/` (T023 note): CI
# must never have a moment where the actual codebase contains the
# deliberately-broken writer.

_UNREGISTERED_DICT_LITERAL_FIXTURE = '''
"""Fixture: an unregistered dict-literal graph-document writer (shape i)."""


def bad_write_graph(graph):
    payload = {
        "schema_version": graph.schema_version,
        "generated_at": graph.generated_at,
        "generated_by": graph.generated_by,
        "nodes": [_node_to_dict(n) for n in graph.nodes],
        "edges": [_edge_to_dict(e) for e in graph.edges],
    }
    return payload
'''

_UNREGISTERED_MODEL_DUMP_FIXTURE = '''
"""Fixture: an unregistered .model_dump()-shaped graph-document writer (shape ii)."""


def bad_pack_writer(graph, kept_edges):
    document = {}
    document["schema_version"] = graph.schema_version
    document["generated_at"] = graph.generated_at
    document["generated_by"] = graph.generated_by
    document["nodes"] = [n.model_dump() for n in graph.nodes]
    document["edges"] = [e.model_dump() for e in kept_edges]
    return document
'''


def _write_fixture_tree(tmp_path: Path, filename: str, content: str) -> Path:
    fixture_root = tmp_path / "fixture_src"
    fixture_root.mkdir(exist_ok=True)
    (fixture_root / filename).write_text(content, encoding="utf-8")
    return fixture_root


def test_self_mutation_dict_literal_writer_reds_independently(tmp_path: Path) -> None:
    """NFR-006/A2 (a): an unregistered shape-(i) writer reds -- and ONLY via
    the dict-literal detector, proving the two detectors are independent."""
    fixture_root = _write_fixture_tree(
        tmp_path, "unregistered_document_writer.py", _UNREGISTERED_DICT_LITERAL_FIXTURE
    )
    sources = _iter_python_sources(fixture_root)

    dict_offenders = find_dict_literal_document_emitters(
        sources, module_root=fixture_root, registered=frozenset()
    )
    assert dict_offenders, "shape (i) fixture did not red the dict-literal detector"

    model_dump_offenders = find_model_dump_document_emitters(
        sources, module_root=fixture_root, registered=frozenset()
    )
    assert not model_dump_offenders, (
        "shape (i) fixture unexpectedly tripped the model_dump detector too -- "
        f"the two detectors are not independent: {model_dump_offenders}"
    )


def test_self_mutation_model_dump_writer_reds_independently(tmp_path: Path) -> None:
    """NFR-006/A2 (b): an unregistered shape-(ii) writer reds -- and ONLY via
    the model_dump detector, proving the two detectors are independent.

    This is the shape that actually motivated the gate (``pack_assembler.py``,
    #3075) -- D-M5 requires this fixture to be proven separately from shape
    (i), not merely implied by it.
    """
    fixture_root = _write_fixture_tree(
        tmp_path, "unregistered_pack_writer.py", _UNREGISTERED_MODEL_DUMP_FIXTURE
    )
    sources = _iter_python_sources(fixture_root)

    model_dump_offenders = find_model_dump_document_emitters(
        sources, module_root=fixture_root, registered=frozenset()
    )
    assert model_dump_offenders, "shape (ii) fixture did not red the model_dump detector"

    dict_offenders = find_dict_literal_document_emitters(
        sources, module_root=fixture_root, registered=frozenset()
    )
    assert not dict_offenders, (
        "shape (ii) fixture unexpectedly tripped the dict-literal detector too -- "
        f"the two detectors are not independent: {dict_offenders}"
    )


def test_self_mutation_writers_green_once_delegating(tmp_path: Path) -> None:
    """Sanity check on the fixtures themselves: a delegating rewrite of the
    shape-(i) fixture no longer reds either detector -- the gate is not
    permanently red for the module, only for the undelegated construct."""
    fixed_source = '''
"""Fixture: the shape (i) writer, fixed to delegate."""

from charter.offering.drg.migration.extractor import graph_document_to_dict


def good_write_graph(graph):
    return graph_document_to_dict(graph)
'''
    fixture_root = _write_fixture_tree(tmp_path, "fixed_document_writer.py", fixed_source)
    sources = _iter_python_sources(fixture_root)

    assert not find_dict_literal_document_emitters(
        sources, module_root=fixture_root, registered=frozenset()
    )
    assert not find_model_dump_document_emitters(
        sources, module_root=fixture_root, registered=frozenset()
    )
