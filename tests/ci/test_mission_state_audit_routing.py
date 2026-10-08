"""Pin the CI routing of Mission state files under ``kitty-specs/`` (spec-kitty#5864).

A Mission that lands with a ``status.json`` its event log no longer materializes to
(``SNAPSHOT_DRIFT``, #5862) used to land green: the router's ``corpus`` group names only
``spec.md``, ``plan.md``, ``tasks/**``, ``contracts/**`` and ``acceptance-matrix.json``, so a
diff that changes only status files selected no job, and the drift surfaced on the next
unrelated PR that ran the upgrade witness. The ``corpus`` jobs would not have caught it either:
the reality check passes on a drifted snapshot. The router's ``mission_state`` group therefore
gates one cheap job, ``mission-state-audit``, that runs the same audit and gate as the upgrade
witness (``doctor mission-state --audit --fail-on teamspace-blocker``) over the checkout's own
``kitty-specs/``.

Every assertion reads the parsed router (``scripts/ci/gate_selection.py``), the one routing
authority, never a restated copy.
"""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci.gate_selection import load_router, select_gates, select_modules
from tests.ci._gh_if import eval_gh_if

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parents[2]
ROUTER = ROOT / ".github" / "workflows" / "ci-router.yml"
WITNESS = ROOT / "tests" / "upgrade" / "preview_support" / "test_public_witnesses.py"
SCRUB = ROOT / "tests" / "release" / "ci_retirement_scrub.json"

GROUP = "mission_state"
JOB = "mission-state-audit"
MISSION = "kitty-specs/some-mission-01ABCDEF"

STATE_ONLY_PATHS = (
    f"{MISSION}/status.json",
    f"{MISSION}/status.events.jsonl",
    f"{MISSION}/meta.json",
    f"{MISSION}/lanes.json",
)


def _jobs() -> dict[str, Any]:
    workflow = yaml.safe_load(ROUTER.read_text(encoding="utf-8"))
    return dict(workflow["jobs"])


def _audit_commands(job: dict[str, Any]) -> list[list[str]]:
    """Every ``spec-kitty doctor mission-state`` invocation in the job's ``run:`` scripts, tokenized."""
    commands: list[list[str]] = []
    for step in job["steps"]:
        for line in str(step.get("run", "")).splitlines():
            tokens = shlex.split(line, comments=True)
            if "doctor" in tokens and "mission-state" in tokens:
                commands.append(tokens)
    return commands


def _witness_argv() -> list[str]:
    """The ``doctor mission-state`` arguments the upgrade witness passes to ``case.run``."""
    match = re.search(r'case\.run\(("doctor", "mission-state"[^)]*)\)', WITNESS.read_text(encoding="utf-8"))
    assert match, "the upgrade witness still runs `doctor mission-state` through case.run"
    return [token.strip().strip('"') for token in match.group(1).split(",")]


@pytest.mark.parametrize("path", STATE_ONLY_PATHS)
def test_a_state_only_diff_selects_the_audit_job(path: str) -> None:
    router = load_router()

    selection = select_gates([path], router=router)

    assert GROUP in selection.matched_groups
    assert JOB in selection.selected_jobs
    assert selection.selected_code_shards == frozenset(), "Mission data selects no code shard"
    assert not selection.unmatched_src
    assert select_modules([path], router=router) == frozenset()


def test_the_group_is_data_only_and_owns_all_of_kitty_specs() -> None:
    router = load_router()

    assert router.filters[GROUP] == ("kitty-specs/**",)
    assert GROUP not in router.src_backed_groups, "a src glob would make the audit a code shard"


def test_the_audit_job_is_gated_on_the_group_alone_and_blocks_the_merge() -> None:
    jobs = _jobs()

    assert load_router().job_gates[JOB] == frozenset({GROUP})
    assert JOB in jobs["router-gate"]["needs"], "router-gate.needs is what makes the job blocking"
    assert eval_gh_if(jobs[JOB]["if"], {f"changes.{GROUP}": True}) is True
    assert eval_gh_if(jobs[JOB]["if"], {f"changes.{GROUP}": False}) is False


def test_the_group_is_not_in_the_fail_closed_unmatched_union() -> None:
    """Non-src groups stay out of the FR-004 union, so Mission data can never mask an unmapped src change."""
    changes = _jobs()["changes"]
    (unmatched,) = [step for step in changes["steps"] if step.get("id") == "unmatched"]

    assert f"steps.filter.outputs.{GROUP}" not in unmatched["run"]


def test_the_audit_job_runs_the_witness_audit_and_gate() -> None:
    commands = _audit_commands(_jobs()[JOB])

    assert len(commands) == 1, f"exactly one audit invocation, found {commands}"
    (command,) = commands
    witness = _witness_argv()
    assert "--audit" in command
    fail_on = witness[witness.index("--fail-on") + 1]
    assert command[command.index("--fail-on") + 1] == fail_on, "the job gates on what the upgrade witness gates on"
    assert "--mission" not in command, "the audit covers every Mission, not one"


def test_scrub_documentation_copy_equals_the_router_group() -> None:
    scrub = json.loads(SCRUB.read_text(encoding="utf-8"))
    (row,) = [row for row in scrub["non_src_router_groups"] if row["group"] == GROUP]

    assert sorted(row["roots"]) == sorted(load_router().filters[GROUP])
