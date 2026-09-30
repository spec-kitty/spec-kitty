"""Backward-compatibility and plumbing tests for MissionRun back-references.

WP05 (FR-024/FR-025/FR-026/FR-027/FR-028/FR-029/FR-030):
- MissionRunSnapshot gains optional mission_id and mission_slug fields
- MissionRunRef gains optional mission_id and mission_slug fields
- start_mission_run accepts and plumbs mission_id/mission_slug into snapshot/ref
- All snapshot-copy sites carry the new fields through
- Existing on-disk state.json files (no mission_id/mission_slug) load with None defaults

WP11 (#1663, FR-025/FR-026/FR-027, SC-006):
- runtime_bridge._advance_run_state_after_composition preserves mission_id/mission_slug
  through both snapshot reconstruction sites (auto-complete and final persist).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from runtime.next._internal_runtime import (
    MissionPolicySnapshot,
    NullEmitter,
    start_mission_run,
)
from runtime.next._internal_runtime.engine import MissionRunRef
from runtime.next._internal_runtime.schema import MissionRunSnapshot

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# T031 – Backward-compatibility: existing state.json files load with None defaults
# ---------------------------------------------------------------------------


def test_mission_run_snapshot_loads_without_mission_id():
    """Existing state.json files (no mission_id/mission_slug) load with None defaults."""
    legacy_data = {
        "run_id": "abc123",
        "mission_key": "software-dev",
        "template_path": "/nonexistent/mission.yaml",
        "template_hash": "deadbeef" * 8,
        "policy_snapshot": {"strictness": "medium", "default_route": "same_llm_context", "extras": {}},
        "completed_steps": [],
        "issued_step_id": None,
        "inputs": {},
        "decisions": {},
        "pending_decisions": {},
        "blocked_reason": None,
        # mission_id and mission_slug intentionally absent
    }
    snapshot = MissionRunSnapshot(**legacy_data)
    assert snapshot.mission_id is None
    assert snapshot.mission_slug is None


def test_mission_run_snapshot_loads_without_mission_id_model_validate():
    """model_validate path also handles missing fields with None defaults."""
    legacy_json = {
        "run_id": "abc456",
        "mission_key": "research",
        "template_path": "/nonexistent/mission.yaml",
        "template_hash": "cafebabe" * 8,
        # mission_id and mission_slug are absent
    }
    snapshot = MissionRunSnapshot.model_validate(legacy_json)
    assert snapshot.mission_id is None
    assert snapshot.mission_slug is None


def test_mission_run_ref_loads_without_mission_id():
    """MissionRunRef backward-compat: missing mission_id/mission_slug default to None."""
    ref = MissionRunRef(run_id="x", run_dir="/nonexistent/run", mission_key="software-dev")
    assert ref.mission_id is None
    assert ref.mission_slug is None


def test_mission_run_snapshot_with_new_fields():
    """New fields round-trip correctly when provided."""
    snapshot = MissionRunSnapshot(
        run_id="run1",
        mission_key="software-dev",
        template_path="/nonexistent/mission.yaml",
        template_hash="a" * 64,
        mission_id="01HABCDEFGHIJKLMNOPQRSTUVWX",
        mission_slug="my-feature-01KT6HVH",
    )
    assert snapshot.mission_id == "01HABCDEFGHIJKLMNOPQRSTUVWX"
    assert snapshot.mission_slug == "my-feature-01KT6HVH"


def test_mission_run_ref_with_new_fields():
    """MissionRunRef new fields round-trip correctly when provided."""
    ref = MissionRunRef(
        run_id="r1",
        run_dir="/nonexistent/runs/r1",
        mission_key="software-dev",
        mission_id="01HABCDEFGHIJKLMNOPQRSTUVWX",
        mission_slug="my-feature",
    )
    assert ref.mission_id == "01HABCDEFGHIJKLMNOPQRSTUVWX"
    assert ref.mission_slug == "my-feature"


# ---------------------------------------------------------------------------
# T028 – start_mission_run plumbs mission_id/mission_slug through
# ---------------------------------------------------------------------------


def _make_mission_yaml(tmp_path: Path, key: str = "test-mission") -> Path:
    mission_dir = tmp_path / key
    mission_dir.mkdir(parents=True, exist_ok=True)
    content = {
        "mission": {"key": key, "name": "Test Mission", "version": "1.0.0"},
        "steps": [
            {"id": "step-1", "title": "Step One", "prompt": "Do something."},
        ],
    }
    mission_yaml = mission_dir / "mission.yaml"
    mission_yaml.write_text(yaml.dump(content))
    return mission_dir


def test_start_mission_run_plumbs_mission_slug_and_id(tmp_path: Path):
    """start_mission_run passes mission_slug and mission_id into snapshot and ref."""
    mission_dir = _make_mission_yaml(tmp_path)
    run_store = tmp_path / "runs"

    ref = start_mission_run(
        template_key=str(mission_dir),
        inputs=None,
        policy_snapshot=MissionPolicySnapshot(),
        run_store=run_store,
        emitter=NullEmitter(),
        mission_slug="my-mission-01KT6HVH",
        mission_id="01KT6HVHEXAMPLEULID000000",
    )

    assert ref.mission_slug == "my-mission-01KT6HVH"
    assert ref.mission_id == "01KT6HVHEXAMPLEULID000000"


def test_start_mission_run_writes_mission_slug_to_snapshot(tmp_path: Path):
    """start_mission_run writes mission_slug/mission_id into the persisted state.json."""
    import json

    mission_dir = _make_mission_yaml(tmp_path)
    run_store = tmp_path / "runs"

    ref = start_mission_run(
        template_key=str(mission_dir),
        inputs=None,
        policy_snapshot=MissionPolicySnapshot(),
        run_store=run_store,
        emitter=NullEmitter(),
        mission_slug="slug-written-to-disk",
        mission_id="01TESTULID000000000000000",
    )

    run_dir = Path(ref.run_dir)
    state = json.loads((run_dir / "state.json").read_text())
    assert state["mission_slug"] == "slug-written-to-disk"
    assert state["mission_id"] == "01TESTULID000000000000000"


def test_start_mission_run_defaults_mission_fields_to_none(tmp_path: Path):
    """When mission_slug/mission_id are not provided, they default to None."""
    import json

    mission_dir = _make_mission_yaml(tmp_path)
    run_store = tmp_path / "runs"

    ref = start_mission_run(
        template_key=str(mission_dir),
        inputs=None,
        policy_snapshot=MissionPolicySnapshot(),
        run_store=run_store,
        emitter=NullEmitter(),
        # mission_slug and mission_id not passed
    )

    assert ref.mission_slug is None
    assert ref.mission_id is None

    run_dir = Path(ref.run_dir)
    state = json.loads((run_dir / "state.json").read_text())
    assert state.get("mission_slug") is None
    assert state.get("mission_id") is None


# ---------------------------------------------------------------------------
# T039/T040 — WP11 (#1663): runtime_bridge snapshot reconstructions carry identity
# ---------------------------------------------------------------------------


def _make_snapshot_with_identity(
    run_dir: Path,
    *,
    mission_id: str,
    mission_slug: str,
    issued_step_id: str | None = "specify",
) -> MissionRunSnapshot:
    """Write a state.json with known identity fields and an in-progress step.

    Simulates what the engine writes after ``start_mission_run`` + an
    initial ``next_step`` call that issues a step.
    """
    from runtime.next._internal_runtime.engine import _write_snapshot

    snapshot = MissionRunSnapshot(
        run_id="test-run-id-001",
        mission_key="software-dev",
        template_path=str(run_dir / "mission_template_frozen.yaml"),
        template_hash="a" * 64,
        policy_snapshot=MissionPolicySnapshot(),
        issued_step_id=issued_step_id,
        completed_steps=[],
        inputs={},
        decisions={},
        pending_decisions={},
        blocked_reason=None,
        mission_id=mission_id,
        mission_slug=mission_slug,
    )
    _write_snapshot(run_dir, snapshot)
    return snapshot


class _NullSyncEmitter:
    """Minimal sync emitter that satisfies _advance_run_state_after_composition."""

    def seed_from_snapshot(self, snapshot: object) -> None:
        return None

    def emit_next_step_auto_completed(self, payload: object) -> None:
        return None

    def emit_next_step_issued(self, payload: object) -> None:
        return None

    def emit_mission_run_completed(self, payload: object) -> None:
        return None

    def emit_decision_input_requested(self, payload: object) -> None:
        return None


def test_advance_run_state_preserves_identity_through_autocomplete_reconstruction(
    tmp_path: Path,
) -> None:
    """Regression for #1663: the auto-complete snapshot reconstruction (site 1)
    in _advance_run_state_after_composition must carry mission_id/mission_slug.

    Before the fix, ``issued_step_id is not None`` triggered a MissionRunSnapshot(...)
    that omitted both identity fields, resetting them to None.  This test asserts
    they survive through the Step 1 reconstruction and are persisted to disk.
    """
    from runtime.next._internal_runtime.engine import _read_snapshot
    from runtime.next._internal_runtime.schema import NextDecision
    from runtime.next.runtime_bridge import _advance_run_state_after_composition
    from runtime.next.runtime_bridge_engine import plan_composition_advance

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    # Provide the frozen template with the exact name _load_frozen_template expects.
    # At least one step is required by load_mission_template_file validation.
    (run_dir / "mission_template_frozen.yaml").write_text(
        "mission:\n  key: software-dev\n  name: Test\n  version: 1.0.0\n"
        "steps:\n  - id: specify\n    title: Specify\n",
        encoding="utf-8",
    )

    _make_snapshot_with_identity(
        run_dir,
        mission_id="01REGR001TEST000000000000",
        mission_slug="regression-test-1663",
        issued_step_id="specify",  # non-null → triggers site-1 reconstruction
    )

    run_ref = MissionRunRef(
        run_id="test-run-id-001",
        run_dir=str(run_dir),
        mission_key="software-dev",
        mission_id="01REGR001TEST000000000000",
        mission_slug="regression-test-1663",
    )
    feature_dir = tmp_path / "kitty-specs" / "regression-test-1663"
    feature_dir.mkdir(parents=True)

    with (
        patch(
            "runtime.next._internal_runtime.planner.plan_next",
            return_value=NextDecision(
                kind="step",
                run_id="test-run-id-001",
                mission_key="software-dev",
                step_id="plan",
            ),
        ),
        patch(
            "runtime.next.runtime_bridge_retrospective._resolve_retrospective_policy_for_runtime",
            return_value=(None, {}, None),
        ),
        patch(
            "runtime.next.runtime_bridge._map_runtime_decision",
            return_value=None,
        ),
    ):
        _advance_run_state_after_composition(
            run_ref=run_ref,
            agent="test-agent",
            mission_slug="regression-test-1663",
            mission_type="software-dev",
            repo_root=tmp_path,
            feature_dir=feature_dir,
            timestamp="2026-06-08T00:00:00+00:00",
            progress={},
            origin={},
            sync_emitter=_NullSyncEmitter(),  # type: ignore[arg-type]
            plan=plan_composition_advance(run_ref, "test-agent"),
        )

    persisted = _read_snapshot(run_dir)
    assert persisted.mission_id == "01REGR001TEST000000000000", (
        f"Expected mission_id='01REGR001TEST000000000000' but got {persisted.mission_id!r}; "
        "site-1 reconstruction dropped identity (#1663)"
    )
    assert persisted.mission_slug == "regression-test-1663", (
        f"Expected mission_slug='regression-test-1663' but got {persisted.mission_slug!r}; "
        "site-1 reconstruction dropped identity (#1663)"
    )

    # Also confirm in the raw JSON (state.json round-trip)
    state = json.loads((run_dir / "state.json").read_text())
    assert state["mission_id"] == "01REGR001TEST000000000000"
    assert state["mission_slug"] == "regression-test-1663"


def test_advance_run_state_preserves_identity_through_final_persist_reconstruction(
    tmp_path: Path,
) -> None:
    """Regression for #1663: the final-persist snapshot reconstruction (site 2)
    in _advance_run_state_after_composition must carry mission_id/mission_slug.

    This covers the Step 4 reconstruction that happens whether or not there was
    an issued_step_id.  Before the fix, both fields were reset to None in the
    persisted state.json.
    """
    from runtime.next._internal_runtime.engine import _read_snapshot
    from runtime.next._internal_runtime.schema import NextDecision
    from runtime.next.runtime_bridge import _advance_run_state_after_composition
    from runtime.next.runtime_bridge_engine import plan_composition_advance

    run_dir = tmp_path / "run2"
    run_dir.mkdir()
    # Provide the frozen template with the exact name _load_frozen_template expects.
    # At least one step is required by load_mission_template_file validation.
    (run_dir / "mission_template_frozen.yaml").write_text(
        "mission:\n  key: software-dev\n  name: Test\n  version: 1.0.0\n"
        "steps:\n  - id: specify\n    title: Specify\n",
        encoding="utf-8",
    )

    # No issued_step_id — skips site-1, exercises site-2 directly.
    _make_snapshot_with_identity(
        run_dir,
        mission_id="01REGR002TEST000000000000",
        mission_slug="regression-test-1663-site2",
        issued_step_id=None,
    )

    run_ref = MissionRunRef(
        run_id="test-run-id-001",
        run_dir=str(run_dir),
        mission_key="software-dev",
        mission_id="01REGR002TEST000000000000",
        mission_slug="regression-test-1663-site2",
    )
    feature_dir = tmp_path / "kitty-specs" / "regression-test-1663-site2"
    feature_dir.mkdir(parents=True)

    with (
        patch(
            "runtime.next._internal_runtime.planner.plan_next",
            return_value=NextDecision(
                kind="step",
                run_id="test-run-id-001",
                mission_key="software-dev",
                step_id="specify",
            ),
        ),
        patch(
            "runtime.next.runtime_bridge_retrospective._resolve_retrospective_policy_for_runtime",
            return_value=(None, {}, None),
        ),
        patch(
            "runtime.next.runtime_bridge._map_runtime_decision",
            return_value=None,
        ),
    ):
        _advance_run_state_after_composition(
            run_ref=run_ref,
            agent="test-agent",
            mission_slug="regression-test-1663-site2",
            mission_type="software-dev",
            repo_root=tmp_path,
            feature_dir=feature_dir,
            timestamp="2026-06-08T00:00:00+00:00",
            progress={},
            origin={},
            sync_emitter=_NullSyncEmitter(),  # type: ignore[arg-type]
            plan=plan_composition_advance(run_ref, "test-agent"),
        )

    persisted = _read_snapshot(run_dir)
    assert persisted.mission_id == "01REGR002TEST000000000000", (
        f"Expected mission_id='01REGR002TEST000000000000' but got {persisted.mission_id!r}; "
        "site-2 final-persist reconstruction dropped identity (#1663)"
    )
    assert persisted.mission_slug == "regression-test-1663-site2", (
        f"Expected mission_slug='regression-test-1663-site2' but got {persisted.mission_slug!r}; "
        "site-2 final-persist reconstruction dropped identity (#1663)"
    )
