"""End-to-end invocation tests (WP05 T018–T021, WP06 T032).

Tests exercise the dispatch/execute loop at the executor level (bypassing the CLI
layer for reliability) to verify:

- T018: A `started` JSONL record is written with a 26-char ULID invocation_id.
- T019: `complete_invocation` appends a `completed` event with the correct outcome.
- T020: `invocations list` reads from local JSONL without SaaS connectivity.
- T021: When `effective_sync_enabled=False`, `_get_saas_client` is never called
         but the local JSONL is still written.

WP06 additions (T032):
- mode_of_work is recorded on the started event (FR-008).
- artifact_link / commit_link events appended by complete_invocation (FR-007).
- InvalidModeForEvidenceError raised pre-write for non-eligible modes (FR-009).
- Legacy records with null mode_of_work allow evidence (backward compat).
- Sync-disabled: all events written locally, no propagation errors.

Implementation note: Tests use the executor/writer/propagator directly rather
than CliRunner to avoid CLI routing complexity (ActionRouter requires profiles).
The acceptance criteria only require the *behaviour* to be verified, not that it
goes through the full CLI layer.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Literal
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.invocation.errors import InvalidModeForEvidenceError
from specify_cli.invocation.executor import ProfileInvocationExecutor
from specify_cli.invocation.modes import ModeOfWork
from specify_cli.invocation.record import OpStartedEvent
from specify_cli.invocation.writer import EVENTS_DIR


# ---------------------------------------------------------------------------
# Shared helpers / fixtures
# ---------------------------------------------------------------------------

# git_repo: the e2e flow exercises close-time auto-commit via subprocess git.
pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "profiles"

_COMPACT_CTX = MagicMock()
_COMPACT_CTX.mode = "compact"
_COMPACT_CTX.text = "compact governance context"

_MISSING_CTX = MagicMock()
_MISSING_CTX.mode = "missing"
_MISSING_CTX.text = ""


def _setup_minimal_project(tmp_path: Path) -> Path:
    """Create a minimal project structure for invocation tests.

    Copies fixture profiles into .kittify/profiles/ so that ProfileRegistry
    can resolve them.  Also creates the events directory pre-emptively so
    directory-existence checks in tests do not require a prior write.
    """
    profiles_dir = tmp_path / ".kittify" / "profiles"
    profiles_dir.mkdir(parents=True)
    for yaml_file in FIXTURES_DIR.glob("*.agent.yaml"):
        shutil.copy(yaml_file, profiles_dir / yaml_file.name)

    events_dir = tmp_path / EVENTS_DIR
    events_dir.mkdir(parents=True, exist_ok=True)
    return tmp_path


def _make_started_record(invocation_id: str = "01KPQRX2EVGMRVB4Q1JQBAZJV3") -> OpStartedEvent:
    """Create a minimal started record for direct writer/propagator tests."""
    return OpStartedEvent(
        invocation_id=invocation_id,
        profile_id="implementer-fixture",
        action="implement",
        request_text="test request",
        actor="claude",
        mode_of_work="task_execution",
        governance_context_hash="abcdef0123456789",
        governance_context_available=True,
        started_at="2026-04-22T06:00:00Z",
    )


# ---------------------------------------------------------------------------
# T018 — test_dispatch_writes_tier1_jsonl
# ---------------------------------------------------------------------------


def test_dispatch_writes_tier1_jsonl(tmp_path: Path) -> None:
    """Running the executor must write a `started` JSONL record (Tier 1 audit trail).

    Verifies:
    - At least one JSONL file is created in kitty-ops/
    - First line event == "started"
    - invocation_id is present and is 26 characters (ULID)
    """
    project = _setup_minimal_project(tmp_path)

    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project)
        payload = executor.invoke("implement the feature", profile_hint="implementer-fixture")

    events_dir = project / EVENTS_DIR
    jsonl_files = list(events_dir.glob("*.jsonl"))
    assert len(jsonl_files) >= 1, f"No JSONL files found in {events_dir}"

    # The file is named after the invocation_id
    expected_file = events_dir / f"{payload.invocation_id}.jsonl"
    assert expected_file.exists(), f"Expected JSONL file {expected_file} not found"

    lines = [ln for ln in expected_file.read_text().splitlines() if ln.strip()]
    assert len(lines) >= 1, "JSONL file is empty"

    started = json.loads(lines[0])
    assert started["event"] == "started", f"Expected event='started', got {started['event']!r}"
    assert "invocation_id" in started, "invocation_id missing from started record"
    assert len(started["invocation_id"]) == 26, f"Expected 26-char ULID, got {len(started['invocation_id'])!r}-char {started['invocation_id']!r}"


# ---------------------------------------------------------------------------
# T019 — test_complete_writes_completed_event
# ---------------------------------------------------------------------------


def test_complete_writes_completed_event(tmp_path: Path) -> None:
    """After calling complete_invocation, the JSONL must have a `completed` event.

    Verifies:
    - JSONL file has exactly 2 lines (started + completed)
    - Second line event == "completed", outcome == "done"
    - invocation_id matches across both records
    """
    project = _setup_minimal_project(tmp_path)

    # Step 1: Start invocation
    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project)
        payload = executor.invoke("implement the feature", profile_hint="implementer-fixture")

    invocation_id = payload.invocation_id

    # Step 2: Complete invocation
    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor.complete_invocation(
            invocation_id=invocation_id,
            outcome="done",
            closed_by="agent",
        )

    # Step 3: Verify JSONL has started + completed
    events_dir = project / EVENTS_DIR
    jsonl_file = events_dir / f"{invocation_id}.jsonl"
    assert jsonl_file.exists(), f"JSONL file {jsonl_file} not found"

    lines = [ln for ln in jsonl_file.read_text().splitlines() if ln.strip()]
    assert len(lines) == 2, f"Expected 2 lines (started + completed), got {len(lines)}"

    completed = json.loads(lines[1])
    assert completed["event"] == "completed", f"Expected event='completed', got {completed['event']!r}"
    assert completed["outcome"] == "done", f"Expected outcome='done', got {completed['outcome']!r}"
    assert completed["invocation_id"] == invocation_id, f"invocation_id mismatch: {completed['invocation_id']!r} != {invocation_id!r}"
    # FR-003: the closing actor is recorded verbatim on the written line.
    assert '"closed_by": "agent"' in lines[1], f"Expected literal closed_by=agent on the completed line, got: {lines[1]!r}"


# ---------------------------------------------------------------------------
# T020 — test_invocations_list_reads_local_only
# ---------------------------------------------------------------------------


def test_invocations_list_reads_local_only(tmp_path: Path) -> None:
    """invocations list must return records from local JSONL without SaaS connectivity.

    Verifies (FR-012/AC-012):
    - A manually-written JSONL file in the events dir is returned by _iter_records
    - No SaaS call is required — the read path is purely local
    """
    from specify_cli.cli.commands.invocations_cmd import _iter_records

    project = _setup_minimal_project(tmp_path)
    events_dir = project / EVENTS_DIR

    # Write a JSONL file directly to simulate a prior invocation
    test_id = "01KPQRX2EVGMRVB4Q1JQBAZJV4"
    jsonl = events_dir / f"{test_id}.jsonl"
    started_record = {
        "event": "started",
        "invocation_id": test_id,
        "profile_id": "implementer-fixture",
        "action": "implement",
        "request_text": "test local read",
        "governance_context_hash": "abc123",
        "governance_context_available": True,
        "actor": "claude",
        "mode_of_work": "task_execution",
        "router_confidence": None,
        "started_at": "2026-04-22T06:00:00Z",
    }
    jsonl.write_text(json.dumps(started_record) + "\n", encoding="utf-8")

    # _iter_records reads local JSONL with no SaaS access
    # Patch the transport seam to ensure no SaaS lookup is attempted
    with patch("specify_cli.invocation.propagator._get_saas_client") as mock_client_lookup:
        records = list(_iter_records(events_dir, profile_filter=None, limit=100, repo_root=project))
        # The transport seam is NOT called by the read path — assert it was never invoked
        mock_client_lookup.assert_not_called()

    assert any(r.get("invocation_id") == test_id for r in records), (
        f"Expected invocation_id={test_id!r} in list output; got: {[r.get('invocation_id') for r in records]}"
    )


# ---------------------------------------------------------------------------
# T021 — no transport registered: local trail only
# ---------------------------------------------------------------------------


def _inline_submit() -> Any:
    """A ``submit`` replacement that propagates synchronously.

    ``InvocationSaaSPropagator.submit`` runs ``_propagate_one`` on a worker thread;
    asserting anything about that work from the test thread without joining it is a
    coin flip. Running it inline keeps the executor's real call path.
    """
    from specify_cli.invocation.propagator import InvocationSaaSPropagator

    def _sync_submit(self: InvocationSaaSPropagator, record: object) -> None:
        from specify_cli.invocation.propagator import _propagate_one

        _propagate_one(record, self._repo_root)  # type: ignore[arg-type]

    return _sync_submit


def test_without_a_transport_only_local_events_are_written(tmp_path: Path) -> None:
    """No transport registered: local JSONL is written, nothing reaches a client.

    Verifies (AC-004), over the wired path (executor + propagator, as
    ``cli.commands.dispatch`` builds them):
    - the transport seam answers ``None`` (nothing registers a factory since issue
      #5 deleted the sync transport), so no envelope is built or sent
    - Local JSONL file is still written (Tier 1 trail is mandatory regardless of sync)
    """
    from specify_cli.invocation.propagator import InvocationSaaSPropagator

    project = _setup_minimal_project(tmp_path)

    with (
        patch(
            "specify_cli.invocation.propagator.InvocationSaaSPropagator.submit",
            new=_inline_submit(),
        ),
        patch(
            "specify_cli.invocation.propagator._get_saas_client",
            return_value=None,
        ) as mock_client,
        patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_COMPACT_CTX,
        ),
    ):
        executor = ProfileInvocationExecutor(project, propagator=InvocationSaaSPropagator(project))
        payload = executor.invoke(
            "implement the feature",
            profile_hint="implementer-fixture",
        )

        # (a) The seam was consulted, answered "no transport", and nothing was sent
        mock_client.assert_called_once()

    # (b) Local JSONL written by the executor (not manually) — Tier 1 is mandatory
    events_dir = project / EVENTS_DIR
    expected_file = events_dir / f"{payload.invocation_id}.jsonl"
    assert expected_file.exists(), f"Expected executor to write JSONL at {expected_file}; file not found"
    import json as _json

    lines = [ln for ln in expected_file.read_text().splitlines() if ln.strip()]
    assert len(lines) >= 1 and _json.loads(lines[0])["event"] == "started"

    from specify_cli.invocation.propagator import PROPAGATION_ERRORS_PATH

    assert not (project / PROPAGATION_ERRORS_PATH).exists(), (
        "transport-less propagation is not an error and must not be logged as one"
    )


# ===========================================================================
# WP06 T032 — Mode derivation + correlation + enforcement e2e tests
# ===========================================================================


def _invoke_with_mode(
    project: Path,
    mode: ModeOfWork,
    profile_hint: str = "implementer-fixture",
) -> str:
    """Helper: invoke executor with explicit mode_of_work, return invocation_id."""
    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project)
        payload = executor.invoke(
            "test request",
            profile_hint=profile_hint,
            mode_of_work=mode,
        )
    return payload.invocation_id


def _write_legacy_started(project: Path, invocation_id: str) -> None:
    """Write a legacy started event WITHOUT mode_of_work (pre-WP06 format).

    Written as a raw JSONL line — the v2 ``OpStartedEvent`` model cannot
    represent this legacy shape (mode_of_work is required by construction).
    """
    events_dir = project / EVENTS_DIR
    events_dir.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {
            "event": "started",
            "invocation_id": invocation_id,
            "profile_id": "implementer-fixture",
            "action": "implement",
            "request_text": "legacy test request",
            "started_at": "2026-04-22T06:00:00Z",
            # Intentionally no mode_of_work
        }
    )
    (events_dir / f"{invocation_id}.jsonl").write_text(line + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# test_started_event_records_mode_advisory
# ---------------------------------------------------------------------------


def test_started_event_records_mode_advisory(tmp_path: Path) -> None:
    """Invoking with ADVISORY mode records mode_of_work='advisory' on the started event (FR-008)."""
    project = _setup_minimal_project(tmp_path)
    inv_id = _invoke_with_mode(project, ModeOfWork.ADVISORY)

    events_dir = project / EVENTS_DIR
    started_raw = json.loads((events_dir / f"{inv_id}.jsonl").read_text().splitlines()[0])
    assert started_raw.get("mode_of_work") == "advisory", f"Expected mode_of_work='advisory', got {started_raw.get('mode_of_work')!r}"


# ---------------------------------------------------------------------------
# test_started_event_records_mode_task_execution
# ---------------------------------------------------------------------------


def test_started_event_records_mode_task_execution(tmp_path: Path) -> None:
    """Standalone execution records mode_of_work='task_execution' (FR-008).

    Simulated programmatically since ActionRouter setup would require full profiles.
    """
    project = _setup_minimal_project(tmp_path)

    inv_id_one = _invoke_with_mode(project, ModeOfWork.TASK_EXECUTION)
    events_dir = project / EVENTS_DIR
    started_one = json.loads((events_dir / f"{inv_id_one}.jsonl").read_text().splitlines()[0])
    assert started_one.get("mode_of_work") == "task_execution"

    inv_id_two = _invoke_with_mode(project, ModeOfWork.TASK_EXECUTION)
    started_two = json.loads((events_dir / f"{inv_id_two}.jsonl").read_text().splitlines()[0])
    assert started_two.get("mode_of_work") == "task_execution"


# ---------------------------------------------------------------------------
# test_complete_with_two_artifacts_and_commit
# ---------------------------------------------------------------------------


def test_complete_with_two_artifacts_and_commit(tmp_path: Path) -> None:
    """complete_invocation with two --artifact and one --commit appends 3 correlation events (FR-007)."""
    project = _setup_minimal_project(tmp_path)
    inv_id = _invoke_with_mode(project, ModeOfWork.TASK_EXECUTION)

    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project)
        executor.complete_invocation(
            invocation_id=inv_id,
            outcome="done",
            closed_by="agent",
            artifact_refs=["src/foo.py", "src/bar.py"],
            commit_sha="deadbeef1234",
        )

    events_dir = project / EVENTS_DIR
    lines = [ln for ln in (events_dir / f"{inv_id}.jsonl").read_text().splitlines() if ln.strip()]
    # started (1) + completed (1) + artifact_link (1) + artifact_link (1) + commit_link (1) = 5
    assert len(lines) == 5, f"Expected 5 lines, got {len(lines)}: {[json.loads(ln)['event'] for ln in lines]}"
    events = [json.loads(ln)["event"] for ln in lines]
    assert events[0] == "started"
    assert events[1] == "completed"
    assert events[2] == "artifact_link"
    assert events[3] == "artifact_link"
    assert events[4] == "commit_link"

    sha_event = json.loads(lines[4])
    assert sha_event["sha"] == "deadbeef1234"


# ---------------------------------------------------------------------------
# test_complete_artifact_ref_normalisation_in_checkout
# ---------------------------------------------------------------------------


def test_complete_artifact_ref_normalisation_in_checkout(tmp_path: Path) -> None:
    """An artifact path inside the repo checkout is stored repo-relative (FR-007 / data-model §6)."""
    project = _setup_minimal_project(tmp_path)
    # Create a file inside the project
    (project / "src").mkdir(exist_ok=True)
    artifact_file = project / "src" / "output.py"
    artifact_file.write_text("# generated")

    inv_id = _invoke_with_mode(project, ModeOfWork.TASK_EXECUTION)

    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project)
        executor.complete_invocation(
            invocation_id=inv_id,
            outcome="done",
            closed_by="agent",
            artifact_refs=[str(artifact_file)],
        )

    events_dir = project / EVENTS_DIR
    lines = [ln for ln in (events_dir / f"{inv_id}.jsonl").read_text().splitlines() if ln.strip()]
    artifact_event = json.loads(lines[2])
    assert artifact_event["event"] == "artifact_link"
    # Should be repo-relative: src/output.py
    stored_ref = artifact_event["ref"]
    assert not Path(stored_ref).is_absolute(), f"Expected repo-relative ref, got: {stored_ref!r}"
    assert "output.py" in stored_ref


# ---------------------------------------------------------------------------
# test_complete_artifact_ref_outside_checkout
# ---------------------------------------------------------------------------


def test_complete_artifact_ref_outside_checkout(tmp_path: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    """An artifact path outside the repo checkout is stored absolute (FR-007 / data-model §6)."""
    project = _setup_minimal_project(tmp_path)
    outside = tmp_path_factory.mktemp("outside_repo") / "external.log"
    outside.write_text("log data")

    inv_id = _invoke_with_mode(project, ModeOfWork.TASK_EXECUTION)

    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project)
        executor.complete_invocation(
            invocation_id=inv_id,
            outcome="done",
            closed_by="agent",
            artifact_refs=[str(outside)],
        )

    events_dir = project / EVENTS_DIR
    lines = [ln for ln in (events_dir / f"{inv_id}.jsonl").read_text().splitlines() if ln.strip()]
    artifact_event = json.loads(lines[2])
    assert artifact_event["event"] == "artifact_link"
    stored_ref = artifact_event["ref"]
    assert Path(stored_ref).is_absolute(), f"Expected absolute ref for external path, got: {stored_ref!r}"


# ---------------------------------------------------------------------------
# test_complete_rejects_evidence_on_advisory
# ---------------------------------------------------------------------------


def test_complete_rejects_evidence_on_advisory(tmp_path: Path) -> None:
    """complete_invocation with --evidence on ADVISORY mode raises InvalidModeForEvidenceError (FR-009).

    The rejection must be pre-write: no `completed` event is appended to the JSONL.
    The evidence artifact must NOT be created.
    """
    project = _setup_minimal_project(tmp_path)
    inv_id = _invoke_with_mode(project, ModeOfWork.ADVISORY)

    # Create a dummy evidence file
    evidence_file = tmp_path / "evidence.md"
    evidence_file.write_text("# Evidence")

    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project)
        with pytest.raises(InvalidModeForEvidenceError) as exc_info:
            executor.complete_invocation(
                invocation_id=inv_id,
                outcome="done",
                closed_by="agent",
                evidence_ref=str(evidence_file),
            )

    assert exc_info.value.mode == ModeOfWork.ADVISORY
    assert exc_info.value.invocation_id == inv_id

    # Verify: no `completed` event appended (rejection is pre-write)
    events_dir = project / EVENTS_DIR
    lines = [ln for ln in (events_dir / f"{inv_id}.jsonl").read_text().splitlines() if ln.strip()]
    assert len(lines) == 1, f"Expected only the started event, but got {len(lines)} lines: {lines}"
    assert json.loads(lines[0])["event"] == "started"

    # Verify: evidence artifact NOT created
    evidence_base = project / ".kittify" / "evidence" / inv_id
    assert not evidence_base.exists(), f"Evidence artifact was created at {evidence_base} despite rejection"


# ---------------------------------------------------------------------------
# test_complete_rejects_evidence_on_query
# ---------------------------------------------------------------------------


def test_complete_rejects_evidence_on_query(tmp_path: Path) -> None:
    """complete_invocation with --evidence on QUERY mode raises InvalidModeForEvidenceError (FR-009).

    Note: Query invocations are not opened at the baseline CLI layer (profiles.list,
    invocations.list don't open InvocationRecords). This test simulates query mode
    programmatically via invoke(mode_of_work=ModeOfWork.QUERY).
    """
    project = _setup_minimal_project(tmp_path)
    inv_id = _invoke_with_mode(project, ModeOfWork.QUERY)

    evidence_file = tmp_path / "evidence.md"
    evidence_file.write_text("# Query Evidence")

    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project)
        with pytest.raises(InvalidModeForEvidenceError) as exc_info:
            executor.complete_invocation(
                invocation_id=inv_id,
                outcome="done",
                closed_by="agent",
                evidence_ref=str(evidence_file),
            )

    assert exc_info.value.mode == ModeOfWork.QUERY

    # Verify pre-write rejection: no completed event
    events_dir = project / EVENTS_DIR
    lines = [ln for ln in (events_dir / f"{inv_id}.jsonl").read_text().splitlines() if ln.strip()]
    assert len(lines) == 1, f"Expected only started event, got {len(lines)} lines"


# ---------------------------------------------------------------------------
# test_complete_allows_evidence_on_task_execution
# ---------------------------------------------------------------------------


def test_complete_allows_evidence_on_task_execution(tmp_path: Path) -> None:
    """complete_invocation with --evidence on TASK_EXECUTION mode succeeds (FR-009)."""
    project = _setup_minimal_project(tmp_path)
    inv_id = _invoke_with_mode(project, ModeOfWork.TASK_EXECUTION)

    # Create an evidence file for promotion
    evidence_file = tmp_path / "evidence.md"
    evidence_file.write_text("# Implementation Evidence\n\nWe did the thing.")

    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project)
        completed = executor.complete_invocation(
            invocation_id=inv_id,
            outcome="done",
            closed_by="agent",
            evidence_ref=str(evidence_file),
        )

    assert completed.event == "completed"
    assert completed.evidence_ref == str(evidence_file)

    # Verify evidence artifact was created
    evidence_base = project / ".kittify" / "evidence" / inv_id
    assert evidence_base.exists(), f"Evidence artifact not found at {evidence_base}"
    assert (evidence_base / "evidence.md").exists()


# ---------------------------------------------------------------------------
# test_complete_allows_evidence_on_mission_step
# ---------------------------------------------------------------------------


def test_complete_allows_evidence_on_mission_step(tmp_path: Path) -> None:
    """complete_invocation with --evidence on MISSION_STEP mode succeeds (FR-009).

    Note: Mission-step invocations are opened out-of-process by agents in the 3.2.x
    baseline. This test simulates mission_step mode programmatically.
    """
    project = _setup_minimal_project(tmp_path)
    inv_id = _invoke_with_mode(project, ModeOfWork.MISSION_STEP)

    evidence_file = tmp_path / "spec_evidence.md"
    evidence_file.write_text("# Spec Evidence")

    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project)
        completed = executor.complete_invocation(
            invocation_id=inv_id,
            outcome="done",
            closed_by="agent",
            evidence_ref=str(evidence_file),
        )

    assert completed.event == "completed"
    # Evidence artifact created
    evidence_base = project / ".kittify" / "evidence" / inv_id
    assert evidence_base.exists()


# ---------------------------------------------------------------------------
# test_complete_on_pre_mission_record_allows_evidence
# ---------------------------------------------------------------------------


def test_complete_on_pre_mission_record_allows_evidence(tmp_path: Path) -> None:
    """A legacy started event with no mode_of_work field allows evidence (backward compat).

    Pre-WP06 InvocationRecords have no mode_of_work. The enforcement gate treats
    None mode as permissive — no enforcement (FR-009 null-tolerant clause).
    """
    project = _setup_minimal_project(tmp_path)
    inv_id = "01KPWA5X1EGACY0000000000WP"
    _write_legacy_started(project, inv_id)

    evidence_file = tmp_path / "legacy_evidence.md"
    evidence_file.write_text("# Legacy Evidence")

    # Ensure events dir exists (legacy records may predate directory creation)
    (project / EVENTS_DIR).mkdir(parents=True, exist_ok=True)

    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project)
        completed = executor.complete_invocation(
            invocation_id=inv_id,
            outcome="done",
            closed_by="agent",
            evidence_ref=str(evidence_file),
        )

    assert completed.event == "completed"
    # Evidence artifact created without enforcement rejection
    evidence_base = project / ".kittify" / "evidence" / inv_id
    assert evidence_base.exists(), "Legacy record should allow evidence promotion"


# ---------------------------------------------------------------------------
# test_sync_disabled_no_propagation_errors (T032 #11)
# ---------------------------------------------------------------------------


# ===========================================================================
# WP02 (#794) — action_hint kwarg behavioral tests (T009)
# ===========================================================================


@pytest.mark.parametrize("action_key", ["specify", "plan", "tasks", "implement", "review"])
def test_invoke_with_action_hint_and_profile_hint_records_hint(tmp_path: Path, action_key: str) -> None:
    """profile_hint + truthy action_hint records action_hint verbatim (FR-009/FR-010).

    Parametrized over the five contract actions (specify/plan/tasks/implement/review)
    used by mission-step composition. The recorded `started` event MUST carry the
    caller-supplied action key, and the returned payload MUST expose the same value.
    """
    project = _setup_minimal_project(tmp_path)

    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project)
        payload = executor.invoke(
            "any request text",
            profile_hint="architect-alphonso",
            action_hint=action_key,
        )

    # Payload exposes the hint
    assert payload.action == action_key, f"Expected payload.action={action_key!r}, got {payload.action!r}"

    # Started JSONL record carries the hint
    events_dir = project / EVENTS_DIR
    jsonl_file = events_dir / f"{payload.invocation_id}.jsonl"
    started = json.loads(jsonl_file.read_text().splitlines()[0])
    assert started["action"] == action_key, f"Expected started.action={action_key!r}, got {started['action']!r}"


def test_invoke_profile_hint_only_falls_back_to_derived_action(tmp_path: Path) -> None:
    """profile_hint with no action_hint falls back to the role-default verb (FR-011).

    With architect-alphonso (Role.ARCHITECT), the legacy derivation returns the first
    canonical verb for the role. The recorded action MUST equal what
    ``_derive_action_from_request(request_text, profile.role)`` returns.
    """
    project = _setup_minimal_project(tmp_path)
    request_text = "design the new component boundaries"

    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project)
        # Compute expected legacy action via the same path the executor uses
        profile = executor._registry.resolve("architect-alphonso")
        expected_action = executor._derive_action_from_request(request_text, profile.role)

        payload = executor.invoke(
            request_text,
            profile_hint="architect-alphonso",
        )

    assert payload.action == expected_action

    events_dir = project / EVENTS_DIR
    jsonl_file = events_dir / f"{payload.invocation_id}.jsonl"
    started = json.loads(jsonl_file.read_text().splitlines()[0])
    assert started["action"] == expected_action, f"Expected legacy-derived action {expected_action!r}, got {started['action']!r}"


def test_invoke_empty_action_hint_falls_back(tmp_path: Path) -> None:
    """Empty-string action_hint is treated as not supplied (EDGE-005).

    The truthiness check (`if action_hint:`) means an empty string falls back to
    the legacy role-default-verb derivation, identical to passing no hint at all.
    """
    project = _setup_minimal_project(tmp_path)
    request_text = "evaluate the architecture"

    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project)
        profile = executor._registry.resolve("architect-alphonso")
        expected_action = executor._derive_action_from_request(request_text, profile.role)

        payload = executor.invoke(
            request_text,
            profile_hint="architect-alphonso",
            action_hint="",
        )

    assert payload.action == expected_action

    events_dir = project / EVENTS_DIR
    jsonl_file = events_dir / f"{payload.invocation_id}.jsonl"
    started = json.loads(jsonl_file.read_text().splitlines()[0])
    assert started["action"] == expected_action, f"Empty-string action_hint should fall back to {expected_action!r}, got {started['action']!r}"


def test_invoke_router_branch_unchanged_with_action_hint(tmp_path: Path) -> None:
    """Router-backed branch ignores action_hint entirely (FR-012).

    When ``profile_hint`` is None, the router decides both profile_id and action.
    A supplied ``action_hint`` MUST NOT override the router's action.
    """
    from specify_cli.invocation.router import RouterDecision

    project = _setup_minimal_project(tmp_path)

    router_action = "implement"
    fake_router = MagicMock()
    fake_router.route.return_value = RouterDecision(
        profile_id="implementer-fixture",
        action=router_action,
        confidence="canonical_verb",
        match_reason="test fixture",
        alternatives=[],
    )

    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project, router=fake_router)
        payload = executor.invoke(
            "implement the feature",
            profile_hint=None,
            action_hint="anything",
        )

    # Router decision wins; action_hint is ignored on this branch
    assert payload.action == router_action
    assert payload.action != "anything"

    events_dir = project / EVENTS_DIR
    jsonl_file = events_dir / f"{payload.invocation_id}.jsonl"
    started = json.loads(jsonl_file.read_text().splitlines()[0])
    assert started["action"] == router_action, f"Router branch must use router action {router_action!r}, got {started['action']!r}"
    assert started["action"] != "anything"


def test_without_a_transport_no_propagation_errors(tmp_path: Path) -> None:
    """With no transport registered, all events are written locally; no
    propagation-errors file is created.

    Verifies NFR-007 / SC-008: local-first invariant holds even with correlation events.
    """
    from specify_cli.invocation.propagator import InvocationSaaSPropagator

    project = _setup_minimal_project(tmp_path)

    with (
        patch(
            "specify_cli.invocation.propagator.InvocationSaaSPropagator.submit",
            new=_inline_submit(),
        ),
        patch(
            "specify_cli.invocation.propagator._get_saas_client",
            return_value=None,
        ) as mock_client,
        patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_COMPACT_CTX,
        ),
    ):
        executor = ProfileInvocationExecutor(project, propagator=InvocationSaaSPropagator(project))
        payload = executor.invoke(
            "implement with mode",
            profile_hint="implementer-fixture",
            mode_of_work=ModeOfWork.TASK_EXECUTION,
        )
        inv_id = payload.invocation_id

        # Complete with artifact and commit links
        executor.complete_invocation(
            invocation_id=inv_id,
            outcome="done",
            closed_by="agent",
            artifact_refs=["src/example.py"],
            commit_sha="cafebabe1234",
        )

        # The seam was consulted for both lifecycle events and answered "no transport"
        assert mock_client.call_count == 2

    # All events written locally
    events_dir = project / EVENTS_DIR
    jsonl_file = events_dir / f"{inv_id}.jsonl"
    assert jsonl_file.exists()
    lines = [ln for ln in jsonl_file.read_text().splitlines() if ln.strip()]
    # started + completed + artifact_link + commit_link = 4 lines
    assert len(lines) == 4, f"Expected 4 lines, got {len(lines)}: {[json.loads(ln)['event'] for ln in lines]}"

    events = [json.loads(ln)["event"] for ln in lines]
    assert events == ["started", "completed", "artifact_link", "commit_link"]

    # No propagation-errors file created
    from specify_cli.invocation.propagator import PROPAGATION_ERRORS_PATH

    prop_errors = project / PROPAGATION_ERRORS_PATH
    if prop_errors.exists():
        content = prop_errors.read_text()
        assert not content.strip(), f"Expected empty propagation-errors but got: {content}"


# ===========================================================================
# WP03 (T011/T013/T014) — closed_by threading + close-time auto-commit
# ===========================================================================


def _git(project: Path, *args: str) -> str:
    import subprocess

    return subprocess.run(
        ["git", "-C", str(project), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_git(project: Path) -> None:
    _git(project, "init", "-b", "wp03-test-branch")
    _git(project, "config", "user.email", "test@example.com")
    _git(project, "config", "user.name", "Test")
    (project / "README.md").write_text("repo\n", encoding="utf-8")
    _git(project, "add", "README.md")
    _git(project, "commit", "--no-verify", "-m", "init")


@pytest.mark.parametrize("outcome", ["done", "failed", "abandoned"])
def test_each_outcome_written_verbatim(tmp_path: Path, outcome: Literal["done", "failed", "abandoned"]) -> None:
    """Every supported outcome value is written verbatim — never coerced (FR-003)."""
    project = _setup_minimal_project(tmp_path)
    inv_id = _invoke_with_mode(project, ModeOfWork.TASK_EXECUTION)

    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project)
        executor.complete_invocation(
            invocation_id=inv_id,
            outcome=outcome,
            closed_by="agent",
        )

    lines = (project / EVENTS_DIR / f"{inv_id}.jsonl").read_text().splitlines()
    completed = json.loads(lines[1])
    assert completed["outcome"] == outcome
    assert completed["closed_by"] == "agent"


def test_closed_by_doctor_sweep_written_verbatim(tmp_path: Path) -> None:
    """The executor records whichever closing actor the caller threads (FR-003)."""
    project = _setup_minimal_project(tmp_path)
    inv_id = _invoke_with_mode(project, ModeOfWork.TASK_EXECUTION)

    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project)
        executor.complete_invocation(
            invocation_id=inv_id,
            outcome="abandoned",
            closed_by="doctor_sweep",
        )

    lines = (project / EVENTS_DIR / f"{inv_id}.jsonl").read_text().splitlines()
    assert json.loads(lines[1])["closed_by"] == "doctor_sweep"


def test_double_close_raises_already_closed_and_appends_nothing(tmp_path: Path) -> None:
    """Second close raises AlreadyClosedError and leaves the trail untouched (idempotent)."""
    from specify_cli.invocation.errors import AlreadyClosedError

    project = _setup_minimal_project(tmp_path)
    inv_id = _invoke_with_mode(project, ModeOfWork.TASK_EXECUTION)

    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project)
        executor.complete_invocation(invocation_id=inv_id, outcome="done", closed_by="agent")
        before = (project / EVENTS_DIR / f"{inv_id}.jsonl").read_text()
        with pytest.raises(AlreadyClosedError):
            executor.complete_invocation(invocation_id=inv_id, outcome="done", closed_by="agent")

    after = (project / EVENTS_DIR / f"{inv_id}.jsonl").read_text()
    assert after == before, "Double close must not append any event"


def test_open_op_untracked_then_committed_with_message_format(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-012: an open Op stays untracked; the close-time auto-commit message is
    ``op(<profile-id>): <action> [<id8>]``."""
    import re

    monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
    project = _setup_minimal_project(tmp_path)
    _init_git(project)

    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project)
        payload = executor.invoke(
            "implement the feature",
            profile_hint="implementer-fixture",
            mode_of_work=ModeOfWork.TASK_EXECUTION,
        )
        op_rel = f"{EVENTS_DIR}/{payload.invocation_id}.jsonl"

        # Before close: the Op record exists but is NOT tracked by git.
        assert (project / op_rel).exists()
        assert op_rel not in _git(project, "ls-files").splitlines()

        executor.complete_invocation(payload.invocation_id, outcome="done", closed_by="agent")

    # After close: file committed with the pinned message format.
    assert op_rel in _git(project, "ls-files").splitlines()
    subject = _git(project, "log", "-1", "--format=%s").strip()
    id8 = payload.invocation_id[:8]
    assert re.fullmatch(rf"op\(implementer-fixture\): \S+ \[{re.escape(id8)}\]", subject), f"Unexpected auto-commit subject: {subject!r}"
