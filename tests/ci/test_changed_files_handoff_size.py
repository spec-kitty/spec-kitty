"""The changed-path list crosses workflow steps in a file, never in one env var (#6915).

Linux caps a single environment string at 128 KiB (``MAX_ARG_STRLEN``). A pull request
that changes ~2000 paths produced a JSON list over that cap, and exec of ``python3``
failed with E2BIG ("Argument list too long", exit 126) in the ``ci-modules.yml``
``changed-files`` step, which then failed the whole module matrix. ``packs.yml``'s
corpus step exported the same list the same way.

These tests execute the REAL step scripts against a throwaway git repository whose
diff lists more than 128 KiB of paths, so the handoff cannot regress to an env var
while the unit-level checks stay green.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci.corpus_select import main as corpus_main

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parents[2]
_MAX_ARG_STRLEN = 128 * 1024
_PATH_COUNT = 2200
_LONG_SEGMENT = "a-deliberately-long-directory-name-to-push-the-list-past-the-limit"


def _steps(workflow: str, job: str) -> dict[str, dict[str, Any]]:
    doc = yaml.safe_load((ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8"))
    return {step["id"]: step for step in doc["jobs"][job]["steps"] if "id" in step}


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return result.stdout.strip()


@pytest.fixture(scope="module")
def big_diff_repo(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, str]:
    """A git repository whose base..head diff lists more than 128 KiB of paths."""
    repo = tmp_path_factory.mktemp("big-diff")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "ci@example.invalid")
    _git(repo, "config", "user.name", "ci")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    target = repo / "docs" / _LONG_SEGMENT
    target.mkdir(parents=True)
    for index in range(_PATH_COUNT):
        (target / f"page-{index:05d}.md").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD")
    listed = _git(repo, "diff", "--name-only", base, head)
    assert len(json.dumps(listed.splitlines())) > _MAX_ARG_STRLEN, "control: the fixture must exceed one env string's limit"
    return repo, base, head


def _python_shim(bin_dir: Path) -> Path:
    bin_dir.mkdir(exist_ok=True)
    shim = bin_dir / "python3"
    shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
    shim.chmod(0o755)
    return bin_dir


def _outputs(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines() if "=" in line)


def test_ci_modules_hands_a_huge_diff_to_the_build_step_in_a_file(tmp_path: Path, big_diff_repo: tuple[Path, str, str]) -> None:
    repo, base, head = big_diff_repo
    steps = _steps("ci-modules.yml", "generate-matrix")
    bin_dir = _python_shim(tmp_path / "bin")
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    changed_output = tmp_path / "changed-output"
    changed_output.write_text("", encoding="utf-8")
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "EVENT_NAME": "pull_request",
        "BASE_SHA": base,
        "HEAD_SHA": head,
        "PUSH_BEFORE": "",
        "MERGE_GROUP_BASE": "",
        "PYTHONPATH": str(ROOT),
        "RUNNER_TEMP": str(runner_temp),
        "GITHUB_OUTPUT": str(changed_output),
    }
    subprocess.run(["bash", "-c", steps["changed-files"]["run"]], cwd=repo, env=env, check=True, capture_output=True, text=True)
    outputs = _outputs(changed_output)
    assert outputs["outcome"] == "success"
    assert "files" not in outputs, "the list itself must never become a step output that lands in an env var"
    listed = json.loads(Path(outputs["files-path"]).read_text(encoding="utf-8"))
    assert len(listed) == _PATH_COUNT

    work = tmp_path / "build"
    (work / ".github").mkdir(parents=True)
    (work / ".github" / "ci-module-registry.yml").write_text((ROOT / ".github" / "ci-module-registry.yml").read_text(encoding="utf-8"), encoding="utf-8")
    build_output = tmp_path / "build-output"
    build_output.write_text("", encoding="utf-8")
    build_env = {
        "PATH": env["PATH"],
        "HOME": str(tmp_path),
        "MODE": "pr",
        "SELECTION_FORCED_FULL": "false",
        "CHANGED_FILES_PATH": outputs["files-path"],
        "CHANGED_FILTER_OUTCOME": outputs["outcome"],
        "GREEN_SKIP": "false",
        "PYTHONPATH": str(ROOT),
        "GITHUB_OUTPUT": str(build_output),
    }
    assert max(len(value) for value in build_env.values()) < _MAX_ARG_STRLEN
    subprocess.run(["bash", "-c", steps["build"]["run"]], cwd=work, env=build_env, check=True, capture_output=True, text=True)
    assert "matrix=" in build_output.read_text(encoding="utf-8")


def test_ci_modules_build_step_reads_the_list_by_path_not_inline() -> None:
    env = _steps("ci-modules.yml", "generate-matrix")["build"]["env"]
    assert env["CHANGED_FILES_PATH"] == "${{ steps.changed-files.outputs.files-path }}"
    assert "CHANGED_FILES" not in env


def test_packs_corpus_step_survives_a_huge_diff(tmp_path: Path, big_diff_repo: tuple[Path, str, str]) -> None:
    repo, base, head = big_diff_repo
    step = _steps("packs.yml", "changes")["corpus"]
    bin_dir = _python_shim(tmp_path / "bin")
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    work = tmp_path / "packs"
    work.mkdir()
    # The step runs `python3 scripts/ci/corpus_select.py` from the checkout root; the script
    # resolves the router from its own (real) location, so a symlink is enough.
    (work / "scripts").symlink_to(ROOT / "scripts")
    github_output = tmp_path / "github-output"
    github_output.write_text("", encoding="utf-8")
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "EVENT_NAME": "pull_request",
        "BASE_SHA": base,
        "HEAD_SHA": head,
        "MODE": "pr",
        "PYTHONPATH": str(ROOT),
        "RUNNER_TEMP": str(runner_temp),
        "GITHUB_OUTPUT": str(github_output),
        "GIT_DIR": str(repo / ".git"),
        "GIT_WORK_TREE": str(repo),
    }
    result = subprocess.run(["bash", "-c", step["run"]], cwd=work, env=env, check=True, capture_output=True, text=True)
    assert "diff unavailable" not in result.stdout.lower()
    assert len(json.loads((runner_temp / "packs-changed-files.json").read_text(encoding="utf-8"))) == _PATH_COUNT
    assert _outputs(github_output)["selected"] in {"true", "false"}


def test_corpus_select_prefers_the_file_over_the_inline_list(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    listed = tmp_path / "changed.json"
    listed.write_text(json.dumps(["docs/readme.md"]), encoding="utf-8")
    out = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setenv("CHANGED_FILES_PATH", str(listed))
    monkeypatch.setenv("CHANGED_FILES", json.dumps(["kitty-specs/m/spec.md"]))
    monkeypatch.setenv("CHANGED_OUTCOME", "success")
    assert corpus_main(["--mode", "pr", "--event", "pull_request"]) == 0
    assert out.read_text(encoding="utf-8") == "selected=false\n"


def test_corpus_select_fails_closed_when_the_file_is_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setenv("CHANGED_FILES_PATH", str(tmp_path / "absent.json"))
    monkeypatch.delenv("CHANGED_FILES", raising=False)
    monkeypatch.setenv("CHANGED_OUTCOME", "success")
    assert corpus_main(["--mode", "pr", "--event", "pull_request"]) == 0
    assert out.read_text(encoding="utf-8") == "selected=true\n"
