"""Red-first regression net for #7201 — the terminus retrospective commit target.

The terminus retrospective bookkeeping commit (``retrospective.yaml`` + the
``status.events.jsonl`` append) resolves its destination from the placement
port, which reads ``meta.json``'s ``target_branch``. After
``spec-kitty consolidate --target <branch>`` that value is stale: the run's real
landing branch is the resolved target, and the checkout's HEAD is on it. The
termimus then asked ``safe_commit`` to commit to the stale target, the guard
correctly refused (``SafeCommitHeadMismatch``), and the fail-open terminus left
both files uncommitted.

These tests are the acceptance criteria of mission
``terminus-retrospective-commit-target-01M6P3E4``:

* SC-001/SC-002 — with the run's resolved target supplied, both artifacts are
  committed onto it and no other ref moves;
* SC-003 — the same fixture with NO resolved target still refuses and still
  leaves both files uncommitted (the guard is intact, the terminus still fails
  open) — the positive/negative pair is built from one shared fixture so the two
  cannot silently drift apart;
* SC-004 — the refusal warning names an executable recovery command that
  carries the target it was given.

Nothing here mocks git: every assertion is made against real refs and the real
working tree.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import pytest

from specify_cli.post_merge.retrospective_terminus import run_retrospective_postcondition

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

MISSION_SLUG = "demo-mission-01ABCDEF"
MISSION_ID = "01ABCDEFZZZ0000000000000AB"
MISSION_MID8 = "01ABCDEF"
META_TARGET = "main"
LANDING_BRANCH = "topic-landing"
TERMINUS_COMMIT_SUBJECT = f"chore({MISSION_SLUG}): capture mission retrospective"


def _git(repo: Path, *args: str) -> str:
    """Run one git command in ``repo`` and return its stripped stdout."""
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"git {' '.join(args)} failed: {result.stderr}"
    return result.stdout.strip()


def _build_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A real repo: ``main`` carries the Mission, HEAD is the landing branch.

    ``meta.json`` names the Mission's *destination* target (``main``) — the same
    shape a ``consolidate --target topic-landing`` run leaves behind: the stale
    meta destination is ``main``, the branch the work actually landed on is
    ``topic-landing``, and the checkout sits on it.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", META_TARGET)
    _git(repo, "config", "user.email", "terminus@example.invalid")
    _git(repo, "config", "user.name", "Terminus Test")

    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": MISSION_ID,
                "mid8": MISSION_MID8,
                "mission_slug": MISSION_SLUG,
                "target_branch": META_TARGET,
            }
        ),
        encoding="utf-8",
    )
    (repo / "README.md").write_text("scratch repo\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    _git(repo, "checkout", "-b", LANDING_BRANCH)
    return repo, feature_dir


def _dirty_terminus_artifacts(feature_dir: Path) -> tuple[Path, Path]:
    """Leave the two terminus artifacts uncommitted, as a capture would."""
    retrospective = feature_dir / "retrospective.yaml"
    retrospective.write_text("schema_version: 1\n", encoding="utf-8")
    events = feature_dir / "status.events.jsonl"
    events.write_text(json.dumps({"kind": "RetrospectiveCaptured"}) + "\n", encoding="utf-8")
    return retrospective, events


def _porcelain(repo: Path) -> list[str]:
    """Working-tree state, one entry per path (empty means clean)."""
    out = _git(repo, "status", "--porcelain")
    return [line for line in out.splitlines() if line.strip()]


def _tip(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", ref)


# ---------------------------------------------------------------------------
# SC-001 / SC-002 — the resolved landing target receives the commit
# ---------------------------------------------------------------------------


def test_resolved_destination_commits_onto_the_landing_branch(tmp_path: Path) -> None:
    """The run's resolved target is the commit destination, not the stale meta target."""
    repo, feature_dir = _build_repo(tmp_path)
    retrospective, events = _dirty_terminus_artifacts(feature_dir)
    meta_tip_before = _tip(repo, META_TARGET)

    sha = run_retrospective_postcondition(
        mission_slug=MISSION_SLUG,
        repo_root=repo,
        destination_ref=LANDING_BRANCH,
    )

    assert sha is not None, "the terminus must commit when it is told the landing branch"
    assert sha == _tip(repo, LANDING_BRANCH), "the reported SHA is the landing branch's new tip"
    assert _porcelain(repo) == [], "no terminus artifact may be left uncommitted"
    assert _git(repo, "log", "-1", "--format=%s", LANDING_BRANCH) == TERMINUS_COMMIT_SUBJECT
    for artifact in (retrospective, events):
        assert artifact.is_file(), "the commit must preserve the artifact on disk"
        tracked = _git(repo, "ls-tree", "-r", "--name-only", LANDING_BRANCH)
        assert str(artifact.relative_to(repo)) in tracked.splitlines()
    assert _tip(repo, META_TARGET) == meta_tip_before, "the meta target must not be advanced"


# ---------------------------------------------------------------------------
# SC-003 — the same fixture without a resolved target still refuses (guard intact)
# ---------------------------------------------------------------------------


def test_without_a_resolved_destination_the_guard_still_refuses(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No destination supplied → placement resolution (stale meta) → still refused."""
    repo, feature_dir = _build_repo(tmp_path)
    retrospective, events = _dirty_terminus_artifacts(feature_dir)
    landing_tip_before = _tip(repo, LANDING_BRANCH)
    meta_tip_before = _tip(repo, META_TARGET)

    with caplog.at_level(logging.WARNING, logger="specify_cli.post_merge.retrospective_terminus"):
        sha = run_retrospective_postcondition(mission_slug=MISSION_SLUG, repo_root=repo)

    assert sha is None, "an unresolved destination must not produce a commit"
    assert _porcelain(repo) == [
        f"?? {retrospective.relative_to(repo)}",
        f"?? {events.relative_to(repo)}",
    ], "both artifacts stay uncommitted — the fail-open terminus leaves them for the operator"
    assert _tip(repo, LANDING_BRANCH) == landing_tip_before
    assert _tip(repo, META_TARGET) == meta_tip_before
    assert "safe_commit" in caplog.text, "the refusal must be reported, not silently swallowed"
    assert "expected 'main'" in caplog.text, "the guard's destination is still the stale meta target"


# ---------------------------------------------------------------------------
# SC-004 — the printed recovery command can be aimed at that branch
# ---------------------------------------------------------------------------


def test_refusal_warning_prints_an_aimable_recovery_command(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed commit with a supplied destination prints ``... --target <branch>``."""
    repo, feature_dir = _build_repo(tmp_path)
    _dirty_terminus_artifacts(feature_dir)

    with caplog.at_level(logging.WARNING, logger="specify_cli.post_merge.retrospective_terminus"):
        sha = run_retrospective_postcondition(
            mission_slug=MISSION_SLUG,
            repo_root=repo,
            destination_ref="branch-that-does-not-exist",
        )

    assert sha is None, "a missing destination is fail-open: warn and return None"
    assert _porcelain(repo), "the artifacts stay uncommitted for the operator to heal"
    assert f"spec-kitty mission close --mission {MISSION_SLUG} --target branch-that-does-not-exist" in caplog.text, (
        "the recovery command must carry the destination the terminus was given"
    )
