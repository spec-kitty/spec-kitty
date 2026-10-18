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

### User Story 1 - Synthesized tactics reach the action they apply to (Priority: P1)

An operator runs `charter synthesize`; it writes one `how-we-apply-<directive>` tactic per active directive. When an agent loads action context for an action in which that directive is delivered, the tactic is delivered too.

**Why this priority**: synthesis is the main way a project expresses its own practice; today none of it reaches an agent (#6404).

**Independent Test**: synthesize in a scratch project, then `charter context --action implement --mission-type software-dev --json` lists the `how-we-apply-*` tactic of every delivered directive.

**Acceptance Scenarios**:

1. **Given** a synthesized project whose directive `DIRECTIVE_024` is delivered for `implement`, **When** the operator loads `implement` action context, **Then** `how-we-apply-directive-024` is in the delivered tactics.
2. **Given** the same project, **When** synthesis runs again, **Then** the project graph holds each directive-to-tactic edge exactly once, and `--prune` does not remove it.
3. **Given** a project synthesized before this change, **When** the operator re-runs `charter synthesize`, **Then** the old `applies` edges are replaced by the new edges.

### User Story 2 - Org-pack artifacts are named and delivered by their declared id (Priority: P1)

An operator activates an org-pack directive whose file is `qa-003-no-fake-green.directive.yaml` and whose declared id is `QA_003`. Every context surface names it `QA_003`, and `--include directive:QA_003` resolves it. The same holds for an org tactic, paradigm, styleguide, toolguide or procedure whose file stem differs from its declared id: it is delivered, not silently dropped.

**Why this priority**: wrong ids cannot be resolved by an agent and silently hide governance (#6406 and its sibling defect for non-directive kinds).

**Independent Test**: with a fixture org pack, compact context lists `QA_003`, never `QA_003_NO_FAKE_GREEN`; an org tactic with stem `qa-tactic-seven` and id `qa-seven` appears in `ActiveCharterService.tactics` and in action context.

**Acceptance Scenarios**:

1. **Given** an activated org directive with stem ≠ id, **When** compact or JSON context is rendered, **Then** the directive id shown is the declared id, with its org-pack source.
2. **Given** an activated org tactic with stem ≠ id, **When** the charter service lists active tactics, **Then** the declared id is present.
3. **Given** a built-in directive activated by its stem, **When** context is rendered, **Then** its id is unchanged from today (`DIRECTIVE_NNN`).

### User Story 3 - An org-pack id in a selection is honoured, an unknown one is reported (Priority: P1)

An operator adds `QA_003` (an org-pack directive) to `governance.charter.selected_directives`. Action context unions it onto the activated set. If the operator adds an id no layer knows, that id alone is dropped with a diagnostic naming where org and project artifacts live; every other directive, paradigm, tool and template set still resolves.

**Why this priority**: today one org id erases all governance behind a success exit (#6407).

**Independent Test**: with the fixture org pack, `selected_directives: [QA_003]` yields `QA_003` in the delivered directives; `selected_directives: [QA_003, NOPE_999]` yields every directive plus a diagnostic naming `NOPE_999`.

**Acceptance Scenarios**:

1. **Given** `selected_directives: [QA_003]` and the org pack declared, **When** context is rendered, **Then** `QA_003` is delivered and no "governance unresolved" diagnostic appears.
2. **Given** `selected_directives: [NOPE_999]`, **When** context is rendered, **Then** the activated directives are still delivered, the diagnostic names `NOPE_999`, and the remediation text does not tell the operator to edit `packs/built-in/`.
3. **Given** an org paradigm in `selected_paradigms`, **When** context is rendered, **Then** it is accepted the same way.

### User Story 4 - The operator can narrow activation deliberately (Priority: P2)

An operator who wants only a few artifacts of a kind in force runs `charter activate <kind> <id> --only`, or the interview's narrow option. An absent key is then initialised to just the selection plus any org-required ids, and the command prints what stops being in force. Without the option, behaviour is unchanged, and the warning now says that the materialised list is frozen (built-ins shipped later do not activate automatically). The `/spec-kitty.charter` command contract explains which path keeps selections narrow.

**Why this priority**: the contract asks for narrow selections but no CLI path delivers one (#6408). Lower than P1 because the default is deliberate and not wrong.

**Independent Test**: in a fresh project, `charter activate toolguide gherkin --only` writes `activated_toolguides: [gherkin]` (plus org-required ids) and lists the toolguides that stop being in force; without `--only` it writes the full effective set as today.

**Acceptance Scenarios**:

1. **Given** no `activated_toolguides` key, **When** `charter activate toolguide gherkin --only`, **Then** the key holds `gherkin` plus org-required toolguides and the output names what stopped being in force.
2. **Given** no key and no `--only`, **When** `charter activate toolguide gherkin`, **Then** the result is identical to today and the warning says the list is now frozen.
3. **Given** the interview with its narrow option and `--selected-directives DIRECTIVE_001`, **When** it promotes selections, **Then** `activated_directives` holds the selection plus org-required ids only.
4. **Given** an existing (present) key, **When** `--only` is passed, **Then** the key is replaced by the selection plus org-required ids and the output names what stopped being in force.

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

- An activation token that resolves in no layer: the identity seam keeps today's warning-and-normalise fallback for activation lists (no regression for legacy stems), but selections report it as unknown.
- The same declared id in two layers: the layer chain's existing precedence (project, then org packs last-declared-first, then built-in) decides.
- A directive whose stem is digit-led (`001-...`): its id stays `DIRECTIVE_001`.
- A tactic synthesized for a directive that is not delivered for the action: the tactic is not delivered for that action either.
- `--only` on a kind with org-required ids: required ids always remain.
- `--only` with `--cascade`: narrowing applies to the named artifact's own kind only; cascaded kinds keep today's behaviour.
- A repository with root manifests for two languages: source-file counts decide; ties keep today's indicator priority.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Synthesis emits a traversable directive-to-tactic edge | As an operator, I want synthesis to link each directive to its how-we-apply tactic with the `suggests` relation from the directive, so that the tactic is delivered wherever the directive is (#6404). | High | Open | [build] | no — the `implement` context test fails today (tactic absent) |
| FR-002 | Synthesis reconcile owns edges by their synthesized endpoint | As an operator, I want re-synthesis and `--prune` to treat an edge whose target is a synthesized node as synthesis-owned, so that the new edge is neither duplicated nor pruned (#6404). | High | Open | [build] | no — a second synthesize run must yield exactly one edge, with a positive control that the edge exists |
| FR-003 | Re-synthesis replaces legacy `applies` edges | As an operator of an already-synthesized project, I want a re-run of `charter synthesize` to drop the old tactic-to-directive `applies` edges, so that the project graph has one shape (#6404). | Medium | Open | [build] | no — fixture graph with legacy edges must change |
| FR-004 | One activation-token to declared-id authority | As an agent, I want every charter surface that turns an activation token or selection into an artifact id to resolve it through the layer chain and the artifact's declared `id:`, so that ids are real and consistent (#6406). | High | Open | [build] | no — `QA_003_NO_FAKE_GREEN` is shown today |
| FR-005 | Declared ids for every kind in the charter service | As an agent, I want active tactics, paradigms, styleguides, toolguides and procedures whose stem differs from their declared id to be delivered, so that org artifacts are not silently dropped (#6406 sibling). | High | Open | [build] | no — org tactic `qa-seven` is absent today |
| FR-006 | Selections validate against every layer | As an operator, I want `selected_directives` and `selected_paradigms` validated against built-in, every org pack and the project layer, so that a valid org id is unioned into governance (#6407). | High | Open | [build] | no — `QA_003` selection fails today |
| FR-007 | An unknown selected id is dropped with a diagnostic | As an operator, I want an id that no layer knows to be dropped with a diagnostic that names it and points at org packs and `.kittify/charter-packs/`, so that one typo does not erase every directive (#6407). | High | Open | [build] | no — paired with a valid sibling id that must still resolve |
| FR-008 | Opt-in narrow activation on `charter activate` | As an operator, I want `charter activate <kind> <id> --only` to set the kind's list to the selection plus org-required ids and to print what stops being in force, so that I can activate narrowly (#6408). | Medium | Open | [build] | no — without `--only` the full set is written, same fixture |
| FR-009 | Opt-in narrow promotion in the interview | As an operator, I want an interview option that promotes selections narrowly (selection plus org-required ids), so that `charter interview` can honour a narrow selection (#6408). | Medium | Open | [build] | no — same fixture without the option writes the full set |
| FR-010 | The materialisation warning and the command contract say the list is frozen | As an operator, I want the "Preserved N" / "Initialized from N" warnings and the `/spec-kitty.charter` contract to say that an explicit list is frozen and how to stay narrow, so that the behaviour is visible (#6408). | Medium | Open | [build] | no — text assertion on the warning |
| FR-011 | Root-first stack detection with JVM indicators | As an operator, I want the code reader to prefer root-level indicators, recognise `build.gradle.kts`, `settings.gradle(.kts)`, `gradlew` and `mvnw` as Java, and break ties by source-file counts, so that a Gradle repository with a nested docs site reads as `java` (#6405). | Medium | Open | [build] | no — fixture reads `typescript` today |
| FR-012 | Neutrality scope match by slug component | As an operator, I want the neutrality gate to match the scope tag against slug components rather than as a substring, so that `java` does not match `javascript-*` (#6405). | Low | Open | [build] | no — `javascript-style-guide` is treated as java-scoped today |
| FR-013 | `--include` resolves declared ids and stems | As an agent, I want `charter context --include directive:<declared id>` and `--include directive:<stem>` both to resolve, so that either spelling works (#6406). | Medium | Open | [build] | no — `--include directive:qa-003-no-fake-green` fails today |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Code quality gates | Every changed Python file passes `ruff check`, `ruff format --check --force-exclude` and `mypy --strict` with zero findings and no new suppressions; every changed function has cyclomatic complexity ≤ 15. | Maintainability | High | Open |
| NFR-002 | Coverage of new code | Changed lines reach ≥ 90% diff coverage under the owning subsystem test directories. | Maintainability | High | Open |
| NFR-003 | Context latency | `charter context --action implement` on the fixture project takes no more than 20% longer than on `main` (identity resolution reuses one resolved layer chain per call). | Performance | Medium | Open |
| NFR-004 | No change to the default in-force set | For a project with no activation keys and no selections, the delivered directive, tactic and paradigm id sets for every built-in action are identical before and after this Mission, except for synthesized tactics newly reachable through FR-001. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Absent-key semantics unchanged | The absent-key default of ADR `2026-10-06-2` and the preserve-don't-narrow rule of #4253/#4400 stay the default; narrowing is opt-in only. | Technical | High | Open |
| C-002 | Charter boundary | `specify_cli` reaches new charter behaviour only through `charter.activation.api` / `charter.offering.api` or existing module seams already imported there; no new reach into charter internals from `runtime` or `specify_cli`. | Technical | High | Open |
| C-003 | No shipped-pack content change | No artifact under `packs/built-in/` other than the `/spec-kitty.charter` mission-step prompt is edited; `packs/internal/` is untouched. If any pack file changes, the pack manifest is regenerated with `spec-kitty charter pack regenerate-graph`. | Technical | High | Open |
| C-004 | `applies` stays inert for authored content | The architectural gate refusing authored `applies` edges in shipped packs stays green; this Mission stops synthesis from emitting `applies` rather than making `applies` traversed. | Technical | High | Open |
| C-005 | Terminology | Prose uses Mission, never the retired term; `tests/architectural/test_no_legacy_terminology.py` stays green. | Business | High | Open |
| C-006 | Single language field | Synthesis evidence keeps one `primary_language` / `scope_tag`; multi-language evidence is out of scope. | Technical | Medium | Open |

### Key Entities

- **Activation token**: an entry in an `activated_<kind>` list; a file stem today, sometimes a declared id.
- **Declared id**: the `id:` field inside an artifact file, and the id a DRG node uses.
- **Layer chain**: built-in, every org pack declared in `charter_packs.org.packs`, then the project pack layer under `.kittify/charter-packs/`.
- **Synthesized node**: a project-layer DRG node written by `charter synthesize`; owns its edges for reconcile purposes.
- **Selection**: `governance.charter.selected_<kind>` in `charter.yaml`, unioned onto the activated base.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a synthesized fixture project, 100% of `how-we-apply-*` tactics whose directive is delivered for `implement` appear in `implement` action context. — [build] · no-op passable: no
- **SC-002**: With the fixture org pack, zero context surfaces (compact text, JSON, `--include`) show a guessed id such as `QA_003_NO_FAKE_GREEN`. — [build] · no-op passable: no
- **SC-003**: With one unknown id in `selected_directives`, the number of delivered directives equals the count without that id. — [build] · no-op passable: no
- **SC-004**: `charter activate <kind> <id> --only` on a fresh project writes at most 1 + (org-required count) entries for that kind. — [build] · no-op passable: no
- **SC-005**: The issue's Gradle/Java fixture is detected as `java`; the docs-only fixture stays `typescript`. — [build] · no-op passable: no

## Assumptions

- The charter repository named in the issues has no org packs or synthesized graph; reproduction uses fixture packs and scratch projects built in tests.
- Projects synthesized before this change are expected to re-run `charter synthesize` to pick up FR-001; no upgrade migration is added (operator decision).
- Kotlin is not added as a language token; a Kotlin-DSL Gradle build with Java sources reads as `java`, and `.kt`-majority repositories read as `java` too until a kotlin vocabulary exists (follow-up).

## Out of Scope / Follow-ups

- Multi-language synthesis evidence and reconciling `infer_repo_languages` with the code reader.
- Edges for synthesized styleguides and the project mission-type directive (`PROJECT_001`), which nothing reaches today.
- Adding synthesized tactics to an explicit `activated_tactics` list automatically.
- `charter activate directive DIRECTIVE_001` accepting a declared id instead of only a stem.
