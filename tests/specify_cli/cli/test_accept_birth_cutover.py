"""WP02 (runtime-state-birth-cutover-all-paths-01KYH654): auto-stamp the
birth-cutover into the mission branch at the terminal ``accept`` seam so the
committed corpus is already cut over before the branch can land by ANY path
-- closing the GitHub-squash/rebase leak (#2917 reopened,
``contracts/stamp-seam.md`` / IC-01).

Three acceptance tests per the WP's own Test Strategy / contract:

* **US1 GitHub-squash simulation (T009)** -- finalize a mission, run the real
  ``accept`` command (which now stamps + commits both partitions), then
  simulate a GitHub-style SQUASH merge into a fresh target branch using
  PLAIN GIT ONLY (``git merge --squash`` -- no ``spec-kitty merge`` anywhere
  in this test) -- and assert the corpus on the TARGET branch is cut over
  (``data-model.md``'s definition) with no post-merge step.
* **Idempotency (T010 / FR-006)** -- re-running the stamp on an
  already-cut-over mission is a no-op: byte-identical
  ``status.events.jsonl``, no error.
* **Fail-closed (T008 / NFR-003 / R6)** -- an absent ``mission_id`` refuses
  to stamp (raises, non-zero), and writes no seed events at all.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.acceptance.matrix import (
    AcceptanceCriterion,
    AcceptanceMatrix,
    write_acceptance_matrix,
)
from specify_cli.cli.commands.accept import accept
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
# The shared tests and helper live once, in the home this suite's always-on lift
# also imports (#5015); importing a test here is what makes pytest collect it.
from tests.architectural._lifted_cli_accept_birth_cutover import (
    _read_events,
)
from tests.architectural._lifted_cli_accept_birth_cutover import (
    test_accept_stamp_fails_closed_when_mission_id_absent as test_accept_stamp_fails_closed_when_mission_id_absent,
)
from tests.architectural._lifted_cli_accept_birth_cutover import (
    test_accept_stamp_idempotent_rerun_is_byte_identical as test_accept_stamp_idempotent_rerun_is_byte_identical,
)

# Cross-test-module reuse of private helpers is an established pattern in this
# suite (e.g. ``tests/migration/test_birth_cutover.py``'s own docstring notes
# ``tests/merge/test_executor_coord_reconcile.py`` importing from
# ``tests/merge/test_issue_2367_bake_strand.py``). Reused here rather than
# re-deriving the exact real event-sourced claim/subtask-completion/approval
# sequence the guard predicate (``_mission_carries_event_log_runtime``)
# actually requires.
from tests.migration.test_birth_cutover import (
    _claim_real,
    _drive_claimed_through_approved,
    _mark_subtask_done,
    _seed_planned,
    _write_wp01_with_subtask,
)
from tests.specify_cli.test_specify_topology_flag import _git

pytestmark = [pytest.mark.non_sandbox, pytest.mark.git_repo]

_SLUG = "accept-birth-cutover-demo"
_MISSION_ID = "01KYH654ACCEPTBIRTHCUTOVR1"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"
_TARGET_BRANCH = "main"


def _porcelain(repo_root: Path) -> str:
    return _git(repo_root, "status", "--porcelain").stdout


def _read_meta(feature_dir: Path) -> dict[str, object]:
    data: dict[str, object] = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    return data


def _init_repo(tmp_path: Path) -> Path:
    """A real, minimal Spec Kitty project root (git + ``.kittify`` marker)."""
    repo = tmp_path / "project"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", _TARGET_BRANCH)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test Runner")
    _git(repo, "config", "commit.gpgsign", "false")
    kittify = repo / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        "project_slug: accept-birth-cutover\nprotection:\n  protected_branches: []\n",
        encoding="utf-8",
    )
    (repo / "kitty-specs").mkdir()
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    # Software Dev Kitty's path-convention check (accept's readiness gate)
    # expects these workspace dirs to exist.
    for required_dir in ("src", "tests", "contracts", "docs"):
        path = repo / required_dir
        path.mkdir()
        (path / ".gitkeep").write_text("")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "chore: bootstrap spec-kitty project")
    return repo


def _build_accept_ready_mission(repo: Path) -> Path:
    """A real, flat (single-branch-shaped) mission ready for ``accept``.

    WP01 is born-reconciled (``_write_wp01_with_subtask``'s shape -- no
    legacy ``agent``/``shell_pid`` frontmatter) with its runtime driven
    ENTIRELY through the real event-sourced pipeline (seed planned, claim,
    subtask-completion, approval) -- the exact T042 shape
    ``tests/migration/test_birth_cutover.py`` already proves produces
    genuine event-log evidence (``_mission_carries_event_log_runtime``) via
    the subtask-completion ``InnerStateChanged`` annotation, and satisfies
    ``_ACCEPTED_READY_LANES`` (``approved``/``done``).
    """
    feature_dir = repo / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)

    meta = {
        "slug": _SLUG,
        "mission_slug": _SLUG,
        "mission_id": _MISSION_ID,
        "mid8": _MISSION_ID[:8],
        "friendly_name": "Accept Birth Cutover Demo",
        "mission_type": "software-dev",
        "target_branch": _TARGET_BRANCH,
        "created_at": "2026-01-01T00:00:00Z",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    for fname in ("spec.md", "plan.md"):
        (feature_dir / fname).write_text(f"# {fname}\nDone.\n", encoding="utf-8")

    # Writes tasks/WP01-root.md (agent="" -- no legacy evictable state) +
    # tasks.md with a real T001 subtask row.
    _write_wp01_with_subtask(feature_dir)

    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=_SLUG,
            mission_id=_SLUG,
            mission_branch=_MISSION_BRANCH,
            target_branch=_TARGET_BRANCH,
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01",),
                    write_scope=("src/**",),
                    predicted_surfaces=("test",),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-04-05T12:00:00Z",
            computed_from="test",
        ),
    )

    write_acceptance_matrix(
        feature_dir,
        AcceptanceMatrix(
            mission_slug=_SLUG,
            criteria=[
                AcceptanceCriterion(
                    criterion_id="AC1",
                    description="mission behaves as specified",
                    proof_type="automated_test",
                    pass_fail="pass",
                )
            ],
            negative_invariants=[],
        ),
    )

    _seed_planned(feature_dir, _SLUG, "WP01")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"chore({_SLUG}): finalize WP01")

    _claim_real(repo, _SLUG, "WP01")
    _mark_subtask_done(repo, _SLUG, "T001")
    _drive_claimed_through_approved(repo, _SLUG, "WP01")

    _git(repo, "add", "-A")
    diff_check = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--quiet"], capture_output=True
    )
    if diff_check.returncode != 0:
        _git(repo, "commit", "-q", "-m", f"chore({_SLUG}): WP01 runtime bookkeeping residue")

    _git(repo, "checkout", "-q", "-b", _MISSION_BRANCH)
    return feature_dir


def _run_accept(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo))
    monkeypatch.chdir(repo)
    accept(
        mission=_SLUG,
        mode="local",
        actor="tester",
        test=[],
        json_output=False,
        # WP01 is claimed through the real event-sourced pipeline without a
        # shell_pid/agent-carrying policy_metadata sidecar (this test is not
        # exercising the strict-metadata gate) -- lenient skips that check so
        # the birth-cutover stamp under test actually gets reached.
        lenient=True,
        no_commit=False,
        diagnose=False,
        allow_fail=False,
    )


def _assert_cut_over(feature_dir: Path) -> None:
    """The data-model.md ``status_phase``/event-log slice of "cut over"."""
    meta = _read_meta(feature_dir)
    assert meta.get("status_phase") == "1", (
        f"expected status_phase == '1' post-stamp, got {meta.get('status_phase')!r}"
    )
    events_text = _read_events(feature_dir)
    assert events_text.strip(), "expected a non-empty status.events.jsonl post-stamp"


def test_squash_merge_after_accept_lands_cut_over_corpus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """US1: accept stamps + commits the cutover on the mission branch; a plain
    ``git merge --squash`` (NO ``spec-kitty merge`` anywhere) into a fresh
    target branch lands an already-cut-over corpus, with no post-merge step.
    """
    repo = _init_repo(tmp_path)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo))
    monkeypatch.chdir(repo)
    feature_dir = _build_accept_ready_mission(repo)

    _run_accept(repo, monkeypatch)

    # Precondition: the mission branch itself is genuinely stamped + clean.
    assert _porcelain(repo) == "", f"accept left a dirty tree:\n{_porcelain(repo)}"
    _assert_cut_over(feature_dir)
    mission_branch_events = _read_events(feature_dir)

    # Simulate a GitHub-style squash merge: plain git only, back on the
    # mission's OWN target branch, no spec-kitty command in sight.
    _git(repo, "checkout", "-q", _TARGET_BRANCH)
    squash = subprocess.run(
        ["git", "-C", str(repo), "merge", "--squash", _MISSION_BRANCH],
        capture_output=True,
        text=True,
    )
    assert squash.returncode == 0, f"git merge --squash failed: {squash.stdout}\n{squash.stderr}"
    _git(repo, "commit", "-q", "-m", f"Squash-merge {_MISSION_BRANCH} into {_TARGET_BRANCH}")

    # No post-merge step of any kind runs here -- the assertions below read
    # exactly what the squash commit landed.
    _assert_cut_over(feature_dir)
    assert _read_events(feature_dir) == mission_branch_events, (
        "the squash-merged target branch's event log must be byte-identical "
        "to what accept already stamped on the mission branch"
    )


