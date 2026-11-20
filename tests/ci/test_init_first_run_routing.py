"""Pin the per-PR routing of an ``init`` change to the first-run path and e2e suite (spec-kitty#7741).

#7708 (#7612) made ``spec-kitty init`` create the root commit on an unborn branch. The tests that
consume ``init`` end to end -- ``tests/acceptance/test_first_run_path.py`` (``tests/acceptance`` is
an ``out_of_matrix_test_dirs`` entry) and ``tests/e2e`` -- ran only in the nightly, so the PR merged
green and main stayed red for two nightlies (#7738-#7741). This module pins the fix: the NON-src
``e2e`` group also names the ``init`` command files and the first-run test file, and the job gated on
it runs both suites in its one pytest invocation.

Every assertion reads the parsed router (``scripts/ci/gate_selection.py``) and the on-disk workflow,
never a restated copy of the routing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci.gate_selection import load_router, select_gates
from scripts.ci.router_gate import ADVISORY_JOB_NAMES
from tests.ci._gh_if import BASE_CONTEXT_ALL_FALSE, eval_gh_if

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parents[2]
ROUTER = ROOT / ".github" / "workflows" / "ci-router.yml"
FIRST_RUN = "tests/acceptance/test_first_run_path.py"

GROUP = "e2e"
JOB = "tests-e2e"

POSITIVE_PATHS = (
    "src/specify_cli/cli/commands/init.py",
    "src/specify_cli/cli/commands/init_help.py",
    FIRST_RUN,
)

# Same-fixture negative controls: real, mapped paths that must NOT select the lane, so a glob that
# matched everything cannot satisfy the positive assertions vacuously. The first one is a neighbour of
# init.py in the same directory.
NEGATIVE_PATHS = (
    "src/specify_cli/cli/commands/upgrade.py",
    "src/specify_cli/cli/commands/doctor.py",
    "tests/acceptance/test_init_ledger_flow.py",
    "docs/development/how-to/manage-issue-tracker.md",
)


def _jobs() -> dict[str, Any]:
    return dict(yaml.safe_load(ROUTER.read_text(encoding="utf-8"))["jobs"])


def _pytest_invocations(job: dict[str, Any]) -> list[str]:
    return [line for step in job.get("steps", []) for line in str(step.get("run", "")).splitlines() if " pytest " in f" {line} "]


@pytest.mark.parametrize("path", POSITIVE_PATHS)
def test_an_init_change_selects_the_e2e_lane(path: str) -> None:
    selection = select_gates([path], router=load_router())

    assert GROUP in selection.matched_groups, f"{path} misses the {GROUP} group"
    assert JOB in selection.selected_jobs, f"{path} selects {GROUP} but not the job gated on it"
    assert not selection.unmatched_src, "a mapped path must never trip the FR-004 fail-closed catch-all"


def test_an_init_change_keeps_its_module_fanout() -> None:
    """The new lane adds to, never replaces, the `cli` group and the `cli_cmd_init` fan-out."""
    selection = select_gates(["src/specify_cli/cli/commands/init.py"], router=load_router())

    assert {"cli", "cli_cmd_init"} <= selection.matched_groups


@pytest.mark.parametrize("path", NEGATIVE_PATHS)
def test_an_unrelated_diff_does_not_select_the_lane(path: str) -> None:
    selection = select_gates([path], router=load_router())

    assert GROUP not in selection.matched_groups, f"{path} must not route the e2e lane"
    assert JOB not in selection.selected_jobs


def test_the_group_stays_non_src() -> None:
    """A `src/`-spelled glob would make `e2e` src-backed, i.e. a module-matrix row it is not."""
    router = load_router()

    assert GROUP not in router.src_backed_groups
    assert not [glob for glob in router.filters[GROUP] if glob.startswith("src/")]


def test_the_lane_runs_both_suites_in_one_unnarrowed_invocation() -> None:
    """One invocation (the duplicate-suite ledger's rule) naming both suites, with no marker filter.

    `test_first_run_path.py` is `integration`-marked, so a marker filter would silently collect none of it.
    """
    invocations = _pytest_invocations(_jobs()[JOB])

    assert len(invocations) == 1, f"the lane must run one pytest invocation, found {invocations}"
    (command,) = invocations
    assert not any(flag in command for flag in (" -m ", " -k ", "--ignore", "--deselect", "-m=", "-k=")), command
    assert "tests/e2e" in command.split()
    assert FIRST_RUN in command.split()
    assert (ROOT / FIRST_RUN).is_file()


def test_the_lane_is_blocking_and_gated_on_the_group() -> None:
    jobs = _jobs()

    assert JOB in jobs["router-gate"]["needs"], "router-gate.needs is what makes the lane blocking"
    assert JOB not in ADVISORY_JOB_NAMES
    context = {**BASE_CONTEXT_ALL_FALSE, f"changes.{GROUP}": True, "prose-scan.prose_only": False}
    assert eval_gh_if(jobs[JOB]["if"], context) is True
    assert eval_gh_if(jobs[JOB]["if"], {**context, f"changes.{GROUP}": False}) is False
