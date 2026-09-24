"""WP08 coherence-integrity owner tests: SHA-scoped strand heal + topology residue.

Two coupled defects, one owner (``coordination.coherence``):

* **#4973 (FR-005 / D4 S-B)** — the strand heal must revert ONLY the strand's own
  recorded commits, never a content-blind ``git revert captured_sha..HEAD`` RANGE
  that also reverts (and thereby erases) a third party's later commit landed in the
  same range on the append-only coordination log.
* **#4978 (FR-009 / C-3 / D8)** — ``is_coord_residue_churn`` must classify against
  the mission's STORED topology: a coord-partition-KIND artifact is coordination
  residue ONLY under a coord-routing topology; on a lanes/single_branch mission it
  is real work, never residue to be ``reset --hard``ed.

Real git fixtures, no git-layer / subprocess mocking (RN-Q3): the heal drives the
actual ``repair_coord_strand`` primitive against a materialized coord worktree, and
the classifier is exercised through its public entry points.

Import ``specify_cli.status`` before any coordination submodule to mirror the
production import order and avoid the ``coordination -> transaction -> status``
init-order cycle when a test module imports coordination first.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import specify_cli.status  # noqa: F401  # import-order guard (see module docstring)
from mission_runtime import MissionTopology
from specify_cli.coordination.coherence import (
    CoordRepairOutcome,
    coord_incoherent_done_wps,
    is_coord_residue_churn,
    is_toolchain_generated_churn,
    repair_coord_strand,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

MISSION_SLUG = "terminus-coherence-integ-01KXTM60"
_THIRD_PARTY_FILE = "THIRD_PARTY.txt"
_THIRD_PARTY_BODY = "independent third-party later coord work\n"


# ---------------------------------------------------------------------------
# Git helpers (self-contained, no mocking)
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-qb", "main", str(repo)], check=True, capture_output=True)
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


def _event(wp_id: str, to_lane: str, *, at: str, event_id: str, from_lane: str) -> dict[str, object]:
    return {
        "actor": "reviewer-renata",
        "at": at,
        "event_id": event_id,
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": MISSION_SLUG,
        "force": False,
        "from_lane": from_lane,
        "reason": None,
        "review_ref": None,
        "to_lane": to_lane,
        "wp_id": wp_id,
    }


def _write_meta(feature_dir: Path) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": MISSION_SLUG,
                "mission_id": "01KXTM60000000000000000000",
                "mission_number": None,
                "mission_type": "software-dev",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_events(feature_dir: Path, events: list[dict[str, object]]) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "status.events.jsonl").write_text(
        "".join(json.dumps(e, sort_keys=True) + "\n" for e in events),
        encoding="utf-8",
    )


def _seed_committed_coord_ref(repo: Path, events: list[dict[str, object]], *, branch: str = "coord") -> Path:
    """Commit ``events`` onto ``branch`` and return the primary feature_dir."""
    _init_repo(repo)
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    _write_meta(feature_dir)
    _write_events(feature_dir, events)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "seed coord events")
    _git(repo, "branch", branch)
    return feature_dir


def _append_done_commit(worktree: Path, wp_id: str, *, event_id: str) -> None:
    """Bake a stranding ``done`` event onto the coord worktree (touches the log)."""
    wt_events = worktree / "kitty-specs" / MISSION_SLUG / "status.events.jsonl"
    with wt_events.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                _event(wp_id, "done", at="2026-09-24T10:05:00+00:00", event_id=event_id, from_lane="approved"),
                sort_keys=True,
            )
            + "\n"
        )
    _git(worktree, "add", ".")
    _git(worktree, "commit", "-m", f"bake {wp_id} done (strands on rollback)")


def _blob_present(repo: Path, ref: str, path: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(repo), "cat-file", "-e", f"{ref}:{path}"],
            capture_output=True,
            text=True,
            check=False,
        ).returncode
        == 0
    )


# ---------------------------------------------------------------------------
# #4973 — SHA-scoped strand heal preserves a third party's later event
# ---------------------------------------------------------------------------


def test_strand_heal_reverts_only_recorded_sha_and_third_party_event_survives(
    tmp_path: Path,
) -> None:
    """The heal reverts ONLY the strand's own commit; a later third-party commit
    landed in ``captured_sha..HEAD`` (that did NOT touch the status log) survives.

    A content-blind ``git revert captured_sha..HEAD`` RANGE revert would revert the
    third-party commit too and erase ``THIRD_PARTY.txt`` — the #4973 defect. The
    SHA-scoped heal reverts only the ``done`` bookkeeping commit that touched the
    append-only log, so the third party's later event is preserved.
    """
    repo = tmp_path / "repo"
    feature_dir = _seed_committed_coord_ref(
        repo,
        [_event("WP-A", "approved", at="2026-09-24T10:00:00+00:00", event_id="01A00", from_lane="in_review")],
    )
    captured_sha = _git(repo, "rev-parse", "coord").stdout.strip()

    worktree = tmp_path / "coord-wt"
    _git(repo, "worktree", "add", str(worktree), "coord")

    # 1) the strand's OWN commit: a stranding ``done`` on the append-only log.
    _append_done_commit(worktree, "WP-A", event_id="01A01")
    strand_sha = _git(worktree, "rev-parse", "HEAD").stdout.strip()

    # 2) an INDEPENDENT third party appends a LATER commit that does NOT touch the
    #    status log (an unrelated coord artifact) — committed AFTER the strand.
    (worktree / _THIRD_PARTY_FILE).write_text(_THIRD_PARTY_BODY, encoding="utf-8")
    _git(worktree, "add", ".")
    _git(worktree, "commit", "-m", "third-party later coord event")
    third_party_sha = _git(worktree, "rev-parse", "HEAD").stdout.strip()
    assert third_party_sha != strand_sha

    # Pre-condition: WP-A is stranded done on the committed ref.
    assert coord_incoherent_done_wps("coord", ["WP-A"], repo_root=repo, feature_dir=feature_dir) == ["WP-A"]

    outcome = repair_coord_strand(
        coord_ref="coord",
        captured_sha=captured_sha,
        coord_worktree=worktree,
        candidate_wps=["WP-A"],
        repo_root=repo,
        feature_dir=feature_dir,
    )

    assert isinstance(outcome, CoordRepairOutcome)
    assert outcome.healed is True
    assert outcome.stranded_wp_ids == ["WP-A"]
    assert outcome.error is None

    # The strand is healed — WP-A is coherent (back to approved) on the ref.
    assert coord_incoherent_done_wps("coord", ["WP-A"], repo_root=repo, feature_dir=feature_dir) == []

    # The third party's later event SURVIVES: both the commit is reachable and its
    # content is intact on the coordination branch (a range revert would erase it).
    assert _blob_present(repo, "coord", _THIRD_PARTY_FILE), "SHA-scoped heal erased a third party's later coord event (#4973)"
    assert (worktree / _THIRD_PARTY_FILE).read_text(encoding="utf-8") == _THIRD_PARTY_BODY


def test_strand_heal_preserves_append_only_log_via_new_revert_commit(tmp_path: Path) -> None:
    """The heal APPENDS a revert commit — it never rewrites the log's history.

    HEAD strictly advances (a new commit) and the pre-heal ``done`` commit stays
    reachable in history; the append-only invariant holds.
    """
    repo = tmp_path / "repo"
    feature_dir = _seed_committed_coord_ref(
        repo,
        [_event("WP-A", "approved", at="2026-09-24T10:00:00+00:00", event_id="01A00", from_lane="in_review")],
    )
    captured_sha = _git(repo, "rev-parse", "coord").stdout.strip()

    worktree = tmp_path / "coord-wt"
    _git(repo, "worktree", "add", str(worktree), "coord")
    _append_done_commit(worktree, "WP-A", event_id="01A01")
    strand_sha = _git(worktree, "rev-parse", "HEAD").stdout.strip()

    outcome = repair_coord_strand(
        coord_ref="coord",
        captured_sha=captured_sha,
        coord_worktree=worktree,
        candidate_wps=["WP-A"],
        repo_root=repo,
        feature_dir=feature_dir,
    )
    assert outcome.healed is True

    head_after = _git(worktree, "rev-parse", "HEAD").stdout.strip()
    assert head_after != strand_sha  # a NEW revert commit was appended
    # The original done commit is still reachable — history was not rewritten.
    ancestry = subprocess.run(
        ["git", "-C", str(worktree), "merge-base", "--is-ancestor", strand_sha, head_after],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ancestry.returncode == 0


# ---------------------------------------------------------------------------
# #4978 — topology-aware residue classification
# ---------------------------------------------------------------------------

# Coord-partition-KIND planning artifacts: residue ONLY under a coord topology.
_COORD_KIND_ARTIFACTS = (
    "issue-matrix.md",
    "status.events.jsonl",
    "traces/tracer.md",
    "decisions/DM-01KXTM60000000000000000000.md",
)


def _rel(basename: str) -> str:
    return f"kitty-specs/{MISSION_SLUG}/{basename}"


@pytest.mark.parametrize("basename", _COORD_KIND_ARTIFACTS)
def test_coord_kind_artifact_is_not_residue_under_lanes_or_single_branch(basename: str) -> None:
    """On a lanes/single_branch mission a coord-partition-KIND planning artifact is
    NOT coordination residue — so the merge dirty gate never ``reset --hard``s it."""
    path = _rel(basename)
    assert is_coord_residue_churn(path, mission_slug=MISSION_SLUG, topology=MissionTopology.LANES) is False
    assert is_coord_residue_churn(path, mission_slug=MISSION_SLUG, topology=MissionTopology.SINGLE_BRANCH) is False


@pytest.mark.parametrize("basename", _COORD_KIND_ARTIFACTS)
def test_coord_kind_artifact_is_residue_under_coord_topologies(basename: str) -> None:
    """Under a coord-routing topology the same artifact IS coordination residue —
    the pre-#4978 behaviour is preserved for genuine coord missions."""
    path = _rel(basename)
    assert is_coord_residue_churn(path, mission_slug=MISSION_SLUG, topology=MissionTopology.COORD) is True
    assert is_coord_residue_churn(path, mission_slug=MISSION_SLUG, topology=MissionTopology.LANES_WITH_COORD) is True


@pytest.mark.parametrize("basename", _COORD_KIND_ARTIFACTS)
def test_topology_default_is_explicit_backward_compatible_coord(basename: str) -> None:
    """The ``topology`` default is an EXPLICIT, overridable COORD projection — it
    keeps every pre-C-3 (inherently coord-context) caller's behaviour unchanged."""
    path = _rel(basename)
    assert is_coord_residue_churn(path, mission_slug=MISSION_SLUG) is True


def test_primary_kind_artifact_is_never_residue_under_any_topology() -> None:
    """A PRIMARY-partition artifact (spec.md) is never coordination residue — a
    control proving the fix flips ONLY the coord-less topology cells."""
    path = _rel("spec.md")
    for topology in MissionTopology:
        assert is_coord_residue_churn(path, mission_slug=MISSION_SLUG, topology=topology) is False
    assert is_coord_residue_churn(path, mission_slug=MISSION_SLUG) is False


def test_toolchain_union_threads_topology_into_residue_leg() -> None:
    """``is_toolchain_generated_churn`` forwards the stored topology to its
    coord-residue leg: issue-matrix churn is toolchain-generated under COORD but
    real work under LANES; self-bookkeeping (meta.json) stays topology-independent."""
    issue_matrix = _rel("issue-matrix.md")
    assert is_toolchain_generated_churn(issue_matrix, mission_slug=MISSION_SLUG, topology=MissionTopology.COORD) is True
    assert is_toolchain_generated_churn(issue_matrix, mission_slug=MISSION_SLUG, topology=MissionTopology.LANES) is False
    # meta.json is self-bookkeeping churn regardless of topology (control leg).
    meta = _rel("meta.json")
    assert is_toolchain_generated_churn(meta, topology=MissionTopology.COORD) is True
    assert is_toolchain_generated_churn(meta, topology=MissionTopology.LANES) is True
