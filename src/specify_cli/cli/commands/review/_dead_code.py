"""Gate 2: portable dead-code scan."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from ._diagnostics import MissionReviewDiagnostic

_IDENTIFIER_CHARCLASS = r"\w"
_UNDETERMINABLE_REMEDIATION = "Verify the baseline commit and Git repository, then rerun `spec-kitty review`."
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


@dataclass(frozen=True)
class _Discovery:
    """Result of baseline-to-HEAD symbol discovery."""

    changed_paths: tuple[str, ...]
    symbols: tuple[tuple[str, str], ...]
    error: str | None = None


def _run_git_diff(
    repo_root: Path,
    baseline_merge_commit: str,
    *diff_args: str,
) -> subprocess.CompletedProcess[str] | None:
    """Run a deterministic Git diff, returning ``None`` when Git is unavailable."""
    try:
        return subprocess.run(
            ["git", "diff", *diff_args, f"{baseline_merge_commit}..HEAD", "--"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return None


def _extract_added_symbols(
    diff_output: str,
    supported_paths: frozenset[str],
) -> tuple[tuple[str, str], ...]:
    """Extract added public Python symbols from unified diff text."""
    symbols: list[tuple[str, str]] = []
    current_file = ""
    for line in diff_output.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
        elif current_file in supported_paths and line.startswith("+") and not line.startswith("+++"):
            match = re.match(
                rf"^\+\s*(def|class)\s+([A-Za-z]{_IDENTIFIER_CHARCLASS}*)\s*[\(:]",
                line,
            )
            if match and not match.group(2).startswith("_"):
                symbols.append((match.group(2), current_file))
    return tuple(symbols)


def _discover_changed_symbols(
    repo_root: Path,
    baseline_merge_commit: str,
) -> _Discovery:
    """Discover changed paths and added Python symbols without a source-root assumption."""
    name_result = _run_git_diff(repo_root, baseline_merge_commit, "--name-only")
    if name_result is None:
        return _Discovery((), (), "git executable is unavailable")
    if name_result.returncode != 0:
        return _Discovery((), (), "git diff failed")

    changed_paths = tuple(path for path in name_result.stdout.splitlines() if path)
    if not changed_paths:
        return _Discovery((), (), "git diff reported no changed files")
    changed_python_paths = tuple(path for path in changed_paths if path.endswith(".py"))
    supported_paths = tuple(path for path in changed_python_paths if path.startswith("src/") or "test" not in path)
    if not supported_paths:
        return _Discovery(
            changed_paths,
            (),
            "changed source set contains no supported Python files",
        )

    diff_result = _run_git_diff(repo_root, baseline_merge_commit, "--unified=0")
    if diff_result is None:
        return _Discovery(changed_paths, (), "git executable is unavailable")
    if diff_result.returncode != 0:
        return _Discovery(changed_paths, (), "git diff failed")
    return _Discovery(
        supported_paths,
        _extract_added_symbols(diff_result.stdout, frozenset(supported_paths)),
    )


def _load_python_corpus(
    repo_root: Path,
    changed_paths: tuple[str, ...],
) -> tuple[tuple[tuple[str, str], ...], str | None]:
    """Load the complete Python corpus, including untracked files, deterministically."""
    changed_python_paths = tuple(path for path in changed_paths if path.endswith(".py"))
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
        callers = [path for path, source in corpus if symbol in source and path != defined_in and "test" not in path]
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
#: branch stood on). An ABSENT field is the ``spec-kitty merge``
#: local-recording lane (which captures the real target tip at merge time) and
#: scans normally; a PRESENT value outside this set means the anchor's
#: completeness is not established, so the gate surfaces that state instead of
#: reporting a green scan over a possibly truncated diff.
_COMPLETE_ANCHOR_EVIDENCE = frozenset(
    {
        "merge-commit-parent-attested",
        "corpus-parent-attested",
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
            remediation = "Run `spec-kitty merge` to bake baseline_merge_commit into meta.json, or rerun review with `--mode post-merge` after merge."
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
) -> None:
    """Scan added public Python symbols and emit an earned review verdict.

    ``acceptance_mode`` (from ``meta.json``) only changes the *reason* and
    *remediation* attached to a ``dead_code_baseline_missing`` finding — never
    the verdict itself: a missing baseline is a hard fail either way because
    the dead-code gate cannot run without an anchor.

    ``pr_merge_evidence`` (from ``meta.json``, written only by the PR-merge
    recording seam) names what the anchor's completeness rests on. The two
    values that seam writes — ``merge-commit-parent-attested`` and
    ``corpus-parent-attested`` (a two-parent and a single-parent landing,
    each recorded under the operator's ``--attest-first-landing-commit``
    attestation) — and an absent field (the ``spec-kitty merge``
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
        return

    evidence_value = (pr_merge_evidence or "").strip()
    if evidence_value and evidence_value not in _COMPLETE_ANCHOR_EVIDENCE:
        _handle_incomplete_evidence(
            console=console,
            findings=findings,
            pr_merge_evidence=evidence_value,
        )
        return

    discovery = _discover_changed_symbols(repo_root, baseline_merge_commit)
    if discovery.error is not None:
        _append_undeterminable(
            reason=discovery.error,
            console=console,
            findings=findings,
        )
        return

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
        return

    dead_symbols = _unreferenced_symbols(discovery.symbols, corpus)
    for dead_symbol in dead_symbols:
        findings.append({"type": "dead_code", **dead_symbol})

    if dead_symbols:
        console.print(f"  [red]✗[/red]  Dead-code scan: {len(dead_symbols)} unreferenced public symbol(s)")
        for dead_symbol in dead_symbols:
            console.print(f"       {dead_symbol['file']}  {dead_symbol['symbol']}")
        return
    console.print("  [green]✓[/green]  Dead-code scan: 0 unreferenced public symbols")
