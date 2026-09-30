#!/usr/bin/env python3
"""Spelling check for the docs tree (issue #5426).

Runs codespell in up to three passes and reports every finding in one deterministic list:

``typo``
    Real typos in ``docs/``, ``packs/built-in/`` and ``README.md`` (Markdown only).
``us``
    British-to-American spellings in the reader-facing prose of ``docs/guides`` and
    ``docs/context``. Code spans, fenced blocks and heading anchors are exempt.
``unreleased``
    The same American-spelling policy applied to the changelog's ``## [Unreleased]`` section only.

Run it from the repository root::

    python -m scripts.docs.check_spelling [--pass {typo,us,unreleased,all}]
                                          [--repo-root PATH] [--changelog PATH]

Exit codes: ``0`` no findings, ``1`` one or more findings, ``2`` usage error, codespell missing,
``pyproject.toml`` without a ``[tool.codespell]`` table, a ``typo`` or ``us`` pass that scanned
zero files, or an ``unreleased`` scratch file that the configured skip globs would drop. See ``contracts/check-cli.md`` in mission
``docs-lint-codespell-changelog-guard-01M3RFGJ``.

codespell is GPL-2.0-only, so it is only ever run as a subprocess
(``python -m codespell_lib --toml <repo>/pyproject.toml ...``). This module never imports it.
The dictionary behavior shared by every pass (the ``skip`` and ``ignore-words-list`` keys) lives in
``[tool.codespell]`` in ``pyproject.toml``; the scope roots and the pass-specific flags live here so
a flag can never leak from one pass into another.

Standard library only, apart from the shared changelog locator in
:mod:`scripts.release.validate_release`.
"""

from __future__ import annotations

import argparse
import fnmatch
import importlib.util
import re
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from scripts.release import validate_release

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
DEFAULT_CHANGELOG: Final[Path] = Path("docs") / "changelog" / "CHANGELOG.md"

# codespell exit codes verified on 2.4.3: 0 means clean, 65 means misspellings were found.
_EXIT_CLEAN: Final[int] = 0
_EXIT_MISSPELLINGS: Final[int] = 65
# Windows caps the command line, so codespell never sees more than this many paths at once.
_BATCH_SIZE: Final[int] = 150

_RULE_TYPO: Final[str] = "typo"
_RULE_US: Final[str] = "us-spelling"
_TYPO: Final[str] = "typo"
_US: Final[str] = "us"
_UNRELEASED: Final[str] = "unreleased"
_SCRATCH_NAME: Final[str] = "unreleased.md"
PASS_NAMES: Final[tuple[str, ...]] = (_TYPO, _US, _UNRELEASED)
_RULE_FOR_PASS: Final[dict[str, str]] = {
    _TYPO: _RULE_TYPO,
    _US: _RULE_US,
    _UNRELEASED: _RULE_US,
}

# Scope roots (Markdown only, recursive) and single files for each pass. The skip list itself is
# owned by [tool.codespell] in pyproject.toml, not re-implemented here.
TYPO_ROOTS: Final[tuple[str, ...]] = ("docs", "packs/built-in")
TYPO_FILES: Final[tuple[str, ...]] = ("README.md",)

US_ROOTS: Final[tuple[str, ...]] = ("docs/guides", "docs/context")

# The whole US-spelling policy, in one place. `--builtin en-GB_to_en-US` replaces codespell's default
# dictionaries on purpose: the typo pass owns typos. `dialogue` is an accepted British form of the
# word. Code spans, fenced blocks and single-word anchor ids are exempt.
#
# codespell keeps only the LAST `--ignore-regex`, so the two exemptions are ONE combined pattern.
# Known blind spot (verified on 2.4.3): codespell's word regex includes "-", so a hyphenated
# British token such as `organisation-tier` or `behaviour-driven` is never flagged, anchor or not.
# The anchor alternative therefore matters only for single-word ids like `<a id="behaviour"></a>`.
US_FLAGS: Final[tuple[str, ...]] = (
    "--builtin",
    "en-GB_to_en-US",
    "-L",
    "dialogue",
    "--ignore-regex",
    r'(`[^`\n]*`|<a id="[^"]*"></a>)',
    "--ignore-multiline-regex",
    r"```.*?```",
)

_FINDING_RE: Final[re.Pattern[str]] = re.compile(r"^(?P<path>.+?):(?P<line>\d+): (?P<word>.+?) ==> (?P<fix>.*)$")


class SpellcheckError(Exception):
    """A problem with the tool or its environment, as opposed to a finding in the docs."""


@dataclass(frozen=True)
class Finding:
    """One misspelling. Field names match the changelog guard's ``Finding``."""

    severity: Literal["error", "warning"]
    rule: str
    path: str
    line: int
    where: str
    fix: str


@dataclass(frozen=True)
class PassResult:
    """The findings of one pass plus how much it scanned (files, or lines for ``unreleased``).

    The scanned count is what lets a caller tell "clean" from "looked at nothing".
    """

    name: str
    findings: tuple[Finding, ...]
    scanned: int


def _sort_key(finding: Finding) -> tuple[str, int, str, str]:
    return (finding.path, finding.line, finding.rule, finding.where)


def format_finding(finding: Finding) -> str:
    """Render ``path:line: [rule] word — fix: <suggestion>``."""
    return f"{finding.path}:{finding.line}: [{finding.rule}] {finding.where} — fix: {finding.fix}"


def _require_codespell() -> None:
    """Fail with an actionable message when codespell is not installed.

    ``find_spec`` locates the package without importing it, so the GPL code stays out of this
    module's import graph.
    """
    if importlib.util.find_spec("codespell_lib") is None:
        raise SpellcheckError("codespell is not installed; run `uv sync --frozen` to install the pinned dev group")


def _load_config(repo_root: Path) -> dict[str, object]:
    """Return the ``[tool.codespell]`` table of ``<repo_root>/pyproject.toml``."""
    pyproject = repo_root / "pyproject.toml"
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise SpellcheckError(f"cannot read {pyproject}: {exc}") from exc
    table = data.get("tool", {}).get("codespell")
    if not isinstance(table, dict):
        raise SpellcheckError(f"{pyproject} has no [tool.codespell] table")
    return table


def _codespell_cmd(repo_root: Path, extra_args: Sequence[str], files: Sequence[str]) -> list[str]:
    """Build the codespell command line.

    Refuses an empty file list: with no path arguments codespell scans ``.``, the whole tree,
    which would silently widen a pass far beyond its scope.
    """
    if not files:
        raise SpellcheckError("refusing to run codespell with zero file arguments (it would scan the whole tree)")
    return [
        sys.executable,
        "-m",
        "codespell_lib",
        "--toml",
        str(repo_root / "pyproject.toml"),
        *extra_args,
        *files,
    ]


def _run_codespell(cmd: Sequence[str], cwd: Path) -> str:
    """Run codespell in *cwd* and return its stdout.

    *cwd* must be the repository root whose config is passed through ``--toml``: codespell also
    reads ``./pyproject.toml`` implicitly. Exit code 0 means clean and 65 means findings; anything
    else is a tool failure.
    """
    proc = subprocess.run(
        list(cmd),
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode not in (_EXIT_CLEAN, _EXIT_MISSPELLINGS):
        detail = (proc.stderr or proc.stdout or "").strip()
        raise SpellcheckError(f"codespell failed with exit code {proc.returncode}: {detail}")
    stdout = proc.stdout or ""
    if proc.returncode == _EXIT_MISSPELLINGS and not any(_FINDING_RE.match(line) for line in stdout.splitlines()):
        raise SpellcheckError("codespell reported misspellings but its output could not be parsed")
    return stdout


def _parse_output(stdout: str, rule: str, path_map: dict[str, str]) -> list[Finding]:
    """Turn codespell's ``path:line: word ==> fix`` lines into findings.

    *path_map* translates the path form codespell echoed into the canonical repo-relative path.
    """
    findings: list[Finding] = []
    for raw in stdout.splitlines():
        match = _FINDING_RE.match(raw)
        if match is None:
            continue
        path = match["path"]
        findings.append(
            Finding(
                severity="error",
                rule=rule,
                path=path_map.get(path, path),
                line=int(match["line"]),
                where=match["word"],
                fix=match["fix"].strip(),
            )
        )
    return findings


def _skip_patterns(config: dict[str, object]) -> list[str]:
    """Return the comma-separated globs of ``[tool.codespell] skip``."""
    raw = config.get("skip", "")
    if not isinstance(raw, str):
        return []
    return [pattern.strip() for pattern in raw.split(",") if pattern.strip()]


def _is_skipped(path: str, patterns: Sequence[str]) -> bool:
    """Mirror codespell's own ``skip`` matching, used only to count what a pass really scanned."""
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _markdown_files(repo_root: Path, roots: Sequence[str], files: Sequence[str] = ()) -> list[str]:
    """List repo-relative ``*.md`` paths under *roots* plus the named *files*, sorted.

    Symlinks are dropped so an alias such as a root ``CHANGELOG.md`` can never double-report the
    canonical file it points at.
    """
    found: set[Path] = set()
    for root in roots:
        base = repo_root / root
        if base.is_dir():
            found.update(base.rglob("*.md"))
    found.update(repo_root / name for name in files)
    return sorted(path.relative_to(repo_root).as_posix() for path in found if not path.is_symlink() and path.is_file())


def _scan(
    repo_root: Path,
    files: Sequence[str],
    extra_args: Sequence[str],
    name: str,
    path_map: dict[str, str] | None = None,
    skip: Sequence[str] = (),
) -> PassResult:
    """Run codespell over *files* in batches and collect one pass's result.

    An empty *files* returns an empty result without invoking codespell at all. Every file is
    handed to codespell, whose own ``skip`` list is the authority; *skip* only shapes the scanned
    count, so files that codespell drops are not counted as looked at.
    """
    rule = _RULE_FOR_PASS[name]
    findings: list[Finding] = []
    for start in range(0, len(files), _BATCH_SIZE):
        batch = files[start : start + _BATCH_SIZE]
        stdout = _run_codespell(_codespell_cmd(repo_root, extra_args, batch), repo_root)
        findings.extend(_parse_output(stdout, rule, path_map or {}))
    findings.sort(key=_sort_key)
    scanned = sum(1 for path in files if not _is_skipped(path, skip))
    return PassResult(name=name, findings=tuple(findings), scanned=scanned)


@dataclass(frozen=True)
class _Scope:
    """What every pass runner needs: the root, the changelog and the config's skip globs."""

    repo_root: Path
    changelog: Path
    skip: tuple[str, ...]


def _run_typo(scope: _Scope) -> PassResult:
    """Typos in every Markdown file of the typo roots. No ignore-regex: code spans are checked."""
    files = _markdown_files(scope.repo_root, TYPO_ROOTS, TYPO_FILES)
    return _scan(scope.repo_root, files, (), _TYPO, skip=scope.skip)


def _run_us(scope: _Scope) -> PassResult:
    """American spelling in the reader-facing prose of the guides and the glossary context."""
    files = _markdown_files(scope.repo_root, US_ROOTS)
    return _scan(scope.repo_root, files, US_FLAGS, _US, skip=scope.skip)


def _display_path(path: Path, repo_root: Path) -> str:
    """Repo-relative forward-slash form of *path*, or its own posix form when it lies outside."""
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _run_unreleased(scope: _Scope) -> PassResult:
    """American spelling in the changelog's ``## [Unreleased]`` section only.

    The section is located by the shared, fence-aware locator, written to a scratch file, and
    scanned with the US flags. codespell reports lines relative to that file, so each is mapped back
    to its real changelog line: the section body starts on the line after the heading. A scratch
    file that the configured skip globs would drop raises :class:`SpellcheckError`.
    """
    try:
        text = scope.changelog.read_text(encoding="utf-8")
    except OSError as exc:
        raise SpellcheckError(f"cannot read changelog {scope.changelog}: {exc}") from exc
    section = validate_release.unreleased_section(text)
    if section is None:
        return PassResult(name=_UNRELEASED, findings=(), scanned=0)
    with tempfile.TemporaryDirectory(prefix="check-spelling-") as scratch:
        scratch_file = Path(scratch) / _SCRATCH_NAME
        # Never claim a scan of a file codespell would drop: refuse when a skip glob matches it.
        if _is_skipped(_SCRATCH_NAME, scope.skip) or _is_skipped(scratch_file.as_posix(), scope.skip):
            raise SpellcheckError(f"the [tool.codespell] skip globs would skip the scratch file {_SCRATCH_NAME}, so the Unreleased section would go unscanned")
        scratch_file.write_text("\n".join(section.lines) + "\n", encoding="utf-8")
        stdout = _run_codespell(_codespell_cmd(scope.repo_root, US_FLAGS, [str(scratch_file)]), scope.repo_root)
    canonical = _display_path(scope.changelog, scope.repo_root)
    findings = [Finding(f.severity, f.rule, canonical, section.start_line + f.line, f.where, f.fix) for f in _parse_output(stdout, _RULE_US, {})]
    findings.sort(key=_sort_key)
    return PassResult(name=_UNRELEASED, findings=tuple(findings), scanned=len(section.lines))


_PASS_RUNNERS: Final[dict[str, Callable[[_Scope], PassResult]]] = {
    _TYPO: _run_typo,
    _US: _run_us,
    _UNRELEASED: _run_unreleased,
}


def run_pass(name: str, repo_root: Path, changelog: Path) -> PassResult:
    """Run one named pass against *repo_root*; *changelog* feeds the ``unreleased`` pass."""
    runner = _PASS_RUNNERS.get(name)
    if runner is None:
        raise SpellcheckError(f"pass {name!r} is not available")
    scope = _Scope(repo_root, changelog, tuple(_skip_patterns(_load_config(repo_root))))
    return runner(scope)


def _require_scanned(results: Sequence[PassResult]) -> None:
    """Refuse a green result from a file-based pass that looked at nothing.

    The ``unreleased`` pass legitimately scans nothing when the changelog has no Unreleased section.
    """
    for result in results:
        if result.name in (_TYPO, _US) and result.scanned == 0:
            raise SpellcheckError(f"the {result.name} pass scanned 0 file(s); a check that looks at nothing cannot pass")


def _summary(results: Sequence[PassResult]) -> str:
    findings = [finding for result in results for finding in result.findings]
    files = {finding.path for finding in findings}
    scanned = ", ".join(f"{result.name}={result.scanned} {'line(s)' if result.name == _UNRELEASED else 'file(s)'}" for result in results)
    return f"{len(findings)} finding(s) across {len(files)} file(s); scanned: {scanned}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.docs.check_spelling",
        description="Spelling check for the docs tree (typos, US spelling, Unreleased changelog).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="root that the scope roots and pyproject.toml resolve against (default: this repository)",
    )
    parser.add_argument(
        "--changelog",
        type=Path,
        default=None,
        help=f"changelog whose Unreleased section gets the US pass (default: {DEFAULT_CHANGELOG.as_posix()})",
    )
    parser.add_argument(
        "--pass",
        dest="selected",
        choices=(*PASS_NAMES, "all"),
        default="all",
        help="run one pass or all three (default: all)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns the process exit code (see the module docstring)."""
    args = _build_parser().parse_args(argv)
    repo_root: Path = args.repo_root.resolve()
    changelog: Path = args.changelog if args.changelog is not None else DEFAULT_CHANGELOG
    if not changelog.is_absolute():
        changelog = repo_root / changelog
    names = PASS_NAMES if args.selected == "all" else (args.selected,)
    try:
        _require_codespell()
        _load_config(repo_root)
        results = [run_pass(name, repo_root, changelog) for name in names]
        _require_scanned(results)
    except SpellcheckError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    findings = sorted((finding for result in results for finding in result.findings), key=_sort_key)
    for finding in findings:
        print(format_finding(finding))
    print(_summary(results))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
