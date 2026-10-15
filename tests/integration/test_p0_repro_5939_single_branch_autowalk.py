"""OPEN P0 #5939 -- red-first reproduction (nightly ``p0_repro`` lane only).

On a ``single_branch`` mission, one unforced
``spec-kitty agent tasks move-task WP01 --to approved --agent bob --note lgtm`` on a
``planned`` work package that nobody claimed or implemented exits 0 and auto-walks
``planned -> claimed -> in_progress -> for_review -> in_review -> approved``, recording
the SAME actor as both implementer and reviewer and attaching an approved
``review_result`` -- with no implementation commit. ``accept`` then passes and
``consolidate`` prints ``All WPs have review approval``, marks the work packages
``done`` and exits 0. The mission is recorded as reviewed and delivered with none of
its work done.

Root cause: the ``for_review`` implementation-commit requirement runs only for owned
checkouts (``tasks_move_task.py``: ``if st.owned is not None: _mt_require_owned_implementation``),
plain ``single_branch`` has no lane worktree so the lane gates do not run, and the
consolidate approval bound (#5668) explicitly skips ``single_branch`` (a documented
residual). On lanes the same move warns ``APPROVAL_STAMP_MISSING`` and consolidate
refuses -- so this is a single_branch-only divergence.

Drives the REAL CLI end to end (host ``consolidate``), translated from the issue's
author-validated ``F-p2a-consolidate-combined.sh single_branch``.

Ideal, asserted here and RED until #5939 is fixed: ``consolidate`` must NOT land, at
exit 0, work packages that were auto-walked ``planned -> approved`` with no
implementation and no independent review -- it must refuse (as it does on lanes).
Today it exits 0 and marks them done. The fix PR removes the ``p0_repro`` marker.
See ADR 2026-07-17-1 and docs/development/reference/red-main-and-release-readiness.md.
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


@pytest.mark.p0_repro(issue=5939)
def test_single_branch_consolidate_must_not_land_autowalked_unimplemented_wps(tmp_path: Path) -> None:
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

    # Subtask checkboxes are ticked (as in the issue's reproduction) -- but NO implementation commit
    # is ever made, which is the point: ticked boxes are not shipped code.
    for subtask in ("T1", "T2"):
        _sk(repo, env, "agent", "tasks", "mark-status", subtask, "--status", "done", "--mission", slug)
    _commit_specs(repo)

    # The defect: a single unforced planned->approved move auto-walks the whole chain, same actor
    # as implementer and reviewer, with NO implementation commit.
    move_out: list[str] = []
    for wp in ("WP01", "WP02"):
        mv = _sk(repo, env, "agent", "tasks", "move-task", wp, "--to", "approved", "--agent", "bob", "--note", "lgtm", "--mission", slug)
        move_out.append(f"{wp} move rc={mv.returncode}: {(mv.stdout + mv.stderr).strip()[:300]}")
    _commit_specs(repo)

    _sk(repo, env, "agent", "acceptance-verdict", "--mission", slug, "--criterion", "FR-001", "--result", "pass", "--actor", "operator", "--evidence", "qa")
    _commit_specs(repo)
    _sk(repo, env, "accept", "--mission", slug, "--json", "--lenient")

    consolidated = _sk(repo, env, "consolidate", "--mission", slug)

    status = _sk(repo, env, "agent", "tasks", "status", "--mission", slug, "--json")
    try:
        lanes = {w["id"]: w["lane"] for w in json.loads(status.stdout)["work_packages"]}
    except Exception:
        lanes = {"<unparsed>": status.stdout[-400:]}

    # Fixture invariant: both work packages reached `approved` via the unforced auto-walk, so a
    # PASS means "consolidate correctly refused that state", not "the move never ran".
    assert all("rc=0" in line for line in move_out), f"fixture: the unforced planned->approved auto-walk did not run clean; moves={move_out}"

    # No implementation commit was ever made, and the "review" was the same actor that "implemented".
    # Ideal: consolidate refuses to land such work (as it does on lanes), so it must NOT exit 0.
    assert consolidated.returncode != 0, (
        "ideal: single_branch consolidate must NOT land, at exit 0, work packages auto-walked "
        "planned->approved with no implementation and no independent review; it must refuse (as on lanes). "
        f"got consolidate rc=0 and WP lanes={lanes} (mission delivered with no work done -- #5939). "
        f"moves={move_out}\nconsolidate stdout:\n{consolidated.stdout[-1500:]}"
    )
