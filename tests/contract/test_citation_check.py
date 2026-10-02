"""Planted-violation tests for ``contracts/tools/citation_check.py`` (FR-010, FR-021, FR-025).

One committed fixture root, ``contracts/tools/fixtures/citation_check/``, holds a clean control
module (``clean``: every property cited, through references, array items, map values and
``allOf``/``oneOf``/``anyOf`` branches, with each citation form), the cited code under ``code/``
and one module per planted violation. Every rule is asserted by its stable code on its own module
while the control stays clean in the same run. Cited paths must be git-tracked, so the fixtures are
resolved against the repository root.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "contracts" / "tools"
FIXTURE_ROOT = TOOLS_DIR / "fixtures" / "citation_check"
SCRIPT = TOOLS_DIR / "citation_check.py"
REAL_CONTRACTS = REPO_ROOT / "contracts"

# module directory in the fixture root -> exactly the codes it must produce, sorted
PLANTED = {
    "v_missing_citation": ["COUNT_MISMATCH", "MISSING_CITATION"],
    "v_missing_via_ref": ["COUNT_MISMATCH", "MISSING_CITATION"],
    "v_comment_symbol": ["CITED_SYMBOL_UNRESOLVED"],
    "v_string_symbol": ["CITED_SYMBOL_UNRESOLVED"],
    "v_substring_symbol": ["CITED_SYMBOL_UNRESOLVED"],
    "v_local_symbol": ["CITED_SYMBOL_UNRESOLVED"],
    "v_free_text_derived": ["BAD_DERIVED_FORM"],
    "v_empty_rule": ["EMPTY_RULE"],
    "v_empty_inputs": ["EMPTY_INPUTS"],
    "v_missing_inputs": ["EMPTY_INPUTS"],
    "v_input_missing_symbol": ["UNRESOLVED_INPUT"],
    "v_input_missing_path": ["UNRESOLVED_INPUT"],
    "v_input_missing_field": ["UNRESOLVED_INPUT"],
    "v_input_bad_shape": ["BAD_DERIVED_FORM"],
    "v_cited_path_missing": ["CITED_PATH_MISSING"],
    "v_path_escapes": ["CITED_PATH_MISSING"],
    "v_both_citations": ["BOTH_CITATIONS", "COUNT_MISMATCH"],
}

EXIT2 = {
    "zero_properties": "ZERO_PROPERTIES",
    "zero_citations": "ZERO_CITATIONS",
    "resolve_failed": "RESOLVE_FAILED",
    "no_module": "NO_MODULE",
}


@pytest.fixture(scope="module")
def citation() -> Any:
    sys.path.insert(0, str(TOOLS_DIR))
    try:
        spec = importlib.util.spec_from_file_location("citation_check_under_test", SCRIPT)
        assert spec is not None and spec.loader is not None, f"cannot load {SCRIPT}"
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(TOOLS_DIR))
    return module


@pytest.fixture(scope="module")
def planted_report(citation: Any) -> Any:
    return citation.check(FIXTURE_ROOT, repo_root=REPO_ROOT)


def _by_module(findings: list[Any]) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for finding in findings:
        grouped[finding.subject.split(":")[0]].append(finding)
    return grouped


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True, check=False, cwd=REPO_ROOT)


@pytest.mark.parametrize(("module", "codes"), sorted(PLANTED.items()))
def test_each_planted_violation_gives_its_stable_code(planted_report: Any, module: str, codes: list[str]) -> None:
    grouped = _by_module(planted_report.findings)
    assert sorted(f.code for f in grouped.get(module, [])) == codes


def test_the_clean_control_and_the_reuse_plant_have_no_failure(planted_report: Any) -> None:
    grouped = _by_module(planted_report.findings)
    assert "clean" not in grouped, [f.code for f in grouped.get("clean", [])]
    assert "v_reuse" not in grouped
    assert planted_report.blocked == []


def test_every_finding_names_the_property_or_the_citation(planted_report: Any) -> None:
    for finding in planted_report.findings:
        assert finding.subject.split(":")[0] in {p.name for p in FIXTURE_ROOT.iterdir()} and finding.detail, finding
    names = {f.subject for f in planted_report.findings if f.code == "MISSING_CITATION"}
    assert names == {"v_missing_citation:Thing.outer.[].inner", "v_missing_via_ref:Bare.bare"}


def test_the_symbol_that_exists_only_in_a_comment_is_named_in_the_finding(planted_report: Any) -> None:
    detail = next(f.detail for f in planted_report.findings if f.subject.startswith("v_comment_symbol:"))
    assert "commented_only" in detail


def test_a_citation_used_by_more_than_five_properties_is_reported_not_failed(citation: Any) -> None:
    report = citation.check(FIXTURE_ROOT, repo_root=REPO_ROOT, modules=("v_reuse",))
    assert report.findings == [] and report.exit_code == 0
    reuse = [item for item in report.info if item.code == "CITATION_REUSE"]
    assert len(reuse) == 1
    assert reuse[0].subject.endswith("sample.py#real_function") and "used by 6 properties" in reuse[0].detail


def test_the_clean_module_is_traversed_to_every_depth_and_counted(citation: Any) -> None:
    report = citation.check(FIXTURE_ROOT, repo_root=REPO_ROOT, modules=("clean",))
    assert report.findings == [] and report.blocked == []
    # Thing's own properties, the allOf branch, Sub.size, Choice.pick, the items and map value properties; shared Problem is exempt
    assert report.counts["properties"] == 21
    assert report.counts["x_source"] + report.counts["x_derived"] == report.counts["properties"]
    assert report.counts["x_derived"] == 2
    assert report.counts["inputs_resolved"] == 5


def test_the_annotated_target_without_a_value_resolves_bare_and_dotted(citation: Any) -> None:
    report = citation.check(FIXTURE_ROOT, repo_root=REPO_ROOT, modules=("clean",))
    assert not [f for f in report.findings if "invariant" in f.subject or "dotted" in f.subject]


def test_the_shared_problem_schema_is_not_a_resource_schema(citation: Any) -> None:
    report = citation.check(FIXTURE_ROOT, repo_root=REPO_ROOT, modules=("clean",))
    assert not [f for f in report.findings if "Problem" in f.subject]
    assert citation.SHARED_ARE_RESOURCE_SCHEMAS is False


@pytest.mark.parametrize(("case", "code"), sorted(EXIT2.items()))
def test_a_check_that_cannot_do_its_job_exits_two_with_its_code(citation: Any, case: str, code: str) -> None:
    report = citation.check(FIXTURE_ROOT / "exit2" / case, repo_root=REPO_ROOT)
    assert [f.code for f in report.blocked][:1] == [code]
    assert report.exit_code == 2
    result = _run("--root", str(FIXTURE_ROOT / "exit2" / case))
    assert result.returncode == 2
    assert f"CONTRACT-CHECK citation_check: {code}" in result.stdout
    assert result.stdout.rstrip().splitlines()[-1].startswith("counts: properties=")


def test_a_repository_that_git_cannot_read_exits_two(citation: Any, tmp_path: Path) -> None:
    report = citation.check(FIXTURE_ROOT, repo_root=tmp_path)
    assert [f.code for f in report.blocked] == ["GIT_UNAVAILABLE"]


def test_an_untracked_cited_file_does_not_resolve_until_it_is_tracked(citation: Any, tmp_path: Path) -> None:
    git = shutil.which("git")
    assert git is not None
    repo = tmp_path / "repo"
    shutil.copytree(FIXTURE_ROOT, repo / "contracts")
    (repo / "code").mkdir()
    shutil.copy(FIXTURE_ROOT / "code" / "sample.py", repo / "code" / "sample.py")
    module = repo / "contracts" / "single"
    shutil.copytree(FIXTURE_ROOT / "clean", module)
    shutil.rmtree(repo / "contracts" / "code")
    for path in module.rglob("*.yaml"):
        text = path.read_text(encoding="utf-8").replace("contracts/tools/fixtures/citation_check/code/", "code/")
        path.write_text(text, encoding="utf-8")
    for step in (["init", "-q"], ["config", "user.email", "t@example.invalid"], ["config", "user.name", "t"]):
        subprocess.run([git, "-C", str(repo), *step], check=True, capture_output=True)
    untracked = citation.check(repo / "contracts", repo_root=repo, modules=("single",))
    assert any(f.code == "CITED_PATH_MISSING" and "not tracked" in f.detail and "sample.py" in f.detail for f in untracked.findings)
    subprocess.run([git, "-C", str(repo), "add", "code/sample.py"], check=True, capture_output=True)
    tracked = citation.check(repo / "contracts", repo_root=repo, modules=("single",))
    assert not [f for f in tracked.findings if f.code == "CITED_PATH_MISSING" and "sample.py" in f.detail]


def test_command_line_output_grammar_and_exit_status() -> None:
    result = _run("--root", str(FIXTURE_ROOT))
    assert result.returncode == 1
    lines = result.stdout.splitlines()
    assert lines[-1].startswith("counts: properties=") and " x_source=" in lines[-1] and " x_derived=" in lines[-1] and " inputs_resolved=" in lines[-1]
    assert any(line.startswith("CONTRACT-CHECK citation_check: MISSING_CITATION: v_missing_citation:") for line in lines)
    clean = _run("--root", str(FIXTURE_ROOT), "--module", "clean")
    assert clean.returncode == 0, clean.stdout
    assert clean.stdout.splitlines()[-1].startswith("counts: properties=21 ")


def test_the_real_mission_status_module_passes_with_a_floor() -> None:
    result = _run("--root", str(REAL_CONTRACTS), "--module", "mission-status")
    assert result.returncode == 0, result.stdout
    counts = dict(pair.split("=") for pair in result.stdout.splitlines()[-1].removeprefix("counts: ").split())
    assert int(counts["properties"]) >= 120
    assert int(counts["x_source"]) + int(counts["x_derived"]) == int(counts["properties"])
