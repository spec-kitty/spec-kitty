"""The synthesis ownership record has exactly one reader, one sidecar parser and one code (#6767).

Companion to :mod:`tests.charter.synthesizer.test_synthesis_ownership_reader` (the behavioural
matrix). This gate pins the *shape* that keeps the convergence from drifting back:

1. **One ownership reader** — ``synthesized_urns`` is defined once, in the module that owns the
   record, and no other module under ``src/`` resolves ownership from the manifest itself.
2. **One sidecar parser** — the provenance sidecar's ``artifact_urn`` is read only by the record
   module: no other module opens a ``provenance`` path with a YAML loader, and the string
   ``artifact_urn`` is not parsed anywhere else.
3. **One code** — ``SYNTHESIS_MEMBERSHIP_UNREADABLE`` is constructed in exactly one place.
4. **No retired readers** — the three pre-#6767 entry points are gone from ``src/``.

Fail-closed: a file that cannot be read or parsed fails the gate (``_ast_scan``), it is never
silently skipped.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architectural._ast_scan import parse_file

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
_RECORD_MODULE = "src/charter/activation/synthesizer/manifest.py"
_CODE_OWNER = "src/charter/activation/synthesizer/errors.py"

_OWNERSHIP_READER = "synthesized_urns"
_SIDECAR_PARSER = "sidecar_artifact_urn"
_UNREADABLE_CODE = "SYNTHESIS_MEMBERSHIP_UNREADABLE"
_RETIRED = ("_synthesized_urns", "_SynthesisOwnershipUnreadableError", "_extract_artifact_id_from_provenance")

#: YAML loaders that would be a second parser of the sidecar shape.
_YAML_LOADERS = frozenset({"YAML", "safe_load", "load_yaml", "load"})


def _source_files() -> list[Path]:
    return sorted(path for path in _SRC.rglob("*.py") if "__pycache__" not in path.parts)


def _rel(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def _defined_functions(tree: ast.Module) -> set[str]:
    return {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def test_the_ownership_reader_is_defined_once_in_the_record_module() -> None:
    definers = [_rel(path) for path in _source_files() if _OWNERSHIP_READER in _defined_functions(parse_file(path))]

    assert definers == [_RECORD_MODULE], f"{_OWNERSHIP_READER} must be defined exactly once, in {_RECORD_MODULE}; found {definers}"


def test_only_the_record_module_parses_the_provenance_sidecar() -> None:
    offenders: list[str] = []
    for path in _source_files():
        if _rel(path) == _RECORD_MODULE:
            continue
        tree = parse_file(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name not in _YAML_LOADERS:
                continue
            rendered = " ".join(ast.unparse(argument) for argument in [*node.args, *node.keywords])
            if "provenance" in rendered or "artifact_urn" in rendered:
                offenders.append(f"{_rel(path)}:{node.lineno}")

    assert offenders == [], "the provenance sidecar shape has one parser (" + _SIDECAR_PARSER + f" in {_RECORD_MODULE}); second parsers at {offenders}"


def test_the_unreadable_code_is_constructed_in_exactly_one_place() -> None:
    constructions = [
        _rel(path) + f":{node.lineno}"
        for path in _source_files()
        for node in ast.walk(parse_file(path))
        if isinstance(node, ast.Constant) and node.value == _UNREADABLE_CODE
    ]

    assert len(constructions) == 1, constructions
    assert constructions[0].rsplit(":", 1)[0] == _CODE_OWNER, constructions


def test_the_retired_readers_are_gone() -> None:
    offenders: list[str] = []
    for path in _source_files():
        tree = parse_file(path)
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.alias):
                names.add((node.asname or node.name).rsplit(".", 1)[-1])
        for retired in _RETIRED:
            if retired in names:
                offenders.append(f"{_rel(path)}:{retired}")

    assert offenders == [], f"retired ownership readers are still referenced: {offenders}"
