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

import ast
import copy
import json
import shlex
import shutil
import subprocess
import sys
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

MISSION_PATHS = (
    f"{MISSION}/spec.md",
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
    for step in job.get("steps", []):
        for line in str(step.get("run", "")).splitlines():
            if "mission-state" not in line:  # other workflows' scripts need not be shlex-clean
                continue
            tokens = shlex.split(line, comments=True)
            if "doctor" in tokens and "mission-state" in tokens:
                commands.append(tokens)
    return commands


def _witness_argv() -> list[str]:
    """The ``doctor mission-state`` arguments the upgrade witness passes to ``case.run``."""
    for node in ast.walk(ast.parse(WITNESS.read_text(encoding="utf-8"))):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "run"):
            continue
        args = [arg.value for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)]
        if args[:2] == ["doctor", "mission-state"]:
            return args
    raise AssertionError("the upgrade witness still runs `doctor mission-state` through case.run")


@pytest.mark.parametrize("path", MISSION_PATHS)
def test_a_mission_diff_selects_the_audit_job(path: str) -> None:
    router = load_router()

    selection = select_gates([path], router=router)

    assert GROUP in selection.matched_groups
    assert JOB in selection.selected_jobs
    assert selection.selected_code_shards == frozenset(), "Mission data selects no code shard"
    assert not selection.unmatched_src
    assert select_modules([path], router=router) == frozenset()
    assert GROUP not in router.src_backed_groups, "a src glob would make the audit a code shard"


def test_the_audit_job_is_gated_on_the_group_alone_and_blocks_the_merge() -> None:
    jobs = _jobs()

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


@pytest.mark.skipif(shutil.which("bash") is None or shutil.which("jq") is None, reason="needs bash and jq")
def test_a_failing_audit_still_prints_the_failing_missions(tmp_path: Path) -> None:
    """The step runs under ``bash -e``; a non-zero audit must not end it before the report is printed (#6058)."""
    (step,) = [step for step in _jobs()[JOB]["steps"] if "mission-state" in str(step.get("run", ""))]
    report = {
        "repo_summary": {"missions_with_errors": 1},
        "missions": [
            {
                "mission_slug": "076-init-command-overhaul",
                "has_errors": True,
                "has_teamspace_blockers": True,
                "findings": [
                    {
                        "code": "SNAPSHOT_DRIFT",
                        "severity": "error",
                        "artifact_path": "status.json",
                        "detail": "reducer output does not match persisted status.json",
                    }
                ],
            }
        ],
    }
    summary = tmp_path / "summary.md"
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    stub = stub_dir / "uv"
    # The auditor call prints the report and fails; the renderer call (`uv run --frozen --no-sync python ...`)
    # runs the real script under the real interpreter, like the stub in test_mission_state_audit_step.py.
    renderer_branch = 'if [ "$4" = "python" ]; then\n  shift 4\n  exec "$STUB_PYTHON" "$@"\nfi\n'
    auditor_branch = f"cat <<'JSON'\n{json.dumps(report)}\nJSON\nexit 1\n"
    stub.write_text(f"#!/usr/bin/env bash\n{renderer_branch}{auditor_branch}", encoding="utf-8")
    stub.chmod(0o755)

    result = subprocess.run(
        ["bash", "-e", "-c", step["run"]],
        cwd=ROOT,
        env={
            "PATH": f"{stub_dir}:/usr/bin:/bin",
            "RUNNER_TEMP": str(tmp_path),
            "GITHUB_STEP_SUMMARY": str(summary),
            "STUB_PYTHON": sys.executable,
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "::error" in result.stdout
    assert "076-init-command-overhaul" in result.stdout
    assert "SNAPSHOT_DRIFT" in result.stdout
    assert "SNAPSHOT_DRIFT" in summary.read_text(encoding="utf-8")


def test_scrub_documentation_copy_equals_the_router_group() -> None:
    scrub = json.loads(SCRUB.read_text(encoding="utf-8"))
    (row,) = [row for row in scrub["non_src_router_groups"] if row["group"] == GROUP]

    assert sorted(row["roots"]) == sorted(load_router().filters[GROUP])


# ---------------------------------------------------------------------------
# #6058 / WP04: the audit runs on every input that can change its verdict.
# ---------------------------------------------------------------------------

NIGHTLY = ROOT / ".github" / "workflows" / "ci-nightly.yml"

# The 5 files of commit 2e97550eb (the reducer bump that turned main red unseen): none was a Mission file.
BUMP_PATHS = (
    ".kittify/release/shared-package-compatibility.json",
    "docs/changelog/CHANGELOG.md",
    "pyproject.toml",
    "tests/architectural/test_pyproject_shape.py",
    "uv.lock",
)

AUDIT_INPUT_PATHS = (
    "uv.lock",
    "pyproject.toml",
    ".kittify/release/shared-package-compatibility.json",
    ".github/workflows/ci-router.yml",
    "scripts/ci/mission_state_audit_report.py",
    "src/specify_cli/status/reducer.py",
    "src/specify_cli/audit/engine.py",
    "src/specify_cli/migration/mission_state.py",
    "src/specify_cli/mission_metadata.py",
    "src/specify_cli/frontmatter.py",
    "src/specify_cli/context/mission_resolver.py",
    "src/specify_cli/core/paths.py",
    "src/specify_cli/core/utils.py",
    "src/specify_cli/core/constants.py",
    "src/specify_cli/core/checkout_identity.py",
    "src/specify_cli/identity/aliases.py",
    "src/specify_cli/lanes/branch_naming.py",
    "src/specify_cli/cli/commands/_mission_state_doctor.py",
    "src/specify_cli/cli/commands/doctor.py",
    "src/specify_cli/cli/commands/_doctor_shared.py",
    "src/kernel/meta_decode.py",
    "src/kernel/git/listing.py",
    "src/kernel/git/paths.py",
    "src/kernel/git/runner.py",
    "src/kernel/guarded_read.py",
    "src/charter/activation/mission_type_key.py",
)


def test_the_reducer_bump_commit_selects_the_audit_job() -> None:
    selection = select_gates(list(BUMP_PATHS), router=load_router())

    assert JOB in selection.selected_jobs


@pytest.mark.parametrize("path", AUDIT_INPUT_PATHS)
def test_audit_inputs_match_the_group_directly(path: str) -> None:
    router = load_router()

    selection = select_gates([path], router=router)

    assert GROUP in selection.matched_groups, f"{path} can change the audit verdict but misses the {GROUP} group"
    assert JOB in selection.selected_jobs
    assert GROUP not in router.src_backed_groups


def test_the_audit_modules_are_not_spelled_src() -> None:
    """A `src/` glob would make the group src-backed (a code-shard gate); the globs are `**/`-prefixed."""
    assert not [g for g in load_router().filters[GROUP] if g.startswith("src/")]


def _nightly_jobs() -> dict[str, Any]:
    return dict(yaml.safe_load(NIGHTLY.read_text(encoding="utf-8"))["jobs"])


def _nightly_audit_name() -> str:
    matches = [name for name, job in _nightly_jobs().items() if _audit_commands(job)]
    assert len(matches) == 1, "exactly one nightly job runs `doctor mission-state`"
    return matches[0]


def _nightly_audit_job() -> dict[str, Any]:
    return dict(_nightly_jobs()[_nightly_audit_name()])


def test_a_red_nightly_audit_escalates_to_a_deduped_p0_on_main() -> None:
    job = _nightly_audit_job()
    (step,) = [s for s in job["steps"] if str(s.get("name", "")).startswith(ESCALATION_STEP_PREFIX)]

    assert "--suite-key mission-state-audit" in step["run"]
    assert "nightly_escalation.py" in step["run"] and '--ref "$GITHUB_REF"' in step["run"]
    assert step["if"] == "always() && github.ref == 'refs/heads/main'"
    assert job["permissions"]["issues"] == "write"
    # Fail-closed: only an explicit success outcome of the audit step closes the P0.
    assert "AUDIT_OUTCOME:-failure" in step["run"] and "steps.audit.outcome" in step["env"]["AUDIT_OUTCOME"]
    assert [s for s in job["steps"] if s.get("id") == "audit"], "the escalation reads the audit step's outcome"


def test_the_nightly_run_audits_main() -> None:
    jobs = _nightly_jobs()
    name = _nightly_audit_name()
    job = jobs[name]

    (command,) = _audit_commands(job)
    assert "--audit" in command and "--json" in command
    assert command[command.index("--fail-on") + 1] == "teamspace-blocker"
    assert "--mission" not in command
    assert any("upload-artifact" in str(s.get("uses", "")) for s in job["steps"]), "the report is uploaded"
    assert "changes" not in job.get("needs", []), "no path gating: the nightly audits main unconditionally"
    assert "changes." not in str(job.get("if", ""))
    assert name in jobs["nightly-summary"]["needs"]
    assert "github.repository == 'spec-kitty/spec-kitty'" in str(job["if"]), "the fork guard"


ESCALATION_STEP_PREFIX = "Escalate mission-state audit red"


def _shared_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The audit steps both jobs run: everything except the nightly-only escalation step (matched by name)."""
    return [s for s in steps if not str(s.get("name", "")).startswith(ESCALATION_STEP_PREFIX)]


def _steps_match(router_steps: list[dict[str, Any]], nightly_steps: list[dict[str, Any]]) -> bool:
    """Every shared step (checkout, setup-uv, uv sync, audit, upload) must be equal; only the escalation differs."""
    return _shared_steps(router_steps) == _shared_steps(nightly_steps)


def test_the_nightly_audit_steps_are_the_router_steps() -> None:
    """Parity: every audit step the nightly job shares with the router job is equal; the nightly-only escalation step is the sole extra."""
    router_steps = _jobs()[JOB]["steps"]
    nightly_steps = _nightly_audit_job()["steps"]

    assert _steps_match(router_steps, nightly_steps)
    assert len(nightly_steps) == len(router_steps) + 1, "the escalation step is the only nightly-only step"
    assert not [s for s in router_steps if str(s.get("name", "")).startswith(ESCALATION_STEP_PREFIX)]
    assert [s.get("run") for s in nightly_steps if str(s.get("run", "")).startswith("uv sync")] == ["uv sync --frozen"]


def test_the_parity_check_is_not_vacuous() -> None:
    """Mutating the nightly checkout pin (or any shared step) must break the parity."""
    router_steps = _jobs()[JOB]["steps"]
    mutated = copy.deepcopy(_nightly_audit_job()["steps"])
    mutated[0]["uses"] = "actions/checkout@" + "0" * 40 + " # v5.0.0"

    assert not _steps_match(router_steps, mutated)


@pytest.mark.parametrize("path", ["tests/specify_cli/status/test_agent_assignment.py", "tests/specify_cli/audit/test_detectors_row_family.py"])
def test_test_only_diffs_under_the_audit_modules_deliberately_over_match(path: str) -> None:
    """Documented over-match (cost only): the `**/specify_cli/{audit,status}/**` globs also match their tests.

    dorny/paths-filter ORs patterns and cannot exclude inside one list without changing the group's
    predicate, so the over-match is accepted (mirrors `contract_tools`). Narrowing it is a conscious change.
    """
    assert GROUP in select_gates([path], router=load_router()).matched_groups
