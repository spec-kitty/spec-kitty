"""A changed-file list must reach CI routing steps through a file, never an env var.

Linux caps ONE argv/env string at ``MAX_ARG_STRLEN`` (128 KiB). A PR that changes
a thousand-odd files overflows it, and the step dies with ``Argument list too
long`` (exit 126) before ``python3`` even starts. The routing steps therefore
write the list under ``$RUNNER_TEMP`` and hand over only the path.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOWS = _REPO_ROOT / ".github" / "workflows"
_SCRIPT = _REPO_ROOT / "scripts" / "ci" / "corpus_select.py"
_MAX_ARG_STRLEN = 128 * 1024

# Env names that used to carry a diff list, and the file-path names that replace them.
_FORBIDDEN_ENV = ("CHANGED_FILES", "SCAN_DIFF_PATHS", "REDUCE_DIFF_PATHS")
_ROUTING_WORKFLOWS = ("ci-router.yml", "packs.yml", "ci-modules.yml")


def _big_docs_list() -> list[str]:
    paths = [f"docs/generated/{'x' * 80}/file-{i:06d}.md" for i in range(2000)]
    assert len(json.dumps(paths)) > _MAX_ARG_STRLEN
    return paths


def _run_script(env_extra: dict[str, str], tmp_path: Path) -> tuple[subprocess.CompletedProcess[str], str]:
    out = tmp_path / "gh-output"
    env = {key: value for key, value in os.environ.items() if key not in {"CHANGED_FILES", "CHANGED_FILES_PATH", "CHANGED_OUTCOME"}}
    env.update({"GITHUB_OUTPUT": str(out), "PYTHONPATH": str(_REPO_ROOT), **env_extra})
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--mode", "pr", "--event", "pull_request"],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
        env=env,
        check=False,
    )
    return result, out.read_text(encoding="utf-8") if out.exists() else ""


def test_corpus_select_reads_an_oversized_list_from_a_file(tmp_path: Path) -> None:
    """A >128 KiB list through CHANGED_FILES_PATH is read; a docs-only diff does NOT select the corpus."""
    list_file = tmp_path / "changed.json"
    list_file.write_text(json.dumps(_big_docs_list()), encoding="utf-8")
    result, output = _run_script({"CHANGED_FILES_PATH": str(list_file), "CHANGED_OUTCOME": "success"}, tmp_path)
    assert result.returncode == 0, result.stderr
    assert "selected=false" in output, f"the file was ignored (fail-closed selected=true): {output!r}"


def test_corpus_select_oversized_env_value_cannot_even_start(tmp_path: Path) -> None:
    """Characterise the defect: the same list in the env var is un-exec-able on Linux."""
    if sys.platform != "linux":
        pytest.skip("MAX_ARG_STRLEN is a Linux limit")
    with pytest.raises(OSError, match="Argument list too long"):
        _run_script({"CHANGED_FILES": json.dumps(_big_docs_list()), "CHANGED_OUTCOME": "success"}, tmp_path)


def test_corpus_select_missing_file_fails_closed(tmp_path: Path) -> None:
    result, output = _run_script({"CHANGED_FILES_PATH": str(tmp_path / "absent.json"), "CHANGED_OUTCOME": "success"}, tmp_path)
    assert result.returncode == 0, result.stderr
    assert "selected=true" in output


def test_corpus_select_unparseable_file_fails_closed(tmp_path: Path) -> None:
    list_file = tmp_path / "changed.json"
    list_file.write_text("not json", encoding="utf-8")
    result, output = _run_script({"CHANGED_FILES_PATH": str(list_file), "CHANGED_OUTCOME": "success"}, tmp_path)
    assert "selected=true" in output, result.stderr


def test_corpus_select_env_fallback_still_works(tmp_path: Path) -> None:
    result, output = _run_script({"CHANGED_FILES": json.dumps(["docs/x.md"]), "CHANGED_OUTCOME": "success"}, tmp_path)
    assert result.returncode == 0, result.stderr
    assert "selected=false" in output


def _step_env_and_run(name: str) -> list[tuple[dict[str, str], str]]:
    doc = yaml.safe_load((_WORKFLOWS / name).read_text(encoding="utf-8"))
    rows: list[tuple[dict[str, str], str]] = []
    for job in doc["jobs"].values():
        for step in job.get("steps", []) or []:
            rows.append((dict(step.get("env") or {}), str(step.get("run", ""))))
    return rows


@pytest.mark.parametrize("workflow", _ROUTING_WORKFLOWS)
def test_no_routing_step_puts_a_diff_list_in_an_env_var(workflow: str) -> None:
    offenders: list[str] = []
    for env, run in _step_env_and_run(workflow):
        for name in _FORBIDDEN_ENV:
            if name in env:
                offenders.append(f"step env {name}")
            # inline `NAME=... cmd`, `export NAME=...`, and `NAME="$diff_output"` forms
            if re.search(rf"(?<![A-Z_]){name}=", run):
                offenders.append(f"run-script assignment {name}=")
        if re.search(r"""[A-Z_]+="\$\{?(diff_output|files_json)\b""", run):
            offenders.append("run-script env assignment of $diff_output / $files_json")
        for value in env.values():
            if "steps.changed-files.outputs.files" in str(value) and not str(value).endswith("-path }}"):
                offenders.append("step env carries the changed-files list output")
    assert not offenders, f"{workflow}: {sorted(set(offenders))}"


@pytest.mark.parametrize("workflow", _ROUTING_WORKFLOWS)
def test_routing_workflow_hands_over_a_file_under_runner_temp(workflow: str) -> None:
    text = (_WORKFLOWS / workflow).read_text(encoding="utf-8")
    assert "RUNNER_TEMP" in text, f"{workflow}: the diff list must live under $RUNNER_TEMP"
    assert re.search(r"(CHANGED_FILES_PATH|SCAN_DIFF_PATHS_FILE|REDUCE_DIFF_PATHS_FILE)", text)
