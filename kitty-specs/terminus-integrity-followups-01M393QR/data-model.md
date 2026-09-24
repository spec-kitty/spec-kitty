# Phase 1 Data Model — Terminus Integrity Follow-ups

The mission changes three data structures. All changes are **additive** (new fields default to a safe/absent value), so a `MergeState` or claim written by pre-mission code loads without migration, and the fail-closed guards treat "absent" conservatively.

## 1. `ApprovedWpCommitSet` (reconciliation claim) — `merge/reconciliation.py`

The approved-WP content authority the gate verifies the target tree against.

| Field | Type | New? | Meaning / Invariant |
|-------|------|------|---------------------|
| (existing) `approved_shas`, `excluded_shas`, `excluded_window_base`, `enforce_closed_world`, `verify_reachability` | — | no | unchanged |
| `authored_blobs` | `frozenset[tuple[str, str]]` — `(path, blob_sha)` | **yes** | The **FINAL** first-parent-authored blob **per (lane, path)** across approved lanes (post-plan F5 — the union of *all* first-parent commits would admit superseded intermediate blobs and let a canceled blob matching a discarded `v1` PASS; taking the final blob per (lane,path) closes that false-PASS and is what makes the 3-way deferral sound). Content identity, not commit SHA ⇒ squash-sound. Populated in `build_approved_wp_set` via `_collect_authored`. **Fail-closed:** empty `authored_blobs` while `approved` is non-empty ⇒ REFUSE (the hoisted vacuous-manifest check inspects only `approved`, so the squash branch must add this explicit REFUSE, not fall through to an empty-loop PASS — post-plan F1 corollary). Always the `(path, blob)` tuple, never blob-only (F10: catches identical-content-different-path). |

**Derived predicate** (`_unattributable_content_squash`, post-plan F1): iterate `git diff --name-status B..T` (`--no-renames`, F6, to match `_collect_authored`'s `changed_paths_of`); for each **Added/Modified** path `P` (skip Deleted — nothing shipped), let `b = blob_id_at(T, P)`. An unexpected empty `b` for an A/M path is a probe error ⇒ **REFUSE** (never infer "deleted" from a `rev-parse` failure — F1). If `(P, b) not in authored_blobs` ⇒ `P` unattributable ⇒ FAIL naming `P`. Bookkeeping paths are excluded via the existing `_is_bookkeeping_path` (product code lives under `src/`, never `kitty-specs/<slug>/`).

## 2. `MergeState` — `merge/state.py`

Persisted resume state at `.kittify/merge-state.json`. A resumed merge must reconstruct the true pre-mutation window from persisted values, never re-derive them live.

| Field | Type | New? | Meaning / Invariant |
|-------|------|------|---------------------|
| (existing) `feature_slug`, `target_branch`, `wp_order`, `completed_wps`, `current_wp`, `has_pending_conflicts`, `strategy`, `pre_mutation_target_sha`, timestamps | — | no | `strategy` exists but is currently **dead** (never written with the operator's choice, never read on resume). `pre_mutation_target_sha` (persisted since #5012) is the target window base. |
| `strategy` (behavior change, not a new field) | `str` | field exists; **write+read are new** | Persisted as the **resolved strategy attempt-1 actually executes** via a WP05 **executor reseed** (post-plan A: NOT `resolve.py`, whose sole caller is the executor and takes no strategy kwarg; F14: it must equal the value attempt-1 ran, given the executor default is SQUASH). On resume, read back (in `cli/commands/merge.py`) with precedence **explicit `--strategy` > persisted > config > SQUASH**. An explicit `--strategy` that **contradicts** the persisted value ⇒ REFUSE (H1). |
| `pre_mutation_coord_sha` | `str \| None` | **yes** | The coordination ref tip captured **before the first mutation of the interrupted run** (symmetric to `pre_mutation_target_sha`). **Read-persisted-first** (post-plan F3/F9): resolve by mirroring `_resolve_pre_mutation_target_sha` (`if persisted: return; else capture+save once`) so a resume never overwrites the anchor with attempt-1's post-consolidation state; and the reconciliation claim must consume this persisted value at the `coord_base` **consumption site**, not the live `_capture_coord_checkpoint`. `None` on resume when it should exist ⇒ REFUSE (H4). |
| `pre_mutation_coord_ref` | `str \| None` | **yes** | The coordination ref name for the above SHA. |
| `pre_interrupt_lane_tips` | `dict[str, str]` — `lane_id → tip_sha` | **yes** | Per-lane branch tip captured (read-persisted-first, as above) before the interrupted run's consolidation. Resume judges reachability against these, preserving pre-interrupt approved commits (#4982/#4997). On resume each persisted tip is a **CAS expectation compared as a git OBJECT** (post-plan D/F8): the live state must be the persisted commit **or a descendant of it**, and — critically — a live tip that is a **strict ancestor** (behind-HEAD) is the exact #4982 window and must **NOT** REFUSE; the branch ref itself may be **gone** (the lane was already consolidated) so the guard checks object reachability, never branch-ref existence. REFUSE only on true divergence (persisted commit not an ancestor of, equal to, or descendant of the live state). |

**Load/compat:** all new fields default (`None` / empty dict), so a legacy `MergeState` deserializes cleanly; absent coord base / lane tips on a resume that requires them ⇒ REFUSE (never silently proceed).

## 3. Coordination write-gate predicate — `mission_runtime/write_target_degrade.py`

No new persisted structure; a refinement of the in-memory self-materialization decision.

| Decision input | Type | New? | Meaning |
|----------------|------|------|---------|
| `state` (`CoordState.UNMATERIALIZED`) | enum | no | filesystem materialization signal |
| local-head branch | bool (`_coord_branch_is_local_head`) | no | branch is a local head ref |
| **committed-artifact-present** | bool (new probe `coordination.surface_resolver`) | **yes** | Detect committed matrix content on `<coord_branch>` for the mission. **Path must derive from the same placement authority that produced `resolved.ref`, or `git ls-tree <coord_branch>:kitty-specs/<slug>/` the whole subtree** (post-plan F2): a hardcoded `kitty-specs/<slug>/issue-matrix.{json,md}` prefix reads a **path-drifted** committed matrix as a clean exit-1 "absent" ⇒ ALLOWs self-materialization ⇒ clobbers. True if any committed matrix artifact is found. Unreadable git (not path-absent) ⇒ treated as **present** (fail-closed). |

**Self-materialization window (new definition):** `UNMATERIALIZED AND local-head AND NOT committed-artifact-present`. Anything else with a coord-routed write ⇒ REFUSE (existing raise + remediation). A genuine first-write (no committed content) still passes (NFR-003 no false-refusal). **F11 (deferred-with-record):** the plan chose *file/tree existence* over paula's row-emptiness check; WP02 must run the `tests/coordination + status + cli + issue_matrix` blast-radius and, if any legitimate flow commits an empty-rows matrix to the coord branch as a first-write, switch to the row-level check (`scaffold_issue_matrix` targets the PRIMARY dir, so this is expected LOW — but the check is recorded, not assumed).

## Entity relationships

```
merge --resume ──reads──▶ MergeState ──anchors──▶ reconciliation claim (ApprovedWpCommitSet)
                              │                          │
              (strategy, pre_mutation_coord_*,           │ authored_blobs
               pre_interrupt_lane_tips)                  ▼
                                              MergeOutcomeVerifier.verify (fail-closed)
                                                         │  FAIL ⇒ CAS rollback ⇒ exit 1
issue-verdict ──resolve_for_write──▶ coordination write gate (assert_coord_write_materialized)
                                                         │  stale-head+committed ⇒ REFUSE
```
