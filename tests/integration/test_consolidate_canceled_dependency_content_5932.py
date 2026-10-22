"""Regression guard for #5932 -- fixed; runs per PR (no ``p0_repro`` marker).

``consolidate`` used to ship the code of a rejected-then-canceled dependency work
package when an approved dependent WP edited the SAME file. lane-a holds WP01
(rejected in review, then canceled with operator provenance); lane-b holds the
approved WP02, which depends on lane-a, fast-forwards it, and APPENDS one line to
WP01's ``src/alpha/mod.py``. Because the dependent touched the path, the
canceled-content axis treated the whole path as superseded, landed WP01's body on
``main``, deleted lane-a and exited 0 -- the reviewer's rejection silently undone
in shipped code (residual of #5569; the #5569 fix only covered the shape where the
dependent leaves the canceled file alone).

Fixed in #5932: content-level supersession keeps the canceled content live when an
append/partial rework preserves its lines, so ``consolidate`` refuses instead of
shipping it. Since #6309 the check is line attribution
(``line_attribution.LineAttribution``) rather than the #5932 all-lines subset test.

This drives the REAL CLI end to end (the full ``consolidate`` pipeline: lane
skipping, coord teardown, squash), because the defect did not reproduce at the
``MergeOutcomeVerifier.verify`` slice -- that gate refuses this fixture for an
unrelated closed-world reason. The scenario is a Python translation of the
issue's author-validated ``B-canceled-partial.sh`` ``touch`` arm (default squash
strategy).

Asserted here: the canceled WP01 content (``MARK_ALPHA``) must NOT be present on
``main`` after consolidate (consolidate refuses, or lands only WP02's own content).
See ADR 2026-07-17-1 and docs/development/reference/red-main-and-release-readiness.md.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CLI = [sys.executable, "-m", "specify_cli"]


def _env(home: Path) -> dict[str, str]:
    import os

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
    """Run the CLI. ``check=False`` (default) tolerates a non-zero exit (some
    lifecycle transitions legitimately warn/refuse) but always captures output;
    ``check=True`` is for steps whose success is a fixture invariant."""
    proc = subprocess.run([*_CLI, *args], cwd=repo, env=env, capture_output=True, text=True, timeout=400)
    if check and proc.returncode != 0:
        raise AssertionError(f"fixture setup step failed: spec-kitty {' '.join(args)}\nrc={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    return proc


def _lane_worktree(repo: Path, lane: str) -> Path:
    porcelain = _git(repo, "worktree", "list", "--porcelain")
    paths = [line.split(" ", 1)[1] for line in porcelain.splitlines() if line.startswith("worktree ")]
    matches = [p for p in paths if p.rstrip("/").endswith(f"-lane-{lane}")]
    assert matches, f"no lane-{lane} worktree found in: {paths}"
    return Path(matches[0])


def test_consolidate_must_not_ship_rejected_then_canceled_dependency_content(tmp_path: Path) -> None:
    env = _env(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "QA")
    _git(repo, "config", "user.email", "qa@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")

    _sk(repo, env, "init", "--ai", "claude", "--non-interactive", check=True)
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "shared.py").write_text("X = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")

    created = _sk(
        repo,
        env,
        "agent",
        "mission",
        "create",
        "gateqa",
        "--mission-type",
        "software-dev",
        "--topology",
        "lanes",
        "--branch-strategy",
        "already-confirmed",
        "--target-branch",
        "main",
        "--friendly-name",
        "Gate QA",
        "--purpose-tldr",
        "gate QA",
        "--purpose-context",
        "Isolated QA fixture.",
        "--json",
        check=True,
    )
    slug = json.loads(created.stdout)["mission_slug"]
    fd = repo / "kitty-specs" / slug

    (fd / "spec.md").write_text("# Spec\n\n## Requirements\n\n- **FR-001**: alpha works.\n- **FR-002**: beta works.\n", encoding="utf-8")
    (fd / "plan.md").write_text("# Plan\n\nTwo modules.\n", encoding="utf-8")
    (fd / "tasks").mkdir(exist_ok=True)
    (fd / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01: alpha\n\n**Dependencies**: None\n\nRequirement refs: FR-001\n\n"
        "## Work Package WP02: beta\n\n**Dependencies**: WP01\n\nRequirement refs: FR-002\n",
        encoding="utf-8",
    )
    (fd / "tasks" / "WP01-alpha.md").write_text(
        "---\nwork_package_id: WP01\ntitle: alpha\ndependencies: []\nrequirement_refs: [FR-001]\n"
        "authoritative_surface: src/alpha/\nowned_files:\n  - src/alpha/**\nsubtasks:\n  - T001\n---\n# WP01\n\n- [ ] T001 alpha\n",
        encoding="utf-8",
    )
    (fd / "tasks" / "WP02-beta.md").write_text(
        "---\nwork_package_id: WP02\ntitle: beta\ndependencies: [WP01]\nrequirement_refs: [FR-002]\n"
        "authoritative_surface: src/beta/\nowned_files:\n  - src/beta/**\nsubtasks:\n  - T002\n---\n# WP02\n\n- [ ] T002 beta\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "planning")
    _sk(repo, env, "agent", "mission", "finalize-tasks", "--mission", slug, "--json", check=True)
    (tmp_path / "analysis.md").write_text("# Analysis\n\nNo blocking findings.\n", encoding="utf-8")
    _sk(repo, env, "agent", "mission", "record-analysis", "--mission", slug, "--input-file", str(tmp_path / "analysis.md"))

    def review_ref(wp: str) -> str:
        return json.dumps({"verdict": "approved", "summary": "ok", "reviewer": "rev1", "reference": f"review/{wp}"})

    def work(wp: str, lane: str, mod: str, subtask: str) -> None:
        _sk(repo, env, "implement", wp, "--mission", slug)
        wt = _lane_worktree(repo, lane)
        (wt / "src" / mod).mkdir(parents=True, exist_ok=True)
        (wt / "src" / mod / "mod.py").write_text(f'def f():\n    return 1\n\nMARK_{mod.upper()} = "{mod} code"\n', encoding="utf-8")
        _git(wt, "add", f"src/{mod}")
        _git(wt, "commit", "-qm", f"{wp}: {mod} module")
        _sk(repo, env, "agent", "tasks", "mark-status", subtask, "--status", "done", "--mission", slug)
        _sk(
            repo,
            env,
            "agent",
            "status",
            "emit",
            wp,
            "--to",
            "for_review",
            "--actor",
            "claude",
            "--mission",
            slug,
            "--subtasks-complete",
            "--implementation-evidence-present",
        )

    def approve(wp: str) -> None:
        _sk(repo, env, "agent", "action", "review", wp, "--mission", slug, "--agent", "claude")
        _sk(
            repo,
            env,
            "agent",
            "status",
            "emit",
            wp,
            "--to",
            "approved",
            "--actor",
            "rev1",
            "--mission",
            slug,
            "--review-ref",
            f"review/{wp}",
            "--review-result-json",
            review_ref(wp),
        )

    work("WP01", "a", "alpha", "T001")
    approve("WP01")
    work("WP02", "b", "beta", "T002")

    (tmp_path / "feedback.md").write_text("# Review\n\n**Issue 1**: alpha is wrong; do not ship it.\n", encoding="utf-8")
    _sk(
        repo,
        env,
        "agent",
        "tasks",
        "move-task",
        "WP01",
        "--to",
        "planned",
        "--mission",
        slug,
        "--review-feedback-file",
        str(tmp_path / "feedback.md"),
        "--reviewer",
        "rev1",
        "--json",
    )
    _sk(repo, env, "agent", "tasks", "move-task", "WP01", "--to", "canceled", "--mission", slug, "--note", "rejected in review; dropping alpha", "--json")

    # WP02 handed back for rework; its implementer edits alpha in lane-b (append only).
    _sk(
        repo,
        env,
        "agent",
        "tasks",
        "move-task",
        "WP02",
        "--to",
        "planned",
        "--mission",
        slug,
        "--review-feedback-file",
        str(tmp_path / "feedback.md"),
        "--reviewer",
        "rev1",
        "--json",
    )
    wt_b = _lane_worktree(repo, "b")
    with (wt_b / "src" / "alpha" / "mod.py").open("a", encoding="utf-8") as fh:
        fh.write("EXTRA = 2\n")
    _git(wt_b, "add", "-A")
    _git(wt_b, "commit", "-qm", "WP02: adjust alpha (touch)")
    _sk(repo, env, "agent", "action", "implement", "WP02", "--mission", slug, "--agent", "claude")
    _sk(repo, env, "agent", "tasks", "mark-status", "T002", "--status", "done", "--mission", slug)
    _sk(
        repo,
        env,
        "agent",
        "status",
        "emit",
        "WP02",
        "--to",
        "for_review",
        "--actor",
        "claude",
        "--mission",
        slug,
        "--subtasks-complete",
        "--implementation-evidence-present",
    )
    approve("WP02")

    # Untracked review locks would make consolidate refuse on a dirty worktree.
    for lock in repo.glob(".worktrees/*/.spec-kitty"):
        subprocess.run(["rm", "-rf", str(lock)], check=True)

    consolidated = _sk(repo, env, "consolidate", "--mission", slug, "--strategy", "squash")

    # Fixture invariant: the scenario reached consolidate (not a setup abort upstream).
    assert "src/alpha" in _git(repo, "ls-tree", "-r", "--name-only", "main") or consolidated.returncode != 0, (
        f"fixture did not reach a consolidatable state; consolidate rc={consolidated.returncode}\n"
        f"stdout:\n{consolidated.stdout[-2000:]}\nstderr:\n{consolidated.stderr[-2000:]}"
    )

    shipped = subprocess.run(["git", "show", "main:src/alpha/mod.py"], cwd=repo, capture_output=True, text=True)
    shipped_body = shipped.stdout if shipped.returncode == 0 else ""

    assert "MARK_ALPHA" not in shipped_body, (
        "ideal: consolidate must NOT ship the rejected-then-canceled WP01's content when the approved "
        f"dependent WP02 only appends to its file; got MARK_ALPHA on main at consolidate rc={consolidated.returncode} "
        f"(canceled code shipped, reviewer's rejection undone -- #5932).\nmain:src/alpha/mod.py=\n{shipped_body}"
    )
