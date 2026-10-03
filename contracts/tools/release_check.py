"""Dry-run of a contract release: tag rules, build, checksum, and the exact ``gh release create`` arguments (FR-022, D-17).

``--root`` is the contracts root. With ``--tag contract-<module>-v<semver>`` (a tag push) only that module is
checked; without a tag (a pull request or a dry run) the candidate tag ``contract-<module>-v<info.version>`` is
derived for every module. Tag rules, each with its stable code (exit 1), printed as
``CONTRACT-CHECK release_check: <CODE>: <tag>: <detail>``:

* ``TAG_FORM``: not ``contract-<module>-v<semver>`` (module in lower-case letters, digits and hyphens).
* ``SNAPSHOT_RELEASE_REFUSED``: the tag's version ends in ``-SNAPSHOT``. A snapshot is the work in progress of a version
  (``1.0.0-SNAPSHOT`` precedes ``1.0.0``) and is never released: the refusal comes right after the form check, before the
  module is looked at, and nothing is built. It applies to a tag that was given (a tag push); a tag-less dry run derives its
  tag from ``info.version``, so for a snapshot module it still builds, checksums and verifies the bundle, prints
  ``SNAPSHOT_DRY_RUN`` and no release command.
* ``MODULE_UNKNOWN``: the tag names a module that is not under the root.
* ``VERSION_MISMATCH``: the tag's semver is not the module's ``info.version``.
* ``CHANGELOG_HEADING_MISSING``: the module ``CHANGELOG.md`` has no heading for that version.
* ``CHECKSUM_MISMATCH``: the written ``openapi.yaml.sha256`` does not verify (``sha256sum -c`` semantics).

A module that passes its rules is built through the shared build wrapper (``bundle.py``, its ``--bundle-only``
path: written twice, digests compared), the bundle is copied to ``<out>/release/<module>/openapi.yaml`` with its
``openapi.yaml.sha256`` beside it, the checksum is verified, and the exact argument list of the release command
is printed as ``GH_RELEASE_ARGS gh release create ...``. It always carries ``--latest=false``, ``--verify-tag`` and the
release notes, and carries ``--prerelease`` only for a prerelease semver (a ``-`` before any ``+`` build metadata). With
``--args-file FILE`` (a tag run only) the arguments after ``gh release create`` are also written there, one per line,
so the publishing step runs exactly what this check approved instead of deriving a second argument list. This script
never runs ``gh`` and never publishes.

Cannot do its job (exit 2): ``MODULE_ROOT_EMPTY`` (the root is absent or empty), ``NO_MODULE``, ``BUNDLE_EMPTY``,
``BUNDLE_STEP_BLOCKED`` (the bundle step itself exited 2, for example an output directory inside the repository;
nothing is checksummed) and ``ARGS_FILE_NEEDS_TAG`` (``--args-file`` without ``--tag``).
The last line is always ``counts: modules=N bundles=N verified=N``.

Run as a bare script (``python contracts/tools/release_check.py --root contracts --out DIR [--tag TAG]``).
Standard library, PyYAML and the sibling ``bundle``.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shlex
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

import bundle

CHECK_NAME = "release_check"
SNAPSHOT_SUFFIX = "-SNAPSHOT"
CHECKSUM_FILE = "openapi.yaml.sha256"
BUNDLE_FILE = "openapi.yaml"
SEMVER_PATTERN = r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?"
TAG_PATTERN = re.compile(rf"^contract-(?P<module>[a-z0-9]+(?:-[a-z0-9]+)*)-v(?P<version>{SEMVER_PATTERN})$")
CHECKSUM_LINE = re.compile(r"^(?P<digest>[0-9a-fA-F]{64}) [ *](?P<name>[^/\\\s][^/\\]*)$")


@dataclass
class Report:
    findings: list[str] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)
    modules: int = 0
    bundles: int = 0
    verified: int = 0

    def counts_line(self) -> str:
        return f"counts: modules={self.modules} bundles={self.bundles} verified={self.verified}"


def finding(code: str, subject: str, detail: str) -> str:
    return f"CONTRACT-CHECK {CHECK_NAME}: {code}: {subject}: {detail}"


def is_prerelease(version: str) -> bool:
    """True for a semver with a prerelease part (``1.0.0-rc.1``); build metadata alone is not a prerelease."""
    return "-" in version.split("+", 1)[0]


def is_snapshot(version: str) -> bool:
    """True for a version that is the work in progress of a release (``1.0.0-SNAPSHOT``); build metadata is ignored."""
    return version.split("+", 1)[0].endswith(SNAPSHOT_SUFFIX)


def release_arguments(tag: str, assets: Sequence[str], *, prerelease: bool, notes: str) -> list[str]:
    """The exact argument list of the release command. ``--latest=false`` and ``--verify-tag`` are always present."""
    arguments = ["gh", "release", "create", tag, *assets, "--title", tag, "--latest=false", "--verify-tag", "--notes", notes]
    if prerelease:
        arguments.append("--prerelease")
    return arguments


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()  # noqa: TID251 -- file-integrity digest of a bundle, not the charter hash


def write_checksum(directory: Path) -> None:
    """Write ``openapi.yaml.sha256`` in the ``sha256sum`` format for the bundle in ``directory``."""
    (directory / CHECKSUM_FILE).write_text(f"{_digest(directory / BUNDLE_FILE)}  {BUNDLE_FILE}\n", encoding="utf-8", newline="\n")


def verify_checksum(directory: Path) -> str | None:
    """Verify ``openapi.yaml.sha256`` as ``sha256sum -c`` does. Returns an error text, or ``None`` when it verifies."""
    checksum = directory / CHECKSUM_FILE
    if not checksum.is_file():
        return f"{CHECKSUM_FILE} is missing"
    lines = [line for line in checksum.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return f"{CHECKSUM_FILE} is empty"
    for line in lines:
        match = CHECKSUM_LINE.match(line)
        if match is None:
            return f"{CHECKSUM_FILE} holds a line that is not '<sha256>  <file>': {line!r}"
        target = directory / match["name"]
        if not target.is_file():
            return f"{CHECKSUM_FILE} names {match['name']}, which is not there"
        if _digest(target) != match["digest"].lower():
            return f"{match['name']} does not match its recorded sha256"
    return None


def changelog_has_heading(module_dir: Path, version: str) -> bool:
    changelog = module_dir / "CHANGELOG.md"
    if not changelog.is_file():
        return False
    pattern = re.compile(rf"^#{{1,6}}\s+\[?{re.escape(version)}\]?(\s|$)", re.MULTILINE)
    return pattern.search(changelog.read_text(encoding="utf-8")) is not None


def module_version(module_dir: Path) -> str:
    document: Any = yaml.safe_load((module_dir / bundle.ROOT_DOCUMENT).read_text(encoding="utf-8"))
    info = document.get("info") if isinstance(document, dict) else None
    return str(info.get("version", "")) if isinstance(info, dict) else ""


def candidate_tags(modules: Sequence[Path], tag: str | None) -> list[tuple[str, Path | None]]:
    """``(tag, module directory or None)`` pairs: the given tag, or one derived tag per module."""
    if tag is not None:
        match = TAG_PATTERN.match(tag)
        by_name = {module.name: module for module in modules}
        return [(tag, by_name.get(match["module"]) if match else None)]
    return [(f"contract-{module.name}-v{module_version(module)}", module) for module in modules]


def rule_violation(tag: str, module_dir: Path | None, *, derived: bool = False) -> tuple[str, str] | None:
    """The first tag rule ``tag`` breaks, as ``(code, detail)``. A ``derived`` tag (a tag-less dry run) may carry -SNAPSHOT."""
    match = TAG_PATTERN.match(tag)
    if match is None:
        return "TAG_FORM", "the tag is not contract-<module>-v<semver> (module: lower-case letters, digits and hyphens)"
    if not derived and is_snapshot(match["version"]):
        return "SNAPSHOT_RELEASE_REFUSED", f"{match['version']} is a snapshot, the work in progress of a version; release the version without {SNAPSHOT_SUFFIX}"
    if module_dir is None:
        return "MODULE_UNKNOWN", f"no module {match['module']!r} with a root {bundle.ROOT_DOCUMENT} under the root"
    version = module_version(module_dir)
    if match["version"] != version:
        return "VERSION_MISMATCH", f"the tag says {match['version']} but info.version of {module_dir.name} is {version!r}"
    if not changelog_has_heading(module_dir, version):
        return "CHANGELOG_HEADING_MISSING", f"{module_dir.name}/CHANGELOG.md has no heading for {version}"
    return None


def build_bundle(root: Path, out_dir: Path, module: str, min_paths: int, lines: list[str]) -> int:
    """Build ``module`` through ``bundle.py`` (bundle-only path); returns its exit status. Its output goes to ``lines``."""
    arguments = ["--root", str(root), "--out", str(out_dir), "--module", module, "--bundle-only", "--min-paths", str(min_paths)]
    return bundle.run(
        arguments,
        out=lambda line: None if line.startswith("counts:") else lines.append(line),  # one counts line, ours, ends the output
        writer=bundle.write_bundle,
    )


def release_module(tag: str, module_dir: Path, args: argparse.Namespace, report: Report) -> tuple[str, str] | None:
    """Build, checksum, verify and print the release arguments for one module.

    Returns ``(code, detail)`` when the check cannot do its job (exit 2), otherwise ``None``.
    """
    status = build_bundle(args.root, args.out, module_dir.name, args.min_paths, report.lines)
    built = args.out / "bundle" / module_dir.name / BUNDLE_FILE
    if status == 2:
        refusal = next((line for line in report.lines if line.startswith("CONTRACT-CHECK bundle:")), "the bundle step could not run")
        return "BUNDLE_STEP_BLOCKED", refusal
    if not built.is_file() or built.stat().st_size == 0:
        return "BUNDLE_EMPTY", f"{module_dir.name}: the written bundle is missing or empty"
    if status != 0:
        report.findings.extend(line for line in report.lines if line.startswith("CONTRACT-CHECK bundle:"))
        return None
    report.bundles += 1
    directory = args.out / "release" / module_dir.name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / BUNDLE_FILE).write_bytes(built.read_bytes())
    write_checksum(directory)
    problem = verify_checksum(directory)
    if problem is not None:
        report.findings.append(finding("CHECKSUM_MISMATCH", tag, problem))
        return None
    report.verified += 1
    match = TAG_PATTERN.match(tag)
    assert match is not None  # the tag passed its form rule
    assets = [str(directory / BUNDLE_FILE), str(directory / CHECKSUM_FILE)]
    notes = f"Contract {match['module']} {match['version']}. Verify the bundle with: sha256sum -c {CHECKSUM_FILE}"
    arguments = release_arguments(tag, assets, prerelease=is_prerelease(match["version"]), notes=notes)
    if is_snapshot(match["version"]):
        report.lines.append(
            f"CONTRACT-CHECK {CHECK_NAME}: SNAPSHOT_DRY_RUN: {tag}: {match['version']} is a snapshot, so it is built and checksummed "
            "but no release command is printed; a snapshot tag is refused"
        )
        return None
    report.lines.append(f"GH_RELEASE_ARGS {shlex.join(arguments)}")
    if args.args_file is not None:
        args.args_file.parent.mkdir(parents=True, exist_ok=True)
        args.args_file.write_text("".join(f"{argument}\n" for argument in arguments[3:]), encoding="utf-8", newline="\n")
    report.lines.append(f"dry run for {tag}: nothing was published; the line above is the command a release would run")
    return None


def run(argv: Sequence[str] | None = None, *, out: Callable[[str], None] = print) -> int:
    parser = argparse.ArgumentParser(description="Dry-run a contract release.")
    parser.add_argument("--root", default="contracts", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--tag", default=None)
    parser.add_argument("--module", action="append", default=[], help="restrict a tag-less run to this module (repeatable)")
    parser.add_argument("--min-paths", type=int, default=bundle.DEFAULT_MIN_PATHS)
    parser.add_argument("--args-file", default=None, type=Path, help="write the arguments after 'gh release create', one per line (needs --tag)")
    args = parser.parse_args(argv)

    report = Report()

    def blocked(code: str, detail: str) -> int:
        out(f"CONTRACT-CHECK {CHECK_NAME}: {code}: {detail}")
        out(report.counts_line())
        return 2

    if args.args_file is not None and args.tag is None:
        return blocked("ARGS_FILE_NEEDS_TAG", "--args-file names the release of one tag, so it needs --tag")
    if not args.root.is_dir() or not any(args.root.iterdir()):
        return blocked("MODULE_ROOT_EMPTY", f"{args.root} is absent or empty")
    modules, _ = bundle.discover_modules(args.root)
    if args.module:
        modules = [module for module in modules if module.name in args.module]
    if not modules:
        return blocked("NO_MODULE", f"no module with a root {bundle.ROOT_DOCUMENT} under {args.root}")

    report.modules = 1 if args.tag is not None else len(modules)
    for tag, module_dir in candidate_tags(modules, args.tag):
        violation = rule_violation(tag, module_dir, derived=args.tag is None)
        if violation is not None:
            report.findings.append(finding(violation[0], tag, violation[1]))
            continue
        assert module_dir is not None  # a rule-clean tag has its module
        refusal = release_module(tag, module_dir, args, report)
        if refusal is not None:
            return blocked(*refusal)

    for line in (*report.lines, *report.findings):
        out(line)
    out(report.counts_line())
    return 1 if report.findings else 0


if __name__ == "__main__":
    sys.exit(run())
