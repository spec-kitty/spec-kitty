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
