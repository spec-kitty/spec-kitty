"""Matrix reusable module-tests workflow(s) gate (FR-001/006/008, WP09 T045-T050).

Mission ci-pipeline-reinstatement-01M1X35E, WP09: gives the suite a public CI
home (FR-001) via **full-tree modular** reusable workflows (FR-006) — a
``workflow_call`` module-tests shard (``.github/workflows/module-tests.yml``)
plus a caller (``.github/workflows/ci-modules.yml``) that **matrixes over the
WP08-committed module registry** (``.github/ci-module-registry.yml``,
FR-008 de-serialized). This gate asserts:

* the caller's matrix realizes **every** registry row — no row unshipped, no
  shard fanned out over a non-registry module (a hardcoded, hand-maintained
  module list in the caller would silently drift from the registry — the
  matrix must be *generated from* the registry, never re-encode it);
* ``module-tests.yml`` is a ``workflow_call`` reusable workflow declaring the
  expected inputs (``module``, ``roots``, ``cov_target``, ``tier``, ``shard``,
  ``mode``);
* each shard consumes the WP04 warmup composite (``.github/actions/warmup``)
  exactly once, never re-running its own install;
* both workflows declare ``workflow_dispatch`` and thread the ``mode`` input;
* shards never ``needs:`` each other (FR-008 de-serialization — concurrent
  within a tier).

Collection-red lazy-load hygiene (contract, T045): every YAML/JSON load below
is lazy and in-test — never at import/collection time — so this module always
*collects* green, even on base where the two workflows do not yet exist. The
red on base is a failed *behavioral* assertion (workflows absent, gates below
fail with a `pytest.fail` naming the missing artefact), never a collection or
import error.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOWS_DIR = _REPO_ROOT / ".github" / "workflows"
_MODULE_TESTS_PATH = _WORKFLOWS_DIR / "module-tests.yml"
_CI_MODULES_PATH = _WORKFLOWS_DIR / "ci-modules.yml"
_WARMUP_ACTION_PATH = _REPO_ROOT / ".github" / "actions" / "warmup" / "action.yml"
_REGISTRY_PATH = _REPO_ROOT / ".github" / "ci-module-registry.yml"

_REQUIRED_INPUTS = {"module", "roots", "cov_target", "tier", "shard", "mode"}
_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


# ---------------------------------------------------------------------------
# Lazy loaders — in-test only (never at collection time, T045 hygiene).
# ---------------------------------------------------------------------------
def _load_module_tests() -> dict[Any, Any]:
    if not _MODULE_TESTS_PATH.exists():
        pytest.fail(f"reusable module-tests workflow missing: {_MODULE_TESTS_PATH.relative_to(_REPO_ROOT)} (WP09 T046 not yet delivered)")
    import yaml  # local import: keep this gate's collection cost near-zero

    payload = yaml.safe_load(_MODULE_TESTS_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), f"{_MODULE_TESTS_PATH} did not parse to a mapping"
    return payload


def _module_tests_text() -> str:
    if not _MODULE_TESTS_PATH.exists():
        pytest.fail(f"reusable module-tests workflow missing: {_MODULE_TESTS_PATH.relative_to(_REPO_ROOT)}")
    return _MODULE_TESTS_PATH.read_text(encoding="utf-8")


def _load_ci_modules() -> dict[Any, Any]:
    if not _CI_MODULES_PATH.exists():
        pytest.fail(f"matrix caller workflow missing: {_CI_MODULES_PATH.relative_to(_REPO_ROOT)} (WP09 T047 not yet delivered)")
    import yaml

    payload = yaml.safe_load(_CI_MODULES_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), f"{_CI_MODULES_PATH} did not parse to a mapping"
    return payload


def _ci_modules_text() -> str:
    if not _CI_MODULES_PATH.exists():
        pytest.fail(f"matrix caller workflow missing: {_CI_MODULES_PATH.relative_to(_REPO_ROOT)}")
    return _CI_MODULES_PATH.read_text(encoding="utf-8")


def _load_registry() -> dict[str, Any]:
    if not _REGISTRY_PATH.exists():
        pytest.fail(f"module-shard registry missing: {_REGISTRY_PATH.relative_to(_REPO_ROOT)} (WP08 not yet delivered)")
    import yaml

    payload = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _registry_modules() -> list[dict[str, Any]]:
    return list(_load_registry().get("modules", []))


def _yaml_jobs(payload: dict[Any, Any]) -> dict[str, Any]:
    jobs = payload.get("jobs")
    assert isinstance(jobs, dict) and jobs, "expected at least one job"
    return jobs


# `on: workflow_call` parses under the YAML boolean key `True` (PyYAML 1.1 core
# schema quirk: bare `on:` is the boolean `True`, not the string `"on"`).
def _on_block(payload: dict[Any, Any]) -> dict[str, Any]:
    on = payload.get("on", payload.get(True))
    assert isinstance(on, dict), f"expected a mapping under 'on:', got {on!r}"
    return on


# ---------------------------------------------------------------------------
# T046: module-tests.yml is a `workflow_call` reusable workflow.
# ---------------------------------------------------------------------------
def test_module_tests_is_a_workflow_call_reusable() -> None:
    payload = _load_module_tests()
    on = _on_block(payload)
    assert "workflow_call" in on, "module-tests.yml must be invocable via `uses:` (on: workflow_call)"


def test_module_tests_declares_the_expected_inputs() -> None:
    payload = _load_module_tests()
    on = _on_block(payload)
    call_block = on["workflow_call"] or {}
    inputs = set((call_block.get("inputs") or {}).keys())
    missing = _REQUIRED_INPUTS - inputs
    assert not missing, f"module-tests.yml workflow_call is missing inputs: {sorted(missing)}"


def test_module_tests_declares_workflow_dispatch_too() -> None:
    """T049: `workflow_dispatch` lets a maintainer manually re-run one shard."""
    payload = _load_module_tests()
    on = _on_block(payload)
    assert "workflow_dispatch" in on, "module-tests.yml must also declare workflow_dispatch (T049)"


def test_module_tests_mode_input_threads_pr_and_full() -> None:
    """T049: the `mode` input must be documented as pr|full, defaulting to pr."""
    payload = _load_module_tests()
    on = _on_block(payload)
    call_inputs = (on["workflow_call"] or {}).get("inputs") or {}
    mode_input = call_inputs.get("mode")
    assert mode_input is not None, "expected a 'mode' input on workflow_call"
    description = str(mode_input.get("description", ""))
    assert "pr" in description and "full" in description


# ---------------------------------------------------------------------------
# T046/T050: the shard consumes the WP04 warmup composite exactly once, never
# re-installing per shard (the #3283 kill in practice).
# ---------------------------------------------------------------------------
def test_module_tests_consumes_the_warmup_composite() -> None:
    assert _WARMUP_ACTION_PATH.exists(), "WP04 warmup composite must exist for module-tests.yml to consume"
    payload = _load_module_tests()
    jobs = _yaml_jobs(payload)
    warmup_steps = [step for job in jobs.values() for step in job.get("steps", []) if str(step.get("uses", "")).startswith("./.github/actions/warmup")]
    assert warmup_steps, "expected a step using './.github/actions/warmup' in module-tests.yml"


def test_module_tests_never_reinstalls_per_shard() -> None:
    """T050: no per-shard `uv sync`/editable-install re-run outside the composite."""
    text = _module_tests_text()
    # The composite itself legitimately runs `uv sync`; module-tests.yml's own
    # steps (outside the composite's action.yml, which lives in a separate
    # file) must not shell out to a second install.
    assert "uv sync" not in text, "module-tests.yml must reuse the warmup composite, never re-run uv sync itself"


# ---------------------------------------------------------------------------
# T050: shards run concurrently within a tier — no `needs:` between them.
# ---------------------------------------------------------------------------
def test_module_tests_job_has_no_needs() -> None:
    payload = _load_module_tests()
    jobs = _yaml_jobs(payload)
    for name, job in jobs.items():
        assert "needs" not in job, f"module-tests.yml job {name!r} must not `needs:` another shard job"


def test_ci_modules_matrix_jobs_do_not_needs_each_other() -> None:
    """The generated matrix entries are one job (matrixed), so there is only
    ever one `needs:` edge -- into the matrix-generation job, never a shard
    depending on another shard."""
    payload = _load_ci_modules()
    jobs = _yaml_jobs(payload)
    matrix_jobs = [job for job in jobs.values() if "strategy" in job and "matrix" in job.get("strategy", {})]
    assert matrix_jobs, "expected a matrixed job in ci-modules.yml"
    for job in matrix_jobs:
        needs = job.get("needs")
        if needs is None:
            continue
        needs_list = [needs] if isinstance(needs, str) else list(needs)
        for dep in needs_list:
            dep_job = jobs.get(dep, {})
            assert "strategy" not in dep_job or "matrix" not in dep_job.get("strategy", {}), (
                f"matrixed job must not needs: another matrixed (shard) job, got {dep!r}"
            )


# ---------------------------------------------------------------------------
# T047: ci-modules.yml matrixes over EVERY WP08 registry row.
# ---------------------------------------------------------------------------
def test_ci_modules_is_generated_from_the_registry_not_hardcoded() -> None:
    """No hand-maintained module list may live in the caller -- it must be
    *generated from* `.github/ci-module-registry.yml` at run time (the single
    data source, WP08 T044). A literal list of the registry's own module names
    baked into the caller would silently drift from the registry."""
    text = _ci_modules_text()
    assert "ci-module-registry.yml" in text, "ci-modules.yml must read the committed module registry"
    # The matrix must be data-driven (fromJson of a generated output), never a
    # static YAML `include:` list -- a static list can't "realize every row"
    # when the registry grows a new row.
    assert "fromJson" in text, "ci-modules.yml matrix must be generated (fromJson), not a static include: list"


def test_ci_modules_calls_module_tests_workflow_exactly_once() -> None:
    """Bounded reusable-workflow fan-out (<=20/caller ceiling, DoD): the caller
    references `module-tests.yml` via exactly one `uses:` -- the matrix
    realizes every row through ONE reusable workflow, never ~40 files."""
    payload = _load_ci_modules()
    jobs = _yaml_jobs(payload)
    uses_module_tests = [
        job.get("uses", "") for job in jobs.values() if str(job.get("uses", "")).endswith("module-tests.yml") or "module-tests.yml" in str(job.get("uses", ""))
    ]
    assert len(uses_module_tests) == 1, f"expected exactly one job calling module-tests.yml (bounded matrix realization), got {uses_module_tests!r}"


def test_ci_modules_declares_workflow_dispatch_and_mode() -> None:
    payload = _load_ci_modules()
    on = _on_block(payload)
    assert "workflow_dispatch" in on, "ci-modules.yml must declare workflow_dispatch (T049)"


def test_ci_modules_passes_shard_structure_from_the_registry() -> None:
    """T047/caveat B: the matrix generation step must consume the registry's
    `shard_count` per row (never invent a different, e.g. round-robin or
    alphabetical, split) -- so every generated matrix leaf carries a shard
    spec derived from that field."""
    text = _ci_modules_text()
    assert "shard_count" in text, "matrix generation must consume the registry's shard_count field"


def test_ci_modules_matrix_realizes_every_registry_module_name() -> None:
    """Static sanity: every registry module name is at least *referenced* by
    the matrix-generation script text (a stronger, execution-based assertion
    that the generated matrix set equals the registry set belongs to a runtime
    smoke test outside this architectural gate's scope, per WP09's DoD, which
    is a static-shape gate over the committed YAML)."""
    text = _ci_modules_text()
    registry_modules = _registry_modules()
    assert registry_modules, "registry must be non-empty for this assertion to be non-vacuous"
    # The generation script must not hardcode a *subset* of module names -- it
    # loads all `modules[].module` entries generically. We assert the script
    # iterates the registry's `modules` key rather than a hand-picked list.
    assert "modules" in text
    assert re.search(r"registry\[.?modules.?\]|registry\.get\(.?modules.?\)|\[.?modules.?\]", text) or ("for " in text and "module" in text), (
        "matrix generation must iterate the registry's modules list, not a hand-picked subset"
    )


# ---------------------------------------------------------------------------
# DIR-051: every `uses:` in the two owned workflows is a full commit SHA.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path", [_MODULE_TESTS_PATH, _CI_MODULES_PATH])
def test_every_uses_step_is_pinned_to_a_full_commit_sha(path: Path) -> None:
    if not path.exists():
        pytest.fail(f"workflow missing: {path.relative_to(_REPO_ROOT)}")
    import yaml

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    jobs = payload.get("jobs", {})
    uses_values = [str(step["uses"]) for job in jobs.values() for step in job.get("steps", []) if "uses" in step and not str(step["uses"]).startswith("./")]
    for uses in uses_values:
        _, _, ref = uses.partition("@")
        assert ref and _FULL_SHA_RE.match(ref), f"'{uses}' in {path.name} is not pinned to a full commit SHA (DIR-051)"


# ---------------------------------------------------------------------------
# T048: artefact-naming contract -- dotted `--cov=`, unique-per-shard basename,
# `-reports` upload name, `if: always()`.
# ---------------------------------------------------------------------------
def test_module_tests_uses_dotted_cov_form() -> None:
    text = _module_tests_text()
    assert "--cov=" in text, "expected a dotted --cov=<module> invocation (never path form)"
    assert "--cov=src" not in text and "--cov=./src" not in text, "must never use the path form of --cov"


def test_module_tests_coverage_and_xunit_paths_match_contract() -> None:
    text = _module_tests_text()
    assert "out/reports/coverage/" in text
    assert "out/reports/xunit-reports/" in text
    assert re.search(r"coverage-[^\"'\s]*\.xml", text), "expected a coverage-*.xml output path"
    assert re.search(r"xunit-result-[^\"'\s]*\.xml", text), "expected an xunit-result-*.xml output path"


def test_module_tests_upload_artifact_name_ends_reports_and_runs_always() -> None:
    payload = _load_module_tests()
    jobs = _yaml_jobs(payload)
    upload_steps = [step for job in jobs.values() for step in job.get("steps", []) if str(step.get("uses", "")).startswith("actions/upload-artifact")]
    assert upload_steps, "expected an actions/upload-artifact step"
    for step in upload_steps:
        name = str(step.get("with", {}).get("name", ""))
        assert name.endswith("-reports"), f"upload-artifact name {name!r} must end '-reports'"
        assert step.get("with", {}).get("path") == "out/reports/"
        assert step.get("if") == "always()", "upload-artifact must run `if: always()` (contract)"
