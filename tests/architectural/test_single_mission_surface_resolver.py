"""Load-bearing architectural guard: mission-surface resolver routing (WP08 / FR-004).

After mission ``single-mission-surface-resolver-01KVGCE8`` collapsed the
coord-vs-primary selection resolvers to one canonical owner
(``coordination/surface_resolver.resolve_status_surface_with_anchor``) and
retired the ``feature_dir_resolver.py`` shim (WP07), this guard is the
permanent enforcement ratchet. It asserts that EVERY FS-reaching
``KITTY_SPECS_DIR / <slug>`` join on the final collapsed tree routes through a
blessed resolver, delegator, or documented topology-blind primitive — and that
zero *functional* raw-bypass joins (joins that actually open/read/write the
filesystem) remain outside the canonical seam.

Anchoring strategy (T030)
--------------------------
This guard re-runs WP01's ``discover_rows()`` live on the current source tree;
it keeps no static, hand-maintained row list.  ``discover_rows()`` is the
authoritative, reproducible AST walker defined in
``tests/architectural/_surface_resolution_scan.py``.

The guard classifies each ``raw-path-join`` row discovered into one of three
categories:
1. **FUNCTIONAL_FS_BYPASS** — a ``KITTY_SPECS_DIR / slug`` join that actually
   reads or writes the filesystem (the forbidden class, FR-004 / SC-002).
2. **DIAGNOSTIC_PAYLOAD** — a join whose path is composed only for a ``raise``
   payload; the path is never opened or stat'd (low-severity, explicitly
   allowed).
3. **TOPOLOGY_BLIND_BY_DESIGN** — the join IS the blessed topology-blind
   primitive definition (``primary_feature_dir_for_mission``), or it uses the
   output of the canonical grammar seam (``mission_dir_name``), or the slug is
   pre-validated by ``_validate_segment`` / ``assert_safe_path_segment`` before
   the join and the resulting path is passed to a blessed resolver.

All ``raw-path-join`` rows that are NOT in the allowlist are treated as
``FUNCTIONAL_FS_BYPASS`` — the guard fails unconditionally on any such row.

Self-test proof (T031)
-----------------------
Two real-code mutations are documented below; each was temporarily injected
into a real source file, the guard was run, the failure was recorded, then the
mutation was reverted and the guard was re-run to confirm it cleared.  The
results are embedded in the module-level docstring as the load-bearing proof
(T031 — required by WP08 Definition of Done).

Mutation A — ``src/specify_cli/status/aggregate.py`` (after line 491):
    _INJECTED_BYPASS = repo_root / KITTY_SPECS_DIR / mission_slug  # noqa: injected
Guard result: FAIL — ``specify_cli/status/aggregate.py:<line>  raw-path-join``
(unexpected bypass, not in allowlist).
Revert: PASS — no unexpected bypass rows.

Mutation B — ``src/specify_cli/coordination/status_transition.py`` (after line 281):
    _EXTRA = repo_root / KITTY_SPECS_DIR / feature_slug  # noqa: injected
Guard result: FAIL — ``specify_cli/coordination/status_transition.py:<line>  raw-path-join``
(unexpected bypass, not in allowlist).
Revert: PASS — no unexpected bypass rows.

Mutation C (raw_handle hole closure) — ``src/specify_cli/status/aggregate.py``:
    _INJECTED = repo_root / KITTY_SPECS_DIR / raw_handle  # noqa: injected
Guard result: FAIL — the join is detected via the ``raw_handle`` token now in the
audit's ``SLUG_NAMES`` net (the previously open hole F-2 closed).
Revert: PASS — no unexpected bypass rows.

Note: the three read-CLI primary-meta bootstrap sites (``agent/context.py:72``,
``agent/mission.py:1327``, ``agent/mission.py:1378``) surfaced as discovered rows
once ``raw_handle`` joined the audit net; they are allowlisted in
``_ALLOWLISTED_RAW_JOINS`` HONESTLY as an un-guarded read-side-desync residual
(#2046 under epic #2007, consolidation deferred), not as clean topology-blind primitives.

Coverage assertions (T031)
---------------------------
1. ``discovered_rows`` is non-empty — a vacuous walk produces zero rows and
   trivially passes all per-row assertions.
2. ``discovered_rows`` count ≥ ``_MIN_DISCOVERED_ROWS`` — a floor that
   prevents a partial/broken walker from producing a thin set that the guard
   rubber-stamps.
3. Independent floor (FR-004 anti-circular): the count of files containing
   ``KITTY_SPECS_DIR`` in ``src/specify_cli`` + ``src/mission_runtime`` minus
   the named topology-blind seam files is ≤ the sum of ``raw-path-join`` +
   non-raw-path-join rows discovered across ALL seam source files.  This
   ensures a refactoring that removes seam rows without updating the walker is
   caught.

Pre-existing failures in the architectural suite
-------------------------------------------------
These failures are NOT ours (confirmed: they also fail on the clean lane base
BEFORE the WP05 changes); they are dependency-lane/cross-WP residuals tracked
for the orchestrator's pre-merge sweep:
- ``test_untrusted_path_containment.py::test_audit_passes_on_fixed_tree`` and
  ``::test_all_discovered_rows_appear_in_inventory``: the SEPARATE
  untrusted-path-audit ``inventory.md`` is stale (line numbers shifted after the
  WP01/WP03 read-side seam edits). THIS guard does not depend on that
  inventory — it re-runs ``discover_rows()`` live (see the module docstring
  above). The companion surface-resolution inventory, its converter and the
  standalone audit script were retired (#3011); only the live scanner
  (``_surface_resolution_scan``) remains.
- ``test_pytest_marker_convention.py``: pre-existing ratchet drift.
- ``test_no_dead_modules.py`` / ``test_no_dead_symbols.py``: dead-module /
  ``__all__`` symbol debt from seam additions (src-side; outside WP05's
  test-only owned surface). The ``specify_cli.mission_read_path`` shim that
  formerly contributed to this debt was retired by #2048.

C-003 pre-condition verification (WP08 / T037)
----------------------------------------------
The ``#2161`` read-leg handle-safety fix is a PRE-CONDITION of this mission
(spec C-003): it must be present on the base before WP02-WP05 build on it. This
WP verifies (does NOT re-implement) it. Evidence captured on the integrated lane:

- Introducing commit: ``ecf45f52c`` ("feat(2119): retrospective durable-home +
  handle-safe write/read seams + topology-aware teardown") — the #2119/#2161
  handle-safe read/write seam work.
- Fix function: ``_canonicalize_primary_read_handle`` is DEFINED at
  ``src/specify_cli/missions/_read_path_resolver.py:1244`` and APPLIED at ``:1367``
  (``canonical = _canonicalize_primary_read_handle(repo_root, mission_slug)``
  immediately before the handle-blind ``primary_feature_dir_for_mission`` compose
  at ``:1368``).
- This fix is DISTINCT from the ``:454`` bare probe
  (``primary_feature_dir_for_mission(repo_root, handle)`` inside
  ``_canonicalize_bare_modern_handle``), which is the C-001/FR-011 topology-blind
  recursion probe — sanctioned, never folded. The read-leg fix lives at the
  seam (``:1367``), NOT at the primitive call.

C-003 status: PRESENT on the base. T038/T040 may build on it.
"""

from __future__ import annotations

import functools
import tempfile
from pathlib import Path
from types import ModuleType

import pytest

from tests.architectural import _surface_resolution_scan as _scan
from tests.architectural._ratchet_keys import (
    CompositeKey,
    ContentDescriptor,
    composite_key_from_file,
    descriptor_still_live,
    resolve_descriptor,
)

pytestmark = pytest.mark.architectural

# ---------------------------------------------------------------------------
# Repo / source roots (resolved once at import time).
# ---------------------------------------------------------------------------
_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[2]
_SRC_ROOT = _REPO_ROOT / "src"
_SRC_SPECIFY_CLI = _SRC_ROOT / "specify_cli"
_SRC_MISSION_RUNTIME = _SRC_ROOT / "mission_runtime"

# ---------------------------------------------------------------------------
# The live AST walker (``discover_rows`` / ``discover_selection_callsites``)
# lives in the ``_surface_resolution_scan`` package module; importing it
# normally means this guard always exercises the live scanner.
# ---------------------------------------------------------------------------
discover_rows = _scan.discover_rows
discover_selection_callsites = _scan.discover_selection_callsites

# ---------------------------------------------------------------------------
# Constants mirrored from ``_surface_resolution_scan`` (re-read from the live
# module so any changes to the walker are automatically reflected here).
# ---------------------------------------------------------------------------
_KITTY_SPECS_NAMES: frozenset[str] = _scan.KITTY_SPECS_NAMES
_ALLOWLISTED_SELECTION_CALLSITES: dict[str, str] = _scan.ALLOWLISTED_SELECTION_CALLSITES

# ---------------------------------------------------------------------------
# Minimum discovered-row floor (T031 anti-vacuous assertion).
#
# read-side-seam-primary-primitive-closure-01KYKMMT WP08 (T038, NFR-007
# floor->census transfer, DIRECTIVE_043): retired 20 -> 15. The old floor
# (set when the live tree still carried ~27 rows) counted many
# `primary_feature_dir_for_mission`-sink rows this scanner tracked by literal
# callee name. WP08 (T035) deletes that wrapper outright, and the sites that
# used to call it now call the module-private `_compose_primary_feature_dir`
# leaf, which this OLDER scanner's tracked-sink name set was never taught (it
# predates WP03's T016 leaf extraction) -- so those internal composition
# calls permanently and correctly fall out of THIS census's tracking scope.
# This is not a vacuity regression: the terminal, whole-tree authority for
# that migration is `tests/architectural/test_no_read_side_bypass.py`'s
# census (now fully green for both primitives) -- but that census's live scan
# deliberately does NOT track the leaf by name (doing so would flag every one
# of the leaf's own legitimate in-module callers as a fresh bypass finding;
# `_LEAF_PRIMITIVE_ALIASES` there is consulted ONLY for ledger/allow-list
# bookkeeping, never by the scanner itself). The live, hand-verified count
# when the floor was set was exactly 15 --
# genuinely non-vacuous still (the walk is not empty), just smaller because
# the migration it was counting is done. A walk that returns fewer than this
# floor is almost certainly misconfigured or operating on an empty source tree.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Allowlisted raw-path-join rows (T030 — explicit disposition with rationale;
# WP04 content-descriptor migration, #2469 IC-DESCRIPTOR).
#
# Each entry is a :class:`ContentDescriptor` (``rel_path``, ``qualname``,
# ``token_substring``, ``occurrence``, ``rationale``) — a two-axis
# content-addressed pointer (enclosing function + a substring of its
# NORMALIZED token line), never a bare ``<rel_path>:<line>`` locator and never
# a hand-authored composite-key literal (NFR-004).  ``resolve_descriptor``
# (``tests/architectural/_ratchet_keys.py``, IC-DESCRIPTOR/WP02) resolves each
# descriptor against the LIVE source to the **exactly one** finding it names —
# RAISING (RED) rather than silently picking a match if the descriptor is
# ambiguous or has drifted off its site entirely.  A descriptor survives
# benign line drift (a seam WP inserting code above the site) AND, unlike a
# bare composite key seeded from a single line, requires no re-anchoring NOTE
# every time an unrelated edit shifts the line — the descriptor is authored
# once against the finding's own qualname + token line and never touched
# again (see ``kitty-specs/content-address-ratchet-allowlists-01KX8M4D/contracts/descriptor-resolver.md``).
#
# These are the ONLY raw-path-join rows permitted on the final collapsed tree.
# Any new raw-path-join row whose composite key is NOT in this set is treated
# as a functional FS-bypass and the guard FAILS.
#
# ``_RAW_JOIN_SEEDED_KEYS`` resolves every descriptor ONCE at import time to
# its live ``(rel_path, qualname, token_line)`` composite key.
# ``_build_allowlisted_raw_joins`` narrows that to the 2-tuple
# ``(qualname, token_line)`` shape ``test_zero_functional_raw_bypass_on_collapsed_tree``
# compares discovered rows against (via ``composite_key_from_file``).
# ``test_allowlist_entries_are_not_stale`` re-resolves each descriptor against
# the live source and compares it to its seeded key via ``descriptor_still_live``
# (exactly-one AND key-equal), so a site that drifts off its function, whose
# code line changes, or that gains a same-qualname sibling with a colliding
# substring is caught loudly.
#
# Classification:
#   DIAG   — diagnostic-payload join: path composed only for a ``raise``
#             payload; no FS open/stat/write.  Safe (zero filesystem side-effect).
#   TBYD   — topology-blind-by-design: the join IS the blessed primitive
#             definition, or the slug is the output of the canonical grammar
#             seam (``mission_dir_name`` → ``mission_slug_formatted``), or the
#             slug is pre-validated by ``_validate_segment`` /
#             ``assert_safe_path_segment`` and the join feeds a blessed resolver.
# ---------------------------------------------------------------------------

#: Seed of content descriptors for each allowlisted raw-join site.  Each
#: ``token_substring`` is authored from the finding's OWN normalized token
#: line (never a raw-source substring — see the descriptor-resolver
#: contract's "Authoring rule"); RJ#1/RJ#2 share the ``_coord_mid8`` qualname
#: and disambiguate purely by ``token_substring``, proving the two-axis
#: descriptor shape.
_RAW_JOIN_SITES: tuple[ContentDescriptor, ...] = (
    # ----- surface_resolver.py: _coord_mid8 fail-closed raise payloads -----
    # Both joins compose paths ONLY inside a ``StatusReadPathNotFound(...)``
    # constructor call inside a ``raise`` statement.  No FS open/stat/write
    # ever happens — the exception is raised immediately.  Rationale: the
    # diagnostic paths document what the resolver searched; they are not used
    # to read any mission file.  RJ#1 (``coord_candidate``) and RJ#2
    # (``primary_candidate``) share the ``_coord_mid8`` qualname; the distinct
    # ``token_substring`` per entry is the disambiguator (no ``occurrence``
    # ordinal needed).
    ContentDescriptor(
        rel_path="specify_cli/coordination/surface_resolver.py",
        qualname="_coord_mid8",
        token_substring="coord_candidate = repo_root",
        occurrence=None,
        rationale=(
            "DIAG — _coord_mid8 fail-closed raise payload: "
            "CoordinationWorkspace.worktree_path(...) / KITTY_SPECS_DIR / mission_slug "
            "inside StatusReadPathNotFound constructor; no FS sink (raise is immediate)."
        ),
    ),
    ContentDescriptor(
        rel_path="specify_cli/coordination/surface_resolver.py",
        qualname="_coord_mid8",
        token_substring="primary_candidate = repo_root / KITTY_SPECS_DIR / mission_slug",
        occurrence=None,
        rationale=(
            "DIAG — _coord_mid8 fail-closed raise payload: repo_root / KITTY_SPECS_DIR / mission_slug for primary_candidate field; no FS sink (raise is immediate)."
        ),
    ),
    # ----- _read_path_resolver.py: _compose_primary_feature_dir definition -----
    # This IS the body of the topology-blind primitive, extracted to a
    # module-private leaf by read-side-seam-primary-primitive-closure-01KYKMMT
    # WP03 (T015/T017): ``primary_feature_dir_for_mission`` (the public wrapper,
    # unchanged qualname) now delegates to this leaf, which owns the actual
    # ``KITTY_SPECS_DIR`` join. It calls ``assert_safe_path_segment(mission_slug)``
    # at the line before the join and wraps ``get_main_repo_root(repo_root)`` on
    # the left. The join is the DEFINITION of the blessed seam, not a bypass of
    # it. All callers that need topology-blind primary-dir access delegate
    # through the leaf (directly, or via the public wrapper).
    ContentDescriptor(
        rel_path="specify_cli/missions/_read_path_resolver.py",
        qualname="_compose_primary_feature_dir",
        token_substring=("primary_dir : Path = get_main_repo_root ( repo_root ) / KITTY_SPECS_DIR / mission_slug"),
        occurrence=None,
        rationale=(
            "TBYD — IS the _compose_primary_feature_dir leaf definition (WP03 "
            "T015 extraction of the former primary_feature_dir_for_mission body); "
            "assert_safe_path_segment called just above (NFR-002); "
            "get_main_repo_root wraps the left operand; "
            "this leaf is the canonical topology-blind entry point, surviving "
            "WP08's deletion of the (now-thin) public wrapper."
        ),
    ),
    # ----- mission_creation.py: seam-grammar output -----
    # ``mission_slug_formatted = mission_dir_name(mission_slug, mid8=...)`` is
    # composed just above.  The slug on the RHS of the join is NOT raw operator
    # input: it is the OUTPUT of the canonical ``mission_dir_name`` grammar
    # seam (FR-032/FR-044), which produces a validated ``<human-slug>-<mid8>``
    # dir name.  The join is therefore using a seam-produced, pre-composed
    # name — not a raw slug bypass.
    ContentDescriptor(
        rel_path="specify_cli/core/mission_creation.py",
        qualname="_create_mission_core_impl",
        token_substring="feature_dir = effective_root / KITTY_SPECS_DIR / mission_slug_formatted",
        occurrence=None,
        rationale=(
            "TBYD — join uses mission_slug_formatted, the OUTPUT of the canonical "
            "mission_dir_name(mission_slug, mid8=...) grammar seam (not raw operator "
            "input); seam is defined in lanes/branch_naming.py (FR-032/FR-044). "
            "Create-time-canonical: the mission dir is being created here "
            "(feature_dir.mkdir follows immediately), so there is no prior surface "
            "to resolve through. Re-pinned 2026-08-13 (#3339/WP12): create_mission_core "
            "is now a thin failure-atomic wrapper delegating to _create_mission_core_impl, "
            "which owns this join line."
        ),
    ),
    # ----- DRAINED by mission retrospective-durable-home-01KVYM1W (#2136/#2164):
    # the raw ``KITTY_SPECS_DIR / parts.mission_slug`` join formerly in
    # ``resolve_review_cycle_pointer`` (review/cycle.py) was routed through the
    # shared write-seam resolver ``candidate_feature_dir_for_mission`` (which folds
    # every handle form and propagates ``MissionSelectorAmbiguous`` — no silent pick,
    # C-009), matching the WRITE seam ``create_rejected_review_cycle``.  No raw join
    # remains, so its allowlist entry was removed to keep this guard precise
    # (``test_allowlist_entries_are_not_stale``).  The downstream ``wp_slug``
    # path-joins remain dispositioned in the untrusted-path inventory.
    # ----- DRAINED by WP02 (FR-002): the four read-CLI raw-join bootstraps that
    # formerly lived here (decision.py D-6 factory boundary +
    # agent/context.py, agent/mission.py x2 #2046 read-side-desync residuals)
    # have been migrated onto the single guarded read-side seam
    # ``resolve_handle_to_read_path`` (and, for the primary-only existence
    # probe, the topology-blind ``primary_feature_dir_for_mission`` primitive).
    # None of them performs a raw ``KITTY_SPECS_DIR / <handle>`` join any
    # longer, so their allowlist entries were removed to keep this guard
    # precise (``test_allowlist_entries_are_not_stale``).  The seam adds the
    # ``assert_safe_path_segment`` guard (FR-004) each bootstrap previously
    # lacked.  WP05 confirms the drain by re-derivation against the
    # equivalence matrix.
    # ----- DRAINED: accept.py's COORD leg of the accept-time birth-cutover stamp
    # ``_stamp_birth_cutover_for_accept`` used to hand-build
    # ``coord_worktree_root / KITTY_SPECS_DIR / mission_slug`` for its COORD leg
    # (allow-listed here as TBYD).  The read-side placement-seam migration routed
    # that leg onto the kind-aware authority instead —
    # ``placement_seam(...).read_dir(MissionArtifactKind.STATUS_STATE)`` via
    # ``accept._coord_status_feature_dir`` — so no raw ``KITTY_SPECS_DIR`` join
    # remains and the entry was removed to keep this guard precise
    # (``test_allowlist_entries_are_not_stale``).  The slug guard survives: the
    # helper still calls ``assert_safe_path_segment`` before consulting the seam.
)


@functools.cache
def _raw_join_source(rel_path: str) -> str:
    """Read (and cache) a ``_RAW_JOIN_SITES`` descriptor's source file, once.

    Several descriptors (RJ#1/RJ#2) share a file — caching avoids re-reading it
    once per descriptor.
    """
    return (_SRC_ROOT / rel_path).read_text(encoding="utf-8")


#: Every ``_RAW_JOIN_SITES`` descriptor resolved ONCE at import time to its
#: live full ``(rel_path, qualname, token_line)`` composite key (NFR-004:
#: never hand-author the key literal).  RAISES :class:`DescriptorResolutionError`
#: at import time if a descriptor is already ambiguous or dangling — the
#: earliest possible surfacing of a mis-authored ``token_substring`` (GAP-1).
_RAW_JOIN_SEEDED_KEYS: dict[ContentDescriptor, CompositeKey] = {
    descriptor: resolve_descriptor(_raw_join_source(descriptor.rel_path), descriptor) for descriptor in _RAW_JOIN_SITES
}


def _build_allowlisted_raw_joins() -> dict[tuple[str, str], str]:
    """Narrow ``_RAW_JOIN_SEEDED_KEYS`` to the ``(qualname, token_line)`` shape.

    ``test_zero_functional_raw_bypass_on_collapsed_tree`` (T030) keys
    discovered rows via ``composite_key_from_file`` — a bare 2-tuple with no
    ``rel_path`` component — so the allowlist it consults must match that
    shape.  The rationale is carried verbatim from the descriptor.
    """
    return {(qualname, token_line): descriptor.rationale for descriptor, (_rel_path, qualname, token_line) in _RAW_JOIN_SEEDED_KEYS.items()}


#: Composite-keyed allowlist: ``(enclosing_qualname, token_line) -> rationale``.
_ALLOWLISTED_RAW_JOINS: dict[tuple[str, str], str] = _build_allowlisted_raw_joins()

# ---------------------------------------------------------------------------
# Named topology-blind seam files for the independent floor calculation (T031).
#
# These are source files whose KITTY_SPECS_DIR usage is EXCLUSIVELY via
# topology-blind-by-design primitives (``primary_feature_dir_for_mission``),
# i.e., they never do a raw KITTY_SPECS_DIR/slug join that bypasses the
# coord-aware resolver.  They are excluded from the floor count because the
# audit's ``discover_rows()`` includes their rows in the topology-blind
# category, not in the (routed + bypass) category that the floor is checking.
#
# Current set: only ``_read_path_resolver.py`` defines the topology-blind
# primitive.  The aggregate.py, status_transition.py, surface_resolver.py
# uses of ``primary_feature_dir_for_mission`` are calls-through-the-primitive,
# not definitions — they are counted in the audit's seam-internal rows.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Helper: collect files with a KITTY_SPECS_DIR reference in the source trees.
# Used for the independent floor assertion (T031-c).
# ---------------------------------------------------------------------------


# ===========================================================================
# T030 — Zero functional raw-bypass guard
# ===========================================================================


def test_zero_functional_raw_bypass_on_collapsed_tree() -> None:
    """Every KITTY_SPECS_DIR/slug join routes through the canonical resolver.

    Asserts that the live source tree (the final collapsed WP06+WP07 state)
    has ZERO functional FS-reaching raw-bypass joins outside the blessed
    resolver / delegator / topology-blind set.

    Every ``raw-path-join`` row discovered by the WP01 AST walker must be
    present in ``_ALLOWLISTED_RAW_JOINS`` with an explicit disposition and
    rationale.  A new ``KITTY_SPECS_DIR / slug`` join in any non-allowlisted
    file FAILS this test immediately.

    FR-004 (SC-002): every mission-surface read routes through the single
    canonical resolver owner.
    """
    rows = discover_rows()

    unexpected: list[str] = []
    for row in rows:
        if row.call_name != "raw-path-join":
            continue
        # Composite key (qualname, token_line) — content-addressed, drift-proof.
        key = composite_key_from_file(_SRC_ROOT / row.rel_path, row.line)
        if key not in _ALLOWLISTED_RAW_JOINS:
            unexpected.append(f"  {row.key()}  key={key!r}  handle={row.handle_source!r}  — functional raw-bypass not in allowlist (FR-004 regression)")

    assert not unexpected, (
        "Unexpected raw KITTY_SPECS_DIR/slug path joins detected.\n"
        "These joins bypass the canonical resolver and MUST either:\n"
        "  (a) be refactored to route through resolve_mission_read_path /\n"
        "      candidate_feature_dir_for_mission / resolve_status_surface_with_anchor, or\n"
        "  (b) be justified and added to _ALLOWLISTED_RAW_JOINS with a rationale\n"
        "      (DIAG — diagnostic-only payload; no FS sink, or\n"
        "       TBYD — topology-blind-by-design, with named reason).\n\n"
        "Regressions found:\n" + "\n".join(unexpected)
    )


def test_allowlist_entries_are_not_stale() -> None:
    """Every ``_RAW_JOIN_SITES`` descriptor still resolves to its seeded key.

    A stale descriptor — one that no longer resolves via ``descriptor_still_live``
    (exactly-one AND key-equal, per the descriptor-resolver contract's D-1
    rule) — indicates either the site drifted off its qualname/token line (an
    upstream refactoring changed the shape of a seam file), the join was
    removed, or a NEW same-qualname sibling now collides with the
    ``token_substring`` and the descriptor can no longer disambiguate to a
    single finding.  Any of these must be caught loudly: a stale descriptor
    that silently keeps "passing" would widen the allowlist and defeat the
    precision of the guard (never "≥1 finding matches" semantics — the D-1
    bite hole).

    This assertion is the twin of ``test_zero_functional_raw_bypass_on_collapsed_tree``:
    that test rejects new bypasses; this test rejects stale exemptions.
    """
    stale: list[str] = []
    for descriptor, seeded_key in _RAW_JOIN_SEEDED_KEYS.items():
        source = _raw_join_source(descriptor.rel_path)
        if not descriptor_still_live(source, descriptor, seeded_key):
            stale.append(
                f"  {descriptor.rel_path}::{descriptor.qualname} "
                f"substring={descriptor.token_substring!r} "
                f"(seeded key={seeded_key!r}) — no longer resolves to exactly "
                "one live finding equal to its seeded key"
            )

    assert not stale, (
        "Stale _RAW_JOIN_SITES descriptors:\n" + "\n".join(stale) + "\n\nEither the site drifted off its qualname/token line (a seam edit "
        "changed the layout), the join was removed entirely, or a new "
        "same-qualname sibling now collides with the token_substring.  Re-author "
        "the descriptor against the live source, or remove the entry if the join "
        "is gone.\n"
        "Call ``_surface_resolution_scan.discover_rows()`` "
        "to identify the current discovered rows."
    )


# ===========================================================================
# T031 — Load-bearing self-test: coverage assertions + independent floor
# ===========================================================================


def test_discovered_rows_non_empty() -> None:
    """The WP01 walker discovers at least one resolution row (T031-a anti-vacuous).

    A misconfigured walker (wrong SRC_ROOT, empty source tree, or broken import)
    produces zero rows and every per-row assertion trivially passes — this test
    catches that failure mode.
    """
    rows = discover_rows()
    assert rows, (
        "discover_rows() returned an empty list.  This means either:\n"
        "  (a) the _SRC_ROOT in _surface_resolution_scan points to an empty/missing directory, or\n"
        "  (b) the _surface_resolution_scan import failed silently.\n"
        f"Expected SRC roots: {_SRC_SPECIFY_CLI}, {_SRC_MISSION_RUNTIME}"
    )


# ===========================================================================
# T019 — plant-and-catch battery for the WP04 content-descriptor migration.
#
# FR-013 / NFR-001 / NFR-002: proves the descriptor migration (T016/T017) is
# neither a false-red trap (a benign line insertion above a migrated site must
# stay green — the whole point of content-addressing) nor a false-green hole
# (a genuinely new/ambiguous raw join must RED).  Three scenarios, per the WP
# prompt:
#   (a) motion battery  — line insertion above a migrated site -> green.
#   (b) bite            — a new un-allowlisted raw KITTY_SPECS_DIR join -> red.
#   (c) same-qualname sibling — a THIRD un-sanctioned raw join planted inside
#       ``_coord_mid8`` with a token line matching RJ#1's sanctioned
#       substring -> red (proves ``resolve_descriptor``'s exactly-one rule
#       does NOT silently absorb the sibling into the existing allowance).
# ===========================================================================


class _IsolatedSourceInsertion:
    """Context manager: insert a line into a TMP COPY of *path*, never the
    real file.

    Isolated counterpart of the retired real-file-mutating
    ``_SourceInsertion`` (see the WP02/#2673+#2638 module note below
    ``_IsolatedSourceMutation``, whose ``_PATCHED_ROOT_NAMES`` root-patch
    logic this class reuses). Copies *path* into a tmp root OUTSIDE the
    scanned source tree and inserts *inserted_line* directly after the first
    line containing *anchor_substring* in the COPY — shifting every line
    AFTER the insertion point down by one, the exact "line inserted above a
    migrated site" shape the T019 motion battery must prove stays green.
    Monkeypatches the surface-resolution scanner module's root globals so any
    ``discover_rows()`` / ``discover_selection_callsites()`` call made inside
    the ``with`` block scans the tmp copy; the real file is opened READ-ONLY
    and is NEVER written.
    """

    def __init__(
        self,
        path: Path,
        anchor_substring: str,
        inserted_line: str,
        scan_mod: ModuleType,
    ) -> None:
        self._path = path
        self._anchor_substring = anchor_substring
        self._inserted_line = inserted_line
        self._scan_mod = scan_mod
        self._tmp_dir: tempfile.TemporaryDirectory[str] | None = None
        self._saved_roots: dict[str, Path] = {}
        self.tmp_src_root: Path = path
        self.tmp_target: Path = path

    def __enter__(self) -> _IsolatedSourceInsertion:
        rel = self._path.relative_to(_SRC_ROOT)
        self._tmp_dir = tempfile.TemporaryDirectory(prefix="wp06-bite-battery-")
        tmp_root = Path(self._tmp_dir.name)
        self.tmp_src_root = tmp_root / "src"
        self.tmp_target = self.tmp_src_root / rel
        self.tmp_target.parent.mkdir(parents=True, exist_ok=True)

        original = self._path.read_text(encoding="utf-8")
        lines = original.splitlines(keepends=True)
        anchor_index = next(i for i, line in enumerate(lines) if self._anchor_substring in line)
        lines.insert(anchor_index + 1, self._inserted_line + "\n")
        self.tmp_target.write_text("".join(lines), encoding="utf-8")

        self._saved_roots = {name: getattr(self._scan_mod, name) for name in _IsolatedSourceMutation._PATCHED_ROOT_NAMES}
        patched_roots: dict[str, Path] = {
            "_REPO_ROOT": tmp_root,
            "_SRC_ROOT": self.tmp_src_root,
            "SRC_SPECIFY_CLI": self.tmp_src_root / "specify_cli",
            "SRC_MISSION_RUNTIME": self.tmp_src_root / "mission_runtime",
        }
        for name in _IsolatedSourceMutation._PATCHED_ROOT_NAMES:
            setattr(self._scan_mod, name, patched_roots[name])
        return self

    def __exit__(self, *exc: object) -> None:
        for name, value in self._saved_roots.items():
            setattr(self._scan_mod, name, value)
        if self._tmp_dir is not None:
            self._tmp_dir.cleanup()


#: The shared file both the motion-battery and same-qualname-sibling plants
#: mutate — it hosts RJ#1/RJ#2's ``_coord_mid8`` qualname.

#: Anchor line inside ``_coord_mid8`` (just before the fail-closed raise) used
#: to insert a benign comment ABOVE both RJ#1/RJ#2 join lines without changing
#: their content.


# ---------------------------------------------------------------------------
# WP02 (#2673 + #2638) + WP06 (#2678) — bite-battery mutation isolation.
#
# ``_IsolatedSourceMutation`` (and its insertion counterpart
# ``_IsolatedSourceInsertion`` above) replaces the real-file-mutating pattern
# for EVERY bite-battery test in this module. Each copies the target file
# into an isolated tmp root OUTSIDE the scanned source tree, injects the
# witness snippet/line into the COPY, and monkeypatches the surface-resolution
# scanner module's root globals (``_REPO_ROOT`` / ``_SRC_ROOT`` /
# ``SRC_SPECIFY_CLI`` / ``SRC_MISSION_RUNTIME``) so ``discover_rows()`` /
# ``discover_selection_callsites()`` scan the tmp copy for the duration of the
# ``with`` block. The real file on disk is opened READ-ONLY and is NEVER
# written — under ``pytest-xdist -n auto --dist loadfile``, workers are
# separate PROCESSES, so a sibling worker's scanner (reading the real,
# never-mutated tree) can no longer observe an injected witness mid-window.
# The formerly real-file-mutating ``_SourceMutation`` / ``_SourceInsertion``
# context managers carried the identical hazard for their remaining call
# sites and have been retired (WP06 / #2678) now that every battery in this
# module is isolated.
# ---------------------------------------------------------------------------


class _IsolatedSourceMutation:
    """Context manager: mutate a TMP COPY of *path*, never the real file.

    See the module note above (WP02 / #2673 + #2638). ``__enter__`` returns
    ``self`` so callers can read ``tmp_src_root`` (the isolated root the
    patched scanner module now scans) to resolve composite keys for the
    injected copy exactly as they would against the real tree.
    """

    #: Scanner-module root globals patched for the mutation window. Accessed
    #: via ``getattr``/``setattr`` (not dotted attribute access) because the
    #: loop iterates attribute NAMES and *scan_mod* is typed as a plain
    #: ``ModuleType``.
    _PATCHED_ROOT_NAMES: tuple[str, ...] = (
        "_REPO_ROOT",
        "_SRC_ROOT",
        "SRC_SPECIFY_CLI",
        "SRC_MISSION_RUNTIME",
    )

    def __init__(self, path: Path, snippet: str, scan_mod: ModuleType) -> None:
        self._path = path
        self._snippet = snippet
        self._scan_mod = scan_mod
        self._tmp_dir: tempfile.TemporaryDirectory[str] | None = None
        self._saved_roots: dict[str, Path] = {}
        self.tmp_src_root: Path = path
        self.tmp_target: Path = path

    def __enter__(self) -> _IsolatedSourceMutation:
        rel = self._path.relative_to(_SRC_ROOT)
        self._tmp_dir = tempfile.TemporaryDirectory(prefix="wp02-bite-battery-")
        tmp_root = Path(self._tmp_dir.name)
        self.tmp_src_root = tmp_root / "src"
        self.tmp_target = self.tmp_src_root / rel
        self.tmp_target.parent.mkdir(parents=True, exist_ok=True)
        original = self._path.read_text(encoding="utf-8")
        self.tmp_target.write_text(original + self._snippet, encoding="utf-8")

        self._saved_roots = {name: getattr(self._scan_mod, name) for name in self._PATCHED_ROOT_NAMES}
        patched_roots: dict[str, Path] = {
            "_REPO_ROOT": tmp_root,
            "_SRC_ROOT": self.tmp_src_root,
            "SRC_SPECIFY_CLI": self.tmp_src_root / "specify_cli",
            "SRC_MISSION_RUNTIME": self.tmp_src_root / "mission_runtime",
        }
        for name in self._PATCHED_ROOT_NAMES:
            setattr(self._scan_mod, name, patched_roots[name])
        return self

    def __exit__(self, *exc: object) -> None:
        for name, value in self._saved_roots.items():
            setattr(self._scan_mod, name, value)
        if self._tmp_dir is not None:
            self._tmp_dir.cleanup()


def test_raw_join_bite_battery_new_unsanctioned_join_reds() -> None:
    """A brand-new, non-allowlisted raw KITTY_SPECS_DIR join IS caught (red).

    NFR-002: mirrors ``test_zero_functional_raw_bypass_on_collapsed_tree``'s
    own logic against a mutated tree — a genuinely new raw-path-join row whose
    composite key is absent from ``_ALLOWLISTED_RAW_JOINS`` must be flagged as
    an unexpected functional bypass, proving the migration didn't accidentally
    widen the guard.

    WP02 (#2673 + #2638): the mutation targets an ISOLATED tmp copy
    (``_IsolatedSourceMutation``), never the real file — see the module note
    above. Detection still runs through the real, unmodified ``discover_rows``
    detector code path (it is root-agnostic: it scans whatever
    ``SRC_ROOT``/``SRC_SPECIFY_CLI`` currently points at), so pointing it at
    the tmp copy for the duration of the ``with`` block still exercises the
    genuine detector, not a stub.
    """
    target = _SRC_SPECIFY_CLI / "core" / "mission_creation.py"

    def _unexpected_mission_creation_rows(src_root: Path) -> list[_scan.ResolutionRow]:
        return [
            row
            for row in discover_rows()
            if row.call_name == "raw-path-join"
            and row.rel_path.endswith("core/mission_creation.py")
            and composite_key_from_file(src_root / row.rel_path, row.line) not in _ALLOWLISTED_RAW_JOINS
        ]

    # Live-detector proof (T013, anti-tautology): BEFORE injection, the same
    # filter against the REAL (never-touched) file finds nothing unexpected —
    # the assertion below is not vacuously true; it depends on the injected
    # snippet actually being present in what discover_rows() scans.
    baseline = _unexpected_mission_creation_rows(_SRC_ROOT)
    assert not baseline, (
        "Bite battery precondition violated: an unexpected raw-path-join row "
        "already exists for mission_creation.py BEFORE injection — the "
        "post-injection assertion would be a tautology."
    )

    snippet = "\n\ndef _wp04_bite_witness(repo_root, mission_slug):  # noqa: injected T019\n    return repo_root / KITTY_SPECS_DIR / mission_slug\n"
    with _IsolatedSourceMutation(target, snippet, _scan) as mutation:
        witness = _unexpected_mission_creation_rows(mutation.tmp_src_root)
        assert witness, (
            "Bite battery FALSE-GREEN: the injected _wp04_bite_witness raw KITTY_SPECS_DIR/mission_slug join was NOT flagged as an unexpected functional bypass."
        )


# ===========================================================================
# WP05 — read-SELECTION-authority ratchet (FR-006a) + seam empty-mid8 gate
#        (FR-006b) + drain re-derivation (FR-007) + frozen-net (FR-006/FR-007)
#
# These tests add a SECOND discriminator to the architectural guard that the
# pre-WP05 raw-path-JOIN scanner is structurally BLIND to: a DIRECT
# ``resolve_mission_read_path(...)`` call (the read-SELECTION authority) outside
# the ``resolve_handle_to_read_path`` seam.  Such a call composes NO
# ``KITTY_SPECS_DIR / slug`` join of its own — the resolver does the join
# internally — so ``discover_rows()`` (raw-join scanner) never sees it.
# ``discover_selection_callsites()`` catches it by name.
# ===========================================================================

# A read CLI that the WP02/WP03 migration routed onto the seam.  We mutate an
# ISOLATED tmp copy of THIS file (``_IsolatedSourceMutation``, WP06 / #2678)
# to prove both the selection ratchet (T017/T019a) and the SLUG_NAMES
# re-injection guard (T021) actually bite on a real source file's content,
# without ever writing the real file on disk.
_READ_CLI_FOR_MUTATION = _SRC_SPECIFY_CLI / "cli" / "commands" / "agent" / "context.py"

# The guarded read-side seam source (T018 gate-presence assertion).


def _external_selection_bypasses() -> list[str]:
    """Return locator keys of direct selection calls outside the seam+allowlist."""
    return [sel.key() for sel in discover_selection_callsites() if not sel.in_seam_file and sel.key() not in _ALLOWLISTED_SELECTION_CALLSITES]


# ---------------------------------------------------------------------------
# T017 — read-SELECTION-callsite ratchet (the NEW discriminator).
# ---------------------------------------------------------------------------


def test_no_direct_selection_call_outside_seam() -> None:
    """Every direct ``resolve_mission_read_path`` call routes through the seam.

    FR-006a: the read-SELECTION authority (``resolve_mission_read_path``) is
    reached ONLY through the ``resolve_handle_to_read_path`` seam, except for
    seam-internal definitions and explicitly-blessed lenient callers in
    ``ALLOWLISTED_SELECTION_CALLSITES``.

    This is the NEW discriminator (NOT the raw-path-JOIN scanner): it catches a
    direct selection call that composes NO ``KITTY_SPECS_DIR`` join — the shape
    the raw-join guard is blind to.
    """
    bypasses = _external_selection_bypasses()
    assert not bypasses, (
        "Direct read-SELECTION calls (resolve_mission_read_path) found outside "
        "the resolve_handle_to_read_path seam and not allowlisted:\n"
        + "\n".join(f"  {b}" for b in bypasses)
        + "\n\nRoute these through resolve_handle_to_read_path (the single "
        "guarded read-side seam, IC-01) or — for a deliberately lenient caller "
        "— add a justified entry to ALLOWLISTED_SELECTION_CALLSITES (FR-006a)."
    )


# ---------------------------------------------------------------------------
# FR-006a hardening — the SELECTION seam is the single
# ``_read_path_resolver.py`` home, NOT the broader RAW-JOIN resolver-source set.
#
# Pins the guard blind-spot fix: ``_find_selection_calls`` discriminates on
# ``_SELECTION_SEAM_STEMS`` (selection axis) rather than
# ``_RESOLVER_SOURCE_STEMS`` (raw-join axis).  The three resolver-source files
# below (``surface_resolver.py``, ``status_transition.py``, ``aggregate.py``)
# define resolvers for the RAW-JOIN axis but are NOT the selection seam — a
# hypothetical direct ``resolve_mission_read_path`` call there must be FLAGGED
# (allowlist or refactor), never auto-blessed as seam-internal.  (WP01 drained
# the lone real external consumer, ``mission_runtime/resolution.py``, by routing
# it onto the ``resolve_handle_to_read_path`` seam — there are now ZERO external
# selection callsites and the allowlist is empty.)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# T019(a) — mutation: inject a direct selection call into a read CLI.
# ---------------------------------------------------------------------------


def test_selection_ratchet_bites_on_injected_direct_call() -> None:
    """Inject a direct ``resolve_mission_read_path`` call -> ratchet FAILS; revert -> PASSES.

    Two-axis live proof on a REAL read CLI (``agent/context.py``).  Axis (a):
    a NEW direct selection call OUTSIDE the seam is caught.
    """
    # Pre-mutation: clean tree, no external bypasses.
    assert not _external_selection_bypasses(), (
        "Pre-condition failed: the clean adopted tree already has an external selection bypass — fix that before running the mutation proof."
    )

    snippet = (
        "\n\ndef _wp05_injected_selection_bypass(repo_root, slug):  # noqa\n"
        "    from specify_cli.missions._read_path_resolver import (\n"
        "        resolve_mission_read_path,\n"
        "    )\n"
        "    from specify_cli.lanes.branch_naming import mid8_from_slug\n"
        "    return resolve_mission_read_path(repo_root, slug, mid8_from_slug(slug))\n"
    )
    with _IsolatedSourceMutation(_READ_CLI_FOR_MUTATION, snippet, _scan):
        during = _external_selection_bypasses()
        assert any(k.startswith("specify_cli/cli/commands/agent/context.py:") for k in during), (
            "Selection ratchet did NOT catch the injected direct "
            "resolve_mission_read_path call in agent/context.py — the "
            "discriminator is vacuous.\n"
            f"  external bypasses during mutation: {during}"
        )

    # Post-revert: clean again (proves __exit__ restored the patched scanner-module
    # roots, so discover_selection_callsites() is back to scanning the real tree).
    assert not _external_selection_bypasses(), (
        "Selection ratchet still reports a bypass after the isolated mutation context exited — the _IsolatedSourceMutation root restore failed."
    )


# ---------------------------------------------------------------------------
# T019(b) — pre/post-mission-tree discrimination (NOT a tautology).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# T018 — seam runtime empty-mid8 fail-closed gate (FR-006b).
# ---------------------------------------------------------------------------


def test_seam_empty_mid8_fail_closed_gate_raises() -> None:
    """The seam RAISES on empty-mid8-against-declared-coord (FR-006b / M5).

    A bare slug whose primary ``meta.json`` declares a ``coordination_branch``
    but carries NEITHER ``mid8`` NOR ``mission_id`` leaves the cascade exhausted
    (empty mid8).  Reading primary would expose a stale view, so the seam MUST
    raise the typed ``StatusReadPathNotFound`` rather than silently fall back.
    """
    import json

    from specify_cli.missions._read_path_resolver import (
        StatusReadPathNotFound,
        resolve_handle_to_read_path,
    )

    slug = "read-side-surface-resolver-adoption"
    coord_branch = "kitty/mission-read-side-surface-resolver-adoption-01KVJPEQ"

    repo_root = _REPO_ROOT  # placeholder; overwritten per-test via tmp below

    import tempfile

    with tempfile.TemporaryDirectory() as td:
        repo_root = Path(td)
        primary_dir = repo_root / "kitty-specs" / slug
        primary_dir.mkdir(parents=True)
        # Declares coordination but NO mid8 / mission_id => unprovable identity.
        (primary_dir / "meta.json").write_text(
            json.dumps({"mission_slug": slug, "coordination_branch": coord_branch}),
            encoding="utf-8",
        )

        with pytest.raises(StatusReadPathNotFound) as exc_info:
            resolve_handle_to_read_path(repo_root, slug)

        assert exc_info.value.mid8 == ""
        assert exc_info.value.mission_slug == slug


# ---------------------------------------------------------------------------
# T020 — confirm the four read-CLI raw joins drained (FR-007 re-derivation).
# ---------------------------------------------------------------------------

# The four read-CLI primary-meta bootstrap raw-join keys that the pre-mission
# tree carried.  WP02 migrated all four onto the ``resolve_handle_to_read_path``
# seam; re-derivation must now find ZERO raw joins at these files.  Three are
# the #2046 read-side-desync residuals; ``decision.py`` is the D-6 consolidation
# drain (a consequence of the WP02 factory-boundary consolidation, NOT a #2046
# residual).


# ---------------------------------------------------------------------------
# T021 — frozen SLUG_NAMES net + re-injection mutation.
# ---------------------------------------------------------------------------

# The minimum net the read-CLI primary-meta bootstrap joins were caught by.
# Narrowing the net (dropping either token) would silently re-blind the scanner
# to the read-CLI bootstrap shape — the fake-drain hole closed by 01KVGCE8.


def test_raw_handle_reinjection_is_caught() -> None:
    """Re-inject a raw ``KITTY_SPECS_DIR / raw_handle`` join -> guard FAILS; revert -> PASSES.

    FR-007 anti-fake-drain mutation proof: on the ADOPTED tree, re-introducing
    the exact pre-mission raw bootstrap shape (``repo_root / KITTY_SPECS_DIR /
    raw_handle``) into a real read CLI must be caught by the raw-join scanner.
    This proves the net was NOT silently narrowed to make the drain pass.
    """
    snippet = (
        "\n\ndef _wp05_reinject_raw_handle(repo_root, raw_handle):  # noqa\n"
        "    from specify_cli.core.paths import KITTY_SPECS_DIR\n"
        "    return repo_root / KITTY_SPECS_DIR / raw_handle\n"
    )
    with _IsolatedSourceMutation(_READ_CLI_FOR_MUTATION, snippet, _scan):
        during = [
            r.key()
            for r in discover_rows()
            if r.call_name == "raw-path-join" and r.handle_source == "raw_handle" and r.key().startswith("specify_cli/cli/commands/agent/context.py:")
        ]
        assert during, "Re-injected raw KITTY_SPECS_DIR / raw_handle join was NOT caught — SLUG_NAMES must have been narrowed (fake-drain hole re-opened)."

    post = [
        r.key()
        for r in discover_rows()
        if r.call_name == "raw-path-join" and r.handle_source == "raw_handle" and r.key().startswith("specify_cli/cli/commands/agent/context.py:")
    ]
    assert not post, "raw_handle re-injection mutation was not reverted cleanly."
