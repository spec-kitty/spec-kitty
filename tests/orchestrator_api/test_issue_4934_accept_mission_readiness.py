"""Issue #4934: orchestrator-api ``accept-mission`` must APPLY the host
readiness verdict.

Before this fix, ``accept_mission`` computed ``collect_feature_summary(...)``
and then discarded ``summary.ok`` entirely -- it recorded acceptance
unconditionally as soon as the incomplete-WP dependency check passed. A
mission with a pending/failing acceptance matrix, or with no ``lanes.json``
at all, was accepted anyway. This drives the REAL
``orchestrator-api accept-mission`` CLI end to end against a real git
fixture and proves:

* A pending-matrix mission and a no-``lanes.json`` mission both
  refuse with ``MISSION_NOT_READY``, write no ``accepted_at`` /
  ``acceptance_mode`` / ``acceptance_history``, and leave HEAD unchanged.
* The SAME acceptable fixture (``lanes.json`` present, a passing matrix)
  accepts -- the shared positive control every negative test above is a
  variant of.
* A failing verdict committed AFTER the readiness check but BEFORE
  the acceptance record is stamped is still caught (the guard's own fresh
  re-read, not the earlier readiness snapshot).
* A lock-acquisition timeout on the pre-stamp verdict guard also refuses
  with ``MISSION_NOT_READY`` rather than a raw traceback or a silent accept.

Conventions copied from ``tests/orchestrator_api/test_issue_4889_caller_independence.py``
(module layout, ``pytestmark``) and the fixture-building helpers from
``tests/specify_cli/acceptance/test_issue_4974_accept_concurrent_verdict.py``,
reusing ``_create_test_feature`` / ``write_single_lane_manifest`` rather than
inventing a third fixture shape.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli.acceptance.matrix import (
    AcceptanceCriterion,
    AcceptanceMatrix,
    AcceptanceMatrixParseError,
    locked_acceptance_verdict_guard as _real_locked_acceptance_verdict_guard,
    read_acceptance_matrix,
    write_acceptance_matrix,
)
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.missions._create import ensure_coordination_branch
from specify_cli.missions._read_path_resolver import coord_feature_dir
from specify_cli.orchestrator_api.commands import app
from specify_cli.status.emit import emit_status_transition
from specify_cli.status.locking import FeatureStatusLockTimeoutError
from specify_cli.status.models import TransitionRequest
from tests.lane_test_utils import derive_mission_id, write_single_lane_manifest
from tests.specify_cli.test_acceptance_regressions import _create_test_feature
from tests.status.conftest import seed_wp_to_planned

pytestmark = [pytest.mark.git_repo, pytest.mark.integration]

runner = CliRunner()

_MISSION_SLUG = "issue-4934-accept-mission-readiness"


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo_root), *args], check=True, capture_output=True)


def _passing_matrix(mission_slug: str) -> AcceptanceMatrix:
    return AcceptanceMatrix(
        mission_slug=mission_slug,
        criteria=[
            AcceptanceCriterion(
                criterion_id="AC-001",
                description="WP01 completes as specified",
                proof_type="automated_test",
                pass_fail="pass",
                evidence="test evidence",
            )
        ],
    )


def _pending_matrix(mission_slug: str) -> AcceptanceMatrix:
    return AcceptanceMatrix(
        mission_slug=mission_slug,
        criteria=[
            AcceptanceCriterion(
                criterion_id="AC-001",
                description="WP01 completes as specified",
                proof_type="automated_test",
                pass_fail="pending",
            )
        ],
    )


def _seed_acceptable_mission(tmp_path: Path, mission_slug: str) -> tuple[Path, Path]:
    """A real-git mission with WP01 ``done``, ``lanes.json``, and a passing
    matrix, committed clean -- the positive control."""
    repo_root, feature_dir = _create_test_feature(tmp_path, mission_slug)
    _git(repo_root, "branch", "-M", "main")

    mission_id = derive_mission_id(mission_slug)
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["mission_id"] = mission_id
    meta["mid8"] = mission_id[:8]
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), target_branch="main", mission_id=mission_id)
    write_acceptance_matrix(feature_dir, _passing_matrix(mission_slug))

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "seed lanes manifest + passing matrix")
    return repo_root, feature_dir


def _seed_mission_with_never_claimed_done_wp(tmp_path: Path, mission_slug: str) -> tuple[Path, Path]:
    """A real-git mission where WP01 reaches ``done`` via a claim event that
    carries NO ``policy_metadata={"agent": ...}``.

    ``status/reducer.py``'s ``_project_implementer_attribution`` writes the
    durable ``agent``/implementer-of-record slot ONLY on a real
    ``planned -> claimed`` hop carrying the claimant in its
    ``policy_metadata`` sidecar -- so a claim with no ``policy_metadata``
    leaves the WP with no recorded implementer even though it reaches
    ``done``, i.e. genuinely "never claimed" in the sense the
    ``strict_metadata=True`` gate cares about. Built from
    ``_create_test_feature(omit_status_events=True)`` (skip its baked-in
    force-to-done event, which stamps the agent via an ``InnerStateChanged``
    annotation) and a real, non-forced lane walk instead.
    """
    from specify_cli.status.models import ReviewResult

    repo_root, feature_dir = _create_test_feature(tmp_path, mission_slug, omit_status_events=True)
    _git(repo_root, "branch", "-M", "main")

    mission_id = derive_mission_id(mission_slug)
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["mission_id"] = mission_id
    meta["mid8"] = mission_id[:8]
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    seed_wp_to_planned(feature_dir, "WP01", slug=mission_slug)
    # Deliberately NO ``policy_metadata`` on the claim hop.
    emit_status_transition(TransitionRequest(feature_dir=feature_dir, mission_slug=mission_slug, wp_id="WP01", to_lane="claimed", actor="ci-bot"))
    emit_status_transition(TransitionRequest(feature_dir=feature_dir, mission_slug=mission_slug, wp_id="WP01", to_lane="in_progress", actor="ci-bot"))
    emit_status_transition(TransitionRequest(feature_dir=feature_dir, mission_slug=mission_slug, wp_id="WP01", to_lane="for_review", actor="ci-bot"))
    emit_status_transition(TransitionRequest(feature_dir=feature_dir, mission_slug=mission_slug, wp_id="WP01", to_lane="in_review", actor="ci-bot"))
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP01",
            to_lane="done",
            actor="ci-bot",
            evidence={
                "review": {
                    "reviewer": "reviewer-agent",
                    "verdict": "approved",
                    "reference": "review-001",
                }
            },
            review_result=ReviewResult(
                reviewer="reviewer-agent",
                verdict="approved",
                reference="review-001",
            ),
        )
    )

    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), target_branch="main", mission_id=mission_id)
    write_acceptance_matrix(feature_dir, _passing_matrix(mission_slug))

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "seed WP01 done with no claim metadata")
    return repo_root, feature_dir


def _invoke_accept_mission(repo_root: Path, mission_slug: str, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(
        "specify_cli.orchestrator_api.commands._get_main_repo_root",
        lambda: repo_root,
    )
    return runner.invoke(
        app,
        ["accept-mission", "--mission", mission_slug, "--actor", "ci-bot"],
        catch_exceptions=False,
    )


def _meta(feature_dir: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    return data


def _head(repo_root: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class TestIssue4934AcceptMissionReadiness:
    def test_positive_control_acceptable_fixture_accepts(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Positive control: lanes.json present, matrix passing ->
        accept-mission accepts and stamps accepted_at."""
        repo_root, feature_dir = _seed_acceptable_mission(tmp_path, _MISSION_SLUG)

        result = _invoke_accept_mission(repo_root, _MISSION_SLUG, monkeypatch)

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["success"] is True
        assert payload["data"]["accepted"] is True
        meta = _meta(feature_dir)
        assert "accepted_at" in meta
        assert payload["data"]["accepted_at"] == meta["accepted_at"]

    def test_pending_matrix_refuses_mission_not_ready(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A pending-matrix mission refuses with MISSION_NOT_READY and
        writes nothing."""
        mission_slug = "issue-4934-pending-matrix"
        repo_root, feature_dir = _seed_acceptable_mission(tmp_path, mission_slug)
        head_before = _head(repo_root)

        write_acceptance_matrix(feature_dir, _pending_matrix(mission_slug))
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-m", "matrix goes pending")
        head_before = _head(repo_root)

        result = _invoke_accept_mission(repo_root, mission_slug, monkeypatch)

        assert result.exit_code != 0, result.output
        payload = json.loads(result.output)
        assert payload["success"] is False
        assert payload["error_code"] == "MISSION_NOT_READY"
        assert payload["data"]["mission_slug"] == mission_slug

        meta = _meta(feature_dir)
        assert "accepted_at" not in meta
        assert "acceptance_mode" not in meta
        assert "acceptance_history" not in meta
        assert _head(repo_root) == head_before, "a refused accept must never advance HEAD"

        assert isinstance(payload["data"]["outstanding"], dict) and payload["data"]["outstanding"]
        assert isinstance(payload["data"]["activity_issues"], list)
        assert isinstance(payload["data"]["skipped_checks"], list)
        assert isinstance(payload["data"]["blocked_checks"], list)

    def test_missing_lanes_json_refuses_mission_not_ready_with_blocked_check(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A mission with NO lanes.json at all refuses with
        MISSION_NOT_READY, carrying a blocked ``lanes_manifest`` check, and
        writes nothing."""
        mission_slug = "issue-4934-no-lanes"
        repo_root, feature_dir = _create_test_feature(tmp_path, mission_slug)
        _git(repo_root, "branch", "-M", "main")
        # No lanes.json, no acceptance-matrix.json -- committed clean as-is.

        head_before = _head(repo_root)

        result = _invoke_accept_mission(repo_root, mission_slug, monkeypatch)

        assert result.exit_code != 0, result.output
        payload = json.loads(result.output)
        assert payload["error_code"] == "MISSION_NOT_READY"

        meta = _meta(feature_dir)
        assert "accepted_at" not in meta
        assert _head(repo_root) == head_before

        blocked = payload["data"]["blocked_checks"]
        assert any(item["check"] == "lanes_manifest" for item in blocked), blocked

    def test_late_verdict_between_readiness_check_and_stamp_refuses(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A failing verdict is committed to disk AFTER the readiness
        check (``collect_feature_summary``) but BEFORE the pre-stamp verdict
        guard's own fresh re-read -- proving the guard's re-read (not the earlier
        readiness snapshot, which still says ``ok``) is what catches it.

        Mutating the guard call in ``_stamp_mission_acceptance_or_fail`` back
        to a bare ``record_acceptance(...)`` (skipping the guard entirely)
        turns this test green-on-a-stale-pass -- i.e. red under that
        mutation, since the acceptance would then wrongly succeed.
        """
        mission_slug = "issue-4934-sc005-late-verdict"
        repo_root, feature_dir = _seed_acceptable_mission(tmp_path, mission_slug)
        head_before = _head(repo_root)

        @contextmanager
        def _late_verdict_guard(repo_root_arg: Path, matrix_dir_arg: Path, *, timeout: float | None = None) -> Iterator[AcceptanceMatrix]:
            matrix = read_acceptance_matrix(matrix_dir_arg)
            assert matrix is not None
            matrix.criteria[0].pass_fail = "fail"
            write_acceptance_matrix(matrix_dir_arg, matrix)
            with _real_locked_acceptance_verdict_guard(repo_root_arg, matrix_dir_arg, timeout=timeout) as fresh:
                yield fresh

        monkeypatch.setattr(
            "specify_cli.acceptance.matrix.locked_acceptance_verdict_guard",
            _late_verdict_guard,
        )

        result = _invoke_accept_mission(repo_root, mission_slug, monkeypatch)

        assert result.exit_code != 0, result.output
        payload = json.loads(result.output)
        assert payload["error_code"] == "MISSION_NOT_READY"

        meta = _meta(feature_dir)
        assert "accepted_at" not in meta
        assert _head(repo_root) == head_before

        on_disk = read_acceptance_matrix(feature_dir)
        assert on_disk is not None
        assert on_disk.criteria[0].pass_fail == "fail"

    def test_guard_lock_timeout_refuses_mission_not_ready(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A ``FeatureStatusLockTimeoutError`` from the pre-stamp verdict
        guard's own lock acquisition must be translated to
        ``MISSION_NOT_READY`` (never a raw traceback), with nothing recorded.

        Mutating the ``except FeatureStatusLockTimeoutError`` translation in
        ``_stamp_acceptance_record`` into a silent pass would let
        the timeout propagate as an unhandled exception instead of a
        structured refusal -- this test's ``catch_exceptions=False`` CLI
        invocation would then raise instead of returning a JSON envelope.
        """
        mission_slug = "issue-4934-guard-lock-timeout"
        repo_root, feature_dir = _seed_acceptable_mission(tmp_path, mission_slug)
        head_before = _head(repo_root)

        @contextmanager
        def _timing_out_guard(*_args: object, **_kwargs: object) -> Iterator[object]:
            raise FeatureStatusLockTimeoutError("lock timed out (test double)")
            yield  # pragma: no cover -- unreachable, required for generator shape

        monkeypatch.setattr(
            "specify_cli.acceptance.matrix.locked_acceptance_verdict_guard",
            _timing_out_guard,
        )

        result = _invoke_accept_mission(repo_root, mission_slug, monkeypatch)

        assert result.exit_code != 0, result.output
        payload = json.loads(result.output)
        assert payload["error_code"] == "MISSION_NOT_READY"
        assert "lock timed out" in payload["data"]["message"]

        meta = _meta(feature_dir)
        assert "accepted_at" not in meta
        assert _head(repo_root) == head_before

    def test_malformed_matrix_refuses_inside_envelope(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A malformed acceptance-matrix item refuses with MISSION_NOT_READY in the
        JSON envelope instead of escaping as a traceback, and records nothing."""
        mission_slug = "issue-4934-malformed-matrix"
        repo_root, feature_dir = _seed_acceptable_mission(tmp_path, mission_slug)
        matrix_path = feature_dir / "acceptance-matrix.json"
        raw = json.loads(matrix_path.read_text(encoding="utf-8"))
        raw["criteria"] = [{"malformed": True}]
        matrix_path.write_text(json.dumps(raw), encoding="utf-8")
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-m", "matrix goes malformed")
        head_before = _head(repo_root)

        result = _invoke_accept_mission(repo_root, mission_slug, monkeypatch)

        assert result.exit_code != 0, result.output
        payload = json.loads(result.output)
        assert payload["error_code"] == "MISSION_NOT_READY"
        assert "accepted_at" not in _meta(feature_dir)
        assert _head(repo_root) == head_before

    def test_matrix_malformed_at_guard_reread_refuses_inside_envelope(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A matrix left malformed between the readiness check and the guard's
        locked re-read refuses with MISSION_NOT_READY, and records nothing."""
        mission_slug = "issue-4934-guard-malformed"
        repo_root, feature_dir = _seed_acceptable_mission(tmp_path, mission_slug)
        head_before = _head(repo_root)

        @contextmanager
        def _malformed_guard(*_args: object, **_kwargs: object) -> Iterator[object]:
            raise AcceptanceMatrixParseError(section="criteria", item_index=0, reason="malformed test double")
            yield  # pragma: no cover -- unreachable, required for generator shape

        monkeypatch.setattr(
            "specify_cli.acceptance.matrix.locked_acceptance_verdict_guard",
            _malformed_guard,
        )

        result = _invoke_accept_mission(repo_root, mission_slug, monkeypatch)

        assert result.exit_code != 0, result.output
        payload = json.loads(result.output)
        assert payload["error_code"] == "MISSION_NOT_READY"
        assert "malformed" in json.dumps(payload)
        assert "accepted_at" not in _meta(feature_dir)
        assert _head(repo_root) == head_before

    def test_coord_topology_accept_reads_back_from_primary_anchor(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """On a coord-topology mission,
        ``_stamp_acceptance_record`` writes ``accepted_at`` into the PRIMARY
        anchor's ``meta.json`` (``summary.feature_dir``), never into
        ``mission_dir`` -- which for a coord-topology mission is the
        coordination worktree's STATUS dir and carries no ``meta.json`` at
        all. Reading the stamp back from ``mission_dir`` (the pre-fix defect)
        let the write succeed and then raised a raw ``FileNotFoundError``
        instead of returning a JSON envelope -- a crash AFTER a partial
        write. This drives the real CLI against a real coordination-branch
        fixture (mirroring ``tests/orchestrator_api/test_issue_4889_caller_independence.py``'s
        ``ensure_coordination_branch`` + ``coord_feature_dir`` pattern) and
        asserts success, a JSON envelope, and ``accepted_at`` landing in the
        PRIMARY ``meta.json`` equal to ``data["accepted_at"]``.
        """
        mission_slug = "issue-4934-coord-topology-accept"
        repo_root, feature_dir = _seed_acceptable_mission(tmp_path, mission_slug)
        mission_id = derive_mission_id(mission_slug)

        (repo_root / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-m", "ignore worktrees")

        coord_result = ensure_coordination_branch(
            repo_root=repo_root,
            mission_slug=mission_slug,
            mission_id=mission_id,
            target_branch="main",
        )
        meta = _meta(feature_dir)
        meta["coordination_branch"] = coord_result.branch_name
        (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-m", "wire coordination_branch into meta")

        coord_root = CoordinationWorkspace.resolve(repo_root, mission_slug, mission_id[:8])
        coord_dir = coord_feature_dir(repo_root, mission_slug, mission_id[:8])
        coord_dir.mkdir(parents=True, exist_ok=True)
        for name in ("status.events.jsonl", "acceptance-matrix.json"):
            source = feature_dir / name
            if source.exists():
                shutil.copy(source, coord_dir / name)
        # The coord-aware STATUS dir carries the mission's live status/matrix
        # but deliberately NO ``meta.json`` -- that is the whole point of the
        # PRIMARY/COORD split this test pins.
        assert not (coord_dir / "meta.json").exists()
        _git(coord_root, "add", "-A")
        _git(coord_root, "commit", "-m", "seed coord status + matrix")

        result = _invoke_accept_mission(repo_root, mission_slug, monkeypatch)

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["success"] is True
        assert payload["data"]["accepted"] is True

        primary_meta = _meta(feature_dir)
        assert "accepted_at" in primary_meta
        assert payload["data"]["accepted_at"] == primary_meta["accepted_at"]
        assert not (coord_dir / "meta.json").exists()

    def test_never_claimed_wp_at_done_refuses_mission_not_ready_metadata(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The explicit ``strict_metadata=True`` pin at the
        ``collect_feature_summary`` call site (``orchestrator_api/commands.py``)
        actually matters. A WP that reaches ``done`` via a claim event with NO
        ``policy_metadata={"agent": ...}`` has no durable implementer of
        record, i.e. it was genuinely never claimed in the sense the strict
        gate cares about -- ``accept-mission`` must refuse with
        ``MISSION_NOT_READY`` and a non-empty ``outstanding["metadata"]``,
        and record nothing. Mutating ``strict_metadata=True`` to ``False``
        at that call site makes this same mission wrongly accept (verified
        manually as red/green mutation evidence).
        """
        mission_slug = "issue-4934-never-claimed-metadata"
        repo_root, feature_dir = _seed_mission_with_never_claimed_done_wp(tmp_path, mission_slug)
        head_before = _head(repo_root)

        result = _invoke_accept_mission(repo_root, mission_slug, monkeypatch)

        assert result.exit_code != 0, result.output
        payload = json.loads(result.output)
        assert payload["success"] is False
        assert payload["error_code"] == "MISSION_NOT_READY"

        outstanding = payload["data"]["outstanding"]
        assert isinstance(outstanding, dict)
        assert outstanding.get("metadata"), outstanding
        assert any("WP01" in item and "missing agent" in item for item in outstanding["metadata"])

        meta = _meta(feature_dir)
        assert "accepted_at" not in meta
        assert "acceptance_mode" not in meta
        assert "acceptance_history" not in meta
        assert _head(repo_root) == head_before
