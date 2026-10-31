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


#: Every module that reads a provenance sidecar, and why it may. The one *ownership* reader is
#: :func:`synthesized_urns`; these are the pre-existing best-effort probes with their own
#: policies (edge backing, registration pruning, registered-artifact split, resynthesis
#: inputs, status display). The set is shrink-only: a new sidecar read must either go through
#: ``sidecar_artifact_urn`` or be added here with a reason (#6767 follow-up).
_SIDECAR_READERS = frozenset(
    {
        "src/charter/activation/project_registration.py",  # _sidecar_recorded_urn: pruning identity probe
        "src/charter/activation/synthesizer/manifest.py",  # the one reader and its sidecar parser
        "src/charter/activation/synthesizer/project_drg.py",  # _registered_project_artifacts: registered split
        "src/charter/activation/synthesizer/reconcile.py",  # _provenance_urn: edge-backing probe
        "src/charter/activation/synthesizer/resynthesize_pipeline.py",  # resynthesis inputs
        "src/specify_cli/cli/commands/charter/_status_collectors.py",  # charter status display
    }
)


def _sidecar_loader_importers(tree: ast.Module) -> bool:
    """True when *tree* binds the provenance model loader under any name, or calls it by attribute."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and "provenance" in (node.module or "") and any(alias.name == "load_yaml" for alias in node.names):
            return True
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "load_yaml" and isinstance(func.value, ast.Name):
                return True
    return False


def test_every_sidecar_reader_is_the_pinned_census() -> None:
    """The sidecar shape has one *ownership* reader; other readers are enumerated, not discovered.

    Resolves the aliased-import idiom the codebase uses (``load_yaml as load_provenance``), so a
    new reader cannot slip past the gate by renaming the parser.
    """
    importers = sorted(_rel(path) for path in _source_files() if _sidecar_loader_importers(parse_file(path)))

    assert set(importers) == _SIDECAR_READERS, (
        "a module reads the provenance sidecar outside the pinned census: "
        f"new={sorted(set(importers) - _SIDECAR_READERS)}, gone={sorted(_SIDECAR_READERS - set(importers))}. "
        "Route it through sidecar_artifact_urn, or add it here with a reason."
    )


def test_no_module_parses_a_sidecar_with_a_raw_yaml_loader() -> None:
    """The one parser of the sidecar *shape* is the validated model loader; raw YAML is a second one."""
    offenders: list[str] = []
    for path in _source_files():
        if _rel(path) == _RECORD_MODULE:
            continue
        tree = parse_file(path)
        raw_names = {"YAML", "safe_load", "load", "unsafe_load"}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in {"ruamel", "yaml"}:
                raw_names.update(alias.asname or alias.name for alias in node.names)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name not in raw_names:
                continue
            rendered = " ".join(ast.unparse(argument) for argument in [*node.args, *node.keywords])
            if "provenance" in rendered or "artifact_urn" in rendered:
                offenders.append(f"{_rel(path)}:{node.lineno}")

    assert offenders == [], f"the sidecar shape has one parser (the validated loader in {_RECORD_MODULE}); raw YAML parses at {offenders}"


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
