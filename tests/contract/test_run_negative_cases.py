"""Tests for ``contracts/tools/run_negative_cases.py``, the driver of the permanent planted proofs (FR-021, FR-014 to FR-016, FR-024).

The driver runs each case of ``contracts/tools/negative_cases.json``: a plant that must fail with its stable code and a clean
control on the same root that must pass. These tests drive it with a tiny fake tool so each failure mode is asserted on its own
(a plant that passes, a wrong reason, a missing or failing control, a truncated run, an empty manifest), then run the committed
manifest for real wherever no JVM, vacuum or oasdiff binary is needed. The tool-bound cases are the ``negative-tests`` CI job's.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tests.contract._loader import load_tool

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

TOOLS_DIR = Path(__file__).resolve().parents[2] / "contracts" / "tools"
SCRIPT = TOOLS_DIR / "run_negative_cases.py"
MANIFEST = TOOLS_DIR / "negative_cases.json"
SKIPPED_TAGS = ("jvm", "vacuum", "oasdiff")

FAKE_TOOL = """\
import sys
from pathlib import Path

mode, *rest = sys.argv[1:] or ["ok"]
if mode == "fail":
    print("CONTRACT-CHECK fake: WANTED_CODE: it failed")
    sys.exit(1)
if mode == "other":
    print("CONTRACT-CHECK fake: OTHER_CODE: it failed differently")
    sys.exit(1)
if mode == "echo-wanted":
    print("CONTRACT-CHECK fake: WANTED_CODE: a control that shows the plant")
    sys.exit(0)
if mode == "ls":
    print("CONTRACT-CHECK fake: ENTRIES_" + "_".join(sorted(path.name.upper() for path in Path(rest[0]).iterdir())))
    sys.exit(1 if rest[1:] == ["plant"] else 0)
print("fine")
"""


@pytest.fixture(scope="module")
def driver() -> Iterator[ModuleType]:
    with pytest.MonkeyPatch.context() as mp:
        yield load_tool(mp, SCRIPT, "run_negative_cases_under_test", syspath=TOOLS_DIR)


def _case(case_id: str = "one", **overrides: Any) -> dict[str, Any]:
    case: dict[str, Any] = {
        "id": case_id,
        "tool": "fake.py",
        "plant": {"args": ["fail"], "code": "WANTED_CODE"},
        "control": {"args": ["ok"]},
    }
    case.update(overrides)
    return case


def _run(driver: ModuleType, tmp_path: Path, cases: list[dict[str, Any]], *extra: str, **keywords: Any) -> tuple[int, list[str]]:
    tools = tmp_path / "tools"
    tools.mkdir(exist_ok=True)
    (tools / "fake.py").write_text(FAKE_TOOL, encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"cases": cases}), encoding="utf-8")
    lines: list[str] = []
    code = driver.run(["--manifest", str(manifest), "--tools-dir", str(tools), "--work", str(tmp_path / "work"), *extra], out=lines.append, **keywords)
    return code, lines


def _failure(lines: list[str]) -> str:
    (line,) = [line for line in lines if "CASE_FAILED" in line]
    return line


def test_a_plant_that_fails_with_its_code_and_a_control_that_passes_is_a_pass(driver: ModuleType, tmp_path: Path) -> None:
    code, lines = _run(driver, tmp_path, [_case("a"), _case("b")])

    assert code == 0, lines
    assert lines[-1] == "counts: cases=2 ran=2 skipped=0 passed=2 failed=0"
    assert [line for line in lines if line.startswith("PASS ")] == ["PASS a", "PASS b"]


def test_an_empty_manifest_cannot_do_its_job_and_prints_a_counts_line(driver: ModuleType, tmp_path: Path) -> None:
    code, lines = _run(driver, tmp_path, [])

    assert code == 2
    assert "ZERO_CASES" in lines[0] and lines[-1] == "counts: cases=0 ran=0 skipped=0 passed=0 failed=0"


def test_a_plant_that_unexpectedly_passes_fails_the_case(driver: ModuleType, tmp_path: Path) -> None:
    code, lines = _run(driver, tmp_path, [_case(plant={"args": ["ok"], "code": "WANTED_CODE"})])

    assert code == 1
    assert "PLANT_PASSED" in _failure(lines)


def test_a_plant_that_fails_for_another_reason_fails_the_case(driver: ModuleType, tmp_path: Path) -> None:
    code, lines = _run(driver, tmp_path, [_case(plant={"args": ["other"], "code": "WANTED_CODE"})])

    assert code == 1
    assert "WRONG_REASON" in _failure(lines) and "OTHER_CODE" in _failure(lines)


def test_a_wrong_exit_status_fails_the_case(driver: ModuleType, tmp_path: Path) -> None:
    code, lines = _run(driver, tmp_path, [_case(plant={"args": ["fail"], "code": "WANTED_CODE", "exit": 2})])

    assert code == 1
    assert "WRONG_EXIT" in _failure(lines)


def test_a_case_without_a_clean_control_fails(driver: ModuleType, tmp_path: Path) -> None:
    case = _case()
    del case["control"]

    code, lines = _run(driver, tmp_path, [case])

    assert code == 1
    assert "CONTROL_MISSING" in _failure(lines)


def test_a_clean_control_that_fails_fails_the_case(driver: ModuleType, tmp_path: Path) -> None:
    code, lines = _run(driver, tmp_path, [_case(control={"args": ["other"]})])

    assert code == 1
    assert "CONTROL_FAILED" in _failure(lines)


def test_a_control_that_prints_the_plant_code_fails_the_case(driver: ModuleType, tmp_path: Path) -> None:
    code, lines = _run(driver, tmp_path, [_case(control={"args": ["echo-wanted"]})])

    assert code == 1
    assert "CONTROL_SHOWS_PLANT_CODE" in _failure(lines)


def test_a_truncated_run_is_a_failure_because_the_case_count_must_equal_the_manifest(driver: ModuleType, tmp_path: Path) -> None:
    def truncated(cases: Iterable[dict[str, Any]], work: Path, tools: Path, execute: Callable[..., tuple[int, str]]) -> list[Any]:
        return list(driver.run_each(cases, work, tools, execute))[:-1]

    code, lines = _run(driver, tmp_path, [_case("a"), _case("b"), _case("c")], iterate=truncated)

    assert code == 1
    assert any("CASE_COUNT_MISMATCH" in line and "ran 2" in line for line in lines)
    assert lines[-1] == "counts: cases=3 ran=2 skipped=0 passed=2 failed=0"


def test_a_missing_script_cannot_do_its_job(driver: ModuleType, tmp_path: Path) -> None:
    code, lines = _run(driver, tmp_path, [_case(tool="absent.py")])

    assert code == 2
    assert "TOOL_MISSING" in lines[0]


def test_malformed_and_duplicate_cases_are_refused_before_anything_runs(driver: ModuleType, tmp_path: Path) -> None:
    duplicate_code, duplicate = _run(driver, tmp_path, [_case("a"), _case("a")])
    no_code_code, no_code = _run(driver, tmp_path, [_case(plant={"args": ["fail"]})])

    assert (duplicate_code, no_code_code) == (2, 2)
    assert "MANIFEST_INVALID" in duplicate[0] and "MANIFEST_INVALID" in no_code[0]


@pytest.mark.parametrize(
    "trivial", ["", " ", ":", "ab", "A", "ABC", "--", ": 12: ", "....", "x y", "error", "Traceback", ": error: ", "failed", "invalid-input", "not-a-rule"]
)
def test_a_trivial_expected_code_is_refused_because_it_matches_any_output(driver: ModuleType, tmp_path: Path, trivial: str) -> None:
    code, lines = _run(driver, tmp_path, [_case(plant={"args": ["fail"], "code": trivial})])

    assert code == 2
    assert "MANIFEST_INVALID" in lines[0] and "expected code" in lines[0]


@pytest.mark.parametrize("meaningful", ["WANTED_CODE", "ABCD", "forbidden-property-name", ": property-described: "])
def test_a_stable_code_and_a_lint_rule_id_are_accepted(driver: ModuleType, tmp_path: Path, meaningful: str) -> None:
    assert driver.code_problem(meaningful) is None


def test_an_unreadable_manifest_cannot_do_its_job(driver: ModuleType, tmp_path: Path) -> None:
    lines: list[str] = []

    code = driver.run(["--manifest", str(tmp_path / "absent.json")], out=lines.append)

    assert code == 2 and "MANIFEST_UNREADABLE" in lines[0]


def test_an_excluded_tag_is_skipped_and_counted_and_a_missing_binary_is_not_silent(driver: ModuleType, tmp_path: Path) -> None:
    tagged = [_case("a"), _case("b", tags=["vacuum"])]

    skipped_code, skipped = _run(driver, tmp_path, tagged, "--exclude-tag", "vacuum")
    missing_code, missing = _run(driver, tmp_path, tagged, which=lambda _name: None)

    assert skipped_code == 0 and skipped[-1] == "counts: cases=2 ran=1 skipped=1 passed=1 failed=0"
    assert missing_code == 2 and "TOOL_MISSING" in missing[0] and "vacuum" in missing[0]


def test_a_run_may_keep_only_some_entries_of_a_shared_root(driver: ModuleType, tmp_path: Path) -> None:
    root = tmp_path / "shared"
    for name in ("clean", "planted", "other"):
        (root / name).mkdir(parents=True)
    case = _case(
        root=str(root),
        tool="fake.py",
        plant={"args": ["ls", "{root}", "plant"], "keep": ["clean", "planted"], "code": "ENTRIES_CLEAN_PLANTED"},
        control={"args": ["ls", "{root}"], "keep": ["clean"]},
    )

    code, lines = _run(driver, tmp_path, [case])

    assert code == 0, lines


# -- the committed manifest ----------------------------------------------------------------------------------------------------------


def _manifest() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = json.loads(MANIFEST.read_text(encoding="utf-8"))["cases"]
    assert cases, "the committed manifest lists no case"
    return cases


def test_the_manifest_has_one_case_per_script_and_tool_each_with_a_control_and_an_expected_code() -> None:
    cases = _manifest()
    tools = {case["tool"] for case in cases}

    expected = {
        "layout_check.py",
        "citation_check.py",
        "provisional_check.py",
        "example_check.py",
        "event_mapping_check.py",
        "enum_pin_check.py",
        "leak_scan.py",
        "structure_check.py",
        "codeowners_check.py",
        "no_pytest_scan.py",
        "verify_pins.py",
        "bundle.py",
        "client_smoke.py",
        "tamper_check.py",
        "lint_check.py",
        "breaking_check.py",
        "resolver_parity.py",
        "release_check.py",
    }
    assert expected <= tools
    assert len({case["id"] for case in cases}) == len(cases)
    for case in cases:
        assert case["plant"]["code"] and case["control"]["args"], case["id"]


def test_the_dangling_reference_client_smoke_case_explains_why_it_expects_resolve_failed() -> None:
    (case,) = (case for case in _manifest() if case["id"] == "client-smoke-unresolvable-module")

    assert case["plant"]["code"] == "RESOLVE_FAILED"
    assert "GENERATION_FAILED" in case["rationale"] and "resolver" in case["rationale"]


def test_the_manifest_pins_the_stable_code_of_each_contract_plant_with_a_clean_control() -> None:
    by_id = {case["id"]: case for case in _manifest()}
    rows = {
        "bundle-dangling-reference": "RESOLVE_FAILED",
        "bundle-module-without-root-document": "MODULE_WITHOUT_ROOT",
        "bundle-invalid-openapi-31": "VALIDATION_FAILED",
        "bundle-builds-differ": "BUILDS_DIFFER",
        "gradle-verification-metadata-tampered": "PLANT_DETECTED",
        "breaking-removed-property": "BREAKING_WITHOUT_MAJOR",
        "breaking-added-response-property": "BREAKING_WITHOUT_MAJOR",
        "release-snapshot-refused": "SNAPSHOT_RELEASE_REFUSED",
        "breaking-bundle-changed-version-same": "BUNDLE_CHANGED_VERSION_SAME",
    }
    for case_id, code in rows.items():
        assert by_id[case_id]["plant"]["code"] == code, case_id
        assert by_id[case_id]["control"], case_id


def test_leak_class_and_lint_leak_plants_are_assembled_at_run_time_and_never_committed() -> None:
    by_id = {case["id"]: case for case in _manifest()}

    for kind in ("host-path-strict", "host-path-human", "email", "forbidden-property"):
        assert by_id[f"leak-scan-{kind}"]["build"] == f"leak:{kind}"
    assert by_id["lint-forbidden-property-name"]["build"] == "lint-forbidden-property"
    assert by_id["lint-forbidden-property-name"]["plant"]["code"] == "forbidden-property-name"
    assert by_id["no-pytest-reference"]["build"] == "no-pytest"


def test_every_vacuum_rule_and_every_breaking_plant_is_in_the_manifest_tagged_for_its_binary() -> None:
    cases = _manifest()
    lint = [case for case in cases if case["tool"] == "lint_check.py"]
    breaking = [case for case in cases if case["tool"] == "breaking_check.py"]

    assert len(lint) == 11 and all(case["tags"] == ["vacuum"] for case in lint), "nine rules, plus the two enum plants of the narrowed exemption"
    assert len(breaking) == 13 and all(case["tags"] == ["oasdiff"] for case in breaking), "seven original plants plus the six response additions"


def test_the_committed_manifest_runs_green_for_every_case_that_needs_no_binary(driver: ModuleType, tmp_path: Path) -> None:
    cases = _manifest()
    tagged = sum(1 for case in cases if set(case.get("tags", [])) & set(SKIPPED_TAGS))
    arguments = ["--work", str(tmp_path / "work")]
    for tag in SKIPPED_TAGS:
        arguments += ["--exclude-tag", tag]
    lines: list[str] = []

    code = driver.run(arguments, out=lines.append)

    assert code == 0, "\n".join(line for line in lines if not line.startswith("PASS"))
    assert lines[-1] == f"counts: cases={len(cases)} ran={len(cases) - tagged} skipped={tagged} passed={len(cases) - tagged} failed=0"
    assert len(cases) - tagged >= 50, "the python-only cases are most of the manifest"
