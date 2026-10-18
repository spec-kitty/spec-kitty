# Mission Specification: Charter governance resolution

**Mission Branch**: `issue-6404-charter-governance-resolution-work` (PR branch `issue-6404-charter-governance-resolution`)
**Created**: 2026-10-18
**Status**: Draft
**Input**: GitHub issues #6404, #6405, #6406, #6407, #6408, found while using Spec Kitty in the `sddevelopment-be/spec-kitty-charter` repository. Grounding brief: `research.md` in this Mission directory. Operator decisions on product semantics were taken on 2026-10-18 and are recorded as resolved Decision Moments.

## Intent Summary

An operator who governs a project with a charter expects the governance an agent receives for an action to be the governance the operator activated and selected. Today five defects break that: synthesized "how we apply" tactics never reach any action, directives from org packs are shown under ids that do not exist, one org-pack id in `selected_directives` silently erases every directive, the first deliberate selection freezes the whole catalog into the project's activation lists, and the stack detector calls a Gradle/Java repository `typescript`. This Mission makes the charter activation layer resolve artifact identity through one layer-aware authority, makes synthesized tactics reachable through the same edge shape built-in directives use, gives the operator an explicit narrow-activation path, and makes stack detection prefer the repository root.

- **Primary actor**: a project operator (or an agent acting for them) running `spec-kitty charter` commands and receiving action context.
- **Trigger**: `charter synthesize`, `charter activate`, `charter interview`, `charter context`, and editing `charter.yaml` selections.
- **Desired outcome**: the action context names the right artifacts by their declared ids and includes everything the operator activated, selected or synthesized for that action.
- **Invariant**: what is in force by default is unchanged; nothing the operator did not ask to narrow stops being in force.
- **Canonical terms**: Mission, activation (the `activated_<kind>` lists in `.kittify/config.yaml`), selection (`governance.charter.selected_<kind>` in `charter.yaml`), declared id (the `id:` an artifact file declares), activation token (the file stem or id stored in an activation list), layer chain (built-in, then every declared org pack, then the project pack layer).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Synthesized tactics reach context through their directive (Priority: P1)

An operator runs `charter synthesize`; it writes one `how-we-apply-<directive>` tactic per active directive. Each tactic is linked from its directive with a `suggests` edge, synthesis adds the tactic to an explicit `activated_tactics` list when one exists, and the tactic reaches action context only through that edge: it is delivered while its directive is active and stops being delivered when the directive is deactivated.

**Why this priority**: synthesis is the main way a project expresses its own practice. Today the tactics hang off an inert edge, are filtered out by any explicit `activated_tactics` list, and, with no list, are delivered for every action regardless of their directive (#6404).

**Independent Test**: synthesize in a scratch project with explicit `activated_directives` and `activated_tactics`, then `charter context --action implement --mission-type software-dev --json` lists the `how-we-apply-*` tactic of each activated directive; deactivating a directive removes its tactic.

**Acceptance Scenarios**:

1. **Given** a project with explicit `activated_directives` (including `DIRECTIVE_024`) and an explicit `activated_tactics` list, **When** `charter synthesize` runs, **Then** `activated_tactics` gains `how-we-apply-directive-024` and the project graph holds `directive:DIRECTIVE_024 --suggests--> tactic:how-we-apply-directive-024`.
2. **Given** that project, **When** the operator loads `implement` action context with `--mission-type software-dev`, **Then** `how-we-apply-directive-024` is delivered. **Given** the same fixture with the edge removed from the graph, **Then** it is not delivered (the edge is the only route).
3. **Given** that project after `charter deactivate directive 024-...`, **When** context is loaded, **Then** `how-we-apply-directive-024` is not delivered, while a non-synthesized activated tactic on the same fixture still is.
4. **Given** a project with no `activated_tactics` key, **When** synthesis runs, **Then** no `activated_tactics` key is written.
5. **Given** the same project, **When** synthesis runs again (full or partial for one tactic), **Then** each directive-to-tactic edge exists exactly once, and `--prune` does not remove it while its tactic exists.
6. **Given** a project synthesized before this change (legacy `applies` edges), **When** `charter synthesize` runs, **Then** no `applies` edge from a synthesized node remains.
7. **Given** an activated org directive with stem ≠ declared id, **When** synthesis runs, **Then** its edge starts at the directive's declared-id URN, which resolves in the merged graph.

---

### User Story 2 - Artifacts are named and delivered by their declared id (Priority: P1)

An operator activates an org-pack directive whose file is `qa-003-no-fake-green.directive.yaml` and whose declared id is `QA_003`. Every context and charter surface names it `QA_003`, and `--include directive:QA_003` or `--include directive:qa-003-no-fake-green` resolves it. The same holds for every activatable kind: an org or project artifact whose file stem differs from its declared id is delivered and listed as activated, whether the activation list stores its stem or its declared id.

**Why this priority**: wrong ids cannot be resolved by an agent and silently hide governance (#6406 and its sibling defect for non-directive kinds).

**Independent Test**: with a fixture org pack, compact context lists `QA_003`, never `QA_003_NO_FAKE_GREEN`; an org tactic with stem `qa-tactic-seven` and id `qa-seven` appears in `ActiveCharterService.tactics`, in action context, and as activated in `charter list`.

**Acceptance Scenarios**:

1. **Given** an activated org directive with stem ≠ id, **When** compact or JSON context is rendered, **Then** the directive id shown is the declared id, with its org-pack source.
2. **Given** one activation list holding a stem token and a declared-id token for two org tactics with stem ≠ id, **When** the charter service and action context list active tactics, **Then** both surfaces deliver both declared ids.
3. **Given** a built-in directive activated by its stem, **When** context is rendered, **Then** its id is unchanged from today (`DIRECTIVE_NNN`).
4. **Given** an activated org tactic with stem ≠ id, **When** `charter list` runs, **Then** it is shown as activated and not as available.

---

### User Story 3 - An org-pack id in a selection is honoured, an unknown one is reported (Priority: P1)

An operator adds `QA_003` (an org-pack directive, by declared id or by stem) to `governance.charter.selected_directives`. Action context unions it onto the activated set. If the operator adds an id no layer knows, that id alone is dropped; the compact text and the JSON `diagnostics` name it and point at org packs and `.kittify/charter-packs/`; every other directive, paradigm, tool and template set still resolves, and the command keeps exiting 0.

**Why this priority**: today one org id erases all governance behind a success exit (#6407).

**Independent Test**: with the fixture org pack, `selected_directives: [QA_003]` yields `QA_003` among the delivered directives; `selected_directives: [QA_003, NOPE_999]` yields the same directives plus a diagnostic naming `NOPE_999`.

**Acceptance Scenarios**:

1. **Given** `selected_directives: [QA_003]` (and separately `[qa-003-no-fake-green]`) with the org pack declared, **When** context is rendered, **Then** `QA_003` is delivered and no "governance unresolved" diagnostic appears.
2. **Given** `selected_directives: [QA_003, NOPE_999]`, **When** context is rendered, **Then** `QA_003` and the activated directives are delivered, the compact text and JSON diagnostics name `NOPE_999`, the exit code is 0, and no remediation text tells the operator to edit `packs/built-in/`.
3. **Given** an org paradigm in `selected_paradigms`, **When** context is rendered, **Then** it is accepted the same way, and an unknown paradigm is dropped with a diagnostic.

---

### User Story 4 - The operator can narrow activation deliberately (Priority: P2)

An operator who wants only a few artifacts of a kind in force runs `charter activate <kind> <id> --only`. The kind's list is set to that id plus the org-required ids of that kind, and the command prints exactly which ids stop being in force. Further ids are added with plain `charter activate`, which appends to the now-present list. The interview's `--narrow-activation` option does the same for the directives, tactics and paradigms it promotes. Without these options behaviour is unchanged, and the "Preserved N" / "Initialized from N" warnings now say that the materialised list is frozen (built-ins shipped later do not activate automatically) and name `--only`. The `/spec-kitty.charter` command contract explains which path keeps activation narrow.

**Why this priority**: the contract asks for narrow selections but no CLI path delivers one (#6408). Lower than P1 because the default is deliberate and not wrong.

**Independent Test**: in a fresh project, `charter activate toolguide gherkin --only` writes `activated_toolguides: [gherkin]` and lists the 17 other toolguides as no longer in force; without `--only` it writes the full effective set as today.

**Acceptance Scenarios**:

1. **Given** no `activated_toolguides` key, **When** `charter activate toolguide gherkin --only`, **Then** the key holds exactly `[gherkin]` and the output lists every other previously effective toolguide as no longer in force.
2. **Given** an org pack requiring a toolguide whose stem differs from its declared id, **When** `--only` narrows that kind, **Then** the required toolguide stays in force (stored in a form the activation filter resolves).
3. **Given** no key and no `--only`, **When** `charter activate toolguide gherkin`, **Then** the written list is identical to today and the warning says the list is now frozen and names `--only`.
4. **Given** a present key, **When** `--only` is passed, **Then** the key is replaced by the id plus org-required ids, and the output names what stopped being in force; **Given** a following plain `charter activate toolguide <other>`, **Then** the list holds both.
5. **Given** `charter interview --defaults --narrow-activation --selected-directives DIRECTIVE_001`, **When** it promotes selections, **Then** `activated_directives` holds only `001-architectural-integrity-standard` plus org-required directives, and the JSON payload names the ids that stopped being in force. **Given** the same command without `--narrow-activation`, **Then** the full set is written as today.
6. **Given** `--only` together with `--preset`, **Then** the command refuses with exit code 2. **Given** `--only` for `skill`, **Then** it is accepted and narrows the explicit list like any other kind.

---

### User Story 5 - Stack detection reports the root build's language (Priority: P2)

An operator synthesizes in a Gradle/Java repository that also hosts a TypeScript docs site under `site/`. The synthesis evidence reports `java`, so the neutrality gate lints the right artifacts.

**Why this priority**: a wrong scope tag mis-lints every synthesized artifact (#6405).

**Independent Test**: the code reader on a fixture with root `build.gradle.kts`, `settings.gradle.kts`, `gradlew`, `src/main/java/App.java` and `site/package.json` + `site/tsconfig.json` reports `java`.

**Acceptance Scenarios**:

1. **Given** the fixture above, **When** evidence is collected, **Then** `primary_language` is `java`.
2. **Given** only a Kotlin-DSL Gradle build with Java sources, **When** evidence is collected, **Then** the language is `java`, not `unknown`.
3. **Given** a docs-only repository whose only manifest is `site/package.json` with `site/tsconfig.json`, **When** evidence is collected, **Then** the language is still `typescript`.
4. **Given** scope tag `java`, **When** the neutrality gate classifies `javascript-style-guide`, **Then** it is not treated as java-scoped.

### Edge Cases

- An activation token that resolves in no layer: activation lists keep today's warning-and-normalise fallback (no regression for legacy tokens); selections report it as unknown and drop it.
- A token that is one artifact's stem and another artifact's declared id: the stem match wins (stems are the canonical activation form); the seam is deterministic and tested.
- The same declared id in two layers: the precedence of `resolve_artifact_urn` (project, then org packs in reverse declaration order, then built-in) decides, pinned by a test.
- A directive whose stem is digit-led (`001-...`): its id stays `DIRECTIVE_001`.
- A synthesized tactic delivers per directive activation, not per action: the `suggests` closure starts from every activated directive, so an unscoped synthesized tactic is delivered for every action while its directive is active.
- A synthesized tactic is pruned (its directive left the synthesis inputs): every edge that touches it is pruned too, so no dangling edge remains.
- `--only` with `--cascade`: narrowing applies to the named artifact's own kind only; cascaded kinds keep today's append behaviour.
- A repository with root manifests for two languages: source-file counts decide; ties keep today's indicator priority.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Synthesis emits a directive-to-tactic `suggests` edge | As an operator, I want synthesis to link each directive to its how-we-apply tactic with `suggests` from the directive's declared-id URN, so that the tactic is reachable the way built-in tactics are (#6404). | High | Open | [build] | no — graph assertion on the fixture; today the edge is `applies` from the tactic |
| FR-002 | Synthesized tactics are reached only through their edge | As an operator, I want synthesized tactics that carry a directive edge never to be traversal roots (edgeless synthesized tactics and hand-authored project tactics stay roots), so that a synthesized tactic is delivered exactly while its directive is active (#6404). | High | Open | [build] | no — paired: edge removed means not delivered, edge present means delivered, same fixture |
| FR-003 | Synthesis adds its tactics to an explicit `activated_tactics` list | As an operator, I want `charter synthesize` to append the tactic ids it creates to an explicit `activated_tactics` list, leaving an absent key absent, so that a curated list does not filter them out (#6404). | High | Open | [build] | no — fixture with an explicit list lacks the ids today |
| FR-004 | Reconcile owns an edge by its synthesis target | As an operator, I want re-synthesis (full and partial), conflict reporting and `--prune` to assign each edge to the synthesized node it was derived for, and pruning a node to remove every edge touching it, so that edges are neither duplicated, orphaned nor wrongly pruned (#6404). | High | Open | [build] | no — second run must yield exactly one edge, with a positive control that it exists |
| FR-005 | Legacy `applies` edges from synthesized nodes are removed | As an operator of an already-synthesized project, I want any synthesize run to drop `applies` edges whose source is a synthesized node, so that the project graph has one shape (#6404). | Medium | Open | [build] | no — fixture graph with legacy edges must change |
| FR-006 | One layer-aware identity index | As an agent, I want one per-invocation index, built once per layer chain, that maps an activation token or selection (stem or declared id) to the artifact's declared id for every activatable kind, and a declared id back to its activation stem, so that every surface agrees (#6406). | High | Open | [build] | no — `QA_003_NO_FAKE_GREEN` is shown today |
| FR-007 | Declared ids in the governance base and every renderer | As an agent, I want the governance directive base, the action bundle (activated and org-required ids), `--include`, the selection block, preset application and `charter list` to use the identity index, so that every surface names declared ids and lists activated artifacts as activated (#6406). | High | Open | [build] | no — each surface has a stem ≠ id fixture assertion |
| FR-008 | Every activatable kind delivers stem ≠ id artifacts | As an agent, I want the charter service's getters for every activatable kind to accept stem and declared-id tokens, so that org artifacts are not silently dropped and lists that store declared ids keep working (#6406 sibling). | High | Open | [build] | no — org tactic `qa-seven` is absent today; declared-id token row is the ratchet control |
| FR-009 | Selections validate against every layer | As an operator, I want `selected_directives` and `selected_paradigms` (stem or declared id) validated against built-in, every org pack and the project layer, so that a valid org id is unioned into governance (#6407). | High | Open | [build] | no — `QA_003` selection fails today |
| FR-010 | An unknown selected id is dropped with a diagnostic | As an operator, I want an id no layer knows to be dropped while every other id resolves, reported in the compact text and the JSON `diagnostics` with exit 0, and named with remediation pointing at org packs and `.kittify/charter-packs/`, so that one typo does not erase governance (#6407). | High | Open | [build] | no — paired with a valid sibling id that must still resolve |
| FR-011 | Remediation text never points at `packs/built-in/` | As an operator, I want every charter selection error (directives, paradigms, template set) to point at org packs, `.kittify/charter-packs/` or `charter list`, so that I am not told to edit the installed package (#6407). | Low | Open | [build] | no — text assertion |
| FR-012 | Opt-in narrow activation on `charter activate` | As an operator, I want `charter activate <kind> <id> --only` to set the kind's list to the id plus that kind's org-required ids and to print exactly which ids stop being in force, refusing `--only` with `--preset` (exit 2), so that I can activate narrowly (#6408). | Medium | Open | [build] | no — without `--only` the full set is written, same fixture |
| FR-013 | Opt-in narrow promotion in the interview | As an operator, I want `charter interview --narrow-activation` to promote selected directives, tactics and paradigms as selection plus org-required ids and name the ids that stop being in force (JSON included), so that the interview can honour a narrow selection (#6408). | Medium | Open | [build] | no — same fixture without the option writes the full set |
| FR-014 | The materialisation warnings and the command contract say the list is frozen | As an operator, I want the "Preserved N" / "Initialized from N" warnings and the `/spec-kitty.charter` contract to say that an explicit list is frozen, that later built-ins do not activate automatically, and how to stay narrow, so that the behaviour is visible (#6408). | Medium | Open | [build] | no — text assertion on the warning |
| FR-015 | Root-first stack detection with JVM indicators | As an operator, I want the code reader to prefer root-level indicators, recognise `build.gradle.kts`, `settings.gradle(.kts)`, `gradlew` and `mvnw` as Java, and break ties between root manifests by source-file counts, so that a Gradle repository with a nested docs site reads as `java` (#6405). | Medium | Open | [build] | no — fixture reads `typescript` today; docs-only fixture is the control |
| FR-016 | Neutrality scope match by slug component | As an operator, I want the neutrality gate to match the scope tag against hyphen-separated slug components, so that `java` matches `java-style-guide` but not `javascript-style-guide` (#6405). | Low | Open | [build] | no — paired positive and negative slug |
| FR-017 | `--include` resolves declared ids and stems | As an agent, I want `charter context --include <kind>:<declared id>` and `--include <kind>:<stem>` both to resolve, so that either spelling works (#6406). | Medium | Open | [build] | no — `--include directive:qa-003-no-fake-green` fails today |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Code quality gates | Every changed Python file passes `ruff check`, `ruff format --check --force-exclude` and `mypy --strict` with zero findings and no new suppressions; every changed function has cyclomatic complexity ≤ 15. | Maintainability | High | Open |
| NFR-002 | Coverage of new code | Changed lines reach ≥ 90% diff coverage under the owning subsystem test directories. | Maintainability | High | Open |
| NFR-003 | Bounded identity scans | One `charter context` invocation scans each (kind, layer set) at most once for identity resolution, asserted structurally by a counting probe in a test. | Performance | Medium | Open |
| NFR-004 | No change to the default in-force set | For a fixture project with no org packs, no synthesized artifacts, no activation keys and no selections, the delivered directive, tactic and paradigm id sets for every built-in software-dev action, and `resolve_project_governance` output, equal a snapshot captured on the merge-base. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Absent-key semantics unchanged | The absent-key default of ADR `2026-10-06-2` and the preserve-don't-narrow rule of #4253/#4400 stay the default; narrowing is opt-in only; synthesis never writes an absent `activated_tactics` key. | Technical | High | Open |
| C-002 | Charter boundary | `specify_cli` and `runtime` reach new charter behaviour only through `charter.activation.api` or modules they already import; the identity index is exported from `charter.activation.api`. | Technical | High | Open |
| C-003 | No shipped-pack content change | No artifact under `packs/built-in/` other than the `/spec-kitty.charter` mission-step prompt is edited; `packs/internal/` is untouched; if any pack file changes, the pack manifest is regenerated with `spec-kitty charter pack regenerate-graph`. | Technical | High | Open |
| C-004 | `applies` stays inert for authored content | The gate refusing authored `applies` edges in shipped packs stays green; this Mission stops synthesis from emitting `applies` rather than making `applies` traversed. | Technical | High | Open |
| C-005 | Terminology | Prose uses Mission, never the retired term; `tests/architectural/test_no_legacy_terminology.py` stays green. | Business | High | Open |
| C-006 | Single language field | Synthesis evidence keeps one `primary_language` / `scope_tag`; multi-language evidence is out of scope. | Technical | Medium | Open |
| C-007 | Absent-key base membership unchanged | The identity index changes how ids are spelled, not which artifacts the absent-key governance base contains. | Technical | High | Open |

### Key Entities

- **Activation token**: an entry in an `activated_<kind>` list; usually a file stem, sometimes a declared id.
- **Declared id**: the `id:` field inside an artifact file, and the id a DRG node uses.
- **Layer chain**: built-in, every org pack declared in `charter_packs.org.packs`, then the project pack layer under `.kittify/charter-packs/`.
- **Identity index**: the per-invocation, layer-aware stem ↔ declared-id map per kind (FR-006).
- **Synthesized node**: a project-layer DRG node written by `charter synthesize`; reconcile assigns it every edge derived for it.
- **Selection**: `governance.charter.selected_<kind>` in `charter.yaml`, unioned onto the activated base.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the explicit-activation synthesized fixture, 100% of `how-we-apply-*` tactics whose directive is activated are delivered for `implement`, and 0% of those whose directive is deactivated. — [build] · no-op passable: no
- **SC-002**: With the fixture org pack, zero context or charter surfaces (compact text, JSON, `--include`, `charter list`) show a guessed id such as `QA_003_NO_FAKE_GREEN`. — [build] · no-op passable: no
- **SC-003**: With one unknown id in `selected_directives`, the number of delivered directives equals the count without that id, and the unknown id appears in diagnostics. — [build] · no-op passable: no
- **SC-004**: `charter activate toolguide gherkin --only` on a fresh project writes exactly one entry and lists every other formerly effective toolguide as no longer in force. — [build] · no-op passable: no
- **SC-005**: The issue's Gradle/Java fixture is detected as `java`; the docs-only fixture stays `typescript`. — [build] · no-op passable: no

## Assumptions

- The charter repository named in the issues has no org packs or synthesized graph; reproduction uses fixture packs and scratch projects built in tests.
- The reporter's `"tactics": []` most likely came from loading context without `--mission-type` (a typeless Mission skips DRG resolution); the real defect is the inert edge plus activation filtering, covered by FR-001 to FR-005.
- Projects synthesized before this change re-run `charter synthesize` to pick up FR-001 to FR-005; no upgrade migration is added (operator decision).
- Kotlin is not added as a language token; Gradle and Maven builds read as `java` (follow-up for a kotlin vocabulary).

## Out of Scope / Follow-ups

- Multi-language synthesis evidence and reconciling `infer_repo_languages` with the code reader.
- Edges for synthesized styleguides and the project mission-type directive (`PROJECT_001`), which nothing reaches today.
- Layer-aware validation of the template set selection (only its remediation text changes here) and validation of `selected_tactics` / `selected_styleguides` / `selected_toolguides` / `selected_procedures` / `selected_agent_profiles`, which `resolve_project_governance` does not validate today.
- `charter activate directive DIRECTIVE_001` accepting a declared id instead of only a stem.
- `charter consistency_check` comparing activation tokens against `references.yaml`.
