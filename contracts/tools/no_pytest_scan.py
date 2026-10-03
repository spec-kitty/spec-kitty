"""Scan the contracts scripts for any path that reaches the test runner (spec FR-017, no-pytest half).

The contracts checks run in CI jobs that install no test runner and must not need one. Every script
under ``<root>/tools/`` is scanned, at any depth except the committed ``fixtures/`` trees and bytecode
caches, this scanner included: Python files (``*.py``), shell
scripts (``*.sh``, ``*.bash``) and make files (``Makefile``, ``*.mk``). The check fails with
``PYTEST_REFERENCE`` when a script:

* imports the runner, directly, from it, or its private package (an ``import`` statement);
* holds a string that invokes it: ``python -m <runner>``, a subprocess argument list, a shell string,
  or a dynamic ``import_module`` name (any string constant that names the runner as a word; docstrings
  are exempt, a message string is not);
* has a make or shell line that runs it (comment lines are skipped);
* hands ``importlib.import_module``, ``__import__``, a ``subprocess`` call (``run``, ``Popen``, ``call``,
  ``check_call``, ``check_output``, ``getoutput``, ``getstatusoutput``), ``os.system`` or ``os.popen`` an
  argument that *spells* the runner without holding the word in one literal: the argument is folded
  (string constants, ``+``, f-strings, ``"sep".join([...])`` and module-level names assigned such a
  value) and a list argument is judged element by element and joined by spaces. A part the folder cannot
  resolve (a function result, an attribute, a parameter) is not judged, so a runner name that arrives at
  run time from outside the file is out of reach of a static scan.

A word is the runner's name not glued to other word characters, dots or hyphens, so a cache
directory name (``.`` + name + ``_cache``) and a hyphenated word do not match. The search strings are
assembled from fragments, so this file does not flag itself, and a unit test shows it does scan itself.
There is no self-exemption: the scanner does assemble the runner name from fragments, but only to search for
it, never to pass it to an import or process sink, so the sink check finds nothing in it.

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
# Calls whose arguments are folded (constants, ``+``, f-strings, ``join``, module-level names) and judged:
# a dynamic import, a process spawn, a shell string. A name the folder cannot resolve is not judged.
IMPORT_SINKS = frozenset({"import_module", "importlib.import_module", "__import__"})
SUBPROCESS_SINKS = frozenset({"run", "Popen", "call", "check_call", "check_output", "getoutput", "getstatusoutput"})
SHELL_SINKS = frozenset({"os.system", "os.popen"})
SKIPPED_DIRECTORIES = frozenset({"fixtures", "__pycache__"})


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


def _fold(node: ast.expr, env: dict[str, str]) -> str | None:
    """The string ``node`` evaluates to when it is built only from constants, ``+``, f-strings, ``join`` and known names."""
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.Name):
        return env.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _fold(node.left, env), _fold(node.right, env)
        return left + right if left is not None and right is not None else None
    if isinstance(node, ast.JoinedStr):
        parts = [_fold(v.value, env) if isinstance(v, ast.FormattedValue) and v.format_spec is None and v.conversion == -1 else _fold(v, env) for v in node.values]
        return None if any(part is None for part in parts) else "".join(part for part in parts if part is not None)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "join" and len(node.args) == 1 and not node.keywords:
        separator, items = _fold(node.func.value, env), node.args[0]
        pieces = [_fold(item, env) for item in items.elts] if isinstance(items, ast.List | ast.Tuple) else None
        if separator is None or pieces is None or any(piece is None for piece in pieces):
            return None
        return separator.join(piece for piece in pieces if piece is not None)
    return None


def _module_strings(tree: ast.Module) -> dict[str, str]:
    """Module-level ``NAME = <foldable string>`` assignments, in order, so a sink argument may be a name."""
    env: dict[str, str] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
            value = _fold(statement.value, env)
            if value is not None:
                env[statement.targets[0].id] = value
    return env


def _sink_name(call: ast.Call) -> str | None:
    function = call.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name):
        return f"{function.value.id}.{function.attr}"
    return None


def _is_sink(call: ast.Call) -> bool:
    name = _sink_name(call)
    if name is None:
        return False
    return name in IMPORT_SINKS or name in SHELL_SINKS or (name.startswith("subprocess.") and name.removeprefix("subprocess.") in SUBPROCESS_SINKS)


def _names_runner(folded: str) -> bool:
    return mentions_runner(folded) or folded.split(".")[0] in _IMPORT_ROOTS


def _sink_argument_strings(call: ast.Call, env: dict[str, str]) -> list[tuple[int, str]]:
    """Every string a sink call is handed, folded: each argument, each list element, and a list joined by spaces."""
    strings: list[tuple[int, str]] = []
    for argument in [*call.args, *(keyword.value for keyword in call.keywords)]:
        folded = _fold(argument, env)
        if folded is not None:
            strings.append((argument.lineno, folded))
        elif isinstance(argument, ast.List | ast.Tuple):
            pieces = [_fold(item, env) for item in argument.elts]
            strings.extend((item.lineno, piece) for item, piece in zip(argument.elts, pieces, strict=True) if piece is not None)
            if all(piece is not None for piece in pieces):
                strings.append((argument.lineno, " ".join(piece for piece in pieces if piece is not None)))
    return strings


def _scan_sinks(name: str, tree: ast.Module) -> list[Finding]:
    env = _module_strings(tree)
    found: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_sink(node):
            found.extend(
                Finding("PYTEST_REFERENCE", f"{name}:{line}", "an import or process call is handed an argument that spells the test runner")
                for line, folded in _sink_argument_strings(node, env)
                if _names_runner(folded)
            )
    return found


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
    found.extend(_scan_sinks(name, tree))
    return _one_per_line(found)


def _one_per_line(findings: list[Finding]) -> list[Finding]:
    seen: set[str] = set()
    unique: list[Finding] = []
    for finding in findings:
        if finding.subject not in seen:
            seen.add(finding.subject)
            unique.append(finding)
    return unique


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
    return sorted(
        p
        for p in tools.rglob("*")
        if p.is_file()
        and not any(part in SKIPPED_DIRECTORIES for part in p.relative_to(tools).parts[:-1])
        and (p.suffix == PYTHON_SUFFIX or p.suffix in SHELL_SUFFIXES or p.name in MAKE_NAMES)
    )


def check(root: str | Path) -> Report:
    root = Path(root)
    report = Report()
    for script in scripts_of(root):
        name = f"{TOOLS_DIRECTORY}/{script.relative_to(root / TOOLS_DIRECTORY).as_posix()}"
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
