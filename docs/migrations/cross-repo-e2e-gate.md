---
title: Cross-Repo E2E Gate — Operator Migration Guide
description: 'Operator migration guide for the cross-repo E2E gate, active since the stability-and-hygiene-hardening mission (2026-04-26): how the gate works and what operators do.'
doc_status: active
updated: '2026-06-03'
---
> Migration note: This page documents a migration path or historical transition. It is not the current 3.2 happy path.

# Cross-Repo E2E Gate — Operator Migration Guide

**Status**: Active as of mission
`stability-and-hygiene-hardening-2026-04-01KQ4ARB` (2026-04-26).
**ADR**: [`docs/adr/3.x/2026-04-26-3-e2e-hard-gate.md`](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/3.x/2026-04-26-3-e2e-hard-gate.md)
**Skill**: [`src/doctrine/skills/spec-kitty-mission-review/SKILL.md`](https://github.com/spec-kitty/spec-kitty/blob/main/src/doctrine/skills/spec-kitty-mission-review/SKILL.md)

This guide tells operators how to run the cross-repo end-to-end gate
that `spec-kitty-mission-review` now enforces, and how to handle the
three exception cases the gate recognizes.

## What the gate is

After every Spec Kitty mission that touches cross-repo behavior
(events / tracker / SaaS / sync / merge / intake / runtime), the
mission-review skill runs three pass/fail checks before allowing
acceptance:

1. **Contract gate** — `pytest spec-kitty/tests/contract/ -v`. Asserts
   that the in-repo expected shape of events/tracker payloads still
   matches what the resolved PyPI versions produce.
2. **Architectural gate** — `pytest spec-kitty/tests/architectural/
   -v`. Asserts that import boundaries, public API surface, and
   layer rules still hold (no `spec_kitty_runtime` imports in
   production paths, public events/tracker imports only, etc.).
3. **Cross-repo e2e gate** — `pytest
   spec-kitty-end-to-end-testing/scenarios/ -v`. Drives real
   workflows against a real dev SaaS endpoint to verify cross-repo
   behavior end to end.

All three are hard gates. A FAIL on any of them blocks
`/spec-kitty.accept`.

The gate also reads
`kitty-specs/<slug>/issue-matrix.md` and rejects any mission whose
matrix has a row with an empty verdict or a verdict outside the
allowed set (`fixed`, `verified-already-fixed`,
`deferred-with-followup`).

## The three floor scenarios

The e2e repo at `spec-kitty-end-to-end-testing/scenarios/` ships at
least these scenarios. Future missions add more on top.

| File | FR coverage | What it proves |
|------|-------------|----------------|
| `dependent_wp_planning_lane.py` | FR-001, FR-005, FR-038 | A mission with sequential dependent WPs plus a planning-lane WP merges with no silent omission of approved commits. |
| `uninitialized_repo_fail_loud.py` | FR-032, FR-039 | `spec-kitty specify`/`plan`/`tasks` in a non-Spec-Kitty directory exit non-zero with `SPEC_KITTY_REPO_NOT_INITIALIZED` and write zero files into a sibling initialized repo. |
| `contract_drift_caught.py` | FR-041 | Staging a fake `spec-kitty-events` candidate that drops a required envelope field causes `pytest tests/contract/` to exit non-zero with a missing-field diagnostic. |

A fourth scenario, `saas_sync_enabled.py` (FR-040), was retired along with
the CLI-to-SaaS sync transport it exercised (commit `e59564b` in
`EXPERIMENTAL-spec-kitty-end-to-end-testing`) and is not part of the floor
— see spec-kitty#4949.

## How to run the gate

From the spec-kitty repo:

```bash
# 0. TeamSpace mission-state gate
spec-kitty doctor mission-state --audit --fail-on teamspace-blocker

# 1. Contract gate
pytest tests/contract/ -v

# 2. Architectural gate
pytest tests/architectural/ -v

# 3. Cross-repo e2e gate (separate repo)
cd ../spec-kitty-end-to-end-testing
pytest scenarios/ -v
```

If all three exit zero AND the issue matrix is fully populated, the
mission is gate-clean.

For launch-readiness checks that should run in GitHub without a full release
candidate, use the manual `TeamSpace Mission-State Readiness` workflow. It
executes the mission-state audit with the selected `--fail-on` threshold and
uploads the JSON report as a workflow artifact.

## Exception path: `mission-exception.md`

The e2e gate has one allowed exception path: the dev SaaS endpoint or
some other environment dependency is genuinely unreachable on the
reviewer's machine, and the failing scenario is not actually about a
code defect.

In that case the operator authors a `mission-exception.md` artifact
under `kitty-specs/<slug>/`:

```markdown
# Mission Exception: <slug>

**Operator**: <human name and email>
**Date**: <ISO date>
**Failing scenario**: `spec-kitty-end-to-end-testing/scenarios/<scenario_module>.py::<test_name>`
**Failing assertion**: `<the specific assertion or pytest.fail message that failed>`

## Why the failure is environmental, not a code defect

[Operator narrative. Example: "The e2e harness's `spec_kitty_repo`
fixture (`scenarios/conftest.py`) could not resolve a sibling
`spec-kitty` checkout on this machine — no `SPEC_KITTY_REPO` override,
no `SK_E2E_REARCH_ROOT`-derived sibling. This is an environment-setup
gap, not a code defect."]

## Reproduction command

```bash
pytest spec-kitty-end-to-end-testing/scenarios/<scenario_module>.py -v
```

## Follow-up

[Either a follow-up issue link, e.g. "Tracked as
spec-kitty/spec-kitty#NNN" OR a written commitment to retry once the
environment gap is resolved.]
```

The mission-review skill rejects an exception artifact that is
missing any of those fields.

## Common exception cases (non-exhaustive)

### Case A: e2e harness cannot resolve a sibling `spec-kitty` checkout

Every scenario shares the `spec_kitty_repo` fixture
(`scenarios/conftest.py`), which requires a resolvable sibling
`spec-kitty` checkout — via an explicit `SPEC_KITTY_REPO` override,
the `SK_E2E_REARCH_ROOT`-aware resolver, or a plain sibling-directory
layout. This is a required prerequisite, not an optional one: an
unresolvable checkout fails the fixture (`pytest.fail(...)`) rather
than skipping the scenario, so a missing prerequisite cannot silently
degrade into skipped (green) coverage. If the reviewer's machine
genuinely lacks a resolvable sibling checkout, the operator files
`mission-exception.md` naming the specific scenario and the exact
`pytest.fail` text, and follows the schema above.

### Case B: e2e harness has a hard dependency this machine cannot satisfy

Example: the harness needs Docker to spin up a tracker fixture and
the reviewer's machine has no Docker daemon. The same exception
schema applies. The exception artifact must name the missing
dependency and the command the operator ran.

### Case C: scenario blocker that is genuinely a follow-up issue

If a scenario's failure is a real code defect that the team has
deliberately deferred to a follow-up mission, the mission cannot be
exception-waived — the issue matrix's `deferred-with-followup` slot
is the right home, and the mission-review skill enforces that the
follow-up issue exists. An exception artifact is for *environmental
blockers*, not for deferred bugs.

## What is NOT allowed

- A blanket waiver across all e2e scenarios. Each failing scenario
  needs its own exception entry. The skill rejects an exception
  artifact whose `Failing scenario:` field names more than one
  scenario.
- A `SPEC_KITTY_E2E_OPTIONAL=1` env-var override. This was rejected
  as Alternative 4 in the ADR.
- An exception with no follow-up. Either a follow-up issue link or a
  written retry commitment is mandatory.

## Cross-references

- ADR (the gate rationale, full alternatives table):
  [`docs/adr/3.x/2026-04-26-3-e2e-hard-gate.md`](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/3.x/2026-04-26-3-e2e-hard-gate.md)
- Skill source (the enforcement code path):
  [`src/doctrine/skills/spec-kitty-mission-review/SKILL.md`](https://github.com/spec-kitty/spec-kitty/blob/main/src/doctrine/skills/spec-kitty-mission-review/SKILL.md)
- Mission spec (FR-038, FR-039, FR-040 *(retired, #4949)*, FR-041, NFR-006, C-010):
  [`kitty-specs/stability-and-hygiene-hardening-2026-04-01KQ4ARB/spec.md`](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-specs/stability-and-hygiene-hardening-2026-04-01KQ4ARB/spec.md)
- Issue matrix (the row-coverage gate input):
  [`kitty-specs/stability-and-hygiene-hardening-2026-04-01KQ4ARB/issue-matrix.md`](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-specs/stability-and-hygiene-hardening-2026-04-01KQ4ARB/issue-matrix.md)
- Research D1 (the matrix shape decision that this gate reads):
  [`kitty-specs/stability-and-hygiene-hardening-2026-04-01KQ4ARB/research.md`](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-specs/stability-and-hygiene-hardening-2026-04-01KQ4ARB/research.md)
