"""Compare each contract module with its last release and refuse a breaking change without a major move (FR-016, D-P6).

For each module (a direct subdirectory of ``--root`` holding a root ``openapi.yaml``) the candidate bundle is written
by the Python resolver (:mod:`bundle`). The baseline is the same module and ``_shared/`` at the latest release tag
``contract-<module>-v<semver>``, extracted with ``git archive`` into a temporary directory and bundled by the same
resolver, or, with ``--baseline-root DIR``, the module found under ``DIR`` (the fixture pairs). ``--release-tag TAG`` names
the tag being released (the release workflow runs on the pushed tag): that tag is left out, so the previous release is the baseline.
Only tags reachable from the commit being checked (``--ref``, default ``HEAD``; ``git tag --merged``) are candidates, so a higher tag on a
side branch is never the baseline. The two bundles are
compared with ``oasdiff breaking`` (pinned in ``pins.json``). A change is *breaking* when oasdiff reports it at
level WARN or ERR: a removed path or response property, a newly required parameter, a narrowed enum, a changed type.

*Closed response schemas.* Response schemas stay closed, so a response-shape change ships as a new schema version and a new
published release. oasdiff reports an added response property at level INFO (compatible for a tolerant reader), which is not
enough here: the check raises exactly the oasdiff change ids in ``RESPONSE_ADDITION_IDS`` to level ERR through oasdiff's own
``--severity-levels`` file, written into the scratch directory. They cover a property added to a response (optional or
required, each also in its write-only form), a property added through a new ``allOf`` branch, and a new response status
code, media type or header, a write-only property that becomes readable and added ``patternProperties``, so each of those needs a
major version move like a removal does. oasdiff reports nothing for a new ``default`` or range (``4XX``) response, so the check also compares each
operation's response keys itself (``response-key-added``). ``additionalProperties: false -> true`` has no oasdiff check; the lint rule
``response-schema-closed`` guards it. A request-side optional
addition (a new optional parameter or request property) stays non-breaking.

Failure codes (exit 1), printed as ``CONTRACT-CHECK breaking_check: <CODE>: <module>: <detail>``:

* ``BREAKING_WITHOUT_MAJOR``: a breaking change while ``info.version`` did not move its major version up.
* ``BUNDLE_CHANGED_VERSION_SAME``: the bundle changed (outside the provisional elements) and ``info.version`` is
  the baseline's, or lower (``VERSION_DECREASED`` when lower).
* ``NO_BASELINE_NOT_INITIAL``: there is no release tag and ``info.version`` is not the initial version, or the
  module CHANGELOG has no entry for it.
* ``RESOLVE_FAILED``: the resolver refused the candidate module.

*First release.* With no release tag the one allowed state is ``info.version == 1.0.0`` together with a
``## 1.0.0`` heading in the module CHANGELOG, or ``1.0.0-SNAPSHOT`` together with a ``## 1.0.0-SNAPSHOT`` heading. It prints
``NO_BASELINE_INITIAL_VERSION`` loudly (and writes the job summary), exits 0, and is counted as ``no_baseline_initial`` in the ``counts:`` line; it is never silent.

*Snapshots.* An unreleased version carries ``-SNAPSHOT`` (``1.0.0-SNAPSHOT``): the work in progress of ``1.0.0``, below it and
above every earlier release. The version rules read it that way: a snapshot of a later major excuses a breaking change, a
snapshot of the released version itself is ``VERSION_DECREASED`` once the bundle changed, and a ``-SNAPSHOT`` tag is never
the baseline (``release_check`` refuses to release one).

*Provisional elements.* Properties, parameters and operations carrying ``x-provisional`` are removed from both
bundles before the comparison. A difference that exists only because of them never fails and is reported in its own
section (``PROVISIONAL_CHANGE`` lines, ``provisional_changes`` in ``counts:``).

*Preview report.* While no release tag exists, the check also prints an informational ``PREVIEW_DELTA`` report against
the latest tag ``preview/<module>/*`` (``PREVIEW_REF_NONE`` when there is none, ``preview_ref=unavailable`` when only the
preview tag listing fails). It never changes the exit status: a failing listing of the RELEASE tags is ``TAG_LIST_ERROR``
(exit 2) because it decides the baseline, a failing listing of the preview tags is a note.

Cannot do its job (exit 2): ``NO_MODULE``, ``SHALLOW_CHECKOUT``, ``TAG_LIST_ERROR``, ``BASELINE_UNBUILDABLE``,
``OASDIFF_MISSING``, ``OASDIFF_FAILED``. The last line is always
``counts: modules=N baselines=N breaking=N provisional_changes=N no_baseline_initial=N preview_ref=NAME``.

Run as a bare script (``python contracts/tools/breaking_check.py --root contracts``). Standard library, PyYAML and
the sibling ``bundle`` and ``contract_resolver``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

import bundle
import contract_resolver
from release_check import SNAPSHOT_SUFFIX, is_snapshot  # one definition of a snapshot for the baseline and the release rules

CHECK_NAME = "breaking_check"
INITIAL_VERSION = "1.0.0"
DEFAULT_REF = "HEAD"
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")
BREAKING_LEVEL = 2  # oasdiff levels: 1 info, 2 warning, 3 error
# The oasdiff 1.32.1 change ids that report a response growing: a property added to a schema, a property added through a new
# allOf branch (a oneOf or anyOf branch is already an error in oasdiff), a new status code, a new media type, a new header.
# oasdiff calls them INFO (compatible for a tolerant reader); closed response schemas make them breaking.
RESPONSE_ADDITION_IDS = (
    "response-optional-property-added",
    "response-required-property-added",
    "response-optional-write-only-property-added",
    "response-required-write-only-property-added",
    "response-body-all-of-added",
    "response-property-all-of-added",
    "response-success-status-added",
    "response-non-success-status-added",
    "response-media-type-added",
    "response-header-added",
    # a property that was write-only (never in a response) becomes readable: the response grows
    "response-optional-property-became-not-write-only",
    "response-required-property-became-not-write-only",
    # patternProperties added to a response schema
    "response-body-pattern-property-added",
    "response-property-pattern-property-added",
)
# oasdiff has no change id for ``additionalProperties: false -> true`` on a response schema, so no id is listed for it: the lint
# rule ``response-schema-closed`` guards that case (every response object schema stays closed).
# oasdiff also reports nothing for a new ``default`` or range (``4XX``/``5XX``) response, so the check compares each operation's
# response keys itself and reports a new key under this id (the same shape as an oasdiff change).
RESPONSE_KEY_ADDED_ID = "response-key-added"
STATUS_ADDED_IDS = ("response-success-status-added", "response-non-success-status-added")
CLOSED_RESPONSE_IDS = (*RESPONSE_ADDITION_IDS, RESPONSE_KEY_ADDED_ID)
SEVERITY_LEVELS_FILE = "severity-levels.txt"
CLOSED_RESPONSE_NOTE = "closed response schemas: a response-shape change is a major version move and a new release"
COMMAND_TIMEOUT_SECONDS = 300
HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
MAX_LINES_PER_KIND = 20

Runner = Callable[[Sequence[str], Path | None], tuple[int, str, str]]
Which = Callable[[str], str | None]


def subprocess_runner(command: Sequence[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Run ``command`` (an argument list, never a shell string) and return ``(status, stdout, stderr)``."""
    completed = subprocess.run(  # noqa: S603 -- argument list built here, binaries resolved with shutil.which, no shell
        list(command), capture_output=True, text=True, timeout=COMMAND_TIMEOUT_SECONDS, check=False, cwd=cwd
    )
    return completed.returncode, completed.stdout, completed.stderr


class CannotRun(Exception):
    """The check could not do its job (exit 2)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass
class Report:
    findings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)
    modules: int = 0
    baselines: int = 0
    breaking: int = 0
    provisional_changes: int = 0
    no_baseline_initial: int = 0
    preview_refs: list[str] = field(default_factory=list)

    def counts_line(self) -> str:
        preview = ",".join(self.preview_refs) if self.preview_refs else "skipped"
        return (
            f"counts: modules={self.modules} baselines={self.baselines} breaking={self.breaking} "
            f"provisional_changes={self.provisional_changes} no_baseline_initial={self.no_baseline_initial} preview_ref={preview}"
        )


def finding(code: str, module: str, detail: str) -> str:
    return f"CONTRACT-CHECK {CHECK_NAME}: {code}: {module}: {detail}"


SemverKey = tuple[int, int, int, tuple[Any, ...]]
NUMERIC_IDENTIFIER = 0  # semver 2.0 section 11: a numeric identifier sorts below an alphanumeric one
ALPHANUMERIC_IDENTIFIER = 1
RELEASE_KEY: tuple[Any, ...] = (1,)  # above every prerelease key, which all start with 0


def _prerelease_key(prerelease: str) -> tuple[Any, ...]:
    """The semver 2.0 precedence key of a prerelease: numeric identifiers numerically, the rest lexically, a shorter set first."""
    identifiers = tuple((NUMERIC_IDENTIFIER, int(item)) if item.isdigit() else (ALPHANUMERIC_IDENTIFIER, item) for item in prerelease.split("."))
    return (0, *identifiers)


def parse_semver(text: str) -> SemverKey | None:
    """``(major, minor, patch, prerelease_key)`` of a semver string, or ``None``; tuples compare by semver 2.0 precedence.

    A release sorts above every prerelease of its own version. Build metadata is ignored.
    """
    match = SEMVER.match(text)
    if match is None:
        return None
    prerelease = match.group(4)
    return int(match.group(1)), int(match.group(2)), int(match.group(3)), RELEASE_KEY if prerelease is None else _prerelease_key(prerelease)


def latest_release_tag(tags: Sequence[str], module: str, exclude: str | None = None) -> str | None:
    """The tag ``contract-<module>-v<semver>`` with the highest version, or ``None``. ``exclude`` is the tag being released."""
    prefix = f"contract-{module}-v"
    best: tuple[SemverKey, str] | None = None
    for tag in tags:
        if not tag.startswith(prefix) or tag == exclude:
            continue
        text = tag[len(prefix) :]
        version = parse_semver(text)
        if is_snapshot(text):
            continue  # a snapshot is work in progress, never a release baseline
        if version is not None and (best is None or version > best[0]):
            best = (version, tag)
    return best[1] if best else None


def strip_provisional(node: Any) -> Any:
    """A copy of ``node`` without the properties, parameters and operations that carry ``x-provisional``.

    The names of removed properties are also taken out of the ``required`` list beside them.
    """

    def provisional(value: Any) -> bool:
        return isinstance(value, dict) and bool(value.get("x-provisional"))

    if isinstance(node, list):
        return [strip_provisional(item) for item in node if not provisional(item)]
    if not isinstance(node, dict):
        return node
    result: dict[str, Any] = {}
    removed: set[str] = set()
    for key, value in node.items():
        if key == "properties" and isinstance(value, dict):
            kept = {name: item for name, item in value.items() if not provisional(item)}
            removed.update(str(name) for name in value if name not in kept)
            result[key] = strip_provisional(kept)
        elif key in HTTP_METHODS and provisional(value):
            continue
        else:
            result[key] = strip_provisional(value)
    if removed and isinstance(result.get("required"), list):
        result["required"] = [name for name in result["required"] if name not in removed]
    return result


def digest(document: Any) -> str:
    text = yaml.safe_dump(document, sort_keys=True, default_flow_style=False, allow_unicode=True, width=1000)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()  # noqa: TID251 -- file-integrity digest of a bundle, not the charter hash


def write_document(document: Any, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(document, sort_keys=False, default_flow_style=False, allow_unicode=True, width=1000), encoding="utf-8")
    return target


def entry_key(entry: dict[str, Any]) -> tuple[str, str, str, str]:
    return (str(entry.get("id")), str(entry.get("operation")), str(entry.get("path")), str(entry.get("text")))


def added_response_keys(baseline: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, Any]]:
    """Changes (oasdiff's entry shape, level ERR) for each response key an operation gained: ``default``, ``4XX`` and any status.

    Closed response schemas make any growth of an operation's response key set breaking. An operation that is new, or
    a path that is new, is left to oasdiff (a new path or method is not a response change).
    """
    entries: list[dict[str, Any]] = []
    old_paths, new_paths = baseline.get("paths"), candidate.get("paths")
    if not isinstance(old_paths, dict) or not isinstance(new_paths, dict):
        return entries
    for path, new_item in new_paths.items():
        old_item = old_paths.get(path)
        if not isinstance(old_item, dict) or not isinstance(new_item, dict):
            continue
        for method in HTTP_METHODS:
            old_operation, new_operation = old_item.get(method), new_item.get(method)
            if not isinstance(old_operation, dict) or not isinstance(new_operation, dict):
                continue
            old_keys = _response_keys(old_operation)
            for key in sorted(_response_keys(new_operation) - old_keys):
                text = f"added the response with the key `{key}`"
                entries.append({"id": RESPONSE_KEY_ADDED_ID, "text": text, "level": 3, "operation": method.upper(), "path": path, "key": key})
    return entries


def reported_by_oasdiff(own: dict[str, Any], entries: list[dict[str, Any]]) -> bool:
    """Whether oasdiff already reports the new response key of ``own`` (a new status code), so it is not counted twice."""
    status = f"`{own['key']}`"
    return any(
        entry.get("id") in STATUS_ADDED_IDS and entry.get("operation") == own["operation"] and entry.get("path") == own["path"] and status in str(entry.get("text"))
        for entry in entries
    )


def _response_keys(operation: dict[str, Any]) -> set[str]:
    responses = operation.get("responses")
    return {str(key) for key in responses} if isinstance(responses, dict) else set()


def write_severity_levels(target: Path) -> Path:
    """Write oasdiff's custom severity file raising every response-property addition to ERR (one ``<id> err`` line each)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(f"{identifier} err\n" for identifier in RESPONSE_ADDITION_IDS), encoding="utf-8", newline="\n")
    return target


def oasdiff_breaking(runner: Runner, oasdiff: str, base: Path, revision: Path, severity_levels: Path | None = None) -> list[dict[str, Any]]:
    """The changes oasdiff reports at level WARN or ERR between two bundle files (with ``severity_levels``, as that file raises them)."""
    command = [oasdiff, "breaking", str(base), str(revision), "--format", "json"]
    if severity_levels is not None:
        command += ["--severity-levels", str(severity_levels)]
    status, stdout, stderr = runner(command, None)
    if status != 0:
        raise CannotRun("OASDIFF_FAILED", f"oasdiff exited {status}: {(stderr or stdout).strip()[:300]}")
    try:
        entries = json.loads(stdout) if stdout.strip() else []
    except ValueError as error:
        raise CannotRun("OASDIFF_FAILED", f"oasdiff printed output that is not JSON: {error}") from error
    if not isinstance(entries, list):
        raise CannotRun("OASDIFF_FAILED", "oasdiff output is not a list of changes")
    return [entry for entry in entries if isinstance(entry, dict) and int(entry.get("level", 0)) >= BREAKING_LEVEL]


def oasdiff_changelog(runner: Runner, oasdiff: str, base: Path, revision: Path) -> list[dict[str, Any]]:
    status, stdout, stderr = runner([oasdiff, "changelog", str(base), str(revision), "--format", "json"], None)
    if status != 0:
        raise CannotRun("OASDIFF_FAILED", f"oasdiff exited {status}: {(stderr or stdout).strip()[:300]}")
    try:
        entries = json.loads(stdout) if stdout.strip() else []
    except ValueError as error:
        raise CannotRun("OASDIFF_FAILED", f"oasdiff printed output that is not JSON: {error}") from error
    return [entry for entry in entries if isinstance(entry, dict)] if isinstance(entries, list) else []


class GitRepo:
    """The few git operations the check needs, through one injectable runner."""

    def __init__(self, directory: Path, runner: Runner, git: str) -> None:
        self.directory = directory
        self.runner = runner
        self.git = git

    def _run(self, *arguments: str) -> tuple[int, str, str]:
        return self.runner([self.git, "-C", str(self.directory), *arguments], None)

    def require_full_history(self) -> None:
        status, stdout, stderr = self._run("rev-parse", "--is-shallow-repository")
        if status != 0:
            raise CannotRun("TAG_LIST_ERROR", f"git rev-parse --is-shallow-repository failed: {stderr.strip()[:200]}")
        if stdout.strip() == "true":
            raise CannotRun("SHALLOW_CHECKOUT", "the clone is shallow, so release tags may be hidden; fetch with full history and tags")

    def tags(self, pattern: str, *, version_sort: bool = False, merged: str | None = None) -> list[str]:
        """The tags matching ``pattern``; with ``merged``, only those reachable from that ref (``git tag --merged``)."""
        arguments = ["tag", "--list", pattern]
        if merged is not None:
            arguments += ["--merged", merged]
        if version_sort:
            arguments.append("--sort=-version:refname")
        status, stdout, stderr = self._run(*arguments)
        if status != 0:
            raise CannotRun("TAG_LIST_ERROR", f"git tag --list {pattern!r} failed: {stderr.strip()[:200]}")
        return [line.strip() for line in stdout.splitlines() if line.strip()]

    def toplevel(self) -> Path:
        status, stdout, stderr = self._run("rev-parse", "--show-toplevel")
        if status != 0:
            raise CannotRun("TAG_LIST_ERROR", f"not a git working tree: {stderr.strip()[:200]}")
        return Path(stdout.strip())

    def extract(self, ref: str, relative_paths: Sequence[str], destination: Path) -> str | None:
        """Extract ``relative_paths`` of ``ref`` into ``destination``. Returns an error text, or ``None``."""
        present: list[str] = []
        for relative in relative_paths:
            status, stdout, _ = self._run("ls-tree", "--name-only", ref, "--", relative)
            if status == 0 and stdout.strip():
                present.append(relative)
        if not present:
            return f"none of {', '.join(relative_paths)} exists at {ref}"
        archive = destination / "baseline.tar"
        destination.mkdir(parents=True, exist_ok=True)
        status, _, stderr = self._run("archive", "--format=tar", f"--output={archive}", ref, "--", *present)
        if status != 0:
            return f"git archive {ref} failed: {stderr.strip()[:200]}"
        with tarfile.open(archive) as handle:
            handle.extractall(destination, filter="data")
        archive.unlink()
        return None


def has_changelog_entry(module_dir: Path, version: str) -> bool:
    changelog = module_dir / "CHANGELOG.md"
    if not changelog.is_file():
        return False
    pattern = re.compile(rf"^#{{1,6}}\s+\[?{re.escape(version)}\]?(\s|$)", re.MULTILINE)
    return pattern.search(changelog.read_text(encoding="utf-8")) is not None


def build_bundle(module_dir: Path, out_dir: Path) -> dict[str, Any]:
    """Write and read back the resolver bundle of ``module_dir``. Raises ``contract_resolver.ResolveError``."""
    document = yaml.safe_load(bundle.write_bundle(module_dir, out_dir).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise contract_resolver.ResolveError("NOT_A_MAPPING", f"the bundle of {module_dir} is not a mapping")
    return document


def version_of(document: dict[str, Any]) -> str:
    info = document.get("info")
    return str(info.get("version", "")) if isinstance(info, dict) else ""


class Checker:
    def __init__(self, args: argparse.Namespace, runner: Runner, which: Which, work: Path) -> None:
        self.args = args
        self.runner = runner
        self.work = work
        self.report = Report()
        self.git_binary = which("git")
        oasdiff = which("oasdiff")
        if oasdiff is None:
            raise CannotRun("OASDIFF_MISSING", "no oasdiff on PATH (run install_tools.py first)")
        self.oasdiff = oasdiff
        self.severity_levels = write_severity_levels(work / SEVERITY_LEVELS_FILE)
        self.repo: GitRepo | None = None
        self.relative_root: str = ""

    def prepare_git(self) -> None:
        if self.git_binary is None:
            raise CannotRun("TAG_LIST_ERROR", "no git on PATH")
        self.repo = GitRepo(self.args.root, self.runner, self.git_binary)
        self.repo.require_full_history()
        top = self.repo.toplevel().resolve()
        self.repo.directory = top  # tree-relative paths below are relative to the working-tree top
        try:
            self.relative_root = self.args.root.resolve().relative_to(top).as_posix()
        except ValueError as error:
            raise CannotRun("TAG_LIST_ERROR", f"{self.args.root} is outside its git working tree") from error

    def baseline_module(self, module: str, tag: str) -> Path:
        assert self.repo is not None
        destination = self.work / "baseline" / tag.replace("/", "_")
        base = self.relative_root or "."
        problem = self.repo.extract(tag, [f"{base}/{module}", f"{base}/_shared"], destination)
        if problem is not None:
            raise CannotRun("BASELINE_UNBUILDABLE", f"{module}: {problem}")
        return destination / base / module

    def baseline_bundle(self, module: str, directory: Path, label: str) -> dict[str, Any]:
        try:
            return build_bundle(directory, self.work / "baseline-out" / label)
        except contract_resolver.ResolveError as error:
            raise CannotRun("BASELINE_UNBUILDABLE", f"{module}: {error}") from error

    def check_module(self, module_dir: Path) -> None:
        module = module_dir.name
        report = self.report
        try:
            candidate = build_bundle(module_dir, self.work / "candidate-out")
        except contract_resolver.ResolveError as error:
            report.findings.append(finding("RESOLVE_FAILED", module, str(error)))
            return
        version = version_of(candidate)
        baseline_dir, label = self.find_baseline(module)
        if baseline_dir is None:
            self.first_release(module, module_dir, version)
            self.preview(module, candidate)
            return
        baseline = self.baseline_bundle(module, baseline_dir, label)
        report.baselines += 1
        self.compare(module, baseline, candidate, version_of(baseline), version, label)

    def find_baseline(self, module: str) -> tuple[Path | None, str]:
        if self.args.baseline_root is not None:
            directory = self.args.baseline_root / module
            return (directory, "baseline-root") if (directory / bundle.ROOT_DOCUMENT).is_file() else (None, "")
        assert self.repo is not None
        # only releases reachable from the commit being checked: a higher tag on a side branch is not this line's baseline
        tag = latest_release_tag(self.repo.tags(f"contract-{module}-v*", merged=self.args.ref), module, self.args.release_tag)
        if tag is None:
            return None, ""
        return self.baseline_module(module, tag), tag

    def first_release(self, module: str, module_dir: Path, version: str) -> None:
        report = self.report
        if version in (INITIAL_VERSION, INITIAL_VERSION + SNAPSHOT_SUFFIX) and has_changelog_entry(module_dir, version):
            report.no_baseline_initial += 1
            line = (
                f"CONTRACT-CHECK {CHECK_NAME}: NO_BASELINE_INITIAL_VERSION: {module}: no release tag exists and "
                f"info.version is the initial version {version} with a CHANGELOG entry; "
                "nothing to compare against, this is the first release"
            )
            report.notes.append(line)
            report.summary.append(
                f"### {module}: NO_BASELINE_INITIAL_VERSION\n\n"
                f"No `contract-{module}-v*` tag exists. Version `{version}` is the initial version (or its snapshot) and "
                "the CHANGELOG has its entry: first release, nothing compared.\n"
            )
        else:
            report.findings.append(
                finding(
                    "NO_BASELINE_NOT_INITIAL",
                    module,
                    f"no release tag exists, but info.version is {version!r} (initial version {INITIAL_VERSION} "
                    f"or {INITIAL_VERSION}{SNAPSHOT_SUFFIX}) or the CHANGELOG has no entry for it",
                )
            )

    def breaking_between(self, baseline: dict[str, Any], candidate: dict[str, Any], prefix: Path) -> list[dict[str, Any]]:
        """oasdiff's WARN/ERR changes plus the response keys oasdiff does not see (a new ``default`` or range response)."""
        base_file = write_document(baseline, prefix.parent / f"{prefix.name}-base.yaml")
        cand_file = write_document(candidate, prefix.parent / f"{prefix.name}-cand.yaml")
        entries = oasdiff_breaking(self.runner, self.oasdiff, base_file, cand_file, self.severity_levels)
        return entries + [own for own in added_response_keys(baseline, candidate) if not reported_by_oasdiff(own, entries)]

    def compare(self, module: str, baseline: dict[str, Any], candidate: dict[str, Any], base_version: str, version: str, label: str) -> None:
        report = self.report
        base_stripped, cand_stripped = strip_provisional(baseline), strip_provisional(candidate)
        full_changed = digest(baseline) != digest(candidate)
        stable_changed = digest(base_stripped) != digest(cand_stripped)
        breaking_full = self.breaking_between(baseline, candidate, self.work / "cmp" / module / "full") if full_changed else []
        breaking_stable = self.breaking_between(base_stripped, cand_stripped, self.work / "cmp" / module / "stable") if stable_changed else []
        stable_keys = {entry_key(entry) for entry in breaking_stable}
        provisional = [entry for entry in breaking_full if entry_key(entry) not in stable_keys]
        provisional_lines = [f"{entry.get('operation')} {entry.get('path')}: {entry.get('text')}" for entry in provisional]
        if full_changed and not stable_changed and not provisional_lines:
            provisional_lines = ["the bundle differs only inside provisional elements (no breaking change)"]
        report.provisional_changes += len(provisional_lines)
        for line in provisional_lines[:MAX_LINES_PER_KIND]:
            report.notes.append(f"CONTRACT-CHECK {CHECK_NAME}: PROVISIONAL_CHANGE: {module}: {line}")
        if provisional_lines:
            report.summary.append(f"### {module}: provisional changes (never failing)\n\n" + "\n".join(f"- {line}" for line in provisional_lines) + "\n")

        base_parts, parts = parse_semver(base_version), parse_semver(version)
        if base_parts is None or parts is None:
            detail = f"info.version {version!r} or the baseline's {base_version!r} is not a semantic version"
            report.findings.append(finding("NO_BASELINE_NOT_INITIAL", module, detail))
            return
        if breaking_stable:
            report.breaking += len(breaking_stable)
            if parts[0] <= base_parts[0]:
                for entry in breaking_stable[:MAX_LINES_PER_KIND]:
                    where = f"{entry.get('operation')} {entry.get('path')}: {entry.get('text')}"
                    if entry.get("id") in CLOSED_RESPONSE_IDS:
                        where += f" ({CLOSED_RESPONSE_NOTE})"
                    report.findings.append(finding("BREAKING_WITHOUT_MAJOR", module, f"{where} (baseline {label} {base_version}, candidate {version})"))
            return
        if stable_changed and parts <= base_parts:
            code = "BUNDLE_CHANGED_VERSION_SAME" if parts == base_parts else "VERSION_DECREASED"
            detail = f"the bundle changed but info.version is {version} (baseline {label} {base_version}); move the version and add a CHANGELOG entry"
            report.findings.append(finding(code, module, detail))

    def preview(self, module: str, candidate: dict[str, Any]) -> None:
        report = self.report
        if self.repo is None:
            return  # explicit baseline root: no tags to look at
        try:
            tags = self.repo.tags(f"preview/{module}/*", version_sort=True)
        except CannotRun as error:
            report.preview_refs.append("unavailable")
            report.notes.append(f"PREVIEW_DELTA {module}: preview_ref=unavailable ({error.code}: {error.detail}); informational, never fails")
            return
        if not tags:
            report.preview_refs.append("none")
            report.notes.append(f"PREVIEW_REF_NONE {module}: no tag under preview/{module}/ exists")
            return
        tag = tags[0]
        report.preview_refs.append(tag)
        try:
            base = self.baseline_bundle(module, self.baseline_module(module, tag), f"preview-{tag.replace('/', '_')}")
            base_file = write_document(base, self.work / "preview" / module / "base.yaml")
            cand_file = write_document(candidate, self.work / "preview" / module / "cand.yaml")
            changes = oasdiff_changelog(self.runner, self.oasdiff, base_file, cand_file)
        except CannotRun as error:
            report.notes.append(f"PREVIEW_DELTA {module}: preview_ref={tag}: unavailable ({error.code}: {error.detail}); informational, never fails")
            return
        report.notes.append(f"PREVIEW_DELTA {module}: preview_ref={tag}: {len(changes)} change(s) against the preview tag (informational, never fails)")
        for entry in changes[:MAX_LINES_PER_KIND]:
            where = " ".join(part for part in (str(entry.get("operation", "")), str(entry.get("path", ""))) if part)
            report.notes.append(f"PREVIEW_DELTA {module}: level={entry.get('level')} {where}: {entry.get('text')}")


def run(argv: Sequence[str] | None = None, *, runner: Runner = subprocess_runner, which: Which = shutil.which, out: Callable[[str], None] = print) -> int:
    parser = argparse.ArgumentParser(description="Refuse a breaking contract change without a major version move.")
    parser.add_argument("--root", default="contracts", type=Path)
    parser.add_argument("--module", action="append", default=[], help="restrict to this module (repeatable)")
    parser.add_argument("--baseline-root", type=Path, default=None, help="compare against the modules under this directory instead of the latest release tag")
    parser.add_argument("--release-tag", default=None, help="the tag being released (a tag push); it is never its own baseline, the previous release is")
    parser.add_argument("--ref", default=DEFAULT_REF, help="the commit being checked; only release tags reachable from it can be the baseline (default: HEAD)")
    parser.add_argument("--summary", type=Path, default=None, help="append the job summary here (default: $GITHUB_STEP_SUMMARY)")
    args = parser.parse_args(argv)

    def blocked(error: CannotRun, report: Report | None = None) -> int:
        out(f"CONTRACT-CHECK {CHECK_NAME}: {error.code}: {error.detail}")
        out((report or Report()).counts_line())
        return 2

    modules, _ = bundle.discover_modules(args.root)
    if args.module:
        modules = [module for module in modules if module.name in args.module]
    if not modules:
        return blocked(CannotRun("NO_MODULE", f"no module with a root {bundle.ROOT_DOCUMENT} under {args.root}"))

    with tempfile.TemporaryDirectory(prefix="breaking-check-") as scratch:
        checker: Checker | None = None
        try:
            checker = Checker(args, runner, which, Path(scratch))
            if args.baseline_root is None:
                checker.prepare_git()
            checker.report.modules = len(modules)
            for module_dir in modules:
                checker.check_module(module_dir)
        except CannotRun as error:
            return blocked(error, checker.report if checker else None)
        report = checker.report

    for line in (*report.notes, *report.findings):
        out(line)
    summary_target = args.summary or (Path(os.environ["GITHUB_STEP_SUMMARY"]) if os.environ.get("GITHUB_STEP_SUMMARY") else None)
    if summary_target is not None and report.summary:
        with summary_target.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(report.summary) + "\n")
    out(report.counts_line())
    return 1 if report.findings else 0


if __name__ == "__main__":
    sys.exit(run())
