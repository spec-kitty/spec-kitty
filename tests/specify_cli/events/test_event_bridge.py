"""The EventBridge port behind the three work package transition doors (#6603).

ADR 2026-10-14-1 D-2 and open question 6: the transition goes through the
port. With no adapter bound, the local file adapter writes what the doors
wrote before. A bound adapter receives every unit, and nothing else writes it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import specify_cli.status.emit as emit_module
from runtime.next.event_bridge import (
    WorkPackageTransition,
    bind_work_package_transition_port,
    bound_work_package_transition_port,
    reset_work_package_transition_port,
)
from specify_cli.coordination.status_service import EventLogWriteContract
from specify_cli.events.event_bridge import LocalFileEventBridge, work_package_transition_port
from specify_cli.status.emit import emit_status_transition, emit_status_transition_batch
from specify_cli.status.models import TransitionRequest
from specify_cli.status.store import EVENTS_FILENAME, read_events
from tests.status.conftest import seed_wp_to_planned
from tests.status.test_mission_write import (
    TXN_COORD_BRANCH,
    TXN_MISSION_ID,
    TXN_SLUG,
    _commit_all,
    _event as _txn_event,
    _git,
    _init_repo,
    _txn,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "bridge-mission"
_REPO_ROOT = Path(__file__).resolve().parents[3]


class _RecordingPort:
    """Records each unit, then persists it through the local file adapter."""

    def __init__(self) -> None:
        self.calls: list[WorkPackageTransition] = []

    def record_work_package_transition(self, transition: WorkPackageTransition) -> None:
        self.calls.append(transition)
        LocalFileEventBridge().record_work_package_transition(transition)


@pytest.fixture(autouse=True)
def _unbound() -> Iterator[None]:
    reset_work_package_transition_port()
    yield
    reset_work_package_transition_port()


@pytest.fixture(autouse=True)
def _no_fan_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(emit_module, "_status_fan_out", lambda *args, **kwargs: None)
    monkeypatch.setattr(emit_module, "_resolved_binding_fan_out", lambda *args, **kwargs: None)


@pytest.fixture
def txn_repo(tmp_path: Path) -> Path:
    """A repository with a coordination branch, as ``test_mission_write.txn_repo`` builds it."""
    repo = tmp_path / "txn-repo"
    mission_dir = _init_repo(repo).parent / TXN_SLUG
    mission_dir.mkdir()
    meta = {"mission_id": TXN_MISSION_ID, "mission_slug": TXN_SLUG, "target_branch": "main", "coordination_branch": TXN_COORD_BRANCH}
    (mission_dir / "meta.json").write_text(json.dumps(meta) + "\n", encoding="utf-8")
    _git(repo, "config", "commit.gpgsign", "false")
    _commit_all(repo, "seed mission")
    _git(repo, "branch", TXN_COORD_BRANCH)
    return repo


@pytest.fixture
def recorder() -> _RecordingPort:
    port = _RecordingPort()
    bind_work_package_transition_port(port)
    return port


@pytest.fixture
def feature_dir(tmp_path: Path) -> Path:
    fd = tmp_path / "kitty-specs" / _SLUG
    (fd / "tasks").mkdir(parents=True)
    (fd / "tasks" / "WP01-slug.md").write_text("---\nwork_package_id: WP01\ntitle: WP01\ndependencies: []\nsubtasks: []\n---\n\n# WP01\n", encoding="utf-8")
    seed_wp_to_planned(fd, "WP01", slug=_SLUG)
    return fd


def _request(feature_dir: Path, to_lane: str, **overrides: Any) -> TransitionRequest:
    fields: dict[str, Any] = {"feature_dir": feature_dir, "mission_slug": _SLUG, "wp_id": "WP01", "to_lane": to_lane, "actor": "agent-1"}
    fields.update(overrides)
    return TransitionRequest(**fields)


# ---------------------------------------------------------------------------
# The three doors
# ---------------------------------------------------------------------------


def test_flat_shell_goes_through_the_port(feature_dir: Path, recorder: _RecordingPort) -> None:
    event = emit_status_transition(_request(feature_dir, "claimed"))
    assert len(recorder.calls) == 1
    unit = recorder.calls[0]
    assert unit.write_location == feature_dir
    assert unit.write_contract is None
    assert unit.rows[0].event_id == event.event_id
    assert read_events(feature_dir)[-1].event_id == event.event_id


def test_batch_door_hands_one_unit_to_the_port(feature_dir: Path, recorder: _RecordingPort) -> None:
    events = emit_status_transition_batch(
        [_request(feature_dir, "claimed"), _request(feature_dir, "in_progress", workspace_context="worktree:/x")],
    )
    assert len(recorder.calls) == 1
    assert [row.event_id for row in recorder.calls[0].rows][: len(events)] == [event.event_id for event in events]


def test_coordination_transaction_goes_through_the_port(txn_repo: Path, recorder: _RecordingPort) -> None:
    txn = _txn(txn_repo)
    with txn:
        txn.append_event(_txn_event("WP01"))
        txn.commit("status: through the port")
    assert len(recorder.calls) == 1
    unit = recorder.calls[0]
    assert isinstance(unit.write_contract, EventLogWriteContract)
    assert unit.write_contract.feature_dir == unit.write_location
    assert unit.write_location.name == TXN_SLUG


def test_unbound_flat_shell_writes_the_same_row(feature_dir: Path) -> None:
    assert bound_work_package_transition_port() is None
    event = emit_status_transition(_request(feature_dir, "claimed"))
    last_line = (feature_dir / EVENTS_FILENAME).read_text(encoding="utf-8").splitlines()[-1]
    assert json.loads(last_line)["event_id"] == event.event_id


# ---------------------------------------------------------------------------
# The local file adapter
# ---------------------------------------------------------------------------


def test_adapter_refuses_a_row_it_cannot_persist(tmp_path: Path) -> None:
    class _Row:
        event_id = "01X"

        def to_dict(self) -> dict[str, Any]:
            return {}

    with pytest.raises(TypeError, match="persists StatusEvent"):
        LocalFileEventBridge().record_work_package_transition(WorkPackageTransition(write_location=tmp_path, rows=(_Row(),)))


def test_adapter_refuses_an_unknown_write_contract(feature_dir: Path) -> None:
    rows = tuple(read_events(feature_dir)[:1])
    with pytest.raises(TypeError, match="unsupported write contract"):
        LocalFileEventBridge().record_work_package_transition(WorkPackageTransition(write_location=feature_dir, rows=rows, write_contract="nope"))


def test_adapter_refuses_a_contract_for_another_location(feature_dir: Path, tmp_path: Path) -> None:
    rows = tuple(read_events(feature_dir)[:1])
    other = EventLogWriteContract.primary_checkout_append(tmp_path / "elsewhere")
    with pytest.raises(ValueError, match="write contract targets"):
        LocalFileEventBridge().record_work_package_transition(WorkPackageTransition(write_location=feature_dir, rows=rows, write_contract=other))


def test_a_transition_needs_a_row(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one row"):
        WorkPackageTransition(write_location=tmp_path, rows=())


# ---------------------------------------------------------------------------
# Binding
# ---------------------------------------------------------------------------


def test_binding_rejects_a_different_adapter() -> None:
    bind_work_package_transition_port(_RecordingPort())
    bind_work_package_transition_port(_RecordingPort())  # same class: rebinds
    with pytest.raises(RuntimeError, match="already bound"):
        bind_work_package_transition_port(LocalFileEventBridge())


def test_bound_port_is_returned(recorder: _RecordingPort) -> None:
    assert work_package_transition_port() is recorder


def test_the_port_leaf_imports_cleanly_into_the_status_shell() -> None:
    """Review finding 1: importing the port must not pull ``_internal_runtime`` (a cycle back into ``status.emit``)."""
    code = "import sys; import specify_cli.status.emit; import runtime.next.event_bridge; print('_internal_runtime.engine' in ' '.join(sys.modules))"
    result = subprocess.run([sys.executable, "-c", code], cwd=_REPO_ROOT, env={"PYTHONPATH": str(_REPO_ROOT / "src")}, capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "False"
