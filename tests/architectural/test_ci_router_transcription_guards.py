"""Guards that pin ``ci-router.yml``'s hand-authored transcriptions to their
single sources of truth.

The router (``.github/workflows/ci-router.yml``) hand-transcribes the same group
information into three load-bearing places, and before this file only one edge
was guarded:

1. The dorny ``changes`` **filter** block (``group -> globs``) is meant to derive
   from ``tests/release/ci_retirement_scrub.json`` (``groups[].roots``). The
   module registry already pins that derivation
   (``test_module_shard_registry.py::test_registry_consumes_scrub_verbatim_no_divergent_rescrub``),
   but the router's own filter block had **no** twin guard — a third,
   unguarded copy of the scrub SSOT (squad finding paula-patterns F1).
2. The ``changes`` job's **outputs** block re-lists every routing group. Nothing
   asserted it covered the filter groups, so a group added to the filters + a
   gated job but omitted from ``outputs`` would resolve ``needs.changes.outputs
   .<group>`` to ``''`` at runtime — the gated job silently skipped, ``unmatched``
   never tripped: zero code gates, green (squad finding architect-alphonso M1 —
   a latent re-entry of the #2967 zero-producer class).
3. The FR-004 fail-closed ``unmatched`` bash step hand-lists the src-backed
   groups it unions. A group dropped from that loop weakens the fail-closed
   catch-all (squad finding architect-alphonso m2 — fail-*safe*, but still an
   unguarded transcription).

All three are consumed as routing truth by the single ``gate_selection.load_router``
authority, the WP17 integrity oracle, and the WP18 local parity check, so a drift
between the router and its declared sources silently desyncs "one authority" from
the SSOT it claims to derive from. These guards close edges (1)-(3) so every
router transcription is pinned, matching the guarantee the mission's own contract
makes for the module registry.

Added post-mission by the #3995 landing pass (squad folds paula-F1 /
alphonso-M1 / alphonso-m2).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci.gate_selection import PROBE_GROUPS, Router, load_router

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ROUTER_PATH = _REPO_ROOT / ".github" / "workflows" / "ci-router.yml"
_SCRUB_PATH = _REPO_ROOT / "tests" / "release" / "ci_retirement_scrub.json"

_FILTER_OUTPUT_REF = re.compile(r"steps\.filter\.outputs\.([a-z0-9_]+)")


def _router_workflow() -> dict[str, Any]:
    return yaml.safe_load(_ROUTER_PATH.read_text(encoding="utf-8"))


def _scrub_roots_by_group() -> dict[str, list[str]]:
    scrub = json.loads(_SCRUB_PATH.read_text(encoding="utf-8"))
    return {g["group"]: list(g["roots"]) for g in scrub["groups"]}


def _src_backed_scrub_groups(scrub_roots: dict[str, list[str]]) -> set[str]:
    """Scrub ``groups`` entries carrying at least one ``src/`` root glob.

    spec-kitty#4386 added the first NON-src group to ``groups`` (``ci``, roots
    ``scripts/ci/**`` + ``.github/workflows/**``) so the module registry — which
    consumes ``groups`` rows verbatim — could give tests/ci a per-PR executor.
    The src-backed half of the derivation guard below is scoped to this subset,
    exactly like the router's own ``src_backed_groups`` property.
    """
    return {group for group, roots in scrub_roots.items() if any(str(root).startswith("src/") for root in roots)}


def _changes_output_groups(workflow: dict[str, Any]) -> set[str]:
    """Routing groups declared in the ``changes`` job ``outputs`` block.

    ``unmatched`` is the raw fail-closed signal, not a routing group.
    """
    outputs = set(workflow["jobs"]["changes"]["outputs"].keys())
    return outputs - {"unmatched"}


def _unmatched_union_groups(workflow: dict[str, Any]) -> set[str]:
    """The src-backed groups the fail-closed ``unmatched`` step unions.

    The step references ``steps.filter.outputs.<group>`` once per group inside its
    ``for group_hit in ...`` loop (``any_src`` lives in the step ``env``, not the
    ``run`` body, so it is not counted here).
    """
    steps = workflow["jobs"]["changes"]["steps"]
    unmatched = next(step for step in steps if step.get("id") == "unmatched")
    return set(_FILTER_OUTPUT_REF.findall(unmatched["run"]))


# ---------------------------------------------------------------------------
# (1) paula-F1 — the router filter block derives from the scrub SSOT
# ---------------------------------------------------------------------------
def test_router_src_filters_derive_from_scrub_verbatim() -> None:
    """Every scrub group's router filter globs equal its scrub roots, verbatim.

    This is the router twin of the registry's
    ``test_registry_consumes_scrub_verbatim_no_divergent_rescrub`` guard: the
    router must consume ``ci_retirement_scrub.json``, not re-scrub. Ordered
    comparison, matching the registry guard's semantics.

    Since spec-kitty#4386 the scrub's ``groups`` list carries one NON-src group
    (``ci`` — the CI-infrastructure paths, so tests/ci could gain a module
    registry row). The guard keeps its exact pre-#4386 strength for the
    src-backed half (set equality + per-group glob equality) and extends the
    per-group verbatim pinning to every scrub group the router transcribes,
    src-backed or not: a non-src scrub group's router globs must equal its
    scrub roots just as strictly, and no scrub group may be missing from the
    router's filter block.
    """
    router = load_router()
    scrub_roots = _scrub_roots_by_group()

    src_groups = set(router.src_backed_groups)
    src_backed_scrub = _src_backed_scrub_groups(scrub_roots)
    assert src_groups == src_backed_scrub, (
        "router src-backed groups diverge from the scrub's src-backed group set — "
        f"only-in-router={sorted(src_groups - src_backed_scrub)}, "
        f"only-in-scrub={sorted(src_backed_scrub - src_groups)}"
    )

    # Every scrub groups[] row — src-backed or not — must be transcribed into
    # the router's filter block (a scrub group the router never declares is a
    # silent coverage hole in the path->group mapping).
    untranscribed = sorted(set(scrub_roots) - set(router.filters))
    assert not untranscribed, f"scrub groups absent from the router filter block: {untranscribed}"

    problems = [
        f"group {group!r}: router globs {list(router.filters[group])} != scrub roots {scrub_roots[group]}"
        for group in sorted(set(scrub_roots) & set(router.filters))
        if list(router.filters[group]) != scrub_roots[group]
    ]
    assert not problems, "router filter block re-scrubs instead of consuming the scrub verbatim:\n" + "\n".join(problems)


# ---------------------------------------------------------------------------
# (2) architect-alphonso M1 — outputs cover every routing group
# ---------------------------------------------------------------------------
def test_changes_outputs_cover_every_routing_group() -> None:
    """``changes.outputs`` (minus ``unmatched``) equals the filter routing groups.

    A gated job references ``needs.changes.outputs.<group>``; a routing group in
    the filters + a job ``if:`` but missing from ``outputs`` resolves to ``''`` at
    runtime — the job skips and ``unmatched`` never fires, selecting zero gates
    while the completeness oracle (which reads filters + job ``if:``, not the
    outputs block) still reports the group covered. Pin the outputs block so that
    latent zero-gate path cannot open.
    """
    workflow = _router_workflow()
    router = load_router()

    declared = _changes_output_groups(workflow)
    routing = set(router.routing_groups)
    assert declared == routing, (
        "changes.outputs is out of sync with the filter routing groups — "
        f"only-in-outputs={sorted(declared - routing)}, "
        f"only-in-filters={sorted(routing - declared)}"
    )


# ---------------------------------------------------------------------------
# (3) architect-alphonso m2 — the fail-closed union covers every src group
# ---------------------------------------------------------------------------
def test_unmatched_union_covers_every_src_backed_group() -> None:
    """The FR-004 ``unmatched`` step unions exactly the src-backed groups.

    A src-backed group dropped from the loop lets an unmapped ``src/**`` change
    escape the fail-closed catch-all when that group happens to match — weakening
    the run-all guarantee (fail-*safe*, but still a silent transcription drift).
    """
    workflow = _router_workflow()
    router = load_router()

    union = _unmatched_union_groups(workflow)
    src = set(router.src_backed_groups)
    assert union == src, (
        f"the unmatched fail-closed union diverges from the src-backed groups — only-in-loop={sorted(union - src)}, only-in-src-groups={sorted(src - union)}"
    )


# ---------------------------------------------------------------------------
# Non-vacuity: each guard actually reds under a manufactured drift
# ---------------------------------------------------------------------------
def test_guards_are_non_vacuous() -> None:
    """A manufactured drift in each transcription is caught by the guard logic.

    Proves the three guards above are real bounds, not tautologies that would pass
    against any router.
    """
    router = load_router()
    scrub_roots = _scrub_roots_by_group()
    workflow = _router_workflow()

    a_src_group = next(iter(sorted(router.src_backed_groups)))

    # (1) drift the router filter globs for one src group away from the scrub.
    drifted_filters = dict(router.filters)
    drifted_filters[a_src_group] = ("src/DRIFTED/**",)
    drifted_router = Router(filters=drifted_filters, job_gates=router.job_gates)
    assert list(drifted_router.filters[a_src_group]) != scrub_roots[a_src_group]

    # (2) drop a routing group from the outputs block.
    drifted_outputs = _changes_output_groups(workflow) - {a_src_group}
    assert drifted_outputs != set(router.routing_groups)

    # (3) drop a src group from the unmatched union.
    drifted_union = _unmatched_union_groups(workflow) - {a_src_group}
    assert drifted_union != set(router.src_backed_groups)

    # Sanity: the probe group is never a routing group (guards exclude it).
    assert PROBE_GROUPS.isdisjoint(router.routing_groups)


# ---------------------------------------------------------------------------
# (4) push-is-diff-based (mission ci-modules-diff-scoping): pin the removal of
# the old `github.event_name == 'push' ||` run-all clause from every
# `changes.outputs.*` expression, so push-to-main stays path-scoped like a PR
# and cannot silently regress back to always-full-scope. The nightly full
# module-matrix run (ci-nightly.yml) is the cross-module post-merge safety net
# that replaced push-always-full-scope.
# ---------------------------------------------------------------------------
def test_changes_outputs_never_force_run_all_on_push() -> None:
    """`changes.outputs.*` must only fold in run-all for `inputs.mode == 'full'`
    or the FR-004 fail-closed `unmatched` catch-all -- never for
    `github.event_name == 'push'`. A reintroduction of that clause would make
    every push-to-main run the full module matrix again, defeating the
    diff-based scoping this guard pins."""
    workflow = _router_workflow()
    outputs = workflow["jobs"]["changes"]["outputs"]
    routing_groups_outputs = {name: expr for name, expr in outputs.items() if name != "unmatched"}
    assert routing_groups_outputs, "expected at least one routing-group output to check"
    offenders = {name: expr for name, expr in routing_groups_outputs.items() if "github.event_name" in str(expr) and "push" in str(expr)}
    assert not offenders, f"changes.outputs must not force run-all on push (mission ci-modules-diff-scoping) -- offending outputs: {offenders}"
