"""Scan ``src/`` for a hand-rolled ancestor walk outside ``kernel.ancestor_walk`` (#7056).

The idiom this bans is the one person writes when they need "this directory and every
parent": ``[p, *p.parents]``, ``(p, *p.parents)``, ``[p] + list(p.parents)``. Every such
loop is a place where repo-root discovery can silently ignore
``GIT_CEILING_DIRECTORIES``, which is exactly the defect #7022 fixed in three walks and
#7056 fixed in the rest. The shared walk is ``kernel.ancestor_walk``; new code calls it.

Scope, deliberately
-------------------

Only the two *idiom* shapes are banned. A bare ``for parent in path.parents:`` is also how
a dozen legitimate, non-root walks are written (path-shape classification, symlink
checks, package-sibling probes). Banning that shape would need an exemption list longer
than the census it protects, and a gate nobody can keep honest is worse than no gate
(``research.md`` D-6).

The exemption list is **shrink-only**. An entry names the file, the enclosing function
and why that walk is not repo-root discovery; the gate fails when an entry no longer
matches a scanned hit, which is how the list drains as those files are touched.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from tests.architectural._ast_scan import parse_file

#: The module that owns the walk. Hits here are the point, not a violation.
PRIMITIVE = "src/kernel/ancestor_walk.py"

#: The scanned corpus, repo-root relative.
SCAN_ROOT = "src"

_INCLUDE_SUFFIX = ".py"


@dataclass(frozen=True, order=True)
class Hit:
    """One hand-rolled ancestor walk found in a source file."""

    path: str
    line: int
    function: str
    snippet: str

    def describe(self) -> str:
        return f"{self.path}:{self.line} in {self.function}(): {self.snippet}"


@dataclass(frozen=True)
class Exemption:
    """A scanned site that is legitimately not a repo-root walk."""

    path: str
    function: str
    reason: str


#: Every exemption states why the walk is not repo-root discovery. Shrink-only: an entry
#: whose site is migrated or deleted fails ``test_every_exemption_still_matches_a_hit``.
EXEMPTIONS: tuple[Exemption, ...] = (
    Exemption(
        "src/kernel/paths.py",
        "_find_relocated_missions_ancestor",
        "Probes a caller-supplied SPEC_KITTY_TEMPLATE_ROOT for the relocated missions "
        "assets; it is not repository discovery and the assets tree may legitimately sit "
        "outside any checkout.",
    ),
    Exemption(
        "src/specify_cli/analysis_inputs.py",
        "_global_template_mirror",
        "Symlink check over the home directory's ancestry, not a marker walk: it accepts "
        "no directory and returns no root.",
    ),
    Exemption(
        "src/specify_cli/coordination/surface_resolver.py",
        "_enclosing_worktree_root",
        "Classifies a path against the '.worktrees/<name>' segment shape; the git ceiling "
        "has no meaning for a path-shape question.",
    ),
    Exemption(
        "src/specify_cli/core/vcs/detection.py",
        "_get_locked_vcs_from_feature",
        "Two segment-shape walks ('kitty-specs/<feature>', '.worktrees/<lane>') that "
        "identify what a path is, not which repository contains it.",
    ),
    Exemption(
        "src/specify_cli/workspace/root_resolver.py",
        "canonicalize_feature_dir",
        "Path-shape fallback used only when the git worktree registry is unreadable; it "
        "proposes a directory it was already handed, never discovers one.",
    ),
    Exemption(
        "src/specify_cli/upgrade/migrations/m_0_6_7_ensure_missions.py",
        "_find_package_missions",
        "Frozen historical migration: its dev-checkout fallback must reproduce what that "
        "release did on an operator's machine, ceiling or not.",
    ),
    Exemption(
        "src/specify_cli/upgrade/migrations/m_0_9_2_research_mission_templates.py",
        "_find_package_research_mission",
        "Frozen historical migration, same reason as m_0_6_7.",
    ),
    Exemption(
        "src/specify_cli/upgrade/migrations/m_0_14_0_centralized_feature_detection.py",
        "_find_package_template",
        "Frozen historical migration, same reason as m_0_6_7.",
    ),
)


def _is_parents_attribute(node: ast.expr) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "parents"


def _is_plain_parents_list(node: ast.expr) -> bool:
    """``list(<expr>.parents)`` — the right-hand half of the concat idiom."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "list"
        and len(node.args) == 1
        and _is_parents_attribute(node.args[0])
    )


def _idiom_nodes(tree: ast.AST) -> Iterator[tuple[ast.expr, str]]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Tuple)):
            if any(isinstance(elt, ast.Starred) and _is_parents_attribute(elt.value) for elt in node.elts):
                yield node, ast.unparse(node)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            sides = (node.left, node.right)
            if any(isinstance(side, ast.List) for side in sides) and any(_is_plain_parents_list(side) for side in sides):
                yield node, ast.unparse(node)


def _qualnames_by_line(tree: ast.AST) -> dict[int, str]:
    """Map the first line of each function body to its qualified name."""
    names: dict[int, str] = {}

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualname = f"{prefix}{child.name}"
                names[child.lineno] = qualname
                visit(child, f"{qualname}.")
            elif isinstance(child, ast.ClassDef):
                visit(child, f"{prefix}{child.name}.")
            else:
                visit(child, prefix)

    visit(tree, "")
    return names


def _enclosing_function(tree: ast.AST, node: ast.expr) -> str:
    best: str | None = None
    best_span = None
    for candidate in ast.walk(tree):
        if isinstance(candidate, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(candidate, "end_lineno", candidate.lineno)
            if candidate.lineno <= node.lineno <= end:
                span = end - candidate.lineno
                if best is None or best_span is None or span <= best_span:
                    best = candidate.name
                    best_span = span
    return best or "<module>"


def scan_source(text: str, path: str) -> list[Hit]:
    """Return the hand-rolled ancestor walks in one source text."""
    tree = ast.parse(text)
    hits: list[Hit] = []
    for node, snippet in _idiom_nodes(tree):
        hits.append(Hit(path=path, line=node.lineno, function=_enclosing_function(tree, node), snippet=snippet))
    return hits


def scan_file(path: Path, *, repo_root: Path) -> list[Hit]:
    """Return the hand-rolled ancestor walks in one file (fail-closed on a parse error)."""
    tree = parse_file(path)
    relative = path.resolve().relative_to(repo_root).as_posix()
    hits: list[Hit] = []
    for node, snippet in _idiom_nodes(tree):
        hits.append(Hit(path=relative, line=node.lineno, function=_enclosing_function(tree, node), snippet=snippet))
    return hits


def scan_tree(repo_root: Path, *, root: str = SCAN_ROOT) -> list[Hit]:
    """Return every hit under ``<repo_root>/<root>``, including the primitive's own."""
    base = repo_root / root
    hits: list[Hit] = []
    for path in sorted(base.rglob(f"*{_INCLUDE_SUFFIX}")):
        hits.extend(scan_file(path, repo_root=repo_root))
    return hits


def exemption_for(hit: Hit) -> Exemption | None:
    return next((entry for entry in EXEMPTIONS if entry.path == hit.path and entry.function == hit.function), None)


def unexempted(hits: Iterable[Hit]) -> list[Hit]:
    """The hits the gate fails on: outside the primitive and not exempted."""
    return [hit for hit in hits if hit.path != PRIMITIVE and exemption_for(hit) is None]


def stale_exemptions(hits: Iterable[Hit]) -> list[Exemption]:
    """Exemptions that no longer correspond to a scanned hit."""
    matched = {(hit.path, hit.function) for hit in hits}
    return [entry for entry in EXEMPTIONS if (entry.path, entry.function) not in matched]
