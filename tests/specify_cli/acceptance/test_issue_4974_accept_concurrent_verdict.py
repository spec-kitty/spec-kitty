"""Standing test pinning the behaviour of #4974: accept fails closed.

Drives the REAL ``spec-kitty accept`` CLI end to end against a fixture whose
acceptance matrix carries a passing criterion and a pending NI-SLOW negative
invariant. A concurrent ``spec-kitty agent mission acceptance-verdict``
invocation is injected mid-check (at the exact seam the gate calls to
enforce negative invariants) to prove accept judges the FRESH,
concurrently-committed matrix rather than overwriting it
with its own stale pre-lock snapshot (#4974's root defect) or stamping
acceptance over a verdict recorded between the gate's splice and the
acceptance-record write.

Reverting the splice alone, or judging the fresh matrix alone, must turn
``test_ni_variant_survives_and_accept_refuses`` red -- assert on the GATE's
own "Acceptance matrix verdict is 'fail'" message (not merely the exit
code), since the pre-stamp verdict guard would otherwise mask a reverted
fresh-matrix check.
"""

from __future__ import annotations

import io
import json
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest
import typer
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.acceptance.matrix import (
    AcceptanceCriterion,
    AcceptanceMatrix,
    NegativeInvariant,
    enforce_negative_invariants as _real_enforce_negative_invariants,
    locked_acceptance_verdict_guard as _real_locked_acceptance_verdict_guard,
    read_acceptance_matrix,
    write_acceptance_matrix,
)
from specify_cli.acceptance import (
    AcceptanceError,
    AcceptanceSummary,
    _commit_acceptance_meta,
)
from specify_cli.acceptance.gates_core import PLANNING_ARTIFACT_ONLY_SKIP_REASON
from specify_cli.cli.commands import accept as accept_module
from specify_cli.cli.commands.agent.acceptance_verdict import acceptance_verdict
from specify_cli.status.locking import FeatureStatusLockTimeoutError
from specify_cli.task_utils import LANES
from tests.lane_test_utils import derive_mission_id, write_single_lane_manifest
from tests.specify_cli.test_acceptance_regressions import _create_test_feature

pytestmark = [pytest.mark.git_repo, pytest.mark.integration]

_MISSION_SLUG = "wp02-concurrent-verdict-mission"

#: A single dedicated work branch used as BOTH the checked-out branch and the
#: mission's ``target_branch`` -- mirrors ``test_acceptance_verdict_command.
#: py``'s ``_init_flat_mission``/``_FLAT_BRANCH`` convention. This sidesteps
#: two unrelated concerns: (1) it is never in ``ProtectionPolicy``'s default
#: protected set (unlike ``main``), so the acceptance commit takes the simple
#: direct-commit path; (2) with no SEPARATE ``main``/mission-branch divergence,
#: the coordination write-seam's E2/CONSOLIDATED short-circuit predicate
#: (``resolved.ref == primary_branch != target_branch``) can never fire, so
#: the concurrent ``acceptance-verdict`` write always lands on the SAME
#: surface accept reads.
_WORK_BRANCH = "wp02-accept-work"


def _seed_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mission_slug: str = _MISSION_SLUG,
) -> tuple[Path, Path]:
    """A passing criterion + pending NI-SLOW, committed clean on ``_WORK_BRANCH``."""
    repo_root, feature_dir = _create_test_feature(tmp_path, mission_slug)
    subprocess.run(
        ["git", "-C", str(repo_root), "branch", "-M", _WORK_BRANCH],
        check=True,
        capture_output=True,
    )

    # ``_create_test_feature``'s meta.json predates the ULID mission-identity
    # model (083+); stamp mission_id/mid8 so the accept-commit's birth-cutover
    # stamp (unrelated to this WP) does not refuse for a fixture reason. Also
    # repoint ``target_branch`` at the single work branch (see ``_WORK_BRANCH``).
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    mission_id = derive_mission_id(mission_slug)
    meta["mission_id"] = mission_id
    meta["mid8"] = mission_id[:8]
    meta["target_branch"] = _WORK_BRANCH
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), target_branch=_WORK_BRANCH)

    matrix = AcceptanceMatrix(
        mission_slug=mission_slug,
        criteria=[
            AcceptanceCriterion(
                criterion_id="FR-001",
                description="WP01 completes as specified",
                proof_type="automated_test",
                pass_fail="pass",
                evidence="test evidence",
            )
        ],
        negative_invariants=[
            NegativeInvariant(
                invariant_id="NI-SLOW",
                description="NI-SLOW must not exist",
                verification_method="custom_command",
                verification_command="exit 0",
            )
        ],
    )
    write_acceptance_matrix(feature_dir, matrix)
    subprocess.run(["git", "-C", str(repo_root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-m", "seed passing criterion + NI-SLOW pending"],
        check=True,
        capture_output=True,
    )
    monkeypatch.chdir(repo_root)
    return repo_root, feature_dir


def _run_accept(repo_root: Path, mission_slug: str, monkeypatch: pytest.MonkeyPatch) -> Result:
    cli = typer.Typer()
    cli.command(name="accept")(accept_module.accept)
    monkeypatch.setattr(accept_module, "find_repo_root", lambda: repo_root)
    return CliRunner().invoke(
        cli,
        ["--mission", mission_slug, "--lenient", "--json"],
        catch_exceptions=False,
    )


def _meta(feature_dir: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    return data


def _matrix_at_head(repo_root: Path, feature_dir: Path) -> dict[str, Any]:
    rel = str((feature_dir / "acceptance-matrix.json").relative_to(repo_root))
    out = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"HEAD:{rel}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    data: dict[str, Any] = json.loads(out)
    return data


def _head(repo_root: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _invoke_verdict(**kwargs: object) -> None:
    """Drive the REAL ``acceptance-verdict`` command, tolerating its
    ``typer.Exit(0)`` success signal (it is a Typer command, not a plain
    function-return API).

    Its own stdout is redirected away: it runs in-process, inside a
    ``CliRunner.invoke()`` of the outer ``accept`` command, and would
    otherwise interleave its JSON with accept's own JSON on the same
    captured stream.
    """
    kwargs.setdefault("json_output", True)
    with redirect_stdout(io.StringIO()):
        try:
            acceptance_verdict(**kwargs)
        except typer.Exit as exc:
            assert exc.exit_code in (0, None), f"concurrent acceptance-verdict invocation failed: exit {exc.exit_code}"


class TestIssue4974AcceptConcurrentVerdict:
    def test_ni_variant_survives_and_accept_refuses(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A concurrent NI-FAIL commits while accept runs NI-SLOW's check.
        NI-FAIL must survive on disk AND in HEAD, the overall verdict must
        be 'fail', and accept must refuse with the GATE's own message (not
        merely a non-zero exit)."""
        repo_root, feature_dir = _seed_fixture(tmp_path, monkeypatch)

        def _wrapper(repo_root_arg: Path, invariants: list[NegativeInvariant], **kwargs: object) -> list[NegativeInvariant]:
            _invoke_verdict(
                mission=_MISSION_SLUG,
                negative_invariant="NI-FAIL",
                description="NI-FAIL must not exist",
                verification_method="custom_command",
                verification_command="exit 1",
            )
            return cast("list[NegativeInvariant]", _real_enforce_negative_invariants(repo_root_arg, invariants, **kwargs))

        monkeypatch.setattr("specify_cli.acceptance.matrix.enforce_negative_invariants", _wrapper)

        result = _run_accept(repo_root, _MISSION_SLUG, monkeypatch)

        assert result.exit_code != 0, result.output
        assert "accepted_at" not in _meta(feature_dir)

        on_disk = read_acceptance_matrix(feature_dir)
        assert on_disk is not None
        by_id = {ni.invariant_id: ni for ni in on_disk.negative_invariants}
        assert by_id["NI-FAIL"].result == "still_present", "a concurrently committed failing row must survive (#4974)"
        assert on_disk.overall_verdict == "fail"

        head_matrix = _matrix_at_head(repo_root, feature_dir)
        head_by_id = {ni["invariant_id"]: ni for ni in head_matrix["negative_invariants"]}
        assert head_by_id["NI-FAIL"]["result"] == "still_present"

        payload = json.loads(result.output)
        activity_issues = payload.get("activity_issues", [])
        assert any("Acceptance matrix verdict is 'fail'" in issue for issue in activity_issues), (
            f"Assert on the GATE's own refusal message -- the pre-stamp verdict guard would otherwise mask a reverted fresh-matrix check. Got: {activity_issues}"
        )

    def test_criterion_variant_stays_fail_and_accept_refuses(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A concurrent ``--criterion FR-001 --result fail`` commits
        mid-check. That criterion must stay 'fail' and accept must refuse."""
        repo_root, feature_dir = _seed_fixture(tmp_path, monkeypatch)

        def _wrapper(repo_root_arg: Path, invariants: list[NegativeInvariant], **kwargs: object) -> list[NegativeInvariant]:
            _invoke_verdict(
                mission=_MISSION_SLUG,
                criterion="FR-001",
                result="fail",
                verification_method="manual_qa",
                actor="concurrent-agent",
                evidence="concurrent finding",
            )
            return cast("list[NegativeInvariant]", _real_enforce_negative_invariants(repo_root_arg, invariants, **kwargs))

        monkeypatch.setattr("specify_cli.acceptance.matrix.enforce_negative_invariants", _wrapper)

        result = _run_accept(repo_root, _MISSION_SLUG, monkeypatch)

        assert result.exit_code != 0, result.output
        assert "accepted_at" not in _meta(feature_dir)

        on_disk = read_acceptance_matrix(feature_dir)
        assert on_disk is not None
        by_id = {c.criterion_id: c for c in on_disk.criteria}
        assert by_id["FR-001"].pass_fail == "fail", "accept's stale 'pass' snapshot must never overwrite a concurrent fail"
        assert on_disk.overall_verdict == "fail"

    def test_positive_control_no_concurrent_verdict_accepts(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The shared positive control for the late-verdict, lock-timeout,
        and re-registration edge cases below: the SAME fixture, no
        interleaving, accepts cleanly."""
        repo_root, feature_dir = _seed_fixture(tmp_path, monkeypatch)

        result = _run_accept(repo_root, _MISSION_SLUG, monkeypatch)

        assert result.exit_code == 0, result.output
        assert "accepted_at" in _meta(feature_dir)
        on_disk = read_acceptance_matrix(feature_dir)
        assert on_disk is not None
        assert on_disk.overall_verdict == "pass"

    def test_late_verdict_after_splice_before_stamp_refuses(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A failing verdict commits AFTER the gate's splice but BEFORE the
        acceptance record is stamped -- injected right at the entry of the
        pre-stamp verdict guard itself, so the guard's own fresh re-read
        (not the earlier gate splice) is what must catch it."""
        repo_root, feature_dir = _seed_fixture(tmp_path, monkeypatch)

        @contextmanager
        def _late_verdict_guard(repo_root_arg: Path, matrix_dir_arg: Path, *, timeout: float | None = None) -> Iterator[AcceptanceMatrix]:
            _invoke_verdict(
                mission=_MISSION_SLUG,
                criterion="FR-001",
                result="fail",
                verification_method="manual_qa",
                actor="late-agent",
                evidence="late finding",
            )
            with _real_locked_acceptance_verdict_guard(repo_root_arg, matrix_dir_arg, timeout=timeout) as fresh:
                yield fresh

        monkeypatch.setattr("specify_cli.acceptance.matrix.locked_acceptance_verdict_guard", _late_verdict_guard)

        result = _run_accept(repo_root, _MISSION_SLUG, monkeypatch)

        assert result.exit_code != 0, result.output
        assert "accepted_at" not in _meta(feature_dir)
        on_disk = read_acceptance_matrix(feature_dir)
        assert on_disk is not None
        by_id = {c.criterion_id: c for c in on_disk.criteria}
        assert by_id["FR-001"].pass_fail == "fail"

    def test_lock_timeout_fails_closed_no_write(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A holder of the mission status lock makes accept fail closed with
        a lock diagnostic and no matrix write."""
        repo_root, feature_dir = _seed_fixture(tmp_path, monkeypatch)
        head_before = _head(repo_root)

        def _timeout_lock(repo_root_arg: Path, lock_key: str, *, timeout: float = -1) -> NoReturn:
            raise FeatureStatusLockTimeoutError(
                "simulated timeout",
                lock_path=Path("/nonexistent/fake.status.lock"),
                timeout=timeout,
            )

        monkeypatch.setattr("specify_cli.status.mission_write.feature_status_lock", _timeout_lock)

        result = _run_accept(repo_root, _MISSION_SLUG, monkeypatch)

        assert result.exit_code != 0, result.output
        payload = json.loads(result.output)
        assert any(item.get("check") == "acceptance_matrix_lock" for item in payload.get("blocked_checks", [])), payload
        assert "accepted_at" not in _meta(feature_dir)
        assert _head(repo_root) == head_before, "a lock timeout must never write or commit the matrix"
        on_disk = read_acceptance_matrix(feature_dir)
        assert on_disk is not None
        assert on_disk.overall_verdict == "pending", "NI-SLOW was never judged/persisted under the timed-out lock"

    def test_reregistered_invariant_with_new_command_kept_pending_refuses(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Edge case: NI-SLOW is re-registered concurrently with a NEW
        verification command (row ownership rule condition 4).
        Accept's stale judgement of the OLD definition must be discarded;
        the fresh, still-pending row (new definition) survives and accept
        refuses on 'pending', never silently accepting."""
        repo_root, feature_dir = _seed_fixture(tmp_path, monkeypatch)

        def _wrapper(repo_root_arg: Path, invariants: list[NegativeInvariant], **kwargs: object) -> list[NegativeInvariant]:
            _invoke_verdict(
                mission=_MISSION_SLUG,
                negative_invariant="NI-SLOW",
                description="NI-SLOW must not exist (redefined)",
                verification_method="custom_command",
                verification_command="exit 1",
                execute=False,
            )
            return cast("list[NegativeInvariant]", _real_enforce_negative_invariants(repo_root_arg, invariants, **kwargs))

        monkeypatch.setattr("specify_cli.acceptance.matrix.enforce_negative_invariants", _wrapper)

        result = _run_accept(repo_root, _MISSION_SLUG, monkeypatch)

        assert result.exit_code != 0, result.output
        assert "accepted_at" not in _meta(feature_dir)

        on_disk = read_acceptance_matrix(feature_dir)
        assert on_disk is not None
        ni = next(n for n in on_disk.negative_invariants if n.invariant_id == "NI-SLOW")
        assert ni.result == "pending"
        assert ni.verification_command == "exit 1", "the fresh (re-registered) definition must be what survives"
        assert on_disk.overall_verdict == "pending"

    def test_population_and_enforcement_run_outside_the_status_lock(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Review-evidence population and negative-invariant enforcement
        (both potentially slow) must run OUTSIDE the mission
        status lock -- only the re-read/splice/write critical section may
        hold it. A spy wraps ``specify_cli.acceptance.matrix.feature_status_lock``
        to record whether it is currently held each time
        ``populate_criteria_from_review_evidence`` / ``enforce_negative_invariants``
        fire; neither may observe the lock held."""
        repo_root, feature_dir = _seed_fixture(tmp_path, monkeypatch)

        from specify_cli.status.locking import feature_status_lock as _real_feature_status_lock
        from specify_cli.acceptance.matrix import populate_criteria_from_review_evidence as _real_populate_criteria

        lock_held = {"value": False}
        observed_while_populating: list[bool] = []
        observed_while_enforcing: list[bool] = []

        @contextmanager
        def _tracking_lock(*args: object, **kwargs: object) -> Iterator[object]:
            lock_held["value"] = True
            try:
                with _real_feature_status_lock(*args, **kwargs) as token:
                    yield token
            finally:
                lock_held["value"] = False

        def _populate_spy(status_dir: Path, criteria: list[object]) -> list[object]:
            observed_while_populating.append(lock_held["value"])
            return cast("list[object]", _real_populate_criteria(status_dir, criteria))

        def _enforce_spy(repo_root_arg: Path, invariants: list[NegativeInvariant], **kwargs: object) -> list[NegativeInvariant]:
            observed_while_enforcing.append(lock_held["value"])
            return cast("list[NegativeInvariant]", _real_enforce_negative_invariants(repo_root_arg, invariants, **kwargs))

        monkeypatch.setattr("specify_cli.status.mission_write.feature_status_lock", _tracking_lock)
        monkeypatch.setattr("specify_cli.acceptance.matrix.populate_criteria_from_review_evidence", _populate_spy)
        monkeypatch.setattr("specify_cli.acceptance.matrix.enforce_negative_invariants", _enforce_spy)

        result = _run_accept(repo_root, _MISSION_SLUG, monkeypatch)

        assert result.exit_code == 0, result.output
        assert observed_while_populating, "populate_criteria_from_review_evidence never ran"
        assert observed_while_enforcing, "enforce_negative_invariants never ran"
        assert observed_while_populating == [False], "review-evidence population must run OUTSIDE the status lock"
        assert observed_while_enforcing == [False], "negative-invariant enforcement must run OUTSIDE the status lock"


class TestStampGuardFR010Branches:
    """Three ``_stamp_acceptance_record`` branches (planning-artifact-only
    bypass, fail-closed on a missing matrix dir, and the guard's own
    lock-timeout translation) survived mutation testing with the whole
    targeted suite green. Each test below was confirmed to go RED under its
    corresponding mutation (see the mission's Activity Log for the
    mutation-and-restore record; every mutation was restored with
    ``git checkout -- <file>``, never ``git stash``)."""

    def test_planning_artifact_only_bypass_stamps_successfully(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """M6: a planning-artifact-only mission, stamped with AUTO-COMMIT
        (never ``--no-commit``, which never reaches the stamp at all), must
        succeed: accept exits 0 and ``accepted_at`` is set in meta.json.
        Mutating the bypass (``record_acceptance(...); return``) into
        ``raise AcceptanceError(...)`` turns this test red."""
        mission_slug = "wp02-m6-planning-only-stamp"
        repo_root, feature_dir = _create_test_feature(tmp_path, mission_slug)
        # A dedicated non-protected branch (never ``main``): planning
        # artifacts must land on a feature branch (unrelated protected-branch
        # guard), which would otherwise mask the branch under test.
        subprocess.run(["git", "-C", str(repo_root), "branch", "-M", _WORK_BRANCH], check=True, capture_output=True)
        (repo_root / ".kittify").mkdir(exist_ok=True)

        deliverables_path = f"docs/research/{mission_slug}/"
        meta_path = feature_dir / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        mission_id = derive_mission_id(mission_slug)
        meta["mission_id"] = mission_id
        meta["mid8"] = mission_id[:8]
        meta["mission_type"] = "research"
        meta["mission"] = "research"
        meta["deliverables_path"] = deliverables_path
        meta["target_branch"] = _WORK_BRANCH
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

        for path_name in ("research", "data", "findings", "reports"):
            directory = repo_root / deliverables_path / path_name
            directory.mkdir(parents=True, exist_ok=True)
            (directory / ".gitkeep").write_text("", encoding="utf-8")

        write_single_lane_manifest(
            feature_dir,
            wp_ids=("WP01",),
            lane_id="lane-planning",
            target_branch=_WORK_BRANCH,
            write_scope=(f"{deliverables_path}**",),
            predicted_surfaces=("planning",),
        )
        subprocess.run(["git", "-C", str(repo_root), "add", "-A"], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo_root), "commit", "-m", "seed planning-artifact-only mission"],
            check=True,
            capture_output=True,
        )

        result = _run_accept(repo_root, mission_slug, monkeypatch)

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["summary"]["ok"] is True
        assert "accepted_at" in _meta(feature_dir)

    def _bare_ok_summary(
        self,
        repo_root: Path,
        feature_dir: Path,
        mission_slug: str,
        branch: str,
        *,
        acceptance_matrix_dir: Path | None,
        acceptance_matrix_gate_skip_reason: str | None,
    ) -> AcceptanceSummary:
        full_lanes: dict[str, list[str]] = {lane: [] for lane in LANES}
        full_lanes["approved"] = ["WP01"]
        return AcceptanceSummary(
            feature=mission_slug,
            repo_root=repo_root,
            feature_dir=feature_dir,
            tasks_dir=feature_dir / "tasks",
            branch=branch,
            worktree_root=repo_root,
            primary_repo_root=repo_root,
            lanes=full_lanes,
            work_packages=[],
            metadata_issues=[],
            activity_issues=[],
            unchecked_tasks=[],
            needs_clarification=[],
            missing_artifacts=[],
            optional_missing=[],
            git_dirty=[],
            path_violations=[],
            warnings=[],
            acceptance_matrix_dir=acceptance_matrix_dir,
            acceptance_matrix_gate_skip_reason=acceptance_matrix_gate_skip_reason,
        )

    def _seed_m7_fixture(self, tmp_path: Path, mission_slug: str) -> tuple[Path, Path]:
        repo_root, feature_dir = _create_test_feature(tmp_path, mission_slug)
        subprocess.run(["git", "-C", str(repo_root), "branch", "-M", _WORK_BRANCH], check=True, capture_output=True)
        meta_path = feature_dir / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        mission_id = derive_mission_id(mission_slug)
        meta["mission_id"] = mission_id
        meta["mid8"] = mission_id[:8]
        meta["target_branch"] = _WORK_BRANCH
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo_root), "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo_root), "commit", "-m", "seed meta for M7"], check=True, capture_output=True)
        return repo_root, feature_dir

    def test_missing_matrix_dir_fails_closed_for_non_planning_mission(self, tmp_path: Path) -> None:
        """M7: ``acceptance_matrix_dir is None`` for any reason OTHER than
        the planning-artifact-only skip must fail closed. Mutating the
        ``raise AcceptanceError(...)`` into a silent
        ``record_acceptance(...)`` turns this test red."""
        mission_slug = "wp02-m7-missing-matrix-dir"
        repo_root, feature_dir = self._seed_m7_fixture(tmp_path, mission_slug)
        summary = self._bare_ok_summary(
            repo_root,
            feature_dir,
            mission_slug,
            _WORK_BRANCH,
            acceptance_matrix_dir=None,
            acceptance_matrix_gate_skip_reason=None,
        )

        with pytest.raises(AcceptanceError, match="Cannot record acceptance"):
            _commit_acceptance_meta(summary, actor_name="tester", mode="local")

        assert "accepted_at" not in _meta(feature_dir)

    def test_missing_matrix_dir_with_non_planning_skip_reason_still_fails_closed(self, tmp_path: Path) -> None:
        """M7 (string-compare variant): a skip_reason that is NOT
        ``PLANNING_ARTIFACT_ONLY_SKIP_REASON`` must still fail closed --
        guards against a future loosening of the exact string compare
        (e.g. an ``in`` check or a truthy check) silently widening the
        bypass to skip reasons that were never meant to exempt the guard."""
        mission_slug = "wp02-m7-non-planning-skip-reason"
        repo_root, feature_dir = self._seed_m7_fixture(tmp_path, mission_slug)
        assert PLANNING_ARTIFACT_ONLY_SKIP_REASON != "not-the-planning-skip-reason"
        summary = self._bare_ok_summary(
            repo_root,
            feature_dir,
            mission_slug,
            _WORK_BRANCH,
            acceptance_matrix_dir=None,
            acceptance_matrix_gate_skip_reason="not-the-planning-skip-reason",
        )

        with pytest.raises(AcceptanceError, match="Cannot record acceptance"):
            _commit_acceptance_meta(summary, actor_name="tester", mode="local")

        assert "accepted_at" not in _meta(feature_dir)

    def test_guard_lock_timeout_translated_to_acceptance_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """M5: the gate itself succeeds cleanly (the SAME fixture as the
        positive control), but the guard's OWN lock acquisition times out.
        ``_stamp_acceptance_record`` must translate
        ``FeatureStatusLockTimeoutError`` into ``AcceptanceError`` -- accept
        exits non-zero with the 'lock timed out while recording acceptance'
        diagnostic and no ``accepted_at`` is written. The lock-timeout test
        above does not cover this: it holds the GATE's own lock, so the gate
        fails before the guard is ever reached; this test reaches the guard
        cleanly and times out there instead."""
        repo_root, feature_dir = _seed_fixture(tmp_path, monkeypatch)

        @contextmanager
        def _timing_out_guard(*_args: object, **_kwargs: object) -> Iterator[object]:
            raise FeatureStatusLockTimeoutError("lock timed out (test double, M5)")
            yield  # pragma: no cover -- unreachable, required for generator shape

        monkeypatch.setattr("specify_cli.acceptance.matrix.locked_acceptance_verdict_guard", _timing_out_guard)

        result = _run_accept(repo_root, _MISSION_SLUG, monkeypatch)

        assert result.exit_code != 0, result.output
        payload = json.loads(result.output)
        assert "lock timed out while recording acceptance" in payload["error"]
        assert "accepted_at" not in _meta(feature_dir)
