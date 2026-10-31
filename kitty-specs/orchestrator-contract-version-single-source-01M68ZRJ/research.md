# Research: Orchestrator contract version, one source of truth in tests

**Mission**: `orchestrator-contract-version-single-source-01M68ZRJ`
**Issue**: spec-kitty/spec-kitty#6578
**Date**: 2026-10-31

## Decision 1 — The durable half of #6578 is still open; the transient red is not

**Decision**: Scope this mission to removing the literal pin and adding a guard that detects its
return. Do not "fix" anything by bumping a number.

**Evidence**:

- `tests/orchestrator_api/test_origin_freshness_envelopes.py:29` reads
  `_CONTRACT_VERSION = "1.21.0"` (compared at lines 122 and 176).
- `src/specify_cli/orchestrator_api/envelope.py:176` reads `CONTRACT_VERSION = "1.21.0"`.
- The issue's reproduction now passes on `origin/main` at `dfe9efb0e8`:
  `uv run --frozen python -m pytest tests/orchestrator_api/test_origin_freshness_envelopes.py -q`
  → `13 passed in 152.44s`. The `1.14.0` vs `1.15.0` assertion failure was cleared by the
  hand-re-pin in commit `c678037c8b` ("bump the orchestrator-api contract to 1.21.0").
- `git log -L 29,29:tests/orchestrator_api/test_origin_freshness_envelopes.py` shows **eleven**
  hand re-pins of that one line: `9ed59d9c5c` (create, 1.11.0), `4c8253b9a9` (1.12.0),
  `3c2bdae4df` (1.13.0), `fc38aacf5c` (1.14.0), `c2ea5bd65d` (1.15.0 — the state #6578 reports),
  `ae0a1c2cbb` (1.16.0), `c0db3bbd0c` (1.17.0), `71e4eddba2` (1.18.0), `79724a4101` (1.19.0),
  `d45ec106e3` (1.20.0), `c678037c8b` (1.21.0).

**Rationale**: The issue body names both acceptable repairs — "read the exported
`CONTRACT_VERSION` (or the test constant needs bumping)" — and adds the requirement that matters:
"so a version bump cannot leave a stale pin behind". Re-pinning satisfies the first and not the
second; the eleven-commit log is the measurement that the second is the real cost.

## Decision 2 — The repository already established the shape: import the constant

**Decision**: Compare the emitted envelope against
`specify_cli.orchestrator_api.envelope.CONTRACT_VERSION` (imported), exactly as sibling modules do.

**Evidence** (sibling precedent, all on `origin/main`):

- `tests/agent/test_envelope_unit.py:11,34` — `from ... import CONTRACT_VERSION`, then
  `assert env["contract_version"] == CONTRACT_VERSION`.
- `tests/orchestrator_api/test_wp_lifecycle_structured_actor_6400.py:21,46,174` — same shape, twice.
- `tests/agent/test_orchestrator_commands_integration.py:25,382` and
  `tests/specify_cli/orchestrator_api/test_planning_client_journey.py:18,200` — same shape.

**Rationale**: `test_origin_freshness_envelopes.py` is the outlier, so the fix is convergence on an
existing canon (charter: single canonical authority; DIRECTIVE_044), not an invention.

## Decision 3 — The assertion stays; only its right-hand side changes

**Decision**: Keep `assert envelope["contract_version"] == <constant>` in both refusal tests.
Do not delete it.

**Rationale**: The assertion still proves that the refusal envelope carries the module's contract
version rather than a hand-built literal — the envelope is produced by a real `python -m specify_cli`
subprocess (`tests/terminus/conftest.py:1513-1541`), so a payload that omitted or hardcoded
`contract_version` would still fail. Deleting it would pass #6578 by removing the check, which the
brief's "never weaken a gate" rule and DIRECTIVE_041 both refuse.

## Decision 4 — Detection, not memory: a guard test in the canonical pin module

**Decision**: Add a fast, fixture-free guard to
`tests/specify_cli/orchestrator_api/test_contract_version.py` that scans `tests/**/*.py` for a quoted
semver on a line naming a contract version and fails, naming `path:line`, for every file except the
canonical pin module itself.

**Evidence** — a dry run of the exact scan on `origin/main` (`dfe9efb0e8`):

```text
tests/orchestrator_api/test_origin_freshness_envelopes.py:29: _CONTRACT_VERSION = "1.21.0"
tests/specify_cli/orchestrator_api/test_contract_version.py:22: ``CONTRACT_VERSION`` is currently ``"1.3.0"`` ...
tests/specify_cli/orchestrator_api/test_contract_version.py:86: assert envelope["contract_version"] == "1.21.0"
```

**Rationale**: the guard is RED on today's tree for the right reason (line 29) and GREEN after
Decision 2, which makes it a genuine red-first artifact rather than a post-hoc assertion. It is also
narrow enough to be non-vacuous:

- It matches a line that names a contract version *and* carries a quoted `X.Y.Z`. Legitimate
  references do not match: module-constant interpolation
  (`f'CONTRACT_VERSION = "{envelope_module.CONTRACT_VERSION}"'`, line 101), the unrelated
  `CONTRACT_VERSION_MISMATCH` error code, and a fixture payload that sets its own
  `"api_version": "3.0.0"` (`tests/specify_cli/orchestrator_api/test_fail_message_preserved.py:67`)
  are not comparisons against the emitted envelope version.
- Scanning `tests/**/*.py` only keeps `envelope.py`'s own constant and its changelog comment block
  (which must spell every historical version) out of scope.
- The allowlist is one real file whose purpose is the pin; if it is renamed the guard fails loudly
  instead of silently allowing everything.

## Decision 5 — The canonical pin's own prose is a drift surface; fix the one stale claim

**Decision**: In `test_contract_version.py`, the docstring currently says
"``CONTRACT_VERSION`` is currently ``"1.3.0"`` (envelope.py:28)" while the pin asserts `1.21.0`.
Rewrite that sentence to stop naming a *current* value it does not own, and make the "superseded"
narrative not read as a live claim.

**Rationale**: same defect class (a second place that spells a version), in the file that owns the
pin — a reader asking "what is the contract version?" gets a wrong answer from prose no test sees.
Keep the historical narrative: it is the record of why each bump happened, and the changelog comment
block in `envelope.py` already carries it.

## Open questions

- None blocking. The mission deliberately does **not** bump `CONTRACT_VERSION`, change `src/`, or
  touch the three test modules that already import the constant.

## Grounding commands (reproducible)

```bash
git log -L 29,29:tests/orchestrator_api/test_origin_freshness_envelopes.py
grep -rn 'CONTRACT_VERSION' tests/ --include=*.py
uv run --frozen python -m pytest tests/specify_cli/orchestrator_api/test_contract_version.py -q
```
