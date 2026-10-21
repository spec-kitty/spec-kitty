---
work_package_id: WP01
title: Core ADR and glossary (activation ledger)
dependencies: []
requirement_refs:
- C-009
- C-006
planning_base_branch: core-align-3-persistent-deactivation
merge_target_branch: core-align-3-persistent-deactivation
branch_strategy: Planning artifacts for this mission were generated on core-align-3-persistent-deactivation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into core-align-3-persistent-deactivation unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 0 - Decision record
history:
- at: '2026-10-19T12:17:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent:
- docs/adr/4.x/2026-10-19-1-activation-ledger-persists-deactivation.md
execution_mode: planning_artifact
model: ''
owned_files:
- docs/adr/4.x/2026-10-19-1-activation-ledger-persists-deactivation.md
- docs/adr/3.x/2026-07-18-1-charter-yaml-authoring-authority-and-extractor-retirement.md
- docs/adr/4.x/2026-10-03-1-charter-read-write-service-strangler.md
- docs/adr/4.x/2026-10-06-2-charter-offering-active-charter-and-activation-presets.md
- docs/adr/4.x/index.md
- docs/development/page-inventory.yaml
- docs/development/docs-retrieval-index.yaml
- docs/context/charter.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Core ADR and glossary (activation ledger)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro` (`packs/built-in/agent_profiles/python-pedro.agent.yaml`)
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

This WP is documentation only. Pedro still owns it (operator routing: one profile for the whole
mission), so apply his discipline to precision and canonical sources; consult
`architect-alphonso` guidance only for ADR structure if you need it.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission persistent-deactivation-ledger-01M59YAA`).
- Address every feedback item before the work is complete; record each fix with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objective

Record the activation-ledger decision as an Accepted 4.x core ADR **before any code lands**
(C-009), amend the three ADRs it touches, register it in the ADR inventory, and add the four
glossary terms the rest of the mission will use.

## Context

- Spec: `kitty-specs/persistent-deactivation-ledger-01M59YAA/spec.md` (operator rulings section is binding).
- Plan: `plan.md` IC-11; research.md D-01..D-23 hold the decisions to record; data-model.md §1–§10 hold the shapes.
- External source: spec-kitty-charter ADR-0013 ("Deactivation persists in one activation ledger, and nothing silently reinstalls it"). Do **not** change anything in the spec-kitty-charter repository (C-006); cite it only.
- Every later WP references this ADR by path. Keep the filename exactly
  `docs/adr/4.x/2026-10-19-1-activation-ledger-persists-deactivation.md`.
- Terminology canon: "Mission", never "feature"; the new term "Activation ledger" must be guarded
  against confusion with the **Migration Ledger** (ADR 2026-10-17-1), the decision ledger and the
  status event log.

## Branch Strategy

- **Strategy**: single_branch topology; WPs run strictly in sequence in the repository root checkout on `core-align-3-persistent-deactivation`.
- **Planning base branch**: `core-align-3-persistent-deactivation`
- **Merge target branch**: `core-align-3-persistent-deactivation` (delivered by PR to `main`; the operator merges)

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

Implementation command:

```bash
spec-kitty agent action implement WP01 --agent claude --mission persistent-deactivation-ledger-01M59YAA
```

## ATDD note (docs-only WP)

This WP owns no executable code and no FR. The red-first rule is honoured by T001's first step:
run the docs checks listed under *Validation* **before** writing, record that the new ADR path does
not resolve in the inventory (`freshen_adr_inventory` reports it missing) and that
`docs/context/charter.md` has no `#activation-ledger` anchor, then make them pass.

## Subtasks

### Subtask T001: Write the core ADR `2026-10-19-1`

**Purpose**: the binding decision record every code WP cites (C-009).

**Steps**:
1. Read the template section at the bottom of `docs/adr/4.x/index.md` and two recent 4.x ADRs
   (for example `2026-10-17-1-explicit-migration-ledger.md`, `2026-10-16-1-extract-charter-offering-first-activation-rework-post-ga.md`) for front matter and tone. Use the template, not an older ADR, as structure.
2. Create the ADR with status **Accepted**, date 2026-10-19, and these sections:
   - **Context**: deactivation today only removes an id from `activated_<kind>`, raises
     `NoActivationRestrictionsError` when the list is absent, and is undone by cascade, the rc6
     cutover reset, the interview and promotion writers; activation state has several homes.
   - **Decision 1 — One ledger**: `.kittify/charter/activation.yaml` (git-tracked) holds
     `activated_kinds`, `mission_type_activations`, `activated_<plural>` (three-state) and
     `deactivated_<plural>` (omitted when empty). Keys derive from `ArtifactKind.activatable`.
   - **Decision 2 — Algebra**: `E(k) = base(k) − D*(k)`, `D* = resolve_deny(D) − R` (copy the
     table from data-model.md §2, including the identity-space rule).
   - **Decision 3 — Source resolution**: the kernel resolver table (data-model.md §5): ledger →
     only source; legacy keys + no ledger → fail closed outside the upgrade scope; in scope →
     legacy byte-for-byte; neither → ledger. Name the `BaseMigration` / registry / runner /
     `migrate ledger` / `upgrade` scope entry points.
   - **Decision 4 — Deny writers**: only `charter activate <kind> <id>` (incl. `--only`),
     cascade `--include-deactivated` and `--preset X --force`; the `deny_change` keyword guard.
   - **Decision 5 — Cascade stops at a denied node** (operator ruling
     `cascade_walk_through_denied`), "skipped, deactivated" and "unreached" buckets.
   - **Decision 6 — Required refusal and strict floor**: union over every declared org pack and its
     `extends:` chain; unreadable pack refuses; precedence untouched (C-005).
   - **Decision 7 — Migration** `4.0.0rc8_activation_ledger`: move, refuse divergence (operator
     ruling `stray_config_copy`), re-runnable after a crash, init writes the ledger.
   - **Consequences**: downgrade hazard (an older CLI treats every kind as absent = all);
     stray legacy keys warned once per process and reported by doctor; the SPDD probe residual
     (deny applied, required floor not, D-07); the overlay gains `extends:`-inherited
     requirements (D-18); reconcile command deferred (P10).
   - **Supersedes / amends**: supersedes 3.x/2026-07-18-1 **Decision 2** only ("charter.yaml owns
     activation"); amends 4.x/2026-10-03-1 (write target is the ledger) and 4.x/2026-10-06-2
     (presets `--force` clears listed exclusions; synthesis never re-adds a denied tactic).
   - **Revisit triggers**: `locked`/`enforced` mutability (spec-kitty-charter ADR-0012); the Java
     offering's #65 filtering; a reconcile command if users hit stray keys.
   - **Out of scope**: ADR-0013 Decision 7 (activation contract set on the charter API).
3. Link the spec and plan of this Mission by relative path.

**Files**: new ADR (~180–260 lines).

**Validation**: the decisions match research.md D-01..D-23 one for one; no "feature" wording; every
operator ruling in spec.md appears.

**Also record (analyze pass 5, L4):** ADR `2026-10-17-1` names `spec-kitty upgrade` as the
migration ledger's only writer. `spec-kitty migrate activation-ledger` (FR-021) becomes a second,
narrow writer. It appends the `4.0.0rc8_activation_ledger` success row only when the migration
ledger already exists, and goes through the ledger module's own record builder. Say this in the
new ADR, with the reason: a narrow re-run path for one cheap, idempotent move.

### Subtask T002: Amendment notes in the three older ADRs

**Purpose**: ADRs are immutable except for appended amendment notes; readers of the older ADRs
must find the new one.

**Steps**:
1. `docs/adr/3.x/2026-07-18-1-charter-yaml-authoring-authority-and-extractor-retirement.md`:
   append an "Amendment 2026-10-19" block stating Decision 2 is superseded by
   `../4.x/2026-10-19-1-…` (activation keys move to `activation.yaml`); the rest stands.
2. `docs/adr/4.x/2026-10-03-1-charter-read-write-service-strangler.md`: amendment — the
   activation write target is the ledger seam (`charter.activation.activation_ledger`).
3. `docs/adr/4.x/2026-10-06-2-charter-offering-active-charter-and-activation-presets.md`:
   amendment — presets without `--force` never touch deny keys and warn; `--force` clears
   exclusions for the ids the preset lists; synthesis never re-adds a denied tactic; the
   created-tactics record stays and is not an activation surface.
4. Do not edit any decision text above the amendment blocks.

**Files**: three ADR files (~10–20 lines appended each).

### Subtask T003: ADR inventory and index

**Steps**:
1. From the repository root: `.venv/bin/python -m scripts.docs.freshen_adr_inventory docs/adr/4.x/2026-10-19-1-activation-ledger-persists-deactivation.md`.
2. Confirm `docs/adr/4.x/index.md` gained the row and `docs/development/page-inventory.yaml`
   gained the entry; bump the index front matter `updated:` date to 2026-10-19 if the tool did not.
3. Refresh the docs retrieval index: `.venv/bin/python -m scripts.docs.docs_index --write` (updates `docs/development/docs-retrieval-index.yaml`).

**Files**: `docs/adr/4.x/index.md`, `docs/development/page-inventory.yaml`, `docs/development/docs-retrieval-index.yaml`.

### Subtask T004: Glossary terms in `docs/context/charter.md`

**Purpose**: the terms later WPs, doctor messages and docs use.

**Steps**:
1. Add four entries in the file's existing table format (Definition / Related terms / Do NOT use
   when): **Activation ledger**, **Exclusion** (deny-list entry), **Effective deny**, **Required floor**.
2. Activation ledger's "Do NOT use when" must point at the Migration Ledger
   (`docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`), the decision ledger and the status
   event log.
3. Update the **Active charter** entry's location wording: activation state now lives in
   `.kittify/charter/activation.yaml` (cite the new ADR). The glossary-pack YAML
   (`packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml`) carries a matching
   definition; that pack edit belongs to WP15 (pack-tier file, outside this planning WP) — leave
   it, and note it in your history entry.

**Files**: `docs/context/charter.md` (~40–60 lines added).

## Validation / targeted test surface

```bash
cd /home/user/spec-kitty
.venv/bin/python -m pytest -q tests/architectural/test_no_legacy_terminology.py
uv run --frozen python -m scripts.docs.check_spelling
.venv/bin/python -m scripts.docs.check_docs_freshness --ci
.venv/bin/python -m pytest -q tests/docs -k "adr or inventory or glossary"
```

Never run the bare `tests/architectural/` directory and never `make test-full`
(`NO_FULL_HEAVY_SUITES_IN_MISSION`). Record each command and its pass/fail counts in your
history note.

## Standing orders (every WP)

- Load python-pedro (above); keep any code change ruff/format(`--force-exclude`)/mypy clean
  (not expected here).
- Append a dated entry (`- **[2026-10-DD][WP01] …**`) to the Mission's
  `kitty-specs/persistent-deactivation-ledger-01M59YAA/traces/` files: `approach.md` (what you did),
  `design-decisions.md` (any wording decision), `tooling-friction.md` (any tool friction). Traces
  are Mission bookkeeping, not owned files.
- Do not edit shipped migrations (C-001, DIRECTIVE_044).

## Definition of Done

- The ADR exists, Accepted, and covers Decisions 1–7, consequences, supersede/amend lines and revisit triggers.
- Three amendment notes appended; nothing above them changed.
- Inventory and index updated by the canonical tool.
- Four glossary terms plus the Active charter location update.
- Validation commands green; each subtask recorded with `spec-kitty agent tasks mark-status T00x --status done --mission persistent-deactivation-ledger-01M59YAA`.

## Risks

- Drifting from the plan's decisions: diff the ADR against research.md D-## by hand.
- Terminology gate failures (`status commit`, never `ceremony`): run the gate.

## Reviewer Guidance

- Check every operator ruling in spec.md is recorded and none is softened.
- Check the supersede is scoped to Decision 2 of 2026-07-18-1 only.
- Check the glossary disambiguates "Activation ledger" vs "Migration Ledger".
