"""WP17 owned-arm tests: history and support modules take the ``OwnedCheckout`` fact.

owned-checkout-lifecycle-authority WP17 (FR-001, FR-022). Every converted
function is called with ``owned=fact`` while a stale copy of the mission sits in
the repository root checkout R. The output must land under the owned checkout P
and nothing may appear under R (NFR-001, ``r_snapshot`` shows 0 differences).
The owned arms never consult a resolver: ``get_main_repo_root`` is poisoned in
every test that can run without a legacy fallback.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from mission_runtime import OwnedCheckout
from specify_cli.cli.commands import _owned_checkout
from specify_cli.core.owned_mission import LIFECYCLE_OWNED_TOPOLOGIES
from tests._owned_fixtures import RSnapshotter
from tests.integration.conftest import (
    OwnedCheckouts,
    make_owned_checkouts,
    make_r_snapshot,
    owned_checkouts,
    r_snapshot,
    stale_root_copy,
)

__all__ = ["make_owned_checkouts", "make_r_snapshot", "owned_checkouts", "r_snapshot", "stale_root_copy"]
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


class _ResolverConsulted(AssertionError):
    """Raised by a poisoned resolver: an owned arm must never reach one."""


class _AllowAllPolicy:
    def is_protected(self, ref: str) -> bool:  # noqa: ARG002 - fixed-answer stub
        return False


def _poison_main_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``get_main_repo_root`` RAISE, so an owned arm cannot re-derive R."""

    def _boom(*_args: object, **_kwargs: object) -> Any:
        raise _ResolverConsulted

    from specify_cli.core import paths

    monkeypatch.setattr(paths, "get_main_repo_root", _boom)


def _under(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def _outside_r(path: Path, checkouts: OwnedCheckouts) -> bool:
    """True when ``path`` is not under R (P's own subtree is excluded when P nests in R)."""
    if _under(path, checkouts.owned_root):
        return True
    return not _under(path, checkouts.repository_root)


@pytest.fixture
def fact(owned_checkouts: OwnedCheckouts) -> OwnedCheckout:
    """The validated fact for the standard R/P/S triple, minted through the shared helper."""
    minted = _owned_checkout.resolve_owned_or_adopt(
        owned_checkouts.repository_root,
        owned_checkouts.owned_root,
        owned_checkouts.mission_slug,
        cwd=owned_checkouts.owned_root,
        allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
    )
    assert minted is not None
    return minted


@pytest.fixture
def stale_r(stale_root_copy: Callable[..., Path]) -> Path:
    """R carries a stale copy of the mission (same id, different WP set and lane map)."""
    return stale_root_copy()


def _write_spec(mission_dir: Path, body: str) -> Path:
    spec = mission_dir / "spec.md"
    spec.write_text(body, encoding="utf-8")
    return spec


# ---------------------------------------------------------------------------
# T090 -- tasks/issue_matrix.py
# ---------------------------------------------------------------------------


def _matrix_rows() -> dict[str, Any]:
    from specify_cli.tasks.issue_matrix import IssueMatrixEntry

    return {"#4321": IssueMatrixEntry(verdict="unknown", evidence_ref="<link or commit>", title="t", source_file="spec.md")}


def test_write_issue_matrix_owned_lands_under_p_only(
    owned_checkouts: OwnedCheckouts,
    fact: OwnedCheckout,
    stale_r: Path,
    r_snapshot: RSnapshotter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``write_issue_matrix(owned=fact)`` writes and commits the matrix in P, never in R."""
    from specify_cli.tasks.issue_matrix import write_issue_matrix

    before = r_snapshot.take()
    _poison_main_repo_root(monkeypatch)

    result = write_issue_matrix(
        repo_root=fact.repository_root,
        mission_slug=fact.mission_slug,
        rows=_matrix_rows(),
        policy=_AllowAllPolicy(),
        owned=fact,
    )

    assert result.status in ("committed", "unchanged"), result.diagnostic
    written = fact.mission_dir / "issue-matrix.json"
    assert written.exists()
    assert _outside_r(written, owned_checkouts)
    assert not (stale_r / "issue-matrix.json").exists()
    r_snapshot.assert_unchanged(before, r_snapshot.take(), tolerate_status_mutex_for=fact.mission_slug)


def test_scaffold_issue_matrix_owned_lands_under_p_only(
    owned_checkouts: OwnedCheckouts,
    fact: OwnedCheckout,
    stale_r: Path,
    r_snapshot: RSnapshotter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``scaffold_issue_matrix(owned=fact)`` reads P's spec and scaffolds the matrix under P."""
    from specify_cli.tasks.issue_matrix import scaffold_issue_matrix

    spec = _write_spec(fact.mission_dir, "# Spec\n\nCloses #4321.\n")
    before = r_snapshot.take()
    _poison_main_repo_root(monkeypatch)

    out = scaffold_issue_matrix(
        fact.mission_dir,
        spec,
        repo_root=fact.repository_root,
        mission_slug=fact.mission_slug,
        policy=_AllowAllPolicy(),
        owned=fact,
    )

    assert out == fact.mission_dir / "issue-matrix.json"
    assert "#4321" in json.loads(out.read_text(encoding="utf-8"))["rows"]
    assert _outside_r(out, owned_checkouts)
    assert not (stale_r / "issue-matrix.json").exists()
    r_snapshot.assert_unchanged(before, r_snapshot.take(), tolerate_status_mutex_for=fact.mission_slug)


def test_scaffold_issue_matrix_owned_is_idempotent_before_any_write(
    fact: OwnedCheckout,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An existing matrix in P short-circuits the owned arm before any write is attempted."""
    from specify_cli.tasks import issue_matrix

    existing = fact.mission_dir / "issue-matrix.json"
    existing.write_text('{"schema_version": 1, "rows": {}}\n', encoding="utf-8")
    spec = _write_spec(fact.mission_dir, "Closes #4321.\n")

    def _no_write(**_kwargs: object) -> object:
        raise AssertionError("idempotent early return must fire before any write")

    monkeypatch.setattr(issue_matrix, "write_issue_matrix", _no_write)

    out = issue_matrix.scaffold_issue_matrix(
        fact.mission_dir,
        spec,
        repo_root=fact.repository_root,
        mission_slug=fact.mission_slug,
        policy=_AllowAllPolicy(),
        owned=fact,
    )

    assert out == existing
    assert existing.read_text(encoding="utf-8") == '{"schema_version": 1, "rows": {}}\n'


def test_scaffold_issue_matrix_owned_fold_into_caller_commit_is_a_bare_write(
    fact: OwnedCheckout,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``fold_into_caller_commit`` keeps its bare-write behaviour under the owned arm (WP13 carry-forward)."""
    from specify_cli.tasks import issue_matrix

    spec = _write_spec(fact.mission_dir, "Closes #4321.\n")

    def _no_commit(**_kwargs: object) -> object:
        raise AssertionError("a folded scaffold must not commit on its own")

    monkeypatch.setattr(issue_matrix, "write_issue_matrix", _no_commit)

    out = issue_matrix.scaffold_issue_matrix(
        fact.mission_dir,
        spec,
        repo_root=fact.repository_root,
        mission_slug=fact.mission_slug,
        policy=_AllowAllPolicy(),
        fold_into_caller_commit=True,
        owned=fact,
    )

    assert out == fact.mission_dir / "issue-matrix.json"
    assert out.exists()


def test_scaffold_issue_matrix_owned_write_failure_raises_but_unowned_returns_none(
    fact: OwnedCheckout,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refused owned write raises; the same refusal on the non-owned arm stays best-effort."""
    from specify_cli.coordination.write_seam import WriteSeamResult
    from specify_cli.tasks import issue_matrix

    spec = _write_spec(fact.mission_dir, "Closes #4321.\n")
    refused = WriteSeamResult(status="refused", entry_id="finalize-scaffold", destination_surface=None, diagnostic="nope")
    monkeypatch.setattr(issue_matrix, "write_issue_matrix", lambda **_kwargs: refused)
    kwargs: dict[str, Any] = {
        "repo_root": fact.repository_root,
        "mission_slug": fact.mission_slug,
        "policy": _AllowAllPolicy(),
    }

    with pytest.raises(RuntimeError, match="nope"):
        issue_matrix.scaffold_issue_matrix(fact.mission_dir, spec, owned=fact, **kwargs)

    import mission_runtime

    monkeypatch.setattr(mission_runtime, "coord_read_dir_for", lambda *a, **k: None)
    assert issue_matrix.scaffold_issue_matrix(fact.mission_dir, spec, **kwargs) is None


# ---------------------------------------------------------------------------
# T091 campsite -- review/cycle.py helpers extracted from create_rejected_review_cycle
# ---------------------------------------------------------------------------


def test_resolve_review_body_prefers_a_valid_feedback_file_and_a_generated_body(tmp_path: Path) -> None:
    """A feedback file is read after its checks; a caller-generated body bypasses the file checks."""
    from specify_cli.review.cycle import ReviewCycleError, _resolve_review_body

    feedback = tmp_path / "feedback.md"
    feedback.write_text("real feedback\n", encoding="utf-8")

    assert _resolve_review_body(feedback_source=feedback, body=None, sub_artifact_dir=tmp_path / "tasks") == "real feedback\n"
    assert _resolve_review_body(feedback_source=None, body="generated\n", sub_artifact_dir=tmp_path) == "generated\n"
    with pytest.raises(ReviewCycleError, match="body is empty"):
        _resolve_review_body(feedback_source=None, body="  \n", sub_artifact_dir=tmp_path)
    with pytest.raises(ReviewCycleError, match="not found"):
        _resolve_review_body(feedback_source=tmp_path / "missing.md", body=None, sub_artifact_dir=tmp_path)
    with pytest.raises(ReviewCycleError, match="not a file"):
        _resolve_review_body(feedback_source=tmp_path, body=None, sub_artifact_dir=tmp_path)
    empty = tmp_path / "empty.md"
    empty.write_text("\n", encoding="utf-8")
    with pytest.raises(ReviewCycleError, match="empty"):
        _resolve_review_body(feedback_source=empty, body=None, sub_artifact_dir=tmp_path)


def test_persistence_after_commit_exception_is_durable_only_when_the_bytes_are_at_the_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A commit that raised is ``durable`` on an exact read-back, else ``persistence_failed`` with a typed reason."""
    from specify_cli.review import cycle

    artifact = tmp_path / "review-cycle-1.md"
    artifact.write_bytes(b"evidence")
    kwargs: dict[str, Any] = {"operation_root": tmp_path, "artifact_path": artifact, "evidence_ref": "review-cycle-1.md", "destination_ref": "main"}

    monkeypatch.setattr(cycle, "_read_artifact_at_ref", lambda *_a, **_k: b"evidence")
    durable = cycle._persistence_after_commit_exception(RuntimeError("late"), **kwargs)
    assert (durable.classification, durable.reason) == ("durable", None)

    monkeypatch.setattr(cycle, "_read_artifact_at_ref", lambda *_a, **_k: None)
    timed_out = cycle._persistence_after_commit_exception(TimeoutError("slow"), **kwargs)
    assert (timed_out.classification, timed_out.reason) == ("persistence_failed", "commit_timeout")
    raised = cycle._persistence_after_commit_exception(RuntimeError("boom"), **kwargs)
    assert raised.reason == "commit_exception"
    assert "boom" in raised.message


# ---------------------------------------------------------------------------
# T091 -- review/cycle.py
# ---------------------------------------------------------------------------

_WP_ID = "WP01"
_WP_SLUG = "WP01-owned"
_FEEDBACK_BODY = "**Issue**: owned arm must stay inside P.\n"


def _git_out(root: Path, *args: str) -> str:
    import subprocess

    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def test_review_cycle_wp_dir_owned_resolves_under_p(
    owned_checkouts: OwnedCheckouts,
    fact: OwnedCheckout,
    stale_r: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_review_cycle_wp_dir(owned=fact)`` names P's ``tasks/<wp>`` dir for both kinds, never R's."""
    from mission_runtime import MissionArtifactKind
    from specify_cli.review import cycle

    _poison_main_repo_root(monkeypatch)

    for kind in (MissionArtifactKind.WORK_PACKAGE_TASK, MissionArtifactKind.REVIEW_CYCLE):
        resolved = cycle._review_cycle_wp_dir(fact.repository_root, fact.mission_slug, _WP_SLUG, kind=kind, owned=fact)
        assert resolved == fact.mission_dir / "tasks" / _WP_SLUG
        assert _outside_r(resolved, owned_checkouts)
        assert not _under(resolved, stale_r)


def test_operation_root_is_the_owned_root_or_the_repository_root(fact: OwnedCheckout, tmp_path: Path) -> None:
    """The one operation-root helper: the fact's owned root when owned, else the caller's root."""
    from specify_cli.review import cycle

    assert cycle._operation_root(tmp_path, fact) == fact.owned_root
    assert cycle._operation_root(tmp_path, None) == tmp_path


def test_create_rejected_review_cycle_owned_local_only_lands_under_p(
    owned_checkouts: OwnedCheckouts,
    fact: OwnedCheckout,
    stale_r: Path,
    r_snapshot: RSnapshotter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a commit router the owned rejection cycle is written under P and reported ``local_only``."""
    from specify_cli.review.cycle import create_rejected_review_cycle

    before = r_snapshot.take()
    _poison_main_repo_root(monkeypatch)

    created = create_rejected_review_cycle(
        main_repo_root=fact.repository_root,
        mission_slug=fact.mission_slug,
        wp_id=_WP_ID,
        wp_slug=_WP_SLUG,
        body=_FEEDBACK_BODY,
        reviewer_agent="reviewer-renata",
        owned=fact,
    )

    assert created.artifact_path.parent == fact.mission_dir / "tasks" / _WP_SLUG
    assert _outside_r(created.artifact_path, owned_checkouts)
    assert created.persistence.classification == "local_only"
    assert created.persistence.evidence_ref == created.artifact_path.relative_to(fact.owned_root).as_posix()
    assert not any(stale_r.rglob("review-cycle-*.md"))
    r_snapshot.assert_unchanged(before, r_snapshot.take(), tolerate_status_mutex_for=fact.mission_slug)


def test_create_rejected_review_cycle_owned_commits_on_p_and_adopts_identical_retry(
    owned_checkouts: OwnedCheckouts,
    fact: OwnedCheckout,
    stale_r: Path,
    r_snapshot: RSnapshotter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the real router the owned cycle is committed on P's branch; an identical retry adopts it.

    Exercises ``_adopt_or_allocate_review_cycle_locked`` and
    ``_commit_review_cycle_artifact`` through their only public entry.
    """
    from specify_cli.agent_tasks_ports import RealCoordCommitRouter
    from specify_cli.review.cycle import create_rejected_review_cycle

    before = r_snapshot.take()
    _poison_main_repo_root(monkeypatch)
    kwargs: dict[str, Any] = {
        "main_repo_root": fact.repository_root,
        "mission_slug": fact.mission_slug,
        "wp_id": _WP_ID,
        "wp_slug": _WP_SLUG,
        "body": _FEEDBACK_BODY,
        "reviewer_agent": "reviewer-renata",
        "commit_router": RealCoordCommitRouter(),
        "owned": fact,
    }

    first = create_rejected_review_cycle(**kwargs)

    assert first.persistence.classification == "durable", first.persistence.message
    evidence = first.persistence.evidence_ref
    assert _git_out(fact.owned_root, "show", f"{fact.write_branch}:{evidence}") == first.artifact_path.read_text(encoding="utf-8").strip()
    assert _git_out(fact.owned_root, "status", "--porcelain", "--", evidence) == ""
    assert _outside_r(first.artifact_path, owned_checkouts)
    assert not any(stale_r.rglob("review-cycle-*.md"))

    retry = create_rejected_review_cycle(**kwargs)

    assert retry.artifact_path == first.artifact_path
    assert retry.persistence.classification == "durable"
    r_snapshot.assert_unchanged(before, r_snapshot.take(), tolerate_status_mutex_for=fact.mission_slug)


def test_owned_review_cycle_commit_uses_owned_scoped_policy(
    owned_checkouts: OwnedCheckouts,
    fact: OwnedCheckout,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#5947 owned-correctness: the owned review-cycle commit builds its protection
    policy from the validated owned fact (``resolve_for_owned(owned, mission_slug)``),
    never the R-only, mission-unscoped ``resolve(main_repo_root)``. By-construction:
    the R-only resolver is forbidden, so a regression that reinstates it fails here."""
    from specify_cli.agent_tasks_ports import RealCoordCommitRouter
    from specify_cli.review import cycle
    from specify_cli.review.cycle import create_rejected_review_cycle

    _poison_main_repo_root(monkeypatch)

    class _PrimaryPolicyUsed(AssertionError):
        pass

    def _forbid_primary(*_args: object, **_kwargs: object) -> Any:
        raise _PrimaryPolicyUsed

    real_owned = cycle.ProtectionPolicy.resolve_for_owned
    owned_calls: list[tuple[object, object]] = []

    def _spy_owned(owned: object, mission_slug: object = None) -> Any:
        owned_calls.append((owned, mission_slug))
        return real_owned(owned, mission_slug)

    monkeypatch.setattr(cycle.ProtectionPolicy, "resolve", staticmethod(_forbid_primary))
    monkeypatch.setattr(cycle.ProtectionPolicy, "resolve_for_owned", staticmethod(_spy_owned))

    created = create_rejected_review_cycle(
        main_repo_root=fact.repository_root,
        mission_slug=fact.mission_slug,
        wp_id=_WP_ID,
        wp_slug=_WP_SLUG,
        body=_FEEDBACK_BODY,
        reviewer_agent="reviewer-renata",
        commit_router=RealCoordCommitRouter(),
        owned=fact,
    )

    assert created.persistence.classification == "durable", created.persistence.message
    assert (fact, fact.mission_slug) in owned_calls


# ---------------------------------------------------------------------------
# T092 -- consolidation/baseline.py
# ---------------------------------------------------------------------------

_BOGUS_TARGET = "bogus-unreachable-target"


def _read_meta(mission_dir: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((mission_dir / "meta.json").read_text(encoding="utf-8"))
    return loaded


@pytest.fixture
def landing(owned_checkouts: OwnedCheckouts, fact: OwnedCheckout, stale_r: Path) -> str:
    """The commit that introduced P's mission corpus on the target branch, with R's stale meta declaring a bogus target.

    P's fixture commit is a single-parent landing on ``codex/owned`` whose
    parent lacks the corpus. R's stale ``meta.json`` declares a target branch
    that does not exist, so any read that resolves R instead of P is refused.
    """
    stale_meta = _read_meta(stale_r)
    stale_meta["target_branch"] = _BOGUS_TARGET
    (stale_r / "meta.json").write_text(json.dumps(stale_meta), encoding="utf-8")
    return _git_out(fact.owned_root, "rev-parse", "HEAD")


def test_resolve_primary_meta_dir_owned_is_p_mission_dir(
    fact: OwnedCheckout,
    landing: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``resolve_primary_meta_dir(owned=fact)`` is P's mission dir, with no resolver consulted."""
    from specify_cli.consolidation.baseline import resolve_primary_meta_dir

    _poison_main_repo_root(monkeypatch)

    assert resolve_primary_meta_dir(fact.repository_root, fact.mission_slug, owned=fact) == fact.mission_dir


def test_verify_pr_merge_evidence_owned_reads_p_declared_target(
    fact: OwnedCheckout,
    landing: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The declared-target read resolves P's ``meta.json`` (real branch), not R's stale bogus target."""
    from specify_cli.consolidation.baseline import PrMergeEvidenceError, verify_pr_merge_evidence

    with pytest.raises(PrMergeEvidenceError, match=_BOGUS_TARGET):
        verify_pr_merge_evidence(fact.repository_root, fact.mission_slug, landing, attest_first_landing=True)

    _poison_main_repo_root(monkeypatch)
    evidence = verify_pr_merge_evidence(fact.repository_root, fact.mission_slug, landing, attest_first_landing=True, owned=fact)

    assert evidence.pr_merge_commit == landing


def test_record_pr_merge_baseline_owned_writes_only_p_meta(
    owned_checkouts: OwnedCheckouts,
    fact: OwnedCheckout,
    landing: str,
    stale_r: Path,
    r_snapshot: RSnapshotter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``record_pr_merge_baseline_for_mission(owned=fact)`` stamps P's ``meta.json`` and leaves R untouched.

    The write leg and the verification's declared-target read resolve the
    same ``owned``, so they can never pick different ``meta.json`` files.
    """
    from specify_cli.consolidation.baseline import record_pr_merge_baseline_for_mission

    before = r_snapshot.take()
    _poison_main_repo_root(monkeypatch)

    evidence = record_pr_merge_baseline_for_mission(
        fact.repository_root,
        fact.mission_slug,
        landing,
        attest_first_landing=True,
        owned=fact,
    )

    p_meta = _read_meta(fact.mission_dir)
    assert p_meta["baseline_merge_commit"] == evidence.baseline_merge_commit
    assert p_meta["pr_merge_commit"] == landing
    assert "baseline_merge_commit" not in _read_meta(stale_r)
    assert _outside_r(fact.mission_dir / "meta.json", owned_checkouts)
    r_snapshot.assert_unchanged(before, r_snapshot.take(), tolerate_status_mutex_for=fact.mission_slug)


def test_record_pr_merge_baseline_private_writer_owned_targets_feature_dir(
    fact: OwnedCheckout,
    landing: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The feature-dir-level writer forwards ``owned`` to the verification's declared-target read."""
    from specify_cli.consolidation.baseline import _record_pr_merge_baseline

    _poison_main_repo_root(monkeypatch)

    evidence = _record_pr_merge_baseline(
        fact.mission_dir,
        fact.repository_root,
        fact.mission_slug,
        landing,
        attest_first_landing=True,
        owned=fact,
    )

    assert _read_meta(fact.mission_dir)["pr_merge_commit"] == evidence.pr_merge_commit


def test_resolve_pr_target_ref_owned_uses_p_declared_target_unless_explicit(
    fact: OwnedCheckout,
    landing: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit ``target_ref`` wins; otherwise the owned checkout's declared target is read from P."""
    from specify_cli.consolidation.baseline import _resolve_pr_target_ref

    _poison_main_repo_root(monkeypatch)

    assert _resolve_pr_target_ref(fact.repository_root, fact.mission_slug, None, owned=fact) == fact.write_branch
    assert _resolve_pr_target_ref(fact.repository_root, fact.mission_slug, "main", owned=fact) == "main"


# ---------------------------------------------------------------------------
# T093 -- git/commit_helpers.py, missions/_read_path_resolver.py
# ---------------------------------------------------------------------------


def test_resolve_subtasks_gate_dir_owned_is_p_mission_dir(
    fact: OwnedCheckout,
    stale_r: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``resolve_subtasks_gate_dir(owned=fact)`` reads ``tasks.md`` from P, never from R's stale copy."""
    from specify_cli.missions._read_path_resolver import resolve_subtasks_gate_dir

    _poison_main_repo_root(monkeypatch)

    resolved = resolve_subtasks_gate_dir(fact.mission_dir, fact.repository_root, fact.mission_slug, owned=fact)

    assert resolved == fact.mission_dir
    assert not _under(resolved, stale_r)


def test_pipeline_default_subtasks_resolver_hands_the_fact_to_the_converted_seam(
    fact: OwnedCheckout,
    stale_r: Path,
) -> None:
    """The pipeline's default resolver gives the fact to the converted seam (WP18 retired the bare-root bridge)."""
    from specify_cli.status import transition_pipeline

    resolve = transition_pipeline._default_resolve_subtasks_dir

    assert resolve(fact.mission_dir, fact.repository_root, fact.mission_slug, owned=fact) == fact.mission_dir


def test_safe_commit_has_no_dead_effective_root_parameter() -> None:
    """The dead ``effective_root`` parameter is deleted from ``safe_commit`` (T093), not converted.

    ``owned`` is a separate, typed parameter (architecture review of the
    origin/main merge, F1): the validated fact the mission-scoped protection
    fold reads, keyword-only and optional -- never a bare root path.
    """
    import inspect

    from specify_cli.git.commit_helpers import safe_commit

    parameters = inspect.signature(safe_commit).parameters
    assert "effective_root" not in parameters
    assert parameters["owned"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["owned"].default is None
    assert parameters["owned"].annotation == "OwnedCheckout | OwnedCreateMission | None"


# ---------------------------------------------------------------------------
# T094 -- migration/runtime_state_cutover.py, migration/backfill_runtime_state.py
# ---------------------------------------------------------------------------


def test_runtime_feature_dir_owned_returns_mission_dir_and_refuses_a_foreign_dir(
    fact: OwnedCheckout,
    stale_r: Path,
) -> None:
    """``_runtime_feature_dir`` anchors on ``owned.mission_dir`` and keeps the exact-directory guard."""
    from mission_runtime import ActionContextError, OwnedRefusalCode
    from specify_cli.migration.backfill_runtime_state import _runtime_feature_dir

    assert _runtime_feature_dir(fact.mission_dir, fact) == fact.mission_dir

    with pytest.raises(ActionContextError) as excinfo:
        _runtime_feature_dir(stale_r, fact)
    assert excinfo.value.code == OwnedRefusalCode.OWNED_MISSION_PATH_REFUSED.value
    assert _runtime_feature_dir(stale_r, None) == stale_r


def test_cutover_primary_home_and_flip_target_owned_resolve_p(
    fact: OwnedCheckout,
    stale_r: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The placement-port answer and the flip target both come from the fact, with no resolver consulted."""
    from specify_cli.migration import runtime_state_cutover as cutover

    _poison_main_repo_root(monkeypatch)

    assert cutover._resolve_primary_home_or_degrade(fact.mission_dir, owned=fact) == fact.mission_dir
    assert cutover._flip_target(fact.mission_dir, owned=fact) == fact.mission_dir
    assert cutover._already_at_snapshot_authority(fact.mission_dir, owned=fact) is False


def test_cutover_mission_owned_flips_only_p(
    owned_checkouts: OwnedCheckouts,
    fact: OwnedCheckout,
    stale_r: Path,
    r_snapshot: RSnapshotter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``cutover_mission(owned=fact)`` seeds and flips P's ``meta.json``; R's stale copy is untouched."""
    from specify_cli.migration.runtime_state_cutover import cutover_mission

    before = r_snapshot.take()
    _poison_main_repo_root(monkeypatch)

    result = cutover_mission(fact.mission_dir, owned=fact)

    assert result.error is None, result.error
    assert result.flipped is True
    assert int(str(_read_meta(fact.mission_dir)["status_phase"])) >= 1
    assert "status_phase" not in _read_meta(stale_r)
    r_snapshot.assert_unchanged(before, r_snapshot.take(), tolerate_status_mutex_for=fact.mission_slug)


def test_stamp_accept_cutover_owned_stamps_only_p(
    fact: OwnedCheckout,
    stale_r: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``stamp_accept_cutover(owned=fact)`` revalidates the anchor and stamps P only."""
    from specify_cli.migration.runtime_state_cutover import stamp_accept_cutover

    _poison_main_repo_root(monkeypatch)

    result = stamp_accept_cutover(fact.mission_dir, owned=fact)

    assert result.error is None, result.error
    assert result.flipped is True
    assert "status_phase" not in _read_meta(stale_r)


def test_backfill_and_verify_owned_run_against_p(
    fact: OwnedCheckout,
    stale_r: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``backfill_runtime_state`` / ``verify_backfill`` / the write refusal take the fact and read P."""
    from specify_cli.core.checkout_identity import Intent
    from specify_cli.migration.backfill_runtime_state import _invocation_write_refusal, backfill_runtime_state, verify_backfill

    _poison_main_repo_root(monkeypatch)

    seeded = backfill_runtime_state(fact.mission_dir, owned=fact)
    verified = verify_backfill(fact.mission_dir, owned=fact)
    write_verified = verify_backfill(fact.mission_dir, intent=Intent.WRITE, owned=fact)

    assert seeded.action != "error", seeded.reason
    assert verified.ok is True
    assert write_verified.ok is True
    assert _invocation_write_refusal(fact.mission_dir, Intent.WRITE, owned=fact) is None
    assert _invocation_write_refusal(fact.mission_dir, Intent.PRIMARY_READ, owned=fact) is None
