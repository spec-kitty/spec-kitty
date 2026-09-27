"""Tests for the public ``spec-kitty safe-commit`` command."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mission_runtime import (
    MissionArtifactKind,
    is_primary_artifact_kind,
    kind_for_mission_file,
    resolve_placement_only,
)
from specify_cli import app as cli_app
from specify_cli.consolidation.baseline import record_baseline_merge_commit
from specify_cli.mission_metadata import load_meta, write_meta


pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

runner = CliRunner()


def _init_spec_kitty_repo(repo: Path) -> None:
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.json").write_text("{}\n", encoding="utf-8")
    (repo / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md", ".kittify/config.json"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, check=True, capture_output=True)


def _seed_merged_and_pruned_mission(tmp_path: Path, mission_slug: str) -> tuple[Path, str, str]:
    """Seed a genuine E2 (PUBLISHED) mission: consolidated, published, Target Ref pruned.

    Shared #3033 fixture shape -- exactly what ``spec-kitty merge`` +
    publish-to-trunk + branch cleanup leaves behind. Reproduces the REAL
    durable post-merge state the shipped write-surface fix keys on (ADR
    2026-07-30-1, ``LifecyclePhase.PUBLISHED`` == ``baseline_merge_commit``
    present AND Target Ref absent AND terminal-completion evidence): the
    mission's ``meta.json`` still names the now-deleted ``target_branch``, but
    it ALSO carries the ``baseline_merge_commit`` that ``record_baseline_merge_commit``
    (the real E1 bookkeeping ``spec-kitty merge`` calls) bakes in plus a
    ``mission_number`` (real merge-time bookkeeping, the terminal-completion
    evidence C-003 requires). Without those durable signals the phase reader
    (correctly) resolves ``PRE_CONSOLIDATION`` -- its safe default for a
    never-materialized Target Ref -- and the E2 write surface never engages;
    an earlier revision of this fixture omitted them and the pins failed on
    that gap, not on the product.

    The later authoring pass runs from the **repository-root checkout on the
    Primary Branch** (``main``), NOT a fresh off-checkout branch: the shipped
    FR-006 contract *refuses* off-checkout writes with a branch-named recovery
    hint rather than silently succeeding, so authoring a PRIMARY-kind artifact
    for a published mission legitimately happens on the Primary Branch. HEAD is
    left on ``main`` so the CLI pin exercises the sanctioned E2 write path.

    Extracted so both the CLI-level #3033 regression
    (``test_public_safe_commit_succeeds_after_merged_branch_deleted_3033``)
    and the seam-level #3033 regression
    (``test_resolve_placement_only_rejects_pruned_target_branch_3033``) drive
    the identical repo shape without duplicating the git choreography.

    Returns ``(feature_dir, feature_branch, primary_branch)`` where
    ``primary_branch`` is the branch HEAD is left on (``main``).
    """
    feature_branch = f"feat/{mission_slug}"
    primary_branch = "main"
    mission_id = "01KYHHR8RELATIONALCUT0001"

    _init_spec_kitty_repo(tmp_path)

    def _git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    baseline_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    _git("checkout", "-q", "-b", feature_branch)
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    meta = {
        "mission_id": mission_id,
        "mission_slug": mission_slug,
        "mission_type": "software-dev",
        "target_branch": feature_branch,
        "friendly_name": "Relational cutover",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"chore({mission_slug}): seed mission meta"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # E1: lane consolidation bakes ``baseline_merge_commit`` (via the REAL
    # merge-bookkeeping entry point) + assigns ``mission_number`` -- the
    # terminal-completion evidence a real consolidation produces (C-003 / D2).
    record_baseline_merge_commit(feature_dir, baseline_commit, mission_id=mission_id)
    consolidated_meta = load_meta(feature_dir)
    assert consolidated_meta is not None
    consolidated_meta["mission_number"] = 214
    write_meta(feature_dir, consolidated_meta, validate=False)
    _git("add", ".")
    _git(
        "commit",
        "-m",
        f"chore({mission_slug}): record baseline_merge_commit + mission_number (E1)",
    )

    # E2: publish to trunk (a real merge commit, mirroring a PR merge) and
    # prune the Target Ref -- exactly what publish + branch cleanup leaves
    # behind. The consolidated ``meta.json`` now lives at the Primary-Branch
    # tip, so ``content_present_at_primary_tip`` succeeds.
    _git("checkout", "-q", primary_branch)
    _git("merge", "-q", "--no-ff", feature_branch, "-m", f"Merge {feature_branch}")
    _git("branch", "-D", feature_branch)

    return feature_dir, feature_branch, primary_branch


@pytest.mark.parametrize(
    "message",
    [
        "chore: apply spec-kitty upgrade changes (3.0.3 -> 3.1.4)",
        "chore: release 3.2.0",
        "release: 3.2.0",
        "chore(099-demo): record done transitions for merged WPs",
    ],
)
def test_public_safe_commit_does_not_honor_internal_protected_branch_exceptions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    message: str,
) -> None:
    """Public CLI messages must not spoof internal safe_commit exceptions."""
    monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
    _init_spec_kitty_repo(tmp_path)
    (tmp_path / "change.txt").write_text("protected branch change\n", encoding="utf-8")
    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    monkeypatch.chdir(tmp_path)
    # Post-#1348 (WP02): --to-branch is required. The test runs on
    # `main` (the protected branch) so the helper rejects the commit at the
    # protected-branch check, which is what this test asserts.
    result = runner.invoke(
        cli_app,
        ["safe-commit", "--to-branch", "main", "--message", message, "--json", "change.txt"],
        catch_exceptions=False,
    )

    payload = json.loads(result.stdout)
    head_after = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert result.exit_code == 1
    assert payload["success"] is False
    assert "protected branch 'main'" in payload["error"]
    assert head_after == head_before


def test_public_safe_commit_rejects_protected_branch_in_test_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SPEC_KITTY_TEST_MODE must not let public safe-commit write to main."""
    monkeypatch.setenv("SPEC_KITTY_TEST_MODE", "1")
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
    _init_spec_kitty_repo(tmp_path)
    (tmp_path / "change.txt").write_text("protected branch change\n", encoding="utf-8")
    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli_app,
        [
            "safe-commit",
            "--to-branch",
            "main",
            "--message",
            "WP01: arbitrary status write",
            "--json",
            "change.txt",
        ],
        catch_exceptions=False,
    )

    payload = json.loads(result.stdout)
    head_after = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert result.exit_code == 1
    assert payload["success"] is False
    assert "protected branch 'main'" in payload["error"]
    assert head_after == head_before


def test_public_safe_commit_succeeds_after_merged_branch_deleted_3033(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression guard for the fixed #3033 defect: post-merge write used to
    fail once the merged mission branch was pruned. #3033 is fixed;
    ``@pytest.mark.regression`` removed (landing fold: make the marker mean
    exactly one thing) now that this test passes as a permanent guard.

    ``spec-kitty safe-commit`` (no ``--to-branch``, which is load-bearing --
    passing it short-circuits the defect at
    ``src/specify_cli/cli/commands/safe_commit_cmd.py:267``) resolves a
    PRIMARY-kind mission artifact's destination through
    ``_resolve_mission_aware_target`` ->
    ``mission_runtime.resolve_placement_only`` ->
    ``specify_cli.core.paths.get_feature_target_branch``
    (``src/specify_cli/core/paths.py:696-733``): a bare ``meta.json`` read of
    ``target_branch`` with NO existence check against git and no
    lifecycle-phase input. Once the mission's feature branch has been merged
    and pruned (``git branch -D``) -- exactly what happens after
    ``spec-kitty merge`` + publish-to-trunk -- authoring a PRIMARY-kind
    artifact (e.g. the retrospective) resolved a ``CommitTarget.ref`` that
    still pointed at the now-nonexistent feature branch, and ``safe_commit``'s
    embedded HEAD-match guard refused the commit
    (``safe_commit: worktree ... expected 'feat/...'``).

    The shipped fix (ADR 2026-07-30-1) makes ``resolve_placement_only``
    lifecycle-aware: for a PUBLISHED mission it resolves the write to the
    Primary Branch. Authoring therefore runs from the repository-root checkout
    on ``main`` (FR-006 refuses off-checkout writes rather than silently
    succeeding), and this test drives that sanctioned E2 write path end-to-end
    through the public ``safe-commit`` CLI.

    ``retrospective.yaml`` is deliberately the changeset here because
    ``mission-review-report.md`` is NOT a member of
    ``_MISSION_FILE_KIND_BY_BASENAME``
    (``src/mission_runtime/artifacts.py:195-220``) -- a commit for that
    basename falls through the mission-aware branch entirely and lands on the
    generic HEAD path, where it would *succeed* despite the same pruned
    branch, masking this defect. Also: ``spec-kitty review`` itself performs
    no commit, so this defect is NOT reachable through the review command
    despite what issue #3033's body says -- it is reachable through any
    direct ``safe-commit`` of a PRIMARY-kind mission artifact (retrospective,
    spec, plan, tasks, analysis-report, ...) once the feature branch is gone.

    This test asserts the OUTCOME, not a particular destination branch name
    (#3033 SS7: "asserted through the seam, not through the review command" /
    "lands on a surface that can be resolved and read back"): beyond
    ``success`` / ``committed``, it re-resolves the branch the commit actually
    left ``HEAD`` on, asserts that ref still exists (``git rev-parse
    --verify``), and reads the artifact content back from it via ``git show
    <ref>:<path>``. A fix that reports ``committed: true`` without the
    content being durably retrievable from an existing ref must not pass.

    Honest limit: because this test drives only the public ``safe-commit``
    CLI (a black-box entry point), a call-site patch in
    ``_resolve_commit_target`` that falls back to the current ``HEAD`` branch
    when the resolved ``target_branch`` does not exist would ALSO satisfy
    these assertions -- ``HEAD`` is by construction an existing, readable ref.
    These assertions catch a broken/fake "success" (nothing durably
    committed, or committed somewhere unresolvable); they cannot mechanically
    prove the fix lives at the seam (``get_feature_target_branch`` /
    ``resolve_placement_only`` gaining post-merge lifecycle awareness) rather
    than at this one call site. Per #3033 SS7 that seam-level placement is the
    binding fix constraint -- whack-a-field call-site patches leave the
    retrospective terminus (SS6) and the acceptance-matrix refresh exposed to
    the identical hole -- but confirming that requires a test on the seam
    itself, not on this command.
    """
    monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)

    mission_slug = "relational-cutover-01KYHHR8"
    feature_dir, _feature_branch, _primary_branch = _seed_merged_and_pruned_mission(tmp_path, mission_slug)

    retro_path = feature_dir / "retrospective.yaml"
    retro_path.write_text(
        "summary: Relational cutover retrospective\nlessons_learned:\n  - Post-merge writes must not require the merged branch to still exist.\n",
        encoding="utf-8",
    )

    # Precondition (MINOR guard): this test's entire value rests on
    # `retrospective.yaml` classifying to a PRIMARY-partition kind -- an
    # unclassified basename falls through to the generic HEAD path (see
    # docstring) and succeeds regardless of the defect. Assert that
    # classification through the public helpers so a future reclassification
    # (or a COORD re-home) makes THIS assertion fail loudly instead of the
    # test silently going green for the wrong reason.
    retro_kind = kind_for_mission_file(retro_path.relative_to(tmp_path), mission_slug=mission_slug)
    assert retro_kind is MissionArtifactKind.RETROSPECTIVE, retro_kind
    assert is_primary_artifact_kind(retro_kind), "retrospective.yaml must classify to a PRIMARY-partition kind for this regression to exercise the #3033 defect"

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli_app,
        [
            "safe-commit",
            "--message",
            f"chore({mission_slug}): record retrospective",
            "--json",
            str(retro_path.relative_to(tmp_path)),
        ],
        catch_exceptions=False,
    )

    payload = json.loads(result.stdout)

    assert payload["success"] is True, payload
    assert payload["committed"] is True, payload

    # Strengthened per #3033 SS7 ("lands on a surface that can be resolved and
    # read back"): a bare success/committed flag is satisfied by a fix that
    # silently drops the write. Re-resolve the ref the commit actually landed
    # on (safe_commit's own HEAD-match guard means that ref is whatever branch
    # is checked out post-invocation) and prove it is (a) a ref git can still
    # resolve, and (b) the artifact's content is retrievable from it -- not
    # merely present in the working tree.
    landed_ref = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "rev-parse", "--verify", landed_ref],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    retro_rel = retro_path.relative_to(tmp_path).as_posix()
    committed_blob = subprocess.run(
        ["git", "show", f"{landed_ref}:{retro_rel}"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "Post-merge writes must not require the merged branch to still exist." in committed_blob, committed_blob


def test_resolve_placement_only_rejects_pruned_target_branch_3033(
    tmp_path: Path,
) -> None:
    """Regression guard for the fixed #3033 defect: the seam itself used to
    hand back a pruned branch -- not a CLI artifact. #3033 is fixed;
    ``@pytest.mark.regression`` removed (landing fold: make the marker mean
    exactly one thing) now that this test passes as a permanent guard.

    #3033 SS7 is explicit: "Fixing it at one call site is whack-a-field."
    ``test_public_safe_commit_succeeds_after_merged_branch_deleted_3033``
    above documents its own "Honest limit": because it drives only the
    public ``safe-commit`` CLI, a call-site patch inside
    ``safe_commit_cmd._resolve_commit_target`` that falls back to the
    checked-out ``HEAD`` branch whenever the resolved ``target_branch``
    doesn't exist would ALSO satisfy that test's assertions -- ``HEAD`` is by
    construction an existing, readable ref, so "ref exists" and "content
    readable back from that ref" are both trivially true for a HEAD
    fallback. That test alone cannot mechanically force the fix to live at
    the seam. This test exists BECAUSE of that gap, and the two are meant to
    be discharged TOGETHER, not interchangeably.

    This test never calls ``safe-commit`` and never goes near
    ``_resolve_commit_target``. It calls the placement seam directly:
    ``mission_runtime.resolve_placement_only`` -- which, for a
    ``MissionArtifactKind.RETROSPECTIVE`` (a PRIMARY-partition kind), returns
    ``CommitTarget(ref=target_branch)`` where ``target_branch`` comes
    straight from ``specify_cli.core.paths.get_feature_target_branch``: a
    bare ``meta.json`` read of ``target_branch`` with NO existence check
    against git and no lifecycle-phase input (see
    ``src/mission_runtime/resolution.py`` around ``resolve_placement_only``'s
    ``if kind in _PRIMARY_ARTIFACT_KINDS: return CommitTarget(ref=target_branch)``
    arm, and ``get_feature_target_branch`` in
    ``src/specify_cli/core/paths.py``). A ``_resolve_commit_target``
    HEAD-fallback patch cannot make this test pass -- it is not on this call
    path at all; the only way to turn this red pin green is to make the seam
    itself existence-checked / lifecycle-aware, which is exactly #3033 SS7's
    binding constraint.

    Contract pinned: for a mission whose ``target_branch`` has been merged
    and pruned, the placement seam must resolve a destination that actually
    exists in the repository -- it must not hand back a ref naming a branch
    that is gone.
    """
    mission_slug = "relational-cutover-01KYHHR8"
    feature_dir, feature_branch, _primary_branch = _seed_merged_and_pruned_mission(tmp_path, mission_slug)
    assert feature_dir.exists()  # sanity: the shared fixture did seed the mission

    target = resolve_placement_only(tmp_path, mission_slug, kind=MissionArtifactKind.RETROSPECTIVE)

    ref_exists = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{target.ref}"],
        cwd=tmp_path,
        capture_output=True,
    )
    assert ref_exists.returncode == 0, (
        f"resolve_placement_only resolved {target.ref!r} for a mission whose "
        "feature branch was merged and pruned -- the placement seam handed "
        "back a destination git can no longer verify. Per #3033 SS7, the fix "
        "belongs at the seam (get_feature_target_branch / "
        "resolve_placement_only gaining post-merge lifecycle awareness), not "
        "as a call-site HEAD fallback in _resolve_commit_target."
    )
    assert target.ref != feature_branch, f"resolve_placement_only must not hand back the pruned feature branch {feature_branch!r} verbatim"


# ---------------------------------------------------------------------------
# partition-authority-residuals (#2966 follow-up): _resolve_mission_aware_target
# calls mission_runtime.resolve_placement_only DIRECTLY (restored -- WP05
# briefly rerouted this through the shared resolve_write_target_or_degrade
# helper for parity with the 3 sibling committers, but that helper's
# _mission_meta_exists pre-gate short-circuits BEFORE resolve_placement_only
# is ever consulted for a mission with no meta.json yet -- exactly the
# create->first-write window a freshly-written kitty-specs/<slug>/spec.md
# sits in (the #2063 case this function exists to fix). See
# _resolve_mission_aware_target's docstring for the full rationale.
#
# Refusal contract (unchanged throughout):
#   * CONSOLIDATED_CONTENT_ABSENT  -> raises MissionAwareCommitRefused
#   * benign FileNotFoundError / ValueError / other ActionContextError -> None
# ---------------------------------------------------------------------------
import mission_runtime as _mission_runtime  # noqa: E402
from mission_runtime import CommitTarget  # noqa: E402
from specify_cli.cli.commands.safe_commit_cmd import (  # noqa: E402
    MissionAwareCommitRefused,
    _CONSOLIDATED_CONTENT_ABSENT_CODE,
    _resolve_mission_aware_target,
)


def _guard_no_shared_helper_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if the fix routes through the shared degrade helper.

    The shared ``resolve_write_target_or_degrade`` helper's
    ``_mission_meta_exists`` pre-gate is the wrong contract for this call
    site (see the module comment above); this sentinel turns a call into
    that helper into a hard error so the routing tests catch a regression
    back to the WP05 shape.
    """

    def _boom(*_a: object, **_k: object) -> object:
        raise AssertionError(
            "_resolve_mission_aware_target must NOT route through "
            "resolve_write_target_or_degrade -- its _mission_meta_exists "
            "pre-gate blocks resolve_placement_only for a meta-less "
            "kitty-specs/ artifact (the #2063 create-window case). It must "
            "call resolve_placement_only directly."
        )

    monkeypatch.setattr(_mission_runtime, "resolve_write_target_or_degrade", _boom)


def test_resolve_mission_aware_target_calls_placement_only_directly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The mission-aware target resolves via a direct ``resolve_placement_only`` call.

    Asserts (a) ``resolve_placement_only`` is invoked with the mission slug
    and kind threaded through (no shared-helper indirection, no meta-gate)
    and (b) its resolved ``CommitTarget`` is returned verbatim.
    """
    _guard_no_shared_helper_call(monkeypatch)
    calls: list[dict[str, object]] = []
    sentinel = CommitTarget(ref="seam-resolved-branch")

    def _fake_resolve_placement_only(
        repo_root: Path,
        mission_slug: str,
        *,
        kind: MissionArtifactKind,
    ) -> CommitTarget:
        calls.append(
            {
                "repo_root": repo_root,
                "mission_slug": mission_slug,
                "kind": kind,
            }
        )
        return sentinel

    monkeypatch.setattr(_mission_runtime, "resolve_placement_only", _fake_resolve_placement_only)

    result = _resolve_mission_aware_target(tmp_path, "my-mission", MissionArtifactKind.SPEC)

    assert result is sentinel
    assert calls == [
        {
            "repo_root": tmp_path,
            "mission_slug": "my-mission",
            "kind": MissionArtifactKind.SPEC,
        }
    ]


def test_resolve_mission_aware_target_consolidated_absent_still_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CONSOLIDATED_CONTENT_ABSENT -> MissionAwareCommitRefused.

    ``resolve_placement_only`` itself raises this structured off-checkout
    refusal (FR-006 / SC-004); it MUST still translate to
    ``MissionAwareCommitRefused`` rather than degrade to the WRONG (HEAD)
    branch.
    """
    _guard_no_shared_helper_call(monkeypatch)

    def _fake_resolve_placement_only(*_a: object, **_k: object) -> CommitTarget:
        raise _mission_runtime.ActionContextError(
            _CONSOLIDATED_CONTENT_ABSENT_CODE,
            "mission is published but this checkout lacks consolidated content",
        )

    monkeypatch.setattr(_mission_runtime, "resolve_placement_only", _fake_resolve_placement_only)

    with pytest.raises(MissionAwareCommitRefused):
        _resolve_mission_aware_target(tmp_path, "published-mission", MissionArtifactKind.SPEC)


@pytest.mark.parametrize(
    "raised",
    [
        pytest.param(
            _mission_runtime.ActionContextError("FEATURE_CONTEXT_UNRESOLVED", "no meta"),
            id="benign-action-context-error",
        ),
        pytest.param(FileNotFoundError("meta.json missing"), id="file-not-found"),
        pytest.param(ValueError("not a resolvable mission path"), id="value-error"),
    ],
)
def test_resolve_mission_aware_target_benign_failure_still_degrades(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raised: Exception) -> None:
    """Benign resolution failures still degrade to ``None``.

    A legitimate operator commit that merely *looks* mission-scoped (no
    ``meta.json`` yet, an ad-hoc fixture, or a non-CONSOLIDATED resolution
    error) must keep degrading to ``None`` so the caller falls back to the
    generic HEAD path.
    """
    _guard_no_shared_helper_call(monkeypatch)

    def _fake_resolve_placement_only(*_a: object, **_k: object) -> CommitTarget:
        raise raised

    monkeypatch.setattr(_mission_runtime, "resolve_placement_only", _fake_resolve_placement_only)

    assert _resolve_mission_aware_target(tmp_path, "looks-like-mission", MissionArtifactKind.SPEC) is None
