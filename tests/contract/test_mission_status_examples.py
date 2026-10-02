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
    def retrieve(uri: str) -> Resource:
        path = Path(uri.removeprefix("file://"))
        return Resource.from_contents(_read(path), default_specification=DRAFT202012)

    return Registry(retrieve=retrieve)


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
