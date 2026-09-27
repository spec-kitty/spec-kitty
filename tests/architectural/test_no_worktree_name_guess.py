"""Literal-ban ratchet: worktree/branch name-guessing forbidden outside the seam.

This is the **filesystem twin** of the branch-identity seam — the 4th ratchet
assertion guarding the recurring wrong-compose regression class
(#1860 / #1949 / #1978 / #1899). The single canonical naming seam,
``src/specify_cli/lanes/branch_naming.py``, composes AND parses every mission /
lane / worktree / coordination directory name.

**Lane names are keyed on the creation input ONLY (FR-002;
ADR** ``docs/adr/3.x/2026-09-26-2-lane-naming-keyed-on-creation-input.md``
**).** A lane branch/worktree/dir name is composed from
``(mission_slug, lane_id)`` alone — the *creation input* — never from the
Mission's declared ``mission_id``. The Mission identity is not an input to
a lane name (I-1); ``lane_branch_name`` / ``worktree_dir_name`` /
``worktree_path`` / ``predict_lane_worktree`` take no ``mission_id``
parameter at all (the signature leg below is green by construction,
FR-009). Mission and
coordination names (``mission_branch_name*`` / ``coord_*``) are the ones still
keyed on ``(slug, mission_id)`` — a DIFFERENT naming domain this ratchet does
not police at the signature level. Any module that hand-rolls a worktree-dir,
mission-branch, or mid8-dedup name outside the seam reintroduces the defect: a
mid8-era mission whose on-disk worktree is ``<slug>-<mid8>-lane-x`` is mis-named
``<slug>-lane-x`` by a bare ``f"{slug}-{lane}"`` guess, so the path never
resolves (the #1899 class).

The ratchet scans every ``*.py`` under ``src/specify_cli/`` and ``src/runtime/``
for THREE forbidden idioms (the first two alone miss the actual
recurrence shape), plus FOUR further legs (FR-008/FR-009/NFR-003) that
close the class so it **stays** closed — signature, compose, match, and
def-use (see the four-leg gate extension section near the end of this file):

1. **worktree-dir name-guess** — a ``.worktrees/`` path composed via an
   interpolated f-string, INCLUDING the assign-then-join indirection
   (``name = f"{slug}-{lane}"`` then ``... / ".worktrees" / name``). Caught by
   walking ``/``-division chains where one operand is a ``.worktrees`` literal /
   ``WORKTREES_DIR*`` name and another is an interpolated f-string (directly, or
   via a local name bound earlier in the function to such an f-string).
2. **branch name-guess** — a literal ``f"kitty/mission-{…}"`` (interpolated)
   not produced by the seam.
3. **inline mid8 re-dedup / bare mission-dir compose** — the
   ``…endswith(f"-{mid8}")…`` / ``endswith(suffix)`` compose idiom and the bare
   ``f"{slug}-{mid8}"`` mission-dir composition — the #1860/#1949 recurrence
   shape that carries NO ``.worktrees/`` literal (this is what would catch the
   historical ``tasks.py:844`` / ``_create.py:157`` sites).

Allow-list: exactly the seam module ``lanes/branch_naming.py`` (the sole legal
home of these idioms) plus a SMALL number of narrowly-justified, individually
commented carve-outs for genuinely-benign uses that are NOT a name compose
(e.g. a ``git branch --list`` glob, or a string fed straight back into the seam
PARSER). Each carve-out is a drift-proof ``(enclosing_qualname, token_line)``
composite key — inserting a blank or comment line above a pinned site does NOT
flip the ratchet RED (FR-008 / WP06 re-key).

Design-P REFERENCE implementation (do NOT convert)
--------------------------------------------------
This module is the canonical **reference implementation** of the *Design-P
content-pinned gate-key* pattern, named as such by the refactor-stable doctrine
(the ``testing-principles`` styleguide) and mission
``refactor-stable-gate-substrate-01KWK3FY``. Design-P freezes a tool-derived
``(enclosing_qualname, token)`` comparand (see ``_ALLOWED_SITES_FILES`` above)
and scans live source for set membership, so a gate key is pinned to CONTENT,
never to a raw line number. The pattern's two proof legs live here as the
template every other converted gate mirrors:

* ``test_name_compose_offenders_match_pinned_baseline`` — the staleness guard: a
  frozen allow-list entry with no live offender (or an extra unjustified entry)
  drifts the pinned baseline count and trips RED.
* ``test_composite_key_survives_line_drift`` — the drift theater: shifting a
  pinned site down by blank/comment lines leaves its composite key unchanged, so
  the ratchet stays GREEN on pure line drift.

**These key semantics MUST NOT be converted to seed-derivation** (the
``_RAW_JOIN_SITES`` load-time-seed style). Seed-derivation is content-FOLLOWING:
a fixed line seed still breaks on drift and a content edit is invisible — it
fails both halves of NFR-001 and would REGRESS this file's content-detection.
The mission's research D1 proves this empirically; FR-005's earlier
"convert Family E" plan was CANCELLED for exactly this reason. This file is the
destination pattern, not a conversion target.

WP09 / Issue #1899 / FR-001 / FR-005 / FR-009.
"""

from __future__ import annotations

import ast
import inspect as _inspect
import re
from collections.abc import Callable
from pathlib import Path
from typing import TypeGuard

import pytest

from tests.architectural._ast_scan import parse_file, read_and_parse
from tests.architectural._ratchet_keys import composite_key

pytestmark = [pytest.mark.architectural, pytest.mark.git_repo]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCAN_ROOTS = (
    _REPO_ROOT / "src" / "specify_cli",
    _REPO_ROOT / "src" / "runtime",
)

# The single canonical naming seam. It is the ONLY module permitted to compose
# worktree-dir / mission-branch / mid8-dedup names by literal/f-string — every
# other module must route through its public API
# (worktree_path / worktree_dir_name / mission_branch_name_required /
# coord_* / mission_dir_name).
_SEAM_REL = "src/specify_cli/lanes/branch_naming.py"

# Marker for the ``.worktrees`` directory literal (matches the bare name and a
# ``.worktrees/...`` leading-segment literal).
_WORKTREES_NAME = ".worktrees"

# Idiom 3 keys on the **mid8 disambiguator** specifically — the token the
# #1860/#1949 recurrence class drops or double-appends. A generic ``f"{a}-{b}"``
# or ``endswith(suffix)`` for path/glob matching is NOT the recurrence shape and
# must NOT be flagged (it would drown the real signal in false positives). The
# detector therefore requires the interpolation/suffix to reference ``mid8``.
_MID8_TOKEN_RE = re.compile(r"\bmid8\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Narrow, individually-justified allow-list (NOT broad carve-outs).
# Each entry is a drift-proof ``(enclosing_qualname, token_line)`` composite
# key (FR-008 / WP06).  Inserting a blank or comment line above a pinned site
# leaves the key unchanged; only a semantic edit (rename the function or change
# the guarded line) produces a new key.
# ---------------------------------------------------------------------------

# Stale-detection map: composite_key → relative file path (used ONLY by
# ``test_allow_list_entries_are_real_and_benign`` to verify the key is still
# live in the expected file; not used for the ratchet lookup itself).
_ALLOWED_SITES_FILES: dict[tuple[str, str], str] = {
    # ── recovery.py: a ``git branch --list`` GLOB pattern, not a compose ──
    # ``f"kitty/mission-{mission_slug}*"`` (trailing ``*``) is passed to
    # ``git branch --list`` to ENUMERATE existing branches; it never names a
    # branch to create. Benign UX/listing glob.
    ("_list_mission_branches", "pattern ="): "src/specify_cli/lanes/recovery.py",
    # NOTE: the ``vcs/detection.py`` seam-parser-round-trip carve-out
    # and the ``lifecycle_sync.py`` diagnostic-placeholder carve-out were
    # REMOVED here. The fix routed ``_get_locked_vcs_from_feature`` through the
    # slug-free ``parse_lane_worktree_dir`` parser (no more fake
    # ``kitty/mission-{worktree_name}`` branch-name round trip) and replaced
    # ``lifecycle_sync.py``'s ``f"{mission_slug}-unknown"`` placeholder with a
    # non-lane-shaped sentinel (no more interpolated ``.worktrees/`` join).
    # Neither site is a live offender any more — a stale exemption is a
    # false-negative window, so both entries are dropped (5 -> 3) in the SAME
    # commit that changed the underlying lines (FR-008).
    # NOTE: the previously-allow-listed pre-existing ``<slug>-<mid8>`` composes
    # (``mission_creation.py:321`` / ``worktree.py:367`` / ``worktree.py:370``)
    # have been ROUTED through ``mission_dir_name()`` / ``resolve_mid8()`` (the
    # #2000 follow-up landed). The detector now flags ZERO offenders at those
    # sites, so the carve-outs were dropped (a stale exemption is a
    # false-negative window). The
    # ``test_name_compose_offenders_match_pinned_baseline`` cross-check below
    # pins the offender count so a re-grown stale allow-list entry is caught.
    # ── surface_resolver.py: _coord_mid8 fail-closed raise payload (idiom 1) ──
    # post-merge addition (coord-primary-partition-lock-01KWZ46V, squash-merged
    # 007528ddf): ``coord_candidate = repo_root / ".worktrees" /
    # f"{mission_slug}-coord" / KITTY_SPECS_DIR / mission_slug`` composes a
    # ``.worktrees``-shaped Path ONLY to populate the ``StatusReadPathNotFound``
    # diagnostic ``raise`` payload — the same site already dispositioned DIAG
    # (no FS sink) in ``test_single_mission_surface_resolver.py`` /
    # ``untrusted_path_audit/inventory.md``. It replaced a
    # ``CoordinationWorkspace.worktree_path(...)`` seam call (#2091, invariant
    # M-1: that seam now REQUIRES a non-empty mid8 and would raise a DIFFERENT
    # exception before this more specific fail-closed one could raise) — no git
    # worktree is ever created/looked up from this value; it is raised
    # immediately.
    # (PR #845/#801: the composed join was line-joined by ruff format when the
    # merged-primary pre-check landed above it — same site, same disposition,
    # token updated to the single-line form.)
    (
        "_coord_mid8",
        "coord_candidate = repo_root / / / KITTY_SPECS_DIR / mission_slug ,",
    ): "src/specify_cli/coordination/surface_resolver.py",
    # ── workspace.py: CoordinationWorkspaceIdentityUnresolved diagnostic (idiom 2) ──
    # post-merge addition (coord-primary-partition-lock-01KWZ46V, same commit):
    # the exception's message is a human-readable string that names the
    # malformed-shape placeholder ``'kitty/mission-<slug>-'`` (angle brackets,
    # not an f-string field) and separately interpolates the real
    # ``mission_slug`` elsewhere in the same sentence ("for mission
    # {mission_slug!r}"). The idiom-2 literal-text check does not distinguish
    # "field interpolated inside the kitty/mission- segment" from "field
    # interpolated anywhere in the concatenated string", so it flags this
    # prose. No branch/worktree/dir name is ever composed or used from this
    # string — it is raised as a StructuredError message and never parsed back
    # into a ref (same finding already carved out in
    # ``test_topology_resolution_boundary.py::_ALLOWLISTED_LEGACY_COMPOSE_SITES``).
    (
        "CoordinationWorkspaceIdentityUnresolved.__init__",
        "",
    ): "src/specify_cli/coordination/workspace.py",
}

_ALLOWED_SITES: frozenset[tuple[str, str]] = frozenset(_ALLOWED_SITES_FILES)

# Pinned count of name-COMPOSE offenders the detector currently flags across the
# scan roots (excluding the seam), pinned as a committed literal so the
# allow-list cannot rot undetected. Mirrors the short-id ratchet's
# ``_SHORTID_BASELINE_RAW_MATCHES``: a stale allow-list entry (one that no longer
# points at a live offender) or an extra unjustified entry would drift this
# count and trip the cross-check. Composition (re-verified after
# the ``vcs/detection.py`` and ``lifecycle_sync.py`` sites were fixed and their
# carve-outs dropped, 5 -> 3):
#   recovery.py:135                    (branch-list glob — benign carve-out)
#   surface_resolver.py:499            (post-merge coord-primary-partition-lock
#                                        01KWZ46V — _coord_mid8 DIAG raise payload,
#                                        benign carve-out)
#   workspace.py:123                   (post-merge coord-primary-partition-lock
#                                        01KWZ46V — CoordinationWorkspaceIdentityUnresolved
#                                        diagnostic message, benign carve-out)
# => 3 raw offenders, all accounted for by the allow-list => 0 un-accounted.
_NAME_COMPOSE_BASELINE_RAW_MATCHES = 3

# Helper text appended to every failure so the offender knows the fix.
# No longer recommends worktree_path()/worktree_dir_name() WITH an
# identity (lane names take no mission_id, FR-002) — points instead at
# predict_lane_worktree() (the single lane-worktree placement decision) plus
# the slug-free recognition parsers (parse_lane_worktree_dir /
# lane_id_for_worktree_dir) for the read/recognition side.
_SEAM_GUIDANCE = (
    "Route the compose through the canonical naming seam "
    f"(`{_SEAM_REL}`): use predict_lane_worktree() (or worktree_path() / "
    "worktree_dir_name(), which take NO mission_id) for lane worktree dirs, "
    "mission_branch_name_required()/coord_branch_name() for branches, and "
    "mission_dir_name()/coord_mission_dir_name() for mission dirs. To "
    "RECOGNIZE an existing worktree dir or lane branch, use the slug-free "
    "parsers parse_lane_worktree_dir() / lane_id_for_worktree_dir() /"
    "parse_mission_slug_from_branch() instead of a hand-rolled match. Do NOT "
    "hand-roll a `.worktrees/` f-string, a `kitty/mission-{...}` literal, a "
    '`-lane-` compose/match, or an inline `endswith(f"-{mid8}")` dedup '
    "outside the seam."
)


def _rel(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def _iter_source_files() -> list[Path]:
    files: list[Path] = []
    for root in _SCAN_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            files.append(path)
    return files


def _is_interpolated_fstring(node: ast.AST) -> TypeGuard[ast.JoinedStr]:
    """True for an f-string carrying at least one ``{...}`` interpolation."""
    return isinstance(node, ast.JoinedStr) and any(isinstance(value, ast.FormattedValue) for value in node.values)


def _is_worktrees_literal(node: ast.AST) -> bool:
    """True for a ``.worktrees`` / ``.worktrees/...`` string literal."""
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and (node.value == _WORKTREES_NAME or node.value.startswith(_WORKTREES_NAME + "/"))


def _is_worktrees_name(node: ast.AST) -> bool:
    """True for a ``WORKTREES_DIR`` / ``WORKTREES_DIRNAME`` style identifier."""
    return isinstance(node, ast.Name) and "WORKTREES" in node.id.upper()


def _flatten_div_operands(node: ast.BinOp) -> list[ast.expr]:
    """Flatten a left-assoc ``a / b / c`` Div chain into its leaf operands."""
    operands: list[ast.expr] = []
    stack: list[ast.expr] = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, ast.BinOp) and isinstance(current.op, ast.Div):
            stack.append(current.left)
            stack.append(current.right)
        else:
            operands.append(current)
    return operands


def _collect_fstring_bound_names(tree: ast.AST) -> set[str]:
    """Names bound to an interpolated f-string (assign-then-join indirection).

    ``name = f"{slug}-{lane}"`` followed by ``... / ".worktrees" / name`` must
    still be caught, so a join operand that is a local ``Name`` bound to an
    interpolated f-string counts as the f-string for idiom 1.
    """
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_interpolated_fstring(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bound.add(target.id)
        elif isinstance(node, ast.AnnAssign) and node.value is not None and _is_interpolated_fstring(node.value) and isinstance(node.target, ast.Name):
            bound.add(node.target.id)
    return bound


def _collect_mid8_suffix_names(tree: ast.AST) -> set[str]:
    """Names bound to a mid8-referencing f-string suffix (``suffix = f"-{mid8}"``).

    The endswith-dedup idiom 3 has an assign-then-test variant: a local (commonly
    ``suffix``) is bound to an interpolated f-string that resolves the mid8, then
    tested with ``X.endswith(suffix)``. Track exactly those names so the test can
    flag the dedup without flagging generic ``endswith(suffix)`` glob/path checks.
    """
    bound: set[str] = set()
    for node in ast.walk(tree):
        value: ast.expr | None = None
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            value, targets = node.value, list(node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            value, targets = node.value, [node.target]
        if value is None or not _is_interpolated_fstring(value):
            continue
        if not _references_mid8(value):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                bound.add(target.id)
    return bound


def _operand_is_interpolated(node: ast.expr, fstring_names: set[str]) -> bool:
    """True if a join operand is an interpolated f-string (direct or via a name)."""
    if _is_interpolated_fstring(node):
        return True
    return isinstance(node, ast.Name) and node.id in fstring_names


def _fstring_literal_text(node: ast.JoinedStr) -> str:
    """Concatenated literal (non-interpolated) text of an f-string."""
    return "".join(str(value.value) for value in node.values if isinstance(value, ast.Constant))


def _references_mid8(node: ast.AST) -> bool:
    """True when an expression references the ``mid8`` disambiguator.

    Matches both a ``mid8(...)`` call and a name/attribute carrying ``mid8``
    (e.g. ``mid8_value``, ``meta.mid8``). Keyed on ``mid8`` specifically so the
    detector targets the recurrence token, not arbitrary string composition.
    """
    return bool(_MID8_TOKEN_RE.search(ast.unparse(node)))


def _is_bare_mid8_dir_compose(node: ast.JoinedStr) -> bool:
    """True for a bare ``f"{slug}-{mid8}"`` mission-dir compose (idiom 3).

    Recurrence shape with NO ``.worktrees/`` literal: exactly two interpolations
    joined by a single ``-`` and nothing else, where the SECOND interpolation
    resolves the ``mid8`` disambiguator. This is the #1860/#1949 shape that
    historically surfaced at ``tasks.py:844`` / ``_create.py:157`` — the canonical
    ``<human-slug>-<mid8>`` mission/worktree dir name that must be produced by the
    seam's ``mission_dir_name()`` / ``worktree_dir_name()`` instead.
    """
    interpolations = [v for v in node.values if isinstance(v, ast.FormattedValue)]
    if len(interpolations) != 2:
        return False
    if _fstring_literal_text(node) != "-":
        return False
    # The disambiguator is the trailing token; require it to reference mid8.
    return _references_mid8(interpolations[1].value)


def _scan_file(path: Path) -> dict[int, str]:
    """Return ``{lineno: idiom-label}`` for every forbidden idiom in ``path``."""
    tree = parse_file(path)

    fstring_names = _collect_fstring_bound_names(tree)
    mid8_suffix_names = _collect_mid8_suffix_names(tree)
    violations: dict[int, str] = {}

    for node in ast.walk(tree):
        # Idiom 1 — worktree-dir name-guess: a ``/`` join chain mixing a
        # ``.worktrees`` literal/name with an interpolated f-string (direct or
        # via an assign-then-join local name).
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            operands = _flatten_div_operands(node)
            has_worktrees = any(_is_worktrees_literal(op) or _is_worktrees_name(op) for op in operands)
            has_fstring = any(_operand_is_interpolated(op, fstring_names) for op in operands)
            if has_worktrees and has_fstring:
                violations[node.lineno] = "worktree-dir name-guess (idiom 1)"
            continue

        # Idiom 3 — inline mid8 re-dedup: ``X.endswith(f"-{mid8}")`` /
        # ``X.endswith(suffix)`` (with ``suffix = f"-{mid8}"``) used to gate a
        # manual ``<slug>-<mid8>`` mission-dir compose. Keyed on mid8 so a
        # generic ``endswith(suffix)`` glob/path test is NOT flagged.
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "endswith" and node.args:
            arg = node.args[0]
            if _is_interpolated_fstring(arg) and _references_mid8(arg):
                # ``endswith(f"-{mid8}")`` — the canonical dedup shape.
                violations[node.lineno] = "inline mid8 re-dedup endswith (idiom 3)"
            elif isinstance(arg, ast.Name) and arg.id in mid8_suffix_names:
                # ``endswith(suffix)`` where ``suffix = f"...{mid8}"`` — the
                # assign-then-test variant of the same dedup.
                violations[node.lineno] = "inline mid8 re-dedup endswith (idiom 3)"
            continue

        if _is_interpolated_fstring(node):
            literal_text = _fstring_literal_text(node)
            # Idiom 2 — branch name-guess: a ``kitty/mission-{...}`` f-string.
            if "kitty/mission-" in literal_text:
                violations[node.lineno] = "branch name-guess kitty/mission- (idiom 2)"
            # Idiom 3 (no-.worktrees variant) — bare ``f"{slug}-{mid8}"`` dir.
            elif _is_bare_mid8_dir_compose(node):
                violations[node.lineno] = "bare slug-mid8 mission-dir compose (idiom 3)"

    return violations


def test_no_worktree_or_branch_name_guess_outside_seam() -> None:
    """No worktree/branch/mid8 name-guess may live outside the canonical seam.

    Composing or de-duplicating a worktree-dir, mission-branch, or mission-dir
    name by hand anywhere other than ``lanes/branch_naming.py`` reintroduces the
    #1860/#1949/#1899 wrong-compose class. The seam is the sole legal home; a
    short, individually-justified allow-list carves out the provably-benign
    non-compose uses (a listing glob, a seam-parser round-trip).
    """
    offenders: list[str] = []

    for path in _iter_source_files():
        rel = _rel(path)
        if rel == _SEAM_REL:
            # The seam itself is where these idioms legally live.
            continue
        source = path.read_text(encoding="utf-8")
        for lineno, label in sorted(_scan_file(path).items()):
            key = composite_key(source, lineno)
            if key in _ALLOWED_SITES:
                continue
            offenders.append(f"  {rel}:{lineno}: {label}")

    if offenders:
        pytest.fail(
            "Forbidden worktree/branch name-guess found outside the canonical "
            "naming seam — this reintroduces the #1860/#1949/#1899 wrong-compose "
            "regression class.\n\n"
            "Offending sites:\n" + "\n".join(sorted(offenders)) + "\n\n" + _SEAM_GUIDANCE
        )


# ===========================================================================
# WP02 (this mission) — AST short-id slice detector + failover-bypass rule.
#
# A SECOND ratchet, distinct from the name-COMPOSE idioms above: it forbids
# hand-derived mission ``mid8`` SHORT-IDs (``mission_id[:8]`` and friends)
# outside the single sanctioned derivation home. The recurring defect this
# guards (FR-004 / FR-010) is a consumer that re-slices the mission_id to a
# mid8 instead of routing through ``resolve_mid8`` — the failover-aware
# entrypoint that reconciles a stale slug tail against the declared identity.
# A bare ``mission_id[:8]`` skips that reconciliation and silently mis-routes
# a colliding-tail mission (the #1899 / #1978 class).
#
# ⚠️ HONESTY NOTE — scope and known limits (binding; do NOT overclaim):
#   * This is a **syntax-level tripwire**, not a completeness oracle. It is
#     defeated by helper indirection: ``def _short(x): return x[:8]`` then
#     ``_short(mission_id)`` carries no ``[:8]`` at the call site and escapes.
#     The real correctness guarantee for this mission is
#     verification-by-deletion: WP03/WP04/WP05 deleted every consumer slice and
#     the suite stayed green. This ratchet only stops a *future* regrowth of
#     the exact syntactic shape.
#   * AST cannot structurally distinguish ``mission_id`` from ``invocation_id``
#     or a content hash — detection rests on a NAME predicate (substring
#     ``mission_id`` / ``mid``). The predicate is deliberately a SUBSTRING/glob,
#     never exact-match, so ``str(raw_mission_id)[:8]`` and ``mission_id_meta``
#     (the original blind spots Paula found) cannot escape via a wrapper or a
#     suffix.
#   * It explicitly does **NOT** cover the deferred ``feature_dir.parent.parent``
#     repo-root-derivation class (~9 sites), which is owned by the read-path /
#     error-fidelity follow-on focus (#2007), not this mission.
# ===========================================================================

# The short-id detector scans ALL of ``src/`` (FR-004 / FR-010 routing is
# repo-wide), NOT just the ``specify_cli`` + ``runtime`` subset the name-COMPOSE
# detector above uses — because one of the sanctioned homes
# (``mission_runtime/context.py``) and potential consumers (``mission_runtime``,
# ``charter``, ``glossary``, ...) live outside that subset. Benign content-hash
# / state slices in those packages carry neither ``mission_id`` nor ``mid`` in
# the operand name, so the name predicate spares them.
_SHORTID_SCAN_ROOT = _REPO_ROOT / "src"


def _iter_shortid_source_files() -> list[Path]:
    """Every ``*.py`` under ``src/`` (the short-id detector's repo-wide scope)."""
    files: list[Path] = []
    if _SHORTID_SCAN_ROOT.exists():
        for path in sorted(_SHORTID_SCAN_ROOT.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            files.append(path)
    return files


# The three permanent sanctioned slice HOMES, skipped at FILE level (the
# ``_SEAM_REL`` home-skip pattern). ``mission_id[:8]`` is legitimate ONLY here:
#   * mission_runtime/identity.py — ``resolve_mid8``'s single-derivation
#     primitive now lives here (relocated out of ``branch_naming.py`` by the
#     coord-trust-2841 layer-boundary follow-up); its failover-aware ``[:8]``
#     slice is THE canonical derivation every consumer routes through.
#   * branch_naming.py — retained as a re-export site for ``resolve_mid8`` /
#     ``mid8_from_slug`` (back-compat import surface) and still hosts its own
#     private ``_mid8`` primitive plus ``resolve_transaction_mid8``'s slice.
#   * mission_runtime/context.py — ``IdentityFragment`` computes the mid8
#     "here and nowhere else" (its own docstring) and self-checks the invariant.
_SHORTID_HOME_FILES: frozenset[str] = frozenset(
    {
        "src/specify_cli/lanes/branch_naming.py",
        "src/mission_runtime/context.py",
        "src/mission_runtime/identity.py",
    }
)

# The single canonical failover-aware short-id entrypoint every consumer must
# route through instead of re-slicing.
_SHORTID_SEAM = "resolve_mid8"

# Substring tokens (case-insensitive) that mark a sliced operand as the
# mission-identity shape. SUBSTRING, not exact-match — that is the whole point:
#   ``mission_id`` catches ``mission_id`` / ``raw_mission_id`` / ``mission_id_meta``
#                  / ``self.mission_id`` (attr) ;
#   ``mid``        catches ``mid`` / ``mid8`` / ``raw_mid`` / ``_mid8``.
# A pure ``invocation_id`` / content-hash operand contains NEITHER token, so it
# is not flagged (and ``invocation_id[:8]`` is additionally named-out below).
_MISSION_ID_NAME_TOKENS: tuple[str, ...] = ("mission_id", "mid")

# Named exclusion: a DIFFERENT identity domain that legitimately slices its own
# id. ``invocation/executor.py`` formats an invocation_id short-tag for a log
# line; it is not a mission mid8 and the name predicate already excludes it, but
# we pin it by name so the intent is explicit and self-documenting.
# Keyed as (enclosing_qualname, token_line) composite (FR-008 / WP06 re-key).
# ``invocation_id[:8]`` lives inside an f-string on Python 3.11 so the
# tokenize-based token_line strips the f-string body → ``"message ="``.
# The qualname ``ProfileInvocationExecutor._commit_op_record`` distinguishes it
# from any future ``message =`` line in a different method.
_SHORTID_NAMED_EXCLUSIONS: frozenset[tuple[str, str]] = frozenset(
    {
        # src/specify_cli/invocation/executor.py:469
        ("ProfileInvocationExecutor._commit_op_record", "message ="),
    }
)

# Stale-detection map for named exclusions: composite_key → relative file path.
_SHORTID_NAMED_EXCLUSIONS_FILES: dict[tuple[str, str], str] = {
    ("ProfileInvocationExecutor._commit_op_record", "message ="): ("src/specify_cli/invocation/executor.py"),
}

# Narrow, individually-justified short-id allow-list (composite key).
# The mission-identity CONSUMER class is otherwise EMPTY after WP03/WP04/WP05
# routed every site; only this deliberate diagnostic-tolerance fallback remains.
# Keyed as (enclosing_qualname, token_line) composite (FR-008 / WP06 re-key).
# The two formerly byte-identical doctor.py tolerance sites were CONSOLIDATED by
# the coord-trust Surface D fold into the single shared helper
# ``_resolve_coord_short`` — one allow-list entry now covers every coord
# worktree/branch short-id derivation in the doctor.
_SHORTID_ALLOWED_SITES: frozenset[tuple[str, str]] = frozenset(
    {
        # ── _coordination_doctor.py — diagnostic short-id TOLERANCE, not a missed route ──
        # ``return resolve_mid8(slug, mission_id=mission_id) or mission_id[:8]``
        # inside the shared ``_resolve_coord_short`` helper. The coord-trust
        # Surface D fold deduplicated the two byte-identical tolerance sites
        # (formerly ``_check_coordination_worktree_health`` and
        # ``_check_lane_sparse_checkout_drift``) into this one helper.
        # WP03 routed the derivation through the failover-aware ``resolve_mid8``;
        # the ``or mission_id[:8]`` tail is a CONSCIOUS fallback that keeps the
        # doctor diagnostic emitting a display short-id even when resolve_mid8
        # declines to ``""`` (e.g. a malformed/short mission_id). Tolerance branch.
        (
            "_resolve_coord_short",
            "return resolve_mid8 ( mission_slug , mission_id = mission_id ) or mission_id [ : 8 ]",
        ),
    }
)

# Stale-detection map for the short-id allow-list: composite_key → relative file path.
# The coord-trust Surface D fold consolidated the two ``_coordination_doctor``
# tolerance sites into the single ``_resolve_coord_short`` helper; one entry now.
_SHORTID_ALLOWED_SITES_FILES: dict[tuple[str, str], str] = {
    (
        "_resolve_coord_short",
        "return resolve_mid8 ( mission_slug , mission_id = mission_id ) or mission_id [ : 8 ]",
    ): "src/specify_cli/cli/commands/_coordination_doctor.py",
}

# Pre-mission baseline of mission-identity ``[:8]`` slices across ``src/`` (the
# raw count BEFORE home/allow-list filtering), pinned as a committed literal so
# "the consumer class is empty" is an OBJECTIVE, diff-checkable claim rather
# than a re-derivation of the live tree. Composition (verified at WP02 land;
# doctor sites collapsed 2→1 by the coord-trust Surface D fold; re-verified
# after the coord-trust-2841 relocation of ``resolve_mid8`` into
# ``mission_runtime/identity.py``):
#   mission_runtime/identity.py:84  (1, HOME — ``resolve_mid8``'s derivation,
#       post-relocation)
#   branch_naming.py:146/363  (2, HOME — ``_mid8`` + ``resolve_transaction_mid8``)
#   mission_runtime/context.py:152/165  (2, HOME)
#   cli/commands/_coordination_doctor.py  (1, allow-listed tolerance in the
#       shared ``_resolve_coord_short`` helper; was 2 byte-identical sites
#       before the coord-trust Surface D dedup)
# => 6 raw matches; 5 in homes + 1 allow-listed => 0 un-accounted consumers.
_SHORTID_BASELINE_RAW_MATCHES = 6


def _unwrap_str_call(node: ast.expr) -> ast.expr:
    """Unwrap a single ``str(<expr>)`` call to its inner argument.

    ``str(raw_mission_id)[:8]`` slices the *call* node; the identity-bearing
    name is the call argument. Unwrapping lets the substring predicate see
    ``raw_mission_id`` instead of the opaque ``str(...)`` text — closing the
    string-wrapped blind spot (M1).
    """
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "str" and len(node.args) == 1:
        return node.args[0]
    return node


def _operand_is_mission_identity(node: ast.expr) -> bool:
    """True if the sliced operand names the mission-identity shape.

    Substring (not exact) match on the unparsed operand text — after unwrapping
    a ``str(...)`` wrapper — against ``mission_id`` / ``mid``. Substring is
    deliberate: an exact-match predicate would let ``str(raw_mission_id)`` and
    ``mission_id_meta`` escape (the original recurrence blind spots).
    """
    text = ast.unparse(_unwrap_str_call(node)).lower()
    return any(token in text for token in _MISSION_ID_NAME_TOKENS)


def _is_eight_slice(node: ast.AST) -> bool:
    """True for a subscript slice ``X[:8]`` / ``X[0:8]`` (no step)."""
    if not isinstance(node, ast.Subscript):
        return False
    sl = node.slice
    if not isinstance(sl, ast.Slice) or sl.step is not None:
        return False
    lower_ok = sl.lower is None or (isinstance(sl.lower, ast.Constant) and sl.lower.value == 0)
    upper_ok = isinstance(sl.upper, ast.Constant) and sl.upper.value == 8
    return lower_ok and upper_ok


def _scan_shortid_file(path: Path) -> dict[int, str]:
    """Return ``{lineno: label}`` for forbidden short-id idioms in ``path``.

    Two idioms:
      * **slice** — a mission-identity ``[:8]`` slice (incl. ``str(<id>)[:8]``).
      * **bypass** — a bare ``_mid8(...)`` call to the now-private primitive
        (the failover-bypass rule, T019): consumers must call ``resolve_mid8``,
        not the unguarded private slice primitive.
    """
    tree = parse_file(path)

    violations: dict[int, str] = {}
    for node in ast.walk(tree):
        if _is_eight_slice(node):
            assert isinstance(node, ast.Subscript)  # narrowed by _is_eight_slice
            if _operand_is_mission_identity(node.value):
                operand = ast.unparse(node.value)
                violations[node.lineno] = f"mission-identity short-id slice `{operand}[:8]` — route through `{_SHORTID_SEAM}` (failover-aware), do not re-slice"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_mid8":
            violations[node.lineno] = f"bare `_mid8(...)` call bypasses the failover entrypoint — route through `{_SHORTID_SEAM}` instead of the private primitive"
    return violations


def _iter_shortid_offenders() -> list[str]:
    """Collect ``file:line: label`` for every un-accounted short-id idiom."""
    offenders: list[str] = []
    for path in _iter_shortid_source_files():
        rel = _rel(path)
        if rel in _SHORTID_HOME_FILES:
            # Sanctioned derivation homes — skipped at file level.
            continue
        source = path.read_text(encoding="utf-8")
        for lineno, label in sorted(_scan_shortid_file(path).items()):
            key = composite_key(source, lineno)
            if key in _SHORTID_NAMED_EXCLUSIONS or key in _SHORTID_ALLOWED_SITES:
                continue
            offenders.append(f"  {rel}:{lineno}: {label}")
    return offenders


def test_no_mission_shortid_slice_or_failover_bypass_outside_seam() -> None:
    """No mission-identity ``mid8`` short-id may be hand-derived outside the seam.

    The mission-identity CONSUMER class must be EMPTY: every consumer routes its
    mid8 through ``resolve_mid8`` (FR-004 / FR-010). The three sanctioned
    derivation homes (``mission_runtime/identity.py`` — ``resolve_mid8``'s
    single-derivation slice, relocated here by the coord-trust-2841
    layer-boundary follow-up — plus ``branch_naming.py`` and
    ``mission_runtime/context.py``) are skipped at file level;
    ``invocation_id[:8]`` is a different identity domain excluded by name; the
    doctor diagnostic-tolerance ``or mission_id[:8]`` is a single justified
    allow-list entry. Anything else is a real missed route.
    """
    offenders = _iter_shortid_offenders()
    if offenders:
        pytest.fail(
            "Forbidden mission-identity short-id derivation found outside the "
            "sanctioned home — this reintroduces the colliding-tail mis-route "
            "class (#1899 / #1978). A bare `mission_id[:8]` (or `_mid8(...)`) "
            "skips the failover reconciliation in `resolve_mid8`.\n\n"
            "Offending sites (each is a REAL missed route — do NOT allow-list "
            "without a justification that proves it is not a consumer):\n" + "\n".join(sorted(offenders)) + f"\n\nRoute the derivation through `{_SHORTID_SEAM}` "
            "(`src/specify_cli/lanes/branch_naming.py`)."
        )


def test_shortid_detector_self_test_flags_all_five_shapes() -> None:
    """The detector flags all 5 recurrence shapes and spares ``invocation_id``.

    Plants each shape Paula found into an in-memory module and asserts the
    scanner flags it; plants ``invocation_id[:8]`` (a different identity domain)
    and asserts it is NOT flagged. Guards the substring predicate against
    silently regressing to exact-match (which would let the wrapped/suffixed
    shapes escape).
    """
    flagged_source = "mission_id[:8]\nstr(raw_mission_id)[:8]\nmid[:8]\nraw_mid[:8]\nmission_id_meta[:8]\n"
    not_flagged_source = "invocation_id[:8]\n"

    flagged_tree = ast.parse(flagged_source)
    flagged: list[str] = []
    for node in ast.walk(flagged_tree):
        if _is_eight_slice(node):
            assert isinstance(node, ast.Subscript)
            if _operand_is_mission_identity(node.value):
                flagged.append(ast.unparse(node.value))

    assert flagged == [
        "mission_id",
        "str(raw_mission_id)",
        "mid",
        "raw_mid",
        "mission_id_meta",
    ], f"detector missed a recurrence shape; flagged only: {flagged}"

    not_flagged_tree = ast.parse(not_flagged_source)
    for node in ast.walk(not_flagged_tree):
        if _is_eight_slice(node):
            assert isinstance(node, ast.Subscript)
            assert not _operand_is_mission_identity(node.value), (
                "invocation_id[:8] is a different identity domain and must NOT be flagged by the mission-identity short-id detector"
            )


def test_shortid_failover_bypass_self_test() -> None:
    """The failover-bypass rule flags a bare ``_mid8(...)`` call.

    The now-private ``_mid8`` primitive slices without the failover
    reconciliation; a consumer calling it directly bypasses ``resolve_mid8``.
    Plants such a call (outside any home) and asserts it is flagged.
    """
    bypass_source = "x = _mid8(mission_id)\n"
    tree = ast.parse(bypass_source)
    flagged = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_mid8":
            flagged = True
    assert flagged, "failover-bypass rule must flag a bare `_mid8(...)` call"


# ===========================================================================
# T025 — Drift-proof + non-vacuity executable tests (FR-008 / WP06)
#
# Three executable tests proving the re-keyed ratchet:
#   1. Survives a +1 line drift (blank/comment line inserted above a pin).
#   2. Flags a NEW offender in an allow-listed function (non-vacuity).
#   3. Produces DISTINCT keys for the two byte-identical doctor.py sites.
# ===========================================================================


def test_new_offender_in_allowlisted_function_is_flagged_red() -> None:
    """A new offender INSIDE an allow-listed function is NOT matched (RED).

    Inserts an EXTRA ``mission_id[:8]`` slice at a DIFFERENT line inside the
    same function as an allow-listed entry.  The composite key for the new
    offender shares the qualname component but has a different token-line
    component, so it does NOT match the allow-listed key.  This proves the
    token-line component is load-bearing: the allow-list is not too loose.
    """
    from tests.architectural._ratchet_keys import composite_key as ck

    # Simulate a source whose allow-list key is the same qualname as doctor.py.
    # The allowed line: ``short = resolve_mid8(...) or mission_id[:8]``
    # The extra (forbidden) line: ``tag = mission_id[:8]``
    source_with_extra = (
        "def _check_coordination_worktree_health(mission_id: str) -> None:\n"
        "    from foo import resolve_mid8\n"
        "    short = resolve_mid8(mission_id) or mission_id[:8]\n"
        "    tag = mission_id[:8]  # NEW offender — not in the allow-list\n"
        "    print(short, tag)\n"
    )
    # The allow-listed key for the ORIGINAL site (line 3):
    # qualname = "_check_coordination_worktree_health"
    # token_line = "short = resolve_mid8 ( mission_id ) or mission_id [ : 8 ]"
    import ast as _ast

    allowed_lineno = 3  # ``short = resolve_mid8(...) or mission_id[:8]``
    extra_lineno = 4  # ``tag = mission_id[:8]``

    allowed_key = ck(source_with_extra, allowed_lineno)
    extra_key = ck(source_with_extra, extra_lineno)

    # Both share the same qualname; their token lines MUST differ.
    assert allowed_key[0] == extra_key[0], (
        f"expected both lines to be inside the same function (allowed qualname={allowed_key[0]!r}, extra qualname={extra_key[0]!r})"
    )
    assert allowed_key[1] != extra_key[1], (
        "token-line component must differ for the two offender lines — "
        "the allow-list would be vacuous if they matched.\n"
        f"  allowed token_line : {allowed_key[1]!r}\n"
        f"  extra   token_line : {extra_key[1]!r}"
    )

    # Simulate the ratchet lookup: the extra offender must NOT be exempted.
    allow_set: frozenset[tuple[str, str]] = frozenset({allowed_key})
    assert extra_key not in allow_set, (
        "the extra offender matched the allow-list key — the token-line "
        "component is not load-bearing (allow-list is too loose).\n"
        f"  extra key    : {extra_key!r}\n"
        f"  allowed key  : {allowed_key!r}"
    )

    # Verify the AST scanner actually flags the extra line (not just the allow-listed one).
    tree = _ast.parse(source_with_extra)
    flagged_linenos: list[int] = []
    for node in _ast.walk(tree):
        if _is_eight_slice(node):
            assert isinstance(node, _ast.Subscript)
            if _operand_is_mission_identity(node.value):
                flagged_linenos.append(node.lineno)
    assert extra_lineno in flagged_linenos, f"the short-id scanner did not flag the extra offender at line {extra_lineno}; flagged lines: {flagged_linenos}"


# ===========================================================================
# Four-leg gate extension.
#
# The seam functions take no ``mission_id`` (it is impossible to REQUEST a
# lane-naming form). This section makes the class STAY closed: it adds
# four independent detection legs on top of the three idioms above, each
# with its own numerically-capped, shrink-only allow-list (FR-008/FR-009/
# NFR-003). A site flagged by more than one leg's detector needs only ONE
# allow-list entry — every leg's suppression check consults the SAME
# combined set of new-leg allow-listed keys (``_NEW_LEG_ALLOWED``), so
# registering a site once (under whichever leg the caps table names)
# exempts it from every leg that would otherwise also flag it.
#
# Baseline offender counts (measured before the naming-authority sweep, for
# calibration only): 6 identity-passing lane calls (since removed — the
# signature leg is green by construction), 18 ``mission_id=None`` calls
# (also since removed), 1 hand-rolled compose, 7 match sites (5 were routed
# through the seam; the remaining 2 — ``detection.py``'s fake-branch round
# trip and ``_coordination_doctor.py``'s ``startswith`` over-match — were
# fixed), 5 allow-listed prose/enumeration sites, 5 raw matches in the
# existing (idiom 1-3) gate above (now 3, after that fix shrank it).
#
# Current counts (re-measured at HEAD): compose sites outside the
# naming authority = 0; allow-lists: signature 0, compose 1, match 5,
# def-use 1.
# ===========================================================================

# ---------------------------------------------------------------------------
# Shared tokens
# ---------------------------------------------------------------------------

_LANE_MATCH_TOKENS: tuple[str, ...] = ("-lane-", "lane-[", _KITTY_MISSION_TOKEN := "kitty/mission-")
_LANE_COMPOSE_TOKENS: tuple[str, ...] = ("-lane-", "lane-", "kitty/mission-")
# Deliberately CASE-SENSITIVE and lowercase-only: the execution-lane domain's
# identifiers (`lane_id`, `lane_dir`, `lane`, `lanes`) are conventionally
# lowercase in this codebase, while the UNRELATED WP-status `Lane` enum
# (`Lane.PLANNED`, `Lane.CLAIMED`, ...) is capitalized. An ``re.IGNORECASE``
# match here would false-flag every `.format(source=Lane.X.value, ...)` call
# in `status/wp_state.py` -- a different "lane" domain entirely.
_LANE_NAME_RE = re.compile(r"\blane[_a-z]*\b")

# The four seam functions whose signature must carry no ``mission_id`` --
# lane names are keyed on the creation input alone (FR-002).
_LANE_SEAM_FUNCS: tuple[str, ...] = (
    "lane_branch_name",
    "worktree_dir_name",
    "worktree_path",
    "predict_lane_worktree",
)


def _contains_lane_or_mission_token(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _module_str_constants(tree: ast.AST) -> dict[str, str]:
    """Module-level ``NAME = "literal"`` string constants, for named-constant
    indirection (compose/match legs must resolve ``_LANE_TOKEN = "-lane-"``
    style indirection)."""
    consts: dict[str, str] = {}
    for node in ast.walk(tree):
        value: ast.expr | None = None
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            value, targets = node.value, list(node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            value, targets = node.value, [node.target]
        if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                consts[target.id] = value.value
    return consts


def _resolve_str_operand(node: ast.expr, consts: dict[str, str]) -> str | None:
    """Resolve a literal or named-constant string operand; ``None`` if neither."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id in consts:
        return consts[node.id]
    return None


def _is_docstring_node(node: ast.AST, docstring_ids: set[int]) -> bool:
    return id(node) in docstring_ids


def _collect_docstring_ids(tree: ast.AST) -> set[int]:
    """id() of every module/class/function docstring Expr.value node."""
    ids: set[int] = set()
    candidates: list[ast.AST] = [tree]
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            candidates.append(node)
    for scope in candidates:
        body = getattr(scope, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            ids.add(id(first.value))
    return ids


# ---------------------------------------------------------------------------
# Leg 1 — signature: the seam functions take no ``mission_id`` (green by
# construction); a call passing ``mission_id=`` to any of them,
# alias-aware, is a regression.
# ---------------------------------------------------------------------------

_SIGNATURE_ALLOWLIST_FILES: dict[tuple[str, str], str] = {}
_SIGNATURE_ALLOWLIST: frozenset[tuple[str, str]] = frozenset(_SIGNATURE_ALLOWLIST_FILES)


def _seam_signatures_carry_no_mission_id() -> list[str]:
    """Assert each seam function's live signature has no ``mission_id`` param."""
    from specify_cli.lanes import branch_naming, worktree_allocator

    funcs = {
        "lane_branch_name": branch_naming.lane_branch_name,
        "worktree_dir_name": branch_naming.worktree_dir_name,
        "worktree_path": branch_naming.worktree_path,
        "predict_lane_worktree": worktree_allocator.predict_lane_worktree,
    }
    bad: list[str] = []
    for name, fn in funcs.items():
        if "mission_id" in _inspect.signature(fn).parameters:
            bad.append(name)
    return bad


def _collect_seam_import_aliases(tree: ast.AST) -> dict[str, str]:
    """Map local alias -> canonical seam-func name for every import in *tree*
    (module-level AND function-local, since several call sites import the
    seam lazily inside a function body)."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in _LANE_SEAM_FUNCS:
                    aliases[alias.asname or alias.name] = alias.name
    return aliases


def _scan_signature_file(path: Path) -> dict[int, str]:
    """Flag any alias-aware call to a seam function passing ``mission_id=``."""
    source, tree = read_and_parse(path)  # fails closed (#5139); never swallows a parse failure
    aliases = _collect_seam_import_aliases(tree)
    if not aliases:
        return {}
    violations: dict[int, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func_name: str | None = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        if func_name is None or func_name not in aliases:
            continue
        for kw in node.keywords:
            if kw.arg == "mission_id":
                canonical = aliases[func_name]
                violations[node.lineno] = f"signature: `{canonical}(...)` called with `mission_id=` -- the seam takes no mission_id"
    return violations


# ---------------------------------------------------------------------------
# Leg 2 — compose: a hand-rolled f-string / ``+`` / ``%`` / ``.format`` /
# ``.join`` composition producing a lane token or a slug-lane join, outside
# the seam. Prose is excluded from heuristics -- handled by the
# allow-list only.
# ---------------------------------------------------------------------------


def _flatten_add_operands(node: ast.BinOp) -> list[ast.expr]:
    """Flatten a left-assoc ``a + b + c`` Add chain into its leaf operands,
    preserving LEFT-TO-RIGHT source order (boundary-adjacency checks below
    depend on operand order, unlike idiom 1's order-independent membership
    test)."""

    def _flatten(current: ast.expr) -> list[ast.expr]:
        if isinstance(current, ast.BinOp) and isinstance(current.op, ast.Add):
            return _flatten(current.left) + _flatten(current.right)
        return [current]

    return _flatten(node)


def _collect_lane_bound_names(tree: ast.AST) -> set[str]:
    """Names LOCALLY assigned (within this file) to a lane-referencing
    expression -- the "variable-renamed" evasion this leg must still catch
    (``lid = lane_dir.name`` then ``f"{s}-{lid}"``). Deliberately scoped to
    LOCAL assignments only: a bare cross-module import (e.g. importing the
    unrelated ``PLANNING_LANE_ID`` display constant) carries no local
    assignment here and is NOT treated as lane-bound -- resolving arbitrary
    imported constants would need cross-module tracing this AST-only leg does
    not attempt (documented limit, mirrors the def-use leg's
    no-inter-procedural-tracing note)."""
    bound: set[str] = set()
    for node in ast.walk(tree):
        value: ast.expr | None = None
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            value, targets = node.value, list(node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            value, targets = node.value, [node.target]
        if value is None or not _LANE_NAME_RE.search(ast.unparse(value)):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                bound.add(target.id)
    return bound


def _fstring_boundary_violation(node: ast.JoinedStr, lane_bound: set[str]) -> str | None:
    """Rule A (boundary-adjacent literal token) + Rule B (slug/lane operand
    join) for a single interpolated f-string.

    Rule A requires the token to sit at the LITERAL/interpolation BOUNDARY
    (the very end of a literal segment immediately followed by an
    interpolation, or the very start of one immediately following an
    interpolation) -- not merely anywhere in the concatenated literal text.
    This is what keeps ``"... required for lane-based features ... {x}"``
    (the token far from any interpolation) out of the offender set while
    still catching ``f"lane-{chr(letter)}"`` and ``f"kitty/mission-{slug}..."``.
    """
    values = node.values
    for index, segment in enumerate(values):
        if not (isinstance(segment, ast.Constant) and isinstance(segment.value, str)):
            continue
        text = segment.value
        next_is_interp = index + 1 < len(values) and isinstance(values[index + 1], ast.FormattedValue)
        prev_is_interp = index > 0 and isinstance(values[index - 1], ast.FormattedValue)
        if next_is_interp and any(text.endswith(tok) for tok in _LANE_COMPOSE_TOKENS):
            return "compose (f-string): lane/kitty-mission literal + interpolation"
        if prev_is_interp and any(text.startswith(tok) for tok in _LANE_COMPOSE_TOKENS):
            return "compose (f-string): lane/kitty-mission literal + interpolation"

    # Rule B: two interpolations joined by a bare ``-``, where the SECOND
    # operand is a lane-bound name (or itself textually lane-referencing) --
    # ``f"{slug}-{lane_id}"`` / the variable-renamed evasion.
    for index in range(len(values) - 2):
        first, sep, second = values[index], values[index + 1], values[index + 2]
        if not (isinstance(first, ast.FormattedValue) and isinstance(sep, ast.Constant) and sep.value == "-" and isinstance(second, ast.FormattedValue)):
            continue
        operand = second.value
        operand_text = ast.unparse(operand)
        if _LANE_NAME_RE.search(operand_text) or (isinstance(operand, ast.Name) and operand.id in lane_bound):
            return "compose (f-string): slug/lane operand join"
    return None


def _operand_is_lane_like(node: ast.expr, lane_bound: set[str]) -> bool:
    return bool(_LANE_NAME_RE.search(ast.unparse(node))) or (isinstance(node, ast.Name) and node.id in lane_bound)


def _add_concat_violation(node: ast.BinOp, consts: dict[str, str], lane_bound: set[str]) -> str | None:
    """``+`` concatenation.

    Rule A: the literal operand immediately ADJACENT (in source order) to a
    non-constant operand must end/start with the token at the boundary --
    mirrors the f-string boundary rule so unrelated prose containing the
    token elsewhere in the chain (e.g. "...lane-tip record...") is not
    flagged.

    Rule B: a chain joining a
    slug-like and a lane-like operand is flagged even with NO literal token
    at all, e.g. ``mission_slug + "-" + lane_id`` -- the same "join a
    slug-like and a lane-like operand" rule the f-string/.format/%/.join
    forms already apply.
    """
    operands = _flatten_add_operands(node)
    texts = [_resolve_str_operand(op, consts) for op in operands]
    for index, text in enumerate(texts):
        if text is None:
            continue
        next_nonconst = index + 1 < len(texts) and texts[index + 1] is None
        prev_nonconst = index > 0 and texts[index - 1] is None
        if (next_nonconst and any(text.endswith(tok) for tok in _LANE_COMPOSE_TOKENS)) or (
            prev_nonconst and any(text.startswith(tok) for tok in _LANE_COMPOSE_TOKENS)
        ):
            return "compose (+ concatenation): lane/kitty-mission literal"
    # Rule B: a bare ``"-"``-only literal ADJACENT to a lane-like operand in
    # the flattened chain, e.g. ``mission_slug + "-" + lane_id``. Narrowly
    # scoped to the bare-hyphen separator (not "any operand anywhere is
    # lane-like", which false-positived on ordinary prose mentioning
    # "lane(s)" in an unrelated literal segment, e.g. "...write lanes.json
    # without..." or " in lane " + lane, and on plain int/list `+` chains
    # like ``len(lanes[Lane.CLAIMED]) + len(lanes[Lane.IN_PROGRESS])`` that
    # carry no string literal at all) -- this is the ``+``-form counterpart
    # of the f-string boundary rule's ``\}-\{`` adjacency.
    for index, text in enumerate(texts):
        if text != "-":
            continue
        neighbors = [operands[index - 1]] if index > 0 else []
        if index + 1 < len(operands):
            neighbors.append(operands[index + 1])
        if any(_operand_is_lane_like(op, lane_bound) for op in neighbors):
            return "compose (+ concatenation): slug/lane operand join"
    return None


def _mod_format_violation(node: ast.BinOp, lane_bound: set[str]) -> str | None:
    """``%`` formatting.

    Rule A: the template literal
    itself carries the token, e.g. ``"kitty/mission-%s" % slug`` -- a SINGLE
    operand, so Rule B's ``len(elements) >= 2`` guard alone would miss it.

    Rule B: the template is almost never the token-bearing literal in
    practice; it is the substituted operands that carry the slug/lane shape,
    e.g. ``"%s-%s" % (slug, lane_id)``.
    """
    if not (isinstance(node.left, ast.Constant) and isinstance(node.left.value, str)):
        return None
    if _contains_lane_or_mission_token(node.left.value, _LANE_COMPOSE_TOKENS):
        return "compose (%% formatting): lane/kitty-mission literal"
    elements: list[ast.expr] = list(node.right.elts) if isinstance(node.right, ast.Tuple) else [node.right]
    if len(elements) >= 2 and any(_operand_is_lane_like(el, lane_bound) for el in elements):
        return "compose (%% formatting): slug/lane operand join"
    return None


def _format_call_violation(node: ast.Call, consts: dict[str, str], lane_bound: set[str]) -> str | None:
    """``.format(...)`` calls.

    Rule A: the template literal
    itself carries the token, e.g. ``"kitty/mission-{}".format(slug)`` -- a
    SINGLE argument, so Rule B's ``len(args) >= 2`` guard alone would miss
    it.

    Rule B: see the ``%`` rationale above -- the template is a placeholder
    shape, the arguments carry the slug/lane content.
    """
    assert isinstance(node.func, ast.Attribute)  # narrowed by caller
    template_text = _resolve_str_operand(node.func.value, consts)
    if template_text is None:
        return None
    if _contains_lane_or_mission_token(template_text, _LANE_COMPOSE_TOKENS):
        return "compose (.format): lane/kitty-mission literal"
    args = list(node.args) + [kw.value for kw in node.keywords]
    if len(args) >= 2 and any(_operand_is_lane_like(a, lane_bound) for a in args):
        return "compose (.format): slug/lane operand join"
    return None


def _join_call_violation(node: ast.Call, consts: dict[str, str], lane_bound: set[str]) -> str | None:
    """``sep.join([...])`` calls."""
    assert isinstance(node.func, ast.Attribute)  # narrowed by caller
    sep_text = _resolve_str_operand(node.func.value, consts)
    if sep_text is None or not node.args:
        return None
    elements_node = node.args[0]
    elements: list[ast.expr] | None = None
    if isinstance(elements_node, (ast.List, ast.Tuple)):
        elements = elements_node.elts
    elif isinstance(elements_node, ast.ListComp):
        elements = [elements_node.elt]
    if elements and any(_operand_is_lane_like(el, lane_bound) for el in elements):
        return "compose (.join): slug/lane operand join"
    return None


def _compose_call_violation(node: ast.Call, consts: dict[str, str], lane_bound: set[str]) -> str | None:
    if not isinstance(node.func, ast.Attribute):
        return None
    if node.func.attr == "format":
        return _format_call_violation(node, consts, lane_bound)
    if node.func.attr == "join":
        return _join_call_violation(node, consts, lane_bound)
    return None


def _scan_compose_file(path: Path) -> dict[int, str]:
    source, tree = read_and_parse(path)  # fails closed (#5139); never swallows a parse failure

    docstring_ids = _collect_docstring_ids(tree)
    lane_bound = _collect_lane_bound_names(tree)
    consts = _module_str_constants(tree)
    violations: dict[int, str] = {}

    for node in ast.walk(tree):
        label: str | None = None
        if _is_interpolated_fstring(node) and not _is_docstring_node(node, docstring_ids):
            label = _fstring_boundary_violation(node, lane_bound)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            label = _add_concat_violation(node, consts, lane_bound)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            label = _mod_format_violation(node, lane_bound)
        elif isinstance(node, ast.Call):
            label = _compose_call_violation(node, consts, lane_bound)
        lineno = getattr(node, "lineno", None)
        if label and lineno is not None:
            violations[lineno] = label
    return violations


# ---------------------------------------------------------------------------
# Leg 3 — match: a lane/kitty-mission-shaped string pattern reaching a
# matching sink (regex, str prefix/suffix/split family, Path glob, fnmatch,
# or an ``in`` comparison), outside the seam. Named-constant indirection is
# resolved; prose (no sink reached) is NOT heuristically detected -- it is
# handled by the allow-list only, mirroring the compose leg.
#
# KNOWN LIMITS (non-blocking; recorded rather than silently
# tolerated): ``name.rpartition("-lane-")`` and
# ``name.removesuffix("-" + lane_id)`` are not in the spec's sink list
# (``_MATCH_STR_METHOD_SINKS``) and are not detected. An attribute-form seam
# call (``branch_naming.lane_branch_name(..., mission_id=x)``) escapes the
# signature leg too -- it only recognizes a bare ``ast.Name`` call target via
# import-alias tracking, not a qualified ``module.func(...)`` form. Low risk:
# such a call raises ``TypeError`` at runtime (the seam takes no
# ``mission_id`` parameter at all), so it cannot silently misname anything.
# ---------------------------------------------------------------------------

_MATCH_STR_METHOD_SINKS: frozenset[str] = frozenset({"startswith", "endswith", "removeprefix", "split", "rsplit", "partition", "glob", "rglob"})
# All of `re.*`'s pattern-taking entry points (leg 3 covers "re.*", not
# just the match/search family) -- `sub`/`subn`/`split`/`findall`/`finditer`
# are included because each takes the pattern as
# its first positional argument, same as `match`/`search`/`fullmatch`/`compile`.
_RE_MODULE_SINKS: frozenset[str] = frozenset({"match", "search", "fullmatch", "compile", "sub", "subn", "split", "findall", "finditer"})


def _match_pattern_text(node: ast.expr, consts: dict[str, str]) -> str | None:
    """Resolve a match-sink's pattern argument to its literal text, if any."""
    if _is_interpolated_fstring(node):
        return _fstring_literal_text(node)
    return _resolve_str_operand(node, consts)


def _scan_match_call(node: ast.Call, consts: dict[str, str]) -> str | None:
    """Return a violation label if *node* is a match-sink call over a
    lane/kitty-mission-shaped pattern, else ``None``."""
    func = node.func
    pattern_arg: ast.expr | None = None
    label: str | None = None

    if isinstance(func, ast.Attribute) and func.attr in _MATCH_STR_METHOD_SINKS and node.args:
        pattern_arg = node.args[0]
        label = f"match (.{func.attr})"
    elif isinstance(func, ast.Attribute) and func.attr in _RE_MODULE_SINKS and isinstance(func.value, ast.Name) and func.value.id == "re" and node.args:
        pattern_arg = node.args[0]
        label = f"match (re.{func.attr})"
    elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "fnmatch" and node.args:
        idx = 1 if func.attr == "fnmatch" else 0
        if len(node.args) > idx:
            pattern_arg = node.args[idx]
            label = f"match (fnmatch.{func.attr})"

    if pattern_arg is None or label is None:
        return None
    text = _match_pattern_text(pattern_arg, consts)
    if text is not None and _contains_lane_or_mission_token(text, _LANE_MATCH_TOKENS):
        return f"{label}: lane/kitty-mission pattern"
    return None


def _scan_match_compare(node: ast.Compare, consts: dict[str, str]) -> str | None:
    """Return a violation label for an ``in``/``not in`` comparison whose
    left operand is a lane/kitty-mission-shaped pattern."""
    if not any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
        return None
    text = _match_pattern_text(node.left, consts)
    if text is not None and _contains_lane_or_mission_token(text, _LANE_MATCH_TOKENS):
        return "match (in comparison): lane/kitty-mission pattern"
    return None


def _scan_match_file(path: Path) -> dict[int, str]:
    source, tree = read_and_parse(path)  # fails closed (#5139); never swallows a parse failure
    consts = _module_str_constants(tree)
    violations: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            label = _scan_match_call(node, consts)
            if label:
                violations[node.lineno] = label
        elif isinstance(node, ast.Compare):
            label = _scan_match_compare(node, consts)
            if label:
                violations[node.lineno] = label
    return violations


# ---------------------------------------------------------------------------
# Leg 4 — def-use: a composed (not merely named) string reaching a git
# worktree/branch mutation or existence-check sink, traced through
# intra-function assignment chains (conservative, no inter-procedural
# tracing -- modelled on test_lane_allocation_single_seam.py).
# ---------------------------------------------------------------------------

_GIT_BRANCH_NONMUTATING_FLAGS: frozenset[str] = frozenset({"--list", "--show-current", "-a", "-r", "--contains", "--merged"})
_DEF_USE_EXISTENCE_CALLS: frozenset[str] = frozenset({"branch_exists", "_branch_exists", "ref_exists"})
# Naming-authority calls: an argument sourced from one of these passes.
_DEF_USE_AUTHORITY_CALLS: frozenset[str] = frozenset(
    {
        "lane_branch_name",
        "worktree_dir_name",
        "worktree_path",
        "predict_lane_worktree",
        "allocate_lane_worktree",
        "mission_branch_name",
        "mission_branch_name_required",
        "coord_branch_name",
        "coord_dir_name",
        "coord_mission_dir_name",
        "coord_reconstruct_branch",
        "resolve_branch_name",
    }
)
_REF_QUALIFIER_RE = re.compile(r"^(refs/heads/|refs/remotes/[^/]+/|\^\{commit\}|\^2|@\{upstream\}|:.*)?$")


def _is_composed_string(node: ast.expr) -> bool:
    """A string built by interpolation/concatenation/format/join -- never a
    bare literal or a bare name/attribute reference.

    Ref-qualifier transparency: an interpolated f-string whose literal
    parts are pure ref-decoration (``refs/heads/``, ``^{commit}``, ...) is
    NOT treated as composed -- the leg traces its interpolated operand
    instead (:func:`_fstring_is_ref_qualifier_only`). Checked here, not just
    at the sink-argument site, so an assign-then-use indirection
    (``ref = f"refs/heads/{branch}"`` then ``[..., ref]``) does not smuggle a
    ref-qualifier f-string into ``local_composed`` under a different name.
    """
    if _is_interpolated_fstring(node):
        return not _fstring_is_ref_qualifier_only(node)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        return True
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"format", "join"}


def _fstring_is_ref_qualifier_only(node: ast.JoinedStr) -> bool:
    """True when every literal segment of the f-string is pure ref-decoration
    (``refs/heads/``, ``^{commit}``, etc.) -- transparent to the def-use leg,
    which instead traces the interpolated operand."""
    return all(not (isinstance(value, ast.Constant) and isinstance(value.value, str) and not _REF_QUALIFIER_RE.match(value.value)) for value in node.values)


def _traces_to_authority_or_param(node: ast.expr, local_composed: set[str], func: ast.AST) -> bool:
    """True when *node* traces (by name, no inter-procedural tracing) to a
    function parameter/attribute/subscript, or a naming-authority call --
    i.e. NOT a locally-composed string."""
    if isinstance(node, ast.Name):
        return node.id not in local_composed
    if isinstance(node, (ast.Attribute, ast.Subscript)):
        return True
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _DEF_USE_AUTHORITY_CALLS


def _collect_locally_composed_names(func: ast.AST) -> set[str]:
    """Names bound to a composed (interpolated/concatenated/formatted) string
    somewhere in *func* -- the def-use leg's assignment-chain tracing."""
    composed: set[str] = set()
    for node in ast.walk(func):
        value: ast.expr | None = None
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            value, targets = node.value, list(node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            value, targets = node.value, [node.target]
        if value is None:
            continue
        if not _is_composed_string(value):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                composed.add(target.id)
    return composed


def _offender_operand(node: ast.expr, local_composed: set[str]) -> bool:
    """True when *node* is (or traces to) a composed string offender."""
    if isinstance(node, ast.Name) and node.id in local_composed:
        return True
    return _is_composed_string(node)


def _is_git_worktree_add_argv(elts: list[ast.expr]) -> bool:
    texts = [ast.literal_eval(e) if isinstance(e, ast.Constant) else None for e in elts]
    return "worktree" in texts and "add" in texts


def _is_git_branch_mutating_argv(elts: list[ast.expr]) -> bool:
    texts = [ast.literal_eval(e) if isinstance(e, ast.Constant) else None for e in elts]
    if "branch" not in texts:
        return False
    return not any(isinstance(t, str) and t in _GIT_BRANCH_NONMUTATING_FLAGS for t in texts)


def _is_rev_parse_argv(elts: list[ast.expr]) -> bool:
    texts = [ast.literal_eval(e) if isinstance(e, ast.Constant) else None for e in elts]
    return "rev-parse" in texts


def _def_use_sink_offender_args(node: ast.AST, local_composed: set[str]) -> list[ast.expr]:
    """Return the sink-arm's offender arguments (composed strings), if any."""
    if isinstance(node, (ast.List, ast.Tuple)):
        elts = list(node.elts)
        if _is_git_worktree_add_argv(elts) or _is_git_branch_mutating_argv(elts) or _is_rev_parse_argv(elts):
            return [e for e in elts if _offender_operand(e, local_composed)]
        return []
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _DEF_USE_EXISTENCE_CALLS:
        return [a for a in node.args if _offender_operand(a, local_composed)]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        # Flatten the WHOLE ``/``-division chain (mirrors idiom 1's
        # ``_flatten_div_operands``): a ``.worktrees`` marker anywhere in the
        # chain, joined with a composed operand anywhere else in the SAME
        # chain, is the def-use leg's path-join sink. A single top-level
        # BinOp only sees its immediate left/right, missing a marker one or
        # more levels further down a left-associative chain.
        operands = _flatten_div_operands(node)
        has_worktrees = any(_is_worktrees_literal(op) or _is_worktrees_name(op) for op in operands)
        if not has_worktrees:
            return []
        return [op for op in operands if _offender_operand(op, local_composed)]
    return []


def _iter_functions(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _scan_def_use_file(path: Path) -> dict[int, str]:
    source, tree = read_and_parse(path)  # fails closed (#5139); never swallows a parse failure
    violations: dict[int, str] = {}
    for func in _iter_functions(tree):
        local_composed = _collect_locally_composed_names(func)
        for node in ast.walk(func):
            offenders = _def_use_sink_offender_args(node, local_composed)
            lineno = getattr(node, "lineno", None)
            if offenders and lineno is not None:
                violations[lineno] = "def-use: composed string reaches a git worktree/branch sink"
    return violations


# ---------------------------------------------------------------------------
# Allow-lists (shrink-only, numerically capped per the caps
# table). A site is registered ONCE, under the leg the caps table names --
# even when another leg's raw scan ALSO flags the same line (recovery.py's
# glob and the ``_coord_mid8`` diagnostic are both compose-leg raw hits too;
# they are exempted via the shared ``_NEW_LEG_ALLOWED`` union below, not
# duplicated across legs).
# ---------------------------------------------------------------------------

# Leg 1 -- signature. Cap 0: every ``mission_id``-carrying call was removed;
# no entry is justified.
# (``_SIGNATURE_ALLOWLIST_FILES`` / ``_SIGNATURE_ALLOWLIST`` declared above,
# in the Leg 1 section.)

# Leg 2 -- compose. Cap 1.
_COMPOSE_ALLOWLIST_FILES: dict[tuple[str, str], str] = {
    # ``candidate = f"lane-{chr(letter)}"`` mints a lane **id** (the next free
    # ``lane-<letter>`` positional slot), not a worktree/branch/dir **name** --
    # the composed value never reaches a filesystem or git sink here; it is
    # returned to the caller, which names the lane worktree/branch through the
    # seam (``worktree_dir_name`` / ``lane_branch_name``) using this id as an
    # INPUT. Benign mint, not a name-guess.
    ("_next_free_lane_id", "candidate ="): "src/specify_cli/lanes/compute.py",
}
_COMPOSE_ALLOWLIST: frozenset[tuple[str, str]] = frozenset(_COMPOSE_ALLOWLIST_FILES)

# Leg 3 -- match. Cap 1 (deviation from the original caps-table cap of
# 5 -- see the mission's Activity Log). 5 spec-excluded sites were named;
# only ONE of them (recovery.py's glob) is a live hit any leg's raw
# AST scan actually produces. The other 4 (stale_check.py, context.py,
# workspace.py, policy.py) are PURE PROSE -- no scanner reaches a bare
# ``console.print("...")`` / exception-message / next-step-example string,
# so they suppress NOTHING (raw match-leg scan = 0 at every site but this
# one). Keeping them in the allow-list would be a latent, unverifiable
# suppressor: the composite key
# ``(qualname, token)`` is not file-qualified and an empty token ``""``
# matches ANY string-only line, so e.g. the ``WorkflowMutationPolicy.
# assert_allowed`` entry would silently exempt an unrelated
# ``f"kitty/mission-{ref}-lane-a"`` compose planted inside that same method
# under a different guise -- a false-negative window
# ``frozen-baseline-shrink-only-ratchet`` forbids. The four unverifiable
# entries were dropped and the cap shrunk accordingly; shrinking
# below a maximum is always allowed. The 4 prose sites' benignity is not
# gate-enforced here (an AST-only leg genuinely cannot reach them --
# prose sinks are handled by the allow-list only, never by
# heuristics) -- they simply need no allow-list entry because nothing
# flags them.
_MATCH_ALLOWLIST_FILES: dict[tuple[str, str], str] = {
    # ── recovery.py: a ``git branch --list`` GLOB pattern, not a name-guess ──
    # Same site/key as the existing idiom-2 carve-out above: the compose leg's
    # raw scan ALSO flags this f-string (kitty/mission- literal + interpolation
    # adjacent), exempted here rather than duplicated in the compose allow-list
    # (the caps table lists it under the match leg).
    ("_list_mission_branches", "pattern ="): "src/specify_cli/lanes/recovery.py",
}
_MATCH_ALLOWLIST: frozenset[tuple[str, str]] = frozenset(_MATCH_ALLOWLIST_FILES)

# Leg 4 -- def-use. Cap 1.
_DEF_USE_ALLOWLIST_FILES: dict[tuple[str, str], str] = {
    # ── surface_resolver.py: _coord_mid8 fail-closed raise payload ──
    # Same site/key as the existing idiom-1 carve-out above: the
    # ``.worktrees``-shaped ``coord_candidate`` Path is composed ONLY to
    # populate the ``StatusReadPathNotFound`` diagnostic ``raise`` payload; no
    # git worktree/branch sink is ever reached (already dispositioned DIAG in
    # ``test_single_mission_surface_resolver.py`` / the surface-resolution and
    # untrusted-path audits).
    (
        "_coord_mid8",
        "coord_candidate = repo_root / / / KITTY_SPECS_DIR / mission_slug ,",
    ): "src/specify_cli/coordination/surface_resolver.py",
}
_DEF_USE_ALLOWLIST: frozenset[tuple[str, str]] = frozenset(_DEF_USE_ALLOWLIST_FILES)


def _qualify(files: dict[tuple[str, str], str]) -> frozenset[tuple[str, str, str]]:
    """Qualify a leg's ``(qualname, token) -> relpath`` allow-list dict into
    ``(relpath, qualname, token)`` triples.

    File-qualified by construction: the raw
    ``(qualname, token)`` composite key alone is not unique repo-wide -- two
    unrelated functions in different files can share both an enclosing
    qualname and a normalized token line (a common name like
    ``_stale_remediation`` or an empty ``""`` token, which matches ANY
    string-only line). Folding the entry's own recorded file path into the
    lookup key closes that cross-file collision without changing how any
    individual leg computes its own composite key.
    """
    return frozenset((relpath, qualname, token) for (qualname, token), relpath in files.items())


# Shared lookup, across ALL FOUR new legs: a site flagged by more than
# one leg's detector is exempted the moment it is registered under ANY one of
# them -- registering it again under a second leg would be a redundant,
# unjustified duplicate entry, not a requirement. File-qualified (see
# `_qualify`): a same-named site in an unregistered file is NOT exempted.
_NEW_LEG_ALLOWED: frozenset[tuple[str, str, str]] = (
    _qualify(_SIGNATURE_ALLOWLIST_FILES) | _qualify(_COMPOSE_ALLOWLIST_FILES) | _qualify(_MATCH_ALLOWLIST_FILES) | _qualify(_DEF_USE_ALLOWLIST_FILES)
)


def _new_leg_offenders(scan_fn: Callable[[Path], dict[int, str]]) -> list[str]:
    """Collect ``file:line: label`` offenders for one leg's scanner, filtered
    through the shared, file-qualified ``_NEW_LEG_ALLOWED`` union."""
    offenders: list[str] = []
    for path in _iter_source_files():
        rel = _rel(path)
        if rel == _SEAM_REL:
            continue
        source = path.read_text(encoding="utf-8")
        for lineno, label in sorted(scan_fn(path).items()):
            qualname, token = composite_key(source, lineno)
            if (rel, qualname, token) in _NEW_LEG_ALLOWED:
                continue
            offenders.append(f"  {rel}:{lineno}: {label}")
    return offenders


def test_seam_signature_carries_no_mission_id() -> None:
    """Leg 1 (signature, FR-002): the seam functions take no
    ``mission_id`` (green by construction) -- neither the LIVE
    signature nor an alias-aware call site may reintroduce it. Cap: 0."""
    bad_sigs = _seam_signatures_carry_no_mission_id()
    assert not bad_sigs, f"seam function signature(s) regained a `mission_id` parameter -- lane names must stay keyed on the creation input alone: {bad_sigs}"
    offenders = _new_leg_offenders(_scan_signature_file)
    if offenders:
        pytest.fail(
            "Call(s) passing `mission_id=` to a lane-naming seam function "
            "found outside the seam -- lane names take no mission_id.\n\n"
            "Offending sites:\n" + "\n".join(sorted(offenders))
        )


def test_no_lane_name_compose_outside_authority() -> None:
    """Leg 2 (compose, FR-009/SC-003): 0 compose sites outside the naming
    authority. Allow-list cap: 1."""
    offenders = _new_leg_offenders(_scan_compose_file)
    if offenders:
        pytest.fail(
            "Hand-rolled lane/kitty-mission name COMPOSE found outside the "
            "canonical naming seam.\n\nOffending sites:\n" + "\n".join(sorted(offenders)) + "\n\n" + _SEAM_GUIDANCE
        )


def test_no_lane_name_match_outside_authority() -> None:
    """Leg 3 (match, FR-009): a lane/kitty-mission-shaped pattern reaching a
    matching sink outside the seam. Allow-list cap: 1 (see the ``_MATCH_ALLOWLIST_FILES``
    comment for why this deviates from the original caps-table cap of 5)."""
    offenders = _new_leg_offenders(_scan_match_file)
    if offenders:
        pytest.fail(
            "Hand-rolled lane/kitty-mission pattern MATCH found outside the "
            "canonical naming seam.\n\nOffending sites:\n" + "\n".join(sorted(offenders)) + "\n\n" + _SEAM_GUIDANCE
        )


def test_no_lane_name_def_use_outside_authority() -> None:
    """Leg 4 (def-use, FR-009): a composed string reaching a git
    worktree/branch mutation or existence-check sink outside the seam.
    Allow-list cap: 1."""
    offenders = _new_leg_offenders(_scan_def_use_file)
    if offenders:
        pytest.fail(
            "A composed (not merely named) string reaches a git "
            "worktree/branch sink outside the canonical naming seam.\n\n"
            "Offending sites:\n" + "\n".join(sorted(offenders)) + "\n\n" + _SEAM_GUIDANCE
        )


# ---------------------------------------------------------------------------
# Staleness guards (re-keyed file-qualified to avoid a cross-file collision):
# every new-leg allow-list entry must suppress at least one LIVE raw
# hit -- from ANY of the four legs' scanners (the shared-union design), but
# ONLY within the SAME file the entry names (`_qualify`'s file qualification).
# No marker-only liveness, and no entry is skipped without a check.
# ---------------------------------------------------------------------------


def _raw_keys_in_file(path: Path) -> set[tuple[str, str]]:
    """Every ``(qualname, token)`` composite key any of the four legs' raw
    scanners produce for *path*, unfiltered by any allow-list."""
    source = path.read_text(encoding="utf-8")
    keys: set[tuple[str, str]] = set()
    for scan_fn in (_scan_signature_file, _scan_compose_file, _scan_match_file, _scan_def_use_file):
        for lineno in scan_fn(path):
            keys.add(composite_key(source, lineno))
    return keys


def _assert_allowlist_entries_are_live(files: dict[tuple[str, str], str], label: str) -> None:
    """Fail-loud staleness guard, file-qualified: every entry must resolve to
    a live raw hit in the SAME file it names -- not merely somewhere in the
    scan roots (that would let a same-qualname collision in an unrelated
    file mask this entry's absence), and not via a text-marker escape hatch
    (a marker only proves the prose still exists, never that the key is
    load-bearing)."""
    stale: list[str] = []
    for key, relpath in files.items():
        path = _REPO_ROOT / relpath
        if not path.exists():
            stale.append(f"{key} -> {relpath} (file does not exist)")
            continue
        if key not in _raw_keys_in_file(path):
            stale.append(f"{key} -> {relpath} (no live raw offender)")
    assert not stale, (
        f"stale {label} allow-list entr{'y' if len(stale) == 1 else 'ies'} -- "
        f"suppresses NO live offender in its own file: {stale}. Remove the "
        "entry -- a stale exemption is a false-negative window."
    )


def test_signature_allowlist_entries_match_live_offenders() -> None:
    _assert_allowlist_entries_are_live(_SIGNATURE_ALLOWLIST_FILES, "signature")


def test_compose_allowlist_entries_match_live_offenders() -> None:
    _assert_allowlist_entries_are_live(_COMPOSE_ALLOWLIST_FILES, "compose")


def test_match_allowlist_entries_match_live_offenders() -> None:
    _assert_allowlist_entries_are_live(_MATCH_ALLOWLIST_FILES, "match")


def test_def_use_allowlist_entries_match_live_offenders() -> None:
    _assert_allowlist_entries_are_live(_DEF_USE_ALLOWLIST_FILES, "def-use")


def test_file_qualified_allowlist_rejects_cross_file_collision(tmp_path: Path) -> None:
    """Non-vacuity control for the file-qualification fix: a
    same-``(qualname, token)`` offender planted in a file
    OTHER than the one the allow-list entry names is NOT exempted -- the
    exact cross-file collision the un-qualified 2-tuple key allowed.
    """
    decoy = _write(
        tmp_path,
        "decoy.py",
        'def _next_free_lane_id(x):\n    candidate = f"lane-{x}"\n    return candidate\n',
    )
    source = decoy.read_text(encoding="utf-8")
    offenders = _scan_compose_file(decoy)
    assert offenders, "the decoy module's own compose offender was not even detected"
    lineno = next(iter(offenders))
    key = composite_key(source, lineno)
    # This key is BYTE-IDENTICAL to the real `_COMPOSE_ALLOWLIST` entry for
    # `lanes/compute.py::_next_free_lane_id` -- proving the 2-tuple form
    # would have wrongly exempted it.
    assert key in _COMPOSE_ALLOWLIST_FILES
    # File-qualified: the decoy's own path is NOT the registered path
    # (`src/specify_cli/lanes/compute.py`), so it must NOT be exempted.
    assert ("decoy.py", *key) not in _NEW_LEG_ALLOWED
    assert str(decoy) not in set(_COMPOSE_ALLOWLIST_FILES.values())


# ---------------------------------------------------------------------------
# Non-vacuous self-test: every leg must go RED on an injected
# evasion form of its own recurrence shape, and stay GREEN on a benign
# module that only calls the naming authority.
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, name: str, source: str) -> Path:
    path = tmp_path / name
    path.write_text(source, encoding="utf-8")
    return path


def test_gate_self_test_flags_every_evasion_form_red(tmp_path: Path) -> None:
    """Each of the fifteen evasion shapes below is red on SOME leg's scanner
    -- a literal, a variable-renamed join, ``.join``, ``%``/``.format`` (both
    the two-operand join form and the single-operand literal-token form), a
    constant-held token, ``+`` concatenation (both the literal-boundary form
    and the bare-``"-"``-separator slug/lane-join form), a regex match (the
    match/search family AND the ``sub``/``findall`` family), a ``Path.glob``,
    a ``mission_id=`` call, and a def-use offender. Proves the legs are
    non-vacuous (they reject real evasions, not just an empty allow-list).
    Review cycle 1 added: ``+`` Rule B, ``%``/``.format`` Rule A, and the
    ``re.sub``/``re.findall`` family."""

    literal = _write(
        tmp_path,
        "literal.py",
        'def f(slug):\n    return f"kitty/mission-{slug}-lane-a"\n',
    )
    assert _scan_compose_file(literal), "literal f-string compose was not flagged"

    renamed = _write(
        tmp_path,
        "renamed.py",
        "def f(s):\n    lid = lane_dir_name(s)\n    return f'{s}-{lid}'\n",
    )
    assert _scan_compose_file(renamed), "variable-renamed slug/lane join was not flagged"

    joined = _write(
        tmp_path,
        "joined.py",
        'def f(slug, lane_id):\n    return "-".join([slug, lane_id])\n',
    )
    assert _scan_compose_file(joined), '"-".join([slug, lane_id]) was not flagged'

    percent = _write(
        tmp_path,
        "percent.py",
        'def f(slug, lane_id):\n    return "%s-%s" % (slug, lane_id)\n',
    )
    assert _scan_compose_file(percent), '"%s-%s" %% (slug, lane_id) was not flagged'

    formatted = _write(
        tmp_path,
        "formatted.py",
        'def f(slug, lane_id):\n    return "{}-{}".format(slug, lane_id)\n',
    )
    assert _scan_compose_file(formatted), '"{}-{}".format(slug, lane_id) was not flagged'

    const_held = _write(
        tmp_path,
        "const_held.py",
        '_LANE_TOKEN = "-lane-"\n\n\ndef f(name, slug):\n    return name.startswith(slug + _LANE_TOKEN)\n',
    )
    assert _scan_compose_file(const_held), "constant-held `_LANE_TOKEN` compose was not flagged"

    plus_join = _write(
        tmp_path,
        "plus_join.py",
        "def f(mission_slug, lane_id):\n    return mission_slug + '-' + lane_id\n",
    )
    assert _scan_compose_file(plus_join), '`mission_slug + "-" + lane_id` (+ Rule B) was not flagged'

    percent_single = _write(
        tmp_path,
        "percent_single.py",
        'def f(slug):\n    return "kitty/mission-%s" % slug\n',
    )
    assert _scan_compose_file(percent_single), '`"kitty/mission-%%s" %% slug` (single-operand %% Rule A) was not flagged'

    format_single = _write(
        tmp_path,
        "format_single.py",
        'def f(slug):\n    return "kitty/mission-{}".format(slug)\n',
    )
    assert _scan_compose_file(format_single), '`"kitty/mission-{}".format(slug)` (single-arg .format Rule A) was not flagged'

    regex_match = _write(
        tmp_path,
        "regex_match.py",
        'import re\n\n\ndef f(b):\n    return re.match(r"^kitty/mission-.+-lane-[a-z]$", b)\n',
    )
    assert _scan_match_file(regex_match), "re.match on a lane/kitty-mission pattern was not flagged"

    regex_sub = _write(
        tmp_path,
        "regex_sub.py",
        'import re\n\n\ndef f(name):\n    return re.sub(r"-lane-[a-z]+$", "", name)\n',
    )
    assert _scan_match_file(regex_sub), "re.sub on a lane pattern was not flagged"

    regex_findall = _write(
        tmp_path,
        "regex_findall.py",
        'import re\n\n\ndef f(t):\n    return re.findall(r"kitty/mission-[\\\\w-]+", t)\n',
    )
    assert _scan_match_file(regex_findall), "re.findall on a kitty/mission pattern was not flagged"

    globbed = _write(
        tmp_path,
        "globbed.py",
        'from pathlib import Path\n\n\ndef f(slug):\n    return Path(".worktrees").glob(f"{slug}-lane-*")\n',
    )
    assert _scan_match_file(globbed), "Path.glob on a lane pattern was not flagged"

    sig_call = _write(
        tmp_path,
        "sig_call.py",
        'from specify_cli.lanes.branch_naming import lane_branch_name\n\n\ndef f(slug, mid):\n    return lane_branch_name(slug, "lane-a", mission_id=mid)\n',
    )
    assert _scan_signature_file(sig_call), "a `mission_id=` call to the seam was not flagged"

    def_use = _write(
        tmp_path,
        "def_use.py",
        'def f(repo_root, slug):\n    import subprocess\n    subprocess.run(["git", "worktree", "add", f"{repo_root}/.worktrees/{slug}-lane-a"])\n',
    )
    assert _scan_def_use_file(def_use), "a composed path fed to `git worktree add` was not flagged"


def test_gate_self_test_ref_qualifier_negative_is_green(tmp_path: Path) -> None:
    """A ``rev-parse`` argv over a plain ``refs/heads/<param>`` ref is GREEN --
    the def-use leg's ref-qualifier transparency traces the interpolated
    operand (a bare parameter) rather than flagging the wrapping f-string."""
    negative = _write(
        tmp_path,
        "ref_qualifier_negative.py",
        'def f(repo_root, branch):\n    import subprocess\n    subprocess.run(["git", "rev-parse", f"refs/heads/{branch}"])\n',
    )
    assert not _scan_def_use_file(negative), "a bare `refs/heads/{param}` rev-parse must stay green"


def test_gate_self_test_benign_authority_only_module_is_green(tmp_path: Path) -> None:
    """A module that composes/matches worktree names ONLY through the naming
    authority is green on all four legs -- the legs do not false-positive on
    the seam's own public API surface."""
    benign = _write(
        tmp_path,
        "benign.py",
        "from specify_cli.lanes.branch_naming import (\n"
        "    lane_branch_name,\n"
        "    lane_id_for_worktree_dir,\n"
        "    parse_lane_worktree_dir,\n"
        "    worktree_dir_name,\n"
        "    worktree_path,\n"
        ")\n"
        "from specify_cli.lanes.worktree_allocator import predict_lane_worktree\n"
        "\n\n"
        "def f(repo_root, slug, lane_id):\n"
        "    branch = lane_branch_name(slug, lane_id)\n"
        "    path, branch2 = predict_lane_worktree(repo_root, slug, lane_id)\n"
        "    dir_name = worktree_dir_name(slug, lane_id=lane_id)\n"
        "    full = worktree_path(repo_root, slug, lane_id=lane_id)\n"
        "    parsed = parse_lane_worktree_dir(dir_name)\n"
        "    confirmed = lane_id_for_worktree_dir(dir_name, slug)\n"
        "    return branch, branch2, path, full, parsed, confirmed\n",
    )
    assert not _scan_signature_file(benign)
    assert not _scan_compose_file(benign)
    assert not _scan_match_file(benign)
    assert not _scan_def_use_file(benign)
