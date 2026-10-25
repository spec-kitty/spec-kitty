# Mission Specification: Upgrade keeps an absent activation key absent

**Mission Branch**: `issue-6629-upgrade-seeded-activation-provenance`
**Created**: 2026-10-25
**Status**: Draft
**Input**: GitHub issue #6629 (refs #6549, #2577, #4785, #6408). The operator ruled "fix now, as a mission". The semi-auto runner resolved the fix shape in Decision Moment `01M5T0ZHT04J7PWFV9DRCEVVGY` as the issue's first suggested shape: do not materialise an absent key when nothing would drop. The PR records it as a question for the operator to confirm.

## Intent Summary

- **Primary actor:** a project owner who ran the charter interview before the activation ledger existed. Their project has interview selections (`answers.yaml` `selected_<kind>`) and no `activated_<kind>` key, so every available artifact of that kind is in force.
- **Trigger:** they run `spec-kitty upgrade`.
- **Desired outcome:** after the upgrade, `charter synthesize` behaves as it does for a project with no activation key. It takes the fresh-project seed and demands no companion tactic per directive, so `agent action implement` can then proceed.
- **Rule that must always hold (zero drop):** every artifact in force before the upgrade, and every interview-selected id that is not on a deny list, is in force after it. An upgrade never makes an artifact stop applying, and it never changes a deny list.
- **Boundary:** this mission changes what an *upgrade* writes. Operator-time writers (the interview, a first `charter activate`, the org-charter union) keep their current behaviour; #6408 owns them.

## Open Questions (for the operator)

1. **Fix shape.** Decision Moment `01M5T0ZHT04J7PWFV9DRCEVVGY` chose the issue's first shape (an upgrade never materialises an absent key) over a provenance marker in the activation ledger. The runner made this call under the "fix now" ruling. Please confirm it.
2. **Projects already seeded by an earlier build.** The reporter's project is one of them. They keep their list (C-004, #6499), and the upgrade only warns them, naming the narrowing commands (FR-008). Should a later mission reset a list that is set-equal to the full in-force set? `_charter_pack_cutover_resets` does this for released defaults, which is a precedent.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upgrade a pre-ledger project whose interview named only built-in artifacts (Priority: P1)

A project owner has an interview record that selects 9 built-in directives and 1 paradigm. The project has no activation list for either kind. They upgrade. The upgrade does not write a full list of 38 directives (or 14 paradigms), so `charter synthesize` takes the fresh-project seed and `implement` can proceed after it.

**Why this priority**: this is the reported defect (#6629, P1). It blocks every work package of an otherwise ready Mission.

**Independent Test**: build that project shape with a version recorded below the promotion's, so the ledger-adoption backfill does not settle it. Run every pending migration through the runner. Then check that no `activated_<kind>` key exists for any of the 8 promoted kinds, that the synthesis request demands zero directive companion tactics, and that `charter synthesize --dry-run --json` reports `fresh_project_seed_dry_run`.

**Acceptance Scenarios**:

1. **Given** a project with built-in-only `selected_directives` and `selected_paradigms` and no activation key, **When** the owner runs the upgrade, **Then** no `activated_<kind>` key exists on the activation surface afterwards, and every selected artifact is still in force.
2. **Given** that upgraded project, **When** the owner runs `charter synthesize`, **Then** the synthesis request lists zero directives for companion tactics and the fresh-project seed applies, the same as for a project that never had the key.

---

### User Story 2 - Upgrade a project whose interview selection is not yet mirrored into an explicit list (Priority: P1)

A project owner has an explicit `activated_directives` list, and the interview selected one more directive that the list does not name. The upgrade appends that directive to the list on the authoritative activation surface, so nothing selected is dropped.

**Why this priority**: this is the zero-drop guarantee the shipped migration exists for. It must survive the change.

**Independent Test**: on a project whose activation keys live in the activation ledger, run the upgrade and check that the ledger list gains exactly the missing directive and that `.kittify/config.yaml` gains no activation key.

**Acceptance Scenarios**:

1. **Given** a project with an explicit list that omits an answers-selected directive, **When** the owner upgrades, **Then** the list on the authoritative surface gains that directive, and every entry it held before is still there.
2. **Given** the same project upgraded once, **When** the owner upgrades again, **Then** nothing changes and nothing is committed.

---

### User Story 3 - Repeat upgrades converge (Priority: P2)

A project owner whose activation keys were already moved out of `.kittify/config.yaml` (by the charter fold or into the activation ledger) upgrades again. The promotion no longer reads `config.yaml` as the authority, so it never writes a second full directive list there (the #6549 mechanism).

**Why this priority**: same migration, same seeding call, related reports; fixing the read surface removes it at no extra cost.

**Independent Test**: on a project whose keys live in the activation ledger and whose interview selections are already in force, run the upgrade twice and check that `config.yaml` never gains an `activated_*` key and the second run reports nothing to do.

**Acceptance Scenarios**:

1. **Given** a project whose activation keys live in the activation ledger, **When** the owner upgrades twice, **Then** `.kittify/config.yaml` has no `activated_*` key after either run.

---

### Edge Cases

- **Interview id that resolves to no artifact:** reported as a warning naming the id, never silently dropped, and the key is left as it was.
- **Interview id the owner deactivated:** neither seeded nor appended, and the deny list is byte-identical afterwards.
- **Absent key:** never written. A resolved interview id is then either in force already (the key's absence puts every available artifact in force) or names no available artifact, and an allow-list entry for that would bring nothing into force.
- **Present list that spells an artifact by its declared id (#6423):** an interview id naming the same artifact in another spelling is not appended.
- **Operator narrows after the upgrade:** for example, `charter activate <kind> <id> --only`. A later upgrade does not append the interview ids back, because the promotion is recorded applied on its first run.
- **Project whose activation was already seeded by an earlier build:** its list stays as it is (#6499). When the list is set-equal to the full in-force set and the interview selected only some of it, the upgrade warns and names `charter interview --narrow-activation` and `charter activate <kind> <id> --only` (#6408). Narrowing makes `charter synthesize` demand companion tactics only for the kept directives. It does not restore the fresh-project seed, because a narrowed list is still an operator's activation.
- **Mission-step-contract selections:** they do not resolve today. This is pre-existing and shared with the shipped migration. They are warned about, as before, and their resolver is out of scope.
- **Project with no `answers.yaml`, or one with no selections:** nothing to do.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Absent key stays absent | As a project owner whose interview selected only artifacts already in force, I want the upgrade to leave every absent `activated_<kind>` key of the 8 promoted kinds absent, so that the project keeps its "nothing chosen yet" state. | High | Open | [build] | no — red on main: the shipped migration writes a 38-entry directive list and a 14-entry paradigm list |
| FR-002 | Synthesis after upgrade matches an absent key | As a project owner, I want `charter synthesize` after the upgrade to demand zero directive companion tactics and take the fresh-project seed, so that `implement` can proceed afterwards. | High | Open | [build] | no — red on main through the same end-to-end fixture |
| FR-003 | Answers-only ids still promoted into a present list | As a project owner with an explicit list, I want an interview-selected id that the list omits (in any spelling) to be appended on the authoritative activation surface, so that nothing selected drops. | High | Open | [ratchet] | yes — paired with a positive assertion on the same fixture that the list gains exactly that id; a do-nothing successor fails it |
| FR-004 | Promotion uses the authoritative activation surface | As a project owner whose activation keys live in the activation ledger, I want the upgrade to read and write activation through the activation ledger seam, so that it never writes a stale `activated_*` copy into `config.yaml`. | High | Open | [build] | no — red on main: the shipped migration writes `config.yaml` on a ledger project |
| FR-005 | Shipped migration superseded, not edited | As a maintainer, I want `unify_charter_activation_promote_answers` registered as a recorded no-op superseded by the new migration, with its module byte-identical and its content hash unchanged, so that recorded history never reads as drift. | High | Open | [build] | yes — paired with FR-001 on the end-to-end fixture, which fails while the shipped migration still runs |
| FR-006 | Deactivations and unresolved ids honoured | As a project owner, I want a deactivated id to be neither seeded nor appended and its deny list left byte-identical, and an unresolvable interview id reported as a warning, so that the upgrade never changes a deactivation and never drops silently. | Medium | Open | [ratchet] | no — own positive assertions: deny list bytes equal, warning text present |
| FR-007 | One run settles it, and only where needed | As a project owner, I want the promotion recorded as applied on its first run, with or without interview selections. It must append nothing when the Migration Ledger records the superseded promotion as applied. Then no upgrade ever appends back interview ids I removed from a list. | High | Open | [build] | no — red on three runner fixtures: narrowing after the upgrade, narrowing before it on an rc7 project, and an interview written after a first upgrade |
| FR-008 | Hint for an already-seeded list | As the owner of a project an earlier build seeded, I want the upgrade to warn, without changing anything, when a present list is set-equal to the full in-force set and my interview selected only some of it, and to name the narrowing commands. | Medium | Open | [build] | no — the warning text is asserted on a seeded fixture, and its absence on an operator-chosen list |
| FR-009 | Bundle stamp kept in parity | As a project owner, I want the charter bundle hash re-stamped after the promotion writes the activation ledger, so that the bundle does not read as stale. | Medium | Open | [build] | no — the stamp equals the recomputed hash after a promotion |
| FR-010 | Dry run previews the promotion | As a project owner, I want `spec-kitty upgrade --dry-run` to name each key that would gain ids and the ids, and to write nothing. | Low | Open | [build] | no — asserted on the FR-003 fixture: the preview names the id and the files are unchanged |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Idempotence | After a run records success, a later upgrade does not select the migration, and a direct re-apply changes 0 bytes across `config.yaml`, `charter.yaml` and `activation.yaml`. | Reliability | High | Open |
| NFR-002 | Upgrade cost | The in-force set is resolved at most once per run, and only when a present list could be a seeded one (FR-008). Detection reads no file, and a project with no interview selection resolves no doctrine. | Performance | Medium | Open |
| NFR-003 | Code quality | New code passes ruff and mypy with zero findings, every function has cyclomatic complexity of 15 or less, and diff coverage of the change is at least 90%. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Never edit a shipped migration | `m_unify_charter_activation.py` stays byte-identical (DIRECTIVE_044). Supersession goes through `SUPERSEDED_MIGRATIONS`, and the new migration gets its own `order_manifest.txt` entry. | Technical | High | Open |
| C-002 | Activation ledger schema unchanged | No new key is added to `.kittify/charter/activation.yaml`. Writes go through the activation ledger seam, so the deny guard applies (ADR 2026-10-19-1). | Technical | High | Open |
| C-003 | Operator-time writers unchanged | The interview, `charter activate`, the org-charter union, `charter synthesize` and `_catalog_is_established` keep their current behaviour for lists an operator wrote (#4785, #6408 pins stay green). | Technical | High | Open |
| C-004 | No silent change to existing lists | An upgrade never narrows or removes an existing explicit activation list (#6499). | Business | High | Open |
| C-005 | Tracked effect | The new migration's effect travels with the commit (`clone_local_effect = False`), and it runs at the project root only (`runs_on_worktrees = False`). | Technical | Medium | Open |
| C-006 | Order | The new migration is declared at 4.0.0rc8 and listed in `order_manifest.txt` after `4.0.0rc8_activation_ledger`, so it reads the moved keys. A lower version would let the ledger-adoption backfill settle it without running it. | Technical | High | Open |

### Key Entities

- **Interview selection**: the `selected_<kind>` ids in `.kittify/charter/interview/answers.yaml`. A record of the interview, not an activation source.
- **Activation surface**: where activation is read and written. That is the activation ledger (`.kittify/charter/activation.yaml`), or, on an unmigrated project, the `charter.yaml` that `config.yaml` points to, or `config.yaml` itself.
- **Absent key**: an `activated_<kind>` key that is not on the activation surface. Every available artifact of that kind is in force, less exclusions.
- **In-force set**: what is in force for a kind while its key is absent (`resolve_effective_sets`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the #6629 project shape, an upgrade followed by `charter synthesize` demands 0 directive companion tactics instead of 38. — [build] · no-op passable: no
- **SC-002**: 100% of interview-selected ids that resolve and are not deactivated are in force after the upgrade, in every fixture of the mission's tests. — [ratchet] · no-op passable: yes (paired with SC-001)
- **SC-003**: A second upgrade on any fixture of the mission's tests changes 0 files, also after the operator narrowed a list in between. — [build] · no-op passable: no
