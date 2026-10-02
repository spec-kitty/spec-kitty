"""Scan the contracts scripts for any path that reaches the test runner (spec FR-017, no-pytest half).

The contracts checks run in CI jobs that install no test runner and must not need one. Every script
directly under ``<root>/tools/`` is scanned, this scanner included: Python files (``*.py``), shell
scripts (``*.sh``, ``*.bash``) and make files (``Makefile``, ``*.mk``). The check fails with
``PYTEST_REFERENCE`` when a script:

* imports the runner, directly, from it, or its private package (an ``import`` statement);
* holds a string that invokes it: ``python -m <runner>``, a subprocess argument list, a shell string,
  or a dynamic ``import_module`` name (any string constant that names the runner as a word; docstrings
  are exempt, a message string is not);
* has a make or shell line that runs it (comment lines are skipped).

A word is the runner's name not glued to other word characters, dots or hyphens, so a cache
directory name (``.`` + name + ``_cache``) and a hyphenated word do not match. The search strings are
assembled from fragments, so this file does not flag itself, and a unit test shows it does scan itself.

Cannot do its job (exit 2): ``ZERO_SCRIPTS`` (nothing to scan) and ``UNREADABLE_SCRIPT`` (a script that
cannot be read or parsed is never reported as clean). Output ``CONTRACT-CHECK no_pytest_scan: <CODE>:
<file>:<line>: <detail>`` per violation and a last ``counts: scripts_scanned=N`` line; exit 0 pass,
1 violation, 2 cannot do its job. The test-directory half of this guard is a separate check.

Run as a bare script (``python contracts/tools/no_pytest_scan.py [--root DIR]``); ``--root`` is the
contracts root. Standard library only; imports nothing from ``tests/`` or ``scripts/``.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

CHECK_NAME = "no_pytest_scan"
TOOLS_DIRECTORY = "tools"
PYTHON_SUFFIX = ".py"
SHELL_SUFFIXES = (".sh", ".bash", ".mk")
MAKE_NAMES = ("Makefile", "GNUmakefile")

# Assembled from fragments so that this file never contains the bare name it searches for.
_NAME = "pyt" + "est"
_ALT_NAME = "py" + "." + "test"
RUNNER_NAMES: tuple[str, ...] = (_NAME, _ALT_NAME)
_WORD = re.compile(r"(?<![\w.\-])(?:" + "|".join(re.escape(name) for name in RUNNER_NAMES) + r")(?![\w\-])")
_IMPORT_ROOTS = frozenset({_NAME, "_" + _NAME})


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
    scanned: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=lambda: {"scripts_scanned": 0})

    @property
    def exit_code(self) -> int:
        if self.blocked:
            return 2
        return 1 if self.findings else 0

    def counts_line(self) -> str:
        return "counts: " + " ".join(f"{key}={value}" for key, value in self.counts.items())


def mentions_runner(text: str) -> bool:
    """True when ``text`` names the test runner as a word."""
    return _WORD.search(text) is not None


def _docstring_nodes(tree: ast.AST) -> set[int]:
    exempt: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                exempt.add(id(first.value))
    return exempt


def scan_python(name: str, source: str) -> list[Finding]:
    tree = ast.parse(source, filename=name)
    exempt = _docstring_nodes(tree)
    found: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in _IMPORT_ROOTS:
                    found.append(Finding("PYTEST_REFERENCE", f"{name}:{node.lineno}", "imports the test runner"))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module and node.module.split(".")[0] in _IMPORT_ROOTS:
                found.append(Finding("PYTEST_REFERENCE", f"{name}:{node.lineno}", "imports from the test runner"))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in exempt and mentions_runner(node.value):
            found.append(Finding("PYTEST_REFERENCE", f"{name}:{node.lineno}", "a string names the test runner (an invocation or an import by name)"))
    return found


def scan_shell(name: str, source: str) -> list[Finding]:
    found: list[Finding] = []
    for number, line in enumerate(source.splitlines(), start=1):
        if line.lstrip().startswith("#"):
            continue
        if mentions_runner(line):
            found.append(Finding("PYTEST_REFERENCE", f"{name}:{number}", "a make or shell line runs the test runner"))
    return found


def scripts_of(root: Path) -> list[Path]:
    tools = root / TOOLS_DIRECTORY
    if not tools.is_dir():
        return []
    return sorted(p for p in tools.iterdir() if p.is_file() and (p.suffix == PYTHON_SUFFIX or p.suffix in SHELL_SUFFIXES or p.name in MAKE_NAMES))


def check(root: str | Path) -> Report:
    root = Path(root)
    report = Report()
    for script in scripts_of(root):
        name = f"{TOOLS_DIRECTORY}/{script.name}"
        try:
            source = script.read_text(encoding="utf-8")
            findings = scan_python(name, source) if script.suffix == PYTHON_SUFFIX else scan_shell(name, source)
        except (OSError, UnicodeDecodeError, SyntaxError, ValueError) as error:
            report.blocked.append(Finding("UNREADABLE_SCRIPT", name, f"cannot be scanned: {type(error).__name__}"))
            continue
        report.scanned.append(name)
        report.findings.extend(findings)
    report.counts["scripts_scanned"] = len(report.scanned)
    if not report.scanned and not report.blocked:
        report.blocked.append(Finding("ZERO_SCRIPTS", str(root / TOOLS_DIRECTORY), "no script was scanned"))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan contracts/tools scripts for any path that reaches the test runner.")
    parser.add_argument("--root", default="contracts", help="contracts root (default: contracts)")
    arguments = parser.parse_args(argv)
    report = check(arguments.root)
    for finding in (*report.blocked, *report.findings):
        print(finding.render())
    print(report.counts_line())
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
