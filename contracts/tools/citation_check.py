"""Citation check for the contract modules under ``contracts/`` (spec FR-010, D-3, FR-025).

Every property of every resource schema must say where it comes from: ``x-source`` (a code or
data citation) or ``x-derived`` (a rule and its inputs), never both. The contract is read through
the single resolver, so a property reached only through a ``$ref``, an array ``items``, an
``additionalProperties`` value schema or an ``allOf``/``oneOf``/``anyOf`` branch is traversed like
any other. A property is counted once per ``<module>:<Schema>.<property path>``, where ``Schema`` is
the ``title`` of the nearest schema file above it (``[]`` marks array items, ``*`` a map value).

Citation grammar (pinned here and in ``contracts/README.md``):

* ``x-source: {path, symbol}``. ``path`` is a repository-relative, git-tracked file. ``symbol``
  resolves by defined name, never by text. In a ``.py`` file it is a ``class``, a ``def`` or an
  assignment target at module or class level found in the syntax tree, including an annotated
  target without a value (``content_invariant: str``); it is written bare (``content_invariant``)
  or dotted (``TailCursor.content_invariant``); a name that occurs only in a comment, a string, a
  function body or as a substring of another name does not resolve. In a ``.yaml`` or ``.json``
  file it is a dotted key path that must exist (``project.slug`` in ``.kittify/config.yaml``). An
  optional ``line`` is allowed and is not checked.
* ``x-derived: {rule, inputs}``. ``rule`` is non-empty prose; ``inputs`` is a non-empty list. Each
  input is a contract-field property path string or a code input ``{path, symbol}`` resolved exactly
  like an ``x-source``; a mixed list is allowed. A bare path (``statusLaneCounts.blocked``, ``items``)
  is relative to the property's own schema, siblings first, and a segment that is not a property of the node it
  is on steps through that node's array items or map value schema (up to three steps per segment); ``Schema.property`` (``MissionHead.createdAt``)
  names a property of another schema of the module. Any x-derived input that does not resolve is
  ``UNRESOLVED_INPUT``, whichever kind it is.
* A property that an ``allOf`` branch redeclares to narrow it (a ``const`` or ``enum`` refinement of a
  property an earlier branch or the schema itself declares) is a refinement, not a new property: it is
  neither counted nor required to carry a citation unless it carries one. A citation written on the root of
  a referenced schema file is inherited by every property that refers to it; a property that writes the
  other kind itself carries that one only.
* No property carries both (``BOTH_CITATIONS``). ``x-provisional`` is not a citation; see
  ``provisional_check.py``.

Shared pieces (``contracts/_shared/``: ``Problem``, ``PageInfo``, the cursors) are cross-module
vocabulary, not resource schemas of the module that uses them. They are skipped by the every-property
rule (:data:`SHARED_ARE_RESOURCE_SCHEMAS` is False); a ``_shared`` schema reached from a module is
neither counted nor required to carry citations.

Failure codes (exit 1), printed ``CONTRACT-CHECK citation_check: <CODE>: <subject>: <detail>``:
``MISSING_CITATION``, ``BOTH_CITATIONS``, ``BAD_DERIVED_FORM``, ``EMPTY_RULE``, ``EMPTY_INPUTS``,
``UNRESOLVED_INPUT``, ``CITED_PATH_MISSING``, ``CITED_SYMBOL_UNRESOLVED``, ``COUNT_MISMATCH`` (the
``x-source`` and ``x-derived`` counts do not sum to the property total). ``CITATION_REUSE`` is reported
for any one citation used by more than five properties and never changes the exit status. Cannot do its
job (exit 2): ``NO_MODULE``, ``RESOLVE_FAILED``, ``GIT_UNAVAILABLE``, ``ZERO_PROPERTIES``,
``ZERO_CITATIONS``. The last line is always
``counts: properties=N x_source=N x_derived=N inputs_resolved=N``.

Run as a bare script from the repository root
(``python contracts/tools/citation_check.py [--root DIR] [--module NAME] [--repo-root DIR]``).
Standard library plus PyYAML; imports only sibling modules.
"""

from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

import contract_resolver

CHECK_NAME = "citation_check"
NON_MODULE_DIRECTORIES = frozenset({"_shared", "fixtures", "gradle", "tools", "build", "node_modules"})
ROOT_DOCUMENT = "openapi.yaml"
SHARED_DIRECTORY = "_shared"
SCHEMAS_DIRECTORY = "schemas"
HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
SHARED_ARE_RESOURCE_SCHEMAS = False
REUSE_LIMIT = 5
_CITATION_KEYS = frozenset({"x-source", "x-derived"})
ARRAY_STEP = "[]"
MAP_STEP = "*"
PYTHON_SUFFIX = ".py"
YAML_SUFFIXES = (".yaml", ".yml")
JSON_SUFFIX = ".json"


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
    counts: dict[str, int] = field(default_factory=lambda: {"properties": 0, "x_source": 0, "x_derived": 0, "inputs_resolved": 0})

    @property
    def exit_code(self) -> int:
        if self.blocked:
            return 2
        return 1 if self.findings else 0

    def counts_line(self) -> str:
        return "counts: " + " ".join(f"{key}={value}" for key, value in self.counts.items())


# -- the traversal -----------------------------------------------------------


@dataclass
class PropertyRecord:
    module: str
    key: str
    node: dict[str, Any]
    siblings: dict[str, Any]
    root: dict[str, Any]
    root_title: str

    @property
    def subject(self) -> str:
        return f"{self.module}:{self.key}"


def effective_properties(node: dict[str, Any]) -> dict[str, Any]:
    """The properties a schema declares itself and through its ``allOf``/``oneOf``/``anyOf`` branches."""
    found: dict[str, Any] = {}
    properties = node.get("properties")
    if isinstance(properties, dict):
        found.update(properties)
    for keyword in ("allOf", "oneOf", "anyOf"):
        branches = node.get(keyword)
        if isinstance(branches, list):
            for branch in branches:
                if isinstance(branch, dict):
                    for name, child in effective_properties(branch).items():
                        found.setdefault(name, child)
    return found


def _parameter_slots(slots: list[tuple[str, dict[str, Any]]], label: str, parameters: Any) -> None:
    for entry in parameters if isinstance(parameters, list) else []:
        if isinstance(entry, dict) and isinstance(entry.get("schema"), dict):
            slots.append((f"{label} parameter {entry.get('name')}", entry["schema"]))


def _content_slots(slots: list[tuple[str, dict[str, Any]]], label: str, content: Any) -> None:
    for media, body in content.items() if isinstance(content, dict) else []:
        if isinstance(body, dict) and isinstance(body.get("schema"), dict):
            slots.append((f"{label} {media}", body["schema"]))


def _operation_slots(slots: list[tuple[str, dict[str, Any]]], label: str, operation: dict[str, Any]) -> None:
    _parameter_slots(slots, label, operation.get("parameters"))
    request = operation.get("requestBody")
    if isinstance(request, dict):
        _content_slots(slots, f"{label} request", request.get("content"))
    responses = operation.get("responses")
    for code, response in responses.items() if isinstance(responses, dict) else []:
        if not isinstance(response, dict):
            continue
        _content_slots(slots, f"{label} {code}", response.get("content"))
        headers = response.get("headers")
        for header, body in headers.items() if isinstance(headers, dict) else []:
            if isinstance(body, dict) and isinstance(body.get("schema"), dict):
                slots.append((f"{label} {code} header {header}", body["schema"]))


class SchemaWalk:
    """Walk the resolved tree of one module: every property record, plus an index of schemas by title."""

    def __init__(self, module: str, tree: dict[str, Any], shared_only: frozenset[str]) -> None:
        self.module = module
        self.records: dict[str, PropertyRecord] = {}
        self.index: dict[str, dict[str, Any]] = {}
        self._shared_only = shared_only
        for where, schema in self._schema_slots(tree):
            self._visit(schema, where, (), True, schema)

    @staticmethod
    def _schema_slots(tree: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        slots: list[tuple[str, dict[str, Any]]] = []
        paths = tree.get("paths")
        for path_key, item in paths.items() if isinstance(paths, dict) else []:
            if not isinstance(item, dict):
                continue
            _parameter_slots(slots, str(path_key), item.get("parameters"))
            for method in HTTP_METHODS:
                if isinstance(item.get(method), dict):
                    _operation_slots(slots, f"{method.upper()} {path_key}", item[method])
        components = tree.get("components")
        schemas = components.get("schemas") if isinstance(components, dict) else None
        for name, schema in schemas.items() if isinstance(schemas, dict) else []:
            if isinstance(schema, dict):
                slots.append((f"components {name}", schema))
        return slots

    def _visit(
        self,
        node: Any,
        title: str,
        trail: tuple[str, ...],
        counted: bool,
        root: dict[str, Any],
        refinements: frozenset[str] = frozenset(),
    ) -> None:
        if not isinstance(node, dict):
            return
        own_title = node.get("title")
        if isinstance(own_title, str) and own_title:
            self.index.setdefault(own_title, node)
            if own_title in self._shared_only:
                counted = False
            title, trail, root = own_title, (), node
        properties = node.get("properties")
        if isinstance(properties, dict):
            siblings = effective_properties(node)
            for name, child in properties.items():
                path = (*trail, str(name))
                refines = str(name) in refinements and not _CITATION_KEYS & set(child if isinstance(child, dict) else ())
                if counted and isinstance(child, dict) and not refines:
                    key = f"{title}.{'.'.join(path)}"
                    self.records.setdefault(
                        f"{self.module}:{key}",
                        PropertyRecord(self.module, key, child, siblings, root, title),
                    )
                self._visit(child, title, path, counted, root)
        items = node.get("items")
        if isinstance(items, dict):
            self._visit(items, title, (*trail, ARRAY_STEP), counted, root)
        extra = node.get("additionalProperties")
        if isinstance(extra, dict):
            self._visit(extra, title, (*trail, MAP_STEP), counted, root)
        all_of = node.get("allOf")
        if isinstance(all_of, list):
            seen = set(properties) if isinstance(properties, dict) else set()
            for branch in all_of:
                self._visit(branch, title, trail, counted, root, frozenset(seen))
                if isinstance(branch, dict):
                    seen |= set(effective_properties(branch))
        for keyword in ("oneOf", "anyOf"):
            branches = node.get(keyword)
            if isinstance(branches, list):
                for branch in branches:
                    self._visit(branch, title, trail, counted, root)


# -- code citations ----------------------------------------------------------


class GitUnavailableError(Exception):
    """git cannot list the tracked files of the repository root."""


def tracked_files(repo_root: Path) -> frozenset[str]:
    """Repository-relative posix paths of every git-tracked file."""
    git = shutil.which("git")
    if git is None:
        raise GitUnavailableError("git is not on the PATH")
    completed = subprocess.run(  # noqa: S603 -- argument list built here, binary resolved with shutil.which, no shell
        [git, "-C", str(repo_root), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise GitUnavailableError(f"git ls-files failed in {repo_root}: {completed.stderr.decode('utf-8', 'replace').strip()}")
    return frozenset(name for name in completed.stdout.decode("utf-8").split("\0") if name)


def _add_target(names: set[str], target: ast.expr, prefix: str) -> None:
    if isinstance(target, ast.Name):
        names.add(target.id)
        names.add(prefix + target.id)
    elif isinstance(target, ast.Tuple | ast.List):
        for element in target.elts:
            _add_target(names, element, prefix)


def _nested_blocks(statement: ast.stmt) -> list[list[ast.stmt]]:
    """The statement lists of a compound statement that still sit at the same definition level."""
    if isinstance(statement, ast.If):
        return [statement.body, statement.orelse]
    if isinstance(statement, ast.With | ast.AsyncWith):
        return [statement.body]
    if isinstance(statement, ast.Try):
        return [statement.body, statement.orelse, statement.finalbody, *(handler.body for handler in statement.handlers)]
    return []


def _collect(names: set[str], body: list[ast.stmt], prefix: str) -> None:
    for statement in body:
        if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.update((statement.name, prefix + statement.name))
            if isinstance(statement, ast.ClassDef):
                _collect(names, statement.body, prefix + statement.name + ".")
        elif isinstance(statement, ast.Assign):
            for target in statement.targets:
                _add_target(names, target, prefix)
        elif isinstance(statement, ast.AnnAssign):
            _add_target(names, statement.target, prefix)
        else:
            for block in _nested_blocks(statement):
                _collect(names, block, prefix)


def python_symbols(source: str) -> set[str]:
    """Names defined at module or class level, bare and dotted (``Class.member``); function bodies are not entered."""
    names: set[str] = set()
    _collect(names, ast.parse(source).body, "")
    return names


def key_path_exists(document: Any, segments: list[str]) -> bool:
    """True when the dotted key path exists; a key may itself contain dots."""
    if not segments:
        return True
    if isinstance(document, dict):
        for length in range(1, len(segments) + 1):
            key = ".".join(segments[:length])
            for candidate, value in document.items():
                if str(candidate) == key and key_path_exists(value, segments[length:]):
                    return True
        return False
    if isinstance(document, list) and segments[0].isdigit() and int(segments[0]) < len(document):
        return key_path_exists(document[int(segments[0])], segments[1:])
    return False


@dataclass(frozen=True)
class CodeProblem:
    kind: str  # "path" or "symbol"
    detail: str


class CodeResolver:
    def __init__(self, repo_root: Path, tracked: frozenset[str]) -> None:
        self._repo_root = repo_root
        self._tracked = tracked
        self._parsed: dict[str, Any] = {}

    def resolve(self, path: Any, symbol: Any) -> CodeProblem | None:
        """``None`` when ``path`` is a tracked file in which ``symbol`` is defined, else the first problem."""
        if not isinstance(path, str) or not path.strip():
            return CodeProblem("path", "the citation has no path")
        pure = PurePosixPath(path.replace("\\", "/"))
        if pure.is_absolute() or ".." in pure.parts or path[:2].endswith(":") or path.startswith("~"):
            return CodeProblem("path", f"{path} is not a repository-relative path")
        name = pure.as_posix()
        if name not in self._tracked:
            existing = (self._repo_root / name).is_file()
            return CodeProblem("path", f"{name} is not tracked by git" + (" (the file exists but is untracked)" if existing else " (no such file)"))
        if not isinstance(symbol, str) or not symbol.strip():
            return CodeProblem("symbol", f"the citation of {name} has no symbol")
        return self._symbol(name, symbol.strip())

    def _symbol(self, name: str, symbol: str) -> CodeProblem | None:
        suffix = PurePosixPath(name).suffix.lower()
        try:
            if name not in self._parsed:
                text = (self._repo_root / name).read_text(encoding="utf-8")
                if suffix == PYTHON_SUFFIX:
                    self._parsed[name] = python_symbols(text)
                elif suffix in YAML_SUFFIXES:
                    self._parsed[name] = yaml.safe_load(text)
                elif suffix == JSON_SUFFIX:
                    self._parsed[name] = json.loads(text)
                else:
                    self._parsed[name] = None
        except (OSError, UnicodeDecodeError, SyntaxError, ValueError, yaml.YAMLError) as error:
            return CodeProblem("symbol", f"{name} cannot be parsed ({type(error).__name__})")
        parsed = self._parsed[name]
        if suffix == PYTHON_SUFFIX:
            found = symbol in parsed
        elif suffix in YAML_SUFFIXES or suffix == JSON_SUFFIX:
            found = key_path_exists(parsed, symbol.split("."))
        else:
            return CodeProblem("symbol", f"{name} is neither Python, YAML nor JSON, so {symbol} cannot be resolved by name")
        return None if found else CodeProblem("symbol", f"{symbol} is not defined in {name}")


# -- contract-field inputs ---------------------------------------------------


def _descend(node: Any, segments: list[str]) -> bool:
    """Follow property names; step through array items or a map value schema when a name is not a property."""
    for position, segment in enumerate(segments):
        for _ in range(3):
            if not isinstance(node, dict):
                return False
            properties = effective_properties(node)
            if segment in properties:
                node = properties[segment]
                break
            if isinstance(node.get("items"), dict):
                node = node["items"]
            elif isinstance(node.get("additionalProperties"), dict):
                node = node["additionalProperties"]
            else:
                return False
        else:
            return False
        del position
    return True


def field_input_resolves(path: str, record: PropertyRecord, index: dict[str, dict[str, Any]]) -> bool:
    """A contract-field path: sibling-relative, then own-schema-relative, then ``Schema.property``."""
    segments = path.split(".")
    if not all(segments):
        return False
    first = segments[0]
    if first in record.siblings and _descend({"properties": record.siblings}, segments):
        return True
    if _descend(record.root, segments):
        return True
    return len(segments) > 1 and first in index and _descend(index[first], segments[1:])


# -- the check ---------------------------------------------------------------


def discover_modules(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and p.name not in NON_MODULE_DIRECTORIES and not p.name.startswith(".") and (p / ROOT_DOCUMENT).is_file())


def _shared_only_titles(root: Path, module: Path) -> frozenset[str]:
    shared = root / SHARED_DIRECTORY / SCHEMAS_DIRECTORY
    if not shared.is_dir():
        return frozenset()
    own = {p.stem for p in (module / SCHEMAS_DIRECTORY).glob("*.yaml")} if (module / SCHEMAS_DIRECTORY).is_dir() else set()
    return frozenset(p.stem for p in shared.glob("*.yaml") if p.stem != "_index" and p.stem not in own)


class _Check:
    def __init__(self, root: Path, repo_root: Path, modules: tuple[str, ...]) -> None:
        self.root = root
        self.repo_root = repo_root
        self.selected = modules
        self.report = Report()
        self.uses: Counter[tuple[str, str]] = Counter()
        self.users: dict[tuple[str, str], list[str]] = {}

    def add(self, code: str, record: PropertyRecord, detail: str) -> None:
        self.report.findings.append(Finding(code, record.subject, detail))

    def block(self, code: str, subject: str, detail: str) -> None:
        self.report.blocked.append(Finding(code, subject, detail))

    def run(self) -> Report:
        modules = [m for m in discover_modules(self.root) if not self.selected or m.name in self.selected]
        if not modules:
            self.block(
                "NO_MODULE",
                str(self.root),
                "no module (a directory with a root openapi.yaml) was found" + (f" among {', '.join(self.selected)}" if self.selected else ""),
            )
            return self.report
        try:
            resolver = CodeResolver(self.repo_root, tracked_files(self.repo_root))
        except GitUnavailableError as error:
            self.block("GIT_UNAVAILABLE", str(self.repo_root), str(error))
            return self.report
        for module in modules:
            self.check_module(module, resolver)
        self.finish()
        return self.report

    def check_module(self, module: Path, resolver: CodeResolver) -> None:
        try:
            tree = contract_resolver.resolve(module).tree
        except contract_resolver.ResolveError as error:
            self.block("RESOLVE_FAILED", module.name, str(error))
            return
        walk = SchemaWalk(module.name, tree, _shared_only_titles(self.root, module))
        before = dict(self.report.counts)
        for record in walk.records.values():
            self.check_property(record, walk.index, resolver)
        total, sourced, derived = (self.report.counts[key] - before[key] for key in ("properties", "x_source", "x_derived"))
        if total and sourced + derived != total:
            self.report.findings.append(Finding("COUNT_MISMATCH", module.name, f"x_source {sourced} + x_derived {derived} != properties {total}"))

    def check_property(self, record: PropertyRecord, index: dict[str, dict[str, Any]], resolver: CodeResolver) -> None:
        counts = self.report.counts
        counts["properties"] += 1
        has_derived = "x-derived" in record.node
        has_source = "x-source" in record.node and not (has_derived and self._inherits_source(record))
        counts["x_source"] += has_source
        counts["x_derived"] += has_derived
        if has_source and has_derived:
            self.add("BOTH_CITATIONS", record, "carries both x-source and x-derived; a property has exactly one")
        if not has_source and not has_derived:
            self.add("MISSING_CITATION", record, "has neither x-source nor x-derived")
        if has_source:
            self.check_source(record, record.node["x-source"], resolver)
        if has_derived:
            self.check_derived(record, record.node["x-derived"], index, resolver)

    def _inherits_source(self, record: PropertyRecord) -> bool:
        """True when the property's x-source is the one written on the root of the schema file it refers to."""
        title = record.node.get("title")
        if not isinstance(title, str):
            return False
        for directory in (self.root / record.module / SCHEMAS_DIRECTORY, self.root / SHARED_DIRECTORY / SCHEMAS_DIRECTORY):
            candidate = directory / f"{title}.yaml"
            if candidate.is_file():
                try:
                    document = yaml.safe_load(candidate.read_text(encoding="utf-8"))
                except (OSError, yaml.YAMLError):
                    return False
                return isinstance(document, dict) and "x-derived" not in document and document.get("x-source") == record.node.get("x-source")
        return False

    def note_use(self, record: PropertyRecord, path: Any, symbol: Any) -> None:
        if isinstance(path, str) and isinstance(symbol, str):
            self.uses[(path, symbol)] += 1
            self.users.setdefault((path, symbol), []).append(record.subject)

    def check_source(self, record: PropertyRecord, source: Any, resolver: CodeResolver) -> None:
        if not isinstance(source, dict):
            self.add("CITED_PATH_MISSING", record, "x-source is not a mapping with a path and a symbol")
            return
        self.note_use(record, source.get("path"), source.get("symbol"))
        problem = resolver.resolve(source.get("path"), source.get("symbol"))
        if problem is not None:
            self.add("CITED_PATH_MISSING" if problem.kind == "path" else "CITED_SYMBOL_UNRESOLVED", record, problem.detail)

    def check_derived(self, record: PropertyRecord, derived: Any, index: dict[str, dict[str, Any]], resolver: CodeResolver) -> None:
        if not isinstance(derived, dict) or set(derived) - {"rule", "inputs"}:
            self.add("BAD_DERIVED_FORM", record, "x-derived must be the structured form {rule, inputs}, not free text or a mapping with other keys")
            return
        rule = derived.get("rule")
        if not isinstance(rule, str) or not rule.strip():
            self.add("EMPTY_RULE", record, "x-derived has an empty or missing rule")
        inputs = derived.get("inputs")
        if inputs is None or inputs == []:
            self.add("EMPTY_INPUTS", record, "x-derived has an empty or missing inputs list")
            return
        if not isinstance(inputs, list):
            self.add("BAD_DERIVED_FORM", record, "x-derived inputs must be a list")
            return
        for entry in inputs:
            if isinstance(entry, str):
                if field_input_resolves(entry.strip(), record, index):
                    self.report.counts["inputs_resolved"] += 1
                else:
                    self.add(
                        "UNRESOLVED_INPUT",
                        record,
                        f"input {entry!r} is not a property of this schema or of {record.root_title}'s siblings, nor Schema.property of the module",
                    )
            elif isinstance(entry, dict) and set(entry) <= {"path", "symbol", "line"}:
                self.note_use(record, entry.get("path"), entry.get("symbol"))
                problem = resolver.resolve(entry.get("path"), entry.get("symbol"))
                if problem is None:
                    self.report.counts["inputs_resolved"] += 1
                else:
                    self.add("UNRESOLVED_INPUT", record, f"code input {problem.detail}")
            else:
                self.add("BAD_DERIVED_FORM", record, f"input {entry!r} is neither a property path string nor a {{path, symbol}} citation")

    def finish(self) -> None:
        counts = self.report.counts
        if counts["properties"] == 0:
            self.block("ZERO_PROPERTIES", str(self.root), "no property of any resource schema was traversed")
        elif counts["x_source"] + counts["x_derived"] == 0:
            self.block("ZERO_CITATIONS", str(self.root), "no property carries x-source or x-derived")
        for (path, symbol), number in sorted(self.uses.items()):
            if number > REUSE_LIMIT:
                self.report.info.append(
                    Finding(
                        "CITATION_REUSE",
                        f"{path}#{symbol}",
                        f"used by {number} properties (limit {REUSE_LIMIT}): {', '.join(sorted(self.users[(path, symbol)])[:3])}, ...",
                    )
                )


def check(root: str | Path, repo_root: str | Path = ".", modules: tuple[str, ...] = ()) -> Report:
    """Run the citation check over the modules under ``root``; ``repo_root`` is where cited paths live."""
    return _Check(Path(root), Path(repo_root), tuple(modules)).run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check that every property of every resource schema is cited.")
    parser.add_argument("--root", default="contracts", help="contracts root (default: contracts)")
    parser.add_argument("--repo-root", default=".", help="repository root cited paths are relative to (default: .)")
    parser.add_argument("--module", action="append", default=[], help="restrict to this module (repeatable)")
    arguments = parser.parse_args(argv)
    report = check(arguments.root, arguments.repo_root, tuple(arguments.module))
    for finding in (*report.blocked, *report.findings, *report.info):
        print(finding.render())
    print(report.counts_line())
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
