# Data model: resolved Work Package state (FR-020)

Mission `mission-status-read-api-mission-detail-01M4S6D5`, phase P3a (WP04). This file is the member-to-source mapping that P3 (WP05) implements from, that P4 and P4b (WP07, WP08) generate goldens from, and that the route phases (WP13 to WP15) check their member-to-route cases against. It holds no code.

## 1. Scope and non-goals

- **In scope.** Every FR-020 member: `assignment` (`agent`, `assignee`, `role`, `agentProfile`, `agentProfileVersion`, `model`, `provider`), the resolved `subtasks` map (and the derived `subtaskProgress`), the latest review result, the review override, the `actor` of the latest change, the ordered transition `history`, and the mission-level `lifecycleTypes` set (D-98).
- **Out of scope.** `lane`, `lastTransitionAt`, `lastEventId`, `forceCount`, the cancellation provenance and `implementerOfRecord` are already Java members (#5529, `domain.model.WpState`). `readiness`, `readyToStart` and `staleness` are route derivations, not reducer members. The overview (`MissionOverview`) does not change (AC-20.2): none of the members below is read by an overview derivation.
- **No `src/` file changes (C-007).** This document is the only deliverable of WP04. Nothing under `src/`, `services/`, `tests/` or `.github/` is touched by this Work Package, and nothing under `services/` enters the Python wheel.
- **No Java in this file.** Planned Java targets (`WpResolved`, `Assignment`, `ReviewResultRecord`, `ReviewOverrideRecord`, `HistoryRow`, `HistoryOrder`) are design names taken from plan section 1.2 and the P3 row; they are not elaborated here.
- **Appending.** WP07 appends the manifest classes and `PROVISION_PLAN`; WP08 appends the `resolved-state` class and its member-to-fixture table. They append after section 8 and never edit above their own section. Section numbers 1 to 8 are stable.

### 1.1 Version pinned by this mapping

Everything below describes `spec-kitty-events` **10.4.4**, the version `uv.lock` pins and the one installed in the project environment. The behaviour of 10.4.0 is not described. The three 10.4.x changes that matter for this mapping, all present in 10.4.4:

1. **Arm (ii) of the arbitration applies to every non-seed setter** (#5967), not only to a rollback setter (section 4.2, rule A2).
2. **Reconstruction-seed exemptions** (#4941, #5967, #6058): a seed that is not itself a rollback does not reject a later live transition, and a seed that loses arm (ii) still folds the claim and verdict payload that no real event wrote (section 4.2, rules A3 and A4).
3. **Canonical-minimum dedup for all-seed rows** sharing an `event_id` (section 4.1, rule D2).

### 1.2 Reconciliation with the #5529 reducer

`domain.readmodel.reducer.StatusReducer` already ports 10.4.4 for the members it serves today: dedup (D1, D2), the sort, and arbitration arms (i) and (ii) with the seed exemptions (A1 to A3). It deliberately omits the seed **payload** fold (A4) and the slot provenance behind it, on the stated ground that those write only slots the service never serves (class Javadoc, `StatusReducer.java` lines 29 to 33). **That ground ends with FR-020**: A4 writes `agent` and `review_result`, both served members. WP05 must port A4 and the provenance (section 4.2). Every other difference found between the Java reducer and the Python source is listed in section 7 as a pinned behaviour or an open point.

## 2. Sources

Citation convention. A symbol (module and function name) is authoritative; a line number after it is the line in the pinned file at the time of writing and is there to make the citation checkable now, not to be relied on later. Prefixes:

| Prefix | File | Module |
|---|---|---|
| `D` | `spec_kitty_events/diary.py` (events 10.4.4) | `spec_kitty_events.diary` |
| `S` | `spec_kitty_events/status.py` (events 10.4.4) | `spec_kitty_events.status` |
| `R` | `src/specify_cli/status/reducer.py` | `specify_cli.status.reducer` |
| `V` | `src/specify_cli/status/wp_view.py` | `specify_cli.status.wp_view` |
| `B` | `src/specify_cli/status/resolved_binding.py` | `specify_cli.status.resolved_binding` |
| `M` | `src/specify_cli/status/models.py` | `specify_cli.status.models` |
| `O` | `tests/contract/_mission_status_payloads.py` | the oracle (`ORACLE`) |
| `J` | `services/mission-status-api/src/main/java/org/speckitty/missionstatus/` | the Java service |

The sources, in the order a value travels:

- `D reduce_parsed` (1792): the fold. Its steps are dedup, sort, transition fold, annotation post-pass, summary. `D reduce` (1898) is `parse_diary` then `reduce_parsed`. `D parse_diary` (1757) partitions rows into transitions and annotations.
- `S` re-exports the diary reducer: `from spec_kitty_events.diary import DiaryError, State, parse_diary, reduce` (169). So `R materialize_snapshot` (373), which calls `reduce_shared_state(raw_events)` (377), runs the same `reduce_parsed` as `R wp_snapshot_state` (187) and `R reduce` (176). **Correction to project prose:** the "Lamport wrapper" wording in the repository `CLAUDE.md` does not describe this import; in this tree both snapshot paths are the wall-clock `(at, event_id)` fold of `reduce_parsed`.
- `R materialize_snapshot` adds two projections on top (`_project_cancellation_provenance` 93, `_project_implementer_attribution` 127). Both are already Java members and are not part of this mapping.
- `V reconstruct_wp_view` (256) and `V _resolved_group` (159) read one Work Package's slots out of `R wp_snapshot_state` and produce the `ResolvedGroup` the oracle uses for `assignment`, `subtasks` and `review.override`.
- `O build_work_package` (1063) composes the `WorkPackage` body. It reads **two** views of the same fold: `view.resolved` (from `V _resolved_group`, which re-reads the ledger through the CLI models in `M`) and `source.snapshot.work_packages[wp_id]` (from `R materialize_snapshot`, which reads raw rows through the diary classes). Both fold with `D reduce_parsed`. That the two read paths decode identically is an inference from the `M` and `D` models being line-for-line parallel (`M ReviewOverride.from_dict` 537, `D ReviewOverride.from_dict` 552; `M InnerStateChanged.from_dict` 764, `D InnerStateChanged.from_dict` 776); P3 should not assume a divergence between them without a fixture.
- `O history_entries` (1041) reads **raw rows**, not the snapshot (section 4.8).
- `B` holds the four resolver sentinels (the `RESOLVED_*_ABSENT` constants, 37 to 40) and `ResolvedBinding.to_delta` (64), the writer that records them.

## 3. Member-to-source mapping

Columns: the FR-020 member; the snapshot slot (or row source); the Python writer(s); the Python read; the oracle field it is checked against (`build_work_package`, `WorkPackage` body); the planned Java target (P3). Rules cited as D1.. A1.. are in section 4.

| FR-020 member | Slot or row source | Python writer | Python read | Oracle field | Java target (P3) |
|---|---|---|---|---|---|
| `assignment.agent` | slot `agent` | claim sidecar `policy_metadata.agent` on an applied `planned -> claimed`, written only when truthy (`D _claim_sidecar_writes` 1119, called from `D _wp_state_from_event` 1206, and from `D _fold_losing_seed` 1558); annotation replace slot (`D _REPLACE_SLOTS` 1038, `D _apply_annotation_delta` 1293 to 1299); cleared by `release_runtime_claim` (1290 to 1292) | `V _resolved_group` 183 via `V _opt_str` (151) | `assignment.agent` (O 1094) | `Assignment.agent` |
| `assignment.assignee` | slot `assignee` | annotation replace slot only | `V _opt_str` (184) | `assignment.assignee` (O 1095) | `Assignment.assignee` |
| `assignment.role` | slot `role` | annotation replace slot only | `V _opt_str` (no sentinel) | `assignment.role` (O 1096) | `Assignment.role` |
| `assignment.agentProfile` | slot `agent_profile` | annotation replace slot; claim seams write `RESOLVED_PROFILE_ABSENT` when no profile resolved (`B ResolvedBinding.to_delta`) | `V normalized` (176) strips `RESOLVED_PROFILE_ABSENT` | `assignment.agentProfile` (O 1097) | `Assignment.agentProfile` |
| `assignment.agentProfileVersion` | slot `agent_profile_version` | as above, sentinel `RESOLVED_PROFILE_VERSION_ABSENT` | `V normalized` | `assignment.agentProfileVersion` (O 1098) | `Assignment.agentProfileVersion` |
| `assignment.model` | slot `model` | as above, sentinel `RESOLVED_MODEL_ABSENT` | `V normalized` | `assignment.model` (O 1099) | `Assignment.model` |
| `assignment.provider` | slot `provider` | as above, sentinel `RESOLVED_PROVIDER_ABSENT` | `V normalized` | `assignment.provider` (O 1100) | `Assignment.provider` |
| `subtasks` and `subtaskProgress` | slot `subtasks` (id to status text) | annotation `subtasks` delta, per-id replace merge (`D _apply_annotation_delta` 1300 to 1304); delta value is decoded by `Status(value)`, i.e. a `Lane` (`D WPInnerStateDelta.from_dict` 719; `D Status` 101) | `V _resolved_group` 170 to 171: `{str(key): str(value)}` | `subtasks` (O 1073, 1102; keys strict-projected) and `subtaskProgress` (`O _subtask_progress` 936, 1103) | `WpResolved.subtasks` (insertion-ordered map) |
| review result | slot `review_result` | `D _wp_state_from_event` 1218 to 1223 (populated on any event carrying a result; explicit `None` on a forced `in_review` exit with none; otherwise carried forward); provenance `D _record_applied_event` 1511, `D _fold_losing_seed` 1565 to 1567 | the oracle reads the slot directly: `O _review_result` (971) from `source.snapshot`. (`R review_result_from_state` 207 is the gate consumers' reader, not the oracle's; see 7.12) | `review.latestResult` (O 1112) | `ReviewResultRecord(reviewer, verdict, reference)` |
| review override | slot `review` (distinct from `review_result`) | annotation `review` delta (`D _apply_annotation_delta` 1317 to 1318): replace with `ReviewOverride.to_dict()`, or clear to `None` on the all-empty release sentinel (`D ReviewOverride.is_release_sentinel` 528) | `V _resolved_group` 173 to 174: the mapping, else `None` | `review.override` via `O review_override` (990; O 1112) | `ReviewOverrideRecord(at, actor, wpId, reason)` with a `complete` predicate |
| `actor` | slot `actor` | set on every applied transition: `actor_identity_str(event.actor)` (`D _wp_state_from_event` 1193; `D actor_identity_str` 251); seeded once by `D _runtime_only_wp_state` (1621) for a Work Package known only from annotations; annotations never change it | `source.snapshot.work_packages[wp]["actor"]` | `actor` via `Projector.actor` (O 476; O 1108) | `WpResolved.actor` |
| ordered `history` | **not a snapshot slot**; raw ledger rows | none (no writer; built from the rows) | `O history_entries` (1041) over `MissionSource.rows` | `history[]` (O 1113) | `HistoryRow` plus `HistoryOrder`, kept per Work Package in `WpResolved.history` |
| `lifecycleTypes` | mission-level, from raw rows | none | `O _lifecycle_types` (923) | feeds `phases[]` via `O derive_phases` (O 966); not a body member | `StatusSnapshot.lifecycleTypes()` from a nullable `LedgerLine.eventType` |

## 4. Per-member rules

All rules are from reading the cited code; where a statement is an inference it is marked **(inference)**. Some rules were also exercised against the installed 10.4.4 reducer with hand-built ledgers in a scratch probe (not committed), and are marked "probe" where they are cited: a claim sidecar with annotations, the release of a claim, a seed that loses arm (ii) folding its claim (A4), a forced `in_review` exit giving a `None` verdict, the sticky verdict and an empty-object result, the structured and the null actor, a numeric agent, the partial override and the all-empty release sentinel, an override holding `null` fields, an invalid subtask status, an annotation-only Work Package, same-id real rows (first wins) and same-id seed rows (canonical minimum wins). Arms (i) and (ii) themselves (A1 to A3) are from reading the code and the Java tests of #5529, not from a probe.

### 4.1 Dedup and ordering

- **D1. Transitions are deduplicated by `event_id`, the first occurrence in file order wins** (`D _dedup_transitions` 1601, called at `D reduce_parsed` 1841). The oracle's own history does not do this (section 7.1).
- **D2. Canonical-minimum for all-seed rows.** When more than one row shares an `event_id` and **every** row of the group is a reconstruction seed, the row with the minimum `_canonical_key` wins whatever the file order (`D _dedup_transitions` 1614 to 1615). `_canonical_key` is `json.dumps(event.to_dict(), sort_keys=True, default=str)` (`D _canonical_key` 1596 to 1598). A group of real rows, or a mixed group, keeps the first row. A reconstruction seed is an event whose `actor_identity_str(actor)` starts with `migration:` (`D _is_reconstruction_seed` 1102 to 1116, prefix at 1099). Java: `StatusReducer.sortedUnique` and `StatusEvent.seedKey` already do this.
- **D3. Annotations are not deduplicated.** `reduce_parsed` has no dedup step for annotations (1829 to 1873); a repeated annotation row is folded twice. For the served slots (replace slots, per-id subtask merge, override replace) a repeat is idempotent, so this is observable only through `note` (not served). **(inference)** from the absence of a dedup call; P3 must not add one.
- **O1. Transition order** is `sorted(unique, key=(at, event_id))` (`D reduce_parsed` 1844). `at` is the stored text and is compared as text by code point; it is never parsed in the fold. Java: `AtThenEventId` (compares by code point, matching Python `str` ordering).
- **O2. Annotation order** is the **same key** over the annotations (`D reduce_parsed` 1867), so two annotations touching one field resolve by `(at, event_id)`, not by file order. Python's sort is stable, so rows equal on both keys keep file order. Annotation `at` and `wp_id` are `str()`-coerced by the decoder (`D InnerStateChanged.from_dict` 795 to 796), so a JSON number or `null` becomes text (`"5"`, `"None"`) before the comparison. `RowClassifier.pythonStr` reproduces this today for `wp_id` only (integers, booleans and null; a float, list or object returns null and the row classifies as unusable); `at` is not decoded by `RowClassifier` yet, so WP05 must decode it the same way.
- **O3. `history` order is a different rule** (parsed instant, then event id; section 4.8) and must not be confused with O1.

### 4.2 The transition fold and its arbitration

The fold visits `sorted_events` once, per Work Package (`D _fold_transitions` 1570 to 1593). For each event:

- **A0. No current state:** the event applies (`D _arbitrate_event` 1394).
- **A1. Arm (i), same-`at` concurrency** (1403 to 1416). When the current state's `last_transition_at` equals the new event's `at`: a rollback beats a forward setter (apply); a forward event never beats a rollback setter (`LOST_TO_ROLLBACK`, contributes nothing). A rollback is `from_lane == in_review` to one of `planned`, `claimed`, `in_progress`, or `from_lane == for_review` with a non-null `review_ref` to one of those (`D _is_rollback_event` 1076 to 1088; targets at 1064). Java: `StatusReducer.isRollback`, `shouldApply` lines 143 to 150.
- **A2. Arm (ii), from-lane continuity against every non-seed setter** (1473 to 1480). The event is dropped (`LOST_ON_CONTINUITY`) when **all** hold: a current setter exists; the event is not a rollback; the setter is not "a seed that is not itself a rollback"; the event is not `force`; and `str(event.from_lane) != current lane`. This is the 10.4.2 change (#5967): it covers a stale forward step after a cancel and after a reclaimed rework, not only after a rollback. Java: `shouldApply` lines 151 to 152.
- **A3. Seed exemptions** (1445 to 1472). A setter that is a reconstruction seed and **not** a rollback is not a decision, so it does not reject a later live transition. A setter that is a seed restating a **rejection** (a rollback) keeps its authority (#4941), so arm (ii) still drops a bare approval that branched off the same `in_review`. `force=True` and a rollback event always pass arm (ii). Java: `setterIsDecision` in `shouldApply`.
- **A4. A seed that loses arm (ii) still folds its payload** (`D _fold_transitions` 1587 to 1592, `D _fold_losing_seed` 1539 to 1567; 10.4.3, #6058). Only a seed that lost on **continuity** does this (a seed that lost arm (i) contributes nothing), and only when a current state exists. Per slot, fill-if-absent: each claim slot the seed's `planned -> claimed` sidecar would write (`D _claim_sidecar_writes`) is written unless the slot is in `prov.real`; `shell_pid_created_at` is withheld while `shell_pid` is in `prov.real`; `review_result` is written only when the seed carries a populated verdict (a verdict-less loser writes nothing, unlike an applied `in_review` exit, which writes an explicit `None`) and the slot is not in `prov.real`. A later seed overwrites an earlier seed's value (the guard is against `prov.real` only). **The lane-setter slots are never touched.** Served consequence: `agent` and `review_result` of a Work Package can come from a seed that lost the lane contest. Probe: a real `planned -> blocked` at t0 and a seed `planned -> claimed` with `agent` at t1 give `lane = blocked` and `agent = <the seed's agent>`.
- **A5. Slot provenance** (`D _SlotProvenance` 1487; `D _record_applied_event` 1511 to 1536). `prov.real` is the set of slots an authoritative applied event has written (a non-seed event, or a rollback seed); `prov.seed` the slots whose value in force came from a seed. After a seed that is not a rollback applies, its written slots go to `prov.seed` and it returns. Otherwise the written slots go to `prov.real` and leave `prov.seed`. The `shell_pid_created_at` void is not a served slot. Provenance lives only during the transition fold and is never serialised; the annotation pass must not consult it (1498 to 1499). A5 exists only to serve A4.

What an applied transition writes (`D _wp_state_from_event` 1143 to 1225):

- **W1.** `lane`, `actor`, `last_transition_at`, `last_event_id` and `force_count` are set from the event (1186 to 1197); `actor` is `actor_identity_str(event.actor)` (a structured actor projects to its `tool`, else `role`, else `""`; a text actor is verbatim; a JSON `null` or number actor was `str()`-coerced at decode time, so `null` arrives as the text `None`: probe).
- **W2.** The runtime slots in `D _RUNTIME_SLOTS` (1013) that the previous state holds are carried forward (1200 to 1203). **(inference, from the order of the passes)** Within `reduce_parsed` only `agent` (and the unserved `shell_pid`, `shell_pid_created_at`) can be present at transition time, because every annotation-written slot (`subtasks`, `assignee`, `role`, the profile and model slots, `review`) is written by the post-pass that runs after the whole transition fold (1856 to 1873). So for those slots the carry-forward is vacuous inside one reduction and the final value depends only on the annotation pass.
- **W3.** The claim exception: the claim sidecar writes (`D _claim_sidecar_writes`) land on an applied `planned -> claimed` (1206). `agent` is written only when `policy_metadata["agent"]` is truthy, and its value is stored **as it is**, whatever its JSON type (probe: `agent: 123` is stored as the number `123`). `V _opt_str` then stringifies it, so the oracle serves `"123"` (section 7.5).
- **W4.** `review_result`: populated when the event carries a populated `ReviewResult` (any `from_lane`); otherwise `None` (explicit) when `from_lane == in_review`; otherwise carried forward verbatim (sticky); a Work Package that never carried a result and never left `in_review` has the slot **absent** (1218 to 1223). A `review_result` JSON value that is falsy (`{}`, `null`) decodes to "no result" (`D StatusEvent.from_dict` 499 to 501). The slot value is `ReviewResult.to_dict()`: `reviewer`, `verdict`, `reference`, and `feedback_path` only when not null (388 to 396).

### 4.3 The annotation post-pass

After the whole transition fold, annotations are folded in `(at, event_id)` order (`D reduce_parsed` 1867 to 1873). For each:

- **N0.** A Work Package with no state is seeded by `_runtime_only_wp_state(annotation.actor)` (1621 to 1638): lane `uninitialized` (non-display), `actor` from the **first** annotation in sort order, `last_transition_at` and `last_event_id` null, `force_count` 0. Later annotations do not change `actor`. This Work Package counts in `wpTotal` and in no lane count (J `StatusReducer.reduce`, lines 86 to 88, already does the lane part).
- **N1. Release first** (1290 to 1292). When `release_runtime_claim` is true, `agent`, `shell_pid` and `shell_pid_created_at` are set to `None` (a present key holding `None`, not removed). It runs before the replace loop, so a concrete value in the same delta wins over the release. `assignee` and the resolved-binding slots are **not** cleared by a release.
- **N2. Replace slots** (1293 to 1299). For each of `shell_pid`, `shell_pid_created_at`, `agent`, `assignee`, `role`, `agent_profile`, `agent_profile_version`, `model`, `provider`: a present value that is not `None` and not `""` replaces the slot, latest-wins by O2. `""` is a no-op. The decoder also normalises a blank scalar to `None` at read time (`D WPInnerStateDelta.__post_init__` 650 to 663), so a blank never reaches the fold. The sentinel strings are ordinary non-empty values here: they are recorded and replace a stale real model on purpose (`B` 37 to 40 and the comment above them).
- **N3. Subtasks** (1300 to 1304): per-id replace merge into the current map, value `str(status)`. A delta value that is not a valid lane name fails the **decode** (`D WPInnerStateDelta.from_dict` 719 raises `ValueError`, `D parse_diary` wraps it as `DiaryError` 1775 to 1777), which makes the whole reduction fail, not just that row (probe). Java: `RowClassifier.validSubtasks` already classifies such a row `Malformed`. Insertion order of the map is the order the ids first appear across the sorted annotations.
- **N4. Review override** (1317 to 1318): replaces with `ReviewOverride.to_dict()`, **unless** the record is the release sentinel (all four fields empty), which clears the slot to `None`. A partial record is persisted. The four fields are `str()`-coerced by the decoder (`D ReviewOverride.from_dict` 560 to 565), so a JSON `null` becomes the text `None`, which is truthy (probe: `at: null` is stored as `"None"`). The `complete` predicate is plain truthiness of all four, whitespace included (523 to 525).
- **N5. Never** touches `force_count` or the lane. `note`, `tracker_refs` and `tracker_refs_replace` are not served.

### 4.4 Absent versus explicit null, per member

| Member | Absent | Explicit null | Oracle reading |
|---|---|---|---|
| `assignment.*` | slot never written | claim released (`agent`) or decoder-normalised blank | both read `None`, then `Projector.handle` gives null; the keep-the-distinction cost is zero, so Java may collapse them |
| `assignment.agentProfile`, `.agentProfileVersion`, `.model`, `.provider` | never recorded | the sentinel string is stored | the sentinel reads null (twice: `V normalized` and `O Projector.handle` 472); the three states (real value, sentinel, absent) all read null or a value, never the sentinel text |
| `subtasks` | `{}` | `{}` | an empty map and `subtaskProgress {done: 0, total: 0}` |
| `review.latestResult` | slot absent | slot `None` (forced `in_review` exit) | both null (`O _review_result` 973 to 974: not a mapping is null). Keep the distinction only if free; nothing served depends on it |
| `review.override` | slot absent | slot `None` (release sentinel) | both null |
| `actor` | cannot be absent for a Work Package that has state | n/a | `{tool: handle(text), role: null, profile: null}`; a structured actor never reaches the snapshot slot (it is a text) |

### 4.5 Subtasks

The map is `{str(key): str(value)}` of the slot (`V` 170 to 171), insertion-ordered. The oracle strict-projects each **key** against the relative-reference pattern with `strict(..., nullable=False)` (O 1073): a key that is not representable is a projection error (a 500 on the route, row T7), not a null. The **value** is passed through as the stored lane text. `subtaskProgress.done` counts values equal to `"done"`, `total` is the map size (`O _subtask_progress` 936 to 937); it is computed, not stored. Emission order of the map is a route concern (S-15).

### 4.6 Review result

Served shape: `{reviewer, verdict, reference}` (`O _review_result` 971 to 979). `reviewer` goes through `Projector.handle` (null unless text matching the handle shape). `verdict` is `raw.get("verdict")` **unprojected**, so the oracle serves whatever JSON value the row held; the contract schema, not the oracle, constrains it. `reference` is `Projector.human(raw["reference"] if not None else "")`: a missing or null reference is the empty string, a non-text reference is `str()`-coerced, then redacted. `feedback_path` is stored in the slot and not exposed. A slot that is not a mapping is null.

### 4.7 Review override

`O review_override` (990 to 1015) reads `ResolvedGroup.review`:

- Not a mapping, or none of the four fields present, gives `null`. A field is present when it is a non-empty text; whitespace is a value (1002 to 1004). So the release sentinel and no record at all both give `null`.
- Otherwise `complete` is true iff all four of `at`, `actor`, `wp_id`, `reason` are present. The body shows `{complete, at, actor, reason}`; `wp_id` is read for the rule and **not shown** (the override sits inside its own Work Package).
- `at` is shown only when it parses as an instant **with an offset** (`O _is_dated` 982 to 987); a partial record with any other `at` shows `at: null`. A **complete** record whose `at` is not such an instant cannot be shown: the projection raises (1007 to 1008), which is row T14 (a 500). Java: `Instants.hasOffset` is the existing offset test.
- `actor` goes through `Projector.handle`; `reason` through `Projector.human`.
- Precedence between `review.override` and `review.latestResult` is a consumer's; both can be populated at once (`D _apply_annotation_delta` docstring, 1279 to 1286).

### 4.8 Actor

The snapshot slot is always text (W1). The oracle shows `Projector.actor(text)`: `{tool: handle(text), role: null, profile: null}` (O 476 to 480). `Projector.handle` returns null for non-text, for a value not matching `^[A-Za-z0-9._:-]{1,128}$`, and for the four sentinel strings. The slot is the actor of the latest **applied** transition, not of the latest event in the ledger: a transition that lost arbitration does not change it, and annotations do not change it (a Work Package known only from annotations carries the first annotation's actor, N0). This reads FR-020's phrase "the `actor` of the latest change" as the latest applied transition; the spec text is not edited (C-004).

### 4.9 History

`O history_entries` (1041 to 1060) builds the list from the raw rows, not from the reduction:

- **Row filter.** `"to_lane" in row and row.get("wp_id") == wp_id`: key presence and exact equality, nothing else. It does not look at `kind`, `event_type` or any other field, and it does not run the reducer's classification (section 7.1, 7.3).
- **Entry.** `eventId = row.get("event_id")`, `at = row.get("at")` (both stored text, unprojected), `kind = "transition"`, `fromStatusLane` and `toStatusLane` through `Projector.lane` (O 520 to 526: null for a missing value and for the non-display lanes `genesis` and `uninitialized`, a projection error for any other value outside the nine display lanes), `actor = Projector.actor(row["actor"])` (the **row's own** actor, possibly a structured record), `force = (row.get("force") is True)`, `reason = Projector.human(row.get("reason"))`, `reviewVerdict = row["review_result"].get("verdict")` when `review_result` is a mapping, else null.
- **Order.** `_history_order_key` (1028 to 1038): the **parsed instant** (`kernel.clock.parse_iso`, i.e. `datetime.fromisoformat`, then `.timestamp()`), then `eventId` as text. A stamp that is not an instant sorts after every real one, in group `(1, 0.0, stamp, eventId)`, so the contract check names it instead of the sort raising. Java: `HistoryOrder`, parsing with `Instants.parse` (`domain.readmodel.overview`), which reads an offset-less stamp as UTC where Python reads it in the local zone (`Instants.java` Javadoc); an offset-less stamp is therefore a documented difference, not a bug to chase.

### 4.10 Which rows reach which part

| Row kind (as `parse_diary` sees it) | Folded transition | Annotation pass | `history` | `lifecycleTypes` |
|---|---|---|---|---|
| lane transition (`kind` absent, no `event_type`) | yes | no | yes (has `to_lane`) | no (no `event_type`) |
| annotation (`kind: annotation`) | no | yes | no (no `to_lane`) | yes if it carries a text `event_type` (inference) |
| lifecycle, retrospective, decision rows (a text-typed `event_type`, or `type` of a retrospective event, or `event_name` starting `retrospective.`) | no | no | only if the row also carries `to_lane` and a matching `wp_id` (inference) | yes when `event_type` is text |
| unknown `kind`, malformed lane or annotation row | the whole reduction fails (`DiaryError`) | | | |

## 5. lifecycleTypes and the markers rule (D-98)

1. **The oracle rule.** `O _lifecycle_types(rows)` (923 to 924) is `frozenset(str(row["event_type"]) for row in rows if isinstance(row.get("event_type"), str))` over **every** parsed row (`MissionSource.rows`). A row with a text `event_type` counts whatever else it lacks: no `event_id`, no timestamp, any `kind`. Phase derivation reads the markers `SpecifyStarted`, `SpecifyCompleted`, `PlanStarted`, `PlanCompleted`, `TasksStarted`, `TasksCompleted` out of this set (`O PHASE_MARKERS`, `O derive_phases` 334).
2. **The Java hazard.** `RowClassifier` (`J adapter/out/filesystem/codec/RowClassifier.java`) sends every non-lane row to `lifecycleOrIgnored` (73 to 81), which returns a `Lifecycle` line only when `event_type` is one of the seven forwarded types (`LifecycleEvent.isForwarded`) **and** `event_id` and `timestamp` are both text; every other non-lane row is `Ignored`. A derivation that classified rows first would therefore drop a phase marker row without a text `event_id` or `timestamp`, which the oracle counts. Verified at this tip: the guard on the row is wider than the single case the plan names, since a row whose `event_type` is **not** one of the seven is also `Ignored` and also counted by the oracle. The set is every text `event_type`, not the seven.
3. **Decision D-98 (in `traces/design-decisions.md`).** `LedgerLine` gains a **nullable `eventType`**, set from any well-formed row that carries a text `event_type`, whatever line kind it is classified as. The reducer derives `StatusSnapshot.lifecycleTypes()` from it by the oracle's rule. The four-argument `StatusSnapshot` constructors stay, so `lifecycleTypes` defaults to empty and the overview is unchanged.
4. **Pinning fixture.** `marker-row-without-event-id` of class `phases-matrix` (added by P4 / WP07; Count 19 after S-20; plan S-20: "a phase marker row with a string `event_type` and no string `event_id` or `timestamp`, which the oracle counts and a classification-based derivation would drop"). WP05 (P3) is red without the nullable `eventType`. P9's `PhaseDeriver` consumes the set.
5. **What it is not.** It is not the stream allow-list of seven lifecycle types (`LifecycleEvent.TYPES`, the forwarded types of the live stream). It is every text `event_type` the rows carry. The two must stay separate: the stream still forwards only the seven, and only when `event_id` and `timestamp` are text.

## 6. Oracle field checklist

For each member: the JSON path in the `WorkPackage` body and the consumer that checks it. Consumers: **G** = the P4b `resolved-state` goldens (`resolved-state` class under the conformance tree, generated by the oracle module `tests.contract._mission_status_conformance --write`) and `ResolvedStateGoldenTest` (P7, AC-20.1); **U** = P3's `Ac5ReductionTest` and the unit tests of the new records; **C** = the route case of section 8.

| Member | Oracle JSON path | Checked by |
|---|---|---|
| agent, assignee, role | `assignment.agent`, `assignment.assignee`, `assignment.role` | G, U, C (T17) |
| agentProfile, agentProfileVersion, model, provider | `assignment.agentProfile`, `.agentProfileVersion`, `.model`, `.provider` | G (sentinel shown as null), U, C (T17) |
| subtasks | `subtasks` (keys: T7) | G, U |
| subtask progress | `subtaskProgress.done`, `subtaskProgress.total` | G, U |
| review result | `review.latestResult.{reviewer, verdict, reference}` | G (each verdict), U, C (T6 `reference`, T17 `reviewer`) |
| review override | `review.override.{complete, at, actor, reason}` | G (a partial and a release-marker override), U, C (T14, T6, T17) |
| actor | `actor.{tool, role, profile}` | G, U, C (T17) |
| history | `history[].{eventId, at, kind, fromStatusLane, toStatusLane, actor, force, reason, reviewVerdict}` | G (mixed `Z`, fraction and offset stamps; rows of other kinds between them), U (`HistoryOrder`), C (T6, T12, T13, T17) |
| lifecycleTypes | not a body member; observed through `phases[]` of `MissionDetail` | G (`phases-matrix`, Count 19), U |

Not compared by the overview goldens (AC-20.2): **none** of the members above. They are carried by the Work Package routes only, and the overview goldens and every overview derivation stay byte-identical. `lifecycleTypes` is consumed by the phase derivation of `getMission` (P9), not by `MissionOverview`.

## 7. Pinned behaviours

Observations of the oracle and the source that P3 and the P4b fixtures must honour, and points where the Java tree differs today.

1. **History is built from rows, not from the snapshot, and the oracle does not de-duplicate by `event_id` and does not apply the reducer's rollback arbitration** (`O history_entries` iterates every `to_lane` row of the Work Package; `D reduce_parsed` de-duplicates and arbitrates). **RULED (orchestrator ruling OO-1, 2026-10-13, binding): the Java history is `history_entries`: every `to_lane` row of the Work Package, ordered by `HistoryOrder`, with no `event_id` de-duplication and no rollback arbitration ("port what Python runs").** This is the rule of this document. The two extra `resolved-state` fixtures (a duplicate-`event_id` row, a lost-arbitration row) are not required.
2. **The model-absent sentinel.** `__resolved_model_absent__` and its three siblings (`__resolved_profile_absent__`, `__resolved_profile_version_absent__`, `__resolved_provider_absent__`) are shown as null, never as the sentinel text (AC-20.1). This holds at two layers: `V normalized` and `O Projector.handle`. Java's `Actor.RESOLVER_SENTINELS` already covers the handle layer; `Assignment` needs the same.
3. **`force` is true only for the literal `true`** (`row.get("force") is True`, AC-20.3). A truthy non-boolean (`1`, `"true"`) is false.
4. **The order key.** Parsed instant first (stamps mix `Z`, fractions and offsets, so text order is wrong), event id as the tie-break; a non-instant stamp sorts after every real one so that the contract check names it instead of the sort raising. Note the contrast: the **fold** orders by text (O1, O2), the **history** by instant.
5. **`agent` is stringified before the oracle sees it.** The sidecar stores the raw `policy_metadata.agent` (any truthy JSON type, W3); `V _opt_str` applies `str()`; `Projector.handle` then accepts it if it matches the handle shape. A numeric agent `123` is served as `"123"`. Java's `RowClassifier.claimAgent` (lines 152 to 154) keeps only a text agent (lines 152 to 154); a non-text truthy agent is therefore ignored by Java and served by Python. The existing implementer projection has the same shape (`R _project_implementer_attribution` 165 to 173, `str(claimant)`). Open for WP05: mirror Python (`str()` of the scalar) or record a `knownDivergence`. This document records the Python behaviour; it does not choose.
6. **The `actor` slot of a `null` or numeric actor is the text of its `str()`.** A transition row with `"actor": null` gives the snapshot actor `"None"` and the oracle serves `actor.tool = "None"` (probe, case F). `RowClassifier.actor` (lines 121 to 128) deliberately reads such a value as no actor. For the **history** entry the oracle gives null (`Projector.handle` of a non-text value, and a null is not a mapping), which agrees with Java; for the **snapshot** `actor` it gives `"None"` or `"123"`, which does not. Open for WP05: record a `knownDivergence` or port `str()` for the snapshot slot only.
7. **A structured actor** in a transition row projects to `tool`, else `role`, else `""` for the snapshot slot (`D actor_identity_str` 251 to 265); an all-null record therefore gives `""`, which `handle` reads as null. In `history` the record is shown field by field (`tool`, `role`, `profile`), each through `handle`; the `model` field is never shown.
8. **`lastTransitionAt`, `forceCount`, `lastEventId`, the cancellation provenance and `implementerOfRecord` are already Java members** and are not part of this mapping. `readiness`, `readyToStart` and `staleness` are route derivations.
9. **The seed payload fold (A4) is required for `agent` and `review_result`.** The Java class Javadoc (`StatusReducer.java` 29 to 33) says it is not ported because it writes only slots the service does not serve; with FR-020 it does. A fixture for it belongs in the `resolved-state` class: a real transition that wins the lane, then a seed `planned -> claimed` with a sidecar agent and a seed carrying a verdict that lose on continuity.
10. **Subtask status must be a lane name** (N3). A `Malformed` classification already exists in Java; the fixture for a valid `done` and a non-`done` value (`planned`, `blocked`) feeds `subtaskProgress`.
11. **`review_result` is sticky and survives a later transition that carries none** (W4): an `in_review -> approved` that carries a verdict followed by `approved -> done` with no verdict keeps the verdict (probe, case J). An `{}` result on the later transition is "no result".
12. **Reader divergence inside Python.** `R review_result_from_state` (207) distinguishes slot absent, slot `None` and malformed; the oracle's `_review_result` collapses all three to null. The consumers that gate on a verdict use the former; the Work Package routes use the latter. This document follows the oracle.
13. **Annotation `at` ordering and decoding.** Annotations are sorted by text `(at, event_id)` after `str()` coercion (O2). Java's `LineKind.Annotation` today holds only `wpId`; WP05 extends it with the delta members and the sort keys it needs.
14. **Display lanes.** `Projector.lane` returns null for `genesis` and `uninitialized` and raises for any value outside the nine display lanes, in `history` as in `statusLane`. A bootstrap `genesis -> planned` row therefore shows `fromStatusLane: null`.
15. **Dedup key of seeds** (`seedKey`) is existing #5529 work (`StatusEvent.seedKey`): the canonical text is the sorted-key JSON of the whole row. This mapping does not change it, but a seed's `policy_metadata` and `review_result` now matter to what is served, so the canonical text must keep including both.

## 8. Member-to-route list

AC-8.4 and plan section 8 (FRESH3-003): the 26 (row, route) pairs of the projection rows T1 to T18, per route. Checked against `MissionHead`, `WorkPackageSummary`, `WorkPackage`, `WorkPackageDetail` and `Readiness` under `contracts/mission-status/schemas/` per plan. WP18's `ProjectionRowCoverageTest` asserts against this list; the rule is per pair, not per row (PLAN-FRESH4-002, D-141).

**`getMission`** (WP13, phase P9, `MissionDetailMapper`): 7 pairs.

| Pair | Members on this route |
|---|---|
| T1 | head `missionId`, `slug`, `targetBranch` |
| T2 | head `missionType`, `lastEventId` |
| T3 | head `friendlyName`, `nextAction` |
| T4 | head `acceptedAt`, `mergedAt`, `discardedAt` |
| T5 | `WorkPackageSummary` `wpId`, `dependencies[]`, `readiness.unsatisfied[]` |
| T6 | `WorkPackageSummary` `title`, `phaseLabel` |
| T10 | `WorkPackageSummary` `lastTransitionAt` |

**`getWorkPackage`** (WP14, phase P10, `WorkPackageMapper`): 10 pairs.

| Pair | Members on this route |
|---|---|
| T5 | `wpId`, `dependencies[]` |
| T6 | `title`, `authored.role`, `authored.agentProfile`, `authored.model`, `executionMode`, `taskType`, `priority`, `phaseLabel`, `review.latestResult.reference`, `review.override.reason`, `cancellation.reason`, `history[].reason` |
| T7 | `authored.subtasks[]`, `ownedFiles[]`, `requirementRefs[]`, `trackerRefs[]`, the `subtasks` map keys |
| T8 | `mergeTargetBranch` |
| T10 | `lastTransitionAt` |
| T11 | `lastEventId` |
| T12 | `history[].eventId` |
| T13 | `history[].at` |
| T14 | `review.override.at` |
| T17 | `assignment.*`, `implementerOfRecord`, `actor.*`, `review.latestResult.reviewer`, `review.override.actor`, `history[].actor.*` |

**`getWorkPackageDetail`** (WP15, phase P11, `WorkPackageDetailMapper`): 9 pairs.

| Pair | Members on this route |
|---|---|
| T1 | `missionId` |
| T5 | `wpId`, `DependencyEntry.wpId` |
| T7 | `SubtaskEntry.id`, `OwnedFileEntry.pattern` |
| T8 | `workspace.planningBranch` |
| T9 | `workspace.laneId`, `workspace.laneBranch` |
| T15 | `reviewCycles[].reviewedAt` |
| T16 | `reviewCycles[].feedbackReference`, `reviewCycles[].artifactPath` |
| T17 | `reviewCycles[].reviewer` |
| T18 | `SubtaskEntry.title` (class 1), `DependencyEntry.title` (class 2) |

Totals: 7 + 10 + 9 = 26 pairs. Every row T1 to T18 appears at least once: T1 (getMission, detail), T2, T3, T4 (getMission), T5 (all three), T6 (getMission, getWorkPackage), T7 (getWorkPackage, detail), T8 (getWorkPackage, detail), T9 (detail), T10 (getMission, getWorkPackage), T11, T12, T13, T14 (getWorkPackage), T15, T16 (detail), T17 (getWorkPackage, detail), T18 (detail).

The FR-020 members of sections 3 to 7 reach the routes through T17 (handles: `assignment.*`, `actor.*`, `latestResult.reviewer`, `override.actor`, `history[].actor.*`), T6 (`latestResult.reference`, `override.reason`, `history[].reason`), T12 to T14 (`history[].eventId`, `history[].at`, `override.at`) and T7 (`subtasks` keys).

## 9. Manifest classes, golden files and PROVISION_PLAN (P4, WP07)

Appended by WP07 (FR-014 as amended by plan section 14). The generator is `tests/contract/_mission_status_conformance.py`; the committed data is under `services/mission-status-api/src/test/resources/conformance/`.

### 9.1 The classes and the `surface` rule

Every class of the table below carries `"surface": "detail"` in its `classes[]` entry of `manifest.json`. The 14 classes of the first conformance gate carry no `surface` key (absent means `overview`), so their entries stay byte-identical. A `python-golden` detail class also carries `goldenFiles`, the file names each of its fixtures holds under `golden/`. `ConformanceTree.classes()`, `fixtures()` and `fixturesOf(tag)` return the overview surface only; `allClasses()`, `detailClasses()` and `detailFixtures()` return the rest.

| Class | Count | Parity | Golden files |
|---|---|---|---|
| `detail-populated` | 8 | python-golden | mission, work package, prompt, work package detail |
| `detail-early` | 1 | python-golden | mission |
| `detail-planning-only` | 1 | python-golden | mission, work package |
| `phases-matrix` | 19 | python-golden | mission |
| `wp-malformed-frontmatter` | 28 | python-golden | mission, work package, work package detail |
| `wp-duplicate-id` | 3 | python-golden | mission, work package, work package detail |
| `wp-two-selectors` | 1 | python-golden | work package, work package detail |
| `wp-prompt-bytes` | 13 | python-golden | work package, prompt |
| `cycles` | 4 | python-golden | work package detail |
| `legacy-lanes-json` | 1 | python-golden | work package detail |
| `tasks-md` | 12 | python-golden | work package detail |
| `worktree-states` | 7 | python-golden | work package detail (host `git=False, worktrees=True`) |
| `artifacts-populated` | 1 | python-golden | listing, content |
| `artifacts-sort` | 1 | python-golden | listing |
| `artifacts-refusals` | 1 | python-golden | content |
| `artifacts-links` | 3 | java-only | none |
| `artifacts-redaction` | 1 | python-golden | content |
| `lookup-faults` | 3 | java-only | none |
| `projection-nulls` | 6 | python-golden | mission, work package, work package detail |
| `projection-refusals` | 4 | java-only | none |

`resolved-state` is WP08's and is not in this table. `CLASS_FLOORS` (Python) holds the 14 overview floors plus the Count column; `GoldenSuiteTest.CLASS_FLOORS` (Java) keeps the 14; `DetailManifestCensusTest.DETAIL_CLASS_FLOORS` (Java) holds the Count column; `test_the_java_class_floors_mirror_the_python_ones` parses both Java maps and demands that their union equals the Python map. A floor equals the class's fixture count at the commit that adds it and is never lowered.

### 9.2 Golden file names and the key convention

One file per route, named after the operation: `get-mission.json`, `get-work-package.json`, `get-work-package-prompt.json`, `get-work-package-detail.json`, `list-artifacts.json`, `get-artifact-content.json`. Each is one canonical-JSON object (the existing `canonical_bytes` writer: sorted keys, compact, UTF-8) keyed by the request key:

- `-` for a Mission-level route (`get-mission.json`, `list-artifacts.json`);
- the Work Package id for the three Work Package routes. `get-work-package-detail.json` also holds the key `WP99`, an id no fixture holds (the 404 control);
- the artifact path for `get-artifact-content.json`: every path of the listing, then the extra paths of the fixture's `ARTIFACT_REQUESTS` file (one path per line, for a missing file or a refused path).

A value is the payload itself (Mission detail, Work Package), `{"status": n, "body": {...}}` for an operation that answers a status (Work Package detail, listing, content), or `{"refusal": {"exception": "<class>", "line": null}}` for an exception the oracle raised. The subject Mission of a fixture is the first directory, in name order, whose `meta.json` holds a `mission_id`; every other directory is a distractor. The Mission and Work Package payloads are index-fed: the winning file of each id (`index_work_packages`) is re-read with `read_authored_wp_frontmatter` and passed as `files=`, so the malformed, duplicate and two-selector classes are a true oracle golden of the shared index rule (FR-006). Names contain none of `: " ? * | { } $` (NFR-007).

### 9.3 PROVISION_PLAN

A file named `PROVISION_PLAN` at the **fixture top level**, never inside a Mission directory (ruling OO-4: `NOT_COPIED` names it, so it never reaches a scratch tree, a listing or a golden; WP10's `ProvisionPlan` reads it from the source fixture directory). Tab-separated, verb-first lines; paths are relative to the project root and may not be absolute or contain `..`; blank lines and lines that start with `#` are ignored; lines are applied in file order to the temporary copy, before the oracle runs and before the service runs.

| Verb | Arguments | Effect |
|---|---|---|
| `link` | `path`, `target` | a symbolic link at `path` to `target`, a root-relative path; `@outside/x` points into a sibling directory made from the fixture's `outside/` tree |
| `gitentry` | `path` | a plain file at `path`, named `.git` by the line (content irrelevant to a stat) |
| `mtime` | `path`, `epochSeconds` | sets the modification time (the `modifiedAt` of a listing) |
| `dir` | `path` | creates a directory (the lane worktrees of `worktree-states`; `.worktrees/` is ignored by git, so it cannot be committed in place) |
| `write` | `path`, `text` | creates a file with `text` as its content (no trailing newline added). A non-ASCII file name is made this way: a committed one stops the native-image test build, whose resource scan fails on it, so `artifacts-sort` commits ASCII names and writes `café.md`, a CJK name, U+FF5E and U+1F600 names here |
| `substitute` | `path`, `marker`, `fragment...` | replaces the marker text in the committed file with the concatenated fragments, so no host path, address or credential shape is committed whole (D-48); a marker that is not in the file is an error |

A leg that cannot create a link reports `not run: link unsupported`, never a pass. `SYMLINK_PLAN` (the existing `symlink` class) keeps its own `javaOnly` grammar and is read exactly as before; the two files coexist. `ARTIFACT_REQUESTS` is also in `NOT_COPIED`. The `junction` fixture of `artifacts-links` carries a comment line only: a junction is created by the Windows leg of the Java harness.

### 9.4 The `knownDivergences` list

The manifest holds a top-level list under the key `knownDivergences`, one entry per row: `V1` to `V20` of the specification table as amended, and `V21` to `V25` for the five D-159 candidates (a) to (e) of the resolved-state reduction (their fixtures arrive with WP08, so they name the class only). An entry has `id`, `cause`, `fixture` (a class, or `injected` or `generated at test time`), `fixtures` (the committed `class/name` keys it covers, possibly empty), `oracleOutcome` and `javaAssertion`; the two differ, or the entry is stale and the Python test fails. `V3` and `V4` also carry `defaultPathOutcomes`: the outcome of the oracle's own default `read_authored_files` path on the same provisioned fixture, per fixture key (a duplicate id listed twice, `FrontmatterError` on a malformed file, a symlinked file followed); the Python test fails when the live default path does not reproduce the stored outcome. A fixture is tagged `knownDivergence` in `classes[].fixtures[].tags` only when its golden differs from the Java outcome on purpose: `ps-link-file`, `ps-link-completed`, `ps-link-started`, `ps-link-neither` (V1), `directory-symlink`, `git-entry-symlink` (V7), `head-dates-nulled` (V19) and `wpm-28` (V20). `ConformanceTree.knownDivergences()` reads the list for WP10 and the route WPs.

## 10. The `resolved-state` class (P4b, WP08)

Appended by WP08 (T054). The class holds 21 fixtures under `conformance/resolved-state/`, `surface: detail`, `parity: python-golden`, one golden file each (`get-work-package.json`, keyed by Work Package id; the value is the `WorkPackage` body). Floor: `CLASS_FLOORS["resolved-state"] = 21` (Python) and `DETAIL_CLASS_FLOORS` entry `resolved-state` = 21 (Java); never lowered. No existing conformance class gained a golden and no overview byte changed (AC-20.2). `lifecycleTypes` is not a body member and is pinned by `phases-matrix` (`marker-row-without-event-id`), so the class has no `get-mission.json`.

### 10.1 Mapping row to fixture

| Mapping row (section 3) | Fixture (golden member shown non-empty) |
|---|---|
| `assignment.agent` set / overwritten / cleared | `set-each-member`, `overwrite-each-member` (WP01 `agent-first` then `agent-second`; WP02 untouched), `clear-each-member` (`release_runtime_claim`) |
| `assignment.assignee`, `role` (annotation slots, a release does not clear them, `""` is a no-op) | `set-each-member`, `overwrite-each-member`, `clear-each-member`, `annotation-order` ((at, event_id) order, not file order) |
| `assignment.agentProfile`, `agentProfileVersion`, `model`, `provider` | `set-each-member`, `overwrite-each-member` |
| the four absent-sentinels shown as null (4.4, 7.2) | `model-absent-sentinel` (WP01 all four sentinels; WP02 a real model and profile replaced by sentinels, provider and version kept) |
| `subtasks`, `subtaskProgress` (`done` counts the literal `done`) | `set-each-member` (2 of 4), `overwrite-each-member` (per-id replace), `clear-each-member` (subtasks survive) |
| review result, each verdict | `review-result-approved` (a null `reference` shown as `""`), `review-result-changes-requested` (`feedback_path` not exposed), `set-each-member`, `overwrite-each-member` (replaced) |
| review result sticky / cleared (7.11, W4) | `review-result-sticky` (a later transition with no result or `{}` keeps it; a Work Package that never had one stays null), `clear-each-member` (forced `in_review` exit with none) |
| review override: complete, partial, release marker | `set-each-member` (complete), `override-partial` (blank reason; reason only; offset-less time shown as null), `override-release-marker` (a complete record then the all-empty marker; the marker alone) |
| `actor` of the latest applied transition (4.8, 7.7) | `actor-forms` (structured record shows `tool`; text that is no handle shows null; annotation-only Work Package takes the first annotation's actor; a transition that lost arbitration leaves it), `set-each-member` |
| seed payload fold (A4, 7.9) | `losing-seed-payload` (lane `blocked`, `agent` and the verdict from seeds that lost on continuity) |
| ordered `history` (4.9, 7.3, 7.4) | `history-mixed-offsets` (stamps with `Z`, a fraction and offsets; two stamps for one instant ordered by event id; annotation, lifecycle and retrospective rows between; `force` true, `1`, `"yes"`; the genesis bootstrap shows a null from-lane) |
| the control | `no-members` (every resolved member empty, history still listed) |
| D-159 (a) to (e), V21 to V25 | see 10.2 |

`marker-row-lifecycle-types` of the prompt's starting list is not in this class, by the reason above.

### 10.2 The knownDivergence fixtures

| Entry | Fixture | Oracle outcome in the golden |
|---|---|---|
| V21 (a) float agent or actor | `float-agent-and-actor` | `agent` `"1.5"`, `actor.tool` `"2.5"` |
| V22 (b) annotation `at` or override member not text | `annotation-at-float`, `annotation-at-list`, `override-member-float` | the annotation is read (its `str()` is the sort key); `reason` `"2.5"` |
| V23 (c) verdict not text | `verdict-not-text` | `verdict` `7`, the raw value |
| V24 (d) subtask status `genesis` / `uninitialized` | `subtask-status-genesis` | both kept, `subtaskProgress` `{done: 1, total: 3}` |
| V25 (e) history `eventId` not text | `history-event-id-not-text` | `eventId` `424242`; a non-text `at` or lane makes the oracle refuse the Mission, so there is no golden for them |
| V26 review-cycle number above the int range (WP15 F3) | none (generated at test time) | oracle serves it; Java 500 `source_unreadable` |

The seven fixtures carry the `knownDivergence` tag in `manifest.json`; V21 to V25 name them in `fixtures`. V26 (WP15) has no committed fixture: its case is generated at test time (`WorkPackageDetailCyclesTest`).

### 10.3 Floors and gates

Python `CLASS_FLOORS` and Java `DETAIL_CLASS_FLOORS` both hold `resolved-state` = 21; `test_the_java_class_floors_mirror_the_python_ones` is green. Oracle drift (PRs 5953, 6127, 6122, src hunks applied to a scratch copy): `--check` 326 files, 0 differences.
