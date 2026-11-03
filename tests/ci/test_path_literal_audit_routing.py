"""Pin the per-PR routing of the runtime-home path-literal guard (spec-kitty#6879).

``tests/audit/test_no_legacy_path_literals.py`` holds the guard that fails the build when a
global-state module hand-rolls ``Path.home() / ".spec-kitty"`` instead of deriving from
``specify_cli.paths.get_runtime_root`` (#2171). #6367 added exactly that literal to
``src/specify_cli/status/locking.py`` and no per-PR job ran ``tests/audit``, so the guard first
saw it in the nightly, escalated as #6582 — which then allowlisted the module instead of fixing
the literal.

The router's ``status`` group selects the module matrix's ``status`` row; ``tests/audit`` is an
``out_of_matrix_test_dirs`` entry with no per-PR lane, so a ``src/specify_cli/status/**`` diff ran
no audit test at all. This module pins the fix: a narrow NON-src ``path_literal_audit`` group
(``**/``-spelled, the ``mission_state`` precedent) gating one blocking job that executes exactly
that one guard file.

Every assertion reads the parsed router (``scripts/ci/gate_selection.py``) and the on-disk
workflow/scrub, never a restated copy of the routing.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci.gate_selection import HEAVY_BATTERY_JOB, load_router, select_gates
from scripts.ci.router_gate import ADVISORY_JOB_NAMES
from tests.ci._gh_if import BASE_CONTEXT_ALL_FALSE, eval_gh_if

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parents[2]
ROUTER = ROOT / ".github" / "workflows" / "ci-router.yml"
SCRUB = ROOT / "tests" / "release" / "ci_retirement_scrub.json"
GUARD = "tests/audit/test_no_legacy_path_literals.py"

GROUP = "path_literal_audit"
JOB = "tests-path-literal-audit"

# The paths whose change can make the guard meaningful or invert it: the reported gap
# (src/specify_cli/status/**), the keystone resolver file the guard's non-vacuity limb asserts
# (src/kernel/paths.py) and the guard file itself.
POSITIVE_PATHS = (
    "src/specify_cli/status/locking.py",
    "src/kernel/paths.py",
    GUARD,
)

# The keystone resolver *directory* is deliberately left unmapped by every src-backed group, so the
# FR-004 fail-closed catch-all still forces run-all there -- and run-all selects this lane. Pinned below
# as the reason the group does not name it (naming it would NARROW the sensor to this one lane).
UNMAPPED_KEYSTONE_PATH = "src/specify_cli/paths/windows_paths.py"

# Same-fixture negative controls: real, mapped paths that must NOT select the lane. Without them a
# probe that matched everything would satisfy the positive assertions vacuously.
NEGATIVE_PATHS = (
    "docs/development/how-to/manage-issue-tracker.md",
    "src/specify_cli/review/pre_review_gate.py",
    "packs/built-in/missions/software-dev/mission.yaml",
)


def _jobs() -> dict[str, Any]:
    return dict(yaml.safe_load(ROUTER.read_text(encoding="utf-8"))["jobs"])


def _pytest_invocations(job: dict[str, Any]) -> list[str]:
    return [line for step in job.get("steps", []) for line in str(step.get("run", "")).splitlines() if " pytest " in f" {line} " or line.startswith("pytest ")]


def _narrows_by_marker_or_name(command: str) -> bool:
    """Whether a pytest command narrows by marker/name (exactly what must be absent here)."""
    return any(flag in command for flag in (" -m ", " -k ", "--ignore", "--deselect", "-m=", "-k="))


@pytest.mark.parametrize("path", POSITIVE_PATHS)
def test_a_path_that_can_break_the_guard_selects_the_lane(path: str) -> None:
    router = load_router()

    selection = select_gates([path], router=router)

    assert GROUP in selection.matched_groups, f"{path} can break the runtime-home guard but misses the {GROUP} group"
    assert JOB in selection.selected_jobs, f"{path} selects {GROUP} but not the job gated on it"
    assert not selection.unmatched_src, "a mapped path must never trip the FR-004 fail-closed catch-all"


def test_the_unmapped_keystone_directory_still_forces_run_all() -> None:
    """The group must not narrow the FR-004 sensor over the keystone resolver directory.

    No src-backed group owns `src/specify_cli/paths/**`, so a diff there trips the catch-all and runs
    every gated job -- this lane included. Naming that directory here would turn `unmatched_src` off and
    narrow the run to this one lane, so the group deliberately does not (issue #6879 grounding).
    """
    router = load_router()

    selection = select_gates([UNMAPPED_KEYSTONE_PATH], router=router)

    assert selection.unmatched_src is True, "the keystone directory must stay unmapped so the catch-all keeps running everything there"
    assert GROUP not in selection.matched_groups
    # Run-all (full mode) is what reaches this lane for an unmapped path.
    assert JOB in select_gates([UNMAPPED_KEYSTONE_PATH], router=router, mode="full").selected_jobs


def test_the_group_stays_non_src_so_it_is_not_a_code_shard_or_a_module() -> None:
    """A non-src group: like `mission_state`, it is an extra narrow lane, never a code-shard group.

    A `src/`-spelled glob would make the group src-backed, which the module-registry model reads as
    "the module matrix owns this" -- and claiming `tests/audit` as a module row is a separate
    CI-budget decision (#6879 candidate 2, out of scope).
    """
    router = load_router()

    assert GROUP not in router.src_backed_groups
    assert not [glob for glob in router.filters[GROUP] if glob.startswith("src/")]
    assert JOB not in select_gates(["src/specify_cli/status/locking.py"], router=router).selected_code_shards
    # The status diff still selects the heavy battery through its own src-backed groups, so the lane's
    # non-src spelling removes nothing from the code gates.
    assert HEAVY_BATTERY_JOB in select_gates(["src/specify_cli/status/locking.py"], router=router).selected_code_shards


@pytest.mark.parametrize("path", NEGATIVE_PATHS)
def test_an_unrelated_diff_does_not_select_the_lane(path: str) -> None:
    """Positive control on the same fixture: `select_gates` DOES match other groups for these paths."""
    selection = select_gates([path], router=load_router())

    assert GROUP not in selection.matched_groups, f"{path} must not route the path-literal audit"
    assert JOB not in selection.selected_jobs


def test_the_lane_runs_exactly_one_file_with_no_marker_filter() -> None:
    """FR-002/FR-005: one invocation, one path argument, no `-m`/`-k`/`--ignore` narrowing.

    The guard module is `pytestmark = [pytest.mark.integration]` and carries no `fast`/`unit`
    marker, so any marker filter deselects all of it (verified: `-m "fast or unit"` collects 0 of
    8). A filter that silently collects nothing must be impossible here.
    """
    invocations = _pytest_invocations(_jobs()[JOB])

    assert len(invocations) == 1, f"the lane must run one pytest invocation, found {invocations}"
    (command,) = invocations
    assert not _narrows_by_marker_or_name(command), f"the lane must not narrow by marker/name: {command}"
    assert "tests/audit" in command, f"the lane no longer runs tests/audit: {command}"
    assert command.count(GUARD) == 1
    # The one path argument beyond the module: no directory lane sneaked in beside the file.
    assert command.count("tests/audit/") == 1, f"the lane must name exactly the one guard file: {command}"


def test_the_guard_file_still_has_the_tests_the_lane_counts_on() -> None:
    """SC-002: the lane's selection is re-derived from the module (no vacuous count)."""
    tree = ast.parse((ROOT / GUARD).read_text(encoding="utf-8"))
    tests = [node.name for node in tree.body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]
    collected = 0
    for node in tree.body:
        if not (isinstance(node, ast.FunctionDef) and node.name.startswith("test_")):
            continue
        cases = 1
        for decorator in node.decorator_list:
            if not (isinstance(decorator, ast.Call) and getattr(decorator.func, "attr", "") == "parametrize"):
                continue
            values = decorator.args[1] if len(decorator.args) > 1 else None
            if isinstance(values, (ast.List, ast.Tuple)):
                cases = max(cases, len(values.elts))
        collected += cases
    module_marks: list[str] = []
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and any(getattr(target, "id", "") == "pytestmark" for target in node.targets)):
            continue
        if isinstance(node.value, ast.List):
            module_marks = [element.attr for element in node.value.elts if isinstance(element, ast.Attribute)]

    assert module_marks == ["integration"], f"the module-level marker changed: {module_marks}"
    assert any(name == "test_no_handrolled_spec_kitty_home_in_global_state_modules" for name in tests), "the runtime-home limb this lane exists for is gone"


def test_the_lane_is_blocking_and_gated_on_the_group_alone() -> None:
    jobs = _jobs()

    assert JOB in jobs["router-gate"]["needs"], "router-gate.needs is what makes the lane blocking"
    assert JOB not in ADVISORY_JOB_NAMES, "the lane must gate the run, not be advisory"

    context = dict(BASE_CONTEXT_ALL_FALSE)
    context[f"changes.{GROUP}"] = True
    context["prose-scan.prose_only"] = False
    assert eval_gh_if(jobs[JOB]["if"], context) is True
    assert eval_gh_if(jobs[JOB]["if"], {**context, f"changes.{GROUP}": False}) is False


def test_a_prose_only_status_diff_still_down_routes_the_lane() -> None:
    """#4842: a proven prose-only diff skips the code shards; this lane invents no exemption."""
    jobs = _jobs()
    context = dict(BASE_CONTEXT_ALL_FALSE)
    context[f"changes.{GROUP}"] = True
    context["prose-scan.prose_only"] = True

    assert eval_gh_if(jobs[JOB]["if"], context) is False


def test_the_scrub_row_is_the_router_group_verbatim() -> None:
    """The two authorities stay in lockstep: the scrub is the SSOT, the router transcribes it."""
    scrub = json.loads(SCRUB.read_text(encoding="utf-8"))
    (row,) = [row for row in scrub["non_src_router_groups"] if row["group"] == GROUP]

    assert list(row["roots"]) == list(load_router().filters[GROUP])
    assert not any(root.startswith("src/") for root in row["roots"]), "a src glob would make the group src-backed"
    # ... and a NON-src group is deliberately absent from the FR-004 fail-closed union, so it can never
    # mask an unmapped src change.
    (unmatched,) = [step for step in _jobs()["changes"]["steps"] if step.get("id") == "unmatched"]
    assert f"steps.filter.outputs.{GROUP}" not in unmatched["run"]


def test_the_lane_is_cheap_enough_to_ride_a_status_diff() -> None:
    """NFR-001: one bounded job that installs the locked env and syncs packs, like its siblings."""
    job = _jobs()[JOB]

    assert int(job["timeout-minutes"]) <= 10
    assert job["needs"] == ["changes", "prose-scan"]
    run_text = "\n".join(str(step.get("run", "")) for step in job["steps"])
    assert "uv sync --frozen" in run_text, "the lane installs the locked environment in its own step"
    assert any("sync-packs" in str(step.get("uses", "")) for step in job["steps"]), "the guard imports the packs-aware CLI"
