# Mission Specification: Activate output and identity

**Mission Branch**: `issue-6457-activate-output-identity` (planning base and merge target)
**Created**: 2026-10-27
**Status**: Draft
**Input**: Operator brief M3 plus operator scope addition 2026-10-27 (#6527 local slice, #6433, #6435; Decision Moments `scope_6527`, `unknown_token_consistency`, `compile_unknown_token`, `ledger_migration`, `no_stem_id`, `step_contracts`). Original brief: M3 "Activate output and identity": #6457 (widened), #6459, #6458 (warning part only), #6403 (docs only). Discovery answered by the brief plus Decision Moments `only_output`, `skill_freeze_warning` and `scope` (all resolved).

## Intent Summary

- **Primary actor**: an operator running `spec-kitty charter activate` against a project, plus a maintainer reading the doctrine-layering and glossary docs.
- **Trigger**: activating one artifact, with or without `--only`, while the kind's activation key is absent or its effective set cannot be resolved; or reading how an activation token resolves and how a pack with no `pack_level` loads.
- **Desired outcome**: the command says exactly what it wrote and never contradicts itself; skill activation tells the operator that the org's required skills are now frozen; the "file name beats declared id" rule is pinned by a test and documented; the two glossary entries describe the shipped `PACK_LEVEL_MISSING` behaviour.
- **Invariant**: output changes only. What is written to the activation ledger, exit codes and the allow-list versus org-required-floor semantics are unchanged (those belong to epic #6518 with #6684/#6685).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - `--only` output says what it wrote (Priority: P1)

An operator narrows a kind with `charter activate <kind> <id> --only`. Today, on an absent `mission-type` key, the command claims it initialized from 4 mission types and also that the effective set could not be resolved, while it wrote 1 entry.

**Why this priority**: contradictory output on a narrowing command erodes trust in what is in force (#6457, operator-widened to every kind whose effective set cannot be resolved).

**Independent Test**: run `activate mission-type software-dev --only` on an absent key and `activate toolguide gherkin --only` with an unreadable org pack; read the output and the written list.

**Acceptance Scenarios**:

1. **Given** an absent `mission-type` key, **When** the operator runs `activate mission-type software-dev --only`, **Then** the output names the 1 entry now listed, reports 0 no longer in force, and prints no preservation or "could not be resolved" warning.
2. **Given** a kind whose effective set cannot be resolved (an org pack that cannot be read), **When** the operator runs `activate <kind> <id> --only`, **Then** exactly one warning says what stopped being in force cannot be listed and gives the reason, and no "initialized from N ids" warning appears.
3. **Given** any `--only` run, **When** it succeeds, **Then** a line names how many entries the kind now lists and which.

### User Story 2 - Skill activation warns that org-required skills are frozen (Priority: P2)

An operator activates a skill. The absent `activated_skills` key puts the org packs' current `required_skills` in force; writing the key freezes that list, so a skill an org later requires never reaches the project.

**Why this priority**: silent loss of future org policy (#6458, operator ruling 2026-10-19: warn on both paths, stop recommending `--only` for skills).

**Independent Test**: activate a skill with and without `--only` on an absent key; read the warnings.

**Acceptance Scenarios**:

1. **Given** an absent `activated_skills` key, **When** the operator runs `activate skill x`, **Then** a warning says the org packs' required skills are frozen at their current values and a later addition will not reach this project, and the output does not recommend `--only`.
2. **Given** any `activated_skills` state, **When** the operator runs `activate skill x --only`, **Then** the same warning prints.
3. **Given** a kind whose absent key means "every available artifact" (e.g. toolguide), **When** it is activated with or without `--only`, **Then** the freeze warning does not print.

### User Story 3 - Activation token resolution is pinned and documented (Priority: P3)

A maintainer needs to know that an activation token matching a file name resolves to that file's artifact, even when another layer declares that token as its id.

**Why this priority**: an unpinned rule a refactor could reverse unnoticed (#6459).

**Independent Test**: a resolver test with a built-in artifact declaring id `foo` in a differently named file and a higher-layer file named `foo`; activate `foo`; the higher-layer artifact is in force and the built-in one is not.

**Acceptance Scenarios**:

1. **Given** that fixture, **When** the runtime gates the kind by the activation list `[foo]`, **Then** the higher-layer artifact is admitted and the built-in artifact that declares `foo` is not.
2. **Given** the doctrine layering doc, **When** a maintainer reads the precedence section, **Then** it says a file name beats a declared id regardless of layer, and the resolver's gating docstring links that note.

### User Story 4 - Glossary describes `PACK_LEVEL_MISSING` as shipped (Priority: P3)

The Pack Level and Charter Pack glossary entries claim loading refuses a pack with no `pack_level`; the loader warns and loads during the ADR 2026-10-11-2 deprecation window (#6403).

**Independent Test**: read both entries against `org_pack_loader.py` and `pack_validator.py`.

**Acceptance Scenarios**:

1. **Given** the two entries, **When** read, **Then** `PACK_LEVEL_MISMATCH` is still a refusal, and `PACK_LEVEL_MISSING` (no field, or an org pack with no `pack.yaml`) is a non-blocking diagnostic during the window (warning on load, advisory in `charter pack validate`) that becomes a refusal once the window closes, naming ADR 2026-10-11-2.

### Edge Cases

- `--only` on a present list: unchanged behaviour (narrows, reports what dropped); only the new count line is added.
- `--only` with an id on the deny list: the existing "Cleared the exclusion" line still prints.
- Skill activation on a present `activated_skills` key without `--only`: no freeze warning (nothing changes state; the list was already explicit).
- A skill already in the org-required set activated from an absent key: the freeze warning still prints, since the key is now written.
- Mission-type `--only` on a present list: dropped types are still reported; no unresolved warning.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | `--only` suppresses preservation warnings | As an operator, I want `--only` to print no absent-key preservation warning so that its output never claims a set it did not write. | High | Open | [build] | no — the same fixture without `--only` still prints the preservation warning (positive control) |
| FR-002 | Mission-type absent key is "nothing in force" | As an operator, I want `--only` on an absent mission-type key to report 0 dropped without an "unresolved" warning, because nothing was in force. | High | Open | [build] | no — today's output carries the warning (red-first) |
| FR-003 | One unresolved warning with its reason | As an operator, I want `--only` on a kind whose effective set cannot be resolved to print one warning that gives the reason. | High | Open | [build] | no — asserts the reason text, absent today |
| FR-004 | `--only` names what is now listed | As an operator, I want `--only` to print the count and ids the kind now lists. | High | Open | [build] | no — new line absent today |
| FR-005 | Skill freeze warning on the plain path | As an operator, I want `activate skill <id>` on an absent key to warn that org-required skills are frozen, without recommending `--only`. | High | Open | [build] | no — same fixture on a present key prints none (positive control) |
| FR-006 | Skill freeze warning on `--only` | As an operator, I want `activate skill <id> --only` to print the same warning. | High | Open | [build] | no — absent today |
| FR-007 | Freeze warning only for "required"-when-absent kinds | As an operator, I want the freeze warning only for kinds whose absent key means "org-required only" (today `skill`, the interview-exclusion rule). | Medium | Open | [build] | no — toolguide control asserts absence while skill asserts presence |
| FR-008 | Pin stem-first gating | As a maintainer, I want a resolver test that fails if a built-in declared id wins over a higher-layer file name. | Medium | Open | [ratchet] | no — includes a positive control that the built-in artifact is otherwise admitted |
| FR-009 | Document stem-first gating | As a maintainer, I want the layering doc to state that a file name beats a declared id regardless of layer, linked from the resolver docstring. | Medium | Open | [build] | yes — docs; verified by review |
| FR-010 | Correct the `PACK_LEVEL_MISSING` glossary clause | As a reader, I want both glossary entries to describe `PACK_LEVEL_MISSING` as non-blocking during the ADR 2026-10-11-2 window and a refusal after it. | Medium | Open | [build] | yes — docs; verified by review |
| FR-011 | Accept URNs on input | As an operator, I want every activation input (activate, deactivate, presets, compile) to accept a `<kind>:<id>` URN as well as a file stem or declared id, resolved through the one identity index. | Medium | Open | [build] | no — a URN is refused today (red-first) |
| FR-012 | Effective set in stems (#6435) | As an operator, I want the effective set to list each artifact once, by its file stem, so that an absent-key materialisation never stores both spellings of an org or project artifact whose stem differs from its declared id. | High | Open | [build] | no — today the toolguide fixture yields 20 ids for 19 artifacts |
| FR-013 | Presets store stems | As an operator, I want `charter activate --preset` to store stems for listed ids and unioned org-required ids. | Medium | Open | [build] | no — an org preset listing `DIRECTIVE_024` stores the declared id today |
| FR-014 | Every writer stores stems | As a maintainer, I want one test over every activation writer (activate incl. absent-key and `--only`, cascade, deactivate, presets, interview both modes, org-required union) proving only stems are stored, for an org and a project stem≠id artifact and a built-in directive; a declared id whose file name another layer uses for a different id is refused with a message naming the conflict (Decision `file_name_collision`). | High | Open | [build] | no — red today for W2/W6/W7/W8 |
| FR-015 | Step contracts in the identity index | As a maintainer, I want built-in mission-step-contract files indexed by `IdentityIndex`, so the one identity authority covers every kind. | Medium | Open | [build] | no — index returns None for a built-in step-contract stem today |
| FR-016 | Compile resolves through the identity index (#6433) | As an operator, I want `charter compile` to resolve activation tokens (stem, declared id, URN) through `IdentityIndex` with the project layer; a truly unknown token still fails compile (Decision `compile_unknown_token`). | Medium | Open | [build] | no — a URN fails compile today; positive control: an unknown token still fails |
| FR-017 | Consistency check resolves through the identity index (#6433) | As an operator, I want `charter consistency-check` to resolve through one `IdentityIndex` covering the project layer, stop reporting stored declared ids and project-layer artifacts as unknown, report each unknown token once, and keep it (warn and keep). | Medium | Open | [build] | no — today a project-layer artifact is reported unknown in both spellings |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Quality gates | Touched files pass `ruff check`, `ruff format --check --force-exclude` and `mypy` with zero new findings; no new `noqa` / `type: ignore`. | Maintainability | High | Open |
| NFR-002 | Complexity | Every touched function stays at cyclomatic complexity <= 15. | Maintainability | High | Open |
| NFR-003 | Coverage | Diff coverage of changed source lines >= 90%. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Output only (WP01-WP03) | For the #6457/#6458/#6459/#6403 work, the activation ledger content written by every `activate` path, exit codes and allow-list / org-required-floor semantics stay byte-identical (epic #6518, #6684, #6685 own semantics). The #6527 local slice (FR-011..FR-017) changes only the *spelling* stored (stems), never which artifacts are in force. A declared id whose file name another layer's file uses for a different id is a pack-content collision: writers refuse it with a message naming the conflict (Decision `file_name_collision`, which withdrew `no_stem_id` / `no_stem_id_in_force`) | Technical | High | Open |
| C-005 | #6527 local slice only | ACL `to_contract` declared-id export and the `activation_invalid` refusal stay with #6520 / epic #6518. No normalising ledger migration (Decision `ledger_migration`). No change to allow-list vs org-required-floor semantics. | Technical | High | Open |
| C-002 | No precedence change | Stem-first gating is pinned, not changed (#6459 is a Task). #6435 (spelling) was folded into this mission by the operator's #6527 scope addition and is fixed here. | Technical | High | Open |
| C-003 | Docs fix only for #6403 | No change to the pack loader or validator switch; the "tier" wording (#6439) is out of scope. | Technical | Medium | Open |
| C-004 | Canonical warning authority | Warning texts live once in `charter.activation.activation_engine`; the CLI renders them without special-casing. | Technical | Medium | Open |

### Key Entities

- **Preservation warning**: the absent-key materialisation message ("Initialized from the N ..."), meaningful only when a list is materialised, never under `--only`.
- **Narrow warning**: the `--only` message for an unresolvable effective set.
- **Org-required freeze warning**: the message for a kind whose absent key puts only org-required ids in force, printed whenever its key is written from absent or rewritten by `--only`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `activate mission-type software-dev --only` on an absent key prints 0 contradictory warnings and names 1 written entry — [build] · no-op passable: no
- **SC-002**: The skill freeze warning prints on both activation paths for skills and on 0 paths for every other kind under test — [build] · no-op passable: no
- **SC-003**: A test goes red when gating is changed to prefer a built-in declared id over a higher-layer file name — [ratchet] · no-op passable: no
- **SC-004**: Both glossary entries agree with the shipped loader behaviour for `PACK_LEVEL_MISSING` — [build] · no-op passable: yes
- **SC-005**: Every activation writer stores only stems for the stem≠id fixtures (0 declared ids or URNs stored) — [build] · no-op passable: no
- **SC-006**: Compile and the consistency check accept the same tokens as the runtime gate; 0 false "unknown" reports for stored declared ids or project-layer artifacts — [build] · no-op passable: no

## Assumptions

- `mission_type_activations` is an activation ledger: an absent key puts no mission type in force (`effective_set._LEDGER`).
- The freeze applies whether or not an org currently declares `required_skills`: a present `activated_skills` list stops the org-required default from being read (`pack_context.py`), so later additions never apply.
