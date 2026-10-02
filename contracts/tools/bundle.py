"""Validate every contract module and bundle it with the ``openapi-yaml`` generator (FR-014).

For each module (a direct subdirectory of ``--root`` holding a root
``openapi.yaml``; ``_shared``, ``fixtures``, ``gradle`` and ``tools`` are never
modules) this runs the pinned Gradle build in ``contracts/`` (``validate_<module>``
then ``bundle_<module>``) and checks the staged bundle. The bundle is a build
product: it is written under ``--out``, which must lie outside the repository
tree, and is never committed.

Failure codes (exit 1), printed as ``CONTRACT-CHECK bundle: <CODE>: <module>: <detail>``:

* ``VALIDATION_FAILED``: the generator's OpenAPI validator rejected the module.
* ``BUNDLE_FAILED``: the bundle task failed for a reason other than validation.
* ``BUNDLE_EMPTY``: the bundle file is missing or empty.
* ``FEWER_THAN_FIVE_PATHS``: the bundle has fewer path items than ``--min-paths`` (default five).
* ``UNRESOLVED_REFERENCE_LEFT``: the bundle still holds a ``$ref`` that is not an internal pointer
  that resolves.

Cannot do its job (exit 2): ``NO_MODULE``, ``MODULE_WITHOUT_ROOT``, ``JVM_MISSING``,
``GRADLE_MISSING``, ``PLUGIN_RESOLUTION_FAILED``, ``DEPENDENCY_VERIFICATION_FAILED``,
``BUILD_SCRIPT_FAILED`` (the Gradle build itself failed to configure)
and ``OUT_INSIDE_REPOSITORY``. The last line is always
``counts: modules=N bundles=N path_items=N``. Determinism (bundling twice and
comparing digests) is added by the hardening work package.

``--write-verification-metadata`` makes Gradle record the sha256 of every
dependency it resolves into ``contracts/gradle/verification-metadata.xml`` (the
only way that file is produced; it is never edited by hand).

Run as a bare script (``python contracts/tools/bundle.py --root DIR --out DIR``).
Standard library plus PyYAML; imports only sibling modules.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CHECK_NAME = "bundle"
NON_MODULE_DIRECTORIES = frozenset({"_shared", "fixtures", "gradle", "tools", "build", "node_modules"})
ROOT_DOCUMENT = "openapi.yaml"
MODULE_HINT_DIRECTORIES = frozenset({"paths", "schemas", "parameters", "responses", "examples"})
DEFAULT_MIN_PATHS = 5
GRADLE_PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]
GRADLE_TIMEOUT_SECONDS = 1200
DETAIL_LINES = 12

Runner = Callable[[list[str]], tuple[int, str]]
Which = Callable[[str], str | None]


def subprocess_runner(command: list[str]) -> tuple[int, str]:
    """Run ``command`` (an argument list, never a shell string) and return its exit status and combined output."""
    completed = subprocess.run(  # noqa: S603 -- argument list built here, binary resolved with shutil.which, no shell
        command, capture_output=True, text=True, timeout=GRADLE_TIMEOUT_SECONDS, check=False
    )
    return completed.returncode, completed.stdout + completed.stderr


@dataclass
class Report:
    findings: list[str] = field(default_factory=list)
    modules: int = 0
    bundles: int = 0
    path_items: int = 0

    def counts_line(self) -> str:
        return f"counts: modules={self.modules} bundles={self.bundles} path_items={self.path_items}"


def finding(code: str, module: str, detail: str, check: str = CHECK_NAME) -> str:
    return f"CONTRACT-CHECK {check}: {code}: {module}: {detail}"


def discover_modules(root: Path) -> tuple[list[Path], list[Path]]:
    """Return ``(modules, directories that look like a module but have no root document)``."""
    modules: list[Path] = []
    without_root: list[Path] = []
    for child in sorted(root.iterdir()) if root.is_dir() else []:
        if not child.is_dir() or child.name in NON_MODULE_DIRECTORIES or child.name.startswith("."):
            continue
        if (child / ROOT_DOCUMENT).is_file():
            modules.append(child)
        elif any((child / hint).is_dir() for hint in MODULE_HINT_DIRECTORIES):
            without_root.append(child)
    return modules, without_root


def repository_root(start: Path) -> Path | None:
    """The nearest ancestor of ``start`` holding a ``.git`` entry (a directory, or a file in a linked worktree)."""
    resolved = start.resolve()
    return next((ancestor for ancestor in (resolved, *resolved.parents) if (ancestor / ".git").exists()), None)


def inside_repository(path: Path) -> bool:
    """True when ``path`` lies inside the git working tree that holds this contracts build."""
    root = repository_root(GRADLE_PROJECT_DIRECTORY)
    resolved = path.resolve()
    return root is not None and (resolved == root or root in resolved.parents)


def staged_files(directory: Path) -> str:
    """A short listing of what the generator did write, for the message of an empty bundle."""
    files = sorted(path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()) if directory.is_dir() else []
    return ", ".join(files[:DETAIL_LINES]) or "none"


def find_unresolved_refs(document: Any) -> list[str]:
    """``$ref`` values that are not internal pointers resolving inside ``document``."""
    bad: list[str] = []

    def resolves(pointer: str) -> bool:
        node: Any = document
        for token in pointer.removeprefix("#/").split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            if isinstance(node, dict) and token in node:
                node = node[token]
            elif isinstance(node, list) and token.isdigit() and int(token) < len(node):
                node = node[int(token)]
            else:
                return False
        return True

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "$ref" and isinstance(value, str):
                    if not (value.startswith("#/") and resolves(value)):
                        bad.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(document)
    return bad


def check_bundle(module: str, out_dir: Path, min_paths: int, report: Report) -> None:
    """Check the staged bundle of one module and record what it finds on ``report``."""
    bundle_file = out_dir / "bundle" / module / ROOT_DOCUMENT
    document = yaml.safe_load(bundle_file.read_text(encoding="utf-8")) if bundle_file.is_file() else None
    if not isinstance(document, dict) or not document:
        report.findings.append(finding("BUNDLE_EMPTY", module, f"{bundle_file.name} is missing or empty; files staged: {staged_files(bundle_file.parent)}"))
        return
    report.bundles += 1
    paths = document.get("paths")
    count = len(paths) if isinstance(paths, dict) else 0
    report.path_items += count
    if count < min_paths:
        report.findings.append(finding("FEWER_THAN_FIVE_PATHS", module, f"{count} path items, floor is {min_paths}"))
    left = find_unresolved_refs(document)
    if left:
        report.findings.append(finding("UNRESOLVED_REFERENCE_LEFT", module, f"{len(left)} reference(s) left, first {left[0]!r}"))


def tail(output: str) -> str:
    lines = [line for line in output.splitlines() if line.strip()]
    return " | ".join(lines[-DETAIL_LINES:])


def classify_gradle_failure(output: str, module: str) -> tuple[str, int]:
    """Map failed Gradle output to ``(code, exit status)``: toolchain failures are exit 2, a rejected module is exit 1."""
    if "Dependency verification failed" in output:
        return "DEPENDENCY_VERIFICATION_FAILED", 2
    if "A problem occurred configuring" in output:
        return "BUILD_SCRIPT_FAILED", 2
    if "Plugin [id:" in output or "Could not resolve" in output or "Could not GET" in output:
        return "PLUGIN_RESOLUTION_FAILED", 2
    if f"task ':validate_{module}'" in output:
        return "VALIDATION_FAILED", 1
    return "BUNDLE_FAILED", 1


def gradle_command(gradle: str, root: Path, out: Path, tasks: Sequence[str], *, write_metadata: bool) -> list[str]:
    command = [gradle, "--no-daemon", "--console=plain", "-p", str(GRADLE_PROJECT_DIRECTORY), f"-PcontractsRoot={root.resolve()}", f"-PoutDir={out.resolve()}"]
    if write_metadata:
        command += ["--write-verification-metadata", "sha256"]
    return [*command, *tasks]


def run(argv: Sequence[str] | None = None, *, runner: Runner = subprocess_runner, which: Which = shutil.which, out: Callable[[str], None] = print) -> int:
    parser = argparse.ArgumentParser(description="Validate and bundle every contract module.")
    parser.add_argument("--root", default="contracts", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--module", action="append", default=[], help="restrict to this module (repeatable)")
    parser.add_argument("--min-paths", type=int, default=DEFAULT_MIN_PATHS)
    parser.add_argument("--write-verification-metadata", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="print the full Gradle output of every module")
    args = parser.parse_args(argv)

    report = Report()

    def blocked(code: str, detail: str) -> int:
        out(f"CONTRACT-CHECK {CHECK_NAME}: {code}: {detail}")
        out(report.counts_line())
        return 2

    modules, without_root = discover_modules(args.root)
    if without_root:
        return blocked("MODULE_WITHOUT_ROOT", f"{without_root[0].name} has no {ROOT_DOCUMENT}")
    if args.module:
        modules = [module for module in modules if module.name in args.module]
    if not modules:
        return blocked("NO_MODULE", f"no module with a root {ROOT_DOCUMENT} under {args.root}")
    if inside_repository(args.out):
        return blocked("OUT_INSIDE_REPOSITORY", f"{args.out} is inside the repository working tree; stage bundles outside the repository")
    java, gradle = which("java"), which("gradle")
    if java is None:
        return blocked("JVM_MISSING", "no java on PATH (the workflow installs the pinned JDK before this step)")
    if gradle is None:
        return blocked("GRADLE_MISSING", "no gradle on PATH (run install_tools.py first)")

    report.modules = len(modules)
    for module in modules:
        status, output = runner(
            gradle_command(gradle, args.root, args.out, (f"validate_{module.name}", f"bundle_{module.name}"), write_metadata=args.write_verification_metadata)
        )
        if args.verbose:
            out(f"--- gradle output for {module.name} (exit {status}) ---\n{output}\n--- end ---")
        if status != 0:
            code, exit_status = classify_gradle_failure(output, module.name)
            if exit_status == 2:
                return blocked(code, f"{module.name}: {tail(output)}")
            report.findings.append(finding(code, module.name, tail(output)))
            continue
        check_bundle(module.name, args.out, args.min_paths, report)

    for line in report.findings:
        out(line)
    out(report.counts_line())
    return 1 if report.findings else 0


if __name__ == "__main__":
    sys.exit(run())
