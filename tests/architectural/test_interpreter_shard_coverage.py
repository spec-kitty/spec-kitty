"""Coverage-completeness + shard-identity roster checks for #4951 (FR-004/FR-005/FR-016).

The nightly ``interpreter-matrix`` job was split into N independent
``interpreter-matrix-shard-<N>`` jobs (see ``_interpreter_shard_roster.py``)
because the single combined job could never finish
``pytest -m "fast or unit"`` on Python 3.13 within its 45-minute timeout on a
GitHub-hosted runner. A shard split is only as good as its boundaries: this
module machine-checks that

1. the union of every shard's REAL collected node-ids equals the full
   ``fast or unit`` 3.13 selection, with zero duplicates and zero gaps
   (FR-004/NFR-002/SC-003) -- never a manual review of directory lists;
2. no shard's selector collects 0 tests (FR-005);
3. no shard is silently dropped from ``ci-nightly.yml``'s ``jobs:`` while
   remaining declared in the roster (FR-016/SC-009) -- distinguishable from
   (2) above, since a deleted job leaves nothing in the workflow file to read
   a shard name from.

Reuse-vs-rejection decision (FR-017/SC-010, plan.md SS A): this module REUSES
``_gate_coverage``'s pure primitives (``Gate``, ``parse_workflow``,
``collect_job_nodeids``, ``BaselineTarget``, ``gates_for_target``) directly,
per-shard, as LOCAL values -- it never adds entries to the shared
``BASELINE_TARGETS`` tuple and never calls
``collect_real_union_for_target``/``freeze_baselines``. That frozen-baseline
layer answers "did this ONE job's selection drift since a human froze it" (a
historical-drift oracle backed by a committed snapshot file); this module
instead proves a LIVE invariant every run -- "do these N independently-named
jobs' selections union to exactly today's full selection, with zero gap and
zero overlap" -- which the frozen-baseline layer cannot express without one
manually-regenerated snapshot file per shard (reintroducing the exact
committed-data-can-drift-from-live-reality hazard ledger SK-247 already
burned this mission's sibling on, one layer up).

Per-file collection memo (FR-006): the two real consumers
(``test_no_shard_collects_zero_tests`` and the union test) both need every
shard's collected node-ids, and each collection is a pytest subprocess. They
share ONE collection per distinct selection through ``_collect_memo``: a
``functools.cache`` keyed on ``(resolved repo root, paths, ignores,
marker_expr)`` -- never on ``gate.job`` or the unhashable ``Gate`` -- holding
node-id FINDINGS (an immutable tuple of strings), not collected items or
syntax trees. Its lifetime is the file: ``_clear_collect_memo`` empties it at
module teardown, and under ``--dist loadfile`` that is "once per file". The
mutation controls never use the memo: they call
``_coverage_completeness_violations`` without ``collect`` and so reach the
(monkeypatched) uncached primitive ``collect_job_nodeids``, resolved from
module globals at call time.
"""

from __future__ import annotations

import contextlib
import dataclasses
import functools
import itertools
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
from _pytest.mark.expression import Expression

from tests.architectural._gate_coverage import (
    Gate,
    BaselineTarget,
    collect_job_nodeids,
    gates_for_target,
    load_spliced_workflow,
    marker_names,
    parse_workflow,
    positive_marker_tokens,
)
from tests.architectural._interpreter_shard_roster import (
    INTERPRETER_SHARD_JOB_KEYS,
    INTERPRETER_SHARDS,
    JOB_KEY_PREFIX,
    InterpreterShard,
    shard_roster_non_vacuity_violation,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

pytestmark = [pytest.mark.architectural]

REPO_ROOT = Path(__file__).resolve().parents[2]
NIGHTLY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci-nightly.yml"

# The canonical shard marker expression every roster shard's job -- and the
# synthetic full-selection Gate it must union back to -- runs under. Landing
# pass #5244 (LAND-PAT-006): declared ONCE, here, ahead of its first use, so
# `_FULL_SELECTION_GATE` and `_shard_gate` (below) both reference this SAME
# constant instead of each separately hardcoding the literal `"fast or
# unit"` -- previously a third copy alongside the two Gates.
_EXPECTED_SHARD_MARKER_EXPR = "fast or unit"

# The full, unsharded selection this mission's shard split must exactly
# reconstruct: `pytest -m "fast or unit"` over the whole `tests/` tree. This
# Gate is NEVER inserted into the real workflow file -- it exists only here,
# so both sides of the FR-004 comparison are collected through the IDENTICAL
# `collect_job_nodeids` mechanics (mirroring `_gate_coverage.py`'s own E3
# "both sides captured by the identical function" design principle).
_FULL_SELECTION_GATE = Gate(
    workflow="ci-nightly.yml",
    job="<synthetic-full-selection>",
    shard=None,
    paths=["tests"],
    marker_expr=_EXPECTED_SHARD_MARKER_EXPR,
)


def _shard_gate(shard: InterpreterShard) -> Gate:
    """Build the LOCAL (never-shared) Gate a shard's BaselineTarget resolves to."""
    return Gate(
        workflow="ci-nightly.yml",
        job=shard.job_key,
        shard=None,
        paths=list(shard.paths),
        ignores=list(shard.ignores),
        marker_expr=_EXPECTED_SHARD_MARKER_EXPR,
    )


def _real_workflow_gates() -> list[Gate]:
    return parse_workflow(NIGHTLY_WORKFLOW)


def test_roster_is_non_empty() -> None:
    """Sanity: the roster must declare at least one shard, AND (landing pass
    #5244, LAND-PAT-006) its count must match the real workflow's --
    delegating to the roster's shared ``shard_roster_non_vacuity_violation``
    helper, collapsing what was a third independent copy of this check."""
    real_job_keys = {gate.job for gate in _real_workflow_gates()}
    violation = shard_roster_non_vacuity_violation(INTERPRETER_SHARD_JOB_KEYS, real_job_keys)
    assert violation is None, violation


def test_every_roster_shard_exists_in_the_workflow_job_list() -> None:
    """FR-016/SC-009: a shard declared in the roster but missing from
    ``ci-nightly.yml``'s ``jobs:`` fails loudly, naming that shard.

    Reuses ``gates_for_target``'s existing raise-loudly-on-zero-gates
    behavior (per-shard, as a LOCAL ``BaselineTarget`` -- never added to the
    shared ``BASELINE_TARGETS`` tuple).
    """
    real_gates = _real_workflow_gates()
    missing: list[str] = []
    for shard in INTERPRETER_SHARDS:
        target = BaselineTarget(slug=shard.job_key, workflow="ci-nightly.yml", job=shard.job_key)
        try:
            gates_for_target(real_gates, target)
        except RuntimeError:
            missing.append(shard.job_key)
    assert not missing, (
        f"shard(s) declared in the roster but absent from ci-nightly.yml's jobs: {missing} (FR-016 -- a shard was silently dropped from the job list)"
    )


def test_no_dangling_job_key_outside_the_roster() -> None:
    """The workflow must not carry an ``interpreter-matrix-shard-*``-shaped
    job that the roster does not also declare -- keeps the roster the single
    source of truth in both directions."""
    real_job_keys = {gate.job for gate in _real_workflow_gates()}
    roster_keys = {shard.job_key for shard in INTERPRETER_SHARDS}
    dangling = {key for key in real_job_keys if key.startswith(JOB_KEY_PREFIX) and key not in roster_keys}
    assert not dangling, f"job(s) in ci-nightly.yml not declared in the roster: {sorted(dangling)}"


# ---------------------------------------------------------------------------
# PR-BOUNDARY-001 (pre-merge squad, severity 4): the checks above only prove
# the roster's OWN paths union to the full selection and that the roster's
# job KEYS match the workflow's job keys. Neither ties the roster's declared
# `paths`/`ignores` to what ci-nightly.yml's COMMITTED `run:` line actually
# passes to pytest for each shard. A YAML-only edit that rebalances a
# shard's test-path arguments (or its marker) directly in the workflow,
# without touching the roster, must fail here by name.
# ---------------------------------------------------------------------------


def _real_paths_ignores_markers_for_job(real_gates: list[Gate], job_key: str) -> tuple[set[str], set[str], set[str]]:
    """Union of ``paths``/``ignores``/``marker_expr`` across every REAL parsed
    ``Gate`` leg for one job key (a job normally has exactly one pytest leg;
    unioning is defensive, never masking a leg)."""
    paths: set[str] = set()
    ignores: set[str] = set()
    markers: set[str] = set()
    for gate in real_gates:
        if gate.job != job_key:
            continue
        paths |= set(gate.paths)
        ignores |= set(gate.ignores)
        if gate.marker_expr:
            markers.add(gate.marker_expr)
    return paths, ignores, markers


# PR-FRESH3-001: `_marker_exprs_are_boolean_equivalent` below enumerates
# `itertools.product((False, True), repeat=len(names))` -- O(2**N) in the
# number of distinct marker names either compared expression references. This
# is instant at today's real call sites (2-3 names), but doubles in cost per
# additional name with no ceiling: 20 names already costs ~1.8s wall-clock for
# ONE comparison (measured directly against `_pytest.mark.expression.Expression`
# in this repo's venv). A future widening of `_EXPECTED_SHARD_MARKER_EXPR` or a
# shard's marker to reference many names (the repo's own `pyproject.toml`
# mutmut config already carries a real 10-name `-m` expression, so double-digit
# counts are not hypothetical here) would silently degrade this check from
# instant to minutes-to-hours -- in a repo whose mission is explicitly about CI
# jobs silently blowing their time budget. This bound fails loudly instead.
_MAX_TRUTH_TABLE_MARKER_NAMES = 12


# _marker_names_referenced (the domain a truth-table equivalence check below
# must range over) was a third, LENIENT (bare ast.walk) sign-blind marker-
# name walker -- a near-copy of _fast_tier_gate._collect_names, which is
# STRICT (raises on an unsupported node). Landing pass #5244 (LAND-PAT-004)
# promoted the strict shape to _gate_coverage.marker_names as the one shared
# implementation; this module now calls that instead of re-deriving its own.


def _marker_exprs_are_boolean_equivalent(expr_a: str, expr_b: str) -> bool:
    """True iff ``expr_a`` and ``expr_b`` evaluate to the IDENTICAL boolean
    value for EVERY possible True/False assignment of every marker name
    either one references -- real boolean-formula equivalence, not merely
    "references the same marker names."

    Operator ruling (round-3 FIX, superseding the ``positive_marker_tokens``
    remedy PR-FRESH-001 shipped): that remedy compared only POSITIVE/NEGATIVE
    marker-NAME sets, so ``"fast or unit"`` and ``"fast and unit"`` -- which
    reference the identical names but select a materially NARROWER
    intersection instead of a union -- collapsed to the same signature and
    were wrongly treated as equal (PR-FRESH2-001). A truth table closes this:
    it evaluates both expressions over every assignment of the names either
    references and requires them to agree on ALL of them, so any combinator
    swap, dropped name, added exclusion, or widened selection that changes
    the result for SOME assignment is caught, while a reorder, added
    whitespace/parens, or double negation -- which agree on EVERY assignment
    -- still pass.

    Evaluated with pytest's OWN marker-expression evaluator
    (``_pytest.mark.expression.Expression.compile(...).evaluate(...)``, the
    exact evaluator pytest itself uses for a real ``-m`` selection) rather
    than a hand-rolled parser. Confirmed permitted for this comparison:
    ``tests/architectural/_gate_coverage.py`` and
    ``tests/architectural/_fast_tier_gate.py`` already import
    ``_pytest.mark.expression.Expression`` directly at module scope, and
    ``pyproject.toml``'s ``[tool.ruff.lint.flake8-tidy-imports.banned-api]``
    (TID251) bans only ``hashlib.sha256``, ``click.exceptions.*``, and named
    retired ``specify_cli``/``websockets`` subsystems -- it does not name
    ``_pytest.mark.expression`` anywhere, so no ``# noqa: TID251`` is needed.
    """
    names = sorted(marker_names(expr_a) | marker_names(expr_b))
    if len(names) > _MAX_TRUTH_TABLE_MARKER_NAMES:
        raise AssertionError(
            f"boolean-equivalence truth table is exponential in the marker count "
            f"({len(names)} names > {_MAX_TRUTH_TABLE_MARKER_NAMES}-name bound: {names}); "
            "refactor to a SAT-style check or shrink the compared expressions "
            "instead of growing the marker taxonomy further"
        )
    compiled_a = Expression.compile(expr_a)
    compiled_b = Expression.compile(expr_b)
    for bits in itertools.product((False, True), repeat=len(names)):
        assignment = dict(zip(names, bits, strict=True))
        matcher = cast("Any", lambda name, _assignment=assignment: _assignment[name])
        if compiled_a.evaluate(matcher) != compiled_b.evaluate(matcher):
            return False
    return True


def test_marker_exprs_are_boolean_equivalent_bounds_the_truth_table_cost() -> None:
    """PR-FRESH3-001: proves the exponential-cost bound trips loudly rather
    than silently enumerating an ever-larger truth table. Constructs an
    expression whose marker-name union exceeds ``_MAX_TRUTH_TABLE_MARKER_NAMES``
    and asserts ``_marker_exprs_are_boolean_equivalent`` refuses to evaluate it,
    naming the offending count in the failure message."""
    too_many_names = " or ".join(f"m{i}" for i in range(_MAX_TRUTH_TABLE_MARKER_NAMES + 1))
    with pytest.raises(AssertionError, match="exponential"):
        _marker_exprs_are_boolean_equivalent(too_many_names, _EXPECTED_SHARD_MARKER_EXPR)


def _marker_expr_diverges_from_expected_shard_marker(marker_expr: str) -> bool:
    """True iff ``marker_expr`` is NOT boolean-equivalent (see
    ``_marker_exprs_are_boolean_equivalent`` above) to the canonical
    ``"fast or unit"`` shard marker over every True/False assignment of the
    marker names either references (PR-FRESH2-001 / the operator ruling that
    supersedes the earlier ``positive_marker_tokens``-set comparison). A
    harmless reorder/reformat/double-negation with identical pytest
    semantics (``"unit or fast"``, ``"fast  or  unit"``, ``"(fast or
    unit)"``, ``"not not (fast or unit)"``) reports no divergence; a real
    selection change -- a combinator swap (``"and"`` for ``"or"``), a dropped
    name, an added exclusion, or an added/widened alternative -- still does.
    """
    return not _marker_exprs_are_boolean_equivalent(marker_expr, _EXPECTED_SHARD_MARKER_EXPR)


def _shard_workflow_divergences(real_gates: list[Gate], shards: tuple[InterpreterShard, ...]) -> list[str]:
    """PRODUCTION comparison for PR-BOUNDARY-001: for every shard, diff the
    REAL per-job paths/ignores/marker parsed out of the committed workflow
    against the roster's own declared paths/ignores (the implied marker,
    ``"fast or unit"``, is what ``_shard_gate`` hardcodes for every shard).
    Returns one human-readable mismatch string per shard with a divergence,
    or an empty list when the roster and the committed workflow agree
    exactly.

    Both the real test below (the REAL ``INTERPRETER_SHARDS`` roster against
    the REAL parsed workflow) and the required Standing-Order-#5 mutation
    test call this SAME function, over a scratch ``real_gates`` copy -- a
    mutation test that never reaches this code cannot prove anything
    (mirroring WP01-R1-001's existing rationale for
    ``_coverage_completeness_violations`` above).
    """
    mismatches: list[str] = []
    for shard in shards:
        real_paths, real_ignores, real_markers = _real_paths_ignores_markers_for_job(real_gates, shard.job_key)
        roster_paths = set(shard.paths)
        roster_ignores = set(shard.ignores)

        missing_paths = roster_paths - real_paths
        extra_paths = real_paths - roster_paths
        missing_ignores = roster_ignores - real_ignores
        extra_ignores = real_ignores - roster_ignores
        bad_markers = {m for m in real_markers if _marker_expr_diverges_from_expected_shard_marker(m)}

        if missing_paths or extra_paths or missing_ignores or extra_ignores or bad_markers:
            mismatches.append(
                f"{shard.job_key}: roster-only paths={sorted(missing_paths)} workflow-only paths={sorted(extra_paths)} "
                f"roster-only ignores={sorted(missing_ignores)} workflow-only ignores={sorted(extra_ignores)} "
                f"unexpected marker(s)={sorted(bad_markers)}"
            )
    return mismatches


def test_every_roster_shard_paths_and_ignores_equal_the_committed_workflow() -> None:
    """PR-BOUNDARY-001: ties the roster's declared ``paths``/``ignores`` to
    what ci-nightly.yml's COMMITTED ``run:`` pytest invocation actually runs,
    per shard -- closing the gap left open by
    ``test_shard_union_equals_full_selection_with_zero_gap_and_zero_overlap``
    (which only proves the roster's OWN paths union to the full selection,
    never that those paths are what the shipped workflow runs). A future
    hand-edit to a shard's ``run:`` pytest path list that diverges from the
    roster now fails loudly here, naming the shard and the mismatched
    path(s)."""
    mismatches = _shard_workflow_divergences(_real_workflow_gates(), INTERPRETER_SHARDS)
    assert not mismatches, "roster paths/ignores diverge from what ci-nightly.yml actually runs (PR-BOUNDARY-001):\n" + "\n".join(mismatches)


def _scratch_gates_with(real_gates: list[Gate], victim: str, transform: Callable[[Gate], dict[str, object]]) -> list[Gate]:
    """Single shared scratch-copy helper (PR-FRESH2-002): a copy of
    ``real_gates`` with ``victim``'s Gate(s) replaced via
    ``dataclasses.replace(g, **transform(g))`` -- never a manual per-field
    ``Gate`` reconstruction (the pre-existing path-mutation copy above and
    the new ``_scratch_gates_with_marker`` each hand-listed all seven ``Gate``
    fields (confirmed via ``dataclasses.fields(Gate)``: ``workflow``, ``job``,
    ``shard``, ``paths``, ``ignores``, ``marker_expr``, ``via``); both now
    route through this ONE helper, so a future ``Gate``
    field addition needs one update site instead of two). ``transform``
    receives the real ``Gate`` so an override can depend on its own current
    field values (e.g. appending to its existing ``paths``). Never touches
    ``.github/workflows/ci-nightly.yml`` on disk."""
    return [dataclasses.replace(g, **transform(g)) if g.job == victim else g for g in real_gates]


def test_shard_workflow_divergence_check_fails_when_a_real_path_is_altered() -> None:
    """Standing Order #5 positive control for PR-BOUNDARY-001: proves
    ``_shard_workflow_divergences`` -- the SAME function the test above
    calls -- actually fails when the committed workflow's parsed path for a
    shard diverges from the roster, without ever touching
    ``.github/workflows/ci-nightly.yml`` on disk. Mutates a SCRATCH copy of
    the real parsed ``Gate`` list (via the shared ``_scratch_gates_with``
    helper) as a stand-in for "someone hand-edited the YAML's pytest path
    arguments"."""
    real_gates = _real_workflow_gates()
    victim = INTERPRETER_SHARDS[0].job_key

    scratch_gates = _scratch_gates_with(real_gates, victim, lambda g: {"paths": [*g.paths, "tests/some/rebalanced/path"]})

    mismatches = _shard_workflow_divergences(scratch_gates, INTERPRETER_SHARDS)
    assert any(victim in m for m in mismatches), (
        f"a path added to the workflow's parsed gate for {victim!r} without touching the roster must surface as a named divergence, got: {mismatches}"
    )


def _scratch_gates_with_marker(real_gates: list[Gate], victim: str, marker_expr: str) -> list[Gate]:
    """Scratch ``Gate`` copy with ``victim``'s marker swapped to
    ``marker_expr``, built on the shared ``_scratch_gates_with`` helper
    (PR-FRESH2-002) -- never touches ``.github/workflows/ci-nightly.yml`` on
    disk."""
    return _scratch_gates_with(real_gates, victim, lambda _g: {"marker_expr": marker_expr})


def test_shard_workflow_divergence_check_tolerates_a_harmless_marker_reorder() -> None:
    """PR-FRESH-001 regression control: a reordered marker expression with
    IDENTICAL pytest semantics to ``"fast or unit"`` must NOT surface as a
    divergence. Demonstrates the red-first case explicitly: the OLD
    comparison this replaced (``real_markers - {"fast or unit"}``, a raw
    literal-string diff) would have false-failed on this exact input --
    asserted inline below, never resurrected as production code -- while
    the current boolean-equivalence truth-table check in
    ``_marker_expr_diverges_from_expected_shard_marker``
    correctly reports no divergence."""
    real_gates = _real_workflow_gates()
    victim = INTERPRETER_SHARDS[0].job_key
    reordered = "unit or fast"

    # Red-first: the retired raw-string comparison this PR replaced WOULD
    # have false-flagged this harmless reorder as an "unexpected marker".
    old_style_bad_markers = {reordered} - {_EXPECTED_SHARD_MARKER_EXPR}
    assert old_style_bad_markers == {reordered}, "sanity check: the old literal-string comparison must treat a reordered marker as unexpected"

    scratch_gates = _scratch_gates_with_marker(real_gates, victim, reordered)
    mismatches = _shard_workflow_divergences(scratch_gates, INTERPRETER_SHARDS)
    assert not any(victim in m for m in mismatches), (
        f"a harmlessly reordered marker with identical pytest semantics must NOT surface as a divergence for {victim!r}, got: {mismatches}"
    )


def test_shard_workflow_divergence_check_fails_when_a_marker_name_is_dropped() -> None:
    """PR-FRESH-001 positive control: dropping ``unit`` from the marker is a
    REAL selection-narrowing change (the shard would stop collecting
    ``unit``-marked tests) and must still surface as a divergence under the
    boolean-equivalence truth-table check."""
    real_gates = _real_workflow_gates()
    victim = INTERPRETER_SHARDS[0].job_key
    narrowed = "fast"

    scratch_gates = _scratch_gates_with_marker(real_gates, victim, narrowed)
    mismatches = _shard_workflow_divergences(scratch_gates, INTERPRETER_SHARDS)
    assert any(victim in m for m in mismatches), (
        f"dropping 'unit' from the marker for {victim!r} is a genuine selection change and must surface as a divergence, got: {mismatches}"
    )


def test_shard_workflow_divergence_check_fails_when_a_marker_exclusion_is_added() -> None:
    """PR-FRESH-001 positive control: adding an ``and not <marker>``
    exclusion is a REAL selection-narrowing change (the shard would stop
    collecting tests carrying that marker) even though it introduces no new
    POSITIVELY-referenced marker name -- must still surface as a divergence
    via the boolean-equivalence truth-table check, which ranges over every
    marker name either expression references, positively or negatively."""
    real_gates = _real_workflow_gates()
    victim = INTERPRETER_SHARDS[0].job_key
    excluding = "fast or unit and not slow"

    scratch_gates = _scratch_gates_with_marker(real_gates, victim, excluding)
    mismatches = _shard_workflow_divergences(scratch_gates, INTERPRETER_SHARDS)
    assert any(victim in m for m in mismatches), (
        f"adding an 'and not slow' exclusion for {victim!r} is a genuine selection change and must surface as a divergence, got: {mismatches}"
    )


# Operator ruling (round-3 FIX, PR-FRESH2-001 / PR-FRESH-001 unresolved): each
# entry is a (marker_expr, expected `diverges`) pair. Every entry is proved
# against the PRODUCTION `_shard_workflow_divergences` in the single test
# below -- never merely asserted, and never resurrected as inline logic.
_MARKER_EQUIVALENCE_TRUTH_TABLE: tuple[tuple[str, bool], ...] = (
    # Harmless reorders/reformats/double-negation: boolean-equivalent to
    # "fast or unit" for every True/False assignment -- must NOT diverge.
    ("unit or fast", False),
    ("(fast or unit)", False),
    ("fast  or  unit", False),
    ("not not (fast or unit)", False),
    # Genuine selection changes -- must diverge.
    ("fast", True),  # drops "unit": narrower (positive-set change)
    ("unit", True),  # drops "fast": narrower (positive-set change)
    ("fast and unit", True),  # "or" swapped for "and": narrower intersection -- PR-FRESH2-001's exact regression
    ("fast or unit and not slow", True),  # adds an "and not slow" exclusion: narrower
    ("fast or unit or slow", True),  # adds "slow" as a third alternative: wider
    ("not (fast or unit)", True),  # full negation: selects the complement entirely
)


def test_shard_workflow_divergence_check_boolean_equivalence_truth_table() -> None:
    """Operator ruling superseding the earlier ``positive_marker_tokens``-set
    remedy: the shard marker check must compare the REAL boolean value of the
    workflow's marker expression against the expected shard marker for EVERY
    True/False assignment of the marker names either references -- not just
    the set of referenced names.

    Red-first, demonstrated inline: PR-FRESH2-001 found that the round-2 fix
    (``positive_marker_tokens``-based positive/negative NAME-set comparison)
    treated ``"fast or unit"`` and ``"fast and unit"`` as equal, because both
    reference the identical name set with identical sign parity -- the
    combinator itself was invisible to that comparison. Demonstrated here via
    the retired helper itself (still exported by ``_gate_coverage``, never
    resurrected as this module's production comparison): both expressions
    produce IDENTICAL positive/negative signatures, which is exactly the
    false-negative this round closes.

    Every row is exercised against the PRODUCTION ``_shard_workflow_divergences``
    over a synthetic scratch ``Gate`` list (via ``_scratch_gates_with_marker``)
    -- the tracked ``.github/workflows/ci-nightly.yml`` is never edited.
    """
    # Red-first demonstration: the retired positive/negative NAME-set
    # comparison cannot distinguish "fast or unit" from "fast and unit" --
    # both signatures are identical, so it would have reported no divergence.
    retired_positive_or = positive_marker_tokens("fast or unit")
    retired_negative_or = positive_marker_tokens("not (fast or unit)")
    retired_positive_and = positive_marker_tokens("fast and unit")
    retired_negative_and = positive_marker_tokens("not (fast and unit)")
    assert retired_positive_or == retired_positive_and, "sanity check: the retired name-set comparison cannot see the or/and combinator swap"
    assert retired_negative_or == retired_negative_and, "sanity check: the retired name-set comparison cannot see the or/and combinator swap"

    real_gates = _real_workflow_gates()
    victim = INTERPRETER_SHARDS[0].job_key

    for marker_expr, expected_diverges in _MARKER_EQUIVALENCE_TRUTH_TABLE:
        scratch_gates = _scratch_gates_with_marker(real_gates, victim, marker_expr)
        mismatches = _shard_workflow_divergences(scratch_gates, INTERPRETER_SHARDS)
        diverges = any(victim in m for m in mismatches)
        assert diverges == expected_diverges, f"marker {marker_expr!r}: expected diverges={expected_diverges}, got {diverges} (mismatches={mismatches})"


# ---------------------------------------------------------------------------
# PR-BOUNDARY-002 (pre-merge squad, severity 3): FR-006's nightly-summary
# ``needs:`` list is a THIRD hand-restatement of shard identity (roster ->
# per-shard `run:` paths -> nightly-summary's `needs:`), with previously
# zero automated coverage tying it to the roster.
# ---------------------------------------------------------------------------


def _nightly_summary_needs() -> list[str]:
    """The REAL ``jobs.nightly-summary.needs`` list, read directly out of
    the committed workflow via the canonical ``load_spliced_workflow``
    helper -- never a second hardcoded copy."""
    data = load_spliced_workflow(NIGHTLY_WORKFLOW)
    jobs = data.get("jobs", {})
    needs = jobs.get("nightly-summary", {}).get("needs", [])
    assert isinstance(needs, list), f"nightly-summary.needs must be a list, got {type(needs)!r}"
    return needs


def _missing_shards_from_needs(needs: list[str], job_keys: tuple[str, ...]) -> set[str]:
    """PRODUCTION comparison for PR-BOUNDARY-002: every roster shard job key
    that is absent from a ``needs:`` list. Both the real test below (the
    REAL ``needs:`` list) and its required mutation test (a scratch
    ``needs:`` list with one key removed) call this SAME function."""
    return set(job_keys) - set(needs)


def test_nightly_summary_needs_includes_every_roster_shard() -> None:
    """PR-BOUNDARY-002/FR-006: the real ``nightly-summary`` job's ``needs:``
    list must name every shard job key the roster declares, derived from
    ``INTERPRETER_SHARD_JOB_KEYS`` -- never a second hardcoded shard-key
    list -- so a future shard rebalance that forgets to update ``needs:``
    fails loudly here."""
    missing = _missing_shards_from_needs(_nightly_summary_needs(), INTERPRETER_SHARD_JOB_KEYS)
    assert not missing, (
        f"nightly-summary.needs is missing shard job key(s) {sorted(missing)} (FR-006 -- a stale or partial "
        "needs: list silently drops that shard's result from the full-mode summary)"
    )


def test_nightly_summary_needs_check_fails_when_a_shard_is_dropped() -> None:
    """Standing Order #5 positive control for PR-BOUNDARY-002: proves
    ``_missing_shards_from_needs`` -- the SAME function the test above
    calls -- actually fails when a roster shard key is absent from
    ``needs:``, without touching ``.github/workflows/ci-nightly.yml`` on
    disk (a scratch ``needs:`` list with one key removed, mirroring
    ``test_roster_diff_fails_when_a_shard_is_deleted_from_the_job_list``'s
    existing scratch-copy pattern)."""
    victim = INTERPRETER_SHARD_JOB_KEYS[0]
    scratch_needs = [key for key in _nightly_summary_needs() if key != victim]

    missing = _missing_shards_from_needs(scratch_needs, INTERPRETER_SHARD_JOB_KEYS)
    assert missing == {victim}, f"removing {victim!r} from nightly-summary.needs must surface as the ONLY missing key, got {missing}"


@functools.cache
def _collect_memo(
    repo_root: Path,
    paths: tuple[str, ...],
    ignores: tuple[str, ...],
    marker_expr: str | None,
) -> tuple[str, ...]:
    """Collect one selection's node-ids ONCE per file (FR-006).

    Keyed on the selection-relevant fields only (``Gate`` is mutable and
    unhashable, and ``gate.job`` does not change what is collected). The value
    is an immutable tuple of node-id strings -- findings, never collected items.
    ``collect_job_nodeids`` is resolved from module globals at CALL time, so a
    test that monkeypatches it still wins.
    """
    gate = Gate(workflow="ci-nightly.yml", job="<memo>", shard=None, paths=list(paths), ignores=list(ignores), marker_expr=marker_expr)
    return tuple(collect_job_nodeids(gate))


def _memo_collect(gate: Gate) -> list[str]:
    """Memoised drop-in for ``collect_job_nodeids`` used by the REAL consumers only."""
    return list(_collect_memo(REPO_ROOT.resolve(), tuple(gate.paths), tuple(gate.ignores), gate.marker_expr))


@pytest.fixture(autouse=True, scope="module")
def _clear_collect_memo() -> Iterator[None]:
    """Bound the memo to this file: nothing outlives it on the worker (FR-006)."""
    yield
    _collect_memo.cache_clear()


@contextlib.contextmanager
def _isolated_collect_memo() -> Iterator[None]:
    """Hand a test an EMPTY memo and leave it EMPTY, however the test ends.

    Every test that seeds or exercises ``_collect_memo`` runs inside this, so a
    real consumer that runs after it in the same process (explicit node ids,
    ``--lf``/``--ff``, reordering) can never be judged against that test's
    synthetic world.
    """
    _collect_memo.cache_clear()
    try:
        yield
    finally:
        _collect_memo.cache_clear()


@pytest.fixture
def isolated_collect_memo() -> Iterator[None]:
    with _isolated_collect_memo():
        yield


def test_no_shard_collects_zero_tests() -> None:
    """FR-005: a shard whose selector collects 0 node-ids fails loudly,
    naming the empty shard -- never a silent pass."""
    empty: list[str] = []
    for shard in INTERPRETER_SHARDS:
        nodeids = _memo_collect(_shard_gate(shard))
        if not nodeids:
            empty.append(shard.job_key)
    assert not empty, f"shard(s) collected 0 tests: {empty} (FR-005 -- a shard must never be silently vacuous)"


def _coverage_completeness_violations(
    shards: tuple[InterpreterShard, ...],
    collect: Callable[[Gate], Sequence[str]] | None = None,
) -> tuple[set[str], set[str], set[str]]:
    """The PRODUCTION coverage-completeness computation for FR-004/NFR-002/SC-003.

    Given a shard roster, collects the full (unsharded) selection and every
    shard's REAL node-id set through the identical ``collect_job_nodeids``
    mechanics, then returns ``(missing_ids, extra_ids, overlap_ids)``.

    Both ``test_shard_union_equals_full_selection_with_zero_gap_and_zero_overlap``
    (called with the REAL ``INTERPRETER_SHARDS`` roster) and the required
    Standing-Order-#5 mutation tests below (called with a mutated roster
    and/or a monkeypatched ``collect_job_nodeids``) call this SAME function --
    a mutation test that never reaches this code cannot prove anything
    (WP01-R1-001).

    ``collect`` defaults to the uncached ``collect_job_nodeids``, resolved from
    module globals at call time so a monkeypatched fake wins. Only the real
    consumer passes the per-file memo (FR-006); the mutation controls never do.
    """
    collect = collect or collect_job_nodeids
    full_ids = set(collect(_FULL_SELECTION_GATE))
    per_shard: dict[str, set[str]] = {shard.job_key: set(collect(_shard_gate(shard))) for shard in shards}

    union_ids: set[str] = set()
    overlap_ids: set[str] = set()
    for ids in per_shard.values():
        overlap_ids |= union_ids & ids
        union_ids |= ids

    missing_ids = full_ids - union_ids
    extra_ids = union_ids - full_ids
    return missing_ids, extra_ids, overlap_ids


def test_shard_union_equals_full_selection_with_zero_gap_and_zero_overlap() -> None:
    """FR-004/NFR-002/SC-003: the coverage-completeness proof.

    Collects the REAL node-id set for the full (unsharded) selection and for
    every shard, then asserts:
    - the union of shard sets equals the full set (zero gap), and
    - no node id is collected by more than one shard (zero overlap).

    On failure, names the specific missing/duplicated node id(s) (spec.md
    Edge Cases).
    """
    missing_ids, extra_ids, overlap_ids = _coverage_completeness_violations(INTERPRETER_SHARDS, collect=_memo_collect)

    assert not missing_ids, f"{len(missing_ids)} node id(s) collected by the full selection but by NO shard: {sorted(missing_ids)[:10]}"
    assert not extra_ids, f"{len(extra_ids)} node id(s) collected by a shard but NOT by the full selection: {sorted(extra_ids)[:10]}"
    assert not overlap_ids, f"{len(overlap_ids)} node id(s) collected by MORE THAN ONE shard: {sorted(overlap_ids)[:10]}"


# ---------------------------------------------------------------------------
# Required mutation tests (Standing Order #5 -- "a gate-unmask cannot
# self-validate"). WP01-R1-001 remedy: these MUST exercise the REAL guard
# path (``_coverage_completeness_violations``, the same function the test
# above calls, over the REAL ``INTERPRETER_SHARDS`` roster) against a
# deliberately mutated input, not a hand-rolled set-arithmetic replica over
# fabricated ids. Real collection is kept cheap by monkeypatching only the
# leaf I/O primitive ``collect_job_nodeids`` with a small deterministic
# node-id world (2 ids per real shard, keyed by the real shard's job_key) --
# the assertion/union/overlap logic under test remains the production code.
# ---------------------------------------------------------------------------


def _synthetic_world_ids(shards: tuple[InterpreterShard, ...]) -> dict[str, set[str]]:
    """A small, realistic-shaped node-id world (2 ids per real shard),
    used only to make the monkeypatched ``collect_job_nodeids`` cheap and
    deterministic for the mutation tests below."""
    return {shard.job_key: {f"tests/unit/test_{shard.job_key}.py::test_a", f"tests/unit/test_{shard.job_key}.py::test_b"} for shard in shards}


def _install_fake_collect_job_nodeids(
    monkeypatch: pytest.MonkeyPatch,
    per_shard_ids: dict[str, set[str]],
    full_ids: set[str],
) -> None:
    """Monkeypatch the module's ``collect_job_nodeids`` reference so
    ``_coverage_completeness_violations`` -- unchanged, real production code
    -- runs against the small synthetic world instead of shelling out to a
    real (slow) pytest collection."""

    def _fake(gate: Gate) -> list[str]:
        if gate.job == _FULL_SELECTION_GATE.job:
            return sorted(full_ids)
        return sorted(per_shard_ids.get(gate.job, set()))

    monkeypatch.setattr(sys.modules[__name__], "collect_job_nodeids", _fake)


def test_coverage_completeness_check_fails_on_a_dropped_test_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """SC-003's required positive control: exercises the REAL
    ``_coverage_completeness_violations`` guard against the REAL
    ``INTERPRETER_SHARDS`` roster, with ``collect_job_nodeids`` monkeypatched
    to a small deterministic world. Dropping one id from a single shard's
    returned set -- while the full-selection gate still reports it -- must
    surface as a real, named gap (not a fabricated replica's own bookkeeping)."""
    per_shard_ids = _synthetic_world_ids(INTERPRETER_SHARDS)
    full_ids: set[str] = set().union(*per_shard_ids.values())

    victim_shard = INTERPRETER_SHARDS[0].job_key
    dropped_id = sorted(per_shard_ids[victim_shard])[0]
    mutated_per_shard_ids = {job_key: (ids - {dropped_id} if job_key == victim_shard else set(ids)) for job_key, ids in per_shard_ids.items()}

    _install_fake_collect_job_nodeids(monkeypatch, mutated_per_shard_ids, full_ids)

    missing_ids, extra_ids, overlap_ids = _coverage_completeness_violations(INTERPRETER_SHARDS)

    assert missing_ids == {dropped_id}, f"the dropped id must surface as a real gap, got {missing_ids}"
    assert not extra_ids
    assert not overlap_ids


def test_coverage_completeness_check_fails_on_a_duplicated_test_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """SC-003's required positive control: exercises the REAL
    ``_coverage_completeness_violations`` guard against the REAL
    ``INTERPRETER_SHARDS`` roster, with ``collect_job_nodeids`` monkeypatched
    to a small deterministic world. Duplicating one id into a SECOND shard's
    returned set must surface as a real, named overlap."""
    per_shard_ids = _synthetic_world_ids(INTERPRETER_SHARDS)
    full_ids: set[str] = set().union(*per_shard_ids.values())

    assert len(INTERPRETER_SHARDS) >= 2, "duplication mutation requires at least two shards"
    shard_a, shard_b = INTERPRETER_SHARDS[0].job_key, INTERPRETER_SHARDS[1].job_key
    duplicated_id = sorted(per_shard_ids[shard_a])[0]
    mutated_per_shard_ids = {job_key: set(ids) for job_key, ids in per_shard_ids.items()}
    mutated_per_shard_ids[shard_b] = mutated_per_shard_ids[shard_b] | {duplicated_id}

    _install_fake_collect_job_nodeids(monkeypatch, mutated_per_shard_ids, full_ids)

    missing_ids, extra_ids, overlap_ids = _coverage_completeness_violations(INTERPRETER_SHARDS)

    assert not missing_ids
    assert not extra_ids
    assert overlap_ids == {duplicated_id}, f"the duplicated id must surface as a real overlap, got {overlap_ids}"


def test_roster_diff_fails_when_a_shard_is_deleted_from_the_job_list() -> None:
    """SC-009's required positive control: a roster-declared shard whose
    ``jobs:`` entry is deleted (in a scratch copy of the real gate list --
    never writing to disk) must be caught, naming that shard -- distinct
    from a present-but-empty shard (FR-005), which this test does NOT cover.
    """
    real_gates = _real_workflow_gates()
    # Scratch copy of the real gates with one roster shard's gate(s) removed,
    # simulating that shard's job being deleted from ci-nightly.yml's jobs:.
    victim = INTERPRETER_SHARDS[0].job_key
    scratch_gates = [g for g in real_gates if g.job != victim]

    target = BaselineTarget(slug=victim, workflow="ci-nightly.yml", job=victim)
    with pytest.raises(RuntimeError, match=victim):
        gates_for_target(scratch_gates, target)


# ---------------------------------------------------------------------------
# FR-006 (ci-runtime-stabilisation, WP13): each distinct selection is collected
# ONCE per file. These tests pin the three properties that make the per-file
# memo safe: duplicate requests compute once, the mutation controls never see a
# memoised real-tree result, and the two REAL consumers actually go through it.
# ---------------------------------------------------------------------------

_SelectionKey = tuple[tuple[str, ...], tuple[str, ...], str | None]


def _selection_key(gate: Gate) -> _SelectionKey:
    return (tuple(gate.paths), tuple(gate.ignores), gate.marker_expr)


def _install_counting_collector(
    monkeypatch: pytest.MonkeyPatch,
    ids_by_selection: dict[_SelectionKey, set[str]],
) -> dict[_SelectionKey, int]:
    """Install a fake ``collect_job_nodeids`` keyed on the SELECTION (never ``gate.job``).

    Returns the live per-selection call counter, so a consumer that bypasses the
    memo shows a count of 2.
    """
    calls: dict[_SelectionKey, int] = {}

    def _counting(gate: Gate) -> list[str]:
        key = _selection_key(gate)
        calls[key] = calls.get(key, 0) + 1
        return sorted(ids_by_selection.get(key, set()))

    monkeypatch.setattr(sys.modules[__name__], "collect_job_nodeids", _counting)
    return calls


def _consistent_fake_world() -> dict[_SelectionKey, set[str]]:
    """Disjoint shards whose union is the full selection, keyed by selection."""
    per_shard = _synthetic_world_ids(INTERPRETER_SHARDS)
    world = {_selection_key(_shard_gate(shard)): per_shard[shard.job_key] for shard in INTERPRETER_SHARDS}
    world[_selection_key(_FULL_SELECTION_GATE)] = set().union(*per_shard.values())
    return world


@pytest.mark.usefixtures("isolated_collect_memo")
def test_collect_memo_invokes_the_collector_once_per_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Equal keys collect once; a different ``ignores`` is a different selection; the value is immutable."""
    key_a = (("tests/unit",), (), "fast or unit")
    key_b = (("tests/unit",), ("tests/unit/slow",), "fast or unit")
    calls = _install_counting_collector(monkeypatch, {key_a: {"a::t"}, key_b: {"b::t"}})

    first = _collect_memo(REPO_ROOT.resolve(), *key_a)
    again = _collect_memo(REPO_ROOT.resolve(), *key_a)
    other = _collect_memo(REPO_ROOT.resolve(), *key_b)

    assert sum(calls.values()) == 2, f"two distinct selections must collect exactly twice, got {calls}"
    assert _collect_memo.cache_info().hits == 1
    assert isinstance(first, tuple)
    assert first == again == ("a::t",)
    assert other == ("b::t",)


@pytest.mark.usefixtures("isolated_collect_memo")
def test_mutation_controls_bypass_the_memo(monkeypatch: pytest.MonkeyPatch) -> None:
    """A warm memo (world A) must never serve the mutation controls (world B)."""
    world_a = _consistent_fake_world()
    _install_counting_collector(monkeypatch, world_a)
    for key in world_a:
        _collect_memo(REPO_ROOT.resolve(), *key)
    assert _collect_memo.cache_info().currsize == len(world_a), "sanity: the memo is warm"

    per_shard_ids = _synthetic_world_ids(INTERPRETER_SHARDS)
    full_ids: set[str] = set().union(*per_shard_ids.values())
    victim = INTERPRETER_SHARDS[0].job_key
    dropped_id = sorted(per_shard_ids[victim])[0]
    world_b = {job_key: (ids - {dropped_id} if job_key == victim else set(ids)) for job_key, ids in per_shard_ids.items()}
    _install_fake_collect_job_nodeids(monkeypatch, world_b, full_ids)

    missing_ids, extra_ids, overlap_ids = _coverage_completeness_violations(INTERPRETER_SHARDS)

    assert missing_ids == {dropped_id}, f"the uncached primitive must report world B's gap, got {missing_ids}"
    assert not extra_ids
    assert not overlap_ids


@pytest.mark.usefixtures("isolated_collect_memo")
@pytest.mark.parametrize("zero_first", [True, False], ids=["zero-test-first", "union-first"])
def test_real_consumers_collect_each_selection_once(monkeypatch: pytest.MonkeyPatch, zero_first: bool) -> None:
    """Production path: the two REAL consumers share one collection per distinct selection, in either order."""
    world = _consistent_fake_world()
    calls = _install_counting_collector(monkeypatch, world)

    if zero_first:
        test_no_shard_collects_zero_tests()
        test_shard_union_equals_full_selection_with_zero_gap_and_zero_overlap()
    else:
        test_shard_union_equals_full_selection_with_zero_gap_and_zero_overlap()
        test_no_shard_collects_zero_tests()

    assert set(calls) == set(world), "every shard gate plus the full-selection gate is collected"
    assert {key: count for key, count in calls.items() if count != 1} == {}, f"a consumer that bypasses the memo collects a selection twice (FR-006): {calls}"


def test_the_isolation_leaves_an_empty_memo_after_a_test_seeds_the_real_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin: a test that warms the memo UNDER THE REAL KEYS leaves nothing behind -- also when it raises."""
    world = _consistent_fake_world()
    _install_counting_collector(monkeypatch, world)
    with _isolated_collect_memo():
        for key in world:
            _collect_memo(REPO_ROOT.resolve(), *key)
        assert _collect_memo.cache_info().currsize == len(world), "sanity: the synthetic world is in the memo"
    assert _collect_memo.cache_info().currsize == 0

    def _seed_then_fail() -> None:
        with _isolated_collect_memo():
            for key in world:
                _collect_memo(REPO_ROOT.resolve(), *key)
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        _seed_then_fail()
    assert _collect_memo.cache_info().currsize == 0, "an erroring test must not leave its world behind either"


# ---------------------------------------------------------------------------
# Order independence of the per-file memo (FR-006 must not weaken the gate).
# A test that warms ``_collect_memo`` under the REAL selection keys with a
# synthetic world must leave it empty, or a real consumer that runs after it in
# the same process (explicit node ids, ``--lf``/``--ff``, reordering) is judged
# against the fake world and the FR-004/FR-005 coverage gate passes vacuously.
# ---------------------------------------------------------------------------

_EMPTY_COLLECTION_PLUGIN = """
def _collects_nothing(gate):
    return []


def pytest_collection_modifyitems(items):
    for module in {item.module for item in items}:
        if hasattr(module, "collect_job_nodeids"):
            module.collect_job_nodeids = _collects_nothing
"""

_THIS_FILE = Path(__file__).as_posix()
_ZERO_TEST_CONSUMER_NODE = f"{_THIS_FILE}::test_no_shard_collects_zero_tests"
_MEMO_SEED_NODES = (
    f"{_THIS_FILE}::test_mutation_controls_bypass_the_memo",
    f"{_THIS_FILE}::test_real_consumers_collect_each_selection_once[zero-test-first]",
    f"{_THIS_FILE}::test_real_consumers_collect_each_selection_once[union-first]",
)


def _run_pytest_with_empty_collection(tmp_path: Path, *node_ids: str) -> subprocess.CompletedProcess[str]:
    """Run ``node_ids`` in ONE fresh pytest process whose real collector finds nothing (a real FR-005 violation)."""
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    (plugin_dir / "empty_collection_plugin.py").write_text(_EMPTY_COLLECTION_PLUGIN, encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(plugin_dir), str(REPO_ROOT)])}
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "empty_collection_plugin", "-p", "no:cacheprovider", "-o", "addopts=", "-q", "-rf", *node_ids],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def test_an_empty_real_collection_still_fails_the_zero_test_consumer_alone(tmp_path: Path) -> None:
    """Control: with a collector that finds nothing the real consumer is red on its own (the harness is not vacuous)."""
    result = _run_pytest_with_empty_collection(tmp_path, _ZERO_TEST_CONSUMER_NODE)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "collected 0 tests" in result.stdout, result.stdout


@pytest.mark.parametrize("seed_node", _MEMO_SEED_NODES, ids=lambda node: node.split("::", 1)[1])
def test_a_memo_seeding_test_cannot_green_wash_a_following_real_consumer(tmp_path: Path, seed_node: str) -> None:
    """FR-006 regression: seed-test THEN real consumer, one process -- the consumer must still go red."""
    result = _run_pytest_with_empty_collection(tmp_path, seed_node, _ZERO_TEST_CONSUMER_NODE)

    assert result.returncode == 1, f"the consumer was served the seed test's fake world and passed on a real violation:\n{result.stdout}{result.stderr}"
    assert re.search(r"^FAILED \S+::test_no_shard_collects_zero_tests", result.stdout, re.MULTILINE), result.stdout
