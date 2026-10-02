# Tracer — Tooling Friction

Mission: **runindex-feature-runs-port**

## TF-01 — Read-only research subagents can't persist findings
Two dispatched `Explore` (read-only) research agents could not write their reports to the
scratchpad (no Write tool / no shell redirect), so findings had to be relayed inline and
re-saved by the orchestrator. Minor: consider a general-purpose agent when a written
artifact is required.

## TF-02 — feature-runs.json filename literal is duplicated across layers
The bare filename lives in `runtime_bridge_io.py` (`_FEATURE_RUNS_FILE`) AND in
`specify_cli/state/contract.py:214` (path_pattern). The single-reader gate forced routing
the second through an import of the port's constant. (Resolved in-mission.)

<!-- append during implementation -->

## TF-03 — heavy conftest import dominates targeted runs
`tests/runtime`, `tests/next` targeted runs spend ~90s mostly on conftest/charter import
before the (fast) tests execute; the multiprocess two-process regression test compounds it
with forked children doing template discovery. Not a correctness issue, but it makes the
red/green loop slow. `-p no:cacheprovider -o addopts=""` needed to bypass the repo's default
pytest addopts (xdist/markers) for a quick single-file run.

## TF-04 — pre-existing mypy drift on the runtime package
`mypy -p runtime` reports 21 pre-existing errors (missing `mission_id`/`mission_slug` on
`spec_kitty_events.mission_next` payloads) in files this mission does not touch — a
cross-package contract drift, flagged in the PR as pre-existing.
