"""Pin the nightly/doc-tooling caches and the DocFX version to their contracts.

These are static workflow assertions: the cache paths and keys are the
guardrail that keeps a JVM or docs build from either paying a cold download
every night or, worse, restoring test results or an unpinned tool. The
checksum-verification behaviour itself is tested in
``tests/ci/test_gradle_tool_cache.py`` and ``tests/docs/test_plantuml_invoke.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOWS = _REPO_ROOT / ".github" / "workflows"
_CACHE_ACTION_PREFIX = "actions/cache@"


def _workflow(name: str) -> dict[str, Any]:
    loaded = yaml.safe_load((_WORKFLOWS / name).read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{name} did not parse to a mapping"
    return loaded


def _triggers(workflow: dict[str, Any]) -> dict[str, Any]:
    for key in ("on", True):
        if key in workflow:
            triggers = workflow[key]
            assert isinstance(triggers, dict), "`on:` block is not a mapping"
            return triggers
    pytest.fail("workflow has no `on:` trigger block")


def _steps(workflow: dict[str, Any], job: str) -> list[dict[str, Any]]:
    steps = workflow["jobs"][job]["steps"]
    assert isinstance(steps, list)
    return steps


def _cache_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [step for step in steps if str(step.get("uses") or "").startswith(_CACHE_ACTION_PREFIX)]


def _step_named(steps: list[dict[str, Any]], fragment: str) -> dict[str, Any]:
    return steps[_step_index(steps, fragment)]


def _step_index(steps: list[dict[str, Any]], fragment: str) -> int:
    for index, step in enumerate(steps):
        if fragment.lower() in str(step.get("name", "")).lower():
            return index
    pytest.fail(f"no step named like {fragment!r}")


def _cache_paths(step: dict[str, Any]) -> str:
    return str(step["with"]["path"])


def _cache_key(step: dict[str, Any]) -> str:
    return str(step["with"]["key"])


def _assert_no_test_results_is_cached(step: dict[str, Any]) -> None:
    paths = _cache_paths(step)
    assert "test-results" not in paths, f"test results must never be cached: {paths!r}"
    assert "acceptance-jvm/build" not in paths, f"build output must never be cached: {paths!r}"
    assert "build/acceptance" not in paths, f"acceptance pass output must never be cached: {paths!r}"


def test_acceptance_jvm_caches_the_tool_and_only_dependency_modules() -> None:
    steps = _steps(_workflow("ci-nightly.yml"), "acceptance-bdd")
    caches = _cache_steps(steps)
    assert len(caches) == 2, f"expected exactly the tool and dependency caches, found {[c.get('name') for c in caches]}"

    tool_cache, dependency_cache = caches
    assert _cache_paths(tool_cache) == "${{ runner.temp }}/tools"
    assert "hashFiles('acceptance-jvm/tools/pins.json')" in _cache_key(tool_cache)
    assert _cache_paths(dependency_cache) == "~/.gradle/caches/modules-2"
    assert "acceptance-jvm/gradle/verification-metadata.xml" in _cache_key(dependency_cache)
    for cache in caches:
        assert cache["uses"].startswith(_CACHE_ACTION_PREFIX)
        assert len(cache["uses"].split("@", 1)[1].split()[0]) == 40, "the cache action must stay SHA-pinned"
        _assert_no_test_results_is_cached(cache)


def test_acceptance_jvm_uses_the_verified_gradle_cache_helper() -> None:
    steps = _steps(_workflow("ci-nightly.yml"), "acceptance-bdd")
    install = _step_named(steps, "Install the pinned Gradle")
    run = str(install["run"])
    assert "scripts/ci/gradle_tool_cache.py ensure" in run
    assert "--pins acceptance-jvm/tools/pins.json" in run
    assert '--installer "$tools/install_tools.py"' in run, "a cache miss must still install through the canonical checksum-verified installer"


def test_acceptance_jvm_cache_steps_run_before_the_gradle_install_and_scenarios() -> None:
    steps = _steps(_workflow("ci-nightly.yml"), "acceptance-bdd")
    tool_cache = _step_index(steps, "Gradle tool cache")
    dependency_cache = _step_index(steps, "Gradle dependency cache")
    install = _step_index(steps, "Install the pinned Gradle")
    gating = next(i for i, step in enumerate(steps) if "-Pacceptance.pass=gating" in str(step.get("run") or ""))
    assert tool_cache < install
    assert dependency_cache < install
    assert install < gating


def test_sonar_caches_the_gradle_tool_and_dependencies_never_test_results() -> None:
    steps = _steps(_workflow("sonar.yml"), "scan")
    caches = _cache_steps(steps)
    assert len(caches) == 2, f"expected exactly the tool and dependency caches, found {[c.get('name') for c in caches]}"
    assert {_cache_paths(cache) for cache in caches} == {"${{ runner.temp }}/tools", "~/.gradle/caches/modules-2"}
    for cache in caches:
        _assert_no_test_results_is_cached(cache)
    install = _step_named(steps, "Install the pinned Gradle")
    assert "scripts/ci/gradle_tool_cache.py ensure" in str(install["run"])


def test_docs_pages_pins_docfx_and_caches_the_versioned_tool() -> None:
    workflow = _workflow("docs-pages.yml")
    build_job = workflow["jobs"]["build"]
    assert build_job["env"]["DOCFX_VERSION"] == "2.81.0", "the DocFX version is an intentional pin, not whatever is latest"

    steps = _steps(workflow, "build")
    docfx_cache = _step_named(steps, "DocFX tool cache")
    assert _cache_paths(docfx_cache).split() == ["~/.dotnet/tools", "~/.nuget/packages"]
    assert "${{ env.DOCFX_VERSION }}" in _cache_key(docfx_cache)

    install = _step_named(steps, "Install DocFX")
    run = str(install["run"])
    assert 'dotnet tool install --global docfx --version "$DOCFX_VERSION"' in run
    assert "dotnet tool install -g docfx\n" not in run, "an unpinned floating DocFX install must not return"


def test_docs_pages_caches_the_checksum_verified_plantuml_jar() -> None:
    steps = _steps(_workflow("docs-pages.yml"), "build")
    jar_cache = _step_named(steps, "PlantUML jar cache")
    assert _cache_paths(jar_cache) == "plantuml.jar"
    assert "hashFiles('scripts/docs/plantuml_pins.json')" in _cache_key(jar_cache)

    render = _step_named(steps, "Render PlantUML schema diagrams")
    run = str(render["run"])
    assert "plantuml_invoke.ensure_jar" in run, "the cached jar must be re-verified through the canonical helper"
    assert "urllib.request" not in run, "the duplicate download path was replaced by the checksum-verifying provisioner"


def test_router_docs_tests_restore_and_save_the_plantuml_jar_before_running() -> None:
    """``tests (docs)`` must not depend on the release-asset download each run.

    The PlantUML render tests provision ``plantuml.jar`` at the repository root.
    A GitHub release-asset 504 redded every docs PR until the job restored the
    jar from the cache docs-pages.yml fills, provisioned it before the tests and
    saved it independently of the test outcome.
    """
    steps = _steps(_workflow("ci-router.yml"), "tests-docs")
    restore = _step_index(steps, "Restore the checksum-verified PlantUML jar cache")
    provision = _step_index(steps, "Provision the checksum-verified PlantUML jar")
    save = _step_index(steps, "Save the checksum-verified PlantUML jar cache")
    run_tests = _step_index(steps, "Run tests")
    assert restore < provision < save < run_tests

    pages_key = _cache_key(_step_named(_steps(_workflow("docs-pages.yml"), "build"), "PlantUML jar cache"))
    for index in (restore, save):
        assert _cache_paths(steps[index]) == "plantuml.jar"
        assert _cache_key(steps[index]) == pages_key, "share the docs-pages cache entry"
    assert str(steps[restore]["uses"]).startswith("actions/cache/restore@")
    assert str(steps[save]["uses"]).startswith("actions/cache/save@")
    assert "plantuml_invoke.ensure_jar" in str(steps[provision]["run"]), "provision through the sha256-verifying helper"


def test_docs_pages_push_trigger_is_main_only_where_the_deploy_runs() -> None:
    triggers = _triggers(_workflow("docs-pages.yml"))
    assert triggers["push"]["branches"] == ["main"], "the deploy job only runs on refs/heads/main, so a 2.x push builds an unused site"
