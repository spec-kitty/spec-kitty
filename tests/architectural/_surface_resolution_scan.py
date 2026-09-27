"""Mission-surface-resolution callsite scanner (live AST walker).

The one live consumer is ``test_single_mission_surface_resolver.py``, which
calls :func:`discover_rows` and :func:`discover_selection_callsites` on the
current source tree and classifies what they return. This module writes no
file and has no command-line entry point; the former inventory, converter and
standalone audit script were retired (#3011).

What the scanner discovers
--------------------------
It AST-walks every ``*.py`` under ``src/specify_cli`` and ``src/mission_runtime``
and reports two classes of callsite (:func:`discover_rows`):

(a) **Blessed resolver calls inside the seam files** (``_RESOLVER_SOURCE_STEMS``):
    calls to a name in ``_RESOLVER_CALLS`` or ``_TOPOLOGY_BLIND_CALLS``, tracked
    so the seam implementations themselves stay correct.

(b) **Raw-bypass joins in every file**: a ``pathlib`` ``/`` join whose right
    operand is a name (or attribute) in ``SLUG_NAMES`` and whose left subtree,
    searched recursively down the ``/`` chain, references a name in
    ``KITTY_SPECS_NAMES`` or the literal ``"kitty-specs"``. So
    ``root / KITTY_SPECS_DIR / mission_slug`` is caught as well as
    ``specs / mission_slug`` when ``specs`` is itself such a join.

A second discriminator, :func:`discover_selection_callsites`, reports every
DIRECT call to a read-SELECTION name (``_SELECTION_READ_CALLS``) whether or not a
``KITTY_SPECS_DIR`` join is present; the raw-join walker is blind to those.

The seed set is data (``SLUG_NAMES``, ``KITTY_SPECS_NAMES``,
``_RESOLVER_SOURCE_STEMS``), not a hard-coded file list, so extending a set
widens the net everywhere.

Deliberately NOT tracked per callsite: downstream callers outside the seam
files that call a blessed resolver (``resolve_feature_dir_for_mission`` etc.).
They are routed through the resolver by construction. Also out of scope: the
``WorktreeTopology`` / ``classify_worktree_topology`` / ``read_worktree_registry``
machinery, which is the correct git-registry authority.

Known false-negative classes (what the matcher does NOT trace)
--------------------------------------------------------------
1. Cross-function flow: a slug passed into a function is not followed into the
   callee.
2. More than one alias hop (``a = slug; b = a; root / KITTY_SPECS_DIR / b``).
3. Container flow: a slug stored in a list or dict and later joined.
4. f-strings, ``os.path.join`` and ``str`` concatenation: only ``pathlib`` ``/``
   joins are matched.
5. ``Path(...)`` built from an untrusted full string rather than a join.
6. Callers outside ``_RESOLVER_SOURCE_STEMS`` that call a blessed resolver
   (routed by construction, see above).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from tests.architectural._ast_scan import parse_file
from tests.architectural._ratchet_keys import CompositeKey, composite_key_from_file

# --------------------------------------------------------------------------- #
# Locate the source trees relative to this file (repo-root independent).
# this file: <root>/tests/architectural/_surface_resolution_scan.py
# --------------------------------------------------------------------------- #
_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[2]
_SRC_ROOT = _REPO_ROOT / "src"
SRC_SPECIFY_CLI = _SRC_ROOT / "specify_cli"
SRC_MISSION_RUNTIME = _SRC_ROOT / "mission_runtime"

# --------------------------------------------------------------------------- #
# Drift-proof composite identity (FR-004 / IC-03). Row identity is the
# ``(rel_path, enclosing_qualname, token)`` composite derived by
# ``composite_key_from_file``, NOT the raw ``rel:line`` locator, which drifts on
# every blank/comment-line insertion above a callsite (the #2306 failure class).
# ``CompositeKey`` is declared once, in the shared ``_ratchet_keys`` substrate.
# --------------------------------------------------------------------------- #


def _composite_from_file(rel_path: str, line: int) -> CompositeKey:
    """Live ``(rel_path, qualname, token)`` for a discovered row.

    The token is returned exactly as ``composite_key_from_file`` renders it, so
    this identity matches the keys the survivor guard builds with that helper.
    """
    qualname, token = composite_key_from_file(_SRC_ROOT / rel_path, line)
    return (rel_path, qualname, token)


# --------------------------------------------------------------------------- #
# Canonical resolver / seam source files. Callsites WITHIN these files are
# tracked to ensure the seam implementations themselves remain correct.
# Callsites OUTSIDE these files that call the blessed resolver functions are
# routed through the resolver by construction and are not tracked row-by-row;
# the raw-bypass scanner still runs codebase-wide, so no hidden raw join can
# escape.
# --------------------------------------------------------------------------- #
_RESOLVER_SOURCE_STEMS: frozenset[str] = frozenset(
    {
        "specify_cli/missions/_read_path_resolver.py",
        # ``feature_dir_resolver.py`` retired in WP07/FR-007: the shim was
        # collapsed into ``_read_path_resolver.py``; its resolvers
        # (``resolve_feature_dir_for_slug`` etc.) now live in that module.
        "specify_cli/coordination/surface_resolver.py",
        "specify_cli/coordination/status_transition.py",
        "specify_cli/status/aggregate.py",
        "mission_runtime/resolution.py",
    }
)

# The read-side SELECTION seam is the SINGLE ``resolve_handle_to_read_path``
# home — only ``_read_path_resolver.py`` legitimately owns the coord-vs-primary
# selection authority. The broader ``_RESOLVER_SOURCE_STEMS`` above stays for the
# RAW-JOIN axis, where ``surface_resolver.py`` / ``status_transition.py`` /
# ``aggregate.py`` / ``mission_runtime/resolution.py`` legitimately *define*
# resolvers — but they are NOT the selection seam. A future direct
# ``resolve_mission_read_path`` call in any of those four must be allowlisted
# (honest) rather than auto-blessed as seam-internal.
_SELECTION_SEAM_STEMS: frozenset[str] = frozenset(
    {
        "specify_cli/missions/_read_path_resolver.py",
    }
)

# --------------------------------------------------------------------------- #
# Seed-set: all blessed resolver function names.
# --------------------------------------------------------------------------- #
_RESOLVER_CALLS: frozenset[str] = frozenset(
    {
        "resolve_mission_read_path",
        "candidate_feature_dir_for_mission",
        "resolve_status_surface",
        "resolve_status_surface_with_anchor",
        "resolve_feature_dir_for_slug",
        "resolve_feature_dir_for_mission",
    }
)

# ``primary_feature_dir_for_mission`` is topology-blind-by-design:
# it deliberately targets the primary checkout. Tracked in seam files.
_TOPOLOGY_BLIND_CALLS: frozenset[str] = frozenset(
    {
        "primary_feature_dir_for_mission",
    }
)

# --------------------------------------------------------------------------- #
# Read SELECTION authority (FR-006a). ``resolve_mission_read_path`` is the
# existence-gated topology resolver that PICKS the coord-vs-primary read
# surface. The canonical adopted seam ``resolve_handle_to_read_path`` is the
# ONLY sanctioned entry point that callers should reach for; a DIRECT
# ``resolve_mission_read_path(...)`` call in a read path bypasses that seam's
# guard (``assert_safe_path_segment``) + fail-closed coord gate, re-acquiring
# the selection authority outside the single owner.
#
# This is a DIFFERENT discriminator from the raw-path-JOIN scanner above: a
# direct ``resolve_mission_read_path`` call composes NO ``KITTY_SPECS_DIR /
# slug`` path of its own (the resolver does that internally), so the raw-join
# scanner is BLIND to it. ``discover_selection_callsites()`` catches it by
# name, regardless of whether a ``KITTY_SPECS_DIR`` join is present.
# --------------------------------------------------------------------------- #
_SELECTION_READ_CALLS: frozenset[str] = frozenset(
    {
        # WP01 (01KVN754) privatized the worker ``resolve_mission_read_path`` →
        # ``_resolve_mission_read_path`` and #2048 retired the historical
        # ``mission_read_path`` shim alias.
        # The discriminator tracks BOTH names so a direct selection call cannot
        # slip the guard by importing the private worker or recreating the old
        # public spelling.
        "resolve_mission_read_path",
        "_resolve_mission_read_path",
    }
)

_ALL_BLESSED_CALLS: frozenset[str] = _RESOLVER_CALLS | _TOPOLOGY_BLIND_CALLS

# --------------------------------------------------------------------------- #
# Raw-bypass seed: local variable names that carry a mission slug and appear
# in a KITTY_SPECS_DIR path join without going through a resolver.
# --------------------------------------------------------------------------- #
SLUG_NAMES: frozenset[str] = frozenset(
    {
        "mission_slug",
        "feature_slug",
        "slug",
        "mission_slug_formatted",
        # ``raw_handle`` / ``handle`` carry the operator-supplied mission handle
        # at the read-CLI primary-meta bootstrap sites (e.g. ``agent/context.py``,
        # ``agent/mission.py``). Omitting them blinded ``discover_rows()`` to three
        # real raw-bypass joins that probe the primary checkout BEFORE the canonical
        # resolver — the same FS-touching shape as the allowlisted ``decision.py``
        # bootstrap (read-side-desync residual; consolidation deferred).
        "raw_handle",
        "handle",
    }
)

# KITTY_SPECS_DIR variable aliases.
KITTY_SPECS_NAMES: frozenset[str] = frozenset(
    {
        "KITTY_SPECS_DIR",
        "kitty_specs_dir",
        "_KITTY_SPECS_DIR",
    }
)


@dataclass(frozen=True)
class ResolutionRow:
    """One discovered mission-surface-resolution callsite."""

    rel_path: str  # relative to _REPO_ROOT/src
    line: int
    call_name: str  # resolver function name or "raw-path-join"
    handle_source: str  # what slug/handle the call uses

    def key(self) -> str:
        """Live ``rel:line`` LOCATOR (public shape — NOT the comparand).

        Frozen: ``test_single_mission_surface_resolver.py`` consumes this string
        (``row.key().startswith(...)``). It is a diagnostics locator only, never
        an identity for comparison — that is :meth:`composite_key`.
        """
        return f"{self.rel_path}:{self.line}"

    def composite_key(self) -> CompositeKey:
        """Drift-proof ``(rel_path, qualname, token)`` identity (the comparand)."""
        return _composite_from_file(self.rel_path, self.line)


def _rel(path: Path) -> str:
    """Return the path relative to ``_REPO_ROOT/src``."""
    try:
        return path.relative_to(_REPO_ROOT / "src").as_posix()
    except ValueError:
        return path.as_posix()


def _names_in(node: ast.expr) -> set[str]:
    """All ``Name`` ids referenced anywhere inside *node*."""
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _slug_on_right(node: ast.BinOp) -> str | None:
    """If the right-hand side of a ``/`` op is a slug name, return it."""
    if not isinstance(node.op, ast.Div):
        return None
    if isinstance(node.right, ast.Name) and node.right.id in SLUG_NAMES:
        return node.right.id
    if isinstance(node.right, ast.Attribute) and node.right.attr in SLUG_NAMES:
        return node.right.attr
    return None


def _contains_kitty_specs(node: ast.expr) -> bool:
    """Recursively check if the left subtree has a KITTY_SPECS_DIR reference."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        right_names = _names_in(node.right)
        if right_names & KITTY_SPECS_NAMES:
            return True
        if isinstance(node.right, ast.Constant) and node.right.value == "kitty-specs":
            return True
        return _contains_kitty_specs(node.left)
    return False


def _find_blessed_calls_in_seam(tree: ast.AST, rel_path: str) -> list[ResolutionRow]:
    """Return rows for every blessed resolver call within a seam source file."""
    rows: list[ResolutionRow] = []
    seen: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name: str | None = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name is None or name not in _ALL_BLESSED_CALLS:
            continue
        # Derive handle_source from the first positional arg (slug param).
        handle_source = "unknown"
        if node.args:
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Name):
                handle_source = first_arg.id
            elif isinstance(first_arg, ast.Attribute):
                handle_source = ast.unparse(first_arg)
            elif isinstance(first_arg, ast.Constant):
                handle_source = repr(first_arg.value)
            else:
                handle_source = ast.unparse(first_arg)
        # resolve_mission_read_path: slug is the second positional arg.
        if name == "resolve_mission_read_path" and len(node.args) >= 2:
            slug_arg = node.args[1]
            handle_source = slug_arg.id if isinstance(slug_arg, ast.Name) else ast.unparse(slug_arg)
        row = ResolutionRow(rel_path, node.lineno, name, handle_source)
        if row.key() not in seen:
            seen.add(row.key())
            rows.append(row)
    return rows


def _find_raw_bypasses(tree: ast.AST, rel_path: str) -> list[ResolutionRow]:
    """Return rows for raw ``KITTY_SPECS_DIR / slug`` path joins in any file.

    A join is a raw bypass when it composes a mission-surface directory from a
    slug variable WITHOUT the IMMEDIATE call going through a resolver function.
    The join is flagged when the slug appears on the RHS of a ``/`` and the
    left subtree contains a ``KITTY_SPECS_DIR`` reference.
    """
    rows: list[ResolutionRow] = []
    seen: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Div):
            continue
        slug = _slug_on_right(node)
        if slug is None:
            continue
        if not _contains_kitty_specs(node.left):
            continue
        row = ResolutionRow(rel_path, node.lineno, "raw-path-join", slug)
        if row.key() not in seen:
            seen.add(row.key())
            rows.append(row)
    return rows


def _audit_file(path: Path) -> list[ResolutionRow]:
    """Audit one source file; return discovered resolution callsites."""
    rel = _rel(path)
    # Fails closed on an unreadable/unparseable file (#5139) -- never a silent [].
    tree = parse_file(path)

    rows: list[ResolutionRow] = []
    # Track blessed resolver calls only within the canonical seam source files.
    if rel in _RESOLVER_SOURCE_STEMS:
        rows.extend(_find_blessed_calls_in_seam(tree, rel))
    # Track raw-bypass joins in ALL files (the exhaustive bypass check).
    rows.extend(_find_raw_bypasses(tree, rel))

    # Deduplicate by key.
    seen: set[str] = set()
    result: list[ResolutionRow] = []
    for r in rows:
        if r.key() not in seen:
            seen.add(r.key())
            result.append(r)
    return result


def discover_rows() -> list[ResolutionRow]:
    """AST-walk the source trees and return every discovered row, sorted."""
    rows: list[ResolutionRow] = []
    for src_root in (SRC_SPECIFY_CLI, SRC_MISSION_RUNTIME):
        if not src_root.exists():
            continue
        for path in sorted(src_root.rglob("*.py")):
            rows.extend(_audit_file(path))
    rows.sort(key=lambda r: (r.rel_path, r.line))
    return rows


# --------------------------------------------------------------------------- #
# FR-006a — read SELECTION callsite discriminator.
#
# Distinct from the raw-path-JOIN scanner: this walks for DIRECT calls to the
# read-selection authority (``resolve_mission_read_path``) regardless of any
# ``KITTY_SPECS_DIR`` join. A direct call is a SELECTION-authority acquisition
# outside the ``resolve_handle_to_read_path`` seam.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SelectionRow:
    """One discovered direct read-SELECTION callsite (``resolve_mission_read_path``)."""

    rel_path: str  # relative to _REPO_ROOT/src
    line: int
    call_name: str
    in_seam_file: bool  # True when the callsite is inside a _SELECTION_SEAM_STEMS file

    def key(self) -> str:
        """Live ``rel:line`` LOCATOR (public shape — NOT the comparand).

        Frozen: ``test_single_mission_surface_resolver.py`` consumes this string
        (``sel.key()`` membership + ``.startswith(...)``). Identity comparison
        uses :meth:`composite_key`.
        """
        return f"{self.rel_path}:{self.line}"

    def composite_key(self) -> CompositeKey:
        """Drift-proof ``(rel_path, qualname, token)`` identity (the comparand)."""
        return _composite_from_file(self.rel_path, self.line)


def _find_selection_calls(tree: ast.AST, rel_path: str) -> list[SelectionRow]:
    """Return rows for every direct read-SELECTION call in *one* file."""
    in_seam = rel_path in _SELECTION_SEAM_STEMS
    rows: list[SelectionRow] = []
    seen: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name: str | None = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name is None or name not in _SELECTION_READ_CALLS:
            continue
        row = SelectionRow(rel_path, node.lineno, name, in_seam)
        if row.key() not in seen:
            seen.add(row.key())
            rows.append(row)
    return rows


def discover_selection_callsites() -> list[SelectionRow]:
    """AST-walk the source trees for DIRECT read-SELECTION calls, sorted.

    Returns every direct ``resolve_mission_read_path(...)`` callsite — the
    read-side SELECTION authority — across ``src/specify_cli`` and
    ``src/mission_runtime``. Callers should reach the selection authority ONLY
    through the ``resolve_handle_to_read_path`` seam (which adds the traversal
    guard + fail-closed coord gate); a direct call re-acquires the authority
    outside the single owner. The ``in_seam_file`` flag distinguishes the
    legitimate seam-internal definitions from external bypasses.
    """
    rows: list[SelectionRow] = []
    for src_root in (SRC_SPECIFY_CLI, SRC_MISSION_RUNTIME):
        if not src_root.exists():
            continue
        for path in sorted(src_root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            # Fails closed on an unreadable/unparseable file (#5139).
            tree = parse_file(path)
            rows.extend(_find_selection_calls(tree, _rel(path)))
    rows.sort(key=lambda r: (r.rel_path, r.line))
    return rows


# --------------------------------------------------------------------------- #
# FR-006a — blessed EXTERNAL read-SELECTION callsites (outside the seam files).
#
# Seam-internal ``resolve_mission_read_path`` calls (``in_seam_file``) are
# auto-blessed (they ARE the seam definitions). Direct calls OUTSIDE the seam
# files re-acquire the read-selection authority and MUST be justified here.
# Any future entry must be content-identified (never a ``path:line`` locator,
# which the positional-anchor ban refuses). Every external selection callsite
# not listed here is a bypass of the ``resolve_handle_to_read_path`` seam
# (FR-006a regression).
# --------------------------------------------------------------------------- #
# WP01 (01KVN754) DRAINED both formerly-blessed external selection callsites by
# rerouting them onto the ``resolve_handle_to_read_path`` seam:
#   * ``specify_cli/acceptance/__init__.py`` (``_status_read_feature_dir``) now
#     calls ``resolve_handle_to_read_path`` directly; the lenient
#     ``status_dir if status_dir.exists() else feature_dir`` fallback is
#     preserved AROUND the seam call (the seam's ``require_exists=False`` default
#     keeps the byte-identical not-found→primary-candidate behaviour).
#   * ``mission_runtime/resolution.py`` (``_resolve_mission_slug``) now calls
#     ``resolve_handle_to_read_path`` and keeps its StatusReadPathNotFound /
#     MissionSelectorAmbiguous → ActionContextError boundary translation.
# With both rerouted, there are ZERO external direct selection callsites — the
# allowlist is intentionally empty (every direct call is now seam-internal).
ALLOWLISTED_SELECTION_CALLSITES: dict[str, str] = {}
