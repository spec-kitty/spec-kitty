"""Mission-level close-out regression guard — coord-read-residuals (01KW2M8V).

WP05 / T027. Requirements: FR-006, FR-007, FR-010, SC-004, NFR-001, NFR-005.

WP01 shipped the FR-007 ``callshape_violations`` arm. Its detector now lives in
the non-collected ``_gate_read_callshape.py`` support module; synthetic self-tests
were retired during suite sanitation. This module supplies the non-vacuous proof
by wiring the arm LIVE as a
production scan over the REAL in-scope ``src/`` tree — the same
``_iter_functions_under`` machinery the dir-read ratchet uses.

Three guards:

1. **Live FR-007 arm (the crux).** Run ``callshape_violations`` over every
   function in the in-scope module families, for BOTH shapes, and assert ZERO
   un-pinned violations:

   * IDENTITY (``resolve_mission_identity`` / ``get_mission_type``) →
     ``cli/commands/`` + ``agent_utils/status.py``.
   * LANES.JSON (``read_lanes_json`` / ``require_lanes_json``) → ``merge/`` +
     ``lanes/`` + ``core/worktree_topology.py``.

   WP01 (identity) + WP02/WP03 (merge / lanes / core) routed every in-scope
   site onto a PRIMARY fold, so the live scan is clean. If ANY in-scope site
   flags, a routing was missed — this test (correctly) goes RED. An anti-vacuity
   floor proves the scan actually SAW the in-scope read call sites (it is not
   green merely because it matched nothing).

2. **Floor honesty — RETIRED (read-side-seam-primary-primitive-closure-01KYKMMT
   WP01, T003/T004, FR-007).** This guard used to pin ``ROUTED_CANONICALIZER_FLOOR``
   against the recorded census. Both use-count floors it depended on
   (``CANONICALIZER_FLOOR`` / ``ROUTED_CANONICALIZER_FLOOR`` /
   ``ROUTED_CANONICALIZER_FLOOR_MARGIN``, in
   ``test_resolution_authority_gates.py``, since deleted) are retired there — the guarantee
   transfers to the read-side bypass census (``test_no_read_side_bypass.py``,
   WP02) per the DIRECTIVE_043 adjudication recorded at that constant's
   retirement comment. Retiring the constants without retiring THIS module's
   import of them would raise ``ImportError`` at collection (~20 tests) —
   DIRECTIVE_034's collection-error hazard — so
   ``test_routed_canonicalizer_floor_matches_recorded_census`` (and the import)
   is retired in the SAME commit as the floors themselves. DIRECTIVE_041
   disposition: STALE — the whole test's subject was validating the retired
   floor's derivation; it carried no coverage beyond that (mined first, per
   ``tactic:delete-the-assertion-not-the-test``).

3. **NFR-001 — zero STATUS legs re-routed to PRIMARY.** The PRIMARY evidence is
   the WP04 STATUS-from-husk behavioral assertions in
   ``tests/integration/test_coord_read_residuals_proof.py`` (the event log via
   ``read_events`` and the executor ``status_feature_dir`` leg STILL resolve the
   coord husk, proven by spies on real runs with executed revert-fails guards).
   This module asserts those named proofs EXIST (a deletion fails here) and adds a
   SECONDARY static cross-check: no STATUS ``read_events`` read in the in-scope
   STATUS-bearing modules is fed by a PRIMARY-fold seam.

Strictness mirrors the sibling ratchets (``pytestmark = pytest.mark.architectural``;
AST-only scans; ``_REPO_ROOT = parents[2]``). The arm machinery and the
canonicalizer census are imported from their canonical homes rather than
re-implemented — this guard COMPOSES the existing gates over the real tree.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architectural._gate_read_callshape import (
    _IDENTITY_READ_FUNCS,
    _LANES_READ_FUNCS,
    _PRIMARY_FOLD_CALLSHAPE_FUNCS,
    _call_func_name,
    _find_function,
    _names_bound_from,
    _names_bound_from_primary_read_dir,
    _read_call_first_arg,
    callshape_violations,
)
pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"


# ---------------------------------------------------------------------------
# In-scope module families. The coord-authority gate-hardening mission
# (``coord-authority-gate-hardening-01KW4T2F`` / WP02, FR-002 + FR-005) UNIFIES the
# identity arm's scope with the lanes arm's and extends BOTH to ``src/runtime/next/``:
#
#   * **FR-002 (scope-unify).** The IDENTITY family now also covers ``merge/`` +
#     ``lanes/`` + ``core/worktree_topology.py`` (the lanes family already did),
#     closing the asymmetry that let ``merge/executor.py``'s identity residual escape
#     the identity arm (it had only ever been in the lanes-shaped scan).
#   * **FR-005 (runtime/next extension).** BOTH families extend to
#     ``src/runtime/next/`` to future-proof the identity/lanes reads that live there
#     (``runtime_bridge.py`` carries ``get_mission_type(feature_dir)``). A
#     runtime/next-only read-site floor (``_RUNTIME_NEXT_IDENTITY_READ_FLOOR``)
#     proves the extension is non-vacuous (it is NOT green merely because the scan
#     matches nothing).
#
# Out-of-scope strangers (sync/, acceptance/, policy/, orchestrator_api/) remain
# follow-on. The two arms now share one base surface (``_SHARED_SCAN_*``) so they
# cannot silently re-diverge.
# ---------------------------------------------------------------------------
_RUNTIME_NEXT_DIR: Path = _SRC / "runtime" / "next"

# Shared base both arms scan (FR-002 scope-unify + FR-005 runtime/next extension).
_SHARED_SCAN_DIRS: tuple[Path, ...] = (
    _SRC / "specify_cli" / "merge",
    _SRC / "specify_cli" / "lanes",
    _RUNTIME_NEXT_DIR,
)
_SHARED_SCAN_FILES: tuple[Path, ...] = (_SRC / "specify_cli" / "core" / "worktree_topology.py",)

_IDENTITY_SCAN_DIRS: tuple[Path, ...] = (
    _SRC / "specify_cli" / "cli" / "commands",
    *_SHARED_SCAN_DIRS,
)
_IDENTITY_SCAN_FILES: tuple[Path, ...] = (
    _SRC / "specify_cli" / "agent_utils" / "status.py",
    *_SHARED_SCAN_FILES,
)

_LANES_SCAN_DIRS: tuple[Path, ...] = _SHARED_SCAN_DIRS
_LANES_SCAN_FILES: tuple[Path, ...] = _SHARED_SCAN_FILES

# Anti-vacuity floors: the live scan SEES a concrete count of in-scope read call
# sites (routed or not). The floors are concrete census integers a few below live —
# tight enough that a scanner that suddenly matched NOTHING (vacuous green) fails,
# loose enough that a benign refactor that drops a read site does not. ``> 0`` is
# explicitly NOT used (it would pass vacuously). FR-002/FR-005's widened surface
# raised the identity live census from 12 → 22 at the time; the lanes live census
# stays 10 (``src/runtime/next/`` carries 0 lanes.json reads today, so its lanes
# floor is unchanged).
# read-side-seam-primary-primitive-closure-01KYKMMT WP01 (T005, FR-016):
# off-by-one census correction — re-derived NOW via this module's own
# ``_count_read_call_sites`` recipe (not trusted from the prior comment): the
# LIVE identity count is 24, not 22 (unrelated `src/` growth on the base branch
# since that figure was recorded; this module made no identity-scan-affecting
# change). The floor itself is untouched (18 remains a valid, non-vacuous
# anti-vacuity bound below either figure).
_IDENTITY_READ_SITE_FLOOR = 18
_LANES_READ_SITE_FLOOR = 8

# FR-005 / NFR-003 runtime/next-only read-site floor. Counts identity reads WITHIN
# ``src/runtime/next/`` ONLY — NOT baseline + new — so removing ``src/runtime/next/``
# from the scan dirs makes this floor FAIL (a baseline-inclusive count would stay
# green and the scope extension would be vacuous; this is the gate-unmask-cannot-
# self-validate trap). The current tree carries exactly 2
# ``get_mission_type(feature_dir)`` reads in ``runtime_bridge.py`` (~:2547 / ~:3392);
# each is a CLEAN read (the ``feature_dir`` param is not bound coord-aware by any
# one-hop caller), so both are absent from the census and are accounted for solely
# by this floor. Query-mode mission-type resolution moved into
# ``mission_context_for`` so runtime/next no longer owns that identity read.
_RUNTIME_NEXT_IDENTITY_READ_FLOOR = 2

# -- FR-003 named shrink-only census (PER-ARM stale-pin split) --------------------
#
# The single shared ``_CALLSHAPE_KNOWN_RESIDUALS`` could not carry an identity-only
# pin without reddening the lanes clean-scan's stale-pin assertion (an identity pin
# is "stale" for the lanes scan, which never flags it). Splitting the census per arm
# keeps BOTH clean-scan stale-pin assertions correct (the risk called out in WP02).
#
# Census schema: ``"<rel_path>::<qualname>"`` → a tracked residual with a tracker
# reference. SHRINK-ONLY: a NEW un-pinned flag → RED (cannot hide behind the known
# set); a pinned residual that no longer flags → RED (remove the stale pin; the
# ratchet stays tight). A "routed" read is NOT a census entry — routed means *not
# flagged* (absent here, proven by the clean scan).
#
# IDENTITY census — read-side-seam-primary-primitive-closure-01KYKMMT WP01
# (T005, FR-014): the ``#2214`` PINNED exception for
# ``mission_setup_plan::_run_documentation_wiring`` is RETIRED here, together
# with the test that asserted the pin exists
# (``test_fr001_documentation_wiring_residual_is_pinned_and_flags``, removed in
# this SAME commit — deleting the entry without retiring that assertion would
# red by construction). The site itself is UNCHANGED (still coord-aware,
# still live-flagged by the arm below) — retiring the pin makes the gate
# assert the TARGET design (this read routed through the PRIMARY fold) rather
# than tolerating the current one-hop residual. This is an EXPECTED RED
# (recorded in research/expected-reds.md): ``test_fr007_arm_live_identity_scan_
# is_clean`` below now flags this site as ``unexpected`` until WP04 routes it
# (FR-024's shared migration procedure, ``migrate-fail-loud`` — C-003's carve-
# out for exactly ONE production routing edit elsewhere does not cover this
# site). DIRECTIVE_041 disposition: STALE — the pin tolerated a residual this
# mission now closes; VALID → the resulting red is a real, correct signal that
# a routing WP must act on, not a defect in this gate.
_IDENTITY_CALLSHAPE_KNOWN_RESIDUALS: frozenset[str] = frozenset()
# LANES census — empty: every in-scope lanes.json read is routed/clean.
_LANES_CALLSHAPE_KNOWN_RESIDUALS: frozenset[str] = frozenset()

# FR-003 sanctioned exclusions (Contract B) — TRUE never-flagged reads, NOT census
# entries. Scoped by QUALNAME (the function being scanned), distinct from the
# read-func-scoped STATUS exclusion below:
#   * ``require_lanes_json`` — the leaf primitive that MUST take a dir; it IS the
#     by-kind resolver leaf (C-006). Flagging it would flag the resolver itself.
#   * ``_mission_identity_payload`` — a payload/builder helper that builds a dict
#     from an already-resolved dir; not a read-routing decision.
_SANCTIONED_EXCLUSION_QUALNAMES: frozenset[str] = frozenset(
    {
        "require_lanes_json",
        "_mission_identity_payload",
    }
)

# NFR-001 SECONDARY cross-check + C-007 read-func-scoped STATUS exclusion: the
# STATUS-bearing in-scope modules whose ``read_events`` STATUS reads MUST stay
# coord-aware (never fed a PRIMARY fold). This is READ-FUNC-SCOPED — only
# ``read_events`` reads (``_STATUS_READ_FUNCS``) inside ``_STATUS_BEARING_MODULES``
# are excluded; identity/lanes reads in the SAME modules stay in-scope and flaggable
# (e.g. an injected ``resolve_mission_identity(run.feature_dir)`` in
# ``merge/executor.py`` — SC-006 / FR-008 — MUST be caught). A blanket-module skip
# would let that executor residual escape.
_STATUS_BEARING_MODULES: tuple[str, ...] = (
    "src/specify_cli/lanes/recovery.py",
    "src/specify_cli/consolidation/executor.py",
)
_STATUS_READ_FUNCS: frozenset[str] = frozenset({"read_events"})

# NFR-001 PRIMARY evidence: the WP04 behavioral STATUS-from-husk proofs.
_WP04_PROOF_MODULE = "tests/integration/test_coord_read_residuals_proof.py"
_WP04_STATUS_FROM_HUSK_PROOFS: tuple[str, ...] = (
    "test_recovery_status_leg_reads_coord_husk_not_primary",
    "test_executor_status_feature_dir_stays_coord_aware",
)


def _rel(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def _functions_in_family(
    pkg_dirs: tuple[Path, ...], files: tuple[Path, ...]
) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef, ast.Module]]:
    """Every ``(rel_path, function, module)`` in *pkg_dirs* plus the standalone *files*.

    The enclosing :class:`ast.Module` is carried so the live scan can pass
    ``module=`` to :func:`callshape_violations` — without it the FR-001 one-hop
    caller index never runs and the ``_run_documentation_wiring`` residual (and any
    future one-hop offender) would silently escape the live scan.
    """
    found: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef, ast.Module]] = []
    pyfiles: list[Path] = []
    for pkg in pkg_dirs:
        pyfiles.extend(sorted(pkg.rglob("*.py")))
    pyfiles.extend(files)
    for py in pyfiles:
        if "__pycache__" in py.parts:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        rel = _rel(py)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.append((rel, node, tree))
    return found


def _live_callshape_offenders(
    pkg_dirs: tuple[Path, ...],
    files: tuple[Path, ...],
    read_funcs: frozenset[str],
) -> dict[str, list[str]]:
    """Run the FR-007 arm LIVE over a family; return ``{rel::func: [hits]}``.

    ``module=`` is threaded so the FR-001 one-hop caller index fires (WP01/T003).
    Functions whose qualname is a sanctioned exclusion (``require_lanes_json`` leaf
    primitive, ``_mission_identity_payload`` payload helper) are never recorded —
    Contract B true exclusions, NOT census entries (FR-003 / C-006).
    """
    offenders: dict[str, list[str]] = {}
    for rel_path, func, module in _functions_in_family(pkg_dirs, files):
        if func.name in _SANCTIONED_EXCLUSION_QUALNAMES:
            continue
        hits = callshape_violations(func, read_funcs=read_funcs, module=module)
        if hits:
            offenders[f"{rel_path}::{func.name}"] = hits
    return offenders


def _count_read_call_sites(
    pkg_dirs: tuple[Path, ...],
    files: tuple[Path, ...],
    read_funcs: frozenset[str],
) -> int:
    """Count every in-scope call to a *read_funcs* function (routed or not)."""
    total = 0
    for _rel_path, func, _module in _functions_in_family(pkg_dirs, files):
        for node in ast.walk(func):
            if (
                isinstance(node, ast.Call)
                and _call_func_name(node) in read_funcs
                and _read_call_first_arg(node) is not None
            ):
                total += 1
    return total


# ===========================================================================
# (1) Live FR-007 arm — the crux: zero un-pinned violations on the real tree.
# ===========================================================================


def test_fr007_arm_live_identity_scan_is_clean() -> None:
    """LIVE: no in-scope IDENTITY read resolves off a coord-aware dir without a
    PRIMARY fold (``cli/commands/`` + ``agent_utils/status.py``).

    This is the production realization of the WP01 synthetic self-tests: the arm
    now actively gates the REAL tree. WP01 routed every identity site onto
    ``primary_feature_dir_for_mission(_canonicalize_primary_read_handle(...))``, so
    the scan is clean. A flag here means a ``resolve_mission_identity`` /
    ``get_mission_type`` read was left bound to a coord-aware resolver (it would
    read the STATUS-only ``-coord`` husk, which carries no ``meta.json`` since
    #2106) — route it through the PRIMARY fold seam.
    """
    offenders = _live_callshape_offenders(
        _IDENTITY_SCAN_DIRS, _IDENTITY_SCAN_FILES, _IDENTITY_READ_FUNCS
    )
    flagged = set(offenders)
    unexpected = flagged - _IDENTITY_CALLSHAPE_KNOWN_RESIDUALS
    stale_pins = _IDENTITY_CALLSHAPE_KNOWN_RESIDUALS - flagged
    assert not unexpected, (
        "LIVE FR-007 identity arm flagged un-pinned coord-aware read(s): "
        f"{dict(sorted((k, offenders[k]) for k in unexpected))}. A "
        "resolve_mission_identity / get_mission_type read is bound from a "
        "coord-aware resolver (resolve_feature_dir_for_mission / "
        "candidate_feature_dir_for_mission / resolve_feature_dir_for_slug / "
        "_find_feature_directory / _resolve_setup_plan_feature_dir), inline OR one "
        "hop up via a caller parameter, without a PRIMARY fold — it reads the -coord "
        "husk (no meta.json since #2106). Route it through "
        "primary_feature_dir_for_mission(_canonicalize_primary_read_handle(...)) "
        "(FR-006 / FR-007), or pin it in _IDENTITY_CALLSHAPE_KNOWN_RESIDUALS with a "
        "tracker ref. A missed in-scope routing means a prior WP left a site."
    )
    assert not stale_pins, (
        f"stale identity callshape pin(s) no longer flagged: {sorted(stale_pins)} — "
        "remove them from _IDENTITY_CALLSHAPE_KNOWN_RESIDUALS (shrink-only)."
    )


def test_fr007_arm_live_lanes_scan_is_clean() -> None:
    """LIVE: no in-scope LANES.JSON read resolves off a coord-aware dir without a
    PRIMARY fold (``merge/`` + ``lanes/`` + ``core/worktree_topology.py``).

    WP02 (merge cluster) + WP03 (lanes/core cluster) routed every ``read_lanes_json``
    / ``require_lanes_json`` read onto the PRIMARY fold. A flag here means a
    LANE_STATE read was left coord-aware (it would read the husk, which carries no
    ``lanes.json`` since #2106) — route it through the PRIMARY fold seam.
    """
    offenders = _live_callshape_offenders(
        _LANES_SCAN_DIRS, _LANES_SCAN_FILES, _LANES_READ_FUNCS
    )
    flagged = set(offenders)
    unexpected = flagged - _LANES_CALLSHAPE_KNOWN_RESIDUALS
    stale_pins = _LANES_CALLSHAPE_KNOWN_RESIDUALS - flagged
    assert not unexpected, (
        "LIVE FR-007 lanes.json arm flagged un-pinned coord-aware read(s): "
        f"{dict(sorted((k, offenders[k]) for k in unexpected))}. A read_lanes_json "
        "/ require_lanes_json read is bound from a coord-aware resolver without a "
        "PRIMARY fold — it reads the -coord husk (no lanes.json since #2106). Route "
        "it through primary_feature_dir_for_mission(_canonicalize_primary_read_handle(...)) "
        "(FR-007), or pin it in _LANES_CALLSHAPE_KNOWN_RESIDUALS with a tracker ref. "
        "A missed in-scope routing means a prior WP left a site."
    )
    assert not stale_pins, (
        f"stale lanes callshape pin(s) no longer flagged: {sorted(stale_pins)} — "
        "remove them from _LANES_CALLSHAPE_KNOWN_RESIDUALS (shrink-only)."
    )


def test_fr007_arm_live_scan_is_non_vacuous() -> None:
    """The clean scans above are not vacuously green: the arm SAW the in-scope read
    call sites it is meant to gate.

    A regression that renamed the read funcs, emptied the scan dirs, or broke the
    family iteration would make the live arm match NOTHING — and report a
    false-clean. This guard pins the live count of in-scope identity / lanes.json
    read CALL SITES (routed or not) to a concrete floor a few below the live census
    (24 identity / 10 lanes, re-derived WP01/T005 — corrected from the stale 22
    recorded after FR-002/FR-005 widening), so a vacuous scan FAILS.
    """
    identity_sites = _count_read_call_sites(
        _IDENTITY_SCAN_DIRS, _IDENTITY_SCAN_FILES, _IDENTITY_READ_FUNCS
    )
    lanes_sites = _count_read_call_sites(
        _LANES_SCAN_DIRS, _LANES_SCAN_FILES, _LANES_READ_FUNCS
    )
    assert identity_sites >= _IDENTITY_READ_SITE_FLOOR, (
        f"in-scope identity read call sites dropped to {identity_sites}; expected "
        f">= {_IDENTITY_READ_SITE_FLOOR}. A shrinking count likely means the live "
        "arm scan stopped matching read call sites (vacuous green)."
    )
    assert lanes_sites >= _LANES_READ_SITE_FLOOR, (
        f"in-scope lanes.json read call sites dropped to {lanes_sites}; expected "
        f">= {_LANES_READ_SITE_FLOOR}. A shrinking count likely means the live arm "
        "scan stopped matching read call sites (vacuous green)."
    )


# ===========================================================================
# (1b) FR-005 runtime/next scan extension — provably non-vacuous (NFR-003).
# ===========================================================================


def _src_rel(*parts: str) -> str:
    """Repo-relative posix path under ``src/`` (e.g. ``src/runtime/next``)."""
    return (_SRC / Path(*parts)).relative_to(_REPO_ROOT).as_posix()


def test_fr005_runtime_next_in_both_scan_families() -> None:
    """FR-005: ``src/runtime/next/`` is in BOTH the identity AND lanes scan dirs.

    The scope extension is what brings ``runtime_bridge.py``'s identity/lanes reads
    under the live arm. If a future edit drops it from either family, the runtime/next
    blind spot reopens — this structural assertion fails before that can happen. It is
    paired with the NON-VACUOUS floor below (a bare membership assert would be
    vacuous on its own).
    """
    assert _RUNTIME_NEXT_DIR in _IDENTITY_SCAN_DIRS, (
        "src/runtime/next/ dropped from _IDENTITY_SCAN_DIRS — the FR-005 identity "
        "extension regressed; runtime_bridge.py identity reads are no longer gated."
    )
    assert _RUNTIME_NEXT_DIR in _LANES_SCAN_DIRS, (
        "src/runtime/next/ dropped from _LANES_SCAN_DIRS — the FR-005 lanes "
        "extension regressed."
    )


def _runtime_next_identity_sites(scan_dirs: tuple[Path, ...]) -> int:
    """Identity read sites within ``src/runtime/next/`` AS SEEN THROUGH *scan_dirs*.

    The count is derived from *scan_dirs* (intersected with ``_RUNTIME_NEXT_DIR``), NOT
    from ``_RUNTIME_NEXT_DIR`` directly — so removing ``src/runtime/next/`` from the
    scan dirs drops the count to 0. This is the gate-unmask-cannot-self-validate
    guard: a count anchored on the bare constant would stay green even with the scope
    extension reverted (the NFR-003 self-validation trap).
    """
    scoped = tuple(d for d in scan_dirs if d == _RUNTIME_NEXT_DIR)
    return _count_read_call_sites(scoped, (), _IDENTITY_READ_FUNCS)


def test_fr005_runtime_next_identity_read_floor_is_non_vacuous() -> None:
    """FR-005 / NFR-003: the runtime/next extension SEES real in-family identity
    reads — it is NOT green merely because the scan matches nothing.

    The floor counts ``get_mission_type(feature_dir)`` reads WITHIN
    ``src/runtime/next/`` ONLY (not baseline + new): ``runtime_bridge.py`` carries 2
    (~:2547 / ~:3392). The count is derived from the LIVE
    ``_IDENTITY_SCAN_DIRS`` so reverting the scope extension breaks it (proven in
    ``test_fr005_runtime_next_floor_fails_if_scope_reverted``).
    """
    sites = _runtime_next_identity_sites(_IDENTITY_SCAN_DIRS)
    assert sites >= _RUNTIME_NEXT_IDENTITY_READ_FLOOR, (
        f"runtime/next identity read sites = {sites}; expected "
        f">= {_RUNTIME_NEXT_IDENTITY_READ_FLOOR}. The FR-005 extension is vacuous — "
        "src/runtime/next/ is no longer in _IDENTITY_SCAN_DIRS, or runtime_bridge.py "
        "no longer carries the get_mission_type reads the floor is built on."
    )


def test_fr005_runtime_next_floor_fails_if_scope_reverted() -> None:
    """FR-005 / NFR-003 revert-sensitivity (executed, not documented): REMOVING
    ``src/runtime/next/`` from the identity scan dirs makes the runtime/next floor
    FAIL.

    This *executes* the revert in-test: recompute the floor's count over the scan
    dirs WITHOUT ``src/runtime/next/`` and assert it falls below the floor (0 < 3).
    Because :func:`_runtime_next_identity_sites` derives the count from the passed
    scan dirs, a vacuous floor (anchored on the bare ``_RUNTIME_NEXT_DIR`` constant)
    would stay green here — so this guard fails loudly if FR-005 is made vacuous.
    """
    reverted = tuple(d for d in _IDENTITY_SCAN_DIRS if d != _RUNTIME_NEXT_DIR)
    sites_after_revert = _runtime_next_identity_sites(reverted)
    assert sites_after_revert < _RUNTIME_NEXT_IDENTITY_READ_FLOOR, (
        "removing src/runtime/next/ from the scan dirs must drop the runtime/next "
        f"identity floor below {_RUNTIME_NEXT_IDENTITY_READ_FLOOR}; got "
        f"{sites_after_revert}. The floor is not scope-sensitive (vacuous)."
    )


# ===========================================================================
# (1c) FR-003 census disposition + sanctioned exclusions, and the FR-001/FR-008
# scope proofs (SC-006). Synthetic shapes are parsed and fed to the LIVE arm so the
# proofs exercise the real classifier, not a restatement of the constants.
# ===========================================================================


def _parse_func(
    src: str, name: str
) -> tuple[ast.FunctionDef | ast.AsyncFunctionDef, ast.Module]:
    """Parse *src* and return ``(function ``name``, enclosing module)``."""
    module = ast.parse(src)
    func = _find_function(module, name)
    assert func is not None, f"helper source missing function {name!r}"
    return func, module


def test_fr003_runtime_bridge_get_mission_type_reads_are_clean_not_pinned() -> None:
    """FR-003 disposition: the 3 ``runtime_bridge.py`` ``get_mission_type(feature_dir)``
    reads are CLEAN (ROUTED, i.e. not flagged) — absent from the census, counted by
    the runtime/next floor.

    Their disposition is *not flagged*: ``feature_dir`` is a plain parameter that no
    one-hop caller binds coord-aware-without-fold, so the hardened arm does not flag
    them. Recording them as census entries would be the "routed-but-also-pinned"
    auditability anti-pattern (T008 NON-FAKEABLE DoD). This guard proves they are
    genuinely absent from the live offender set AND that they are not pinned.
    """
    offenders = _live_callshape_offenders(
        (_RUNTIME_NEXT_DIR,), (), _IDENTITY_READ_FUNCS
    )
    runtime_bridge_flags = {k for k in offenders if "runtime_bridge.py" in k}
    assert not runtime_bridge_flags, (
        "runtime_bridge.py identity reads unexpectedly flagged — their FR-003 "
        f"disposition is CLEAN/ROUTED, not pinned: {runtime_bridge_flags}. If a real "
        "coord-aware binding appeared, route it or pin it explicitly."
    )
    # And they are not (incorrectly) carried as census pins.
    assert not any(
        "runtime_bridge.py" in entry for entry in _IDENTITY_CALLSHAPE_KNOWN_RESIDUALS
    ), "runtime_bridge.py reads must NOT be census pins — they are clean (ROUTED)."


# read-side-seam-primary-primitive-closure-01KYKMMT WP01 (T005, FR-014):
# ``test_fr001_documentation_wiring_residual_is_pinned_and_flags`` RETIRED
# together with the ``#2214`` pin above (removing the pin without retiring this
# assertion would red by construction: it asserted the pin EXISTS). The live
# flag it used to certify is now asserted directly by
# ``test_fr007_arm_live_identity_scan_is_clean``'s ``unexpected`` check above —
# with the pin gone, that residual now surfaces there as an EXPECTED red
# (recorded in research/expected-reds.md) until WP04 routes it.


def test_fr003_sanctioned_exclusions_are_read_func_scoped_for_status() -> None:
    """C-007 / FR-003: the STATUS exclusion is READ-FUNC-SCOPED, not a blanket-module
    skip. Proven by a POSITIVE flag pair on synthetic ``merge/executor.py``-shaped
    source: an identity read off a coord-aware dir IS flagged, while a ``read_events``
    STATUS read off the SAME coord-aware dir is NOT an identity flag.

    A vacuous ``assert "…/executor.py" in _IDENTITY_SCAN_DIRS`` would only prove the
    module is scanned, not that an identity read there survives the exclusion. This
    feeds the live arm instead: the exclusion keys on the read-func NAME
    (``read_events`` is not an identity read func), so an injected
    ``resolve_mission_identity`` in the status-bearing module remains flaggable
    (SC-006 / FR-008), while the STATUS leg is governed by the separate NFR-001
    cross-check (``test_no_status_leg_rerouted_to_primary``), not silenced by a
    blanket module skip.
    """
    # The status-bearing module IS in identity scope (merge/ is part of the unify) —
    # so its identity reads are scanned, NOT blanket-excluded.
    executor = _SRC / "specify_cli" / "merge" / "executor.py"
    assert any(executor.is_relative_to(d) for d in _IDENTITY_SCAN_DIRS), (
        "merge/executor.py must be inside an identity scan dir (FR-002 unify) so its "
        "identity reads are in-scope despite being a STATUS-bearing module."
    )
    assert "src/specify_cli/consolidation/executor.py" in _STATUS_BEARING_MODULES, (
        "executor.py must remain a STATUS-bearing module for the read-func-scoped "
        "read_events exclusion."
    )
    # POSITIVE proof: identity read off a coord-aware dir IS flagged in the
    # status-bearing module shape.
    identity_src = (
        "def build_run(repo, slug):\n"
        "    feature_dir = resolve_feature_dir_for_mission(repo, slug)\n"
        "    return resolve_mission_identity(feature_dir)\n"
    )
    ident_func, ident_module = _parse_func(identity_src, "build_run")
    assert callshape_violations(
        ident_func, read_funcs=_IDENTITY_READ_FUNCS, module=ident_module
    ), "an identity read off a coord-aware dir must flag even in a STATUS-bearing module."
    # NEGATIVE control: a read_events STATUS read off the same coord-aware dir is NOT
    # an identity-arm flag (the exclusion keys on the read-func name).
    status_src = (
        "def status_leg(repo, slug):\n"
        "    feature_dir = candidate_feature_dir_for_mission(repo, slug)\n"
        "    return read_events(feature_dir)\n"
    )
    status_func, status_module = _parse_func(status_src, "status_leg")
    assert (
        callshape_violations(
            status_func, read_funcs=_IDENTITY_READ_FUNCS, module=status_module
        )
        == []
    ), "read_events is not an identity read func — the identity arm must not flag it."


def test_sc006_executor_identity_reads_in_scope_both_shapes() -> None:
    """SC-006 / FR-008: the FR-002 scope-unify makes ``merge/executor.py`` identity
    reads in-scope for BOTH the parameter shape AND the ``run.feature_dir`` attribute
    shape — proven by feeding both shapes through the scope-unified arm.

    A single-shape assertion is insufficient: the attribute shape (FR-008) must be
    proven in-scope HERE (live-scope), not only synthetically in WP01/T005. The
    parameter (one-hop) shape proves the FR-001 caller index reaches the module.
    """
    # Scope: executor.py is under an identity scan dir (FR-002 unify).
    executor = _SRC / "specify_cli" / "merge" / "executor.py"
    assert any(executor.is_relative_to(d) for d in _IDENTITY_SCAN_DIRS)

    # (1) ATTRIBUTE shape (FR-008): resolve_mission_identity(run.feature_dir) — a
    # non-sanctioned coord-bearing attribute — flags. (run.target_feature_dir, the
    # sanctioned primary attribute the real executor.py uses, would NOT flag.)
    attr_src = (
        "def reopen_executor_attr(run):\n"
        "    return resolve_mission_identity(run.feature_dir).mission_id\n"
    )
    attr_func, attr_module = _parse_func(attr_src, "reopen_executor_attr")
    assert callshape_violations(
        attr_func, read_funcs=_IDENTITY_READ_FUNCS, module=attr_module
    ), "the FR-008 attribute escape resolve_mission_identity(run.feature_dir) must flag."
    sanctioned_src = (
        "def executor_primary_attr(run):\n"
        "    return resolve_mission_identity(run.target_feature_dir).mission_id\n"
    )
    sanctioned_func, sanctioned_module = _parse_func(
        sanctioned_src, "executor_primary_attr"
    )
    assert (
        callshape_violations(
            sanctioned_func, read_funcs=_IDENTITY_READ_FUNCS, module=sanctioned_module
        )
        == []
    ), "the sanctioned primary attribute run.target_feature_dir must NOT flag (C-001)."

    # (2) PARAMETER (one-hop) shape: a callee reads its feature_dir param; its caller
    # binds it coord-aware-without-fold → flags via the module-scoped caller index.
    param_src = (
        "def _executor_identity_leg(feature_dir):\n"
        "    return resolve_mission_identity(feature_dir).mission_id\n"
        "\n"
        "def _executor_caller(repo, slug):\n"
        "    feature_dir = resolve_feature_dir_for_mission(repo, slug)\n"
        "    return _executor_identity_leg(feature_dir)\n"
    )
    param_func, param_module = _parse_func(param_src, "_executor_identity_leg")
    assert callshape_violations(
        param_func, read_funcs=_IDENTITY_READ_FUNCS, module=param_module
    ), "the FR-001 one-hop parameter shape must flag through the scope-unified arm."
    # BOUNDARY: without module context the one-hop shape is NOT flagged (proves the
    # flag came solely from the caller index, not a same-function binding).
    assert (
        callshape_violations(param_func, read_funcs=_IDENTITY_READ_FUNCS) == []
    ), "the one-hop parameter shape must NOT flag without the module-scoped caller index."


# ===========================================================================
# (2) Floor honesty — RETIRED (read-side-seam-primary-primitive-closure-01KYKMMT
# WP01, T003/T004, FR-007). ``test_routed_canonicalizer_floor_matches_recorded_
# census`` used to pin ``ROUTED_CANONICALIZER_FLOOR == 40`` /
# ``CANONICALIZER_FLOOR == 44`` here. Both constants (and the two use-count
# floor tests that owned them) are retired in
# ``test_resolution_authority_gates.py`` (since deleted) — see that module's retirement
# comment for the honest re-derived census and the DIRECTIVE_043 transfer
# adjudication (the guarantee moves to the read-side bypass census, WP02).
# DIRECTIVE_041 disposition: STALE — this test's entire subject was verifying
# the retired floor's derivation; it carried no coverage beyond the two
# equality pins and the two bound checks that depended on them, so the whole
# test is retired (not merely the pins) rather than re-pointed to a vacuous
# shell. Retiring the constants without retiring this module's IMPORT of them
# would raise ``ImportError`` at collection (~20 tests, DIRECTIVE_034) — hence
# this removal lands in the SAME commit as T003.
# ===========================================================================


# ===========================================================================
# (3) NFR-001 — zero STATUS legs re-routed to PRIMARY.
# ===========================================================================


def test_wp04_status_from_husk_proofs_exist() -> None:
    """NFR-001 PRIMARY evidence: the WP04 behavioral STATUS-from-husk proofs exist.

    These are the load-bearing NFR-001 evidence — they assert (on real runs, with
    executed revert-fails guards) that the STATUS event log (``read_events``) and
    the executor ``status_feature_dir`` leg STILL resolve the coord husk, never
    PRIMARY. Deleting/renaming them would silently remove the primary proof, so
    this close-out guard pins their existence.
    """
    proof_path = _REPO_ROOT / _WP04_PROOF_MODULE
    assert proof_path.exists(), (
        f"WP04 behavioral proof module missing: {_WP04_PROOF_MODULE} — the NFR-001 "
        "STATUS-from-husk primary evidence is gone."
    )
    tree = ast.parse(proof_path.read_text(encoding="utf-8"))
    missing = [
        name for name in _WP04_STATUS_FROM_HUSK_PROOFS if _find_function(tree, name) is None
    ]
    assert not missing, (
        f"WP04 STATUS-from-husk proof function(s) missing: {missing}. These are the "
        "NFR-001 primary evidence (the STATUS legs still read the coord husk on a "
        "real run); restore them."
    )


def test_no_status_leg_rerouted_to_primary() -> None:
    """NFR-001 SECONDARY cross-check: no in-scope STATUS ``read_events`` read is fed
    a PRIMARY-fold dir.

    This is a static cross-check ONLY — the PRIMARY evidence is the WP04 behavioral
    proofs (``test_wp04_status_from_husk_proofs_exist``). A STATUS event-log read
    that was silently re-pointed to ``primary_feature_dir_for_mission`` /
    ``resolve_planning_read_dir`` (the NFR-001 regression) would surface here as a
    ``read_events`` call whose first arg is bound from / built by a PRIMARY-fold
    seam. The STATUS legs must stay coord-aware (read the ``-coord`` husk).
    """
    offenders: dict[str, list[str]] = {}
    for rel_path in _STATUS_BEARING_MODULES:
        tree = ast.parse((_REPO_ROOT / rel_path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # WP01/T001 (Ledger M7): UNION the kind-discriminated seam-idiom
            # binding rather than widening _PRIMARY_FOLD_CALLSHAPE_FUNCS by
            # callee name — see that constant's docstring (test_gate_read_
            # literal_ban.py) for why a bare ``read_dir`` name would sanction a
            # STATUS_STATE-kind read here identically to a PRIMARY_METADATA one.
            primary_bound = _names_bound_from(
                node, _PRIMARY_FOLD_CALLSHAPE_FUNCS
            ) | _names_bound_from_primary_read_dir(node)
            hits: list[str] = []
            for call in ast.walk(node):
                if (
                    not isinstance(call, ast.Call)
                    or _call_func_name(call) not in _STATUS_READ_FUNCS
                    or not call.args
                ):
                    continue
                first = call.args[0]
                if isinstance(first, ast.Name) and first.id in primary_bound:
                    hits.append(f"read_events({first.id})  # PRIMARY-fold bound")
                elif isinstance(first, ast.Call) and (
                    _call_func_name(first) in _PRIMARY_FOLD_CALLSHAPE_FUNCS
                ):
                    hits.append(f"read_events({_call_func_name(first)}(...))")
            if hits:
                offenders[f"{rel_path}::{node.name}"] = hits

    assert not offenders, (
        "NFR-001 REGRESSION: a STATUS read_events leg was re-routed to PRIMARY: "
        f"{dict(sorted(offenders.items()))}. The STATUS event log must stay "
        "coord-aware (read the -coord husk via candidate_feature_dir_for_mission); "
        "see the WP04 behavioral proofs for the primary evidence (C-001 KEEP)."
    )
