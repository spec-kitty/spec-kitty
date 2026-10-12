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
import contextlib
import copy
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from types import FrameType
from typing import Any, NamedTuple

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


def test_scrub_documentation_copy_equals_the_router_group() -> None:
    scrub = json.loads(SCRUB.read_text(encoding="utf-8"))
    (row,) = [row for row in scrub["non_src_router_groups"] if row["group"] == GROUP]

    assert sorted(row["roots"]) == sorted(load_router().filters[GROUP])


# ---------------------------------------------------------------------------
# #6058 / WP04: the audit runs on every input that can change its verdict.
# ---------------------------------------------------------------------------

NIGHTLY = ROOT / ".github" / "workflows" / "ci-nightly.yml"
ALIGNMENT = ROOT / ".github" / "workflows" / "check-spec-kitty-events-alignment.yml"
# The dependency manifests that carry the reducer (spec-kitty-events): the drift workflow fires on them, and a bump of
# any of them changes what the audit reports (commit 2e97550eb), so the router group must match every one.
MANIFESTS = frozenset({"pyproject.toml", "uv.lock", ".kittify/release/shared-package-compatibility.json"})

# The 5 files of commit 2e97550eb (the reducer bump that turned main red unseen): none was a Mission file.
BUMP_PATHS = (
    ".kittify/release/shared-package-compatibility.json",
    "docs/changelog/CHANGELOG.md",
    "pyproject.toml",
    "tests/architectural/test_pyproject_shape.py",
    "uv.lock",
)

# The audit's executed *modules* are derived (test_every_executed_audit_module_matches_the_group),
# not hand copied (#6090). These are the remaining trigger inputs the audit depends on that a
# call-frame trace of the real `doctor mission-state --audit` command cannot observe, so they stay an
# explicit (small) list:
#   - the dependency manifests that carry the reducer (spec-kitty-events);
#   - the router workflow itself and the report renderer (CI machinery, not src modules the audit runs);
#   - a module-level-only constant source the audit imports but calls no function in (core/constants.py).
# Each must still match the mission_state group; the manifests must also fire the events-alignment workflow.
NON_DERIVABLE_TRIGGER_INPUTS = (
    "uv.lock",
    "pyproject.toml",
    ".kittify/release/shared-package-compatibility.json",
    ".github/workflows/ci-router.yml",
    "scripts/ci/mission_state_audit_report.py",
    "src/specify_cli/core/constants.py",
)


def _alignment_trigger_paths(event: str) -> set[str]:
    workflow: dict[Any, Any] = yaml.safe_load(ALIGNMENT.read_text(encoding="utf-8"))
    triggers = workflow.get("on", workflow.get(True))  # YAML 1.1 parses the bare `on` key as boolean True
    assert triggers is not None, "the events-alignment workflow has no `on:` triggers"
    return set(triggers[event]["paths"])


def test_the_reducer_bump_commit_selects_the_audit_job() -> None:
    selection = select_gates(list(BUMP_PATHS), router=load_router())

    assert JOB in selection.selected_jobs


# The union, so a manifest dropped from the tuple is still checked (routing and events-alignment).
@pytest.mark.parametrize("path", sorted(set(NON_DERIVABLE_TRIGGER_INPUTS) | MANIFESTS))
def test_non_derivable_trigger_inputs_match_the_group(path: str) -> None:
    router = load_router()

    selection = select_gates([path], router=router)

    assert GROUP in selection.matched_groups, f"{path} can change the audit verdict but misses the {GROUP} group"
    assert JOB in selection.selected_jobs
    if path in MANIFESTS:  # alignment: the drift workflow fires on the same files the audit group matches
        assert path in _alignment_trigger_paths("pull_request") and path in _alignment_trigger_paths("push")


def test_the_audit_modules_are_not_spelled_src() -> None:
    """A `src/` glob would make the group src-backed (a code-shard gate); the globs are `**/`-prefixed."""
    assert not [g for g in load_router().filters[GROUP] if g.startswith("src/")]


# ---------------------------------------------------------------------------
# #6090: derive the executed-module trigger set from a real in-process audit run,
# instead of hand-copying "the modules the audit touches" (which drifts, #6058).
# ---------------------------------------------------------------------------

# Positive control: the derived set must be non-empty and contain these anchors, so a
# vacuous capture (zero modules) cannot satisfy the coverage assertion vacuously.
_AUDIT_ANCHOR_MODULES = frozenset(
    {
        "src/specify_cli/audit/engine.py",
        "src/specify_cli/status/reducer.py",
    }
)

# One mission whose persisted status.json drifts from its event log, so the audit's reducer
# SNAPSHOT_DRIFT / findings-rendering path (the #6058 surface) runs. A clean mission derives the
# identical module set (measured), so it is not planted.
_FIXTURE_SLUG = "001-audit-trigger-drift"
_FIXTURE_MISSION_ID = "01KQHRB9GCFJAX7HM4ZY52AQGR"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _fixture_event(event_id: str, at: str, from_lane: str, to_lane: str) -> dict[str, Any]:
    return {
        "actor": "claude",
        "at": at,
        "event_id": event_id,
        "evidence": None,
        "execution_mode": "worktree",
        "force": False,
        "from_lane": from_lane,
        "reason": None,
        "review_ref": None,
        "to_lane": to_lane,
        "wp_id": "WP01",
    }


def _write_fixture_mission(specs_dir: Path, slug: str, mission_id: str) -> None:
    """Write one modern (``mission_id``-keyed) fixture mission whose ``status.json`` drifts.

    The valid-but-mismatching ``status.json`` makes the reducer's ``SNAPSHOT_DRIFT`` check
    produce a finding, so the findings-rendering path runs. Modern events only: a legacy
    ``feature_slug`` would route the audit through a slug-resolution module the real corpus
    never runs (#6090 grounding).
    """
    mission = specs_dir / slug
    mission.mkdir(parents=True)
    (mission / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "mission_slug": slug,
                "mission_number": 1,
                "friendly_name": f"Audit trigger fixture ({slug})",
                "mission_type": "software-dev",
                "target_branch": "main",
            }
        ),
        encoding="utf-8",
    )
    events = (
        _fixture_event("01HXYZAUDIT01", "2026-02-08T12:00:00+00:00", "planned", "claimed"),
        _fixture_event("01HXYZAUDIT02", "2026-02-08T12:05:00+00:00", "claimed", "in_progress"),
    )
    (mission / "status.events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
    (mission / "spec.md").write_text("# Spec\n\nFixture mission.\n", encoding="utf-8")
    (mission / "tasks").mkdir()
    (mission / "tasks" / "WP01.md").write_text("---\nwp_id: WP01\n---\n\n# WP01\n", encoding="utf-8")
    # Valid JSON object that does not match the reduced snapshot → SNAPSHOT_DRIFT.
    (mission / "status.json").write_text(json.dumps({"work_packages": {}}) + "\n", encoding="utf-8")


def _build_audit_fixture(repo_root: Path) -> None:
    """Create a small git repo with one modern mission whose ``status.json`` drifts from its event log.

    The classifier path and the reducer / findings-rendering path (the #6058 surface) both
    execute. Committed so git-tracked mission detection runs.
    """
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "fixture@example.invalid")
    _git(repo_root, "config", "user.name", "Fixture")
    specs_dir = repo_root / "kitty-specs"
    _write_fixture_mission(specs_dir, _FIXTURE_SLUG, _FIXTURE_MISSION_ID)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "audit fixture")


def _doctor_audit_argv() -> list[str]:
    """The ``doctor`` subcommand arguments CI runs, taken from the router job (never restated here)."""
    (command,) = _audit_commands(_jobs()[JOB])
    argv: list[str] = []
    for token in command[command.index("doctor") + 1 :]:
        if token in {">", "||", "|", "&&", ";"}:  # the shell redirect/status capture is not an argument
            break
        argv.append(token)
    return argv


class _AuditRun(NamedTuple):
    exit_code: int
    report: dict[str, Any]


def _run_audit_over_fixture(repo_root: Path) -> _AuditRun:
    """Invoke the real ``doctor mission-state --audit`` typer command, as CI does, from ``repo_root``."""
    from typer.testing import CliRunner

    from specify_cli.cli.commands import doctor

    with contextlib.chdir(repo_root):
        result = CliRunner().invoke(doctor.app, _doctor_audit_argv())
    return _AuditRun(result.exit_code, json.loads(result.stdout))


class _AuditCapture(NamedTuple):
    modules: frozenset[str]
    run: _AuditRun


def _executed_audit_src_modules(repo_root: Path) -> _AuditCapture:
    """Return the ``src/`` modules whose functions run during the audit over ``repo_root``.

    A warm-up run resolves every lazy import first; the profiled second run then records
    only function-call frames (``co_name != "<module>"``), so one-time import-body
    execution of eagerly-imported siblings is never mistaken for an audit dependency.
    This makes the derived set deterministic and order-independent (profiling the first
    run instead would wrongly fold in ~12 import-only modules — see #6090 grounding).
    """
    _run_audit_over_fixture(repo_root)  # warm-up: resolve lazy imports
    executed: set[str] = set()

    def _record(frame: FrameType, event: str, _arg: object) -> None:
        if event == "call" and frame.f_code.co_name != "<module>":
            executed.add(frame.f_code.co_filename)

    prior = sys.getprofile()
    prior_thread = threading.getprofile()
    sys.setprofile(_record)
    # sys.setprofile is thread-local: future-proofs against audit work moved into a worker thread (none today)
    threading.setprofile(_record)
    try:
        run = _run_audit_over_fixture(repo_root)
    finally:
        sys.setprofile(prior)  # restore, never clobber a pre-existing profiler
        threading.setprofile(prior_thread)

    src_root = (ROOT / "src").resolve()
    modules: set[str] = set()
    for filename in executed:
        try:
            relative = Path(filename).resolve().relative_to(src_root)
        except (ValueError, OSError):
            continue
        modules.add("src/" + relative.as_posix())
    return _AuditCapture(frozenset(modules), run)


@pytest.fixture(scope="module")
def executed_audit_modules(tmp_path_factory: pytest.TempPathFactory) -> _AuditCapture:
    if shutil.which("git") is None:
        pytest.skip("git is required to build the audit fixture repo")
    repo_root = tmp_path_factory.mktemp("audit-trigger-fixture")
    _build_audit_fixture(repo_root)
    return _executed_audit_src_modules(repo_root)


def test_every_executed_audit_module_matches_the_group(executed_audit_modules: _AuditCapture) -> None:
    """Every ``src/`` module the audit executes must match a ``mission_state`` glob (#6090).

    Derived from a real ``doctor mission-state --audit --fail-on teamspace-blocker`` run through the
    typer app (the argv is read from the CI job), not a hand copy, so the trigger cannot silently
    go stale when the audit's module graph changes (#6058).

    Scope and blind spots (deliberate): this is an ongoing drift *tripwire*, not a corpus-wide
    completeness proof. It guards the ``src/`` modules whose functions the audit **calls** over
    this modern, drifting fixture mission (37 at landing; the grounding corpus scan of 604 real
    missions found the same in-audit set). A call-frame profile cannot see purely declarative
    modules (constants, regexes, frozensets, enums, models without validators) or
    dataclass-generated methods: such an input can change the verdict (``core/constants.py``
    sets the scan root) yet never shows up here, so it must be added to
    ``NON_DERIVABLE_TRIGGER_INPUTS`` by hand. The nightly full-corpus audit is the backstop for
    what neither covers. The warm-up also folds out code that runs only at a cold process's
    import time. Nor does the test guard a module reachable only through a path no real mission
    takes (a legacy ``feature_slug`` shape routes through a slug-resolution module the real
    corpus never runs) or a mode CI never invokes (``--fix`` / ``--teamspace-dry-run``). Widen
    the fixture if the audit later routes a verdict-affecting module through one of those paths.
    """
    router = load_router()
    modules, run = executed_audit_modules

    # Positive control: a vacuous (empty / anchor-less) capture must not pass vacuously.
    assert modules >= _AUDIT_ANCHOR_MODULES, (
        f"the audit fixture did not exercise the anchor modules {sorted(_AUDIT_ANCHOR_MODULES)}; derived set was {sorted(modules)}"
    )
    # The gate CI runs (`--fail-on teamspace-blocker`) fires on the planted drift: exit 1, never swallowed.
    assert run.exit_code == 1, f"the audit gate must exit 1 over the drifting fixture, got {run.exit_code}"
    # The fixture's purpose: the audit reported the mission and produced the SNAPSHOT_DRIFT finding.
    findings = {(m["mission_slug"], f["code"]) for m in run.report["missions"] for f in m["findings"]}
    assert (_FIXTURE_SLUG, "SNAPSHOT_DRIFT") in findings, f"the planted drift was not reported; findings were {sorted(findings)}"

    uncovered = sorted(module for module in modules if GROUP not in select_gates([module], router=router).matched_groups)
    assert not uncovered, (
        f"the audit executes these src modules but no {GROUP} glob matches them, so a PR that "
        f"changes the audit's verdict would skip the audit (#6058/#6090): {uncovered}"
    )
    assert GROUP not in router.src_backed_groups, "a src glob would make the audit a code shard"


def _nightly_jobs() -> dict[str, Any]:
    return dict(yaml.safe_load(NIGHTLY.read_text(encoding="utf-8"))["jobs"])


def _nightly_audit_name() -> str:
    matches = [name for name, job in _nightly_jobs().items() if _audit_commands(job)]
    assert len(matches) == 1, "exactly one nightly job runs `doctor mission-state`"
    return matches[0]


def _nightly_audit_job() -> dict[str, Any]:
    return dict(_nightly_jobs()[_nightly_audit_name()])


def _escalation_argv(step: dict[str, Any], tmp_path: Path, outcome: str | None) -> list[str]:
    """Run the escalation step's real ``run:`` body under bash with a stub ``python3``; return the argv it received."""
    bin_dir = tmp_path / f"bin-{outcome}"
    bin_dir.mkdir()
    argv_file = tmp_path / f"argv-{outcome}.txt"
    stub = bin_dir / "python3"
    stub.write_text('#!/bin/sh\nfor arg in "$@"; do printf \'%s\\n\' "$arg"; done > "$ARGV_FILE"\n', encoding="utf-8")
    stub.chmod(0o755)
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "ARGV_FILE": str(argv_file),
        "GH_TOKEN": "dummy",
        "GITHUB_REF": "refs/heads/main",
    }
    if outcome is not None:
        env["AUDIT_OUTCOME"] = outcome
    body = re.sub(r"\$\{\{.*?\}\}", "expr", str(step["run"]))  # GitHub expressions are expanded before bash runs
    subprocess.run(["bash", "-e", "-c", body], env=env, check=True, capture_output=True, text=True)
    return argv_file.read_text(encoding="utf-8").splitlines()


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required to run the step body")
@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        ("success", "success"),
        ("failure", "failure"),
        ("cancelled", "failure"),
        ("skipped", "failure"),
        ("", "failure"),
        (None, "failure"),
    ],
)
def test_a_red_nightly_audit_escalates_to_a_deduped_p0_on_main(tmp_path: Path, outcome: str | None, expected: str) -> None:
    job = _nightly_audit_job()
    (step,) = [s for s in job["steps"] if str(s.get("name", "")).startswith(ESCALATION_STEP_PREFIX)]

    assert step["if"] == "always() && github.ref == 'refs/heads/main'"
    assert job["permissions"]["issues"] == "write"
    assert "steps.audit.outcome" in step["env"]["AUDIT_OUTCOME"]
    assert [s for s in job["steps"] if s.get("id") == "audit"], "the escalation reads the audit step's outcome"

    # Behaviour: fail-closed. Only an explicit success outcome of the audit step closes the P0.
    argv = _escalation_argv(step, tmp_path, outcome)
    assert argv[0].endswith("nightly_escalation.py")
    assert argv[argv.index("--suite-key") + 1] == "mission-state-audit"
    assert argv[argv.index("--conclusion") + 1] == expected
    assert argv[argv.index("--ref") + 1] == "refs/heads/main"


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
