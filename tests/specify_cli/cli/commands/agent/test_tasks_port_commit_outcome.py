"""Red-first: outcome-masking guards for the tasks-port commit-outcome
consumers (WP08, FR-007/FR-007a/FR-007b/SC-003).

``review/cycle.py``'s ``_commit_review_cycle_artifact`` (via
``create_rejected_review_cycle``) and ``tasks_map_requirements.py``'s
``_mr_auto_commit`` both must render through the shared
``commit_outcome`` trio (``render_commit_outcome`` / ``commit_outcome_payload``
/ ``commit_outcome_exit_code``, ``specify_cli/coordination/commit_outcome.py``)
and must never report success when a surface the contract names the OWNING
copy was refused -- even when the legacy top-level
``CommitArtifactResult.status`` says "committed" (today's caller-surface
projection, contract rule 4). At the lane base neither consumer inspects
``.surfaces`` at all, so a refused coordination surface is silently masked.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import pytest

from mission_runtime import MissionArtifactKind
from specify_cli.agent_tasks_ports import (
    CommitArtifactResult,
    CommitStatusResult,
    MissionHandle,
    TasksPorts,
)
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.coordination.commit_outcome import (
    COORD_RECORD_IN_ROOT_CHECKOUT,
    PathFate,
    SurfaceOutcome,
)
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.review.cycle import _commit_review_cycle_artifact, _first_refused_surface_reason
from specify_cli.status import TransitionRequest

pytestmark = [pytest.mark.unit]

_STATUS_LOCK_HELD = "STATUS_LOCK_HELD"


def _masked_result(*, placement_ref: str, reason: str = _STATUS_LOCK_HELD) -> CommitArtifactResult:
    """A fake commit-router result: PRIMARY committed, COORDINATION refused.

    The coordination surface is the OWNING copy for a COORD-kind artifact
    (contract rule 2) -- a caller that only reads the legacy top-level
    ``status`` field (here deliberately "committed", mirroring the
    caller-surface projection rule 4) must still classify this as a failure.
    """
    return CommitArtifactResult(
        status="committed",
        placement_ref=placement_ref,
        commit_hash="abc1234",
        surfaces=(
            SurfaceOutcome(
                surface="primary",
                branch="topic",
                status="committed",
                commit_hash="abc1234",
                committed=("kitty-specs/demo/spec.md",),
            ),
            SurfaceOutcome(
                surface="coordination",
                branch=placement_ref,
                status="refused",
                commit_hash=None,
                refused=(
                    PathFate(
                        path="kitty-specs/demo/tasks/WP01/review-cycle-1.md",
                        reason=reason,
                    ),
                ),
            ),
        ),
    )


class _FakeCommitRouter:
    """Minimal ``CoordCommitRouter`` double returning a fixed, masked result."""

    def __init__(self, result: CommitArtifactResult) -> None:
        self._result = result
        self.calls = 0

    def feature_write_dir(self, mission: MissionHandle) -> Path:  # pragma: no cover - unused
        raise NotImplementedError

    def commit_status(self, request: TransitionRequest, *, capability: GuardCapability) -> CommitStatusResult:  # pragma: no cover - unused
        raise NotImplementedError

    def commit_artifact(
        self,
        mission: MissionHandle,
        paths: Sequence[Path],
        message: str,
        *,
        kind: MissionArtifactKind,
        policy: ProtectionPolicy,
    ) -> CommitArtifactResult:
        self.calls += 1
        return self._result


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], check=check, capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "WP08 outcome fixture")
    _git(repo, "config", "user.email", "wp08-outcome@spec-kitty.test")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "init")


def test_review_cycle_commit_never_reports_durable_when_the_owning_surface_is_refused(
    tmp_path: Path,
) -> None:
    """FR-007/SC-003: a refused coordination surface classifies as
    persistence_failed (never durable), naming the refused surface + reason --
    even when the EXACT evidence bytes genuinely read back at the (fake)
    ``placement_ref`` the router's legacy top-level ``status`` names.

    MUTATION-SENSITIVE: removing the ``.surfaces``-aware masking check in
    ``_commit_review_cycle_artifact`` makes this red -- the pre-fix code
    trusts ``result.status == "committed"`` plus a successful byte-identical
    readback alone, and reports ``classification == "durable"`` for this
    exact fixture (the readback is real and passes; only the surfaces-aware
    guard this WP adds can catch the refused coordination copy).
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    evidence_ref = "kitty-specs/demo/tasks/WP01/review-cycle-1.md"
    artifact_path = repo / evidence_ref
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_bytes = b"---\nwp_id: WP01\n---\nfake evidence body\n"
    artifact_path.write_bytes(artifact_bytes)

    # Commit the EXACT same bytes onto a throwaway ref so the function's own
    # `git show <placement_ref>:<evidence_ref>` readback genuinely succeeds
    # and matches -- proving the masking is caught by the NEW surfaces-aware
    # check, not merely by the pre-existing readback-mismatch heuristic.
    fake_ref = "fake-coord-ref"
    _git(repo, "checkout", "-q", "-b", fake_ref)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "fake coordination commit")
    _git(repo, "checkout", "-q", "main")
    # `checkout` just removed the artifact (and its now-empty parent dirs)
    # from the working tree (it is not part of `main`'s tree) -- restore it
    # so the function under test reads the SAME local bytes it would in
    # production (a real artifact on disk, independent of which branch the
    # repo-root checkout happens to be on).
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(artifact_bytes)

    router = _FakeCommitRouter(_masked_result(placement_ref=fake_ref))
    outcome = _commit_review_cycle_artifact(
        router,
        main_repo_root=repo,
        mission_slug="demo",
        wp_id="WP01",
        artifact_path=artifact_path,
        cycle_number=1,
        verdict="rejected",
    )

    assert router.calls == 1
    assert outcome.classification == "persistence_failed"
    assert outcome.verdict_durably_persisted is False
    assert _STATUS_LOCK_HELD in outcome.message
    assert "coordination" in outcome.message


def _durable_result_with_root_checkout_skip(*, placement_ref: str) -> CommitArtifactResult:
    """A genuinely successful (non-masked) result whose PRIMARY group skipped
    a COORD-kind record it is never committed to the target branch for --
    review cycle 2 B3's "every arm carries surfaces" requirement must surface
    this even on the HAPPY (durable) path, not only on a refusal."""
    return CommitArtifactResult(
        status="committed",
        placement_ref=placement_ref,
        commit_hash="abc1234",
        surfaces=(
            SurfaceOutcome(
                surface="primary",
                branch="topic",
                status="unchanged",
                commit_hash=None,
                skipped=(
                    PathFate(
                        path="kitty-specs/demo/tasks/WP01/review-cycle-1.md",
                        reason=COORD_RECORD_IN_ROOT_CHECKOUT,
                    ),
                ),
            ),
            SurfaceOutcome(
                surface="coordination",
                branch=placement_ref,
                status="committed",
                commit_hash="abc1234",
                committed=("kitty-specs/demo/tasks/WP01/review-cycle-1.md",),
            ),
        ),
    )


def test_review_cycle_commit_durable_arm_still_surfaces_a_root_checkout_skip(
    tmp_path: Path,
) -> None:
    """Review cycle 2 B3: the ``durable`` arm must carry
    ``render_commit_outcome`` lines too, not only the masked-refusal arm --
    a COORD_RECORD_IN_ROOT_CHECKOUT skip on the PRIMARY group is actionable
    (the operator's root-checkout edit never reaches the target) even though
    the overall outcome is a genuine success.

    MUTATION-SENSITIVE: before this fix, the durable arm's message is a bare
    "committed and verified at <ref>" with no surface detail -- this assertion
    fails without the fix.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    evidence_ref = "kitty-specs/demo/tasks/WP01/review-cycle-1.md"
    artifact_path = repo / evidence_ref
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_bytes = b"---\nwp_id: WP01\n---\nfake evidence body\n"
    artifact_path.write_bytes(artifact_bytes)

    fake_ref = "fake-coord-ref-durable"
    _git(repo, "checkout", "-q", "-b", fake_ref)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "fake coordination commit")
    _git(repo, "checkout", "-q", "main")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(artifact_bytes)

    router = _FakeCommitRouter(_durable_result_with_root_checkout_skip(placement_ref=fake_ref))
    outcome = _commit_review_cycle_artifact(
        router,
        main_repo_root=repo,
        mission_slug="demo",
        wp_id="WP01",
        artifact_path=artifact_path,
        cycle_number=1,
        verdict="rejected",
    )

    assert outcome.classification == "durable"
    assert outcome.verdict_durably_persisted is True
    assert COORD_RECORD_IN_ROOT_CHECKOUT in outcome.message, outcome.message


def test_review_cycle_commit_non_committed_arm_surfaces_detail(tmp_path: Path) -> None:
    """Review cycle 2 B3: a non-``"committed"`` arm (``unchanged`` /
    ``no_op_wrong_surface`` / ``error``) builds its message from
    ``result.diagnostic`` alone today -- it must ALSO carry
    ``render_commit_outcome`` lines, so a refused coordination surface
    sitting alongside the reported top-level status is visible."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    evidence_ref = "kitty-specs/demo/tasks/WP01/review-cycle-1.md"
    artifact_path = repo / evidence_ref
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(b"---\nwp_id: WP01\n---\nfake evidence body\n")

    result = CommitArtifactResult(
        status="unchanged",
        placement_ref="kitty/mission-demo",
        diagnostic="nothing to commit",
        surfaces=(
            SurfaceOutcome(
                surface="coordination",
                branch="kitty/mission-demo",
                status="refused",
                commit_hash=None,
                refused=(PathFate(path=evidence_ref, reason=_STATUS_LOCK_HELD),),
            ),
        ),
    )
    router = _FakeCommitRouter(result)
    outcome = _commit_review_cycle_artifact(
        router,
        main_repo_root=repo,
        mission_slug="demo",
        wp_id="WP01",
        artifact_path=artifact_path,
        cycle_number=1,
        verdict="rejected",
    )

    assert outcome.classification == "persistence_failed"
    assert _STATUS_LOCK_HELD in outcome.message, outcome.message


def test_map_requirements_auto_commit_renders_a_warning_when_a_surface_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-007: when ``.surfaces`` names a refused coordination copy, that
    refusal must be visible to the operator -- even though the legacy
    top-level ``status`` ("committed", contract rule 4's caller-surface
    projection) is left unchanged and ``st.committed`` still reflects it.

    MUTATION-SENSITIVE: at the lane base, ``_mr_auto_commit`` never inspects
    ``.surfaces`` at all -- nothing refusal-shaped is ever printed, so this
    assertion fails until the renderer is wired in.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.cli.commands.agent.tasks_map_requirements import _MapReqState, _mr_auto_commit

    printed: list[str] = []
    monkeypatch.setattr(_tasks.console, "print", lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args)))

    tasks_dir = tmp_path / "kitty-specs" / "demo" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-demo.md").write_text("---\nwork_package_id: WP01\n---\n", encoding="utf-8")

    st = _MapReqState(
        wp=None,
        refs=None,
        batch=None,
        replace=False,
        tracker_ref=None,
        mission="demo",
        json_output=False,
        auto_commit=True,
    )
    st.main_repo_root = tmp_path
    st.mission_slug = "demo"
    st.tasks_dir = tasks_dir
    st.auto_commit_on = True
    st.new_mappings = {"WP01": ["FR-001"]}

    router = _FakeCommitRouter(_masked_result(placement_ref="kitty/mission-demo"))
    # `_mr_auto_commit` only ever touches `ports.coord` -- `fs`/`git`/`render`
    # are genuinely unused by the function under test, so a `cast` (rather
    # than three more throwaway Protocol-satisfying stub classes) is the
    # honest way to construct this narrow fixture.
    ports = TasksPorts(fs=cast(Any, None), coord=router, git=cast(Any, None), render=cast(Any, None))

    _mr_auto_commit(st, ports)

    # Legacy top-level projection is unaffected (contract rule 4, additive-only).
    assert st.committed is True
    assert any(_STATUS_LOCK_HELD in line for line in printed), printed


def _committed_result_with_root_checkout_skip(*, placement_ref: str) -> CommitArtifactResult:
    """Every surface is ``committed``/``unchanged`` (exit code 0) -- except
    one carries an actionable ``COORD_RECORD_IN_ROOT_CHECKOUT`` skip. Review
    cycle 2 B3 / contract rule 5 / D8: this must still render a warning even
    though nothing is refused or errored."""
    return CommitArtifactResult(
        status="committed",
        placement_ref=placement_ref,
        commit_hash="abc1234",
        surfaces=(
            SurfaceOutcome(
                surface="primary",
                branch="topic",
                status="unchanged",
                commit_hash=None,
                skipped=(
                    PathFate(
                        path="kitty-specs/demo/tasks.md",
                        reason=COORD_RECORD_IN_ROOT_CHECKOUT,
                    ),
                ),
            ),
            SurfaceOutcome(
                surface="coordination",
                branch=placement_ref,
                status="committed",
                commit_hash="abc1234",
                committed=("kitty-specs/demo/tasks.md",),
            ),
        ),
    )


def test_map_requirements_renders_a_warning_on_an_actionable_skip_with_exit_code_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review cycle 2 B3: ``_mr_render_refused_surfaces`` must render on a
    ``COORD_RECORD_IN_ROOT_CHECKOUT`` skip even when every surface is
    ``committed``/``unchanged`` (``commit_outcome_exit_code`` is 0) -- the OLD
    trigger (``commit_outcome_exit_code(result) == 0: return``) silently
    swallows this actionable case (contract rule 5 / D8: a discarding caller
    must warn whenever a surface is not committed/unchanged, OR carries this
    specific skip).

    MUTATION-SENSITIVE: reverting ``_mr_surface_needs_warning`` to the old
    exit-code-only check makes this assertion fail (nothing is printed).
    """
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.cli.commands.agent.tasks_map_requirements import _MapReqState, _mr_auto_commit

    printed: list[str] = []
    monkeypatch.setattr(_tasks.console, "print", lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args)))

    tasks_dir = tmp_path / "kitty-specs" / "demo" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-demo.md").write_text("---\nwork_package_id: WP01\n---\n", encoding="utf-8")

    st = _MapReqState(
        wp=None,
        refs=None,
        batch=None,
        replace=False,
        tracker_ref=None,
        mission="demo",
        json_output=False,
        auto_commit=True,
    )
    st.main_repo_root = tmp_path
    st.mission_slug = "demo"
    st.tasks_dir = tasks_dir
    st.auto_commit_on = True
    st.new_mappings = {"WP01": ["FR-001"]}

    router = _FakeCommitRouter(_committed_result_with_root_checkout_skip(placement_ref="kitty/mission-demo"))
    ports = TasksPorts(fs=cast(Any, None), coord=router, git=cast(Any, None), render=cast(Any, None))

    _mr_auto_commit(st, ports)

    assert st.committed is True
    assert any(COORD_RECORD_IN_ROOT_CHECKOUT in line for line in printed), printed


def test_map_requirements_warning_prefix_is_styled_without_parsing_the_line_as_markup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review cycle 2 B2: a REAL ``rich.console.Console`` must never print the
    literal ``[yellow]``/``[/yellow]`` tags as text (the OLD
    ``markup=False`` call printed them verbatim), and a genuine ``[...]``
    substring INSIDE the rendered line (not the styling markup) must survive
    byte-for-byte -- proving the fix parses markup for the STYLED PREFIX
    only, never for the line itself."""
    from rich.console import Console

    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.cli.commands.agent.tasks_map_requirements import _MapReqState, _mr_auto_commit

    real_console = Console(record=True, width=200, force_terminal=False, no_color=True)
    monkeypatch.setattr(_tasks, "console", real_console)

    tasks_dir = tmp_path / "kitty-specs" / "demo" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-demo.md").write_text("---\nwork_package_id: WP01\n---\n", encoding="utf-8")

    st = _MapReqState(
        wp=None,
        refs=None,
        batch=None,
        replace=False,
        tracker_ref=None,
        mission="demo",
        json_output=False,
        auto_commit=True,
    )
    st.main_repo_root = tmp_path
    st.mission_slug = "demo"
    st.tasks_dir = tasks_dir
    st.auto_commit_on = True
    st.new_mappings = {"WP01": ["FR-001"]}

    # A reason string that itself contains a literal ``[...]`` substring --
    # NOT markup -- so a correct fix (markup parsed for the prefix only)
    # leaves it untouched, while a naive "turn markup back on for everything"
    # fix would corrupt or swallow it.
    bracketed_reason = "STATUS_LOCK_HELD[contended]"
    router = _FakeCommitRouter(_masked_result(placement_ref="kitty/mission-demo", reason=bracketed_reason))
    ports = TasksPorts(fs=cast(Any, None), coord=router, git=cast(Any, None), render=cast(Any, None))

    _mr_auto_commit(st, ports)

    output = real_console.export_text()
    assert "[yellow]" not in output and "[/yellow]" not in output, output
    assert bracketed_reason in output, output


def test_first_refused_surface_reason_falls_back_to_diagnostic_then_none() -> None:
    """Unit coverage for the two remaining branches of
    ``_first_refused_surface_reason``: a bare refusal (no named path) falls
    back to the surface's own ``diagnostic``, and a surfaces tuple with no
    refused/error entry at all yields ``None``."""
    bare_refusal = (
        SurfaceOutcome(
            surface="coordination",
            branch="kitty/mission-demo",
            status="refused",
            commit_hash=None,
            diagnostic="bare refusal, no named path",
        ),
    )
    assert _first_refused_surface_reason(bare_refusal) == "bare refusal, no named path"

    all_healthy = (SurfaceOutcome(surface="primary", branch="topic", status="committed", commit_hash="abc1234"),)
    assert _first_refused_surface_reason(all_healthy) is None


def test_mr_surface_needs_warning_direct_unit_coverage() -> None:
    """Direct unit coverage for both branches of
    ``_mr_surface_needs_warning`` (review cycle 2 B3): the ``False`` fallback
    when every surface is healthy AND carries no actionable skip, and the
    ``True`` short-circuit on a non-committed/unchanged status (the sibling
    to the already-covered ``COORD_RECORD_IN_ROOT_CHECKOUT`` skip arm)."""
    from specify_cli.cli.commands.agent.tasks_map_requirements import _mr_surface_needs_warning

    all_healthy_no_skip = CommitArtifactResult(
        status="committed",
        placement_ref="kitty/mission-demo",
        commit_hash="abc1234",
        surfaces=(
            SurfaceOutcome(surface="primary", branch="topic", status="committed", commit_hash="abc1234"),
            SurfaceOutcome(surface="coordination", branch="kitty/mission-demo", status="unchanged", commit_hash=None),
        ),
    )
    assert _mr_surface_needs_warning(all_healthy_no_skip) is False

    has_refused = CommitArtifactResult(
        status="committed",
        placement_ref="kitty/mission-demo",
        surfaces=(SurfaceOutcome(surface="coordination", branch="kitty/mission-demo", status="refused", commit_hash=None),),
    )
    assert _mr_surface_needs_warning(has_refused) is True
