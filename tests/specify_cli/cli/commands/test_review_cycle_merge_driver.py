"""review-cycle-verdict-seam-rebuild-01KZ2W7W WP18 -- the review-cycle merge
driver (T077-T080).

Covers:

- T077: ``merge_driver_review_cycle``'s two decision branches (identical
  content resolves cleanly; a genuine two-verdict collision embeds both
  documents verbatim behind conflict markers, never blending them into one).
- T078: the ``.gitattributes`` pattern is filename-anchored -- it must not
  sweep in ``tasks/<wp>/baseline-tests.json`` or ``tasks/WP*.md``.
- T079: the upgrade migration is idempotent and additive (preserves
  unrelated ``.gitattributes`` content).
- T080 (C-011, red-first): reproduces the create-window clobber (ADR
  2026-08-03-1 / #2804 shape) through the REAL mission->target squash merge
  path (``specify_cli.lanes.merge._merge_branch_into`` -> real
  ``git merge --squash -X theirs``), first WITHOUT the driver registered
  (RED: the target's genuine cycle-1 verdict is destroyed) and then WITH it
  (GREEN: both verdicts survive, embedded behind conflict markers, and the
  squash still succeeds). A second, fully hermetic proof drives ``git merge``
  directly with an explicit, absolute-interpreter-path driver command this
  test builds itself (never the ambient ``.git/config``, never bare
  ``spec-kitty`` on ``PATH``).

verdict-seam-write-unification-01KZ9Q35 WP09 (FR-014/D-PLAN-6) update: WP18's
original driver REFUSED fail-closed (exit 1, abort the squash) on a genuine
collision. This mission's WP05 (a hard dependency of WP09) demoted the
``.md`` render to non-authoritative, unread best-effort prose -- the
event-sourced ``review_result`` slot is the sole verdict authority now -- so
WP09 downgraded the driver to non-aborting: both documents still survive
verbatim behind conflict markers (never blended/fabricated), but the driver
no longer raises and the squash proceeds. The tests below that asserted the
OLD refuse-fail-closed contract are re-pinned to the new non-aborting
contract (renamed where the old name asserted "refuses"/aborts); none are
deleted -- see ``tests/review/test_review_cycle_merge_driver.py`` for WP09's
own new red-first proof of the downgrade through the same real squash-merge
path.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from specify_cli.cli.commands.merge_driver import merge_driver_review_cycle
from specify_cli.lanes.merge import _MERGE_DRIVERS, _merge_branch_into
from specify_cli.merge.config import MergeStrategy
from specify_cli.upgrade.migrations.m_3_2_7_review_cycle_merge_driver import (
    ReviewCycleMergeDriverMigration,
)

# Module-level marker convention (tests/architectural/test_pytest_marker_
# convention.py): most tests here shell out to real git; the pure in-process
# driver-decision tests additionally carry their own @pytest.mark.unit.
pytestmark = [pytest.mark.git_repo]

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[4]
_SRC_ROOT = _REPO_ROOT / "src"

_MISSION_SLUG = "coord-review-cycle-hazard-01ABCDEFGH"
_WP_ID = "WP01"
_REVIEW_CYCLE_REL_PATH = f"kitty-specs/{_MISSION_SLUG}/tasks/{_WP_ID}/review-cycle-1.md"
_REVIEW_CYCLE_ATTR_ENTRY = "kitty-specs/**/tasks/*/review-cycle-*.md merge=spec-kitty-review-cycle"

# The genuine first review cycle, landed on the PRIMARY partition (the
# target's own history) -- this is the record that must never be destroyed.
_TARGET_VERDICT = (
    "---\n"
    "cycle_number: 1\n"
    f"wp_id: {_WP_ID}\n"
    f"mission_slug: {_MISSION_SLUG}\n"
    "reviewer_agent: reviewer-rowan\n"
    "verdict: approved\n"
    "reviewed_at: '2026-08-01T10:00:00Z'\n"
    "affected_files: []\n"
    "reproduction_command: null\n"
    "---\n\n"
    "Genuine first-cycle review: approved. This is the real cycle 1.\n"
)

# The create-window bug's mis-numbered record: chronologically a LATER
# review, but re-numbered "1" because next_cycle_number globbed a worktree
# that had not yet materialized the earlier cycles (ADR 2026-08-03-1).
_MISCOUNTED_VERDICT = (
    "---\n"
    "cycle_number: 1\n"
    f"wp_id: {_WP_ID}\n"
    f"mission_slug: {_MISSION_SLUG}\n"
    "reviewer_agent: reviewer-rowan\n"
    "verdict: rejected\n"
    "reviewed_at: '2026-08-03T18:00:00Z'\n"
    "affected_files: []\n"
    "reproduction_command: null\n"
    "---\n\n"
    "Actually the 4th review cycle for this WP, mis-numbered '1' by the "
    "create-window next_cycle_number bug (the COORD worktree saw zero "
    "review-cycle files at the moment it was written).\n"
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
    """``git show <ref>:<rel_path>`` -- reads the blob straight from the ref,
    independent of whatever happens to be checked out in *repo*'s worktree."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{rel_path}"],
        cwd=str(repo), capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise AssertionError(f"git show {ref}:{rel_path} failed: {result.stderr}")
    return result.stdout


def _bootstrap_create_window_collision(repo: Path) -> str:
    """Build the exact T017 create-window collision.

    Base has NO ``review-cycle-1.md`` for this WP at all. The mission branch
    and ``main`` (the target) each ADD ``review-cycle-1.md`` independently,
    with genuinely different verdict content -- an add/add divergence, no
    common-ancestor blob for this path, matching the real hazard exactly
    (the coord mission's cycle-1 write lands on a DIFFERENT physical surface
    than the target's own genuine cycle-1).

    Returns the mission branch name; the target branch is always ``main``.
    """
    _init_repo(repo)
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")

    mission_branch = f"kitty/mission-{_MISSION_SLUG}"
    _git(repo, "branch", mission_branch)
    _git(repo, "checkout", "-q", mission_branch)
    review_path = repo / _REVIEW_CYCLE_REL_PATH
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(_MISCOUNTED_VERDICT, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "mission: cycle-1 write lands on COORD (create-window bug)")

    _git(repo, "checkout", "-q", "main")
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(_TARGET_VERDICT, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "target: genuine first review cycle")

    return mission_branch


# ---------------------------------------------------------------------------
# T077 -- driver decision branches, in-process (no subprocess/git overhead)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_merge_driver_review_cycle_identical_content_resolves_cleanly(tmp_path: Path) -> None:
    """Validation checklist: identical-content collision is a trivial fast
    path, never reported as a conflict."""
    base = tmp_path / "O"
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    base.write_text("", encoding="utf-8")
    ours.write_text(_TARGET_VERDICT, encoding="utf-8")
    theirs.write_text(_TARGET_VERDICT, encoding="utf-8")

    merge_driver_review_cycle(str(base), str(ours), str(theirs))  # must not raise

    merged = ours.read_text(encoding="utf-8")
    assert merged == _TARGET_VERDICT
    assert "<<<<<<<" not in merged


@pytest.mark.unit
def test_merge_driver_review_cycle_distinct_verdicts_embeds_both_without_raising(
    tmp_path: Path,
) -> None:
    """WP09/FR-014 re-pin: two distinct verdicts under one filename never
    produce a blended document -- both survive verbatim inside conflict
    markers, never interleaved -- but the driver no longer raises (the
    ``.md`` is non-authoritative, unread prose; the squash must proceed)."""
    base = tmp_path / "O"
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    base.write_text("", encoding="utf-8")
    ours.write_text(_TARGET_VERDICT, encoding="utf-8")
    theirs.write_text(_MISCOUNTED_VERDICT, encoding="utf-8")

    merge_driver_review_cycle(str(base), str(ours), str(theirs))  # must NOT raise

    merged = ours.read_text(encoding="utf-8")

    # Both documents survive byte-for-byte, as contiguous verbatim blocks --
    # not line-interleaved, not field-merged, not fabricated.
    ours_start = merged.index(_TARGET_VERDICT)
    theirs_start = merged.index(_MISCOUNTED_VERDICT)
    assert merged[ours_start : ours_start + len(_TARGET_VERDICT)] == _TARGET_VERDICT
    assert merged[theirs_start : theirs_start + len(_MISCOUNTED_VERDICT)] == _MISCOUNTED_VERDICT
    assert "<<<<<<< ours" in merged
    assert "=======" in merged
    assert ">>>>>>> theirs" in merged


@pytest.mark.unit
def test_merge_driver_review_cycle_missing_theirs_side_embeds_both_without_raising(
    tmp_path: Path,
) -> None:
    """WP09/FR-014 re-pin: a pure add-on-one-side (git would not normally
    invoke the driver for this, but the function must degrade sanely if it
    ever is): an absent side reads as empty text, so a real file vs. a
    genuinely absent file differ -- the driver still never silently picks a
    side (both are embedded, the absent side as an empty block), but no
    longer raises."""
    base = tmp_path / "O"
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    base.write_text("", encoding="utf-8")
    ours.write_text(_TARGET_VERDICT, encoding="utf-8")
    # theirs deliberately not created.

    merge_driver_review_cycle(str(base), str(ours), str(theirs))  # must NOT raise

    merged = ours.read_text(encoding="utf-8")
    assert _TARGET_VERDICT in merged
    assert "<<<<<<< ours" in merged
    assert ">>>>>>> theirs" in merged


# ---------------------------------------------------------------------------
# T078 -- .gitattributes pattern is filename-anchored, not directory-anchored
# ---------------------------------------------------------------------------


def _check_attr(repo: Path, rel_path: str) -> str:
    result = subprocess.run(
        ["git", "check-attr", "merge", "--", rel_path],
        cwd=str(repo), capture_output=True, text=True, check=True,
    )
    return result.stdout.strip().rsplit(": ", 1)[-1]


@pytest.mark.git_repo
def test_review_cycle_pattern_is_filename_anchored_not_directory_anchored(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / ".gitattributes").write_text(_REVIEW_CYCLE_ATTR_ENTRY + "\n", encoding="utf-8")
    _git(repo, "add", ".gitattributes")
    _git(repo, "commit", "-m", "attrs")

    assert (
        _check_attr(repo, "kitty-specs/m1/tasks/WP01/review-cycle-1.md")
        == "spec-kitty-review-cycle"
    )
    assert (
        _check_attr(repo, "kitty-specs/m1/tasks/WP01/review-cycle-12.md")
        == "spec-kitty-review-cycle"
    )
    # Negative case 1: the deliberately-PRIMARY, single-writer baseline
    # artifact living in the SAME per-wp directory must NOT be swept in.
    assert (
        _check_attr(repo, "kitty-specs/m1/tasks/WP01/baseline-tests.json") == "unspecified"
    )
    # Negative case 2: WP task files live directly under tasks/, never
    # nested under a per-wp subdirectory -- must also not be swept in.
    assert _check_attr(repo, "kitty-specs/m1/tasks/WP01.md") == "unspecified"


# ---------------------------------------------------------------------------
# T079 -- upgrade migration: idempotent, additive (never clobbers unrelated
# .gitattributes content)
# ---------------------------------------------------------------------------


@pytest.mark.git_repo
def test_migration_installs_driver_and_is_idempotent(tmp_path: Path) -> None:
    repo = tmp_path / "project"
    _init_repo(repo)
    migration = ReviewCycleMergeDriverMigration()

    assert migration.detect(repo) is True
    result1 = migration.apply(repo)
    assert result1.success is True
    assert result1.changes_made  # first run makes real changes
    assert migration.detect(repo) is False

    attributes = (repo / ".gitattributes").read_text(encoding="utf-8")
    assert _REVIEW_CYCLE_ATTR_ENTRY in attributes
    driver_value = _git(
        repo, "config", "--local", "--get", "merge.spec-kitty-review-cycle.driver"
    ).stdout.strip()
    assert driver_value == "spec-kitty merge-driver-review-cycle %O %A %B"

    # Idempotent: a second apply is a genuine no-op.
    result2 = migration.apply(repo)
    assert result2.success is True
    assert result2.changes_made == []


@pytest.mark.git_repo
def test_migration_preserves_unrelated_gitattributes_content(tmp_path: Path) -> None:
    """The migration is strictly additive -- an operator's pre-existing,
    unrelated .gitattributes lines are never rewritten or dropped."""
    repo = tmp_path / "project"
    _init_repo(repo)
    (repo / ".gitattributes").write_text("*.png binary\n", encoding="utf-8")

    ReviewCycleMergeDriverMigration().apply(repo)

    text = (repo / ".gitattributes").read_text(encoding="utf-8")
    assert "*.png binary" in text
    assert _REVIEW_CYCLE_ATTR_ENTRY in text


# ---------------------------------------------------------------------------
# T080 (C-011, red-first) -- the create-window clobber, through the REAL
# mission->target squash merge path
# ---------------------------------------------------------------------------


@pytest.mark.git_repo
@pytest.mark.non_sandbox  # shells out to `spec-kitty merge-driver-*` via git
def test_create_window_collision_fails_closed_without_driver_registered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#4892: without a driver to reconcile it, the create-window collision is
    now an ordinary content conflict — the squash must FAIL CLOSED, not clobber.

    Before #4892 the mission->target squash ran ``-X theirs``, so with the
    review-cycle driver EXCLUDED from the registry the target's genuine cycle-1
    verdict was silently overwritten by the mission branch's mis-numbered
    verdict (the #2804-shaped clobber this test used to pin). Dropping
    ``-X theirs`` turns that same collision into a normal unresolved conflict:
    ``_merge_branch_into`` raises and ``main`` never moves, so the target's
    verdict survives verbatim. This is the fail-closed contract the driver-
    present sibling test exercises the reconciling path for."""
    repo = tmp_path / "repo"
    mission_branch = _bootstrap_create_window_collision(repo)

    pre = _show(repo, "main", _REVIEW_CYCLE_REL_PATH)
    assert pre == _TARGET_VERDICT, "precondition: target must start with its genuine verdict"
    main_before = _git(repo, "rev-parse", "main").stdout.strip()

    without_review_cycle = tuple(
        spec for spec in _MERGE_DRIVERS if spec.config_key != "spec-kitty-review-cycle"
    )
    assert len(without_review_cycle) == len(_MERGE_DRIVERS) - 1, (
        "sanity: the review-cycle driver must actually be registered in "
        "_MERGE_DRIVERS for excluding it to mean anything"
    )
    monkeypatch.setattr("specify_cli.lanes.merge._MERGE_DRIVERS", without_review_cycle)

    with pytest.raises(RuntimeError) as excinfo:
        _merge_branch_into(repo, mission_branch, "main", strategy=MergeStrategy.SQUASH)
    assert _REVIEW_CYCLE_REL_PATH in str(excinfo.value), (
        "the fail-closed error must name the conflicting review-cycle artifact; "
        f"got: {excinfo.value!r}"
    )

    # main must NOT have advanced, and the target's genuine verdict must survive
    # verbatim — the whole point of failing closed instead of clobbering.
    assert _git(repo, "rev-parse", "main").stdout.strip() == main_before, (
        "target ref advanced despite an unresolved conflict — fail-closed broken"
    )
    post = _show(repo, "main", _REVIEW_CYCLE_REL_PATH)
    assert post == _TARGET_VERDICT, (
        f"the target's genuine verdict was not preserved verbatim. Got: {post!r}"
    )


@pytest.mark.git_repo
@pytest.mark.non_sandbox  # shells out to `spec-kitty merge-driver-*` via git
def test_driver_registered_embeds_both_verdicts_without_aborting_real_squash_merge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WP09/FR-014 re-pin of the T080 GREEN case: the SAME real merge path,
    with the review-cycle driver present in the real, unmodified
    ``_MERGE_DRIVERS`` registry. The driver no longer aborts the squash --
    both verdicts survive, embedded verbatim behind conflict markers, and
    ``main`` DOES advance (unlike the pre-WP09 refuse-fail-closed contract).

    ``PYTHONPATH`` is pinned to this lane's own ``src/`` (never inherited
    ambient ``PATH``/site-packages ordering): the spawned
    ``spec-kitty merge-driver-review-cycle`` subprocess must import THIS
    lane's ``specify_cli``, not whatever editable install happens to win on
    an unrelated ambient ``PATH`` (the exact hazard the sibling hermetic test
    below already guards against for the ``git merge`` direct-invocation
    path; this pins the same guarantee for ``_merge_branch_into``'s own
    subprocess plumbing)."""
    monkeypatch.setenv("PYTHONPATH", str(_SRC_ROOT))
    repo = tmp_path / "repo"
    mission_branch = _bootstrap_create_window_collision(repo)

    pre = _show(repo, "main", _REVIEW_CYCLE_REL_PATH)
    assert pre == _TARGET_VERDICT

    changed = _merge_branch_into(repo, mission_branch, "main", strategy=MergeStrategy.SQUASH)
    assert changed is True, "the squash must succeed (non-aborting driver)"

    post = _show(repo, "main", _REVIEW_CYCLE_REL_PATH)
    assert _TARGET_VERDICT in post, (
        "the target's genuine verdict must survive verbatim, embedded inside "
        f"the conflict-marked document. Got: {post!r}"
    )
    assert _MISCOUNTED_VERDICT in post, (
        "the incoming (mission-side) verdict must also survive verbatim -- "
        f"never lost/fabricated. Got: {post!r}"
    )
    assert "<<<<<<<" in post, "both verdicts must stay demarcated, never blended"


def _hermetic_driver_command_line() -> str:
    """An absolute-interpreter-path driver command this test builds itself --
    never bare ``spec-kitty`` on ``PATH``, never the ambient ``.git/config``.
    Mirrors the WP's own prescribed hermetic form
    (``sys.executable -m specify_cli ...``)."""
    return f"{shlex.quote(sys.executable)} -m specify_cli merge-driver-review-cycle %O %A %B"


def _hermetic_env() -> dict[str, str]:
    """An explicit env this test constructs itself (never inherited PATH
    ordering): ``PYTHONPATH`` points directly at THIS worktree's ``src/``,
    so ``python -m specify_cli`` resolves to this lane's code regardless of
    which clone's console script would otherwise win on an ambient PATH."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_SRC_ROOT)
    return env


@pytest.mark.git_repo
@pytest.mark.non_sandbox  # shells out to a real `python -m specify_cli` subprocess
def test_driver_registered_via_absolute_interpreter_path_survives_real_git_merge(
    tmp_path: Path,
) -> None:
    """T080 (fully hermetic variant), re-pinned by WP09/FR-014: registers the
    driver with an absolute interpreter path + explicit PYTHONPATH this test
    constructs itself (never relying on ambient ``.git/config`` or
    ``PATH``), then drives a genuine ``git merge --squash -X theirs``
    subprocess directly -- proving the driver's own (now non-aborting)
    behavior through git's real merge-driver contract, independent of
    ``_merge_branch_into``'s internal environment plumbing."""
    repo = tmp_path / "repo"
    mission_branch = _bootstrap_create_window_collision(repo)
    (repo / ".gitattributes").write_text(_REVIEW_CYCLE_ATTR_ENTRY + "\n", encoding="utf-8")
    _git(repo, "add", ".gitattributes")
    _git(repo, "commit", "-m", "attrs")

    _git(repo, "config", "merge.spec-kitty-review-cycle.name", "review-cycle test driver")
    _git(repo, "config", "merge.spec-kitty-review-cycle.driver", _hermetic_driver_command_line())

    result = subprocess.run(
        ["git", "merge", "--squash", "-X", "theirs", mission_branch],
        cwd=str(repo), capture_output=True, text=True, env=_hermetic_env(),
    )
    assert result.returncode == 0, (
        "expected the review-cycle driver to resolve WITHOUT aborting on a "
        f"genuine two-verdict collision (FR-014/D-PLAN-6); "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "review-cycle verdict collision" in result.stdout, result.stdout

    working_tree_content = (repo / _REVIEW_CYCLE_REL_PATH).read_text(encoding="utf-8")
    assert _TARGET_VERDICT in working_tree_content, (
        "the target's genuine verdict must survive verbatim, embedded inside "
        f"the conflict-marked document. Got: {working_tree_content!r}"
    )
    assert _MISCOUNTED_VERDICT in working_tree_content, (
        "the incoming (mission-side) verdict must also survive verbatim -- "
        f"never lost. Got: {working_tree_content!r}"
    )
    assert "<<<<<<<" in working_tree_content
    assert ">>>>>>>" in working_tree_content

    # main's own ref/blob (as opposed to the dirty conflicted working tree)
    # is untouched -- no commit was ever made.
    assert _show(repo, "main", _REVIEW_CYCLE_REL_PATH) == _TARGET_VERDICT
