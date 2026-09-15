"""Charter path-literal authority gate — FR-016 anti-regression durability gate.

Mission ``doctrine-charter-split-unification-01KZ0SRB`` / WP11 (SINK).
Requirements: FR-016, NFR-004, NFR-002. Constraint: C-001.

This mission unified the charter read authority: ``charter.yaml`` is the
deterministic presence/config authority (C-001) and
:mod:`charter.bundle` owns the ONE declaration of the bundle paths
(:data:`charter.bundle.CHARTER_YAML` / :data:`charter.bundle.CHARTER_MD`).
WP01/WP02/WP03/WP06 drained the inline path literals that had scattered that
authority across the tree. Without a structural gate that drain is a
point-in-time cleanup that rots on the next PR — so this module makes it
durable, failing CI when either half of the split-brain regrows:

* **Clause (a)** — a NEW inline ``.kittify``/``charter``/``charter.{yaml,md}``
  path literal appears in a path-construction context outside
  ``src/charter/bundle.py``.
* **Clause (b)** — a NEW ``charter.md``-keyed ``.exists()`` **presence** gate
  appears anywhere. C-001: ``charter.md`` is readable secondary prose and is
  **never** a presence/config authority; only ``charter.yaml`` may gate.

Detection is AST path-construction, NOT raw text grep
-----------------------------------------------------
``research.md`` D6: a text grep for ``charter.md`` matches **161** lines in
``src/**/*.py``, almost all docstring/prose mentions (including this
docstring). A grep-shaped gate would be unmaintainable noise. This scanner
therefore only counts a charter filename constant when it sits in a genuine
**path-construction / filename-declaration** context:

1. a ``/`` path-join ``BinOp`` (``charter_dir / "charter.md"``),
2. an argument to a ``Path(...)`` construction,
3. the RHS of a constant assignment (``_CHARTER_FILENAME = "charter.md"``),
4. an element of a filename sequence literal (``("charter.yaml",)``).

Prose, docstrings, log messages and exception text are structurally excluded.

Scope decision (D6 open decision, resolved here): the gate DOES police ``src/charter/offering/**``
-------------------------------------------------------------------------------------------
``research.md`` D6 left open whether the gate polices ``src/charter/offering/**`` or
scopes only to ``src/charter/`` + ``src/specify_cli/``. **Decision: it polices
the whole of ``src/``, doctrine included, with the doctrine sites carried as
named allowlist entries.**

Rationale. ``src/charter/offering/`` genuinely *cannot* route onto the
``charter.bundle`` authority: the enforced layering is
``runtime -> charter -> doctrine`` (``test_runtime_charter_doctrine_boundary.py``),
and ``src/charter/offering/versioning.py`` states the rule in its own module docstring
("This module must NOT import from charter.*"). Importing
``charter.bundle.CHARTER_YAML`` from charter.offering would invert the dependency
direction and break the Shared Package Boundary ADR (doctrine ships as its own
wheel). So the doctrine sites are permanently deferred, not fixable.

That is an argument for *allowlisting* them, NOT for scoping them out. Scoping
``src/charter/offering/**`` out of the scan would be precisely the blanket directory
glob D10 forbids: it would let an unbounded number of FUTURE charter path
literals into doctrine, silently. Policing doctrine with a bounded, named,
shrink-only allowlist means each existing site is justified in writing and any
NEW doctrine site reds the build and forces a conscious decision. Strictly
stronger, and the scope stays honest.

Non-vacuity (NFR-004 + research.md D10)
---------------------------------------
An allowlisted gate is worthless if the allowlist is a growable escape hatch.
Five independent mechanics keep this one honest:

1. **Per-entry justification, no globs.** Every entry is a
   ``(file, qualname, token, literal, clause)`` composite key plus a mandatory
   one-line ``rationale``.
   The loader REJECTS wildcard/directory-shaped ``file`` fields
   (:func:`load_allowlist`), so ``upgrade/migrations/**`` cannot be waved
   through as a category — each migration site is enumerated by name.
2. **Shrink-only baseline.** ``charter_path_literal_baseline`` is a frozen
   scalar; the allowlist may only shrink beneath it. Adding an entry to
   green a new violation fails :func:`test_allowlist_shrink_only`.
3. **Ceiling + margin.** The live census must stay ``<= FLOOR``, and the FLOOR
   may not be pinned more than ``FLOOR_MARGIN`` above the live count — so the
   ceiling cannot be parked high to mask regrowth.
4. **Staleness twin-guard + exact accounting.** Every allowlist entry must
   match a live site, and the allowlist size must EQUAL the live census. A
   speculative entry pre-added to cover a future violation is stale, and fails.
5. **Allowlisting is per-literal, never per-module.** Because the key is the
   full composite, sanctioning one literal in a module does NOT waive AST
   detection for that module — a second, different literal in the very same
   file, even the same function, still reds
   (:func:`test_allowlisting_one_literal_does_not_waive_the_module`), and an
   allowlisted ``charter.yaml`` site swapped to ``charter.md`` still reds
   (:func:`test_allowlisted_yaml_site_cannot_be_swapped_to_md`).

The self-mutation proof (:func:`test_injected_charter_literal_is_flagged`)
injects into a scratch module that is deliberately **not** on the allowlist —
injecting into an already-allowlisted module would trivially pass and prove
nothing (D10).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pytest
import yaml

from tests.architectural._ratchet_keys import code_tokens_by_line

pytestmark = pytest.mark.architectural

# --------------------------------------------------------------------------- #
# Roots. this file: <root>/tests/architectural/test_charter_path_literal_authority.py
# --------------------------------------------------------------------------- #
_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[2]
SRC_ROOT = _REPO_ROOT / "src"
ALLOWLIST_PATH = _THIS.parent / "charter_path_literal_allowlist.yaml"

#: The ONE module entitled to declare the charter bundle path literals. Every
#: other module must import ``CHARTER_YAML`` / ``CHARTER_MD`` from it.
AUTHORITY_REL_PATH = "src/charter/bundle.py"

#: The charter bundle filenames whose path literals this gate governs.
CHARTER_FILENAMES: frozenset[str] = frozenset({"charter.yaml", "charter.md"})

#: Clause (b): only ``charter.md`` is barred from gating presence. ``charter.yaml``
#: presence checks are the C-001-sanctioned authority and are NOT violations.
PRESENCE_GATE_FILENAME = "charter.md"


class AllowlistEntryError(ValueError):
    """Raised when a YAML allow-list entry is malformed, glob-shaped, or unjustified."""


# --------------------------------------------------------------------------- #
# Composite key + allow-list machinery.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CharterPathKey:
    """Composite allow-list key surviving benign line drift.

    ``rel_path`` is the repo-relative source path, ``enclosing_qualname`` the
    dotted chain of enclosing ``def``/``class`` names (``"<module>"`` at file
    scope), and ``token`` the FROZEN tool-derived ``code_tokens_by_line`` string
    of the site's line. Keying on the composite (not on ``rel_path`` alone) is
    what makes sanctioning per-literal rather than per-module (non-vacuity
    mechanic 5).

    ``literal`` and ``clause`` are load-bearing, not decoration.
    ``code_tokens_by_line`` deliberately ELIDES string-literal *values* (so
    ``p = d / "charter.yaml"`` and ``p = d / "charter.md"`` both normalize to
    ``'p = d /'``). Keying on the token alone would therefore let an allowlisted
    ``charter.yaml`` site be silently swapped to ``charter.md`` — reintroducing
    exactly the C-001 split-brain this mission closed, under cover of its own
    allow-list entry. Pinning the matched ``literal`` (and the ``clause`` that
    fired, so a clause-(a) literal and a clause-(b) presence gate on one line
    stay distinct keys) closes that hole.
    """

    rel_path: str
    enclosing_qualname: str
    token: str
    literal: str
    clause: str


def _require_str(mapping: dict[str, object], key: str, context: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AllowlistEntryError(
            f"allow-list entry {context} is missing a non-empty {key!r} field "
            f"(got {value!r}); every deferred charter path literal needs an "
            f"explicit {key} — no silent drift"
        )
    return value


def _reject_glob_shaped(rel_path: str, context: str) -> None:
    """Refuse directory-glob allow-list entries (research.md D10, no blanket globs).

    ``upgrade/migrations/**`` is exactly the category-shaped waiver D10 forbids:
    it would sanction an unbounded number of FUTURE literals. Entries must name
    one real file, which the staleness twin-guard can then hold to a live site.
    """
    if "*" in rel_path or "?" in rel_path or rel_path.endswith("/"):
        raise AllowlistEntryError(
            f"allow-list entry {context} has a glob/directory-shaped file "
            f"{rel_path!r}; entries must name exactly one module (research.md D10 "
            "forbids blanket directory globs — enumerate each site by name)"
        )
    if not rel_path.endswith(".py"):
        raise AllowlistEntryError(f"allow-list entry {context} file {rel_path!r} is not a .py module path")


def load_allowlist(path: Path) -> list[CharterPathKey]:
    """Load the governance YAML's ``charter_path_literals`` entries.

    Each entry carries ``file:``/``qualname:``/``token:`` (the composite key)
    plus a mandatory one-line ``rationale:`` and an optional non-authoritative
    ``line:`` locator. Missing fields, non-integer locators and glob-shaped
    ``file`` fields all raise :class:`AllowlistEntryError`.
    """
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("charter_path_literals") or []
    keys: list[CharterPathKey] = []
    for idx, entry in enumerate(entries):
        context = f"charter_path_literals[{idx}]"
        if not isinstance(entry, dict):
            raise AllowlistEntryError(f"{context} is not a mapping (got {entry!r})")
        rel_path = _require_str(entry, "file", context)
        _reject_glob_shaped(rel_path, context)
        qualname = _require_str(entry, "qualname", context)
        token = _require_str(entry, "token", context)
        literal = _require_str(entry, "literal", context)
        clause = _require_str(entry, "clause", context)
        _require_str(entry, "rationale", context)
        if clause not in ("a", "b"):
            raise AllowlistEntryError(f"{context} has clause {clause!r}; expected 'a' or 'b'")
        line = entry.get("line")
        if line is not None and not isinstance(line, int):
            raise AllowlistEntryError(f"{context} ({qualname!r}) has a non-integer line locator {line!r}")
        keys.append(CharterPathKey(rel_path, qualname, token, literal, clause))
    return keys


def load_baseline(path: Path) -> int:
    """Return the frozen shrink-only baseline scalar.

    The baseline lives in the same YAML as the allow-list it bounds; the
    co-location is survivable because exact accounting
    (:func:`test_allowlist_accounts_for_every_live_site`) and the staleness
    twin-guard (:func:`test_allowlist_entries_are_still_live`) both compare
    against the LIVE census, not against this mutable scalar.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    value = raw.get("charter_path_literal_baseline")
    if not isinstance(value, int):
        raise AllowlistEntryError(f"charter_path_literal_baseline scalar missing or non-integer in {path.name}")
    return value


def staleness_twin_guard(allowlist_keys: set[CharterPathKey], live_keys: set[CharterPathKey]) -> list[CharterPathKey]:
    """Return allow-list keys with no matching live site.

    A non-empty result is a failure: the allow-list sanctions a literal that no
    longer exists (a drained site left masking) or one that never existed (a
    speculative entry pre-added to green a future violation).
    """
    return sorted(
        allowlist_keys - live_keys,
        key=lambda k: (k.rel_path, k.enclosing_qualname, k.token),
    )


# --------------------------------------------------------------------------- #
# AST helpers.
# --------------------------------------------------------------------------- #
def _parent_map(tree: ast.Module) -> dict[int, ast.AST]:
    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    return parents


def _qualname_from_parents(parents: dict[int, ast.AST], target: ast.AST) -> str:
    chain: list[str] = []
    cur: ast.AST | None = target
    while cur is not None:
        cur = parents.get(id(cur))
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            chain.append(cur.name)
        elif isinstance(cur, ast.Lambda):
            chain.append("<lambda>")
    return ".".join(reversed(chain)) if chain else "<module>"


def _enclosing_function(parents: dict[int, ast.AST], target: ast.AST) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    cur: ast.AST | None = target
    while cur is not None:
        cur = parents.get(id(cur))
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur
    return None


def _rel(path: Path) -> str:
    try:
        return path.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _iter_source_files(src_root: Path) -> list[Path]:
    return [p for p in sorted(src_root.rglob("*.py")) if "__pycache__" not in p.parts]


# --------------------------------------------------------------------------- #
# Clause (a) — charter path literal in a path-construction context.
# --------------------------------------------------------------------------- #
def is_charter_path_literal(value: object) -> bool:
    """True when *value* is a string whose final path segment is a charter filename.

    Matches both the bare filename form (``"charter.md"``) and the whole-path
    form (``Path(".kittify/charter/charter.yaml")``).
    """
    if not isinstance(value, str) or not value:
        return False
    return value.split("/")[-1] in CHARTER_FILENAMES


def _is_path_call(call: ast.Call) -> bool:
    """True for a ``Path(...)`` / ``pathlib.Path(...)`` construction."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id == "Path"
    return isinstance(func, ast.Attribute) and func.attr == "Path"


def is_path_construction_context(parent: ast.AST | None, node: ast.Constant) -> bool:
    """True when *node* sits in a path-construction / filename-declaration context.

    The four sanctioned shapes (see module docstring) — a ``/`` join, a
    ``Path(...)`` argument, a constant assignment RHS, or a filename sequence
    literal element. Everything else (docstrings, log/exception text, comparison
    operands) is prose and is deliberately NOT counted: that exclusion is what
    keeps this gate off the 161 raw-grep matches.
    """
    if parent is None:
        return False
    if isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Div):
        return True
    if isinstance(parent, ast.Call):
        return _is_path_call(parent) and node in parent.args
    if isinstance(parent, ast.Assign):
        return node is parent.value
    if isinstance(parent, ast.AnnAssign):
        return node is parent.value
    return isinstance(parent, (ast.List, ast.Tuple, ast.Set)) and node in parent.elts


@dataclass(frozen=True)
class CharterPathSite:
    """One discovered charter path literal. ``lineno`` is a diagnostics locator ONLY."""

    rel_path: str
    key: CharterPathKey
    lineno: int
    clause: str


def _scan_file(path: Path, rel: str) -> list[CharterPathSite]:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    parents = _parent_map(tree)
    token_map = code_tokens_by_line(source)
    charter_bundle_names = _charter_bundle_name_bindings(tree)

    def _site(node: ast.expr, literal: str, clause: str) -> CharterPathSite:
        key = CharterPathKey(
            rel,
            _qualname_from_parents(parents, node),
            token_map.get(node.lineno, ""),
            literal,
            clause,
        )
        return CharterPathSite(rel, key, node.lineno, clause)

    found: list[CharterPathSite] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and is_charter_path_literal(node.value):
            if is_path_construction_context(parents.get(id(node)), node):
                found.append(_site(node, str(node.value), "a"))
        elif isinstance(node, ast.Call) and _is_charter_md_presence_gate(node, parents, charter_bundle_names):
            found.append(_site(node, PRESENCE_GATE_FILENAME, "b"))
    return found


#: The module every charter-bundle filename constant must be imported from.
#: A ``Name`` receiver whose binding traces back to an ``ImportFrom`` of this
#: module is resolved to the literal it stands for — see
#: :func:`_charter_bundle_name_bindings`.
CHARTER_BUNDLE_MODULE = "charter.bundle"

#: Imported-constant name -> the path-literal it declares (``charter/bundle.py``
#: is the single declaration authority for both).
_CHARTER_BUNDLE_CONSTANT_LITERALS: dict[str, str] = {
    "CHARTER_MD": "charter.md",
    "CHARTER_YAML": "charter.yaml",
}


def _charter_bundle_name_bindings(tree: ast.Module) -> dict[str, str]:
    """Map local names bound to a charter filename to their literal.

    Two independent Name-forms feed the same downstream
    :func:`_path_expr_tail_literal` resolution:

    1. ``from charter.bundle import CHARTER_MD`` (and aliased imports,
       ``from charter.bundle import CHARTER_MD as _MD``) — resolved to the
       filename literal the constant declares. Without this, a receiver spine
       that bottoms out on an ``ast.Name`` referencing the imported constant —
       exactly the idiomatic form this mission's own migration produces
       (``root / CHARTER_MD``) — resolves to ``None`` and clause (b) goes
       blind the moment a call site adopts the constant it is supposed to be
       enforcing.
    2. A MODULE-LOCAL string-constant alias declared in the same file rather
       than imported from ``charter.bundle`` (``_CHARTER_FILENAME =
       "charter.md"`` ... ``d / _CHARTER_FILENAME``) — resolved by
       :func:`_module_level_charter_filename_aliases`. This is a distinct
       blind spot from (1): a local alias never touches ``charter.bundle`` at
       all, so the import-based resolution above cannot see it, yet the
       presence-gate shape it feeds is identical. Two real, live sites
       (``src/charter/activation/sync.py`` / ``src/charter/activation/pack_manager.py``) use exactly
       this form.
    """
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == CHARTER_BUNDLE_MODULE:
            for alias in node.names:
                literal = _CHARTER_BUNDLE_CONSTANT_LITERALS.get(alias.name)
                if literal is not None:
                    bindings[alias.asname or alias.name] = literal
    bindings.update(_module_level_charter_filename_aliases(tree))
    return bindings


def _module_level_charter_filename_aliases(tree: ast.Module) -> dict[str, str]:
    """Map module-level ``NAME = "charter.md"`` / ``"charter.yaml"`` constants to their literal.

    Only top-level (module-scope) ``Assign`` nodes qualify — a function-local
    reassignment of the same name is a different binding and is already
    resolved separately by :func:`_assigned_value`'s intra-function hop.
    """
    aliases: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not (isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
            continue
        literal = node.value.value
        if literal not in CHARTER_FILENAMES:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                aliases[target.id] = literal
    return aliases


# --------------------------------------------------------------------------- #
# Clause (b) — charter.md-keyed .exists() presence gate (C-001).
# --------------------------------------------------------------------------- #
def _path_expr_tail_literal(expr: ast.expr, charter_bundle_names: dict[str, str] | None = None) -> str | None:
    """Return the final literal path segment of a path expression, if any.

    Walks the right spine of ``/`` joins and unwraps ``Path(...)`` so both
    ``d / "charter.md"`` and ``Path(".kittify/charter/charter.md")`` resolve.
    *charter_bundle_names*, when given, additionally resolves an ``ast.Name``
    leaf whose binding is the imported ``charter.bundle.CHARTER_MD`` /
    ``CHARTER_YAML`` constant (``d / CHARTER_MD``) to the literal it stands
    for — the constant-import form is not a different case from the literal,
    it IS the literal, one indirection away.
    """
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value.split("/")[-1]
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Div):
        return _path_expr_tail_literal(expr.right, charter_bundle_names)
    if isinstance(expr, ast.Call) and _is_path_call(expr) and expr.args:
        return _path_expr_tail_literal(expr.args[-1], charter_bundle_names)
    if isinstance(expr, ast.Name) and charter_bundle_names is not None and expr.id in charter_bundle_names:
        return charter_bundle_names[expr.id]
    return None


def _assigned_value(fn: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> ast.expr | None:
    """Return the RHS of *name*'s binding inside *fn* (single intra-function hop)."""
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == name:
                    return node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None and isinstance(node.target, ast.Name) and node.target.id == name:
            return node.value
    return None


def _is_charter_md_presence_gate(call: ast.Call, parents: dict[int, ast.AST], charter_bundle_names: dict[str, str]) -> bool:
    """True for an ``.exists()`` call whose receiver path ends in ``charter.md``.

    Resolves the direct form ``(d / "charter.md").exists()``, the one-hop
    named form ``charter_md_path = d / "charter.md"`` ... ``charter_md_path.exists()``,
    and the constant-import form ``charter_md_path = d / CHARTER_MD`` ...
    ``charter_md_path.exists()`` (via *charter_bundle_names*).
    """
    func = call.func
    if not isinstance(func, ast.Attribute) or func.attr != "exists":
        return False
    receiver: ast.expr = func.value
    if isinstance(receiver, ast.Name):
        fn = _enclosing_function(parents, call)
        bound = _assigned_value(fn, receiver.id) if fn is not None else None
        if bound is None:
            return False
        receiver = bound
    return _path_expr_tail_literal(receiver, charter_bundle_names) == PRESENCE_GATE_FILENAME


# --------------------------------------------------------------------------- #
# Scan + gate.
# --------------------------------------------------------------------------- #
def scan_charter_path_literals(src_root: Path) -> list[CharterPathSite]:
    """AST-walk ``<src_root>/**/*.py`` for charter path literals and md presence gates.

    Excludes :data:`AUTHORITY_REL_PATH` — ``charter/bundle.py`` IS the single
    declaration authority, so its literals are the definition, not a violation.
    """
    sites: list[CharterPathSite] = []
    for path in _iter_source_files(src_root):
        rel = _rel(path)
        if rel == AUTHORITY_REL_PATH:
            continue
        sites.extend(_scan_file(path, rel))
    return sites


def check_charter_path_literal_gate(src_root: Path, allowlist: set[CharterPathKey]) -> list[str]:
    """Return violation strings for un-allowlisted charter path literals."""
    remedy = {
        "a": ("declares an inline charter bundle path literal instead of importing charter.bundle.CHARTER_YAML / CHARTER_MD (FR-016 clause a)"),
        "b": ("gates presence on charter.md; charter.yaml is the C-001 presence authority and charter.md is readable secondary prose only (FR-016 clause b)"),
    }
    violations: list[str] = []
    for site in scan_charter_path_literals(src_root):
        if site.key in allowlist:
            continue
        violations.append(
            f"{site.rel_path}:{site.lineno} ({site.key.enclosing_qualname}) "
            f"token={site.key.token!r} {remedy[site.clause]} — route it through the "
            "authority or allow-list it with a one-line rationale"
        )
    return sorted(violations)


@lru_cache(maxsize=1)
def live_sites() -> tuple[CharterPathSite, ...]:
    """Cached census of the real ``src/`` tree (the scan is re-used by many tests)."""
    return tuple(scan_charter_path_literals(SRC_ROOT))


def _live_keys() -> set[CharterPathKey]:
    return {site.key for site in live_sites()}


# --------------------------------------------------------------------------- #
# Concrete integer bounds (NFR-002) — seeded from the live AST census run in
# WP11 AFTER the WP01/WP02/WP03/WP06 repoints landed, so the frozen set is the
# minimal residual and not a stale pre-drain snapshot.
# --------------------------------------------------------------------------- #
# 2026-08-11 (#3317 landing): lowered 49 -> 48 alongside the allow-list DRAIN of
# the FR-005 graceful-degrade charter.md read (extracted into
# context_result_builders.py, where charter_path is a parameter, not a keyed
# `<root> / CHARTER_MD` literal — the census slot is genuinely gone).
# RESTORED 2026-09-14 (#3514): the bounds block and the four governance tests
# below were deleted by the #3285 test-sanitization landing (2026-08-12) while
# the module docstring and the allow-list YAML header kept claiming them — the
# drift mission charter-preflight-missing-charter-advisory-01M050PD filed as
# #3514. Re-seeded at the honest current census: 50 live sites (49 at the
# 2026-08-16 GREW note, +2 from the 2026-08-13 #2831 F1/F2 fix whose growth was
# never recorded, -1 stale activation.py entry drained by the #3838 WP01
# rewrite and removed in the same #3514 change).
CHARTER_PATH_LITERAL_FLOOR = 50
FLOOR_MARGIN = 2


# =========================================================================== #
# TESTS
# =========================================================================== #


# --- unit: composite-key machinery -----------------------------------------


# --- unit: detector shape ----------------------------------------------------


# --- NFR-004 self-mutation proof (injects into a NON-allowlisted module) ----
def test_injected_charter_literal_is_flagged(tmp_path: Path) -> None:
    """Self-mutation proof: a re-introduced inline charter literal goes RED.

    D10: the injection target is a **scratch module that is NOT on the
    allowlist** — injecting into an already-allowlisted module would be
    sanctioned by its existing entry, pass trivially, and prove nothing. This is
    a standing test, so the RED-on-demand property is re-proven on every run,
    not eyeballed once.
    """
    pkg = tmp_path / "src" / "scratch_pkg"
    pkg.mkdir(parents=True)
    (pkg / "regressed.py").write_text(
        "from pathlib import Path\n"
        "class Regressed:\n"
        "    def load(self, repo_root):\n"
        '        charter_path = repo_root / ".kittify" / "charter" / "charter.md"\n'
        "        return charter_path.exists()\n",
        encoding="utf-8",
    )
    scratch_src = tmp_path / "src"

    # The injected module is absent from the real allow-list by construction.
    real_allowlist = set(load_allowlist(ALLOWLIST_PATH))
    assert all("scratch_pkg" not in k.rel_path for k in real_allowlist), "self-mutation target must be a NON-allowlisted module (D10)"

    violations = check_charter_path_literal_gate(scratch_src, real_allowlist)
    assert violations, "self-mutation: a re-introduced charter path literal must be flagged"
    assert any("Regressed.load" in v for v in violations)
    # Both clauses fire on this shape: the literal (a) and the md presence gate (b).
    clauses = {s.clause for s in scan_charter_path_literals(scratch_src)}
    assert clauses == {"a", "b"}


def test_allowlisting_one_literal_does_not_waive_the_module(tmp_path: Path) -> None:
    """Second non-vacuity guard: the allow-list is per-literal, never per-module.

    The escape-hatch failure mode this blocks: "my module is on the allowlist,
    so anything I add to it is fine." Because the key is the
    ``(file, qualname, token)`` triple, sanctioning ONE literal leaves every
    other literal in the same file — even in the same function — still RED. An
    author cannot widen an existing entry to swallow an unrelated violation;
    they must add a new, separately-justified entry, which is in turn bounded by
    the shrink-only baseline (mechanic 2).
    """
    pkg = tmp_path / "src" / "scratch_pkg"
    pkg.mkdir(parents=True)
    (pkg / "two_literals.py").write_text(
        'def load(d):\n    sanctioned = d / "charter.yaml"\n    smuggled = d / "charter.md"\n    return sanctioned, smuggled\n',
        encoding="utf-8",
    )
    scratch_src = tmp_path / "src"

    sites = scan_charter_path_literals(scratch_src)
    assert {s.key.literal for s in sites} == {"charter.yaml", "charter.md"}, "fixture must contain exactly the two distinct charter literals"

    sanctioned = next(s for s in sites if s.key.literal == "charter.yaml")
    smuggled = next(s for s in sites if s.key.literal == "charter.md")
    assert sanctioned.rel_path == smuggled.rel_path, "both literals live in ONE module"
    assert sanctioned.key.enclosing_qualname == smuggled.key.enclosing_qualname, "both literals live in the SAME function — the strongest form of the guard"

    # Sanction only the first literal: the module is now "on the allowlist".
    violations = check_charter_path_literal_gate(scratch_src, {sanctioned.key})
    assert len(violations) == 1, "allowlisting one literal must not waive the module"
    assert smuggled.key.token in violations[0]


def test_allowlisted_yaml_site_cannot_be_swapped_to_md(tmp_path: Path) -> None:
    """An allowlisted ``charter.yaml`` site swapped to ``charter.md`` still reds.

    ``code_tokens_by_line`` elides string-literal values, so token+qualname alone
    would treat the two as the SAME site and the existing entry would sanction
    the swap — silently reintroducing the C-001 split-brain under cover of the
    allow-list. Pinning ``literal`` in the key is what makes this RED.
    """
    pkg = tmp_path / "src" / "scratch_pkg"
    pkg.mkdir(parents=True)
    target = pkg / "swap.py"
    before = 'def load(d):\n    charter_path = d / "charter.yaml"\n    return charter_path\n'
    target.write_text(before, encoding="utf-8")
    scratch_src = tmp_path / "src"

    sanctioned = {s.key for s in scan_charter_path_literals(scratch_src)}
    assert check_charter_path_literal_gate(scratch_src, sanctioned) == [], "sanity: green before"

    # The swap: same file, same function, same normalized token — only the
    # governed filename changed (yaml -> md).
    target.write_text(before.replace("charter.yaml", "charter.md"), encoding="utf-8")
    after = scan_charter_path_literals(scratch_src)
    assert {s.key.token for s in after} == {k.token for k in sanctioned}, "precondition: the normalized token is identical across the swap"
    assert check_charter_path_literal_gate(scratch_src, sanctioned), (
        "a charter.yaml -> charter.md swap must NOT be waved through by the pre-existing charter.yaml allow-list entry (C-001)"
    )


def test_speculative_allowlist_entry_is_caught_as_stale() -> None:
    """A pre-added entry covering a not-yet-existing violation fails staleness.

    Closes the other half of the escape hatch: you cannot land the allow-list
    entry in one PR and the violation in the next, because an entry with no
    matching live site is stale on arrival.
    """
    speculative = CharterPathKey("src/specify_cli/future.py", "Future.load", "p = d /", "charter.md", "a")
    live = _live_keys()
    assert staleness_twin_guard({speculative}, live) == [speculative]


# --- real-tree gate ----------------------------------------------------------
def test_gate_green_against_seeded_allowlist() -> None:
    """With the seeded allow-list, the live tree reports zero violations."""
    allowlist = set(load_allowlist(ALLOWLIST_PATH))
    violations = check_charter_path_literal_gate(SRC_ROOT, allowlist)
    assert violations == [], "\n".join(violations)


def test_census_stays_under_ceiling() -> None:
    """Shrink-only CEILING + margin: fewer charter path literals is progress."""
    count = len(live_sites())
    assert count <= CHARTER_PATH_LITERAL_FLOOR, (
        f"charter path-literal census grew to {count}; expected "
        f"<= {CHARTER_PATH_LITERAL_FLOOR}. A new inline charter path literal "
        "regressed the FR-016 drain — import charter.bundle.CHARTER_YAML / "
        "CHARTER_MD instead, or allow-list it with a one-line rationale."
    )
    assert CHARTER_PATH_LITERAL_FLOOR - count <= FLOOR_MARGIN, (
        f"CHARTER_PATH_LITERAL_FLOOR ({CHARTER_PATH_LITERAL_FLOOR}) sits more than "
        f"FLOOR_MARGIN ({FLOOR_MARGIN}) above the live count ({count}); tighten it "
        "to the honest census so it cannot mask a future regrowth."
    )


def test_allowlist_accounts_for_every_live_site() -> None:
    """The allow-list size EQUALS the live census — every literal is justified."""
    assert len(load_allowlist(ALLOWLIST_PATH)) == len(live_sites())


def test_allowlist_shrink_only() -> None:
    """The frozen baseline: entries may only be removed, never added.

    A growth is possible only through an explicit, reviewed baseline bump
    recorded in the YAML header's GREW audit trail — the scalar is in the
    same file as the list, so the bump is a visible diff a reviewer signs.
    """
    keys = load_allowlist(ALLOWLIST_PATH)
    baseline = load_baseline(ALLOWLIST_PATH)
    assert len(keys) <= baseline, (
        f"charter path-literal allow-list ({len(keys)}) exceeds baseline ({baseline}) — entries may only be removed (routed onto charter.bundle), never added"
    )


def test_allowlist_entries_are_still_live() -> None:
    """Twin-guard: every seeded entry matches a live site (no masking leftovers)."""
    stale = staleness_twin_guard(set(load_allowlist(ALLOWLIST_PATH)), _live_keys())
    assert stale == [], f"stale charter path-literal allow-list entries: {stale}"
