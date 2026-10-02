"""Generate a throwaway TypeScript client from the SPLIT contract files (plan D-P13).

For each module (a direct subdirectory of ``--root`` holding a root
``openapi.yaml``) this runs the pinned Gradle build's ``clientSmoke_<module>`` task,
the openapi-generator ``typescript-fetch`` generator pointed at the split root
document, so a reference layout the generator reads badly is found long before a
consumer meets it. Generation only: the output is staged under ``--out`` (outside
the repository tree), counted, and never compiled (compiling needs Node, which
this repository does not use, C-005).

Failure codes (exit 1), printed as ``CONTRACT-CHECK client_smoke: <CODE>: <module>: <detail>``:

* ``GENERATION_FAILED``: the generator exited non-zero, or printed a warning that
  matches ``FATAL_WARNING_PATTERNS`` / ``--fail-on-warning`` (the condition the
  pushed spike run proved). The detail carries the generator's own message.

Cannot do its job (exit 2): ``NO_MODULE``, ``ZERO_FILES_EMITTED``, ``JVM_MISSING``,
``GRADLE_MISSING``, plus the toolchain failures ``bundle.py`` shares
(``PLUGIN_RESOLUTION_FAILED``, ``DEPENDENCY_VERIFICATION_FAILED``,
``OUT_INSIDE_REPOSITORY``). The last line is always
``counts: modules=N files_emitted=N generator_warnings=N``.

Run as a bare script (``python contracts/tools/client_smoke.py --root DIR --out DIR``).
Standard library only; imports only sibling modules.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

import bundle

CHECK_NAME = "client_smoke"
# Warning texts that mean the generator read the contract wrongly although it exited 0.
# Filled only from a pushed spike run that observed the text; empty until then.
FATAL_WARNING_PATTERNS: tuple[str, ...] = ()
_WARNING_LINE = re.compile(r"\bWARN\b")
GENERATOR_METADATA_DIRECTORY = ".openapi-generator"


def count_emitted(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    return sum(1 for path in directory.rglob("*") if path.is_file() and GENERATOR_METADATA_DIRECTORY not in path.parts)


def count_warnings(output: str) -> int:
    return sum(1 for line in output.splitlines() if _WARNING_LINE.search(line))


def fatal_warnings(module: str, output: str, fatal: Sequence[re.Pattern[str]]) -> list[str]:
    """One ``GENERATION_FAILED`` finding when a warning line matches a pattern the spike proved fatal."""
    matched = [line for line in output.splitlines() if _WARNING_LINE.search(line) and any(pattern.search(line) for pattern in fatal)]
    return [bundle.finding("GENERATION_FAILED", module, f"fatal generator warning: {matched[0].strip()}", CHECK_NAME)] if matched else []


def run(
    argv: Sequence[str] | None = None, *, runner: bundle.Runner = bundle.subprocess_runner, which: bundle.Which = shutil.which, out: Callable[[str], None] = print
) -> int:
    parser = argparse.ArgumentParser(description="Generate a TypeScript client from the split contract files.")
    parser.add_argument("--root", default="contracts", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--module", action="append", default=[], help="restrict to this module (repeatable)")
    parser.add_argument("--fail-on-warning", action="append", default=[], metavar="REGEX", help="a generator warning that fails the smoke (repeatable)")
    parser.add_argument("--write-verification-metadata", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="print the full Gradle output of every module")
    args = parser.parse_args(argv)

    modules_seen = files_emitted = warnings = 0

    def counts_line() -> str:
        return f"counts: modules={modules_seen} files_emitted={files_emitted} generator_warnings={warnings}"

    def blocked(code: str, detail: str) -> int:
        out(f"CONTRACT-CHECK {CHECK_NAME}: {code}: {detail}")
        out(counts_line())
        return 2

    modules, without_root = bundle.discover_modules(args.root)
    if without_root:
        return blocked("MODULE_WITHOUT_ROOT", f"{without_root[0].name} has no {bundle.ROOT_DOCUMENT}")
    if args.module:
        modules = [module for module in modules if module.name in args.module]
    if not modules:
        return blocked("NO_MODULE", f"no module with a root {bundle.ROOT_DOCUMENT} under {args.root}")
    if bundle.inside_repository(args.out):
        return blocked("OUT_INSIDE_REPOSITORY", f"{args.out} is inside the repository working tree; stage output outside it")
    if which("java") is None:
        return blocked("JVM_MISSING", "no java on PATH (the workflow installs the pinned JDK before this step)")
    gradle = which("gradle")
    if gradle is None:
        return blocked("GRADLE_MISSING", "no gradle on PATH (run install_tools.py first)")

    fatal = [re.compile(pattern) for pattern in (*FATAL_WARNING_PATTERNS, *args.fail_on_warning)]
    modules_seen = len(modules)
    findings: list[str] = []
    for module in modules:
        status, output = runner(
            bundle.gradle_command(gradle, args.root, args.out, (f"clientSmoke_{module.name}",), write_metadata=args.write_verification_metadata)
        )
        if args.verbose:
            out(f"--- gradle output for {module.name} (exit {status}) ---\n{output}\n--- end ---")
        warnings += count_warnings(output)
        if status != 0:
            code, exit_status = bundle.classify_gradle_failure(output, module.name)
            if exit_status == 2:
                return blocked(code, f"{module.name}: {bundle.tail(output)}")
            findings.append(bundle.finding("GENERATION_FAILED", module.name, bundle.tail(output), CHECK_NAME))
            continue
        emitted = count_emitted(args.out / "client" / module.name)
        files_emitted += emitted
        if emitted == 0:
            return blocked("ZERO_FILES_EMITTED", f"{module.name}: the generator exited 0 but emitted no file")
        findings.extend(fatal_warnings(module.name, output, fatal))

    for line in findings:
        out(line)
    out(counts_line())
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(run())
