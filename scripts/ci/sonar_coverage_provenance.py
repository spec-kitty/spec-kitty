"""Bind nightly Sonar coverage to the exact checked-out source revision.

The nightly ``Sonar`` workflow consumes coverage artefacts produced by the
successful ``CI Modules`` run for the commit it analyses. Before this helper it
selected the newest successful run for the branch, whatever its ``head_sha``,
and filled gaps from the run before it. On a nightly that had no run at the
checked-out revision (or on a force-push/re-run race) that silently scanned one
revision's source with another revision's coverage.

This module owns the two decisions, so each is testable against a recorded
GitHub API payload without executing a workflow:

``select``
    Given a ``listWorkflowRuns`` payload (``{"workflow_runs": [...]}`` or the
    bare list), the checked-out ``source_sha`` and, when the ref is a branch,
    that ``branch``, return at most two runs: the newest successful run whose
    ``head_sha`` is exactly ``source_sha`` (and whose ``head_branch`` is
    ``branch``) and, as a gap-filling fallback at the SAME source revision, the
    next-newest such run. Every other run is ignored and counted with a reason:
    another revision, another branch, a non-success status/conclusion.

    Runs are grouped by ``id`` first: for one workflow run only its highest
    ``run_attempt`` is considered, because the artifact download action fetches
    the latest attempt. A higher attempt that failed therefore yields no
    coverage -- it never falls back to an older attempt of the same run.
    Selection order is deterministic: ``(run_number, run_id, run_attempt)``
    descending, independent of API response order.

``reconcile``
    Deduplicate downloaded ``coverage-*.xml`` basenames (current run first,
    same-revision fallback fills gaps) into the comma-joined ``reportPaths``
    value Sonar merges server-side.

Both commands are informational: a missing matching run or an empty coverage
tree prints a ``::warning::`` and exits 0, because ``sonar.yml`` is an
advisory, non-required nightly check. They never substitute another revision's
coverage, and never fail a fork-safe run that has no ``SONAR_TOKEN`` (the
workflow does not call them in that case).

Standard library only, so the workflow can run it with a bare ``python3``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from collections.abc import Iterable, Mapping, Sequence

__all__ = (
    "ProvenanceError",
    "ReconcileResult",
    "RunCandidate",
    "Selection",
    "load_payload",
    "reconcile_coverage",
    "select_runs",
    "write_outputs",
)


class ProvenanceError(ValueError):
    """A payload or invocation cannot be evaluated (never a data verdict)."""


@dataclass(frozen=True)
class RunCandidate:
    """One workflow run, reduced to the fields provenance depends on."""

    run_id: int
    run_number: int
    run_attempt: int
    head_sha: str
    head_branch: str | None
    status: str
    conclusion: str | None


@dataclass(frozen=True)
class Selection:
    """The runs at the checked-out revision, newest first."""

    source_sha: str
    branch: str | None
    primary: RunCandidate | None
    fallback: RunCandidate | None
    ignored: Mapping[str, int] = field(default_factory=dict)

    @property
    def coverage_available(self) -> bool:
        return self.primary is not None

    @property
    def reason(self) -> str:
        """One-line human explanation of the verdict (never multiline)."""
        target = f"source revision {self.source_sha}"
        if self.branch is not None:
            target += f" on branch {self.branch}"
        if self.primary is None:
            ignored = sum(self.ignored.values())
            if ignored:
                counted = ", ".join(f"{count} {reason}" for reason, count in sorted(self.ignored.items()))
                return (
                    f"no successful CI Modules run at {target}; ignored {ignored} candidate run(s): {counted}. "
                    "Scanning without coverage rather than reusing another revision's report."
                )
            return f"no CI Modules run returned for {target}. Scanning without coverage rather than reusing another revision's report."
        if self.fallback is not None:
            return (
                f"coverage bound to CI Modules run {self.primary.run_id} attempt {self.primary.run_attempt} at {target}; "
                f"run {self.fallback.run_id} (same source revision) fills missing report basenames"
            )
        return f"coverage bound to CI Modules run {self.primary.run_id} attempt {self.primary.run_attempt} at {target}"


def _as_int(value: Any, *, field_name: str, run: Mapping[str, Any]) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ProvenanceError(f"run {run.get('id')!r}: {field_name} is not an integer: {value!r}") from error


def _candidate(run: Any) -> RunCandidate | None:
    """A payload entry to :class:`RunCandidate`, or ``None`` when it is unusable."""
    if not isinstance(run, Mapping):
        return None
    run_id = run.get("id")
    head_sha = run.get("head_sha")
    if run_id is None or not isinstance(head_sha, str) or not head_sha:
        return None
    try:
        return RunCandidate(
            run_id=_as_int(run_id, field_name="id", run=run),
            run_number=_as_int(run.get("run_number", 0), field_name="run_number", run=run),
            run_attempt=_as_int(run.get("run_attempt", 1), field_name="run_attempt", run=run),
            head_sha=head_sha.lower(),
            head_branch=run.get("head_branch") if isinstance(run.get("head_branch"), str) else None,
            status=str(run.get("status") or ""),
            conclusion=str(run["conclusion"]) if run.get("conclusion") is not None else None,
        )
    except ProvenanceError:
        return None


def _payload_runs(payload: Any) -> list[Any]:
    if isinstance(payload, Mapping):
        runs = payload.get("workflow_runs")
        if runs is None:
            raise ProvenanceError("payload is a mapping without a workflow_runs key")
        if not isinstance(runs, list):
            raise ProvenanceError("payload workflow_runs is not a list")
        return runs
    if isinstance(payload, list):
        return payload
    raise ProvenanceError("payload is neither a mapping nor a list")


def load_payload(path: Path) -> Any:
    """Read and shape-check a recorded ``listWorkflowRuns`` JSON payload."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ProvenanceError(f"cannot read run payload {path}: {error}") from error
    except ValueError as error:
        raise ProvenanceError(f"run payload {path} is not valid JSON: {error}") from error
    _payload_runs(payload)
    return payload


def _newest_attempt_by_run_id(runs: Iterable[Any], ignored: Counter[str]) -> dict[int, RunCandidate]:
    """Collapse a payload to one candidate per workflow run id: its newest attempt."""
    by_id: dict[int, RunCandidate] = {}
    for run in runs:
        candidate = _candidate(run)
        if candidate is None:
            ignored["malformed"] += 1
            continue
        current = by_id.get(candidate.run_id)
        if current is None or (candidate.run_attempt, candidate.run_number) > (current.run_attempt, current.run_number):
            by_id[candidate.run_id] = candidate
    return by_id


def _succeeded(candidate: RunCandidate) -> bool:
    """A completed workflow run whose conclusion is success.

    Both REST fields must agree: a partial or inconsistent payload is not
    successful revision evidence.
    """
    return candidate.status == "completed" and candidate.conclusion == "success"


def select_runs(payload: Any, *, source_sha: str, branch: str | None = None) -> Selection:
    """Select successful runs at exactly ``source_sha`` (and ``branch`` when given)."""
    if not source_sha:
        raise ProvenanceError("source_sha is required: coverage provenance is bound to a revision")
    expected_sha = source_sha.lower()
    ignored: Counter[str] = Counter()
    candidates = _newest_attempt_by_run_id(_payload_runs(payload), ignored)

    eligible: list[RunCandidate] = []
    for candidate in candidates.values():
        if candidate.head_sha != expected_sha:
            ignored["at another source revision"] += 1
            continue
        if branch is not None and candidate.head_branch != branch:
            ignored["on another branch"] += 1
            continue
        if not _succeeded(candidate):
            conclusion = candidate.conclusion or candidate.status or "unknown"
            ignored[f"with {conclusion} conclusion"] += 1
            continue
        eligible.append(candidate)

    eligible.sort(key=lambda run: (run.run_number, run.run_id, run.run_attempt), reverse=True)
    return Selection(
        source_sha=expected_sha,
        branch=branch,
        primary=eligible[0] if eligible else None,
        fallback=eligible[1] if len(eligible) > 1 else None,
        ignored=dict(sorted(ignored.items())),
    )


@dataclass(frozen=True)
class ReconcileResult:
    """Resolved coverage files and the basenames filled from the fallback run."""

    report_paths: str
    files: tuple[Path, ...]
    stale: tuple[str, ...]


def _coverage_files(directory: Path | None) -> list[Path]:
    if directory is None or not directory.exists():
        return []

    def order(path: Path) -> tuple[int, str]:
        # Reruns retain previous-attempt artifacts under the same run id.
        # Download-artifact does not select an attempt for us; prefer the
        # latest report for each basename, never an older partial report.
        attempts = [int(match[1]) for part in path.parts if (match := re.search(r"-attempt-([0-9]+)-reports$", part))]
        return (-max(attempts, default=0), str(path))

    return sorted((path for path in directory.rglob("coverage-*.xml") if path.is_file()), key=order)


def reconcile_coverage(*, current: Path | None, fallback: Path | None) -> ReconcileResult:
    """Deduplicate coverage basenames; the current run wins, the fallback fills gaps."""
    resolved: dict[str, Path] = {}
    stale: list[str] = []
    for path in _coverage_files(current):
        resolved.setdefault(path.name, path)
    for path in _coverage_files(fallback):
        if path.name not in resolved:
            resolved[path.name] = path
            stale.append(path.name)
    files = tuple(resolved[name] for name in sorted(resolved))
    return ReconcileResult(
        report_paths=",".join(str(path) for path in files),
        files=files,
        stale=tuple(stale),
    )


def _one_line(value: str) -> str:
    return " ".join(value.split())


def write_outputs(path: Path | None, outputs: Mapping[str, str]) -> None:
    """Append ``key=value`` lines to a GitHub step output file (or stdout)."""
    lines = "".join(f"{key}={_one_line(str(value))}\n" for key, value in outputs.items())
    if path is None:
        sys.stdout.write(lines)
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(lines)


def _select_command(args: argparse.Namespace) -> int:
    payload = load_payload(Path(args.runs))
    selection = select_runs(payload, source_sha=args.source_sha, branch=args.branch)
    outputs = {
        "run_id": "" if selection.primary is None else str(selection.primary.run_id),
        "fallback_run_id": "" if selection.fallback is None else str(selection.fallback.run_id),
        "run_attempt": "" if selection.primary is None else str(selection.primary.run_attempt),
        "run_number": "" if selection.primary is None else str(selection.primary.run_number),
        "source_sha": selection.source_sha,
        "branch": selection.branch or "",
        "coverage_available": "true" if selection.coverage_available else "false",
        "reason": selection.reason,
    }
    write_outputs(None if args.output is None else Path(args.output), outputs)
    level = "notice" if selection.coverage_available else "warning"
    print(f"::{level}::sonar: {selection.reason}")
    return 0


def _reconcile_command(args: argparse.Namespace) -> int:
    result = reconcile_coverage(
        current=None if args.current is None else Path(args.current),
        fallback=None if args.fallback is None else Path(args.fallback),
    )
    write_outputs(
        None if args.output is None else Path(args.output),
        {
            "report-paths": result.report_paths,
            "coverage-files": str(len(result.files)),
            "stale-basenames": ",".join(result.stale),
        },
    )
    if result.files:
        source = f" for source revision {args.source_sha}" if args.source_sha else ""
        print(
            f"::notice::sonar: resolved {len(result.files)} coverage report(s){source}; "
            f"{len(result.stale)} served from the same-revision fallback: {sorted(result.stale)}"
        )
    else:
        source = f" for source revision {args.source_sha}" if args.source_sha else ""
        print(f"::warning::sonar: no coverage report found{source}; scanning without coverage rather than reusing another revision's report.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bind nightly Sonar coverage to the checked-out source revision.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    select_parser = subparsers.add_parser("select", help="choose successful CI Modules runs at one source revision")
    select_parser.add_argument("--runs", required=True, help="recorded listWorkflowRuns JSON payload")
    select_parser.add_argument("--source-sha", required=True, help="the checked-out revision")
    select_parser.add_argument("--branch", default=None, help="the checked-out branch (omit for a detached ref)")
    select_parser.add_argument("--output", default=None, help="GitHub step output file (default: stdout)")
    select_parser.set_defaults(handler=_select_command)

    reconcile_parser = subparsers.add_parser("reconcile", help="dedupe downloaded coverage basenames")
    reconcile_parser.add_argument("--current", default=None, help="directory holding the selected run's reports")
    reconcile_parser.add_argument("--fallback", default=None, help="directory holding the same-revision fallback reports")
    reconcile_parser.add_argument("--source-sha", default=None, help="the checked-out revision (for the notice)")
    reconcile_parser.add_argument("--output", default=None, help="GitHub step output file (default: stdout)")
    reconcile_parser.set_defaults(handler=_reconcile_command)

    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except ProvenanceError as error:
        print(f"::error::sonar: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover - exercised through main()
    raise SystemExit(main())
