"""Tests for ``scripts/ci/acceptance_evidence.py`` (WP03, FR-010/FR-011, evidence schema v1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ci import acceptance_evidence as ev

pytestmark = [pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = REPO_ROOT / "kitty-specs" / "acceptance-scenario-contract-01M4T9GC" / "contracts" / "evidence.schema.json"
ENV_KEYS = ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _suite(tests: int, failures: int = 0, errors: int = 0, skipped: int = 0) -> str:
    return f'<testsuite tests="{tests}" failures="{failures}" errors="{errors}" skipped="{skipped}"/>'


def _make_pass(
    root: Path,
    name: str,
    *xmls: str,
    env: str | None = None,
) -> Path:
    base = root / name
    (base / "junit").mkdir(parents=True)
    (base / "allure-results").mkdir()
    (base / "cucumber.json").write_text("[]", encoding="utf-8")
    for index, xml in enumerate(xmls):
        (base / "junit" / f"TEST-{index}.xml").write_text(xml, encoding="utf-8")
    if env is not None:
        (base / "allure-results" / "environment.properties").write_text(env, encoding="utf-8")
    return base


def _check_against_schema(bundle: dict, schema: dict) -> None:
    """Minimal checker for the subset of JSON Schema the evidence contract uses."""
    for key in schema["required"]:
        assert key in bundle, key
    assert bundle["schema_version"] == schema["properties"]["schema_version"]["const"]
    for key in ("commit_sha", "cli_version", "run_url"):
        assert bundle[key] is None or isinstance(bundle[key], str)
    assert isinstance(bundle["os"], str)
    pass_schema = schema["properties"]["passes"]
    for key in pass_schema["required"]:
        assert key in bundle["passes"]
    item = pass_schema["additionalProperties"]
    for entry in bundle["passes"].values():
        for key in item["required"]:
            assert key in entry, key
        assert entry["outcome"] in item["properties"]["outcome"]["enum"]
        for count in ("tests", "failures", "errors", "skipped"):
            assert isinstance(entry[count], int) and entry[count] >= 0
        for key in item["properties"]["results"]["required"]:
            assert isinstance(entry["results"][key], str)


def test_passed_gating_and_empty_wip(tmp_path: Path) -> None:
    _make_pass(tmp_path, "gating", _suite(5, skipped=1), env="cli.version=1.2.3\ncommit.sha=abc\n")
    bundle = ev.build_bundle(tmp_path, "ubuntu-24.04")
    assert bundle["passes"]["gating"]["outcome"] == "passed"
    assert bundle["passes"]["gating"]["tests"] == 5
    assert bundle["passes"]["gating"]["skipped"] == 1
    assert bundle["passes"]["wip"]["outcome"] == "missing"
    assert bundle["passes"]["wip"]["tests"] == 0
    assert bundle["cli_version"] == "1.2.3"
    assert bundle["commit_sha"] == "abc"
    assert bundle["os"] == "ubuntu-24.04"
    _check_against_schema(bundle, json.loads(SCHEMA.read_text(encoding="utf-8")))


def test_failed_gating(tmp_path: Path) -> None:
    _make_pass(tmp_path, "gating", _suite(4, failures=1))
    assert ev.build_bundle(tmp_path, "x")["passes"]["gating"]["outcome"] == "failed"


def test_errors_alone_fail(tmp_path: Path) -> None:
    _make_pass(tmp_path, "gating", _suite(4, errors=2))
    gating = ev.build_bundle(tmp_path, "x")["passes"]["gating"]
    assert gating["outcome"] == "failed"
    assert gating["errors"] == 2


def test_missing_gating(tmp_path: Path) -> None:
    bundle = ev.build_bundle(tmp_path, "x")
    assert bundle["passes"]["gating"]["outcome"] == "missing"
    assert bundle["commit_sha"] is None
    assert bundle["cli_version"] is None


def test_multiple_junit_files_summed_and_testsuites_root(tmp_path: Path) -> None:
    wrapped = f"<testsuites>{_suite(2, failures=1)}{_suite(3, errors=1, skipped=2)}</testsuites>"
    _make_pass(tmp_path, "gating", _suite(10), wrapped)
    gating = ev.build_bundle(tmp_path, "x")["passes"]["gating"]
    assert (gating["tests"], gating["failures"], gating["errors"], gating["skipped"]) == (15, 1, 1, 2)


def test_unparseable_junit_counts_as_failed(tmp_path: Path) -> None:
    _make_pass(tmp_path, "gating", "<not-xml")
    assert ev.build_bundle(tmp_path, "x")["passes"]["gating"]["outcome"] == "failed"


def test_environment_falls_back_to_wip(tmp_path: Path) -> None:
    _make_pass(tmp_path, "gating", _suite(1))
    _make_pass(tmp_path, "wip", _suite(1), env="# comment\ncli.version = 9.9\ncommit.sha=def\nbogus\n")
    bundle = ev.build_bundle(tmp_path, "x")
    assert bundle["cli_version"] == "9.9"
    assert bundle["commit_sha"] == "def"


def test_run_url_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert ev.build_bundle(tmp_path, "x")["run_url"] is None
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    assert ev.build_bundle(tmp_path, "x")["run_url"] == "https://github.com/o/r/actions/runs/42"


def test_result_paths_relative_posix(tmp_path: Path) -> None:
    _make_pass(tmp_path, "gating", _suite(1))
    assert ev.build_bundle(tmp_path, "x")["passes"]["gating"]["results"] == {
        "allure": "gating/allure-results",
        "cucumber": "gating/cucumber.json",
        "junit": "gating/junit",
    }


def test_main_writes_evidence_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _make_pass(tmp_path, "gating", _suite(2))
    assert ev.main(["--root", str(tmp_path), "--os", "windows-latest"]) == 0
    written = json.loads((tmp_path / "evidence.json").read_text(encoding="utf-8"))
    assert written["os"] == "windows-latest"
    assert written["schema_version"] == 1
    assert "evidence.json" in capsys.readouterr().out


def test_main_creates_missing_root_and_exits_nonzero(tmp_path: Path) -> None:
    root = tmp_path / "absent"
    assert ev.main(["--root", str(root), "--os", "x"]) == 1
    written = json.loads((root / "evidence.json").read_text(encoding="utf-8"))
    assert written["passes"]["gating"]["outcome"] == "missing"


def test_gating_with_nothing_executed_fails(tmp_path: Path) -> None:
    _make_pass(tmp_path, "gating", _suite(0))
    assert ev.build_bundle(tmp_path, "x")["passes"]["gating"]["outcome"] == "failed"


def test_gating_with_everything_skipped_fails(tmp_path: Path) -> None:
    _make_pass(tmp_path, "gating", _suite(3, skipped=3))
    assert ev.build_bundle(tmp_path, "x")["passes"]["gating"]["outcome"] == "failed"


def test_wip_with_nothing_executed_still_passes(tmp_path: Path) -> None:
    _make_pass(tmp_path, "wip", _suite(0))
    assert ev.build_bundle(tmp_path, "x")["passes"]["wip"]["outcome"] == "passed"


def test_main_exits_nonzero_for_empty_gating_but_writes_evidence(tmp_path: Path) -> None:
    _make_pass(tmp_path, "gating", _suite(0))
    assert ev.main(["--root", str(tmp_path), "--os", "x"]) == 1
    assert (tmp_path / "evidence.json").is_file()


def test_main_exits_zero_when_only_wip_is_missing(tmp_path: Path) -> None:
    _make_pass(tmp_path, "gating", _suite(2))
    assert ev.main(["--root", str(tmp_path), "--os", "x"]) == 0


def test_nested_suites_not_double_counted(tmp_path: Path) -> None:
    nested = '<testsuite tests="3" failures="0" errors="0" skipped="0"><testsuite tests="3"/></testsuite>'
    _make_pass(tmp_path, "gating", nested)
    assert ev.build_bundle(tmp_path, "x")["passes"]["gating"]["tests"] == 3


def test_non_numeric_counter_counts_as_error(tmp_path: Path) -> None:
    _make_pass(tmp_path, "gating", '<testsuite tests="many"/>')
    assert ev.build_bundle(tmp_path, "x")["passes"]["gating"]["outcome"] == "failed"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("cli.version=1\\:2\\=3", "1:2=3"),
        ("k=a\\#b\\!c", "a#b!c"),
        ("k=back\\\\slash", "back\\slash"),
        ("k=caf\\u00e9", "café"),
        ("k=\\ leading", " leading"),
        ("k=tab\\there\\nnl", "tab\there\nnl"),
    ],
)
def test_properties_values_are_unescaped(tmp_path: Path, raw: str, expected: str) -> None:
    path = tmp_path / "environment.properties"
    path.write_text(raw + "\n", encoding="utf-8")
    key = raw.split("=", 1)[0]
    assert ev._read_properties(path)[key] == expected


def test_properties_keys_are_unescaped(tmp_path: Path) -> None:
    path = tmp_path / "environment.properties"
    path.write_text("a\\:b=1\n", encoding="utf-8")
    assert ev._read_properties(path) == {"a:b": "1"}
