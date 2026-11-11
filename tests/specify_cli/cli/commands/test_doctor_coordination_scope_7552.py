"""#7552: ``doctor coordination --fix`` acts only on the Missions named.

Driven through the real ``doctor`` Typer app (the pre-existing entry point),
against real git repositories:

* ``--fix`` with no scope refuses and mutates nothing (FR-001);
* ``--fix --all-missions`` keeps the repository-wide repair (FR-002);
* ``--fix --mission A`` reports and repairs only A, stranded-revert markers
  included (FR-003);
* ``--mission`` with ``--all-missions`` refuses (FR-004);
* a Mission held only by its Mission branch (no checkout) is found, reported
  and repaired (FR-006), and a Mission branch contributes only its own Mission
  (FR-007).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands import _coordination_doctor as cd
from specify_cli.cli.commands.doctor import app as doctor_app

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_RUNNER = CliRunner()

A_SLUG = "alpha-mission-01J6XW9K"
A_ID = "01J6XW9KABCDEFGHJKMNPQRSTV"
B_SLUG = "bravo-mission-01J6ZZ00"
B_ID = "01J6ZZ00ABCDEFGHJKMNPQRSTV"
C_SLUG = "charlie-mission-01J7AAAA"
C_ID = "01J7AAAAABCDEFGHJKMNPQRSTV"
C_BRANCH = f"kitty/mission-{C_SLUG}"
D_SLUG = "delta-mission-01J7BBBB"
D_ID = "01J7BBBBABCDEFGHJKMNPQRSTV"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@x.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    return repo


def _write_mission(repo: Path, slug: str, mission_id: str, **extra: object) -> Path:
    mission_dir = repo / "kitty-specs" / slug
    mission_dir.mkdir(parents=True)
    (mission_dir / "spec.md").write_text("# spec\n")
    (mission_dir / "status.events.jsonl").write_text("")
    meta = {"mission_slug": slug, "mission_id": mission_id, **extra}
    (mission_dir / "meta.json").write_text(json.dumps(meta))
    return mission_dir / "meta.json"


@pytest.fixture
def two_never_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    """Missions A and B, each declaring a coordination branch that was never created."""
    repo = _init_repo(tmp_path)
    meta_a = _write_mission(repo, A_SLUG, A_ID, coordination_branch="kitty/mission-never-created-aaaaaaaa")
    meta_b = _write_mission(repo, B_SLUG, B_ID, coordination_branch="kitty/mission-never-created-bbbbbbbb")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "missions")
    monkeypatch.setattr(cd, "locate_project_root", lambda: repo)
    monkeypatch.chdir(repo)
    return repo, meta_a, meta_b


def _invoke(*args: str) -> tuple[int, str]:
    result = _RUNNER.invoke(doctor_app, ["coordination", *args])
    return result.exit_code, result.output


# ---------------------------------------------------------------------------
# FR-001 / FR-002 / FR-004: the scope gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("json_flag", [(), ("--json",)])
def test_fix_without_scope_refuses_and_mutates_nothing(two_never_created: tuple[Path, Path, Path], json_flag: tuple[str, ...]) -> None:
    _repo, meta_a, meta_b = two_never_created
    before = (meta_a.read_bytes(), meta_b.read_bytes())

    code, output = _invoke("--fix", *json_flag)

    assert code == 1
    assert "COORDINATION_FIX_SCOPE_REQUIRED" in output
    assert "--mission" in output and "--all-missions" in output
    assert (meta_a.read_bytes(), meta_b.read_bytes()) == before


def test_fix_all_missions_repairs_every_mission(two_never_created: tuple[Path, Path, Path]) -> None:
    _repo, meta_a, meta_b = two_never_created

    code, output = _invoke("--fix", "--all-missions")

    assert code == 0, output
    assert "coordination_branch" not in json.loads(meta_a.read_text())
    assert "coordination_branch" not in json.loads(meta_b.read_text())


def test_fix_with_mission_repairs_only_that_mission(two_never_created: tuple[Path, Path, Path]) -> None:
    _repo, meta_a, meta_b = two_never_created
    before_b = meta_b.read_bytes()

    code, output = _invoke("--fix", "--mission", A_SLUG)

    assert code == 0, output
    assert "coordination_branch" not in json.loads(meta_a.read_text())
    assert meta_b.read_bytes() == before_b


def test_mission_and_all_missions_together_refuse(two_never_created: tuple[Path, Path, Path]) -> None:
    _repo, meta_a, meta_b = two_never_created
    before = (meta_a.read_bytes(), meta_b.read_bytes())

    code, output = _invoke("--fix", "--mission", A_SLUG, "--all-missions")

    assert code == 1
    assert "COORDINATION_FIX_SCOPE_CONFLICT" in output
    assert (meta_a.read_bytes(), meta_b.read_bytes()) == before


def test_report_without_fix_needs_no_scope(two_never_created: tuple[Path, Path, Path]) -> None:
    """The read-only report keeps scanning every Mission with no flag (C-003)."""
    _repo, meta_a, meta_b = two_never_created
    before = (meta_a.read_bytes(), meta_b.read_bytes())

    code, output = _invoke("--json")

    payload = json.loads(output)
    assert {f["error_code"] for f in payload} >= {"COORDINATION_WORKTREE_NEVER_CREATED"}
    assert "COORDINATION_FIX_SCOPE_REQUIRED" not in output
    assert code == 0
    assert (meta_a.read_bytes(), meta_b.read_bytes()) == before

    # ``--all-missions`` without ``--fix`` still reports, and says it has no effect.
    code, output = _invoke("--all-missions")
    assert code == 0
    assert "only applies with --fix" in output
    assert (meta_a.read_bytes(), meta_b.read_bytes()) == before


# ---------------------------------------------------------------------------
# FR-003: --mission scopes the stranded-revert check and its fixer
# ---------------------------------------------------------------------------


def test_mission_scope_drops_another_missions_strand(two_never_created: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    strand_b = cd.DoctorFinding(
        severity="error",
        message=f"stranded done for {B_SLUG}",
        next_step="",
        error_code=cd._STRANDED_COORD_REVERT_CODE,
        extra={"mission_id": B_ID, "mission_slug": B_SLUG},
    )
    monkeypatch.setattr(cd, "_check_stranded_coord_revert", lambda _root: [strand_b])
    healed: list[str] = []

    def _record_heal(finding: cd.DoctorFinding, _root: Path) -> tuple[str | None, cd.DoctorFinding | None]:
        healed.append(str(finding.extra.get("mission_slug")))
        return None, None

    monkeypatch.setattr(cd, "_heal_one_strand", _record_heal)

    code, output = _invoke("--fix", "--mission", A_SLUG, "--json")

    assert code == 0, output
    assert B_SLUG not in output
    assert healed == []

    # Positive control on the same fixture: the unscoped run reports and heals B's strand.
    code_all, output_all = _invoke("--fix", "--all-missions", "--json")
    assert B_SLUG in output_all
    assert healed == [B_SLUG]
    assert code_all == 1  # the strand finding survives the (recorded no-op) heal


# ---------------------------------------------------------------------------
# FR-006 / FR-007: a Mission held only by its Mission branch
# ---------------------------------------------------------------------------


@pytest.fixture
def branch_only_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Mission C exists only on its own Mission branch; no checkout holds that branch.

    The branch also carries Mission D's directory, whose meta names another
    branch (inherited content): it must not be attributed to C's branch.
    """
    repo = _init_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", C_BRANCH)
    _write_mission(
        repo,
        C_SLUG,
        C_ID,
        mission_branch=C_BRANCH,
        coordination_branch=C_BRANCH,
        target_branch="main",
        topology="lanes_with_coord",
        topology_source="default",
    )
    _write_mission(repo, D_SLUG, D_ID, mission_branch="kitty/mission-elsewhere-01J7BBBB", coordination_branch="kitty/mission-elsewhere-01J7BBBB")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "mission C (and inherited D)")
    _git(repo, "checkout", "-q", "main")
    assert not (repo / "kitty-specs").exists()
    monkeypatch.setattr(cd, "locate_project_root", lambda: repo)
    monkeypatch.chdir(repo)
    return repo


def test_scan_reports_the_branch_only_missions_missing_worktree(branch_only_mission: Path) -> None:
    code, output = _invoke("--json")

    payload = json.loads(output)
    missing = [f for f in payload if f["error_code"] == "COORDINATION_WORKTREE_MISSING"]
    assert [f["extra"].get("mission_slug") for f in missing] == [C_SLUG], output
    assert D_SLUG not in output  # FR-007: inherited directory not attributed to C's branch
    assert code in (0, 1)
    assert not (branch_only_mission / ".worktrees").exists()  # C-003: the report is read-only


@pytest.mark.parametrize("handle", [C_ID, C_ID[:8], C_SLUG])
def test_fix_with_mission_materializes_the_branch_only_missions_worktree(branch_only_mission: Path, handle: str) -> None:
    code, output = _invoke("--fix", "--mission", handle)

    worktrees = [line.split()[0] for line in _git(branch_only_mission, "worktree", "list", "--porcelain").splitlines() if line.startswith("worktree ")]
    held = _git(branch_only_mission, "worktree", "list", "--porcelain")
    assert f"branch refs/heads/{C_BRANCH}" in held, output
    assert len(worktrees) == 2
    assert code == 0, output


def test_all_missions_fix_does_not_restore_a_branch_only_worktree(branch_only_mission: Path) -> None:
    """``consolidate --abort`` removes a coordination worktree on purpose and keeps the branch:
    an unscoped ``--fix --all-missions`` reports it but does not bring it back (review fold)."""
    code, output = _invoke("--fix", "--all-missions", "--json")

    held = _git(branch_only_mission, "worktree", "list", "--porcelain")
    assert f"branch refs/heads/{C_BRANCH}" not in held
    assert f"--fix --mission {C_SLUG}" in output
    assert "COORDINATION_WORKTREE_NOT_RESTORED" in output
    assert code == 0, output


@pytest.mark.parametrize("how", ["corrupt_file", "reader_returns_none"])
def test_named_mission_with_unreadable_meta_is_never_reported_healthy(
    two_never_created: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, how: str
) -> None:
    """A named Mission whose meta.json is unreadable fails closed, and the other Mission is untouched.

    ``reader_returns_none`` pins the branch a resolved-then-unreadable Mission takes
    (the resolver itself skips a corrupt file, so ``corrupt_file`` may stop earlier).
    """
    _repo, meta_a, meta_b = two_never_created
    if how == "corrupt_file":
        meta_a.write_text("{not json")
    else:
        monkeypatch.setattr(cd, "_read_scanned_meta", lambda _dir: None)
    before = (meta_a.read_bytes(), meta_b.read_bytes())

    code, output = _invoke("--fix", "--mission", A_SLUG, "--json")

    assert code == 1, output
    expected = ("COORDINATION_META_UNREADABLE",) if how == "reader_returns_none" else ("MISSION_NOT_FOUND", "COORDINATION_META_UNREADABLE")
    assert any(code_name in output for code_name in expected), output
    assert (meta_a.read_bytes(), meta_b.read_bytes()) == before


def test_scan_sees_a_mission_held_only_by_its_coordination_worktree(branch_only_mission: Path) -> None:
    """FR-005: once the coordination worktree exists, the Mission is read from it (the root
    checkout still has no copy) and its worktree is reported healthy, not missing."""
    code, output = _invoke("--fix", "--mission", C_SLUG)
    assert code == 0, output
    assert not (branch_only_mission / "kitty-specs").exists()

    code, output = _invoke("--json")

    payload = json.loads(output)
    assert not [f for f in payload if f["error_code"] == "COORDINATION_WORKTREE_MISSING"], output
    assert any(C_SLUG in f["message"] for f in payload if f["severity"] == "ok"), output
    assert code == 0, output


def test_malformed_meta_on_a_mission_branch_is_a_warning_not_a_crash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A Mission branch whose meta.json does not decode is reported, never repaired (FR-006)."""
    repo = _init_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", C_BRANCH)
    broken = repo / "kitty-specs" / C_SLUG
    broken.mkdir(parents=True)
    (broken / "meta.json").write_text("{not json")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "broken meta")
    _git(repo, "checkout", "-q", "main")
    monkeypatch.setattr(cd, "locate_project_root", lambda: repo)
    monkeypatch.chdir(repo)

    code, output = _invoke("--json")

    payload = json.loads(output)
    unreadable = [f for f in payload if f["error_code"] == "COORDINATION_BRANCH_META_UNREADABLE"]
    assert [f["extra"]["branch"] for f in unreadable] == [C_BRANCH], output
    assert code == 0, output


def test_mid8_shared_by_a_root_and_an_off_root_mission_is_ambiguous(two_never_created: tuple[Path, Path, Path]) -> None:
    """A mid8 naming a root Mission and a branch-only one must not silently pick the root one."""
    repo, meta_a, _meta_b = two_never_created
    e_slug = "echo-mission-01J6XW9K"
    e_branch = f"kitty/mission-{e_slug}"
    _git(repo, "checkout", "-q", "-b", e_branch)
    _git(repo, "rm", "-rq", "kitty-specs")
    _write_mission(repo, e_slug, A_ID[:8] + "ZZZZZZZZZZZZZZZZZZ", mission_branch=e_branch, coordination_branch=e_branch)
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "mission E")
    _git(repo, "checkout", "-q", "main")
    before = meta_a.read_bytes()

    code, output = _invoke("--fix", "--mission", A_ID[:8], "--json")

    assert code == 1, output
    assert "AMBIGUOUS_HANDLE" in output
    assert meta_a.read_bytes() == before
