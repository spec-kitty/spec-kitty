"""Client-side shapes of the CLI to write-service protocol (#6675, ADR 2026-10-27-1).

The shapes carry no transport. These tests pin the wire names, the refusal
vocabulary, version negotiation and the fail-closed endpoint-file reader; the
contract tests (``tests/contract/test_mission_write_contract.py``) validate the
same shapes against ``contracts/mission-write``.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from runtime.next.event_bridge import WorkPackageTransition
from specify_cli.coordination.status_service import EventLogWriteContract
from specify_cli.status import write_service_protocol as wsp

pytestmark = [pytest.mark.unit, pytest.mark.fast]

POSIX_ONLY = pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
TOKEN = "q" * 43
INSTANCE_ID = "01M5Z6N54A59R5FVKJRAGZNTVK"
EVENT_ID = "01M5Z7A1B2C3D4E5F6G7H8J9KM"


@dataclass(frozen=True)
class _Row:
    event_id: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"event_id": self.event_id, **self.payload}


def _context() -> wsp.RequestContext:
    return wsp.RequestContext(
        actor="claude",
        checkout=".",
        mission_directory="kitty-specs/demo-01M5Z6N5",
        write_surface=wsp.WriteSurface.CHECKOUT_APPEND,
        destination_ref=None,
    )


def _unit() -> wsp.TransitionUnit:
    return wsp.TransitionUnit(wp_id="WP01", rows=({"event_id": EVENT_ID, "wp_id": "WP01"},), context=_context())


# -- vocabulary -------------------------------------------------------------


def test_every_refusal_code_has_a_status_and_every_reason_a_code() -> None:
    assert set(wsp.REFUSAL_STATUS) == set(wsp.WriteRefusalCode)
    assert all(400 <= status <= 599 for status in wsp.REFUSAL_STATUS.values())
    assert set(wsp.REASON_CODE) == set(wsp.WriteRefusalReason)
    assert set(wsp.WriteRefusalCode) > wsp.PROTOCOL_ONLY_CODES


def test_reason_urns_share_one_prefix_and_name_the_reason() -> None:
    for reason in wsp.WriteRefusalReason:
        assert reason.urn == f"urn:spec-kitty:write-refusal:{reason.value}"


def test_guard_reasons_map_to_the_cli_edge_codes() -> None:
    assert wsp.REASON_CODE[wsp.WriteRefusalReason.DEPENDENCIES_UNSATISFIED] is wsp.WriteRefusalCode.DEPENDENCIES_NOT_SATISFIED
    assert wsp.REASON_CODE[wsp.WriteRefusalReason.CLAIM_HELD_BY_OTHER_ACTOR] is wsp.WriteRefusalCode.WP_ALREADY_CLAIMED
    assert wsp.REASON_CODE[wsp.WriteRefusalReason.ILLEGAL_TRANSITION] is wsp.WriteRefusalCode.TRANSITION_REJECTED


# -- requests ---------------------------------------------------------------


def test_transition_unit_wire_shape_keeps_rows_in_order() -> None:
    rows = ({"event_id": "a"}, {"event_id": "b"})
    wire = wsp.TransitionUnit(wp_id="WP02", rows=rows, context=_context()).to_wire()

    assert wire == {
        "wpId": "WP02",
        "rows": [{"event_id": "a"}, {"event_id": "b"}],
        "context": {
            "actor": "claude",
            "checkout": ".",
            "missionDirectory": "kitty-specs/demo-01M5Z6N5",
            "writeSurface": "checkout_append",
            "destinationRef": None,
        },
    }


def test_transition_unit_refuses_an_empty_unit() -> None:
    with pytest.raises(wsp.ProtocolShapeError):
        wsp.TransitionUnit(wp_id="WP01", rows=(), context=_context())


@pytest.mark.parametrize("count", [0, wsp.MAX_BATCH_UNITS + 1])
def test_transition_batch_refuses_an_empty_or_oversized_batch(count: int) -> None:
    with pytest.raises(wsp.ProtocolShapeError):
        wsp.TransitionBatch(units=tuple(_unit() for _ in range(count)))


def test_transition_batch_and_annotation_wire_shapes() -> None:
    assert wsp.TransitionBatch(units=(_unit(), _unit())).to_wire()["units"] == [_unit().to_wire(), _unit().to_wire()]
    annotation = wsp.AnnotationRequest(wp_id="WP01", row={"event_id": EVENT_ID}, context=_context()).to_wire()
    assert annotation == {"wpId": "WP01", "row": {"event_id": EVENT_ID}, "context": _context().to_wire()}


def test_transition_unit_from_the_port_maps_location_checkout_and_surface(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    checkout = repository_root / ".worktrees" / "demo-lane-a"
    mission_dir = checkout / "kitty-specs" / "demo-01M5Z6N5"
    mission_dir.mkdir(parents=True)
    row = _Row(EVENT_ID, {"wp_id": "WP03", "actor": "claude"})
    transition = WorkPackageTransition(
        write_location=mission_dir,
        rows=(row,),
        write_contract=EventLogWriteContract.coordination_transaction_append(mission_dir),
    )

    unit = wsp.transition_unit_from(transition, checkout=checkout, repository_root=repository_root)

    assert unit.wp_id == "WP03"
    assert unit.rows == ({"event_id": EVENT_ID, "wp_id": "WP03", "actor": "claude"},)
    assert unit.context == wsp.RequestContext(
        actor="claude",
        checkout=".worktrees/demo-lane-a",
        mission_directory="kitty-specs/demo-01M5Z6N5",
        write_surface=wsp.WriteSurface.COORDINATION_TRANSACTION_APPEND,
        destination_ref=None,
    )


def test_transition_unit_from_a_flat_shell_append_is_a_primary_append_at_the_root(tmp_path: Path) -> None:
    mission_dir = tmp_path / "kitty-specs" / "demo"
    mission_dir.mkdir(parents=True)
    transition = WorkPackageTransition(write_location=mission_dir, rows=(_Row(EVENT_ID, {"wp_id": "WP01", "actor": "a"}),))

    unit = wsp.transition_unit_from(transition, checkout=tmp_path, repository_root=tmp_path)

    assert unit.context.checkout == "."
    assert unit.context.write_surface is wsp.WriteSurface.CHECKOUT_APPEND


def test_transition_unit_from_refuses_a_location_outside_the_checkout(tmp_path: Path) -> None:
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "checkout").mkdir()
    transition = WorkPackageTransition(write_location=tmp_path / "elsewhere", rows=(_Row(EVENT_ID, {"wp_id": "WP01", "actor": "a"}),))

    with pytest.raises(wsp.ProtocolShapeError):
        wsp.transition_unit_from(transition, checkout=tmp_path / "checkout", repository_root=tmp_path)


# -- responses --------------------------------------------------------------


def test_durability_acks_read_the_wire_shapes() -> None:
    ack_wire = {"eventIds": [EVENT_ID], "appendedLines": 1, "fsynced": True, "statusCommit": None, "replayed": False}

    ack = wsp.DurabilityAck.from_wire(ack_wire)
    batch = wsp.BatchDurabilityAck.from_wire({"units": [ack_wire, ack_wire], "fsyncs": 1})

    assert ack == wsp.DurabilityAck(event_ids=(EVENT_ID,), appended_lines=1, fsynced=True, status_commit=None, replayed=False)
    assert batch.units == (ack, ack)
    assert batch.fsyncs == 1


def test_handshake_and_health_read_the_wire_shapes() -> None:
    handshake = wsp.Handshake.from_wire({"protocolVersions": [1], "serviceVersion": "4.0.0", "instanceId": INSTANCE_ID, "repositoryId": "a" * 64})
    health = wsp.Health.from_wire({"status": "ready", "instanceId": INSTANCE_ID})

    assert handshake.protocol_versions == (1,)
    assert health.status == "ready"


def test_write_refusal_reads_code_status_and_reason() -> None:
    refusal = wsp.WriteRefusal.from_wire(
        {
            "type": wsp.WriteRefusalReason.ILLEGAL_TRANSITION.urn,
            "title": "Transition rejected",
            "status": 409,
            "code": "TRANSITION_REJECTED",
            "detail": "Illegal transition: planned -> done",
        }
    )

    assert refusal.code is wsp.WriteRefusalCode.TRANSITION_REJECTED
    assert refusal.reason is wsp.WriteRefusalReason.ILLEGAL_TRANSITION
    assert refusal.status == 409


@pytest.mark.parametrize(
    ("shape", "wire"),
    [
        (wsp.DurabilityAck, {"eventIds": [EVENT_ID], "appendedLines": "1", "fsynced": True, "statusCommit": None, "replayed": False}),
        (wsp.DurabilityAck, {"eventIds": [EVENT_ID], "appendedLines": 1, "fsynced": False, "statusCommit": None, "replayed": False}),
        (wsp.Handshake, {"protocolVersions": [], "serviceVersion": "x", "instanceId": INSTANCE_ID, "repositoryId": "a" * 64}),
        (wsp.Health, {"status": "asleep", "instanceId": INSTANCE_ID}),
        (wsp.WriteRefusal, {"title": "t", "status": 409, "code": "NOT_A_CODE"}),
        (wsp.WriteRefusal, {"title": "t", "status": 500, "code": "TRANSITION_REJECTED"}),
    ],
)
def test_response_shapes_refuse_a_wrong_field(shape: Any, wire: dict[str, Any]) -> None:
    with pytest.raises(wsp.ProtocolShapeError):
        shape.from_wire(wire)


def test_negotiation_picks_the_highest_common_major() -> None:
    assert wsp.negotiate_protocol_version((1, 2)) == 1
    with pytest.raises(wsp.ProtocolShapeError):
        wsp.negotiate_protocol_version((2, 3))


def test_repository_id_is_the_digest_of_the_resolved_common_dir(tmp_path: Path) -> None:
    common = tmp_path / "repo" / ".git"
    common.mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(common)

    expected = hashlib.sha256(common.resolve().as_posix().encode("utf-8")).hexdigest()  # noqa: TID251 -- the protocol identity digest, not a charter hash

    assert wsp.repository_id(common) == expected
    assert wsp.repository_id(link) == expected


# -- endpoint file ----------------------------------------------------------


def _endpoint_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "host": "127.0.0.1",
        "port": 48213,
        "token": TOKEN,
        "instance_id": INSTANCE_ID,
        "pid": 4242,
        "protocol_versions": [1],
        "started_at": "2026-10-27T18:00:00Z",
    }
    payload.update(overrides)
    return payload


def _write_endpoint(common_dir: Path, payload: dict[str, Any] | str, *, file_mode: int = 0o600, dir_mode: int = 0o700) -> Path:
    path = wsp.endpoint_file_path(common_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
    path.chmod(file_mode)
    path.parent.chmod(dir_mode)
    return path


def test_endpoint_file_lives_in_the_git_common_dir(tmp_path: Path) -> None:
    assert wsp.endpoint_file_path(tmp_path) == tmp_path / "spec-kitty-write-service" / "endpoint.json"


@POSIX_ONLY
def test_a_well_formed_private_endpoint_file_reads(tmp_path: Path) -> None:
    endpoint = wsp.read_endpoint_file(_write_endpoint(tmp_path, _endpoint_payload()))

    assert (endpoint.host, endpoint.port, endpoint.instance_id) == ("127.0.0.1", 48213, INSTANCE_ID)
    assert endpoint.protocol_versions == (1,)
    assert TOKEN not in repr(endpoint)


def test_a_missing_endpoint_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(wsp.EndpointFileError) as caught:
        wsp.read_endpoint_file(wsp.endpoint_file_path(tmp_path))

    assert caught.value.error_code == wsp.EndpointRefusalCode.MISSING


@POSIX_ONLY
@pytest.mark.parametrize(
    ("payload", "code"),
    [
        pytest.param("{not json", wsp.EndpointRefusalCode.MALFORMED, id="invalid-json"),
        pytest.param("[]", wsp.EndpointRefusalCode.MALFORMED, id="not-an-object"),
        pytest.param(_endpoint_payload(schema_version=2), wsp.EndpointRefusalCode.MALFORMED, id="schema-version"),
        pytest.param(_endpoint_payload(host="0.0.0.0"), wsp.EndpointRefusalCode.NOT_LOOPBACK, id="all-interfaces"),
        pytest.param(_endpoint_payload(host="localhost"), wsp.EndpointRefusalCode.NOT_LOOPBACK, id="hostname"),
        pytest.param(_endpoint_payload(port=0), wsp.EndpointRefusalCode.MALFORMED, id="port-zero"),
        pytest.param(_endpoint_payload(port=70000), wsp.EndpointRefusalCode.MALFORMED, id="port-range"),
        pytest.param(_endpoint_payload(token="short"), wsp.EndpointRefusalCode.MALFORMED, id="short-token"),
        pytest.param(_endpoint_payload(token="q" * 42 + "/"), wsp.EndpointRefusalCode.MALFORMED, id="token-alphabet"),
        pytest.param(_endpoint_payload(protocol_versions=[]), wsp.EndpointRefusalCode.MALFORMED, id="no-versions"),
        pytest.param(_endpoint_payload(instance_id=""), wsp.EndpointRefusalCode.MALFORMED, id="no-instance"),
    ],
)
def test_a_malformed_endpoint_file_is_refused(tmp_path: Path, payload: dict[str, Any] | str, code: wsp.EndpointRefusalCode) -> None:
    with pytest.raises(wsp.EndpointFileError) as caught:
        wsp.read_endpoint_file(_write_endpoint(tmp_path, payload))

    assert caught.value.error_code == code


@POSIX_ONLY
@pytest.mark.parametrize(("file_mode", "dir_mode"), [(0o640, 0o700), (0o604, 0o700), (0o600, 0o750), (0o600, 0o707)])
def test_an_exposed_endpoint_file_is_refused_without_naming_the_token(tmp_path: Path, file_mode: int, dir_mode: int) -> None:
    path = _write_endpoint(tmp_path, _endpoint_payload(), file_mode=file_mode, dir_mode=dir_mode)

    with pytest.raises(wsp.EndpointFileError) as caught:
        wsp.read_endpoint_file(path)

    assert caught.value.error_code == wsp.EndpointRefusalCode.EXPOSED
    assert TOKEN not in str(caught.value)
    assert TOKEN not in json.dumps(caught.value.to_dict())


@POSIX_ONLY
def test_a_symlinked_endpoint_file_is_refused(tmp_path: Path) -> None:
    real = _write_endpoint(tmp_path / "real", _endpoint_payload())
    link = wsp.endpoint_file_path(tmp_path / "linked")
    link.parent.mkdir(parents=True)
    link.parent.chmod(0o700)
    link.symlink_to(real)

    with pytest.raises(wsp.EndpointFileError) as caught:
        wsp.read_endpoint_file(link)

    assert caught.value.error_code == wsp.EndpointRefusalCode.EXPOSED
    assert stat.S_ISLNK(link.lstat().st_mode)


@POSIX_ONLY
def test_no_refusal_message_carries_the_token(tmp_path: Path) -> None:
    path = _write_endpoint(tmp_path, _endpoint_payload(host="10.0.0.1"))

    with pytest.raises(wsp.EndpointFileError) as caught:
        wsp.read_endpoint_file(path)

    assert TOKEN not in str(caught.value)


# -- review cycle 1 (WP02) ----------------------------------------------------


@pytest.mark.parametrize(
    ("shape", "wire"),
    [
        (wsp.DurabilityAck, []),
        (wsp.BatchDurabilityAck, {"units": ["x"], "fsyncs": 1}),
        (wsp.BatchDurabilityAck, {"units": [], "fsyncs": 1}),
        (wsp.Handshake, "handshake"),
        (wsp.Health, None),
        (wsp.WriteRefusal, 409),
        (wsp.DurabilityAck, {"eventIds": [EVENT_ID], "appendedLines": -1, "fsynced": True, "statusCommit": None, "replayed": False}),
        (wsp.Handshake, {"protocolVersions": [2, 1], "serviceVersion": "x", "instanceId": INSTANCE_ID, "repositoryId": "a" * 64}),
        (wsp.Handshake, {"protocolVersions": [1, 1], "serviceVersion": "x", "instanceId": INSTANCE_ID, "repositoryId": "a" * 64}),
    ],
)
def test_response_shapes_refuse_a_non_mapping_or_out_of_range_body(shape: Any, wire: Any) -> None:
    with pytest.raises(wsp.ProtocolShapeError):
        shape.from_wire(wire)


@pytest.mark.parametrize("missing", ["actor", "wp_id"])
def test_transition_unit_from_refuses_a_row_without_actor_or_wp_id(tmp_path: Path, missing: str) -> None:
    payload = {"wp_id": "WP01", "actor": "claude"}
    del payload[missing]
    transition = WorkPackageTransition(write_location=tmp_path, rows=(_Row(EVENT_ID, payload),))

    with pytest.raises(wsp.ProtocolShapeError):
        wsp.transition_unit_from(transition, checkout=tmp_path, repository_root=tmp_path)


@POSIX_ONLY
@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(_endpoint_payload(schema_version=True), id="schema-version-bool"),
        pytest.param(_endpoint_payload(schema_version=1.0), id="schema-version-float"),
        pytest.param(_endpoint_payload(protocol_versions=[2, 1]), id="versions-unsorted"),
        pytest.param(_endpoint_payload(protocol_versions=[1, 1]), id="versions-duplicate"),
    ],
)
def test_an_endpoint_file_with_a_loose_value_is_refused(tmp_path: Path, payload: dict[str, Any]) -> None:
    with pytest.raises(wsp.EndpointFileError) as caught:
        wsp.read_endpoint_file(_write_endpoint(tmp_path, payload))

    assert caught.value.error_code == wsp.EndpointRefusalCode.MALFORMED


@POSIX_ONLY
def test_a_malformed_endpoint_refusal_chains_no_exception_that_holds_the_token(tmp_path: Path) -> None:
    path = _write_endpoint(tmp_path, json.dumps(_endpoint_payload()) + " trailing")

    with pytest.raises(wsp.EndpointFileError) as caught:
        wsp.read_endpoint_file(path)

    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@POSIX_ONLY
def test_an_endpoint_file_that_vanishes_before_it_is_opened_is_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _write_endpoint(tmp_path, _endpoint_payload())

    def _gone(*_: Any, **__: Any) -> int:
        raise FileNotFoundError(str(path))

    monkeypatch.setattr(wsp.os, "open", _gone)
    with pytest.raises(wsp.EndpointFileError) as caught:
        wsp.read_endpoint_file(path)

    assert caught.value.error_code == wsp.EndpointRefusalCode.MISSING


@POSIX_ONLY
def test_an_unreadable_endpoint_file_is_a_named_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _write_endpoint(tmp_path, _endpoint_payload())

    def _denied(*_: Any, **__: Any) -> int:
        raise PermissionError(str(path))

    monkeypatch.setattr(wsp.os, "open", _denied)
    with pytest.raises(wsp.EndpointFileError) as caught:
        wsp.read_endpoint_file(path)

    assert caught.value.error_code == wsp.EndpointRefusalCode.MALFORMED


# -- review cycle 2 (WP02) ----------------------------------------------------


@POSIX_ONLY
def test_a_fifo_at_the_endpoint_path_is_refused_without_blocking(tmp_path: Path) -> None:
    path = wsp.endpoint_file_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.parent.chmod(0o700)
    os.mkfifo(path, 0o600)
    outcome: list[BaseException] = []

    def _read() -> None:
        try:
            wsp.read_endpoint_file(path)
        except BaseException as exc:  # noqa: BLE001 -- the outcome is asserted on the main thread
            outcome.append(exc)

    reader = threading.Thread(target=_read, daemon=True)
    reader.start()
    reader.join(timeout=5)

    assert not reader.is_alive(), "read_endpoint_file blocked on a FIFO"
    assert len(outcome) == 1 and isinstance(outcome[0], wsp.EndpointFileError)
    assert outcome[0].error_code == wsp.EndpointRefusalCode.EXPOSED


@POSIX_ONLY
def test_a_malformed_endpoint_refusal_keeps_no_context_that_holds_the_token(tmp_path: Path) -> None:
    path = _write_endpoint(tmp_path, json.dumps(_endpoint_payload()) + " trailing")

    with pytest.raises(wsp.EndpointFileError) as caught:
        wsp.read_endpoint_file(path)

    assert caught.value.__context__ is None


@POSIX_ONLY
@pytest.mark.parametrize(
    "text",
    [
        pytest.param("[" * 65000, id="deep-nesting"),
        pytest.param('{"port": ' + "9" * 5000 + "}", id="huge-integer"),
    ],
)
def test_pathological_endpoint_content_is_a_named_refusal(tmp_path: Path, text: str) -> None:
    with pytest.raises(wsp.EndpointFileError) as caught:
        wsp.read_endpoint_file(_write_endpoint(tmp_path, text))

    assert caught.value.error_code == wsp.EndpointRefusalCode.MALFORMED


# -- pre-merge squad folds -------------------------------------------------------


def test_a_unit_whose_rows_name_different_work_packages_is_refused(tmp_path: Path) -> None:
    rows = (_Row(EVENT_ID, {"wp_id": "WP01", "actor": "a"}), _Row("01M5Z7A1B2C3D4E5F6G7H8J9KN", {"wp_id": "WP02", "actor": "a"}))
    transition = WorkPackageTransition(write_location=tmp_path, rows=rows)

    with pytest.raises(wsp.ProtocolShapeError):
        wsp.transition_unit_from(transition, checkout=tmp_path, repository_root=tmp_path)


def _ack(*, replayed: bool) -> dict[str, Any]:
    return {"eventIds": [EVENT_ID], "appendedLines": 0 if replayed else 1, "fsynced": True, "statusCommit": None, "replayed": replayed}


def test_a_batch_acknowledgement_syncs_once_unless_every_unit_was_replayed() -> None:
    assert wsp.BatchDurabilityAck.from_wire({"units": [_ack(replayed=True)] * 2, "fsyncs": 0}).fsyncs == 0
    assert wsp.BatchDurabilityAck.from_wire({"units": [_ack(replayed=True), _ack(replayed=False)], "fsyncs": 1}).fsyncs == 1
    with pytest.raises(wsp.ProtocolShapeError):
        wsp.BatchDurabilityAck.from_wire({"units": [_ack(replayed=False)], "fsyncs": 0})
    with pytest.raises(wsp.ProtocolShapeError):
        wsp.BatchDurabilityAck.from_wire({"units": [_ack(replayed=True)], "fsyncs": 1})


def test_a_draining_service_has_its_own_code() -> None:
    assert wsp.REFUSAL_STATUS[wsp.WriteRefusalCode.SERVICE_DRAINING] == 503
    assert wsp.WriteRefusalCode.SERVICE_DRAINING in wsp.PROTOCOL_ONLY_CODES


@dataclass(frozen=True)
class _UnknownContract:
    target: Any


def test_an_unknown_write_target_is_a_shape_error(tmp_path: Path) -> None:
    @dataclass(frozen=True)
    class _Target:
        value: str

    transition = WorkPackageTransition(
        write_location=tmp_path,
        rows=(_Row(EVENT_ID, {"wp_id": "WP01", "actor": "a"}),),
        write_contract=_UnknownContract(target=_Target("somewhere_else")),
    )

    with pytest.raises(wsp.ProtocolShapeError):
        wsp.transition_unit_from(transition, checkout=tmp_path, repository_root=tmp_path)
