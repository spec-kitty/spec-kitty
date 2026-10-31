---
work_package_id: WP01
title: Red-first guard for both glossary claims
dependencies: []
requirement_refs:
- FR-004
- NFR-003
- C-002
- SC-003
planning_base_branch: issue-6439-contract-scenario-glossary-and-pack-level
merge_target_branch: issue-6439-contract-scenario-glossary-and-pack-level
branch_strategy: Planning artifacts for this mission were generated on issue-6439-contract-scenario-glossary-and-pack-level. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6439-contract-scenario-glossary-and-pack-level unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Guard (red-first)
history:
- at: '2026-10-31T08:52:00+00:00'
  actor: system
  action: Prompt generated during tasks phase
agent_profile: python-pedro
authoritative_surface: tests/docs/
create_intent:
- tests/docs/test_context_glossary_contract_scenario_and_pack_level.py
execution_mode: code_change
model: ''
owned_files:
- tests/docs/test_context_glossary_contract_scenario_and_pack_level.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Red-first guard for both glossary claims

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` with `spec-kitty agent profile show python-pedro` and
`spec-kitty charter context --action implement --include agent-profile:python-pedro`
before reading anything else. Naming the profile is not enough; apply its rules.

## Objective

Author one standing pytest module, `tests/docs/test_context_glossary_contract_scenario_and_pack_level.py`,
that pins the two claims issue #6439 asks for:

1. `docs/context/governance.md`'s **Pack Level** entry, and `docs/context/charter.md`'s
   **Charter Pack** entry, never call a pack's level a "tier" in prose — while still
   naming `kernel.pack_tiers` as the one authority for the three level names.
2. `docs/context/charter.md` defines **Contract Scenario** with its four required rows
   plus a `Do NOT use when` guard and a `Related terms` row, and the guard steers a
   reader away from "BDD scenarios".

The module must be **red on the current tree** (WP02 has not landed): the entry is
missing and "tier" is present in both entries. It goes green when WP02 lands. Do not
edit the glossary pages yourself — that is WP02, and a docs-scoped test is the only
thing this WP owns.

## Branch Strategy

Planning/base branch `issue-6439-contract-scenario-glossary-and-pack-level`; final
merge target the same branch. The mission is `single_branch`: work in the repository
root checkout, no lane worktree. `lanes.json` names the one repo-root lane.

## Context

- Entry schema: `docs/context/glossary-conventions.md` ("Term Entry Schema" — four
  required rows, optional `Do NOT use when` / `Related terms`).
- The wording authority for "level, not tier":
  `docs/adr/4.x/2026-10-11-2-a-pack-declares-its-level-in-pack-yaml.md`, **Rejected**:
  *"`pack_tier` and `layer`. "Tier" is overloaded (model tiers, tiered rigour)."*
- The term and its guard text: `../data-model.md`, "Entity: Contract Scenario".
  `../research.md` D1–D7 carries the reproduction evidence and the probe design (P2).
- Precedent for pinning glossary prose in a test:
  `tests/architectural/test_glossary_authority_parity.py:268` asserts the
  `Do NOT use when` row on the `charter` entry. Read it for shape, then write this
  module in `tests/docs/` with **no** new pytest marker (a docs-scoped test belongs to
  the docs shard, which already runs on a docs-only diff).

## Red-first check (ATDD)

T004 is mandatory and must run **before** WP02 changes any prose. Capture the exact
failure ids/lines — they go in the PR body's `## Tests run` section as the red-first
proof. Expected red set on this tree (four assertion failures):

- `### Contract Scenario` is absent from `docs/context/charter.md`
- the Contract Scenario required rows / guard are therefore absent
- "tier" appears in the Pack Level entry's prose
- "tier" appears in the Charter Pack entry's prose

## Subtasks

### T001 — Slicer, fixtures and positive controls

File: `tests/docs/test_context_glossary_contract_scenario_and_pack_level.py`.

- Resolve the repo root the way the neighbouring `tests/docs` modules do (walk up to
  the `.kittify/` marker; do not hard-code a machine path).
- One module-scoped fixture reading each page once as text.
- `_entry_body(text: str, heading: str) -> str`: slice from the `### <heading>` line to
  the next `---` rule or the next `### ` heading, whichever comes first.
- **Positive controls, on the same fixture:** the Pack Level body is non-empty and
  contains `kernel.pack_tiers`; the slicer returns non-empty bodies for at least two
  known entries on each page (for example `Charter Pack` and `Activation preset`, and
  `Precedence Rule` and `Pack Level`). An absence probe with no positive control can
  pass by reading nothing — this WP must not ship that shape.

### T002 — The pack-level wording probes

- `_prose(body)` strips inline code spans (`` `…` ``) before probing, so
  `kernel.pack_tiers` cannot red the guard.
- For both `Pack Level` (governance.md) and `Charter Pack` (charter.md):
  `assert not re.search(r"(?i)\btiers?\b", _prose(body))`, with a failure message that
  names the file, the entry and the matched word plus its line.
- Keep the positive control: the **raw** Pack Level body still contains
  `kernel.pack_tiers`.
- Do **not** assert anything about `Organization Tier`, `Three-layer DRG` or any other
  entry — those senses of the word are out of scope (C-003). Add a comment saying so,
  so a future maintainer does not widen the guard.

### T003 — The Contract Scenario probes

- The `### Contract Scenario` heading exists in `docs/context/charter.md`.
- Its body carries each required row label (`Definition`, `Context`, `Status`,
  `Applicable to`) and each optional row this mission adds (`Do NOT use when`,
  `Related terms`).
- The definition cell names the Gherkin half of the charter contract, the
  `contracts/charter/openapi.yaml` operation call, and states the `@contract` /
  `@provisional` / `verifyAll` facts.
- The guard row mentions "BDD" and the acceptance scenarios or the conformance corpus,
  i.e. it steers a reader somewhere, not merely forbids a word.
- Assert entry placement: Contract Scenario sits between `Charter Pack` and
  `Activation preset`, which is what "beside Charter Pack" means concretely.

### T004 — Observe red and record it

```bash
uv run --frozen pytest tests/docs/test_context_glossary_contract_scenario_and_pack_level.py -q
```

Must fail with the four expected assertions listed above. Save the summary lines; if
the module passes on this tree, the guard is vacuous — fix the guard, do not proceed.

### T005 — Lint and format

```bash
uv run --frozen ruff check tests/docs/test_context_glossary_contract_scenario_and_pack_level.py
uv run --frozen ruff format --check tests/docs/test_context_glossary_contract_scenario_and_pack_level.py
uv run --frozen mypy tests/docs/test_context_glossary_contract_scenario_and_pack_level.py
```

Type-annotate the helpers (`-> str`, `pytest.fixture` return types) so `mypy` stays
clean; no `# type: ignore`, no blanket `# noqa`.

## Definition of Done

- The module exists, is fully typed, and carries no new marker.
- It is red on this tree for the four expected reasons (T004 output recorded verbatim).
- It contains a positive control on the same fixture as every absence probe, and a
  comment pinning the out-of-scope "tier" senses.
- `ruff check`, `ruff format --check` and `mypy` are clean on the new file.
- No file outside `tests/docs/` is modified.

## Reviewer guidance

Read the module and ask: could this pass while the glossary says nothing? Every
absence assertion must sit next to a presence assertion built from the same fixture.
Then check the probe strips code spans: `kernel.pack_tiers` must survive, and no
allowlist may be introduced. Confirm the red set on the pre-fix tree is exactly the
four assertions and that none of them is a typo in the test.
