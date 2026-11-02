"""Executable regressions for CI verdicts and removal of redundant work."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"


def _workflow(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("mode", ["pr", "full"])
@pytest.mark.parametrize("exit_code", [0, 1, 2, 5])
def test_actual_shard_shell_propagates_pytest_status(tmp_path: Path, mode: str, exit_code: int) -> None:
    """Run the shipped shell, not a second model of its mode branch."""
    steps = _workflow("module-tests.yml")["jobs"]["test"]["steps"]
    script = next(step["run"] for step in steps if step.get("name") == "Run pytest for this shard")
    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    python = venv / "bin/python"
    python.write_text(
        f"#!{sys.executable}\n"
        "import os, subprocess, sys\n"
        "if sys.argv[1:3] == ['-m', 'pytest']:\n"
        "    raise SystemExit(int(os.environ['FAKE_PYTEST_STATUS']))\n"
        f"raise SystemExit(subprocess.call([{sys.executable!r}, *sys.argv[1:]]))\n",
        encoding="utf-8",
    )
    python.chmod(0o755)
    package = tmp_path / "src/probe"
    package.mkdir(parents=True)
    (package / "__init__.py").touch()
    (tmp_path / "shard_tests.txt").write_text("tests/test_probe.py::test_probe\n", encoding="utf-8")
    script = script.replace("${{ steps.warmup.outputs.venv-path }}", str(venv))
    script = script.replace("${{ steps.shard-info.outputs.slug }}", "1-of-1")
    script = script.replace("${{ github.run_id }}", "123")
    result = subprocess.run(
        ["bash", "-c", script],
        cwd=tmp_path,
        env={**os.environ, "TIER": "unit", "MODULE": "probe", "MODE": mode,
             "COV_TARGET": '["probe"]', "RUNNER_TEMP": str(tmp_path), "FAKE_PYTEST_STATUS": str(exit_code)},
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == exit_code, result.stdout + result.stderr
    upload = next(step for step in steps if step.get("name") == "Upload coverage + xunit artefacts")
    assert upload["if"] == "always()"


def test_static_checks_have_one_owner_and_required_router_waits() -> None:
    router = _workflow("ci-router.yml")["jobs"]
    quality = _workflow("ci-quality.yml")["jobs"]
    assert "lint" not in quality
    assert "uv-lock-check" not in quality
    assert "import-linter" not in router
    assert {"ruff", "uv-lock"} <= set(router["router-gate"]["needs"])
    assert "Clean install verification" in quality["clean-install-verification"]["name"]


def test_windows_cancels_only_superseded_pr_evidence() -> None:
    workflow = _workflow("ci-windows.yml")
    concurrency = workflow["concurrency"]
    assert "github.event.pull_request.number" in concurrency["group"]
    assert "github.run_id" in concurrency["group"]
    assert "pull_request" in concurrency["cancel-in-progress"]


def test_aggregate_explicitly_enables_uv_cache_for_workflow_run() -> None:
    jobs = _workflow("ci-aggregate.yml")["jobs"]
    steps = [step for job in jobs.values() for step in job.get("steps", [])]
    setup = [step for step in steps if step.get("uses", "").startswith("astral-sh/setup-uv@")]
    assert setup
    assert all(step.get("with", {}).get("enable-cache") is True for step in setup)


def test_docsite_pnpm_cache_uses_site_lockfile() -> None:
    steps = _workflow("ci-router.yml")["jobs"]["docs-site"]["steps"]
    setup = next(step for step in steps if step.get("uses", "").startswith("actions/setup-node@"))
    assert setup["with"]["cache"] == "pnpm"
    assert setup["with"]["cache-dependency-path"] == "site/pnpm-lock.yaml"
