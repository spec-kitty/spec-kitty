"""``spec-kitty doctor workspaces`` landed-worktree report and ``--prune`` (#7173, WP04).

Real repositories with a bare ``origin``; the CLI is driven through
``CliRunner``. The process probe is the real one pointed at an empty fake
``/proc`` (nothing is busy), so a clean landed worktree gets ``landed``
whatever runs on the test host; one case reports processes that could not be
inspected.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands import doctor as doctor_module
from specify_cli.git.destructive_guard import DestructiveOpRefused
from specify_cli.workspace import landed_worktrees, process_probe
from specify_cli.workspace.process_probe import ProcessProbeResult

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_LANDED = "land-7086"
_PRUNE_HINT = "spec-kitty doctor workspaces --prune"
_HUSK_KEYS = {"worktrees_dir", "healthy", "registration_error", "husks"}


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed in {cwd}: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def _commit(cwd: Path, name: str, content: str) -> str:
    (cwd / name).write_text(content, encoding="utf-8")
    _git(cwd, "add", "-A")
    _git(cwd, "commit", "-q", "-m", f"add {name}")
    return _git(cwd, "rev-parse", "HEAD").strip()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repository whose ``main`` is pushed to a bare ``origin``; the CLI resolves to it."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    (root / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    _commit(root, "src.py", "x = 1\n")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-q", "-u", "origin", "main")
    monkeypatch.setattr(doctor_module, "locate_project_root", lambda *a, **k: root)
    monkeypatch.chdir(root)
    return root


@pytest.fixture(autouse=True)
def idle_proc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The real probe over an empty fake ``/proc``: no process stands in any worktree."""
    real = process_probe.processes_with_cwd_under
    empty = tmp_path / "proc-empty"
    empty.mkdir()

    def probe(paths: Sequence[Path]) -> ProcessProbeResult:
        return real(paths, proc_root=empty)

    monkeypatch.setattr(process_probe, "processes_with_cwd_under", probe)


def _landed_worktree(root: Path, branch: str = _LANDED) -> tuple[Path, str]:
    """A worktree whose commit was merged into ``main`` and pushed, with ``origin/main`` fetched."""
    path = root / ".worktrees" / branch
    _git(root, "worktree", "add", "-q", "-b", branch, str(path), "main")
    tip = _commit(path, f"{branch}.txt", f"{branch}\n")
    _git(root, "merge", "-q", "--ff-only", branch)
    _git(root, "push", "-q", "origin", "main")
    _git(root, "fetch", "-q", "origin")
    return path, tip


def _unlanded_worktree(root: Path, branch: str) -> Path:
    path = root / ".worktrees" / branch
    _git(root, "worktree", "add", "-q", "-b", branch, str(path), "main")
    _commit(path, f"{branch}.txt", "local only\n")
    return path


def _registered(root: Path, path: Path) -> bool:
    return str(path.resolve()) in _git(root, "worktree", "list", "--porcelain")


def _has_branch(root: Path, branch: str) -> bool:
    probe = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    return probe.returncode == 0


def _husk(root: Path) -> Path:
    husk = root / ".worktrees" / "husk-a"
    husk.mkdir(parents=True)
    return husk


def _invoke(*args: str) -> tuple[int, str]:
    result = runner.invoke(doctor_module.app, ["workspaces", *args])
    return result.exit_code, result.stdout


def _verdict_of(payload: dict[str, object], path: Path) -> dict[str, object]:
    worktrees = payload["worktrees"]
    assert isinstance(worktrees, list)
    matches = [w for w in worktrees if Path(str(w["path"])).resolve() == path.resolve()]
    assert len(matches) == 1, payload
    return dict(matches[0])


# --- report (no --prune) -----------------------------------------------------


def test_report_lists_landed_worktree_exits_zero_and_writes_nothing(repo: Path) -> None:
    path, tip = _landed_worktree(repo)

    code, out = _invoke()

    assert code == 0, out
    assert "No workspace husks found." in out
    assert f".worktrees/{_LANDED} ({_LANDED}): landed" in out
    assert _PRUNE_HINT in out
    assert "1 landed, 0 kept" in out
    assert _registered(repo, path)
    assert _has_branch(repo, _LANDED)
    assert tip in _git(repo, "rev-parse", _LANDED)


def test_report_orders_groups_and_hides_excluded(repo: Path) -> None:
    _unlanded_worktree(repo, "wip-1")
    _landed_worktree(repo)

    code, out = _invoke()

    assert code == 0, out
    assert out.index(f"({_LANDED}): landed") < out.index("(wip-1): not_landed")
    assert "CONTENT_NOT_ON_PRIMARY" in out
    assert "MAIN_WORKTREE" not in out
    assert "1 landed, 1 kept" in out


def test_report_json_keeps_husk_keys_and_adds_worktrees(repo: Path) -> None:
    path, tip = _landed_worktree(repo)

    code, out = _invoke("--json")

    assert code == 0, out
    payload = json.loads(out)
    assert payload.keys() >= _HUSK_KEYS
    assert "pruned" not in payload
    assert payload["uninspected_processes"] == 0
    verdict = _verdict_of(payload, path)
    assert verdict["verdict"] == "landed"
    assert verdict["tip"] == tip
    assert verdict["removable"] is True
    main = _verdict_of(payload, repo)
    assert main["verdict"] == "excluded"  # excluded verdicts are shown in JSON


def test_dirty_landed_content_worktree_is_kept(repo: Path) -> None:
    path, _ = _landed_worktree(repo)
    (path / "notes.txt").write_text("unsaved\n", encoding="utf-8")

    code, out = _invoke("--prune")

    assert code == 0, out
    assert "not_landed" in out
    assert "UNCOMMITTED_CHANGES" in out
    assert "No landed worktrees to prune." in out
    assert _registered(repo, path)


def test_mission_worktree_is_only_reported(repo: Path) -> None:
    branch = "kitty/mission-foo-01ABCDEF-lane-a"
    path = repo / ".worktrees" / "foo-lane-a"
    _git(repo, "worktree", "add", "-q", "-b", branch, str(path), "main")

    code, out = _invoke("--prune")

    assert code == 0, out
    assert "mission_owned" in out
    assert "MISSION_LANE" in out
    assert _registered(repo, path)


def test_uninspected_processes_line(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _landed_worktree(repo)

    def probe(_paths: Sequence[Path]) -> ProcessProbeResult:
        return ProcessProbeResult(available=True, busy=frozenset(), detail="", uninspected=2)

    monkeypatch.setattr(process_probe, "processes_with_cwd_under", probe)

    code, out = _invoke()
    assert code == 0, out
    assert "2 process(es) could not be inspected for a working directory inside a worktree; they were skipped." in out

    code, out = _invoke("--json")
    assert code == 0, out
    assert json.loads(out)["uninspected_processes"] == 2


def test_unreadable_worktree_list_exits_one(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def unreadable(_root: Path, **_kwargs: object) -> landed_worktrees.WorktreeAssessment:
        return landed_worktrees.WorktreeAssessment(primary_ref=None, verdicts=(), error="the worktree list cannot be read: boom")

    monkeypatch.setattr(landed_worktrees, "assess_worktrees", unreadable)

    code, out = _invoke()
    assert code == 1
    assert "the worktree list cannot be read: boom" in out

    code, out = _invoke("--json")
    assert code == 1
    payload = json.loads(out)
    assert payload["worktrees_error"] == "the worktree list cannot be read: boom"
    assert payload.keys() >= _HUSK_KEYS


# --- --prune -----------------------------------------------------------------


def test_prune_removes_landed_worktree_and_prints_recreate(repo: Path) -> None:
    path, tip = _landed_worktree(repo)

    code, out = _invoke("--prune")

    assert code == 0, out
    assert f"Removed .worktrees/{_LANDED} (branch {_LANDED} at {tip[:12]})" in out
    assert f"recreate: git branch {_LANDED} {tip}" in out
    assert _PRUNE_HINT not in out
    assert not _registered(repo, path)
    assert not path.exists()
    assert not _has_branch(repo, _LANDED)


def test_prune_detached_worktree_prints_worktree_add_recreate(repo: Path) -> None:
    path, tip = _landed_worktree(repo)
    _git(path, "checkout", "-q", "--detach")
    _git(repo, "branch", "-q", "-D", _LANDED)

    code, out = _invoke("--prune")

    assert code == 0, out
    assert f"(detached @{tip[:12]}): landed" in out
    assert f"Removed .worktrees/{_LANDED} (detached at {tip[:12]})" in out
    assert f"recreate: git worktree add --detach {path.resolve()} {tip}" in out
    assert not _registered(repo, path)


def test_prune_json_payload(repo: Path) -> None:
    path, tip = _landed_worktree(repo)

    code, out = _invoke("--prune", "--json")

    assert code == 0, out
    payload = json.loads(out)
    assert payload.keys() >= _HUSK_KEYS
    assert payload["healthy"] is True
    pruned = payload["pruned"]
    assert len(pruned) == 1
    assert pruned[0]["removed"] is True
    assert pruned[0]["branch_deleted"] is True
    assert pruned[0]["recreate"] == f"git branch {_LANDED} {tip}"
    assert pruned[0]["refusal"] is None
    assert _verdict_of(payload, path)["verdict"] == "landed"


def test_fix_alone_leaves_landed_worktree(repo: Path) -> None:
    path, _ = _landed_worktree(repo)
    husk = _husk(repo)

    code, out = _invoke("--fix")

    assert code == 0, out
    assert "Removed husk:" in out
    assert not husk.exists()
    assert _registered(repo, path)
    assert _has_branch(repo, _LANDED)
    assert _PRUNE_HINT in out


def test_fix_json_alone_keeps_fix_keys_and_has_no_pruned(repo: Path) -> None:
    path, _ = _landed_worktree(repo)
    _husk(repo)

    code, out = _invoke("--fix", "--json")

    assert code == 0, out
    payload = json.loads(out)
    assert {"removed", "skipped_registered", "skipped_appeared_valid", "skipped_unsafe"} <= payload.keys()
    assert "pruned" not in payload
    assert _registered(repo, path)


def test_fix_and_prune_removes_husk_then_landed_worktree(repo: Path) -> None:
    path, _ = _landed_worktree(repo)
    husk = _husk(repo)

    code, out = _invoke("--fix", "--prune")

    assert code == 0, out
    assert out.index("Removed husk:") < out.index(f"Removed .worktrees/{_LANDED}")
    assert not husk.exists()
    assert not _registered(repo, path)


def test_guard_refusal_exits_one_and_lists_the_refusal(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, _ = _landed_worktree(repo)

    def refuse(worktree: Path, **_kwargs: object) -> None:
        raise DestructiveOpRefused(error_code="WORKTREE_DIRTY", remediation="commit first", worktree_path=worktree)

    monkeypatch.setattr(landed_worktrees, "guarded_worktree_remove", refuse)

    code, out = _invoke("--prune")
    assert code == 1
    assert f"Kept .worktrees/{_LANDED}" in out
    assert "refused (WORKTREE_DIRTY)" in out
    assert _registered(repo, path)

    code, out = _invoke("--prune", "--json")
    assert code == 1
    payload = json.loads(out)
    # Fold J: ``healthy`` follows the exit code, worktree section included.
    assert payload["healthy"] is False
    pruned = payload["pruned"]
    assert pruned[0]["removed"] is False
    assert pruned[0]["refusal"] == "WORKTREE_DIRTY"


def test_husks_keep_exit_one_with_landed_worktree(repo: Path) -> None:
    _landed_worktree(repo)
    _husk(repo)

    code, out = _invoke()

    assert code == 1
    assert "Remove unregistered husks with: spec-kitty doctor workspaces --fix" in out
    assert "1 landed, 0 kept" in out


def test_no_linked_worktrees(repo: Path) -> None:
    code, out = _invoke()
    assert code == 0, out
    assert "No linked worktrees to assess." in out
    assert "0 landed, 0 kept" in out


def test_kept_ref_and_branch_refusal_are_rendered(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, tip = _landed_worktree(repo)
    outcome = landed_worktrees.PruneOutcome(
        path=path,
        branch=_LANDED,
        tip=tip,
        removed=True,
        branch_deleted=False,
        kept_ref=f"refs/spec-kitty/discarded/{_LANDED}",
        recreate=f"git branch {_LANDED} {tip}",
        refusal="BRANCH_MOVED",
    )
    monkeypatch.setattr(landed_worktrees, "prune_landed", lambda *_a, **_k: [outcome])

    code, out = _invoke("--prune")

    assert code == 1
    assert f"tip kept at refs/spec-kitty/discarded/{_LANDED}" in out
    assert "branch kept: BRANCH_MOVED" in out


def test_outside_git_repository_keeps_husk_only_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.setattr(doctor_module, "locate_project_root", lambda *a, **k: plain)

    code, out = _invoke("--json")

    assert code == 0, out
    payload = json.loads(out)
    assert "worktrees" not in payload
    assert payload.keys() >= _HUSK_KEYS


@pytest.mark.parametrize(
    ("removed", "refusal", "expected"),
    [
        (False, landed_worktrees.WORKTREE_REMOVE_FAILED, "the removal could not run; inspect it, then `git worktree remove"),
        (True, landed_worktrees.BRANCH_DELETE_FAILED, f"the branch delete failed; content is on origin/main: `git branch -D {_LANDED}`"),
        (True, landed_worktrees.BRANCH_MOVED, f"the branch moved after it was assessed; inspect it with `git log {_LANDED}`"),
        (False, landed_worktrees.TIP_MOVED, f"run `{_PRUNE_HINT}` again"),
        (False, landed_worktrees.NOT_REGISTERED, f"run `{_PRUNE_HINT}` again"),
    ],
)
def test_could_not_run_refusals_print_a_hand_remedy(repo: Path, monkeypatch: pytest.MonkeyPatch, removed: bool, refusal: str, expected: str) -> None:
    path, tip = _landed_worktree(repo)
    outcome = landed_worktrees.PruneOutcome(
        path=path,
        branch=_LANDED,
        tip=tip,
        removed=removed,
        branch_deleted=False,
        kept_ref=None,
        recreate=f"git branch {_LANDED} {tip}",
        refusal=refusal,
    )
    monkeypatch.setattr(landed_worktrees, "prune_landed", lambda *_a, **_k: [outcome])

    code, out = _invoke("--prune")

    assert code == 1
    assert expected in out


def test_guard_refusal_prints_no_hand_remedy(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, tip = _landed_worktree(repo)
    outcome = landed_worktrees.PruneOutcome(
        path=path, branch=_LANDED, tip=tip, removed=False, branch_deleted=False, kept_ref=None, recreate="", refusal="WORKTREE_DIRTY"
    )
    monkeypatch.setattr(landed_worktrees, "prune_landed", lambda *_a, **_k: [outcome])

    code, out = _invoke("--prune")

    assert code == 1
    assert "refused (WORKTREE_DIRTY)" in out
    assert "could not run" not in out
    assert "again;" not in out
    assert f"run `{_PRUNE_HINT}` again" not in out
    assert "git worktree remove" not in out


# --- squad folds (#7173 pre-PR adversarial squad) -----------------------------


def _ignore_locally(root: Path, *patterns: str) -> None:
    """Ignore *patterns* in every worktree of *root* (``info/exclude`` lives in the common dir)."""
    common = Path(_git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").strip())
    (common / "info").mkdir(exist_ok=True)
    (common / "info" / "exclude").write_text("".join(f"{p}\n" for p in patterns), encoding="utf-8")


def test_ignored_files_the_removal_deletes_are_shown(repo: Path) -> None:
    """Fold H: the text report and JSON name the ignored files removed with the worktree."""
    _ignore_locally(repo, ".venv/", ".env", "*.log")
    path, _ = _landed_worktree(repo)
    (path / ".venv").mkdir()
    (path / ".venv" / "x").write_text("x", encoding="utf-8")
    (path / ".env").write_text("SECRET=1\n", encoding="utf-8")
    for index in range(5):
        (path / f"r{index}.log").write_text("log\n", encoding="utf-8")

    code, out = _invoke()

    assert code == 0, out
    assert "will also delete ignored: .env, .venv/, r0.log, r1.log, r2.log (+2 more)" in out

    code, out = _invoke("--json")
    verdict = _verdict_of(json.loads(out), path)
    assert verdict["ignored_count"] == 7
    assert verdict["ignored_paths"] == [".env", ".venv/", "r0.log", "r1.log", "r2.log"]


def test_unproven_only_for_the_process_probe_prints_the_manual_commands(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fold G: everything else is proven; tell the operator how to remove it by hand."""
    path, _ = _landed_worktree(repo)

    def missing(_paths: Sequence[Path]) -> ProcessProbeResult:
        return ProcessProbeResult(available=False, busy=frozenset(), detail="/proc is not available", uninspected=0)

    monkeypatch.setattr(process_probe, "processes_with_cwd_under", missing)

    code, out = _invoke("--prune")

    assert code == 0, out
    assert "PROCESS_PROOF_UNAVAILABLE" in out
    assert "only after checking nothing runs in it; content is on origin/main:" in out
    assert f"git worktree remove {path.resolve()}" in out
    assert "--force" not in out
    assert f"git branch -D {_LANDED}" in out
    assert _registered(repo, path)


def test_other_unproven_reasons_print_no_manual_commands(repo: Path) -> None:
    path = repo / ".worktrees" / "idle"
    _git(repo, "worktree", "add", "-q", "-b", "idle", str(path), "main")
    _git(repo, "reflog", "delete", "--rewrite", "refs/heads/idle@{0}")
    common = Path(_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").strip())
    (common / "logs" / "refs" / "heads" / "idle").unlink(missing_ok=True)

    code, out = _invoke()

    assert code == 0, out
    assert "REFLOG_MISSING" in out
    assert "git worktree remove" not in out


def test_a_project_root_inside_a_larger_repository_gets_the_worktree_section(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fold J: the project root of a monorepo subproject has no ``.git`` of its own."""
    project = repo / "services" / "api"
    project.mkdir(parents=True)
    path, _ = _landed_worktree(repo)
    monkeypatch.setattr(doctor_module, "locate_project_root", lambda *a, **k: project)

    code, out = _invoke("--json")

    assert code == 0, out
    payload = json.loads(out)
    assert _verdict_of(payload, path)["verdict"] == "landed"


def test_prune_help_names_what_removal_deletes() -> None:
    result = runner.invoke(doctor_module.app, ["workspaces", "--help"], env={"COLUMNS": "400"})

    assert result.exit_code == 0
    assert "ignored files (e.g. .venv/, .env) are deleted with the worktree" in result.stdout
    assert "Linux only" in result.stdout


def test_inside_work_tree_is_false_when_git_cannot_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands import _workspace_husk_doctor as husk_doctor

    def no_git(*_a: object, **_k: object) -> None:
        raise OSError("git not found")

    monkeypatch.setattr(husk_doctor.subprocess, "run", no_git)

    assert husk_doctor._inside_work_tree(tmp_path) is False
    (tmp_path / ".git").mkdir()
    assert husk_doctor._inside_work_tree(tmp_path) is True, "a .git entry answers without git"
