"""Prove the Java parser accepts the resolver-written bundle and sees the same inventory; read every example twice (FR-019, plan D-P2; E-1 ruling of 2026-10-02).

The released bundle is written by the Python resolver (``bundle.py``), because the Java
``openapi-yaml`` generator drops OpenAPI 3.1 constructs. This script therefore no longer
compares trees. ``bundle.py`` has the Gradle build validate the bundle and re-emit it as the Java
parser reads it (``<bundles>/javaview/<module>/openapi.yaml``); here the *inventory* of that view
is compared with the inventory of the written bundle
(``<bundles>/bundle/<module>/openapi.yaml``): the path keys, the operations (method plus
operationId), the parameters (name and location), the response codes with their media types, and the
schema names (the ``title`` of every schema reached from a path). Keys the emitter adds or rewrites
(synthesised examples, ``nullable``, ``style`` defaults, open ``additionalProperties``) are not part
of the inventory. The bundle must also equal the resolver's tree (``BUNDLE_STALE``), so a stale file
cannot pass.

It is a **consistency check, never an independent proof**: a construct both readers get wrong the
same way is invisible to it. The independent dereference check narrows that gap: every example under a
schema file's ``examples`` keyword is validated twice, once against the schema as the resolver's tree
has it and once with ``jsonschema`` and a ``referencing.Registry`` that retrieves the split files itself
(no code from ``contract_resolver.py``), both with ``schema_formats.FORMAT_CHECKER``. The verdicts must
agree for every example, invalid planted ones included (agreement on "invalid" is ``example_check``'s
business).

Failure codes (exit 1), printed ``CONTRACT-CHECK resolver_parity: <CODE>: <module>: <detail>``:
``PATHS_DIFFER``, ``OPERATIONS_DIFFER``, ``PARAMETERS_DIFFER``, ``RESPONSES_DIFFER``,
``SCHEMA_NAMES_DIFFER`` (each names what is only in the bundle and what is only in the Java view),
``BUNDLE_STALE``, ``INDEPENDENT_DEREF_DISAGREES``, ``RESOLVE_FAILED``, ``VIEW_UNREADABLE`` (the Java
view has a reference that does not resolve). Cannot do its job (exit 2): ``RESOLVER_IMPORT_FAILED``,
``BUNDLE_MISSING_OR_EMPTY`` (either file), ``BELOW_FLOOR`` (fewer than ``--min-paths`` path items in the
tree or the bundle, zero schemas, zero resolved references) and ``NO_MODULE``. The last line is always
``counts: path_items=N schemas=N refs_resolved=N operations=N parameters=N responses=N schema_names=N
examples_cross_checked=N`` on one line.

Run as a bare script (``python contracts/tools/resolver_parity.py --root DIR --bundles DIR``).
Standard library, PyYAML and jsonschema with ``referencing``; imports only sibling modules.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import quote, unquote

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

import bundle
from schema_formats import FORMAT_CHECKER

CHECK_NAME = "resolver_parity"
DEFAULT_MIN_PATHS = 5
LIBRARY_BASE_URI = "https://contract.invalid/"
HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
NO_MEDIA_TYPE = "-"
# Keys whose values are data, not schemas: a ``title`` inside them is not a schema name.
DATA_KEYS = frozenset({"example", "examples", "default", "enum", "const", "value"})
SEPARATOR = "; "


@dataclass(frozen=True)
class ExampleVerdict:
    schema: str
    index: int
    resolver_valid: bool
    library_valid: bool


@dataclass(frozen=True)
class Inventory:
    """What a reader of the contract can see, independent of how an emitter shapes the document."""

    paths: frozenset[str]
    operations: frozenset[tuple[str, str, str]]
    parameters: frozenset[tuple[str, str, str, str]]
    responses: frozenset[tuple[str, str, str, str]]
    schema_names: frozenset[str]


@dataclass
class Totals:
    path_items: int = 0
    schemas: int = 0
    refs_resolved: int = 0
    operations: int = 0
    parameters: int = 0
    responses: int = 0
    schema_names: int = 0
    examples_cross_checked: int = 0
    findings: list[str] = field(default_factory=list)

    def counts_line(self) -> str:
        return (
            f"counts: path_items={self.path_items} schemas={self.schemas} refs_resolved={self.refs_resolved} operations={self.operations} "
            f"parameters={self.parameters} responses={self.responses} schema_names={self.schema_names} "
            f"examples_cross_checked={self.examples_cross_checked}"
        )


class BundleError(Exception):
    """A document could not be dereferenced (a reference that does not resolve, or a cycle)."""


# -- the inventory --------------------------------------------------------------------------


def _node_at(document: Any, pointer: str) -> Any:
    node = document
    for raw in pointer.split("/")[1:] if pointer else []:
        token = raw.replace("~1", "/").replace("~0", "~")
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


def _titles(node: Any, found: set[str]) -> None:
    if isinstance(node, dict):
        title = node.get("title")
        if isinstance(title, str):
            found.add(title)
        for key, value in node.items():
            if key not in DATA_KEYS and not str(key).startswith("x-"):
                _titles(value, found)
    elif isinstance(node, list):
        for item in node:
            _titles(item, found)


def _parameters(owner: dict[str, Any], path: str, method: str) -> set[tuple[str, str, str, str]]:
    listed = owner.get("parameters")
    return {(path, method, str(item.get("name")), str(item.get("in"))) for item in listed if isinstance(item, dict)} if isinstance(listed, list) else set()


def inventory(document: dict[str, Any]) -> Inventory:
    """The inventory of an OpenAPI document, following its internal ``#/...`` references."""
    resolved = deref_bundle(document)
    paths = resolved.get("paths") if isinstance(resolved, dict) else None
    operations: set[tuple[str, str, str]] = set()
    parameters: set[tuple[str, str, str, str]] = set()
    responses: set[tuple[str, str, str, str]] = set()
    names: set[str] = set()
    for path, item in (paths or {}).items():
        if not isinstance(item, dict):
            continue
        parameters |= _parameters(item, str(path), "*")
        for method in HTTP_METHODS:
            operation = item.get(method)
            if not isinstance(operation, dict):
                continue
            verb = method.upper()
            operations.add((str(path), verb, str(operation.get("operationId"))))
            parameters |= _parameters(operation, str(path), verb)
            for code, response in (operation.get("responses") or {}).items():
                content = response.get("content") if isinstance(response, dict) else None
                for media in content if isinstance(content, dict) and content else [NO_MEDIA_TYPE]:
                    responses.add((str(path), verb, str(code), str(media)))
        _titles({key: value for key, value in item.items() if key not in {"summary", "description"}}, names)
    return Inventory(frozenset(str(path) for path in (paths or {})), frozenset(operations), frozenset(parameters), frozenset(responses), frozenset(names))


def _describe(item: Any) -> str:
    return " ".join(item) if isinstance(item, tuple) else str(item)


def compare_inventories(module: str, bundle_side: Inventory, view_side: Inventory) -> list[str]:
    """One finding per kind of difference, naming what is only in the bundle and what only in the Java view."""
    findings: list[str] = []
    for code, mine, theirs in (
        ("PATHS_DIFFER", bundle_side.paths, view_side.paths),
        ("OPERATIONS_DIFFER", bundle_side.operations, view_side.operations),
        ("PARAMETERS_DIFFER", bundle_side.parameters, view_side.parameters),
        ("RESPONSES_DIFFER", bundle_side.responses, view_side.responses),
        ("SCHEMA_NAMES_DIFFER", bundle_side.schema_names, view_side.schema_names),
    ):
        if mine == theirs:
            continue
        only_bundle = SEPARATOR.join(sorted(_describe(item) for item in mine - theirs)) or "nothing"
        only_view = SEPARATOR.join(sorted(_describe(item) for item in theirs - mine)) or "nothing"
        findings.append(f"CONTRACT-CHECK {CHECK_NAME}: {code}: {module}: only in the bundle: {only_bundle} | only in the Java view: {only_view}")
    return findings


def deref_bundle(document: dict[str, Any]) -> Any:
    """Dereference the internal ``#/...`` references of a bundle. Siblings of a ``$ref`` override the target, as the resolver reads them."""

    def walk(node: Any, active: tuple[str, ...]) -> Any:
        if isinstance(node, list):
            return [walk(item, active) for item in node]
        if not isinstance(node, dict):
            return node
        siblings = {key: walk(value, active) for key, value in node.items() if key != "$ref"}
        ref = node.get("$ref")
        if ref is None:
            return siblings
        if not isinstance(ref, str) or not ref.startswith("#/"):
            raise BundleError(f"reference {ref!r} is not an internal pointer")
        if ref in active:
            raise BundleError(f"reference cycle through {ref}")
        try:
            target = walk(_node_at(document, ref.removeprefix("#")), (*active, ref))
        except (KeyError, IndexError, ValueError, TypeError) as error:
            raise BundleError(f"reference {ref} does not resolve") from error
        if not siblings:
            return target
        if not isinstance(target, dict):
            raise BundleError(f"reference {ref} has sibling keywords but resolves to a non-mapping")
        return {**target, **siblings}

    return walk(document, ())


# -- the library reading (no resolver code below this line until the resolver reading) --


def _library_instance(raw: Any, schema_file: Path) -> Any:
    """An example as the library reading sees it: a literal, or the file a lone ``$ref`` names, loaded as plain YAML."""
    if isinstance(raw, dict) and set(raw) == {"$ref"} and isinstance(raw["$ref"], str):
        target = (schema_file.parent / unquote(raw["$ref"].partition("#")[0])).resolve()
        return yaml.safe_load(target.read_text(encoding="utf-8"))
    return raw


def _library_validator(root: Path, schema_file: Path) -> Draft202012Validator:
    base = root.resolve()

    def retrieve(uri: str) -> Resource[Any]:
        path = (base / unquote(uri.removeprefix(LIBRARY_BASE_URI))).resolve()
        if base != path and base not in path.parents:
            raise FileNotFoundError(uri)
        return Resource.from_contents(yaml.safe_load(path.read_text(encoding="utf-8")), default_specification=DRAFT202012)

    uri = LIBRARY_BASE_URI + quote(schema_file.resolve().relative_to(base).as_posix(), safe="/")
    return Draft202012Validator(
        {"$ref": uri},
        registry=Registry(retrieve=retrieve),  # type: ignore[call-arg]  # attrs private-field alias, the documented kwarg
        format_checker=FORMAT_CHECKER,
    )


# -- the resolver reading ------------------------------------------------------------------


def _resolver_schema(resolver: ModuleType, root: Path, schema_file: Path) -> dict[str, Any]:
    """The schema file as the resolver's dereferenced tree has it, reached through a throwaway root document.

    The throwaway root lies outside the contracts tree, so the resolver is told ``root`` is where refs may reach.
    """
    with tempfile.TemporaryDirectory() as scratch:
        relative = os.path.relpath(schema_file, scratch).replace(os.sep, "/")
        Path(scratch, "openapi.yaml").write_text(yaml.safe_dump({"schema": {"$ref": quote(relative, safe="/")}}), encoding="utf-8")
        tree = resolver.resolve(scratch, roots=(root,)).tree
    schema: dict[str, Any] = tree["schema"]
    return schema


def cross_check_examples(root: Path, module_dir: Path, resolver_module: str = "contract_resolver") -> list[ExampleVerdict]:
    """Validate every ``examples`` entry of every schema file of the module under both readings."""
    resolver = importlib.import_module(resolver_module)
    verdicts: list[ExampleVerdict] = []
    schemas_dir = module_dir / "schemas"
    for schema_file in sorted(schemas_dir.glob("*.yaml")) if schemas_dir.is_dir() else []:
        raw = yaml.safe_load(schema_file.read_text(encoding="utf-8"))
        if schema_file.name == "_index.yaml" or not isinstance(raw, dict) or not isinstance(raw.get("examples"), list):
            continue
        resolved = _resolver_schema(resolver, root, schema_file)
        resolver_validator = Draft202012Validator({key: value for key, value in resolved.items() if key != "examples"}, format_checker=FORMAT_CHECKER)
        library_validator = _library_validator(root, schema_file)
        name = schema_file.relative_to(module_dir).as_posix()
        for index, (via_resolver, via_files) in enumerate(zip(resolved.get("examples", []), raw["examples"], strict=False)):
            instance = _library_instance(via_files, schema_file)
            verdicts.append(ExampleVerdict(name, index, resolver_validator.is_valid(via_resolver), library_validator.is_valid(instance)))
    return verdicts


# -- the script ----------------------------------------------------------------------------


def _cross_check(root: Path, module: Path, resolver_module: str, totals: Totals) -> None:
    verdicts = cross_check_examples(root, module, resolver_module)
    totals.examples_cross_checked += len(verdicts)
    for verdict in verdicts:
        if verdict.resolver_valid != verdict.library_valid:
            totals.findings.append(
                f"CONTRACT-CHECK {CHECK_NAME}: INDEPENDENT_DEREF_DISAGREES: {module.name}: {verdict.schema} example {verdict.index}: "
                f"resolver tree says {'valid' if verdict.resolver_valid else 'invalid'}, library says {'valid' if verdict.library_valid else 'invalid'}"
            )


def _load(path: Path) -> dict[str, Any] | None:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None
    return loaded if isinstance(loaded, dict) and loaded else None


def _compare_inventories(module: Path, resolution: Any, args: argparse.Namespace, totals: Totals) -> tuple[str, str] | None:
    """Compare the written bundle with the Java view. Returns ``(code, detail)`` when the check cannot do its job, else ``None``."""
    bundle_file = args.bundles / "bundle" / module.name / bundle.ROOT_DOCUMENT
    view_file = args.bundles / "javaview" / module.name / bundle.ROOT_DOCUMENT
    written, view = _load(bundle_file), _load(view_file)
    if written is None:
        return "BUNDLE_MISSING_OR_EMPTY", f"{module.name}: {bundle_file} is missing or empty (run bundle.py first)"
    if view is None:
        return "BUNDLE_MISSING_OR_EMPTY", f"{module.name}: the Java view {view_file} is missing or empty (the Gradle javaView task did not write it)"
    counts = resolution.counts
    bundle_paths = written.get("paths")
    bundle_count = len(bundle_paths) if isinstance(bundle_paths, dict) else 0
    floors = [
        (counts["path_items"] < args.min_paths, f"{counts['path_items']} path items in the tree"),
        (bundle_count < args.min_paths, f"{bundle_count} path items in the bundle"),
        (counts["schemas"] == 0, "zero schemas resolved"),
        (counts["refs_resolved"] == 0, "zero references resolved"),
    ]
    below = [text for failed, text in floors if failed]
    if below:
        return "BELOW_FLOOR", f"{module.name}: {SEPARATOR.join(below)} (floor {args.min_paths})"
    if written != resolution.tree:
        totals.findings.append(f"CONTRACT-CHECK {CHECK_NAME}: BUNDLE_STALE: {module.name}: {bundle_file.name} is not the resolver's tree of the split files")
        return None
    try:
        mine, theirs = inventory(written), inventory(view)
    except BundleError as error:
        totals.findings.append(f"CONTRACT-CHECK {CHECK_NAME}: VIEW_UNREADABLE: {module.name}: {error}")
        return None
    totals.operations += len(mine.operations)
    totals.parameters += len(mine.parameters)
    totals.responses += len(mine.responses)
    totals.schema_names += len(mine.schema_names)
    totals.findings.extend(compare_inventories(module.name, mine, theirs))
    return None


def run(argv: Sequence[str] | None = None, *, out: Callable[[str], None] = print, resolver_module: str = "contract_resolver") -> int:
    parser = argparse.ArgumentParser(description="Compare the Java view's inventory with the resolver-written bundle and cross-check every example.")
    parser.add_argument("--root", default="contracts", type=Path)
    parser.add_argument("--bundles", required=True, type=Path, help="the --out directory bundle.py staged into")
    parser.add_argument("--module", action="append", default=[], help="restrict to this module (repeatable)")
    parser.add_argument("--min-paths", type=int, default=DEFAULT_MIN_PATHS)
    parser.add_argument("--examples-only", action="store_true", help="run the independent dereference check without a bundle")
    args = parser.parse_args(argv)

    totals = Totals()

    def blocked(code: str, detail: str) -> int:
        out(f"CONTRACT-CHECK {CHECK_NAME}: {code}: {detail}")
        out(totals.counts_line())
        return 2

    try:
        resolver = importlib.import_module(resolver_module)
    except ImportError as error:
        return blocked("RESOLVER_IMPORT_FAILED", f"{resolver_module}: {error}")

    modules, _ = bundle.discover_modules(args.root)
    if args.module:
        modules = [module for module in modules if module.name in args.module]
    if not modules:
        return blocked("NO_MODULE", f"no module with a root {bundle.ROOT_DOCUMENT} under {args.root}")

    for module in modules:
        try:
            resolution = resolver.resolve(module)
        except resolver.ResolveError as error:
            totals.findings.append(f"CONTRACT-CHECK {CHECK_NAME}: RESOLVE_FAILED: {module.name}: {error}")
            continue
        for key in ("path_items", "schemas", "refs_resolved"):
            setattr(totals, key, getattr(totals, key) + resolution.counts[key])
        _cross_check(args.root, module, resolver_module, totals)
        if args.examples_only:
            continue
        stop = _compare_inventories(module, resolution, args, totals)
        if stop is not None:
            return blocked(*stop)

    for line in totals.findings:
        out(line)
    out(totals.counts_line())
    return 1 if totals.findings else 0


if __name__ == "__main__":
    sys.exit(run())
