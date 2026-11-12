"""Pin the ``docs-site`` job: the doc-kitty build on pull requests (#6930, #6937).

ADR ``docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md`` D-11 puts a
``docs-site`` job in ``ci-router.yml`` behind a ``docs/**`` + ``site/**`` path filter
parsed by ``scripts/ci/gate_selection.py``. The job calls the ONE shared build definition,
``.github/workflows/docs-site-build.yml`` (#6937), which installs the site with the frozen
lockfile and no token, builds it, and uploads ``site/dist`` (or, for the Pages deploy at
#6938, the Pages artifact). The step checks below read that called job, the steps that
actually run. Since #6937 the gate is **required**: ``router-gate``'s ``needs:`` names it
and it carries no ``continue-on-error``. Since #6938 the Pages deploy publishes this build,
and #6943 retired the legacy generator it replaced (D-13).

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
#: The dockitty-* bins that read no site config, so take no ``--astro-config``: ``dockitty-assert-diagrams``
#: reads only the built HTML and refuses any argument but ``<dist>`` (exit 2; doc-kitty 1042a40, #314).
_NO_ASTRO_CONFIG_BINS = frozenset({"dockitty-assert-diagrams"})


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
        "scripts/docs/site_built_check_llms.py",
        "scripts/docs/site_built_check_render.py",
        "scripts/docs/site_link_gates.py",
        "scripts/docs/site_live_probe.py",
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


def test_no_step_swallows_a_failure() -> None:
    """A required job never swallows a failure: no step-level ``continue-on-error`` and no shell fallback."""
    job = _build_job()

    assert job["steps"], "the build job carries the steps (non-vacuity)"
    assert all("continue-on-error" not in step for step in job["steps"])
    assert not re.search(r"\|\|\s*true\b|\bset\s+\+e\b", _run_text(job))


# --- dockitty-* gates carry --astro-config (FR-009, ADR D-1) ------------------------------------


def _astro_config_violations(text: str) -> list[str]:
    """Every line that calls a ``dockitty-*`` binary that reads the site config without ``--astro-config astro.config.mjs``."""
    return [
        line.strip()
        for line in text.splitlines()
        if not line.lstrip().startswith("#") and set(_DOCKITTY_CALL.findall(line)) - _NO_ASTRO_CONFIG_BINS and _ASTRO_CONFIG not in line
    ]


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


def test_only_the_config_free_bin_is_exempt_from_the_astro_config() -> None:
    """The exemption names one bin: a config-reading call on the same line is still caught."""
    exempt = "        run: pnpm exec dockitty-assert-diagrams dist\n"
    mixed = "        run: pnpm exec dockitty-assert-diagrams dist && pnpm exec dockitty-check-links ../docs\n"

    assert _astro_config_violations(exempt) == []
    assert _astro_config_violations(mixed) == [mixed.strip()]


# --- doc-kitty's diagram bins (#6100, spec-kitty/doc-kitty#314 at 1042a40) ----------------------
#
# The no-plantuml.com guard runs as doc-kitty's `dockitty-plantuml-guard` bin, not as an inline
# `node --input-type=module` import of the toolkit's library. The built HTML's diagram markup is
# checked by doc-kitty's `dockitty-assert-diagrams dist`, after the build and before core's
# built-site check, whose `diagrams` surface keeps only the per-route count. Both the shared job
# and `make docs-site` run them in that order.

_GUARD = "pnpm exec dockitty-plantuml-guard --astro-config astro.config.mjs"
_ASSERT_DIAGRAMS = "pnpm exec dockitty-assert-diagrams dist"
_BUILD = "pnpm run build"
_BUILT_CHECK = "-m scripts.docs.site_built_check site/dist"
_INLINE_NODE = "--input-type"


def _step_runs(job: dict[str, Any]) -> list[tuple[str, str]]:
    """``(working-directory, run)`` of every run step, in order."""
    return [(str(step.get("working-directory", "")), str(step["run"])) for step in job.get("steps", []) if "run" in step]


def _make_docs_site_lines(makefile: str) -> list[str]:
    """The recipe lines of the ``docs-site:`` target, in order."""
    lines = makefile.split("\ndocs-site: ##", 1)[1].splitlines()[1:]
    return [line.strip() for line in lines[: next(i for i, line in enumerate(lines) if not line.startswith(("\t", " ")))]]


def _diagram_bin_violations(runs: list[str]) -> list[str]:
    """What is wrong with the order of the guard, the build, the bin and the built-site check in *runs*."""
    found = [f"inline node guard: {run.strip()}" for run in runs if _INLINE_NODE in run]
    needles = {"plantuml-guard": _GUARD, "build": _BUILD, "assert-diagrams": _ASSERT_DIAGRAMS, "built-site check": _BUILT_CHECK}
    at = {name: next((i for i, run in enumerate(runs) if needle in run), -1) for name, needle in needles.items()}
    missing = [f"missing: {name}" for name, index in at.items() if index < 0]
    if missing:
        return found + missing
    if not at["plantuml-guard"] < at["build"]:
        found.append("plantuml-guard does not run before the build")
    if not at["build"] < at["assert-diagrams"] < at["built-site check"]:
        found.append("assert-diagrams does not run after the build and before the built-site check")
    return found


def test_the_shared_job_runs_doc_kittys_diagram_bins_in_order() -> None:
    runs = _step_runs(_build_job())

    assert _diagram_bin_violations([run for _, run in runs]) == []
    assert {wd for wd, run in runs if _GUARD in run or _ASSERT_DIAGRAMS in run} == {"site"}


def test_make_docs_site_runs_doc_kittys_diagram_bins_in_order() -> None:
    lines = _make_docs_site_lines(MAKEFILE.read_text(encoding="utf-8"))

    assert _diagram_bin_violations(lines) == []
    assert all(line.startswith("cd site && ") for line in lines if _GUARD in line or _ASSERT_DIAGRAMS in line)


def test_a_missing_misplaced_or_inline_diagram_bin_is_caught() -> None:
    good = [_GUARD, _BUILD, _ASSERT_DIAGRAMS, f"python3 {_BUILT_CHECK} --docs docs"]

    assert _diagram_bin_violations(good) == []
    assert _diagram_bin_violations([good[0], good[1], good[3]]) == ["missing: assert-diagrams"]
    assert _diagram_bin_violations([good[0], good[1], good[3], good[2]]) == ["assert-diagrams does not run after the build and before the built-site check"]
    assert _diagram_bin_violations([good[1], good[0], good[2], good[3]]) == ["plantuml-guard does not run before the build"]
    assert _diagram_bin_violations(["node --input-type=module -e x", good[1], good[2], good[3]]) == [
        "inline node guard: node --input-type=module -e x",
        "missing: plantuml-guard",
    ]


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


# --- the live-site probe on every build (#6938) -------------------------------------------------
#
# The post-deploy smoketest (docs-pages.yml, #2361) probes the production site; the shared build
# first probes the site it just built, served over local HTTP, so a pull request that removes a URL
# class from the ledgers, or a build that stops answering one, fails before any deploy. The Pages
# artifact's name is an input; the deploy uses its default, `github-pages`.


def _step_index(job: dict[str, Any], fragment: str) -> int:
    (index,) = [i for i, step in enumerate(job["steps"]) if fragment in str(step.get("run", "")) or fragment in str(step.get("uses", ""))]
    return index


def test_the_build_probes_the_built_site_over_local_http_before_any_upload() -> None:
    job = _build_job()
    probe = job["steps"][_step_index(job, "scripts.docs.site_live_probe")]
    run = str(probe["run"])

    assert _step_index(job, "pnpm run build") < _step_index(job, "scripts.docs.site_live_probe")
    assert _step_index(job, "scripts.docs.site_live_probe") < _step_index(job, "actions/upload-artifact@")
    assert _step_index(job, "scripts.docs.site_live_probe") < _step_index(job, "actions/upload-pages-artifact@")
    assert "http.server" in run and "site/dist" in run
    assert "--attempts 1" in run
    assert probe["env"]["PYTHONPATH"] == ".:src"
    assert probe.get("timeout-minutes", 99) <= 1, "the local probe adds well under 30 s; a hang must not hold the job"


def test_the_pages_artifact_name_is_an_input_defaulting_to_github_pages() -> None:
    job = _build_job()
    inputs = _triggers(_shared())["workflow_call"]["inputs"]
    upload = job["steps"][_step_index(job, "actions/upload-pages-artifact@")]

    assert inputs["pages-artifact-name"] == {
        "description": inputs["pages-artifact-name"]["description"],
        "type": "string",
        "required": False,
        "default": "github-pages",
    }
    assert upload["with"]["name"] == "${{ inputs.pages-artifact-name }}"


# --- one PlantUML renderer, CI and local (#6936, ADR D-11) -------------------------------------
#
# The shared job runs the PlantUML server as a `services:` container; `make docs-site` renders
# against the same image started by `make docs-site-plantuml`. A real CI run proves the CI image
# renders and refuses remote includes (the canary); it cannot see the Makefile. What is pinned
# here is that the two name ONE image, by digest, so a half-bumped digest (CI moved, local not, or
# the reverse) or a tag-only image (a re-tag swaps the renderer) is caught.

_PLANTUML_IMAGE = re.compile(r"^plantuml/plantuml-server:[^@\s]+@sha256:[0-9a-f]{64}$")
_MAKE_PLANTUML_IMAGE = re.compile(r"^DOCS_SITE_PLANTUML_IMAGE\s*:=\s*(\S+)\s*$", re.MULTILINE)


def _plantuml_image_violations(job: dict[str, Any], makefile: str) -> list[str]:
    image = str(((job.get("services") or {}).get("plantuml") or {}).get("image", ""))
    found = []
    if not _PLANTUML_IMAGE.match(image):
        found.append(f"services.plantuml.image is not a digest-pinned plantuml-server image: {image!r}")
    local = _MAKE_PLANTUML_IMAGE.search(makefile)
    if local is None or local.group(1) != image:
        found.append(f"Makefile DOCS_SITE_PLANTUML_IMAGE {local.group(1) if local else None!r} is not the CI image {image!r}")
    return found


def test_ci_and_make_docs_site_render_against_one_digest_pinned_plantuml_image() -> None:
    assert _plantuml_image_violations(_build_job(), MAKEFILE.read_text(encoding="utf-8")) == []


def test_a_half_bumped_or_tag_only_plantuml_image_is_caught() -> None:
    job = _build_job()
    makefile = MAKEFILE.read_text(encoding="utf-8")
    image = job["services"]["plantuml"]["image"]
    other = image[:-1] + ("0" if image[-1] != "0" else "1")
    half_bumped = makefile.replace(image, other)
    tag_only = copy.deepcopy(job)
    tag_only["services"]["plantuml"]["image"] = image.split("@", 1)[0]

    assert _plantuml_image_violations(job, half_bumped) == [f"Makefile DOCS_SITE_PLANTUML_IMAGE {other!r} is not the CI image {image!r}"]
    assert _plantuml_image_violations(tag_only, makefile)[0].startswith("services.plantuml.image is not a digest-pinned")
