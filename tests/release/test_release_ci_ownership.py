"""Ownership guards for the interim restored CI producers."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

pytestmark = [pytest.mark.fast]

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
CONVERGENCE_MAP = ROOT / "docs" / "convergence" / "interim-ci-producer.md"
RELEASE_CHECKLIST = ROOT / "RELEASE_CHECKLIST.md"
DOCS_REFERENCE_INDEX = ROOT / "docs" / "development" / "reference" / "index.md"
DRIFT_WORKFLOW = "check-spec-kitty-events-alignment.yml"
DRIFT_SCRIPT = Path("scripts/release/check_shared_package_drift.py")
COMPATIBILITY_MANIFEST = Path(".kittify/release/shared-package-compatibility.json")

RESTORED_WORKFLOWS = {
    "ci-quality.yml",
    "protect-main.yml",
    "ci-windows.yml",
    "docs-pages.yml",
    "check-spec-kitty-events-alignment.yml",
    "release-readiness.yml",
    "release.yml",
}

# WP01 (FR-012 / C-001): the `introduced` disposition models net-new workflows
# that have NO pre-fork ancestor and therefore cannot be expressed in the closed
# restore/defer/never-restore vocabulary. The set is FROZEN at exactly the seven
# net-new workflow names this mission adds — an 8th net-new workflow is not
# representable here and reopens WP01 (documented) rather than being appended
# silently downstream.
INTRODUCED_WORKFLOWS = {
    "sonar.yml",
    "ci-router.yml",
    "module-tests.yml",
    "ci-modules.yml",
    "ci-aggregate.yml",
    "ci-nightly.yml",
    "packs.yml",
}

# WP01 (FR-017 / C-010): the dead EXPERIMENTAL-fenced Blacksmith producer is
# retired; the reinstated CI on this repo is now the primary/sole producer.
RETIRED_EXPERIMENTAL_WORKFLOW = ".github/workflows/ci.yml"

# The private EXPERIMENTAL repo-identity fence that must not survive on any
# public job once `ci.yml` is retired (FR-017 / C-010).
EXPERIMENTAL_REPO_FENCE = "spec-kitty/EXPERIMENTAL-spec-kitty"

UPSTREAM_WORKFLOW_PATHS = {
    "all-contributors-normalize.yml",
    "all-contributors-sync.yml",
    "canonical-producer-lint.yml",
    "check-spec-kitty-events-alignment.yml",
    "ci-flake-report.yml",
    "ci-quality.yml",
    "ci-windows.yml",
    "docs-build-pr.yml",
    "docs-freshness.yml",
    "docs-pages.yml",
    "doctrine-charter-tests.yml",
    "drift-detector.yml",
    "module-doctrine-fast.yml",
    "module-doctrine-integration.yml",
    "module-kernel.yml",
    "module-packs.yml",
    "mutation-remediation.md",
    "orchestrator-boundary.yml",
    "performance.yml",
    "plantuml-egress-spike.yml",
    "plugin-validate.yml",
    "project-sync-consent-evidence.yml",
    "protect-main.yml",
    "regen-assets.yml",
    "release-readiness.yml",
    "release.yml",
    "review-verdict-durability.yml",
    "teamspace-mission-state-readiness.yml",
    "ui-e2e.yml",
}

UPSTREAM_SCRIPT_PATHS = {
    "scripts/check-release-exists.sh",
    "scripts/create-github-release.sh",
    "scripts/create-release-packages.sh",
    "scripts/generate-release-notes.sh",
    "scripts/get-next-version.sh",
    "scripts/update-version.sh",
}


def load_workflow(name: str) -> dict[str | bool, Any]:
    return cast(dict[str | bool, Any], yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8")))


def workflow_text(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_shared_package_drift_preserves_candidate_trust_and_skip_policy() -> None:
    workflow = load_workflow(DRIFT_WORKFLOW)
    assert workflow["name"] == "Check Shared Package Drift"
    assert workflow["permissions"] == {"contents": "read"}
    jobs = workflow["jobs"]
    assert set(jobs) == {"prepare-candidate-metadata", "verify-drift"}
    prepare, verify = jobs["prepare-candidate-metadata"], jobs["verify-drift"]
    assert prepare["name"] == "Prepare candidate package metadata"
    assert verify["name"] == "Verify shared package drift"
    policy = "${{ !contains(github.event.pull_request.labels.*.name, 'pr:deferred') && !contains(github.event.pull_request.labels.*.name, 'pr:skip-ci') }}"
    assert prepare["if"] == verify["if"] == policy
    assert verify["needs"] == ["prepare-candidate-metadata"]
    checkout = next(step for step in verify["steps"] if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["ref"] == "${{ github.event_name == 'pull_request' && github.event.pull_request.base.sha || github.sha }}"
    upload = next(step for step in prepare["steps"] if step.get("uses", "").startswith("actions/upload-artifact@"))
    download = next(step for step in verify["steps"] if step.get("uses", "").startswith("actions/download-artifact@"))
    assert upload["with"]["name"] == download["with"]["name"] == "candidate-package-metadata"
    assert set(upload["with"]["path"].splitlines()) == {"pyproject.toml", "uv.lock", str(COMPATIBILITY_MANIFEST)}
    assert download["with"]["path"] == "candidate"
    # PyYAML's YAML 1.1 loader treats the unquoted GitHub Actions "on" key as True.
    triggers = workflow[True]
    assert set(triggers) == {"pull_request", "push", "schedule", "workflow_dispatch"}
    for event in ("pull_request", "push"):
        assert triggers[event]["branches"] == ["main", "develop", "2.x"]
        assert set(triggers[event]["paths"]) == {
            "pyproject.toml",
            "uv.lock",
            str(COMPATIBILITY_MANIFEST),
            "scripts/release/**",
            f".github/workflows/{DRIFT_WORKFLOW}",
        }
    assert triggers["schedule"] == [{"cron": "11 2 * * *"}]


def test_shared_package_drift_is_local_and_unconditional() -> None:
    workflow = load_workflow(DRIFT_WORKFLOW)
    job = workflow["jobs"]["verify-drift"]
    step = next(step for step in job["steps"] if step.get("name") == "Validate shared package drift")
    assert "if" not in step, "Local validation must run even when no SaaS read secret is available"
    assert "continue-on-error" not in job
    assert "continue-on-error" not in step
    text = workflow_text(DRIFT_WORKFLOW)
    for retired_reference in ("fetch_refs", "--saas-pyproject", "secrets.", "CROSS_REPO_TOKEN", "HAS_SAAS_READ_TOKEN"):
        assert retired_reference not in text
    run = step["run"]
    assert f"python {DRIFT_SCRIPT}" in run
    assert "--pyproject candidate/pyproject.toml" in run
    assert "--lockfile candidate/uv.lock" in run
    assert f"--compatibility-manifest candidate/{COMPATIBILITY_MANIFEST}" in run


@pytest.mark.parametrize(
    ("mutation", "diagnostic"),
    [
        ("none", "Shared package drift check passed."),
        ("lock", "uv.lock version 0.0.0 is outside CLI constraint"),
        ("manifest", "does not match release authority 0.0.0"),
        ("range", "does not match release authority"),
        ("retired", "Retired runtime package must not be a CLI dependency"),
        ("missing-manifest", "Compatibility manifest not found:"),
    ],
)
def test_shared_package_drift_workflow_executes_real_local_validator_without_secret(
    tmp_path: Path,
    mutation: str,
    diagnostic: str,
) -> None:
    job = load_workflow(DRIFT_WORKFLOW)["jobs"]["verify-drift"]
    step = next(step for step in job["steps"] if step.get("name") == "Validate shared package drift")
    assert "if" not in step, "The workflow must not skip the local validator without a secret"
    candidate = tmp_path / "candidate"
    for relative in (Path("pyproject.toml"), Path("uv.lock"), COMPATIBILITY_MANIFEST):
        destination = candidate / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    script = tmp_path / DRIFT_SCRIPT
    script.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / DRIFT_SCRIPT, script)
    manifest_path = candidate / COMPATIBILITY_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    events = next(entry for entry in manifest["packages"] if entry["package"] == "spec-kitty-events")
    if mutation == "lock":
        lock = candidate / "uv.lock"
        text, count = re.subn(
            r'(name = "spec-kitty-events"\nversion = ")[^"]+',
            r"\g<1>0.0.0",
            lock.read_text(encoding="utf-8"),
        )
        assert count == 1
        lock.write_text(text, encoding="utf-8")
    elif mutation == "manifest":
        events["locked_version"] = "0.0.0"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif mutation in {"retired", "range"}:
        pyproject = candidate / "pyproject.toml"
        text = pyproject.read_text(encoding="utf-8")
        if mutation == "retired":
            text, count = re.subn(r"(dependencies\s*=\s*\[)", r'\1"spec-kitty-runtime==0.0.0",', text, count=1)
        else:
            text, count = re.subn(r'"spec-kitty-events[^"]+"', '"spec-kitty-events>=0,<1"', text, count=1)
        assert count == 1
        pyproject.write_text(text, encoding="utf-8")
    elif mutation == "missing-manifest":
        manifest_path.unlink()
    env = dict(os.environ)
    for key in ("SPEC_KITTY_SAAS_READ_TOKEN", "CROSS_REPO_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        env.pop(key, None)
    env["HAS_SAAS_READ_TOKEN"] = "false"
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", step["run"]],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode == (0 if mutation == "none" else 1), output
    assert diagnostic in output


# The map ROW — not filesystem presence — is the enforcer subject: a disposition
# is asserted over the rows registered in `docs/convergence/interim-ci-producer.md`.
_DISPOSITION_ROW_RE = re.compile(
    r"^\| `([^`]+)` \| (restore|never-restore|defer|introduced) \|",
    re.MULTILINE,
)


def map_rows(text: str | None = None) -> dict[str, str]:
    """Parse the convergence map into a ``{path: disposition}`` row index."""
    body = CONVERGENCE_MAP.read_text(encoding="utf-8") if text is None else text
    return {match.group(1): match.group(2) for match in _DISPOSITION_ROW_RE.finditer(body)}


def disposition_paths(disposition: str, text: str | None = None) -> set[str]:
    """Full-path row set registered under one disposition (map-ROW subject)."""
    return {path for path, disp in map_rows(text).items() if disp == disposition}


def introduced_workflow_names(text: str | None = None) -> set[str]:
    """Basenames registered under the `introduced` disposition."""
    return {Path(path).name for path in disposition_paths("introduced", text)}


# The closed pre-fork vocabulary, kept distinct from the net-new `introduced`
# disposition so the legacy exact-set cover-test never conflates the two.
LEGACY_DISPOSITIONS = frozenset({"restore", "never-restore", "defer"})


def legacy_disposition_rows(text: str | None = None) -> dict[str, str]:
    """Map rows registered under the closed pre-fork vocabulary only."""
    return {path: disp for path, disp in map_rows(text).items() if disp in LEGACY_DISPOSITIONS}


def test_release_checklist_marks_deferred_publish_workflows_as_p3_4b_prerequisite() -> None:
    checklist = RELEASE_CHECKLIST.read_text(encoding="utf-8")
    assert "P3.4b prerequisite" in checklist
    assert "release.yml" in checklist
    assert "release-readiness.yml" in checklist


def test_reduced_ci_quality_has_exact_jobs() -> None:
    workflow = load_workflow("ci-quality.yml")

    # The per-PR `sonarcloud` reporter (spec-kitty#3993) was REMOVED from this
    # set by mission sonar-per-pr-coverage-reuse (#4334): it re-ran the whole
    # fast tier under `pytest --cov` to obtain a coverage report the
    # ci-modules shards had already produced for the same commit. The per-PR
    # Sonar report now lives in ci-aggregate.yml's `sonar-pr` job, which
    # consumes those shard artefacts instead of measuring a second time
    # (FR-001/FR-003/NFR-001). This file's producers execute no test suite at
    # all -- `tests/architectural/test_suite_jobs_gate_blocking.py` asserts
    # exactly that, and `test_no_duplicate_suite_execution.py` reds if any
    # change-triggered job reaches pytest outside the authorised matrix.
    assert set(workflow["jobs"]) == {
        "lint",
        "build-wheel",
        "clean-install-verification",
        "uv-lock-check",
        "quality-gate",
    }
    assert workflow["jobs"]["clean-install-verification"]["needs"] == ["build-wheel"]


def test_clean_install_check_name_is_branch_protection_ready() -> None:
    workflow = load_workflow("ci-quality.yml")
    job = workflow["jobs"]["clean-install-verification"]

    assert job["name"] == "Clean install verification"
    assert "spec-kitty-runtime" in workflow_text("ci-quality.yml")
    assert "tests/fixtures/clean_install_fixture_mission" in workflow_text("ci-quality.yml")


def test_quality_gate_blocks_every_reduced_producer_job() -> None:
    workflow = load_workflow("ci-quality.yml")
    gate = workflow["jobs"]["quality-gate"]

    assert set(gate["needs"]) == {
        "lint",
        "build-wheel",
        "clean-install-verification",
        "uv-lock-check",
    }
    assert "NEEDS_JSON: ${{ toJSON(needs) }}" in workflow_text("ci-quality.yml")


def test_ci_windows_has_no_sync_path_filters() -> None:
    workflow = load_workflow("ci-windows.yml")
    changes = workflow["jobs"]["changes"]["steps"]
    filter_step = next(step for step in changes if step.get("id") == "filter")
    filters = filter_step["with"]["filters"]

    assert "tests/sync/" not in filters
    assert workflow["jobs"]["windows-critical"]["runs-on"] == "windows-latest"


def test_ci_windows_filter_can_read_pull_request_files() -> None:
    workflow = load_workflow("ci-windows.yml")

    # Least-privilege permissions live at job scope (#4342 GitHub Actions
    # hardening, S8264): the 'changes' job runs dorny/paths-filter and must be
    # able to read PR files, so the read grants are asserted on that job rather
    # than at the (now absent) workflow level.
    assert workflow["jobs"]["changes"]["permissions"] == {
        "contents": "read",
        "pull-requests": "read",
    }


@pytest.mark.parametrize("name", ["ci-quality.yml", "ci-windows.yml"])
def test_public_ci_uses_released_dependencies_without_private_credentials(name: str) -> None:
    text = workflow_text(name)

    assert "SK_CI_TOKEN" not in text
    assert "Configure private git dependencies" not in text


def test_ci_windows_install_uses_runner_temp() -> None:
    workflow = load_workflow("ci-windows.yml")
    steps = workflow["jobs"]["windows-critical"]["steps"]
    install_step = next(step for step in steps if step.get("name") == "Install spec-kitty-cli (editable) + test deps")

    assert install_step["env"]["TMP"] == "${{ runner.temp }}"
    assert install_step["env"]["TEMP"] == "${{ runner.temp }}"


def test_private_factory_ci_fence_is_retired_from_public_workflows() -> None:
    """FR-017 / C-010: the dead EXPERIMENTAL-fenced `ci.yml` producer is retired.

    Reconciles the former ``test_private_factory_ci_is_scoped_to_experimental_repo``
    (which hard-asserted the fence): the file is gone, the map registers it as
    ``never-restore``, and the invariant that NO surviving public workflow carries
    the private EXPERIMENTAL fence / runner / token is still enforced non-vacuously.
    """
    assert not (WORKFLOWS / "ci.yml").exists()
    assert map_rows()[RETIRED_EXPERIMENTAL_WORKFLOW] == "never-restore"

    surviving = sorted(WORKFLOWS.glob("*.yml"))
    assert surviving, "expected surviving public workflows to guard against"
    for workflow in surviving:
        text = workflow.read_text(encoding="utf-8")
        assert EXPERIMENTAL_REPO_FENCE not in text, workflow.name
        assert "blacksmith" not in text.lower(), workflow.name


def test_docs_pages_deploys_only_from_promotion_repo_and_fails_transient_setup_errors() -> None:
    workflow = load_workflow("docs-pages.yml")
    pages_job = workflow["jobs"]["pages"]
    probe_step, setup_step = pages_job["steps"]
    build_job = workflow["jobs"]["build"]
    deploy_job = workflow["jobs"]["deploy"]

    assert pages_job["outputs"] == {"configured": "${{ steps.probe-pages.outputs.available }}"}
    assert probe_step["id"] == "probe-pages"
    assert probe_step["env"]["GITHUB_TOKEN"] == "${{ github.token }}"
    assert 'status="$(curl' in probe_step["run"]
    assert "200)" in probe_step["run"]
    assert 'echo "available=true" >> "$GITHUB_OUTPUT"' in probe_step["run"]
    assert "404)" in probe_step["run"]
    assert 'echo "available=false" >> "$GITHUB_OUTPUT"' in probe_step["run"]
    assert "::error::GitHub Pages configuration probe failed with HTTP $status." in probe_step["run"]
    assert setup_step["id"] == "setup-pages"
    assert setup_step["if"] == "steps.probe-pages.outputs.available == 'true'"
    assert setup_step["uses"] == "actions/configure-pages@v6"
    assert "continue-on-error" not in setup_step
    assert build_job["needs"] == ["pages"]
    assert build_job["if"] == "needs.pages.outputs.configured == 'true' && needs.pages.result == 'success'"
    assert deploy_job["if"] == "github.repository == 'Priivacy-ai/spec-kitty' && github.ref == 'refs/heads/main' && needs.build.result == 'success'"

    publication_policy = DOCS_REFERENCE_INDEX.read_text(encoding="utf-8")
    assert "intentionally deployed from the promotion-only" in publication_policy
    assert "does not claim the custom domain" in publication_policy
    assert "controller's promotion loop" in publication_policy


@pytest.mark.parametrize("name", sorted(RESTORED_WORKFLOWS))
def test_restored_workflows_use_stock_runners(name: str) -> None:
    text = workflow_text(name)

    assert "blacksmith" not in text.lower()
    assert "runner-group" not in text.lower()


def test_release_wheel_gate_counts_charter_offering_and_skills() -> None:
    workflow = load_workflow("release.yml")
    step = next(step for step in workflow["jobs"]["build-release"]["steps"] if step.get("name") == "Verify wheel contents")
    run = step["run"]

    assert "git ls-files src/charter/offering" in run
    assert "find " in run
    assert "wheel_check/charter/offering" in run
    assert "git ls-files src/charter/offering/skills" in run
    assert "wheel_check/charter/offering/skills" in run
    assert "git ls-files src/doctrine" not in run


def test_release_readiness_cutover_guard_uses_public_lock_dependencies() -> None:
    workflow = load_workflow("release-readiness.yml")
    job = workflow["jobs"]["cutover-guard"]
    job_dump = repr(job)

    assert "pip install -e ." not in job_dump
    assert "git+https" not in job_dump
    assert ".cutover-deps" not in job_dump
    assert "grep -vE" not in job_dump

    install = next(step for step in job["steps"] if step.get("name") == "Install the source-only guard environment")
    assert "uv export --frozen --no-dev" in install["run"]
    assert "python -m pip install -r .cutover-requirements.lock.txt" in install["run"]

    guard = next(step for step in job["steps"] if step.get("name") == "Run cutover guard (fail-closed on any un-cut-over mission)")
    assert "PYTHONPATH=src" in guard["run"]
    assert "from specify_cli.cli.commands.cutover_guard import cutover_guard" in guard["run"]


def _legacy_expected_paths() -> set[str]:
    # The retired EXPERIMENTAL producer is registered `never-restore` in lockstep
    # with its file retirement (FR-017 / C-010), so it joins the legacy cover set.
    return (
        {f".github/workflows/{name}" for name in UPSTREAM_WORKFLOW_PATHS}
        | {f".github/workflows/{name}" for name in UPSTREAM_SCRIPT_PATHS}
        | {RETIRED_EXPERIMENTAL_WORKFLOW}
    )


def test_convergence_map_dispositions_every_upstream_workflow_and_script() -> None:
    rows = legacy_disposition_rows()
    expected = _legacy_expected_paths()

    assert set(rows) == expected, f"convergence map path mismatch: missing={sorted(expected - set(rows))}, extra={sorted(set(rows) - expected)}"
    assert {rows[path] for path in expected if path.endswith(".yml")} <= set(LEGACY_DISPOSITIONS)


def test_introduced_disposition_and_ci_yml_retirement_are_registered() -> None:
    """WP01 ATDD anchor (RED on mission base).

    Pins two behaviours the WP delivers:

    * the map + enforcer carry a fourth `introduced` disposition whose set holds
      at least the mission's net-new workflow names (contract: `sonar.yml`), and
    * the dead EXPERIMENTAL-fenced `ci.yml` producer is retired — the file is
      gone and no surviving public workflow carries the EXPERIMENTAL repo fence.

    Red-on-base reasons: the map has no `introduced` vocabulary yet, and
    `.github/workflows/ci.yml` still exists carrying the fence.
    """
    introduced = introduced_workflow_names()
    assert "sonar.yml" in introduced
    assert introduced >= INTRODUCED_WORKFLOWS

    assert not (WORKFLOWS / "ci.yml").exists()
    for workflow in WORKFLOWS.glob("*.yml"):
        assert EXPERIMENTAL_REPO_FENCE not in workflow.read_text(encoding="utf-8")


def test_introduced_disposition_is_the_frozen_seven_net_new_set() -> None:
    """`introduced` is an EXACT set — exactly the seven net-new workflow names.

    Frozen for the mission (schema contract §Invariants, C-001): an 8th net-new
    workflow is not representable here and reopens WP01 rather than being
    appended silently downstream. Content equality (not a `len == N` cardinality
    assertion) so the exact membership is the enforced contract.
    """
    assert introduced_workflow_names() == INTRODUCED_WORKFLOWS


def test_introduced_and_restore_rows_forbid_private_runner_and_token() -> None:
    """Invariant 2: `introduced` + `restore` workflows use **stock runners** and
    carry **no `SK_CI_TOKEN` on public jobs**.

    The map ROW is the subject, so the map documents the invariant. The stock-runner
    half is text-checked over every `restore` + `introduced` file present on disk
    (the private `blacksmith` runner must appear nowhere). The token half applies to
    *public jobs*: net-new `introduced` producers must be tokenless (forward-guarded
    here for when the downstream WPs land the files), while the reduced public CI
    producers are guarded by ``test_public_ci_uses_released_dependencies...``;
    ``release.yml`` legitimately resolves pinned private git dependencies with the
    token at release time and is not a public CI job.
    """
    map_text = CONVERGENCE_MAP.read_text(encoding="utf-8")
    assert "stock runners" in map_text
    assert "SK_CI_TOKEN" in map_text

    restore_and_introduced = {Path(path).name for path in disposition_paths("restore")} | introduced_workflow_names()
    for name in sorted(restore_and_introduced):
        path = WORKFLOWS / name
        if not path.exists():
            continue
        assert "blacksmith" not in path.read_text(encoding="utf-8").lower(), name

    for name in sorted(introduced_workflow_names()):
        path = WORKFLOWS / name
        if not path.exists():
            continue
        assert "SK_CI_TOKEN" not in path.read_text(encoding="utf-8"), name


def test_enforcer_scope_runs_on_every_workflow_changing_pr() -> None:
    """Invariant 4: the ownership enforcer runs on every workflow-changing PR, not
    only a tag push — a load-bearing part of the mission's governance spine."""
    map_text = CONVERGENCE_MAP.read_text(encoding="utf-8")
    assert "runs on every workflow-changing PR" in map_text


def test_deleting_any_disposition_row_reds_the_enforcer() -> None:
    """SO#5 non-vacuity: the enforcer keys on map ROWS, so removing any row from
    any disposition set changes the parsed sets — the guard is not vacuous and
    adding `introduced` did not weaken the pre-existing three sets."""
    baseline = map_rows()
    lines = CONVERGENCE_MAP.read_text(encoding="utf-8").splitlines(keepends=True)
    sample_paths = {
        "restore": ".github/workflows/ci-quality.yml",
        "defer": ".github/workflows/regen-assets.yml",
        "never-restore": ".github/workflows/performance.yml",
        "introduced": ".github/workflows/sonar.yml",
    }
    for disposition, path in sample_paths.items():
        assert baseline.get(path) == disposition, f"fixture drift for {path}"
        mutated = "".join(line for line in lines if f"`{path}`" not in line)
        assert path not in map_rows(mutated)
        assert disposition_paths(disposition, mutated) != disposition_paths(disposition)


@pytest.mark.parametrize("job_name", ["build-release", "publish-pypi"])
@pytest.mark.parametrize(
    ("version", "is_prerelease"),
    [
        ("3.2.6.1", False),
        ("3.2.6.1rc1", True),
        ("3.2.6.1RC1", True),
        ("3.2.6.1ALPHA", True),
        ("3.2.7BETA2", True),
        ("3.2.6.1alpha", True),
        ("3.2.7beta2", True),
        ("3.2.7", False),
    ],
)
def test_release_workflow_classifies_hotfix_channel(tmp_path: Path, job_name: str, version: str, is_prerelease: bool) -> None:
    workflow = load_workflow("release.yml")
    script = next(step["run"] for step in workflow["jobs"][job_name]["steps"] if step.get("name") == "Classify release channel")
    output = tmp_path / "github-output"

    result = subprocess.run(
        ["bash", "-eu", "-c", script],
        env={**os.environ, "RELEASE_TAG": f"v{version}", "GITHUB_OUTPUT": str(output)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output.read_text().strip() == f"is_prerelease={str(is_prerelease).lower()}"
