"""Integration test: ``spec-kitty doctor sparse-checkout`` finding surface (FR-002).

The detection-only cases that a user can reach with plain git (a clean
project, sparse-checkout in the primary checkout, and in the primary plus
two linked worktrees) moved to the acceptance scenarios in
``tests/scenarios/doctor/sparse-checkout.feature``, which run the built CLI
on Linux, macOS and Windows (ADR 2026-10-15-1; rows in
``tests/scenarios/absorption-ledger.json``).

What stays here needs Spec Kitty's own lane registration
(``register_lane_sparse_checkout``), which no CLI command exposes: a managed
lane's sparse-checkout is never reported or remediated as legacy state.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.doctor import app as doctor_app
from specify_cli.coordination import register_lane_sparse_checkout


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_bare_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-q", str(repo)])
    _run(["git", "-C", str(repo), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(repo), "config", "user.name", "Test User"])
    (repo / "README.md").write_text("# Hello\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_text("print('a')\n", encoding="utf-8")
    _run(["git", "-C", str(repo), "add", "-A"])
    _run(["git", "-C", str(repo), "commit", "-m", "seed"])
    # Mark as a spec-kitty project so locate_project_root() resolves to
    # the fixture directory.
    (repo / ".kittify").mkdir()


MISSION_SLUG = "demo-feature-01J6XW9K"
MISSION_ID = "01J6XW9KABCDEFGHJKMNPQRSTV"
MID8 = "01J6XW9K"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}"


def _init_managed_lane_repo(repo: Path) -> Path:
    _init_bare_repo(repo)
    spec_dir = repo / "kitty-specs" / MISSION_SLUG
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    (spec_dir / "status.events.jsonl").write_text("{}\n", encoding="utf-8")
    (spec_dir / "status.json").write_text("{}\n", encoding="utf-8")
    (spec_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": MISSION_SLUG,
                "mission_id": MISSION_ID,
                "coordination_branch": COORD_BRANCH,
            }
        ),
        encoding="utf-8",
    )
    _run(["git", "-C", str(repo), "add", "-A"])
    _run(["git", "-C", str(repo), "commit", "-m", "mission"])
    _run(["git", "-C", str(repo), "branch", COORD_BRANCH])
    wt = _add_worktree(repo, f"{MISSION_SLUG}-lane-a")
    _run(
        [
            "git",
            "-C",
            str(wt),
            "checkout",
            "-q",
            "-B",
            f"{COORD_BRANCH}-lane-a",
            COORD_BRANCH,
        ],
    )
    register_lane_sparse_checkout(wt, MISSION_SLUG, MID8)
    return wt


def _enable_sparse(repo: Path, pattern: str = "README.md\n") -> None:
    _run(["git", "-C", str(repo), "config", "core.sparseCheckout", "true"])
    pf = repo / ".git" / "info" / "sparse-checkout"
    pf.parent.mkdir(parents=True, exist_ok=True)
    pf.write_text(pattern, encoding="utf-8")


def _add_worktree(repo: Path, name: str) -> Path:
    # Exclude .worktrees/ from untracked listings to keep `git status` clean.
    excl = repo / ".git" / "info" / "exclude"
    excl_text = excl.read_text(encoding="utf-8") if excl.exists() else ""
    if ".worktrees/" not in excl_text:
        excl.write_text(excl_text + ".worktrees/\n", encoding="utf-8")
    wt = repo / ".worktrees" / name
    _run(
        ["git", "-C", str(repo), "worktree", "add", "-b", f"feature/{name}", str(wt)],
    )
    # Enable worktree-scoped sparse config so the scanner flags it.
    _run(["git", "-C", str(repo), "config", "extensions.worktreeConfig", "true"])
    _run(
        ["git", "-C", str(wt), "config", "--worktree", "core.sparseCheckout", "true"],
    )
    return wt


def test_doctor_managed_lane_sparse_checkout_is_not_legacy_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Managed lane sparse-checkout must not be remediated as legacy state."""
    repo = tmp_path / "managed"
    wt = _init_managed_lane_repo(repo)

    monkeypatch.setattr(
        "specify_cli.cli.commands._sparse_checkout_doctor.locate_project_root",
        lambda: repo,
    )

    runner = CliRunner()
    result = runner.invoke(doctor_app, ["sparse-checkout"])
    assert result.exit_code == 0, result.stdout
    assert "No legacy sparse-checkout state detected" in result.stdout
    assert "Legacy sparse-checkout state detected" not in result.stdout
    assert "spec-kitty doctor sparse-checkout --fix" not in result.stdout
    assert str(wt) not in result.stdout


def test_doctor_fix_plan_skips_managed_lane_sparse_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "mixed"
    wt = _init_managed_lane_repo(repo)
    _enable_sparse(repo, pattern="README.md\n")

    monkeypatch.setattr(
        "specify_cli.cli.commands._sparse_checkout_doctor.locate_project_root",
        lambda: repo,
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands._sparse_checkout_doctor._is_interactive_environment",
        lambda: True,
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    runner = CliRunner()
    result = runner.invoke(doctor_app, ["sparse-checkout", "--fix"])
    assert result.exit_code == 0, result.stdout
    assert "git sparse-checkout disable (primary)" in result.stdout
    assert "repeat steps" not in result.stdout
    assert str(wt) not in result.stdout
