# Mission Specification: Pack-shipped built-in override sanction

**Mission Branch**: `issue-replaceable-builtins-sanction`
**Created**: 2026-10-05
**Status**: Draft
**Input**: Operator brief relayed from consumer sessions. Issue #5767: "Org packs cannot ship their own replaceable-builtins sanction; consumer allowlists drift on every built-in promotion".
**Grounding**: [`research/code-grounding.md`](research/code-grounding.md), from a squad of four lenses (architect, doctrine-integrity, related-issue, test-suite) run before specify.

## Intent Summary

**Discovery mode:** brief intake. The operator's brief states the objective, constraints, options and acceptance criteria, and it delegates the choice of design to specify/plan. Decision Moments `01M45WDZ…` (sanction source) and `01M45WE5…` (consumer revocation) record the resolutions.

**Actors:**
- **Consumer operator**: runs `spec-kitty doctor doctrine` in a repository that has an org pack configured.
- **Org-pack author**: maintains the pack, which deliberately replaces some built-in doctrine.

**Trigger:** Upstream promotes an org-authored artifact into the built-in set. The pack's same-id artifact then becomes an override of a built-in. Every consumer whose hand-copied `.kittify/doctrine/replaceable-builtins.yaml` predates the promotion now fails `doctor doctrine` with RC=1, even though the consumer changed nothing.

**Desired outcome:** The org pack ships the sanction for the built-ins it deliberately replaces. `doctor doctrine` honours that sanction in place, with no edit in the consumer repository.

**Rules that must always hold:**
- An override that nobody sanctions still fails closed.
- A pack can only sanction overrides that it contributes itself.
- A directive override still needs a stated reason.
- Existing consumer allowlists keep working unchanged.
- The consumer can always withdraw a sanction that a pack delivered.

**Primary scenario:** A consumer runs CLI rc6 with org pack `doctrine-org`. The pack ships `replaceable-builtins.yaml` at its root, and that file sanctions `directive:MINUTES_STAND_ALONE` with a reason. The consumer's own allowlist is absent or stale. `doctor doctrine` → RC=0, and the report shows the override as sanctioned by pack `doctrine-org`.

**Main exception:** The pack overrides a built-in that its own file does not list, and the consumer file does not list it either. `doctor doctrine` → RC=1, unchanged from today.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Built-in promotion no longer breaks consumers (Priority: P1)

An org-pack author lists the built-ins the pack deliberately replaces in the pack's own sanction file. A consumer who refreshes the pack stays green, even when upstream later promotes one of the pack's artifacts to a built-in, and the consumer edits nothing.

**Why this priority**: This is the defect in #5767. Today every consumer must hand-copy and re-copy a template, and that copy drifts on every promotion.

**Independent Test**: Set up a consumer fixture with a stale or absent consumer allowlist and an org pack that overrides a built-in URN and sanctions it in its pack-root sanction file. `spec-kitty doctor doctrine` exits 0. The same fixture without the pack-root file exits 1, which serves as the red-first control.

**Acceptance Scenarios**:

1. **Given** an org pack overriding built-in `directive:MINUTES_STAND_ALONE` and sanctioning it, with a reason, in its pack-root sanction file, and **given** no consumer allowlist, **When** the operator runs `spec-kitty doctor doctrine`, **Then** it exits 0 and reports no unsanctioned override.
2. **Given** the same pack and a consumer allowlist that lists other URNs but not this one (stale), **When** doctor runs, **Then** it exits 0.
3. **Given** the same pack without the pack-root sanction file, **When** doctor runs, **Then** it exits 1 and names the URN. This is the positive control showing the check bites.

---

### User Story 2 - The governance boundary stays fail-closed and scoped (Priority: P1)

A consumer operator trusts that delegating a sanction to a pack does not turn the allowlist into a blanket waiver.

**Why this priority**: The fix must not weaken NFR-004 of `doctrine-governance-fidelity-01KW42KY` (fail-closed) or the rule that a directive override needs a reason.

**Independent Test**: Run one fixture per negative case through `doctor doctrine --json`. Each case reports `unsanctioned_overrides` and exits 1.

**Acceptance Scenarios**:

1. **Given** pack A overrides a built-in and pack B's sanction file lists that URN, **When** doctor runs, **Then** the override is unsanctioned (RC=1), because pack B cannot sanction pack A's override.
2. **Given** a pack sanctions a built-in **directive** override with an empty reason, **When** doctor runs, **Then** the override is unsanctioned (RC=1).
3. **Given** a pack's sanction file is present but malformed, **When** doctor runs, **Then** the report is unhealthy (RC=1) with an error that names the pack and the file, and no override is treated as sanctioned because of that file.
4. **Given** the consumer allowlist alone sanctions the override (today's setup), **When** doctor runs, **Then** it exits 0, exactly as before.

---

### User Story 3 - The consumer can see and withdraw a delegated sanction (Priority: P2)

A consumer operator sees which source sanctioned each built-in override, including on green runs. The operator can withdraw a pack's sanctions, either for one URN or for a whole configured pack, without forking or unconfiguring the pack.

**Why this priority**: Delegated governance must stay visible and revocable. Otherwise configuring a pack becomes an irrevocable waiver, and a newly self-sanctioned override that arrives on the next pack refresh goes green unnoticed.

**Independent Test**: Use a fixture with a pack-sanctioned override and a consumer allowlist that revokes that URN. Doctor exits 1 and names the revocation. Remove the revocation: doctor exits 0, and the JSON and human output name the sanctioning pack.

**Acceptance Scenarios**:

1. **Given** a pack-sanctioned override, **When** doctor runs, **Then** both the human output and the JSON payload list the override as sanctioned, together with its source (the pack's registry name) and reason. This holds even though the run is green.
2. **Given** a consumer allowlist that revokes pack sanctions for that URN, **When** doctor runs, **Then** the override is unsanctioned (RC=1), and the finding says that the consumer allowlist revoked the pack's sanction.
3. **Given** a consumer allowlist that revokes all sanctions of that pack, **When** doctor runs, **Then** every override from that pack that only the pack sanctioned is unsanctioned (RC=1).
4. **Given** a consumer allowlist that both revokes a URN for pack sanctions and lists that URN itself, **When** doctor runs, **Then** the consumer's own listing sanctions it (RC=0). Revocation withdraws only what packs delivered.

---

### User Story 4 - Packs still on the legacy template get an actionable hint (Priority: P3)

Some packs still ship only `templates/setup/replaceable-builtins.yaml` and have not moved it to the pack root yet. A consumer of such a pack is told exactly how to fix the red without guessing, and without being steered into a whole-file copy that would drift again.

**Why this priority**: This hint bridges the window until the pack authors move the file. It is also the rc6 fallback if the full fix slips.

**Independent Test**: In a fixture, the pack ships the URN only in its legacy template. Doctor exits 1 and prints the pack-author remedy plus the exact entry to add to the consumer allowlist.

**Acceptance Scenarios**:

1. **Given** an unsanctioned override whose own pack lists that URN in `templates/setup/replaceable-builtins.yaml`, **When** doctor runs, **Then** it still exits 1, because a template is not a sanction. Doctor also prints (a) the pack-author remedy, which is to move the template to the pack root as `replaceable-builtins.yaml`, and (b) the exact `{urn, reason}` entry to append to the consumer allowlist, with the reason taken from the template. Doctor never prints a whole-file copy command.
2. **Given** a malformed legacy template, **When** doctor runs, **Then** no hint is printed and the template causes no error. The template is advisory input only.

### Edge Cases

- **Several org packs override the same built-in.** The merge keeps the last pack's node. Only that surviving node is adjudicated, against the sanction of the pack that contributed it. This documents current merge behaviour, which this mission leaves unchanged (C-005).
- **A pack sanction lists a URN that is not a built-in, or that the pack does not override.** The entry is inert. It never sanctions anything else and never changes the exit code.
- **The pack's sanction file is a symlink or path that resolves outside the pack root, or it cannot be read.** It is treated as malformed for that pack (FR-006).
- **A pack's root is the consumer's own `.kittify/doctrine/` directory.** The file there is the consumer allowlist and is attributed to the consumer only. It is never counted twice.
- **A pack sanction file carries `revoked_pack_sanctions`.** That key is consumer-only, so the pack file is malformed. Other unknown top-level keys are ignored in both files, for forward compatibility. A typo in the `replaceable_builtins` key therefore yields an empty sanction, which fails closed.
- **An assembled pack.** It carries the union of its inputs' sanctions, because every assembled node carries the assembled pack's provenance (FR-015).
- **A pack fetched through an API source.** API sources do not carry pack-root files, so no pack sanction is delivered and the consumer file still governs. This limitation is documented.
- **Project-tier overrides** (`.kittify/doctrine/`) stay intentionally ungoverned, per `doctrine-governance-fidelity-01KW42KY#FR-012`.
- **No org packs configured.** Doctor output is byte-identical to today.
- **A malformed pack file while the consumer allowlist validly sanctions the override.** The override counts as sanctioned (by the consumer), but the report is still unhealthy (RC=1), because the pack file itself is broken (FR-006).
- **A malformed consumer allowlist.** Doctor reports it as an error naming the file and treats the consumer allowlist as empty, which fails closed. Every other finding is still reported. This is a deliberate change: today a malformed consumer file goes unnoticed when no org override exists, and it aborts all override findings when one does.
- **`revoked_pack_sanctions` names a pack that is not configured** (matching is exact and case-sensitive). The report is unhealthy (RC=1) and names the entry, so a typo can never leave a sanction in force that the operator believes revoked.
- **Out of scope, pre-existing.** Edges that a losing org pack contributes at a built-in URN, and edge-form `overrides`/`enhances` relations targeting a built-in, are not adjudicated today. This mission does not change that; see Out of Scope.

### Sanction decision table

This table applies to one surviving org override of a built-in at URN `U`, contributed by pack `P`. "Valid" means the entry lists `U` and, when `U` is a directive, carries a non-empty reason.

| Consumer allowlist | Pack `P` sanction | Consumer revokes `U` or `P` | Verdict | Reported source / finding |
|---|---|---|---|---|
| valid | any | any | sanctioned | consumer |
| absent or invalid | valid | no | sanctioned | pack `P` |
| absent or invalid | valid | yes | **unsanctioned** | "pack sanction revoked by the consumer replaceable-builtins allowlist" |
| absent | absent | — | **unsanctioned** | "not on .kittify/doctrine/replaceable-builtins.yaml or pack `P`'s replaceable-builtins.yaml" |
| absent or not listing `U` | lists `U`, but it is a directive with an empty reason | no | **unsanctioned** | "directive override requires a non-empty reason (pack `P` replaceable-builtins.yaml)" |
| lists `U`, but it is a directive with an empty reason | absent or invalid | no | **unsanctioned** | "directive override requires a non-empty reason" |

A revocation is reported in preference to a reason finding whenever the pack would otherwise have sanctioned `U`. Revoking a URN that the pack never sanctioned changes nothing. A revocation naming another pack `P'` does not affect `P`.

Every finding text names `replaceable-builtins`. When both the consumer and the pack sanction an override, the consumer is reported, because the consumer is checked first. Another pack's sanction never applies.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Pack-root sanction honoured | As a consumer operator, I want `doctor doctrine` to treat an org override of a built-in as sanctioned when the overriding pack lists that URN in a `replaceable-builtins.yaml` at its pack root, so that built-in promotions stop breaking me without any edit on my side. | High | Open | build | no |
| FR-002 | Sanction scoped to the contributing pack | As a consumer operator, I want a pack's sanction to apply only to overrides whose surviving node was contributed by that same configured pack, identified by the registry name from my configuration and never by a name the pack declares, so that one pack can never waive another pack's override. | High | Open | build | no |
| FR-003 | Directive reason, per the decision table | As a consumer operator, I want a built-in directive override to be sanctioned only by an entry that carries a non-empty reason, following the sanction decision table, so that the reason rule holds whichever source sanctions the override. | High | Open | build | no |
| FR-004 | Consumer allowlist unchanged and checked first | As a consumer operator, I want my existing `.kittify/doctrine/replaceable-builtins.yaml` to keep its current schema and meaning, to be checked before pack sanctions, and to be unioned with them, so that nothing I already have breaks. | High | Open | ratchet | no (positive control: US2 scenario 4 plus the FR-001 fixture) |
| FR-005 | Fail closed for unsanctioned overrides | As a consumer operator, I want an org override that neither my allowlist nor its own pack sanctions to keep failing `doctor doctrine` (RC=1), so that governance is not weakened. | High | Open | ratchet | yes. Positive control: the FR-001 fixture with the pack file removed must go red. |
| FR-006 | Malformed pack sanction is isolated and loud | As a consumer operator, I want a pack sanction file that is malformed, unreadable, not a regular file, or resolves outside the pack root to make the report unhealthy. The error names the pack and the file. The file voids only that pack's sanctions, every other finding is still reported, and the file is checked for every loaded org pack whether or not that pack overrides anything. Then a broken file is never silent and never widens or narrows governance. | High | Open | build | no |
| FR-007 | Consumer revocation of pack sanctions | As a consumer operator, I want an additive `revoked_pack_sanctions` list in my allowlist, whose entries name a URN or a configured pack, so that I can withdraw pack-delivered sanctions without unconfiguring the pack. A CLI that predates the key ignores it. | Medium | Open | build | no |
| FR-008 | Sanction source visible on every run | As a consumer operator, I want `doctor doctrine` human and JSON output to list every built-in override that is sanctioned, together with its source and reason, including on green runs. In JSON this is an `org_drg.sanctioned_overrides` list that is absent when there are no org packs. Then delegated governance is auditable. | Medium | Open | build | no |
| FR-009 | Legacy-template hint | As a consumer operator, I want an unsanctioned override whose own pack ships the URN only in `templates/setup/replaceable-builtins.yaml` to come with a printed pack-root move for the pack author and the exact `{urn, reason}` entry to append to my allowlist. No whole-file copy is suggested, and the printed values are escaped. Then I can fix the red immediately. The probe is transitional and is removed with #2594. | Medium | Open | build | no |
| FR-010 | The generic hint names the pack-side remedy | As a consumer operator, I want the unsanctioned-override hint to mention both my allowlist and the pack-root sanction file, so that the remedy is discoverable. | Low | Open | build | no |
| FR-011 | Documentation, ADR and changelog | As an org-pack author, I want the pack-root sanction file, its scoping, the decision table, revocation, integrity, and the API-source limitation documented in an ADR, a how-to, and a `[Unreleased]` changelog entry, so that I can migrate my template. | Medium | Open | build | no |
| FR-012 | No-org-packs output unchanged | As a consumer operator without org packs, I want `doctor doctrine` output to stay byte-identical, so that the fix has no blast radius on me. | Medium | Open | ratchet | yes. Positive control: FR-008's new output on the org-pack fixture. |
| FR-013 | One effective-policy loader | As a maintainer, I want one loader that combines the consumer allowlist, pack sanctions and revocations, and that takes its pack roots from the already-loaded org fragments, to feed both `doctor doctrine` and the repository's built-in-override architectural gate, so that the two can never adjudicate differently. | High | Open | build | no |
| FR-014 | Pack validation catches a bad sanction at authoring time | As an org-pack author, I want pack validation to parse the pack-root sanction file with the same parser. It reports an error for a malformed file or a directive entry without a reason, and an advisory for an entry the pack does not override. Then a broken sanction never ships. | Medium | Open | build | no |
| FR-015 | Pack assembly keeps sanctions | As an org-pack author, I want pack assembly to write the union of its input packs' sanction files to the assembled pack root, and to report an error when two inputs give the same URN different reasons, so that assembling packs never silently drops sanctions. | Medium | Open | build | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded I/O | `doctor doctrine` reads at most one pack-root sanction file per configured org pack, plus at most one legacy template per unsanctioned override. A test asserts this as a file-read count, not a timing. | Performance | Medium | Open |
| NFR-002 | Forward compatibility | A pack that ships the pack-root sanction file, and a consumer allowlist that carries `revoked_pack_sanctions`, each load with zero new errors or warnings on a CLI that predates this mission. | Compatibility | High | Open |
| NFR-003 | Code quality | New and changed code passes `ruff check`, `ruff format --check --force-exclude` and `mypy` with zero issues. Every function stays at McCabe complexity ≤ 15. No new suppressions. | Maintainability | High | Open |
| NFR-004 | Coverage | Every new branch and helper is executed by a focused test in the same change, and diff coverage is ≥ 90%. | Maintainability | High | Open |
| NFR-005 | Safe output | Every pack path, URN and reason that doctor prints is escaped for the console renderer, so that a crafted value can neither break nor alter the printed remedy. | Security | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No widening of strict schemas | Do not add fields to `OrgCharterPolicy`, `OrgPackConfig`, `PackManifest`, `PackDescriptor` or the org DRG fragment/node models. They all refuse unknown keys, so pre-fix CLIs would break. | Technical | High | Open |
| C-002 | No mutation at fetch time | `doctrine fetch` must not write or merge consumer governance files. | Technical | High | Open |
| C-003 | Single governance authority | Sanction semantics (parse, scope, union, revoke, decision table) live in `charter.offering.drg.override_policy`. Doctor, pack validation, assembly and the architectural gate only wire it in. The predicates stay free of I/O. | Architectural | High | Open |
| C-004 | Layer rules | `charter.offering` must not import `charter.activation` or `specify_cli` (`tests/architectural/test_layer_rules.py`). | Architectural | High | Open |
| C-005 | Merge behaviour unchanged | DRG merge behaviour is untouched; only docstring corrections are allowed. Precedence semantics belong to #2216 / #2592. | Technical | High | Open |
| C-006 | Project tier ungoverned | Project-tier overrides stay out of adjudication (`doctrine-governance-fidelity-01KW42KY#FR-012`). | Governance | High | Open |
| C-007 | Absorbable by #2594 | Introduce no governance concept beyond the existing `{urn, reason}` entry grammar plus consumer revocation. The ADR states how #2594 absorbs both. | Governance | Medium | Open |
| C-008 | Scope boundaries | Do not edit the external doctrine-org or doctrine-ps packs, or consumer repositories. Do not touch files owned by running missions: `implement.py` (#5635), `mission_creation.py` (#5634), consolidation rollback/reconciliation (#5686 / #5668), and the upgrade runner (#5457 / #4925). | Process | High | Open |

### Key Entities

- **Consumer allowlist**: `.kittify/doctrine/replaceable-builtins.yaml` in the consumer repository. It holds `replaceable_builtins: [{urn, reason}]`. New and optional: `revoked_pack_sanctions: [{urn} | {pack}]`, each with an optional reason.
- **Pack sanction**: `replaceable-builtins.yaml` at an org pack's resolved root (including any configured `subdir`), using the same `replaceable_builtins: [{urn, reason}]` grammar. It is effective only for overrides contributed by that pack.
- **Sanction source**: what sanctioned a given override. This is either the consumer allowlist or a configured pack, identified by its registry name from the consumer's configuration.
- **Built-in override**: an org-provenance DRG node that sits at a built-in URN after the three-layer merge.

## Success Criteria *(mandatory)*

### Measurable Outcomes

| ID | Outcome | Delivery | No-op passable? |
|----|---------|----------|-----------------|
| SC-001 | Regression "built-in promoted upstream, consumer allowlist stale": a fixture whose consumer file predates the promotion goes from RC=1 to RC=0 through the real `doctor doctrine` entry point, with zero edits to the consumer fixture. | build | no |
| SC-002 | Every negative case in US2 (cross-pack, missing directive reason, malformed file) still yields RC=1 through the real entry point. | ratchet | no (each paired with the SC-001 positive fixture) |
| SC-003 | All pre-existing override-policy, doctor-doctrine and architectural-gate tests pass unchanged, or with honest additive re-pins only. | ratchet | yes; SC-001 is the positive control |
| SC-005 | An architectural parity test proves that `doctor doctrine` and the built-in-override gate get their effective policy from the same loader. | build | no |
| SC-004 | The four reported URNs (`directive:ACTION_ITEM_ATTRIBUTION`, `directive:MINUTES_STAND_ALONE`, `agent_profile:minutes-mahad`, `paradigm:extract-then-publish-separation`), sanctioned only by a pack-root file, produce RC=0. | build | no |

## Assumptions

- The external doctrine-org and doctrine-ps packs will move their existing template to the pack root (a one-file move, outside this mission). Until they do, FR-009 gives consumers an exact workaround.
- Pack-root files are delivered by git and https pack sources (fetch keeps the whole tree) and by local-path packs. API-sourced packs do not carry them. That limitation is documented, not fixed.
- The pack-root sanction file has the same integrity as pack artifacts: git/https fetches hash the whole tree at fetch time, and local-path packs carry no integrity check. It is not recorded in the pack-manifest constituents, because their models refuse non-kind entries (C-001).
- Provenance identity is closed against spoofing. The loader stamps each fragment with the consumer's registry name and overrides any name the pack declares.
- Release impact is P1, not P0. The rc5 → rc6 built-in delta is empty, so rc6 introduces no new break.

## Out of Scope

- Editing the doctrine-org or doctrine-ps pack content, and refreshing consumer repositories. The operator refreshes: vanguard, ps-fleet, doctrine-ps-codegraph, gdm-mapping-validator, regnology-ps-chatbots.
- Reporting stale allowlist entries (URNs that are no longer built-in). This is an advisory that #2594 can carry.
- Built-in skill replacement through the allowlist (pack skills slice 3, ADR `2026-09-27-1`).
- `component-type` / `AUTHORITATIVE` enforcement (#2216, #2591–#2594).
- Adjudicating edges that a losing org pack contributes at a built-in URN, and edge-form `overrides`/`enhances` relations that target built-ins (pre-existing, #5769).
- The pack assembler's pre-existing loss of `org-charter.yaml` fields other than `required_directives` (pre-existing, #5770).
