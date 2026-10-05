"""Every example of the ``mission-status`` contract validates against the schema that carries it.

Convention (WP01 README): a schema file lists its examples under ``examples:``; an entry may
be a lone ``$ref`` to a file under ``examples/``, which then holds the bare instance. The
examples are enumerated from a directory listing (no names are hard-coded) and each one is
validated twice, through two independent readings of the split files:

* the resolver path: ``contract_resolver.resolve`` dereferences the module, the schema is
  found in that tree by its ``title`` and ``jsonschema`` validates against the plain tree;
* the library path: ``jsonschema`` with a ``referencing.Registry`` whose retriever reads the
  split files itself.

Both use ``schema_formats.FORMAT_CHECKER``, so ``date-time`` has one verdict whether or not
``rfc3339-validator`` is importable (plan D-P14). A malformed ``date-time`` example is planted
at run time in a temporary copy of the module (never committed) and must be rejected through
both paths: that proves the validation is not vacuous (FR-025, C-010).
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from tests.contract._loader import load_tool

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = REPO_ROOT / "contracts"
MODULE = CONTRACTS / "mission-status"
TOOLS = CONTRACTS / "tools"
MIN_EXAMPLES = 47
PLANTED_FILE = "Planted.malformed.yaml"
PLANTED_SCHEMA = "MissionOverview"
MALFORMED_TIMESTAMP = "2026-13-45T25:61:00Z"


# The tools are loaded at import time (the verdicts parametrise on them), so the module owns one
# MonkeyPatch for its sys.modules entries and a module-scoped fixture undoes it at teardown.
_MP = pytest.MonkeyPatch()


@pytest.fixture(scope="module", autouse=True)
def _undo_tool_registration() -> Iterator[None]:
    yield
    _MP.undo()


def _load_tool(name: str) -> ModuleType:
    return load_tool(_MP, TOOLS / f"{name}.py", f"{name}_under_test")


resolver = _load_tool("contract_resolver")
schema_formats = _load_tool("schema_formats")
leak_patterns = _load_tool("leak_patterns")
leak_scan = load_tool(_MP, TOOLS / "leak_scan.py", "leak_scan_under_test", syspath=TOOLS)


def _read(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _example_refs(module: Path) -> dict[str, str]:
    """Map each example file name to the schema file stem that lists it under ``examples:``."""
    owners: dict[str, str] = {}
    for schema_file in sorted((module / "schemas").glob("*.yaml")):
        document = _read(schema_file)
        entries = document.get("examples", []) if isinstance(document, dict) else []
        for entry in entries:
            ref = entry.get("$ref") if isinstance(entry, dict) and set(entry) == {"$ref"} else None
            if isinstance(ref, str) and ref.startswith("../examples/"):
                owners[ref.removeprefix("../examples/")] = schema_file.stem
    return owners


def _example_files(module: Path) -> list[str]:
    return sorted(p.name for p in (module / "examples").glob("*.yaml") if p.name != "_index.yaml")


def _find_schema(node: Any, title: str) -> dict[str, Any] | None:
    if isinstance(node, dict):
        if node.get("title") == title and "type" in node:
            return node
        for value in node.values():
            found = _find_schema(value, title)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_schema(item, title)
            if found is not None:
                return found
    return None


def _errors(validator: Draft202012Validator, instance: Any) -> list[str]:
    return sorted(error.message for error in validator.iter_errors(instance))


def _resolver_errors(module: Path, schema_title: str, instance: Any) -> list[str]:
    tree = resolver.resolve(module).tree
    schema = _find_schema(tree.get("paths"), schema_title)
    assert schema is not None, f"schema {schema_title!r} is not reachable from any path of {module.name}"
    return _errors(Draft202012Validator(schema, format_checker=schema_formats.FORMAT_CHECKER), instance)


def _library_registry(module: Path) -> Registry:
    """Every YAML file of the module and its ``_shared`` sibling, registered under its own file URI."""
    resources = [
        (path.resolve().as_uri(), Resource.from_contents(_read(path), default_specification=DRAFT202012))
        for base in (module, module.parent / "_shared")
        for path in sorted(base.rglob("*.yaml"))
    ]
    return Registry().with_resources(resources)


def _library_errors(module: Path, schema_title: str, instance: Any) -> list[str]:
    target = (module / "schemas" / f"{schema_title}.yaml").resolve().as_uri()
    validator = Draft202012Validator({"$ref": target}, registry=_library_registry(module), format_checker=schema_formats.FORMAT_CHECKER)
    return _errors(validator, instance)


def _plant(tmp_path: Path) -> Path:
    """A temporary copy of the module (and ``_shared``) with one malformed ``date-time`` example added."""
    root = tmp_path / "contracts"
    shutil.copytree(MODULE, root / MODULE.name)
    shutil.copytree(CONTRACTS / "_shared", root / "_shared")
    module = root / MODULE.name
    owners = _example_refs(module)
    donor = next(name for name, stem in sorted(owners.items()) if stem == PLANTED_SCHEMA)
    instance = _read(module / "examples" / donor)
    instance["createdAt"] = MALFORMED_TIMESTAMP
    (module / "examples" / PLANTED_FILE).write_text(yaml.safe_dump(instance), encoding="utf-8")
    return module


def test_the_module_exists() -> None:
    assert (MODULE / "openapi.yaml").is_file(), f"{MODULE} has no root openapi.yaml"


def test_every_example_validates_through_both_paths() -> None:
    owners = _example_refs(MODULE)
    files = _example_files(MODULE)
    assert len(files) >= MIN_EXAMPLES, f"only {len(files)} examples found, the floor is {MIN_EXAMPLES}"
    orphans = sorted(set(files) - set(owners))
    assert not orphans, f"examples no schema lists under examples:: {orphans}"
    ghosts = sorted(set(owners) - set(files))
    assert not ghosts, f"schemas list examples that do not exist: {ghosts}"
    failures: list[str] = []
    checked = 0
    for name in files:
        instance = _read(MODULE / "examples" / name)
        for label, errors in (
            ("resolver", _resolver_errors(MODULE, owners[name], instance)),
            ("library", _library_errors(MODULE, owners[name], instance)),
        ):
            checked += 1
            failures.extend(f"{name} [{label}] against {owners[name]}: {message}" for message in errors)
    assert checked == 2 * len(files)
    assert not failures, "\n".join(failures)


def test_examples_carry_no_host_path_or_email() -> None:
    findings: list[str] = []
    for name in _example_files(MODULE):
        text = (MODULE / "examples" / name).read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for code in leak_patterns.leak_codes(line, leak_patterns.HUMAN):
                findings.append(f"{name}:{line_number}: {code}")
    assert not findings, "\n".join(findings)


def test_format_policy_is_the_explicit_date_time_checker() -> None:
    assert set(schema_formats.FORMAT_CHECKER.checkers) == {"date-time"}


def test_a_planted_malformed_date_time_is_rejected_through_both_paths(tmp_path: Path) -> None:
    module = _plant(tmp_path)
    instance = _read(module / "examples" / PLANTED_FILE)
    assert instance["createdAt"] == MALFORMED_TIMESTAMP
    resolver_errors = _resolver_errors(module, PLANTED_SCHEMA, instance)
    library_errors = _library_errors(module, PLANTED_SCHEMA, instance)
    assert resolver_errors, "the resolver path accepted a malformed date-time"
    assert library_errors, "the library path accepted a malformed date-time"
    assert any("date-time" in message for message in resolver_errors), resolver_errors
    assert any("date-time" in message for message in library_errors), library_errors


def test_the_planted_example_is_what_the_orphan_check_would_catch(tmp_path: Path) -> None:
    module = _plant(tmp_path)
    assert PLANTED_FILE in set(_example_files(module)) - set(_example_refs(module))


# --------------------------------------------------------------------------------------
# WP04: Mission detail and work package resources (FR-005, FR-006, FR-009, FR-013)
# --------------------------------------------------------------------------------------

DETAIL_SCHEMA = "MissionDetail"
WORK_PACKAGE_SCHEMA = "WorkPackage"
MIN_DETAIL_EXAMPLES = 1
MIN_WORK_PACKAGE_EXAMPLES = 8
PHASE_COUNT = 5
PHASE_BASES = {"artifact", "lifecycle_event", "derived_from_status_lanes"}
MIN_PATH_PARAMETERS = 3
MIN_MISSION_ID_PARAMETERS = 2
ULID_PATTERN = "^[0-9A-HJKMNP-TV-Z]{26}$"
PAGE_CURSOR_FILE = "_shared/schemas/PageCursor.yaml"
STREAM_CURSOR_FILE = "mission-status/schemas/StreamCursor.yaml"
FORBIDDEN_PROPERTY = "prompt" + "Path"


def _instances_of(schema: str) -> dict[str, dict[str, Any]]:
    """Every example instance the module attaches to ``schema``, by file name."""
    return {name: _read(MODULE / "examples" / name) for name, stem in sorted(_example_refs(MODULE).items()) if stem == schema}


def _both_paths(module: Path, schema: str, instance: Any) -> tuple[list[str], list[str]]:
    return _resolver_errors(module, schema, instance), _library_errors(module, schema, instance)


def _first(instances: dict[str, dict[str, Any]], predicate: Any) -> tuple[str, dict[str, Any]]:
    for name, instance in instances.items():
        if predicate(instance):
            return name, instance
    raise AssertionError(f"no example satisfies {getattr(predicate, '__name__', 'the predicate')}; found {sorted(instances)}")


def _all_handles_null(actor: Any) -> bool:
    return isinstance(actor, dict) and set(actor) == {"tool", "role", "profile"} and all(value is None for value in actor.values())


def test_the_new_resources_have_examples_in_the_required_cases() -> None:
    details = _instances_of(DETAIL_SCHEMA)
    packages = _instances_of(WORK_PACKAGE_SCHEMA)
    assert len(details) >= MIN_DETAIL_EXAMPLES, f"found {len(details)} {DETAIL_SCHEMA} examples: {sorted(details)}"
    assert len(packages) >= MIN_WORK_PACKAGE_EXAMPLES, f"found {len(packages)} {WORK_PACKAGE_SCHEMA} examples: {sorted(packages)}"
    for name, detail in details.items():
        assert len(detail["phases"]) == PHASE_COUNT, f"{name}: {len(detail['phases'])} phases"
    bases = {phase["basis"] for detail in details.values() for phase in detail["phases"]}
    assert bases == PHASE_BASES, f"the detail examples cover the bases {sorted(bases)}"
    _first(packages, lambda wp: "promptMarkdown" not in wp)
    _first(packages, lambda wp: isinstance(wp.get("promptMarkdown"), str) and wp["promptMarkdown"] != "")
    _first(packages, lambda wp: wp.get("staleness") is not None)
    _first(packages, lambda wp: wp["statusLane"] is None)
    _first(packages, lambda wp: _all_handles_null(wp["actor"]))
    _first(packages, lambda wp: wp["actor"]["tool"] is not None and wp["actor"]["role"] is None and wp["actor"]["profile"] is None)
    _first(packages, lambda wp: all(value is not None for value in wp["actor"].values()))
    _first(packages, lambda wp: wp["cancellation"] is not None)
    _first(packages, lambda wp: wp["review"]["override"] is not None and wp["review"]["override"]["complete"] is True)
    _first(packages, lambda wp: wp["review"]["override"] is not None and wp["review"]["override"]["complete"] is False)
    _first(packages, lambda wp: wp["review"]["latestResult"] is not None)
    _first(packages, lambda wp: len(wp["history"]) > 0)


def test_a_phase_entry_without_a_basis_is_rejected_through_both_paths() -> None:
    name, detail = next(iter(_instances_of(DETAIL_SCHEMA).items()))
    assert not any(_both_paths(MODULE, DETAIL_SCHEMA, detail)), f"{name} is not a clean control"
    del detail["phases"][0]["basis"]
    resolver_errors, library_errors = _both_paths(MODULE, DETAIL_SCHEMA, detail)
    assert any("basis" in message for message in resolver_errors), resolver_errors
    assert any("basis" in message for message in library_errors), library_errors


@pytest.mark.parametrize("phase_name", ["implement", "review"])
def test_an_implement_or_review_phase_claiming_an_artifact_basis_is_rejected(phase_name: str) -> None:
    _, detail = next(iter(_instances_of(DETAIL_SCHEMA).items()))
    entry = next(phase for phase in detail["phases"] if phase["name"] == phase_name)
    assert entry["basis"] == "derived_from_status_lanes"
    entry["basis"] = "artifact"
    resolver_errors, library_errors = _both_paths(MODULE, DETAIL_SCHEMA, detail)
    assert resolver_errors, f"the resolver path accepted a {phase_name} phase with an artifact basis"
    assert library_errors, f"the library path accepted a {phase_name} phase with an artifact basis"


def test_a_specify_phase_claiming_a_lane_derived_basis_is_rejected() -> None:
    _, detail = next(iter(_instances_of(DETAIL_SCHEMA).items()))
    entry = next(phase for phase in detail["phases"] if phase["name"] == "specify")
    entry["basis"] = "derived_from_status_lanes"
    assert any(_both_paths(MODULE, DETAIL_SCHEMA, detail))


def test_a_history_entry_with_a_kind_other_than_transition_is_rejected() -> None:
    packages = _instances_of(WORK_PACKAGE_SCHEMA)
    name, package = _first(packages, lambda wp: len(wp["history"]) > 0)
    assert all(entry["kind"] == "transition" for entry in package["history"]), f"{name} is not a clean control"
    assert not any(_both_paths(MODULE, WORK_PACKAGE_SCHEMA, package))
    package["history"][0]["kind"] = "annotation"
    resolver_errors, library_errors = _both_paths(MODULE, WORK_PACKAGE_SCHEMA, package)
    assert resolver_errors, "the resolver path accepted a history entry of kind annotation"
    assert library_errors, "the library path accepted a history entry of kind annotation"


def test_a_work_package_carrying_a_path_property_is_rejected() -> None:
    _, package = next(iter(_instances_of(WORK_PACKAGE_SCHEMA).items()))
    assert not any(_both_paths(MODULE, WORK_PACKAGE_SCHEMA, package))
    package[FORBIDDEN_PROPERTY] = "tasks/WP01-example.md"
    resolver_errors, library_errors = _both_paths(MODULE, WORK_PACKAGE_SCHEMA, package)
    assert any(FORBIDDEN_PROPERTY in message for message in resolver_errors), resolver_errors
    assert any(FORBIDDEN_PROPERTY in message for message in library_errors), library_errors


def test_a_work_package_with_a_stale_frontmatter_key_is_rejected() -> None:
    _, package = next(iter(_instances_of(WORK_PACKAGE_SCHEMA).items()))
    for key in ("agent", "shell_pid", "lane", "assignee", "review_status"):
        planted = {**package, key: "x"}
        assert any(_both_paths(MODULE, WORK_PACKAGE_SCHEMA, planted)), f"a stale frontmatter key {key!r} was accepted"


# FR-009: the two cursors never share a reference, and path parameters select a Mission by ULID only.


def _ref_closure(contracts: Path, start: str) -> set[str]:
    """The files reachable from ``start`` by following ``$ref`` values, ``start`` included."""
    seen: set[str] = set()
    pending = [(contracts / start).resolve()]
    root = contracts.resolve()
    while pending:
        current = pending.pop()
        key = current.relative_to(root).as_posix()
        if key in seen:
            continue
        seen.add(key)
        stack: list[Any] = [_read(current)]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                ref = node.get("$ref")
                if isinstance(ref, str) and ref.partition("#")[0]:
                    pending.append((current.parent / ref.partition("#")[0]).resolve())
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    return seen


def _cursor_overlap(contracts: Path) -> tuple[set[str], int, int]:
    page = _ref_closure(contracts, PAGE_CURSOR_FILE)
    stream = _ref_closure(contracts, STREAM_CURSOR_FILE)
    return page & stream, len(page), len(stream)


def test_page_cursor_and_stream_cursor_closures_are_disjoint() -> None:
    shared, page_size, stream_size = _cursor_overlap(CONTRACTS)
    assert page_size >= 1 and stream_size >= 1, f"closure sizes {page_size} and {stream_size}"
    assert not shared, f"the page cursor and the stream cursor both reach {sorted(shared)}"


def test_a_planted_shared_reference_makes_the_cursor_closures_overlap(tmp_path: Path) -> None:
    contracts = tmp_path / "contracts"
    shutil.copytree(MODULE, contracts / MODULE.name)
    shutil.copytree(CONTRACTS / "_shared", contracts / "_shared")
    stream_file = contracts / STREAM_CURSOR_FILE
    document = _read(stream_file)
    document["properties"]["offset"] = {"$ref": "../../_shared/schemas/PageCursor.yaml"}
    stream_file.write_text(yaml.safe_dump(document), encoding="utf-8")
    shared, _, _ = _cursor_overlap(contracts)
    assert PAGE_CURSOR_FILE in shared


def _path_parameters(node: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if node.get("in") == "path" and "name" in node:
            found.append(node)
        for value in node.values():
            found.extend(_path_parameters(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_path_parameters(item))
    return found


def _identity_findings(module: Path) -> tuple[list[str], int, int]:
    parameters = _path_parameters(resolver.resolve(module).tree.get("paths"))
    findings: list[str] = []
    mission_ids = 0
    for parameter in parameters:
        name = parameter["name"]
        if name == "displayNumber":
            findings.append("a path parameter is named displayNumber")
        if name == "missionId":
            mission_ids += 1
            if parameter.get("schema", {}).get("pattern") != ULID_PATTERN:
                findings.append("a missionId path parameter does not carry the ULID pattern")
    return findings, len(parameters), mission_ids


def test_mission_id_path_parameters_carry_the_ulid_pattern_and_no_display_number_parameter() -> None:
    findings, total, mission_ids = _identity_findings(MODULE)
    assert total >= MIN_PATH_PARAMETERS, f"found {total} path parameters, the floor is {MIN_PATH_PARAMETERS}"
    assert mission_ids >= MIN_MISSION_ID_PARAMETERS, f"found {mission_ids} missionId path parameters"
    assert not findings, findings


def test_planted_identity_violations_are_found(tmp_path: Path) -> None:
    root = tmp_path / "contracts"
    shutil.copytree(MODULE, root / MODULE.name)
    shutil.copytree(CONTRACTS / "_shared", root / "_shared")
    module = root / MODULE.name
    assert not _identity_findings(module)[0]
    parameter_file = next(path for path in sorted((module / "parameters").glob("*.yaml")) if {"name": "missionId", "in": "path"}.items() <= _read(path).items())
    document = _read(parameter_file)
    document["schema"] = {"type": "string"}
    parameter_file.write_text(yaml.safe_dump(document), encoding="utf-8")
    assert any("ULID" in finding for finding in _identity_findings(module)[0])
    parameter_file.write_text(yaml.safe_dump({**document, "name": "displayNumber"}), encoding="utf-8")
    assert any("displayNumber" in finding for finding in _identity_findings(module)[0])


# --------------------------------------------------------------------------------------
# WP05: the event stream resource (FR-007, FR-009, FR-013)
# --------------------------------------------------------------------------------------

EVENT_SCHEMAS = {
    "status-transition": "StatusTransitionEvent",
    "mission-lifecycle": "MissionLifecycleEvent",
    "log-truncated": "LogTruncatedEvent",
}
REFUSAL_SCHEMA = "StreamRefusal"
CURSOR_STRING_SCHEMA = "StreamCursorString"
REFUSAL_CODES = {"negative", "out_of_range", "misaligned", "content_mismatch", "cursor_without_mission"}
LIFECYCLE_TYPES = {
    "MissionCreated",
    "SpecifyStarted",
    "SpecifyCompleted",
    "PlanStarted",
    "PlanCompleted",
    "TasksStarted",
    "TasksCompleted",
}
TRUNCATION_REASONS = {"size_shrink", "content_mismatch"}
EMPTY_DIGEST = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
EVENTS_PATH = "/events"
EXPECTED_PATH_KEYS = {
    "/project",
    "/missions",
    "/missions/{missionId}",
    "/missions/{missionId}/work-packages/{wpId}",
    "/missions/{missionId}/artifacts",
    "/missions/{missionId}/artifacts/content",
    "/missions/{missionId}/work-packages/{wpId}/detail",
    EVENTS_PATH,
}


def _first_of(schema: str) -> dict[str, Any]:
    instances = _instances_of(schema)
    assert instances, f"no examples are attached to {schema}"
    return next(iter(instances.values()))


def test_every_event_kind_and_every_refusal_has_a_validating_example() -> None:
    for kind, schema in EVENT_SCHEMAS.items():
        instances = _instances_of(schema)
        assert instances, f"no example for the {kind} event ({schema})"
        for name, instance in instances.items():
            assert not any(_both_paths(MODULE, schema, instance)), f"{name} does not validate against {schema}"
    refusals = _instances_of(REFUSAL_SCHEMA)
    assert {instance["code"] for instance in refusals.values()} == REFUSAL_CODES, sorted(refusals)
    for name, instance in refusals.items():
        assert not any(_both_paths(MODULE, REFUSAL_SCHEMA, instance)), f"{name} does not validate against {REFUSAL_SCHEMA}"


def test_the_event_examples_cover_the_interesting_cases() -> None:
    transitions = _instances_of("StatusTransitionEvent")
    _first(transitions, lambda event: event["fromStatusLane"] is None)
    _first(transitions, lambda event: event["fromStatusLane"] is not None)
    _first(transitions, lambda event: event["force"] is True)
    lifecycle = _instances_of("MissionLifecycleEvent")
    assert len({event["eventType"] for event in lifecycle.values()}) >= 2, sorted(lifecycle)
    truncated = _instances_of("LogTruncatedEvent")
    assert {event["reason"] for event in truncated.values()} == TRUNCATION_REASONS, sorted(truncated)


@pytest.mark.parametrize("kind", sorted(EVENT_SCHEMAS))
def test_an_event_with_a_property_outside_its_schema_is_rejected(kind: str) -> None:
    schema = EVENT_SCHEMAS[kind]
    event = _first_of(schema)
    assert not any(_both_paths(MODULE, schema, event)), f"the {schema} control is not clean"
    for extra in ("payload", "aggregateId", "reason" if kind != "log-truncated" else "note"):
        planted = {**event, extra: "x"}
        resolver_errors, library_errors = _both_paths(MODULE, schema, planted)
        assert any(extra in message for message in resolver_errors), (extra, resolver_errors)
        assert any(extra in message for message in library_errors), (extra, library_errors)


@pytest.mark.parametrize("schema", sorted(EVENT_SCHEMAS.values()))
def test_an_event_without_its_cursor_or_mission_is_rejected(schema: str) -> None:
    for required in ("streamCursor", "missionId"):
        event = {key: value for key, value in _first_of(schema).items() if key != required}
        assert any(_both_paths(MODULE, schema, event)), f"a {schema} without {required} was accepted"


def test_a_log_truncated_event_with_another_reason_is_rejected() -> None:
    event = _first_of("LogTruncatedEvent")
    for reason in ("rotated", "size_growth", "", None):
        planted = {**event, "reason": reason}
        resolver_errors, library_errors = _both_paths(MODULE, "LogTruncatedEvent", planted)
        assert resolver_errors and library_errors, f"reason {reason!r} was accepted"


def test_a_log_truncated_event_resets_the_cursor_to_offset_zero_with_the_empty_digest() -> None:
    for name, event in _instances_of("LogTruncatedEvent").items():
        assert event["streamCursor"] == {"offset": 0, "invariant": EMPTY_DIGEST}, name
    event = _first_of("LogTruncatedEvent")
    for cursor in ({"offset": 40, "invariant": EMPTY_DIGEST}, {"offset": 0, "invariant": "a" * 64}):
        planted = {**event, "streamCursor": cursor}
        assert all(_both_paths(MODULE, "LogTruncatedEvent", planted)), f"a non-reset cursor {cursor} was accepted"


def test_a_lifecycle_event_with_a_type_outside_the_seven_is_rejected() -> None:
    schema = _read(MODULE / "schemas" / "MissionLifecycleEvent.yaml")
    assert set(schema["properties"]["eventType"]["enum"]) == LIFECYCLE_TYPES
    event = _first_of("MissionLifecycleEvent")
    for outside in ("ProjectInitialized", "WPCreated", "ReviewerSelfApproval", "MissionReopened", "FollowUpRecorded", "missioncreated", ""):
        planted = {**event, "eventType": outside}
        resolver_errors, library_errors = _both_paths(MODULE, "MissionLifecycleEvent", planted)
        assert resolver_errors and library_errors, f"eventType {outside!r} was accepted"


def test_an_event_missionId_must_be_a_ulid_never_a_slug() -> None:
    event = _first_of("StatusTransitionEvent")
    for identity in ("example-mission-01JZCB3C", "WP01", ""):
        planted = {**event, "missionId": identity}
        resolver_errors, library_errors = _both_paths(MODULE, "StatusTransitionEvent", planted)
        assert resolver_errors and library_errors, f"missionId {identity!r} was accepted"


def test_the_cursor_string_form_is_offset_colon_invariant() -> None:
    valid = [f"0:{EMPTY_DIGEST}", f"1024:{'a' * 64}"]
    invalid = [
        "",
        EMPTY_DIGEST,
        f"-1:{EMPTY_DIGEST}",
        f"1.5:{EMPTY_DIGEST}",
        f"0:{EMPTY_DIGEST.upper()}",
        f"0:{'a' * 63}",
        f"0:{'a' * 65}",
        f"0: {EMPTY_DIGEST}",
        f"x:{EMPTY_DIGEST}",
    ]
    for text in valid:
        assert not any(_both_paths(MODULE, CURSOR_STRING_SCHEMA, text)), text
    for text in invalid:
        resolver_errors, library_errors = _both_paths(MODULE, CURSOR_STRING_SCHEMA, text)
        assert resolver_errors and library_errors, f"{text!r} was accepted"


def test_the_cursor_string_agrees_with_the_cursor_object_examples() -> None:
    events = _instances_of("StatusTransitionEvent")
    assert events, "no StatusTransitionEvent examples"
    for name, event in events.items():
        cursor = event["streamCursor"]
        text = f"{cursor['offset']}:{cursor['invariant']}"
        assert not any(_both_paths(MODULE, CURSOR_STRING_SCHEMA, text)), name


STREAM_CONTRACT_FILES = (
    f"mission-status/schemas/{CURSOR_STRING_SCHEMA}.yaml",
    "mission-status/schemas/StatusTransitionEvent.yaml",
    "mission-status/schemas/LogTruncatedEvent.yaml",
    "mission-status/schemas/MissionLifecycleEvent.yaml",
    f"mission-status/schemas/{REFUSAL_SCHEMA}.yaml",
    "mission-status/parameters/EventsMissionId.yaml",
    "mission-status/parameters/EventsStreamCursor.yaml",
    "mission-status/parameters/LastEventId.yaml",
)


def _page_cursor_reaches(contracts: Path) -> list[str]:
    return [start for start in STREAM_CONTRACT_FILES if PAGE_CURSOR_FILE in _ref_closure(contracts, start)]


def test_the_stream_cursor_string_never_reaches_the_page_cursor() -> None:
    assert not _page_cursor_reaches(CONTRACTS), _page_cursor_reaches(CONTRACTS)
    assert STREAM_CURSOR_FILE in _ref_closure(CONTRACTS, "mission-status/schemas/LogTruncatedEvent.yaml")


def test_a_planted_page_cursor_reference_in_an_events_parameter_is_seen(tmp_path: Path) -> None:
    contracts = tmp_path / "contracts"
    shutil.copytree(MODULE, contracts / MODULE.name)
    shutil.copytree(CONTRACTS / "_shared", contracts / "_shared")
    target = contracts / "mission-status/parameters/EventsStreamCursor.yaml"
    document = _read(target)
    document["schema"] = {"$ref": "../../_shared/schemas/PageCursor.yaml"}
    target.write_text(yaml.safe_dump(document), encoding="utf-8")
    assert _page_cursor_reaches(contracts) == ["mission-status/parameters/EventsStreamCursor.yaml"]


def _provisional_text(node: Any) -> str:
    assert isinstance(node, dict) and "x-provisional" in node, "no x-provisional here"
    decision = node["x-provisional"]["open_decision"]
    assert isinstance(decision, str) and decision.strip()
    return " ".join(decision.split())


def test_the_contract_owned_refusal_code_is_provisional() -> None:
    refusal = _read(MODULE / "schemas" / f"{REFUSAL_SCHEMA}.yaml")
    code = next(p["properties"]["code"] for p in refusal["allOf"] if "properties" in p and "code" in p["properties"])
    text = _provisional_text(code)
    assert "cursor_without_mission" in text and "contract" in text and "#5528" in text


def test_the_stream_framing_and_heartbeat_are_provisional_on_the_operation() -> None:
    text = _provisional_text(_events_operation())
    for needle in ("event:", "id:", "data:", "heartbeat", "30", "400", "409", "#5528"):
        assert needle in text, f"the operation's open decision does not mention {needle!r}"


def test_the_cursor_precedence_is_provisional_on_the_stream_cursor_parameter() -> None:
    text = _provisional_text(_read(MODULE / "parameters" / "EventsStreamCursor.yaml"))
    assert "Last-Event-ID" in text and "streamCursor" in text and "#5528" in text


def test_the_stricter_cursor_rule_is_stated_as_provisional_on_the_cursor_string() -> None:
    text = _provisional_text(_read(MODULE / "schemas" / f"{CURSOR_STRING_SCHEMA}.yaml"))
    for needle in ("validate_resume_cursor", "invariant", "stricter", "#5528"):
        assert needle in text, f"the cursor string's open decision does not mention {needle!r}"


def test_the_changelog_lists_each_contract_owned_stream_part_as_provisional() -> None:
    changelog = (MODULE / "CHANGELOG.md").read_text(encoding="utf-8")
    section = " ".join(changelog.split("### Provisional", 1)[1].split())
    for needle in ("cursor_without_mission", "framing", "heartbeat", "Last-Event-ID", "stricter", "validate_resume_cursor"):
        assert needle in section, f"the Provisional section does not mention {needle!r}"


def test_every_path_is_mapped_each_to_a_brace_free_file() -> None:
    root = _read(MODULE / "openapi.yaml")
    assert set(root["paths"]) == EXPECTED_PATH_KEYS
    for key, item in root["paths"].items():
        assert set(item) == {"$ref"}, key
        expected = f"paths/{resolver.path_file_name(key)}"
        assert item["$ref"] == expected, (key, item["$ref"])
        assert "{" not in item["$ref"] and "%7" not in item["$ref"].lower(), key
        assert (MODULE / expected).is_file(), expected
    assert root["paths"][EVENTS_PATH]["$ref"] == "paths/events.yaml"


def _events_operation() -> dict[str, Any]:
    operation: dict[str, Any] = _read(MODULE / "paths" / "events.yaml")["get"]
    return operation


def test_the_events_operation_streams_event_stream_and_documents_the_request_shape() -> None:
    operation = _events_operation()
    ok = operation["responses"]["200"]
    assert set(ok["content"]) == {"text/event-stream"}, sorted(ok["content"])
    parameters = [_read(MODULE / "paths" / ref["$ref"]) for ref in operation["parameters"]]
    shape = {(parameter["name"], parameter["in"], parameter["required"]) for parameter in parameters}
    assert shape == {("missionId", "query", False), ("streamCursor", "query", False), ("Last-Event-ID", "header", False)}, shape
    text = " ".join(operation["description"].split())
    for needle in ("Last-Event-ID", ": heartbeat", "30 seconds", "live only", "log-truncated", "per Mission", "provisional", "TailCursor"):
        assert needle in text, f"the stream description does not mention {needle!r}"
    mapped = [schema for schema in EVENT_SCHEMAS.values() if schema in text]
    assert sorted(mapped) == sorted(EVENT_SCHEMAS.values())
    for kind in EVENT_SCHEMAS:
        assert text.count(f"`{kind}` ->") == 1, f"the mapping must name {kind} exactly once"


def test_the_events_refusals_are_problem_responses_with_the_documented_codes() -> None:
    operation = _events_operation()
    assert {"400", "409", "default"} <= set(operation["responses"])
    refusal = _read(MODULE / "schemas" / f"{REFUSAL_SCHEMA}.yaml")
    code_enum = next(part["properties"]["code"]["enum"] for part in refusal["allOf"] if "properties" in part and "code" in part["properties"])
    assert set(code_enum) == REFUSAL_CODES


def test_no_event_example_carries_a_leak_shaped_value_or_a_raw_log_key() -> None:
    raw_keys = {"aggregate_id", "event_id", "event_type", "payload", "to_lane", "from_lane", "tail_offset", "tail_invariant", "detected_at_offset"}
    for schema in (*EVENT_SCHEMAS.values(), REFUSAL_SCHEMA):
        instances = _instances_of(schema)
        assert instances, f"no examples for {schema}"
        for name, instance in instances.items():
            assert not raw_keys & set(instance), f"{name} carries a raw log key"


_OVERRIDE_AT = "2026-09-01T10:11:00+00:00"


@pytest.mark.parametrize(
    "instance",
    [
        {"complete": True, "at": None, "actor": "operator", "reason": "out of band"},
        {"complete": True, "at": _OVERRIDE_AT, "actor": "operator", "reason": None},
        {"complete": True, "at": None, "actor": "operator", "reason": None},
    ],
    ids=["null-at", "null-reason", "null-both"],
)
def test_a_complete_review_override_without_its_at_and_reason_is_rejected_through_both_paths(instance: dict[str, Any]) -> None:
    """The if/then of ReviewOverride is what makes ``complete`` trustworthy; nothing else enforces it."""
    resolved, library = _both_paths(MODULE, "ReviewOverride", instance)
    assert resolved and library, (resolved, library)


@pytest.mark.parametrize(
    "instance",
    [
        {"complete": False, "at": None, "actor": None, "reason": None},
        {"complete": False, "at": _OVERRIDE_AT, "actor": "operator", "reason": None},
        {"complete": True, "at": _OVERRIDE_AT, "actor": "operator", "reason": "out of band"},
    ],
    ids=["incomplete-all-null", "incomplete-null-reason", "complete-filled"],
)
def test_an_incomplete_review_override_may_carry_nulls_through_both_paths(instance: dict[str, Any]) -> None:
    assert _both_paths(MODULE, "ReviewOverride", instance) == ([], [])


def test_the_structured_stream_cursor_is_provisional_like_its_text_form() -> None:
    """The ``{offset, invariant}`` object exposes tail_reader byte offsets, as the string form does."""
    text = _provisional_text(_read(MODULE / "schemas" / "StreamCursor.yaml"))
    for needle in ("TailCursor", "byte offset", "#5528"):
        assert needle in text, f"the structured cursor's open decision does not mention {needle!r}"


PAGE_CURSOR_REFUSAL_SCHEMA = "PageCursorRefusal"
PAGE_CURSOR_REFUSAL = {"type": "about:blank", "title": "The page cursor was refused", "status": 400, "code": "invalid_page_cursor"}


def _list_missions_400() -> dict[str, Any]:
    response: dict[str, Any] = _read(MODULE / "paths" / "missions.yaml")["get"]["responses"]["400"]
    return response


def test_the_list_missions_400_is_the_page_cursor_refusal() -> None:
    ref = _list_missions_400()["$ref"]
    assert ref.endswith("responses/PageCursorRefused.yaml"), ref
    schema = _read(MODULE / "responses" / "PageCursorRefused.yaml")["content"]["application/problem+json"]["schema"]
    assert schema == {"$ref": f"../schemas/{PAGE_CURSOR_REFUSAL_SCHEMA}.yaml"}, schema


def test_the_page_cursor_refusal_has_a_validating_example() -> None:
    instances = _instances_of(PAGE_CURSOR_REFUSAL_SCHEMA)
    assert instances, f"no example is attached to {PAGE_CURSOR_REFUSAL_SCHEMA}"
    for name, instance in instances.items():
        assert instance["code"] == "invalid_page_cursor", name
        assert not any(_both_paths(MODULE, PAGE_CURSOR_REFUSAL_SCHEMA, instance)), name


@pytest.mark.parametrize(
    "change",
    [{"code": "negative"}, {"code": None}, {"status": 409}, {"status": 500}],
    ids=["stream-code", "null-code", "status-409", "status-500"],
)
def test_the_page_cursor_refusal_rejects_any_other_code_or_status_through_both_paths(change: dict[str, Any]) -> None:
    resolved, library = _both_paths(MODULE, PAGE_CURSOR_REFUSAL_SCHEMA, {**PAGE_CURSOR_REFUSAL, **change})
    assert resolved and library, (resolved, library)


def test_the_page_cursor_refusal_requires_its_code() -> None:
    instance = {key: value for key, value in PAGE_CURSOR_REFUSAL.items() if key != "code"}
    resolved, library = _both_paths(MODULE, PAGE_CURSOR_REFUSAL_SCHEMA, instance)
    assert resolved and library, (resolved, library)


def test_mid8_is_never_null_and_is_the_first_eight_characters_of_the_mission_id() -> None:
    head = _read(MODULE / "schemas" / "MissionHead.yaml")
    assert head["properties"]["mid8"]["type"] == "string", head["properties"]["mid8"]["type"]
    for schema in ("MissionOverview", "MissionDetail", "MissionOverviewPage"):
        for name, instance in _instances_of(schema).items():
            items = instance["items"] if schema == "MissionOverviewPage" else [instance]
            for item in items:
                assert item["mid8"] == item["missionId"][:8], (name, item["missionId"], item["mid8"])


@pytest.mark.parametrize("schema", ["MissionOverview", "MissionDetail"])
def test_a_null_mid8_is_rejected_through_both_paths(schema: str) -> None:
    instance = dict(_first_of(schema))
    instance["mid8"] = None
    resolved, library = _both_paths(MODULE, schema, instance)
    assert resolved and library, (resolved, library)


def _description(schema: str, *path: str) -> str:
    node: Any = _read(MODULE / "schemas" / f"{schema}.yaml")
    for key in path:
        node = node[key]
    return " ".join(node["description"].split())


def test_the_content_mismatch_reason_names_the_last_line_digest_not_the_prefix() -> None:
    text = _description("LogTruncatedEvent", "properties", "reason")
    assert "last complete line" in text and "SHA-256" in text, text
    assert "bytes before the cursor" not in text, text


def test_the_transition_event_names_the_status_event_fields_it_leaves_out() -> None:
    text = _description("StatusTransitionEvent")
    for field in ("reason", "reason_source", "review_ref", "evidence", "review_result", "policy_metadata", "execution_mode", "mission_slug"):
        assert field in text, f"the transition event does not name the left-out field {field!r}"


# --------------------------------------------------------------------------------------
# WP03: the artifact reads, listArtifacts and getArtifactContent (FR-009 to FR-013, FR-017 to FR-019)
# --------------------------------------------------------------------------------------

ARTIFACT_VERSION = "1.0.0-SNAPSHOT"
ARTIFACT_LISTING_PATH = "/missions/{missionId}/artifacts"
ARTIFACT_CONTENT_PATH = "/missions/{missionId}/artifacts/content"
ARTIFACT_LISTING_SCHEMA = "ArtifactListing"
ARTIFACT_CONTENT_SCHEMA = "ArtifactContent"
ARTIFACT_REFUSAL_SCHEMA = "ArtifactRefusal"
ARTIFACT_PATH_SCHEMA = "ArtifactPath"
ARTIFACT_KINDS = [
    "review_cycle",
    "work_package_prompt",
    "spec",
    "plan",
    "tasks",
    "data_model",
    "quickstart",
    "analysis_report",
    "research",
    "contract",
    "checklist",
    "other",
]
# the pinned status of each refusal code, in the order of the enum
ARTIFACT_REFUSAL_STATUS = {
    "invalid_artifact_path": 400,
    "not_found": 404,
    "artifact_too_large": 413,
    "artifact_not_text": 415,
    "artifact_secret": 422,
    "artifact_unreadable": 500,
    "artifact_listing_unreadable": 500,
}
ARTIFACT_LISTING_MAX_ITEMS = 1000
ARTIFACT_CREDENTIAL_WORDS = ("ghp", "gho", "ghu", "ghs", "ghr", "github_pat", "AKIA", "ASIA", "PEM")
NUL = chr(0)
BACKSLASH = chr(92)
# (path, malformed): the table of the three-way agreement (the leak scan predicate, a literal restatement of the spec
# predicate and the ArtifactPath schema pattern); restated here as data, a test module never imports another one
ARTIFACT_PATH_CASES: list[tuple[str, bool]] = [
    ("a.md", False),
    ("dir/a.md", False),
    ("home/someone/notes.md", False),
    ("with space.md", False),
    ("caf" + chr(233) + ".md", False),
    ("icon" + chr(64) + "2x.png", False),
    ("~", False),
    ("~user/a.md", False),
    (".hidden", False),
    ("a..b", False),
    ("...", False),
    ("a/.../b", False),
    ("1:a", False),
    ("dir/C:x", False),
    ("x" * 512, False),
    ("", True),
    ("x" * 513, True),
    ("/a", True),
    ("/", True),
    ("~/a", True),
    ("~/", True),
    ("C:/a", True),
    ("z:", True),
    ("a" + BACKSLASH + "b", True),
    ("a" + NUL + "b", True),
    ("a" + chr(10) + "b", True),
    ("a" + chr(13) + "b", True),
    ("a" + chr(11) + "b", True),
    ("a" + chr(12) + "b", True),
    ("a" + chr(28) + "b", True),
    ("a" + chr(29) + "b", True),
    ("a" + chr(30) + "b", True),
    ("a" + chr(133) + "b", True),
    ("a" + chr(0x2028) + "b", True),
    ("a" + chr(0x2029) + "b", True),
    ("a" + chr(10), True),
    ("a" + chr(13) + chr(10), True),
    ("a/" + chr(10), True),
    ("a//b", True),
    ("a/", True),
    ("a/b/", True),
    ("./a", True),
    (".", True),
    ("a/./b", True),
    ("..", True),
    ("a/../b", True),
    ("../a", True),
]


def _spec_path_malformed(path: str) -> bool:
    """A literal restatement of the spec predicate (data model, ArtifactPath), independent of the tool and of the pattern."""
    if path == "" or len(path) > 512:
        return True
    if path.startswith(("/", "~/")):
        return True
    if len(path) >= 2 and path[1] == ":" and path[0].isascii() and path[0].isalpha():
        return True
    if BACKSLASH in path or NUL in path or any(character.splitlines() != [character] for character in path):
        return True
    return path.endswith("/") or any(segment in ("", ".", "..") for segment in path.split("/"))


def _artifact_operation(path: str) -> dict[str, Any]:
    item = _read(MODULE / "openapi.yaml")["paths"][path]
    return _read(MODULE / item["$ref"])["get"]


def test_the_module_stays_at_the_unreleased_1_0_0_snapshot_version() -> None:
    assert _read(MODULE / "openapi.yaml")["info"]["version"] == ARTIFACT_VERSION


def test_the_two_artifact_operations_are_mapped_and_tagged_with_the_existing_tag() -> None:
    root = _read(MODULE / "openapi.yaml")
    assert [tag["name"] for tag in root["tags"]] == ["Project", "Missions", "Events"]
    listing = _artifact_operation(ARTIFACT_LISTING_PATH)
    content = _artifact_operation(ARTIFACT_CONTENT_PATH)
    assert listing["operationId"] == "listArtifacts" and content["operationId"] == "getArtifactContent"
    assert listing["tags"] == ["Missions"] == content["tags"]
    assert set(listing["responses"]) == {"200", "404", "500", "default"}
    assert set(content["responses"]) == {"200", "400", "404", "413", "415", "422", "500", "default"}
    assert "security" not in listing and "security" not in content


def test_every_artifact_refusal_response_carries_the_artifact_refusal_schema() -> None:
    expected = {
        "ArtifactPathRefused": "400",
        "ArtifactNotFound": "404",
        "ArtifactTooLarge": "413",
        "ArtifactNotText": "415",
        "ArtifactSecretRefused": "422",
        "ArtifactUnreadable": "500",
        "ArtifactListingUnreadable": "500",
    }
    mounted: dict[str, str] = {}
    for path in (ARTIFACT_LISTING_PATH, ARTIFACT_CONTENT_PATH):
        for status, response in _artifact_operation(path)["responses"].items():
            ref = response.get("$ref", "")
            if ref.startswith("../responses/Artifact"):
                mounted[ref.removeprefix("../responses/").removesuffix(".yaml")] = status
    assert mounted == expected, mounted
    for name in expected:
        body = _read(MODULE / "responses" / f"{name}.yaml")
        assert body["content"]["application/problem+json"]["schema"]["$ref"] == f"../schemas/{ARTIFACT_REFUSAL_SCHEMA}.yaml", name


def test_the_artifact_path_parameter_is_the_required_query_parameter_path() -> None:
    parameter = _read(MODULE / "parameters" / "ArtifactPath.yaml")
    assert (parameter["name"], parameter["in"], parameter["required"]) == ("path", "query", True)
    assert parameter["schema"]["$ref"] == f"../schemas/{ARTIFACT_PATH_SCHEMA}.yaml"


def test_the_artifact_enums_hold_their_pinned_values() -> None:
    assert _read(MODULE / "schemas" / "ArtifactKind.yaml")["enum"] == ARTIFACT_KINDS
    assert _read(MODULE / "schemas" / "ArtifactRefusalCode.yaml")["enum"] == list(ARTIFACT_REFUSAL_STATUS)


def test_the_artifact_listing_holds_at_most_a_thousand_entries() -> None:
    listing = _read(MODULE / "schemas" / f"{ARTIFACT_LISTING_SCHEMA}.yaml")
    assert listing["properties"]["entries"]["maxItems"] == ARTIFACT_LISTING_MAX_ITEMS


def test_the_artifact_content_encoding_is_the_constant_utf_8() -> None:
    content = _read(MODULE / "schemas" / f"{ARTIFACT_CONTENT_SCHEMA}.yaml")
    assert content["properties"]["encoding"]["const"] == "utf-8"


def test_the_readable_and_422_descriptions_name_the_credential_kinds() -> None:
    entry = _description("ArtifactEntry", "properties", "readable")
    refusal = " ".join(_read(MODULE / "responses" / "ArtifactSecretRefused.yaml")["description"].split())
    for text in (entry, refusal):
        for word in ARTIFACT_CREDENTIAL_WORDS:
            assert word in text, f"{word!r} is missing from: {text}"


def test_every_artifact_refusal_code_has_a_validating_example_with_its_pinned_status() -> None:
    instances = _instances_of(ARTIFACT_REFUSAL_SCHEMA)
    assert len(instances) >= len(ARTIFACT_REFUSAL_STATUS), sorted(instances)
    seen = {instance["code"]: instance["status"] for instance in instances.values()}
    assert seen == ARTIFACT_REFUSAL_STATUS, seen


def test_the_artifact_examples_cover_both_values_of_the_provisional_flags() -> None:
    listings = _instances_of(ARTIFACT_LISTING_SCHEMA)
    contents = _instances_of(ARTIFACT_CONTENT_SCHEMA)
    assert listings and contents, (sorted(listings), sorted(contents))
    _first(listings, lambda listing: listing["truncated"] is True)
    _first(listings, lambda listing: listing["truncated"] is False)
    readable = {entry["readable"] for listing in listings.values() for entry in listing["entries"]}
    assert readable == {True, False}, readable
    assert {content["redacted"] for content in contents.values()} == {True, False}
    kinds = {entry["kind"] for listing in listings.values() for entry in listing["entries"]}
    assert len(kinds) >= 3, f"the listing examples cover only the kinds {sorted(kinds)}"
    assert any(content["mediaType"] == "application/json" for content in contents.values())
    _first(contents, lambda content: content["content"] == "" and content["sizeBytes"] == 0)


def test_the_truncated_listing_example_is_short_and_says_so() -> None:
    name, listing = _first(_instances_of(ARTIFACT_LISTING_SCHEMA), lambda listing: listing["truncated"] is True)
    assert len(listing["entries"]) < ARTIFACT_LISTING_MAX_ITEMS, name
    assert "1000" in (MODULE / "examples" / name).read_text(encoding="utf-8"), f"{name} does not state the real truncation size"


def test_the_artifact_examples_carry_no_absolute_path_or_unredacted_leak() -> None:
    paths: list[str] = []
    for listing in _instances_of(ARTIFACT_LISTING_SCHEMA).values():
        paths.extend(entry["path"] for entry in listing["entries"])
    paths.extend(content["path"] for content in _instances_of(ARTIFACT_CONTENT_SCHEMA).values())
    assert paths, "no artifact path occurs in any example"
    assert not [path for path in paths if _spec_path_malformed(path)], paths


@pytest.mark.parametrize(("path", "malformed"), ARTIFACT_PATH_CASES, ids=[str(index) for index in range(len(ARTIFACT_PATH_CASES))])
def test_the_artifact_path_schema_agrees_with_the_spec_predicate_through_both_paths(path: str, malformed: bool) -> None:
    assert _spec_path_malformed(path) is malformed, repr(path)
    resolver_errors, library_errors = _both_paths(MODULE, ARTIFACT_PATH_SCHEMA, path)
    assert bool(resolver_errors) is malformed, f"resolver path {resolver_errors} for {path!r}"
    assert bool(library_errors) is malformed, f"library path {library_errors} for {path!r}"


def test_the_artifact_path_agreement_table_has_the_three_way_floor_and_both_classes() -> None:
    assert len(ARTIFACT_PATH_CASES) >= 30
    assert {malformed for _, malformed in ARTIFACT_PATH_CASES} == {True, False}
    assert sum(1 for path, _ in ARTIFACT_PATH_CASES if any(c.splitlines() != [c] for c in path)) >= 10


def test_the_artifact_path_leak_scan_predicate_agrees_with_the_table() -> None:
    for path, malformed in ARTIFACT_PATH_CASES:
        assert (leak_scan.malformed_artifact_path(path) is not None) is malformed, repr(path)


PLANTED_COPY_NAMES = [
    "listing-extra-property",
    "entry-extra-property",
    "listing-missing-truncated",
    "entry-missing-readable",
    "entry-absolute-path",
    "content-extra-property",
    "content-missing-redacted",
    "content-absolute-path",
    "content-other-encoding",
    "refusal-missing-code",
    "refusal-wrong-status",
    "refusal-unknown-code",
]


def _planted_copies() -> dict[str, tuple[str, Any]]:
    """name -> (schema title, planted instance): a copy of a real example with one property wrong."""
    listing = next(iter(_instances_of(ARTIFACT_LISTING_SCHEMA).values()))
    content = next(iter(_instances_of(ARTIFACT_CONTENT_SCHEMA).values()))
    refusal = next(iter(_instances_of(ARTIFACT_REFUSAL_SCHEMA).values()))
    extra_entry = {**listing, "entries": [{**listing["entries"][0], "absolutePath": "x"}]}
    missing_entry = {**listing, "entries": [{key: value for key, value in listing["entries"][0].items() if key != "readable"}]}
    absolute_entry = {**listing, "entries": [{**listing["entries"][0], "path": "/" + listing["entries"][0]["path"]}]}
    return {
        "listing-extra-property": (ARTIFACT_LISTING_SCHEMA, {**listing, "extra": True}),
        "entry-extra-property": (ARTIFACT_LISTING_SCHEMA, extra_entry),
        "listing-missing-truncated": (ARTIFACT_LISTING_SCHEMA, {key: value for key, value in listing.items() if key != "truncated"}),
        "entry-missing-readable": (ARTIFACT_LISTING_SCHEMA, missing_entry),
        "entry-absolute-path": (ARTIFACT_LISTING_SCHEMA, absolute_entry),
        "content-extra-property": (ARTIFACT_CONTENT_SCHEMA, {**content, "extra": True}),
        "content-missing-redacted": (ARTIFACT_CONTENT_SCHEMA, {key: value for key, value in content.items() if key != "redacted"}),
        "content-absolute-path": (ARTIFACT_CONTENT_SCHEMA, {**content, "path": "/etc/hosts"}),
        "content-other-encoding": (ARTIFACT_CONTENT_SCHEMA, {**content, "encoding": "latin-1"}),
        "refusal-missing-code": (ARTIFACT_REFUSAL_SCHEMA, {key: value for key, value in refusal.items() if key != "code"}),
        "refusal-wrong-status": (ARTIFACT_REFUSAL_SCHEMA, {**refusal, "status": 418}),
        "refusal-unknown-code": (ARTIFACT_REFUSAL_SCHEMA, {**refusal, "code": "teapot"}),
    }


@pytest.mark.parametrize("name", PLANTED_COPY_NAMES)
def test_a_planted_artifact_example_is_rejected_through_both_paths(name: str) -> None:
    planted = _planted_copies()
    assert sorted(planted) == sorted(PLANTED_COPY_NAMES)
    schema, instance = planted[name]
    resolver_errors, library_errors = _both_paths(MODULE, schema, instance)
    assert resolver_errors, f"the resolver path accepted the planted copy {name}"
    assert library_errors, f"the library path accepted the planted copy {name}"


def test_a_refusal_is_valid_exactly_with_the_status_pinned_to_its_code_through_both_paths() -> None:
    for code, pinned in ARTIFACT_REFUSAL_STATUS.items():
        for status in sorted(set(ARTIFACT_REFUSAL_STATUS.values())):
            instance = {"type": "about:blank", "title": "refused", "status": status, "code": code, "detail": "x"}
            resolver_errors, library_errors = _both_paths(MODULE, ARTIFACT_REFUSAL_SCHEMA, instance)
            assert bool(resolver_errors) is (status != pinned), f"resolver path: {code} with {status}: {resolver_errors}"
            assert bool(library_errors) is (status != pinned), f"library path: {code} with {status}: {library_errors}"


# --------------------------------------------------------------------------------------
# WP04: the work package detail read, getWorkPackageDetail (FR-001 to FR-008, FR-013, FR-015, FR-018, FR-019)
# --------------------------------------------------------------------------------------

DETAIL_PATH = "/missions/{missionId}/work-packages/{wpId}/detail"
WP_DETAIL_SCHEMA = "WorkPackageDetail"
WP_DETAIL_REFUSAL_SCHEMA = "WorkPackageDetailRefusal"
WP_DETAIL_REFUSAL_STATUS = {"not_found": 404, "source_unreadable": 500}
CHANGE_STATES = ["changed", "unchanged", "unknown"]
DETAIL_REQUIRED = [
    "missionId",
    "wpId",
    "subtasks",
    "dependencies",
    "reviewCycles",
    "workspace",
    "ownedFiles",
    "artifactReferences",
]
DETAIL_SCHEMA_FILES = [
    "WorkPackageDetail",
    "Subtask",
    "DependencyRef",
    "ReviewCycle",
    "Workspace",
    "OwnedFile",
    "ChangeState",
    "ArtifactReferences",
    "ArtifactReference",
    "WorkPackageDetailRefusal",
    "WorkPackageDetailRefusalCode",
]
DETAIL_CLOSED_SCHEMAS = [name for name in DETAIL_SCHEMA_FILES if name not in ("ChangeState", "WorkPackageDetailRefusal", "WorkPackageDetailRefusalCode")]
DUPLICATE_ID_WORDS = ("first", "regular", "symlink", "byte order", "WP[0-9]{2,}-*.md")


def _detail_operation() -> dict[str, Any]:
    return _artifact_operation(DETAIL_PATH)


def _detail_examples() -> dict[str, dict[str, Any]]:
    return _instances_of(WP_DETAIL_SCHEMA)


def test_the_detail_operation_is_mapped_tagged_and_pairs_each_status_with_its_response() -> None:
    operation = _detail_operation()
    assert operation["operationId"] == "getWorkPackageDetail"
    assert operation["tags"] == ["Missions"]
    assert "security" not in operation
    assert set(operation["responses"]) == {"200", "404", "500", "default"}
    assert operation["responses"]["404"]["$ref"] == "../responses/WorkPackageDetailNotFound.yaml"
    assert operation["responses"]["500"]["$ref"] == "../responses/WorkPackageDetailUnreadable.yaml"
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == f"../schemas/{WP_DETAIL_SCHEMA}.yaml"
    parameters = [parameter["$ref"] for parameter in operation["parameters"]]
    assert parameters == ["../parameters/MissionId.yaml", "../parameters/WpId.yaml"]
    for name in ("WorkPackageDetailNotFound", "WorkPackageDetailUnreadable"):
        body = _read(MODULE / "responses" / f"{name}.yaml")
        assert body["content"]["application/problem+json"]["schema"]["$ref"] == f"../schemas/{WP_DETAIL_REFUSAL_SCHEMA}.yaml", name


def test_the_detail_path_description_states_the_duplicate_id_rule() -> None:
    text = " ".join(str(_detail_operation()["description"]).split())
    for word in DUPLICATE_ID_WORDS:
        assert word in text, f"{word!r} is missing from the published description: {text}"


def test_the_detail_enums_hold_their_pinned_values() -> None:
    assert _read(MODULE / "schemas" / "ChangeState.yaml")["enum"] == CHANGE_STATES
    assert _read(MODULE / "schemas" / "WorkPackageDetailRefusalCode.yaml")["enum"] == list(WP_DETAIL_REFUSAL_STATUS)


def test_the_eleven_detail_schemas_exist_titled_by_their_file_and_the_closed_ones_are_closed() -> None:
    for name in DETAIL_SCHEMA_FILES:
        assert (MODULE / "schemas" / f"{name}.yaml").is_file(), name
        assert _read(MODULE / "schemas" / f"{name}.yaml")["title"] == name
    for name in DETAIL_CLOSED_SCHEMAS:
        assert _read(MODULE / "schemas" / f"{name}.yaml")["additionalProperties"] is False, name


def test_the_detail_requires_every_array_and_embeds_no_work_package() -> None:
    schema = _read(MODULE / "schemas" / f"{WP_DETAIL_SCHEMA}.yaml")
    assert sorted(schema["required"]) == sorted(DETAIL_REQUIRED)
    assert sorted(schema["properties"]) == sorted(DETAIL_REQUIRED)
    assert "WorkPackage.yaml" not in str(schema) and "WorkPackageSummary.yaml" not in str(schema)


def test_the_detail_examples_cover_the_required_cases() -> None:
    details = _detail_examples()
    assert len(details) >= 6, sorted(details)
    states = {owned["changeState"] for detail in details.values() for owned in detail["ownedFiles"]}
    assert states == set(CHANGE_STATES), states
    cycles = [cycle for detail in details.values() for cycle in detail["reviewCycles"]]
    assert any(cycle["feedbackReference"] is None for cycle in cycles)
    assert any(cycle["reviewedAt"] is None for cycle in cycles)
    assert {cycle["verdict"] for cycle in cycles} >= {"approved", "changes_requested", None}
    _first(details, lambda detail: detail["reviewCycles"] == [])
    _first(details, lambda detail: all(value is None for key, value in detail["workspace"].items() if key != "worktreePresent"))
    _first(details, lambda detail: detail["workspace"]["laneId"] == "lane-planning" and detail["workspace"]["laneBranch"] is None)
    _first(details, lambda detail: detail["workspace"]["worktreePresent"] is False and any(o["changeState"] == "unknown" for o in detail["ownedFiles"]))
    _first(details, lambda detail: any("{" in owned["pattern"] for owned in detail["ownedFiles"]))
    _first(details, lambda detail: any(owned["isGlob"] for owned in detail["ownedFiles"]))
    _first(details, lambda detail: detail["artifactReferences"]["prompt"] is None and detail["artifactReferences"]["spec"] is None)
    _first(details, lambda detail: detail["artifactReferences"]["prompt"] is not None and detail["artifactReferences"]["spec"] is not None)
    _first(details, lambda detail: any(subtask["title"] is None for subtask in detail["subtasks"]))
    _first(details, lambda detail: any(dependency["statusLane"] is None for dependency in detail["dependencies"]))


def test_a_change_state_is_determined_only_when_a_worktree_is_present() -> None:
    for name, detail in _detail_examples().items():
        if not detail["workspace"]["worktreePresent"]:
            assert all(owned["changeState"] == "unknown" for owned in detail["ownedFiles"]), name


def test_every_detail_refusal_code_has_a_validating_example_with_its_pinned_status() -> None:
    instances = _instances_of(WP_DETAIL_REFUSAL_SCHEMA)
    seen = {instance["code"]: instance["status"] for instance in instances.values()}
    assert seen == WP_DETAIL_REFUSAL_STATUS, seen


def test_a_detail_refusal_is_valid_exactly_with_the_status_pinned_to_its_code_through_both_paths() -> None:
    for code, pinned in WP_DETAIL_REFUSAL_STATUS.items():
        for status in (400, 404, 500):
            instance = {"type": "about:blank", "title": "refused", "status": status, "code": code, "detail": "x"}
            resolver_errors, library_errors = _both_paths(MODULE, WP_DETAIL_REFUSAL_SCHEMA, instance)
            assert bool(resolver_errors) is (status != pinned), f"resolver path: {code} with {status}: {resolver_errors}"
            assert bool(library_errors) is (status != pinned), f"library path: {code} with {status}: {library_errors}"


def test_the_detail_descriptions_state_the_host_dependence_and_the_derivation() -> None:
    worktree = _description("Workspace", "properties", "worktreePresent")
    owned = _description("OwnedFile", "properties", "changeState")
    change_state = " ".join(str(_read(MODULE / "schemas" / "ChangeState.yaml")["description"]).split())
    cycle = " ".join(str(_read(MODULE / "schemas" / "ReviewCycle.yaml")["description"]).split())
    for text in (worktree, owned, change_state):
        assert "host" in text, text
    assert "coordination" in cycle and "[]" in cycle, cycle
    derived = _read(MODULE / "schemas" / "OwnedFile.yaml")["properties"]["changeState"]["x-derived"]
    names = {entry["symbol"] for entry in derived["inputs"] if isinstance(entry, dict)}
    assert {"git_merge_base", "changed_paths", "is_glob_pattern"} <= names, names


def _detail_planted_copies() -> dict[str, tuple[str, Any]]:
    detail = _first(_detail_examples(), lambda d: d["reviewCycles"] and d["subtasks"] and d["dependencies"] and d["ownedFiles"])[1]
    refusal = next(iter(_instances_of(WP_DETAIL_REFUSAL_SCHEMA).values()))

    def without(key: str) -> dict[str, Any]:
        return {name: value for name, value in detail.items() if name != key}

    return {
        "detail-extra-property": (WP_DETAIL_SCHEMA, {**detail, "extra": True}),
        "detail-embeds-prompt-markdown": (WP_DETAIL_SCHEMA, {**detail, "promptMarkdown": "x"}),
        "detail-missing-review-cycles": (WP_DETAIL_SCHEMA, without("reviewCycles")),
        "detail-missing-workspace": (WP_DETAIL_SCHEMA, without("workspace")),
        "detail-null-array": (WP_DETAIL_SCHEMA, {**detail, "ownedFiles": None}),
        "subtask-extra-property": (WP_DETAIL_SCHEMA, {**detail, "subtasks": [{**detail["subtasks"][0], "extra": 1}]}),
        "subtask-empty-title": (WP_DETAIL_SCHEMA, {**detail, "subtasks": [{**detail["subtasks"][0], "title": ""}]}),
        "dependency-null-title": (WP_DETAIL_SCHEMA, {**detail, "dependencies": [{**detail["dependencies"][0], "title": None}]}),
        "dependency-bad-lane": (WP_DETAIL_SCHEMA, {**detail, "dependencies": [{**detail["dependencies"][0], "statusLane": "weighing"}]}),
        "cycle-zero-number": (WP_DETAIL_SCHEMA, {**detail, "reviewCycles": [{**detail["reviewCycles"][0], "cycleNumber": 0}]}),
        "cycle-date-only": (WP_DETAIL_SCHEMA, {**detail, "reviewCycles": [{**detail["reviewCycles"][0], "reviewedAt": "2026-09-22"}]}),
        "cycle-bad-verdict": (WP_DETAIL_SCHEMA, {**detail, "reviewCycles": [{**detail["reviewCycles"][0], "verdict": "maybe"}]}),
        "cycle-foreign-pointer": (WP_DETAIL_SCHEMA, {**detail, "reviewCycles": [{**detail["reviewCycles"][0], "feedbackReference": "feedback://x/y/z"}]}),
        "cycle-absolute-artifact-path": (WP_DETAIL_SCHEMA, {**detail, "reviewCycles": [{**detail["reviewCycles"][0], "artifactPath": "/a.md"}]}),
        "cycle-pointer-parent-segment": (
            WP_DETAIL_SCHEMA,
            {**detail, "reviewCycles": [{**detail["reviewCycles"][0], "feedbackReference": "review-cycle://../x/review-cycle-1.md"}]},
        ),
        "cycle-pointer-dot-leading-segment": (
            WP_DETAIL_SCHEMA,
            {**detail, "reviewCycles": [{**detail["reviewCycles"][0], "feedbackReference": "review-cycle://a/.hid/review-cycle-1.md"}]},
        ),
        "cycle-pointer-double-dot-segment": (
            WP_DETAIL_SCHEMA,
            {**detail, "reviewCycles": [{**detail["reviewCycles"][0], "feedbackReference": "review-cycle://a..b/x/review-cycle-1.md"}]},
        ),
        "cycle-pointer-non-ascii-segment": (
            WP_DETAIL_SCHEMA,
            {**detail, "reviewCycles": [{**detail["reviewCycles"][0], "feedbackReference": "review-cycle://\u00e9/x/review-cycle-1.md"}]},
        ),
        "workspace-overlong-planning-branch": (WP_DETAIL_SCHEMA, {**detail, "workspace": {**detail["workspace"], "planningBranch": "b" * 256}}),
        "workspace-extra-property": (WP_DETAIL_SCHEMA, {**detail, "workspace": {**detail["workspace"], "path": "x"}}),
        "workspace-missing-worktree-present": (WP_DETAIL_SCHEMA, {**detail, "workspace": {k: v for k, v in detail["workspace"].items() if k != "worktreePresent"}}),
        "workspace-option-like-branch": (WP_DETAIL_SCHEMA, {**detail, "workspace": {**detail["workspace"], "laneBranch": "--upload-pack=x"}}),
        "owned-unknown-change-state": (WP_DETAIL_SCHEMA, {**detail, "ownedFiles": [{**detail["ownedFiles"][0], "changeState": "modified"}]}),
        "owned-absolute-pattern": (WP_DETAIL_SCHEMA, {**detail, "ownedFiles": [{**detail["ownedFiles"][0], "pattern": "/etc/*"}]}),
        "references-missing-spec": (WP_DETAIL_SCHEMA, {**detail, "artifactReferences": {"prompt": None}}),
        "reference-absolute-path": (
            WP_DETAIL_SCHEMA,
            {**detail, "artifactReferences": {**detail["artifactReferences"], "spec": {"path": "/spec.md", "kind": "spec"}}},
        ),
        "reference-unknown-kind": (
            WP_DETAIL_SCHEMA,
            {**detail, "artifactReferences": {**detail["artifactReferences"], "spec": {"path": "spec.md", "kind": "novel"}}},
        ),
        "refusal-missing-code": (WP_DETAIL_REFUSAL_SCHEMA, {k: v for k, v in refusal.items() if k != "code"}),
        "refusal-unknown-code": (WP_DETAIL_REFUSAL_SCHEMA, {**refusal, "code": "artifact_secret"}),
    }


DETAIL_PLANTED_NAMES = [
    "detail-extra-property",
    "detail-embeds-prompt-markdown",
    "detail-missing-review-cycles",
    "detail-missing-workspace",
    "detail-null-array",
    "subtask-extra-property",
    "subtask-empty-title",
    "dependency-null-title",
    "dependency-bad-lane",
    "cycle-zero-number",
    "cycle-date-only",
    "cycle-bad-verdict",
    "cycle-foreign-pointer",
    "cycle-absolute-artifact-path",
    "cycle-pointer-parent-segment",
    "cycle-pointer-dot-leading-segment",
    "cycle-pointer-double-dot-segment",
    "cycle-pointer-non-ascii-segment",
    "workspace-overlong-planning-branch",
    "workspace-extra-property",
    "workspace-missing-worktree-present",
    "workspace-option-like-branch",
    "owned-unknown-change-state",
    "owned-absolute-pattern",
    "references-missing-spec",
    "reference-absolute-path",
    "reference-unknown-kind",
    "refusal-missing-code",
    "refusal-unknown-code",
]


@pytest.mark.parametrize("name", DETAIL_PLANTED_NAMES)
def test_a_planted_detail_example_is_rejected_through_both_paths(name: str) -> None:
    planted = _detail_planted_copies()
    assert sorted(planted) == sorted(DETAIL_PLANTED_NAMES)
    schema, instance = planted[name]
    resolver_errors, library_errors = _both_paths(MODULE, schema, instance)
    assert resolver_errors, f"the resolver path accepted the planted copy {name}"
    assert library_errors, f"the library path accepted the planted copy {name}"


def test_the_detail_schemas_name_the_provisional_elements() -> None:
    texts = {name: str(_read(MODULE / "schemas" / f"{name}.yaml")) for name in DETAIL_SCHEMA_FILES}
    for name in ("ReviewCycle", "Workspace", "WorkPackageDetailRefusalCode", "WorkPackageDetailRefusal"):
        assert "x-provisional" in texts[name], name
    assert "x-provisional" in str(_read(MODULE / "schemas" / f"{WP_DETAIL_SCHEMA}.yaml")["properties"]["reviewCycles"])
    assert "x-provisional" in str(_read(MODULE / "schemas" / f"{WP_DETAIL_SCHEMA}.yaml")["properties"]["workspace"])
    assert "x-provisional" in str(_read(MODULE / "schemas" / "ArtifactReference.yaml")["properties"]["kind"])


def test_the_review_cycle_pointer_pattern_is_no_wider_than_the_product_validator() -> None:
    import re

    from specify_cli.review.cycle import ReviewCycleError, validate_review_cycle_pointer

    pattern = re.compile(str(_read(MODULE / "schemas" / "ReviewCycle.yaml")["properties"]["feedbackReference"]["pattern"]))

    def accepted_by_validator(pointer: str) -> bool:
        try:
            validate_review_cycle_pointer(pointer)
        except ReviewCycleError:
            return False
        return True

    fixtures = [cycle["feedbackReference"] for detail in _detail_examples().values() for cycle in detail["reviewCycles"] if cycle["feedbackReference"] is not None]
    assert fixtures
    corpus = [
        *fixtures,
        "review-cycle://m/w/review-cycle-1.md",
        "review-cycle://mission-01JZCB3C/WP04-contract-slice-b-detail/review-cycle-12.md",
        "review-cycle://a.b/c_d/review-cycle-3.md",
        "review-cycle://../x/review-cycle-1.md",
        "review-cycle://a/../review-cycle-1.md",
        "review-cycle://a/.hid/review-cycle-1.md",
        "review-cycle://.a/x/review-cycle-1.md",
        "review-cycle://a..b/x/review-cycle-1.md",
        "review-cycle://a/b../review-cycle-1.md",
        "review-cycle://\u00e9/x/review-cycle-1.md",
        "review-cycle://-a/x/review-cycle-1.md",
        "review-cycle://a/x/review-cycle-0.md",
        "review-cycle://a/x/review-cycle-01.md",
        "review-cycle://a/x/y/review-cycle-1.md",
        "review-cycle://a b/x/review-cycle-1.md",
        "review-cycle://a/x/review-cycle-1.md\n",
        "feedback://a/x/review-cycle-1.md",
    ]
    for pointer in corpus:
        matches = pattern.search(pointer) is not None
        valid = accepted_by_validator(pointer)
        if pointer in fixtures:
            assert valid and matches, pointer
        # The schema may never accept what the validator refuses; it need not refuse more.
        assert not matches or valid, f"the schema accepts {pointer!r}, which the validator refuses"
        assert matches == valid, f"the schema and the validator disagree on {pointer!r}"
