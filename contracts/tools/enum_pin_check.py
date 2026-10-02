"""Enum pinning for the fixed vocabularies of a contract module (spec FR-008, FR-025).

The status lanes, the lifecycle statuses and the topologies are closed vocabularies: a consumer branches on
every value. The pin file (``--pins``, default ``enum_pins.json`` next to this script) lists, per module and
per enum schema (by ``title``), exactly the values the contract may carry. The module is read through the
single resolver and the schema's ``enum`` is compared with the pin as a set. Pin file shape::

    {"<module>": {"<EnumSchema>": ["value", ...], ...}, ...}

A module with no entry in the pin file is not pinned (and is only scanned for a board grouping). Failure
codes (exit 1), printed ``CONTRACT-CHECK enum_pin_check: <CODE>: <module>:<Enum or name>: <detail>``:

* ``ENUM_VALUE_ADDED`` / ``ENUM_VALUE_REMOVED``: the schema has a value the pin lacks, or lacks one the pin
  has (a swap gives both). A change of vocabulary is a deliberate edit of the pin file in the same commit.
* ``BOARD_GROUPING_PRESENT``: a schema title or a property name is a board grouping (a token ``column``,
  ``columns``, ``board`` or ``grouping`` in its camel-case or snake-case words). The grouping of status
  lanes into board columns is a consumer convention and is not part of any contract (FR-008).

Cannot do its job (exit 2): ``NO_MODULE``, ``RESOLVE_FAILED``, ``PINS_UNREADABLE``, ``PIN_EMPTY`` (a pin with no
enums or an enum with no values, or no pin applied to any module), ``ENUM_UNREADABLE`` (a pinned schema is not
in the module or has no ``enum`` list). The last line is always ``counts: enums=N values=N`` (pinned enums
checked, and the number of values they currently carry).

Run as a bare script (``python contracts/tools/enum_pin_check.py [--root DIR] [--pins FILE] [--module NAME]``).
Standard library plus PyYAML; imports only sibling modules.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import contract_resolver

CHECK_NAME = "enum_pin_check"
NON_MODULE_DIRECTORIES = frozenset({"_shared", "fixtures", "gradle", "tools", "build", "node_modules"})
ROOT_DOCUMENT = "openapi.yaml"
DEFAULT_PINS = Path(__file__).resolve().parent / "enum_pins.json"
BOARD_TOKENS = frozenset({"column", "columns", "board", "boards", "grouping", "groupings"})
_WORD_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|[_\-\s]+")
_SKIPPED_KEYS = frozenset({"examples", "example", "default", "enum", "const"})


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
    counts: dict[str, int] = field(default_factory=lambda: {"enums": 0, "values": 0})

    @property
    def exit_code(self) -> int:
        if self.blocked:
            return 2
        return 1 if self.findings else 0

    def counts_line(self) -> str:
        return "counts: " + " ".join(f"{key}={value}" for key, value in self.counts.items())


def is_board_grouping_name(name: str) -> bool:
    """True when a word of ``name`` (split on camel case, ``_``, ``-`` and spaces) is a board-grouping word."""
    return any(word.lower() in BOARD_TOKENS for word in _WORD_BOUNDARY.split(name) if word)


def _scan(node: Any, titles: dict[str, dict[str, Any]], grouping: set[str]) -> None:
    if isinstance(node, list):
        for item in node:
            _scan(item, titles, grouping)
    elif isinstance(node, dict):
        title = node.get("title")
        if isinstance(title, str):
            titles.setdefault(title, node)
            if is_board_grouping_name(title):
                grouping.add(f"schema {title}")
        for key, value in node.items():
            if key in _SKIPPED_KEYS:
                continue
            if key == "properties" and isinstance(value, dict):
                for name, child in value.items():
                    if is_board_grouping_name(str(name)):
                        grouping.add(f"property {name}")
                    _scan(child, titles, grouping)
            else:
                _scan(value, titles, grouping)


def load_pins(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise TypeError("the pin file is not a mapping of module to enums")
        return document, ""
    except (OSError, ValueError, TypeError) as error:
        return None, f"{path}: {type(error).__name__}: {error}"


def discover_modules(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and p.name not in NON_MODULE_DIRECTORIES and not p.name.startswith(".") and (p / ROOT_DOCUMENT).is_file())


class _Check:
    def __init__(self, root: Path, pins: Path, modules: tuple[str, ...]) -> None:
        self.root = root
        self.pins_path = pins
        self.selected = modules
        self.report = Report()

    def block(self, code: str, subject: str, detail: str) -> None:
        self.report.blocked.append(Finding(code, subject, detail))

    def add(self, code: str, module: str, subject: str, detail: str) -> None:
        self.report.findings.append(Finding(code, f"{module}:{subject}", detail))

    def run(self) -> Report:
        modules = [m for m in discover_modules(self.root) if not self.selected or m.name in self.selected]
        if not modules:
            self.block("NO_MODULE", str(self.root), "no module (a directory with a root openapi.yaml) was found")
            return self.report
        pins, problem = load_pins(self.pins_path)
        if pins is None:
            self.block("PINS_UNREADABLE", str(self.pins_path), problem)
            return self.report
        for module in modules:
            self.check_module(module, pins)
        if self.report.counts["enums"] == 0 and not self.report.blocked:
            self.block("PIN_EMPTY", str(self.pins_path), "no pinned enum was checked: the pin file names none of the modules")
        return self.report

    def check_module(self, module: Path, pins: dict[str, Any]) -> None:
        try:
            tree = contract_resolver.resolve(module).tree
        except contract_resolver.ResolveError as error:
            self.block("RESOLVE_FAILED", module.name, str(error))
            return
        titles: dict[str, dict[str, Any]] = {}
        grouping: set[str] = set()
        _scan(tree, titles, grouping)
        for name in sorted(grouping):
            self.add("BOARD_GROUPING_PRESENT", module.name, name, "a board grouping is a consumer convention and is not part of the contract (FR-008)")
        if module.name not in pins:
            return
        module_pins = pins[module.name]
        if not isinstance(module_pins, dict) or not module_pins:
            self.block("PIN_EMPTY", module.name, "the pin file lists no enum for the module")
            return
        for enum, listed in module_pins.items():
            self.check_enum(module.name, enum, listed, titles.get(enum))

    def check_enum(self, module: str, enum: str, listed: Any, node: dict[str, Any] | None) -> None:
        if not isinstance(listed, list) or not listed:
            self.block("PIN_EMPTY", f"{module}:{enum}", "the pinned list is empty")
            return
        current = node.get("enum") if node is not None else None
        if not isinstance(current, list):
            self.block("ENUM_UNREADABLE", f"{module}:{enum}", "the schema is not in the module or has no enum list")
            return
        self.report.counts["enums"] += 1
        self.report.counts["values"] += len(current)
        for value in sorted(set(map(str, current)) - set(map(str, listed))):
            self.add("ENUM_VALUE_ADDED", module, enum, f"{value!r} is in the schema and not in the pin")
        for value in sorted(set(map(str, listed)) - set(map(str, current))):
            self.add("ENUM_VALUE_REMOVED", module, enum, f"{value!r} is in the pin and not in the schema")


def check(root: str | Path, pins: str | Path = DEFAULT_PINS, modules: tuple[str, ...] = ()) -> Report:
    """Run the enum pin check over the modules under ``root`` against the pin file ``pins``."""
    return _Check(Path(root), Path(pins), tuple(modules)).run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check that the fixed vocabularies keep exactly their pinned values.")
    parser.add_argument("--root", default="contracts", help="contracts root (default: contracts)")
    parser.add_argument("--pins", default=str(DEFAULT_PINS), help="pin file (default: the committed enum_pins.json; override for fixtures only)")
    parser.add_argument("--module", action="append", default=[], help="restrict to this module (repeatable)")
    arguments = parser.parse_args(argv)
    report = check(arguments.root, arguments.pins, tuple(arguments.module))
    for finding in (*report.blocked, *report.findings):
        print(finding.render())
    print(report.counts_line())
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
