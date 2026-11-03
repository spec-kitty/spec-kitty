"""#7106: claiming a work package must not stale the mission's recorded analysis.

The analysis-freshness gate (`check_analysis_report_current`) fingerprints the
mission's material closure. A claim writes runtime bookkeeping into two files the
closure used to hash whole -- the workspace-provenance triple in the claimed WP
prompt and the VCS lock in `meta.json` -- so the first claim invalidated the gate
that guards the claim, and every later claim (and every rework re-claim, whose
review artifacts live under `tasks/<wp>/`) was refused with
`analysis_report_required` until an operator re-recorded an analysis nobody re-ran.

These tests drive the real CLI end to end on a finalized `lanes` mission: record
the analysis through `record-analysis --report-only` (the material-manifest path
the issue uses), claim WP01 through `agent action implement` (which allocates a
real lane worktree and stamps the provenance), then claim WP02. The positive
controls assert the opposite direction on the same fixture: a real planning edit,
and a rework cycle, still gate implementation.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(1200)]

_CLI = [sys.executable, "-m", "specify_cli"]

#: A valid ``analysis-findings/v1`` carrier with no findings -> verdict ``ready``.
_ANALYSIS_BODY = (
    "---\n"
    "schema: analysis-findings/v1\n"
    "findings: []\n"
    "counts: {critical: 0, high: 0, medium: 0, low: 0, info: 0}\n"
    "verdict_hint: ready\n"
    "---\n"
    "# Analysis\n\n"
    "No blocking findings.\n"
)


@dataclass(frozen=True)
class _Mission:
    repo: Path
    env: dict[str, str]
    slug: str
    feature_dir: Path

    @property
    def tasks_dir(self) -> Path:
        return self.feature_dir / "tasks"

    def wp_path(self, prefix: str) -> Path:
        matches = sorted(self.tasks_dir.glob(f"{prefix}-*.md"))
        assert len(matches) == 1, f"expected exactly one {prefix} prompt, found {matches}"
        return matches[0]


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


def _sk(mission: _Mission | tuple[Path, dict[str, str]], *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    repo, env = (mission.repo, mission.env) if isinstance(mission, _Mission) else mission
    proc = subprocess.run([*_CLI, *args], cwd=repo, env=env, capture_output=True, text=True, timeout=400)
    if check and proc.returncode != 0:
        raise AssertionError(f"fixture step failed: spec-kitty {' '.join(args)}\nrc={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    return proc


def _out(proc: subprocess.CompletedProcess[str]) -> str:
    """stdout+stderr with whitespace runs collapsed (the console wraps long lines)."""
    return " ".join((proc.stdout + proc.stderr).split())


def _commit_all(repo: Path, message: str) -> None:
    if _git(repo, "status", "--porcelain"):
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", message)


def _wp_file(wp: str, subtask: str, surface: str, owned: str) -> str:
    return (
        f"---\nwork_package_id: {wp}\ntitle: {wp}\ndependencies: []\nrequirement_refs: [FR-001]\n"
        f"authoritative_surface: {surface}\nowned_files:\n  - {owned}\nsubtasks:\n  - {subtask}\n"
        f"---\n# {wp}\n\n- [ ] {subtask} do\n"
    )


def _mission(tmp_path: Path) -> _Mission:
    """A finalized two-WP `lanes` mission with one recorded, current analysis.

    WP01 owns ``src/m1/**`` and WP02 owns ``tools/**``, so each claims its own
    lane and each claim allocates a fresh worktree -- the write that used to stale
    the report.
    """
    env = _env(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "QA")
    _git(repo, "config", "user.email", "qa@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    _sk((repo, env), "init", "--ai", "claude", "--non-interactive", check=True)
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "shared.py").write_text("A = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")

    created = _sk(
        (repo, env),
        *("agent", "mission", "create", "fx", "--mission-type", "software-dev", "--topology", "lanes"),
        *("--branch-strategy", "already-confirmed", "--target-branch", "main", "--friendly-name", "fx"),
        *("--purpose-tldr", "fx", "--purpose-context", "Freshness fixture.", "--json"),
        check=True,
    )
    slug = json.loads(created.stdout)["mission_slug"]
    feature_dir = repo / "kitty-specs" / slug
    (feature_dir / "spec.md").write_text("# Spec\n\n## Requirements\n\n- **FR-001**: things work.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n\nModules.\n", encoding="utf-8")
    (feature_dir / "tasks").mkdir(exist_ok=True)
    sections = "".join(
        f"## Work Package {wp}: {wp}\n\n**Dependencies**: None\n\nRequirement refs: FR-001\n\n- [ ] {subtask} do\n\n"
        for wp, subtask in (("WP01", "T1"), ("WP02", "T2"))
    )
    (feature_dir / "tasks.md").write_text(f"# Tasks\n\n{sections}", encoding="utf-8")
    (feature_dir / "tasks" / "WP01-m1.md").write_text(_wp_file("WP01", "T1", "src/m1/", "src/m1/**"), encoding="utf-8")
    (feature_dir / "tasks" / "WP02-tools.md").write_text(_wp_file("WP02", "T2", "tools/", "tools/**"), encoding="utf-8")
    _commit_all(repo, "planning")
    _sk((repo, env), "agent", "mission", "finalize-tasks", "--mission", slug, "--json", check=True)

    body = tmp_path / "analysis.md"
    body.write_text(_ANALYSIS_BODY, encoding="utf-8")
    recorded = _sk(
        (repo, env),
        "agent",
        "mission",
        "record-analysis",
        "--mission",
        slug,
        "--input-file",
        str(body),
        "--report-only",
        "--json",
        check=True,
    )
    assert json.loads(recorded.stdout)["success"], recorded.stdout
    _commit_all(repo, "record analysis")
    return _Mission(repo, env, slug, feature_dir)


def _wp_lane(mission: _Mission, wp: str) -> str | None:
    status = _sk(mission, "agent", "tasks", "status", "--mission", mission.slug, "--json")
    try:
        return {row["id"]: row["lane"] for row in json.loads(status.stdout)["work_packages"]}.get(wp)
    except (ValueError, KeyError, TypeError):
        return None


def _lane_worktree(mission: _Mission, wp: str) -> Path:
    manifest = json.loads((mission.feature_dir / "lanes.json").read_text(encoding="utf-8"))
    lane_id = next(lane["lane_id"] for lane in manifest["lanes"] if wp in lane["wp_ids"])
    return mission.repo / ".worktrees" / f"{mission.slug}-{lane_id}"


def test_claiming_a_work_package_keeps_the_analysis_current(tmp_path: Path) -> None:
    """#7106: WP02 claims at exit 0 after WP01's claim, with no re-record."""
    mission = _mission(tmp_path)
    report = mission.feature_dir / "analysis-report.md"
    report_before = report.read_bytes()
    wp01 = mission.wp_path("WP01")
    meta = mission.feature_dir / "meta.json"
    assert "vcs" not in json.loads(meta.read_text(encoding="utf-8"))

    first = _sk(mission, "agent", "action", "implement", "WP01", "--agent", "alice", "--mission", mission.slug)
    assert first.returncode == 0, _out(first)[-3000:]
    assert _wp_lane(mission, "WP01") == "in_progress"
    # Fixture guard: the claim really wrote both runtime surfaces, so the second
    # claim is a meaningful test rather than a no-op.
    assert _lane_worktree(mission, "WP01").is_dir()
    claim_stamp = wp01.read_text(encoding="utf-8")
    assert "base_branch:" in claim_stamp and "base_commit:" in claim_stamp and "created_at:" in claim_stamp
    assert json.loads(meta.read_text(encoding="utf-8"))["vcs"] == "git"

    second = _sk(mission, "agent", "action", "implement", "WP02", "--agent", "alice", "--mission", mission.slug)

    assert second.returncode == 0, _out(second)[-3000:]
    assert "analysis_report_required" not in _out(second)
    assert _wp_lane(mission, "WP02") == "in_progress"
    # The recorded report itself is untouched -- nothing re-recorded it.
    assert report.read_bytes() == report_before


def test_planning_edit_after_the_analysis_still_refuses_the_next_claim(tmp_path: Path) -> None:
    """Positive control (#7106): a substantive planning edit still gates implementation."""
    mission = _mission(tmp_path)
    first = _sk(mission, "agent", "action", "implement", "WP01", "--agent", "alice", "--mission", mission.slug)
    assert first.returncode == 0, _out(first)[-3000:]

    wp01 = mission.wp_path("WP01")
    edited = wp01.read_text(encoding="utf-8").replace("subtasks:\n- T1\n", "subtasks:\n- T1\n- T1b\n")
    assert edited != wp01.read_text(encoding="utf-8")
    wp01.write_text(edited, encoding="utf-8")
    _commit_all(mission.repo, "planning edit after analysis")

    second = _sk(mission, "agent", "action", "implement", "WP02", "--agent", "alice", "--mission", mission.slug)

    assert second.returncode != 0, f"a planning edit must still refuse the claim:\n{_out(second)[-3000:]}"
    assert "analysis_report_required" in _out(second)
    assert "stale_analysis_report" in _out(second)
    assert f"tasks/{wp01.name}" in _out(second)
    assert _wp_lane(mission, "WP02") != "in_progress"


def test_rework_reclaim_does_not_require_re_recording(tmp_path: Path) -> None:
    """#7106 rework path: a rejection's per-WP artifacts must not stale the analysis."""
    mission = _mission(tmp_path)
    report = mission.feature_dir / "analysis-report.md"
    report_before = report.read_bytes()
    first = _sk(mission, "agent", "action", "implement", "WP01", "--agent", "alice", "--mission", mission.slug)
    assert first.returncode == 0, _out(first)[-3000:]
    _sk(mission, "agent", "tasks", "mark-status", "T1", "--status", "done", "--mission", mission.slug, check=True)

    review_ready = _sk(
        mission,
        "agent",
        "tasks",
        "move-task",
        "WP01",
        "--to",
        "for_review",
        "--agent",
        "alice",
        "--note",
        "done",
        "--force",
        "--mission",
        mission.slug,
    )
    assert review_ready.returncode == 0, _out(review_ready)[-3000:]
    review = _sk(mission, "agent", "action", "review", "WP01", "--agent", "bob", "--mission", mission.slug)
    assert review.returncode == 0, _out(review)[-3000:]

    feedback = tmp_path / "feedback.md"
    feedback.write_text("Please adjust the response shape.\n", encoding="utf-8")
    rejected = _sk(
        mission,
        "agent",
        "tasks",
        "move-task",
        "WP01",
        "--to",
        "planned",
        "--agent",
        "bob",
        "--note",
        "changes requested",
        "--review-feedback-file",
        str(feedback),
        "--mission",
        mission.slug,
    )
    assert rejected.returncode == 0, _out(rejected)[-3000:]
    assert _wp_lane(mission, "WP01") == "planned"
    # Fixture guard: the review cycle really wrote its per-WP artifacts.
    generated = _wp_artifacts(mission)
    assert any(name.startswith("review-cycle-") for name in generated), f"no review-cycle artifact was written: {generated}"

    reclaim = _sk(mission, "agent", "action", "implement", "WP01", "--agent", "alice", "--mission", mission.slug)

    assert reclaim.returncode == 0, _out(reclaim)[-3000:]
    assert "analysis_report_required" not in _out(reclaim)
    assert _wp_lane(mission, "WP01") == "in_progress"
    assert report.read_bytes() == report_before


def _wp_artifacts(mission: _Mission) -> list[str]:
    """Every generated per-WP artifact file name under ``tasks/<wp>/``."""
    names: list[str] = []
    for sub in mission.tasks_dir.iterdir():
        if sub.is_dir():
            names.extend(path.name for path in sub.iterdir())
    return sorted(names)
