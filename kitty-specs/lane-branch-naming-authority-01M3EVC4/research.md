# Research: Lane Branch Naming Authority

Consolidates the Phase-0 research for plan.md. Two research passes were run (profile-loaded): naming-authority design (architect-alphonso) and #5113 decision materialization (python-pedro). Their full reports follow verbatim as Part A and Part B, after the adjudications below.

## Adjudications (orchestrator, within the confirmed Intent Summary)

| # | Question raised by research | Decision | Rationale | Alternatives |
|---|---|---|---|---|
| ADJ-1 | NFR-001 (goldens unchanged) vs FR-002 (no identity parameter) conflict on lane/worktree goldens that encode identity-injected names | Read NFR-001 as "every golden describing a *created* name stays byte-identical"; re-pin lane/worktree columns of identity-injected rows to the created name (PD-3) | Those goldens pin the #5108 defect (e.g. `GOLDEN_ROWS["legacy-NNN-with-mid8-1589"]` is literally shape (a)); charter standing order #4: judge the test — stale → re-pin | Keep a private identity-aware composer to satisfy them — violates FR-002/C-004 |
| ADJ-2 | FR-005 literal reading would refuse every non-coordination resume (tips only captured on coord topology) | Scope the refusal to coordination topology with a persisted `pre_mutation_coord_sha` (PD-4); spec FR-005 amended | Matches where the anchor exists; non-coordination Missions have no guard to disarm | Extend tip capture to all topologies — larger change, outside #5108 |
| ADJ-3 | Extra match sites `merge/resolve.py:44`, `core/vcs/detection.py:159` | Fold into FR-008 | Same class; tiny; gate would otherwise need allow-list entries | Allow-list with justification |
| ADJ-4 | Extra divergent site `acceptance/__init__.py:770` | Fold into FR-006 | Same defect: acceptance silently finds no lane source roots for divergent shapes | Follow-up |
| ADJ-5 | `status/aggregate.py:751` recomposes the Mission branch with identity | Fold into FR-011 (prefer manifest `mission_branch`) | Same defect class, one line | Follow-up |
| ADJ-6 | Six more emitters of the false `doctor workspaces --fix` remedy | Fold all into FR-014 (PD-10) | FR-014 is about the error the operator sees, wherever it is raised; text-only changes | Fix one site, follow-up for the rest |
| ADJ-7 | Review-workspace lane creation outside the allocator (`workflow.py:1691`), recovery prefix over-match, `mission_state` rebuild, >26-lane grammar | Follow-up issues at close-out | Naming-compliant or distinct defects; locality of change | Fold |

---

## Part A — Naming authority (architect-alphonso)

### 0. Headline findings

1. **Today, creation never uses the identity.** `predict_lane_worktree` (`lanes/worktree_allocator.py:265-281`) calls `lane_branch_name(slug, lane)` and `worktree_path(..., mission_id=None, ...)`. The **created name** is therefore already the slug-only form. The #5108 defect comes from six *read* sites that pass `mission_id` (§1).
2. **The spec's list misses one divergent site.** `acceptance/__init__.py:770` (`_approved_lane_source_roots`) passes `mission_id=manifest.mission_id`. For divergent shapes, acceptance silently finds no lane source roots. Fold it into FR-006.
3. **NFR-001 and FR-002 conflict** on the goldens (§1.4). This needs an operator ruling.
4. **FR-005 needs scoping.** Lane tips are captured only on coordination topology (`executor.py:1985`, inside `_resolve_pre_mutation_coord_sha`). A literal FR-005 would refuse every resume of a non-coordination Mission (§3).
5. **FR-011 has one writer and one creator.** `compute_and_write_lanes` is the only writer. `_ensure_mission_branch` then creates the branch *from the manifest value*. So after a re-finalize, the phantom name is actually **created**: the next allocation forks a new Mission branch off the target (§4).
6. **NFR-002 conflicts on two functions already over the ceiling.** `compute_lanes` scores 34 and `backfill_ownership` scores 24; both are hidden by `ruff.toml` per-file C901 ignores. The design keeps both untouched (§4, §6).

---

### 1. Authority API

#### 1.1 Current signatures (`lanes/branch_naming.py`)
- `lane_branch_name(mission_slug, lane_id, planning_base_branch=None, *, mission_id=None)` — L389
- `worktree_dir_name(mission_slug, *, mission_id, lane_id)` — L440. `mission_id` is **required keyword**, so every caller must choose a form.
- `worktree_path(repo_root, mission_slug, *, mission_id, lane_id)` — L472
- `mission_branch_name(mission_slug, *, mission_id=None)` — L195. It is independent: it is not built on `lane_branch_name`, and the dependency runs the other way (`worktree_dir_name` → `lane_branch_name`).

A grammar subtlety that must stay byte-identical: with `mission_id=None`, the branch uses `_idempotent_legacy_body`, which strips `NNN-` when the slug embeds a mid8. The worktree dir is `f"{slug}-{lane}"` **verbatim**. For slug `057-foo-01KV6510` that gives branch `kitty/mission-foo-01KV6510-lane-a` and dir `057-foo-01KV6510-lane-a`. Both are the created names; the authority keeps both behaviours.

#### 1.2 Every src caller of the lane functions (by `mission_id` value)
**Non-None identity (the divergent sites, 6):**
- `merge/reconciliation.py:855` `_lane_branch_for`
- `merge/executor.py:1945` `_capture_pre_interrupt_lane_tips`
- `merge/executor.py:2756` cleanup, using `run.baseline_mission_id`
- `merge/executor.py:2966` `_pre_mutation_safety_preflight`, using `canonical_mission_id`
- `lanes/lifecycle_sync.py:103` `_resolve_lane_branch` (the probe)
- `acceptance/__init__.py:770` — **new, not in the spec**

**Explicit `mission_id=None` (behaviour-preserving, 18):**
- `worktree_allocator.py:280`
- `lanes/merge.py:204`
- `lanes/recovery.py:398`, `:696`, `:718`
- `lanes/implement_support.py:94`
- `lanes/lifecycle_sync.py:170`
- `merge/executor.py:2782`
- `orchestrator_api/commands.py:915`, `:1338`
- `cli/commands/mission_type.py:1153`
- `coordination/status_transition.py:1462`
- `cli/commands/agent/tasks_parsing_validation.py:608`
- `workspace/context.py:309`, `:898`, `:908`, `:978`, `:1000`

**No identity argument (already the created form):**
- `worktree_allocator.py:279`, `:990`
- `lanes/merge.py:263`
- `lanes/lifecycle_sync.py:111`
- `lanes/implement_support.py:480`
- `merge/executor.py:654`, `:2794`
- `orchestrator_api/commands.py:944`
- `mission_type.py:828`, `:1052`
- `context/resolver.py:270`
- `core/worktree_topology.py:220`
- `migration/backfill_ownership.py:148`
- `workspace/context.py:889`, `:911`

Other callers:
- `predict_lane_worktree` is called at `worktree_allocator.py:552`, `implement_support.py:166`, `:375`, `for_review_gate.py:132` and `orchestrator_api/commands.py:1443`.
- Three-positional `worktree_path(repo_root, slug, mid8)` calls, such as `coordination/workspace.py:261`, are `CoordinationWorkspace.worktree_path`. That is a different function and is out of scope.

#### 1.3 Decision
- **Decision:** the authority is `predict_lane_worktree(repo_root, mission_slug, lane_id) -> (Path, str)`, the placement decision, delegating to the grammar in `branch_naming.py`. Its public lane surface becomes:
  - `lane_branch_name(mission_slug: str, lane_id: str, planning_base_branch: str | None = None) -> str`
  - `worktree_dir_name(mission_slug: str, *, lane_id: str) -> str`
  - `worktree_path(repo_root: os.PathLike[str] | str, mission_slug: str, *, lane_id: str) -> Path`

  `mission_id` is removed from all three (FR-002). The bodies become today's `mission_id is None` branches. `worktree_dir_name` must stop delegating to `lane_branch_name`; the dir stays verbatim, as in §1.1.
- **The split is required.** `mission_branch_name`, `mission_branch_name_required`, `coord_branch_name`, `resolve_branch_name` and `resolve_transaction_mid8` **keep** `mission_id`. They name the Mission and coordination branches, not lanes. `coord_branch_name` and `mission_branch_name_required` delegate to `mission_branch_name`, never to the lane functions, so the removal does not ripple into them. `_mid8` and `_human_slug_for_mid8_branch` remain in use by `mission_branch_name` only.
- **Rationale:** slug + lane id is exactly the creation input. With no identity parameter, no caller can request a naming form, and the "invalid identity < 8 chars" crash goes away: `_mid8` raises from `lane_branch_name` today.
- **Alternatives:**
  - (a) Keep the parameter and ignore it — a dead knob that FR-002 forbids.
  - (b) Add a new `LanePlacement` value object keyed on the manifest — nicer, but a second API surface. Not needed, because every consumer already holds the slug and lane id. At most, add a private executor helper `_created_lane_branch(run, lane_id)` to deduplicate the four executor call sites (S1192).

#### 1.4 Golden conflict with NFR-001 (needs a ruling)
Rows whose lane or worktree goldens encode a name creation never produces:
- `tests/specify_cli/lanes/test_branch_naming_ssot_entrypoint.py` `_PARITY_CASES`:
  - row 1 (`mission-id-canonical-identity-migration`, `_OTHER_ID`)
  - row 2 (`083-my-feature`, `_OTHER_ID` → `my-feature-01KNXQS9-lane-a`)
  - row 5 (`plain-slug`, `_FULL_ID` → `plain-slug-01KV6510-lane-a`)
  - Row 3 (embedded, matching id) gives identical bytes without `mission_id`. Row 4 is unchanged.
- `tests/lanes/test_branch_naming_seam.py` `GOLDEN_ROWS["legacy-NNN-with-mid8-1589"]`: `lane_branch="kitty/mission-test-01COORD0-lane-a"`, `worktree_dir="test-01COORD0-lane-a"`. This is literally #5108 shape (a).
- `tests/core/test_branch_naming_human_slug.py`: lane cases at L93, L100, L108, L114, L138-139, L264 and L306 (the mismatched-mid8 lane).

Test-call inventory: **61** test calls pass a `mission_id` keyword to lane naming (37 non-None). They sit in 18 files; the largest are `tests/merge/test_reconciliation.py` (15), `tests/core/test_branch_naming_human_slug.py` (9) and `tests/lanes/test_branch_naming_seam.py` (8).

- **Decision (proposed):** read NFR-001 as "every golden that describes a *created* name is byte-unchanged".
  - Mission-branch, coordination and mission-dir columns stay unchanged.
  - Lane and worktree columns of mid8-injected rows are re-expressed as the slug-only created name. They get new rows asserting that divergent shapes compose the created name.
  - Row 3 and the legacy rows keep the same bytes.
- **Rationale:** those goldens pin the defect.
- **Alternative:** keep them through a private identity-aware composer. That violates FR-002 and C-004. The operator must confirm this as a spec clarification to NFR-001/SC-004.

### 2. Which slug

- **Decision:** the key is `LanesManifest.mission_slug`, the "Mission slug recorded for the lane".
- **Rationale:**
  - Creation receives `mission_slug` from implement or orchestrator (`implement_support.py:166-173`, `orchestrator_api/commands.py:1375`).
  - Finalize writes the manifest with the same slug: `mission_finalize.py:2503` (slug from `owned.slug` / `_resolve_mission_slug`, L3336) or `planning_dir.name` (L3503); `tasks_finalize.py:382` (`st.mission_slug`); `migration/mission_state.py:1621`.
  - All of these are the `kitty-specs/<dir>` name, which equals `meta.json.mission_slug`.
  - Backfill (`migration/backfill_identity.py:96 backfill_mission`) writes only identity fields. It never renames the directory or touches `lanes.json`, so the slug is stable across backfill (confirms the spec Assumption).
- **Executor note:** the executor mixes `run.mission_slug` (L654, L2756, L2782, L2794) with `run.lanes_manifest.mission_slug` (L1945, reconciliation). Route all of them through one helper keyed on the manifest slug.
- **Can a modern Mission's lanes be created in mid8-form through `mission_id`?** No. No creation path passes an identity. A lane is mid8-form only when its slug embeds the mid8, which is the modern norm (for example, this Mission's own slug). In that case slug-only and identity forms coincide. There are two exceptions: a mismatched embedded mid8, where `_human_slug_for_mid8_branch` does not strip it, and an invalid identity.

#### C-005 creation-site enumeration

| Site | Creates | Name source | Verdict |
|---|---|---|---|
| `worktree_allocator.py:1169` `_create_lane_worktree` (`worktree add -b`) | lane branch + worktree | `predict_lane_worktree` | authority ✔ |
| `worktree_allocator.py:1195` `_recover_lane_worktree` (attach) | worktree | allocator L619; `recovery.py:696` (`_worktree_path` None + parsed branch) | authority ✔ (FR-006 kwarg drop) |
| `worktree_allocator.py:898` `_create_branch_from` (via L1118 `_ensure_branch_exists` coordination, L1151 `_ensure_mission_branch`) | coordination / Mission branch | manifest `mission_branch` / `coordination_branch` | not a lane; see FR-011 |
| `lanes/lifecycle_sync.py:186` `worktree add <path> <lane_branch>` | lane worktree (attach) | **probe** `_resolve_lane_branch` | fold into FR-007 |
| `cli/commands/agent/workflow.py:1691/1693` review workspace (`-b` when the branch is absent) | lane branch + worktree | `workspace/context.py:911` (`lane_branch_name`, no id) | name ✔. **A second creation path outside the allocator** (branches from HEAD); naming-compliant, so file a follow-up rather than fold |
| `core/worktree.py:309` `create_wp_workspace` | per-WP worktree | caller-supplied | **no src callers** (dead code); gate-exempt, flag |
| `mission_branch_context.py:260` `switch -c` | Mission branch | not a lane | out of scope |
| `update-ref` (`git/ref_advance.py:502`, `:542`) | advances only, never creates lanes | — | ✔ |

### 3. Per-site change list

#### FR-003 — `merge/reconciliation.py`
- `_lane_branch_for` (L853): drop `mission_id`.
- `_collect_approved_shas` (L884, CC5), `_collect_excluded` (L904, CC3), `_collect_authored` (L1055, CC5): no code change beyond the helper.
- In `build_approved_wp_set` (L770), after the snapshot, add `_unresolvable_approved_lane_branches(repo_root, manifest, work_packages) -> list[tuple[str, str]]`. It covers approved lanes (`_lane_is_approved`) other than `lane-planning`, using `lanes/_git.branch_exists` (L49). If any branch is missing, return `ApprovedWpCommitSet(refusal="approved lane <id>: created branch '<branch>' does not exist …")`.
- Keep `_lane_tip_commits` / `_lane_first_parent_spine` tolerant **only** for the canceled axis. For approved lanes whose branch passed the existence check, a `GitProbeError` becomes a named refusal rather than `[]`. Implement this with a `tolerate: bool` parameter or a separate strict helper.
- `build_approved_wp_set` is currently CC2 and stays ≤ 5.

#### FR-004 — `executor.py:1928` `_capture_pre_interrupt_lane_tips` (CC4)
- Drop `mission_id` and use the shared `_created_lane_branch(run, lane_id)`.
- Also skip lanes whose WPs are all in `run.excluded_canceled_wp_ids`, which is set at L3033 before the claim at L3150.

#### FR-005 — `_enforce_resume_anchor_integrity` (L1991, CC5; loop at L2034-2043)
- Add an H5 check before the CAS loop: `missing = _unanchored_lane_branches(run)`. This is the set of non-planning lanes, excluding fully-canceled ones, whose `_created_lane_branch` key is not in `state.pre_interrupt_lane_tips`. If `missing` is non-empty, refuse and name `spec-kitty merge --abort` followed by a fresh merge.
- **Gate H5 on** `coord_topology and state.pre_mutation_coord_sha`. That is the condition under which tips were captured (L1985).
- Non-coordination Missions never persist tips, so an unscoped H5 would refuse every legacy resume. **Needs a ruling:** either scope as above (recommended), or extend capture to non-coordination topologies (larger change).
- An old-release record keyed under the mid8 form fails this check. That is the intended refusal (US2 AS2).
- The function goes to about CC6.

#### FR-006 — consumer re-routes

| Site | Change |
|---|---|
| `executor.py:2966` preflight | Drop `canonical_mission_id` (the **behaviour fix**, AS4). The `canonical_mission_id` parameter may become unused. Check the callers at L3379 and L3537. |
| `executor.py:2756` cleanup | Drop `baseline_mission_id` (**behaviour fix**, AS5). |
| `executor.py:2782`, `:2794`, `:654` | Use `_created_lane_branch` / kwarg drop. `_phase_cleanup_worktrees_and_branches` is CC10 now; extracting `_remove_lane_worktrees` and `_delete_lane_branches` makes it about CC4. |
| `lanes/merge.py:204`, `:263` | Kwarg drop / none. |
| `orchestrator_api/commands.py:915`, `:944`, `:1338` | Kwarg drop. `_apply_lane_merge_cleanup` is CC8. |
| `mission_type.py:828`, `:1052`, `:1153` | Kwarg drop at L1153. |
| `workspace/context.py:309`, `:889`, `:898`, `:908`, `:911`, `:978`, `:1000` | Kwarg drops. |
| `context/resolver.py:270`, `core/worktree_topology.py:220`, `implement_support.py:94`, `:480`, `worktree_allocator.py:280`, `:990`, `migration/backfill_ownership.py:148` | None or kwarg drop. **Do not touch** `backfill_ownership` (CC24) beyond that. |
| `lanes/recovery.py:398`, `:696`, `:718`; `status_transition.py:1462`; `tasks_parsing_validation.py:608` | Kwarg drop. |
| `acceptance/__init__.py:770` | Drop `mission_id` (**new divergent site**). |

#### FR-007 — `lanes/lifecycle_sync.py`
- Delete `_resolve_lane_branch` (L92-124, CC4) and `_git_ref_exists` (L81), since the latter is used only by the probe.
- `sync_lane_after_coordination_commit` (CC7) uses `predict_lane_worktree(repo_root, mission_slug, lane.lane_id)` for both path and branch.
- The HEAD fallback (`rev-parse --abbrev-ref HEAD`) is also a third strategy; remove it.

#### FR-008 — match sites and parsers
New parsers in `branch_naming.py`:
- `parse_lane_worktree_dir(dir_name: str) -> tuple[str, str] | None` returns `(slug, lane_id)` by right-anchored `-(lane-[a-z]+)$`.
- `lane_id_for_worktree_dir(dir_name: str, mission_slug: str) -> str | None` recognizes a dir by *recomposing* `worktree_dir_name(mission_slug, lane_id=…)` and comparing, not by prefix.
- Fix `is_lane_branch` to accept `_PLAIN_LEGACY_LANE_RE`. Today it rejects `kitty/mission-foo-lane-a`, which creation produces for a bare slug.

| Site | New form |
|---|---|
| `git/sparse_checkout.py:229` `matches_path` | `lane_id_for_worktree_dir(path.name, self.mission_slug) is not None` |
| `git/sparse_checkout.py:236` `expected_branch_for` | **This is a hand-rolled compose.** Replace with `lane_branch_name(self.mission_slug, lane_id)`. It currently diverges for `NNN-` coordination Missions: the coordination branch is verbatim `060-test-<mid8>` while the created lane is `kitty/mission-060-test-lane-a`. |
| `_coordination_doctor.py:774` | `lane_id_for_worktree_dir` |
| `status/doctor.py:287` glob `{slug}-lane-*` | `iterdir` + `lane_id_for_worktree_dir` |
| `live_work/bindings.py:40` `_WORKTREE_DIR_RE` | This mid8-only regex misses legacy dirs. Replace with `parse_lane_worktree_dir`, then confirm the Mission by `worktree_dir_name(m.mission_slug, lane_id=…) == name` instead of by mid8 prefix. |
| `policy/commit_guard.py:40` `_LANE_BRANCH_RE` | `is_lane_branch` (after the plain-legacy fix). Only the `is_implementation_branch` body changes; the CC14 `validate_staged_files` is untouched. |
| Extra, not in FR-008: `merge/resolve.py:44` | Redundant legacy regex after `parse_mission_slug_from_branch`; delete it. |
| Extra, not in FR-008: `core/vcs/detection.py:159` | Round-trips a dir through the branch parser, which is wrong for `NNN-`+mid8 slugs; use `parse_lane_worktree_dir`. |

Recommend folding both extras. Otherwise, allow-list them with a justification.

### 4. FR-011 — Mission branch

- **Where it is created:** `allocate_lane_worktree` → `_ensure_mission_branch(repo_root, decision.topology_parent_ref, target)` (L684; body L1139-1156). `topology_parent_ref` is `lanes_manifest.mission_branch` for the FRESH_LEGACY route (`_resolve_lane_parent`, L333-348). Coordination Missions parent on `coordination_branch` instead.
- **Consequence:** the **manifest is the name source**. A re-finalized phantom name gets *created* off the target, and lanes fork from an empty Mission branch.
- **Writers:** `compute.py:518` (planning-only), `:715` (main), `:852` (`_empty_manifest`). All go through `compute_and_write_lanes` (`compute_and_persist.py:126-136`), which already reads `previous_lanes`.
- **Decision:** apply preservation in `compute_and_write_lanes`, next to the existing `planning_commit_sha` post-assignment (L135). The helper is `_preserved_mission_branch(previous: LanesManifest | None, computed: str) -> str`. It returns `previous.mission_branch` when present, otherwise `computed`. First-time finalize is unchanged (US3 AS2).
- **Rationale:** `compute_lanes` is CC34 behind a `ruff.toml` per-file C901 ignore. Editing it would put a CC34 function on the touched list (NFR-002). `compute_and_write_lanes` is CC2 and is the single persistence boundary, including the `mission_state.py:1621` rebuild.
- **Alternatives:**
  - Thread the value into `compute_lanes`'s three sites. This touches a CC34 function unless it is first tidied to ≤ 15, a large refactor.
  - Persist a "created" flag. That is a schema change (C-002).
- **Independent composers (report, not in scope):**
  - `lanes/recovery.py:268` and `merge/preflight.py:123` / `:165`. These are fallbacks only when the manifest value is absent.
  - `status/aggregate.py:751`: `destination_ref = coordination_branch or mission_branch_name_required(slug, mission_id)`. For a backfilled legacy Mission with no coordination branch, this names the phantom branch. **Recommend a follow-up issue**, or fold by preferring the manifest `mission_branch`.
  - `migration/mission_state.py:1621`: a rebuild with no prior `lanes.json` recomposes with the identity. This residual risk cannot be fixed without probing.

### 5. Gate (FR-009)

The existing `tests/architectural/test_no_worktree_name_guess.py` (893 lines, the Design-P reference) scans `src/specify_cli` and `src/runtime` for three idioms:
1. `.worktrees` joins with f-strings
2. `f"kitty/mission-{…}"`
3. mid8 dedup

It has 5 allow-listed raw matches. It **does not** see identity-passing calls, `f"{x}-{lane_id}"`, or any regex, glob or startswith match.

- **Decision:** add a sibling `tests/architectural/test_lane_naming_authority_gate.py` that reuses `_ratchet_keys.composite_key`, the `(qualname, token)` keys. It has:
  - (i) **signature leg:** `inspect.signature` of `lane_branch_name`, `worktree_dir_name`, `worktree_path` and `predict_lane_worktree` has no `mission_id`. An AST leg flags any call to them with a `mission_id=` keyword.
  - (ii) **compose leg:** f-strings or `+` concatenations whose literal template contains `-lane-` or `kitty/mission-`, or matches `\}-\{[^}]*lane`. Docstrings, `lane-{…}` id minting, and prose sinks (`print`, `console.print`, `logger.*`, `raise …Error(…)`) are excluded, with prose confirmed by allow-list rather than heuristics.
  - (iii) **match leg:** a string containing `-lane-`, `lane-[` or `kitty/mission-` passed to `re.*`, `startswith`, `endswith`, `removeprefix`, `split`, `glob`, `rglob`, `fnmatch`, or used in an `in` comparison.
  - (iv) **self-test:** injects one synthetic offender per leg into a temp module and asserts red.
- **Timing:** land the gate last, at the final floor. Recording the baseline in plan.md satisfies NFR-003 without an ownership collision on a mutable constant.

**Measured baseline (src/specify_cli, seam excluded), to record in plan.md:**
- **Compose — identity-passing calls: 6 non-None + 18 `mission_id=None` = 24.** Target is 0; the signature change makes them impossible.
- **Compose — hand-rolled lane f-string: 1** (`git/sparse_checkout.py:236`). Target is 0.
- **Compose total outside the authority: 7** (1 + the 6 divergent). With the `None` form counted as a naming-form choice, the total is 25. Target is 0.
- **Match: 7** — `sparse_checkout.py:229`, `_coordination_doctor.py:774`, `status/doctor.py:287`, `live_work/bindings.py:40`, `policy/commit_guard.py:40`, `merge/resolve.py:44`, `core/vcs/detection.py:159`. Target is 0 lane-match sites outside the seam.
- **Excluded by spec:** recovery enumeration `recovery.py:136` (and its follow-up issue); prose `stale_check.py:118`, `context.py:101`, `coordination/workspace.py:126`, `coordination/policy.py:189`. Mission-level glob `core/mission_creation.py:72` is not a lane. These go in the allow-list with justification (5).
- **Existing gate's `_NAME_COMPOSE_BASELINE_RAW_MATCHES = 5`:** it drops to 4 if `detection.py:159` is fixed. Update `_ALLOWED_SITES_FILES` in the same WP.

### 6. Campsite (C901, `--max-complexity=10` probe; full scores)

Touched functions and their scores:
- CC10: `_phase_cleanup_worktrees_and_branches`, `_check_lane_sparse_checkout_drift`
- CC8: `_phase_merge_lanes`, `_apply_lane_merge_cleanup`
- CC7: `_merge_dependency_lane_tips`, `sync_lane_after_coordination_commit`, `_resolve_workspace_for_wp_impl`, `resolve_feature_worktree`, `_approved_lane_source_roots`
- CC6: `allocate_lane_worktree`, `_pre_mutation_safety_preflight`, `consolidate_lane_into_mission`, `check_orphan_workspaces`, `resolve_context`, `materialize_worktree_topology`, `_tombstone_lane_workspace_context_on_cancel`
- CC5: `_enforce_resume_anchor_integrity`, `_collect_*`, `_resolve_mission_from_worktree`, `_expected_discard_branches`, `_approved_dependency_lane_refs`, `_scan_live_branch_states`
- CC4: `_capture_pre_interrupt_lane_tips`, `_resolve_lane_branch` (deleted)
- CC ≤ 3: everything else

**Nothing touched is ≥ 13 except** two functions hidden behind `ruff.toml` per-file ignores: `compute_lanes` (**34**) and `backfill_ownership` (**24**). The design avoids editing both, per §4 and FR-006, where the call at L148 is already correct.

Tidy-first extractions (each needs focused tests):
- `_phase_cleanup_worktrees_and_branches` → `_remove_lane_worktrees(run)` + `_delete_lane_branches(run)`
- the executor helper `_created_lane_branch(run, lane_id)`
- `_unresolvable_approved_lane_branches` (reconciliation)
- `_unanchored_lane_branches` (executor)
- `_preserved_mission_branch` (compute_and_persist)

### 7. WP decomposition (file-disjoint; red-first tests listed)

| WP | Scope | owned_files | Depends | Red-first tests |
|---|---|---|---|---|
| **WP01** Reconciliation claim (FR-003, FR-012) | §3 FR-003, plus a shared divergent-shape fixture builder that creates lanes via `allocate_lane_worktree` for four shapes: backfilled `057-foo`, mismatched mid8, invalid id ≥ 8, invalid id < 8 | `src/specify_cli/merge/reconciliation.py`, `tests/merge/_divergent_shapes.py` (new), `tests/merge/test_reconciliation_divergent.py` (new), `tests/merge/test_reconciliation.py` | — | claim attributes each shape; canceled + survivor; missing created branch → named refusal; `TestPlanningArtifactReachesTarget` green with its fixture unedited |
| **WP02** Executor stages (FR-004/005/006-executor) | tips, H5 resume refusal, preflight, cleanup, merge-lanes, `_created_lane_branch` | `src/specify_cli/merge/executor.py`, `tests/merge/test_executor_lane_naming.py` (new), `tests/merge/test_executor_terminus_integrity.py`, `tests/integration/test_merge_lane_worktree_safety.py` | WP01 (fixture) | tips keyed by created name; unanchored / old-form record refuses with `--abort`; canceled-only and planning-only exempt; dirty divergent worktree refuses; 0 orphans after merge (SC-002); 4/4 end-to-end (SC-001) |
| **WP03** Lanes + CLI consumers (FR-006 rest, FR-007) | probe removal; kwarg drops; acceptance fix | `lanes/lifecycle_sync.py`, `lanes/merge.py`, `lanes/recovery.py`, `lanes/implement_support.py`, `acceptance/__init__.py`, `coordination/status_transition.py`, `cli/commands/agent/tasks_parsing_validation.py`, `orchestrator_api/commands.py`, `cli/commands/mission_type.py`, `workspace/context.py`, and their tests | — | lifecycle sync on a divergent shape attaches the created branch (was probe/HEAD); acceptance source roots found for a divergent shape |
| **WP04** Match sites + parsers (FR-008) | new parsers, `is_lane_branch` fix, six (to eight) match sites | `lanes/branch_naming.py` (additive only), `git/sparse_checkout.py`, `cli/commands/_coordination_doctor.py`, `status/doctor.py`, `live_work/bindings.py`, `policy/commit_guard.py`, `merge/resolve.py`, `core/vcs/detection.py`, `tests/specify_cli/lanes/test_lane_naming_parsers.py` (new) | — | parsers recognize all three grammars; commit guard recognizes plain-legacy; doctor finds legacy orphan dirs; `expected_branch_for` on an `NNN-` coordination Mission |
| **WP05** Mission branch (FR-011, FR-010 re-verify) | `_preserved_mission_branch` | `lanes/compute_and_persist.py`, `tests/lanes/test_refinalize_mission_branch.py` (new) | — | finalize → backfill → re-finalize keeps byte-identical `mission_branch`; first finalize unchanged; FR-010 lane-id stability plus the `origin/<lane>` tests still green |
| **WP06** Signature cutover + gate (FR-002, FR-009) | remove `mission_id` from the three functions; `worktree_allocator.py:280`; migrate the 61 test calls and the goldens (§1.4); new gate + self-test; update the existing gate's allow-list and guidance text | `lanes/branch_naming.py`, `lanes/worktree_allocator.py`, `tests/architectural/test_lane_naming_authority_gate.py` (new), `tests/architectural/test_no_worktree_name_guess.py`, naming test files | WP01–WP04 | signature test red before the cutover; injected offenders red |
| **WP07** #5113 (independent) | reserved; designed by the other research agent | `decisions/service.py`, `decisions/emit.py`, `coordination/surface_resolver.py`, `doctor workspaces` CLI module | — | per the sibling research |

WP01–WP04 each drop the `mission_id=None` kwargs in their own files. Passing `None` is legal before the cutover, so WP06 only touches the seam, the allocator and the tests. WP04 and WP06 share `branch_naming.py`, which the dependency serializes. Parallelism: {WP01, WP03, WP04, WP05, WP07} → WP02 → WP06.

### 8. Risks

1. **NFR-001 vs FR-002 golden conflict** (§1.4). An operator ruling is required before WP06.
2. **FR-005 scope for non-coordination Missions** (§3). Taken literally, it would refuse all legacy resumes.
3. **Hidden C901 debt.** `compute_lanes` (34) and `backfill_ownership` (24) must stay untouched, or NFR-002 fails.
4. **Invalid-identity shapes beyond naming.** Other merge stages still read `mission_id`: the post-fix marker `_post_fix_marker_path`, `baseline_mission_id`, and the coordination mid8. SC-001 (4/4 end to end) may surface non-naming failures. Keep the end-to-end test in WP02 as the proof.
5. **Behaviour changes hidden in "re-routes".** `sparse_checkout.expected_branch_for` for `NNN-` coordination Missions, `live_work` binding by slug instead of mid8, and `is_lane_branch` accepting plain-legacy (which flips `is_mission_branch` for `kitty/mission-foo-lane-a` to False, correctly). Each needs a named test.
6. **The lane-id grammar is single-letter in the regexes** (`lane-[a-z]`). Past 26 lanes, `_next_free_lane_id` yields `lane-{`. This is pre-existing; the new parsers should use `lane-[a-z]+`, or keep parity and file the gap.
7. **Remaining phantom Mission-branch composers:** `status/aggregate.py:751` and the `mission_state` rebuild without a prior manifest. Recommend follow-up issues.
8. **Second lane-creation path:** the review workspace (`workflow.py:1691`) creates lane branches outside the allocator. Its naming is compliant, but record it for a C-005 follow-up.
9. **Test churn:** about 61 call sites across 18 test files. Fixtures that compose names with an identity must move to allocator-built fixtures (FR-012), not merely have the kwarg deleted.

---

## Part B — #5113 decision materialization (python-pedro)

### Reproduced (real `create_mission_core`, COORD topology)
Coord branch `kitty/mission-<slug>` exists, `.worktrees/` is absent, and `decision open --json` fails. It exits 1 with an **uncaught** `CoordinationWorktreeUnmaterialized`, which reaches the operator as a raw traceback with no JSON. It also leaves three new files behind: `decisions/DM-<id>.md`, `decisions/index.json` and `decisions/index.json.lock`.
Prototype: calling `CoordinationWorkspace.resolve` first gives an EMPTY coord state, because the coord branch forks off `planning_branch` *before* the scaffold commit (`core/mission_creation.py:1103`) and so carries no mission dir. After that, open (lamport 3), resolve (lamport 4), list and verify all exit 0. Events append to the primary `status.events.jsonl`, next to the `MissionCreated` events, so C-006 partitions are unchanged.

### D1 — Where materialization happens (FR-013)
**Decision:** add one coordination-layer helper, `materialize_coord_surface_for_write(repo_root, mission_slug) -> None`, in `src/specify_cli/coordination/surface_resolver.py`, next to `resolve_for_write` (L695). Its body:
1. `read_primary_meta` (`missions/_read_path_resolver.py:822`), then read `coordination_branch`. If it is absent, return (flat, SINGLE_BRANCH or LANES).
2. Compute `mid8 = resolve_declared_mid8(meta, slug)` (L750) and `state = probe_coord_state(..., coordination_branch=...)` (`_read_path_resolver.py:284`).
3. If the state is not `UNMATERIALIZED`, return. MATERIALIZED and EMPTY need nothing. DELETED is left to raise downstream, as today.
4. If the branch is not a local head (`_coord_branch_is_local_head`, L610), raise `CoordinationWorktreeUnmaterialized.for_mission(...)` **before any write**. This mirrors the #4970 gate in `write_target_degrade.py:217-228`: a remote-only branch is never auto-materialized.
5. Otherwise call `CoordinationWorkspace.resolve(repo_root, slug, mid8)` (`coordination/workspace.py:250`). On `OSError | SubprocessError | CoordinationWorkspaceBranchMismatch | CoordinationWorkspaceIdentityUnresolved`, raise `CoordinationWorktreeUnmaterialized` with `from exc`. These are the same narrowed exceptions as `status_transition.py:271-283`.

The `coord_branch_has_committed_artifact` probe is **not** reused. It guards a *primary-degraded* matrix write. Here `git worktree add <existing local head>` checks out committed state as-is, so it clobbers nothing, and the state becomes MATERIALIZED with events going to the coord worktree. That is correct routing.

**Callers:** `decisions/service.py`
- `open_decision` (L418): call the helper after `_resolve_mission_id` and the `dry_run` early return (~L474-485). Then pre-resolve `events_path = _events_path(...)`. Both must run **before** `_locate_or_create_open_entry` (L509), which today creates the `.lock` sidecar and the index.
- `_terminal_command` (L643): call it after the `dry_run` return (~L673) and before `_apply_terminal_under_lock` (L680). This covers resolve, defer and cancel, which all route through `_terminal_command`.
- Pre-resolving `_events_path` turns any residual placement failure (for example DELETED) into a fail-before-write as well.

`emit.py::_mission_dir` (L79-88) stays unchanged. It re-resolves the same dir deterministically after materialization. Threading an `events_path` parameter through the public `emit_decision_*` API is rejected: that would widen the emit contract for the widen/charter/orchestrator callers without any gain.

**Import:** use a function-local import (`# noqa: PLC0415` with rationale), following the `emit.py:132` precedent. It must be local because `decisions.emit` sits on the charter cold-import path (`tests/architectural/test_cold_import_status_boundary.py`). Direction is not a problem: `decisions` and `coordination` are both inside `specify_cli`, and `test_layer_rules.py` has no intra-`specify_cli` rule for decisions.

**Rationale:** there is one canonical materializer (C-001 of commit_router, `workspace.py:250`). Putting the call in the *service* fixes every caller: the CLI, `specify_interview.py:178/322`, `plan_interview.py`, the charter interview, widen, and `orchestrator_api/commands.py:3119/3186`.

**Alternatives rejected:**
- (a) Materialize inside `emit._mission_dir`. It runs after the ledger write, so a failure still leaves a partial write.
- (b) Reuse `_materialise_coord_worktree` (`commit_router.py:714`). It is private, commit-shaped (stages files) and kind-guarded.
- (c) Reuse `status_transition._resolve_fallback_coord_worktree`. It is private and bound to `_TransactionIdentity`. Converging it onto the new helper is optional campsite work; see D6.
- (d) CLI-only fix. It would miss the interview, widen and orchestrator callers.
- (e) Fail-before-write only. SC-006 requires success.

**CLI error surface:** `cmd_open` (`cli/commands/decision.py:328-353`) and the resolve/defer/cancel verbs (~L395, 443, 494) need `except StatusReadPathNotFound` rendered as `{"error", "code": exc.error_code, "next_step"}`. Today the exception escapes as a raw traceback, which is a #8-class symptom. Add one `_handle_status_read_path_error` helper next to `_handle_action_context_error` (L197).

**Orchestrator-api:** `commands.py:626-630` already maps `StatusReadPathNotFound`. Check that `open_decision`/`resolve_decision` wrappers route through it, and **do not** add a new `DecisionErrorCode`, because it would change `upstream_contract.json`.

### D2 — Read paths (list/verify)
Not affected. Verified live on an UNMATERIALIZED coord mission: `decision list --json` gives `count 0`, exit 0, and `decision verify --json` gives `clean`, exit 0. Both read the ledger through PRIMARY (#4966 fold). They must **not** materialize, because reads stay side-effect free. No change.

### D3 — FR-014 remedy
**Decision:** make `spec-kitty doctor coordination --mission <slug> --fix` materialize a missing coord worktree, and name that command in the remedy.
- `_coordination_doctor.py:515-532` already detects exactly this state (`COORDINATION_WORKTREE_MISSING`, where the branch exists and the worktree is absent). It is mission-scoped (`--mission`, L1252) and has an error-code-scoped fixer dispatch (`_apply_coordination_fixes`, L1260).
- Add `_apply_missing_worktree_fix(findings, repo_root)`. It calls the D1 helper, or `CoordinationWorkspace.resolve` directly, using `extra["mission_slug"]` and `extra["mid8"]`. To make that work, add those keys to the finding at L525 and keep `recovery_args` (pinned by `test_doctor_coordination.py:216`).
- Change `next_step` to lead with `spec-kitty doctor coordination --mission <slug> --fix` and keep the raw `git worktree add` as a fallback.
- Update the `--fix` help (`doctor.py:1226-1235`) and the docstring for `run_coordination_health`.

Rewrite `surface_resolver.py:323-332` so it no longer promises self-materialization. It should say that `decision` and other coordination writes materialize the worktree on demand, or that you can run `spec-kitty doctor coordination --mission {mission_slug} --fix`. Keep "materializ" and avoid "flatten"; both are pinned by `tests/mission_runtime/test_coord_read_seam.py:177-178` and `test_coord_read_seam_callers.py:189/232/416`.

**Alternatives rejected:**
- Extending `doctor workspaces --fix`. It is husk-scoped with no `--mission` flag, and #2240 plus the comment at `_coordination_doctor.py:516-517` explicitly say it cannot create worktrees.
- A raw `git worktree add` only. It is not a spec-kitty command and bypasses stale-registration handling (`workspace.py:289`).
- A new top-level command. Rejected as surface creep.

**Other sites** with the same false `doctor workspaces --fix` remedy for *unmaterialized* coord:
- `runtime/next/runtime_bridge.py:2965` (pinned by `tests/runtime/test_bridge_parity.py:1772`)
- `mission_runtime/write_target_degrade.py:241`
- `implement_cores.py:703`, `implement.py:1088`, `agent/mission_record_analysis.py:148`
- `surface_resolver.py:133` (EMPTY warning)

These are campsite work: fix them only if the WP owns the tests. Otherwise file a follow-up (recommended: fold `surface_resolver.py:133`, and file a follow-up for the rest).

### D4 — Tests (red-first)
**Why the existing fixtures cannot reproduce:**
- `_coord_declared_no_worktree` (`test_decision_single_authority.py:75`) never creates the coord branch, so `probe_coord_state` gives DELETED and the error is `COORDINATION_BRANCH_DELETED`.
- `_coord_materialized` (L83) fakes coord dirs with no git, so the state is MATERIALIZED.

Neither reaches UNMATERIALIZED.

**Fixture:** reuse `_init_git_repo` and `_create_mission(repo, slug, MissionTopology.COORD)` from `tests/integration/test_placement_partition_golden_path.py:105/122`. This is the real `create_mission_core` with only `is_worktree_context` patched, and it gives exactly branch present, worktree absent. That module already imports it (L32-35). Hoist a `fresh_coord_mission` fixture into `tests/specify_cli/cli/commands/` (conftest or module-local).

New file `tests/specify_cli/cli/commands/test_decision_fresh_coord_5113.py` (markers `integration, git_repo`):
1. `test_open_materializes_and_returns_id`: the command exits 0, the payload has `decision_id`, `.worktrees/<slug>-<mid8>-coord` exists, and `decision list` contains the id.
2. `test_resolve_materializes`: open, then `git worktree remove` to get back to UNMATERIALIZED, then resolve exits 0 with status `resolved`.
3. `test_materialization_failure_is_byte_identical[open|resolve]`: a *real* failure made by writing `.worktrees` as a regular file (`resolve`'s `mkdir` raises `FileExistsError`, and the probe still reads UNMATERIALIZED). Snapshot every file byte under `kitty-specs/<slug>/` plus the file list before and after. Assert equality, including no `decisions/` dir and no `index.json.lock`, plus exit 1, a JSON `code == "COORDINATION_WORKTREE_UNMATERIALIZED"`, and no raw traceback.
4. `test_remote_only_branch_refuses_before_write`: `git update-ref refs/remotes/origin/<b>`, then `git branch -D <b>`. Assert the same byte-identity.
5. `test_remedy_command_materializes`: take the `next_step` from the error in (3). After removing the obstacle, or on a fresh mission, run `doctor coordination --mission <slug> --fix` through `CliRunner` and assert the worktree exists. Also parse the named command out of `CoordinationWorktreeUnmaterialized.next_step` so the text and the behavior cannot drift.

Unit tests for the helper go in `tests/coordination/test_surface_write_gate.py` or a new `test_materialize_coord_surface.py`, one per arm: no coord branch, MATERIALIZED, EMPTY, UNMATERIALIZED+local, remote-only, and resolve raising. Doctor fixer tests go in `tests/specify_cli/cli/commands/test_doctor_coordination.py`, using the existing `fresh_mission_repo` (L53).

### D5 — Complexity
`ruff --select C901 (max 10)` on `decisions/service.py`, `decisions/emit.py`, `decision.py`, `workspace.py`, `surface_resolver.py` and `_coordination_doctor.py` flags only `_fix_one_mission_coord_staleness` (11) and `resolve_status_surface_with_anchor` (12). Neither is touched. `open_decision` and `_terminal_command` gain one call each and stay low.

Campsite candidates:
- The duplicated `except` arms in `cmd_*`: extract the new handler once.
- `status_transition._resolve_fallback_coord_worktree` could delegate to the new helper. That is optional and should be a separate commit.

### D6 — Proposed WP
**Owned files:**
- `src/specify_cli/coordination/surface_resolver.py` (helper plus remedy text)
- `src/specify_cli/decisions/service.py`
- `src/specify_cli/cli/commands/decision.py`
- `src/specify_cli/cli/commands/_coordination_doctor.py`
- `src/specify_cli/cli/commands/doctor.py` (help)
- the new test file above, `tests/specify_cli/cli/commands/test_doctor_coordination.py`, and the new or updated `tests/coordination/test_materialize_coord_surface.py`

**Subtasks:**
- T1: red integration tests (D4 items 1-5).
- T2: the helper plus its unit tests.
- T3: wire the helper into `open_decision` and `_terminal_command`, pre-resolving events.
- T4: the structured CLI error handler.
- T5: the doctor `--fix` materialize fixer, extras and help.
- T6: the remedy text in `surface_resolver.py` L323-332 (and L133).
- T7: ruff, format, mypy, blast radius.

**Blast radius:**
```
make test-fast
.venv/bin/python -m pytest tests/specify_cli/decisions tests/specify_cli/cli/commands/test_decision_single_authority.py tests/specify_cli/cli/commands/test_decision_fresh_coord_5113.py tests/specify_cli/cli/commands/test_doctor_coordination.py tests/specify_cli/cli/commands/test_coordination_doctor.py tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py tests/specify_cli/coordination tests/coordination tests/mission_runtime/test_coord_read_seam.py tests/mission_runtime/test_coord_read_seam_callers.py tests/runtime/test_bridge_parity.py -q
.venv/bin/python -m pytest tests/architectural/test_cold_import_status_boundary.py tests/architectural/test_cli_error_surface_seam.py tests/architectural/test_no_read_side_bypass.py tests/architectural/test_layer_rules.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_legacy_terminology.py -q
ruff check <files>; ruff format --check <files>; mypy <files>
```
Also run `grep -rl "decisions.service\|open_decision\|resolve_decision" tests/`, which picks up the interview, widen and orchestrator-api tests.

### D7 — Risks
- **Concurrency:** `CoordinationWorkspace.resolve` serializes with an *in-process* `threading.Lock` only (`workspace.py:62/268`). If two CLI processes race, `git worktree add` fails in one of them. Mitigation: on failure, re-probe once; if the state is now MATERIALIZED or EMPTY, continue. Materialization runs **before** both the ledger sidecar lock (`service.py:122`) and `feature_status_lock` (`emit.py:137`), so no locks nest. It spawns git outside every critical section (NFR-001 of `emit.py`).
- **Running from primary or a lane worktree:** `repo_root` comes from `locate_project_root` (the main checkout). `git -C repo_root worktree add` is safe from either place. Dirty or untracked primary files are irrelevant, because the checkout goes to a new dir.
- **A materialized EMPTY coord makes STATUS_STATE route to primary** (`resolution.py:1990`). That is intended and matches where creation events live. Solo COORD emits no warning. LANES_WITH_COORD logs the EMPTY warning (`surface_resolver.py:1184`), which is acceptable because it is pre-existing behavior.
- **A later `spec-commit` still routes `decisions/` to coord** (the #5023 split ledger). That is out of scope under C-006; record it as residual in the PR.
- **Env gates:** there are no `SPEC_KITTY_*` gates on materialization, workspace or decisions paths.
- **Dry-run:** it must not materialize, so the helper call goes after the `dry_run` return.
- **Contracts:** do not add a `DecisionErrorCode` (orchestrator `upstream_contract.json`). If the doctor golden pins help text, update it.
