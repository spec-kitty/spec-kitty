"""Compare the Java generator's bundle with the Python resolver's tree, and read every example twice (FR-019, plan D-P2).

Every content check reads the resolver's dereferenced tree, so this script is the
evidence that the tree is what a second implementation makes of the same files. It
is a **consistency check, never an independent proof**: when the generator and the
resolver read a construct the same wrong way it cannot tell. The independent
dereference check narrows that gap.

*Tree comparison.* The bundle (``<bundles>/bundle/<module>/openapi.yaml``, staged by
``bundle.py``) is dereferenced through its internal ``$ref`` values; its
``components`` container (a generator artefact: the schemas it holds are already
inlined where used) is set aside. Both trees are then passed through the named
:data:`NORMALISATIONS` and compared ignoring key order. The list starts empty and
gains an entry only from an observed generator behaviour, each naming the construct
and the behaviour with a planted test; at most :data:`MAX_NORMALISATIONS`.
A normalisation that drops information is a decision for the maintainers, not an
entry.

*Independent dereference check.* Every example under a schema file's ``examples``
keyword is validated twice: once against the schema as the resolver's tree has it,
and once with ``jsonschema`` and a ``referencing.Registry`` that retrieves the split
files itself (no code from ``contract_resolver.py``). Both use
``schema_formats.FORMAT_CHECKER``. The verdicts must agree for every example, invalid
planted ones included: agreement on "invalid" is not a failure here (that is
``example_check``'s job), disagreement is.

Failure codes (exit 1), printed ``CONTRACT-CHECK resolver_parity: <CODE>: <module>: <detail>``:
``TREE_DIFFERS`` (first differing JSON pointer; every one with ``--report-all``),
``UNDOCUMENTED_NORMALISATION``, ``NORMALISATION_CAP_EXCEEDED``,
``INDEPENDENT_DEREF_DISAGREES``, ``RESOLVE_FAILED`` (the resolver refused the
module). Cannot do its job (exit 2): ``RESOLVER_IMPORT_FAILED``,
``BUNDLE_MISSING_OR_EMPTY``, ``BELOW_FLOOR`` (fewer than ``--min-paths`` path items
in the tree or the bundle, zero schemas, zero resolved references) and ``NO_MODULE``.
The last line is always
``counts: path_items=N schemas=N refs_resolved=N normalisations=N examples_cross_checked=N``.

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
MAX_NORMALISATIONS = 8
DEFAULT_MIN_PATHS = 5
MAX_REPORTED_DIFFERENCES = 200
SHORT_VALUE_LENGTH = 80
LIBRARY_BASE_URI = "https://contract.invalid/"
BUNDLE_ONLY_KEYS = frozenset({"components"})


@dataclass(frozen=True)
class Normalisation:
    """A documented, observed generator rewrite, applied to both trees before they are compared."""

    name: str
    construct: str
    behaviour: str
    planted_test: str
    apply: Callable[[Any], Any]


# Starts empty. An entry is added only from a pushed spike run that observed the behaviour.
NORMALISATIONS: tuple[Normalisation, ...] = ()


@dataclass(frozen=True)
class ExampleVerdict:
    schema: str
    index: int
    resolver_valid: bool
    library_valid: bool


@dataclass
class Totals:
    path_items: int = 0
    schemas: int = 0
    refs_resolved: int = 0
    normalisations: int = 0
    examples_cross_checked: int = 0
    findings: list[str] = field(default_factory=list)

    def counts_line(self) -> str:
        return (
            f"counts: path_items={self.path_items} schemas={self.schemas} refs_resolved={self.refs_resolved} "
            f"normalisations={self.normalisations} examples_cross_checked={self.examples_cross_checked}"
        )


class BundleError(Exception):
    """The bundle could not be dereferenced (a reference that does not resolve, or a cycle)."""


# -- comparison -----------------------------------------------------------------------


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _same_scalar(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return bool(left == right)
    return type(left) is type(right) and bool(left == right)


def all_differences(left: Any, right: Any, pointer: str = "", limit: int = MAX_REPORTED_DIFFERENCES) -> list[str]:
    """JSON pointers of the places where ``left`` and ``right`` differ, ignoring key order; at most ``limit``."""
    found: list[str] = []

    def walk(a: Any, b: Any, here: str) -> None:
        if len(found) >= limit:
            return
        if isinstance(a, dict) and isinstance(b, dict):
            if set(a) != set(b):
                found.append(here)
                return
            for key in sorted(a, key=str):
                walk(a[key], b[key], f"{here}/{_escape(str(key))}")
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                found.append(here)
                return
            for index, (x, y) in enumerate(zip(a, b, strict=True)):
                walk(x, y, f"{here}/{index}")
        elif isinstance(a, (dict, list)) or isinstance(b, (dict, list)) or not _same_scalar(a, b):
            found.append(here)

    walk(left, right, pointer)
    return found


def first_difference(left: Any, right: Any) -> str | None:
    """The first differing JSON pointer (keys visited in sorted order), or ``None`` when the trees are equal."""
    found = all_differences(left, right, limit=1)
    return found[0] if found else None


def _node_at(document: Any, pointer: str) -> Any:
    node = document
    for raw in pointer.split("/")[1:] if pointer else []:
        token = raw.replace("~1", "/").replace("~0", "~")
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


def _short(value: Any) -> str:
    text = repr(value)
    return text if len(text) <= SHORT_VALUE_LENGTH else text[: SHORT_VALUE_LENGTH - 3] + "..."


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


def _check_registry(normalisations: Sequence[Normalisation], report: Callable[[str], None]) -> bool:
    ok = True
    if len(normalisations) > MAX_NORMALISATIONS:
        report(f"CONTRACT-CHECK {CHECK_NAME}: NORMALISATION_CAP_EXCEEDED: {len(normalisations)} normalisations, the cap is {MAX_NORMALISATIONS}")
        ok = False
    for entry in normalisations:
        missing = [name for name in ("construct", "behaviour", "planted_test") if not getattr(entry, name).strip()]
        if not entry.name.strip() or missing:
            report(f"CONTRACT-CHECK {CHECK_NAME}: UNDOCUMENTED_NORMALISATION: {entry.name}: no {', '.join(missing) or 'name'}")
            ok = False
    return ok


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


def _resolver_schema(resolver: ModuleType, schema_file: Path) -> dict[str, Any]:
    """The schema file as the resolver's dereferenced tree has it, reached through a throwaway root document."""
    with tempfile.TemporaryDirectory() as scratch:
        relative = os.path.relpath(schema_file, scratch).replace(os.sep, "/")
        Path(scratch, "openapi.yaml").write_text(yaml.safe_dump({"schema": {"$ref": quote(relative, safe="/")}}), encoding="utf-8")
        tree = resolver.resolve(scratch).tree
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
        resolved = _resolver_schema(resolver, schema_file)
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


def _compare_bundle(module: Path, resolution: Any, args: argparse.Namespace, active: Sequence[Normalisation], totals: Totals) -> tuple[str, str] | None:
    """Compare the module's bundle with its tree. Returns ``(code, detail)`` when the check cannot do its job, else ``None``."""
    bundle_file = args.bundles / "bundle" / module.name / bundle.ROOT_DOCUMENT
    document = yaml.safe_load(bundle_file.read_text(encoding="utf-8")) if bundle_file.is_file() else None
    if not isinstance(document, dict) or not document:
        return "BUNDLE_MISSING_OR_EMPTY", f"{module.name}: {bundle_file.name} is missing or empty under {args.bundles}"
    counts = resolution.counts
    bundle_paths = document.get("paths")
    bundle_count = len(bundle_paths) if isinstance(bundle_paths, dict) else 0
    floors = [
        (counts["path_items"] < args.min_paths, f"{counts['path_items']} path items in the tree"),
        (bundle_count < args.min_paths, f"{bundle_count} path items in the bundle"),
        (counts["schemas"] == 0, "zero schemas resolved"),
        (counts["refs_resolved"] == 0, "zero references resolved"),
    ]
    below = [text for failed, text in floors if failed]
    if below:
        return "BELOW_FLOOR", f"{module.name}: {'; '.join(below)} (floor {args.min_paths})"
    try:
        dereferenced = {key: value for key, value in deref_bundle(document).items() if key not in BUNDLE_ONLY_KEYS}
    except BundleError as error:
        totals.findings.append(f"CONTRACT-CHECK {CHECK_NAME}: TREE_DIFFERS: {module.name}: bundle cannot be dereferenced: {error}")
        return None
    tree: Any = resolution.tree
    for entry in active:
        tree, dereferenced = entry.apply(tree), entry.apply(dereferenced)
    for pointer in all_differences(tree, dereferenced, limit=MAX_REPORTED_DIFFERENCES if args.report_all else 1):
        try:
            detail = f" (tree {_short(_node_at(tree, pointer))}, bundle {_short(_node_at(dereferenced, pointer))})"
        except (KeyError, IndexError, ValueError, TypeError):
            detail = ""
        totals.findings.append(f"CONTRACT-CHECK {CHECK_NAME}: TREE_DIFFERS: {module.name}: {pointer}{detail}")
    return None


def run(
    argv: Sequence[str] | None = None,
    *,
    out: Callable[[str], None] = print,
    normalisations: Sequence[Normalisation] | None = None,
    resolver_module: str = "contract_resolver",
) -> int:
    parser = argparse.ArgumentParser(description="Compare the bundle with the resolver's tree and cross-check every example.")
    parser.add_argument("--root", default="contracts", type=Path)
    parser.add_argument("--bundles", required=True, type=Path, help="the --out directory bundle.py staged into")
    parser.add_argument("--module", action="append", default=[], help="restrict to this module (repeatable)")
    parser.add_argument("--min-paths", type=int, default=DEFAULT_MIN_PATHS)
    parser.add_argument("--report-all", action="store_true", help="list every differing pointer, not only the first")
    parser.add_argument("--examples-only", action="store_true", help="run the independent dereference check without a bundle")
    args = parser.parse_args(argv)
    active = NORMALISATIONS if normalisations is None else tuple(normalisations)

    totals = Totals(normalisations=len(active))

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
    if not _check_registry(active, totals.findings.append):
        for line in totals.findings:
            out(line)
        out(totals.counts_line())
        return 1

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
        stop = _compare_bundle(module, resolution, args, active, totals)
        if stop is not None:
            return blocked(*stop)

    for line in totals.findings:
        out(line)
    out(totals.counts_line())
    return 1 if totals.findings else 0


if __name__ == "__main__":
    sys.exit(run())
