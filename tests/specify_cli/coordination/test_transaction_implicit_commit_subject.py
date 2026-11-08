"""#4837: the implicit transaction commit subject must name the staged
artifact, not just the operation.

Before: every implicit commit (a ``BookkeepingTransaction`` whose caller never
called ``commit()`` explicitly — the status-transition batch path
``status_transition.py`` relies on) landed as
``chore(spec-kitty): <operation>``, which names nothing about WHAT was
committed. On a coordination branch that subject is the only commit-level
context an operator sees in ``git log``, so several different missions'
bookkeeping commits become indistinguishable.

After: the subject carries the area(s) of the staged paths (the first two
worktree-relative components, deduped), e.g.
``chore(spec-kitty): status transition batch WP01
(kitty-specs/outbound-feature-01J6OUTB)``. When no area resolves (every staged
path outside the worktree), the subject keeps the historical operation-only
shape rather than growing an empty parenthetical.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination.transaction import BookkeepingTransaction
from specify_cli.status.emit import build_status_event
from specify_cli.status.models import StatusEvent

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


MISSION_SLUG = "outbound-feature"
MID8 = "01J6OUTB"  # exactly 8 chars (the mid8 contract) -- must match MISSION_ID[:8]
MISSION_ID = "01J6OUTBD00000000000000000"  # 26-char placeholder ULID
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}-{MID8}"
FEATURE_DIRNAME = f"{MISSION_SLUG}-{MID8}"
OPERATION = "status transition batch WP01"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "Test")
    _git(r, "config", "commit.gpgsign", "false")
    (r / "seed.txt").write_text("seed\n")
    _git(r, "add", "seed.txt")
    _git(r, "commit", "-q", "-m", "initial")
    _git(r, "branch", COORD_BRANCH)
    return r


def _write_modern_meta(repo: Path) -> None:
    """Declare this mission's coordination branch in ``meta.json`` (WP07)."""
    feature_dir = repo / "kitty-specs" / FEATURE_DIRNAME
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        (
            "{\n"
            f'  "mission_id": "{MISSION_ID}",\n'
            f'  "mission_slug": "{FEATURE_DIRNAME}",\n'
            '  "target_branch": "main",\n'
            f'  "coordination_branch": "{COORD_BRANCH}"\n'
            "}\n"
        ),
        encoding="utf-8",
    )


def _make_event(wp_id: str = "WP01") -> StatusEvent:
    return build_status_event(
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        wp_id=wp_id,
        from_lane="planned",
        to_lane="claimed",
        actor="subject-test",
    )


def test_implicit_commit_subject_names_the_staged_artifact_area(repo: Path) -> None:
    """The implicit commit on the coordination branch names the staged
    ``kitty-specs/<slug>-<mid8>/`` area in its subject."""
    _write_modern_meta(repo)
    event = _make_event()

    with BookkeepingTransaction.acquire(
        repo_root=repo,
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
        mid8=MID8,
        destination_ref=COORD_BRANCH,
        operation=OPERATION,
    ) as txn:
        txn.append_event(event)
        # No explicit commit() — __exit__ performs the implicit commit.

    subject = _git(repo, "log", "-1", "--format=%s", COORD_BRANCH)
    assert subject == (f"chore(spec-kitty): {OPERATION} (kitty-specs/{FEATURE_DIRNAME})"), (
        f"the implicit commit subject must name the staged artifact area, not just the operation; got {subject!r}"
    )


def test_implicit_commit_subject_falls_back_to_operation_when_no_area_resolves(
    repo: Path,
) -> None:
    """A staged path outside the worktree resolves to no area: the subject
    keeps the historical operation-only shape rather than an empty
    parenthetical."""
    _write_modern_meta(repo)

    with BookkeepingTransaction.acquire(
        repo_root=repo,
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
        mid8=MID8,
        destination_ref=COORD_BRANCH,
        operation=OPERATION,
    ) as txn:
        outside = Path("/definitely/outside/any/worktree.md")
        txn._staged_paths.append(outside)
        subject = txn._implicit_commit_subject()
        # Drop the outside path again so __exit__'s implicit commit is not
        # asked to stage a path that cannot exist in the worktree.
        txn._staged_paths.remove(outside)

    assert subject == f"chore(spec-kitty): {OPERATION}"
