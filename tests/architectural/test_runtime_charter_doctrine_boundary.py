"""Runtime reaches doctrine through the charter boundary."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.architectural._ast_scan import parse_file, read_source
from tests.architectural.test_doctrine_census import (
    EXEMPT_MANAGEMENT_SURFACE,
    _doctrine_paths,
    _is_doctrine_name,
)


pytestmark = [pytest.mark.architectural]

_REPO_ROOT = Path(__file__).resolve().parents[2]
# Scanned roots are an EXPLICIT LIST (#3522): the boundary must examine every
# package that reaches doctrine, and adding a src/ package to the scan is a
# visible, reviewed decision — not an accident of a single hardcoded root.
# ``src/runtime`` was silently unscanned before (the #3522 gap: a direct
# doctrine import there passed CI); it is now a first-class scan root.
_SCAN_ROOTS: tuple[Path, ...] = (
    _REPO_ROOT / "src" / "specify_cli",
    _REPO_ROOT / "src" / "runtime",
)
_EXEMPT_SUBPACKAGE = _REPO_ROOT / "src" / "specify_cli" / "doctrine"


def _has_module_level_doctrine_import(source: str) -> bool:
    visitor = _LazyDoctrineVisitor()
    visitor.visit(ast.parse(source))
    return bool(visitor.module_paths)


def _is_exempt_subpackage(path: Path) -> bool:
    try:
        path.relative_to(_EXEMPT_SUBPACKAGE)
    except ValueError:
        return False
    return True


def _iter_runtime_python_files() -> list[Path]:
    return sorted(path for root in _SCAN_ROOTS for path in root.rglob("*.py"))


def _rel_to_repo(path: Path) -> str:
    return str(path.relative_to(_REPO_ROOT))


def test_boundary_predicate_has_prohibited_and_compliant_controls() -> None:
    assert _has_module_level_doctrine_import("from charter.offering.resolver import resolve_profile\n")
    assert not _has_module_level_doctrine_import("from charter.profiles import resolve_profile\n")


def test_runtime_has_no_direct_doctrine_imports() -> None:
    violators: list[str] = []
    for path in _iter_runtime_python_files():
        if _is_exempt_subpackage(path):
            continue
        source = read_source(path)
        if _has_module_level_doctrine_import(source):
            violators.append(_rel_to_repo(path))

    assert not violators, "runtime must reach doctrine through charter; direct imports: " + ", ".join(violators)


# ===========================================================================
# WP04 — Sibling lazy-import ratchet + source-side laundering guard
# ===========================================================================
#
# The module-level ratchet descends control-flow blocks but leaves imports in
# function/class bodies to the lazy ratchet. Both use the same scope-tracking
# visitor, so imports cannot fall between the two classifications. This
# section provides the sibling ratchet (FR-006 / SC-003) plus the SOURCE-side
# re-export-laundering guard (C-005 / FR-004). The two ratchets stay separate:
# the module-level baseline above remains EMPTY; lazy file/import pairs are pinned here.
#
# Mechanism (T017): a **parent-tracking recursive descent** — NOT bare
# ``ast.walk``, which flattens the tree and loses the enclosing-block context
# needed to (a) skip ``if TYPE_CHECKING:`` imports (erased at runtime; not a real
# reach-through) and (b) tell a module-level import (owned by the ratchet above)
# from a lazy nested one. The visitor tracks ``(nesting_depth, TYPE_CHECKING
# depth)`` and flags only depth>0, non-TYPE_CHECKING doctrine imports.
#
# Known limits (T020):
#   * Bare ``import charter.offering`` (path/metadata introspection, e.g.
#     tool_surface/bundles/codex.py reading ``charter.offering.__file__``) IS matched by
#     the descent — it is a level-0 absolute ``doctrine`` name — so a file that
#     only does metadata introspection still appears in the lazy baseline. It is
#     classified INTERNAL-METADATA in WP01's census (FR-006 exempt at the
#     disposition layer), but the ratchet's job is only "does not regrow", so it
#     is pinned like any other baseline entry and migrates out with its file.
#   * Aliased imports (``import charter.offering.x as dx`` / ``from charter.offering.x import y as
#     z``) are matched on the *source* module path, not the local alias, so an
#     alias cannot hide a reach-through.
#   * Dynamic imports (``importlib.import_module("charter.offering.x")``) are invisible to
#     a static AST scan. Zero exist today; the "cannot silently regrow" guarantee
#     is therefore bounded to *static* imports (C3 "Known limit").


_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "doctrine_boundary"


#: Measured 2026-09-06: 11 file/import pairs across six files. Whole-file
#: exceptions hid added reaches (#3522); pin exact modules and evict each pair
#: when it migrates, even if another import remains in the same file.
_LAZY_BASELINE_ALLOWLIST: frozenset[tuple[str, str]] = frozenset(
    {
        # #3179: wrapped sole-door service construction for asset operations.
        ("src/specify_cli/cli/commands/_doctrine_asset.py", "charter.offering.service"),
        # #3179: wrapped raw service for unfiltered diagnostic repositories.
        ("src/specify_cli/cli/commands/_doctrine_collect.py", "charter.offering.service"),
        # #3179: existing operating-procedure diagnostics, pending facade migration.
        ("src/specify_cli/cli/commands/_doctrine_collect.py", "charter.offering.agent_profiles.operating_procedures"),
        # #3179: diagnostic node-kind classification, pending charter.drg migration.
        ("src/specify_cli/cli/commands/_doctrine_collect.py", "charter.offering.artifact_kinds"),
        # #3179: built-in graph for diagnostics, pending charter.drg migration.
        ("src/specify_cli/cli/commands/_doctrine_collect.py", "charter.offering.drg.loader"),
        # #3179: doorless override-audit management internal (TICKETED-BASELINE).
        ("src/specify_cli/cli/commands/_doctrine_collect.py", "charter.offering.drg.override_policy"),
        # #3179: diagnostic pack location, pending facade migration.
        ("src/specify_cli/cli/commands/_doctrine_collect.py", "charter.offering.pack_paths"),
        # #3179: doorless DRG-regeneration internal (TICKETED-BASELINE).
        ("src/specify_cli/cli/commands/doctrine.py", "charter.offering.drg.migration.hand_authored_overlay"),
        # #3179: package __file__ metadata, not a symbol reach-through.
        ("src/specify_cli/tool_surface/bundles/codex.py", "charter.offering"),
        # #3522: pre-existing step-contract reach, charter.missions migration #2173.
        ("src/runtime/next/runtime_bridge_composition.py", "charter.offering.missions.step_contracts"),
        # #3522: pre-existing step-projection reach, charter.missions migration #2173.
        ("src/runtime/next/runtime_bridge_io.py", "charter.offering.missions.step_projection"),
    }
)


#: SOURCE-side laundering baseline. Each entry is a ``src/specify_cli/doctrine/*``
#: module that re-exports doctrine-origin symbols through its own ``__all__`` — a
#: first-party re-export "laundering" conduit. ``config.py`` re-exports the
#: shared org-pack-config contract; WP05 closes the conduit, which forces the
#: stale-entry eviction below. A consumer-side check is impossible: ``from
#: specify_cli.doctrine.config import load_pack_registry`` (laundered) and ``…
#: import assert_pack_local_paths_exist`` (genuine first-party) are byte-identical
#: import syntax, so the rule must be enforced at the SOURCE module's ``__all__``.
# WP05 (01KZPDSR / C-005, FR-004) CLOSED the ``config.py`` conduit: the
# doctrine-origin org-pack-config symbols are no longer listed in
# ``config.__all__``, so the module launders nothing and the baseline is empty.
# The module-level bindings survive for in-surface + management-surface-test
# consumers, but ``__all__`` is the enforced surface (a consumer-side check is
# impossible — see the note above), so an empty baseline is the closed state.
_LAUNDERING_BASELINE: dict[str, frozenset[str]] = {}


def _is_type_checking_guard(test: ast.expr) -> bool:
    """True for ``if TYPE_CHECKING:`` / ``if typing.TYPE_CHECKING:`` guards."""
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"
    return False


class _LazyDoctrineVisitor(ast.NodeVisitor):
    """Parent-tracking descent separating module-level and nested doctrine imports.

    Tracks ``(nesting_depth, type_checking_depth)`` so it can:

    * skip any doctrine import that lives under an ``if TYPE_CHECKING:`` guard
      (it is erased at runtime — not a real reach-through), and
    * distinguish a *module-level* import (``nesting_depth == 0`` — owned by the
      module-level ratchet, whose baseline stays empty) from a *lazy* import
      nested inside a function/class body (``nesting_depth > 0``).

    Outside TYPE_CHECKING blocks, absolute imports at ``nesting_depth > 0``
    contribute to :attr:`paths`; depth-zero imports contribute to
    :attr:`module_paths`, including those inside module-level control flow.
    """

    def __init__(self) -> None:
        self.paths: set[str] = set()
        self.module_paths: set[str] = set()
        self._nesting_depth = 0
        self._type_checking_depth = 0

    def _record(self, node: ast.AST) -> None:
        if self._type_checking_depth:
            return
        paths = self.paths if self._nesting_depth else self.module_paths
        paths.update(_doctrine_paths(node))

    def visit_Import(self, node: ast.Import) -> None:
        self._record(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._record(node)

    def visit_If(self, node: ast.If) -> None:
        guarded = _is_type_checking_guard(node.test)
        if guarded:
            self._type_checking_depth += 1
        for child in node.body:
            self.visit(child)
        if guarded:
            self._type_checking_depth -= 1
        for child in node.orelse:
            self.visit(child)

    def _visit_scope(self, node: ast.AST) -> None:
        self._nesting_depth += 1
        self.generic_visit(node)
        self._nesting_depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_scope(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_scope(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_scope(node)


def _file_lazy_doctrine_paths(path: Path) -> set[str]:
    """Exact lazy (nested, non-TYPE_CHECKING) doctrine import modules in a file."""
    tree = parse_file(path)
    visitor = _LazyDoctrineVisitor()
    visitor.visit(tree)
    return visitor.paths


def _file_has_lazy_doctrine_import(path: Path) -> bool:
    """True iff ``path`` performs a lazy (nested, non-TYPE_CHECKING) doctrine import."""
    return bool(_file_lazy_doctrine_paths(path))


def _lazy_doctrine_violators() -> set[tuple[str, str]]:
    """Lazy file/import pairs outside the exempt management surface."""
    violators: set[tuple[str, str]] = set()
    for path in _iter_runtime_python_files():
        if _is_exempt_subpackage(path):
            continue
        violators.update((_rel_to_repo(path), module) for module in _file_lazy_doctrine_paths(path))
    return violators


def _format_lazy_ratchet_failure(*, new_violators: list[tuple[str, str]], stale_allowlist_entries: list[tuple[str, str]]) -> str:
    parts: list[str] = []
    if new_violators:
        bullets = "\n  - ".join(f"{file} -> {module}" for file, module in new_violators)
        parts.append(
            "Lazy (function-body) doctrine reach-through. The following file/import pairs under\n"
            "the scanned roots (src/specify_cli/, src/runtime/) introduce a NEW nested\n"
            "`from charter.offering.*` / `import\n"
            "doctrine` import (outside `if TYPE_CHECKING:` and outside the\n"
            "src/specify_cli/doctrine/ management surface) that is not in the\n"
            "lazy baseline:\n"
            f"  - {bullets}\n"
            "\n"
            "Fix: route the access through the charter proxy (charter.profiles,\n"
            "charter.drg, charter.missions, charter.model_routing, charter.assets,\n"
            "…). A lazy import is not exempt from the boundary. See\n"
            "docs/development/runtime-charter-doctrine-boundary.md."
        )
    if stale_allowlist_entries:
        bullets = "\n  - ".join(f"{file} -> {module}" for file, module in stale_allowlist_entries)
        parts.append(
            "Stale lazy-import baseline entries. The following pairs are listed in\n"
            "`_LAZY_BASELINE_ALLOWLIST` but no longer perform that lazy doctrine import\n"
            "(a migration landed):\n"
            f"  - {bullets}\n"
            "\n"
            "Fix: remove those entries from `_LAZY_BASELINE_ALLOWLIST` so the ratchet\n"
            "shrinks with the migration (only-shrink invariant)."
        )
    return "\n\n".join(parts)


def _declared_all(tree: ast.Module) -> set[str] | None:
    """Return the string members of a module-level ``__all__`` literal, else None."""
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            continue
        value = node.value
        if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
            return {elt.value for elt in value.elts if isinstance(elt, ast.Constant) and isinstance(elt.value, str)}
    return None


def _doctrine_origin_names(tree: ast.Module) -> set[str]:
    """Local names bound by a direct ``from charter.offering…`` / ``import charter.offering`` import.

    Block context is irrelevant to laundering — a doctrine-origin name that
    appears in ``__all__`` is laundering regardless of where it was imported — so
    a flat ``ast.walk`` is correct here (unlike the reach-through ratchet, which
    needs the enclosing-block context). The bound *local* name (``asname`` when
    aliased) is what could appear in ``__all__``.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if not _doctrine_paths(node):
                continue
            for alias in node.names:
                if node.module != "charter" or alias.name == "offering":
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _is_doctrine_name(alias.name):
                    names.add(alias.asname or alias.name.split(".")[0])
    return names


def _laundered_symbols(tree: ast.Module) -> set[str]:
    """Doctrine-origin symbols a module re-exports through its own ``__all__``."""
    declared = _declared_all(tree)
    if not declared:
        return set()
    return declared & _doctrine_origin_names(tree)


def _source_side_laundering() -> dict[str, frozenset[str]]:
    """Map each management-surface module → the doctrine symbols it launders."""
    result: dict[str, frozenset[str]] = {}
    for path in sorted(_EXEMPT_SUBPACKAGE.rglob("*.py")):
        tree = parse_file(path)
        laundered = _laundered_symbols(tree)
        if laundered:
            result[_rel_to_repo(path)] = frozenset(laundered)
    return result


def test_exempt_surface_matches_wp01_manifest() -> None:
    """The lazy ratchet's exempt root is exactly WP01's enumerated management surface.

    Binds this file's exemption to a single source (WP01's ``EXEMPT_MANAGEMENT_SURFACE``)
    so the two cannot drift.
    """
    assert {_rel_to_repo(_EXEMPT_SUBPACKAGE)} == set(EXEMPT_MANAGEMENT_SURFACE)


def test_lazy_detector_skips_type_checking_fixture() -> None:
    """Fixture proof (T020): a ``TYPE_CHECKING`` doctrine import is NOT flagged."""
    assert _file_has_lazy_doctrine_import(_FIXTURES_DIR / "type_checking_import.py") is False


def test_lazy_detector_flags_nested_function_fixture() -> None:
    """Fixture proof (T020): a nested-function doctrine import IS flagged."""
    assert _file_has_lazy_doctrine_import(_FIXTURES_DIR / "nested_function_import.py") is True


def test_lazy_ratchet_arithmetic_is_bidirectional() -> None:
    """Gate efficacy: prove both failure directions without mutating the tree.

    A new violator (present, not baselined) is caught by ``actual - baseline``; a
    stale entry (baselined, migrated away) is caught by ``baseline - actual``.
    """
    baseline = frozenset({"a.py", "b.py"})
    grown = {"a.py", "b.py", "c.py"}
    assert sorted(grown - baseline) == ["c.py"]
    assert not (baseline - grown)
    shrunk = {"a.py"}
    assert not (shrunk - baseline)
    assert sorted(baseline - shrunk) == ["b.py"]


def test_runtime_has_no_new_lazy_doctrine_imports() -> None:
    """Pin the LAZY doctrine reach-through as an only-shrink ratchet (FR-006 / SC-003).

    A new file/import pair fails even in an already-baselined file. Migrating
    one import without evicting its pair fails even if that file still reaches
    other doctrine modules. This preserves each measured reach independently.
    """
    actual_violators = _lazy_doctrine_violators()

    new_violators = sorted(actual_violators - _LAZY_BASELINE_ALLOWLIST)
    stale_allowlist_entries = sorted(_LAZY_BASELINE_ALLOWLIST - actual_violators)

    assert not new_violators and not stale_allowlist_entries, _format_lazy_ratchet_failure(
        new_violators=new_violators,
        stale_allowlist_entries=stale_allowlist_entries,
    )


def test_source_side_no_new_doctrine_laundering() -> None:
    """Pin the SOURCE-side re-export-laundering surface (C-005 / FR-004).

    No ``src/specify_cli/doctrine/*`` module may add a doctrine-origin symbol to
    its ``__all__`` beyond the documented baseline (currently ``config.py``). A
    new laundering module/symbol trips the "grow" direction; when WP05 closes the
    ``config.py`` conduit, the "stale" direction forces the baseline eviction.
    """
    actual = _source_side_laundering()

    new_launderers = {
        path: sorted(symbols - _LAUNDERING_BASELINE.get(path, frozenset()))
        for path, symbols in actual.items()
        if symbols - _LAUNDERING_BASELINE.get(path, frozenset())
    }
    stale_baseline = {
        path: sorted(_LAUNDERING_BASELINE[path] - actual.get(path, frozenset()))
        for path in _LAUNDERING_BASELINE
        if _LAUNDERING_BASELINE[path] - actual.get(path, frozenset())
    }

    assert not new_launderers and not stale_baseline, (
        "Source-side doctrine re-export laundering drift.\n\n"
        f"New/extra laundered symbols (a src/specify_cli/doctrine/* module lists a\n"
        f"doctrine-origin name in its __all__ beyond the baseline): {new_launderers}\n\n"
        f"Stale baseline entries (a conduit was closed — shrink _LAUNDERING_BASELINE): "
        f"{stale_baseline}\n\n"
        "Fix: the management surface is inbound-only. Do not re-export doctrine\n"
        "objects through a first-party __all__; route callers through the charter\n"
        "facade instead. See contracts/public-api-contract.md C4."
    )


def test_config_conduit_is_closed() -> None:
    """Closure-proof (WP05, 01KZPDSR / C-005): ``config.py`` launders nothing.

    Inverts the pre-WP05 ``…is_still_a_conduit`` sanity-pin: once WP05 dropped the
    doctrine-origin org-pack-config symbols from ``config.__all__``, the module
    must no longer appear in the source-side laundering map, and the baseline that
    seeded it must be empty. Re-introducing a doctrine-origin symbol into
    ``config.__all__`` (re-opening the conduit) reds this guard.
    """
    actual = _source_side_laundering()
    assert "src/specify_cli/doctrine/config.py" not in actual
    assert _LAUNDERING_BASELINE == {}


@pytest.mark.parametrize("spelling", ["doctrine", "charter.offering"])
def test_lazy_gate_rejects_added_reach_in_baselined_file(spelling: str) -> None:
    """Reproduce #3522 through the existing live-source scan, without source edits."""
    target = _REPO_ROOT / "src/runtime/next/runtime_bridge_composition.py"
    original_read = Path.read_text
    source = target.read_text(encoding="utf-8")
    facade = "from charter.drg import resolve_org_dirs"
    assert source.count(facade) == 1
    mutation = source.replace(facade, f"from {spelling}.drg.org_pack_config import resolve_org_dirs")

    def read_source(path: Path, encoding: str | None = None) -> str:
        return mutation if path == target else original_read(path, encoding=encoding)

    with (
        patch.object(Path, "read_text", read_source),
        pytest.raises(AssertionError, match="org_pack_config"),
    ):
        test_runtime_has_no_new_lazy_doctrine_imports()


def test_lazy_gate_rejects_partial_baseline_removal() -> None:
    """Migrating one import must shrink its entry even when the file still reaches."""
    target = _REPO_ROOT / "src/specify_cli/cli/commands/_doctrine_collect.py"
    original_read = Path.read_text
    source = target.read_text(encoding="utf-8")
    assert "from charter.offering.drg.loader import" in source
    mutation = source.replace("from charter.offering.drg.loader import", "from charter.drg import")

    def read_source(path: Path, encoding: str | None = None) -> str:
        return mutation if path == target else original_read(path, encoding=encoding)

    with (
        patch.object(Path, "read_text", read_source),
        pytest.raises(AssertionError, match=r"(?s)Stale lazy-import baseline.*charter\.offering\.drg\.loader"),
    ):
        test_runtime_has_no_new_lazy_doctrine_imports()


@pytest.mark.parametrize("package", ["runtime", "specify_cli"])
@pytest.mark.parametrize("lazy", [False, True], ids=["top-level", "lazy"])
@pytest.mark.parametrize(
    "statement",
    [
        "from doctrine.drg.org_pack_config import resolve_org_dirs",
        "from charter.offering.drg.org_pack_config import resolve_org_dirs",
        "from charter import offering as implementation",
        "import charter.offering.service, charter.offering.drg.org_pack_config",
    ],
)
def test_source_scan_rejects_direct_import_forms(package: str, lazy: bool, statement: str) -> None:
    target = _REPO_ROOT / "src" / package / "__init__.py"
    original_read = Path.read_text
    addition = f"def injected_probe():\n    {statement}\n" if lazy else statement + "\n"
    mutation = target.read_text(encoding="utf-8") + "\n" + addition

    def read_source(path: Path, encoding: str | None = None) -> str:
        return mutation if path == target else original_read(path, encoding=encoding)

    gate = test_runtime_has_no_new_lazy_doctrine_imports if lazy else test_runtime_has_no_direct_doctrine_imports
    with (
        patch.object(Path, "read_text", read_source),
        pytest.raises(AssertionError, match=f"src/{package}/__init__.py"),
    ):
        gate()


def test_parent_import_laundering_tracks_only_offering_binding() -> None:
    tree = ast.parse("from charter import offering as implementation, drg\n__all__ = ['implementation', 'drg']\n")
    assert _laundered_symbols(tree) == {"implementation"}


@pytest.mark.parametrize("spelling", ["doctrine", "charter.offering"])
def test_lazy_visitor_collects_every_module_in_multi_import(spelling: str) -> None:
    visitor = _LazyDoctrineVisitor()
    visitor.visit(ast.parse(f"def probe():\n    import {spelling}.service, {spelling}.drg.org_pack_config\n"))
    assert visitor.paths == {f"{spelling}.service", f"{spelling}.drg.org_pack_config"}


@pytest.mark.parametrize("spelling", ["doctrine", "charter.offering"])
@pytest.mark.parametrize("members", ["drg as implementation", "service as factory, drg as implementation", "*"])
def test_metadata_exception_rejects_root_member_import(spelling: str, members: str) -> None:
    """A bare-package metadata exception must not grant access to its members."""
    target = _REPO_ROOT / "src/specify_cli/tool_surface/bundles/codex.py"
    original_read = Path.read_text
    metadata_import = "import charter.offering as _charter_offering"
    source = target.read_text(encoding="utf-8") + (f"\ndef injected_metadata_probe():\n    {metadata_import}\n    {metadata_import}\n")
    assert source.count(metadata_import) == 2
    mutation = source.replace(metadata_import, f"from {spelling} import {members}", 1)

    def read_source(path: Path, encoding: str | None = None) -> str:
        return mutation if path == target else original_read(path, encoding=encoding)

    with (
        patch.object(Path, "read_text", read_source),
        pytest.raises(AssertionError, match="codex.py"),
    ):
        test_runtime_has_no_new_lazy_doctrine_imports()


@pytest.mark.parametrize("spelling", ["doctrine", "charter.offering"])
@pytest.mark.parametrize(
    "block",
    ["if True:\n    {statement}\n", "try:\n    {statement}\nexcept ImportError:\n    pass\n"],
    ids=["if", "try"],
)
def test_source_scan_rejects_module_control_flow_import(spelling: str, block: str) -> None:
    """A classified module in a migration-owned file still violates the top-level gate."""
    target = _REPO_ROOT / "src/specify_cli/cli/commands/_doctrine_collect.py"
    original_read = Path.read_text
    statement = f"from {spelling}.drg.org_pack_config import resolve_org_dirs"
    mutation = target.read_text(encoding="utf-8") + "\n" + block.format(statement=statement)

    def read_source(path: Path, encoding: str | None = None) -> str:
        return mutation if path == target else original_read(path, encoding=encoding)

    with (
        patch.object(Path, "read_text", read_source),
        pytest.raises(AssertionError, match="_doctrine_collect.py"),
    ):
        test_runtime_has_no_direct_doctrine_imports()


@pytest.mark.parametrize(
    ("source", "module_level", "lazy"),
    [
        ("if True:\n    from charter.drg import resolve_org_dirs\n", False, False),
        ("if TYPE_CHECKING:\n    from charter.offering.service import DoctrineService\n", False, False),
        ("try:\n    if typing.TYPE_CHECKING:\n        import doctrine.service\nexcept ImportError:\n    pass\n", False, False),
        ("if TYPE_CHECKING:\n    pass\nelse:\n    import doctrine.service\n", True, False),
        ("try:\n    pass\nexcept ImportError:\n    import doctrine.service\n", True, False),
        ("try:\n    pass\nfinally:\n    import charter.offering.service\n", True, False),
        ("if True:\n    def probe():\n        import doctrine.service\n", False, True),
        ("try:\n    async def probe():\n        import doctrine.service\nexcept ImportError:\n    pass\n", False, True),
        ("if True:\n    class Probe:\n        import charter.offering.service\n", False, True),
        ("if TYPE_CHECKING:\n    def probe():\n        import doctrine.service\n", False, False),
    ],
    ids=["facade", "type-checking", "try-type-checking", "runtime-else", "handler", "finally", "function", "async-function", "class", "type-checking-function"],
)
def test_control_flow_preserves_import_scope(source: str, module_level: bool, lazy: bool) -> None:
    assert _has_module_level_doctrine_import(source) is module_level
    visitor = _LazyDoctrineVisitor()
    visitor.visit(ast.parse(source))
    assert bool(visitor.paths) is lazy
