"""verdict-seam-write-unification-01KZ9Q35 WP09 (T044/T045, FR-014/D-PLAN-6).

Red-first proof that two divergent best-effort ``review-cycle-N.md`` renders
colliding under one filename do NOT abort a real mission->target squash merge.

Context: ``review-cycle-verdict-seam-rebuild-01KZ2W7W`` WP18 registered
``merge_driver_review_cycle`` as a REFUSE-fail-closed driver (T077) -- a
genuine two-verdict collision made ``git merge --squash -X theirs`` report
the path as an unresolved conflict, so ``specify_cli.lanes.consolidation.
_merge_branch_into`` aborted the squash and raised ``RuntimeError``. That was
correct while the ``.md`` render was the authoritative verdict record.

This mission's WP05 (a hard dependency of this WP) demoted the ``.md`` render
to non-authoritative, unread best-effort prose: ``status.events.jsonl``'s
``review_result`` event slot is now the sole verdict authority (see
``kitty-specs/verdict-seam-write-unification-01KZ9Q35/contracts/
provenance-backfill.md``). Aborting an otherwise-clean squash over unread
prose is pure friction with no safety benefit, so WP09 downgrades the driver
to non-aborting (FR-014/D-PLAN-6): both divergent renders are still embedded
verbatim behind conflict markers (never blended/fabricated), but the driver
no longer raises -- the squash proceeds.

This test drives the REAL squash-merge path
(``specify_cli.lanes.consolidation._merge_branch_into``, the same function
``spec-kitty merge`` calls for mission->target integration) so the proof is
against the actual git merge-driver contract, not just the in-process
function. It is RED against the pre-WP09 fail-closed driver (the squash
raises ``RuntimeError`` and ``main`` never advances) and GREEN after the
downgrade (the squash succeeds and ``main`` advances to the conflict-marked,
merged content).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.consolidation import _merge_branch_into
from specify_cli.consolidation.config import MergeStrategy

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[2]
_SRC_ROOT = _REPO_ROOT / "src"

_MISSION_SLUG = "wp09-divergent-render-fixture-01KZ9Q35"
_WP_ID = "WP07"
_REVIEW_CYCLE_REL_PATH = f"kitty-specs/{_MISSION_SLUG}/tasks/{_WP_ID}/review-cycle-1.md"

# Two independently-authored best-effort renders of the SAME cycle number --
# ordinary prose drift now that neither side is read for verdict authority.
_OURS_RENDER = (
    "---\n"
    "cycle_number: 1\n"
    f"wp_id: {_WP_ID}\n"
    f"mission_slug: {_MISSION_SLUG}\n"
    "reviewer_agent: reviewer-renata\n"
    "verdict: approved\n"
    "reviewed_at: '2026-08-05T09:00:00Z'\n"
    "---\n\n"
    "Target-side best-effort render: approved.\n"
)

_THEIRS_RENDER = (
    "---\n"
    "cycle_number: 1\n"
    f"wp_id: {_WP_ID}\n"
    f"mission_slug: {_MISSION_SLUG}\n"
    "reviewer_agent: reviewer-renata\n"
    "verdict: rejected\n"
    "reviewed_at: '2026-08-05T11:00:00Z'\n"
    "---\n\n"
    "Mission-side best-effort render: rejected (later re-review).\n"
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _show(repo: Path, ref: str, rel_path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{ref}:{rel_path}"],
        cwd=str(repo), capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise AssertionError(f"git show {ref}:{rel_path} failed: {result.stderr}")
    return result.stdout


def _bootstrap_divergent_renders(repo: Path) -> str:
    """Base has no ``review-cycle-1.md`` for this WP. ``main`` (target) and a
    mission branch each independently ADD it with different best-effort
    content -- an add/add divergence under the driver's own pattern.

    Returns the mission branch name; the target branch is always ``main``.
    """
    _init_repo(repo)
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")

    mission_branch = f"kitty/mission-{_MISSION_SLUG}"
    _git(repo, "branch", mission_branch)

    _git(repo, "checkout", "-q", "main")
    review_path = repo / _REVIEW_CYCLE_REL_PATH
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(_OURS_RENDER, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "target: best-effort render")

    _git(repo, "checkout", "-q", mission_branch)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(_THEIRS_RENDER, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "mission: divergent best-effort render")

    _git(repo, "checkout", "-q", "main")
    return mission_branch


def test_divergent_best_effort_renders_do_not_abort_the_squash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T044/T045 (FR-014): a genuine two-render collision under
    ``review-cycle-1.md`` must NOT abort ``git merge --squash -X theirs``.

    RED against the pre-WP09 fail-closed driver: ``_merge_branch_into`` would
    raise ``RuntimeError`` (the squash aborts, ``main`` never advances). GREEN
    after the downgrade: the squash succeeds, ``main`` advances, and both
    renders survive verbatim behind conflict markers -- never blended,
    never silently dropped.

    ``PYTHONPATH`` is pinned to this lane's own ``src/`` so the
    ``spec-kitty merge-driver-review-cycle`` subprocess git spawns imports
    THIS lane's ``specify_cli`` rather than an unrelated editable install
    that may otherwise win on ambient ``PATH``/site-packages ordering.
    """
    monkeypatch.setenv("PYTHONPATH", str(_SRC_ROOT))
    repo = tmp_path / "repo"
    mission_branch = _bootstrap_divergent_renders(repo)

    pre_main = _show(repo, "main", _REVIEW_CYCLE_REL_PATH)
    assert pre_main == _OURS_RENDER, "precondition: target starts with its own render"

    # The squash must complete without raising -- this is the red-first
    # assertion: it fails with RuntimeError("Squash merge ... failed") against
    # the pre-downgrade fail-closed driver.
    changed = _merge_branch_into(repo, mission_branch, "main", strategy=MergeStrategy.SQUASH)
    assert changed is True

    post_main = _show(repo, "main", _REVIEW_CYCLE_REL_PATH)
    assert _OURS_RENDER in post_main, (
        "the target's own best-effort render must survive verbatim, embedded "
        f"inside the conflict-marked document. Got: {post_main!r}"
    )
    assert _THEIRS_RENDER in post_main, (
        "the incoming mission-side render must also survive verbatim -- "
        f"never lost/fabricated. Got: {post_main!r}"
    )
    assert "<<<<<<<" in post_main, "both renders must stay demarcated, never blended"
