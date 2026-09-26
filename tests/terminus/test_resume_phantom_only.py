"""Safety guard for the #4997 behind-own-HEAD resume recovery (US1 AC2, FR-002).

The recovery must reset the primary to HEAD ONLY when the lag is *provably pure* — the
working tree AND index are byte-identical to the persisted ``pre_mutation_target_sha``.
Lane-ancestry alone (``BEHIND_OWN_HEAD``) is INSUFFICIENT: it proves the lane is
integrated but nothing about *what* is dirty. If a genuine tracked edit coexists in the
same window, a blind ``git reset --hard HEAD`` would destroy it. This test proves the
recovery REFUSES (never resets) the instant the primary carries a change not explained by
the pure lag, so genuine operator work is preserved (Renata's data-loss hole).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import _git as git
from tests.terminus.conftest import build_coord_mission, run_terminus
from tests.terminus.test_repro_4997 import _interrupt_behind_own_head

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def test_resume_refuses_and_preserves_a_genuine_edit_in_the_behind_head_window(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M4997B")
    _interrupt_behind_own_head(mission, ["WP01", "WP02"])

    # A GENUINE tracked edit coexisting with the behind-own-HEAD lag: the working tree now
    # differs from the persisted pre_mutation_target_sha, so this is NOT a pure lag.
    readme = mission.repo / "README.md"
    sentinel = "GENUINE OPERATOR EDIT — must survive the resume\n"
    readme.write_text(readme.read_text(encoding="utf-8") + sentinel, encoding="utf-8")

    result = run_terminus(mission, ["merge", "--resume", "--yes"])

    assert result.returncode != 0, (
        f"merge --resume must REFUSE (fail-closed) when the behind-own-HEAD window also carries a genuine edit, got rc=0\nstdout:\n{result.stdout}"
    )
    assert sentinel in readme.read_text(encoding="utf-8"), (
        "the genuine operator edit was DESTROYED by a reset --hard during resume — the phantom-only proof failed to protect non-lag local work (#4997 / FR-002)"
    )


def test_resume_refuses_and_preserves_an_untracked_file_colliding_with_a_restored_path(tmp_path: Path) -> None:
    # #4997 pre-PR finding: `git diff --quiet <base>` is blind to untracked files, but
    # `git reset --hard HEAD` OVERWRITES an untracked file sitting at a path HEAD restores
    # (a mission file the lagging tree lacks). The phantom-only proof must screen this via
    # the untracked-obstruction check, else it silently destroys the operator's file.
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M4997D")
    _interrupt_behind_own_head(mission, ["WP01", "WP02"])

    # An UNTRACKED operator file at exactly a to-be-restored mission path.
    collide = mission.repo / "src" / "pkg" / "wp01.py"
    collide.parent.mkdir(parents=True, exist_ok=True)
    sentinel = "PRECIOUS UNTRACKED OPERATOR CONTENT — must survive the resume\n"
    collide.write_text(sentinel, encoding="utf-8")

    result = run_terminus(mission, ["merge", "--resume", "--yes"])

    assert result.returncode != 0, (
        f"merge --resume must REFUSE when an untracked file would be clobbered by the behind-own-HEAD reset, got rc=0\nstdout:\n{result.stdout}"
    )
    assert collide.read_text(encoding="utf-8") == sentinel, (
        "the untracked operator file at a restored mission path was CLOBBERED by reset --hard during resume — the untracked-obstruction check failed (#4997)"
    )


def test_resume_refuses_and_preserves_a_gitignored_file_the_mission_force_added(tmp_path: Path) -> None:
    # regression: #4997 follow-up (data-loss, VERIFIED LIVE). `git ls-files --others
    # --exclude-standard` (the old obstruction scan) EXCLUDES gitignored paths, but
    # `git reset --hard HEAD` overwrites an IGNORED file sitting at a path HEAD's tree
    # tracks. If a mission commit force-adds (`git add -f`) a path that is gitignored,
    # and the operator has genuine local content at that same gitignored path in the
    # behind-own-HEAD window, the reset must NOT clobber it. The fix widens the
    # obstruction scan to `git status --porcelain --ignored` (`??` AND `!!`), consumed
    # through the public seam `ref_advance.reset_would_obstruct_untracked` (INV-3).
    mission = build_coord_mission(
        tmp_path,
        wps=("WP01", "WP02"),
        mid8="01M4997F",
        extra_base_files={".gitignore": "secret.env\n"},
    )

    # WP01's approved lane commit force-adds a gitignored path (attributed to a real
    # approved WP, so the terminus reconciliation gate has no unrelated reason to
    # refuse) — HEAD's (post-advance) tree tracks `secret.env` despite `.gitignore`
    # listing it.
    lane_branch = mission.lane_branch("WP01")
    git(mission.repo, "checkout", "-q", lane_branch)
    (mission.repo / "secret.env").write_text("mission-tracked-secret\n", encoding="utf-8")
    git(mission.repo, "add", "-f", "secret.env")
    git(mission.repo, "commit", "-qm", "feat: WP01 force-adds a gitignored path")
    git(mission.repo, "checkout", "-q", mission.target_branch)

    _interrupt_behind_own_head(mission, ["WP01", "WP02"])

    # The OPERATOR has genuine local content at that same gitignored path, in the
    # primary checkout, while it sits behind its own (already-advanced) HEAD. The
    # primary's currently checked-out tree predates the force-add commit, so this
    # file reads as untracked-and-ignored (`!!`), not a tracked modification.
    secret = mission.repo / "secret.env"
    sentinel = "OPERATOR'S OWN GITIGNORED SECRET — must survive the resume\n"
    secret.write_text(sentinel, encoding="utf-8")

    result = run_terminus(mission, ["merge", "--resume", "--yes"])

    assert result.returncode != 0, (
        f"merge --resume must REFUSE when a gitignored file the operator owns collides "
        f"with a path the mission force-added and the behind-own-HEAD reset would "
        f"restore, got rc=0\nstdout:\n{result.stdout}"
    )
    assert secret.read_text(encoding="utf-8") == sentinel, (
        "the operator's gitignored file was CLOBBERED by reset --hard during resume — "
        "the --exclude-standard obstruction scan is blind to ignored paths (#4997 "
        "follow-up, data-loss)"
    )
