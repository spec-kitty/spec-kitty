# Mission Specification: Interview and first activate keep an absent activation key absent

**Mission Branch**: `issue-6685-interview-and-first-activate-keep-absent-key-absent`
**Created**: 2026-10-30
**Status**: Draft
**Input**: GitHub issue #6685 (refs #6629, #6678, #6683, #6408, #4253, #4400, #2577, #4785). The mission applies the ruling that #6629 / #6683 merged for the upgrade caller — an absent `activated_<kind>` key means "everything in force", so writing a list changes its meaning — to the two operator-time writers the issue names. The open question the PR carries is recorded under "Open Questions".

## Intent Summary

- **Primary actor:** a project owner who has run `spec-kitty charter interview` on a project whose `activated_<kind>` keys are absent (a fresh project, or one the #6629 upgrade left absent).
- **Trigger:** they run `charter interview` (any selection, without `--narrow-activation`), or the first `charter activate <kind> <id>` for that kind without `--only`.
- **Defect:** both writers materialise the kind's whole in-force set into the absent key (38 directives, 14 paradigms on the built-in pack) before appending the selection. Runtime governance does not change — the set written is what was already in force — but `charter synthesize` reads a *present* list as an operator's activation. It then demands one companion tactic per directive and skips the fresh-project seed, and `implement` refuses every work package with `synthesized_drg missing`. That is the #6629 block, re-created at operator time.
- **Desired outcome:** neither writer turns an absent key into a list. The key stays absent, so synthesis keeps treating the project as having made no activation choice, and every artifact that was in force stays in force.
- **Rule that must always hold (zero drop):** every artifact in force before either writer runs, and every selection that resolves and is not deactivated, is in force after it. `--narrow-activation` and `--only` remain the explicit, unchanged way to *choose* a list, and they are the only way a selection narrows what is in force.
- **Boundary:** the upgrade's own promotion (#6629, #6683) and the org-required union are already correct and are not touched. Kinds whose absent key does **not** put the artifact in force — `mission-type`, and the `required`-when-absent `skill` kind — keep materialising exactly as today, because for them not writing would silently lose the activation.

## Open Questions (for the operator)

1. **Ruling conflict, recorded deliberately.** The triage comment on #6685 records *option (b)*: keep the default (an operator-time writer still fills an absent key from the in-force set) and teach `charter synthesize` to tell a filled list from an operator's choice. This mission implements the opposite (*option (a)*), because that is what #6629 and #6683 already merged for the upgrade caller, what the org-required union already does ("an absent key is never seeded"), and what this run's dispatch names: an absent key means "everything in force", so writing a list changes its meaning, and the write must stop. Option (b) would need provenance the activation ledger does not record. **This needs a maintainer decision**; the PR states it and does not pretend the question is settled.
2. **Lists already seeded by an earlier build.** A project an earlier build (or a pre-fix interview) already seeded keeps its list; this mission never narrows or clears an existing list (#6499). Should a later mission reset a list that is set-equal to the full in-force set? Out of scope here, same as #6684.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Interview on a project with absent activation keys (Priority: P1)

A project owner runs `charter interview --defaults --selected-directives <id> --selected-paradigms <id>` on a project whose `activated_directives` and `activated_paradigms` keys are absent. Nothing is written into either key. The interview still records the choices in `answers.yaml`, and it says, per kind, that the whole kind is already in force, so nothing had to be written, and that `--narrow-activation` is how to make the selection explicit.

**Why this priority**: this is the reported defect (#6685, P1). It blocks `implement` on any project whose first charter step is the interview.

**Independent Test**: build a project with no activation keys, run the interview through the CLI with a selection, then check that no `activated_<kind>` key exists on the activation surface, that `_catalog_is_established` is `False`, and that `charter synthesize --dry-run --json` reports `fresh_project_seed_dry_run`.

**Acceptance Scenarios**:

1. **Given** a project with no `activated_<kind>` key, **When** the owner runs `charter interview` with selections and without `--narrow-activation`, **Then** no `activated_<kind>` key is written for any promoted kind, and the output names each key that stayed absent.
2. **Given** that project, **When** the owner runs `charter synthesize --dry-run --json`, **Then** it reports `fresh_project_seed_dry_run`, exactly as for a project that never ran the interview.
3. **Given** the same project, **When** the owner runs the interview with `--narrow-activation`, **Then** each kind's list is the selection plus the org-required ids, as today.

---

### User Story 2 - First `charter activate` on a project with an absent key (Priority: P1)

A project owner runs `charter activate directive <id>` — no `--only` — on a project whose `activated_directives` is absent. The directive is already in force (the absent key means every available directive is in force), so nothing is written: the key stays absent and the output says the activation changes nothing and that writing a list would freeze the kind.

**Why this priority**: the second half of the reported defect, and the same `synthesize` block. It is also the #4253 surface, so the zero-drop rule has to hold here in a stronger form than before.

**Independent Test**: build a project with no activation keys, run `charter activate directive <id>` through the CLI, then check the key is still absent, that every directive effective before is still effective, and that `charter synthesize --dry-run --json` reports `fresh_project_seed_dry_run`.

**Acceptance Scenarios**:

1. **Given** an absent `activated_directives` key and an artifact the effective set already has in force, **When** the owner runs `charter activate directive <id>` without `--only`, **Then** no allow list is written, `PackContext.activated_directives` is still `None`, and every artifact that was in force is still in force.
2. **Given** the same project, **When** the owner runs `charter activate --only`, **Then** the list is the selection plus the org-required ids and the output names what stopped being in force (unchanged, #6408).
3. **Given** an absent key and an id that is *not* in force (an unresolved effective set, a `required`-when-absent `skill`, or `mission-type`), **When** the owner activates it, **Then** the list is materialised as today, so the activation is not lost.

---

### User Story 3 - Present lists, deny lists and re-runs are unchanged (Priority: P2)

A project owner with an explicit `activated_directives` list runs the interview: the selection is appended to the present list exactly as today. An owner who deactivated an artifact and then activates it: the exclusion is cleared exactly as today (`deny-only`, allow list still absent). An owner who re-runs either writer: nothing changes, and no byte changes on disk.

**Why this priority**: the change must not narrow an operator's list, must not touch a deny list, and must not make re-runs write.

**Independent Test**: on a fixture with a present list, run the interview and assert the list gains exactly the missing selection; on a fixture with a denied id, activate it and assert the deny entry is gone and no allow list appeared; run both writers twice and assert the activation files are byte-identical.

**Acceptance Scenarios**:

1. **Given** a present `activated_directives` list, **When** the owner runs the interview with a selection the list lacks, **Then** the list gains exactly that id on the authoritative activation surface, and no other entry changes.
2. **Given** a deactivated directive and an absent `activated_directives`, **When** the owner activates it, **Then** its `deactivated_<kind>` entry is removed and the allow key stays absent.
3. **Given** any fixture of this mission, **When** either writer runs a second time, **Then** `config.yaml`, `charter.yaml` and `activation.yaml` are byte-identical to after the first run.

---

### Edge Cases

- **`--narrow-activation` with an empty selection, or `--only` with an unavailable id:** unchanged — a kind with an empty selection is never narrowed, and an unavailable id still raises `UnknownActivationIdError` before any write.
- **Unresolved effective set:** `charter activate` keeps today's tolerant materialisation from the readable chain, because "already in force" cannot be positively asserted there. The interview writes nothing and says so.
- **`mission-type`:** its absent key puts *nothing* in force, so a first `activate mission-type` still materialises the chain-wide list; skipping the write would lose the activation.
- **`skill` (`effective_when_absent == "required"`):** the absent key puts only the org-required skills in force, so activating a non-required skill still writes the list; the documented behaviour ("the first `activate skill <id>` writes it") is preserved.
- **Org-required ids:** the union that adds them already refuses to seed an absent key; it is not touched.
- **Cascade activation** (`activate <kind> <id> --cascade ...`): each cascaded activation goes through the same manager call, so a cascade target that is already in force writes nothing either; a target that is not in force still materialises.
- **Interview on a project whose keys live in the activation ledger:** the same rule applies to the ledger's allow keys, not to `config.yaml`.
- **A project an earlier build already seeded:** its list is left as it is (#6499); this mission does not clear it.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Interview never fills an absent key | As a project owner whose activation keys are absent, I want `charter interview` to promote a selection into a *present* list only, so that the project keeps its "nothing chosen yet" state. | High | Open | [build] | no — red on main: the interview writes a 38-entry directive list and a 14-entry paradigm list |
| FR-002 | Interview names what it left absent | As that owner, I want the interview output to name each key it left absent and to say the kind is already in force and that `--narrow-activation` writes the list, so that nothing changes silently. | High | Open | [build] | no — the message is asserted, and its absence on a present-list run |
| FR-003 | First activate keeps an in-force artifact implicit | As a project owner, I want `charter activate <kind> <id>` without `--only`, on an absent key of an `all`-when-absent kind, to write no allow list when the artifact is already in force, so that a first activation does not freeze the kind. | High | Open | [build] | no — red on main: the key is written with the whole in-force set |
| FR-004 | Activate still materialises where absence is not "all" | As a project owner, I want `mission-type`, a `required`-when-absent kind, an unresolved effective set, or an artifact that is not in force to still materialise the list on activation, so that no activation is silently lost. | High | Open | [ratchet] | yes — paired with a positive assertion per row (`mission_type_activations` written, skill list frozen, unresolvable fixture seeded, unknown id refused) |
| FR-005 | Zero drop | As a project owner, I want every artifact in force before either writer, and every resolving selection, to still be in force after it, measured through the consumer surfaces. | High | Open | [build] | no — the end-to-end fixture asserts it through `PackContext` / the activation-aware service |
| FR-006 | Synthesis is unblocked | As a project owner, I want `charter synthesize --dry-run --json` after either writer to report `fresh_project_seed_dry_run` and `_catalog_is_established` to stay `False`, so that `implement` can proceed. | High | Open | [build] | no — red on main through both end-to-end fixtures |
| FR-007 | Present lists, denies and `--only` unchanged | As a project owner, I want a present list to keep append semantics, a deny list to stay untouched by the interview and to be cleared only by an explicit activation, and `--only` / `--narrow-activation` to keep their contract. | High | Open | [ratchet] | yes — paired with FR-001: the same fixture asserts the present list gains exactly the missing id |
| FR-008 | Re-runs write nothing | As a project owner, I want a second run of either writer to change no byte on the activation surface. | Medium | Open | [build] | no — byte equality is asserted after a second run |
| FR-009 | The FR-015 acceptance matrix follows the rule | As a maintainer, I want the `interview` and the activating caller rows of `test_fr015_promotion_preserves_effective_set` to expect the key to stay absent, keeping every zero-drop assertion, so that one caller cannot drift back alone. | Medium | Open | [build] | no — the rows are red on main for exactly these two callers |
| FR-010 | Docstrings and docs state the rule | As a maintainer, I want the docstrings that call the interview seeding "the #6408 residual", and the operator docs for `charter interview` / `charter activate`, to state that an absent key is never filled, so that the next reader does not re-introduce it. | Medium | Open | [build] | yes — the docs check is paired with FR-001's behaviour assertion |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No extra resolution | The interview resolves no effective set on the non-narrowing path (it no longer needs one), and the activation resolves the set it already resolves; no new ledger or file read is added. | Performance | Medium | Open |
| NFR-002 | Idempotence | A second run of either writer changes 0 bytes across `config.yaml`, `charter.yaml` and `activation.yaml`, and does not append to a list. | Reliability | High | Open |
| NFR-003 | Code quality | New code passes ruff and `ruff format --check`, mypy with zero findings, every function stays at cyclomatic complexity 15 or less, and diff coverage of the change is at least 90%. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | An absent key means everything in force | No writer may narrow what is in force. Not writing leaves the unrestricted state; writing a subset would narrow it, which is why the materialisation is what has to go. | Business | High | Open |
| C-002 | Activation-ledger schema unchanged | No new key in `.kittify/charter/activation.yaml`; writes keep going through `resolve_activation_write_target` and the activation ledger seam, so the deny guard applies (ADR 2026-10-19-1). | Technical | High | Open |
| C-003 | Explicit narrowing keeps its contract | `--only` / `--narrow-activation` stay opt-in, keep naming what stopped being in force, and are the only paths that write a list into an absent key (#6408, #6457, #6458). | Technical | High | Open |
| C-004 | No upgrade or migration change | #6629 / #6683 already fixed the upgrade promotion; no migration, supersession or order-manifest entry changes here. | Technical | High | Open |
| C-005 | Required-when-absent and mission tier untouched | `skill` (`effective_when_absent == "required"`) and `mission-type` keep materialising, because their absent key does not put the artifact in force. | Technical | High | Open |
| C-006 | Existing lists are never narrowed | A list an earlier build or an operator wrote is never cleared or trimmed by this mission (#6499, #6684 territory). | Business | High | Open |
| C-007 | Single write seam | Both writers keep their one write seam: the interview through `promote_activations`, the activation through `plan_activation` + `commit_plan`. No direct `save` call is added. | Technical | High | Open |

### Key Entities

- **Absent key**: an `activated_<kind>` key that is not on the activation surface. For every kind except `skill`, it means "every available artifact of that kind is in force".
- **In-force set**: what a kind has effective while its key is absent (`resolve_effective_sets`), less the effective deny.
- **Activation surface**: the activation ledger (`.kittify/charter/activation.yaml`), or, on an unmigrated project, the `charter.yaml` that `config.yaml` points to, or `config.yaml` itself.
- **Interview selection**: the `selected_<kind>` ids in `.kittify/charter/interview/answers.yaml`. A record of the interview, not an activation source.
- **Promotion**: appending ids into a present `activated_<kind>` list through `promote_activations`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the #6685 project shape, an interview with a selection leaves 0 `activated_<kind>` keys behind (from 2 on main), and `charter synthesize --dry-run` reports `fresh_project_seed_dry_run`. — [build] · no-op passable: no
- **SC-002**: On the same shape, a first `charter activate <kind> <id>` leaves 0 allow lists behind (from 1 with 38 entries on main) and deactivates 0 artifacts. — [build] · no-op passable: no
- **SC-003**: 100% of artifacts in force before either writer, and of resolving non-deactivated selections, are in force after it, in every fixture of the mission's tests. — [ratchet] · no-op passable: yes (paired with SC-001/SC-002)
- **SC-004**: A second run of either writer changes 0 bytes on the activation surface. — [build] · no-op passable: no
