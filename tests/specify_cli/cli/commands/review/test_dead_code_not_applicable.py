"""CLI acceptance for the not-applicable dead-code gate (#5283).

Drives the real ``spec-kitty review`` typer app (in-process) against a real git
repository. A change set that contains nothing the Python-only dead-code scan
supports must record the gate as ``skip`` with exactly one
``dead_code_not_applicable`` finding, verdict ``pass_with_notes`` and exit 0 --
never the false ``DEAD_CODE_UNDETERMINABLE`` hard failure and never a false
"0 unreferenced" clean zero.

Every test docstring is labelled ``RED (pins the fix)`` or
``GREEN control (pins unchanged behaviour)``.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from specify_cli.cli.commands.review._dead_code import _Discovery, _discover_changed_symbols
from tests.specify_cli.cli.commands._review_fixtures import (
    MISSION_SLUG,
    build_cli_app,
    make_mock_resolved,
    seed_wp_event,
    write_meta,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.git_repo,
    pytest.mark.non_sandbox,
]

_NOT_APPLICABLE_CODE = "MISSION_REVIEW_DEAD_CODE_NOT_APPLICABLE"
_UNDETERMINABLE_CODE = "MISSION_REVIEW_DEAD_CODE_UNDETERMINABLE"
_TEST_EXTRA_CODE = "MISSION_REVIEW_TEST_EXTRA_MISSING"
_ZERO_UNREFERENCED = "0 unreferenced public symbols"
_MODES = ["lightweight", "post-merge"]

_ZIG_GO_FILES = {
    "src/main.zig": "pub fn main() void {}\n",
    "src/util.zig": "pub fn util() void {}\n",
    "cmd/app/main.go": "package main\n\nfunc main() {}\n",
}


def _git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _build_repo(tmp_path: Path, files: dict[str, str]) -> tuple[Path, Path]:
    """Real git repo: baseline commit, then one commit adding ``files``."""
    if shutil.which("git") is None:
        pytest.skip("Git is required for the review acceptance contract")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.name", "Not Applicable Test")
    _git(repo_root, "config", "user.email", "not-applicable@example.invalid")
    (repo_root / "README.md").write_text("# baseline\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-qm", "baseline")
    baseline = _git(repo_root, "rev-parse", "HEAD")
    if files:
        for relative, content in files.items():
            target = repo_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        _git(repo_root, "add", *files)
        _git(repo_root, "commit", "-qm", "mission change")
    # Mission artefacts stay untracked so they never enter the baseline..HEAD diff.
    feature_dir = repo_root / "kitty-specs" / MISSION_SLUG
    write_meta(feature_dir, baseline_merge_commit=baseline)
    seed_wp_event(feature_dir, "WP01", "done", "01KQTEST000000000000000001")
    return repo_root, feature_dir


def _run_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    files: dict[str, str],
    mode: str,
    *,
    pytest_missing: bool = False,
) -> tuple[int, str, str, Path]:
    """Run the review CLI, returning (rc, whitespace-normalised stdout, report, report path)."""
    repo_root, feature_dir = _build_repo(tmp_path, files)
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr("specify_cli.cli.commands.review.find_repo_root", lambda: repo_root)
    resolved = make_mock_resolved(feature_dir)
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.resolve_mission_handle",
        lambda handle, repo_root: resolved,
    )
    if pytest_missing:
        from specify_cli.cli.commands.review import TestExtraMissing

        def _raise_missing(_: Path) -> None:
            raise TestExtraMissing(_TEST_EXTRA_CODE)

        monkeypatch.setattr("specify_cli.cli.commands.review.assert_pytest_available", _raise_missing)

    result = CliRunner().invoke(build_cli_app(), ["--mission", MISSION_SLUG, "--mode", mode])
    report_path = feature_dir / "mission-review-report.md"
    report = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    return result.exit_code, " ".join(result.output.split()), report, report_path


def _frontmatter(report: str) -> dict[str, object]:
    loaded = yaml.safe_load(report.split("---")[1])
    assert isinstance(loaded, dict)
    return loaded


def _gate_result(report: str, gate_id: str) -> str:
    gates = _frontmatter(report)["gates_recorded"]
    assert isinstance(gates, list)
    return str(next(gate["result"] for gate in gates if gate["id"] == gate_id))


def _not_applicable_lines(report: str) -> list[str]:
    return [line for line in report.splitlines() if "**dead_code_not_applicable**" in line]


def _unsupported_extensions(line: str) -> str:
    match = re.search(r"unsupported_extensions=`([^`]*)`", line)
    assert match is not None, line
    return match.group(1)


@pytest.mark.parametrize("mode", _MODES)
def test_zig_go_only_change_is_not_applicable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    """RED (pins the fix): Zig/Go-only changes skip the gate, one note, rc 0, no false zero."""
    rc, stdout, report, _ = _run_review(tmp_path, monkeypatch, _ZIG_GO_FILES, mode)

    assert rc == 0, stdout
    assert "not applicable" in stdout
    assert _NOT_APPLICABLE_CODE in stdout
    assert _UNDETERMINABLE_CODE not in stdout
    assert _ZERO_UNREFERENCED not in stdout
    lines = _not_applicable_lines(report)
    assert len(lines) == 1, report
    assert _unsupported_extensions(lines[0]) == ".go, .zig"
    assert ".py" not in _unsupported_extensions(lines[0]).split(", ")
    assert _frontmatter(report)["findings"] == 1
    assert _frontmatter(report)["verdict"] == "pass_with_notes"
    assert _gate_result(report, "gate_2") == "skip"
    assert "0 unreferenced" not in report


@pytest.mark.parametrize("mode", _MODES)
def test_report_body_renders_not_applicable_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    """RED (pins the fix): the written report body carries the rendered diagnostic line."""
    rc, stdout, report, _ = _run_review(tmp_path, monkeypatch, _ZIG_GO_FILES, mode)

    assert rc == 0, stdout
    assert _NOT_APPLICABLE_CODE in report.split("## Findings", 1)[1]


@pytest.mark.parametrize("mode", _MODES)
def test_tests_only_and_docs_only_change_is_not_applicable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    """RED (pins the fix): test-only Python + docs are not applicable; `.py` is never unsupported."""
    files = {"tests/test_x.py": "def test_x() -> None:\n    assert True\n", "docs/guide.md": "guide\n"}
    rc, stdout, report, _ = _run_review(tmp_path, monkeypatch, files, mode)

    assert rc == 0, stdout
    assert _NOT_APPLICABLE_CODE in stdout
    assert "test-only Python paths" in stdout
    lines = _not_applicable_lines(report)
    assert len(lines) == 1, report
    assert _unsupported_extensions(lines[0]) == ".md"
    assert "excluded_test_paths=`1`" in lines[0]
    assert _gate_result(report, "gate_2") == "skip"
    assert _ZERO_UNREFERENCED not in stdout


@pytest.mark.parametrize("mode", _MODES)
def test_mixed_change_still_scans_python_subset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    """RED (pins the fix): mixed sets keep reporting Python symbols and note the remainder."""
    files = {
        "src/main.zig": "pub fn main() void {}\n",
        "scripts/gen.py": "def DeliberatelyUnreferenced() -> None:\n    return None\n",
    }
    rc, stdout, report, _ = _run_review(tmp_path, monkeypatch, files, mode)

    assert rc == 0, stdout
    assert "DeliberatelyUnreferenced" in stdout
    assert "not applicable" in stdout
    assert ".zig" in stdout
    assert _frontmatter(report)["verdict"] == "pass_with_notes"
    assert _gate_result(report, "gate_2") == "fail"


@pytest.mark.parametrize("mode", _MODES)
def test_python_only_clean_change_has_no_note(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    """GREEN control (pins unchanged behaviour): Python-only change reports a real zero, no note."""
    rc, stdout, report, _ = _run_review(tmp_path, monkeypatch, {"src/fixture.py": "VALUE = 1\n"}, mode)

    assert rc == 0, stdout
    assert _ZERO_UNREFERENCED in stdout
    assert "not applicable" not in stdout
    assert _not_applicable_lines(report) == []
    assert _gate_result(report, "gate_2") == "pass"


@pytest.mark.parametrize("mode", _MODES)
def test_python_only_dead_symbol_is_reported_without_note(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    """GREEN control (pins unchanged behaviour): a Python-only unreferenced def is still reported."""
    files = {"src/fixture.py": "def DeliberatelyUnreferenced() -> None:\n    return None\n"}
    rc, stdout, report, _ = _run_review(tmp_path, monkeypatch, files, mode)

    assert rc == 0, stdout
    assert "1 unreferenced public symbol(s)" in stdout
    assert "not applicable" not in stdout
    assert _gate_result(report, "gate_2") == "fail"


@pytest.mark.parametrize("mode", _MODES)
def test_empty_change_set_stays_undeterminable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    """GREEN control (pins unchanged behaviour): an empty change set is still undeterminable + fail."""
    rc, stdout, report, _ = _run_review(tmp_path, monkeypatch, {}, mode)

    assert rc == 1, stdout
    assert _UNDETERMINABLE_CODE in stdout
    assert "not applicable" not in stdout
    assert _frontmatter(report)["verdict"] == "fail"
    assert _gate_result(report, "gate_2") == "fail"


def test_missing_pytest_warns_and_review_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """RED (pins the fix): a missing pytest is a warning; the review still runs and writes its report."""
    rc, stdout, report, report_path = _run_review(
        tmp_path,
        monkeypatch,
        {"src/fixture.py": "VALUE = 1\n"},
        "lightweight",
        pytest_missing=True,
    )

    assert rc == 0, stdout
    assert _TEST_EXTRA_CODE in stdout
    assert '"severity": "warning"' in stdout
    assert report_path.exists()
    assert _gate_result(report, "gate_2") == "pass"


def test_pytest_present_emits_no_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GREEN control (pins unchanged behaviour): with pytest available there is no warning."""
    rc, stdout, _, _ = _run_review(tmp_path, monkeypatch, {"src/fixture.py": "VALUE = 1\n"}, "lightweight")

    assert rc == 0, stdout
    assert _TEST_EXTRA_CODE not in stdout


# ---------------------------------------------------------------------------
# Pre-PR fold F2: discovery path handling (quoted non-ASCII paths, suffix case,
# path-segment test-only rule)
# ---------------------------------------------------------------------------


def _discover(tmp_path: Path, files: dict[str, str]) -> _Discovery:
    repo_root, _ = _build_repo(tmp_path, files)
    baseline = _git(repo_root, "rev-list", "--max-parents=0", "HEAD")
    return _discover_changed_symbols(repo_root, baseline)


def test_non_ascii_python_path_is_discovered_as_python(tmp_path: Path) -> None:
    """RED (pins F2a): Git must not octal-quote ``src/café.py`` into a bogus ``.py"`` extension."""
    discovery = _discover(tmp_path, {"src/café.py": "def cafe_fn() -> None:\n    return None\n"})

    assert discovery.outcome == "scan"
    assert discovery.symbols == (("cafe_fn", "src/café.py"),)
    assert discovery.unsupported_extensions == ()


@pytest.mark.parametrize("mode", _MODES)
def test_non_ascii_python_path_is_scanned_by_the_review_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    """RED (pins F2a, CLI): a non-ASCII ``.py`` path is scanned, never reported as not applicable."""
    files = {"src/café.py": "def DeliberatelyUnreferenced() -> None:\n    return None\n"}
    rc, stdout, report, _ = _run_review(tmp_path, monkeypatch, files, mode)

    assert rc == 0, stdout
    assert "DeliberatelyUnreferenced" in stdout
    assert "not applicable" not in stdout
    assert _not_applicable_lines(report) == []


@pytest.mark.parametrize("path", ["pkg/MODULE.PY", "pkg/Tool.Py"])
def test_python_suffix_check_is_case_insensitive(tmp_path: Path, path: str) -> None:
    """RED (pins F2b): an upper/mixed-case ``.PY`` suffix is Python, consistently with the summary's lower-casing."""
    discovery = _discover(tmp_path, {path: "def cased_fn() -> None:\n    return None\n"})

    assert discovery.outcome == "scan"
    assert discovery.symbols == (("cased_fn", path),)


@pytest.mark.parametrize("path", ["latest.py", "pkg/contest.py", "pkg/attestation.py", "pkg/testing_utils.py"])
def test_substring_test_in_a_name_is_still_scanned_python(tmp_path: Path, path: str) -> None:
    """RED (pins F2c): ``test`` as a substring of a name (latest, contest, attestation) is not a test path."""
    discovery = _discover(tmp_path, {path: "def scanned_fn() -> None:\n    return None\n"})

    assert discovery.outcome == "scan"
    assert discovery.symbols == (("scanned_fn", path),)


@pytest.mark.parametrize(
    "path",
    ["tests/helper.py", "pkg/test/helper.py", "pkg/test_foo.py", "pkg/foo_test.py", "pkg/conftest.py", "pkg/TEST_case.PY"],
)
def test_real_test_paths_stay_test_only(tmp_path: Path, path: str) -> None:
    """GREEN control (pins unchanged behaviour): directory segments and test file names are still test-only."""
    discovery = _discover(tmp_path, {path: "def helper_fn() -> None:\n    return None\n"})

    assert discovery.outcome == "not_applicable"
    assert discovery.excluded_test_paths == 1
    assert discovery.unsupported_extensions == ()


def test_src_prefix_keeps_test_named_module_supported(tmp_path: Path) -> None:
    """GREEN control (pins unchanged behaviour): anything under ``src/`` is scanned even when named like a test."""
    discovery = _discover(tmp_path, {"src/pkg/test_support.py": "def support_fn() -> None:\n    return None\n"})

    assert discovery.outcome == "scan"
    assert discovery.symbols == (("support_fn", "src/pkg/test_support.py"),)
