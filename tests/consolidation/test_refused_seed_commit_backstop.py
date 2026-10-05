"""A refused coordination seed commit stops ``consolidate`` with its real cause (#5651, FR-006).

The seed commit is built at ``coordination/coord_seed.py::_commit_seed`` and runs through
the real ``safe_commit`` door (``git commit --only`` without ``--no-verify``), so a
``commit-msg`` hook that rejects the seed subject refuses it for real. Before the
backstop, ``consolidate`` carried on past the refused seed and ended in the misleading
``MERGE_UNSAFE_WORKTREE_DIRTY`` refusal ("Commit, stash, or revert"), pointing the
operator at files the tool planted itself.

Nothing in this file patches anything: the hook is a real git hook, the commit goes
through the real router and ``safe_commit``, and the real ``consolidate`` Typer command
runs end to end through the CLI runner (real done record, real bookkeeping commit, real
gates), with no mock of in-repository or external code.
"""

from __future__ import annotations

import json
import re
import stat
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from tests.consolidation.approval_stamps import approved_lane_tips, with_lane_head
from tests.integration.test_merge_lane_planning_data_loss import (
    _commit_file,
    _git,
    _init_git_repo,
    _invoke_merge_cli,
    _seed_wp_approved,
    _write_coord_retaining_meta,
    _write_lanes_manifest,
    _write_wp_file,
)


def _stamp_untracked_approval_at_lane_tips(repo: Path, feature_dir: Path) -> None:
    """Stamp each `approved` event with its lane tip in an UNTRACKED status log (#5668), no commit.

    The approval seeded before the lane commit exists carries no `lane_head`, which #5668's
    approved bound refuses. Here the status pair stays UNTRACKED at the root (consolidate seeds
    it), so stamp in place WITHOUT committing -- unlike the committed-log fixtures that use
    `restamp_log_at_lane_tips`.
    """
    tips = approved_lane_tips(repo, feature_dir)
    log = feature_dir / "status.events.jsonl"
    events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    stamped = [with_lane_head(event, tips[str(event["wp_id"])]) if event.get("to_lane") == "approved" and event.get("wp_id") in tips else event for event in events]
    log.write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in stamped), encoding="utf-8")


pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]

_REFUSED_CODE = "COORD_SEED_COMMIT_REFUSED"
_DIRTY_CODE = "MERGE_UNSAFE_WORKTREE_DIRTY"
_OLD_REMEDY = "Commit, stash, or revert"
_SEED_SUBJECT_MARKER = "seed coordination surface"
_MISSION_ID = "01KX0000000SEEDBACKSTOP001"
_MID8 = _MISSION_ID[:8]
# A COMPOSED primary directory: the slug already carries the mid8, so the primary
# directory name equals the composed ``<slug>-<mid8>`` name and no alias is involved.
_SLUG = f"seed-backstop-{_MID8}"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"
_SEEDED_STATUS_FILES = (
    f"kitty-specs/{_SLUG}/status.events.jsonl",
    f"kitty-specs/{_SLUG}/status.json",
)

_REJECTING_HOOK = f"""#!/bin/sh
# Reject only the coordination seed commit; every other commit passes.
if grep -q '{_SEED_SUBJECT_MARKER}' "$1"; then
  echo "seed backstop test hook: refusing the coordination seed commit" >&2
  exit 1
fi
exit 0
"""

_REJECT_EVERY_COMMIT_HOOK = """#!/bin/sh
echo "seed backstop test hook: refusing every commit" >&2
exit 1
"""


@dataclass(frozen=True)
class _Fixture:
    repo: Path
    coord_worktree: Path
    hooks_dir: Path

    def install_hook(self, script: str = _REJECTING_HOOK) -> Path:
        self.hooks_dir.mkdir(parents=True, exist_ok=True)
        hook = self.hooks_dir / "commit-msg"
        hook.write_text(script, encoding="utf-8")
        hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return hook

    def remove_hook(self) -> None:
        (self.hooks_dir / "commit-msg").unlink()

    def head(self, ref: str) -> str:
        return _git(self.repo, "rev-parse", ref).stdout.strip()

    def refs(self) -> dict[str, str]:
        return {ref: self.head(ref) for ref in ("main", _MISSION_BRANCH, f"kitty/mission-{_SLUG}-lane-a")}


def _build_fixture(tmp_path: Path) -> _Fixture:
    """A coordination Mission, composed primary directory, whose coordination worktree lacks the Mission dir.

    The coordination branch is cut BEFORE the bootstrap commit, so its worktree has no
    ``kitty-specs/<slug>`` directory and the status files exist only as untracked root
    files: consolidate has to seed the coordination surface, which is the commit the
    hook then rejects.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _git(repo, "branch", _MISSION_BRANCH, "main")

    feature_dir = repo / "kitty-specs" / _SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    _write_coord_retaining_meta(feature_dir, _SLUG)
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["mission_id"] = _MISSION_ID
    meta["mid8"] = _MID8
    meta["coordination_branch"] = _MISSION_BRANCH
    meta["mission_branch"] = _MISSION_BRANCH
    meta.pop("retain_branches")
    meta.pop("retain_worktrees")
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_lanes_manifest(feature_dir, _SLUG, code_wp_ids=["WP01"], planning_wp_ids=[], mission_branch=_MISSION_BRANCH)
    _write_wp_file(feature_dir, "WP01")
    _seed_wp_approved(feature_dir, _SLUG, "WP01")
    # Commit the Mission's planning files; the status pair stays untracked at the root.
    _git(repo, "add", ".", ":!kitty-specs/*/status.events.jsonl", ":!kitty-specs/*/status.json")
    _git(repo, "commit", "-m", f"chore({_SLUG}): bootstrap coord mission")
    # Materialize the coordination worktree after the bootstrap commit so it is not swept into it.
    from specify_cli.coordination.workspace import CoordinationWorkspace

    coord_worktree = CoordinationWorkspace.worktree_path(repo, _SLUG, _MID8)
    _git(repo, "worktree", "add", "-q", str(coord_worktree), _MISSION_BRANCH)

    lane_a_branch = f"kitty/mission-{_SLUG}-lane-a"
    _git(repo, "branch", lane_a_branch, "main")
    _commit_file(
        repo,
        branch=lane_a_branch,
        relpath="src/seed_backstop.py",
        content="def foo():\n    return 1\n",
        message=f"feat({_SLUG}): add foo function (WP01)",
    )
    _git(repo, "checkout", "main")
    _stamp_untracked_approval_at_lane_tips(repo, feature_dir)
    from specify_cli.lanes.worktree_allocator import predict_lane_worktree

    lane_worktree, _lane_branch = predict_lane_worktree(repo, _SLUG, "lane-a")
    _git(repo, "worktree", "add", str(lane_worktree), lane_a_branch)
    return _Fixture(repo=repo, coord_worktree=coord_worktree, hooks_dir=repo / ".git" / "hooks")


@pytest.fixture
def fixture(tmp_path: Path) -> Iterator[_Fixture]:
    yield _build_fixture(tmp_path)


def _consolidate(fx: _Fixture) -> Any:
    return _invoke_merge_cli(fx.repo, ["--mission", _SLUG, "--yes", "--allow-sparse-checkout"])


def _seed_files_in_coord_worktree(fx: _Fixture) -> list[str]:
    return [rel for rel in _SEEDED_STATUS_FILES if (fx.coord_worktree / rel).is_file()]


def _is_tracked_on_branch(fx: _Fixture, branch: str, relpath: str) -> bool:
    return bool(_git(fx.repo, "ls-tree", "--name-only", branch, "--", relpath).stdout.strip())


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell commit-msg hook")
class TestRefusedSeedCommitBackstop:
    def test_hook_rejected_seed_stops_with_the_real_cause(self, fixture: _Fixture) -> None:
        fixture.install_hook()
        refs_before = fixture.refs()

        result = _consolidate(fixture)

        output = re.sub(r"\s+", " ", result.output).strip()
        assert result.exit_code == 1, output
        assert f"Error code: {_REFUSED_CODE}." in output, output
        for rel in _SEEDED_STATUS_FILES:
            assert rel in output.replace(" ", ""), output
        assert "kept" in output and "re-run" in output.lower(), output
        assert _DIRTY_CODE not in output, output
        assert _OLD_REMEDY not in output, output
        assert "before any state change" not in output, output
        assert fixture.refs() == refs_before
        assert _seed_files_in_coord_worktree(fixture) == list(_SEEDED_STATUS_FILES)

    def test_retry_after_the_cause_is_fixed_commits_the_kept_files(self, fixture: _Fixture) -> None:
        fixture.install_hook()
        first = _consolidate(fixture)
        assert first.exit_code == 1, first.output
        assert _seed_files_in_coord_worktree(fixture) == list(_SEEDED_STATUS_FILES)

        fixture.remove_hook()
        second = _consolidate(fixture)

        assert second.exit_code == 0, second.output
        assert _REFUSED_CODE not in second.output
        for rel in _SEEDED_STATUS_FILES:
            assert _is_tracked_on_branch(fixture, "main", rel), rel

    def test_refused_twice_still_names_both_files(self, fixture: _Fixture) -> None:
        fixture.install_hook()
        first = _consolidate(fixture)
        second = _consolidate(fixture)

        for result in (first, second):
            output = re.sub(r"\s+", " ", result.output).strip()
            assert result.exit_code == 1, output
            assert f"Error code: {_REFUSED_CODE}." in output, output
            for rel in _SEEDED_STATUS_FILES:
                assert rel in output.replace(" ", ""), output
        assert _seed_files_in_coord_worktree(fixture) == list(_SEEDED_STATUS_FILES)

    def test_a_hook_rejecting_every_commit_is_a_clean_refusal_with_no_merge_record(self, fixture: _Fixture) -> None:
        fixture.install_hook(_REJECT_EVERY_COMMIT_HOOK)
        refs_before = fixture.refs()

        result = _consolidate(fixture)

        output = re.sub(r"\s+", " ", result.output).strip()
        assert result.exit_code == 1, output
        assert result.exception is None or isinstance(result.exception, SystemExit), repr(result.exception)
        assert output.endswith(f"Error code: {_REFUSED_CODE}."), output
        assert "Consolidation refused before any branch moved." in output, output
        assert fixture.refs() == refs_before
        assert list((fixture.repo / ".kittify" / "runtime" / "merge").glob("*/state.json")) == []
        assert _seed_files_in_coord_worktree(fixture) == list(_SEEDED_STATUS_FILES)


class TestSeedHappensWithoutTheHook:
    """Non-vacuity control: the same fixture, no hook, consolidates; the refusal needs a refused commit."""

    def test_no_hook_consolidates_and_reports_no_refusal(self, fixture: _Fixture) -> None:
        result = _consolidate(fixture)

        assert result.exit_code == 0, result.output
        assert _REFUSED_CODE not in result.output
