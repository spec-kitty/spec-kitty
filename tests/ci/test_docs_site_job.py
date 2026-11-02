"""Pin the ``docs-site`` job: the doc-kitty parallel-run build on pull requests (#6930).

ADR ``docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md`` D-11 puts a
``docs-site`` job in ``ci-router.yml`` behind a ``docs/**`` + ``site/**`` path filter
parsed by ``scripts/ci/gate_selection.py``. It installs the site with the frozen
lockfile and no token, builds it, and uploads ``site/dist``. It is not required yet:
``router-gate``'s ``needs:`` gains it in #6937. DocFX keeps deploying (D-13).

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
DOCS_PAGES = ROOT / ".github" / "workflows" / "docs-pages.yml"
MAKEFILE = ROOT / "Makefile"
SCRUB = ROOT / "tests" / "release" / "ci_retirement_scrub.json"

GROUP = "docs_site"
JOB = "docs-site"
EXPECTED_GLOBS = {
    "docs/**",
    "site/**",
    ".github/workflows/ci-router.yml",
    "scripts/docs/_dockitty_contract.py",
    "scripts/docs/site_contract.py",
}
_SHA_PIN = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
_CORE_GUARD = "(github.repository == 'spec-kitty/spec-kitty' || github.event_name == 'pull_request' || github.event_name == 'workflow_dispatch')"
_ASTRO_CONFIG = "--astro-config astro.config.mjs"
_DOCKITTY_CALL = re.compile(r"\bdockitty-[a-z-]+\b")


def _workflow() -> dict[str, Any]:
    return dict(yaml.safe_load(ROUTER.read_text(encoding="utf-8")))


def _job() -> dict[str, Any]:
    return dict(_workflow()["jobs"][JOB])


def _run_text(job: dict[str, Any]) -> str:
    return "\n".join(str(step["run"]) for step in job.get("steps", []) if "run" in step)


# --- routing (FR-007, C-002) -------------------------------------------------------------------


@pytest.mark.parametrize("path", ["docs/guides/install.md", "docs/_meta/sections.yaml", "site/package.json", "site/pnpm-lock.yaml", "site/astro.config.mjs"])
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


def test_the_group_names_exactly_the_site_inputs() -> None:
    router = load_router()

    assert set(router.filters[GROUP]) == EXPECTED_GLOBS
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


def test_the_job_is_not_required_yet() -> None:
    """``router-gate.needs`` makes a job blocking; the docs-site job joins it in #6937."""
    assert JOB not in _workflow()["jobs"]["router-gate"]["needs"]


# --- the job's steps (FR-007, NFR-001..003) -----------------------------------------------------


def _pin_violations(job: dict[str, Any]) -> list[str]:
    uses = [str(step["uses"]) for step in job.get("steps", []) if "uses" in step]
    return [ref for ref in uses if not ref.startswith("./") and not _SHA_PIN.match(ref.split("#")[0].strip())]


def _credential_violations(job: dict[str, Any]) -> list[str]:
    text = yaml.safe_dump(job)
    found = [token for token in ("secrets.", "github.token", "GITHUB_TOKEN", "NODE_AUTH_TOKEN", "NPM_TOKEN") if token in text]
    permissions = job.get("permissions")
    if permissions not in (None, {"contents": "read"}):
        found.append(f"permissions: {permissions}")
    return found


def test_every_action_is_pinned_by_commit() -> None:
    assert _pin_violations(_job()) == []


def test_a_tag_pinned_action_is_caught() -> None:
    mutant = copy.deepcopy(_job())
    mutant["steps"].append({"uses": "actions/setup-node@v7"})

    assert _pin_violations(mutant) == ["actions/setup-node@v7"]


def test_the_job_uses_no_credential() -> None:
    assert _workflow()["permissions"] == {"contents": "read"}
    assert _credential_violations(_job()) == []


def test_a_token_in_the_job_is_caught() -> None:
    mutant = copy.deepcopy(_job())
    mutant["steps"].append({"run": "pnpm install", "env": {"NPM_CONFIG_USERCONFIG": "${{ secrets.NPMRC }}"}})

    assert _credential_violations(mutant)


def test_the_job_installs_frozen_checks_the_contract_builds_and_uploads() -> None:
    job = _job()
    run = _run_text(job)

    assert "pnpm install --frozen-lockfile" in run
    assert "-m scripts.docs.site_contract --check" in run
    assert "pnpm run build" in run
    uploads = [step for step in job["steps"] if "actions/upload-artifact@" in str(step.get("uses", ""))]
    assert len(uploads) == 1
    assert uploads[0]["with"]["path"] == "site/dist"
    assert uploads[0]["with"]["if-no-files-found"] == "error"


def test_the_job_is_bounded_and_no_step_swallows_a_failure() -> None:
    """Job-level ``continue-on-error`` is the advisory mechanism (below); a step never swallows a failure."""
    job = _job()

    assert 0 < int(job["timeout-minutes"]) <= 20
    assert all("continue-on-error" not in step for step in job["steps"])
    assert not re.search(r"\|\|\s*true\b|\bset\s+\+e\b", _run_text(job))


# --- dockitty-* gates carry --astro-config (FR-009, ADR D-1) ------------------------------------


def _astro_config_violations(text: str) -> list[str]:
    """Every line that calls a ``dockitty-*`` binary without ``--astro-config astro.config.mjs``."""
    return [line.strip() for line in text.splitlines() if _DOCKITTY_CALL.search(line) and not line.lstrip().startswith("#") and _ASTRO_CONFIG not in line]


def test_every_dockitty_call_passes_the_astro_config() -> None:
    assert _astro_config_violations(ROUTER.read_text(encoding="utf-8")) == []
    assert _astro_config_violations(MAKEFILE.read_text(encoding="utf-8")) == []


def test_a_dockitty_call_without_the_astro_config_is_caught() -> None:
    mutant = (
        "        run: pnpm exec dockitty-check-links ../docs --strict\n"
        "        run: pnpm exec dockitty-validate-frontmatter ../docs --astro-config astro.config.mjs\n"
    )

    assert _astro_config_violations(mutant) == ["run: pnpm exec dockitty-check-links ../docs --strict"]


# --- DocFX keeps deploying (C-001) --------------------------------------------------------------


def test_docfx_deploy_is_untouched_by_the_parallel_run() -> None:
    text = DOCS_PAGES.read_text(encoding="utf-8")

    assert "docfx" in text.lower()
    assert "pnpm" not in text and "site/dist" not in text, "the deploy switches to site/dist only at cutover (#6938)"


# --- advisory to the terminal gate until #6937 (FR-008) -----------------------------------------
#
# router-gate classifies EVERY jobs-API row of the run, not only its `needs:` (#4208), so a job kept
# out of `needs:` would still block the gate on failure, and could be read as incomplete while it
# runs. The classifier therefore skips the names in router_gate.ADVISORY_JOB_NAMES, and the
# `needs:` invariant (tests/architectural/test_dual_mode_contract.py) subtracts the same set.


def _gate_verdict(rows: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> str:
    monkeypatch.setattr("sys.stdin", io.StringIO(rows))
    try:
        router_gate.main()
    except SystemExit as stop:
        return f"blocked: {stop.code}"
    return capsys.readouterr().out


def test_the_job_is_advisory_to_the_terminal_gate() -> None:
    assert _job()["name"] in router_gate.ADVISORY_JOB_NAMES


@pytest.mark.parametrize("conclusion", ["failure", "", "timed_out", "cancelled"])
def test_an_advisory_row_never_blocks_the_gate(conclusion: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    rows = f"{_job()['name']}\t{conclusion}\nruff (fast, always-on)\tsuccess\n"

    assert _gate_verdict(rows, monkeypatch, capsys).startswith("router-gate OK")


def test_a_required_row_still_blocks_beside_an_advisory_one(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    rows = f"{_job()['name']}\tsuccess\nruff (fast, always-on)\tfailure\n"

    assert _gate_verdict(rows, monkeypatch, capsys).startswith("blocked")


def test_every_advisory_name_is_a_router_job_outside_router_gate_needs() -> None:
    """Self-draining: #6937 adds the job to `needs:` and must then delete its advisory entry."""
    jobs = _workflow()["jobs"]
    needs = set(jobs["router-gate"]["needs"])
    by_name = {str(job.get("name")): key for key, job in jobs.items() if isinstance(job, dict)}

    assert router_gate.ADVISORY_JOB_NAMES, "the set is empty once #6937 lands; delete this test with it"
    for name in router_gate.ADVISORY_JOB_NAMES:
        assert name in by_name, f"advisory name {name!r} names no ci-router.yml job"
        assert by_name[name] not in needs, f"{by_name[name]} is required (in router-gate needs); drop it from ADVISORY_JOB_NAMES"


# --- advisory to the run conclusion too (review cycle 1) ----------------------------------------
#
# The fleet verdict (scripts/ci/fleet_verdict.py), the main-branch P0 intake (scripts/ci/fleet_main.py)
# and skip-if-green (scripts/ci/green_match.py) read the CI Router RUN conclusion, not router-gate.
# A failed advisory job must not turn the run red, so it carries job-level continue-on-error -- the
# ci-aggregate.yml `sonar-pr` precedent ("the workflow-run-conclusion half of the non-blocking
# guarantee"). The two halves travel together: a router job has job-level continue-on-error if and
# only if its display name is in router_gate.ADVISORY_JOB_NAMES, so #6937 removes both at once.


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


def test_an_advisory_job_without_continue_on_error_is_caught() -> None:
    jobs = copy.deepcopy(_workflow()["jobs"])
    jobs[JOB].pop("continue-on-error", None)

    assert _advisory_violations(jobs, router_gate.ADVISORY_JOB_NAMES) == [f"{JOB}: advisory=True, job-level continue-on-error=False"]


def test_a_required_job_with_continue_on_error_is_caught() -> None:
    jobs = copy.deepcopy(_workflow()["jobs"])
    jobs["ruff"]["continue-on-error"] = True

    assert "ruff: advisory=False, job-level continue-on-error=True" in _advisory_violations(jobs, router_gate.ADVISORY_JOB_NAMES)
