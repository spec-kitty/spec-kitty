"""Regression guard for the ``ci`` module wiring (spec-kitty#4386).

``tests/ci`` — the guard suites for ``scripts/ci/`` and the CI workflows it
feeds, including the credential-holding ``sonar-pr`` path — was claimed by no
``.github/ci-module-registry.yml`` row, so no per-PR job ever selected it: the
only lane reaching it was ``ci-nightly.yml``'s scheduled, fail-soft interpreter
sweep. These tests pin the three-part wiring that closed that gap, so it cannot
silently rot back:

1. the registry carries a ``ci`` row claiming ``tests/ci`` — its per-PR
   executor is the ``ci-modules.yml`` module matrix, which runs on every PR
   and fails the PR on a regression in these suites;
2. the scrub (``tests/release/ci_retirement_scrub.json``) carries the matching
   group with the same roots/cov_targets — the registry consumes ``groups[]``
   rows verbatim, so a divergent row is a re-scrub;
3. ``ci-router.yml`` names the CI-infrastructure paths as the ``ci`` filter
   group — a ``scripts/ci``-only or workflow-only diff ROUTES (matches a named
   group) instead of silently matching nothing — while staying OUTSIDE the
   FR-004 fail-closed catch-all (that sensor is contractually unmapped
   ``src/**`` code, ``contracts/router-two-authority.md`` Invariants 1-2) and
   gating no router job (the module matrix is the executor; a router
   ``tests (ci)`` job would double-run the suite per PR, the duplicate class
   ``tests/architectural/test_no_duplicate_suite_execution.py`` exists to
   remove).

This file lives in ``tests/ci`` on purpose: it runs via the ``ci`` module
shard on every PR — including a PR that touches ONLY CI-infrastructure paths,
which is exactly the PR shape whose wiring it guards. The architectural
battery's heavy job is gated on src-backed groups, so it would skip such a PR.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci.gate_selection import Router, load_router, select_gates

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY_PATH = _REPO_ROOT / ".github" / "ci-module-registry.yml"
_SCRUB_PATH = _REPO_ROOT / "tests" / "release" / "ci_retirement_scrub.json"

_MODULE = "ci"
_ROOTS = ["scripts/ci/**", ".github/workflows/**"]
_TEST_DIRS = ["tests/ci"]


def _registry_rows() -> list[dict[str, Any]]:
    payload = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8"))
    return list(payload["modules"])


def _ci_row() -> dict[str, Any]:
    rows = [row for row in _registry_rows() if row.get("module") == _MODULE]
    assert len(rows) == 1, f"expected exactly one {_MODULE!r} registry row, found {len(rows)}"
    return rows[0]


@pytest.fixture(scope="module")
def router() -> Router:
    return load_router()


# ---------------------------------------------------------------------------
# (1) the registry row — tests/ci's per-PR executor
# ---------------------------------------------------------------------------
def test_registry_ci_row_claims_tests_ci() -> None:
    """The `ci` row exists and claims exactly tests/ci as its test directory."""
    row = _ci_row()
    assert list(row["roots"]) == _ROOTS, "the ci row's roots must be the CI-infrastructure paths"
    assert list(row["test_dirs"]) == _TEST_DIRS, "the ci row must claim tests/ci explicitly"
    assert isinstance(row["shard_count"], int) and row["shard_count"] >= 1
    assert list(row["cov_targets"]), "registry rows require a non-empty cov_targets ownership declaration"


def test_registry_ci_row_is_measured_not_guessed() -> None:
    """shard_count is backed by recorded per-test durations for the ci module.

    The registry's own rule (WP08 T042/NFR-005): shard_count comes from greedy
    LPT over the MEASURED per-test durations in ci-shard-timings.json, never
    from file counts. A row with no recorded durations is a guessed count, and
    the three parallel per-module tables must stay in lockstep (a count that
    disagrees with the duration list is stale data -- the defect
    ``scripts/ci/capture_shard_timings.py``'s merge exists to close).
    """
    _ci_row()  # the row must exist; the rest of the wiring is pinned by the other tests
    timings = json.loads((_REPO_ROOT / ".github" / "ci-shard-timings.json").read_text(encoding="utf-8"))
    durations = timings["module_test_durations"][_MODULE]
    assert durations, "no measured per-test durations recorded for the ci module"
    count = timings["module_test_count"][_MODULE]
    assert count == len(durations), "module_test_count disagrees with module_test_durations for the ci module"
    provenance = timings["module_capture_provenance"][_MODULE]
    assert provenance["producer"] == "scripts/ci/capture_shard_timings.py", (
        "the ci module's durations must come from the reproducible capture producer, never a hand-edit"
    )


# ---------------------------------------------------------------------------
# (2) the scrub group — the registry consumes it verbatim
# ---------------------------------------------------------------------------
def test_scrub_carries_the_ci_group_verbatim() -> None:
    """The scrub's ci group matches the registry row's roots/cov_targets."""
    scrub = json.loads(_SCRUB_PATH.read_text(encoding="utf-8"))
    groups = [g for g in scrub["groups"] if g.get("group") == _MODULE]
    assert len(groups) == 1, f"expected exactly one {_MODULE!r} scrub group, found {len(groups)}"
    row = _ci_row()
    assert list(groups[0]["roots"]) == list(row["roots"]), "registry ci row roots diverge from the scrub group (re-scrub)"
    assert list(groups[0]["cov_targets"]) == list(row["cov_targets"]), "registry ci row cov_targets diverge from the scrub group (re-scrub)"


# ---------------------------------------------------------------------------
# (3) the router group — the paths route, and the two deliberate exclusions
# ---------------------------------------------------------------------------
def test_ci_infra_only_diffs_route_to_the_named_group(router: Router) -> None:
    """scripts/ci-only and workflow-only diffs match the named `ci` group.

    Before #4386 these path families matched NO filter group -- a PR rewriting
    a workflow, the script it runs, and the tests guarding both selected zero
    routing groups and zero code shards, so nothing path-visible in the router
    even noticed the change.
    """
    for paths in (
        ["scripts/ci/gate_selection.py"],
        ["scripts/ci/fleet_verdict.py", "scripts/ci/sonar_pr_analysis.py"],
        [".github/workflows/ci-aggregate.yml"],
        [".github/workflows/sonar.yml", "scripts/ci/sonarcloud_branch_review.sh"],
    ):
        selection = select_gates(paths, router=router)
        assert selection.matched_groups == frozenset({_MODULE}), (
            f"a CI-infrastructure diff {paths} must route to the named {_MODULE!r} group, got {sorted(selection.matched_groups)}"
        )
        assert not selection.unmatched_src, "CI-infrastructure paths are not src and must never trip the src catch-all"


def test_ci_group_gates_no_router_job_and_stays_out_of_the_catch_all(router: Router) -> None:
    """The two deliberate exclusions recorded in #4386, pinned.

    * the group is non-src, so it stays out of the FR-004 fail-closed
      ``unmatched`` union (the catch-all is the sensor for unmapped src/**
      CODE; these paths are now named);
    * no ci-router.yml job gates on it — the per-PR executor is the
      ci-modules.yml module matrix, which runs on every PR; a router
      ``tests (ci)`` job would double-run the suite per PR.

    This pin is the other half of the FR-003b exemption: the workflow-coherence
    guard (tests/architectural/test_workflow_coherence.py) exempts the ``ci``
    group from its "every filter group gates a job" rule via
    ``_DELIBERATELY_UNGATED_FILTER_GROUPS`` precisely because THIS test keeps
    the group's routing live and asserted — the exemption is only safe while
    this file pins what the group does instead of gating.
    """
    assert _MODULE not in router.src_backed_groups, "the ci group is CI infrastructure, not src code"
    gated = sorted(job for job, groups in router.job_gates.items() if _MODULE in groups)
    assert not gated, (
        f"ci-router.yml job(s) {gated} gate on the ci group -- the per-PR executor for tests/ci is the "
        "ci-modules.yml module matrix (it runs on every PR); a router job would double-run the suite per PR"
    )


def test_ci_infra_diff_alongside_src_change_keeps_the_src_routing(router: Router) -> None:
    """A mixed CI-infra + src diff selects both families' routing unchanged."""
    selection = select_gates(["scripts/ci/gate_selection.py", "src/specify_cli/merge/executor.py"], router=router)
    assert selection.matched_groups == frozenset({"ci", "merge"})
    assert "tests-merge" in selection.selected_code_shards
    assert not selection.unmatched_src
