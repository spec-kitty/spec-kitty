# Mission Specification: Requirement-ID grammar and finalize-tasks diagnostics

**Mission Branch**: `issue-2991-requirement-id-grammar` (planning/base and merge target; coordination branch `kitty/mission-requirement-id-grammar-01M3NRCA`)
**Created**: 2026-09-29
**Status**: Draft
**Input**: Slice 5 toward the 4.0.0rc5 cut under epic #1676 (parent). Closes #2991, #3519 (part 2, plus the qualified-citation form that retires part 1's last false positive) and the remaining scope of #2066. Discovery: a pre-spec grounding squad (alignment, scope and architecture lenses) on `main` `aedb30cddd`, and a post-spec adversarial squad (non-vacuity and boundary lenses). The operator made seven rulings, each recorded as a Decision Moment:
- success criteria are tracked but not gating;
- a letter suffix is accepted, with lowercase as the canonical form;
- the planning hand-off blocks malformed declared IDs and only warns on citations;
- qualified citations of another mission are included;
- `malformed` and `unknown_spec_id` fail, and `foreign_qualified` never fails;
- the orchestrator-api refusal carries its reason in data;
- existing authored refs are never rewritten.

## Intent Summary (confirmed 2026-09-29)

A **mission author** (a human or an agent) writes a spec's requirements and each work package's `requirement_refs`. A **reviewer** reads the coverage output. When the author hands the spec to planning (`setup-plan`, and the orchestrator-api `plan` verb that wraps it), maps requirements (`map-requirements`), finalizes tasks (`finalize-tasks`) or drives `spec-kitty next`, every requirement ID is read the same way by one grammar. Authored refs are never erased or rewritten, and every rejected ref explains itself. The invariant: **no requirement ref an author wrote ever disappears without a trace.**

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Authored refs are never erased (Priority: P1)

An author lists success criteria and letter-suffixed requirements in a work package's `requirement_refs`, following the tasks-packages guidance to copy refs from the manifest. They run `finalize-tasks`. Today those refs are deleted from the work package file on disk, with at most a warning that misses some shapes. After this mission every authored item is still in the file, byte-for-byte. Refs finalize cannot use are listed with a reason instead of being removed.

**Why this priority**: This is data loss (#2991). An author who follows the canonical guidance has their work silently reverted one step later, and reviewers get a clean traceability answer that means nothing.

**Independent Test**: Seed a work package with a functional requirement ref, two declared success-criterion refs (one with a letter suffix) and one malformed token. Run `finalize-tasks` for real, without `--validate-only`, then read the work package file back from disk.

**Acceptance Scenarios**:

1. **Given** a work package whose refs are a declared functional requirement and two declared success criteria, **When** the author runs `finalize-tasks` without `--validate-only`, **Then** the file's `requirement_refs` is item-for-item identical to the seeded list, the other finalize fields (such as the planning base branch) were written in the same pass (proving the write ran), and the functional requirement counts toward coverage.
2. **Given** the same work package plus one token that matches no grammar shape, **When** the author runs `finalize-tasks`, **Then** the token is still in the file, is reported under `malformed`, and fails finalize. The declared functional requirement on the same work package still counts toward coverage.
3. **Given** a work package that already carries a success-criterion ref, **When** the author runs `map-requirements` to add a functional requirement to it, **Then** the existing item is unchanged on disk and the new ref is added.

---

### User Story 2 - Success criteria and letter-suffixed IDs are first-class (Priority: P1)

An author's spec declares a success criterion and a sub-requirement with a letter suffix (a functional requirement numbered like six-a). They register both with `map-requirements` and expect finalize to account for them. Today `map-requirements` rejects both. Finalize cannot see the suffixed requirement at all, so leaving it unmapped passes validation unnoticed.

**Why this priority**: This is #3519 part 2. The unnoticed pass is a coverage hole that defeats the gate's purpose.

**Independent Test**: A spec declaring one plain and one letter-suffixed functional requirement plus one success criterion. Map only the plain requirement, then run `finalize-tasks --validate-only`.

**Acceptance Scenarios**:

1. **Given** a spec that declares a letter-suffixed functional requirement that no work package maps, **When** the author runs `finalize-tasks --validate-only`, **Then** validation fails and names that suffixed ID as unmapped. With the suffixed ID mapped, the same fixture passes.
2. **Given** the same spec, **When** the author maps the suffixed requirement and the success criterion with `map-requirements`, **Then** both are accepted, added in canonical form (uppercase kind, lowercase suffix) and counted.
3. **Given** a declared success criterion that no work package references, **When** finalize runs, **Then** the criterion is listed as unreferenced in an informational success-criteria coverage block, and finalize still passes on that account.
4. **Given** a work package ref stored with an uppercase suffix, **When** either command or the runtime reads it, **Then** it matches the declared lowercase-suffix ID and is left as written.

---

### User Story 3 - Every rejection explains itself (Priority: P2)

A requirement-coverage check fails. The author or reviewer needs to know which IDs the spec declares, which refs each work package carries, and why each unusable ref was rejected. Today `finalize-tasks` reports an unmapped list with no parsed spec-ID set, and `map-requirements`' pre-write gate rejects `--refs` input without listing the declared IDs.

**Why this priority**: This is #2066. A one-character format mismatch reads like data corruption, and agents burn time guessing.

**Independent Test**: Trigger a coverage failure on both commands with one malformed ref, one undeclared well-formed ref and one qualified citation, and compare the diagnostics.

**Acceptance Scenarios**:

1. **Given** a finalize coverage failure, **When** the author reads the JSON output, **Then** it includes the requirement IDs parsed from the spec, grouped by kind, and each rejected ref with exactly one reason: `malformed`, `unknown_spec_id` or `foreign_qualified`.
2. **Given** `map-requirements --refs` input containing a malformed ID, **When** the command refuses it, **Then** the refusal names the grammar rule and lists the IDs the spec declares.
3. **Given** the same fixture, **When** both commands report on the same rejected ref, **Then** they give the same reason.

---

### User Story 4 - Malformed IDs are caught at the planning hand-off (Priority: P2)

An author finishes a spec and hands it to planning. A requirement row declares an ID in a shape outside the grammar, for example a kind prefix followed by a hyphenated word or a dotted number. Today nothing notices until tasks are finalized, and sometimes never. After this mission the hand-off refuses, naming the offending ID and the rule. A suspect ID that is only mentioned in prose produces a warning, not a refusal.

**Why this priority**: This is the remaining authoring-time slice of #2066. The error arrives one phase earlier, while the author is still editing the spec.

**Independent Test**: Two specs identical except that one has a malformed declared ID. Run the planning hand-off and the orchestrator-api `plan` verb on each.

**Acceptance Scenarios**:

1. **Given** a spec with a malformed ID in a declared position, **When** the author runs the planning hand-off, **Then** it refuses with the code `SPEC_REQUIREMENT_IDS_INVALID`, naming the offending ID, its line and the grammar rule.
2. **Given** the same spec with that ID corrected, **When** the author runs the hand-off, **Then** it proceeds (positive control on the same fixture).
3. **Given** a spec whose prose mentions an undeclared requirement-shaped token, **When** the hand-off runs, **Then** it proceeds and returns a warning naming the token.
4. **Given** the malformed spec, **When** the orchestrator-api `plan` verb runs, **Then** the envelope's `error_code` is the contract-registered `PLAN_SETUP_FAILED`, and the payload carries the reason `SPEC_REQUIREMENT_IDS_INVALID` and the offending IDs.

---

### User Story 5 - Citing another mission's IDs (Priority: P3)

An author's spec references an ID that another mission owns. A mid-sentence citation is already ignored today, but inside a requirements section the blocking bare-prose check can flag it. The only workarounds are dropping the canonical form or disguising the hyphen. After this mission the author writes a qualified citation, `<mission-slug>#<ID>`. It is recognised as another mission's ID and is never counted, mapped or flagged as this mission's own.

**Why this priority**: This closes the last false positive behind #3519 part 1 and gives authors an honest canonical form. The need is less frequent than the P1 and P2 stories.

**Independent Test**: A spec whose requirements section holds a qualified citation of an ID this spec does not declare, next to a bare, unqualified, undeclared token in the same section.

**Acceptance Scenarios**:

1. **Given** a qualified citation in a requirements section, **When** the bare-prose check runs, **Then** the citation is not flagged. The bare undeclared token in the same section still is (positive control).
2. **Given** a qualified citation, **When** coverage is computed, **Then** it is neither declared nor required, and the planning hand-off does not warn about it.
3. **Given** a work package that lists a qualified citation in its refs, **When** either command runs, **Then** the ref is kept, reported under `foreign_qualified`, and does not fail finalize.

---

### User Story 6 - finalize and the runtime agree (Priority: P2)

An author finalizes tasks, then drives `spec-kitty next`. Today the runtime readiness check applies its own view of requirement refs, so it can refuse a work package that finalize accepted, or the reverse.

**Why this priority**: A split verdict between two gates on the same data is the whack-a-field failure this mission exists to close.

**Independent Test**: One fixture evaluated by both `finalize-tasks --validate-only` and the runtime readiness check.

**Acceptance Scenarios**:

1. **Given** a fixture whose work packages reference declared success criteria and a declared letter-suffixed functional requirement, **When** both gates evaluate it, **Then** both pass.
2. **Given** the same fixture plus one work package ref to an undeclared success criterion, **When** both gates evaluate it, **Then** both fail with `unknown_spec_id`, and the runtime's findings are non-empty if and only if finalize fails.

### Edge Cases

- A letter suffix is a single lowercase letter. When a spec is scanned for declarations or prose tokens, only a lowercase suffix is recognised. Placeholder shapes with a capital letter in the digit position therefore stay unrecognised, and a spec that declares an uppercase-suffix ID is refused at the planning hand-off with a hint to write the suffix in lowercase. Uppercase-suffix tolerance applies only when a work package ref or `--refs` input is matched against a declared ID.
- Digit width is preserved verbatim. A one-digit constraint ID and a three-digit constraint ID with the same numeric value are distinct IDs, because existing specs rely on that distinction.
- A struck-through declared ID still counts as declared, as it does today.
- Only the first ID on a declaration line is the declaration. A citation inside a table row's description cell is never a second declaration.
- Prose compounds, such as an ID followed by `-mandated` or `-only`, are not IDs with a qualifier and must not become one.
- A well-formed ref that the spec does not declare is `unknown_spec_id`, not `malformed`. This holds for success criteria too.
- A qualifier is not resolved against existing missions, and a qualified citation is always foreign, even when it names this mission's own slug. Slugs are lowercase words joined by hyphens, optionally followed by an uppercase eight-character mission-ID tail.
- A work package whose only usable refs are success criteria counts as having requirement refs.
- A mission with no success-criteria section finalizes exactly as today; the informational block is empty.
- Concern IDs (the two-digit implementation-concern class) are a separate grammar and are unaffected.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One requirement-ID grammar | As a mission author, I want every requirement-ID surface to recognise the same set of shapes: kinds FR, NFR, C and SC, digits, an optional single lowercase letter suffix, and an optional `<mission-slug>#` qualifier. The surfaces are the planning hand-off, map-requirements, finalize-tasks (including its tasks.md fallback reader), the runtime readiness check (including its tasks.md fallback reader) and the merge-cleanup retention reader's constraint-row check (only an unqualified constraint ID counts, letter-suffixed ones included). An ID then means the same thing wherever I use it. | High | Open | [build] | no |
| FR-002 | Canonical form and matching | As a mission author, I want one canonical form (kind uppercase, digits verbatim, suffix lowercase). A work package ref or `--refs` input with an uppercase suffix, such as `FR-006A`, should match the declared `FR-006a`, while spec scanning recognises only a lowercase suffix and digit width stays significant. That way a stored spelling difference never breaks a match, and placeholders never parse. | High | Open | [build] | no — positive control: a placeholder token is not declared while `FR-006a` is, on the same fixture |
| FR-003 | Declared success criteria and suffixed IDs | As a mission author, I want a success criterion or letter-suffixed requirement written in any declared shape (table row, heading, bullet, bold lead) recognised as declared by my spec, so that it can be mapped and counted. | High | Open | [build] | no |
| FR-004 | finalize-tasks never erases or rewrites authored refs | As a mission author, I want `finalize-tasks` to leave every `requirement_refs` item I wrote byte-identical in the work package file, and to report the refs it cannot use with a reason instead of removing them, so that my traceability survives finalize. | High | Open | [build] | no — verified by a real (non-validate-only) run whose other written fields prove the write happened |
| FR-005 | map-requirements never erases authored refs | As a mission author, I want `map-requirements` to keep the existing items on the work package it is mapping byte-identical, to add new refs in canonical form, and to deduplicate by canonical form, so that registering one mapping can never delete or respell another. `--replace` is the explicit, operator-invoked overwrite; its JSON payload lists the items it removed. | High | Open | [build] | no |
| FR-006 | map-requirements accepts SC and suffixed IDs | As a mission author, I want `map-requirements` to accept success criteria and letter-suffixed IDs that my spec declares, so that I can register them structurally. | High | Open | [build] | no — paired with an undeclared success criterion being refused as `unknown_spec_id` on the same fixture |
| FR-007 | Success criteria tracked, not gating | As a reviewer, I want finalize to report, for information, which declared success criteria are referenced by which work packages and which are unreferenced, and never to fail because a declared success criterion is unreferenced. The old warning that success-criterion refs are "dropped, not traced" is retired, since it is no longer true. | High | Open | [build] | no — positive control: an unmapped functional requirement in the same fixture still fails; the retired warning is asserted absent for a referenced success criterion |
| FR-008 | Suffixed requirements are coverage-gated | As a reviewer, I want a declared letter-suffixed functional requirement that no work package maps to fail finalize coverage like any other functional requirement, so that the silent coverage hole is closed. | High | Open | [build] | no |
| FR-009 | Qualified citations of another mission | As a mission author, I want `<mission-slug>#<ID>` recognised as another mission's ID, so that I can cite honestly in canonical form. Such an ID is never declared, never required for coverage, never flagged by the bare-prose check, never warned about at the planning hand-off, and reported as `foreign_qualified` if it is placed in a work package's refs. | Medium | Open | [build] | no — positive control: a bare undeclared token in the same section is still flagged |
| FR-010 | One rejection-reason vocabulary | As a reviewer, I want every requirement ref that finalize, map-requirements or the runtime readiness check cannot use to be classified into exactly one reason (`malformed`, `unknown_spec_id`, `foreign_qualified`), with the same vocabulary on all three (verdicts per FR-019), so that I can tell a format slip from a missing declaration from a foreign citation. | High | Open | [build] | no |
| FR-011 | finalize-tasks reports the parsed spec IDs | As a reviewer, I want finalize-tasks' requirement output to include the IDs parsed from the spec, grouped by kind, next to the reasoned rejections for each work package, so that a coverage failure shows what the parser actually saw. | High | Open | [build] | no |
| FR-012 | map-requirements pre-write refusal explains itself | As a mission author, I want the `map-requirements --refs` refusal of an unusable ID to name the grammar rule and list the IDs my spec declares, so that I can correct the input without guessing. | Medium | Open | [build] | no |
| FR-013 | Planning hand-off blocks malformed declared IDs | As a mission author, I want the planning hand-off to refuse with `SPEC_REQUIREMENT_IDS_INVALID`, naming the ID, its line and the rule, when a declared position holds a token outside the grammar, so that I fix it while still editing the spec. A declared position is the first table cell, the first token of a heading, the lead token of a bullet or numbered item, or the lead of a bold paragraph, when that token begins with an uppercase requirement kind followed by a hyphen or underscore and then a digit or an uppercase letter. | High | Open | [build] | no — positive control: the corrected spec proceeds |
| FR-014 | Planning hand-off warns on suspect prose IDs | As a mission author, I want the planning hand-off to return a non-blocking warning for unqualified requirement-shaped tokens in prose that my spec does not declare, extending (not duplicating) the existing undeclared-citation warning, so that I notice a likely typo without being blocked by a legitimate citation. | Medium | Open | [build] | no |
| FR-015 | Orchestrator-api plan verb parity | As an external orchestrator, I want the `plan` verb to refuse the same specs as the direct hand-off. The envelope keeps the contract-registered `PLAN_SETUP_FAILED` code, and the payload carries the reason `SPEC_REQUIREMENT_IDS_INVALID` and the offending IDs, so that automation sees the same gate without a cross-repo contract change. | Medium | Open | [build] | no — asserts the envelope code is contract-registered and the payload reason is present |
| FR-016 | Runtime readiness uses the grammar and verdicts | As a mission author driving `spec-kitty next`, I want the runtime readiness check to accept declared success criteria and letter-suffixed refs, to apply the FR-019 verdicts, and never to fail on an unreferenced declared success criterion, so that it passes exactly the fixtures finalize passes. | High | Open | [build] | no — parity scenario with an undeclared success criterion as positive control |
| FR-017 | Consumer guidance describes the grammar | As a mission author in a consumer project, I want the shipped spec template and the guidance for task outlining, task packaging, task finalization and review to describe the grammar: the four kinds, the letter suffix, the qualified citation, the rejection reasons, and that success criteria are tracked but not gating. The guidance then matches what the tools accept. | Medium | Open | [build] | no |
| FR-018 | Grammar policy recorded | As a maintainer, I want the single-grammar policy and the FR-019 verdict table recorded as an architecture decision that supersedes the "success criteria are not admitted" behaviour, and the terms *Requirement ID*, *Success criterion* and *Qualified citation* defined in the glossary, so that the policy has one durable authority. | Medium | Open | [build] | no |
| FR-019 | Shared rejection verdicts | As a reviewer, I want finalize-tasks, map-requirements and the runtime readiness check to apply one verdict table: `malformed` fails, `unknown_spec_id` fails (for every kind, success criteria included), `foreign_qualified` never fails. A rejected ref never stops the valid refs on the same work package from counting toward coverage. Then a slip is caught without one bad ref hiding good ones. | High | Open | [build] | no — positive control: the valid ref on the same work package counts while its sibling ref fails |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Existing-corpus safety | A scan committed in the mission artifacts runs on the merge-base with `upstream/main` recorded at scan time and on the branch head over the same file list (every `kitty-specs/*/spec.md`; 518 specs at planning time; the exact count is recorded). It reports four things. (a) The blocking bare-prose check flags no more specs at head than at the merge-base (1). (b) It lists every spec the planning hand-off would newly refuse (4 expected: kind-prefixed malformed IDs in declared positions). (c) It lists every spec whose declared-ID set grows. (d) It lists every existing `kitty-specs/*/tasks/WP*.md` ref whose classification changes. | Reliability | High | Open |
| NFR-002 | JSON contract compatibility | 100% of JSON keys emitted today by the planning hand-off, `map-requirements` and `finalize-tasks` remain, with the same type. Changes are additive except for these, each listed in the changelog: letter-suffixed IDs in the pinned byte-contract and stale-ref fixtures move from `malformed` to `unknown_spec_id` (or to accepted, when declared); `stale_ref_reasons` gains a `foreign_qualified` key; the refusal hint wording changes; and the retired success-criterion discard warning no longer appears. The orchestrator-api contract minor version is bumped once (1.7.0 → 1.8.0) for the additive data keys. | Compatibility | High | Open |
| NFR-003 | Latency | Requirement-ID parsing adds at most 50 ms to `finalize-tasks` on a 30-work-package fixture. This is measured in-process as the median of 20 runs at the branch head against the merge-base, using a micro-benchmark rather than a performance suite. `finalize-tasks` stays within the charter's 2-second budget for typical projects. | Performance | Medium | Open |
| NFR-004 | Code quality | New and changed code passes ruff (lint and format) and mypy strict with zero findings, keeps every function at complexity ≤ 15, and reaches ≥ 90% diff coverage. | Maintainability | High | Open |
| NFR-005 | Red-first proof | Each of the four defects has an issue-pinned reproduction that fails through the pre-existing entry point before its fix and passes after it: 4 of 4. The defects are: finalize-tasks erasing authored refs (#2991); map-requirements erasing authored refs (#2991); a declared, unmapped letter-suffixed requirement passing finalize (#3519); and finalize failure output lacking the parsed spec-ID set (#2066). | Quality | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single grammar authority | Product code has exactly one definition of the requirement-ID grammar, one canonicalisation of IDs and one tokenisation of `requirement_refs` values. No consumer compiles its own requirement-ID pattern or changes an ID's case itself. An architectural test fails on a requirement-ID pattern literal outside the grammar's home. The setup-plan substantive-spec gate and the retrospective generator are the only exceptions. Each is a documented, frozen divergence that names its follow-up ticket (HiC ruling, Decision Moment `01M3P2HXKASQY2ZKSEY3MAWA9H`, which supersedes `01M3P07HV88QNVVKP3E2W28VB6`). | Technical | High | Open |
| C-002 | Layering unchanged | No new import-ledger entries and no raised architectural baselines. The stdlib-only runtime-bridge core module takes the grammar as a required argument, with no default and no local ID pattern. Its caller supplies the grammar through the import it already has. | Technical | High | Open |
| C-003 | Manifest schema unchanged | The work-package manifest schema is not modified. Its `requirement_refs` items stay plain strings (see #5065 for the separate lifecycle-status question). | Technical | High | Open |
| C-004 | Concern IDs untouched | Implementation-concern IDs remain a separate grammar and are not admitted as requirement IDs. | Technical | Medium | Open |
| C-005 | Safe regex engine | Every grammar pattern compiles and behaves identically under the product's safe regex engine (no lookbehind, no backreferences). | Technical | High | Open |
| C-006 | Source templates only | Template and prompt changes are made in the shipped source packs only, never in generated agent copies. | Technical | High | Open |
| C-007 | No heavy suites during mission work | Implementers and reviewers run only the tests covering the touched files, the owning module's fast tier, and the specific named architectural gate files the change implicates. No whole architectural, e2e, integration, performance, stress or timing suite, and no whole-repo run. | Process | High | Open |
| C-008 | Out of scope | Not in this mission: the lifecycle-status shape for requirement refs (see #5065); concern-ref warnings (see #5079); stale authority on re-finalize (see #2644); the runtime-field strip noted on #2991 (see #2093); a requirement-ID check on `plan.md`; re-seeding existing acceptance matrices with newly visible IDs; the differing tasks.md line-selection rules of the two fallback readers; and the two frozen patterns named in C-001: the setup-plan substantive-spec gate's functional-requirement table-row pattern and the retrospective generator's functional-requirement reference pattern. | Business | Medium | Open |
| C-009 | Non-blocking prose policy preserved | The blocking bare-prose check's candidate kinds stay unqualified, unsuffixed FR, NFR and C tokens, exactly as today; compound prose tokens such as an ID followed by `-mandated` are no longer candidates, so the candidate set can only shrink. Success-criterion, letter-suffixed and qualified tokens in prose never block. New prose detection is warning-only. | Technical | High | Open |

### Key Entities

- **Requirement ID**: a stable identifier for one spec requirement. It has a kind (functional, non-functional, constraint, success criterion), a digit string whose width is significant, an optional single lowercase letter suffix, and an optional mission qualifier that marks it as another mission's.
- **Declared ID**: a Requirement ID the spec itself declares in one of the declaration shapes. Only declared functional IDs are coverage-gated. Declared success criteria are tracked for information.
- **Qualified citation**: a Requirement ID with a mission qualifier. It belongs to the named mission and is never counted as this mission's own.
- **Rejected ref**: a requirement ref on a work package that the tools cannot use. It stays in place, carries exactly one reason (`malformed`, `unknown_spec_id` or `foreign_qualified`), and fails or passes according to the shared verdict table.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the reproduction fixture, 0 authored refs are removed or respelled by `finalize-tasks` or `map-requirements`. Today every success-criterion and letter-suffixed ref is removed. — [build] · no-op passable: no
- **SC-002**: A spec that declares a letter-suffixed functional requirement left unmapped fails finalize validation every time. Today it passes every time. — [build] · no-op passable: no
- **SC-003**: 100% of rejected refs reported by `finalize-tasks`, `map-requirements` and the runtime readiness check carry exactly one reason, from the same vocabulary. Every finalize rejection output includes the spec's parsed ID set; today it includes neither. — [build] · no-op passable: no
- **SC-004**: A malformed declared ID is reported at the planning hand-off, one phase before tasks exist. Today it is reported at finalize, or never. — [build] · no-op passable: no
- **SC-005**: Across the existing spec corpus, the number of specs flagged by the blocking bare-prose check does not rise above the merge-base count of 1. — [ratchet] · no-op passable: yes — positive control: the known flagged spec is still detected unless its citations are rewritten in qualified form
- **SC-006**: Requirement-ID shapes are defined in exactly one place in product code, apart from the two documented frozen divergences. Today there are 6 separate definitions, 4 of them in scope. — [build] · no-op passable: no
- **SC-007**: On a shared fixture set, finalize-tasks and the runtime readiness check agree on pass/fail in 100% of cases. — [build] · no-op passable: no

## Assumptions

- Existing missions that re-finalize will, for the first time, see their declared letter-suffixed functional requirements counted and their malformed or undeclared refs fail. Newly failing coverage there is the intended fix, not a regression. The NFR-001 scan lists every affected spec and work package.
- Success criteria in existing specs use the template's bold-bullet shape, so they become declared without any author action.
- Refs previously normalised to an uppercase suffix exist only in work package files, never in specs. Suffix-tolerant matching covers them.
- Keeping refs that finalize used to erase changes the cross-repo dossier parity hash for the affected work packages. This is expected and is noted in the changelog.
- The manifest keeps the author's spelling, and tasks.md is regenerated from it. Because finalize never rewrites items, the manifest and the work package files no longer drift apart.
