---
work_package_id: WP04
title: '[PR A] P3a Resolved-state mapping (FR-020, documentation only)'
dependencies:
- WP03
requirement_refs:
- FR-020
- C-007
planning_base_branch: issue-957-mission-status-read-api-mission-detail
merge_target_branch: issue-957-mission-status-read-api-mission-detail
branch_strategy: Planning artifacts for this mission were generated on issue-957-mission-status-read-api-mission-detail. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-957-mission-status-read-api-mission-detail unless the human explicitly redirects the landing branch.
subtasks:
- T026
- T027
- T028
- T029
history: []
agent_profile: planner-priti
authoritative_surface: kitty-specs/mission-status-read-api-mission-detail-01M4S6D5/
create_intent:
- kitty-specs/mission-status-read-api-mission-detail-01M4S6D5/data-model.md
execution_mode: planning_artifact
model: sonnet
owned_files:
- kitty-specs/mission-status-read-api-mission-detail-01M4S6D5/data-model.md
role: planner
tags: []
tracker_refs: []
---

# Work Package Prompt: WP04 – [PR A] P3a Resolved-state mapping (FR-020, documentation only)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `planner-priti`
- **Role**: `planner`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Pull request and dependencies

- **Pull request**: **PR A** (draft; phase tag **P3a**). PR A stacks on the branch carrying #5529's last slice; the operator retargets it to `main` after #5529 lands. No agent pushes, opens or retargets a PR.
- **Depends on**: WP03 (P1b), through WP01 -> WP02 -> WP03. This is deliberate: the order of D-44 is campsite (P1, P1a, P1b), then this mapping, then P3 as the first functional change. **External dependency (not a `dependencies` entry)**: the #5529 re-cut tip merged into the branch by the orchestrator, which WP01 needs; this WP writes no Java path, so it does not depend on the re-cut layout itself, only on the order.
- **Dependents**: WP05 (P3) implements the reduction from this mapping and is pinned by it; WP07 (P4) and WP08 (P4b) **append** their sections to the file this WP creates (named edits of theirs, listed below for context); WP08's `resolved-state` goldens are generated from this mapping.
- **Write scope**: `owned_files` only: the single file `M/data-model.md`. This is a **`planning_artifact`** WP: every owned entry is confined to `kitty-specs/`, so it is exempt from the `INVALID_WP_OWNED_FILES_KITTY_SPECS` rule that bans `kitty-specs/` paths from a `code_change` WP.
- **Named edits (out-of-map)**: none. (The tracer files are append-only; if you observe a tooling friction, append one dated entry to `M/traces/tooling-friction.md`; never in `owned_files`.)
- **Later writers of the file you create** (for orientation only, you do not write their sections): WP07 (P4) appends the manifest classes and `PROVISION_PLAN`; WP08 (P4b) appends the `resolved-state` class. Rule: they append, they never edit above their section. Leave the document structured so appending is natural (end each section with a blank line; no trailing "end of file" marker).

**Path aliases** (repo-relative): `M` = `kitty-specs/mission-status-read-api-mission-detail-01M4S6D5`; `S` = `services/mission-status-api`; `J` = `S/src/main/java/org/speckitty/missionstatus`; `T` = `S/src/test/java/org/speckitty/missionstatus`; `R` = `S/src/test/resources`. Package root `org.speckitty.missionstatus`. `PY_REDUCER` = `.venv/lib/python3.11/site-packages/spec_kitty_events/diary.py` (module `spec_kitty_events.diary`), `PY_STATUS` = `src/specify_cli/status/`, `ORACLE` = `tests/contract/_mission_status_payloads.py`.

## Objective

Write `M/data-model.md` as its first commit: the member-to-source mapping for every FR-020 member (assignment, subtasks, review result, review override, actor, ordered history, `lifecycleTypes`), each citing the symbol in `spec_kitty_events.diary.reduce_parsed` and `specify_cli.status.reducer.wp_snapshot_state` that produces it, the oracle field it is checked against, the markers rule for `lifecycleTypes` (D-98), and the statement that no `src/` file changes (C-007). **Documentation only; no code.** It also holds the section **Member-to-route list** (AC-8.4, plan section 8 FRESH3-003): the 26 (row, route) pairs of the projection rows T1 to T18, per route. `getMission` (WP13, 7 pairs): T1, T2, T3, T4 for the head and, for the `WorkPackageSummary`, T5, T6, T10. `getWorkPackage` (WP14, 10 pairs): T5, T6, T7, T8, T10, T11, T12, T13, T14, T17. `getWorkPackageDetail` (WP15, 9 pairs): T1, T5, T7, T8, T9, T15, T16, T17, T18. WP18's `ProjectionRowCoverageTest` asserts against this list.

## Context

- Why this WP exists (plan section 11, "Phasing"; D-110): P4 generates the `resolved-state` goldens from a member-to-source mapping that P3 derives, and P3 is pinned by those goldens. That would be a cycle, so the mapping is its own first phase (P3a): P3 implements from it, P4/P4b generate the goldens from it, and each is pinned by the other without a cycle.
- FR-020 (spec section "Functional requirements"): the Java reducer of #5529 keeps `lane`, `lastTransitionAt`, `lastEventId`, `forceCount`, the cancellation provenance and `implementerOfRecord` per Work Package. The Work Package routes need more of what `materialize_snapshot` and `reconstruct_wp_view` (`PY_STATUS/wp_view.py`, `ResolvedGroup`) resolve: the `assignment` handles (`agent`, `assignee`, `role`, `agent_profile`, `agent_profile_version`, `model`, `provider`), the resolved `subtasks` map, the latest `review_result` and the review override, the `actor` of the latest change, and the ordered transition `history`. It must be produced under the same ordering by `(at, event_id)` and the same oracle gate; the overview must not change (AC-20.2).
- Acceptance criteria this mapping must make checkable (spec): AC-20.1 (member-by-member parity against the oracle on the conformance ledgers plus a new `resolved-state` class holding set / overwrite / clear transitions, the model-absent sentinel shown as null, each review verdict, a partial and a release-marker override), AC-20.3 (history: mixed `Z`/fraction/offset stamps, annotation / lifecycle / retrospective rows between them, transitions only, ordered by parsed instant then `eventId`, `force` true only for the literal `true`), AC-20.4 (the domain stays pure: rules 1 and 12 of `ArchitectureRules`), AC-20.5 (cache growth, NFR-009).
- C-007: nothing under `services/` enters the Python wheel and **no `src/` production code changes**. This WP writes no code at all; the document must say so.
- C-004 / archive freeze: `M/**` is not on `main` while PR A is open, so creating a new `M/data-model.md` is allowed. After PR A lands, `tests/architectural/test_archive_root_byte_identical.py` fails any modification of an `M/**` file already on `main`; this is why later phases only **append** (and why a WP04 edit after PR A lands is not possible: fork E-12, plan section 14).
- No Gradle gate applies (no Java line changes): Gate G and Gate P are **not** part of this WP's exit (plan 11: "every phase that names Gate G (P1 to P13 but P3a)").

---

### Subtask T026: Create `M/data-model.md` (first commit) with the member-to-source mapping

**Purpose**: the single mapping P3 implements from and P4b generates goldens from. Every FR-020 member gets a cited source symbol, so no later WP re-derives the oracle by reading Python.

**Steps**:
1. Create `M/data-model.md` in a **first, document-only commit** (commit message prefix `docs(mission)`; say "FR-020 mapping, documentation only (WP04, P3a)").
2. Document skeleton (the headings are the contract with the appenders; keep them):
   - `# Data model: resolved Work Package state (FR-020)`
   - `## 1. Scope and non-goals` (FR-020 members only; overview unchanged; no `src/` change, C-007; no Java line in this document; how WP07 and WP08 append)
   - `## 2. Sources` (the two symbols the plan names plus the supporting ones, each with module and function name, never a line number: line numbers drift)
   - `## 3. Member-to-source mapping` (the table of T026 step 3)
   - `## 4. Per-member rules` (T026 step 4)
   - `## 5. lifecycleTypes and the markers rule (D-98)` (T027)
   - `## 6. Oracle field checklist` (T028)
   - `## 7. Pinned behaviours` (T028 step 3)
   - `## 8. Member-to-route list` (the 26 (row, route) pairs of the Objective: getMission 7, getWorkPackage 10, getWorkPackageDetail 9; T1 to T18 each at least once; WP18's `ProjectionRowCoverageTest` asserts against it)
3. The mapping table (section 3). Columns: **FR-020 member** | **snapshot slot or row source** | **Python source symbol (writer)** | **Python read symbol** | **Java target (planned; P3)** | **Oracle field**. Start from the rows below, **and verify each against the source before committing** (the symbols exist at `PY_REDUCER` and `PY_STATUS`; if a symbol or behaviour differs from what is written here, the source wins, and you record the correction in the document):
   - **assignment.agent**: slot `agent`. Writers: `planned -> claimed` transition sidecar `policy_metadata.agent` (written only when truthy) through `_claim_sidecar_writes` in `_wp_state_from_event`; annotation delta `agent` (a `_REPLACE_SLOTS` entry, latest-wins by `(at, event_id)`, `""` is a no-op); cleared by `release_runtime_claim` (applied before the replace loop) in `_apply_annotation_delta`. Read: `specify_cli.status.wp_view._resolved_group` (`_opt_str`). Java: `Assignment.agent`. Oracle: `assignment.agent` in `build_work_package`.
   - **assignment.assignee**: slot `assignee`; annotation delta only (replace slot). Read as above. Oracle: `assignment.assignee`.
   - **assignment.role**: slot `role`; annotation delta (replace slot). Read via `_opt_str` (no sentinel). Oracle: `assignment.role`.
   - **assignment.agentProfile / agentProfileVersion / model / provider**: slots `agent_profile`, `agent_profile_version`, `model`, `provider`; annotation delta (replace slots). Read: `_resolved_group` normalises the internal sentinels `RESOLVED_PROFILE_ABSENT`, `RESOLVED_PROFILE_VERSION_ABSENT`, `RESOLVED_MODEL_ABSENT`, `RESOLVED_PROVIDER_ABSENT` (module `specify_cli.status.resolved_binding`) to `None`, so the sentinel string never leaks. Oracle: `assignment.agentProfile`, `.agentProfileVersion`, `.model`, `.provider`, each through `projector.handle` (a sentinel or a non-handle shape reads null).
   - **subtasks**: slot `subtasks` (id -> status string), per-subtask replace merge from the delta's `subtasks` (`str(status)`), carried across transitions by `_RUNTIME_SLOTS`. Read: `{str(key): str(value)}`. Java: `WpResolved.subtasks` (an ordered map; emission order is a route concern: S-15). Oracle: `subtasks` (keys strict-projected against the relative-reference pattern) and its derived `subtaskProgress` (`_subtask_progress`: `done` count and `total`), which is computed from the map, not stored.
   - **review result**: slot `review_result`. Written in `_wp_state_from_event`: any event carrying a populated `ReviewResult` populates it; otherwise a transition with `from_lane == in_review` writes an explicit `None` (a forced exit with no verdict); otherwise the slot is carried forward verbatim (sticky); never-reviewed leaves it **absent**. Provenance rules for reconstruction seeds are in `_record_applied_event` / `_fold_losing_seed` (`_VERDICT_SLOT`). Read: `specify_cli.status.reducer.review_result_from_state`. Java: `ReviewResultRecord(reviewer, verdict, reference)` (`feedback_path` is not exposed). Oracle: `review.latestResult` via `_review_result`: not a mapping (absent or `None`) is null; else `{reviewer: handle, verdict: raw, reference: human-projected with "" for a missing reference}`.
   - **review override**: slot `review` (note: distinct from `review_result`; both may be populated at once, precedence is a consumer's). Written by the annotation delta `review` (a `ReviewOverride` with `at`, `actor`, `wp_id`, `reason`): replace, **except** the all-empty release sentinel (`ReviewOverride.is_release_sentinel`) which clears the slot to `None`; a **partial** record is persisted. Read: `_resolved_group` takes the mapping or `None`. Java: `ReviewOverrideRecord(at, actor, wpId, reason)` with the `complete` predicate. Oracle: `review.override` via `review_override`: null for no record or the release marker; else `{complete, at, actor, reason}`; `wp_id` is read for the rule and not shown; `complete` is plain truthiness of the four strings (whitespace is a value); `at` is null on a partial record when it is not an instant; a record the code calls complete with a non-instant `at` cannot be shown as complete (the projection fails).
   - **actor**: slot `actor`, set on every **applied transition** by `_wp_state_from_event` as `actor_identity_str(event.actor)` (a structured actor projects to its `tool`, else `role`, else `""`; a string is verbatim) and seeded by `_runtime_only_wp_state` for an annotation-only Work Package; **annotations do not change it**. Java: `WpResolved.actor`. Oracle: `actor` via `projector.actor(state.get("actor"))` (a plain string reads as `{tool: handle, role: null, profile: null}`).
   - **ordered history**: **not a snapshot slot.** Built from the raw rows. Oracle: `history_entries`: every row with a `to_lane` key and `wp_id` equal to the Work Package, as `{eventId, at, kind: "transition", fromStatusLane, toStatusLane, actor (projector.actor of the row's own actor, possibly structured), force (row.force is True, the literal), reason (human-projected), reviewVerdict (row.review_result.verdict or null)}`, sorted by `_history_order_key` (the parsed instant; a non-instant sorts after every real one; event id breaks ties). Java: `HistoryRow` plus `domain.readmodel.derive.HistoryOrder`, kept per Work Package in `WpResolved.history`.
4. Section 4 (per-member rules) states for each member: absent versus explicit-null (for `review_result`, absent and `None` both read null in the oracle, so keep the distinction only if it is free), the folding order (transitions first, folded under rollback-aware precedence; **annotations in a dedicated post-pass sorted by `(at, event_id)`**, the same key, so a same-`at` transition never clobbers an annotation slot and annotations never bump `force_count`), the overwrite / clear semantics (replace slots latest-wins; `""` is a no-op; `release_runtime_claim` clears the claim triple `agent`, `shell_pid`, `shell_pid_created_at`), and dedupe by `event_id` (the reducer keeps the first occurrence; same-id reconstruction seeds keep the canonical-minimum row).

**Files**: `M/data-model.md` (new, ~180 to 260 lines).

**Validation**: every row of section 3 cites at least one Python symbol that `grep -n` finds in the named module; no line numbers are cited; every FR-020 member of the FR text has a row.

---

### Subtask T027: Record the markers rule for `lifecycleTypes` (D-98)

**Purpose**: `lifecycleTypes` is the mission-level set the phase derivation needs (`PhaseDeriver`, P9). The oracle and a classification-based Java derivation disagree on marker rows; the document must settle it before P3 writes the field.

**Steps** (section 5 of the document):
1. State the oracle rule exactly: `ORACLE._lifecycle_types(rows)` is `frozenset(str(row["event_type"]) for row in rows if isinstance(row.get("event_type"), str))` over **every** parsed row, so a row with a string `event_type` counts whatever else it lacks.
2. State the Java hazard: `RowClassifier` (`J/adapter/out/filesystem/codec/RowClassifier.java`, exists in the #5529 tree) classifies a row; a lifecycle row without a string `event_id` or timestamp is dropped to **Ignored** by `lifecycleOrIgnored`, so a classification-based derivation would drop a phase **marker row** that the oracle counts. (Cite the class and method names as they exist at the tip; verify with `grep -n lifecycleOrIgnored` before writing.)
3. Record the decision D-98 (already in `traces/design-decisions.md`): `LedgerLine` gains a **nullable `eventType`** set from any well-formed row; the reducer derives `StatusSnapshot.lifecycleTypes()` from it by the oracle's rule; the four-argument `StatusSnapshot` constructors stay (so `lifecycleTypes` defaults empty and the overview is unchanged).
4. Name the pinning fixture: `marker-row-without-event-id` of class `phases-matrix` (P4 adds it; Count 19; plan S-20: "a phase marker row with a string `event_type` and no string `event_id` or `timestamp`, which the oracle counts and a classification-based derivation would drop"). State that WP05 (P3) is red without the nullable `eventType`, and that P9's `PhaseDeriver` consumes the set.
5. State what `lifecycleTypes` is **not**: it is not the stream allow-list of seven lifecycle types (that is `LIFECYCLE_ALLOW_LIST` for the live stream); the set is every string `event_type` the rows carry.

**Files**: `M/data-model.md` (section 5, ~30 lines).

**Validation**: the section cites `_lifecycle_types`, `RowClassifier`'s ignore path, D-98, S-20 and the fixture name; no other fixture name is invented.

---

### Subtask T028: Record the oracle field each member is checked against; state that no `src/` file changes

**Purpose**: P3's tests and P4b's goldens need to know, per member, which oracle field they compare, so nobody re-derives it.

**Steps**:
1. Section 6 (a checklist table): for each FR-020 member, the oracle JSON path in the `WorkPackage` body (`assignment.agent` ... `assignment.provider`, `subtasks`, `subtaskProgress`, `review.latestResult`, `review.override`, `actor`, `history[]`) and the consumer that checks it: the resolved-state goldens of P4b (`R/conformance/resolved-state/**`, generated by `.venv/bin/python -m tests.contract._mission_status_conformance --write`), P3's `Ac5ReductionTest` (`T/conformance/port/Ac5ReductionTest.java`, exists in the #5529 tree) and the unit tests of the new records, and `ResolvedStateGoldenTest` (P7, AC-20.1). Also note which members are **not** compared by the overview goldens (AC-20.2: unchanged byte for byte).
2. State plainly: **"No file under `src/` changes (C-007); this document is the only deliverable; nothing under `services/` is touched by this Work Package."**
3. Section 7 (pinned behaviours), recorded as observations of the oracle that P3 and the P4b fixtures must honour. Record at least:
   - **History is built from rows, not from the snapshot, and the oracle does not de-duplicate by `event_id` and does not apply the reducer's rollback arbitration** (`history_entries` iterates every `to_lane` row of the Work Package; `reduce_parsed` de-duplicates and arbitrates). **RULED (orchestrator ruling OO-1, 2026-10-13, binding): the Java history is `history_entries`: every `to_lane` row of the Work Package, ordered by `HistoryOrder`, with no `event_id` de-duplication and no rollback arbitration ("port what Python runs").** State this as the rule of the document, not as an open point.
   - The model-absent sentinel: `__resolved_model_absent__` (and the three siblings) are shown as null, never as the sentinel string (AC-20.1).
   - `force` is true only for the literal `true` (AC-20.3); a truthy non-boolean is false.
   - The order key: parsed instant (stamps mix `Z`, fractions and offsets, text order is wrong), event id as the tie-break; a non-instant stamp sorts after every real one so the contract check names it instead of the sort raising.
   - `implementerOfRecord`, `lastTransitionAt`, `forceCount`, `lastEventId` and the cancellation provenance are **already** Java members (#5529) and are not part of this mapping; `readiness`, `readyToStart` and `staleness` are route derivations, not reducer members.

**Files**: `M/data-model.md` (sections 6 and 7, ~60 lines).

**Validation**: every FR-020 member has an oracle field named; the "no `src/` file changes" sentence is present.

---

### Subtask T029: Review pass

**Purpose**: the WP's red-first form is "not applicable (no behaviour)"; its review is a completeness and hygiene pass.

**Steps**:
1. Completeness: re-read the FR-020 text and AC-20.1 to AC-20.5 in `spec.md` against the document. Every member has a cited source symbol **and** an oracle field. No code in the document beyond short symbol names and the one-line oracle expression of T027.
1b. Member-to-route list: section 8 exists and lists 26 pairs (7, 10 and 9), every row T1 to T18 at least once.
2. Scope: `git diff <WP base>..HEAD --stat` shows exactly one file, `M/data-model.md`, under `kitty-specs/`; no `src/`, `services/`, `tests/`, `.github/` path.
3. Gates unaffected (file is new, not on `main`): `.venv/bin/python -m pytest tests/architectural/test_archive_root_byte_identical.py -q`; the Windows-filename guard after staging the file (`.venv/bin/python -m pytest tests/architectural/test_no_invalid_windows_filenames.py -q`; the guard reads `git ls-files`, so stage first); the terminology guard (`.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q`); prose uses Mission and Work Package, never "feature" for a domain object.
4. Public-repo hygiene (C-006): no home-directory path, user name, e-mail or token; the document cites repo-relative paths and module names only. Use `PY_REDUCER`-style placeholders in prose where an absolute path would be needed; the virtualenv path `.venv/lib/python3.11/site-packages/spec_kitty_events/diary.py` is cited as module `spec_kitty_events.diary`, not as a path.
5. Mission-state audit is the orchestrator's before it publishes the ref: `.venv/bin/spec-kitty doctor mission-state --audit --fail-on teamspace-blocker --json > "<scratch>/audit.json"; echo "exit $?"` (scratch outside the repository). If it reports `SNAPSHOT_DRIFT`, it is fixed with `spec-kitty agent status materialize --mission mission-status-read-api-mission-detail-01M4S6D5`, never by hand.

**Validation**: all of the above recorded in the hand-off.

---

## Self-contained green

- **Fixtures live with their tests / no Java**: this WP adds no fixture, no test, no Java or Python line. The `marker-row-without-event-id` fixture named in the document is **P4's** (WP07), referenced as a future artifact in prose, never asserted by a gate here.
- **Floors and counts**: nothing to satisfy; no JaCoCo line, no `DEFINED_RULE_COUNT`, no native floor changes. The statement "Count 19" is a quotation of plan S-20 for WP07.
- **No test or gate names a type of a later WP**: the document may name planned Java targets (`WpResolved`, `Assignment`, `ReviewResultRecord`, `ReviewOverrideRecord`, `HistoryRow`, `HistoryOrder`) as design targets; no gate reads the document, so no gate can go red on a later type.
- **Pin `tests/ci/test_mission_status_api_build.py`**: untouched. Its tracked-path scan covers `git ls-files` of `S` only, and this WP adds no path under `S` (plan 11: Gate P is not part of P3a).
- **Mission record stays complete**: the document is a new file under `M/`; `meta.json` is untouched; `status.json` is only ever produced by `spec-kitty agent status materialize --mission <slug>`, never by hand, so cutover-guard, the mission-state audit and corpus-blocking see a complete record; do not commit untracked CLI state blind (compare with the coordination copy first).
- **Archive freeze**: the file is **new, not on `main`**, so `tests/architectural/test_archive_root_byte_identical.py` is unaffected; after PR A is on `main` it can no longer be edited, and PR B does not touch it (interim default F1/E-12: PR B adds only new files to the mission directory).

## Plan defects found

- **RULED: OO-1 (orchestrator ruling 2026-10-13, binding; formerly TASKS-COVER-009 item 1): history semantics.** `history` holds every `to_lane` row of the Work Package like the oracle's `history_entries`, ordered by `HistoryOrder`; no `event_id` de-duplication and no rollback arbitration (the Java history follows what the Python oracle runs). The two extra `resolved-state` fixtures (a duplicate-`event_id` row, a lost-arbitration row) are NOT required. This WP records the rule in section 7 of `M/data-model.md` as a pinned behaviour; nothing is left open.
- **History semantics (formerly a gap; closed by ruling OO-1)**: AC-20.3 and plan P3 say the history is "ordered by the parsed instant then `eventId`" and "transitions only". The oracle (`history_entries` over `source.rows`) includes every `to_lane` row of the Work Package, whereas `spec_kitty_events.diary.reduce_parsed` de-duplicates by `event_id` and arbitrates. By ruling OO-1 the Java history is built from every row, like the oracle; the document records that reading in section 7 and no fixture is added for it.
- **Spec wording**: FR-020 says "the `actor` of the latest change". The snapshot `actor` slot is the actor of the latest **applied transition** (annotations do not change it); an annotation-only Work Package's `actor` is the annotation's. The document states this reading; the spec text is not edited (C-004).
- Nothing forward-referencing or unsatisfiable for this WP.

## Definition of Done

- [ ] Each of T026 to T029 has a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.
- [ ] `M/data-model.md` exists as the **first commit** of this WP, with sections 1 to 7 as listed, and is the only file changed.
- [ ] Every FR-020 member (assignment: agent, assignee, role, agentProfile, agentProfileVersion, model, provider; subtasks; review result; review override; actor; ordered history; `lifecycleTypes`) has a cited source symbol in `spec_kitty_events.diary` or `specify_cli.status` and a named oracle field.
- [ ] The markers rule for `lifecycleTypes` (D-98) is recorded with the oracle expression, the `RowClassifier` hazard and the `marker-row-without-event-id` fixture name.
- [ ] The sentence "no `src/` file changes (C-007)" is present; no code in the document.
- [ ] The history rule (ruling OO-1: every `to_lane` row, no de-duplication, no arbitration) is recorded in section 7 as a pinned behaviour.
- [ ] Archive-freeze, Windows-filename and terminology guards pass; no home path, user name or token.

## Risks

- **Transcribing the Python from memory**: the mapping is the contract P3 and P4b build on. Verify each symbol and behaviour against `spec_kitty_events.diary` and `specify_cli.status` in the synced `.venv` (a stale venv gives false reads: `uv sync --frozen --all-extras` first if a symbol is missing).
- **Line numbers rot**: cite symbols and module names only.
- **Over-reaching into design**: this is a mapping, not a Java design; planned target names come from the plan (1.2, P3 row) and are not elaborated.
- **Appenders collide**: WP07 and WP08 append to the same file; keep section numbering stable and do not leave placeholders they would have to edit.

## Reviewer Guidance

- Check, member by member, that the cited symbol exists and does what the row says (open `spec_kitty_events.diary` / `specify_cli.status.wp_view` and the oracle `history_entries` / `review_override` / `_review_result`); reject a row without a symbol or without an oracle field.
- Check the `lifecycleTypes` section against `_lifecycle_types` and the `RowClassifier` ignore path, and that the fixture name is the plan's.
- Check scope: one file changed, under `kitty-specs/`, no code, no `src/`.
- Check section 7 states the OO-1 history rule (every `to_lane` row like `history_entries`) and does not hedge it.
- Run the archive-freeze, Windows-filename and terminology guards; grep the file for an absolute home-directory prefix and for the retired word "feature".

## Implementation command

```bash
spec-kitty agent action implement WP04 --agent claude --mission mission-status-read-api-mission-detail-01M4S6D5
```
