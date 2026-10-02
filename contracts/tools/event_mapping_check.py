"""Event-mapping check for the event stream of a contract module (spec FR-007, FR-025).

OpenAPI 3.1 has no native way to name the events of a stream, so the stream operation (the one whose 200
response is ``text/event-stream``) documents the mapping as bullet lines in its description, one per event:

    - `status-transition` -> StatusTransitionEvent: <prose>

and lists the data schemas as the ``oneOf`` branches of the response schema. This check parses the bullet
lines (``- `name` -> Schema``) and compares them with the branch titles, through the single resolver. It
fails (exit 1, ``CONTRACT-CHECK event_mapping_check: <CODE>: <module>:<name or schema>: <detail>``) when:

* ``NAME_WITHOUT_SCHEMA``: a name maps to a schema that is not a branch of the response schema.
* ``SCHEMA_WITHOUT_NAME``: a branch schema is named by no bullet line.
* ``SCHEMA_MULTI_NAME``: one schema is named by more than one event name.

Informational, never a failure and never a change of exit status: ``LIFECYCLE_TYPE_NOT_FORWARDED: <type>``
for each member of the runtime's ``LIFECYCLE_EVENT_TYPES`` that is not one of the contract-owned allow-list
(the ``eventType`` enum of ``MissionLifecycleEvent``). The runtime set is read from
``src/specify_cli/status/lifecycle_events.py`` by parsing the syntax tree, never by importing it
(``--lifecycle-source`` overrides the path; ``--repo-root`` is where the default lives).

Cannot do its job (exit 2): ``NO_MODULE``, ``RESOLVE_FAILED``, ``ZERO_EVENT_NAMES`` (no event name found in any
stream operation, including a module with no stream at all), ``LIFECYCLE_SOURCE_UNREADABLE``. The last line is
always ``counts: event_names=N event_schemas=N lifecycle_not_forwarded=N``.

Run as a bare script from the repository root
(``python contracts/tools/event_mapping_check.py [--root DIR] [--module NAME] [--repo-root DIR]``).
Standard library plus PyYAML; imports only sibling modules.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import contract_resolver

CHECK_NAME = "event_mapping_check"
NON_MODULE_DIRECTORIES = frozenset({"_shared", "fixtures", "gradle", "tools", "build", "node_modules"})
ROOT_DOCUMENT = "openapi.yaml"
STREAM_MEDIA_TYPE = "text/event-stream"
HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
LIFECYCLE_SCHEMA = "MissionLifecycleEvent"
LIFECYCLE_PROPERTY = "eventType"
LIFECYCLE_CONSTANT = "LIFECYCLE_EVENT_TYPES"
DEFAULT_LIFECYCLE_SOURCE = Path("src") / "specify_cli" / "status" / "lifecycle_events.py"
_MAPPING_LINE = re.compile(r"^\s*[-*]\s+`([^`\s]+)`\s*->\s*([A-Za-z][A-Za-z0-9_]*)")


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
    info: list[Finding] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=lambda: {"event_names": 0, "event_schemas": 0, "lifecycle_not_forwarded": 0})

    @property
    def exit_code(self) -> int:
        if self.blocked:
            return 2
        return 1 if self.findings else 0

    def counts_line(self) -> str:
        return "counts: " + " ".join(f"{key}={value}" for key, value in self.counts.items())


def read_lifecycle_types(source: Path) -> set[str]:
    """The members of ``LIFECYCLE_EVENT_TYPES`` in ``source``, found by parsing it (names resolve to module-level strings)."""
    tree = ast.parse(source.read_text(encoding="utf-8"))
    constants: dict[str, str] = {}
    members: set[str] | None = None
    for statement in tree.body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1 or not isinstance(statement.targets[0], ast.Name):
            continue
        name, value = statement.targets[0].id, statement.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            constants[name] = value.value
        elif name == LIFECYCLE_CONSTANT:
            collection = value.args[0] if isinstance(value, ast.Call) and value.args else value
            if not isinstance(collection, ast.Set | ast.List | ast.Tuple):
                raise ValueError(f"{LIFECYCLE_CONSTANT} is not a set, list or tuple of names")
            members = set()
            for element in collection.elts:
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    members.add(element.value)
                elif isinstance(element, ast.Name) and element.id in constants:
                    members.add(constants[element.id])
                else:
                    raise ValueError(f"a member of {LIFECYCLE_CONSTANT} is neither a string nor a module-level string constant")
    if not members:
        raise ValueError(f"{LIFECYCLE_CONSTANT} was not found or is empty in {source}")
    return members


def discover_modules(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and p.name not in NON_MODULE_DIRECTORIES and not p.name.startswith(".") and (p / ROOT_DOCUMENT).is_file())


def stream_operations(tree: dict[str, Any]) -> list[tuple[str, dict[str, Any], list[dict[str, Any]]]]:
    """Each stream operation as ``(label, operation, response schemas)``."""
    found: list[tuple[str, dict[str, Any], list[dict[str, Any]]]] = []
    paths = tree.get("paths")
    for path_key, item in paths.items() if isinstance(paths, dict) else []:
        for method in HTTP_METHODS:
            operation = item.get(method) if isinstance(item, dict) else None
            responses = operation.get("responses") if isinstance(operation, dict) else None
            schemas: list[dict[str, Any]] = []
            for response in responses.values() if isinstance(responses, dict) else []:
                content = response.get("content") if isinstance(response, dict) else None
                body = content.get(STREAM_MEDIA_TYPE) if isinstance(content, dict) else None
                if isinstance(body, dict) and isinstance(body.get("schema"), dict):
                    schemas.append(body["schema"])
            if schemas and isinstance(operation, dict):
                found.append((f"{method.upper()} {path_key}", operation, schemas))
    return found


def branch_titles(schema: dict[str, Any]) -> list[str]:
    """The titles of the schemas a stream response offers: the ``oneOf``/``anyOf`` branches, or the schema itself."""
    branches = schema.get("oneOf") or schema.get("anyOf")
    candidates = branches if isinstance(branches, list) else [schema]
    return [branch["title"] for branch in candidates if isinstance(branch, dict) and isinstance(branch.get("title"), str)]


def lifecycle_allow_list(tree: dict[str, Any]) -> set[str]:
    """The ``eventType`` enum of the lifecycle schema wherever it appears in the resolved tree."""
    found: set[str] = set()

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("title") == LIFECYCLE_SCHEMA:
                properties = node.get("properties")
                values = (
                    properties.get(LIFECYCLE_PROPERTY, {}).get("enum")
                    if isinstance(properties, dict) and isinstance(properties.get(LIFECYCLE_PROPERTY), dict)
                    else None
                )
                if isinstance(values, list):
                    found.update(str(value) for value in values)
            for key, value in node.items():
                if key not in {"examples", "example"}:
                    visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(tree)
    return found


class _Check:
    def __init__(self, root: Path, repo_root: Path, modules: tuple[str, ...], lifecycle_source: Path | None) -> None:
        self.root = root
        self.selected = modules
        self.lifecycle_source = lifecycle_source if lifecycle_source is not None else repo_root / DEFAULT_LIFECYCLE_SOURCE
        self.report = Report()
        self.allow: set[str] = set()

    def add(self, code: str, module: str, subject: str, detail: str) -> None:
        self.report.findings.append(Finding(code, f"{module}:{subject}", detail))

    def run(self) -> Report:
        modules = [m for m in discover_modules(self.root) if not self.selected or m.name in self.selected]
        if not modules:
            self.report.blocked.append(Finding("NO_MODULE", str(self.root), "no module (a directory with a root openapi.yaml) was found"))
            return self.report
        for module in modules:
            self.check_module(module)
        counts = self.report.counts
        if counts["event_names"] == 0 and not self.report.blocked:
            self.report.blocked.append(Finding("ZERO_EVENT_NAMES", str(self.root), "no event name was found in the description of any stream operation"))
        if not self.report.blocked:
            self.lifecycle()
        return self.report

    def check_module(self, module: Path) -> None:
        try:
            tree = contract_resolver.resolve(module).tree
        except contract_resolver.ResolveError as error:
            self.report.blocked.append(Finding("RESOLVE_FAILED", module.name, str(error)))
            return
        self.allow |= lifecycle_allow_list(tree)
        for _label, operation, schemas in stream_operations(tree):
            names = [(match.group(1), match.group(2)) for line in str(operation.get("description", "")).splitlines() if (match := _MAPPING_LINE.match(line))]
            titles = [title for schema in schemas for title in branch_titles(schema)]
            self.report.counts["event_names"] += len(names)
            self.report.counts["event_schemas"] += len(set(titles))
            self.compare(module.name, names, set(titles))

    def compare(self, module: str, names: list[tuple[str, str]], titles: set[str]) -> None:
        named: dict[str, list[str]] = defaultdict(list)
        for name, schema in names:
            named[schema].append(name)
            if schema not in titles:
                self.add("NAME_WITHOUT_SCHEMA", module, name, f"maps to {schema}, which is not one of the response schemas ({', '.join(sorted(titles)) or 'none'})")
        for schema in sorted(titles):
            if schema not in named:
                self.add("SCHEMA_WITHOUT_NAME", module, schema, "is a response schema that no event name maps to")
        for schema, schema_names in sorted(named.items()):
            if len(schema_names) > 1 and schema in titles:
                self.add("SCHEMA_MULTI_NAME", module, schema, f"is named by more than one event name: {', '.join(schema_names)}")

    def lifecycle(self) -> None:
        try:
            types = read_lifecycle_types(self.lifecycle_source)
        except (OSError, SyntaxError, ValueError) as error:
            self.report.blocked.append(Finding("LIFECYCLE_SOURCE_UNREADABLE", str(self.lifecycle_source), f"{type(error).__name__}: {error}"))
            return
        for name in sorted(types - self.allow):
            self.report.info.append(Finding("LIFECYCLE_TYPE_NOT_FORWARDED", name, "is a runtime lifecycle type the contract's lifecycle event does not forward"))
        self.report.counts["lifecycle_not_forwarded"] = len(self.report.info)


def check(root: str | Path, modules: tuple[str, ...] = (), repo_root: str | Path = ".", lifecycle_source: str | Path | None = None) -> Report:
    """Run the event-mapping check over the modules under ``root``."""
    return _Check(Path(root), Path(repo_root), tuple(modules), Path(lifecycle_source) if lifecycle_source is not None else None).run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check that every event name maps to one schema and every schema to one name.")
    parser.add_argument("--root", default="contracts", help="contracts root (default: contracts)")
    parser.add_argument("--repo-root", default=".", help="repository root holding the runtime lifecycle module (default: .)")
    parser.add_argument("--lifecycle-source", default=None, help="path of the runtime lifecycle module (default: under --repo-root)")
    parser.add_argument("--module", action="append", default=[], help="restrict to this module (repeatable)")
    arguments = parser.parse_args(argv)
    report = check(arguments.root, tuple(arguments.module), arguments.repo_root, arguments.lifecycle_source)
    for finding in (*report.blocked, *report.findings, *report.info):
        print(finding.render())
    print(report.counts_line())
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
