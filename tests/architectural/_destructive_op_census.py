"""Shared AST-census / allowlist-diff / self-mutation plumbing (DIRECTIVE_044).

Single authority for the two destructive-op architectural gates, so the
census machinery is written and audited once, not copy-pasted (charter
single-canonical-authority; DIRECTIVE_044):

* ``test_destructive_op_routing.py`` — scans **git argv literals**
  (``reset --hard`` / ``worktree remove --force`` / ``merge --abort``) under
  ``src/specify_cli`` (mission ``merge-destructive-op-safety-01M2XQF8``).
* ``test_mutation_ownership_routing.py`` — scans **Python filesystem
  ``ast.Call`` literals** (``shutil.rmtree`` / ``Path.unlink`` / …) in the
  ``init`` + upgrade-migration mutating-flow module set (mission
  ``ownership-boundary-preservation-01M32KEN``, WP09).

Both gates share the same shape: walk the AST of a fixed module set, classify
each literal, diff the live census against a frozen, individually-rationalized,
**shrink-only** allowlist (a NEW un-rationalized literal FAILS; a vanished one
only WARNS), and prove non-vacuity by (a) planting an un-routed op the same
scanner must detect and (b) dropping one real allowlist entry to reproduce the
exact gate failure. Everything below is the generic, classifier-agnostic core;
each gate keeps its own classifier, module set, and ``_ALLOWLIST``.
"""

from __future__ import annotations

import ast as _ast
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TypeVar

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
SPECIFY_CLI_ROOT = SRC_ROOT / "specify_cli"

_T = TypeVar("_T")


# ---------------------------------------------------------------------------
# AST plumbing
# ---------------------------------------------------------------------------


def iter_py_files(root: Path) -> list[Path]:
    """Every ``*.py`` file under *root*, ``__pycache__`` excluded, sorted."""
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def parse(path: Path) -> _ast.Module | None:
    """Parse *path*; ``None`` on a read/decode/syntax failure (never raises)."""
    try:
        return _ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return None


def module_string_constants(tree: _ast.Module) -> dict[str, str]:
    """Module-level ``NAME = "literal"`` / ``NAME: str = "literal"`` bindings.

    Resolves indirections like ``coordination/workspace.py``'s
    ``_GIT_WORKTREE = "worktree"`` so an argv element referencing the constant
    by name is not invisible to a scan.
    """
    consts: dict[str, str] = {}
    for node in tree.body:
        if (
            isinstance(node, _ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], _ast.Name)
            and isinstance(node.value, _ast.Constant)
            and isinstance(node.value.value, str)
        ):
            consts[node.targets[0].id] = node.value.value
        elif (
            isinstance(node, _ast.AnnAssign)
            and isinstance(node.target, _ast.Name)
            and node.value is not None
            and isinstance(node.value, _ast.Constant)
            and isinstance(node.value.value, str)
        ):
            consts[node.target.id] = node.value.value
    return consts


def import_alias_map(tree: _ast.Module) -> dict[str, str]:
    """Every ``import X`` / ``import X as Y`` binding in *tree*: bound local
    name -> canonical dotted module name (e.g. ``import shutil as sh`` ->
    ``{"sh": "shutil"}``; ``import shutil`` -> ``{"shutil": "shutil"}``).

    Walks the whole tree (not just module-level body) so a function-local
    ``import shutil as sh`` is resolved too — a receiver-name census that only
    recognised the literal ``shutil``/``os`` spelling would otherwise treat an
    aliased import as invisible.
    """
    aliases: dict[str, str] = {}
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                aliases[bound] = alias.name
    return aliases


def from_import_map(tree: _ast.Module) -> dict[str, tuple[str, str]]:
    """Every ``from X import Y [as Z]`` binding in *tree*: bound local name ->
    ``(module, original_attr_name)`` (e.g. ``from shutil import rmtree`` ->
    ``{"rmtree": ("shutil", "rmtree")}``; ``from shutil import rmtree as rm``
    -> ``{"rm": ("shutil", "rmtree")}``).

    Resolves a bare-``Name`` call bound this way (``rmtree(x)``) to its
    canonical ``module.attr`` op label — a call-site classifier keyed only on
    ``ast.Attribute`` receivers never sees this call shape at all.
    """
    bindings: dict[str, tuple[str, str]] = {}
    for node in _ast.walk(tree):
        if isinstance(node, _ast.ImportFrom) and node.module is not None:
            for alias in node.names:
                bound = alias.asname or alias.name
                bindings[bound] = (node.module, alias.name)
    return bindings


def resolve_token(node: _ast.expr, consts: Mapping[str, str]) -> str | None:
    """A string constant, or a ``Name`` bound to a module-level string constant."""
    if isinstance(node, _ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, _ast.Name):
        return consts.get(node.id)
    return None


def argv_tokens(node: _ast.List | _ast.Tuple, consts: Mapping[str, str]) -> list[str | None]:
    """Resolve each element of a list/tuple literal to its string value or ``None``."""
    return [resolve_token(elt, consts) for elt in node.elts]


def ordered_subsequence(tokens: list[str | None], *needles: str) -> bool:
    """True when *needles* appear, in order (not necessarily contiguous), among
    the resolved (non-``None``) elements of *tokens*."""
    idx = 0
    for tok in tokens:
        if tok is not None and tok == needles[idx]:
            idx += 1
            if idx == len(needles):
                return True
    return False


def enclosing_qualname(tree: _ast.Module, lineno: int) -> str:
    """Dotted qualname (``Class.method`` or bare ``func``) of the innermost
    function/method whose body contains *lineno*; ``"<module>"`` for
    module-level code."""

    class _Finder(_ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[str] = []
            self.result: str | None = None

        def _visit_def(self, node: _ast.FunctionDef | _ast.AsyncFunctionDef) -> None:
            end = getattr(node, "end_lineno", node.lineno) or node.lineno
            if node.lineno <= lineno <= end:
                self.result = ".".join([*self.stack, node.name])
                self.stack.append(node.name)
                self.generic_visit(node)
                self.stack.pop()
            else:
                self.generic_visit(node)

        def visit_FunctionDef(self, node: _ast.FunctionDef) -> None:
            self._visit_def(node)

        def visit_AsyncFunctionDef(self, node: _ast.AsyncFunctionDef) -> None:
            self._visit_def(node)

        def visit_ClassDef(self, node: _ast.ClassDef) -> None:
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

    finder = _Finder()
    finder.visit(tree)
    return finder.result or "<module>"


# ---------------------------------------------------------------------------
# Allowlist diff (shrink-only ratchet) + self-mutation harness
# ---------------------------------------------------------------------------


def diff_against_allowlist(live_flat: set[str], allowlist: Mapping[str, str]) -> tuple[set[str], set[str]]:
    """Return ``(unexpected, stale)``.

    * ``unexpected`` — sites live in the tree but absent from *allowlist*:
      the gate FAILS on these (a new un-rationalized destructive literal).
    * ``stale`` — sites listed but no longer live: WARN only (shrink-only
      ratchet — legitimate cleanup must never be blocked).
    """
    unexpected = live_flat - allowlist.keys()
    stale = set(allowlist) - live_flat
    return unexpected, stale


def scan_planted_source(tmp_path: Path, name: str, source: str, finder: Callable[[Path], _T]) -> _T:
    """Write *source* to ``tmp_path/name`` and run *finder* over it.

    The generic half of the planted-op non-vacuity proof: each gate passes its
    own literal finder so the SAME scanner the primary gate runs is proven to
    detect a planted, un-routed op.
    """
    planted = tmp_path / name
    planted.write_text(source, encoding="utf-8")
    return finder(planted)


def drop_one_entry(allowlist: Mapping[str, str]) -> tuple[str, dict[str, str]]:
    """Return ``(victim, shrunk)`` where *victim* is one entry removed from
    *allowlist* — the generic half of the drop-one-entry non-vacuity proof:
    re-diffing *shrunk* against the live tree must reproduce the gate failure
    the primary gate would raise for a genuine regression."""
    victim = next(iter(allowlist))
    shrunk = {k: v for k, v in allowlist.items() if k != victim}
    return victim, shrunk
