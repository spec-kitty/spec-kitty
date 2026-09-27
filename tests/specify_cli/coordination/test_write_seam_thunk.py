"""WP04 (#3033 T018) -- write-seam staging thunk + off-checkout refusal regressions.

Mission ``post-merge-write-authoring-finish-01KYRRM5`` WP04 (FR-003/004/005/006).
Covers what the WP02 red-first pins (``tests/regression/
test_issue_3033_post_consolidation_write.py``) do NOT: the T014 thunk
mutual-exclusion guard, SC-003 (refused write leaves zero residue), SC-004
(off-checkout refuse-with-recovery, no forced checkout), SC-009 (``review
--mode post-merge`` exits 0 end-to-end on a genuine E2 mission), and the
probe/commit phase-agreement invariant (NFR-001).

Real-git fixtures throughout (never mocked), mirroring WP02's own
``_build_e2_mission_*`` pattern -- a genuine E2 state is constructed through
real entry points (``record_baseline_merge_commit``, real ``git merge``/
``git branch -D``), not synthesized meta.json fields in isolation.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mission_runtime import MissionArtifactKind
from specify_cli import app as cli_app
from specify_cli.coordination.write_seam import (
    WriteSeamUsageError,
    is_post_consolidation_write_target,
    write_artifact,
)
from specify_cli.core.git_ops import resolve_primary_branch
from specify_cli.core.paths import get_main_repo_root
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.merge.baseline import record_baseline_merge_commit
from specify_cli.mission_metadata import load_meta, write_meta

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

runner = CliRunner()


# ---------------------------------------------------------------------------
# Real-git plumbing helpers (mirrors WP02's test_issue_3033_post_consolidation_write.py)
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args], cwd=repo)


def _init_git_repo(repo: Path) -> str:
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


def _current_head_sha(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _current_branch_or_head(repo: Path) -> str:
    return _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo).stdout.strip()


def _write_meta(
    feature_dir: Path,
    *,
    mission_slug: str,
    mission_id: str,
    mid8: str,
    target_branch: str,
) -> None:
    meta: dict[str, object] = {
        "mission_slug": mission_slug,
        "mission_id": mission_id,
        "mid8": mid8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": target_branch,
        "topology": "single_branch",
        "friendly_name": "WP04 write-seam thunk fixture",
    }
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_wp_file(feature_dir: Path, wp_id: str) -> Path:
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    wp_path = tasks_dir / f"{wp_id}-scaffold.md"
    wp_path.write_text(
        "---\n"
        f"work_package_id: {wp_id}\n"
        f"title: {wp_id} scaffold\n"
        "agent: python-pedro\n"
        "review_status: approved\n"
        "---\n"
        f"# {wp_id}\n\nInitial scaffold.\n",
        encoding="utf-8",
    )
    return wp_path


def _done_event(mission_slug: str, wp_id: str) -> dict[str, object]:
    return {
        "actor": "reviewer-renata",
        "at": "2026-07-30T12:00:00+00:00",
        "event_id": f"01HXYZTHUNK0000000000{wp_id}",
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
        f"chore({mission_slug}): record baseline_merge_commit + mission_number (E1)",
    )


def _build_e2_mission(
    repo: Path, *, mid8: str, slug_prefix: str, mission_number: int
) -> tuple[str, Path, str]:
    """A genuine, FLAT-topology E2 mission (mirrors WP02 T005's PRIMARY-kind
    variant, C-006's canonical repro topology). Unlike WP02's fixture, the
    tasks WP file is left MODIFIABLE by the caller so a genuinely new write
    (not byte-identical to what already merged) can be exercised -- FR-012
    idempotence means a byte-identical write correctly reports "unchanged",
    never "committed" (the module docstring's own contract); the tests below
    that need a "committed" outcome append fresh content before writing.

    Returns ``(mission_slug, wp_file_path, target_branch)``.
    """
    mission_id = f"{mid8}0000000000000000"
    mission_slug = f"{slug_prefix}-{mid8}"
    target_branch = f"kitty/mission-{mission_slug}"
    wp_id = "WP01"

    init_sha = _init_git_repo(repo)

    _git(repo, "checkout", "-q", "-b", target_branch)
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mid8=mid8,
        target_branch=target_branch,
    )
    wp_path = _write_wp_file(feature_dir, wp_id)
    (feature_dir / "status.events.jsonl").write_text(
        json.dumps(_done_event(mission_slug, wp_id), sort_keys=True) + "\n", encoding="utf-8"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): mission scaffold")

    _record_e1_consolidation(
        repo,
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        baseline_commit=init_sha,
        mission_number=mission_number,
    )

    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", target_branch, "-m", f"Merge {target_branch}")
    _git(repo, "branch", "-D", target_branch)

    return mission_slug, wp_path, target_branch


# ---------------------------------------------------------------------------
# T014 -- exactly-one-of files=/stage= misuse guard (renata m4)
# ---------------------------------------------------------------------------


def test_write_artifact_rejects_neither_files_nor_stage(tmp_path: Path) -> None:
    """Neither ``files=`` nor ``stage=`` supplied -> raises immediately, no probe."""
    policy = ProtectionPolicy.resolve(tmp_path)
    with pytest.raises(WriteSeamUsageError, match="neither"):
        write_artifact(
            repo_root=tmp_path,
            mission_slug="does-not-matter",
            kind=MissionArtifactKind.TRACER_FILE,
            message="irrelevant",
            policy=policy,
            entry_id="e1",
        )


def test_write_artifact_rejects_both_files_and_stage(tmp_path: Path) -> None:
    """Both ``files=`` and ``stage=`` supplied -> raises immediately, no probe."""
    policy = ProtectionPolicy.resolve(tmp_path)
    staged: list[str] = []

    def _stage() -> tuple[Path, ...]:
        staged.append("called")
        return (tmp_path / "x.txt",)

    with pytest.raises(WriteSeamUsageError, match="both"):
        write_artifact(
            repo_root=tmp_path,
            mission_slug="does-not-matter",
            kind=MissionArtifactKind.TRACER_FILE,
            files=(tmp_path / "x.txt",),
            stage=_stage,
            message="irrelevant",
            policy=policy,
            entry_id="e1",
        )
    assert staged == [], "stage() must never run when the entry guard raises"


# ---------------------------------------------------------------------------
# SC-003 -- a refused write leaves zero untracked residue (#3073 / FR-005)
# ---------------------------------------------------------------------------


def _build_coord_branch_deleted_fixture(repo: Path) -> str:
    """A PRE-consolidation mission declaring a ``coordination_branch`` in
    ``meta.json`` that does NOT exist in git (never created / already
    retired) -- ``resolve_placement_only``'s unconditional coordination-
    surface probe raises ``CoordinationBranchDeleted`` (a
    ``StatusReadPathNotFound`` subclass) for a coord-partition ``kind``
    BEFORE any phase-specific routing, the literal FR-011 zero-write
    scenario this module's docstring names. No ``baseline_merge_commit`` is
    recorded, so this is NOT the FR-006 off-checkout case (covered
    separately below) -- it is the generic "genuinely unroutable target"
    refusal.
    """
    mid8 = "01KYQS50"
    mission_id = f"{mid8}0000000000000000"
    mission_slug = f"orphaned-coord-mission-{mid8}"
    target_branch = f"kitty/mission-{mission_slug}"
    coordination_branch = f"kitty/mission-{mission_slug}-coord"

    _init_git_repo(repo)
    _git(repo, "checkout", "-q", "-b", target_branch)
    feature_dir = repo / "kitty-specs" / mission_slug
    meta: dict[str, object] = {
        "mission_slug": mission_slug,
        "mission_id": mission_id,
        "mid8": mid8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": target_branch,
        "topology": "coord",
        "coordination_branch": coordination_branch,
        "friendly_name": "WP04 orphaned-coord-branch fixture",
    }
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): mission scaffold, no coord branch ever created")
    return mission_slug


def test_refused_write_never_invokes_stage_and_leaves_no_residue(tmp_path: Path) -> None:
    """An unroutable mission (FR-011 -- coordination surface declared but
    missing) refuses the write; ``stage()`` (the thunk) is NEVER invoked --
    probe-before-stage, the single locus T014 establishes (SC-003 / #3073).
    """
    repo = tmp_path / "repo"
    mission_slug = _build_coord_branch_deleted_fixture(repo)
    policy = ProtectionPolicy.resolve(repo)

    would_be_path = repo / "kitty-specs" / mission_slug / "traces" / "tooling-friction.md"
    staged: list[str] = []

    def _stage() -> tuple[Path, ...]:
        staged.append("called")
        would_be_path.parent.mkdir(parents=True, exist_ok=True)
        would_be_path.write_text("should never land\n", encoding="utf-8")
        return (would_be_path,)

    result = write_artifact(
        repo_root=repo,
        mission_slug=mission_slug,
        kind=MissionArtifactKind.TRACER_FILE,
        stage=_stage,
        message="chore: should be refused",
        policy=policy,
        entry_id="never-lands",
    )

    assert result.status == "refused", result
    assert result.destination_surface is None, result
    assert "#3033" in (result.diagnostic or ""), result
    assert staged == [], "stage() must never run on a refused (unroutable) write"
    assert not would_be_path.exists(), "refused write must leave zero untracked residue"
    status = _git(repo, "status", "--porcelain", "--untracked-files=all")
    assert status.stdout.strip() == "", f"expected a clean tree, got: {status.stdout!r}"


# ---------------------------------------------------------------------------
# SC-004 -- off-checkout refuse-with-recovery (FR-006), no forced checkout
# ---------------------------------------------------------------------------


def _build_off_checkout_fixture(repo: Path) -> tuple[str, str]:
    """A genuine PUBLISHED (E2) mission whose lifecycle bookkeeping
    (``baseline_merge_commit`` + ``mission_number``) is visible from the
    CURRENT (detached) checkout, but whose content was NEVER actually merged
    into 'main' (the resolved Primary Branch) -- e.g. a stale local clone
    that has not yet fetched the just-published PR. This is what
    ``content_present_at_primary_tip`` (D1, squash-robust) is built to
    detect: it queries 'main' AS A REF (git object presence), never the
    literal checked-out working directory, so the operator's OWN
    Target-Ref-deleted checkout can still show E2 bookkeeping while 'main'
    genuinely lacks the content.

    Returns ``(mission_slug, detached_sha)``.
    """
    mid8 = "01KYQS40"
    mission_id = f"{mid8}0000000000000000"
    mission_slug = f"stale-clone-mission-{mid8}"
    target_branch = f"kitty/mission-{mission_slug}"
    wp_id = "WP01"

    init_sha = _init_git_repo(repo)

    _git(repo, "checkout", "-q", "-b", target_branch)
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mid8=mid8,
        target_branch=target_branch,
    )
    _write_wp_file(feature_dir, wp_id)
    (feature_dir / "status.events.jsonl").write_text(
        json.dumps(_done_event(mission_slug, wp_id), sort_keys=True) + "\n", encoding="utf-8"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): mission scaffold")

    _record_e1_consolidation(
        repo,
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        baseline_commit=init_sha,
        mission_number=901,
    )

    detached_sha = _current_head_sha(repo)
    # Detach HEAD at the mission's own content (bookkeeping visible on disk)
    # WITHOUT ever merging into 'main' -- 'main' stays at the bare "init"
    # commit, genuinely lacking kitty-specs/<slug>/meta.json at its tip.
    _git(repo, "checkout", "-q", "--detach", detached_sha)
    _git(repo, "branch", "-D", target_branch)

    return mission_slug, detached_sha


def test_off_checkout_write_refuses_with_branch_named_recovery(tmp_path: Path) -> None:
    """SC-004 (seam level): off-checkout write refuses with a recovery
    message naming the branch-DERIVED default (never a hard-coded literal
    guess, never a bare SHA -- the resolver derives it via
    ``resolve_primary_branch(..., bias=False)``, whose Method 1 is
    ``git symbolic-ref refs/remotes/origin/HEAD``), leaves zero residue, and
    performs no checkout.
    """
    repo = tmp_path / "repo"
    mission_slug, detached_sha = _build_off_checkout_fixture(repo)
    assert _current_head_sha(repo) == detached_sha, "fixture must leave HEAD detached"

    policy = ProtectionPolicy.resolve(repo)
    would_be_path = repo / "kitty-specs" / mission_slug / "traces" / "tooling-friction.md"
    staged: list[str] = []

    def _stage() -> tuple[Path, ...]:
        staged.append("called")
        would_be_path.parent.mkdir(parents=True, exist_ok=True)
        would_be_path.write_text("should never land\n", encoding="utf-8")
        return (would_be_path,)

    result = write_artifact(
        repo_root=repo,
        mission_slug=mission_slug,
        kind=MissionArtifactKind.TRACER_FILE,
        stage=_stage,
        message=f"chore({mission_slug}): should refuse off-checkout",
        policy=policy,
        entry_id="off-checkout",
    )

    expected_branch = resolve_primary_branch(get_main_repo_root(repo), bias=False)
    assert result.status == "refused", result
    assert result.diagnostic is not None
    assert expected_branch in result.diagnostic, result.diagnostic
    assert "FR-006" in result.diagnostic, result.diagnostic
    assert staged == [], "stage() must never run on an off-checkout refusal"
    assert not would_be_path.exists()

    # No checkout was ever performed: HEAD is still the SAME detached SHA.
    assert _current_head_sha(repo) == detached_sha
    status = _git(repo, "status", "--porcelain", "--untracked-files=all")
    assert status.stdout.strip() == "", f"expected a clean tree, got: {status.stdout!r}"


def test_off_checkout_safe_commit_cli_exits_nonzero_with_no_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SC-004 (CLI level, 'surfaced through safe_commit_cmd.py'): the same
    off-checkout condition, driven through ``spec-kitty safe-commit`` on a
    classified PRIMARY artifact, exits non-zero and performs no checkout.
    """
    repo = tmp_path / "repo"
    mission_slug, detached_sha = _build_off_checkout_fixture(repo)
    wp_path = repo / "kitty-specs" / mission_slug / "tasks" / "WP01-scaffold.md"
    wp_path.write_text(wp_path.read_text(encoding="utf-8") + "\nEvidence.\n", encoding="utf-8")

    monkeypatch.chdir(repo)
    result = runner.invoke(
        cli_app,
        [
            "safe-commit",
            "--message",
            f"chore({mission_slug}): should refuse off-checkout",
            "--json",
            str(wp_path.relative_to(repo)),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code != 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["success"] is False, payload
    expected_branch = resolve_primary_branch(get_main_repo_root(repo), bias=False)
    assert expected_branch in payload["error"], payload

    # No checkout was performed by the CLI: still detached at the same SHA.
    assert _current_head_sha(repo) == detached_sha
    assert _current_branch_or_head(repo) == "HEAD", "must still be detached, no checkout forced"


# ---------------------------------------------------------------------------
# E2 CONSOLIDATED write success + probe/commit phase agreement (NFR-001)
# ---------------------------------------------------------------------------


def test_e2_consolidated_coord_kind_write_commits_and_agrees_with_probe(
    tmp_path: Path,
) -> None:
    """A genuine E2 write (with content that GENUINELY differs from what is
    already on 'main' -- FR-012 idempotence means a byte-identical write
    correctly reports "unchanged", not "committed") lands as ``committed`` on
    the resolved Primary Branch, and the probe-time recognition
    (:func:`is_post_consolidation_write_target`) agrees with the actual
    commit-time destination (NFR-001 -- the probe and the materialiser never
    disagree about where a write lands).
    """
    repo = tmp_path / "repo"
    mission_slug, wp_path, target_branch = _build_e2_mission(
        repo, mid8="01KYQS20", slug_prefix="evidence-capture-mission", mission_number=812
    )
    feature_dir = repo / "kitty-specs" / mission_slug
    assert not _branch_exists(repo, target_branch)

    policy = ProtectionPolicy.resolve(repo)
    trace_path = feature_dir / "traces" / "tooling-friction.md"

    def _stage() -> tuple[Path, ...]:
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.write_text(
            "# Tracer: tooling-friction\n\n2026-07-30 · pedro · genuinely new finding\n",
            encoding="utf-8",
        )
        return (trace_path,)

    # Probe-time recognition, computed independently of the write below --
    # NFR-001's "identical phase" invariant means this must equal the ACTUAL
    # committed destination.
    from mission_runtime import placement_seam

    probed = placement_seam(repo, mission_slug).write_target(MissionArtifactKind.TRACER_FILE)
    assert is_post_consolidation_write_target(
        repo, mission_slug, MissionArtifactKind.TRACER_FILE, probed
    ), probed

    result = write_artifact(
        repo_root=repo,
        mission_slug=mission_slug,
        kind=MissionArtifactKind.TRACER_FILE,
        stage=_stage,
        message=f"chore({mission_slug}): record tracer finding (E2)",
        policy=policy,
        entry_id="tooling-friction-1",
    )

    expected_branch = resolve_primary_branch(get_main_repo_root(repo), bias=False)
    assert result.status == "committed", result
    assert result.destination_surface == expected_branch, result
    # Probe/commit phase agreement (NFR-001): the SAME ref the probe
    # recognised is exactly what the write landed on -- no split-brain.
    assert probed.ref == result.destination_surface == expected_branch
    assert result.commit_hash is not None, result
    assert _current_branch_or_head(repo) == "main"
    # The committed artifact itself must leave no residue at its OWN path
    # (SC-003's guarantee extends to the success path too: the thunk wrote
    # exactly once, and that write is now committed, not untracked).
    # ``.kittify/sync-state.json`` is unrelated, pre-existing spec-kitty sync
    # bookkeeping noise (emitted by safe_commit's own local-commit
    # notification for any kitty-specs/ write) -- not residue this WP's
    # thunk contract is about, so it is excluded rather than asserted away.
    status = _git(repo, "status", "--porcelain", "--untracked-files=all")
    residual_paths = [
        line[3:].strip()
        for line in status.stdout.splitlines()
        if line.strip() and not line[3:].strip().endswith(".kittify/sync-state.json")
    ]
    assert residual_paths == [], f"expected no artifact residue, got: {residual_paths!r}"
    assert not trace_path.exists() or _git(
        repo, "log", "--oneline", "-1", "--", str(trace_path.relative_to(repo))
    ).stdout.strip(), "trace_path must be committed, not left as untracked residue"


# ---------------------------------------------------------------------------
# SC-009 -- `spec-kitty review --mode post-merge` exits 0 end-to-end on an E2 mission
# ---------------------------------------------------------------------------


def test_review_post_merge_exits_zero_on_e2_mission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SC-009: the operator-facing symptom clears. ``review --mode
    post-merge`` performs no commit (C-006) -- this pins the READ-side E2
    resolution (WP03's ``SurfaceLocations.consolidated`` / lifecycle-phase
    wiring) end-to-end through the real CLI on a genuine E2 mission (E1
    consolidated, then published to trunk, Target Ref deleted).
    """
    repo = tmp_path / "repo"
    mission_slug, wp_path, target_branch = _build_e2_mission(
        repo, mid8="01KYQS30", slug_prefix="widget-catalog-review", mission_number=555
    )
    assert not _branch_exists(repo, target_branch)

    # A changed Python file (no NEW public symbol) so the dead-code gate is
    # determinable -- the review command's OWN, unrelated gate 2 requirement
    # (not this WP's concern), avoiding an "undeterminable" finding that
    # would obscure what SC-009 actually pins.
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "review_fixture_module.py").write_text(
        '"""Placeholder module (no public symbols) for the review dead-code gate."""\n',
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): add placeholder module")

    monkeypatch.chdir(repo)
    result = runner.invoke(
        cli_app,
        ["review", "--mission", mission_slug, "--mode", "post-merge"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.stdout
    assert "Verdict: pass" in result.stdout, result.stdout
