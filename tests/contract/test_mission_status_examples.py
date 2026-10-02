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

import importlib.util
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = REPO_ROOT / "contracts"
MODULE = CONTRACTS / "mission-status"
TOOLS = CONTRACTS / "tools"
MIN_EXAMPLES = 8
PLANTED_FILE = "Planted.malformed.yaml"
PLANTED_SCHEMA = "MissionOverview"
MALFORMED_TIMESTAMP = "2026-13-45T25:61:00Z"


def _load_tool(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", TOOLS / f"{name}.py")
    assert spec is not None and spec.loader is not None, f"cannot load {name}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


resolver = _load_tool("contract_resolver")
schema_formats = _load_tool("schema_formats")
leak_patterns = _load_tool("leak_patterns")


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
    _first(packages, lambda wp: wp["review"]["override"] is not None)
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


def test_the_stream_cursor_string_never_reaches_the_page_cursor() -> None:
    for start in (f"mission-status/schemas/{CURSOR_STRING_SCHEMA}.yaml", "mission-status/schemas/StatusTransitionEvent.yaml"):
        reached = _ref_closure(CONTRACTS, start)
        assert PAGE_CURSOR_FILE not in reached, f"{start} reaches the page cursor"
        assert STREAM_CURSOR_FILE in _ref_closure(CONTRACTS, "mission-status/schemas/LogTruncatedEvent.yaml")


def test_all_five_paths_are_mapped_each_to_a_brace_free_file() -> None:
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
