"""#7793 / #7297: the single_branch planning pin follows the planning commit across a rebase.

A single_branch Mission's implementation evidence window is ``planning_commit_sha..mission_branch``.
Before this fix, ``finalize-tasks --refresh-planning-commit --allow-orphaned`` (the remedy
``implement`` prints after a rebase) re-pointed the pin to the branch TIP, the window emptied, and
``move-task --to for_review`` refused ``SINGLE_BRANCH_IMPLEMENTATION_MISSING`` (#7793, observed on PR
#7778). The re-pin now follows the rebased copy of the recorded planning commit by patch-id, and
refuses with a named code when no such copy exists.

Two single_branch shapes are driven through the REAL CLI (the #5939 harness):

* ``commit_to_target`` -- the Mission commits to an unprotected topic branch (``mission_branch`` is
  the target). This is the exact #7793 shape.
* ``minted`` -- the default create mints ``kitty/mission-...`` off a protected ``main``. Before this
  fix the pin was ``main``'s tip (the target), so a rebase onto a newer ``main`` widened the window to
  ``main``'s new commits and ``--refresh-planning-commit`` refused ``PLANNING_REFRESH_FAIL_CLOSED``
  (#7297 item 2). The pin now sits on the mission branch, the line the window reads.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.integration.test_5939_single_branch_autowalk_guards import _commit_specs, _env, _git, _sk

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SHAPES = ("commit_to_target", "minted")


def _mission_env(tmp_path: Path) -> dict[str, str]:
    env = _env(tmp_path)
    # A real protected main: the minted shape needs the protection policy to mint the branch.
    env.pop("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", None)
    return env


def _write_planning(fd: Path) -> None:
    (fd / "spec.md").write_text("# Spec\n\n## Requirements\n\n- **FR-001**: things work.\n", encoding="utf-8")
    (fd / "plan.md").write_text("# Plan\n\nModules.\n", encoding="utf-8")
    (fd / "tasks").mkdir(exist_ok=True)
    (fd / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01: m1\n\n**Dependencies**: None\n\nRequirement refs: FR-001\n\n- [ ] T1 do m1\n",
        encoding="utf-8",
    )
    (fd / "tasks" / "WP01-m1.md").write_text(
        "---\nwork_package_id: WP01\ntitle: WP01 m1\ndependencies: []\nrequirement_refs: [FR-001]\n"
        "authoritative_surface: src/m1/\nowned_files:\n  - src/m1/**\ncreate_intent:\n  - src/m1/a.py\nsubtasks:\n  - T1\n---\n# WP01 m1\n\n- [ ] T1 do m1\n",
        encoding="utf-8",
    )


def _setup(tmp_path: Path, shape: str) -> tuple[Path, dict[str, str], str, Path]:
    """A single_branch Mission of one code WP (WP01 owns ``src/m1/**``), finalized and analysed."""
    env = _mission_env(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "QA")
    _git(repo, "config", "user.email", "qa@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    _sk(repo, env, "init", "--ai", "claude", "--non-interactive", check=True)
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "shared.py").write_text("A = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")

    create = ["agent", "mission", "create", "fx", "--mission-type", "software-dev", "--branch-strategy", "already-confirmed"]
    create += ["--friendly-name", "fx", "--purpose-tldr", "fx", "--purpose-context", "QA fixture.", "--json"]
    if shape == "commit_to_target":
        _git(repo, "checkout", "-q", "-b", "topic")
        create += ["--topology", "single_branch", "--target-branch", "topic"]
    else:
        create += ["--target-branch", "main"]
    slug = json.loads(_sk(repo, env, *create, check=True).stdout)["mission_slug"]
    fd = repo / "kitty-specs" / slug
    _write_planning(fd)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "planning")
    _sk(repo, env, "agent", "mission", "finalize-tasks", "--mission", slug, "--json", check=True)
    (tmp_path / "analysis.md").write_text("# Analysis\n\nNo blocking findings.\n", encoding="utf-8")
    _sk(repo, env, "agent", "mission", "record-analysis", "--mission", slug, "--input-file", str(tmp_path / "analysis.md"))
    _commit_specs(repo)
    return repo, env, slug, fd


def _lanes(fd: Path) -> dict[str, object]:
    data: dict[str, object] = json.loads((fd / "lanes.json").read_text(encoding="utf-8"))
    return data


def _submit_wp01(repo: Path, env: dict[str, str], slug: str) -> None:
    _sk(repo, env, "agent", "action", "implement", "WP01", "--mission", slug, "--agent", "alice", check=True)
    _commit_specs(repo)
    _sk(repo, env, "agent", "tasks", "mark-status", "T1", "--wp", "WP01", "--status", "done", "--mission", slug, check=True)
    _commit_specs(repo)


def _implement_reject_rebase(tmp_path: Path, repo: Path, env: dict[str, str], slug: str) -> str:
    """WP01 committed, sent to review, rejected, then the Mission branch rebased onto a newer main."""
    _submit_wp01(repo, env, slug)
    (repo / "src" / "m1").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "m1" / "a.py").write_text("X = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "WP01 implementation")
    _sk(repo, env, "agent", "tasks", "move-task", "WP01", "--to", "for_review", "--agent", "alice", "--mission", slug, check=True)
    _commit_specs(repo)
    feedback = tmp_path / "feedback.md"
    feedback.write_text("# Feedback\n\nRework the module.\n", encoding="utf-8")
    _sk(
        repo,
        env,
        "agent",
        "tasks",
        "move-task",
        "WP01",
        "--to",
        "planned",
        "--agent",
        "bob",
        "--force",
        "--review-feedback-file",
        str(feedback),
        "--mission",
        slug,
        check=True,
    )
    _commit_specs(repo)
    mission_branch = _git(repo, "branch", "--show-current")
    _git(repo, "checkout", "-q", "main")
    (repo / "upstream.txt").write_text("upstream\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "main moves on")
    upstream = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", mission_branch)
    _git(repo, "rebase", "-q", "main")
    return upstream


@pytest.mark.parametrize("shape", _SHAPES)
def test_repin_after_rebase_follows_planning_commit_and_keeps_the_work(tmp_path: Path, shape: str) -> None:
    """SC-001 (#7793): after the rebase the documented re-pin keeps WP01's commit inside the window."""
    repo, env, slug, fd = _setup(tmp_path, shape)
    recorded = str(_lanes(fd)["planning_commit_sha"])
    mission_branch = _git(repo, "branch", "--show-current")
    # I-1 (#7297 item 2): the pin sits on the line the window reads, never the target alone.
    assert _git(repo, "merge-base", "--is-ancestor", recorded, mission_branch) == ""
    upstream = _implement_reject_rebase(tmp_path, repo, env, slug)

    refresh = _sk(repo, env, "agent", "mission", "finalize-tasks", "--mission", slug, "--refresh-planning-commit", "--allow-orphaned", "--json")
    assert refresh.returncode == 0, f"re-pin must succeed\n{refresh.stdout}\n{refresh.stderr}"
    planning = json.loads(refresh.stdout)["planning_commit"]
    assert planning["action"] == "repinned", planning
    assert planning["matched_by"] == "patch_id", planning
    new_pin = str(_lanes(fd)["planning_commit_sha"])
    assert new_pin != _git(repo, "rev-parse", mission_branch), "the pin must not land on the tip"
    # SC-004: the window holds the Mission's work and none of main's newer commit.
    window = _git(repo, "diff", "--name-only", f"{new_pin}..{mission_branch}").splitlines()
    assert "src/m1/a.py" in window
    assert "upstream.txt" not in window, f"main's commit entered the evidence window: {window}"
    assert _git(repo, "merge-base", "--is-ancestor", upstream, new_pin) == ""
    _commit_specs(repo)

    _submit_wp01(repo, env, slug)
    move = _sk(repo, env, "agent", "tasks", "move-task", "WP01", "--to", "for_review", "--agent", "alice", "--mission", slug)
    assert move.returncode == 0, f"WP01's committed work must stay in the evidence window\n{move.stdout}\n{move.stderr}"


def test_minted_repin_refuses_when_the_planning_change_is_only_upstream(tmp_path: Path) -> None:
    """Review B2 (minted): the planning commit also landed on main, so the rebase dropped the Mission's copy.

    Pinning main's copy would count main's later commits as this Mission's work; the re-pin refuses.
    """
    repo, env, slug, fd = _setup(tmp_path, "minted")
    recorded = str(_lanes(fd)["planning_commit_sha"])
    mission_branch = _git(repo, "branch", "--show-current")
    _submit_wp01(repo, env, slug)
    (repo / "src" / "m1").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "m1" / "a.py").write_text("X = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "WP01 implementation")
    _git(repo, "checkout", "-q", "main")
    # The planning change lands upstream too: every Mission commit up to the pin, so the copies apply.
    _git(repo, "cherry-pick", f"main..{recorded}")
    (repo / "src" / "m1").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "m1" / "b.py").write_text("Y = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "later main work on an owned path")
    _git(repo, "checkout", "-q", mission_branch)
    _git(repo, "rebase", "-q", "main")
    before = (fd / "lanes.json").read_bytes()

    refresh = _sk(repo, env, "agent", "mission", "finalize-tasks", "--mission", slug, "--refresh-planning-commit", "--allow-orphaned", "--json")

    assert refresh.returncode != 0, refresh.stdout
    payload = json.loads(refresh.stdout)
    assert payload["error_code"] == "PLANNING_PIN_NO_PATCH_ID_MATCH", payload
    assert "only on the upstream" in payload["error"]
    assert (fd / "lanes.json").read_bytes() == before


def test_repin_with_no_patch_id_match_refuses_and_writes_nothing(tmp_path: Path) -> None:
    """SC-002: an orphaned pin whose change is on no commit of the branch refuses with a named code."""
    repo, env, slug, fd = _setup(tmp_path, "commit_to_target")
    _implement_reject_rebase(tmp_path, repo, env, slug)
    # A present, unreachable commit whose change no branch commit carries: the rebase rewrote it.
    mission_branch = _git(repo, "branch", "--show-current")
    _git(repo, "checkout", "-q", "-b", "scratch", "main")
    (repo / "rewritten.txt").write_text("a planning change no branch commit carries\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "rewritten planning")
    stray = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", mission_branch)
    _git(repo, "branch", "-q", "-D", "scratch")
    lanes = _lanes(fd)
    lanes["planning_commit_sha"] = stray
    (fd / "lanes.json").write_text(json.dumps(lanes, indent=2) + "\n", encoding="utf-8")
    _commit_specs(repo)
    before = (fd / "lanes.json").read_bytes()

    refresh = _sk(repo, env, "agent", "mission", "finalize-tasks", "--mission", slug, "--refresh-planning-commit", "--allow-orphaned", "--json")
    assert refresh.returncode != 0, refresh.stdout
    payload = json.loads(refresh.stdout)
    assert payload["error_code"] == "PLANNING_PIN_NO_PATCH_ID_MATCH", payload
    assert "evidence window" in payload["error"]
    assert (fd / "lanes.json").read_bytes() == before
