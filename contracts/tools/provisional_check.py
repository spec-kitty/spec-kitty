"""Provisional-marking check for the contract modules under ``contracts/`` (spec FR-011, D-7, FR-025).

An ``x-provisional`` element is one whose shape is not settled. The marker is
``x-provisional: {open_decision: <text>}`` on a property, a schema, a parameter or an operation, and the
text must name what is undecided. This check reads each module through the single resolver and fails when:

* ``MISSING_MARKER``: a property named in :data:`REQUIRED_PROVISIONAL_PROPERTIES` (staleness and the next
  action, FR-011) has no ``x-provisional``.
* ``UNDESCRIBED_MARKER``: an ``x-provisional`` is not a mapping with an ``open_decision`` of at least
  :data:`MIN_DECISION_WORDS` words (``true``, an empty text, ``TBD`` and a mapping without the key all fail).
* ``NOT_NULLABLE``: a property named in :data:`REQUIRED_PROVISIONAL_PROPERTIES` cannot be null (``type``
  without ``null``, no ``null`` branch in ``oneOf``/``anyOf``), because a payload that cannot compute it
  must be able to say so (FR-011). Another property marked ``x-provisional`` (a contract-owned value set,
  say) says its shape is open, not that it may be absent, and is not required to be nullable.
* ``NOT_IN_CHANGELOG``: the element is not named in the module CHANGELOG's ``Provisional`` section (D-7).
  An element is named when its own name appears there as a whole word: the property name, the schema
  title, the parameter name, or the operation's path. A missing CHANGELOG or a missing ``Provisional``
  heading fails every element of the module.

Cannot do its job (exit 2): ``NO_MODULE``, ``RESOLVE_FAILED``, ``ZERO_PROVISIONAL`` (no ``x-provisional`` in
the modules at all). Output ``CONTRACT-CHECK provisional_check: <CODE>: <module>:<element>: <detail>`` per
violation and a last line ``counts: provisional_elements=N`` (distinct elements, counted once however
many paths of the resolved tree reach them).

Run as a bare script (``python contracts/tools/provisional_check.py [--root DIR] [--module NAME]``).
Standard library plus PyYAML; imports only sibling modules.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import contract_resolver

CHECK_NAME = "provisional_check"
NON_MODULE_DIRECTORIES = frozenset({"_shared", "fixtures", "gradle", "tools", "build", "node_modules"})
ROOT_DOCUMENT = "openapi.yaml"
CHANGELOG = "CHANGELOG.md"
PROVISIONAL_HEADING = "Provisional"
REQUIRED_PROVISIONAL_PROPERTIES: tuple[str, ...] = ("staleness", "nextAction")
MIN_DECISION_WORDS = 4
HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
DATA_KEYS = frozenset({"example", "examples", "default", "enum", "const"})
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


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
    counts: dict[str, int] = field(default_factory=lambda: {"provisional_elements": 0})

    @property
    def exit_code(self) -> int:
        if self.blocked:
            return 2
        return 1 if self.findings else 0

    def counts_line(self) -> str:
        return "counts: " + " ".join(f"{key}={value}" for key, value in self.counts.items())


@dataclass
class Element:
    label: str
    token: str
    kind: str  # property, schema, parameter, operation, other
    node: dict[str, Any]


def is_nullable(node: dict[str, Any]) -> bool:
    """True when ``null`` is a valid value: a ``null`` type, a type array holding it, or a ``null`` branch."""
    declared = node.get("type")
    if declared == "null" or (isinstance(declared, list) and "null" in declared):
        return True
    for keyword in ("oneOf", "anyOf"):
        branches = node.get(keyword)
        if isinstance(branches, list) and any(isinstance(branch, dict) and is_nullable(branch) for branch in branches):
            return True
    return False


class _Walk:
    """Collect every provisional element and every property named in the required list from a resolved tree."""

    def __init__(self, tree: dict[str, Any]) -> None:
        self.elements: dict[str, Element] = {}
        self.required: dict[str, dict[str, Any]] = {}
        self._visit(tree, ("root",), "", None)

    def _identify(self, node: dict[str, Any], pointer: tuple[str, ...], title: str, prop: str | None) -> tuple[str, str, str]:
        if prop is not None:
            return f"{title}.{prop}", prop, "property"
        if len(pointer) == 4 and pointer[1] == "paths" and pointer[3] in HTTP_METHODS:
            return f"{pointer[3].upper()} {pointer[2]}", pointer[2], "operation"
        if isinstance(node.get("name"), str) and "in" in node:
            return f"parameter {node['name']}", node["name"], "parameter"
        if isinstance(node.get("title"), str):
            return f"schema {node['title']}", node["title"], "schema"
        return "/".join(pointer[1:]), pointer[-1], "other"

    def _visit(self, node: Any, pointer: tuple[str, ...], title: str, prop: str | None) -> None:
        if isinstance(node, list):
            for position, item in enumerate(node):
                self._visit(item, (*pointer, str(position)), title, None)
            return
        if not isinstance(node, dict):
            return
        if prop in REQUIRED_PROVISIONAL_PROPERTIES and prop is not None:
            self.required.setdefault(f"{title}.{prop}", node)
        if "x-provisional" in node:
            label, token, kind = self._identify(node, pointer, title, prop)
            self.elements.setdefault(label, Element(label, token, kind, node))
        child_title = node["title"] if isinstance(node.get("title"), str) and prop is None else title
        if prop is not None and isinstance(node.get("title"), str):
            child_title = node["title"]
        for key, value in node.items():
            if key in DATA_KEYS or key == "x-provisional":
                continue
            if key == "properties" and isinstance(value, dict):
                for name, child in value.items():
                    self._visit(child, (*pointer, key, str(name)), child_title, str(name))
            else:
                self._visit(value, (*pointer, str(key)), child_title, None)


def provisional_sections(changelog: str) -> list[str]:
    """The text of every ``Provisional`` section: from its heading to the next heading of the same or a higher level."""
    lines = changelog.splitlines()
    sections: list[str] = []
    index = 0
    while index < len(lines):
        match = _HEADING.match(lines[index])
        if match and match.group(2) == PROVISIONAL_HEADING:
            level = len(match.group(1))
            body: list[str] = []
            index += 1
            while index < len(lines):
                inner = _HEADING.match(lines[index])
                if inner and len(inner.group(1)) <= level:
                    break
                body.append(lines[index])
                index += 1
            sections.append("\n".join(body))
        else:
            index += 1
    return sections


def names(section_text: str, token: str) -> bool:
    """True when ``token`` appears as a whole word (a hyphen or word character does not border it)."""
    return re.search(r"(?<![\w-])" + re.escape(token) + r"(?![\w-])", section_text) is not None


def discover_modules(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and p.name not in NON_MODULE_DIRECTORIES and not p.name.startswith(".") and (p / ROOT_DOCUMENT).is_file())


def _shared_property_tokens(elements: list[Element]) -> frozenset[str]:
    """Bare property names carried by more than one provisional element (e.g. ``code`` on two schemas)."""
    counts = Counter(element.token for element in elements if element.kind == "property")
    return frozenset(token for token, count in counts.items() if count > 1)


class _Check:
    def __init__(self, root: Path, modules: tuple[str, ...]) -> None:
        self.root = root
        self.selected = modules
        self.report = Report()

    def add(self, code: str, module: str, element: str, detail: str) -> None:
        self.report.findings.append(Finding(code, f"{module}:{element}", detail))

    def run(self) -> Report:
        modules = [m for m in discover_modules(self.root) if not self.selected or m.name in self.selected]
        if not modules:
            self.report.blocked.append(Finding("NO_MODULE", str(self.root), "no module (a directory with a root openapi.yaml) was found"))
            return self.report
        for module in modules:
            self.check_module(module)
        if self.report.counts["provisional_elements"] == 0 and not self.report.blocked:
            self.report.blocked.append(Finding("ZERO_PROVISIONAL", str(self.root), "no element carries x-provisional"))
        return self.report

    def check_module(self, module: Path) -> None:
        try:
            walk = _Walk(contract_resolver.resolve(module).tree)
        except contract_resolver.ResolveError as error:
            self.report.blocked.append(Finding("RESOLVE_FAILED", module.name, str(error)))
            return
        name = module.name
        for label, node in walk.required.items():
            if "x-provisional" not in node:
                self.add("MISSING_MARKER", name, label, f"{label.rsplit('.', 1)[-1]} is provisional (FR-011) and carries no x-provisional")
        sections = self.changelog_sections(module)
        shared = _shared_property_tokens(list(walk.elements.values()))
        for element in walk.elements.values():
            self.report.counts["provisional_elements"] += 1
            self.check_element(name, element, sections, shared)

    def changelog_sections(self, module: Path) -> list[str] | str:
        path = module / CHANGELOG
        if not path.is_file():
            return f"{CHANGELOG} does not exist"
        sections = provisional_sections(path.read_text(encoding="utf-8"))
        return sections if sections else f"{CHANGELOG} has no {PROVISIONAL_HEADING!r} section"

    def check_element(self, module: str, element: Element, sections: list[str] | str, shared: frozenset[str] = frozenset()) -> None:
        marker = element.node["x-provisional"]
        decision = marker.get("open_decision") if isinstance(marker, dict) else None
        if not isinstance(decision, str) or len(decision.split()) < MIN_DECISION_WORDS:
            self.add(
                "UNDESCRIBED_MARKER",
                module,
                element.label,
                f"x-provisional must be a mapping whose open_decision names what is undecided in at least {MIN_DECISION_WORDS} words",
            )
        if element.kind == "property" and element.token in REQUIRED_PROVISIONAL_PROPERTIES and not is_nullable(element.node):
            self.add("NOT_NULLABLE", module, element.label, "a provisional property must be nullable (a null type or a null branch)")
        if isinstance(sections, str):
            self.add("NOT_IN_CHANGELOG", module, element.label, sections)
        else:
            # A property name carried by several provisional elements is ambiguous bare: each must be named qualified.
            needed = element.label if element.kind == "property" and element.token in shared else element.token
            if not any(names(text, needed) for text in sections):
                self.add("NOT_IN_CHANGELOG", module, element.label, f"{needed!r} is not named in the {PROVISIONAL_HEADING} section of {CHANGELOG}")


def check(root: str | Path, modules: tuple[str, ...] = ()) -> Report:
    """Run the provisional check over the modules under ``root``."""
    return _Check(Path(root), tuple(modules)).run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check x-provisional markers, nullability and the CHANGELOG record.")
    parser.add_argument("--root", default="contracts", help="contracts root (default: contracts)")
    parser.add_argument("--module", action="append", default=[], help="restrict to this module (repeatable)")
    arguments = parser.parse_args(argv)
    report = check(arguments.root, tuple(arguments.module))
    for finding in (*report.blocked, *report.findings):
        print(finding.render())
    print(report.counts_line())
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
