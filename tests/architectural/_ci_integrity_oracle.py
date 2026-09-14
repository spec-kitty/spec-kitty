"""CI-integrity (collection-completeness) oracle — WP17 / FR-016 / #2967.

The collection-completeness / two-authority integrity oracle, rebuilt against
the **real on-disk** reinstated ``.github/workflows/ci-router.yml``. It answers
one question — *is any change-class silently gated by nothing?* — and it answers
it **through the single gate-selection authority** (``scripts/ci/gate_selection``),
never by re-parsing the workflow YAML itself. That single-authority reuse is the
whole point of FR-016 / #2476: one parser, one answer, no drift. This module has
no ``yaml`` import for exactly that reason.

What the oracle proves, and what it deliberately does NOT:

* **Proves WIRING.** For every src-backed routing group, a representative change
  confined to that group must select at least one code-scoped gate (a test shard
  or the heavy architectural battery). A group that selects none is *zero-gated*:
  a ``src/`` path a change can touch that routes to no test/arch job — the exact
  "untested-but-green" hole this oracle exists to forbid. It also asserts the
  enumerated must-run gates (the always-on lint/regen/terminology/layer gates and
  the code-scoped heavy battery) are wired in the reinstated topology (SC-004).

* **Does NOT prove RUNTIME.** ``RUNTIME_EVIDENCE_BOUNDARY`` states it plainly:
  the oracle proves a gate is *wired*, never that it *ran green*. Each gate's
  runtime execution is evidenced by its own job result (SC-004). The oracle reads
  no job result/conclusion and shells out to nothing, so it can never over-claim
  runtime green from static wiring.

**Non-vacuity (DIR-043).** The oracle fails closed if it evaluates an empty set:
a router with no src-backed routing group raises :class:`OracleVacuousError`
rather than passing because it checked nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scripts.ci.gate_selection import load_router, select_gates

if TYPE_CHECKING:
    from scripts.ci.gate_selection import Router

__all__ = [
    "HEAVY_BATTERY_GATE",
    "MUST_RUN_ALWAYS_ON_GATES",
    "RUNTIME_EVIDENCE_BOUNDARY",
    "MustRunGateUnwiredError",
    "OracleVacuousError",
    "ZeroGatedGroupError",
    "assert_must_run_gates_wired",
    "assert_no_zero_gated_group",
    "build_group_gate_map",
    "load_router",
    "representative_path",
    "zero_gated_groups",
]

#: The runtime-vs-static boundary (T093 / SC-004), stated as a load-bearing
#: constant so a reader — or a guard test — can pin it: the oracle proves a gate
#: is WIRED; a gate's RUNTIME execution is evidenced by its own job result, never
#: inferred from this static wiring proof.
RUNTIME_EVIDENCE_BOUNDARY = (
    "This oracle proves WIRING only: that every change-class selects at least one "
    "gate and that the enumerated must-run gates are wired. A gate's RUNTIME "
    "execution (did it actually run and pass) is evidenced by that gate's own CI "
    "job result (SC-004) and is never inferred from this static wiring proof."
)

#: Enumerated always-on must-run gates (SC-004): the cheapest gates that
#: must run on every change regardless of path. Names are ``ci-router.yml``
#: job keys. These carry NO filter group — they are always-on by construction.
#: ``archive-freeze`` (#4365) is here so a docs-only PR that rewrites archived
#: dossiers can never again merge without meeting the archive freeze — the
#: gap #4260 slipped through (the heavy battery is code-scoped).
MUST_RUN_ALWAYS_ON_GATES = frozenset(
    {
        "ruff",
        "import-linter",
        "regen-check",
        "terminology",
        "layer-rules",
        "archive-freeze",
    },
)

#: The heavy architectural battery gate: code-scoped, gated over exactly the
#: src-backed routing groups (contract router-two-authority §"Derived").
HEAVY_BATTERY_GATE = "architectural-heavy"


class OracleVacuousError(AssertionError):
    """The oracle was asked to evaluate an empty set (DIR-043 non-vacuity floor)."""


class ZeroGatedGroupError(AssertionError):
    """A src-backed routing group selects no code-scoped gate (a coverage hole)."""


class MustRunGateUnwiredError(AssertionError):
    """An enumerated must-run gate is absent or mis-wired in the topology."""


def representative_path(globs: tuple[str, ...]) -> str:
    """A concrete ``src/`` path standing in for a routing group's globs.

    Picks the group's first ``src/`` glob and materializes it into a concrete
    path the gate-selection authority can match (``**``/``*`` → a probe file),
    so a group can be exercised through :func:`scripts.ci.gate_selection.select_gates`
    exactly as a real diff would be routed. A group with no ``src/`` glob is not a
    src-backed group and is never passed here.
    """
    for glob in globs:
        if not glob.startswith("src/"):
            continue
        if "**" in glob:
            return glob.replace("**", "probe.py")
        if "*" in glob:
            return glob.replace("*", "probe")
        return glob
    msg = f"routing group has no src/ glob to build a representative path from: {globs!r}"
    raise ValueError(msg)


def build_group_gate_map(router: Router) -> dict[str, frozenset[str]]:
    """Map every src-backed routing group → the code-scoped gates it selects.

    Derived purely through the single ``select_gates`` authority (no second
    parser): a representative change confined to each group is routed exactly as
    CI would route it, and the group is mapped to the resulting
    ``selected_code_shards``. This is the "test→gate selection map" the
    completeness assertion reasons over.
    """
    return {
        group: select_gates(
            [representative_path(router.filters[group])],
            router=router,
            mode="pr",
        ).selected_code_shards
        for group in sorted(router.src_backed_groups)
    }


def zero_gated_groups(router: Router) -> frozenset[str]:
    """The src-backed groups whose representative change selects no code gate.

    A non-empty result is a live coverage hole: a ``src/`` change-class that
    routes to no test/arch job.
    """
    return frozenset(group for group, gates in build_group_gate_map(router).items() if not gates)


def _require_non_vacuous(router: Router) -> None:
    """Fail closed if there is nothing to evaluate (DIR-043)."""
    if not router.src_backed_groups:
        msg = (
            "CI-integrity oracle evaluated an EMPTY set of src-backed routing "
            "groups — a vacuous pass that checks nothing is the exact defect "
            "FR-016 closes. The parsed router has no src-backed group."
        )
        raise OracleVacuousError(msg)


def assert_no_zero_gated_group(router: Router) -> None:
    """Assert no src-backed routing group is zero-gated (the completeness core).

    Raises :class:`OracleVacuousError` if the router has no src-backed group to
    evaluate (non-vacuity floor), and :class:`ZeroGatedGroupError` if any group
    routes to no code-scoped gate.
    """
    _require_non_vacuous(router)
    orphans = zero_gated_groups(router)
    if orphans:
        msg = (
            "src-backed routing group(s) select no code-scoped gate — a change "
            f"confined to them routes to no test/arch job: {sorted(orphans)}. "
            "Gate them on a code shard or the heavy architectural battery."
        )
        raise ZeroGatedGroupError(msg)


def assert_must_run_gates_wired(router: Router) -> None:
    """Assert the enumerated must-run gates are wired (SC-004).

    The always-on gates in :data:`MUST_RUN_ALWAYS_ON_GATES` must be present AND
    carry no filter group (they run on every change), and the heavy architectural
    battery must be code-scoped over EXACTLY the src-backed routing groups — the
    OR-list of authority #2 equals the parsed authority #1 src-backed set
    (contract router-two-authority §"Derived").
    """
    _require_non_vacuous(router)

    missing_always_on = MUST_RUN_ALWAYS_ON_GATES - router.always_on_jobs
    if missing_always_on:
        msg = (
            "enumerated always-on must-run gate(s) are not wired as always-on in "
            f"the reinstated topology: {sorted(missing_always_on)}. Each must be a "
            "job that carries no filter group so it runs on every change."
        )
        raise MustRunGateUnwiredError(msg)

    if HEAVY_BATTERY_GATE not in router.code_shard_jobs:
        msg = f"the heavy architectural battery gate {HEAVY_BATTERY_GATE!r} is not wired as a code-scoped gate in the reinstated topology (SC-004)."
        raise MustRunGateUnwiredError(msg)

    heavy_groups = router.job_gates.get(HEAVY_BATTERY_GATE, frozenset())
    if heavy_groups != router.src_backed_groups:
        msg = (
            "the heavy architectural battery must be gated over EXACTLY the "
            "src-backed routing groups (authority #2 OR-list == authority #1 "
            "src-backed set). Mismatch — only-in-if: "
            f"{sorted(heavy_groups - router.src_backed_groups)}; "
            f"only-in-filters: {sorted(router.src_backed_groups - heavy_groups)}."
        )
        raise MustRunGateUnwiredError(msg)
