"""Reactive stale-running sweep backstop (mission ci-terminal-cancel-verdict, 4b).

A scheduled safety net for the one wedge the in-CI reporter (4a,
``scripts/ci/fleet_verdict.py``) structurally cannot reach: a head whose latest
``[ci]`` verdict is ``running`` while *every* required run has already reached a
terminal state. That happens when the reporter run itself was cancelled (the
Stage-1 "survivor-no-successor" soft-wedge) or on the cancelled-``main``
residual -- no later reporter event ever fires to release the head.

This module is a **backstop, not the verdict authority** (C-003 / FR-008 /
SW-1). It only *surfaces* a wedge:

- it posts an idempotent, ``[ci-sweep]``-namespaced watch comment on the
  affected PR plus a ``::warning::`` annotation, and
- it NEVER posts a ``[ci] <state>`` verdict, edits the reporter's comments,
  re-triggers CI, or auto-releases a head.

The decision is a *pure* function of injected values (:func:`find_stale_running`
-- no I/O, no ``subprocess``, no clock) so it is unit-testable red-first. The
``gh`` calls that gather open PRs, their latest ``[ci]`` comment and their runs
live only at :func:`main`'s edge, mirroring ``select_source_artifacts.py`` /
``source_eligibility.py``. The ``[ci] <state> @<head>`` verdict vocabulary and
the authenticated ``GitHub`` client are reused read-only from ``fleet_verdict``.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Actions runs this trusted-checkout script before installing the package, and
# ``scripts.ci`` resolves as a namespace package only with the repo root on the
# path. Resolve from the script, never the caller's cwd.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.ci.fleet_verdict import GitHub  # noqa: E402  (import after the path guard above)

# The reporter's own verdict vocabulary (fleet_verdict keeps the authoritative
# recognition regex inline in ``report``); the sweep only *reads* these states.
_VERDICT_STATES = ("green", "red", "running", "infra-error", "no suite")
_RUNNING = "running"

_CI_VERDICT_RE = re.compile(r"^\[ci\] (" + "|".join(re.escape(s) for s in _VERDICT_STATES) + r") @([0-9a-f]{40})\b")
_SHA_RE = re.compile(r"[0-9a-f]{40}")

# The sweep's watch surface -- deliberately NOT the reporter's `[ci]` marker.
SWEEP_MARKER = "<!-- spec-kitty-ci-sweep-v1 -->"
_FINGERPRINT_RE = re.compile(r"<!-- ci-sweep-fingerprint: ([^>]+?) -->")


@dataclass(frozen=True)
class RunState:
    """One required run's terminal state (``status`` is the only detector input)."""

    name: str
    status: str
    conclusion: str | None = None

    @property
    def is_terminal(self) -> bool:
        """A run is terminal iff GitHub reports ``status == "completed"`` (cancelled included)."""
        return self.status == "completed"


@dataclass(frozen=True)
class Candidate:
    """One head to evaluate, with every value the pure detector needs injected."""

    subject: str  # "pr#<n>" or "main"
    head_sha: str
    latest_verdict: str | None  # the latest `[ci] <state> @head` state, or None
    required_runs: tuple[RunState, ...]
    existing_sweep_fingerprints: frozenset[str] = field(default_factory=frozenset)

    @property
    def fingerprint(self) -> str:
        """A per-head dedup key: a new commit yields a new fingerprint (SW-2)."""
        return f"{self.subject}@{self.head_sha}"


@dataclass(frozen=True)
class StaleHead:
    """A surfaced wedge: subject, head, human reason, and the dedup fingerprint."""

    subject: str
    head_sha: str
    reason: str
    fingerprint: str


def _is_stale_running(candidate: Candidate) -> bool:
    """Pure staleness rule (data-model 4b): running verdict + all runs terminal.

    Fail-closed (SW-3): a terminal/absent verdict, no required runs, or any
    non-terminal required run -> not stale.
    """
    if candidate.latest_verdict != _RUNNING:
        return False
    if not candidate.required_runs:
        return False
    return all(run.is_terminal for run in candidate.required_runs)


def _reason(candidate: Candidate) -> str:
    cancelled = sorted(run.name for run in candidate.required_runs if run.conclusion == "cancelled")
    detail = f"; cancelled run(s): {', '.join(cancelled)}" if cancelled else ""
    return f"latest [ci] verdict is 'running' for {candidate.head_sha} but all {len(candidate.required_runs)} required run(s) have reached a terminal state{detail}"


def find_stale_running(candidates: list[Candidate]) -> list[StaleHead]:
    """Pure detector: heads wedged at ``running`` while all required runs are terminal.

    A head is stale-running iff its latest ``[ci]`` verdict is ``running`` for
    that head AND its required runs are non-empty AND every one is terminal
    (``status == "completed"``, cancelled included). Fail-closed (SW-3): a
    non-terminal run, a terminal/absent verdict, or zero runs -> not flagged.
    Idempotent (SW-2): a head already carrying its own ``[ci-sweep]``
    fingerprint is skipped, so a re-run posts no duplicate surface.
    """
    stale: list[StaleHead] = []
    for candidate in candidates:
        if not _is_stale_running(candidate):
            continue
        if candidate.fingerprint in candidate.existing_sweep_fingerprints:
            continue
        stale.append(
            StaleHead(
                subject=candidate.subject,
                head_sha=candidate.head_sha,
                reason=_reason(candidate),
                fingerprint=candidate.fingerprint,
            )
        )
    return stale


def watch_comment_body(stale: StaleHead) -> str:
    """Render the ``[ci-sweep]`` watch comment -- a backstop notice, never a verdict.

    The body carries :data:`SWEEP_MARKER` and an embedded per-head fingerprint so
    a later sweep dedups against it (SW-2), and it never reproduces the reporter's
    ``[ci] <state> @<head>`` format (SW-1).
    """
    return (
        "\n".join(
            [
                f"[ci-sweep] stale-running watch for {stale.subject} @{stale.head_sha}",
                "",
                SWEEP_MARKER,
                f"<!-- ci-sweep-fingerprint: {stale.fingerprint} -->",
                "",
                "This is a **backstop watch item**, not a CI verdict. The latest "
                "`[ci]` verdict for this head is `running`, yet every required run "
                "has already reached a terminal state -- a cancelled reporter or "
                "producer run can wedge a head at `running` with no later event to "
                "release it.",
                "",
                f"Reason: {stale.reason}",
                "",
                "Action: re-run the required workflow(s) so the reporter re-evaluates "
                "and releases the head. This sweep never posts a `[ci]` verdict, never "
                "edits the reporter's comments, and never re-triggers CI itself.",
                "",
            ]
        )
        + "\n"
    )


# --------------------------------------------------------------------------- #
# Edge -- gh at the boundary only. Never covered by the pure unit tests.      #
# --------------------------------------------------------------------------- #


def _is_sha(value: object) -> bool:
    return isinstance(value, str) and _SHA_RE.fullmatch(value) is not None


def _latest_verdict(comments: list[dict[str, object]], head_sha: str) -> str | None:
    """The most recent ``[ci] <state> @<head_sha>`` verdict state, or None."""
    for comment in reversed(comments):
        body = comment.get("body")
        if not isinstance(body, str):
            continue
        match = _CI_VERDICT_RE.match(body)
        if match is not None and match.group(2) == head_sha:
            return match.group(1)
    return None


def _sweep_fingerprints(comments: list[dict[str, object]]) -> frozenset[str]:
    """Every ``[ci-sweep]`` fingerprint already posted on this subject (SW-2)."""
    found: set[str] = set()
    for comment in comments:
        body = comment.get("body")
        if isinstance(body, str) and SWEEP_MARKER in body:
            found.update(_FINGERPRINT_RE.findall(body))
    return frozenset(found)


def _required_runs(api: GitHub, head_sha: str) -> tuple[RunState, ...]:
    """The pull-request runs for this head (a safe superset of the required gates).

    Requiring *every* run to be terminal is fail-closed: an in-flight run keeps
    the head un-flagged, so a broad run set can only suppress a watch item, never
    fabricate one.
    """
    runs = api.pages(f"actions/runs?head_sha={head_sha}&event=pull_request", "workflow_runs")
    return tuple(
        RunState(
            name=Path(str(run.get("path", ""))).name or str(run.get("id", "")),
            status=str(run.get("status", "")),
            conclusion=run.get("conclusion") if isinstance(run.get("conclusion"), str) else None,
        )
        for run in runs
    )


def _gather_candidates(api: GitHub) -> list[Candidate]:
    """Read open PRs, their latest ``[ci]`` verdict, their runs and prior sweeps."""
    candidates: list[Candidate] = []
    for pr in api.pages("pulls?state=open"):
        number = pr.get("number")
        head = pr.get("head")
        head_sha = head.get("sha") if isinstance(head, dict) else None
        if not isinstance(number, int) or not _is_sha(head_sha):
            continue
        assert isinstance(head_sha, str)  # narrowed by _is_sha for the type checker
        comments = api.pages(f"issues/{number}/comments")
        candidates.append(
            Candidate(
                subject=f"pr#{number}",
                head_sha=head_sha,
                latest_verdict=_latest_verdict(comments, head_sha),
                required_runs=_required_runs(api, head_sha),
                existing_sweep_fingerprints=_sweep_fingerprints(comments),
            )
        )
    return candidates


def _pr_number(subject: str) -> int | None:
    match = re.fullmatch(r"pr#([1-9][0-9]*)", subject)
    return int(match.group(1)) if match else None


def _surface(api: GitHub, stale: StaleHead, *, dry_run: bool) -> None:
    """Emit the annotation and post the PR watch comment (append-once; SW-1)."""
    print(f"::warning::[ci-sweep] stale-running head {stale.subject} @{stale.head_sha}: {stale.reason}")
    number = _pr_number(stale.subject)
    if number is None:
        # The operator-ratified surface is a PR comment; a non-PR subject only annotates.
        return
    body = watch_comment_body(stale)
    if dry_run:
        print(body, end="")
        return
    api.request(f"issues/{number}/comments", {"body": body})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reactive stale-running sweep backstop (surface-only; never a verdict).")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"), help="owner/repo (default: $GITHUB_REPOSITORY).")
    parser.add_argument("--dry-run", action="store_true", help="Print the watch comment instead of posting it.")
    args = parser.parse_args(argv)
    if not args.repository:
        parser.error("repository is required (pass --repository or set GITHUB_REPOSITORY)")

    api = GitHub(args.repository)
    stale_heads = find_stale_running(_gather_candidates(api))
    for stale in stale_heads:
        _surface(api, stale, dry_run=args.dry_run)
    if not stale_heads:
        print("::notice::[ci-sweep] no stale-running heads detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
