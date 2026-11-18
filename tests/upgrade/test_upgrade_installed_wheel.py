"""Source-free installed-wheel witness for upgrade preview."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.distribution, pytest.mark.integration, pytest.mark.slow]
CHECKOUT = Path(__file__).resolve().parents[2]


def test_installed_wheel_full_preview_has_no_source_leak(installed_wheel_venv: dict[str, Path], tmp_path: Path) -> None:
    venv = installed_wheel_venv["venv_dir"]
    executable = venv / ("Scripts/spec-kitty.exe" if os.name == "nt" else "bin/spec-kitty")
    python = installed_wheel_venv["python"]
    wheel = installed_wheel_venv["wheel"]
    env = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "SPEC_KITTY_TEMPLATE_ROOT"}}
    env.update(HOME=str(tmp_path / "home"), SPEC_KITTY_HOME=str(tmp_path / "home/.kittify"), SPEC_KITTY_ENABLE_SAAS_SYNC="0")
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "wheel"], cwd=project, check=True, env=env)
    # init makes this unborn repository's root commit (#7612), which needs an identity.
    for key, value in (("user.name", "QA"), ("user.email", "qa@example.invalid"), ("commit.gpgsign", "false")):
        subprocess.run(["git", "config", key, value], cwd=project, check=True, env=env)
    initialized = subprocess.run(
        [str(executable), "init", "--ai", "claude,codex", "--non-interactive"],
        cwd=project,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert initialized.returncode == 0, initialized.stderr
    probe = subprocess.run(
        [str(python), "-c", "import json,specify_cli; print(json.dumps({'module':specify_cli.__file__}))"],
        cwd=project,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    module = Path(json.loads(probe.stdout)["module"]).resolve()
    assert module.is_relative_to(venv.resolve()) and not module.is_relative_to(CHECKOUT.resolve())
    result = subprocess.run(
        [str(executable), "upgrade", "--plan-json", "--no-worktrees"],
        cwd=project,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["decision"] == "ready" and payload["complete"] is True
    assert hashlib.sha256(wheel.read_bytes()).hexdigest()  # noqa: TID251 - distribution artifact integrity
