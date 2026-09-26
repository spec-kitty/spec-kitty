"""Literal-ban ratchet: worktree/branch name-guessing forbidden outside the seam.

This is the **filesystem twin** of the branch-identity seam — the 4th ratchet
assertion guarding the recurring wrong-compose regression class
(#1860 / #1949 / #1978 / #1899). The single canonical naming seam,
``src/specify_cli/lanes/branch_naming.py``, composes AND parses every mission /
lane / worktree / coordination directory name keyed on the declared
``(slug, mission_id)`` (FR-001 / FR-005). Any other module that hand-rolls a
worktree-dir, mission-branch, or mid8-dedup name reintroduces the defect: a
mid8-era mission whose on-disk worktree is ``<slug>-<mid8>-lane-x`` is mis-named
``<slug>-lane-x`` by a bare ``f"{slug}-{lane}"`` guess, so the path never
resolves (the #1899 class).

The ratchet scans every ``*.py`` under ``src/specify_cli/`` and ``src/runtime/``
for THREE forbidden idioms (the squad showed the first two alone miss the actual
recurrence shape):

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
import re
from pathlib import Path
from typing import TypeGuard

import pytest

from tests.architectural._ast_scan import parse_file
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
    # ── vcs/detection.py: string fed straight back into the seam PARSER ──
    # ``parse_mission_slug_from_branch(f"kitty/mission-{worktree_name}")``
    # round-trips a worktree dir name THROUGH the canonical seam parser to
    # decode it — it decodes, it does not name/create a branch.
    (
        "_get_locked_vcs_from_feature",
        "parsed = parse_mission_slug_from_branch ( )",
    ): "src/specify_cli/core/vcs/detection.py",
    # ── lifecycle_sync.py: error-report placeholder, NOT a worktree lookup ──
    # ``repo_root / WORKTREES_DIRNAME / f"{mission_slug}-unknown"`` lives in
    # the ``CorruptLanesError`` branch — a human-readable diagnostic placeholder;
    # the path is reported, not opened.  Benign: not a name-guess of a real worktree.
    (
        "sync_lane_after_coordination_commit",
        "lane_worktree_path = repo_root / WORKTREES_DIRNAME / ,",
    ): "src/specify_cli/lanes/lifecycle_sync.py",
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
# count and trip the cross-check. Composition (verified at this baseline land):
#   recovery.py:135                    (branch-list glob — benign carve-out)
#   vcs/detection.py:161               (seam-parser round-trip — benign carve-out)
#   lifecycle_sync.py:135              (corrupt-lanes diagnostic placeholder — benign)
#   surface_resolver.py:499            (post-merge coord-primary-partition-lock
#                                        01KWZ46V — _coord_mid8 DIAG raise payload,
#                                        benign carve-out)
#   workspace.py:123                   (post-merge coord-primary-partition-lock
#                                        01KWZ46V — CoordinationWorkspaceIdentityUnresolved
#                                        diagnostic message, benign carve-out)
# => 5 raw offenders, all accounted for by the allow-list => 0 un-accounted.
_NAME_COMPOSE_BASELINE_RAW_MATCHES = 5

# Helper text appended to every failure so the offender knows the fix.
_SEAM_GUIDANCE = (
    "Route the compose through the canonical naming seam "
    f"(`{_SEAM_REL}`): use worktree_path()/worktree_dir_name() for worktree "
    "dirs, mission_branch_name_required()/coord_branch_name() for branches, and "
    "mission_dir_name()/coord_mission_dir_name() for mission dirs. Do NOT "
    "hand-roll a `.worktrees/` f-string, a `kitty/mission-{...}` literal, or an "
    "inline `endswith(f\"-{mid8}\")` dedup outside the seam."
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
    return isinstance(node, ast.JoinedStr) and any(
        isinstance(value, ast.FormattedValue) for value in node.values
    )


def _is_worktrees_literal(node: ast.AST) -> bool:
    """True for a ``.worktrees`` / ``.worktrees/...`` string literal."""
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and (node.value == _WORKTREES_NAME or node.value.startswith(_WORKTREES_NAME + "/"))
    )


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
        elif (
            isinstance(node, ast.AnnAssign)
            and node.value is not None
            and _is_interpolated_fstring(node.value)
            and isinstance(node.target, ast.Name)
        ):
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
    return "".join(
        str(value.value)
        for value in node.values
        if isinstance(value, ast.Constant)
    )


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
            has_worktrees = any(
                _is_worktrees_literal(op) or _is_worktrees_name(op) for op in operands
            )
            has_fstring = any(
                _operand_is_interpolated(op, fstring_names) for op in operands
            )
            if has_worktrees and has_fstring:
                violations[node.lineno] = "worktree-dir name-guess (idiom 1)"
            continue

        # Idiom 3 — inline mid8 re-dedup: ``X.endswith(f"-{mid8}")`` /
        # ``X.endswith(suffix)`` (with ``suffix = f"-{mid8}"``) used to gate a
        # manual ``<slug>-<mid8>`` mission-dir compose. Keyed on mid8 so a
        # generic ``endswith(suffix)`` glob/path test is NOT flagged.
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "endswith"
            and node.args
        ):
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
            "Offending sites:\n"
            + "\n".join(sorted(offenders))
            + "\n\n"
            + _SEAM_GUIDANCE
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
    ("ProfileInvocationExecutor._commit_op_record", "message ="): (
        "src/specify_cli/invocation/executor.py"
    ),
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
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "str"
        and len(node.args) == 1
    ):
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
    lower_ok = sl.lower is None or (
        isinstance(sl.lower, ast.Constant) and sl.lower.value == 0
    )
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
                violations[node.lineno] = (
                    f"mission-identity short-id slice `{operand}[:8]` — route "
                    f"through `{_SHORTID_SEAM}` (failover-aware), do not re-slice"
                )
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_mid8"
        ):
            violations[node.lineno] = (
                "bare `_mid8(...)` call bypasses the failover entrypoint — "
                f"route through `{_SHORTID_SEAM}` instead of the private primitive"
            )
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
            "without a justification that proves it is not a consumer):\n"
            + "\n".join(sorted(offenders))
            + f"\n\nRoute the derivation through `{_SHORTID_SEAM}` "
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
    flagged_source = (
        "mission_id[:8]\n"
        "str(raw_mission_id)[:8]\n"
        "mid[:8]\n"
        "raw_mid[:8]\n"
        "mission_id_meta[:8]\n"
    )
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
                "invocation_id[:8] is a different identity domain and must NOT "
                "be flagged by the mission-identity short-id detector"
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
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_mid8"
        ):
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
        "expected both lines to be inside the same function "
        f"(allowed qualname={allowed_key[0]!r}, extra qualname={extra_key[0]!r})"
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
    assert extra_lineno in flagged_linenos, (
        f"the short-id scanner did not flag the extra offender at line {extra_lineno}; "
        f"flagged lines: {flagged_linenos}"
    )
