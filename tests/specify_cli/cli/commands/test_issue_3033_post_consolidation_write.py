"""#3033 (P0): post-consolidation (E2) writes used to fail against a
deleted Target Ref.

Formerly a red-first ``@pytest.mark.regression`` reproduction (mission
``post-merge-write-authoring-finish-01KYRRM5`` WP02, FR-003, C-006,
SC-001/SC-002); relocated here and un-marked (landing fold: make
``@pytest.mark.regression`` mean exactly one thing) once WP03/WP04 wired
``TopologySurface.CONSOLIDATED`` write routing (FR-001..FR-004) and this
module started passing. #3033 is fixed — this same test file, unmodified,
is the acceptance evidence for that fix and is now a permanent guard, not a
red-first pin.

Terminology (binding, per spec.md "the ``merge`` footgun"):

* **Target Ref** = ``target_branch`` = the mission's own feature/consolidation
  branch (e.g. ``kitty/mission-<slug>``) -- NOT trunk.
* **Lane consolidation (E1)** -- ``spec-kitty merge`` folds lane branches into
  the Target Ref; ``baseline_merge_commit`` lands there durably.
* **Publish-to-trunk (E2)** -- the Target Ref is integrated into the
  **Primary Branch** (trunk / ``main``) via a real merge, then the Target Ref
  is deleted. The mission's content now lives only on the Primary Branch, in
  the repository-root checkout.

T005 builds a genuine E2 state through REAL entry points in an isolated git
repo (never mocked): ``record_baseline_merge_commit`` (the actual
``spec-kitty merge`` bookkeeping function) bakes ``baseline_merge_commit``
into ``meta.json`` on the Target Ref; a real ``git merge --no-ff`` publishes
that content to ``main`` (mirroring a GitHub PR merge commit); a real
``git branch -D`` deletes the Target Ref (and, for the T007 fixture, the
mission's coordination branch too) -- exactly what a mission's branch
cleanup leaves behind post-publish.

Two DISTINCT E2 fixtures are built (``_build_e2_mission_flat`` /
``_build_e2_mission_coord``), both genuinely E2 (``baseline_merge_commit``
present, Target Ref deleted, content on the Primary Branch) but with
different topologies -- this is deliberate, not an inconsistency:

* T006 needs a FLAT topology (no coordination branch) so the PRIMARY-kind
  placement resolves cleanly to the (now-deleted) Target Ref and the defect
  surfaces exactly where C-006 pins it: ``safe_commit``'s HEAD-vs-ref guard
  (``SafeCommitHeadMismatch``).
* T007 needs a COORD topology whose coordination branch has ALSO been
  deleted (a fully-retired mission, the realistic end state once a mission's
  lifecycle bookkeeping is durably on trunk) -- ``resolve_placement_only``
  unconditionally probes the coordination surface for EVERY kind (see
  ``mission_runtime.resolution._assemble_core_fragments`` ->
  ``_resolve_status_surface_dir``), so a coord-branch-deleted mission raises
  ``ActionContextError`` there (wrapping ``CoordinationBranchDeleted``)
  BEFORE any kind-specific placement decision -- which is exactly what
  ``write_seam.write_artifact`` maps to a ``"refused"`` result. Using the
  SAME (flat) topology as T006 would instead let the coord-kind write
  proceed past the probe and fail *inside* ``commit_for_mission`` with
  ``status="error"``, not ``"refused"`` -- the wrong pin for SC-002.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mission_runtime import (
    MissionArtifactKind,
    kind_for_mission_file,
    resolve_placement_only,
)
from specify_cli import app as cli_app
from specify_cli.coordination.write_seam import write_artifact
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.consolidation.baseline import record_baseline_merge_commit
from specify_cli.mission_metadata import load_meta, write_meta

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

runner = CliRunner()


# ---------------------------------------------------------------------------
# Real-git plumbing helpers (T005)
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args], cwd=repo)


def _init_git_repo(repo: Path) -> str:
    """Real ``git init`` on ``main``. Returns the initial commit SHA."""
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", "main", str(repo)], cwd=repo)
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.json").write_text("{}\n", encoding="utf-8")
    (repo / "README.md").write_text("# repo\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _branch_exists(repo: Path, branch: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=repo,
        capture_output=True,
    )
    return result.returncode == 0


def _current_branch(repo: Path) -> str:
    return _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo).stdout.strip()


def _write_meta(
    feature_dir: Path,
    *,
    mission_slug: str,
    mission_id: str,
    mid8: str,
    target_branch: str,
    topology: str,
    coordination_branch: str | None = None,
) -> None:
    meta: dict[str, object] = {
        "mission_slug": mission_slug,
        "mission_id": mission_id,
        "mid8": mid8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": target_branch,
        "topology": topology,
        "friendly_name": "Post-consolidation write regression fixture",
    }
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_wp_file(feature_dir: Path, wp_id: str) -> Path:
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    wp_path = tasks_dir / f"{wp_id}-record-post-consolidation-evidence.md"
    wp_path.write_text(
        "---\n"
        f"work_package_id: {wp_id}\n"
        f"title: {wp_id} record post-consolidation evidence\n"
        "agent: python-pedro\n"
        "review_status: approved\n"
        "---\n"
        f"# {wp_id}\n\nInitial scaffold.\n",
        encoding="utf-8",
    )
    return wp_path


def _write_issue_matrix_file(feature_dir: Path) -> Path:
    """A realistic, production-shaped ``issue-matrix.json`` (schema per
    ``specify_cli.tasks.issue_matrix``) -- the coord-partition artifact T007
    attempts to record."""
    matrix_path = feature_dir / "issue-matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "rows": {
                    "#4200": {
                        "verdict": "verified-already-fixed",
                        "evidence_ref": "commit <sha> (WP01)",
                        "title": "post-consolidation write surface (#3033)",
                        "scope": None,
                        "wp": "WP01",
                        "fr": "FR-003",
                        "nfr": None,
                        "sc": "SC-001",
                        "repo": None,
                    }
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return matrix_path


def _done_event(mission_slug: str, wp_id: str) -> dict[str, object]:
    return {
        "actor": "reviewer-renata",
        "at": "2026-07-30T12:00:00+00:00",
        "event_id": f"01HXYZ3033DONE00000000{wp_id}",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": mission_slug,
        "force": False,
        "from_lane": "approved",
        "reason": None,
        "review_ref": None,
        "to_lane": "done",
        "wp_id": wp_id,
    }


def _record_e1_consolidation(
    repo: Path,
    feature_dir: Path,
    *,
    mission_slug: str,
    mission_id: str,
    baseline_commit: str,
    mission_number: int,
) -> None:
    """Bake ``baseline_merge_commit`` via the REAL merge-bookkeeping entry
    point (:func:`record_baseline_merge_commit`, the exact function
    ``spec-kitty merge`` calls at E1), then assign ``mission_number`` (also
    real merge-time bookkeeping) and commit -- the terminal-completion
    evidence a consolidation produces (C-003 / D2)."""
    record_baseline_merge_commit(feature_dir, baseline_commit, mission_id=mission_id)
    meta = load_meta(feature_dir)
    assert meta is not None
    meta["mission_number"] = mission_number
    write_meta(feature_dir, meta, validate=False)
    _git(repo, "add", ".")
    _git(
        repo,
        "commit",
        "-m",
        f"chore({mission_slug}): record baseline_merge_commit + mission_number (E1 consolidation)",
    )


def _build_e2_mission_flat(repo: Path) -> tuple[str, Path, str]:
    """T005 (flat variant): a genuine E2 mission with FLAT topology (no
    coordination branch) -- the PRIMARY-kind fixture T006 needs.

    Returns ``(mission_slug, wp_file_path, target_branch)``.
    """
    mid8 = "01KYQR3F"
    mission_id = f"{mid8}0000000000000000"
    mission_slug = f"widget-catalog-hardening-{mid8}"
    target_branch = f"kitty/mission-{mission_slug}"
    wp_id = "WP01"

    init_sha = _init_git_repo(repo)

    # E1 groundwork: the mission's own consolidation branch (Target Ref)
    # forks from the Primary Branch, exactly as `mission create` does.
    _git(repo, "checkout", "-q", "-b", target_branch)
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mid8=mid8,
        target_branch=target_branch,
        topology="single_branch",
    )
    wp_path = _write_wp_file(feature_dir, wp_id)
    (feature_dir / "status.events.jsonl").write_text(json.dumps(_done_event(mission_slug, wp_id), sort_keys=True) + "\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): mission scaffold")

    # E1: lane consolidation lands baseline_merge_commit + mission_number.
    _record_e1_consolidation(
        repo,
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        baseline_commit=init_sha,
        mission_number=214,
    )

    # E2: publish-to-trunk -- a real merge commit (mirrors a GitHub PR merge)
    # into the Primary Branch, then the Target Ref is deleted.
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", target_branch, "-m", f"Merge {target_branch}")
    _git(repo, "branch", "-D", target_branch)

    return mission_slug, wp_path, target_branch


def _build_e2_mission_coord(repo: Path) -> tuple[str, str, str]:
    """T005 (coord variant): a genuine E2 mission whose COORD topology
    coordination branch has ALSO been retired -- the fixture T007 needs.

    Returns ``(mission_slug, target_branch, coordination_branch)``.
    """
    mid8 = "01KYQR9C"
    mission_id = f"{mid8}0000000000000000"
    mission_slug = f"invoice-export-retry-{mid8}"
    target_branch = f"kitty/mission-{mission_slug}"
    coordination_branch = f"kitty/mission-{mission_slug}-coord"
    wp_id = "WP01"

    init_sha = _init_git_repo(repo)

    _git(repo, "checkout", "-q", "-b", target_branch)
    # Real coordination-branch materialization, mirroring `mission create`
    # minting the mission's coord branch alongside its Target Ref.
    _git(repo, "branch", coordination_branch, target_branch)

    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mid8=mid8,
        target_branch=target_branch,
        topology="coord",
        coordination_branch=coordination_branch,
    )
    _write_wp_file(feature_dir, wp_id)
    _write_issue_matrix_file(feature_dir)
    (feature_dir / "status.events.jsonl").write_text(json.dumps(_done_event(mission_slug, wp_id), sort_keys=True) + "\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): mission scaffold")

    _record_e1_consolidation(
        repo,
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        baseline_commit=init_sha,
        mission_number=217,
    )

    # Coordination-branch lifecycle cleanup: the coord worktree/branch is
    # retired once the mission's lifecycle bookkeeping is durably folded into
    # the Target Ref -- the same cleanup `spec-kitty merge` performs.
    _git(repo, "branch", "-D", coordination_branch)

    # E2: publish-to-trunk + Target Ref deletion.
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", target_branch, "-m", f"Merge {target_branch}")
    _git(repo, "branch", "-D", target_branch)

    return mission_slug, target_branch, coordination_branch


# ---------------------------------------------------------------------------
# T006 (SC-001): PRIMARY-kind safe-commit on an E2 mission
# ---------------------------------------------------------------------------


def test_safe_commit_succeeds_for_primary_kind_write_on_e2_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression guard for the fixed #3033 defect (T006 / SC-001 / C-006).

    On a genuine E2 mission (consolidated then published-to-trunk, Target Ref
    deleted), running the pre-existing ``spec-kitty safe-commit`` on a
    classified PRIMARY artifact from the repository-root checkout on the
    Primary Branch commits cleanly (exit 0).

    Was RED before the fix: ``resolve_placement_only`` had no CONSOLIDATED
    wiring (FR-001..003, WP03/WP04), so it handed back the deleted Target Ref
    for a PRIMARY-kind artifact -- both the seam-level resolution and the
    CLI-level commit failed at exactly the HEAD-vs-ref guard C-006 names
    (``SafeCommitHeadMismatch``), never an unrelated error. #3033 is now
    fixed and this same test, unmodified, is the permanent SC-001 acceptance
    guard.
    """
    monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)

    repo = tmp_path / "repo"
    mission_slug, wp_path, target_branch = _build_e2_mission_flat(repo)
    feature_dir = repo / "kitty-specs" / mission_slug

    # Sanity: this really is a genuine E2 state.
    meta = load_meta(feature_dir)
    assert meta is not None
    assert meta["baseline_merge_commit"], meta
    assert meta["mission_number"] == 214, meta
    assert not _branch_exists(repo, target_branch), "Target Ref must be deleted for a genuine E2 fixture"
    assert _current_branch(repo) == "main", "must run from the repository-root checkout on the Primary Branch"
    assert (feature_dir / "meta.json").exists()

    # Seam-level pin ("for the right reason"): the CommitTarget a PRIMARY-kind
    # write resolves to must actually EXIST in git. TODAY it resolves the
    # deleted Target Ref verbatim (no existence check, no lifecycle
    # awareness) -- this assertion fails today, naming the stale ref.
    kind = kind_for_mission_file(wp_path.relative_to(repo), mission_slug=mission_slug)
    assert kind is MissionArtifactKind.WORK_PACKAGE_TASK, kind
    resolved = resolve_placement_only(repo, mission_slug, kind=kind)
    assert _branch_exists(repo, resolved.ref), (
        f"resolve_placement_only resolved {resolved.ref!r} for a genuine E2 "
        f"mission -- that ref no longer exists in git (the deleted Target "
        f"Ref {target_branch!r}, handed back verbatim). Per #3033 the fix "
        f"wires TopologySurface.CONSOLIDATED so this resolves to the "
        f"repository-root checkout instead."
    )

    # A real, uncommitted evidence write on the PRIMARY artifact.
    wp_path.write_text(
        wp_path.read_text(encoding="utf-8") + "\nEvidence recorded post-consolidation.\n",
        encoding="utf-8",
    )

    # CLI-level pin (C-006's literal repro path): `spec-kitty safe-commit`
    # from the repository-root checkout should commit cleanly. No
    # `--to-branch` is passed -- passing it would short-circuit resolution
    # through the mission-aware seam entirely and mask the defect.
    monkeypatch.chdir(repo)
    result = runner.invoke(
        cli_app,
        [
            "safe-commit",
            "--message",
            f"chore({mission_slug}): record evidence",
            "--json",
            str(wp_path.relative_to(repo)),
        ],
        catch_exceptions=False,
    )

    payload = json.loads(result.stdout)
    # TODAY: exit_code == 1, success is False, and payload["error"] carries
    # the SafeCommitHeadMismatch message ("HEAD is 'main', expected
    # '<target_branch>'") -- the assertion failure below surfaces that text
    # directly, proving the red is for the HEAD-guard reason, not a crash.
    assert result.exit_code == 0, payload
    assert payload["success"] is True, payload
    assert payload["committed"] is True, payload


# ---------------------------------------------------------------------------
# T007 (SC-002): coord-kind write_seam on an E2 mission
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "entry_id"),
    [
        (MissionArtifactKind.ISSUE_MATRIX, "#4200"),
        (MissionArtifactKind.TRACER_FILE, "trace-4200"),
        (MissionArtifactKind.ACCEPTANCE_MATRIX, "AC-001"),
    ],
)
def test_write_artifact_succeeds_for_coord_kind_write_on_e2_mission(tmp_path: Path, kind: MissionArtifactKind, entry_id: str) -> None:
    """Regression guard for the fixed #3033 defect (T007 / SC-002).

    On a genuine E2 mission whose COORD topology coordination branch has
    ALSO been retired, ``write_artifact`` for a coord-partition kind
    (issue-matrix / tracer / acceptance-matrix) returns a ``"committed"``
    result on the CONSOLIDATED surface.

    Was RED before the fix: the seam's unconditional coordination-surface
    probe (``mission_runtime.resolution._assemble_core_fragments`` ->
    ``_resolve_status_surface_dir`` -> ``resolve_status_surface``) raised
    ``CoordinationBranchDeleted`` (a ``StatusReadPathNotFound`` subclass),
    wrapped into ``ActionContextError`` and propagated out of
    ``resolve_placement_only`` -- the unroutable-target condition
    ``write_seam.write_artifact`` mapped to a zero-write ``"refused"``
    result that explicitly named #3033 in its diagnostic (asserted below).
    #3033 is now fixed and this same test, unmodified, is the permanent
    SC-002 acceptance guard.
    """
    repo = tmp_path / "repo"
    mission_slug, target_branch, coordination_branch = _build_e2_mission_coord(repo)
    feature_dir = repo / "kitty-specs" / mission_slug

    # Sanity: this really is a genuine E2 state -- BOTH the Target Ref and
    # the coordination branch have been deleted from git.
    meta = load_meta(feature_dir)
    assert meta is not None
    assert meta["baseline_merge_commit"], meta
    assert meta["mission_number"] == 217, meta
    assert not _branch_exists(repo, target_branch), "Target Ref must be deleted for a genuine E2 fixture"
    assert not _branch_exists(repo, coordination_branch), "coordination branch must be deleted for this fixture's mechanism"
    assert _current_branch(repo) == "main"

    policy = ProtectionPolicy.resolve(repo)
    assert (feature_dir / "issue-matrix.json").exists()
    # Stage GENUINELY-NEW per-kind content (T007/SC-002 re-pin, 2026-07-30):
    # the prior fixture passed the already-committed ``issue-matrix.json``, whose
    # bytes were identical to what the E1->E2 merge put on ``main``, so the E2
    # write was an idempotent no-op that correctly returns ``"unchanged"``. To
    # exercise the genuine post-fix ``"committed"`` outcome, stage a fresh per-kind
    # file absent from ``main`` (reviewer-renata confirmed the no-op reading empirically).
    write_path = feature_dir / f"{kind.value.replace('_', '-')}-{entry_id.lstrip('#')}.e2probe.json"
    write_path.write_text(
        json.dumps({"kind": kind.value, "entry_id": entry_id, "e2_probe": True}) + "\n",
        encoding="utf-8",
    )

    result = write_artifact(
        repo_root=repo,
        mission_slug=mission_slug,
        kind=kind,
        files=(write_path,),
        message=f"chore({mission_slug}): record {kind.value}",
        policy=policy,
        entry_id=entry_id,
    )

    # Post-fix: the E2 write reaches the CONSOLIDATED surface (destination 'main')
    # and commits the genuinely-new content -> status "committed" (SC-002).
    assert result.status == "committed", result
    assert result.entry_id == entry_id
    assert result.destination_surface is not None, result
