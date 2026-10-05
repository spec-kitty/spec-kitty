"""Leak scan over every file of the contracts tree (spec FR-012, FR-015, D-14, FR-025).

No host path, e-mail address, secret or token or identity-bearing property name may appear anywhere under the contracts
root: descriptions, citations, the README and CHANGELOG, examples (``promptMarkdown`` included, which is
authored here). No contracts directory is exempt: not ``fixtures/``, not ``tools/``, not a marker line. Only the directories named in
``SKIPPED_DIRECTORIES`` (VCS, cache and build output such as ``build`` and ``node_modules``) are not walked, and no tracked file
of the contracts tree lies under one of those names. The one thing that is
masked is narrow: the *value* of a ``path`` or ``artifactPath`` key (the artifact-path class, AD-19) in a YAML file that
parses, reached without passing through an ``x-source`` or ``x-derived`` key. Such a value is a name inside a Mission
directory, so a legitimate name (a ``home/<x>/`` segment, a space, an accented letter, an at sign) is judged by the
artifact-path rule (``malformed_artifact_path``) and not by the host-path and e-mail patterns. Under ``x-source`` and
``x-derived`` the key ``path`` is a repository path and keeps the human scan. Two passes read the same files:

* the text pass: every non-blank line of every text file against the human-text host-path patterns, the
  e-mail pattern and the secret patterns of ``leak_patterns`` (so ``leak_patterns.py`` and ``fixture_builder.py``, which write their
  patterns from fragments, are not flagged by it). In a YAML file that parses, the artifact-path value spans are
  blanked first (``artifact_path_spans``, ``mask_spans``; newlines are kept so line numbers hold) for the host-path and e-mail
  patterns; the secret patterns always read the original line, so a token in a path value is still reported. A JSON
  file and a YAML file that does not parse are scanned unmasked;
* the structured pass over parsed YAML and JSON: every mapping *key* against the forbidden property names
  (``FORBIDDEN_PROPERTY_NAME``), and every string *value* by field class (spec D-14): a value under one of
  ``fixture_builder.STRICT_FIELDS`` (identifiers, handles, path-like values; the items of a list under such a
  key too) is scanned with the strict host-path patterns, a value under an artifact-path key with
  ``malformed_artifact_path`` (and for secrets), any other value with the human-text patterns, and
  every value for e-mail (an artifact-path value excepted).

Findings (exit 1), printed ``CONTRACT-CHECK leak_scan: <CODE>: <file>:<line or key path>: <detail>`` (the
leaked value is never echoed): ``FORBIDDEN_PROPERTY_NAME``, ``HOST_PATH``, ``EMAIL``,
``ARTIFACT_PATH_MALFORMED`` (a value under ``path`` or ``artifactPath`` that breaks the artifact-path rule; the detail names the reason),
``SECRET`` (a GitHub token, an AWS access key id or a private-key header, in text or in any parsed string
value), ``PLANTED_NOT_DETECTED`` (the built-in self test: each ``fixture_builder`` plant is built into a temporary
root, scanned, and must be found, so a scan that went blind fails loudly), ``CONTROL_FLAGGED`` (the same
self test found a leak in the clean control next to a plant), ``PARSE_FAILED`` (a ``.yaml``, ``.yml`` or
``.json`` file that does not parse, so the structured pass could not read it; the text pass still ran).
Cannot do its job (exit 2): ``ZERO_FILES``, ``ZERO_VALUES_IN_CLASS`` (no string value of the ``strict`` or ``human`` class was scanned). A file that is
binary (a NUL byte or invalid UTF-8) is skipped and not counted. The last line is always
``counts: files=N values_strict=N values_human=N values_all=N values_artifact_path=N`` (text files read; string values per class;
non-blank text lines; string values under an artifact-path key). There is no floor on the artifact-path class.

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
import yaml.nodes

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
CODE_PARSE_FAILED = "PARSE_FAILED"
CODE_ARTIFACT_PATH = "ARTIFACT_PATH_MALFORMED"
ARTIFACT_PATH_KEYS = frozenset({"path", "artifactPath"})
SOURCE_KEYS = frozenset({"x-source", "x-derived"})
MAX_ARTIFACT_PATH_LENGTH = 512
COUNT_KEYS = ("files", "values_strict", "values_human", "values_all", "values_artifact_path")
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
    counts: dict[str, int] = field(default_factory=lambda: dict.fromkeys(COUNT_KEYS, 0))

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


def has_line_break(text: str) -> bool:
    """Whether ``text`` holds a character the scanner's line splitting (``str.splitlines``) treats as a line break."""
    return any(character.splitlines() != [character] for character in text)


def malformed_artifact_path(path: str) -> str | None:
    """The stable reason ``path`` is not an artifact path, or ``None`` when it is one (the one definition on the tooling side).

    The reasons are checked in this order: ``empty``, ``too_long`` (over 512 characters), ``absolute``, ``tilde`` (a leading
    ``~/``), ``drive_letter``, ``backslash``, ``nul``, ``line_break`` (any character the scanner treats as a line break:
    ``splitlines`` boundaries such as LF, CR, VT, FF, NEL, U+2028), ``trailing_slash``, ``empty_segment``, ``dot_segment``, ``dotdot_segment``.
    """
    if not path:
        return "empty"
    if len(path) > MAX_ARTIFACT_PATH_LENGTH:
        return "too_long"
    if path.startswith("/"):
        return "absolute"
    if path.startswith("~/"):
        return "tilde"
    if len(path) >= 2 and path[1] == ":" and path[0].isascii() and path[0].isalpha():
        return "drive_letter"
    if chr(92) in path:
        return "backslash"
    if chr(0) in path:
        return "nul"
    if has_line_break(path):
        return "line_break"
    if path.endswith("/"):
        return "trailing_slash"
    segments = path.split("/")
    if "" in segments:
        return "empty_segment"
    if "." in segments:
        return "dot_segment"
    return "dotdot_segment" if ".." in segments else None


def _value_spans(node: yaml.nodes.Node) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    if isinstance(node, yaml.nodes.MappingNode):
        for key_node, value_node in node.value:
            key = key_node.value if isinstance(key_node, yaml.nodes.ScalarNode) else None
            if key in SOURCE_KEYS:
                continue
            if key in ARTIFACT_PATH_KEYS and isinstance(value_node, yaml.nodes.ScalarNode):
                # a value with a line break is malformed (not an artifact path), so it is never masked: the human patterns read it
                if not has_line_break(str(value_node.value)):
                    spans.append((value_node.start_mark.index, value_node.end_mark.index))
            else:
                spans.extend(_value_spans(value_node))
    elif isinstance(node, yaml.nodes.SequenceNode):
        for item in node.value:
            spans.extend(_value_spans(item))
    return spans


def artifact_path_spans(text: str) -> list[tuple[int, int]]:
    """The character spans of each scalar value of an artifact-path key reached without passing an ``x-source`` or ``x-derived`` key.

    A text that does not compose as one YAML document has no span (it is scanned unmasked).
    """
    try:
        root = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError:
        return []
    return [] if root is None else _value_spans(root)


def mask_spans(text: str, spans: list[tuple[int, int]]) -> str:
    """``text`` with the characters of each span blanked; a line break stays, so line numbers hold."""
    characters = list(text)
    for start, end in spans:
        for position in range(start, min(end, len(characters))):
            character = characters[position]
            if character.splitlines() == [character]:
                characters[position] = " "
    return "".join(characters)


class _Scanner:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.findings: list[Finding] = []
        self.counts = dict.fromkeys(COUNT_KEYS, 0)

    def run(self) -> None:
        for path in list_files(self.root):
            text = read_text(path)
            if text is None:
                continue
            name = path.relative_to(self.root).as_posix()
            self.counts["files"] += 1
            masked = mask_spans(text, artifact_path_spans(text)) if path.suffix in YAML_SUFFIXES else text
            self.scan_text(name, text, masked)
            if path.suffix in YAML_SUFFIXES or path.suffix == JSON_SUFFIX:
                self.scan_structured(name, path.suffix, text)

    def add(self, code: str, subject: str, detail: str) -> None:
        self.findings.append(Finding(code, subject, detail))

    def scan_text(self, name: str, text: str, masked: str | None = None) -> None:
        """Host-path and e-mail findings come from ``masked`` (default: ``text``), secrets from the original line."""
        masked_lines = (text if masked is None else masked).splitlines()
        for number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            self.counts["values_all"] += 1
            visible = masked_lines[number - 1] if number <= len(masked_lines) else line
            codes = [c for c in leak_patterns.leak_codes(visible, leak_patterns.HUMAN) if c != leak_patterns.CODE_CREDENTIAL]
            codes += [c for c in leak_patterns.leak_codes(line, leak_patterns.HUMAN) if c == leak_patterns.CODE_CREDENTIAL]
            for code in codes:
                self.add(code, f"{name}:{number}", f"{_kind(code)} in text")

    def scan_structured(self, name: str, suffix: str, text: str) -> None:
        try:
            document = json.loads(text) if suffix == JSON_SUFFIX else yaml.safe_load(text)
        except (ValueError, yaml.YAMLError) as error:
            # name the exception type only: a parser message quotes the offending source text
            language = "JSON" if suffix == JSON_SUFFIX else "YAML"
            self.add(CODE_PARSE_FAILED, name, f"not valid {language} ({type(error).__name__}), so the structured pass could not read it")
            return
        self.walk(name, document, "", False)

    def walk(self, name: str, node: Any, keypath: str, strict: bool, *, key: str = "", sourced: bool = False) -> None:
        if isinstance(node, dict):
            for child, value in node.items():
                path = f"{keypath}.{child}" if keypath else str(child)
                if leak_patterns.is_forbidden_property_name(str(child)):
                    self.add(CODE_FORBIDDEN, f"{name}:{path}", "a property name that carries local identity")
                self.walk(name, value, path, str(child) in STRICT_FIELDS, key=str(child), sourced=sourced or str(child) in SOURCE_KEYS)
        elif isinstance(node, list):
            for position, item in enumerate(node):
                self.walk(name, item, f"{keypath}[{position}]", strict, sourced=sourced)
        elif isinstance(node, str):
            if key in ARTIFACT_PATH_KEYS and not sourced:
                self.check_artifact_path(name, keypath, node)
                return
            field_class = leak_patterns.STRICT if strict else leak_patterns.HUMAN
            self.counts["values_strict" if strict else "values_human"] += 1
            for code in leak_patterns.leak_codes(node, field_class):
                self.add(code, f"{name}:{keypath}", f"{_kind(code)} in a {field_class} field")

    def check_artifact_path(self, name: str, keypath: str, value: str) -> None:
        """An artifact-path value is judged by the rule, not by the host-path and e-mail patterns; a secret is still a secret."""
        self.counts["values_artifact_path"] += 1
        reason = malformed_artifact_path(value)
        if reason is not None:
            self.add(CODE_ARTIFACT_PATH, f"{name}:{keypath}", f"a malformed artifact path ({reason})")
        if leak_patterns.CODE_CREDENTIAL in leak_patterns.leak_codes(value, leak_patterns.HUMAN):
            self.add(leak_patterns.CODE_CREDENTIAL, f"{name}:{keypath}", f"{_kind(leak_patterns.CODE_CREDENTIAL)} in an artifact path")


def _kind(code: str) -> str:
    if code == leak_patterns.CODE_HOST_PATH:
        return "host path"
    return "secret or token" if code == leak_patterns.CODE_CREDENTIAL else "e-mail address"


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
