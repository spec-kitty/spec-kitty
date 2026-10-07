"""``RESIDUE_DIRECTORY``: a non-Mission directory is reported, non-blocking (#5812)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.audit import AuditOptions, run_audit
from specify_cli.audit.models import MissionAuditResult, is_teamspace_blocker

pytestmark = [pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "T")
    (tmp_path / ".gitignore").write_text("*.lock\n", encoding="utf-8")
    ghost = tmp_path / "kitty-specs" / "ghost-01ABCDEF"
    ghost.mkdir(parents=True)
    (ghost / "x.lock").write_text("", encoding="utf-8")
    legacy = tmp_path / "kitty-specs" / "legacy-01LEGACYY"
    legacy.mkdir()
    (legacy / "meta.json").write_text(json.dumps({"mission_slug": legacy.name}), encoding="utf-8")
    (legacy / "spec.md").write_text("# legacy\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def _result(repo: Path, slug: str) -> MissionAuditResult:
    report = run_audit(AuditOptions(repo_root=repo))
    (result,) = (m for m in report.missions if m.mission_slug == slug)
    return result


@pytest.mark.parametrize("scan_root_form", ["default"])
def test_residue_yields_one_non_blocking_finding_and_no_identity_missing(
    repo: Path, tmp_path_factory: pytest.TempPathFactory, scan_root_form: str
) -> None:
    scan_root = None
    if scan_root_form == "symlink":
        # A symlinked scan root is still the default kitty-specs/ scan; it must keep filtering residue.
        scan_root = tmp_path_factory.mktemp("link") / "specs"
        scan_root.symlink_to(repo / "kitty-specs", target_is_directory=True)
    report = run_audit(AuditOptions(repo_root=repo, scan_root=scan_root))
    (ghost,) = (m for m in report.missions if m.mission_slug == "ghost-01ABCDEF")
    assert [f.code for f in ghost.findings] == ["RESIDUE_DIRECTORY"]
    # The operator is told how to recover a pre-identity Mission that was mis-read as residue.
    assert "spec-kitty migrate backfill-identity" in ghost.findings[0].detail
    assert not any(is_teamspace_blocker(f) for f in ghost.findings)


def test_real_mission_without_mission_id_still_reports_identity_missing(repo: Path) -> None:
    assert "IDENTITY_MISSING" in _result(repo, "legacy-01LEGACYY").finding_codes


def test_repair_backfills_identity_for_real_legacy_mission_and_skips_residue(repo: Path) -> None:
    from specify_cli.migration.mission_state import repair_repo

    report = repair_repo(repo, allow_dirty=True)

    assert report.residue_directories == ["ghost-01ABCDEF"]
    assert report.target_missions == ["legacy-01LEGACYY"]
    meta = json.loads((repo / "kitty-specs" / "legacy-01LEGACYY" / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("mission_id")
    assert not (repo / "kitty-specs" / "ghost-01ABCDEF" / "meta.json").exists()
