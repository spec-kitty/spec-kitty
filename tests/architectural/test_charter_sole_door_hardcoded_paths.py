"""Missions-root hardcode gate — FR-004 / FR-007 (Gate 4, mission-wide).

Mission ``charter-sole-door-bypass-closure-01KZ3WAA`` / WP06. This mission
absorbed the former WP09 Gate 4 into WP06 (post-tasks squad restructure —
the gate only ever guarded WP06's own surface).

WP06 closed 2 of 3 duplicate hardcodes that independently reconstructed the
shipped ``src/charter/offering/missions`` root via a ``Path(__file__)``-relative
literal containing ``"doctrine"`` immediately followed by ``"missions"`` as
adjacent path-join components:

* ``charter.activation.mission_type_profile_repository.builtin_missions_root()`` (T022)
* ``specify_cli.runtime.home.get_package_asset_root()``'s ``dev_roots``
  fallback tuple (T023)

Both now delegate to the ONE promoted authority,
:meth:`~charter.offering.missions.repository.MissionTemplateRepository.default_missions_root`.
This gate makes that closure durable: it is a **zero-tolerance** scan (no
allow-list) for that exact literal shape anywhere in ``src/`` outside the one
promoted authority module, ``src/charter/offering/missions/repository.py``.

Landing-fold gate hardening (A6): three widenings
----------------------------------------------------
Adversarial-review injection probes measured this gate at a 2/9 real catch
rate. Three widenings close the dominant misses, reusing machinery this
fold's earlier commits already promoted to :mod:`tests.architectural._sole_door_scan`:

* **``.joinpath(...)`` accepted alongside ``/``.** ``Path(__file__).resolve()
  .parents[1].joinpath("doctrine", "missions")`` is semantically identical to
  the ``/``-chain form and was previously invisible.
* **A single literal containing the separator is split before the adjacency
  check.** ``... / "doctrine/missions"`` (one combined literal) previously
  produced a one-element literals list with no adjacent pair to match; each
  literal is now split on ``"/"`` first.
* **``Path(__file__)``-rooted variables are tainted per scope.** ``HERE =
  Path(__file__).resolve().parents[1]`` followed by ``HERE / "doctrine" /
  "missions"`` — at module level OR function-local scope — previously evaded
  the root check entirely, since the root of the join chain was a bare
  ``ast.Name``, not a literal ``Path(__file__)`` call. Reuses the same
  per-scope-statement machinery (:func:`tests.architectural._sole_door_scan._own_scope_statements`)
  the A1 alias-rebind fix (Gates 1-2) already applies.

Scope note (named residual, not silently fixed) — spellings deliberately
left uncaught by this gate, even after the A6 widening
------------------------------------------------------------------------------
* **Root-relative anchor, not ``Path(__file__)``-relative** (e.g.
  ``repo_root / "src" / "charter" / "offering" / "missions"``) — a post-tasks squad pass
  found 3 such sites this gate does not police:

  * ``src/kernel/paths.py`` (around lines 89-90)
  * ``src/specify_cli/template/manager.py`` (around lines 45, 126)
  * ``src/specify_cli/cli/commands/charter/list_cmd.py`` (around lines 66, 79)

  Closing those is out of this WP's scope (see WP06's task file T025).
* **``os.path.join(str(Path(__file__)...), "doctrine", "missions")``** — a
  different call shape (``os.path.join``, not ``Path./ `` or
  ``Path.joinpath``) this gate does not recognise.
* **f-string interpolation** (e.g. ``f"{Path(__file__).parent}/doctrine/missions"``)
  — the join happens inside string formatting, invisible to the
  ``BinOp``/``joinpath``-call detection this gate performs.
* **Component constants** — e.g. ``_DOCTRINE = "doctrine"``; ``_MISSIONS =
  "missions"``; ``... / _DOCTRINE / _MISSIONS`` — the A6 widening taints the
  join chain's **root** variable, not the individual **literal path
  components**; resolving a component held in a separate constant would need
  a second, distinct constant-propagation pass this fold does not add.

This gate's job remains narrowly the ``Path(__file__)``-relative ``/`` and
``.joinpath()`` shapes (with split-literal and tainted-root support),
non-vacuous per the self-mutation tests below.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.architectural._ast_scan import parse_file
from tests.architectural._sole_door_scan import (
    SRC_ROOT,
    _own_scope_statements,
    _scope_chain,
    _scope_nodes,
    iter_source_files,
    parent_map,
    rel_to_repo,
)

pytestmark = pytest.mark.architectural

#: The ONE module entitled to construct the missions-root path natively.
#: Every other module must call
#: ``MissionTemplateRepository.default_missions_root()`` instead of
#: reconstructing the literal itself.
AUTHORITY_REL_PATH = "src/charter/offering/missions/repository.py"

#: The two path-join components this gate looks for, adjacent, in that order.
_GUARDED_COMPONENTS = ("doctrine", "missions")


@dataclass(frozen=True)
class MissionsRootHardcodeSite:
    """One discovered ``Path(__file__)``-relative missions-root literal."""

    rel_path: str
    qualname: str
    lineno: int


def _is_path_call(call: ast.Call) -> bool:
    """True for a ``Path(...)`` / ``pathlib.Path(...)`` construction."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id == "Path"
    return isinstance(func, ast.Attribute) and func.attr == "Path"


def _is_dunder_file_path_call(node: ast.expr) -> bool:
    """True for ``Path(__file__)`` (bare, unwrapped)."""
    return isinstance(node, ast.Call) and _is_path_call(node) and len(node.args) == 1 and isinstance(node.args[0], ast.Name) and node.args[0].id == "__file__"


def _is_joinpath_call(node: ast.AST | None) -> bool:
    """True for ``<expr>.joinpath(...)`` — the A6-accepted sibling of ``/``."""
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "joinpath"


def _unwrap_to_base(node: ast.expr) -> ast.expr:
    """Descend through ``.attr``, ``[subscript]`` and ``.method()`` wrappers.

    Handles the two live pre-fix shapes:
    ``Path(__file__).resolve().parents[1]`` and ``Path(__file__).parents[2]``
    — stripping ``.resolve()``, ``.parents``, and the ``[N]`` index to reach
    the base ``Path(__file__)`` call. A ``.joinpath(...)`` call is deliberately
    NOT stripped here — it is a join step handled by :func:`_collect_join_chain`,
    not base-wrapper noise.
    """
    while True:
        if _is_joinpath_call(node):
            return node
        if isinstance(node, (ast.Subscript, ast.Attribute)):
            node = node.value
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            node = node.func.value
        else:
            return node


def _root_is_dunder_file_path(
    root: ast.expr,
    scope_chain: list[ast.AST],
    dunder_file_rebinds_by_scope: dict[int, dict[str, bool]],
) -> bool:
    """True when *root* is (or resolves to) a ``Path(__file__)``-rooted expr.

    A6 widening: previously this only recognised the literal
    ``Path(__file__)`` call shape. Now also true when *root* is a bare
    ``ast.Name`` bound — at module level OR function-local scope, via
    *scope_chain* — to an expression that itself roots at ``Path(__file__)``
    (``HERE = Path(__file__).resolve().parents[1]`` then ``HERE / "doctrine"
    / "missions"``).
    """
    base = _unwrap_to_base(root)
    if _is_dunder_file_path_call(base):
        return True
    if isinstance(base, ast.Name):
        for scope in scope_chain:
            rebinds = dunder_file_rebinds_by_scope.get(id(scope))
            if rebinds and rebinds.get(base.id):
                return True
    return False


def _dunder_file_rebinds_for_scope(scope: ast.AST) -> dict[str, bool]:
    """Names in *scope* bound directly to a ``Path(__file__)``-relative expr.

    Computed via :func:`_own_scope_statements` — the same per-scope-statement
    helper the A1 alias-rebind fix (Gates 1-2) already uses — so a
    function-local rebind is tainted, not just a module-level one (NFR-003).
    """
    tainted: dict[str, bool] = {}
    for node in _own_scope_statements(scope):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and _is_dunder_file_path_call(_unwrap_to_base(node.value)):
            tainted[target.id] = True
    return tainted


def _literal_components(node: ast.expr) -> list[str]:
    """Split a string-literal join operand into its ``"/"``-separated parts.

    A6 widening: a single literal already containing the separator
    (``"doctrine/missions"``) previously produced one un-splittable list
    element with no adjacent pair for :func:`_has_adjacent_guarded_components`
    to match. Splitting first makes a combined literal equivalent to two
    separately-joined ones.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [part for part in node.value.split("/") if part]
    return []


def _collect_join_chain(node: ast.expr) -> tuple[ast.expr, list[str]]:
    """Return ``(root_expr, [literal_components_in_join_order])``.

    Walks a left-associative ``/`` (``BinOp`` / ``Div``) chain AND a
    ``.joinpath(...)`` call chain (A6 widening — the two are semantically
    equivalent join steps), collecting each string-literal operand/argument's
    split components in order. ``root_expr`` is the non-join-step base the
    chain bottoms out on.
    """
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        root, literals = _collect_join_chain(node.left)
        literals.extend(_literal_components(node.right))
        return root, literals
    if _is_joinpath_call(node):
        assert isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        root, literals = _collect_join_chain(node.func.value)
        for arg in node.args:
            literals.extend(_literal_components(arg))
        return root, literals
    return node, []


def _has_adjacent_guarded_components(literals: list[str]) -> bool:
    guarded_first, guarded_second = _GUARDED_COMPONENTS
    return any(a == guarded_first and b == guarded_second for a, b in zip(literals, literals[1:], strict=False))


def _is_join_step(node: ast.AST) -> bool:
    return (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)) or (isinstance(node, ast.expr) and _is_joinpath_call(node))


def _is_outermost_join(parents: dict[int, ast.AST], node: ast.AST) -> bool:
    """True when *node* is not itself consumed by an enclosing join step.

    Prevents double-counting the same literal join chain once per nested
    join step — only the single outermost node in a chain is scored. Covers
    both join-step shapes: nesting inside an enclosing ``/`` (as ``.left``)
    and nesting inside an enclosing ``.joinpath(...)`` (as the receiver).
    """
    parent = parents.get(id(node))
    if isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Div):
        return parent.left is not node
    if _is_joinpath_call(parent):
        assert isinstance(parent, ast.Call) and isinstance(parent.func, ast.Attribute)
        return parent.func.value is not node
    return True


def _qualname_via_scope_chain(scope_chain: list[ast.AST]) -> str:
    names = [scope.name for scope in scope_chain if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    return ".".join(reversed(names)) if names else "<module>"


def _scan_file(path: Path, rel: str) -> list[MissionsRootHardcodeSite]:
    tree = parse_file(path, display=rel)
    parents = parent_map(tree)
    dunder_file_rebinds_by_scope = {id(scope): _dunder_file_rebinds_for_scope(scope) for scope in _scope_nodes(tree)}

    found: list[MissionsRootHardcodeSite] = []
    for node in ast.walk(tree):
        if not _is_join_step(node):
            continue
        if not _is_outermost_join(parents, node):
            continue
        assert isinstance(node, ast.expr)
        root, literals = _collect_join_chain(node)
        scope_chain = _scope_chain(parents, node, tree)
        if not _root_is_dunder_file_path(root, scope_chain, dunder_file_rebinds_by_scope):
            continue
        if not _has_adjacent_guarded_components(literals):
            continue
        found.append(MissionsRootHardcodeSite(rel, _qualname_via_scope_chain(scope_chain), node.lineno))
    return found


def scan_missions_root_hardcodes(src_root: Path) -> list[MissionsRootHardcodeSite]:
    """AST-walk ``<src_root>/**/*.py`` for ``Path(__file__)``-relative missions-root literals.

    Excludes :data:`AUTHORITY_REL_PATH` — that module IS the promoted
    authority, so its own resolution logic is the definition, not a
    violation.
    """
    sites: list[MissionsRootHardcodeSite] = []
    for path in iter_source_files(src_root):
        rel = rel_to_repo(path)
        if rel == AUTHORITY_REL_PATH:
            continue
        sites.extend(_scan_file(path, rel))
    return sites


def check_missions_root_hardcode_gate(src_root: Path) -> list[str]:
    """Return violation strings — zero-tolerance, no allow-list."""
    return [
        f"{site.rel_path}:{site.lineno} ({site.qualname}) reconstructs the "
        "missions-root path via a Path(__file__)-relative "
        '"doctrine" / "missions" literal instead of calling '
        "MissionTemplateRepository.default_missions_root() (FR-004) — route "
        "it through the promoted authority"
        for site in scan_missions_root_hardcodes(src_root)
    ]


# =========================================================================== #
# TESTS
# =========================================================================== #


# --- unit: detector shape ----------------------------------------------------


# --- A6 widening: .joinpath(), split literals, tainted roots -----------------


def test_untainted_root_variable_is_not_flagged(tmp_path: Path) -> None:
    """True negative: a root variable NOT bound from ``Path(__file__)`` stays clean.

    Guards the A6 root-taint widening against becoming overbroad — the
    variable's origin still has to be a real ``Path(__file__)``-relative
    expression, not just any ``Path``.
    """
    mod = tmp_path / "snippet.py"
    mod.write_text(
        'from pathlib import Path\n\n\ndef f(repo_root):\n    HERE = Path(repo_root)\n    return HERE / "doctrine" / "missions"\n',
        encoding="utf-8",
    )
    assert _scan_file(mod, "snippet.py") == []


# --- zero-tolerance real-tree gate -------------------------------------------
def test_gate_is_zero_tolerance_against_the_live_tree() -> None:
    """T022 + T023 closed both Path(__file__)-relative sites: the live tree is clean.

    No allow-list: any future reintroduction of this exact literal shape
    (outside the promoted authority) fails this test immediately.
    """
    violations = check_missions_root_hardcode_gate(SRC_ROOT)
    assert violations == [], "\n".join(violations)


# --- NFR-004 self-mutation proof ---------------------------------------------
def test_injected_hardcode_is_flagged_naming_the_exact_line(tmp_path: Path) -> None:
    """Self-mutation proof: a re-introduced hardcode goes RED, naming its line.

    Injects into a scratch module (never the real, already-closed sites) so
    the RED-on-demand property is proven fresh on every run, not eyeballed
    once at review time.
    """
    pkg = tmp_path / "src" / "scratch_pkg"
    pkg.mkdir(parents=True)
    regressed = pkg / "regressed.py"
    regressed.write_text(
        'from pathlib import Path\n\n\nclass Regressed:\n    def load(self):\n        return Path(__file__).resolve().parents[1] / "doctrine" / "missions"\n',
        encoding="utf-8",
    )
    scratch_src = tmp_path / "src"

    violations = check_missions_root_hardcode_gate(scratch_src)
    assert violations, "self-mutation: a re-introduced missions-root hardcode must be flagged"
    assert any("regressed.py:6" in v and "Regressed.load" in v for v in violations), violations
