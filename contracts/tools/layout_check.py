"""Layout check for the top-level ``contracts/`` tree (spec FR-001).

A *module* is a direct subdirectory of the contracts root holding a root
``openapi.yaml``; ``_shared``, ``fixtures``, ``gradle`` and ``tools`` are never
modules. The check reads files only and fails, naming the offending path, when:

* ``PATH_FILE_NAME``: a mapped path file is not named after its path item (the
  path with ``/`` turned into ``_`` and each ``{param}`` turned into ``param``, plus
  ``.yaml``; ``contract_resolver.path_file_name`` is the one definition).
* ``MAPPED_FILE_MISSING``: the root ``openapi.yaml`` maps a path to a file that
  does not exist (or maps it inline, with no ``$ref``).
* ``ORPHAN_PATH_FILE``: a ``paths/`` file is mapped by no root entry.
* ``SCHEMA_NAME_MISMATCH``: a schema file's ``title`` is not its file stem.
* ``INDEX_MISSING_FILE`` / ``INDEX_OMITS_FILE`` / ``INDEX_MALFORMED``: an
  ``_index.yaml`` (``files: [...]``) lists a file that is absent, omits one that
  is present, or is not a mapping with a ``files`` list.
* ``BAD_REF_FORM``: a ``$ref`` is a URL, an absolute path, uses a ``~`` pointer or carries a
  brace in any spelling (path files are named brace-free).
* ``PATH_FILE_COLLISION``: two path items map to the same file name (``/a/{b}`` and
  ``/a/b`` both want ``a_b.yaml``).
* ``SHARED_MISUSE``: a ``$ref`` reaches into ``_shared/`` outside its admitted
  ``schemas/``, ``parameters/`` and ``responses/`` directories, or a ``_shared``
  piece depends on a piece inside a module (a module-specific piece in the
  cross-module tree). Which shared pieces ought to be shared at all is a review
  question the README's admission criteria answer; this rule checks the
  structure that can be checked.
* ``TRACKED_BUNDLE``: a module holds a bundled document, that is an OpenAPI
  document other than its root ``openapi.yaml``, or a root carrying
  ``components``. Build output directories are not scanned.
* ``UNREADABLE_FILE``: a YAML file cannot be parsed.

It cannot do its job (exit 2) when there is no module (``NO_MODULE``), no path
file was inspected (``ZERO_PATH_FILES``) or no ``_index.yaml`` was read
(``ZERO_INDEX``). Output: ``CONTRACT-CHECK layout_check: <CODE>: <path>: <detail>``
per violation and a last ``counts:`` line; exit 0 pass, 1 violation, 2 cannot
do its job.

Run as a bare script (``python contracts/tools/layout_check.py [--root DIR]``).
Standard library plus PyYAML; imports only sibling modules.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import yaml

import contract_resolver

CHECK_NAME = "layout_check"
NON_MODULE_DIRECTORIES = frozenset({"_shared", "fixtures", "gradle", "tools"})
SHARED_DIRECTORY = "_shared"
SHARED_ADMITTED = frozenset({"schemas", "parameters", "responses"})
INDEXED_DIRECTORIES = ("schemas", "parameters", "responses", "examples")
INDEX_REQUIRED_DIRECTORIES = frozenset({"schemas", "parameters", "responses"})
INDEX_NAME = "_index.yaml"
ROOT_DOCUMENT = "openapi.yaml"
PATHS_DIRECTORY = "paths"
SCHEMAS_DIRECTORY = "schemas"
SKIPPED_DIRECTORIES = frozenset({"build", ".gradle", "node_modules"})
YAML_SUFFIXES = (".yaml", ".yml")


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    detail: str

    def render(self) -> str:
        return f"CONTRACT-CHECK {CHECK_NAME}: {self.code}: {self.path}: {self.detail}"


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    blocked: list[Finding] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=lambda: {"modules": 0, "path_files": 0, "index_files": 0})

    @property
    def exit_code(self) -> int:
        if self.blocked:
            return 2
        return 1 if self.findings else 0

    def counts_line(self) -> str:
        return "counts: " + " ".join(f"{key}={value}" for key, value in self.counts.items())


class _Check:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.report = Report()
        self._documents: dict[Path, Any] = {}

    # -- helpers -----------------------------------------------------------

    def rel(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return path.name

    def add(self, code: str, path: Path, detail: str) -> None:
        self.report.findings.append(Finding(code, self.rel(path), detail))

    def load(self, path: Path) -> Any:
        if path not in self._documents:
            try:
                self._documents[path] = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (yaml.YAMLError, UnicodeDecodeError) as error:
                self._documents[path] = None
                self.add("UNREADABLE_FILE", path, str(error).splitlines()[0] if str(error) else type(error).__name__)
        return self._documents[path]

    def yaml_files(self, directory: Path) -> list[Path]:
        return sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix in YAML_SUFFIXES and not self._skipped(p, directory))

    @staticmethod
    def _skipped(path: Path, base: Path) -> bool:
        return any(part in SKIPPED_DIRECTORIES for part in path.relative_to(base).parts)

    # -- discovery ---------------------------------------------------------

    def modules(self) -> list[Path]:
        if not self.root.is_dir():
            return []
        return sorted(p for p in self.root.iterdir() if p.is_dir() and p.name not in NON_MODULE_DIRECTORIES and (p / ROOT_DOCUMENT).is_file())

    # -- rules -------------------------------------------------------------

    def check_paths(self, module: Path) -> None:
        root_doc_path = module / ROOT_DOCUMENT
        document = self.load(root_doc_path)
        mapped: set[Path] = set()
        entries = document.get("paths") if isinstance(document, dict) else None
        names: dict[str, str] = {}
        for path_key, entry in (entries or {}).items():
            self._check_collision(root_doc_path, str(path_key), names)
            target = self._mapped_target(module, root_doc_path, str(path_key), entry)
            if target is not None:
                mapped.add(target)
        paths_dir = module / PATHS_DIRECTORY
        present = sorted(p for p in paths_dir.glob("*") if p.is_file() and p.suffix in YAML_SUFFIXES) if paths_dir.is_dir() else []
        self.report.counts["path_files"] += len(present)
        for path_file in present:
            if path_file.resolve() not in mapped:
                self.add("ORPHAN_PATH_FILE", path_file, "no entry of the root openapi.yaml maps this file")

    def _check_collision(self, root_doc_path: Path, path_key: str, names: dict[str, str]) -> None:
        name = contract_resolver.path_file_name(path_key)
        if name is None:
            return
        if name in names:
            self.add("PATH_FILE_COLLISION", root_doc_path, f"paths {names[name]!r} and {path_key!r} both map to {name!r}")
        else:
            names[name] = path_key

    def _mapped_target(self, module: Path, root_doc_path: Path, path_key: str, entry: Any) -> Path | None:
        ref = entry.get("$ref") if isinstance(entry, dict) else None
        if not isinstance(ref, str):
            self.add("MAPPED_FILE_MISSING", root_doc_path, f"path {path_key!r} has no $ref to a path file")
            return None
        file_part = unquote(ref.partition("#")[0])
        target = (module / file_part).resolve()
        if not target.is_file():
            self.add("MAPPED_FILE_MISSING", root_doc_path, f"path {path_key!r} maps {file_part!r}, which does not exist")
            return None
        expected = contract_resolver.path_file_name(path_key)
        if target.parent != (module / PATHS_DIRECTORY).resolve() or target.name != expected:
            self.add("PATH_FILE_NAME", target, f"path {path_key!r} must live in {PATHS_DIRECTORY}/{expected}")
        return target

    def check_schema_names(self, directory: Path) -> None:
        for schema_file in sorted(directory.glob("*")):
            if not schema_file.is_file() or schema_file.suffix not in YAML_SUFFIXES or schema_file.name == INDEX_NAME:
                continue
            document = self.load(schema_file)
            title = document.get("title") if isinstance(document, dict) else None
            if title != schema_file.stem:
                self.add("SCHEMA_NAME_MISMATCH", schema_file, f"file defines {title!r}, expected title {schema_file.stem!r}")

    def check_indexes(self, base: Path) -> None:
        for name in INDEXED_DIRECTORIES:
            directory = base / name
            if not directory.is_dir():
                continue
            files = sorted(p.name for p in directory.glob("*") if p.is_file() and p.name != INDEX_NAME and p.suffix in (*YAML_SUFFIXES, ".json"))
            index_path = directory / INDEX_NAME
            if not index_path.is_file():
                if name in INDEX_REQUIRED_DIRECTORIES:
                    for missing in files:
                        self.add("INDEX_OMITS_FILE", directory / missing, f"{directory.name}/ has no {INDEX_NAME}")
                continue
            self.report.counts["index_files"] += 1
            self._compare_index(index_path, files)

    def _compare_index(self, index_path: Path, files: list[str]) -> None:
        document = self.load(index_path)
        listed = document.get("files") if isinstance(document, dict) else None
        if not isinstance(listed, list) or not all(isinstance(item, str) for item in listed):
            self.add("INDEX_MALFORMED", index_path, "expected a mapping with a `files` list of file names")
            return
        for ghost in sorted(set(listed) - set(files)):
            self.add("INDEX_MISSING_FILE", index_path, f"lists {ghost!r}, which does not exist")
        for omitted in sorted(set(files) - set(listed)):
            self.add("INDEX_OMITS_FILE", index_path, f"does not list {omitted!r}")

    def check_refs(self, base: Path, *, inside_shared: bool) -> None:
        for yaml_file in self.yaml_files(base):
            if yaml_file.name == INDEX_NAME:
                continue
            for ref in _collect_refs(self.load(yaml_file)):
                self._check_ref(yaml_file, ref, inside_shared=inside_shared)

    def _check_ref(self, origin: Path, ref: str, *, inside_shared: bool) -> None:
        refused = contract_resolver.refusal_code_for_ref(ref)
        if refused is not None:
            self.add("BAD_REF_FORM", origin, f"{ref!r} is refused: {refused}")
            return
        file_part = ref.partition("#")[0]
        if not file_part:
            return
        decoded = unquote(file_part)
        target = (origin.parent / decoded).resolve()
        self._check_shared_use(origin, ref, target, inside_shared=inside_shared)

    def _check_shared_use(self, origin: Path, ref: str, target: Path, *, inside_shared: bool) -> None:
        shared_root = (self.root / SHARED_DIRECTORY).resolve()
        if shared_root in target.parents:
            admitted = target.relative_to(shared_root).parts[:1]
            if not admitted or admitted[0] not in SHARED_ADMITTED:
                self.add("SHARED_MISUSE", origin, f"{ref!r} reaches into {SHARED_DIRECTORY}/ outside {sorted(SHARED_ADMITTED)}")
        elif inside_shared and self.root.resolve() in target.parents:
            self.add("SHARED_MISUSE", origin, f"{ref!r} makes a {SHARED_DIRECTORY}/ piece depend on a module-specific piece")

    def check_bundles(self, module: Path) -> None:
        for yaml_file in self.yaml_files(module):
            document = self.load(yaml_file)
            if not isinstance(document, dict) or "openapi" not in document:
                continue
            if yaml_file == module / ROOT_DOCUMENT:
                if "components" in document:
                    self.add("TRACKED_BUNDLE", yaml_file, "the root openapi.yaml carries components, so it is a bundled document")
            else:
                self.add("TRACKED_BUNDLE", yaml_file, "an OpenAPI document other than the root openapi.yaml is a bundled document")

    # -- orchestration -----------------------------------------------------

    def run(self) -> Report:
        modules = self.modules()
        self.report.counts["modules"] = len(modules)
        if not modules:
            self.report.blocked.append(Finding("NO_MODULE", ".", f"no module (a directory with a root {ROOT_DOCUMENT}) under {self.root.name!r}"))
            return self.report
        for module in modules:
            self.check_paths(module)
            self.check_indexes(module)
            if (module / SCHEMAS_DIRECTORY).is_dir():
                self.check_schema_names(module / SCHEMAS_DIRECTORY)
            self.check_refs(module, inside_shared=False)
            self.check_bundles(module)
        shared = self.root / SHARED_DIRECTORY
        if shared.is_dir():
            self.check_indexes(shared)
            if (shared / SCHEMAS_DIRECTORY).is_dir():
                self.check_schema_names(shared / SCHEMAS_DIRECTORY)
            self.check_refs(shared, inside_shared=True)
        self._floors()
        return self.report

    def _floors(self) -> None:
        if self.report.counts["path_files"] == 0:
            self.report.blocked.append(Finding("ZERO_PATH_FILES", ".", "no file under any paths/ directory was inspected"))
        if self.report.counts["index_files"] == 0:
            self.report.blocked.append(Finding("ZERO_INDEX", ".", f"no {INDEX_NAME} was read"))


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


def check(root: str | Path) -> Report:
    """Run every layout rule over the contracts tree at ``root``."""
    return _Check(Path(root)).run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the layout of the contracts tree.")
    parser.add_argument("--root", default="contracts", help="contracts root (default: contracts)")
    arguments = parser.parse_args(argv)
    report = check(arguments.root)
    for finding in (*report.blocked, *report.findings):
        print(finding.render())
    print(report.counts_line())
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
