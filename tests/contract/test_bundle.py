"""Planted-violation tests for ``contracts/tools/bundle.py`` (FR-014, FR-018; E-1 ruling of 2026-10-02).

The released single-file contract is written by the Python resolver, byte-deterministically, and
is faithful to OpenAPI 3.1 (the openapi-yaml generator drops ``const``, ``unevaluatedProperties``,
``x-provisional`` and more, so it is never an artefact). The JVM build only *consumes* it: it
validates the split root and the written bundle and re-emits the bundle as the Java parser sees it
(``javaview``, used by the parity check). There is no JVM in the unit-test environment, so the Gradle
run is an injected runner and the resolver step is real. Each violation is asserted on its own planted
fixture with a clean control.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

from tests.contract._loader import load_tool

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

TOOLS_DIR = Path(__file__).resolve().parents[2] / "contracts" / "tools"
FIXTURES = TOOLS_DIR / "fixtures" / "bundle"
CLEAN_ROOT = FIXTURES / "roots" / "clean"
NO_ROOT = FIXTURES / "roots" / "no_root"
# invalid YAML, written at run time: the leak scan parses every committed .yaml
UNREADABLE_MODULE_YAML = "openapi: 3.1.0\ninfo:\n  title: Unreadable fixture\n  version: [1.0.0\npaths: {}\n"
SPIKE_ROOT = TOOLS_DIR / "fixtures" / "spike"
PLANTS_ROOT = TOOLS_DIR / "fixtures" / "client_smoke" / "plants"
SCRIPT = TOOLS_DIR / "bundle.py"

Runner = Callable[[list[str]], tuple[int, str]]


@pytest.fixture(scope="module")
def bundler() -> Iterator[ModuleType]:
    with pytest.MonkeyPatch.context() as mp:
        yield load_tool(mp, SCRIPT, "bundle_under_test", syspath=TOOLS_DIR)


def _tool(name: str) -> str | None:
    return f"/fixture/bin/{name}"


def _gradle(returncode: int = 0, output: str = "BUILD SUCCESSFUL") -> Runner:
    def run(_command: list[str]) -> tuple[int, str]:
        return returncode, output

    return run


def _run(bundler: ModuleType, root: Path, out: Path, runner: Runner, *extra: str, which: Callable[[str], str | None] = _tool) -> tuple[int, str]:
    lines: list[str] = []
    code = bundler.run(["--root", str(root), "--out", str(out), *extra], runner=runner, which=which, out=lines.append)
    return code, "\n".join(lines)


def _bundle(out: Path, module: str = "full") -> dict[str, Any]:
    loaded = yaml.safe_load((out / "bundle" / module / "openapi.yaml").read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


# -- the released bundle is written by the resolver ------------------------------------------------


def test_clean_control_writes_and_checks_the_bundle_and_prints_counts(bundler: ModuleType, tmp_path: Path) -> None:
    code, output = _run(bundler, SPIKE_ROOT, tmp_path / "out", _gradle(), "--module", "full")

    assert code == 0, output
    assert output.splitlines()[-1] == "counts: modules=1 bundles=1 path_items=5"


def test_the_bundle_keeps_every_31_construct_the_openapi_yaml_generator_dropped(bundler: ModuleType, tmp_path: Path) -> None:
    _run(bundler, SPIKE_ROOT, tmp_path / "out", _gradle(), "--module", "full")
    document = _bundle(tmp_path / "out")
    mission = document["paths"]["/missions/{missionId}"]["get"]["responses"]["200"]["content"]["application/json"]
    schema = mission["schema"]
    pong = document["paths"]["/ping"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert document["info"]["summary"].startswith("A one-module fixture"), "info.summary is kept"
    assert pong["properties"]["ok"] == {"const": True} and pong["additionalProperties"] is False, "const and closed objects are kept"
    assert schema["unevaluatedProperties"] is False and schema["properties"]["kind"] == {"const": "mission"}
    assert schema["properties"]["title"]["type"] == ["string", "null"], "type arrays are kept, not rewritten to nullable"
    assert "x-provisional" in schema["properties"]["nextAction"] and "x-provisional" in schema["properties"]["stale"]
    assert schema["properties"]["nextAction"]["oneOf"][1] == {"type": "null"}, "oneOf with null is kept"
    assert schema["properties"]["summary"]["description"].startswith("A sibling keyword"), "$ref siblings are kept"
    assert schema["x-source"]["symbol"] == "Mission" and schema["properties"]["isDone"]["x-derived"]["inputs"] == ["lifecycle", "workPackages"]
    assert schema["examples"] and "example" not in schema, "the authored examples list is kept and nothing is invented"
    assert mission["examples"]["discarded"]["value"]["title"] is None, "null members of an Example Object are kept"
    assert "text/event-stream" in document["paths"]["/missions/{missionId}/events"]["get"]["responses"]["200"]["content"]


def test_the_bundle_is_the_resolver_tree_and_holds_no_reference(bundler: ModuleType, tmp_path: Path) -> None:
    with pytest.MonkeyPatch.context() as mp:
        mp.syspath_prepend(str(TOOLS_DIR))
        import contract_resolver

        tree = contract_resolver.resolve(SPIKE_ROOT / "full").tree
    _run(bundler, SPIKE_ROOT, tmp_path / "out", _gradle(), "--module", "full")
    text = (tmp_path / "out" / "bundle" / "full" / "openapi.yaml").read_text(encoding="utf-8")

    assert yaml.safe_load(text) == tree
    assert "$ref" not in text


def test_two_runs_write_byte_identical_bundles_with_a_documented_key_order(bundler: ModuleType, tmp_path: Path) -> None:
    _run(bundler, SPIKE_ROOT, tmp_path / "a", _gradle(), "--module", "full")
    _run(bundler, SPIKE_ROOT, tmp_path / "b", _gradle(), "--module", "full")
    first = (tmp_path / "a" / "bundle" / "full" / "openapi.yaml").read_bytes()
    second = (tmp_path / "b" / "bundle" / "full" / "openapi.yaml").read_bytes()

    assert first == second
    assert first.endswith(b"\n") and not first.endswith(b"\n\n")
    top = list(yaml.safe_load(first))
    assert top == [key for key in bundler.TOP_LEVEL_ORDER if key in top], "top-level keys follow the documented order"
    assert list(yaml.safe_load(first)["info"]) == sorted(yaml.safe_load(first)["info"]), "every other mapping is key-sorted"


def test_rendering_is_independent_of_the_source_key_order(bundler: ModuleType) -> None:
    one = {"paths": {}, "openapi": "3.1.0", "info": {"b": 1, "a": 2}}
    other = {"info": {"a": 2, "b": 1}, "openapi": "3.1.0", "paths": {}}

    assert bundler.render_bundle(one) == bundler.render_bundle(other)


# -- planted bundle violations -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("empty_bundle", "BUNDLE_EMPTY"),
        ("few_paths_bundle", "FEWER_THAN_FIVE_PATHS"),
        ("external_ref_bundle", "UNRESOLVED_REFERENCE_LEFT"),
        ("dangling_ref_bundle", "UNRESOLVED_REFERENCE_LEFT"),
    ],
)
def test_each_planted_bundle_fails_with_its_code_naming_the_module(bundler: ModuleType, tmp_path: Path, fixture: str, expected: str) -> None:
    staged = tmp_path / "bundle" / "alpha"
    staged.mkdir(parents=True)
    shutil.copy(FIXTURES / f"{fixture}.yaml", staged / "openapi.yaml")
    report = bundler.Report()

    bundler.check_bundle("alpha", tmp_path, 5, report)

    assert [line.split(": ")[1] for line in report.findings] == [expected]
    assert report.findings[0].startswith(f"CONTRACT-CHECK bundle: {expected}: alpha")


def test_an_absent_bundle_file_is_an_empty_bundle_and_names_what_was_staged(bundler: ModuleType, tmp_path: Path) -> None:
    stray = tmp_path / "bundle" / "alpha" / "openapi" / "openapi.yaml"
    stray.parent.mkdir(parents=True)
    stray.write_text("openapi: 3.1.0\n", encoding="utf-8")
    report = bundler.Report()

    bundler.check_bundle("alpha", tmp_path, 5, report)

    assert "BUNDLE_EMPTY: alpha" in report.findings[0] and "openapi/openapi.yaml" in report.findings[0]


def test_a_module_below_the_path_floor_fails_and_the_floor_is_a_parameter(bundler: ModuleType, tmp_path: Path) -> None:
    code, output = _run(bundler, CLEAN_ROOT, tmp_path / "a", _gradle())
    relaxed_code, _ = _run(bundler, CLEAN_ROOT, tmp_path / "b", _gradle(), "--min-paths", "0")

    assert code == 1 and "FEWER_THAN_FIVE_PATHS: alpha" in output
    assert relaxed_code == 0


def test_a_module_the_resolver_refuses_is_a_violation_and_never_reaches_gradle(bundler: ModuleType, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(command: list[str]) -> tuple[int, str]:
        calls.append(command)
        return 0, ""

    code, output = _run(bundler, PLANTS_ROOT, tmp_path / "out", runner, "--module", "dangling_ref", "--min-paths", "0")

    assert code == 1
    assert "CONTRACT-CHECK bundle: RESOLVE_FAILED: dangling_ref: UNRESOLVED_REF" in output
    assert calls == []
    assert output.splitlines()[-1] == "counts: modules=1 bundles=0 path_items=0"


def test_a_module_with_an_unreadable_file_prints_the_stable_line_and_the_counts_line(bundler: ModuleType, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(command: list[str]) -> tuple[int, str]:
        calls.append(command)
        return 0, ""

    unreadable_root = tmp_path / "unreadable"
    (unreadable_root / "alpha").mkdir(parents=True)
    (unreadable_root / "alpha" / "openapi.yaml").write_text(UNREADABLE_MODULE_YAML, encoding="utf-8")

    code, output = _run(bundler, unreadable_root, tmp_path / "out", runner, "--min-paths", "0")

    assert code == 1
    assert "CONTRACT-CHECK bundle: RESOLVE_FAILED: alpha: UNREADABLE" in output
    assert calls == []
    assert output.splitlines()[-1] == "counts: modules=1 bundles=0 path_items=0"


# -- cannot do the job -------------------------------------------------------------------------------


def test_no_module_cannot_do_its_job(bundler: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()

    code, output = _run(bundler, tmp_path / "empty", tmp_path / "out", _gradle())

    assert code == 2
    assert "NO_MODULE" in output
    assert output.splitlines()[-1] == "counts: modules=0 bundles=0 path_items=0"


def test_a_module_directory_without_a_root_document_cannot_do_its_job(bundler: ModuleType, tmp_path: Path) -> None:
    code, output = _run(bundler, NO_ROOT, tmp_path / "out", _gradle())

    assert code == 2
    assert "MODULE_WITHOUT_ROOT: orphan" in output


@pytest.mark.parametrize(("missing", "expected"), [("java", "JVM_MISSING"), ("gradle", "GRADLE_MISSING")])
def test_a_missing_tool_cannot_do_its_job(bundler: ModuleType, tmp_path: Path, missing: str, expected: str) -> None:
    def which(name: str) -> str | None:
        return None if name == missing else _tool(name)

    code, output = _run(bundler, SPIKE_ROOT, tmp_path / "out", _gradle(), "--module", "full", which=which)

    assert code == 2
    assert expected in output


_CONFIG_FAILURE = (
    "FAILURE: Build failed with an exception.\n\n* Where:\nBuild file 'contracts/build.gradle' line: 25\n\n* What went wrong:\n"
    "A problem occurred configuring root project 'contracts'.\n> Could not create task ':validate_full'.\n"
)


@pytest.mark.parametrize(
    ("canned", "expected"),
    [
        ((FIXTURES / "gradle_plugin_failure.txt").read_text(encoding="utf-8"), "PLUGIN_RESOLUTION_FAILED"),
        ((FIXTURES / "gradle_verification_failure.txt").read_text(encoding="utf-8"), "DEPENDENCY_VERIFICATION_FAILED"),
        (_CONFIG_FAILURE, "BUILD_SCRIPT_FAILED"),
    ],
)
def test_toolchain_failures_cannot_do_the_job(bundler: ModuleType, tmp_path: Path, canned: str, expected: str) -> None:
    code, output = _run(bundler, SPIKE_ROOT, tmp_path / "out", _gradle(1, canned), "--module", "full")

    assert code == 2
    assert expected in output


@pytest.mark.parametrize("task", ["validate_full", "validateBundle_full"])
def test_a_rejected_specification_is_a_violation_for_the_split_root_and_for_the_bundle(bundler: ModuleType, tmp_path: Path, task: str) -> None:
    text = f"Spec is invalid.\n\nIssues:\n\n\tattribute paths.'/p0'(get).responses is missing\n\n* What went wrong:\nExecution failed for task ':{task}'.\n"

    code, output = _run(bundler, SPIKE_ROOT, tmp_path / "out", _gradle(1, text), "--module", "full")

    assert code == 1
    assert "VALIDATION_FAILED: full" in output and "attribute paths" in output


def test_output_inside_the_repository_is_refused(bundler: ModuleType) -> None:
    code, output = _run(bundler, SPIKE_ROOT, TOOLS_DIR / "bundle-output-must-not-be-here", _gradle(), "--module", "full")

    assert code == 2
    assert "OUT_INSIDE_REPOSITORY" in output


def test_the_gradle_command_validates_the_split_root_and_the_bundle_and_never_uses_a_daemon(bundler: ModuleType, tmp_path: Path) -> None:
    seen: list[list[str]] = []

    def runner(command: list[str]) -> tuple[int, str]:
        seen.append(command)
        return 0, ""

    _run(bundler, SPIKE_ROOT, tmp_path / "out", runner, "--module", "full", "--write-verification-metadata")

    command = seen[0]
    assert command[0] == "/fixture/bin/gradle" and "--no-daemon" in command
    assert any(part.startswith("-PcontractsRoot=") for part in command) and any(part.startswith("-PoutDir=") for part in command)
    assert command[command.index("--write-verification-metadata") + 1] == "sha256"
    assert [part for part in command if "_" in part and part.split("_")[0] in {"validate", "validateBundle", "javaView"}] == [
        "validate_full",
        "validateBundle_full",
        "javaView_full",
    ]


def test_verbose_prints_the_gradle_output(bundler: ModuleType, tmp_path: Path) -> None:
    code, output = _run(bundler, SPIKE_ROOT, tmp_path / "out", _gradle(0, "GRADLE-TRANSCRIPT-LINE"), "--module", "full", "--verbose")

    assert code == 0 and "GRADLE-TRANSCRIPT-LINE" in output


def test_script_exits_2_with_a_counts_line_when_the_root_has_no_module(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "--out", str(tmp_path / "o")], capture_output=True, text=True, timeout=60, check=False
    )

    assert result.returncode == 2
    assert result.stdout.splitlines()[-1] == "counts: modules=0 bundles=0 path_items=0"


# -- determinism: the bundle is built twice and the digests are compared --------------------


def _digest_lines(output: str) -> list[str]:
    return [line for line in output.splitlines() if line.startswith("bundle sha256 ")]


def test_two_builds_of_one_commit_agree_and_the_digest_is_printed(bundler: ModuleType, tmp_path: Path) -> None:
    code, output = _run(bundler, SPIKE_ROOT, tmp_path / "out", _gradle(), "--module", "full")

    assert code == 0, output
    (line,) = _digest_lines(output)
    digest = line.split()[-1]
    assert line.startswith("bundle sha256 full ") and len(digest) == 64
    assert digest == hashlib.sha256((tmp_path / "out" / "bundle" / "full" / "openapi.yaml").read_bytes()).hexdigest()  # noqa: TID251 -- file-integrity digest of a bundle
    assert "BUILDS_DIFFER" not in output
    assert not (tmp_path / "out" / "bundle-second").exists(), "the second build is a scratch copy and is removed"


def test_builds_that_differ_fail_with_both_digests(bundler: ModuleType, tmp_path: Path) -> None:
    real = bundler.write_bundle
    calls: list[int] = []

    def flaky(module: Path, out_dir: Path) -> Path:
        target = real(module, out_dir)
        calls.append(1)
        if len(calls) == 2:
            target.write_text(target.read_text(encoding="utf-8") + "# drift\n", encoding="utf-8")
        return target

    lines: list[str] = []
    code = bundler.run(
        ["--root", str(SPIKE_ROOT), "--out", str(tmp_path / "out"), "--module", "full"], runner=_gradle(), which=_tool, out=lines.append, writer=flaky
    )
    output = "\n".join(lines)

    assert code == 1, output
    differ = [line for line in lines if "BUILDS_DIFFER" in line]
    assert len(differ) == 1 and differ[0].startswith("CONTRACT-CHECK bundle: BUILDS_DIFFER: full: ")
    first, second = re.findall(r"\b[0-9a-f]{64}\b", differ[0])
    assert first != second
    assert lines[-1].startswith("counts: modules=1")


def test_the_second_build_is_independent_of_the_first(bundler: ModuleType, tmp_path: Path) -> None:
    targets: list[Path] = []
    real = bundler.write_bundle

    def spying(module: Path, out_dir: Path) -> Path:
        targets.append(out_dir)
        return real(module, out_dir)

    bundler.run(["--root", str(SPIKE_ROOT), "--out", str(tmp_path / "out"), "--module", "full"], runner=_gradle(), which=_tool, out=lambda _l: None, writer=spying)

    assert len(targets) == 2 and targets[0] != targets[1], "two builds, two different output directories"


def test_bundle_only_needs_no_jvm_and_never_runs_gradle(bundler: ModuleType, tmp_path: Path) -> None:
    def forbidden(_command: list[str]) -> tuple[int, str]:
        raise AssertionError("gradle must not run with --bundle-only")

    code, output = _run(bundler, SPIKE_ROOT, tmp_path / "out", forbidden, "--module", "full", "--bundle-only", which=lambda _n: None)

    assert code == 0, output
    assert output.splitlines()[-1] == "counts: modules=1 bundles=1 path_items=5"
    assert len(_digest_lines(output)) == 1
    assert (tmp_path / "out" / "bundle" / "full" / "openapi.yaml").is_file()


def test_bundle_only_still_refuses_an_output_inside_the_repository(bundler: ModuleType) -> None:
    code, output = _run(bundler, SPIKE_ROOT, TOOLS_DIR / "inside", _gradle(), "--bundle-only", which=lambda _n: None)

    assert code == 2 and "OUT_INSIDE_REPOSITORY" in output
