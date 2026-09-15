"""Timed-out-aware terminal router-gate classification (#4208).

The ``router-gate`` job in ``.github/workflows/ci-router.yml`` is the terminal
aggregator: it must fail the run when any dependency did not succeed, while
letting a router-scoped *skip* (a shard not selected for this diff) pass.

Historically the step read only the ``needs`` context and folded ``cancelled``
into the blocking set alongside ``failure``. But a ``timeout-minutes`` kill
collapses to ``cancelled`` in the ``needs`` context (which cannot carry the
``timed_out`` conclusion), so a genuine timeout was indistinguishable from an
external cancel in the reported verdict. The distinguishing signal is the
Actions *jobs API* ``conclusion`` (API-only) -- the same conclusion vocabulary
the fleet reporter consumes (``scripts/ci/fleet_verdict.py``).

:func:`classify` takes the jobs-API conclusions and returns a
:class:`GateDecision`. The blocking pass/fail decision is **byte-identical** to
the historical policy -- ``failure`` and ``cancelled`` both block, ``success``
and a router-scoped ``skipped`` both pass -- while ``timed_out`` now blocks under
its own distinct label and any unfamiliar or incomplete conclusion fails closed.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass

__all__ = [
    "NON_BLOCKING_CONCLUSIONS",
    "ROUTER_GATE_JOB_NAME",
    "GateDecision",
    "classify",
    "main",
]

# The only jobs-API conclusions that do NOT block the terminal gate: a clean
# success and a router-scoped skip (a shard not selected for this diff). Every
# other conclusion blocks -- the fleet reporter's failure vocabulary
# (``failure``/``timed_out``/``startup_failure``/``action_required``, see
# scripts/ci/fleet_verdict.py:89), an external ``cancelled``, and any
# unrecognised or incomplete conclusion -- so the gate fails closed. This is
# byte-identical to the historical needs-context policy for the conclusions that
# context could report ({failure, cancelled} block; {success, skipped} pass) and
# additionally distinguishes a real ``timed_out`` from a ``cancelled``.
NON_BLOCKING_CONCLUSIONS: frozenset[str] = frozenset({"success", "skipped"})

# The terminal job's own display name (``name:`` in ci-router.yml). It is
# excluded from its own verdict: while it runs its jobs-API conclusion is null.
ROUTER_GATE_JOB_NAME = "router gate"

# The conclusion recorded for a job the jobs API reports without one (still in
# progress or missing). It is not in NON_BLOCKING_CONCLUSIONS, so it blocks.
_INCOMPLETE_CONCLUSION = "incomplete"


@dataclass(frozen=True)
class GateDecision:
    """The terminal gate's verdict over a set of dependency conclusions."""

    blocking: Mapping[str, str]
    """Every dependency that blocks the gate, mapped to its jobs-API conclusion
    (``timed_out`` distinct from ``cancelled`` distinct from ``failure``)."""

    @property
    def blocks(self) -> bool:
        """Whether the gate fails: at least one dependency did not pass."""
        return bool(self.blocking)

    @property
    def timed_out(self) -> Mapping[str, str]:
        """The blocking dependencies killed by a timeout, reported distinctly."""
        return {job: conclusion for job, conclusion in self.blocking.items() if conclusion == "timed_out"}


def classify(conclusions: Mapping[str, str]) -> GateDecision:
    """Return the terminal gate verdict for the given jobs-API conclusions.

    A dependency blocks unless its conclusion is in
    :data:`NON_BLOCKING_CONCLUSIONS`. The returned :class:`GateDecision`
    preserves each blocking dependency's raw conclusion, so ``timed_out`` is
    reported distinctly from ``cancelled`` (contract C-gate-1) while the
    pass/fail decision stays byte-identical to the historical policy
    (contract C-gate-2/3/4).
    """
    # This evaluates the WHOLE run's job set (every jobs-API row bar this gate's
    # own). That equals "classify the gate's `needs:`" ONLY while every job is a
    # gate dependency and none is `continue-on-error` (paula INFO-1 / alphonso
    # LOW); the `needs:`==all-jobs invariant is pinned by
    # test_dual_mode_contract.test_router_gate_step_wiring_and_needs_invariant_are_pinned.
    blocking = {job: conclusion for job, conclusion in conclusions.items() if conclusion not in NON_BLOCKING_CONCLUSIONS}
    return GateDecision(blocking=blocking)


def _parse_conclusions(raw: str) -> dict[str, str]:
    """Parse ``name<TAB>conclusion`` rows (the jobs-API output) into a mapping.

    The terminal gate's own job is dropped (its conclusion is null while it
    runs); a row without a conclusion is recorded as incomplete, which blocks.
    """
    conclusions: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        name, _, conclusion = line.partition("\t")
        name = name.strip()
        if not name or name == ROUTER_GATE_JOB_NAME:
            continue
        conclusions[name] = conclusion.strip() or _INCOMPLETE_CONCLUSION
    return conclusions


def _format(pairs: Mapping[str, str]) -> str:
    """Render a job -> conclusion mapping as a stable, sorted string."""
    return ", ".join(f"{job}={conclusion}" for job, conclusion in sorted(pairs.items()))


def main() -> None:
    """CLI entry point: read jobs-API rows from stdin, exit non-zero if blocked.

    The ``router-gate`` workflow step pipes the current run's jobs-API rows
    (``name<TAB>conclusion``) to stdin. A timed-out dependency is reported
    distinctly before the blocking verdict is raised.
    """
    decision = classify(_parse_conclusions(sys.stdin.read()))
    if decision.timed_out:
        print(f"timed-out job(s) (blocking, distinct from cancelled): {_format(decision.timed_out)}")
    if decision.blocks:
        raise SystemExit(f"blocking job(s) did not succeed: {_format(decision.blocking)}")
    print(f"router-gate OK (mode={os.environ.get('MODE', 'pr')})")


if __name__ == "__main__":
    main()
