"""Name the shard that actually failed, so one red shard stops looking like forty (#4420).

``ci-modules.yml`` runs the module matrix with ``fail-fast: true`` in ``pr``
mode. That is a deliberate and defensible choice: it stops ~40 shards the
moment one goes red and saves a great deal of CI time. The cost lands
somewhere else entirely — **a cancelled shard is reported as a failure**.
``gh pr checks`` prints ``fail`` for it and the PR's check list renders it
exactly like a genuine red, so a single failing shard presents as forty
failing shards with nothing on the surface distinguishing the one that
actually failed from the thirty-nine that were merely stopped.

Recovering the real failure means listing the run's jobs and filtering on
``conclusion == "failure"`` — which a reader only knows to do *after* working
out that fail-fast is in play. The data is already there; it is the surface
that is missing. This module is that surface.

The false-attribution hazard is the reason this is worth a script rather than
a doc note: an engineer (or agent) who takes the check list at face value can
conclude their own change broke forty shards and start "fixing" tests it never
touched. The signal that prevents that — *one* shard failed, here it is, the
rest were stopped — is present in the API response and absent from the UI.

What this deliberately does not do
----------------------------------
It does not turn fail-fast off. Honest per-shard statuses at the cost of
running a full matrix past a known failure is a worse trade, and the issue
recorded that direction as considered and rejected.

It also never changes a run's conclusion. This is a reporting seam: it is
invoked from an ``if: always()`` step that tolerates its failure, so a
summariser bug can never redden a green run or green a red one.

Usage
-----
::

    gh api "repos/$REPO/actions/runs/$RUN_ID/jobs?per_page=100" \
      | python scripts/ci/summarize_shard_outcomes.py

Reads the GitHub "list jobs for a workflow run" payload on stdin (or from
``--jobs-file``), writes Markdown to ``$GITHUB_STEP_SUMMARY`` when that is set
(and always to stdout), and emits one ``::notice::`` workflow annotation so the
verdict appears at the top of the run page.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

# GitHub reports a job that never ran to completion as "cancelled". Under
# fail-fast that is the overwhelmingly common outcome and is NOT evidence of
# anything wrong with that shard.
CANCELLED = "cancelled"
FAILURE = "failure"
TIMED_OUT = "timed_out"

# A job that ran out of wall-clock is a genuine outcome worth naming
# separately: it is neither an innocent fail-fast casualty nor an assertion
# failure, and conflating it with either sends the reader to the wrong place.
REAL_FAILURE_CONCLUSIONS = (FAILURE, TIMED_OUT)


@dataclass(frozen=True)
class ShardOutcome:
    """One job's outcome, reduced to what a reader needs to act."""

    name: str
    conclusion: str
    url: str = ""


@dataclass(frozen=True)
class Summary:
    """The classification a reader needs, computed once."""

    failed: list[ShardOutcome] = field(default_factory=list)
    cancelled: list[ShardOutcome] = field(default_factory=list)
    succeeded: list[ShardOutcome] = field(default_factory=list)
    other: list[ShardOutcome] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.failed) + len(self.cancelled) + len(self.succeeded) + len(self.other)

    @property
    def headline(self) -> str:
        """One line that answers "what actually happened?" without scrolling.

        The zero-failure-but-cancelled case is called out separately and never
        described as a shard failure: that shape means the run was stopped from
        outside (a superseded push, a concurrency group, a manual cancel), and
        telling someone to go read a failing shard that does not exist is worse
        than saying nothing.
        """
        if not self.failed and self.cancelled:
            return (
                f"No shard failed. {len(self.cancelled)} of {self.total} jobs were cancelled — "
                f"this run was stopped from outside (superseded push, concurrency group, or manual cancel), "
                f"not by a test failure."
            )
        if not self.failed:
            return f"All {self.total} jobs passed."
        names = ", ".join(outcome.name for outcome in self.failed)
        if self.cancelled:
            return (
                f"{len(self.failed)} of {self.total} jobs actually failed ({names}). "
                f"The other {len(self.cancelled)} were CANCELLED by fail-fast, not failing — "
                f"do not read them as {len(self.cancelled)} separate breakages."
            )
        return f"{len(self.failed)} of {self.total} jobs failed ({names})."


def _conclusion_of(job: object) -> str:
    if not isinstance(job, dict):
        return ""
    value = job.get("conclusion")
    return value if isinstance(value, str) else ""


def _name_of(job: object) -> str:
    if not isinstance(job, dict):
        return "<unnamed job>"
    value = job.get("name")
    return value if isinstance(value, str) and value else "<unnamed job>"


def _url_of(job: object) -> str:
    if not isinstance(job, dict):
        return ""
    value = job.get("html_url")
    return value if isinstance(value, str) else ""


def summarize(jobs: Iterable[object]) -> Summary:
    """Classify a run's jobs. Pure: no I/O, no environment, no API calls.

    Unknown or absent conclusions land in ``other`` rather than being guessed
    into a bucket — a job still ``in_progress`` when this runs has a ``None``
    conclusion, and silently counting it as a pass or a failure would make the
    headline lie.
    """
    failed: list[ShardOutcome] = []
    cancelled: list[ShardOutcome] = []
    succeeded: list[ShardOutcome] = []
    other: list[ShardOutcome] = []

    for job in jobs:
        outcome = ShardOutcome(name=_name_of(job), conclusion=_conclusion_of(job), url=_url_of(job))
        if outcome.conclusion in REAL_FAILURE_CONCLUSIONS:
            failed.append(outcome)
        elif outcome.conclusion == CANCELLED:
            cancelled.append(outcome)
        elif outcome.conclusion == "success":
            succeeded.append(outcome)
        else:
            other.append(outcome)

    return Summary(failed=failed, cancelled=cancelled, succeeded=succeeded, other=other)


def render_markdown(summary: Summary) -> str:
    """Render the step-summary block a reader sees on the run page."""
    lines = ["## Module shard outcomes", "", summary.headline, ""]

    if summary.failed:
        lines.append("### Failed — start here")
        lines.append("")
        for outcome in summary.failed:
            suffix = f" ([log]({outcome.url}))" if outcome.url else ""
            label = "timed out" if outcome.conclusion == TIMED_OUT else "failed"
            lines.append(f"- **{outcome.name}** — {label}{suffix}")
        lines.append("")

    if summary.cancelled:
        lines.append(f"### Cancelled by fail-fast — {len(summary.cancelled)} job(s), not failures")
        lines.append("")
        lines.append(
            "These were stopped because another shard went red first. "
            "They are reported as `fail` by `gh pr checks` and in the PR check list; "
            "that is a rendering artefact of the cancellation, not a result."
        )
        lines.append("")
        lines.append("<details><summary>Show cancelled jobs</summary>")
        lines.append("")
        for outcome in summary.cancelled:
            lines.append(f"- {outcome.name}")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    if summary.other:
        lines.append(f"### Not concluded — {len(summary.other)} job(s)")
        lines.append("")
        for outcome in summary.other:
            lines.append(f"- {outcome.name} — `{outcome.conclusion or 'no conclusion yet'}`")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_annotation(summary: Summary) -> str:
    """One ``::notice::`` line, which GitHub surfaces at the top of the run."""
    return f"::notice title=Module shard outcomes::{summary.headline}"


def _load_jobs(raw: str) -> list[object]:
    """Accept the API envelope (``{"jobs": [...]}``) or a bare list."""
    payload = json.loads(raw)
    if isinstance(payload, dict):
        jobs = payload.get("jobs", [])
        return list(jobs) if isinstance(jobs, list) else []
    if isinstance(payload, list):
        return list(payload)
    return []


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--jobs-file",
        default="",
        help="Path to a GitHub list-jobs payload. Defaults to reading stdin.",
    )
    args = parser.parse_args(argv)

    raw = open(args.jobs_file, encoding="utf-8").read() if args.jobs_file else sys.stdin.read()  # noqa: SIM115
    if not raw.strip():
        # No payload is not a summariser failure: say so and leave the run alone.
        print("summarize-shard-outcomes: empty jobs payload; nothing to summarize", file=sys.stderr)
        return 0

    summary = summarize(_load_jobs(raw))
    markdown = render_markdown(summary)

    print(render_annotation(summary))
    print(markdown)

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as handle:
            handle.write(markdown)

    return 0


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())
