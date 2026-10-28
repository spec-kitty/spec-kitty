"""Acceptance and refusal-parity tests of ``contracts/mission-write`` (#6675, ADR 2026-10-27-1).

The module is resolved with the contract resolver (the one resolution authority) and checked
against the operator's protocol rulings: six operations, the bearer scheme on every one, the
protocol header on every one but the handshake, closed success bodies and a ``WriteRefusal`` for
every refusal. Refusal-code parity is checked three ways: the contract, the client shapes
(``specify_cli.status.write_service_protocol``) and the inventory
``tests/contract/fixtures/mission_write_refusal_parity.yaml`` agree, and every code that claims
a CLI origin is found verbatim in the CLI file the inventory cites. The client shapes' serialized
requests and the module's examples validate against the resolved schemas.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

from runtime.next.event_bridge import WorkPackageTransition
from specify_cli.coordination.status_service import EventLogWriteContract
from specify_cli.status import write_service_protocol as wsp
from tests.contract._loader import load_tool

pytestmark = [pytest.mark.contract, pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "contracts" / "tools"
MODULE_DIR = REPO_ROOT / "contracts" / "mission-write"
EXAMPLES_DIR = MODULE_DIR / "examples"
PARITY_FILE = Path(__file__).resolve().parent / "fixtures" / "mission_write_refusal_parity.yaml"

OPERATIONS = {
    ("/handshake", "get"): "handshake",
    ("/health", "get"): "getHealth",
    ("/missions/{missionId}/work-package-transitions", "post"): "recordWorkPackageTransition",
    ("/missions/{missionId}/work-package-transitions/batch", "post"): "recordWorkPackageTransitionBatch",
    ("/missions/{missionId}/inner-state-annotations", "post"): "recordInnerStateAnnotation",
    ("/shutdown", "post"): "shutdown",
}
PROBLEM_MEDIA_TYPE = "application/problem+json"
JSON_MEDIA_TYPE = "application/json"


@pytest.fixture(scope="module")
def tree() -> Iterator[dict[str, Any]]:
    with pytest.MonkeyPatch.context() as mp:
        resolver = load_tool(mp, TOOLS_DIR / "contract_resolver.py", "contract_resolver_mission_write", syspath=TOOLS_DIR)
        yield resolver.resolve(MODULE_DIR).tree


@pytest.fixture(scope="module")
def parity() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(PARITY_FILE.read_text(encoding="utf-8"))
    return loaded


def _operations(tree: Mapping[str, Any]) -> Iterator[tuple[str, str, dict[str, Any]]]:
    for path, item in tree["paths"].items():
        for method, operation in item.items():
            if method in {"get", "post", "put", "patch", "delete"}:
                yield path, method, operation


def _refusal_schema(tree: Mapping[str, Any]) -> dict[str, Any]:
    response = tree["paths"]["/missions/{missionId}/work-package-transitions"]["post"]["responses"]["409"]
    schema: dict[str, Any] = response["content"][PROBLEM_MEDIA_TYPE]["schema"]
    return schema


def _request_schema(tree: Mapping[str, Any], path: str) -> dict[str, Any]:
    schema: dict[str, Any] = tree["paths"][path]["post"]["requestBody"]["content"][JSON_MEDIA_TYPE]["schema"]
    return schema


def _success_schema(tree: Mapping[str, Any], path: str, method: str, status: str) -> dict[str, Any]:
    schema: dict[str, Any] = tree["paths"][path][method]["responses"][status]["content"][JSON_MEDIA_TYPE]["schema"]
    return schema


def _validate(schema: Mapping[str, Any], instance: Any) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=str)
    assert not errors, [error.message for error in errors]


def _example(name: str) -> Any:
    return yaml.safe_load((EXAMPLES_DIR / name).read_text(encoding="utf-8"))


# -- operations and security --------------------------------------------------


def test_the_module_has_exactly_the_six_operations(tree: dict[str, Any]) -> None:
    found = {(path, method): operation["operationId"] for path, method, operation in _operations(tree)}

    assert found == OPERATIONS


def test_every_operation_requires_the_bearer_token(tree: dict[str, Any]) -> None:
    scheme = tree["components"]["securitySchemes"]["writeToken"]

    assert (scheme["type"], scheme["scheme"]) == ("http", "bearer")
    assert tree["security"] == [{"writeToken": []}]
    for path, method, operation in _operations(tree):
        assert "security" not in operation, f"{method} {path} overrides the root security requirement"


UNVERSIONED_OPERATIONS = frozenset({"handshake", "getHealth"})


def test_every_operation_but_handshake_and_health_requires_the_protocol_header(tree: dict[str, Any]) -> None:
    for path, method, operation in _operations(tree):
        headers = [p for p in operation.get("parameters", []) if p["in"] == "header" and p["name"] == wsp.WRITE_PROTOCOL_HEADER]
        if operation["operationId"] in UNVERSIONED_OPERATIONS:
            assert headers == []
        else:
            assert [h["required"] for h in headers] == [True], f"{method} {path}"


def test_every_refusal_is_a_write_refusal_and_every_success_body_is_closed(tree: dict[str, Any]) -> None:
    for path, method, operation in _operations(tree):
        for status, response in operation["responses"].items():
            content = response.get("content")
            if status.startswith("2"):
                if content is not None:
                    assert content[JSON_MEDIA_TYPE]["schema"]["additionalProperties"] is False, f"{method} {path} {status}"
                continue
            assert list(content) == [PROBLEM_MEDIA_TYPE], f"{method} {path} {status}"
            assert content[PROBLEM_MEDIA_TYPE]["schema"]["title"] == "WriteRefusal", f"{method} {path} {status}"
            codes = {code for code, fixed in wsp.REFUSAL_STATUS.items() if fixed == int(status)}
            assert codes, f"{method} {path} declares {status}, which no refusal code fixes"


# -- refusal vocabulary --------------------------------------------------------


def _contract_codes(tree: Mapping[str, Any]) -> list[str]:
    branch = next(
        part for part in _refusal_schema(tree)["allOf"] if "properties" in part and "code" in part.get("properties", {}) and "oneOf" in part["properties"]["code"]
    )
    return [option["const"] for option in branch["properties"]["code"]["oneOf"]]


def _contract_reasons(tree: Mapping[str, Any]) -> list[str]:
    branch = next(part for part in _refusal_schema(tree)["allOf"] if "oneOf" in part.get("properties", {}).get("type", {}))
    return [option["const"] for option in branch["properties"]["type"]["oneOf"]]


def _contract_statuses(tree: Mapping[str, Any]) -> dict[str, int]:
    return {
        part["if"]["properties"]["code"]["const"]: part["then"]["properties"]["status"]["const"]
        for part in _refusal_schema(tree)["allOf"]
        if "code" in part.get("if", {}).get("properties", {})
    }


def test_contract_codes_and_statuses_equal_the_client_vocabulary(tree: dict[str, Any]) -> None:
    codes = _contract_codes(tree)

    assert len(codes) == len(set(codes))
    assert set(codes) == {code.value for code in wsp.WriteRefusalCode}
    assert _contract_statuses(tree) == {code.value: status for code, status in wsp.REFUSAL_STATUS.items()}


def test_contract_reasons_equal_the_client_reason_urns(tree: dict[str, Any]) -> None:
    assert sorted(_contract_reasons(tree)) == sorted(reason.urn for reason in wsp.WriteRefusalReason)


# -- parity inventory ------------------------------------------------------------


def _tracked(path: str) -> bool:
    result = subprocess.run(["git", "ls-files", "--error-unmatch", path], cwd=REPO_ROOT, capture_output=True, check=False)  # noqa: S603, S607 -- fixed argv, git on PATH
    return result.returncode == 0


def parity_violations(inventory: Mapping[str, Any]) -> list[str]:
    """Every way the inventory disagrees with the client vocabulary or its cited CLI sources."""
    violations: list[str] = []
    codes = {row["code"]: row for row in inventory["codes"]}
    if len(codes) != len(inventory["codes"]):
        violations.append("a code is listed twice")
    if set(codes) != {code.value for code in wsp.WriteRefusalCode}:
        violations.append(f"inventory codes differ from WriteRefusalCode: {sorted(set(codes) ^ {c.value for c in wsp.WriteRefusalCode})}")
    for code, row in codes.items():
        if code in wsp.WriteRefusalCode.__members__ and row["status"] != wsp.REFUSAL_STATUS[wsp.WriteRefusalCode(code)]:
            violations.append(f"{code}: inventory status {row['status']} differs from the client's")
        protocol_only = wsp.WriteRefusalCode(code) in wsp.PROTOCOL_ONLY_CODES if code in wsp.WriteRefusalCode.__members__ else None
        if row["origin"] == "protocol":
            if "source" in row or protocol_only is False:
                violations.append(f"{code}: a protocol-only code names a CLI source or is not protocol-only in the client")
            continue
        source = row.get("source", "")
        if row["origin"] != "cli" or protocol_only or not source or not _tracked(source):
            violations.append(f"{code}: a CLI code needs origin cli, a tracked source and no protocol-only mark")
            continue
        text = (REPO_ROOT / source).read_text(encoding="utf-8")
        if f'"{code}"' not in text:
            violations.append(f"{code}: the literal is not in {source}")
    reasons = {row["reason"]: row for row in inventory["reasons"]}
    if set(reasons) != {reason.value for reason in wsp.WriteRefusalReason}:
        violations.append("inventory reasons differ from WriteRefusalReason")
    for reason, row in reasons.items():
        if reason in {r.value for r in wsp.WriteRefusalReason} and row["code"] != wsp.REASON_CODE[wsp.WriteRefusalReason(reason)].value:
            violations.append(f"{reason}: travels under {row['code']} in the inventory but not in the client")
        if not _tracked(row["source"]) or row["source_text"] not in (REPO_ROOT / row["source"]).read_text(encoding="utf-8"):
            violations.append(f"{reason}: {row['source_text']!r} is not in {row['source']}")
    return violations


def test_every_refusal_code_has_a_proven_origin(parity: dict[str, Any], tree: dict[str, Any]) -> None:
    assert parity_violations(parity) == []
    assert [row["code"] for row in parity["codes"]] == _contract_codes(tree)


def test_the_parity_check_catches_a_wrong_source(parity: dict[str, Any]) -> None:
    mutated = {**parity, "codes": [dict(row) for row in parity["codes"]]}
    first_cli = next(row for row in mutated["codes"] if row["origin"] == "cli")
    first_cli["source"] = "src/specify_cli/status/write_service_protocol.py.missing"
    other = next(row for row in mutated["codes"] if row["origin"] == "cli" and row is not first_cli)
    other["source"] = "pyproject.toml"

    violations = parity_violations(mutated)

    assert any(first_cli["code"] in v for v in violations)
    assert any(other["code"] in v and "literal" in v for v in violations)


def test_the_parity_check_catches_a_wrong_reason_text(parity: dict[str, Any]) -> None:
    mutated = {**parity, "reasons": [dict(row) for row in parity["reasons"]]}
    mutated["reasons"][0]["source_text"] = "a text the CLI never raises"

    assert any(mutated["reasons"][0]["reason"] in v for v in parity_violations(mutated))


# -- client shapes against the contract -----------------------------------------


@dataclass(frozen=True)
class _Row:
    payload: dict[str, Any]

    @property
    def event_id(self) -> str:
        return str(self.payload["event_id"])

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)


def _unit_from_the_port(tmp_path: Path) -> wsp.TransitionUnit:
    checkout = tmp_path / ".worktrees" / "demo-01M5Z6N5-coord"
    mission_dir = checkout / "kitty-specs" / "demo-01M5Z6N5"
    mission_dir.mkdir(parents=True)
    row = _example("TransitionUnit.claim.yaml")["rows"][0]
    transition = WorkPackageTransition(
        write_location=mission_dir,
        rows=(_Row(row),),
        write_contract=EventLogWriteContract.coordination_transaction_append(mission_dir),
    )
    return wsp.transition_unit_from(transition, checkout=checkout, repository_root=tmp_path)


def test_requests_the_client_builds_validate_against_the_contract(tree: dict[str, Any], tmp_path: Path) -> None:
    unit = _unit_from_the_port(tmp_path)
    annotation = wsp.AnnotationRequest(wp_id="WP01", row=_example("AnnotationRequest.note.yaml")["row"], context=unit.context)

    _validate(_request_schema(tree, "/missions/{missionId}/work-package-transitions"), unit.to_wire())
    _validate(_request_schema(tree, "/missions/{missionId}/work-package-transitions/batch"), wsp.TransitionBatch(units=(unit, unit)).to_wire())
    _validate(_request_schema(tree, "/missions/{missionId}/inner-state-annotations"), annotation.to_wire())


@pytest.mark.parametrize(
    ("path", "method", "status", "example", "shape"),
    [
        ("/missions/{missionId}/work-package-transitions", "post", "201", "DurabilityAck.appended.yaml", wsp.DurabilityAck),
        ("/missions/{missionId}/work-package-transitions", "post", "201", "DurabilityAck.replayed.yaml", wsp.DurabilityAck),
        ("/missions/{missionId}/work-package-transitions/batch", "post", "201", "BatchDurabilityAck.two-units.yaml", wsp.BatchDurabilityAck),
        ("/handshake", "get", "200", "Handshake.example.yaml", wsp.Handshake),
        ("/health", "get", "200", "Health.ready.yaml", wsp.Health),
    ],
)
def test_success_examples_validate_and_the_client_reads_them(tree: dict[str, Any], path: str, method: str, status: str, example: str, shape: Any) -> None:
    body = _example(example)

    _validate(_success_schema(tree, path, method, status), body)
    shape.from_wire(body)


@pytest.mark.parametrize("example", sorted(p.name for p in EXAMPLES_DIR.glob("WriteRefusal.*.yaml")))
def test_refusal_examples_validate_and_the_client_reads_them(tree: dict[str, Any], example: str) -> None:
    body = _example(example)

    _validate(_refusal_schema(tree), body)
    refusal = wsp.WriteRefusal.from_wire(body)
    assert (refusal.reason is not None) == ("type" in body)


def test_a_refusal_with_the_wrong_status_for_its_code_is_invalid(tree: dict[str, Any]) -> None:
    body = {"title": "Transition rejected", "status": 422, "code": "TRANSITION_REJECTED"}

    assert list(Draft202012Validator(_refusal_schema(tree)).iter_errors(body))


def test_an_empty_unit_and_an_oversized_batch_are_invalid(tree: dict[str, Any]) -> None:
    unit = _example("TransitionUnit.claim.yaml")
    empty = {**unit, "rows": []}
    oversized = {"units": [unit] * (wsp.MAX_BATCH_UNITS + 1)}

    assert list(Draft202012Validator(_request_schema(tree, "/missions/{missionId}/work-package-transitions")).iter_errors(empty))
    assert list(Draft202012Validator(_request_schema(tree, "/missions/{missionId}/work-package-transitions/batch")).iter_errors(oversized))


def test_the_module_keeps_its_hands_off_the_events_envelope(tree: dict[str, Any]) -> None:
    row = _request_schema(tree, "/missions/{missionId}/work-package-transitions")["properties"]["rows"]["items"]

    assert row["required"] == ["event_id"]
    assert list(row["properties"]) == ["event_id"]
    assert row["additionalProperties"] is True
    assert "spec-kitty-events#92" in row["description"]


def test_the_split_root_reads_without_the_resolver() -> None:
    # A consumer with only PyYAML can read the split root and see the six path keys.
    root: dict[str, Any] = yaml.safe_load((MODULE_DIR / "openapi.yaml").read_text(encoding="utf-8"))

    assert {path for path, _ in OPERATIONS} == set(root["paths"])
    assert root["info"]["version"] == "1.0.0-SNAPSHOT"


# -- pre-merge squad folds -------------------------------------------------------


def _context_schema(tree: Mapping[str, Any]) -> dict[str, Any]:
    schema: dict[str, Any] = _request_schema(tree, "/missions/{missionId}/work-package-transitions")["properties"]["context"]
    return schema


def test_the_write_surface_wire_values_name_no_retired_alias(tree: dict[str, Any]) -> None:
    values = _context_schema(tree)["properties"]["writeSurface"]["enum"]

    assert values == [surface.value for surface in wsp.WriteSurface] == ["checkout_append", "coordination_transaction_append"]


@pytest.mark.parametrize("field", ["checkout", "missionDirectory"])
@pytest.mark.parametrize("value", ["..", "../x", "a/../b", "/abs", "C:/x", "a\\b", ""])
def test_request_paths_refuse_escapes_and_host_paths(tree: dict[str, Any], field: str, value: str) -> None:
    context = {**_example("TransitionUnit.claim.yaml")["context"], field: value}

    assert list(Draft202012Validator(_context_schema(tree)).iter_errors(context)), f"{field}={value!r} was accepted"


@pytest.mark.parametrize("value", [".", "kitty-specs/demo-01M5Z6N5", ".worktrees/demo-01M5Z6N5-lane-a"])
def test_request_paths_accept_relative_forward_slash_paths(tree: dict[str, Any], value: str) -> None:
    context = {**_example("TransitionUnit.claim.yaml")["context"], "checkout": value}

    _validate(_context_schema(tree), context)


def test_a_reason_travels_only_under_its_own_code(tree: dict[str, Any]) -> None:
    mismatched = {"type": wsp.WriteRefusalReason.DEPENDENCIES_UNSATISFIED.urn, "title": "t", "status": 409, "code": "TRANSITION_REJECTED"}
    matched = {**mismatched, "code": "DEPENDENCIES_NOT_SATISFIED"}

    assert list(Draft202012Validator(_refusal_schema(tree)).iter_errors(mismatched))
    _validate(_refusal_schema(tree), matched)


def test_a_fully_replayed_batch_acknowledges_zero_fsyncs(tree: dict[str, Any]) -> None:
    replayed = _example("DurabilityAck.replayed.yaml")
    body = {"units": [replayed, replayed], "fsyncs": 0}

    _validate(_success_schema(tree, "/missions/{missionId}/work-package-transitions/batch", "post", "201"), body)
    assert wsp.BatchDurabilityAck.from_wire(body).fsyncs == 0


def test_the_unauthorized_answer_declares_its_challenge(tree: dict[str, Any]) -> None:
    response = tree["paths"]["/missions/{missionId}/work-package-transitions"]["post"]["responses"]["401"]

    assert "WWW-Authenticate" in response["headers"]


def test_a_busy_answer_declares_retry_after(tree: dict[str, Any]) -> None:
    response = tree["paths"]["/missions/{missionId}/work-package-transitions"]["post"]["responses"]["503"]

    assert "Retry-After" in response["headers"]


def test_every_reason_branch_binds_the_code_the_client_binds(tree: dict[str, Any]) -> None:
    bound = {
        part["if"]["properties"]["type"]["const"]: part["then"]["properties"]["code"]["const"]
        for part in _refusal_schema(tree)["allOf"]
        if "type" in part.get("if", {}).get("properties", {})
    }

    assert bound == {reason.urn: code.value for reason, code in wsp.REASON_CODE.items()}


def test_the_row_encoding_is_the_clis_one_encoder(tree: dict[str, Any]) -> None:
    # ADR 2026-10-22-1 D-7: the service writes the bytes store.serialize_event_line writes,
    # sanitize_event_for_log first (it strips host and developer fields), then sorted keys.
    description = _request_schema(tree, "/missions/{missionId}/work-package-transitions")["description"]

    assert "serialize_event_line" in description
    assert "sanitize_event_for_log" in description
