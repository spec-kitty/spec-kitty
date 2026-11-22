"""Changed test files that only the nightly runs are named on the PR (#7801).

A test file under an ``out_of_matrix_test_dirs`` directory of
``.github/ci-module-registry.yml`` runs in no per-PR shard, so a PR that edits
it is green whatever the file does. The router now names those files with a
``::warning`` and a step-summary list. It never fails the run.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts.ci.gate_selection import (
    DEFAULT_REGISTRY_PATH,
    out_of_matrix_test_paths,
    render_out_of_matrix_report,
)

pytestmark = [pytest.mark.fast]

ROOT = Path(__file__).resolve().parents[2]
ROUTER = ROOT / ".github/workflows/ci-router.yml"


def _registry(tmp_path: Path) -> Path:
    path = tmp_path / "registry.yml"
    path.write_text(
        yaml.safe_dump(
            {
                "modules": [
                    {"module": "ci", "roots": ["scripts/ci/**"]},
                    {"module": "upgrade", "roots": ["src/specify_cli/upgrade/**"], "test_dirs": ["tests/upgrade", "tests/specify_cli/upgrade/claimed"]},
                ],
                "out_of_matrix_test_dirs": [
                    {"reason": "root helpers", "dirs": ["tests"]},
                    {"reason": "nightly only", "dirs": ["tests/specify_cli/upgrade", "tests/specify_cli/upgrade/migrations"]},
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_out_of_matrix_test_file_is_named(tmp_path: Path) -> None:
    hits = out_of_matrix_test_paths(["tests/specify_cli/upgrade/x.py"], registry_path=_registry(tmp_path))
    assert hits == (("tests/specify_cli/upgrade/x.py", "tests/specify_cli/upgrade"),)


def test_live_registry_names_an_upgrade_test_as_nightly_only() -> None:
    hits = out_of_matrix_test_paths(["tests/specify_cli/upgrade/x.py"], registry_path=DEFAULT_REGISTRY_PATH)
    assert [path for path, _ in hits] == ["tests/specify_cli/upgrade/x.py"]


@pytest.mark.parametrize(
    ("path", "owner"),
    [
        # The deepest recorded directory owns the file.
        ("tests/specify_cli/upgrade/migrations/test_m.py", "tests/specify_cli/upgrade/migrations"),
        # A file below an unnamed subdirectory belongs to the deepest record.
        ("tests/specify_cli/upgrade/fixtures/test_data.py", "tests/specify_cli/upgrade"),
        ("tests/specify_cli/upgrade/conftest.py", "tests/specify_cli/upgrade"),
        ("tests/test_root_helper.py", "tests"),
        ("tests/fixtures/data.json", "tests"),
    ],
)
def test_owner_is_the_deepest_recorded_directory(tmp_path: Path, path: str, owner: str) -> None:
    assert out_of_matrix_test_paths([path], registry_path=_registry(tmp_path)) == ((path, owner),)


@pytest.mark.parametrize(
    "path",
    [
        "tests/ci/test_x.py",  # canonical mirror of a row's root
        "tests/upgrade/test_x.py",  # explicit test_dirs claim
        "tests/specify_cli/upgrade/claimed/test_x.py",  # a claim below a recorded directory wins
        "src/specify_cli/upgrade/x.py",  # not a test path
        "testsuite/test_x.py",  # a prefix is not a directory
        "src/tests/test_x.py",  # not under tests/
    ],
)
def test_matrix_and_non_test_paths_are_not_named(tmp_path: Path, path: str) -> None:
    assert out_of_matrix_test_paths([path], registry_path=_registry(tmp_path)) == ()


@pytest.mark.parametrize("path", ["tests/conftest.py", "tests/lane_test_utils.py", "tests/specify_cli/upgrade/x.py", "tests/fixtures/data.json"])
def test_support_file_warning_makes_no_nightly_only_claim(path: str) -> None:
    """A conftest or helper may be loaded per PR too: never told "no per-PR shard runs it"."""
    commands, summary = render_out_of_matrix_report(((path, "tests"),))
    assert commands[0].startswith("::warning")
    assert path in commands[0]
    assert "no per-PR shard runs it" not in commands[0]
    assert "may depend on it" in commands[0]
    assert "Changed support files" in summary
    assert "run only in the nightly" not in summary


@pytest.mark.parametrize("path", ["tests/specify_cli/upgrade/test_x.py", "tests/specify_cli/upgrade/x_test.py"])
def test_test_module_gets_the_nightly_only_warning(path: str) -> None:
    commands, summary = render_out_of_matrix_report(((path, "tests/specify_cli/upgrade"),))
    assert commands[0].startswith("::warning")
    assert "no per-PR shard runs it" in commands[0]
    assert "Changed support files" not in summary


def test_hits_are_sorted_and_deduplicated(tmp_path: Path) -> None:
    paths = ["tests/specify_cli/upgrade/b.py", "tests/specify_cli/upgrade/a.py", "tests/specify_cli/upgrade/a.py"]
    hits = out_of_matrix_test_paths(paths, registry_path=_registry(tmp_path))
    assert [path for path, _ in hits] == ["tests/specify_cli/upgrade/a.py", "tests/specify_cli/upgrade/b.py"]


def test_report_warns_and_lists_each_file() -> None:
    hits = (("tests/specify_cli/upgrade/test_x.py", "tests/specify_cli/upgrade"), ("tests/specify_cli/upgrade/x.py", "tests/specify_cli/upgrade"))
    warnings, summary = render_out_of_matrix_report(hits)
    assert len(warnings) == 2
    assert all(line.startswith("::warning") for line in warnings)
    assert "tests/specify_cli/upgrade/test_x.py" in warnings[0]
    assert "tests/specify_cli/upgrade/x.py" in warnings[1]
    assert "- `tests/specify_cli/upgrade/test_x.py` (out-of-matrix directory `tests/specify_cli/upgrade`)" in summary
    assert "- `tests/specify_cli/upgrade/x.py` (out-of-matrix directory `tests/specify_cli/upgrade`)" in summary


def test_report_is_empty_without_hits() -> None:
    assert render_out_of_matrix_report(()) == ((), "")


def _router_scan_script() -> str:
    workflow = yaml.safe_load(ROUTER.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["prose-scan"]["steps"]
    script = next(step["run"] for step in steps if step.get("id") == "out-of-matrix")
    assert isinstance(script, str)
    return script


def test_router_step_runs_the_helper_and_never_fails(tmp_path: Path) -> None:
    """Execute the router step as written against a two-commit repo."""
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> str:
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()

    git("init", "-q")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Test")
    (repo / "README.md").write_text("x\n")
    (repo / "tests/specify_cli/upgrade").mkdir(parents=True)
    (repo / "tests/specify_cli/upgrade/test_gone.py").write_text("def test_gone():\n    pass\n")
    git("add", ".")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    (repo / "tests/specify_cli/upgrade/test_gone.py").unlink()
    target = repo / "tests/specify_cli/upgrade/test_x.py"
    target.write_text("def test_x():\n    pass\n")
    git("add", "-A")
    git("commit", "-qm", "head")
    head = git("rev-parse", "HEAD")
    summary = tmp_path / "summary.md"
    env = dict(
        os.environ,
        EVENT_NAME="pull_request",
        BASE_SHA=base,
        HEAD_SHA=head,
        PUSH_BEFORE="",
        MERGE_GROUP_BASE="",
        PYTHONPATH=str(ROOT),
        RUNNER_TEMP=str(tmp_path),
        GITHUB_STEP_SUMMARY=str(summary),
    )
    result = subprocess.run(["bash", "-c", _router_scan_script()], cwd=repo, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "::warning" in result.stdout
    assert "tests/specify_cli/upgrade/test_x.py" in result.stdout
    assert "tests/specify_cli/upgrade/test_x.py" in summary.read_text(encoding="utf-8")
    # A deleted nightly-only test has nothing left to run, so it is not named.
    assert "test_gone.py" not in result.stdout


def test_router_step_surfaces_a_helper_crash_as_a_warning(tmp_path: Path) -> None:
    """A broken helper must not read as a quiet run, and must still exit 0."""
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> str:
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()

    git("init", "-q")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Test")
    (repo / "a.txt").write_text("a\n")
    git("add", ".")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    (repo / "a.txt").write_text("b\n")
    git("commit", "-qam", "head")
    env = dict(
        os.environ,
        EVENT_NAME="pull_request",
        BASE_SHA=base,
        HEAD_SHA=git("rev-parse", "HEAD"),
        PUSH_BEFORE="",
        MERGE_GROUP_BASE="",
        PYTHONPATH=str(tmp_path / "no-such-checkout"),
        RUNNER_TEMP=str(tmp_path),
    )
    result = subprocess.run(["bash", "-c", _router_scan_script()], cwd=repo, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "::warning::out-of-matrix scan failed" in result.stdout


def test_router_step_is_quiet_on_a_degenerate_base(tmp_path: Path) -> None:
    env = dict(
        os.environ, EVENT_NAME="push", BASE_SHA="", HEAD_SHA="HEAD", PUSH_BEFORE="0" * 40, MERGE_GROUP_BASE="", PYTHONPATH=str(ROOT), RUNNER_TEMP=str(tmp_path)
    )
    result = subprocess.run(["bash", "-c", _router_scan_script()], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "::warning" not in result.stdout
