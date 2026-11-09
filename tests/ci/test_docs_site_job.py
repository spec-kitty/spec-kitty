"""Pin the ``docs-site`` job: the doc-kitty build on pull requests (#6930, #6937).

ADR ``docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md`` D-11 puts a
``docs-site`` job in ``ci-router.yml`` behind a ``docs/**`` + ``site/**`` path filter
parsed by ``scripts/ci/gate_selection.py``. The job calls the ONE shared build definition,
``.github/workflows/docs-site-build.yml`` (#6937), which installs the site with the frozen
lockfile and no token, builds it, and uploads ``site/dist`` (or, for the Pages deploy at
#6938, the Pages artifact). The step checks below read that called job, the steps that
actually run. Since #6937 the gate is **required**: ``router-gate``'s ``needs:`` names it
and it carries no ``continue-on-error``. DocFX keeps deploying (D-13).

Every routing assertion reads the parsed router (``gate_selection.load_router``), the one
routing authority. Each structural checker has a mutant fed through the same checker
(non-vacuity).
"""

from __future__ import annotations

import copy
import io
import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci import router_gate
from scripts.ci.gate_selection import HEAVY_BATTERY_JOB, load_router, select_gates, select_modules
from tests.ci._gh_if import eval_gh_if

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parents[2]
ROUTER = ROOT / ".github" / "workflows" / "ci-router.yml"
MAKEFILE = ROOT / "Makefile"
SCRUB = ROOT / "tests" / "release" / "ci_retirement_scrub.json"
SHARED = ROOT / ".github" / "workflows" / "docs-site-build.yml"
SHARED_REF = "./.github/workflows/docs-site-build.yml"
BUILD_JOB = "build"

GROUP = "docs_site"
JOB = "docs-site"
_SHA_PIN = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
_CORE_GUARD = "(github.repository == 'spec-kitty/spec-kitty' || github.event_name == 'pull_request' || github.event_name == 'workflow_dispatch')"
_ASTRO_CONFIG = "--astro-config astro.config.mjs"
_DOCKITTY_CALL = re.compile(r"\bdockitty-[a-z-]+\b")


def _workflow() -> dict[str, Any]:
    return dict(yaml.safe_load(ROUTER.read_text(encoding="utf-8")))


def _job() -> dict[str, Any]:
    return dict(_workflow()["jobs"][JOB])


def _shared() -> dict[Any, Any]:
    """The shared build definition (ADR D-11): one reusable workflow for the gate and the deploy."""
    return dict(yaml.safe_load(SHARED.read_text(encoding="utf-8")))


def _build_job() -> dict[str, Any]:
    """The job that actually builds the site: the shared definition's ``build`` job."""
    return dict(_shared()["jobs"][BUILD_JOB])


def _triggers(workflow: dict[Any, Any]) -> dict[str, Any]:
    """``on:`` parses as the boolean ``True`` key under YAML 1.1."""
    raw = workflow.get("on", workflow.get(True))
    return dict(raw) if isinstance(raw, dict) else {str(raw): None}


def _run_text(job: dict[str, Any]) -> str:
    return "\n".join(str(step["run"]) for step in job.get("steps", []) if "run" in step)


# --- routing (FR-007, C-002) -------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "docs/guides/install.md",
        "docs/_meta/sections.yaml",
        "site/package.json",
        "site/pnpm-lock.yaml",
        "site/astro.config.mjs",
        ".github/workflows/docs-site-build.yml",
        "scripts/docs/site_built_check.py",
    ],
)
def test_a_docs_or_site_change_selects_the_job(path: str) -> None:
    router = load_router()

    selection = select_gates([path], router=router)

    assert GROUP in selection.matched_groups
    assert JOB in selection.selected_jobs
    assert not selection.unmatched_src
    assert selection.selected_code_shards <= {HEAVY_BATTERY_JOB}, "a docs/site diff selects no code shard beyond a scoped battery run"


def test_a_site_only_change_selects_no_module() -> None:
    assert select_modules(["site/package.json"], router=load_router()) == frozenset()


@pytest.mark.parametrize("path", ["src/specify_cli/status/store.py", "tests/status/test_store.py", "README.md", "kitty-specs/x/spec.md"])
def test_an_unrelated_change_does_not_select_the_job(path: str) -> None:
    assert JOB not in select_gates([path], router=load_router()).selected_jobs


def test_the_group_is_not_src_backed() -> None:
    router = load_router()

    assert GROUP not in router.src_backed_groups, "a src glob would make the docs build a code shard"


def test_the_group_is_not_in_the_fail_closed_unmatched_union() -> None:
    changes = _workflow()["jobs"]["changes"]
    (unmatched,) = [step for step in changes["steps"] if step.get("id") == "unmatched"]

    assert f"steps.filter.outputs.{GROUP}" not in unmatched["run"]


def test_the_group_output_folds_full_mode_but_not_the_unmatched_union() -> None:
    outputs = _workflow()["jobs"]["changes"]["outputs"]

    assert outputs[GROUP] == f"${{{{ inputs.mode == 'full' && 'true' || steps.filter.outputs.{GROUP} }}}}"


def test_scrub_documentation_copy_equals_the_router_group() -> None:
    scrub = json.loads(SCRUB.read_text(encoding="utf-8"))
    (row,) = [row for row in scrub["non_src_router_groups"] if row["group"] == GROUP]

    assert sorted(row["roots"]) == sorted(load_router().filters[GROUP])


# --- wiring (FR-007, FR-008) -------------------------------------------------------------------


def test_the_job_is_gated_on_the_group_alone() -> None:
    job = _job()

    assert job["needs"] == ["changes"]
    assert load_router().job_gates[JOB] == frozenset({GROUP})
    assert eval_gh_if(job["if"], {f"changes.{GROUP}": True}) is True
    assert eval_gh_if(job["if"], {f"changes.{GROUP}": False}) is False


def test_the_job_skips_on_forks_through_the_guarded_changes_job() -> None:
    """``needs: [changes]`` makes the job skip whenever ``changes`` does (fork pushes, pr:pause-ci)."""
    changes_if = " ".join(str(_workflow()["jobs"]["changes"]["if"]).split())

    assert changes_if.startswith(_CORE_GUARD)
    assert "always()" not in str(_job()["if"]), "an always() job would start on its own and need its own guard"


# --- the job's steps (FR-007, NFR-001..003) -----------------------------------------------------


def _pin_violations(job: dict[str, Any]) -> list[str]:
    uses = [str(step["uses"]) for step in job.get("steps", []) if "uses" in step]
    return [ref for ref in uses if not ref.startswith("./") and not _SHA_PIN.match(ref.split("#")[0].strip())]


def _credential_violations(job: dict[str, Any]) -> list[str]:
    text = yaml.safe_dump(job)
    found = [token for token in ("secrets.", "github.token", "GITHUB_TOKEN", "NODE_AUTH_TOKEN", "NPM_TOKEN") if token in text]
    if "secrets" in job:  # `secrets: inherit` hands every caller secret to the called workflow
        found.append(f"secrets: {job['secrets']}")
    permissions = job.get("permissions")
    if permissions not in (None, {"contents": "read"}):
        found.append(f"permissions: {permissions}")
    return found


def test_every_action_is_pinned_by_commit() -> None:
    assert _pin_violations(_build_job()) == []


def test_a_tag_pinned_action_is_caught() -> None:
    mutant = copy.deepcopy(_build_job())
    mutant["steps"].append({"uses": "actions/setup-node@v7"})

    assert _pin_violations(mutant) == ["actions/setup-node@v7"]


def test_the_job_uses_no_credential() -> None:
    assert _workflow()["permissions"] == {"contents": "read"}
    assert _credential_violations(_job()) == []
    assert _credential_violations(_build_job()) == []


def test_a_token_in_the_job_is_caught() -> None:
    expression = copy.deepcopy(_build_job())
    expression["steps"].append({"run": "pnpm install", "env": {"NPM_CONFIG_USERCONFIG": "${{ secrets.NPMRC }}"}})
    inherited = {**_job(), "secrets": "inherit"}  # the caller-job form of a credential leak

    assert _credential_violations(expression)
    assert _credential_violations(inherited) == ["secrets: inherit"]


def test_the_job_installs_frozen_and_checks_the_contract() -> None:
    run = _run_text(_build_job())

    assert "pnpm install --frozen-lockfile" in run
    assert "-m scripts.docs.site_contract --check" in run


def _step_index(job: dict[str, Any], needle: str) -> int:
    """The position of the first ``run`` step carrying *needle*, or ``-1``."""
    runs = [str(step.get("run", "")) for step in job.get("steps", [])]
    return next((index for index, run in enumerate(runs) if needle in run), -1)


def _gate_order_violations(job: dict[str, Any]) -> list[str]:
    """The source gates run after the install, the built-site checks after the build (D-11)."""
    install = _step_index(job, "pnpm install --frozen-lockfile")
    build = _step_index(job, "pnpm run build")
    violations = []
    for needle, after, name in (
        ("dockitty-validate-frontmatter", install, "install"),
        ("-m scripts.docs.site_built_check", build, "build"),
    ):
        index = _step_index(job, needle)
        if index <= after or after < 0:
            violations.append(f"{needle} must run after the {name} step")
    return violations


def test_the_gates_run_where_their_inputs_exist() -> None:
    assert _gate_order_violations(_build_job()) == []


def test_a_built_site_check_before_the_build_is_caught() -> None:
    mutant = copy.deepcopy(_build_job())
    steps = mutant["steps"]
    (check,) = [step for step in steps if "-m scripts.docs.site_built_check" in str(step.get("run", ""))]
    steps.remove(check)
    steps.insert(0, check)

    assert _gate_order_violations(mutant) == ["-m scripts.docs.site_built_check must run after the build step"]


def test_no_step_swallows_a_failure() -> None:
    """A required job never swallows a failure: no step-level ``continue-on-error`` and no shell fallback."""
    job = _build_job()

    assert job["steps"], "the build job carries the steps (non-vacuity)"
    assert all("continue-on-error" not in step for step in job["steps"])
    assert not re.search(r"\|\|\s*true\b|\bset\s+\+e\b", _run_text(job))


# --- dockitty-* gates carry --astro-config (FR-009, ADR D-1) ------------------------------------


def _astro_config_violations(text: str) -> list[str]:
    """Every line that calls a ``dockitty-*`` binary without ``--astro-config astro.config.mjs``."""
    return [line.strip() for line in text.splitlines() if _DOCKITTY_CALL.search(line) and not line.lstrip().startswith("#") and _ASTRO_CONFIG not in line]


def test_every_dockitty_call_passes_the_astro_config() -> None:
    assert _astro_config_violations(ROUTER.read_text(encoding="utf-8")) == []
    assert _astro_config_violations(SHARED.read_text(encoding="utf-8")) == []
    assert _astro_config_violations(MAKEFILE.read_text(encoding="utf-8")) == []


def test_a_dockitty_call_without_the_astro_config_is_caught() -> None:
    mutant = (
        "        run: pnpm exec dockitty-check-links ../docs --strict\n"
        "        run: pnpm exec dockitty-validate-frontmatter ../docs --astro-config astro.config.mjs\n"
    )

    assert _astro_config_violations(mutant) == ["run: pnpm exec dockitty-check-links ../docs --strict"]


# --- required by the terminal gate since #6937 (FR-008) -----------------------------------------
#
# router-gate classifies EVERY jobs-API row of the run, not only its `needs:` (#4208). Leaving the
# job out of `needs:` while it is not exempted would still block the gate on failure, and could be
# read as incomplete while it runs. #6937 makes it required on both halves: it is in `needs:` (so
# the classify-all == classify-needs invariant covers it) and its display name is not in
# router_gate.ADVISORY_JOB_NAMES (which is empty), so its row is classified like any other.


def _gate_verdict(rows: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> str:
    monkeypatch.setattr("sys.stdin", io.StringIO(rows))
    try:
        router_gate.main()
    except SystemExit as stop:
        return f"blocked: {stop.code}"
    return capsys.readouterr().out


def test_the_job_is_required_by_the_terminal_gate() -> None:
    workflow = _workflow()
    needs = set(workflow["jobs"]["router-gate"]["needs"])

    assert JOB in needs, "docs-site must stay in router-gate.needs: (required, #6937)"
    assert JOB not in router_gate.ADVISORY_JOB_NAMES, "a required job is never advisory"


def test_the_advisory_set_is_empty() -> None:
    """#6937 drained its last entry; an advisory job is priced debt (Standing Order #5)."""
    assert not router_gate.ADVISORY_JOB_NAMES


CALLER_ROW = "docs site (doc-kitty build)"  # a called job's rows are reported as `<caller> / <callee>`
CALLED_ROW = f"{CALLER_ROW} / build"


@pytest.mark.parametrize(
    ("row", "conclusion", "blocks"),
    [(CALLED_ROW, conclusion, True) for conclusion in ("failure", "timed_out", "cancelled", "")] + [(CALLER_ROW, "skipped", False)],
)
def test_the_docs_site_row_gates_by_conclusion(
    row: str, conclusion: str, blocks: bool, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A red called-build row blocks; the caller row skipped (job not selected) does not."""
    verdict = _gate_verdict(f"{row}\t{conclusion}\nruff (fast, always-on)\tsuccess\n", monkeypatch, capsys)

    assert verdict.startswith("blocked") is blocks


def test_a_green_docs_site_row_passes_beside_another_failure_row(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """The gate blocks on the OTHER job: docs-site's own green row never masks a red."""
    rows = f"{CALLED_ROW}\tsuccess\nruff (fast, always-on)\tfailure\n"

    assert _gate_verdict(rows, monkeypatch, capsys).startswith("blocked")


# --- required on the run conclusion too (#6937) ------------------------------------------------
#
# The fleet verdict (scripts/ci/fleet_verdict.py), the main-branch P0 intake (scripts/ci/fleet_main.py)
# and skip-if-green (scripts/ci/green_match.py) read the CI Router RUN conclusion, not router-gate.
# A required job must therefore not turn its own failure into a non-blocking one via job-level
# continue-on-error -- the ci-aggregate.yml `sonar-pr` precedent (the workflow-run-conclusion half of
# "non-blocking"). The two halves travel together: a router job carries job-level
# continue-on-error if and only if its display name is in router_gate.ADVISORY_JOB_NAMES.


def _advisory_violations(jobs: dict[str, Any], advisory_names: frozenset[str]) -> list[str]:
    violations = []
    for key, job in jobs.items():
        if not isinstance(job, dict):
            continue
        advisory = job.get("name") in advisory_names
        tolerant = job.get("continue-on-error") is True
        if advisory != tolerant:
            violations.append(f"{key}: advisory={advisory}, job-level continue-on-error={tolerant}")
    return violations


def test_job_level_continue_on_error_is_exactly_the_advisory_set() -> None:
    assert _advisory_violations(_workflow()["jobs"], router_gate.ADVISORY_JOB_NAMES) == []


def test_a_required_job_with_continue_on_error_is_caught() -> None:
    jobs = copy.deepcopy(_workflow()["jobs"])
    jobs[JOB]["continue-on-error"] = True

    assert _advisory_violations(jobs, router_gate.ADVISORY_JOB_NAMES) == [f"{JOB}: advisory=False, job-level continue-on-error=True"]


# --- one shared build definition (#6937 remainder, ADR D-11) -----------------------------------
#
# The router job calls the shared definition, so every step check above reads the steps that
# actually run. What is pinned here is what a real CI run would not catch on its own: the call
# target the step checks follow, the definition's security surface, and that a red row of the
# called job blocks the terminal gate (issue #7484: no YAML-shape restatements).


def test_the_router_job_calls_the_shared_definition() -> None:
    """The step checks read SHARED; this keeps them reading the file the router actually calls."""
    assert _job()["uses"] == SHARED_REF


def test_the_shared_definition_is_only_callable_with_read_only_access() -> None:
    workflow = _shared()
    call = _triggers(workflow)

    assert set(call) == {"workflow_call"}, "no automated trigger: callers own when it runs (and the fork guard)"
    assert "secrets" not in (call["workflow_call"] or {})
    assert workflow["permissions"] == {"contents": "read"}
