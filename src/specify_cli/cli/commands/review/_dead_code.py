"""Gate 2: portable dead-code scan."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from rich.console import Console

from kernel.git import GitCommandError, NameStatusEntry, run_git
from kernel.git import changed_entries as git_changed_entries

from specify_cli.consolidation.baseline import (
    ANCHOR_EVIDENCE_CORPUS_PARENT_ATTESTED,
    ANCHOR_EVIDENCE_MERGE_COMMIT_PARENT_ATTESTED,
)

from ._diagnostics import MissionReviewDiagnostic

_IDENTIFIER_CHARCLASS = r"\w"
_UNDETERMINABLE_REMEDIATION = "Verify the baseline commit and Git repository, then rerun `spec-kitty review`."
# Tech-agnostic on purpose (#2330 / #5283): never advise a non-Python mission to
# create Python files or adopt Python tooling; point at the local charter instead.
_NOT_APPLICABLE_REMEDIATION = (
    "The dead-code scan only analyzes Python sources. For other languages, add "
    "tech-specific review guidance and your own analyzer or test command to your local charter "
    "(see 'Extend your charter for an unsupported language')."
)
_NO_EXTENSION_LABEL = "(no extension)"
_PYTHON_SUFFIX = ".py"
_TEST_DIRECTORY_NAMES = frozenset({"test", "tests"})
_EXCLUDED_CORPUS_PARTS = frozenset(
    {
        ".git",
        ".nox",
        ".pytest_cache",
        ".tox",
        ".venv",
        ".worktrees",
        "node_modules",
        "venv",
    }
)


DiscoveryOutcome = Literal["scan", "undeterminable", "not_applicable"]

#: What ``scan_dead_code`` did: ran to completion, found nothing it supports
#: (``not_applicable``), or could not run at all (missing baseline, legacy
#: mission, incomplete evidence, undeterminable discovery).
DeadCodeOutcome = Literal["scanned", "not_applicable", "unscanned"]


@dataclass(frozen=True)
class _Discovery:
    """Result of baseline-to-HEAD symbol discovery.

    ``outcome`` discriminates a normal scan from an undeterminable discovery
    (``error`` is set) and from a change set the Python-only scan does not
    apply to. ``unsupported_extensions`` / ``excluded_test_paths`` describe the
    changed files the scan cannot analyze (sorted, de-duplicated; ``.py`` is
    never listed).
    """

    changed_paths: tuple[str, ...]
    symbols: tuple[tuple[str, str], ...]
    error: str | None = None
    outcome: DiscoveryOutcome = "scan"
    unsupported_extensions: tuple[str, ...] = ()
    excluded_test_paths: int = 0


def _is_python_path(path: str) -> bool:
    """Return True for a ``.py`` path, matching the suffix case-insensitively."""
    return PurePosixPath(path).suffix.lower() == _PYTHON_SUFFIX


def _is_test_only_path(path: str) -> bool:
    """Return True when *path* is a test path by segment or file name, never by substring.

    A directory segment named ``test``/``tests``, or a file named ``test_*.py``,
    ``*_test.py`` or ``conftest.py`` (case-insensitive), marks a test path;
    ``latest.py``, ``contest.py`` and ``attestation.py`` do not.
    """
    pure = PurePosixPath(path.casefold())
    if any(part in _TEST_DIRECTORY_NAMES for part in pure.parts[:-1]):
        return True
    if pure.name == "conftest.py":
        return True
    return pure.suffix == _PYTHON_SUFFIX and (pure.stem.startswith("test_") or pure.stem.endswith("_test"))


def _summarize_unsupported(
    changed_paths: tuple[str, ...],
    supported_paths: tuple[str, ...],
) -> tuple[tuple[str, ...], int]:
    """Summarize changed files the scan cannot analyze.

    Returns ``(sorted unique extensions, count of test-only Python paths)``.
    Python files excluded by the test-path filter are counted, never listed as
    an unsupported extension.
    """
    supported = frozenset(supported_paths)
    extensions: set[str] = set()
    excluded_test_paths = 0
    for path in changed_paths:
        if path in supported:
            continue
        if _is_python_path(path):
            excluded_test_paths += 1
        else:
            extensions.add(PurePosixPath(path).suffix.lower() or _NO_EXTENSION_LABEL)
    return tuple(sorted(extensions)), excluded_test_paths


_HUNK_MARKER = "@@"
_ADDED_SYMBOL_PATTERN = re.compile(rf"^\+\s*(def|class)\s+([A-Za-z]{_IDENTIFIER_CHARCLASS}*)\s*[\(:]")


def _added_symbols_in_diff(diff_text: str, path: str) -> tuple[tuple[str, str], ...]:
    """Extract added public Python symbols from the ``--unified=0`` diff of exactly one path.

    Every ``+`` line after the first hunk marker belongs to *path*, the path the
    diff was asked for. No path is ever read back out of diff text (git quotes
    or tab-suffixes some ``+++`` header spellings), so attribution cannot be lost.
    """
    symbols: list[tuple[str, str]] = []
    in_hunk = False
    for line in diff_text.splitlines():
        if line.startswith(_HUNK_MARKER):
            in_hunk = True
        elif in_hunk and line.startswith("+"):
            match = _ADDED_SYMBOL_PATTERN.match(line)
            if match and not match.group(2).startswith("_"):
                symbols.append((match.group(2), path))
    return tuple(symbols)


def _added_symbols_for_entry(
    repo_root: Path,
    baseline_merge_commit: str,
    entry: NameStatusEntry,
) -> tuple[tuple[str, str], ...]:
    """Diff one changed Python path (and its rename source) and attribute its added symbols to it."""
    pathspecs = [str(entry.path)]
    if entry.orig_path is not None:
        pathspecs.insert(0, str(entry.orig_path))
    result = run_git(
        repo_root,
        "--literal-pathspecs",
        "diff",
        "--unified=0",
        "-M",
        f"{baseline_merge_commit}..HEAD",
        "--",
        *pathspecs,
    )
    return _added_symbols_in_diff(result.stdout.decode("utf-8", errors="replace"), str(entry.path))


def _undeterminable(changed_paths: tuple[str, ...], exc: GitCommandError) -> _Discovery:
    unavailable = exc.not_run
    return _Discovery(changed_paths, (), "git executable is unavailable" if unavailable else "git diff failed", "undeterminable")


def _discover_changed_symbols(
    repo_root: Path,
    baseline_merge_commit: str,
) -> _Discovery:
    """Discover changed paths and added Python symbols without a source-root assumption."""
    try:
        listed = git_changed_entries(repo_root, f"{baseline_merge_commit}..HEAD", renames=True)
    except GitCommandError as exc:
        # Discovery is a scan gate: a failed listing is reported as undeterminable, never as "no changes".
        return _undeterminable((), exc)

    changed_paths = tuple(str(entry.path) for entry in listed)
    if not changed_paths:
        return _Discovery((), (), "git diff reported no changed files", "undeterminable")
    changed_python_paths = tuple(path for path in changed_paths if _is_python_path(path))
    supported_paths = tuple(path for path in changed_python_paths if path.startswith("src/") or not _is_test_only_path(path))
    unsupported_extensions, excluded_test_paths = _summarize_unsupported(changed_paths, supported_paths)
    if not supported_paths:
        return _Discovery(
            changed_paths,
            (),
            outcome="not_applicable",
            unsupported_extensions=unsupported_extensions,
            excluded_test_paths=excluded_test_paths,
        )

    supported = frozenset(supported_paths)
    symbols: list[tuple[str, str]] = []
    try:
        for entry in listed:
            if str(entry.path) in supported:
                symbols.extend(_added_symbols_for_entry(repo_root, baseline_merge_commit, entry))
    except GitCommandError as exc:
        # Attribution needs every per-path diff; a failed one is undeterminable, never "no symbols".
        return _undeterminable(changed_paths, exc)
    return _Discovery(
        supported_paths,
        tuple(symbols),
        unsupported_extensions=unsupported_extensions,
        excluded_test_paths=excluded_test_paths,
    )


def _load_python_corpus(
    repo_root: Path,
    changed_paths: tuple[str, ...],
) -> tuple[tuple[tuple[str, str], ...], str | None]:
    """Load the complete Python corpus, including untracked files, deterministically."""
    changed_python_paths = tuple(path for path in changed_paths if _is_python_path(path))
    search_root = repo_root / "src" if changed_python_paths and all(path.startswith("src/") for path in changed_python_paths) else repo_root
    try:
        paths = sorted(
            path
            for path in search_root.rglob("*.py")
            if path.is_file() and not path.is_symlink() and not (_EXCLUDED_CORPUS_PARTS & set(path.relative_to(repo_root).parts))
        )
    except OSError as exc:
        return (), f"could not enumerate Python source: {exc}"

    corpus: list[tuple[str, str]] = []
    for path in paths:
        relative_path = path.relative_to(repo_root).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return (), f"could not read Python source: {relative_path}"
        corpus.append((relative_path, source))
    if not corpus:
        return (), "Python source corpus is empty"
    return tuple(corpus), None


def _unreferenced_symbols(
    symbols: tuple[tuple[str, str], ...],
    corpus: tuple[tuple[str, str], ...],
) -> list[dict[str, str]]:
    """Return symbols with no caller, preserving the legacy path filters."""
    dead_symbols: list[dict[str, str]] = []
    for symbol, defined_in in symbols:
        callers = [path for path, source in corpus if symbol in source and path != defined_in and not _is_test_only_path(path)]
        if not callers:
            dead_symbols.append({"symbol": symbol, "file": defined_in})
    return dead_symbols


def _append_undeterminable(
    *,
    reason: str,
    console: Console,
    findings: list[dict[str, str]],
) -> None:
    diagnostic_code = MissionReviewDiagnostic.DEAD_CODE_UNDETERMINABLE
    console.print(f"  [red]✗[/red]  Dead-code scan: undeterminable ({diagnostic_code})")
    console.print(f"       reason: {reason}")
    console.print(f"       remediation: {_UNDETERMINABLE_REMEDIATION}")
    findings.append(
        {
            "type": "dead_code_undeterminable",
            "diagnostic_code": str(diagnostic_code),
            "reason": reason,
            "remediation": _UNDETERMINABLE_REMEDIATION,
        }
    )


def _append_not_applicable(
    *,
    discovery: _Discovery,
    console: Console,
    findings: list[dict[str, str]],
) -> None:
    """Record that the Python-only scan does not apply to this change set."""
    diagnostic_code = MissionReviewDiagnostic.DEAD_CODE_NOT_APPLICABLE
    extensions = ", ".join(discovery.unsupported_extensions)
    reason = (
        "no changed file is one the dead-code scan supports "
        f"(unsupported extensions: {extensions or '(none)'}; "
        f"test-only Python paths excluded: {discovery.excluded_test_paths})"
    )
    console.print(f"  [yellow]⚠[/yellow]  Dead-code scan: not applicable ({diagnostic_code})")
    console.print(f"       reason: {reason}")
    console.print(f"       remediation: {_NOT_APPLICABLE_REMEDIATION}")
    findings.append(
        {
            "type": "dead_code_not_applicable",
            "diagnostic_code": str(diagnostic_code),
            "unsupported_extensions": extensions,
            "excluded_test_paths": str(discovery.excluded_test_paths),
            "reason": reason,
            "remediation": _NOT_APPLICABLE_REMEDIATION,
        }
    )


#: ``reason`` value on a ``dead_code_baseline_missing`` finding whose mission
#: was accepted through a GitHub PR (``meta.json`` ``acceptance_mode: "pr"``):
#: the missing baseline means the PR merge was never recorded, not that the
#: mission never merged (#4231 — the two previously produced the identical
#: verdict, so a cleanly PR-merged mission was indistinguishable from a
#: fidelity failure).
_REASON_PR_MERGE_UNRECORDED = "pr_accepted_merge_unrecorded"
_REASON_NEVER_MERGED = "never_merged_via_spec_kitty_merge"

#: ``meta.json`` ``pr_merge_evidence`` values the dead-code gate accepts as a
#: COMPLETE anchor: a two-parent merge landing and a single-parent landing,
#: each recorded under the operator's explicit ``--attest-first-landing-commit``
#: attestation (#4231 fix rounds 3–4 — neither shape is a git proof, because
#: post-landing git history cannot show which side of a landing the target
#: branch stood on). An ABSENT field is the ``spec-kitty consolidate``
#: local-recording lane (which captures the real target tip at merge time) and
#: scans normally; a PRESENT value outside this set means the anchor's
#: completeness is not established, so the gate surfaces that state instead of
#: reporting a green scan over a possibly truncated diff.
#:
#: Bound to the writer's own constants (``specify_cli.consolidation.baseline``) rather
#: than duplicating the string literals here, so the reader and the writer can
#: never drift out of sync.
_COMPLETE_ANCHOR_EVIDENCE = frozenset(
    {
        ANCHOR_EVIDENCE_MERGE_COMMIT_PARENT_ATTESTED,
        ANCHOR_EVIDENCE_CORPUS_PARENT_ATTESTED,
    }
)

_PR_MERGE_EVIDENCE_INCOMPLETE_REMEDIATION = (
    "This mission's baseline_merge_commit was recorded from a PR landing "
    "whose anchor evidence is not recognized as complete "
    f"(pr_merge_evidence must be one of {sorted(_COMPLETE_ANCHOR_EVIDENCE)}). "
    "Re-record the baseline from the PR's landing commit with the operator "
    "attestation (`spec-kitty migrate backfill-merge-commit --mission "
    "<slug> --merge-commit <sha> --attest-first-landing-commit`), then rerun "
    "review. A scan anchored on incomplete evidence could silently miss "
    "mission changes."
)

_PR_MERGE_UNRECORDED_REMEDIATION = (
    "This mission was accepted via PR (acceptance_mode: pr): the missing "
    "baseline_merge_commit means the PR merge was never recorded, not that "
    "the mission never merged. If the PR has merged, record the real merge "
    "commit with `spec-kitty migrate backfill-merge-commit --mission "
    "<slug> --merge-commit <sha>` (or re-run `spec-kitty accept --mode pr "
    "--merge-commit <sha>`); if it has not, merge it, then rerun review "
    "with `--mode post-merge`."
)


def _handle_missing_baseline(
    *,
    console: Console,
    findings: list[dict[str, str]],
    mission_id: str | None,
    mission_slug: str | None,
    acceptance_mode: str | None = None,
) -> None:
    if mission_id:
        # #4231: a PR-accepted mission without a baseline is a DIFFERENT state
        # from a never-merged mission — the merge likely happened and was
        # simply never recorded. Same verdict weight (still a hard fail: the
        # dead-code gate cannot run), but a distinct reason + remediation so a
        # later reader can tell the two apart without re-deriving the audit.
        pr_accepted = (acceptance_mode or "").strip().lower() == "pr"
        if pr_accepted:
            reason = _REASON_PR_MERGE_UNRECORDED
            remediation = _PR_MERGE_UNRECORDED_REMEDIATION
        else:
            reason = _REASON_NEVER_MERGED
            remediation = "Run `spec-kitty consolidate` to bake baseline_merge_commit into meta.json, or rerun review with `--mode post-merge` after merge."
        console.print(f"  [red]✗[/red]  Dead-code scan: missing baseline_merge_commit ({MissionReviewDiagnostic.LIGHTWEIGHT_REVIEW_MISSING_BASELINE})")
        console.print(f"       reason: {reason}")
        console.print(f"       remediation: {remediation}")
        findings.append(
            {
                "type": "dead_code_baseline_missing",
                "diagnostic_code": str(MissionReviewDiagnostic.LIGHTWEIGHT_REVIEW_MISSING_BASELINE),
                "mission_id": mission_id,
                "mission_slug": mission_slug or "",
                "reason": reason,
                "remediation": remediation,
            }
        )
        return
    console.print(
        f"  [yellow]⚠[/yellow]  Dead-code scan skipped: no baseline_merge_commit in meta.json"
        f" (legacy / pre-083 mission, {MissionReviewDiagnostic.LEGACY_MISSION_DEAD_CODE_SKIP})"
    )


def _handle_incomplete_evidence(
    *,
    console: Console,
    findings: list[dict[str, str]],
    pr_merge_evidence: str,
) -> None:
    """Surface an anchor whose completeness is not established — never green.

    ``pr_merge_evidence`` (from ``meta.json``) names what the recorded
    ``baseline_merge_commit`` anchor rests on. A value the recording seam
    never writes means the anchor's completeness is unproven: running the
    scan anyway could report 0 unreferenced symbols over a truncated diff —
    the strictly-worse third state this gate exists to avoid — so the gate
    fails with its own diagnostic instead of scanning.
    """
    diagnostic_code = MissionReviewDiagnostic.DEAD_CODE_EVIDENCE_INCOMPLETE
    console.print(f"  [red]✗[/red]  Dead-code scan: baseline evidence incomplete ({diagnostic_code})")
    console.print(f"       pr_merge_evidence: {pr_merge_evidence}")
    console.print(f"       remediation: {_PR_MERGE_EVIDENCE_INCOMPLETE_REMEDIATION}")
    findings.append(
        {
            "type": "dead_code_evidence_incomplete",
            "diagnostic_code": str(diagnostic_code),
            "pr_merge_evidence": pr_merge_evidence,
            "remediation": _PR_MERGE_EVIDENCE_INCOMPLETE_REMEDIATION,
        }
    )


def scan_dead_code(
    baseline_merge_commit: str | None,
    repo_root: Path,
    console: Console,
    findings: list[dict[str, str]],
    *,
    mission_id: str | None = None,
    mission_slug: str | None = None,
    acceptance_mode: str | None = None,
    pr_merge_evidence: str | None = None,
) -> DeadCodeOutcome:
    """Scan added public Python symbols and emit an earned review verdict.

    Returns ``"not_applicable"`` when the change set holds nothing the
    Python-only scan supports (the caller records the gate as ``skip``),
    ``"unscanned"`` when the scan could not run, else ``"scanned"``.

    ``acceptance_mode`` (from ``meta.json``) only changes the *reason* and
    *remediation* attached to a ``dead_code_baseline_missing`` finding — never
    the verdict itself: a missing baseline is a hard fail either way because
    the dead-code gate cannot run without an anchor.

    ``pr_merge_evidence`` (from ``meta.json``, written only by the PR-merge
    recording seam) names what the anchor's completeness rests on. The two
    values that seam writes — ``merge-commit-parent-attested`` and
    ``corpus-parent-attested`` (a two-parent and a single-parent landing,
    each recorded under the operator's ``--attest-first-landing-commit``
    attestation) — and an absent field (the ``spec-kitty consolidate``
    local-recording lane) scan normally; any other PRESENT value surfaces
    ``MISSION_REVIEW_DEAD_CODE_EVIDENCE_INCOMPLETE`` instead of a green scan,
    because the anchor may not cover the whole mission.
    """
    if not baseline_merge_commit:
        _handle_missing_baseline(
            console=console,
            findings=findings,
            mission_id=mission_id,
            mission_slug=mission_slug,
            acceptance_mode=acceptance_mode,
        )
        return "unscanned"

    evidence_value = (pr_merge_evidence or "").strip()
    if evidence_value and evidence_value not in _COMPLETE_ANCHOR_EVIDENCE:
        _handle_incomplete_evidence(
            console=console,
            findings=findings,
            pr_merge_evidence=evidence_value,
        )
        return "unscanned"

    discovery = _discover_changed_symbols(repo_root, baseline_merge_commit)
    if discovery.outcome == "not_applicable":
        _append_not_applicable(discovery=discovery, console=console, findings=findings)
        return "not_applicable"
    if discovery.error is not None:
        _append_undeterminable(
            reason=discovery.error,
            console=console,
            findings=findings,
        )
        return "unscanned"
    if discovery.unsupported_extensions:
        extensions = ", ".join(discovery.unsupported_extensions)
        console.print(f"  [yellow]⚠[/yellow]  Dead-code scan: not applicable to some changed files ({extensions})")

    corpus, corpus_error = _load_python_corpus(
        repo_root,
        discovery.changed_paths,
    )
    if corpus_error is not None:
        _append_undeterminable(
            reason=corpus_error,
            console=console,
            findings=findings,
        )
        return "unscanned"

    dead_symbols = _unreferenced_symbols(discovery.symbols, corpus)
    for dead_symbol in dead_symbols:
        findings.append({"type": "dead_code", **dead_symbol})

    if dead_symbols:
        console.print(f"  [red]✗[/red]  Dead-code scan: {len(dead_symbols)} unreferenced public symbol(s)")
        for dead_symbol in dead_symbols:
            console.print(f"       {dead_symbol['file']}  {dead_symbol['symbol']}")
        return "scanned"
    console.print("  [green]✓[/green]  Dead-code scan: 0 unreferenced public symbols")
    return "scanned"
