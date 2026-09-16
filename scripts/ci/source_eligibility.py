"""Decide the stale-artefact fallback source for ci-aggregate, with provenance.

Mission ci-aggregate-source-eligibility WP01 (FR-001..FR-006, FR-008;
NFR-003/4). Replaces the untested, provenance-blind inline-shell selection in
``.github/workflows/ci-aggregate.yml``'s ``last-success`` step.

The decision is a *pure* function of its arguments (no I/O, no ``subprocess``,
no clock) so it is unit-testable red-first. The ``gh run list`` call that
gathers candidate runs stays in the workflow; ``main()`` is the thin edge that
parses that injected JSON and emits exactly two ``key=value`` lines
(``run-id`` + ``eligibility``) to ``$GITHUB_OUTPUT`` — never completeness data
(that belongs to ``reconcile_shards.py``). A legitimate absence of an eligible
source is a *named* ``No*`` decision that exits 0; only malformed input raises,
so ``reconcile`` remains the fail-closed terminus (NFR-004).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import assert_never

_SUCCESS = "success"

# Eligibility slugs (INV-C: every decision maps to exactly one named slug).
ELIGIBLE_SOURCE = "eligible-source"
NO_SUCCESS_SOURCE = "no-success-source"
PR_HEAD_TRIGGER = "pr-head-trigger"
FAILED_TRIGGER = "failed-trigger"
DISPATCH_NO_FALLBACK = "dispatch-no-fallback"


@dataclass(frozen=True)
class TriggerMeta:
    """The triggering ``workflow_run``'s provenance (``github.event.workflow_run``)."""

    event: str
    head_branch: str
    conclusion: str

    @classmethod
    def from_payload(cls, data: object) -> TriggerMeta:
        if not isinstance(data, dict):
            raise ValueError("trigger payload must be a JSON object")
        event, head_branch, conclusion = _require_str(data, "event", "head_branch", "conclusion")
        return cls(event=event, head_branch=head_branch, conclusion=conclusion)


@dataclass(frozen=True)
class CandidateRun:
    """One entry from ``gh run list --json databaseId,conclusion,headBranch,event``."""

    database_id: int
    conclusion: str
    head_branch: str
    event: str

    @classmethod
    def from_payload(cls, data: object) -> CandidateRun:
        if not isinstance(data, dict):
            raise ValueError("candidate run must be a JSON object")
        raw_id = data.get("databaseId")
        # bool is an int subclass — a JSON ``true`` is not a database id.
        if not isinstance(raw_id, int) or isinstance(raw_id, bool):
            raise ValueError("candidate databaseId must be an integer")
        conclusion, head_branch = _require_str(data, "conclusion", "headBranch")
        return cls(
            database_id=raw_id,
            conclusion=conclusion,
            head_branch=head_branch,
            event=str(data.get("event", "")),
        )


# --------------------------------------------------------------------------- #
# SourceDecision — a tagged union; exactly one variant per call (data-model).  #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class EligibleSource:
    """Eligible provenance + a success run on ``{source, default}``."""

    run_id: int


@dataclass(frozen=True)
class NoEligibleSource:
    """Eligible provenance but no success candidate on ``{source, default}``."""

    reason: str


@dataclass(frozen=True)
class NotAMainSource:
    """``event=pull_request`` or ``conclusion=failure`` — never a main run-id."""

    reason: str
    slug: str


@dataclass(frozen=True)
class NoFallback:
    """``event=workflow_dispatch`` — exact-source-only, no ledger query."""


SourceDecision = EligibleSource | NoEligibleSource | NotAMainSource | NoFallback


def resolve_source(trigger: TriggerMeta, candidates: list[CandidateRun], default_branch: str) -> SourceDecision:
    """Decide the fallback source from provenance + a success/branch-scoped ledger.

    Pure and deterministic. Order (D-04):

    1. ``workflow_dispatch`` → :class:`NoFallback` (no ledger consulted, INV-F).
    2. ``event=pull_request`` → :class:`NotAMainSource` (``pr-head-trigger``).
    3. ``conclusion=failure`` → :class:`NotAMainSource` (``failed-trigger``).
    4. else the most-recent ``success`` candidate whose ``head_branch`` equals
       the source branch, else the default branch → :class:`EligibleSource`
       (INV-A success-only, INV-B branch-scope).
    5. none → :class:`NoEligibleSource`.
    """
    if trigger.event == "workflow_dispatch":
        return NoFallback()
    if trigger.event == "pull_request":
        return NotAMainSource(reason="triggering run is a pull-request head, not a main lineage", slug=PR_HEAD_TRIGGER)
    if trigger.conclusion == "failure":
        return NotAMainSource(reason="triggering run concluded in failure", slug=FAILED_TRIGGER)

    # Branch-scope (INV-B): only the source and default branches are eligible,
    # source preferred. Candidates arrive most-recent-first (gh run list order),
    # so the first success on each branch is the most recent (INV-A).
    for branch in _eligible_branches(trigger.head_branch, default_branch):
        for run in candidates:
            if run.conclusion == _SUCCESS and run.head_branch == branch:
                return EligibleSource(run_id=run.database_id)
    return NoEligibleSource(reason="no successful CI Modules run on the source or default branch")


def render_outputs(decision: SourceDecision) -> tuple[str, str]:
    """Map a decision to its ``(run-id, eligibility)`` outputs.

    ``run-id`` is empty for every non-eligible variant; the slug is always
    non-empty (INV-C) so an empty run-id is never silent.
    """
    match decision:
        case EligibleSource(run_id=run_id):
            return str(run_id), ELIGIBLE_SOURCE
        case NoEligibleSource():
            return "", NO_SUCCESS_SOURCE
        case NotAMainSource(slug=slug):
            return "", slug
        case NoFallback():
            return "", DISPATCH_NO_FALLBACK
        case _:  # pragma: no cover - exhaustiveness guard for mypy
            assert_never(decision)


def parse_candidates(data: object) -> list[CandidateRun]:
    """Parse the ``gh run list --json`` array into :class:`CandidateRun`\\ s."""
    if not isinstance(data, list):
        raise ValueError("candidate inventory must be a JSON array")
    return [CandidateRun.from_payload(entry) for entry in data]


def _eligible_branches(source_branch: str, default_branch: str) -> list[str]:
    branches = [source_branch]
    if default_branch != source_branch:
        branches.append(default_branch)
    return branches


def _require_str(data: dict[str, object], *keys: str) -> tuple[str, ...]:
    values: list[str] = []
    for key in keys:
        value = data.get(key)
        if not isinstance(value, str):
            raise ValueError(f"field {key!r} must be a string")
        values.append(value)
    return tuple(values)


def _parse_trigger_env(raw: str) -> TriggerMeta | None:
    """Parse ``TRIGGER_JSON``; ``null``/empty means the dispatch (no-trigger) path."""
    stripped = raw.strip()
    if not stripped or stripped == "null":
        return None
    payload = json.loads(stripped)
    if payload is None:
        return None
    return TriggerMeta.from_payload(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Decide the ci-aggregate fallback source with provenance.")
    parser.add_argument(
        "--candidates",
        type=Path,
        default=None,
        help="JSON file of `gh run list --json ...` output; default: stdin.",
    )
    parser.add_argument(
        "--default-branch",
        default=os.environ.get("DEFAULT_BRANCH", "main"),
        help="Repository default branch (fallback-source scope).",
    )
    args = parser.parse_args(argv)

    candidates_text = args.candidates.read_text(encoding="utf-8") if args.candidates else sys.stdin.read()
    try:
        trigger = _parse_trigger_env(os.environ.get("TRIGGER_JSON", ""))
        if trigger is None:
            decision: SourceDecision = NoFallback()
        else:
            candidates = parse_candidates(json.loads(candidates_text))
            decision = resolve_source(trigger, candidates, args.default_branch)
    except ValueError as error:
        # INV-E / NFR-004: ONLY malformed input is fatal; reconcile stays the
        # fail-closed terminus for a legitimate absence of source.
        print(f"::error::source_eligibility: malformed input -- {error}", file=sys.stderr)
        return 1

    run_id_output, eligibility = render_outputs(decision)
    print(f"run-id={run_id_output}")
    print(f"eligibility={eligibility}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
