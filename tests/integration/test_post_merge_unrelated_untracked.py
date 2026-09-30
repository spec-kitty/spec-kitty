"""Post-merge bookkeeping tolerates untracked files (FR-004).

Untracked ``.worktrees/`` and unrelated untracked files (e.g. a stray
``tmp.txt``) must not block the post-merge bookkeeping pass. The contract is:

* **Untracked entries** (``??`` in porcelain v1) -- silently dropped. Untracked
  files cannot diverge from HEAD, so they are not a merge concern.
* **Tracked diverging entries** outside of the expected status files --
  surfaced as a structured error. NO silent suppression.

The contract is pinned twice:

* directly on ``_classify_porcelain_lines`` (the helper the merge invariant
  uses), and
* end to end on a REAL coordination mission (``tests/terminus`` harness: real
  git, real lanes, real reconciliation / bake / teardown gates -- nothing in the
  merge pipeline is stubbed). The untracked half drives the real CLI; the
  tracked half drives the real executor in-process with exactly ONE seam
  injected -- the raw ``git status --porcelain`` read -- because a genuinely
  dirty tracked file is refused by the earlier ``MERGE_UNSAFE_PRIMARY_DIRTY``
  preflight and so can never reach the post-merge invariant with real git.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

from specify_cli.cli.commands.consolidate import (
    _classify_porcelain_lines,
    _run_lane_based_consolidation,
)
from specify_cli.consolidation.config import MergeStrategy
from tests.terminus.conftest import build_coord_mission, run_terminus
from tests._support.git_cli import git_out


pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]


class TestClassifyPorcelainLines:
    """Pin the contract on the helper directly."""

    def test_untracked_worktrees_dir_dropped(self):
        lines = ["?? .worktrees/scratch/", "?? tmp.txt"]
        offending, skipped = _classify_porcelain_lines(lines, expected_paths=set())
        assert offending == [], f"Untracked entries must be silently dropped (FR-004), got: {offending!r}"
        assert skipped == 2

    def test_expected_status_files_dropped(self):
        lines = [
            " M kitty-specs/test/status.events.jsonl",
            " M kitty-specs/test/status.json",
        ]
        offending, _ = _classify_porcelain_lines(
            lines,
            expected_paths={
                "kitty-specs/test/status.events.jsonl",
                "kitty-specs/test/status.json",
            },
        )
        assert offending == [], f"The two status files in expected_paths must be allowlisted: {offending!r}"

    def test_tracked_unrelated_modification_is_offending(self):
        """No silent suppression: a tracked change outside the allowlist must surface."""
        lines = [" M src/unexpected_file.py"]
        offending, _ = _classify_porcelain_lines(
            lines,
            expected_paths={"kitty-specs/test/status.events.jsonl"},
        )
        assert offending == [" M src/unexpected_file.py"], (
            "Tracked diverging changes outside expected_paths MUST be reported. FR-004 forbids silent suppression of operator-supplied tracked changes."
        )

    def test_mixed_untracked_and_tracked(self):
        """Untracked entries are dropped; tracked diverging entries surface."""
        lines = [
            "?? .worktrees/",
            "?? scratch.txt",
            " D src/important.py",  # tracked deletion — must surface
        ]
        offending, skipped = _classify_porcelain_lines(lines, expected_paths=set())
        assert offending == [" D src/important.py"]
        assert skipped == 2


class TestMergeToleratesUntrackedFiles:
    """End to end on real git: the merge succeeds when only untracked entries exist."""

    @pytest.mark.slow  # real `spec-kitty consolidate` subprocess on a real coord mission (>30s)
    def test_merge_succeeds_with_untracked_worktrees_and_tmp(self, tmp_path: Path) -> None:
        mission = build_coord_mission(tmp_path)
        scratch = mission.repo / ".worktrees" / "scratch"
        scratch.mkdir(parents=True)
        (scratch / "notes.txt").write_text("operator scratch\n", encoding="utf-8")
        (mission.repo / "tmp.txt").write_text("stray\n", encoding="utf-8")
        target_before = mission.rev(mission.target_branch)

        result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

        assert result.returncode == 0, f"untracked entries must not block the merge\nstdout={result.stdout}\nstderr={result.stderr}"
        assert "invariant violated" not in result.stdout
        # The merge really landed: the WP01 lane code is on the target branch...
        assert mission.rev(mission.target_branch) != target_before
        assert "def wp01()" in git_out(mission.repo, "show", f"{mission.target_branch}:src/pkg/wp01.py")
        # ...and the operator's untracked files were neither committed nor destroyed.
        tracked = git_out(mission.repo, "ls-tree", "-r", "--name-only", mission.target_branch).splitlines()
        assert "tmp.txt" not in tracked
        assert not any(name.startswith(".worktrees/") for name in tracked)
        assert (mission.repo / "tmp.txt").read_text(encoding="utf-8") == "stray\n"
        assert (scratch / "notes.txt").exists()

    def test_merge_aborts_on_unrelated_tracked_change(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A tracked change outside the allowlist trips the post-merge invariant (exit 1 + named path)."""
        mission = build_coord_mission(tmp_path)
        monkeypatch.setenv("HOME", str(mission.home))
        monkeypatch.setenv("SPEC_KITTY_NO_UPGRADE_CHECK", "1")
        monkeypatch.chdir(mission.repo)

        # The ONLY injected seam: what ``git status --porcelain`` reports after
        # the merge. Untracked noise is tolerated; the tracked modification is not.
        monkeypatch.setattr(
            "specify_cli.consolidation.executor._raw_porcelain_status",
            lambda _repo_root: (0, "?? .worktrees/\n M src/operator_change.py\n"),
        )

        with pytest.raises(typer.Exit) as excinfo:
            _run_lane_based_consolidation(
                repo_root=mission.repo,
                mission_slug=mission.slug,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
            )

        out = capsys.readouterr().out
        assert excinfo.value.exit_code == 1
        assert "Post-merge working-tree invariant violated" in out
        assert "src/operator_change.py" in out
        # The tolerated untracked entry must NOT be reported as offending.
        assert ".worktrees/" not in out.split("invariant violated", 1)[1]
