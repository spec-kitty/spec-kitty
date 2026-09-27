"""Unit tests for the standalone ISSUE_MATRIX coordination-ref content read (IC-01a).

Mission ``issue-matrix-partition-integrity-01M3H10A`` WP01 (#5171/#4943, FR-005/FR-007,
NFR-002/NFR-003). Covers:

* CONSOLIDATED (#5171's exact case): coord branch retained, Target Ref present -- the read
  resolves the coordination branch ref, via the SAME lifecycle-phase authority the write path
  uses (:func:`~mission_runtime.resolution.resolve_placement_only`), never the primary residue.
* PUBLISHED (E2): Target Ref deleted + completion evidence -- the read resolves the consolidated
  PRIMARY ref (the resolved Primary Branch), not the coordination branch.
* Fail-closed legs (FR-007), each paired with a same-fixture positive control:
  - resolved ref deleted (coordination branch removed from git) -> refuse.
  - content probe error (path never committed at a valid ref) -> refuse on a DISTINCT path from
    the deleted-ref leg.
  - empty authored content -> refuse rather than "nothing to enforce".
* #4959 non-regression: ``_classify_artifact_surface`` (consumed by
  :func:`~mission_runtime.resolution.resolve_artifact_surface`) keeps raising
  ``CoordinationWorktreeUnmaterialized`` for every OTHER coord kind on an UNMATERIALIZED coord
  state, while the new standalone read serves the ISSUE_MATRIX post-consolidation case on the
  SAME fixture (the carve-out is not vacuous).

Fixtures build REAL git repos through the actual merge-time bookkeeping entry point
(:func:`specify_cli.merge.baseline.record_baseline_merge_commit`), mirroring
``tests/mission_runtime/test_consolidated_resolution.py`` and
``tests/mission_runtime/test_lifecycle_phase.py``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import mission_runtime.resolution as resolution_module
from mission_runtime import MissionArtifactKind
from mission_runtime.lifecycle_phase import LifecyclePhase, resolve_lifecycle_phase
from mission_runtime.resolution import (
    IssueMatrixRefReadError,
    read_issue_matrix_ref_content,
    resolve_artifact_surface,
)
from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized
from specify_cli.merge.baseline import record_baseline_merge_commit
from specify_cli.mission_metadata import load_meta, write_meta

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Real-git plumbing helpers (mirrors test_consolidated_resolution.py)
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


def _write_meta(
    feature_dir: Path,
    *,
    mission_slug: str,
    mission_id: str,
    mid8: str,
    target_branch: str,
    topology: str = "coord",
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
        "friendly_name": "Issue-matrix ref-read fixture",
    }
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_wp_file(feature_dir: Path, wp_id: str) -> Path:
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    wp_path = tasks_dir / f"{wp_id}-evidence.md"
    wp_path.write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: {wp_id}\n---\n# {wp_id}\n",
        encoding="utf-8",
    )
    return wp_path


def _write_issue_matrix_file(feature_dir: Path, content: str) -> Path:
    matrix_path = feature_dir / "issue-matrix.json"
    matrix_path.write_text(content, encoding="utf-8")
    return matrix_path


def _consolidate_e1(
    repo: Path,
    feature_dir: Path,
    *,
    mission_slug: str,
    mission_id: str,
    baseline_commit: str,
) -> None:
    record_baseline_merge_commit(feature_dir, baseline_commit, mission_id=mission_id)
    meta = load_meta(feature_dir)
    assert meta is not None
    write_meta(feature_dir, meta, validate=False)
    _git(repo, "add", ".")
    _git(
        repo,
        "commit",
        "-m",
        f"chore({mission_slug}): record baseline_merge_commit (E1 consolidation)",
    )


def _build_consolidated_coord_mission(
    repo: Path,
    *,
    mid8: str,
    primary_matrix_content: str = "in-mission",
    coord_matrix_content: str | None = "fixed",
    branch_coordination_before_scaffold: bool = False,
) -> tuple[str, Path, str, str]:
    """A genuine CONSOLIDATED (E1) coord mission -- #5171's exact case.

    Baseline present, Target Ref still exists, coordination branch retained
    but NEVER materialized as a worktree on disk. The coord branch, when
    ``coord_matrix_content`` is not ``None``, carries its OWN authored
    ``issue-matrix.json`` distinct from the (stale) content left on the
    Target Ref -- proving a read that resolves the coord ref, not the
    primary residue.

    ``branch_coordination_before_scaffold=True`` branches coordination at the
    PRE-scaffold tip, so its tree carries no mission dir at all -- the
    ``git show <ref>:<path>`` content-probe-error fixture (the path is
    genuinely absent at a VALID ref, distinct from a deleted ref).

    HEAD is left on ``target_branch`` (not the coordination branch) so the
    resolved PRIMARY read anchors on the mission's real (baseline-recorded)
    meta.json, exactly as an operator's checkout would after consolidation --
    only the coordination branch REF exists; its worktree is never
    materialized on disk.

    Returns ``(mission_slug, feature_dir, target_branch, coordination_branch)``.
    """
    mission_id = f"{mid8}0000000000000000"
    mission_slug = f"widget-catalog-{mid8}"
    target_branch = f"kitty/mission-{mission_slug}"
    coordination_branch = f"kitty/mission-{mission_slug}-coord"
    wp_id = "WP01"

    _git(repo, "checkout", "-q", "-b", target_branch)
    if branch_coordination_before_scaffold:
        _git(repo, "branch", coordination_branch, target_branch)
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mid8=mid8,
        target_branch=target_branch,
        coordination_branch=coordination_branch,
    )
    _write_wp_file(feature_dir, wp_id)
    _write_issue_matrix_file(feature_dir, primary_matrix_content)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): mission scaffold")
    scaffold_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    if not branch_coordination_before_scaffold:
        # Branch coordination AFTER the scaffold commit so it carries the
        # committed ``issue-matrix.json`` -- branching earlier (the
        # ``branch_coordination_before_scaffold=True`` arm) leaves the coord
        # branch with no mission dir at all (the probe-error fixture).
        _git(repo, "branch", coordination_branch, target_branch)

    _consolidate_e1(
        repo,
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        baseline_commit=scaffold_sha,
    )

    if coord_matrix_content is not None:
        _git(repo, "checkout", "-q", coordination_branch)
        _write_issue_matrix_file(feature_dir, coord_matrix_content)
        _git(repo, "add", ".")
        _git(repo, "commit", "--allow-empty", "-m", f"chore({mission_slug}): author issue-matrix verdict")
        # HEAD returns to target_branch -- the coordination branch is only a
        # retained REF; the primary/current checkout stays on the Target Ref,
        # matching the real post-consolidation shape (no coord worktree).
        _git(repo, "checkout", "-q", target_branch)

    return mission_slug, feature_dir, target_branch, coordination_branch


def _build_published_coord_mission(
    repo: Path,
    *,
    mid8: str,
    matrix_content: str = "fixed",
) -> tuple[str, Path, str, str]:
    """A genuine PUBLISHED (E2) coord mission -- Target Ref deleted + completion evidence.

    Returns ``(mission_slug, feature_dir, target_branch, coordination_branch)``.
    """
    mission_id = f"{mid8}0000000000000000"
    mission_slug = f"invoice-export-{mid8}"
    target_branch = f"kitty/mission-{mission_slug}"
    coordination_branch = f"kitty/mission-{mission_slug}-coord"
    wp_id = "WP01"

    _git(repo, "checkout", "-q", "-b", target_branch)
    _git(repo, "branch", coordination_branch, target_branch)
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mid8=mid8,
        target_branch=target_branch,
        coordination_branch=coordination_branch,
    )
    _write_wp_file(feature_dir, wp_id)
    _write_issue_matrix_file(feature_dir, matrix_content)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): mission scaffold")
    scaffold_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()

    _consolidate_e1(
        repo,
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        baseline_commit=scaffold_sha,
    )
    meta = load_meta(feature_dir)
    assert meta is not None
    meta["mission_number"] = 401
    write_meta(feature_dir, meta, validate=False)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): assign mission_number")

    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", target_branch, "-m", f"Merge {target_branch}")
    _git(repo, "branch", "-D", target_branch)
    _git(repo, "branch", "-D", coordination_branch)

    return mission_slug, feature_dir, target_branch, coordination_branch


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    _init_git_repo(r)
    return r


# ---------------------------------------------------------------------------
# CONSOLIDATED (#5171's exact case): reads the coordination branch ref
# ---------------------------------------------------------------------------


def test_consolidated_reads_coordination_branch_ref_content(repo: Path) -> None:
    """CONSOLIDATED: the read resolves the coord branch ref and returns ITS
    content -- never the stale content left on the Target Ref (the #5171 bug
    the write side already fixed; this proves the READ never diverges)."""
    mission_slug, _feature_dir, _target, coordination_branch = _build_consolidated_coord_mission(repo, mid8="01KZM1AA", coord_matrix_content="fixed")
    assert resolve_lifecycle_phase(mission_slug, repo) is LifecyclePhase.CONSOLIDATED

    content = read_issue_matrix_ref_content(repo, mission_slug)

    assert content == "fixed"


def test_consolidated_reads_in_mission_verdict_from_coord(repo: Path) -> None:
    """Positive/negative pair (T001): a non-terminal coord verdict is read back
    byte-identically -- the primitive is content-neutral, not verdict-aware."""
    mission_slug, _feature_dir, _target, _coord = _build_consolidated_coord_mission(repo, mid8="01KZM1AB", coord_matrix_content="in-mission")

    content = read_issue_matrix_ref_content(repo, mission_slug)

    assert content == "in-mission"


# ---------------------------------------------------------------------------
# PUBLISHED: reads the consolidated-primary ref, not the coordination branch
# ---------------------------------------------------------------------------


def test_published_reads_consolidated_primary_ref(repo: Path) -> None:
    """PUBLISHED (E2): the coordination branch has ALSO been retired
    (fully-retired-coord shape); the read must resolve the resolved Primary
    Branch tip, never attempt the (now-deleted) coordination branch."""
    mission_slug, _feature_dir, _target, coordination_branch = _build_published_coord_mission(repo, mid8="01KZM1BB", matrix_content="fixed")
    assert resolve_lifecycle_phase(mission_slug, repo) is LifecyclePhase.PUBLISHED
    assert not _branch_exists(repo, coordination_branch)

    content = read_issue_matrix_ref_content(repo, mission_slug)

    assert content == "fixed"


# ---------------------------------------------------------------------------
# Fail-closed legs (FR-007), each paired with a same-fixture positive control
# ---------------------------------------------------------------------------


def test_deleted_ref_refuses(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The ref the phase authority resolved to no longer exists in git ->
    refuse, typed distinctly, never silently falling back to the primary
    residue.

    Note: a mission whose DECLARED coordination branch is itself deleted from
    git is already caught earlier, loudly, by ``resolve_placement_only``'s own
    coordination-surface probe (``CoordinationBranchDeleted`` / #1848) — this
    helper's existence probe is the belt-and-suspenders leg for a resolved ref
    that stops existing for any OTHER reason (e.g. concurrent branch deletion
    between resolution and read). Monkeypatching the ref-resolution helper
    isolates exactly that leg without relying on an unreachable git shape.
    """
    mission_slug, _feature_dir, _target, _coord = _build_consolidated_coord_mission(repo, mid8="01KZM1CC", coord_matrix_content="fixed")
    monkeypatch.setattr(resolution_module, "_issue_matrix_ref", lambda *a, **kw: "refs/heads/does-not-exist-anywhere")

    with pytest.raises(IssueMatrixRefReadError) as excinfo:
        read_issue_matrix_ref_content(repo, mission_slug)

    assert excinfo.value.code == "ISSUE_MATRIX_REF_ABSENT"


def test_deleted_ref_positive_control_resolves(repo: Path) -> None:
    """Same fixture, unpatched (the real ref resolves) -> resolves (the
    paired positive control)."""
    mission_slug, _feature_dir, _target, _coord = _build_consolidated_coord_mission(repo, mid8="01KZM1DD", coord_matrix_content="fixed")

    assert read_issue_matrix_ref_content(repo, mission_slug) == "fixed"


def test_content_probe_error_refuses_on_a_distinct_path(repo: Path) -> None:
    """The resolved ref is valid but the object was never committed there
    (unreadable at ``<ref>:<path>``) -> refuse, on a DISTINCT typed path from
    the deleted-ref leg above (never conflated)."""
    mission_slug, _feature_dir, _target, _coord = _build_consolidated_coord_mission(
        repo, mid8="01KZM1EE", coord_matrix_content=None, branch_coordination_before_scaffold=True
    )

    with pytest.raises(IssueMatrixRefReadError) as excinfo:
        read_issue_matrix_ref_content(repo, mission_slug)

    assert excinfo.value.code == "ISSUE_MATRIX_PROBE_ERROR"
    assert excinfo.value.code != "ISSUE_MATRIX_REF_ABSENT"


def test_content_probe_error_positive_control_resolves(repo: Path) -> None:
    """Same fixture, the object DOES exist at the ref -> resolves."""
    mission_slug, _feature_dir, _target, _coord = _build_consolidated_coord_mission(repo, mid8="01KZM1FF", coord_matrix_content="fixed")

    assert read_issue_matrix_ref_content(repo, mission_slug) == "fixed"


def test_empty_authored_content_refuses(repo: Path) -> None:
    """An empty authored matrix must never be read as 'nothing to enforce'."""
    mission_slug, _feature_dir, _target, _coord = _build_consolidated_coord_mission(repo, mid8="01KZM1GG", coord_matrix_content="")

    with pytest.raises(IssueMatrixRefReadError) as excinfo:
        read_issue_matrix_ref_content(repo, mission_slug)

    assert excinfo.value.code == "ISSUE_MATRIX_EMPTY_CONTENT"


def test_empty_authored_content_positive_control_resolves(repo: Path) -> None:
    """Same fixture, non-empty authored content -> resolves (paired control)."""
    mission_slug, _feature_dir, _target, _coord = _build_consolidated_coord_mission(repo, mid8="01KZM1HH", coord_matrix_content="fixed")

    assert read_issue_matrix_ref_content(repo, mission_slug) == "fixed"


# ---------------------------------------------------------------------------
# #4959 non-regression: `_classify` keeps raising for every OTHER coord kind;
# the standalone read serves ISSUE_MATRIX on the SAME fixture (non-vacuous).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind",
    [
        MissionArtifactKind.TRACER_FILE,
        MissionArtifactKind.REVIEW_CYCLE,
        MissionArtifactKind.ACCEPTANCE_MATRIX,
        MissionArtifactKind.STATUS_STATE,
    ],
)
def test_4959_other_coord_kinds_still_raise_on_unmaterialized(repo: Path, kind: MissionArtifactKind) -> None:
    """#4959 non-regression: an UNMATERIALIZED coord worktree still raises
    ``CoordinationWorktreeUnmaterialized`` for every coord kind OTHER than
    ISSUE_MATRIX's new standalone path -- the carve-out must not be blanket."""
    mission_slug, _feature_dir, _target, _coord = _build_consolidated_coord_mission(repo, mid8="01KZM1II", coord_matrix_content="fixed")

    with pytest.raises(CoordinationWorktreeUnmaterialized):
        resolve_artifact_surface(repo, mission_slug, kind)


# ---------------------------------------------------------------------------
# #5222 (F2): every underlying git-probe failure surfaces as the ONE typed
# error this function's docstring promises, never an untyped exception.
# ---------------------------------------------------------------------------


def test_ref_existence_probe_error_wrapped_as_issue_matrix_error(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``_rev_is_valid`` raising ``LifecyclePhaseProbeError`` (its own
    documented failure mode, e.g. a ``git rev-parse`` timeout) must not
    escape untyped -- a caller catching only ``IssueMatrixRefReadError``
    (the ONE type this module's docstring promises) would otherwise miss it.
    """
    from mission_runtime.lifecycle_phase import LifecyclePhaseProbeError

    mission_slug, _feature_dir, _target, _coord = _build_consolidated_coord_mission(repo, mid8="01KZM1KK", coord_matrix_content="fixed")

    def _boom(*_a: object, **_kw: object) -> bool:
        raise LifecyclePhaseProbeError("git rev-parse --verify timed out")

    monkeypatch.setattr(resolution_module, "_rev_is_valid", _boom)

    with pytest.raises(IssueMatrixRefReadError) as excinfo:
        read_issue_matrix_ref_content(repo, mission_slug)

    assert excinfo.value.code == "ISSUE_MATRIX_PROBE_ERROR"


def test_content_probe_oserror_wrapped_as_issue_matrix_error(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An ``OSError`` from ``subprocess.run`` (e.g. the ``git`` executable is
    missing) must not escape untyped either -- same class of gap as the
    ``TimeoutExpired`` leg this function already wrapped."""
    mission_slug, _feature_dir, _target, _coord = _build_consolidated_coord_mission(repo, mid8="01KZM1LL", coord_matrix_content="fixed")

    real_run = resolution_module.subprocess.run

    def _boom_on_show(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        # Only the ``git show`` content probe this function performs must be
        # affected -- every other git call this call chain makes (ref
        # resolution, phase derivation, etc.) uses the REAL subprocess so this
        # stays a narrow, single-leg probe-failure fixture.
        if cmd[:2] == ["git", "show"]:
            raise FileNotFoundError("git executable not found")
        return real_run(cmd, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(resolution_module.subprocess, "run", _boom_on_show)

    with pytest.raises(IssueMatrixRefReadError) as excinfo:
        read_issue_matrix_ref_content(repo, mission_slug)

    assert excinfo.value.code == "ISSUE_MATRIX_PROBE_ERROR"


def test_issue_matrix_ref_read_error_importable_from_package_root() -> None:
    """#5222 (F2): the error must be catchable via ``mission_runtime`` (the
    package root), not only the import-forbidden ``mission_runtime.resolution``
    submodule (MR-1/MR-2) -- a review/doctor consumer outside this package can
    only ever import from the root."""
    import mission_runtime

    assert mission_runtime.IssueMatrixRefReadError is IssueMatrixRefReadError


# ---------------------------------------------------------------------------
# #5222 (F3): legacy markdown failover at the SAME ref, mirroring the
# dir-based reader's JSON-first-then-``.md`` probe order (FR-013).
# ---------------------------------------------------------------------------


def test_legacy_markdown_failover_reads_when_json_absent_at_ref(repo: Path) -> None:
    """A coord mission whose ref-committed matrix is the LEGACY ``.md`` format
    (no ``issue-matrix.json`` ever committed there) must resolve via the
    ``.md`` failover, not refuse with a JSON-only probe error."""
    mission_slug, feature_dir, _target, coordination_branch = _build_consolidated_coord_mission(
        repo, mid8="01KZM1MM", coord_matrix_content=None, branch_coordination_before_scaffold=True
    )
    md_text = "| issue | verdict | evidence_ref |\n|---|---|---|\n| #1234 | fixed | PR #1 |\n"
    _git(repo, "checkout", "-q", coordination_branch)
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "issue-matrix.md").write_text(md_text, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): author legacy issue-matrix.md")
    _git(repo, "checkout", "-q", f"kitty/mission-{mission_slug}")

    content = read_issue_matrix_ref_content(repo, mission_slug)

    assert content == md_text


def test_legacy_markdown_failover_json_still_wins_when_both_present(repo: Path) -> None:
    """JSON-first is preserved: when BOTH formats exist at the ref, the
    structured ``.json`` is read, never the legacy ``.md`` (mirrors the
    dir-based reader's own precedence)."""
    mission_slug, feature_dir, _target, coordination_branch = _build_consolidated_coord_mission(
        repo, mid8="01KZM1NN", coord_matrix_content='{"rows": {"#1234": {"verdict": "fixed", "evidence_ref": "PR #1"}}}'
    )
    _git(repo, "checkout", "-q", coordination_branch)
    (feature_dir / "issue-matrix.md").write_text("| issue | verdict | evidence_ref |\n|---|---|---|\n| #1234 | in-mission | PR #1 |\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): also author legacy issue-matrix.md")
    _git(repo, "checkout", "-q", f"kitty/mission-{mission_slug}")

    content = read_issue_matrix_ref_content(repo, mission_slug)

    assert content.strip().startswith("{")
    assert "fixed" in content


def test_neither_format_at_ref_still_refuses_with_probe_error(repo: Path) -> None:
    """Neither ``.json`` nor ``.md`` committed at the ref -> still a probe
    error (the ``.md`` failover attempt's own absence), never a silent pass."""
    mission_slug, _feature_dir, _target, _coord = _build_consolidated_coord_mission(
        repo, mid8="01KZM1OO", coord_matrix_content=None, branch_coordination_before_scaffold=True
    )

    with pytest.raises(IssueMatrixRefReadError) as excinfo:
        read_issue_matrix_ref_content(repo, mission_slug)

    assert excinfo.value.code == "ISSUE_MATRIX_PROBE_ERROR"


def test_4959_issue_matrix_post_consolidation_served_by_standalone_read(repo: Path) -> None:
    """Non-vacuity: on the IDENTICAL fixture the parametrized test above uses,
    ``resolve_artifact_surface`` for ISSUE_MATRIX STILL raises
    ``CoordinationWorktreeUnmaterialized`` (``_classify`` is unchanged) -- but
    the NEW standalone read succeeds, proving the ISSUE_MATRIX carve-out is
    actually exercised rather than a dead branch."""
    mission_slug, _feature_dir, _target, _coord = _build_consolidated_coord_mission(repo, mid8="01KZM1JJ", coord_matrix_content="fixed")

    with pytest.raises(CoordinationWorktreeUnmaterialized):
        resolve_artifact_surface(repo, mission_slug, MissionArtifactKind.ISSUE_MATRIX)

    assert read_issue_matrix_ref_content(repo, mission_slug) == "fixed"
