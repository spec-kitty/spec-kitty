# Mission Specification: Squad doctrine: single owner and profile-per-task rule

> **Scope (fold-in, operator 2026-09-28):** this mission covers the whole of epic #5218 (#5219 squad, #5220 testing / bug-fixing / BDD, #5221 Common Docs / change scope / supply chain / review tactics), plus #5202 (P0: duplicated software-dev guidelines, runtime serves the stale copy) and #5078 (commit and PR guidance). It ships as one mission and one PR. The mission slug predates the fold-in; the friendly name is kept per the no-metadata-rewrite rule.

**Mission Branch**: `claude/squad-doctrine-single-owner-rzqpvw`
**Created**: 2026-09-28
**Status**: Draft
**Input**: GitHub issues #5219, #5220, #5221 (epic #5218), #5202, #5078. Sources: the operator grounding brief (main `4e81f4d5`) and a four-lens grounding squad on `d95e60a2` (2026-09-28).

## Intent Summary

- **Primary actor:** an orchestrating agent (or human operator) in a consumer project who wants to run an adversarial squad at a mission point-cut.
- **Trigger:** the orchestrator reaches a point-cut (pre-spec, post-spec, post-plan, post-tasks, pre-merge, or an ad-hoc decision) and loads squad doctrine.
- **Desired outcome:** exactly one artifact — the `adversarial-squad-deployment` procedure — tells it when to run a squad, what question to ask, and **which profiles to pick for that task**, with squad sizes and casting shown as *examples*, not rules.
- **Invariant:** every other artifact that mentions the squad references the procedure by id (plus a DRG edge) and does not restate its playbook, point-cut list or sizes.
- **Boundary:** the squad stays optional, advisory and never a gate. The fixed-lens specialisations (five-paradigm debugging, Paula's architecture scouts) keep their five-lens sets. DIRECTIVE_046 and the wrap-up procedure keep recommending a squad.

## Epic rule (#5218)

**One owner states each rule; every other artifact references it by id (and a DRG edge).** This is not wholesale merging:
- a directive is a rule;
- a tactic is a how;
- a styleguide is a format;
- a procedure is a workflow;
- a paradigm is a worldview.

**Delivery-risk rule:** every trim or deletion keeps the owner delivered. It adds a replacement `suggests`/`requires` edge where the trimmed copy was the only delivery path. This is verified with `spec-kitty charter context --action implement|review` before and after.

## Problem (#5219 — squad)

Squad guidance has three self-declared owners — the procedure, the `adversarial-squad-cadence` styleguide and the `adversarial-squad` harness skill — plus partial restatements in DIRECTIVE_052, the project charter and two profiles. The copies disagree:

- **Size reads as a hard rule:** 3-4 in the procedure and the skill, 3-5 in the styleguide, exactly 5 in the fixed-lens tactics.
- **Point-cut lists differ in four places.** The styleguide adds "mission sizing" and drops pre-spec and pre-merge. The procedure and the skill place the "pre-spec" squad *after* `/spec-kitty.specify`, which contradicts its own name.
- **Recommended casting contradicts the cast profiles.** `paula-patterns` and `debugger-debbie` both avoid first-occurrence work, call themselves expensive, and fan out five sub-agents by default.
- **A nonexistent profile is cast:** `researcher-ryan`. The real profile is `researcher-robbie`.
- **The profile-per-task rule is never stated.** The owner's framing is that different profiles are selected depending on the task at hand.
- **The glossary term** "adversarial squad" exists only in the internal (non-shipping) pack.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One owner answers "who do I cast?" (Priority: P1)

An orchestrator at a post-tasks point-cut loads the procedure and finds, in one place:
- the point-cut list;
- the rule "choose profiles whose declared focus answers this point-cut's question";
- an example point-cut → profile table.

Nothing in the procedure presents a headcount as a requirement.

**Why this priority**: this is the core defect. Contradictory owners give orchestrators conflicting instructions.

**Independent Test**: parse the procedure. It states the profile-per-task rule, contains exactly one point-cut list with pre-spec before `/spec-kitty.specify`, labels its sizes and table as examples, and every profile id in the table resolves to a shipped profile.

**Acceptance Scenarios**:

1. **Given** the shipped procedure, **When** an agent reads its invariants and anti-patterns, **Then** no fixed headcount (for example "3-4") appears as an invariant or as the yardstick of an anti-pattern.
2. **Given** the example casting table, **When** each profile id is resolved against the shipped profile set, **Then** every id resolves (so `researcher-ryan` cannot appear).
3. **Given** the example table, **When** it casts a recurrence-only profile (`debugger-debbie`, `paula-patterns`), **Then** it does so only for a recurrence or escalation row, never as a default lens for first-occurrence work.

---

### User Story 2 - Retiring the styleguide does not break consumer projects (Priority: P1)

A consumer project whose charter activated the `adversarial-squad-cadence` styleguide upgrades Spec Kitty. After the upgrade:
- charter compilation and `charter context` still work;
- the retired id is gone from the project's activation and compiled surfaces.

**Why this priority**: the charter compiler fails closed on an unknown activated id. Deleting the artifact without a migration would hard-fail every such project.

**Independent Test**: a fixture project with the retired id in `config.yaml`, `charter.yaml` (activation plus catalog block) and `references.yaml`. Running the migration removes every occurrence. A second run is a no-op. A project without the id is untouched.

**Acceptance Scenarios**:

1. **Given** a project activating the retired styleguide, **When** `detect` runs, **Then** it returns true. **When** `apply` runs, **Then** every occurrence is removed and nothing else changes.
2. **Given** a project with no `.kittify/` files, **When** the migration runs, **Then** nothing is created.

---

### User Story 3 - Inbound references still deliver the owner (Priority: P2)

DIRECTIVE_043, DIRECTIVE_052, `mission-tracer-files` and `brownfield-onboarding` previously pointed at the styleguide. After the change:
- DIRECTIVE_043, DIRECTIVE_052 and `mission-tracer-files` point at the procedure.
- `brownfield-onboarding` already requires the procedure, so its styleguide edge is simply removed.

The shipped graph regenerates cleanly and no artifact or edge names the deleted styleguide.

**Independent Test**: `spec-kitty doctrine regenerate-graph --check` exits 0. A grep of the shipped pack, the generated manifest and the extractor finds no `adversarial-squad-cadence`. The reachability goldens update only by the ledgered delta.

---

### User Story 4 - Fixed-lens specialisations defer to the procedure (Priority: P2)

The following reference the procedure for the squad playbook:
- DIRECTIVE_040;
- the `five-paradigm-parallel-debugging` and `paula-patterns-architecture-scout-review` tactics;
- the `debugger-debbie` and `paula-patterns` profiles.

Both tactics `refines` the procedure in the DRG. Both profiles offer a `squad-delegate` mode that answers one lens without fanning out. The harness skill shrinks to its triggers plus "follow the procedure".

**Independent Test**: the DRG contains `tactic:five-paradigm-parallel-debugging --refines--> procedure:adversarial-squad-deployment`, the same edge from the Paula scout tactic, and `procedure:adversarial-squad-deployment --suggests--> tactic:model-task-routing`. It no longer contains `procedure --requires--> five-paradigm`. The skill no longer restates the recipe steps.

---

### User Story 5 - The concept ships with its definition (Priority: P3)

Consumers see "adversarial squad" defined in the built-in glossary. The internal pack no longer carries a duplicate definition.

### User Story 6 - Agents receive the guidelines that authors actually edit (Priority: P1, #5202)

A consumer agent at the software-dev implement, plan, review or tasks step loads the step guidelines. It receives the single `mission-steps/` copy, which includes the supply-chain sections and the corrected terminology and dependency rule. No second `actions/*/guidelines.md` copy exists to drift.

**Independent Test**: `MissionRepository` resolves every action's guidelines from `mission-steps/<type>/<action>/guidelines.md`. No `actions/*/guidelines.md` file exists under `packs/built-in/missions/`. The served software-dev review guideline states the approved/done dependency rule.

### User Story 7 - Printed commit and PR guidance matches doctrine (Priority: P2, #5078)

An implementing agent reads the implement footer, the planning-artifact hint and the other printed recipes.
- Each commit recipe uses `spec-kitty safe-commit <files> -m … --to-branch <branch>`, never a raw `git commit`.
- When the target is a protected primary branch, the guidance says how to proceed.
- For a work package that changes `.github/workflows/*`, the WP agent pushes its branch and reports to the orchestrator, which opens the draft PR and records the CI run.

**Independent Test**: a scan of the CLI's user-facing printed strings finds no raw `git commit -m` recipe. The implement step prompt assigns PR opening to the orchestrator.

### User Story 8 - One owner per testing and bug-fixing rule (Priority: P2, #5220)

An agent fixing a bug receives one consistent workflow: `test-first-bug-fixing`. It references DIRECTIVE_034 (reproduce), DIRECTIVE_052 (diagnose first), DIRECTIVE_025 (tidy-first sequencing), `red-main-release-discipline` (P0 repro topology) and `disciplined-defect-diagnosis`. The retired `bug-fixing-checklist` no longer competes with it.

Testing terms mean one thing each:
- "Predictive", "Inspiring" and "Clear test boundaries" are defined by `test-desiderata-and-boundaries`.
- `testing-principles` covers refactor-stable test design and references Quad-A.
- There is one mutation band table, framed as triage bands.

The BDD artifacts follow the paradigm's phase order.

### User Story 9 - One owner per docs, change-scope, supply-chain and review rule (Priority: P2, #5221)

- **Docs:** DIRECTIVE_037 owns the same-change docs rule, and the common-docs styleguide owns frontmatter conventions. ADRs keep MADR `status`.
- **Change scope:** the change-scope reconciler names DIRECTIVE_052 and states the tidy-first carve-out and the rename-inside-touched-area tie-break.
- **Supply chain:** DIRECTIVE_051 states its pillars once, and an ecosystem-neutral tactic plus per-ecosystem toolguides carry the steps.
- **Disposition contract:** the findings-disposition contract ships once, owned by the squad procedure.
- **Review tactics:** `code-review-incremental` builds on `review-intent-and-risk-first` with one risk taxonomy.

### Edge Cases

- A project activated the styleguide in `charter.yaml` only (no `config.yaml` entry), or in `config.yaml` only. Each surface is handled independently.
- A hand-edited config lists the retired id twice. Every occurrence is removed.
- A malformed project YAML file is skipped, never fatal. This follows the rtk precedent.
- A retired id that has a successor, whether moved or kind-changed, gets its successor activated. Examples: `bug-fixing-checklist` → procedure `test-first-bug-fixing`, and `boring-code-review` tactic → the styleguide. A retired id with no consumer-facing successor is simply removed; this covers the ids moved to `packs/internal`.
- DIRECTIVE `024-locality-of-change` shares a slug with the `locality-of-change` tactic. The migration matches by kind key and never touches the directive.
- A consumer plans on a protected `main`: safe-commit refuses, and the printed guidance must name the supported path.
- The lens-activation guard (`tests/doctrine/test_activation_squad_lenses.py`) previously parsed the skill's lens list. It must now parse the procedure's example table. If the skill is shrunk, the guard must not pass vacuously.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Requirement | Status | Delivery | No-op passable? |
|----|-------------|--------|----------|-----------------|
| FR-001 | The `adversarial-squad-deployment` procedure states the profile-per-task rule: choose profiles whose declared focus answers this point-cut's question. | proposed | [build] | no |
| FR-002 | The procedure owns the single point-cut list: pre-spec (before `/spec-kitty.specify`), post-spec, post-plan, post-tasks, pre-merge, ad-hoc decision. No other shipped squad artifact — the skill, DIRECTIVE_052, the styleguide (deleted), the project charter's Standing Order #1 or the standing-orders reference page — restates a point-cut list. "Restates" means naming ≥3 of {pre-spec, post-spec, post-plan, post-tasks, pre-merge} in one block. The detector's positive control: it must flag today's SKILL.md and styleguide text. | proposed | [build] | no |
| FR-003 | Squad sizes and a point-cut → profile table appear in the procedure, explicitly labelled as examples. No headcount range or "exactly N" appears in the procedure's `anti_patterns` or invariant text, or in the SKILL.md. The fixed-lens tactics and the Debbie/Paula profiles are excluded by name (C-003). Positive control: the detector flags the pre-change strings "bounded (3-4)" and "3-4 distinct lenses". | proposed | [build] | no |
| FR-004 | The procedure's example table uses a fixed, parseable line grammar under a literal anchor. Every profile id it casts resolves through the profile repository **and** is in the default pack's `activated_agent_profiles`, which keeps the #3810 guard. The table keeps `doctrine-daphne` and `randy-reducer`. A profile whose `avoidance-boundary` excludes first-occurrence work appears only on a recurrence/escalation row. Negative control: a line casting `researcher-ryan` fails. | proposed | [build] | no |
| FR-005 | Model-tier choice is delegated to the `model-task-routing` tactic. It gets a procedure → tactic `suggests` edge, authored as a curated extractor edge because procedure YAML `references` to a tactic always mint `requires`. The procedure step names the tactic and no longer restates tiers ("stronger model tier" / "lighter tier" are absent). | proposed | [build] | no |
| FR-006 | The procedure no longer `requires` `five-paradigm-parallel-debugging`. | proposed | [build] | no |
| FR-007 | The styleguide `adversarial-squad-cadence` is deleted. Its unique content is folded into the procedure: post-tasks is the highest-value point-cut, a bounded timebox, and the gate-hardwiring example. | proposed | [build] | no |
| FR-008 | DIRECTIVE_043 (a YAML `references` entry, which mints `suggests`), DIRECTIVE_052 (its curated edge plus prose) and `mission-tracer-files` point at the procedure with `suggests`. The tracer edge is a curated extractor edge, because a procedure → procedure YAML reference would mint `requires` and create a hard chain that contradicts C-001. `brownfield-onboarding` drops its styleguide reference, since it already requires the procedure. The shipped comment in `acceptance-criteria-non-vacuity` and the overlay comment are updated too. | proposed | [build] | no |
| FR-009 | One data-driven upgrade migration retires every id this mission removes, renames, moves or re-kinds. It activates the successor where one exists. For the styleguide it removes the retired id from `.kittify/config.yaml`, `.kittify/charter/charter.yaml` (activation list and catalog block), `.kittify/charter/references.yaml`, the interview `selected_styleguides` answer, and the legacy `governance.charter.selected_<kind>` block in `charter.yaml`. The answer is included so a later `charter generate` cannot reintroduce the id. The legacy block is included because `charter generate` preserves it unchanged and `charter context` still renders it, so leaving it would keep serving retired ids to agents (found by the WP10 dogfood review). The migration is idempotent and creates nothing (the directory tree is unchanged on a bare project). The generic logic is a shared helper that the existing rtk-retirement migration also uses, so no near-copy is added. | proposed | [build] | no |
| FR-010 | This repository's own charter surfaces stop naming the retired styleguide. The change goes through the source (`interview/answers.yaml`, the charter prose) and the canonical charter CLI regeneration, not by hand-editing compiled output. Standing Order #1 points at the procedure. | proposed | [build] | no |
| FR-011 | The `adversarial-squad` harness skill shrinks to its triggers plus a pointer to the procedure. It restates no recipe steps, lens list, point-cut list or headcount. The lens-activation guard is re-pointed (not deleted) to parse the procedure's example table and asserts a non-empty lens set. | proposed | [build] | no |
| FR-012 | DIRECTIVE_040, `five-paradigm-parallel-debugging` and `paula-patterns-architecture-scout-review` name the procedure in prose. Both tactics carry a curated `refines` edge to the procedure, the only way to author `refines`. `refines` is followed by charter cascade, not by context delivery. The procedure still reaches loaded agents through its existing inbound `requires`/`suggests` edges, so no duplicate `suggests` edge is added for the same pair. | proposed | [build] | no |
| FR-013 | `debugger-debbie` and `paula-patterns` each declare a `squad-delegate` entry in `mode-defaults`: when cast as one lens of a squad, answer that lens directly without fanning out. This is prose only, with no `operating-procedures` edge. The procedure's dispatch step names the `squad-delegate` mode, and each profile's initialization declaration stays consistent with it. The test is a prose ratchet: presence of the mode and the cross-reference. | proposed | [build] | no |
| FR-014 | DIRECTIVE_001 → `paula-patterns-architecture-scout-review` (a curated edge) becomes `suggests` instead of `requires`. **Conditional:** only if the action-reachability goldens show no loss of delivery for artifacts reached through the tactic (for example `strategic-domain-classification`). Otherwise the edge stays `requires` and the decision is recorded. `tests/doctrine/test_paula_patterns_artifacts.py` pins the current relation. | proposed | [build] | no |
| FR-015 | The glossary term "adversarial squad" is defined in the built-in glossary pack and removed from the internal pack. | proposed | [build] | no |
| FR-016 | #5202: `mission-steps/<type>/<action>/guidelines.md` is the single served guidelines owner. The loader resolves it, every `actions/*/guidelines.md` is deleted, and the four drifted software-dev files merge the correct halves: supply-chain sections from `mission-steps/`, "repository root checkout" and the tasks wording from `actions/`, and the review dependency rule rewritten to approved/done. | proposed | [build] | no |
| FR-017 | #5202: the byte-identity guard is replaced by an absence guard (no `actions/*/guidelines.md`) plus a loader-path test. The docs that name `actions/*/guidelines.md` as the source (`04_implementation_mapping`) are corrected. | proposed | [build] | no |
| FR-018 | #5078: every user-facing commit recipe printed by the CLI (implement footer, planning-artifact hint, tasks validation, charter synthesis, setup-plan) uses `spec-kitty safe-commit … --to-branch <branch>`. The protected-primary case names the supported path. | proposed | [build] | no |
| FR-019 | #5078: the software-dev implement step prompt makes the WP agent push only and report. The orchestrator opens the draft PR and records the CI run ID, consistent with `mission-wrap-up-sequence` and DIRECTIVE_045. | proposed | [build] | no |
| FR-020 | #5220: `bug-fixing-checklist` is folded into `test-first-bug-fixing`, carrying its four unique lines, and retired. The procedure references 034, 052, 025, `red-main-release-discipline` and `disciplined-defect-diagnosis`. Its refactor, minimal-fix and commit-topology wording follows the recorded decisions. The four profiles that cited the checklist cite the procedure through `operating-procedures`. | proposed | [build] | no |
| FR-021 | #5220: "Predictive", "Inspiring" and "Clear test boundaries" have one owner (`test-desiderata-and-boundaries`). `testing-principles` renames its colliding terms, references Quad-A, the pyramid and over-mocking, and gains a `testing-principles → quadruple-a` edge before its inline copy is trimmed (delivery risk). The overlay `when` text and the two tactic citations are corrected. | proposed | [build] | no |
| FR-022 | #5220: exactly one mutation band table exists (in `mutation-testing-workflow`), framed as triage bands. The "Target 80%+" line and the TypeScript `break: 60` default are removed; a CI break gate is shown as a project opt-in with `break: 0` as the default. | proposed | [build] | no |
| FR-023 | #5220: DIRECTIVE_025 scopes pre-existing-failure handling to the touched area and defers classification to DIRECTIVE_030. `development-bdd` follows the paradigm's phase order. The BDD tactic is renamed `bdd-scenario-formulation` under `tactics/testing/`, references the given-when-then styleguide (`requires`), the gherkin toolguide and the lifecycle procedure, and moves its toolchain notes to the toolguide. The BDD paradigm gains edges to its practices. A glossary alias covers both spellings of behaviour/behavior. | proposed | [build] | no |
| FR-024 | #5221 A: ADR guidance uses MADR `status`, never `doc_status`. The section count is stated once, by the styleguide. The lint config moves to a data file owned by the lint asset. The status vocabulary stays within the five values or is declared by the lint asset. DIRECTIVE_037 owns the same-change docs rule, and the other artifacts reference it. `common-docs-curation` is folded into scaffold/write/find and retired. | proposed | [build] | no |
| FR-025 | #5221 B: `RECONCILE_CHANGE_SCOPE_TENSIONS` names DIRECTIVE_052 and states two rules: the tidy-first carve-out, and the tie-break that DIRECTIVE_025 naming improvements are allowed inside the touched area. The `locality-of-change` tactic is folded into `avoid-gold-plating` and retired. `easy-to-change`, `avoid-gold-plating` and `boring-code-review` link the reconciler. | proposed | [build] | no |
| FR-026 | #5221 C: DIRECTIVE_051 states its pillars once, and Node LTS moves to a JS/TS toolguide. An ecosystem-neutral supply-chain tactic plus per-ecosystem toolguides carry the operational steps. Prompts, guidelines, step contracts and profiles reference them by id instead of restating them. | proposed | [build] | no |
| FR-027 | #5221 C: the findings-disposition contract (`accepted` / `changed` / `deferred_with_rationale`) ships once, owned by the squad procedure. Every citer references it by id. The documentation-validate vocabulary is mapped onto it. | proposed | [build] | no |
| FR-028 | #5221 D: `code-review-incremental` builds on `review-intent-and-risk-first` by reference, with one risk taxonomy and no "confirm with the author" step. `iterative-deepening-review` is renamed to name backlog triage and moves to `packs/internal` together with `tracker-organisation-workflow`. `boring-code-review` becomes a styleguide. Step contracts cite directives as `DIRECTIVE_NNN`. | proposed | [build] | no |

### Non-Functional Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| NFR-001 | `spec-kitty doctrine regenerate-graph --check` exits 0 after the change. `pack-manifest.yaml` is regenerated, never hand-edited. | proposed |
| NFR-002 | The builtin-pack provenance ratchet counts only go down, and pack prose carries no `#NNNN` issue references. | proposed |
| NFR-003 | New Python passes `ruff check`, `ruff format --check` and `mypy`, with function complexity ≤ 15. New migration branches are covered by focused tests (diff coverage ≥ 90%). | proposed |
| NFR-004 | The DRG golden ledgers record the edge delta explicitly. No reachability set changes without a ledger note. | proposed |

### Constraints

| ID | Constraint | Status |
|----|------------|--------|
| C-001 | The squad stays optional and advisory. No status or mission gate is added. | binding |
| C-002 | (Reversed by the fold-in.) The findings-disposition contract IS written, once, as part of the squad procedure (FR-027). | superseded |
| C-003 | Keep the fixed-lens tactics' five-lens sets, DIRECTIVE_040's recurrence requirement, and DIRECTIVE_046 plus the wrap-up procedure's squad recommendation. | binding |
| C-004 | Edit source templates and pack files only. Never hand-edit generated agent copies or `pack-manifest.yaml`. | binding |
| C-005 | Do not reword enforcement levels. They move to the charter under a separate issue. | binding |

## Success Criteria

| ID | Criterion | Delivery | No-op passable? |
|----|-----------|----------|-----------------|
| SC-001 | Exactly one shipped artifact states the squad point-cut list and playbook. This is measured by the FR-002/FR-003 detectors over the named file set (procedure, SKILL.md, DIRECTIVE_052, charter Standing Order #1, standing-orders reference page), with their positive controls. | [build] | no |
| SC-002 | Under `src/` and `packs/`, `adversarial-squad-cadence` appears only in the retirement migration. The id may also remain in historical records: the relocation fixture `content-manifest.json`, archived `kitty-specs/`, `docs/reports/`, and golden-ledger history comments. Positive control: the same grep finds hits on the base commit. | [build] | no |
| SC-003 | A fixture project activating the retired id loses it after the migration, and a second run reports nothing to do. | [build] | no |
| SC-004 | The DRG shows the two `refines` edges, the `model-task-routing` suggests edge, and no procedure → five-paradigm `requires` edge. | [build] | no |
| SC-005 | Software-dev agents receive the supply-chain guideline sections at implement, plan and review. `charter context` or the loader output contains them, and they are absent at base. | [build] | no |
| SC-006 | Zero raw `git commit` recipes in CLI-printed guidance anywhere under `src/specify_cli`, outside a named allowlist. The base count, about 11 sites, is pinned in the test. | [build] | no |
| SC-007 | For every owner named in the epic (Quad-A, 025, 030, 034, 037, 051, 052, the squad procedure, the disposition contract), `charter context --action implement` and `--action review` deliver it after the change wherever they did before. A delivery test pins this. | [build] | no |
| SC-008 | A fixture consumer project activating every retired, renamed or re-kinded id compiles its charter after the migration, and each successor id is activated. | [build] | no |

## Domain Language

- **Adversarial squad**: a set of profile-loaded delegates, one lens each, dispatched in parallel at a point-cut, with lenses chosen for the task at hand. The fixed five-lens swarms (*five-paradigm debugging*, *architecture-scout review*) are **fixed-lens specialisations**: they refine the squad pattern with a predetermined lens set, which is why they `refines` the procedure. Their "five" names a lens set, not a squad size.
- **Point-cut**: a named moment in the mission lifecycle where a squad may run.
- **Squad delegate**: one profile cast as one lens of a squad.

## Assumptions

- The rtk-retirement migration pattern is the accepted consumer-safe path for deleting an activatable artifact.
- `refines` is a first-class, traversable relation (cascade traverses it). The "zero built-in edges" wording in its relation description (`RELATION_DESCRIPTIONS` in the DRG models) becomes stale and is updated, together with `docs/architecture/doctrine-relationships.md`, which `test_relation_doc_parity.py` keeps word-for-word in sync.
- Consumer `graph.yml` is compiled output that `charter synthesize` regenerates. The implement step checks whether a stale styleguide node in it breaks `charter context`. If it does, the migration covers it too.
- Additional surfaces that restate the squad or name the styleguide, updated in scope: `docs/development/reference/quality-and-tech-debt-standing-orders.md` (a second point-cut table) and `docs/development/agent-fleet.md`.

## Out of Scope

- Enforcement-level and criticality wording (#5207).
- Other in-house-in-built-in moves (#5203), except the `iterative-deepening-review` and `tracker-organisation-workflow` move, which is folded in by operator decision.
- Renaming ids for spelling alone (`paradigm:behaviour-driven-development` stays).
