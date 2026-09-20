"""RED-first regression: #4765 (FR-004/FR-005) + #2745 facet 3 (FR-013).

``mission close`` without ``--discard`` had zero preconditions despite its own
``--help`` claiming otherwise: it exits 0, commits a ``retrospective.yaml``
stamped ``kind: runtime_post_completion`` to the mainline, and tears down the
coordination worktree for a mission that was **never merged**. Downstream
tooling (``retrospect summary``) then counts an in-flight mission as done, and
the coordination worktree the operator was still using is gone.

The fix (WP06, ``mission_type.py`` ``close_cmd``) adds a fail-closed
``is_mission_merged`` guard at the TOP of the non-discard ``else`` branch,
BEFORE ``_teardown_coordination_worktree`` — refusing (``Exit(1)``, no writes)
unless the mission carries a live ``merged_at`` marker (D4: NOT
``is_mission_completed`` — an all-terminal-but-unmerged mission must still go
via ``--discard``).

This file also pins FR-013 (#2745 facet 3): ``mission close`` tolerating a
mission left with an orphaned ``coordination_branch`` marker (declared in
``meta.json`` but absent from git) — no traceback, the mission slug rendered
once, and ``--json`` honored (the option did not exist at all pre-WP06).

See:
* spec.md FR-004, FR-005, FR-013; US2 (US2-1/US2-2/US2-3); US5-3.
* contracts/terminus-safety-contract.md -- C-CLOSE (PRE/REFUSE/PASS/ROBUST).
* data-model.md -- D4 (``is_mission_merged``, not ``is_mission_completed``).
* tasks/WP06-mission-close-safety-orphan-robustness.md (T017/T018/T019).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands import mission_type
from specify_cli.coordination import CoordinationWorkspace

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

runner = CliRunner()

MISSION_ID = "01J6XW9K000000000000000000"
MID8 = MISSION_ID[:8]
SLUG = f"issue-4765-close-guard-{MID8}"
COORD_BRANCH = CoordinationWorkspace.branch_name(SLUG, MID8)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _seed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".kittify").mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    return repo


def _write_meta(
    fdir: Path,
    *,
    merged_at: str | None,
) -> None:
    meta: dict[str, object] = {
        "mission_slug": SLUG,
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "coordination_branch": COORD_BRANCH,
        "mission_branch": COORD_BRANCH,
        "target_branch": "main",
    }
    if merged_at is not None:
        meta["merged_at"] = merged_at
    (fdir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _write_wp_event(fdir: Path, *, to_lane: str, from_lane: str, reason: str | None = None) -> None:
    """Append one realistic status-lane transition event for WP01."""
    event = {
        "actor": "claude",
        "at": "2026-09-20T09:00:00+00:00",
        "event_id": f"01J6XW9K0000000000WP{to_lane[:4].upper()}",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": SLUG,
        "force": False,
        "from_lane": from_lane,
        "reason": reason,
        "review_ref": None,
        "to_lane": to_lane,
        "wp_id": "WP01",
    }
    events_path = fdir / "status.events.jsonl"
    existing = events_path.read_text(encoding="utf-8") if events_path.exists() else ""
    events_path.write_text(existing + json.dumps(event) + "\n", encoding="utf-8")


@pytest.fixture
def coord_mission_unmerged(tmp_path: Path) -> Path:
    """A live, in-flight coordination mission -- no merge baseline recorded.

    Primary branch carries meta.json (no ``merged_at``) + status; the
    coordination branch's mission dir is status-only; a real coordination
    worktree is materialised (the operator is still using it).
    """
    repo = _seed_repo(tmp_path)
    fdir = repo / "kitty-specs" / SLUG
    fdir.mkdir(parents=True)
    _write_meta(fdir, merged_at=None)
    (fdir / "status.events.jsonl").write_text("", encoding="utf-8")
    _write_wp_event(fdir, from_lane="claimed", to_lane="in_progress")
    (fdir / "status.json").write_text("{}", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed primary mission surface")

    _git(repo, "branch", COORD_BRANCH)
    _git(repo, "checkout", "-q", COORD_BRANCH)
    _git(repo, "rm", "-q", f"kitty-specs/{SLUG}/meta.json")
    _git(repo, "commit", "-q", "-m", "coord: status-only mission surface")
    _git(repo, "checkout", "-q", "main")

    CoordinationWorkspace.resolve(repo, SLUG, MID8)
    assert CoordinationWorkspace.is_present(repo, SLUG, MID8)
    return repo


def test_close_without_discard_refuses_unmerged_in_flight_mission(coord_mission_unmerged: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """US2-1 / FR-004 / FR-005: an unmerged, in-flight mission (WP01
    ``in_progress``) refuses a non-discard ``close`` -- exits non-zero, writes
    no retrospective, commits nothing, leaves the coordination worktree
    intact, and points the operator at ``--discard``."""
    repo = coord_mission_unmerged
    monkeypatch.chdir(repo)
    fdir = repo / "kitty-specs" / SLUG
    retro_path = fdir / "retrospective.yaml"
    head_before = _git(repo, "rev-parse", "main").stdout.strip()

    result = runner.invoke(mission_type.app, ["close", "--mission", SLUG], env={"PWD": str(repo)})

    assert result.exit_code != 0, f"an unmerged mission must refuse `mission close` without --discard (today it fabricates completion); output: {result.output!r}"
    assert not retro_path.exists(), f"a refused close must write NO retrospective.yaml (FR-005); found one at {retro_path}"
    events_text = (fdir / "status.events.jsonl").read_text(encoding="utf-8")
    assert "RetrospectiveCaptured" not in events_text, (
        f"a refused close must emit NO RetrospectiveCaptured/completion event (FR-005); status.events.jsonl: {events_text!r}"
    )
    assert CoordinationWorkspace.is_present(repo, SLUG, MID8), f"a refused close must leave the coordination worktree intact (output: {result.output!r})"
    head_after = _git(repo, "rev-parse", "main").stdout.strip()
    assert head_after == head_before, "a refused close must commit nothing to main"
    assert "--discard" in result.output, f"the refusal message must point the operator at --discard (output: {result.output!r})"


def test_close_without_discard_refuses_all_cancelled_unmerged_boundary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Edge case / D4: a mission whose only work package is CANCELLED but
    carries NO merge baseline must still refuse a non-discard close and route
    the operator to --discard -- proving the guard keys on `is_mission_merged`,
    not on `is_mission_completed` (which would treat an all-terminal-but-
    unmerged mission as done and tear it down)."""
    repo = _seed_repo(tmp_path)
    fdir = repo / "kitty-specs" / SLUG
    fdir.mkdir(parents=True)
    _write_meta(fdir, merged_at=None)
    (fdir / "status.events.jsonl").write_text("", encoding="utf-8")
    _write_wp_event(fdir, from_lane="claimed", to_lane="in_progress")
    _write_wp_event(fdir, from_lane="in_progress", to_lane="canceled", reason="superseded by architecture")
    (fdir / "status.json").write_text("{}", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed primary mission surface")

    _git(repo, "branch", COORD_BRANCH)
    _git(repo, "checkout", "-q", COORD_BRANCH)
    _git(repo, "rm", "-q", f"kitty-specs/{SLUG}/meta.json")
    _git(repo, "commit", "-q", "-m", "coord: status-only mission surface")
    _git(repo, "checkout", "-q", "main")

    CoordinationWorkspace.resolve(repo, SLUG, MID8)
    monkeypatch.chdir(repo)

    result = runner.invoke(mission_type.app, ["close", "--mission", SLUG], env={"PWD": str(repo)})

    assert result.exit_code != 0, f"an all-cancelled-but-UNMERGED mission must still refuse a non-discard close (D4); output: {result.output!r}"
    assert not (fdir / "retrospective.yaml").exists()
    assert "--discard" in result.output


@pytest.fixture
def coord_mission_merged(tmp_path: Path) -> Path:
    """A genuinely merged coordination mission (``merged_at`` recorded)."""
    repo = _seed_repo(tmp_path)
    fdir = repo / "kitty-specs" / SLUG
    fdir.mkdir(parents=True)
    _write_meta(fdir, merged_at="2026-09-20T08:00:00+00:00")
    (fdir / "status.events.jsonl").write_text("", encoding="utf-8")
    _write_wp_event(fdir, from_lane="in_progress", to_lane="approved")
    (fdir / "status.json").write_text("{}", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed primary mission surface")

    _git(repo, "branch", COORD_BRANCH)
    _git(repo, "checkout", "-q", COORD_BRANCH)
    _git(repo, "rm", "-q", f"kitty-specs/{SLUG}/meta.json")
    _git(repo, "commit", "-q", "-m", "coord: status-only mission surface")
    _git(repo, "checkout", "-q", "main")

    CoordinationWorkspace.resolve(repo, SLUG, MID8)
    assert CoordinationWorkspace.is_present(repo, SLUG, MID8)
    return repo


def test_close_without_discard_admits_merged_mission_and_tears_down(coord_mission_merged: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """US2-2: the guard admits a genuinely merged mission -- the existing
    completion teardown still runs, exactly as before the fix."""
    repo = coord_mission_merged
    monkeypatch.chdir(repo)

    result = runner.invoke(mission_type.app, ["close", "--mission", SLUG], env={"PWD": str(repo)})

    assert result.exit_code == 0, result.output
    assert not CoordinationWorkspace.is_present(repo, SLUG, MID8), (
        f"a merged mission's non-discard close must still tear down the coordination worktree; output: {result.output!r}"
    )
    assert "closed" in result.output.lower()


@pytest.fixture
def coord_mission_orphaned(tmp_path: Path) -> Path:
    """A MERGED mission whose ``coordination_branch`` marker is orphaned:
    declared in meta.json, but the branch/worktree was NEVER created (never
    materialised via ``CoordinationWorkspace.resolve``) -- the direct-on-target
    / partially-torn-down shape US5-3 describes."""
    repo = _seed_repo(tmp_path)
    fdir = repo / "kitty-specs" / SLUG
    fdir.mkdir(parents=True)
    _write_meta(fdir, merged_at="2026-09-20T08:00:00+00:00")
    (fdir / "status.events.jsonl").write_text("", encoding="utf-8")
    _write_wp_event(fdir, from_lane="in_progress", to_lane="approved")
    (fdir / "status.json").write_text("{}", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed primary mission surface")
    # NOTE: no coordination branch is ever created, no worktree materialised.
    return repo


def test_close_orphaned_coordination_branch_no_traceback_single_slug(coord_mission_orphaned: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """US5-3 / FR-013: an orphaned coordination_branch marker is tolerated --
    no traceback, and the mission slug is rendered once (not doubled)."""
    repo = coord_mission_orphaned
    monkeypatch.chdir(repo)

    result = runner.invoke(mission_type.app, ["close", "--mission", SLUG], env={"PWD": str(repo)})

    assert result.exception is None, f"orphaned coordination_branch marker must not raise a traceback: {result.exception!r}"
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    assert f"{MID8}-{MID8}" not in result.output, f"mission identity rendered doubled: {result.output!r}"
    assert f"{SLUG}-{MID8}" not in result.output, f"mission identity rendered doubled: {result.output!r}"


def test_close_orphaned_coordination_branch_honors_json(coord_mission_orphaned: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """US5-3 / FR-013: ``--json`` is honored on the orphan-tolerant close
    path -- valid, parseable JSON, not a Typer usage error (the option did
    not exist at all pre-WP06) and not mixed human/JSON text."""
    repo = coord_mission_orphaned
    monkeypatch.chdir(repo)

    result = runner.invoke(mission_type.app, ["close", "--mission", SLUG, "--json"], env={"PWD": str(repo)})

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["mission_slug"] == SLUG
    assert payload["result"] == "closed"
