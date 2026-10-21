---
work_package_id: WP15
title: Docs, changelog, agent instructions
dependencies:
- WP14
requirement_refs:
- C-009
- C-010
- FR-021
- FR-024
planning_base_branch: core-align-3-persistent-deactivation
merge_target_branch: core-align-3-persistent-deactivation
branch_strategy: Planning artifacts for this mission were generated on core-align-3-persistent-deactivation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into core-align-3-persistent-deactivation unless the human explicitly redirects the landing branch.
subtasks:
- T085
- T086
- T087
- T088
- T089
- T090
phase: Phase 10 - Docs and release notes
history:
- at: '2026-10-19T12:17:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
- docs/api/charter-commands.md
- docs/architecture/charter-pack-usage-journey.md
- docs/architecture/06_unified_charter_bundle.md
- docs/context/governance.md
- docs/migrations/charter-pack-cutover.md
- CLAUDE.md
- AGENTS.md
- packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml
- .kittify/glossaries/spec_kitty_core.yaml
- docs/development/docs-retrieval-index.yaml
- packs/built-in/*.graph.yaml
- packs/built-in/pack-manifest.yaml
- docs/api/cli-commands.md
- docs/adr/4.x/2026-10-19-1-activation-ledger-persists-deactivation.md
- docs/adr/4.x/2026-10-16-1-extract-charter-offering-first-activation-rework-post-ga.md
- docs/architecture/activation-ledger-and-charter-contract.md
- docs/adr/4.x/index.md
- docs/development/page-inventory.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP15 – Docs, changelog, agent instructions

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro` (`packs/built-in/agent_profiles/python-pedro.agent.yaml`)
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

This WP owns a `packs/` file and the root agent-instruction files, so it is `code_change`, not
`planning_artifact`.

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` in the event log; address every item; record with `spec-kitty agent tasks add-history WP15 --note "..."`.

---

## Objective

Bring every user-facing and agent-facing description of activation in line with what shipped:
the changelog (Breaking / Upgrade Notes / Added / Fixed under `## [Unreleased] - 4.0.0rc8`),
the command reference, the architecture and migration docs, the "Charter Activation" sections of
`CLAUDE.md` and `AGENTS.md`, and the glossary pack's "Active charter" definition.

## Context

- Plan IC-14; spec operator ruling `older_cli_downgrade` (documented downgrade hazard); C-009 tail (docs cite ADR `docs/adr/4.x/2026-10-19-1-activation-ledger-persists-deactivation.md`); C-010 (release line: target milestone "CLI 4.x stable" unless the operator says otherwise — say so in the PR body, not in docs).
- Describe only what the code now does; read the merged behaviour (WP02–WP14, after the flip: **one mode** — unmigrated projects read legacy allow keys and refuse deny writes; fresh projects and migrated ones use the ledger; no `SPEC_KITTY_ACTIVATION_STRICT`) rather than the plan where they differ, and record any difference in `traces/design-decisions.md`.
- Terminology: "Mission", never "feature"; "status commit", never "ceremony"; "Activation ledger" is never shortened to "the ledger" where the Migration Ledger is also in the paragraph.
- Editing a `packs/built-in/` file trips the pack-manifest regen gate: run `spec-kitty charter pack regenerate-graph` afterwards. It rewrites `packs/built-in/*.graph.yaml` (sharded DRG fragments) and `packs/built-in/pack-manifest.yaml`; this WP owns those files (F19). Commit whatever the regeneration produces; expect only the glossary-pack fragment and the manifest hash to change.
- Docs-only test policy: this WP changes no Python, so the baseline is the docs gates plus `make test-fast` as a smoke check.

## Branch Strategy

- **Strategy**: single_branch; sequential in the repository root checkout on `core-align-3-persistent-deactivation`.
- **Planning base branch**: `core-align-3-persistent-deactivation`
- **Merge target branch**: `core-align-3-persistent-deactivation`

```bash
spec-kitty agent action implement WP15 --agent claude --mission persistent-deactivation-ledger-01M59YAA
```

## ATDD note

No FR is implemented here. Red-first evidence: before editing, run
`grep -rn "NoActivationRestrictionsError\|activated_<kind>.*charter.yaml\|config.yaml.*activated_" docs CLAUDE.md AGENTS.md packs/built-in/glossary_packs`
and the docs gates; record the stale hits as the "red" list in your history note; the WP is done
when that list is empty (except immutable ADR history and released changelog sections).

## Subtasks

### Subtask T085: Changelog

**Steps**: under `## [Unreleased] - 4.0.0rc8` in `docs/changelog/CHANGELOG.md` (follow `make docs-lint` changelog style):
- **Breaking**: activation keys move from `charter.yaml` / `config.yaml` to `.kittify/charter/activation.yaml` (by `spec-kitty upgrade` or `spec-kitty migrate activation-ledger`); on an unmigrated project reads stay as before, but `charter deactivate` refuses until the project is migrated (`mission_pivot_option_b`); `NoActivationRestrictionsError` removed; `--preset X --force` now has two effects (overwrite customised keys **and** clear exclusions for the ids X lists).
- **Upgrade Notes**: deactivation requires the ledger — run `spec-kitty upgrade` or the narrow `spec-kitty migrate activation-ledger` (FR-021; on a project without a migration ledger it records nothing and a later upgrade re-skips it); fresh projects and `spec-kitty init` get the ledger automatically; run `spec-kitty upgrade` (migration `4.0.0rc8_activation_ledger`; refuses and changes nothing when two legacy copies disagree — fix by hand, re-run); older CLIs read every kind as absent (= all) after the move — do not downgrade a migrated project; activation keys an older CLI or a pre-cutover branch writes back into `charter.yaml` are ignored with a warning and reported by `spec-kitty doctor charter-packs`; the org required-selection overlay now includes `extends:`-inherited requirements.
- **Added**:
  - `deactivated_<kind>` exclusions;
  - `spec-kitty migrate activation-ledger [--dry-run] [--json]`;
  - `charter activate` accepts declared ids (#6423, R3);
  - `charter activate mission-type X --cascade` walks the mission type (FR-022);
  - `charter list --json` `deactivated` and `required_not_in_force` keys;
  - preset `--json` `kept_deactivated` / `cleared_exclusions` (only when non-empty);
  - doctor codes `ACTIVATION_UNMIGRATED`, `LEGACY_DENY_KEY`, `REQUIRED_OMITTED_BY_ALLOW_LIST` and the rest of §9;
  - `charter.activation.api` re-exports `deny_delta`; `--include-deactivated`; cascade "Skipped, deactivated" / "Unreached" report; required-artifact refusal naming the org pack; doctor activation-ledger findings; the ledger in the bundle hash.
- **Fixed**: a deactivation now persists across cascade, upgrade, interview, presets and synthesis (spec-kitty-charter #62, #63, #64, #66, #67 — cite as context, e.g. "see spec-kitty-charter#63").

### Subtask T086: Reference, architecture and migration docs

**Steps**:
1. `docs/api/cli-commands.md`: `spec-kitty migrate activation-ledger [--dry-run] [--json]` (FR-021: narrow ledger move, the same refusals, idempotent, the migration-ledger record, exit codes, JSON shape).
1a. `docs/api/charter-commands.md`:
    - `charter activate`: `--include-deactivated` in its own "Cascade options" help panel; `--force` has two effects; declared ids are accepted; the mission type is a cascade source (FR-022); the no-cascade warning (`referenced kind/id is deactivated and was not activated.`).
    - `charter deactivate`: the exclusion; the required refusal; the unmigrated refusal naming `spec-kitty upgrade`; cascade rendering.
    - `charter list`: the `deactivated` and `required_not_in_force` JSON keys.
    - Preset `--json`: `kept_deactivated` and `cleared_exclusions`.
    - **The shipped cascade output format**, one line per node:
      - `Skipped (out of scope): kind/id` (a denied one adds `(deactivated; nothing behind it was walked)`);
      - `Skipped, deactivated: kind/id (required by <urn> — the parent no longer has this requirement)`;
      - `Unreached (behind a deactivated artifact): kind/id`;
      - then `Hint: Run with --include-deactivated to activate these and clear their exclusions.`

      This is not data-model §7's old block headings.
    - Doctor finding codes and JSON shape (data-model §9).
    - `migrate activation-ledger` JSON (`ledger_record` ∈ `written` | `not_recorded`).

    Document the binding WP08 behaviour (T051.2: it records only when a migration ledger exists), not older planning-doc text.
2. `docs/architecture/charter-pack-usage-journey.md` and `docs/architecture/06_unified_charter_bundle.md`: ledger file, optional bundle member and hash member, the source resolver.
3. `docs/context/governance.md`: effective-set algebra summary and the deny-writer rule; link the glossary entries WP01 added.
4. `docs/migrations/charter-pack-cutover.md`: the rc8 ledger migration step, divergence refusal remedy, crash re-run.
5. Keep each page's front matter `updated:` current.

### Subtask T087: `CLAUDE.md` and `AGENTS.md`

**Steps** (also: the "Charter Cascade" examples are now true, via FR-022; add `--include-deactivated` beside them and note that the cascade stops at a deactivated artifact, and that `charter activate mission-type X` without `--cascade` prints the no-cascade warning for everything the mission type references): update the "Charter Activation and Doctrine Integrity Model" sections: activation lives in `.kittify/charter/activation.yaml` behind `charter.activation.activation_ledger`; deny lists and the explicit-choice writers; cascade stop-at-denied and `--include-deactivated`; required refusal; the `4.0.0rc8_activation_ledger` migration and the upgrade-only legacy scope; doctor codes. Keep both files consistent with each other; do not restructure unrelated sections.

### Subtask T088: Glossary pack entry

**Steps**: update the "active charter" definition in `packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml` (currently "… in .kittify/config.yaml or the charter.yaml it points to …") and the matching entry in `.kittify/glossaries/spec_kitty_core.yaml` if it carries the same text; add "activation ledger" if the pack lists comparable terms (mirror WP01's `docs/context/charter.md` wording). Then run `.venv/bin/spec-kitty charter pack regenerate-graph` and the pack tests.

### Subtask T089: ADR amendments, the divergence register and the contract replies

**Steps**:
1. Append a dated **Amendment 2026-10-20** to `docs/adr/4.x/2026-10-19-1-activation-ledger-persists-deactivation.md`, recording:
   - `mission_pivot_option_b`:
     - reads on an unmigrated project stay on the legacy allow keys;
     - deny writes there refuse;
     - the strict read and the fixture sweep move to the alignment epic (epic child #6535: retire the legacy activation reader);
     - the charter.yaml bootstrap allow-key copy and the `CharterYaml` activation fields stay until then;
   - `contract_document_scope` (homes stay; a future ACL maps them);
   - `required_always_active_divergence`;
   - `contract_rulings_r2_r12` (one line per R2–R12). For R8, record that the CLI verbs map 1:1: charter #125 answered request 4, so the contract's `select` clears the named id's own exclusion and `deactivate` records the exclusion and unselects. That is aligned, not a divergence;
   - `contract_epic_ga_milestone` (epic on milestone #11);
   - `mission_type_cascade_source` (FR-022, folded into WP07; the decision record's "a new WP" wording is superseded);
   - the reply to charter ADR-0020 "Requests to core":
     - item 1: answered "mapped at the seam" (the ledger keeps its unknown-key refusal);
     - the id-spelling request: answered by R3/R11;
     - the ADR 2026-10-16-1 amendment: R2;
   - residuals:
     - the legacy `.kittify/profiles` overlay still serves a denied profile id (outside the activation model, C-002/FR-007);
     - a hand-edited declared-id deny entry is not matched by the shipped `m_unify_charter_activation` promotion (raw spelling).
2. Append the R2 dated amendment to `docs/adr/4.x/2026-10-16-1-extract-charter-offering-first-activation-rework-post-ga.md`: after the 1.0.0 remote cutover the charter service is authoritative and core's file is the mapped local copy. The post-GA timing is superseded by `contract_epic_ga_milestone`.
3. The divergence register: link the FR-024 `divergences:` section of `tests/charter/conformance/activation_ledger_cases.yaml` from the ADR amendment and from `docs/architecture/activation-ledger-and-charter-contract.md`'s "Divergence register". Update that table's Status column for the rulings now made (R5, R7, R10, R11, required-on-read). **Keep** the "Activate" and "Deactivate" rows on the page, marked "Aligned (charter #125)" (R8, 1:1), and note the alignment under the ADR-0020 replies. The corpus `divergences:` list (WP10) holds only open divergences, so aligned rows live only on this page (pass-9 L1).
4. Refresh the ADR inventory if the tool requires it (`python -m scripts.docs.freshen_adr_inventory <file>`).

### Subtask T090: Docs gates and PR-body note

**Steps**: run the commands below; fix spelling/freshness findings; write the PR-body paragraph announcing the cutover for open branches. Include:
- P10: keys written by a pre-cutover branch are ignored with a warning;
- run `spec-kitty upgrade` or `spec-kitty migrate activation-ledger` after merging `main`;
- deactivation needs the ledger;
- a **Deferred** section citing the epic child (epic child #6535: retire the legacy activation reader), #6506 (latency, pre-existing; NFR-003 restated) and the pre-existing reds #6424, #6512, #5602 and #6513.

Put the paragraph into `traces/approach.md` so the orchestrator can paste it.

## Validation / targeted test surface

```bash
cd /home/user/spec-kitty
make docs-lint
.venv/bin/python -m scripts.docs.check_docs_freshness --ci
.venv/bin/python -m scripts.docs.docs_index --write
.venv/bin/python -m pytest -q tests/architectural/test_no_legacy_terminology.py
.venv/bin/python -m pytest -q tests/docs
.venv/bin/python -m pytest -q -n auto --dist loadfile -m "not timing and not stress" tests/charter_offering -k "glossary"
make test-fast
```

If `docs_index --write` changes generated index files outside `owned_files`, keep them and record the out-of-map edit with a one-line rationale.

## Standing orders

- python-pedro discipline applied to prose: precise, canonical sources, no invented behaviour.
- Append dated entries to the Mission's `traces/*.md`.
- Do not edit shipped migrations or released changelog sections.

## Definition of Done

- The stale-hit list is empty (outside immutable history).
- Changelog sections complete; docs pages and agent instructions describe shipped behaviour.
- Glossary pack updated and regenerated; docs gates green; subtasks marked done.

## Risks

- Describing planned rather than shipped behaviour: verify each statement against the code or a test.
- Pack regen touching more than the glossary fragment and the manifest: keep the regenerated output (owned), and record why in the history note.

## Reviewer Guidance

- Read the Upgrade Notes as a user about to upgrade: is the downgrade hazard unmistakable?
- Check `CLAUDE.md` and `AGENTS.md` agree.
