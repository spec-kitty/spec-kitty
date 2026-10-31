---
work_package_id: WP02
title: Correct the two entries, regenerate the index, add the changelog
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-003
- SC-001
- SC-002
- SC-004
planning_base_branch: issue-6439-contract-scenario-glossary-and-pack-level
merge_target_branch: issue-6439-contract-scenario-glossary-and-pack-level
branch_strategy: Planning artifacts for this mission were generated on issue-6439-contract-scenario-glossary-and-pack-level. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6439-contract-scenario-glossary-and-pack-level unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
- T011
phase: Phase 2 - Correct the wording
history:
- at: '2026-10-31T08:52:00+00:00'
  actor: system
  action: Prompt generated during tasks phase
agent_profile: implementer-ivan
authoritative_surface: docs/context/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/context/charter.md
- docs/context/governance.md
- docs/development/docs-retrieval-index.yaml
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Correct the two entries, regenerate the index, add the changelog

## ⚡ Do This First: Load Agent Profile

Load `implementer-ivan` with `spec-kitty agent profile show implementer-ivan` and
`spec-kitty charter context --action implement --include agent-profile:implementer-ivan`
before reading anything else. Naming the profile is not enough; apply its rules.

## Objective

Make the glossary say what the issue asks it to say:

1. `docs/context/governance.md` **Pack Level** — a Charter Pack declares a **level**,
   by `pack_level` in its `pack.yaml`; the entry says "level token", never "tier token",
   and still names `kernel.pack_tiers` as the one authority and keeps the #6403
   `PACK_LEVEL_MISSING` wording.
2. `docs/context/charter.md` **Charter Pack** — the same claim restated there ("the
   tier token") becomes "the level token".
3. `docs/context/charter.md` gains a **Contract Scenario** entry between **Charter Pack**
   and **Activation preset**, with the definition, home, related terms and
   `Do NOT use when` guard fixed in `../data-model.md`.
4. The docs index is regenerated for the new heading and one `[Unreleased]` changelog
   entry records the change for #6439.

WP01's guard module must already exist and must have been observed red on the pre-WP02
tree. After this WP it goes green.

## Branch Strategy

Planning/base branch `issue-6439-contract-scenario-glossary-and-pack-level`; final
merge target the same branch. The mission is `single_branch`: work in the repository
root checkout, no lane worktree. `lanes.json` names the one repo-root lane.

## Context

- Authoring rules: `docs/context/glossary-conventions.md` ("Term Entry Schema" —
  `Definition`, `Context`, `Status`, `Applicable to` required; `Do NOT use when`,
  `Related terms` optional) and styleguide `kitty-glossary-writing` (one concept per
  definition, functional over compositional, no buzzword soup, no "user" where the
  Human-in-Charge (HiC) holds decision authority).
- Why "tier" is wrong: `docs/adr/4.x/2026-10-11-2-a-pack-declares-its-level-in-pack-yaml.md`,
  Rejected — *"`pack_tier` and `layer`. "Tier" is overloaded (model tiers, tiered
  rigour)."*
- The entry text and its invariants: `../data-model.md` (Entity: Contract Scenario,
  Entity: Pack Level).
- Reproduction evidence: `../research.md` D1 (still reproduces on `35318ef51c`) and
  D3 (the ADR basis).

## Wording to apply — Pack Level (T006)

The current opening, verbatim from `docs/context/governance.md:79`:

> The tier a Charter Pack occupies, declared by the `pack_level` field in the pack's
> `pack.yaml` — one of `built-in`, `org` or `project`, in ascending precedence …

becomes

> The level a Charter Pack occupies, declared by the `pack_level` field in the pack's
> `pack.yaml` — one of `built-in`, `org` or `project`, in ascending precedence …

and later in the same cell "the tier token and the provenance/layer value share a
single spelling, `built-in`" becomes "the level token and the provenance/layer value
share a single spelling, `built-in`". **Every other clause stays byte-identical**,
including `kernel.pack_tiers`, `PACK_LEVEL_MISMATCH`, `PACK_LEVEL_MISSING` and the
deprecation-window sentence. Do not reformat the table row or re-wrap the cell.

## Wording to apply — Charter Pack (T007)

`docs/context/charter.md:54` carries "the tier token and the provenance/layer value now
share a single spelling, `built-in`" → "the level token and the provenance/layer value
now share a single spelling, `built-in`". Nothing else in that cell changes.

## Wording to apply — Contract Scenario (T008)

Insert between the Charter Pack entry's closing `---` and `### Activation preset`:

```markdown
### Contract Scenario

| | |
|---|---|
| **Definition** | A Gherkin scenario that is the behavior half of the charter contract: it names pack files, calls one operation of `contracts/charter/openapi.yaml` and states the answer. Scenarios tagged `@contract` run in `verifyAll`; `@provisional` marks behavior the conformance corpus has yet to decide. |
| **Context** | Governance |
| **Status** | candidate |
| **Applicable to** | `4.x` |
| **Do NOT use when** | You mean the acceptance scenarios under `tests/scenarios/charter/`, the conformance corpus as a whole, or BDD the practice. Do not write "BDD scenarios". |
| **Related terms** | [Charter Pack](#charter-pack); the acceptance scenarios and the conformance corpus are defined in spec-kitty-charter, not in this glossary yet |
```

Constraints on that entry: one table cell per row (no wrapped paragraphs); `Status`
is `candidate` because the styleguide says new terms enter as candidate and the HiC
promotes; `Applicable to` matches the Charter Pack entry (`4.x`); no issue number and no
`src/` path in the prose (the downstream repository imports this page verbatim).
**Do not create the `Acceptance Scenario` or `Conformance Corpus` entries** — that is a
second scope; the `Related terms` row says where they live instead of dangling a link.

## Subtasks

### T006 — Pack Level in `docs/context/governance.md`
Apply the two deletions above. Leave the rest of the cell byte-identical.

### T007 — Charter Pack in `docs/context/charter.md`
Apply the one deletion above.

### T008 — The Contract Scenario entry
Insert the entry above, in place, with its `---` separation matching the page's style.

### T009 — Regenerate the docs index, check the inventory

```bash
uv run --frozen python -m scripts.docs.docs_index --write
uv run --frozen python scripts/docs/freshen_adr_inventory.py --check --all
```

Only `docs/development/docs-retrieval-index.yaml` should change (the new `###` heading);
no page is added or removed, so the page inventory must stay a no-op. If `--write`
rewrites unrelated rows, stop and inspect the diff instead of committing churn; this
clone may be running beside other agents, and the brief warns against a churny full
regeneration. Record what changed in the review handoff if it is more than the new
heading's rows.

### T010 — Changelog

One `### Added` entry under `## [Unreleased] - 4.0.0rc8` in
`docs/changelog/CHANGELOG.md`, impact-first, with `(#6439)`, before/after, under 1,200
characters. Shape:

> **The core glossary now defines "Contract Scenario" and calls a pack's level a level,
> not a tier** (#6439). **Before:** `docs/context/charter.md` had no entry for the
> Gherkin behavior half of the charter contract, and the Pack Level and Charter Pack
> entries called a pack's declared level a "tier" (and a "tier token"). **After:** the
> Contract Scenario entry states what a scenario names, calls and asserts, which tags
> run in `verifyAll`, and what `@provisional` marks, with a `Do NOT use when` guard
> against the acceptance scenarios and "BDD scenarios"; both pack entries say **level**
> and "level token". `kernel.pack_tiers` keeps its name. Downstream importers of this
> glossary pick both up on their next re-import.

Verify with `make docs-lint` style rules: `check_changelog_style` must accept it.

### T011 — Run the gates

```bash
uv run --frozen pytest tests/docs/test_context_glossary_contract_scenario_and_pack_level.py -q   # now green
uv run --frozen pytest tests/docs/test_committed_docs_index_fresh.py tests/docs/test_freshen_adr_inventory.py -q
uv run --frozen python -m scripts.docs.check_docs_freshness --ci                                  # errors=0
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
make docs-lint
```

Record each command's outcome verbatim for the review handoff and the PR body. A red
you cannot attribute to this diff is cited in the PR's `## Deferred` with the issue
number; never skip, xfail, allowlist or baseline it.

## Half-by-half proof (required)

Revert each prose edit in turn and confirm a **distinct** assertion reds:

- drop only the Pack Level wording → the governance "tier" assertion reds;
- drop only the Charter Pack wording → the charter "tier" assertion reds;
- drop only the new entry → the Contract Scenario presence/rows assertions red.

Record the three results. A guard that stays green after reverting one half is only
testing the other half and must be fixed in WP01 before this WP is approved.

## Definition of Done

- Contract Scenario present beside Charter Pack with all six rows, `Status: candidate`,
  `Applicable to` `4.x`, a guard that names the alternatives, and no dangling link.
- No prose in the Pack Level or Charter Pack entry calls a pack's level a "tier";
  `kernel.pack_tiers` and every #6403 clause are intact.
- `docs/development/docs-retrieval-index.yaml` fresh; page inventory unchanged.
- One changelog entry, impact-first, with `(#6439)`, under 1,200 characters.
- WP01's module green; all T011 commands green (or a red cited as pre-existing).
- No file outside `owned_files` is modified; Organization Tier, Three-layer DRG, the
  seed and the built-in glossary pack are untouched.

## Reviewer guidance

Diff the two corrected entries against `origin/main` clause by clause and confirm only
the "tier"→"level" words moved. Then read the new entry as a newcomer: can you say what
a contract scenario does without a follow-up question? Check the guard actually sends
you somewhere. Finally, confirm the changelog's before/after matches the diff and that
nothing was allowlisted or skipped to get green.
