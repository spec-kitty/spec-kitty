"""Tests for the lint ruleset ``contracts/lint/ruleset.yaml`` and its runner ``contracts/tools/lint_check.py`` (FR-015).

Two layers. The ruleset is parsed in Python and every rule the requirement names must be present, described and
backed by a planted fixture; the runner's refusals (empty ruleset, zero rules, zero files, missing binary) run
against a faked process boundary. Where the real ``vacuum`` is on ``PATH`` (the lint job installs it from the
pinned release; a developer may too) every planted fixture is run through it and must fail with exactly its own
rule, and the clean control must pass under the same ruleset.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

from tests.contract._loader import load_tool

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

REPO = Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO / "contracts" / "tools"
RULESET = REPO / "contracts" / "lint" / "ruleset.yaml"
FIXTURES = TOOLS_DIR / "fixtures" / "vacuum"
SCRIPT = TOOLS_DIR / "lint_check.py"
REAL_VACUUM = shutil.which("vacuum")

# The conventions FR-015 names, as the rule ids that enforce them.
REQUIRED_RULES = (
    "operation-operationId",
    "operation-operationId-unique",
    "operation-tags",
    "non-2xx-is-problem",
    "property-described",
    "resource-property-cited",
    "forbidden-property-name",
    "enum-case",
    "response-schema-closed",
)
# Rules whose plant is committed as <rule>.yaml; the forbidden-name plant is assembled at run time (it is leak-shaped).
COMMITTED_PLANTS = tuple(rule for rule in REQUIRED_RULES if rule != "forbidden-property-name")


@pytest.fixture(scope="module")
def linter() -> Iterator[ModuleType]:
    with pytest.MonkeyPatch.context() as mp:
        yield load_tool(mp, SCRIPT, "lint_check_under_test", syspath=TOOLS_DIR)


def _ruleset() -> dict[str, Any]:
    loaded = yaml.safe_load(RULESET.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


# -- the ruleset, parsed in Python ---------------------------------------------------------------------


def test_the_ruleset_is_spectral_format_and_names_every_required_rule() -> None:
    ruleset = _ruleset()

    assert ruleset["extends"] == [["vacuum:oas", "off"]], "no built-in rule runs unless this ruleset names it"
    assert set(REQUIRED_RULES) <= set(ruleset["rules"])


@pytest.mark.parametrize("rule", [rule for rule in REQUIRED_RULES if not rule.startswith("operation-")])
def test_every_custom_rule_has_a_description_an_error_severity_a_target_and_a_function(rule: str) -> None:
    body = _ruleset()["rules"][rule]

    assert body["description"].strip() and body["severity"] == "error"
    assert body["given"], "the rule has a JSONPath target"
    assert body["then"]["function"] in {"schema", "pattern", "truthy"}
    options = body["then"].get("functionOptions")
    assert options, "the function carries its configuration: a rule with no assertion would pass everything"


@pytest.mark.parametrize("rule", ["operation-operationId", "operation-operationId-unique", "operation-tags"])
def test_built_in_rules_are_switched_on_not_off(rule: str) -> None:
    assert _ruleset()["rules"][rule] is True


@pytest.mark.parametrize("rule", COMMITTED_PLANTS)
def test_every_rule_has_a_valid_planted_fixture_and_the_clean_control_exists(rule: str) -> None:
    plant = FIXTURES / f"{rule}.yaml"
    document = yaml.safe_load(plant.read_text(encoding="utf-8"))

    assert document["openapi"] == "3.1.0" and document["paths"]
    assert yaml.safe_load((FIXTURES / "clean.yaml").read_text(encoding="utf-8"))["paths"]
    assert document != yaml.safe_load((FIXTURES / "clean.yaml").read_text(encoding="utf-8")), "a plant differs from the control"


def test_the_ruleset_directory_holds_no_module_root_document() -> None:
    assert not (RULESET.parent / "openapi.yaml").exists(), "contracts/lint is not a module"


def test_fixtures_are_all_tracked() -> None:
    on_disk = sorted(path.relative_to(REPO).as_posix() for path in FIXTURES.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    tracked = subprocess.run(["git", "ls-files", str(FIXTURES)], capture_output=True, text=True, check=True, cwd=REPO).stdout.split()  # noqa: S603, S607 -- git, argument list
    assert on_disk and on_disk == sorted(tracked)


# -- the runner's refusals, with the process boundary faked --------------------------------------------


def _fake(rules: int = 9, report: list[dict[str, Any]] | None = None) -> Callable[[Sequence[str]], tuple[int, str, str]]:
    def run(command: Sequence[str]) -> tuple[int, str, str]:
        if "spectral-report" in command:
            return 0, json.dumps(report or []), ""
        return 0, f" using ruleset 'x' (containing {rules} rules)\n", ""

    return run


def _run(linter: ModuleType, *args: str, runner: Any = None, which: Callable[[str], str | None] | None = None) -> tuple[int, str]:
    lines: list[str] = []
    code = linter.run(list(args), runner=runner or _fake(), which=which or (lambda name: f"/fixture/bin/{name}"), out=lines.append)
    return code, "\n".join(lines)


def test_clean_run_with_no_results_passes_and_counts_files_and_rules(linter: ModuleType) -> None:
    code, output = _run(linter, "--ruleset", str(RULESET), "--file", str(FIXTURES / "clean.yaml"))

    assert code == 0, output
    assert output.splitlines()[-1] == "counts: files=1 rules=9 violations=0"


def test_a_result_is_a_violation_with_rule_file_and_path(linter: ModuleType) -> None:
    report = [{"code": "enum-case", "path": ["paths", "/things", "get"], "message": "bad value", "severity": 0}]

    code, output = _run(linter, "--ruleset", str(RULESET), "--file", str(FIXTURES / "clean.yaml"), runner=_fake(report=report))

    assert code == 1
    assert "CONTRACT-CHECK lint_check: LINT_VIOLATION:" in output and "enum-case" in output and "/things" in output
    assert output.splitlines()[-1] == "counts: files=1 rules=9 violations=1"


def test_a_missing_ruleset_cannot_do_its_job(linter: ModuleType, tmp_path: Path) -> None:
    code, output = _run(linter, "--ruleset", str(tmp_path / "absent.yaml"), "--file", str(FIXTURES / "clean.yaml"))

    assert code == 2 and "RULESET_MISSING" in output
    assert output.splitlines()[-1].startswith("counts: ")


@pytest.mark.parametrize("text", ["", "# only a comment\n", "rules: {}\n", "rules:\n  a: false\n  b: 'off'\n", "extends: []\n"])
def test_an_empty_ruleset_cannot_do_its_job(linter: ModuleType, tmp_path: Path, text: str) -> None:
    ruleset = tmp_path / "ruleset.yaml"
    ruleset.write_text(text, encoding="utf-8")

    code, output = _run(linter, "--ruleset", str(ruleset), "--file", str(FIXTURES / "clean.yaml"))

    assert code == 2 and "RULESET_EMPTY" in output


def test_zero_rules_loaded_by_the_binary_cannot_do_its_job(linter: ModuleType) -> None:
    code, output = _run(linter, "--ruleset", str(RULESET), "--file", str(FIXTURES / "clean.yaml"), runner=_fake(rules=0))

    assert code == 2 and "ZERO_RULES_LOADED" in output


def test_a_rule_count_that_differs_from_the_ruleset_cannot_do_its_job(linter: ModuleType) -> None:
    code, output = _run(linter, "--ruleset", str(RULESET), "--file", str(FIXTURES / "clean.yaml"), runner=_fake(rules=3))

    assert code == 2 and "RULES_LOADED_MISMATCH" in output


def test_zero_files_cannot_do_its_job(linter: ModuleType, tmp_path: Path) -> None:
    code, output = _run(linter, "--ruleset", str(RULESET), "--bundles", str(tmp_path))

    assert code == 2 and "ZERO_FILES" in output


def test_a_listed_file_that_is_absent_cannot_be_skipped(linter: ModuleType, tmp_path: Path) -> None:
    code, output = _run(linter, "--ruleset", str(RULESET), "--file", str(tmp_path / "absent.yaml"))

    assert code == 2 and "ZERO_FILES" in output


def test_a_missing_binary_cannot_do_its_job(linter: ModuleType) -> None:
    code, output = _run(linter, "--ruleset", str(RULESET), "--file", str(FIXTURES / "clean.yaml"), which=lambda _name: None)

    assert code == 2 and "VACUUM_MISSING" in output


def test_bundles_are_found_under_the_bundle_directory(linter: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "bundle" / "alpha").mkdir(parents=True)
    (tmp_path / "bundle" / "alpha" / "openapi.yaml").write_text("openapi: 3.1.0\n", encoding="utf-8")
    (tmp_path / "bundle" / "beta").mkdir(parents=True)
    (tmp_path / "bundle" / "beta" / "openapi.yaml").write_text("openapi: 3.1.0\n", encoding="utf-8")

    code, output = _run(linter, "--ruleset", str(RULESET), "--bundles", str(tmp_path))

    assert code == 0, output
    assert output.splitlines()[-1] == "counts: files=2 rules=9 violations=0"


def test_a_binary_that_prints_no_json_cannot_do_its_job(linter: ModuleType) -> None:
    def broken(command: Sequence[str]) -> tuple[int, str, str]:
        if "spectral-report" in command:
            return 1, "boom", "could not parse"
        return 0, "containing 9 rules", ""

    code, output = _run(linter, "--ruleset", str(RULESET), "--file", str(FIXTURES / "clean.yaml"), runner=broken)

    assert code == 2 and "VACUUM_FAILED" in output


# -- the real binary ---------------------------------------------------------------------------------------

needs_vacuum = pytest.mark.skipif(
    REAL_VACUUM is None, reason="vacuum is not installed here; the lint workflow job runs the planted fixtures against the pinned binary"
)


def _run_real(linter: ModuleType, *files: Path) -> tuple[int, str]:
    lines: list[str] = []
    code = linter.run(["--ruleset", str(RULESET), *[arg for file in files for arg in ("--file", str(file))]], out=lines.append)
    return code, "\n".join(lines)


@needs_vacuum
def test_the_clean_control_passes_under_the_real_ruleset(linter: ModuleType) -> None:
    code, output = _run_real(linter, FIXTURES / "clean.yaml")

    assert code == 0, output
    assert output.splitlines()[-1] == "counts: files=1 rules=9 violations=0"


@needs_vacuum
@pytest.mark.parametrize("rule", COMMITTED_PLANTS)
def test_each_planted_violation_fails_with_exactly_its_own_rule(linter: ModuleType, rule: str) -> None:
    code, output = _run_real(linter, FIXTURES / f"{rule}.yaml")

    assert code == 1, output
    violated = {line.split(": ")[3] for line in output.splitlines() if "LINT_VIOLATION" in line}
    assert violated == {rule}, output


@needs_vacuum
def test_a_forbidden_property_name_fails_and_is_assembled_at_run_time(linter: ModuleType, tmp_path: Path) -> None:
    document = yaml.safe_load((FIXTURES / "clean.yaml").read_text(encoding="utf-8"))
    schema = document["paths"]["/things"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    name = "work" + "tree" + "Path"
    schema["properties"][name] = {"type": "string", "description": "A local path.", "x-source": {"path": "src/example/things.py", "symbol": "Thing.id"}}
    plant = tmp_path / "forbidden.yaml"
    plant.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    code, output = _run_real(linter, plant)

    assert code == 1 and "forbidden-property-name" in output, output


@needs_vacuum
def test_a_non_2xx_response_with_another_content_type_fails_through_the_real_pipeline(linter: ModuleType, tmp_path: Path) -> None:
    with pytest.MonkeyPatch.context() as mp:
        mp.syspath_prepend(str(TOOLS_DIR))
        import bundle

        written = bundle.write_bundle(FIXTURES / "other_content_type" / "things", tmp_path)

    code, output = _run_real(linter, written)

    assert code == 1 and "non-2xx-is-problem" in output, output


@needs_vacuum
def test_the_real_contract_bundle_passes_the_ruleset(linter: ModuleType, tmp_path: Path) -> None:
    with pytest.MonkeyPatch.context() as mp:
        mp.syspath_prepend(str(TOOLS_DIR))
        import bundle

        written = bundle.write_bundle(REPO / "contracts" / "mission-status", tmp_path)

    code, output = _run_real(linter, written)

    assert code == 0, output
