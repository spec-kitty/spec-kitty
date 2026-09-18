"""Regression: ``research --mission <nonexistent>`` must refuse, not scaffold.

FR-001 / contract C1 (``kitty-specs/mission-handle-resolution-consistency-…/
contracts/cli-behavior.md``): before this gate, ``research`` resolved the
mission directory with *path-safety only* (no existence check) and then ran
``planning_dir.mkdir(parents=True, exist_ok=True)`` — so a bad ``--mission``
handle silently scaffolded a phantom ``kitty-specs/<handle>/`` tree and exited
0. The command must instead emit the canonical ``Mission not found: <handle>``
(WP01's :data:`MISSION_NOT_FOUND_MESSAGE` constant), exit non-zero, and leave
the filesystem byte-for-byte unchanged (NFR-001 snapshot invariant).

``research`` is human-only (no ``--json``, FR-011) so this asserts on human
text + exit code + an on-disk snapshot, via the in-process
:class:`typer.testing.CliRunner` (the subprocess ``run_cli`` fixture is avoided
per the WP: it is ~90s slower and prone to stale-install false-reds).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def _seed_mission(specs_dir: Path, slug: str, mission_id: str) -> None:
    """Create a minimal but real mission directory under ``kitty-specs/``."""
    mission_dir = specs_dir / slug
    mission_dir.mkdir(parents=True)
    (mission_dir / "spec.md").write_text(f"# {slug}\n", encoding="utf-8")
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission": "research", "mission_id": mission_id, "mission_slug": slug}),
        encoding="utf-8",
    )


def _snapshot(root: Path) -> list[str]:
    """Sorted, root-relative listing of the whole ``kitty-specs/`` subtree."""
    specs = root / "kitty-specs"
    return sorted(str(p.relative_to(root)) for p in specs.rglob("*"))


@pytest.fixture
def staged_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real repo with two genuine missions and no ``zznope`` mission."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "research-gate@example.invalid")
    _git(repo_root, "config", "user.name", "Research Gate")
    _git(repo_root, "config", "commit.gpgsign", "false")
    (repo_root / ".kittify").mkdir()

    specs_dir = repo_root / "kitty-specs"
    _seed_mission(specs_dir, "001-alpha-mission", "01M2TPWG0000000000000ALPHA")
    _seed_mission(specs_dir, "002-beta-mission", "01M2TPWG00000000000000BETA")

    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)
    return repo_root


def test_research_nonexistent_mission_refuses_and_writes_nothing(staged_repo: Path) -> None:
    """A nonexistent handle must not scaffold a phantom ``kitty-specs/<handle>/``."""
    before = _snapshot(staged_repo)

    result = runner.invoke(app, ["research", "--mission", "zznope"])

    assert result.exit_code != 0, result.output
    assert "Mission not found: zznope" in result.output

    after = _snapshot(staged_repo)
    assert after == before, f"research must leave kitty-specs/ byte-for-byte unchanged on a nonexistent handle; diff added: {sorted(set(after) - set(before))}"

    # The specific phantom paths the pre-fix mkdir/scaffold produced must be absent.
    phantom = staged_repo / "kitty-specs" / "zznope"
    assert not phantom.exists()
    for leaf in ("research.md", "data-model.md", "research/evidence-log.csv", "research/source-register.csv"):
        assert not (phantom / leaf).exists()
