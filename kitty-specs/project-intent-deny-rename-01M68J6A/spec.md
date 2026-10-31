# Mission Specification: The project-intent rename carries a deny entry with it

**Mission Branch**: `main` (single-branch mission)
**Created**: 2026-10-31
**Status**: Ready for plan
**Input**: Issue #6565 — "The project-intent rename (#6443) does not rename a deny entry for the old
directive id". Operator ruling in the issue body (2026-10-21): document and follow up here; the
denial invariant of the persistent-deactivation mission (persistent-deactivation-ledger-01M59YAA#FR-014)
stays absolute for every path it pins.

## Summary

`rename_legacy_project_intent_directive` (#6443) rewrites the legacy
`NNN-mission-type-scope-directive` stem to `NNN-project-intent-directive` everywhere the directive is
named — artifact file, harness input, provenance, synthesis manifest, overlay label, and the
activation **allow** lists. It does not touch the activation ledger's deny lists
(`deactivated_directives`, ADR `2026-10-19-1` Decision 4, #6496–#6500).

When a project is deactivated by the old stem and the rename then runs (a refused or skipped earlier
rename, #6539; a later `charter synthesize` / `resynthesize` / upgrade retry), the deny entry keeps
naming a stem that no longer exists. The denial is reported as `DENY_UNKNOWN_ID` and silently stops
applying: the renamed `project-intent-directive` is back in force against the user's explicit
deactivation.

**This mission makes the rename move the exclusion with the artifact, through the same rename
authority and the same ledger seam**, so no second mapping exists and no path other than the pinned
one gains the power to change a deny list.

### Reproduced on `main` (35318ef5)

Ledger project with `activated_directives: [001-mission-type-scope-directive, DIRECTIVE_003]` and
`deactivated_directives: [001-mission-type-scope-directive]`, then
`rename_legacy_project_intent_directive(root)`:

```text
rename report: ("rewrite 'activated_directives' stem token(s) in .kittify/charter/activation.yaml",)
after ledger:  {'activated_directives': ['001-project-intent-directive', 'DIRECTIVE_003'],
                'deactivated_directives': ['001-mission-type-scope-directive']}
```

The allow list moved; the exclusion did not, and it now names an id that no longer exists.

### Approach chosen (from the two options in the issue)

**Carry the exclusion** (the issue's first option), not "refuse the rename". Refusing would fail a
migration on state the user cannot be expected to know about, and would leave `charter synthesize`
permanently broken on such a project. The rename authority already knows the old→new stem mapping
(`_rename_stem`); it renames the deny entry through the ledger's one writer with **one new sanctioned
`DenyListChoice.RENAME`**, and the deny-list gate allowlists exactly that one origin.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — A deactivated project-intent directive stays deactivated across the rename (Priority: P1) — #6565

A user deactivated `001-mission-type-scope-directive` on a ledger project. The project-intent rename
runs later. Today the exclusion is orphaned; after this mission it follows the artifact.

**Why this priority**: This is the defect. Losing an explicit deactivation is a silent governance
regression: the artifact the user removed comes back into force with no warning they can act on.

**Independent Test**: Seed a ledger project whose allow list and deny list both name
`001-mission-type-scope-directive`; run `rename_legacy_project_intent_directive(root)`; assert the
deny list is `['001-project-intent-directive']`, the allow list is renamed, and every other deny
entry is byte-identical. Then run it again and assert the report is empty (idempotent).

**Acceptance Scenarios**:

1. **Given** a ledger project whose `deactivated_directives` names the legacy stem, **When** the
   rename runs, **Then** that entry is rewritten to the target stem in the same single ledger write
   as the allow list, and the artifact stays excluded.
2. **Given** the same project, **When** `charter synthesize` (or `resynthesize`, or the
   `4.0.0rc8_project_intent_directive_rename` migration) drives the rename, **Then** the outcome is
   the same, because all three call the one helper.
3. **Given** the rename already ran, **When** it runs again, **Then** it reports nothing to do and
   writes nothing.
4. **Given** a deny list holding the legacy stem twice or both the legacy and the target stem,
   **When** the rename runs, **Then** the deny list holds exactly one target entry.
5. **Given** a deny list holding a declared id (`DIRECTIVE_003`) or any id that is not a legacy
   stem, **When** the rename runs, **Then** that entry is untouched.

---

### User Story 2 — Only the pinned rename write may change a deny list (Priority: P1) — #6565

The denial invariant (persistent-deactivation-ledger-01M59YAA#FR-014) — "no migration and no built-in preset removes a deny entry" — must survive.
The new capability is narrower than that: it moves one entry between two spellings of the same
artifact, and it is reachable from exactly one function.

**Why this priority**: The gate is what keeps `charter deactivate` the only thing that denies. A
fix that quietly widened it would trade one silent regression for a worse one.

**Independent Test**: The src-wide pins (`CHOICE_ORIGINS`, `DENY_CHANGE_FORWARDS`,
`DENY_KEY_MODULES`) name the helper's one origin and nothing else; the dynamic half still runs every
activation-touching migration over a deny-bearing fixture and compares the deny keys before/after; a
positive control on the same fixture family proves the pinned origin *does* rename the entry, so the
allowance is not stale.

**Acceptance Scenarios**:

1. **Given** the source tree, **When** the pins are recomputed, **Then** the only new
   `DenyListChoice.RENAME` origin is the rename helper's token step, and the only new
   `deny_change=` forward is that step passing its chosen value on.
2. **Given** any registered migration other than the rename, **When** it runs on its fixture,
   **Then** the deny entries are unchanged (the existing dynamic check, unchanged).
3. **Given** the rename's own fixture family with a legacy deny entry, **When** the rename migration
   runs, **Then** exactly one deny entry changes, old stem → target stem.
4. **Given** a throwaway migration that drops a deny entry with a raw write, **When** the dynamic
   check runs, **Then** it fails naming the offender (existing non-vacuity test, unchanged).

---

### User Story 3 — An unmigrated project is not touched, and is not newly refused (Priority: P2)

A pre-ledger project may carry a hand-written `deactivated_*` key on `charter.yaml` / `config.yaml`.
Such a key is never applied (ADR `2026-10-19-1` Amendment 2026-10-20), and the legacy save refuses to
change one. The rename must keep working there.

**Why this priority**: The rename runs during `spec-kitty upgrade` on projects that have not migrated
yet. A deny rename attempted on the legacy surface would turn a no-op into a refusal.

**Independent Test**: The existing legacy-surface fixtures (no ledger, pointer `charter.yaml` with
activation keys, including a hand-written `deactivated_directives`) run the rename to completion
with the deny key left exactly where it was.

**Acceptance Scenarios**:

1. **Given** an unmigrated project with a hand-written legacy deny key, **When** the rename runs,
   **Then** it does not raise, does not rewrite the deny key, and still renames everything else.
2. **Given** a fresh project with no ledger and no activation keys, **When** the rename runs,
   **Then** it reports nothing to do (no ledger is created).

---

### Edge Cases

- **Deny list unreadable / ledger invalid**: the existing preflight soft refusal applies — the
  rename reports the target unreadable and refuses rather than writing a guess.
- **`dry_run`**: the report lists the deny rewrite with the allow rewrite; nothing is written.
- **A deny entry for a kind that has no legacy stem** (tactics, skills, other directives): never
  matched, never rewritten.
- **Both spellings denied**: the rename collapses them to one entry (set semantics the ledger
  already enforces: sorted, unique).
- **Deny entry spelled by declared id** (`DIRECTIVE_003`): not a stem token, untouched — the same
  identity-space behaviour `charter deactivate` has.
- **A rename refused by a collision**: still refuses, changing nothing, deny entry included.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Rename carries the deny entry | As an operator, I want my deactivation of the project-intent directive to survive the #6443 rename so that the directive does not silently come back into force. | High | Open | [build] | no — same fixture proves the entry existed and moved |
| FR-002 | One rename authority, one seam write | As a maintainer, I want the deny entry renamed by the helper that already owns the old→new mapping, through the ledger's one writer, so that no second mapping or raw deny write exists. | High | Open | [build] | yes — an allow-only rename still produces exactly one write |
| FR-003 | One new sanctioned choice | As a maintainer, I want the authority to change a deny list to be a single named `DenyListChoice.RENAME` minted in exactly one function, so the deny-list guard (persistent-deactivation-ledger-01M59YAA#FR-014) still refuses every other path. | High | Open | [ratchet] | no — a second origin fails the pin |
| FR-004 | The deny-list gate pins the allowance | As a reviewer, I want the deny-list gate to name the new origin in both directions and keep its dynamic check plus a positive control, so the allowance is provably used and cannot silently widen. | High | Open | [ratchet] | no — a stale allowance fails the positive control |
| FR-005 | Legacy deny keys are left alone | As an operator on an unmigrated project, I want the rename to keep working and to leave my hand-written legacy deny key untouched, because it was never applied there. | Medium | Open | [build] | no — the fixture carries the key and asserts it unchanged |
| FR-006 | Docs state the fifth path | As a maintainer, I want ADR Decision 4, the AGENTS.md activation rule and the charter command docs to name the rename as the fifth deny-list path and its exact limit, so the contract matches the code. | Medium | Open | [build] | no — the ADR text is asserted by review, the changelog by entry |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Idempotent, atomic | A second rename run performs zero writes; the deny rename lands in the same single ledger write as the allow rename, so an interrupted run leaves no half-renamed pair. | Reliability | High | Open |
| NFR-002 | No behaviour change off the legacy state | Projects without a legacy stem in any activation list perform exactly the writes they perform today. | Compatibility | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Reuse the existing mapping | The deny rename reuses `legacy_rename`'s `_rename_stem` / `_target_filename`; no new slug table, alias map or second spelling authority is introduced. | Technical | High | Open |
| C-002 | One writer | The deny entry is written only through `resolve_activation_write_target`'s save, which reaches `prepare_ledger_write`; no raw YAML write of a deny list. | Technical | High | Open |
| C-003 | The deny guard stays absolute elsewhere | Every path ADR Decision 4 pins keeps `DenyListWriteRefused` (persistent-deactivation-ledger-01M59YAA#FR-014); `RENAME` is not reachable from any preset, interview, promotion, or other migration. | Regulatory | High | Open |
| C-004 | Authority only where deny is authoritative | A deny key is renamed only on the activation ledger; a legacy surface's deny key is never applied, so it is never rewritten. | Technical | High | Open |
| C-005 | No new public surface beyond the enum member | The change adds one `DenyListChoice` member (already re-exported by `charter.activation.api`) and no new public function or module. | Technical | Medium | Open |

### Key Entities

- **Deny entry**: one id in `deactivated_<plural>` of the activation ledger. Compared as a set;
  spelled as the artifact's stored stem, its declared id, or a URN.
- **The rename report** (`RenameReport`): the preflight's per-change lines, one per rewritten
  activation key; the deny rewrite appears as its own line and its key name.
- **`DenyListChoice`**: the enumerated authorities (`activate`, `deactivate`,
  `cascade-include-deactivated`, `preset-force`, and now `rename`) that may change a deny list.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The issue's reproduction (ledger with allow and deny on the legacy stem, then the
  rename) leaves the deny list holding the target stem and not the legacy one; a second run reports
  no actions. — [build] · no-op passable: no
- **SC-002**: Every other deny entry in the fixture (a directive by declared id, a tactic, a skill) is
  byte-identical after the rename. — [build] · no-op passable: no
- **SC-003**: The deny-list gate's pins are exact in both directions and its dynamic check still fails
  a throwaway deny-dropping migration; the new positive control fails if the rename stops renaming.
  — [ratchet] · no-op passable: no
- **SC-004**: The three entry points (`rename_legacy_project_intent_directive`, the rc8 migration,
  `charter synthesize`) reach the same end state on the same fixture. — [build] · no-op passable: no

## Out of Scope

- Retiring the legacy activation reader (#6535) and the persistent-deactivation epic's own scope.
- A general alias mechanism for directive ids outside the project-intent rename (no second mapping,
  per C-001 and the issue's framing).
- `#6539` (the rename skipped when there is no git repository): unchanged and still a valid trigger,
  which this mission makes harmless rather than fixing.
- Rewriting a deny entry that names a *declared id* (`PROJECT_001` / `DIRECTIVE_003`): ids are not
  renamed by #6443 and stay valid.
