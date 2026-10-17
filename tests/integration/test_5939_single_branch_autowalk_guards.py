"""#5939 single_branch autowalk — the two-layer defense-in-depth net (per-PR guards).

Background (#5939, P0). On a ``single_branch`` mission, one unforced
``spec-kitty agent tasks move-task WP01 --to approved --agent bob --note lgtm`` on a
``planned`` work package that nobody claimed or implemented used to exit 0 and auto-walk
``planned -> claimed -> in_progress -> for_review -> in_review -> approved``, recording the
SAME actor as both implementer and reviewer and attaching an approved ``review_result`` --
with no implementation commit. ``accept`` then passed and ``consolidate`` marked the work
packages ``done`` at exit 0: a mission recorded as reviewed and delivered with none of its
work done. On ``lanes`` the same move warns ``APPROVAL_STAMP_MISSING`` and consolidate
refuses; plain ``single_branch`` had no backstop.

The fix is a two-layer net, each layer guarded here (these are per-PR regression guards,
not the nightly ``p0_repro`` lane -- the ``p0_repro`` marker is intentionally dropped):

* **Layer 2 (move gate)** -- :func:`test_move_gate_refuses_autowalk_without_implementation`:
  the unforced ``planned -> approved`` move on single_branch with NO implementation commit
  REFUSES at the move (rc != 0, names the missing implementation). Defense in depth.
* **Layer 1 (consolidate backstop, primary)** --
  :func:`test_consolidate_backstop_refuses_hollow_approved_wps`: a hollow-approved
  single_branch WP constructed so it BYPASSES the move gate (forced transitions) is still
  refused by ``consolidate`` (rc != 0). This proves the backstop independently of the move
  gate -- it is the P0's core.
* **Positive control** -- :func:`test_real_single_branch_work_moves_and_consolidates_clean`:
  a single_branch WP WITH a real implementation commit and a proper independent review moves
  AND consolidates clean (rc == 0, lands done). Guards against over-refusal.

Drives the REAL CLI end to end (host ``consolidate``), translated from the issue's
author-validated ``F-p2a-consolidate-combined.sh single_branch``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CLI = [sys.executable, "-m", "specify_cli"]


def _env(home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        HOME=str(home / "home"),
        XDG_CONFIG_HOME=str(home / "xc"),
        XDG_CACHE_HOME=str(home / "xcache"),
        XDG_DATA_HOME=str(home / "xd"),
        SPEC_KITTY_NO_UPGRADE_CHECK="1",
        SPEC_KITTY_WORKTREE_REMOVAL_DELAY="0",
        SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS="1",
        SPEC_KITTY_ENABLE_SAAS_SYNC="0",
    )
    for key in ("home", "xc", "xcache", "xd"):
        (home / key).mkdir(parents=True, exist_ok=True)
    return env


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _sk(repo: Path, env: dict[str, str], *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run([*_CLI, *args], cwd=repo, env=env, capture_output=True, text=True, timeout=400)
    if check and proc.returncode != 0:
        raise AssertionError(f"fixture setup step failed: spec-kitty {' '.join(args)}\nrc={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    return proc


def _commit_specs(repo: Path) -> None:
    if _git(repo, "status", "--porcelain", "--", "kitty-specs"):
        _git(repo, "add", "-A", "kitty-specs")
        _git(repo, "commit", "-qm", "status residue")


def _setup_mission(tmp_path: Path) -> tuple[Path, dict[str, str], str, Path]:
    """A protected single_branch mission with two code WPs (WP01 owns src/m1/**, WP02 src/m2/**)."""
    env = _env(tmp_path)
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

    created = _sk(
        repo,
        env,
        "agent",
        "mission",
        "create",
        "fx",
        "--mission-type",
        "software-dev",
        "--topology",
        "single_branch",
        "--branch-strategy",
        "already-confirmed",
        "--target-branch",
        "main",
        "--friendly-name",
        "fx",
        "--purpose-tldr",
        "fx",
        "--purpose-context",
        "QA fixture.",
        "--json",
        check=True,
    )
    slug = json.loads(created.stdout)["mission_slug"]
    fd = repo / "kitty-specs" / slug

    (fd / "spec.md").write_text("# Spec\n\n## Requirements\n\n- **FR-001**: things work.\n", encoding="utf-8")
    (fd / "plan.md").write_text("# Plan\n\nModules.\n", encoding="utf-8")
    (fd / "tasks").mkdir(exist_ok=True)
    (fd / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01: m1\n\n**Dependencies**: None\n\nRequirement refs: FR-001\n\n- [ ] T1 do m1\n\n"
        "## Work Package WP02: m2\n\n**Dependencies**: None\n\nRequirement refs: FR-001\n\n- [ ] T2 do m2\n",
        encoding="utf-8",
    )
    (fd / "tasks" / "WP01-m1.md").write_text(
        "---\nwork_package_id: WP01\ntitle: WP01 m1\ndependencies: []\nrequirement_refs: [FR-001]\n"
        "authoritative_surface: src/m1/\nowned_files:\n  - src/m1/**\nsubtasks:\n  - T1\n---\n# WP01 m1\n\n- [ ] T1 do m1\n",
        encoding="utf-8",
    )
    (fd / "tasks" / "WP02-m2.md").write_text(
        "---\nwork_package_id: WP02\ntitle: WP02 m2\ndependencies: []\nrequirement_refs: [FR-001]\n"
        "authoritative_surface: src/m2/\nowned_files:\n  - src/m2/**\nsubtasks:\n  - T2\n---\n# WP02 m2\n\n- [ ] T2 do m2\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "planning")
    _sk(repo, env, "agent", "mission", "finalize-tasks", "--mission", slug, "--json", check=True)
    (tmp_path / "analysis.md").write_text("# Analysis\n\nNo blocking findings.\n", encoding="utf-8")
    _sk(repo, env, "agent", "mission", "record-analysis", "--mission", slug, "--input-file", str(tmp_path / "analysis.md"))
    _commit_specs(repo)
    return repo, env, slug, fd


def _lanes(status: subprocess.CompletedProcess[str]) -> dict[str, str]:
    try:
        return {w["id"]: w["lane"] for w in json.loads(status.stdout)["work_packages"]}
    except Exception:
        return {"<unparsed>": status.stdout[-400:]}


def test_move_gate_refuses_autowalk_without_implementation(tmp_path: Path) -> None:
    """Layer 2: an unforced planned->approved move with no implementation commit refuses at the move."""
    repo, env, slug, _fd = _setup_mission(tmp_path)

    # Ticked subtask checkboxes are not shipped code; no implementation commit is ever made.
    for subtask in ("T1", "T2"):
        _sk(repo, env, "agent", "tasks", "mark-status", subtask, "--status", "done", "--mission", slug)
    _commit_specs(repo)

    mv = _sk(repo, env, "agent", "tasks", "move-task", "WP01", "--to", "approved", "--agent", "bob", "--note", "lgtm", "--mission", slug)
    combined = (mv.stdout + mv.stderr).lower()

    assert mv.returncode != 0, (
        "Layer 2: the unforced planned->approved auto-walk of a single_branch WP with no implementation "
        f"commit must REFUSE at the move. got rc=0\nstdout:\n{mv.stdout}\nstderr:\n{mv.stderr}"
    )
    assert "implementation" in combined, f"the refusal must name the missing implementation; got:\n{mv.stdout}\n{mv.stderr}"

    status = _sk(repo, env, "agent", "tasks", "status", "--mission", slug, "--json")
    lanes = _lanes(status)
    assert lanes.get("WP01") != "approved", f"the refused move must not have landed WP01 in approved; lanes={lanes}"


def test_consolidate_backstop_refuses_hollow_approved_wps(tmp_path: Path) -> None:
    """Layer 1: a hollow-approved single_branch WP that bypassed the move gate (force) is still refused by consolidate."""
    repo, env, slug, _fd = _setup_mission(tmp_path)

    for subtask in ("T1", "T2"):
        _sk(repo, env, "agent", "tasks", "mark-status", subtask, "--status", "done", "--mission", slug)
    _commit_specs(repo)

    # Reach `approved` WITHOUT any implementation commit, past the move gate: the walk into
    # in_progress sits below the review threshold (Layer 2 does not fire), and `--force` on the
    # approval bypasses Layer 2. This proves the consolidate backstop independently of the move gate.
    move_out: list[str] = []
    for wp in ("WP01", "WP02"):
        _sk(repo, env, "agent", "tasks", "move-task", wp, "--to", "in_progress", "--agent", "bob", "--note", "wip", "--mission", slug, check=True)
        mv = _sk(repo, env, "agent", "tasks", "move-task", wp, "--to", "approved", "--agent", "bob", "--note", "lgtm", "--force", "--mission", slug)
        move_out.append(f"{wp} approve rc={mv.returncode}: {(mv.stdout + mv.stderr).strip()[:300]}")
    _commit_specs(repo)

    status = _sk(repo, env, "agent", "tasks", "status", "--mission", slug, "--json")
    lanes = _lanes(status)
    # Fixture invariant: the forced path actually reached `approved` (so a PASS below means
    # "consolidate refused that hollow state", not "the WPs never got there").
    assert all(lanes.get(wp) == "approved" for wp in ("WP01", "WP02")), f"fixture: the forced hollow approval did not land; lanes={lanes}; moves={move_out}"

    _sk(repo, env, "agent", "acceptance-verdict", "--mission", slug, "--criterion", "FR-001", "--result", "pass", "--actor", "operator", "--evidence", "qa")
    _commit_specs(repo)
    _sk(repo, env, "accept", "--mission", slug, "--json", "--lenient")

    consolidated = _sk(repo, env, "consolidate", "--mission", slug)
    assert consolidated.returncode != 0, (
        "Layer 1: single_branch consolidate must REFUSE to land, at exit 0, work packages approved with no "
        f"implementation and no independent review. got rc=0; lanes={lanes}\nconsolidate stdout:\n{consolidated.stdout[-1500:]}"
    )


def test_real_single_branch_work_moves_and_consolidates_clean(tmp_path: Path) -> None:
    """Positive control: a single_branch WP with a real implementation commit and an independent review ships clean."""
    repo, env, slug, _fd = _setup_mission(tmp_path)

    move_out: list[str] = []
    for wp, module in (("WP01", "m1"), ("WP02", "m2")):
        # Implementer alice claims and implements (autowalk planned->in_progress is below the review threshold).
        _sk(repo, env, "agent", "tasks", "move-task", wp, "--to", "in_progress", "--agent", "alice", "--note", "claim", "--mission", slug, check=True)
        src_dir = repo / "src" / module
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "real.py").write_text(f"VALUE = {wp!r}\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", f"feat({wp}): implement {module}")
        _sk(repo, env, "agent", "tasks", "mark-status", "T1" if wp == "WP01" else "T2", "--status", "done", "--mission", slug)
        _commit_specs(repo)
        # Independent reviewer bob approves. The WP is assigned to its implementer alice, so an
        # independent reviewer taking it over uses --force (the documented cross-agent override);
        # implementer (alice) != approving actor (bob) keeps the review independent.
        mv = _sk(repo, env, "agent", "tasks", "move-task", wp, "--to", "approved", "--agent", "bob", "--note", "lgtm", "--force", "--mission", slug)
        move_out.append(f"{wp} approve rc={mv.returncode}: {(mv.stdout + mv.stderr).strip()[:300]}")
    _commit_specs(repo)

    assert all("rc=0" in line for line in move_out), f"legit single_branch work must move clean (no over-refusal); moves={move_out}"

    _sk(repo, env, "agent", "acceptance-verdict", "--mission", slug, "--criterion", "FR-001", "--result", "pass", "--actor", "operator", "--evidence", "qa")
    _commit_specs(repo)
    _sk(repo, env, "accept", "--mission", slug, "--json", "--lenient")

    consolidated = _sk(repo, env, "consolidate", "--mission", slug)
    status = _sk(repo, env, "agent", "tasks", "status", "--mission", slug, "--json")
    lanes = _lanes(status)
    assert consolidated.returncode == 0, (
        "positive control: a single_branch WP with a real implementation commit and an independent review must "
        f"consolidate clean (no over-refusal). got rc={consolidated.returncode}; lanes={lanes}\n"
        f"moves={move_out}\nconsolidate stdout:\n{consolidated.stdout[-1500:]}\nstderr:\n{consolidated.stderr[-800:]}"
    )
    assert all(lanes.get(wp) == "done" for wp in ("WP01", "WP02")), f"both WPs must land done; lanes={lanes}"
