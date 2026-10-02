"""Leak scan over every file of the contracts tree (spec FR-012, D-14, NFR-004, FR-025).

No host path, e-mail address or identity-bearing property name may appear anywhere under the contracts
root: descriptions, citations, the README and CHANGELOG, examples (``promptMarkdown`` included, which is
authored here). Nothing is exempt: not ``fixtures/``, not ``tools/``, not a marker line. Two passes read the
same files:

* the text pass: every non-blank line of every text file against the human-text host-path patterns and the
  e-mail pattern of ``leak_patterns`` (so ``leak_patterns.py`` and ``fixture_builder.py``, which write their
  patterns from fragments, are not flagged by it);
* the structured pass over parsed YAML and JSON: every mapping *key* against the forbidden property names
  (``FORBIDDEN_PROPERTY_NAME``), and every string *value* by field class (spec D-14): a value under one of
  ``fixture_builder.STRICT_FIELDS`` (identifiers, handles, path-like values; the items of a list under such a
  key too) is scanned with the strict host-path patterns, any other value with the human-text patterns, and
  every value for e-mail.

Findings (exit 1), printed ``CONTRACT-CHECK leak_scan: <CODE>: <file>:<line or key path>: <detail>`` (the
leaked value is never echoed): ``FORBIDDEN_PROPERTY_NAME``, ``HOST_PATH``, ``EMAIL``,
``PLANTED_NOT_DETECTED`` (the built-in self test: each ``fixture_builder`` plant is built into a temporary
root, scanned, and must be found, so a scan that went blind fails loudly), ``CONTROL_FLAGGED`` (the same
self test found a leak in the clean control next to a plant). Cannot do its job (exit 2): ``ZERO_FILES``,
``ZERO_VALUES_IN_CLASS`` (no string value of the ``strict`` or ``human`` class was scanned). A file that is
binary (a NUL byte or invalid UTF-8) is skipped and not counted. The last line is always
``counts: files=N values_strict=N values_human=N values_all=N`` (text files read; string values per class;
non-blank text lines).

Run as a bare script (``python contracts/tools/leak_scan.py [--root DIR]``). Standard library plus PyYAML;
imports only sibling modules.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

import fixture_builder
import leak_patterns

CHECK_NAME = "leak_scan"
SKIPPED_DIRECTORIES = frozenset({".git", "__pycache__", ".gradle", "build", "node_modules", ".mypy_cache", ".ruff_cache", ".pytest_cache"})
SKIPPED_SUFFIXES = frozenset({".pyc", ".pyo"})
YAML_SUFFIXES = (".yaml", ".yml")
JSON_SUFFIX = ".json"
CODE_FORBIDDEN = "FORBIDDEN_PROPERTY_NAME"
CODE_NOT_DETECTED = "PLANTED_NOT_DETECTED"
CODE_CONTROL_FLAGGED = "CONTROL_FLAGGED"
STRICT_FIELDS = frozenset(fixture_builder.STRICT_FIELDS)


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
    counts: dict[str, int] = field(default_factory=lambda: {"files": 0, "values_strict": 0, "values_human": 0, "values_all": 0})

    @property
    def exit_code(self) -> int:
        if self.blocked:
            return 2
        return 1 if self.findings else 0

    def counts_line(self) -> str:
        return "counts: " + " ".join(f"{key}={value}" for key, value in self.counts.items())


def list_files(root: Path) -> list[Path]:
    """Every regular file under ``root`` except tool-local caches and build output."""
    if not root.is_dir():
        return []
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix not in SKIPPED_SUFFIXES and not any(part in SKIPPED_DIRECTORIES for part in path.relative_to(root).parts)
    )


def read_text(path: Path) -> str | None:
    """The file's text, or ``None`` for a binary file."""
    data = path.read_bytes()
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


class _Scanner:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.findings: list[Finding] = []
        self.counts = {"files": 0, "values_strict": 0, "values_human": 0, "values_all": 0}

    def run(self) -> None:
        for path in list_files(self.root):
            text = read_text(path)
            if text is None:
                continue
            name = path.relative_to(self.root).as_posix()
            self.counts["files"] += 1
            self.scan_text(name, text)
            if path.suffix in YAML_SUFFIXES or path.suffix == JSON_SUFFIX:
                self.scan_structured(name, path.suffix, text)

    def add(self, code: str, subject: str, detail: str) -> None:
        self.findings.append(Finding(code, subject, detail))

    def scan_text(self, name: str, text: str) -> None:
        for number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            self.counts["values_all"] += 1
            for code in leak_patterns.leak_codes(line, leak_patterns.HUMAN):
                self.add(code, f"{name}:{number}", f"{_kind(code)} in text")

    def scan_structured(self, name: str, suffix: str, text: str) -> None:
        try:
            document = json.loads(text) if suffix == JSON_SUFFIX else yaml.safe_load(text)
        except (ValueError, yaml.YAMLError):
            return
        self.walk(name, document, "", False)

    def walk(self, name: str, node: Any, keypath: str, strict: bool) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                path = f"{keypath}.{key}" if keypath else str(key)
                if leak_patterns.is_forbidden_property_name(str(key)):
                    self.add(CODE_FORBIDDEN, f"{name}:{path}", "a property name that carries local identity")
                self.walk(name, value, path, str(key) in STRICT_FIELDS)
        elif isinstance(node, list):
            for position, item in enumerate(node):
                self.walk(name, item, f"{keypath}[{position}]", strict)
        elif isinstance(node, str):
            field_class = leak_patterns.STRICT if strict else leak_patterns.HUMAN
            self.counts["values_strict" if strict else "values_human"] += 1
            for code in leak_patterns.leak_codes(node, field_class):
                self.add(code, f"{name}:{keypath}", f"{_kind(code)} in a {field_class} field")


def _kind(code: str) -> str:
    return "host path" if code == leak_patterns.CODE_HOST_PATH else "e-mail address"


def scan_tree(root: str | Path) -> list[Finding]:
    """The raw findings of both passes over ``root``, without floors or the self test."""
    scanner = _Scanner(Path(root))
    scanner.run()
    return scanner.findings


def run_self_test(scan: Callable[[Path], list[Finding]] | None = None) -> list[Finding]:
    """Build each plant, scan it and demand it is found while the control beside it is not."""
    scan_function = scan if scan is not None else scan_tree
    problems: list[Finding] = []
    for kind in fixture_builder.KINDS:
        with tempfile.TemporaryDirectory() as directory:
            built = fixture_builder.build(kind, directory)
            findings = scan_function(Path(directory))
        if any(fixture_builder.CONTROL_FILE in finding.subject for finding in findings):
            problems.append(Finding(CODE_CONTROL_FLAGGED, kind, "the clean control next to the plant was reported as a leak"))
        found = {finding.code for finding in findings if fixture_builder.PLANTED_FILE in finding.subject}
        if not set(built.expected_codes) <= found:
            problems.append(Finding(CODE_NOT_DETECTED, kind, f"the planted {kind} was not reported ({', '.join(built.expected_codes)} expected)"))
    return problems


def check(root: str | Path) -> Report:
    """Scan ``root``, run the self test, and apply the floors."""
    base = Path(root)
    report = Report()
    if not list_files(base):
        report.blocked.append(Finding("ZERO_FILES", str(base), "no file was found to scan"))
        return report
    scanner = _Scanner(base)
    scanner.run()
    report.findings.extend(scanner.findings)
    report.counts.update(scanner.counts)
    report.findings.extend(run_self_test())
    if report.counts["files"] == 0:
        report.blocked.append(Finding("ZERO_FILES", str(base), "every file under the root is binary"))
    for field_class in leak_patterns.FIELD_CLASSES:
        if report.counts[f"values_{field_class}"] == 0:
            report.blocked.append(Finding("ZERO_VALUES_IN_CLASS", field_class, f"no string value of the {field_class} class was scanned"))
    if report.counts["values_all"] == 0:
        report.blocked.append(Finding("ZERO_VALUES_IN_CLASS", "all", "no text line was scanned"))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan every file under the contracts tree for host paths, e-mail addresses and forbidden property names.")
    parser.add_argument("--root", default="contracts", help="directory to scan (default: contracts)")
    arguments = parser.parse_args(argv)
    report = check(arguments.root)
    for finding in (*report.blocked, *report.findings):
        print(finding.render())
    print(report.counts_line())
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
