"""Example validation and orphan-example check (spec FR-013, FR-025, D-15).

Every example of a module must validate against the schema that carries it, with the one date-time policy
of ``schema_formats.FORMAT_CHECKER``; every file under ``examples/`` must be used; and the examples the
module is required to carry must be there. The module is read through the single resolver, so a schema is
looked up in the resolved tree by its ``title`` and validated as consumers see it.

Convention: a schema file lists its examples under ``examples:``, each entry an inline instance or a lone
``$ref`` to a file under ``examples/`` that holds the bare instance.

Failure codes (exit 1), printed ``CONTRACT-CHECK example_check: <CODE>: <module>:<example>: <detail>``:

* ``EXAMPLE_INVALID``: an example does not validate (a missing or extra property, a wrong type, a malformed
  ``date-time``); one finding per validation error.
* ``ORPHAN_EXAMPLE``: a file in ``examples/`` is referenced by nothing.
* ``EXAMPLE_VALIDATES_NOTHING``: an example is referenced but checked against no real schema: it is attached
  to a schema no path reaches, to a schema that constrains nothing, or it is referenced from a file that
  is not a schema's ``examples``.
* ``REQUIRED_EXAMPLE_MISSING``: the required-example manifest names a ``(schema, example file)`` pair that
  no validated example provides.

The manifest (``--manifest``, default ``fixtures/example_check/required_examples.json`` next to this
script) is ``{"modules": {"<module>": [{"schema": ..., "example": ..., "reason": ...}, ...]}}``. Cannot do
its job (exit 2): ``NO_MODULE``, ``RESOLVE_FAILED``, ``MANIFEST_UNREADABLE``, ``MANIFEST_MODULE_MISSING`` (a
module without an entry), ``MANIFEST_EMPTY`` (an entry that requires nothing), ``ZERO_EXAMPLES``. The last
line is always ``counts: examples=N validated=N`` (examples found; examples that validated against a real
schema).

Run as a bare script (``python contracts/tools/example_check.py [--root DIR] [--manifest FILE] [--module NAME]``).
Standard library plus PyYAML and jsonschema; imports only sibling modules.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import yaml
from jsonschema import Draft202012Validator

import contract_resolver
from schema_formats import FORMAT_CHECKER

CHECK_NAME = "example_check"
NON_MODULE_DIRECTORIES = frozenset({"_shared", "fixtures", "gradle", "tools", "build", "node_modules"})
ROOT_DOCUMENT = "openapi.yaml"
EXAMPLES_DIRECTORY = "examples"
INDEX_NAME = "_index.yaml"
DEFAULT_MANIFEST = Path(__file__).resolve().parent / "fixtures" / "example_check" / "required_examples.json"
YAML_SUFFIXES = (".yaml", ".yml")
# JSON Schema keywords that constrain an instance; a schema with none of them accepts anything.
CONSTRAINT_KEYWORDS = frozenset(
    {
        "type",
        "properties",
        "required",
        "enum",
        "const",
        "allOf",
        "anyOf",
        "oneOf",
        "not",
        "items",
        "prefixItems",
        "pattern",
        "format",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "uniqueItems",
        "multipleOf",
        "additionalProperties",
        "unevaluatedProperties",
        "patternProperties",
        "minProperties",
        "maxProperties",
        "if",
        "contains",
    }
)


@dataclass(frozen=True)
class Finding:
    code: str
    subject: str
    detail: str

    def render(self) -> str:
        return f"CONTRACT-CHECK {CHECK_NAME}: {self.code}: {self.subject}: {self.detail}"


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    blocked: list[Finding] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=lambda: {"examples": 0, "validated": 0})

    @property
    def exit_code(self) -> int:
        if self.blocked:
            return 2
        return 1 if self.findings else 0

    def counts_line(self) -> str:
        return "counts: " + " ".join(f"{key}={value}" for key, value in self.counts.items())


def discover_modules(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and p.name not in NON_MODULE_DIRECTORIES and not p.name.startswith(".") and (p / ROOT_DOCUMENT).is_file())


def _yaml_files(directory: Path) -> list[Path]:
    return sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix in YAML_SUFFIXES) if directory.is_dir() else []


def _collect_refs(node: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                refs.append(value)
            else:
                refs.extend(_collect_refs(value))
    elif isinstance(node, list):
        for item in node:
            refs.extend(_collect_refs(item))
    return refs


def _schemas_with_examples(tree: Any, found: dict[str, dict[str, Any]]) -> None:
    """Index the resolved schema nodes that carry an ``examples`` list, by ``title`` (first one wins)."""
    if isinstance(tree, list):
        for item in tree:
            _schemas_with_examples(item, found)
    elif isinstance(tree, dict):
        title = tree.get("title")
        if isinstance(title, str) and isinstance(tree.get("examples"), list):
            found.setdefault(title, tree)
        for key, value in tree.items():
            if key not in {"examples", "example", "default", "enum", "const"}:
                _schemas_with_examples(value, found)


def is_vacuous(schema: dict[str, Any]) -> bool:
    """True when the schema holds no keyword that constrains an instance."""
    return not CONSTRAINT_KEYWORDS & set(schema)


def _referenced_examples(module: Path) -> set[str]:
    """Names of the files under ``examples/`` that any YAML file of the module refers to with a ``$ref``."""
    examples_dir = (module / EXAMPLES_DIRECTORY).resolve()
    referenced: set[str] = set()
    for path in _yaml_files(module):
        if examples_dir in path.resolve().parents:
            continue
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        for ref in _collect_refs(document):
            target = (path.parent / unquote(ref.partition("#")[0])).resolve() if ref.partition("#")[0] else path.resolve()
            if target.parent == examples_dir:
                referenced.add(target.name)
    return referenced


@dataclass(frozen=True)
class RawExample:
    schema: str
    index: int
    file: str | None  # file name under examples/, or None for an inline instance

    @property
    def subject(self) -> str:
        return f"{EXAMPLES_DIRECTORY}/{self.file}" if self.file else f"{self.schema}#examples[{self.index}]"


def _raw_examples(module: Path) -> list[RawExample]:
    """The entries of every schema file's ``examples`` list, in order."""
    found: list[RawExample] = []
    for path in _yaml_files(module / "schemas"):
        if path.name == INDEX_NAME:
            continue
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        entries = document.get("examples") if isinstance(document, dict) else None
        title = document.get("title") if isinstance(document, dict) else None
        if not isinstance(entries, list) or not isinstance(title, str):
            continue
        for position, entry in enumerate(entries):
            ref = entry.get("$ref") if isinstance(entry, dict) and set(entry) == {"$ref"} else None
            target = (path.parent / unquote(ref.partition("#")[0])).resolve() if isinstance(ref, str) else None
            in_examples = target is not None and target.parent == (module / EXAMPLES_DIRECTORY).resolve()
            found.append(RawExample(title, position, target.name if in_examples and target is not None else None))
    return found


def load_manifest(path: Path) -> tuple[dict[str, list[dict[str, str]]] | None, str]:
    """The manifest's per-module requirements, or ``None`` and the reason it cannot be read."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        modules = document["modules"]
        if not isinstance(modules, dict):
            raise TypeError("modules is not a mapping")
        return {str(name): list(entries) for name, entries in modules.items()}, ""
    except (OSError, ValueError, KeyError, TypeError) as error:
        return None, f"{path}: {type(error).__name__}: {error}"


class _Check:
    def __init__(self, root: Path, manifest: Path, modules: tuple[str, ...]) -> None:
        self.root = root
        self.manifest_path = manifest
        self.selected = modules
        self.report = Report()

    def add(self, code: str, module: str, subject: str, detail: str) -> None:
        self.report.findings.append(Finding(code, f"{module}:{subject}", detail))

    def block(self, code: str, subject: str, detail: str) -> None:
        self.report.blocked.append(Finding(code, subject, detail))

    def run(self) -> Report:
        modules = [m for m in discover_modules(self.root) if not self.selected or m.name in self.selected]
        if not modules:
            self.block("NO_MODULE", str(self.root), "no module (a directory with a root openapi.yaml) was found")
            return self.report
        manifest, problem = load_manifest(self.manifest_path)
        if manifest is None:
            self.block("MANIFEST_UNREADABLE", str(self.manifest_path), problem)
            return self.report
        for module in modules:
            self.check_module(module, manifest)
        if self.report.counts["examples"] == 0 and not self.report.blocked:
            self.block("ZERO_EXAMPLES", str(self.root), "no example was found under any schema's examples")
        return self.report

    def check_module(self, module: Path, manifest: dict[str, list[dict[str, str]]]) -> None:
        try:
            tree = contract_resolver.resolve(module).tree
        except contract_resolver.ResolveError as error:
            self.block("RESOLVE_FAILED", module.name, str(error))
            return
        required = manifest.get(module.name)
        if required is None:
            self.block("MANIFEST_MODULE_MISSING", module.name, f"{self.manifest_path.name} has no entry for the module")
            return
        if not required:
            self.block("MANIFEST_EMPTY", module.name, "the manifest entry for the module requires no example")
            return
        nodes: dict[str, dict[str, Any]] = {}
        _schemas_with_examples(tree, nodes)
        raws = _raw_examples(module)
        checked = self.validate(module, nodes, raws)
        attached = {raw.file for raw in raws if raw.file is not None}
        referenced = _referenced_examples(module)
        for path in sorted((module / EXAMPLES_DIRECTORY).glob("*")) if (module / EXAMPLES_DIRECTORY).is_dir() else []:
            if path.is_file() and path.name != INDEX_NAME and path.name not in referenced:
                self.add("ORPHAN_EXAMPLE", module.name, f"{EXAMPLES_DIRECTORY}/{path.name}", "no schema or operation refers to this file")
        for name in sorted(referenced - attached):
            self.add(
                "EXAMPLE_VALIDATES_NOTHING", module.name, f"{EXAMPLES_DIRECTORY}/{name}", "referenced, but not as an example of a schema, so nothing validates it"
            )
        for entry in required:
            pair = (str(entry.get("schema")), str(entry.get("example")))
            if pair not in checked:
                self.add(
                    "REQUIRED_EXAMPLE_MISSING",
                    module.name,
                    f"{pair[0]}:{pair[1]}",
                    f"the manifest requires this example ({entry.get('reason', 'no reason given')}) and no validated example provides it",
                )

    def validate(self, module: Path, nodes: dict[str, dict[str, Any]], raws: list[RawExample]) -> set[tuple[str, str]]:
        """Validate every raw example; return the ``(schema, file)`` pairs that were checked against a real schema."""
        done: set[tuple[str, str]] = set()
        for raw in raws:
            self.report.counts["examples"] += 1
            node = nodes.get(raw.schema)
            if node is None:
                self.add("EXAMPLE_VALIDATES_NOTHING", module.name, raw.subject, f"schema {raw.schema} is reached by no path of the module")
                continue
            if is_vacuous(node):
                self.add("EXAMPLE_VALIDATES_NOTHING", module.name, raw.subject, f"schema {raw.schema} constrains nothing")
                continue
            instances = node["examples"]
            instance = instances[raw.index] if raw.index < len(instances) else None
            errors = sorted(
                Draft202012Validator(node, format_checker=FORMAT_CHECKER).iter_errors(instance), key=lambda error: [str(part) for part in error.absolute_path]
            )
            for error in errors:
                where = "/".join(str(part) for part in error.absolute_path) or "(root)"
                self.add("EXAMPLE_INVALID", module.name, raw.subject, f"against {raw.schema} at {where}: {error.message}")
            if not errors:
                self.report.counts["validated"] += 1
            if raw.file is not None:
                done.add((raw.schema, raw.file))
        return done


def check(root: str | Path, manifest: str | Path = DEFAULT_MANIFEST, modules: tuple[str, ...] = ()) -> Report:
    """Run the example check over the modules under ``root`` against the required-example ``manifest``."""
    return _Check(Path(root), Path(manifest), tuple(modules)).run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate every example and find orphan examples.")
    parser.add_argument("--root", default="contracts", help="contracts root (default: contracts)")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="required-example manifest (default: the committed one)")
    parser.add_argument("--module", action="append", default=[], help="restrict to this module (repeatable)")
    arguments = parser.parse_args(argv)
    report = check(arguments.root, arguments.manifest, tuple(arguments.module))
    for finding in (*report.blocked, *report.findings):
        print(finding.render())
    print(report.counts_line())
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
