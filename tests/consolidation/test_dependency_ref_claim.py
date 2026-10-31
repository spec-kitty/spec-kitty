"""Claim-level units for the declared dependency-ref attribution (#6771).

A lane that merged an external dependency branch's newer head must not read as
"removed/canceled work would ship". ``resolve_external_dependency_refs`` turns an
operator declaration into a verified exempt set; the closed-world window axes then treat
those commits/blobs exactly like content that predates the window. Every mis-declaration
(an unresolvable ref, a ref the mission branch never merged, a ref that would cover a
commit on a mission spine) REFUSEs — the closed world is never widened into a bypass.

Red-first on ``main``: ``resolve_external_dependency_refs`` does not exist and
``_unattributable_content`` flags every second-parent commit of the lane's merge.
"""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from specify_cli.consolidation.config import MergeStrategy
from specify_cli.consolidation.git_probes import blob_id_at
from specify_cli.consolidation.phase_claim import _pin_dependency_refs
from specify_cli.consolidation.phase_gate import _reconciliation_claim_for_gate
from specify_cli.consolidation.reconciliation import (
    ApprovedWpCommitSet,
    MergeOutcomeVerifier,
    VerifyStatus,
    dependency_refs_moved_refusal,
    resolve_external_dependency_refs,
)
from specify_cli.lanes.models import ExecutionLane, LanesManifest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

LANE_BRANCH = "lane-a"
MISSION_BRANCH = "kitty/mission-test-01M6771A"
DEP_BRANCH = "dep-branch"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def _write(repo: Path, path: str, content: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", f"add {path}")


@pytest.fixture
def merged_dependency_repo(tmp_path: Path) -> dict[str, object]:
    """A base, an approved lane commit, and a lane merge of an external dependency branch.

    ``BASE`` is the target's pre-run tip (the closed-world window base). ``lane-a`` holds
    one own content commit and then merges ``dep-branch`` (three content commits, not an
    ancestor of the base) with ``--no-ff``: exactly the shape in #6771.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.com")
    _write(repo, "src/app.py", "VALUE = 0\n")
    base = _git(repo, "rev-parse", "HEAD")

    _git(repo, "checkout", "-q", "-b", DEP_BRANCH, base)
    for idx in range(3):
        _write(repo, f"src/dep/mod{idx}.py", f"DEP = {idx}\n")
    dep_tip = _git(repo, "rev-parse", DEP_BRANCH)

    _git(repo, "checkout", "-q", "-b", LANE_BRANCH, base)
    _write(repo, "src/lane.py", "LANE = 1\n")
    lane_commit = _git(repo, "rev-parse", "HEAD")
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", DEP_BRANCH)
    lane_tip = _git(repo, "rev-parse", "HEAD")
    # The mission branch is what the landing reaches: a fast-forward of the lane here.
    _git(repo, "branch", MISSION_BRANCH, lane_tip)

    manifest = LanesManifest(
        version=1,
        mission_slug="test-01M6771A",
        mission_id=None,
        mission_branch=MISSION_BRANCH,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=("src/lane.py",),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-10-30T00:00:00Z",
        computed_from="test",
    )
    return {
        "repo": repo,
        "base": base,
        "lane_commit": lane_commit,
        "lane_tip": lane_tip,
        "dep_tip": dep_tip,
        "manifest": manifest,
    }


def _claim(**overrides: object) -> ApprovedWpCommitSet:
    fields: dict[str, object] = {
        "approved": {"WP01": ("x",)},
        "excluded_window_base": "x",
        "surface_resolved": True,
        "enforce_closed_world": True,
        "authored_shas": frozenset(),
        "authored_patch_ids": frozenset(),
        "mission_slug": "test-01M6771A",
        "planning_prefix": "kitty-specs/test-01M6771A",
    }
    fields.update(overrides)
    return ApprovedWpCommitSet(**fields)  # type: ignore[arg-type]


def _dependency_commits(repo: Path, base: str, ref: str) -> list[str]:
    out = _git(repo, "rev-list", f"{base}..{ref}")
    return [line for line in out.splitlines() if line]


def _resolver(repo: Path, base: str, manifest: LanesManifest, refs: tuple[str, ...], **extra: object):
    return resolve_external_dependency_refs(
        repo,
        refs=refs,
        window_base=base,
        mission_branch=manifest.mission_branch,
        lanes_manifest=manifest,
        coord_base_ref=extra.pop("coord_base_ref", base),  # type: ignore[arg-type]
        **extra,  # type: ignore[arg-type]
    )


def test_lane_merged_dependency_content_is_unattributable_without_a_declaration(merged_dependency_repo: dict[str, object]) -> None:
    """Control: the #6771 refusal is real on the same fixture the exemption is proven on."""
    repo = merged_dependency_repo["repo"]
    base = merged_dependency_repo["base"]
    lane_tip = merged_dependency_repo["lane_tip"]
    lane_commit = merged_dependency_repo["lane_commit"]
    assert isinstance(repo, Path) and isinstance(base, str) and isinstance(lane_tip, str) and isinstance(lane_commit, str)

    claim = _claim(excluded_window_base=base, authored_shas=frozenset({lane_commit}), approved={"WP01": (lane_commit,)})
    result = MergeOutcomeVerifier(repo).verify(lane_tip, claim)

    assert result.status is VerifyStatus.FAIL
    flagged = {sha for sha, _pid in result.divergence.unattributable_content}  # type: ignore[union-attr]
    assert merged_dependency_repo["dep_tip"] in flagged, "the dependency's own tip must be the reported un-attributable commit"


def test_declared_dependency_ref_exempts_only_the_merged_content(merged_dependency_repo: dict[str, object]) -> None:
    repo = merged_dependency_repo["repo"]
    base = merged_dependency_repo["base"]
    lane_tip = merged_dependency_repo["lane_tip"]
    lane_commit = merged_dependency_repo["lane_commit"]
    manifest = merged_dependency_repo["manifest"]
    assert isinstance(repo, Path) and isinstance(base, str) and isinstance(lane_tip, str) and isinstance(lane_commit, str)
    assert isinstance(manifest, LanesManifest)

    attribution = _resolver(repo, base, manifest, (DEP_BRANCH,))
    assert attribution.refusal is None, attribution.refusal
    expected = set(_dependency_commits(repo, base, DEP_BRANCH))
    assert attribution.shas == frozenset(expected), "exactly the dependency's window commits are exempt"

    claim = _claim(
        excluded_window_base=base,
        authored_shas=frozenset({lane_commit}),
        approved={"WP01": (lane_commit,)},
        external_dependency_refs=attribution.refs,
        external_dependency_shas=attribution.shas,
        external_dependency_blobs=attribution.blobs,
        external_dependency_deletions=attribution.deletions,
    )
    result = MergeOutcomeVerifier(repo).verify(lane_tip, claim)

    assert result.is_pass, result.recovery_guidance()


def test_declaration_that_covers_a_lane_spine_commit_is_refused(merged_dependency_repo: dict[str, object]) -> None:
    """A mission lane branch declared as the "dependency" would exempt mission work — REFUSE."""
    repo = merged_dependency_repo["repo"]
    base = merged_dependency_repo["base"]
    manifest = merged_dependency_repo["manifest"]
    lane_commit = merged_dependency_repo["lane_commit"]
    assert isinstance(repo, Path) and isinstance(base, str) and isinstance(lane_commit, str)
    assert isinstance(manifest, LanesManifest)

    attribution = _resolver(repo, base, manifest, (LANE_BRANCH,))

    assert attribution.refusal is not None
    assert attribution.shas == frozenset(), "a refused declaration exempts nothing"
    refusal = attribution.refusal
    assert "'lane-a'" in refusal
    assert "would exempt commit" in refusal
    assert "first-parent spine" in refusal
    # The named commit really is mission work: the lane's own commit, or the merge that
    # carried it onto the mission branch's spine — never the dependency's content.
    named = refusal.split("would exempt commit ")[1].split(" ")[0]
    assert lane_commit.startswith(named) or named in {sha[:10] for sha in _dependency_commits(repo, base, "lane-a")}


def test_unresolvable_declaration_is_refused(merged_dependency_repo: dict[str, object]) -> None:
    repo = merged_dependency_repo["repo"]
    base = merged_dependency_repo["base"]
    manifest = merged_dependency_repo["manifest"]
    assert isinstance(repo, Path) and isinstance(base, str) and isinstance(manifest, LanesManifest)

    attribution = _resolver(repo, base, manifest, ("no-such-ref",))

    assert attribution.refusal is not None
    assert "no-such-ref" in attribution.refusal
    assert attribution.shas == frozenset()


def test_declaration_the_mission_never_merged_is_refused(merged_dependency_repo: dict[str, object], tmp_path: Path) -> None:
    """A ref the mission branch does not reach cannot explain landing content — REFUSE."""
    repo = merged_dependency_repo["repo"]
    base = merged_dependency_repo["base"]
    manifest = merged_dependency_repo["manifest"]
    assert isinstance(repo, Path) and isinstance(base, str) and isinstance(manifest, LanesManifest)

    _git(repo, "checkout", "-q", "-b", "unrelated", base)
    _write(repo, "src/unrelated.py", "OTHER = 1\n")
    _git(repo, "checkout", "-q", LANE_BRANCH)

    attribution = _resolver(repo, base, manifest, ("unrelated",))

    assert attribution.refusal is not None
    assert "unrelated" in attribution.refusal
    assert attribution.shas == frozenset()


def test_no_declaration_probes_nothing_and_exempts_nothing(merged_dependency_repo: dict[str, object]) -> None:
    repo = merged_dependency_repo["repo"]
    base = merged_dependency_repo["base"]
    manifest = merged_dependency_repo["manifest"]
    assert isinstance(repo, Path) and isinstance(base, str) and isinstance(manifest, LanesManifest)

    attribution = _resolver(repo, base, manifest, ())

    assert attribution.refusal is None
    assert attribution.refs == ()
    assert attribution.shas == attribution.blobs == attribution.deletions == frozenset()
    # An unresolved window base is only a refusal when a declaration is actually in force.
    unresolved = _resolver(repo, None, manifest, ())  # type: ignore[arg-type]
    assert unresolved.refusal is None


def test_declaration_without_a_window_base_is_refused(merged_dependency_repo: dict[str, object]) -> None:
    repo = merged_dependency_repo["repo"]
    manifest = merged_dependency_repo["manifest"]
    assert isinstance(repo, Path) and isinstance(manifest, LanesManifest)

    attribution = _resolver(repo, None, manifest, (DEP_BRANCH,))  # type: ignore[arg-type]

    assert attribution.refusal is not None
    assert DEP_BRANCH in attribution.refusal


def test_squash_axis_honours_the_declaration(merged_dependency_repo: dict[str, object]) -> None:
    """The same declaration covers the squash blob axis (#5013), so the class is closed twice."""
    repo = merged_dependency_repo["repo"]
    base = merged_dependency_repo["base"]
    manifest = merged_dependency_repo["manifest"]
    lane_commit = merged_dependency_repo["lane_commit"]
    assert isinstance(repo, Path) and isinstance(base, str) and isinstance(manifest, LanesManifest)
    assert isinstance(lane_commit, str)

    # A squash of the lane onto the base: one commit carrying the lane's file and the
    # dependency's files, with the dependency blobs identical to the branch's own.
    _git(repo, "checkout", "-q", "-b", "squashed", base)
    _git(repo, "merge", "-q", "--squash", LANE_BRANCH)
    _git(repo, "commit", "-qm", "squash lane-a")
    squashed = _git(repo, "rev-parse", "HEAD")

    attribution = _resolver(repo, base, manifest, (DEP_BRANCH,))
    assert attribution.refusal is None, attribution.refusal
    dep_blob = blob_id_at(repo, DEP_BRANCH, "src/dep/mod0.py")

    claim = _claim(
        excluded_window_base=base,
        verify_reachability=False,
        approved={"WP01": (lane_commit,)},
        authored_blobs=frozenset({("src/lane.py", blob_id_at(repo, squashed, "src/lane.py"))}),
        external_dependency_refs=attribution.refs,
        external_dependency_blobs=attribution.blobs,
        external_dependency_deletions=attribution.deletions,
    )
    result = MergeOutcomeVerifier(repo).verify(squashed, claim)
    assert result.is_pass, result.recovery_guidance()

    without = replace(claim, external_dependency_blobs=frozenset(), external_dependency_deletions=frozenset())
    flagged = MergeOutcomeVerifier(repo).verify(squashed, without)
    assert flagged.status is VerifyStatus.FAIL
    assert ("src/dep/mod0.py", dep_blob) in flagged.divergence.unattributable_blobs  # type: ignore[union-attr]


def _merge_removed_lane_into_carrier(repo: Path, base: str, branch: str) -> str:
    """The #4945 shape: a removed work package's lane commit rides the carrier lane, then its branch is deleted.

    The carrier (``lane-a``) merges ``branch`` --no-ff, the mission branch follows the carrier,
    and ``branch`` is deleted, so no live ref (and no entry of ``lanes.json``) names the work
    any more. Returns the removed lane's tip SHA, the only handle left to declare.
    """
    _git(repo, "checkout", "-q", "-b", branch, base)
    _write(repo, "src/removed.py", "REMOVED = 1\n")
    tip = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", LANE_BRANCH)
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", branch)
    _git(repo, "branch", "-f", MISSION_BRANCH, LANE_BRANCH)
    _git(repo, "branch", "-q", "-D", branch)
    return tip


def test_removed_lane_whose_branch_was_deleted_cannot_be_declared_by_its_recorded_tip(merged_dependency_repo: dict[str, object]) -> None:
    """Red-first (#4945 via #6771): the recorded work tip of a removed lane is Mission work, not a dependency.

    The guard used to know only the CURRENT manifest's live spines, so the deleted lane's
    SHA exempted its content and it landed at exit 0.
    """
    repo, base, manifest = merged_dependency_repo["repo"], merged_dependency_repo["base"], merged_dependency_repo["manifest"]
    assert isinstance(repo, Path) and isinstance(base, str) and isinstance(manifest, LanesManifest)
    removed_tip = _merge_removed_lane_into_carrier(repo, base, f"{MISSION_BRANCH}-lane-removed")
    _git(repo, "update-ref", f"refs/spec-kitty/lane-tip/{MISSION_BRANCH}-lane-removed", removed_tip)

    attribution = _resolver(repo, base, manifest, (removed_tip,))

    assert attribution.refusal is not None, "a removed lane's recorded tip was exempted as an external dependency"
    assert "Error code: DEPENDENCY_REF_COVERS_MISSION_WORK." in attribution.refusal
    assert "recorded work tip" in attribution.refusal
    assert attribution.shas == frozenset()


def test_removed_work_package_whose_lane_head_was_stamped_cannot_be_declared(merged_dependency_repo: dict[str, object]) -> None:
    """A ``lane_head`` stamp ANY work package recorded (a canceled or removed one included) marks Mission work."""
    repo, base, manifest = merged_dependency_repo["repo"], merged_dependency_repo["base"], merged_dependency_repo["manifest"]
    assert isinstance(repo, Path) and isinstance(base, str) and isinstance(manifest, LanesManifest)
    removed_tip = _merge_removed_lane_into_carrier(repo, base, "removed-wp")

    attribution = _resolver(repo, base, manifest, (removed_tip,), recorded_lane_heads=frozenset({removed_tip}))

    assert attribution.refusal is not None
    assert "Error code: DEPENDENCY_REF_COVERS_MISSION_WORK." in attribution.refusal
    assert "lane head" in attribution.refusal
    # The control: without the stamp (and with no recorded tip ref) nothing marks the commit.
    assert _resolver(repo, base, manifest, (removed_tip,)).refusal is None


def test_ref_named_in_the_mission_branch_namespace_is_refused(merged_dependency_repo: dict[str, object]) -> None:
    """Red-first: a branch of the Mission's own namespace that ``lanes.json`` no longer lists is still Mission work."""
    repo, base, manifest = merged_dependency_repo["repo"], merged_dependency_repo["base"], merged_dependency_repo["manifest"]
    assert isinstance(repo, Path) and isinstance(base, str) and isinstance(manifest, LanesManifest)
    stray = f"{MISSION_BRANCH}-lane-removed"
    _git(repo, "checkout", "-q", "-b", stray, base)
    _write(repo, "src/removed.py", "REMOVED = 1\n")
    _git(repo, "checkout", "-q", LANE_BRANCH)
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", stray)
    _git(repo, "branch", "-f", MISSION_BRANCH, LANE_BRANCH)

    attribution = _resolver(repo, base, manifest, (stray,))

    assert attribution.refusal is not None
    assert "Error code: DEPENDENCY_REF_COVERS_MISSION_WORK." in attribution.refusal
    assert "branch namespace" in attribution.refusal


def test_unreadable_lane_spine_refuses_instead_of_shrinking_the_guard(merged_dependency_repo: dict[str, object]) -> None:
    """Red-first: a lane branch that EXISTS but whose spine cannot be read is a probe failure, not an empty spine."""
    repo, base, manifest = merged_dependency_repo["repo"], merged_dependency_repo["base"], merged_dependency_repo["manifest"]
    assert isinstance(repo, Path) and isinstance(base, str) and isinstance(manifest, LanesManifest)
    from specify_cli.consolidation.reconciliation import _lane_branch_for

    _git(repo, "branch", _lane_branch_for(manifest, "lane-a"), "lane-a")

    attribution = _resolver(repo, base, manifest, (DEP_BRANCH,), coord_base_ref="no-such-coord-base")

    assert attribution.refusal is not None
    assert "Error code: DEPENDENCY_REF_UNVERIFIABLE." in attribution.refusal
    assert attribution.shas == frozenset()


@pytest.mark.parametrize(
    ("refs", "code"),
    [
        (("no-such-ref",), "DEPENDENCY_REF_UNRESOLVED"),
        (("unrelated",), "DEPENDENCY_REF_UNREACHABLE"),
        ((LANE_BRANCH,), "DEPENDENCY_REF_COVERS_MISSION_WORK"),
    ],
)
def test_each_refusal_carries_its_stable_code(merged_dependency_repo: dict[str, object], refs: tuple[str, ...], code: str) -> None:
    repo, base, manifest = merged_dependency_repo["repo"], merged_dependency_repo["base"], merged_dependency_repo["manifest"]
    assert isinstance(repo, Path) and isinstance(base, str) and isinstance(manifest, LanesManifest)
    _git(repo, "branch", "unrelated", base)
    _git(repo, "checkout", "-q", "unrelated")
    _write(repo, "src/unrelated.py", "OTHER = 1\n")
    _git(repo, "checkout", "-q", LANE_BRANCH)

    attribution = _resolver(repo, base, manifest, refs)

    assert attribution.refusal is not None
    assert attribution.refusal.endswith(f"Error code: {code}.")


def test_ref_moved_after_the_claim_is_refused_by_the_resolver_and_the_gate(merged_dependency_repo: dict[str, object]) -> None:
    """TOCTOU: the claim pins the SHA it verified; a name that moved afterwards refuses, naming both SHAs."""
    repo, base, manifest = merged_dependency_repo["repo"], merged_dependency_repo["base"], merged_dependency_repo["manifest"]
    dep_tip, lane_commit = merged_dependency_repo["dep_tip"], merged_dependency_repo["lane_commit"]
    assert isinstance(repo, Path) and isinstance(base, str) and isinstance(manifest, LanesManifest)
    assert isinstance(dep_tip, str) and isinstance(lane_commit, str)

    verified = _resolver(repo, base, manifest, (DEP_BRANCH,))
    assert verified.refusal is None and dict(verified.pins) == {DEP_BRANCH: dep_tip}
    # Pinned and unmoved: the pin is what is verified, and nothing changes.
    assert _resolver(repo, base, manifest, (DEP_BRANCH,), pins=verified.pins).shas == verified.shas

    _git(repo, "branch", "-f", DEP_BRANCH, lane_commit)  # the name now points at the lane's own commit

    moved = _resolver(repo, base, manifest, (DEP_BRANCH,), pins=verified.pins)
    assert moved.refusal is not None and moved.shas == frozenset()
    assert dep_tip in moved.refusal and lane_commit in moved.refusal
    assert moved.refusal.endswith("Error code: DEPENDENCY_REF_MOVED.")
    assert dependency_refs_moved_refusal(repo, verified.pins) == moved.refusal

    # The gate takes the same refusal: the captured claim is replaced by a refusing one.
    claim = _claim(external_dependency_refs=verified.refs, external_dependency_shas=verified.shas)
    run = SimpleNamespace(main_repo=repo, approved_wp_set=claim, strategy=MergeStrategy.MERGE, dependency_ref_pins=dict(verified.pins))
    assert _reconciliation_claim_for_gate(run).refusal == moved.refusal  # type: ignore[arg-type]
    # A name that no longer resolves is not "moved": the pinned commit still stands.
    _git(repo, "branch", "-D", DEP_BRANCH)
    assert dependency_refs_moved_refusal(repo, verified.pins) is None
    assert _resolver(repo, base, manifest, (DEP_BRANCH,), pins=verified.pins).refusal is None


def test_first_claim_pins_an_unpinned_record_once(merged_dependency_repo: dict[str, object]) -> None:
    """Back-compat: a record holding names only is pinned on first use, and a pin is never rewritten."""
    from specify_cli.consolidation.state import ConsolidationState, load_state

    repo, dep_tip = merged_dependency_repo["repo"], merged_dependency_repo["dep_tip"]
    assert isinstance(repo, Path) and isinstance(dep_tip, str)
    state = ConsolidationState(mission_id="m", mission_slug="s", target_branch="main", wp_order=["WP01"], dependency_refs=[DEP_BRANCH])
    run = SimpleNamespace(
        main_repo=repo,
        state=state,
        dependency_ref_pins={},
        approved_wp_set=_claim(external_dependency_pins={DEP_BRANCH: dep_tip}),
    )

    _pin_dependency_refs(run)  # type: ignore[arg-type]
    persisted = load_state(repo, "m")
    assert persisted is not None and persisted.dependency_ref_pins == {DEP_BRANCH: dep_tip}
    assert run.dependency_ref_pins == {DEP_BRANCH: dep_tip}

    run.approved_wp_set = _claim(external_dependency_pins={DEP_BRANCH: "f" * 40})
    _pin_dependency_refs(run)  # type: ignore[arg-type]
    assert run.dependency_ref_pins == {DEP_BRANCH: dep_tip}, "a pin is written once"
