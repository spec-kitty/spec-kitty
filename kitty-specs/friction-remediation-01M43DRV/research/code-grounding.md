# Code grounding — friction-remediation-01M43DRV

Read-only grounding run, 2026-10-04, against `origin/main` @ `7c2dbd4e`.
It re-verifies the prior squad's findings for #5552, #5298, #5653, #5654 and #5186.
Line numbers are as of that commit.

Audience: the implementer and reviewer of this Mission (software-engineer persona).

## 0. Sequencing status at grounding time

| PR | State | Touches |
|----|-------|---------|
| #5650 (consolidation executor decomposition, `ConsolidateOptions`) | open, not merged | `cli/commands/consolidate.py` (~100 lines), one line each in `bookkeeping_projection.py` and `acceptance/gates_core.py` |
| #5656 (regression-slice test cleanup) | open, not merged | adds `tests/_support/eacces.py` (`deny_open_in`, `deny_path_method`); edits `test_canceled_attestation.py` and `test_provision_kitty_env.py` |

Outcome: WP01 (#5552) and WP02 (#5298) proceed. WP03 (#5653) and WP04 (#5654 + #5186) wait on these PRs. The check is repeated before WP03/WP04 would start (Decision Moment `01M43DSJXP334BFKRQFAVMH22J`).

The 90-day churn is from `git log --since=90.days --oneline -- <file> | wc -l` (the clone was unshallowed first):

| File | Commits / 90 d |
|------|----------------|
| `src/mission_runtime/artifacts.py` | 12 |
| `src/specify_cli/consolidation/bookkeeping_projection.py` | 2 |
| `src/specify_cli/acceptance/summary_core.py` | 10 |
| `src/specify_cli/validators/paths.py` | 3 |
| `src/specify_cli/core/paths.py` | 26 |
| `src/specify_cli/acceptance/__init__.py` | 42 |
| `src/specify_cli/mission_metadata.py` | 19 |
| `packs/built-in/missions/software-dev/mission.yaml` | 3 |

`core/paths.py` and `acceptance/__init__.py` are hot. WP02 therefore adds one helper to `core/paths.py` and leaves `acceptance/__init__.py` untouched.

## 1. #5552 — squash consolidate false-REFUSE (WP01)

### Responsibility map

- **`src/mission_runtime/artifacts.py`**: the ONE file→kind classifier (`kind_for_mission_file` :431 → `_artifact_kind_for_path` :466), plus the partition sets:
  - `_PRIMARY_ARTIFACT_KINDS` (:164);
  - `_PLACEMENT_ARTIFACT_KINDS` (:207, the COORD partition);
  - the basename map `_MISSION_FILE_KIND_BY_BASENAME` (:240);
  - the first-segment directory map `_COORD_RESIDUE_DIRS` (:289). Despite its name, it already holds PRIMARY kinds: `tasks`, `checklists`, `decisions`.
- **`src/specify_cli/consolidation/bookkeeping_projection.py::_post_checkpoint_mission_paths`** (:407): a denylist. It projects every changed mission path EXCEPT the status byte-sets, `meta.json`, any kind that is known and PRIMARY, and the two gate matrices. `None` stays projected.
- **`_projected_path_content_matches`** (:541): the squash proof. For a projected path whose target diverged from the checkpoint, with no registered driver, it fails closed and the gate REFUSEs.

### Root cause (re-verified)

`kind_for_mission_file("kitty-specs/<m>/quickstart.md")` and `…/contracts/x.md` return `None`. They stay in the projected set, so the proof REFUSEs on planning content that is byte-identical (or absent on the coordination ref, per the 4.0.0rc6 recurrence comment).

### Fix shape

- Add `"quickstart.md": CHECKLIST` to the basename map. This matches the existing explicit choice in `acceptance/__init__.py::_accept_planning_artifact_kinds` (:1189-1199), which already classifies quickstart as `CHECKLIST`, so it is one classification, not two.
- Add a new PRIMARY kind `CONTRACT` mapped by the directory entry `"contracts"`, and list it in `_PRIMARY_ARTIFACT_KINDS`.
- Add `CONTRACT` to `coordination/commit_router.py::_PRE_TASKS_ARTIFACT_KINDS` (:173). Contracts are `/spec-kitty.plan` output, so the protected-branch refusal must not recommend `finalize-tasks --target-branch` for them.

### Caller impact (every `kind_for_mission_file` caller; survey by a read-only sub-agent)

| Site | Before (None) | After (PRIMARY) | Change |
|------|---------------|-----------------|--------|
| `bookkeeping_projection.py:466` | projected | excluded | the fix |
| `cli/commands/agent/workflow.py:412` `_partition_paths_by_primary_kind` | coord_bound (committed via the coordination worktree) | primary_bound | doctrinal fix; planning artifacts never transit coordination |
| `safe_commit_cmd.py:252` `_mission_file_kind` | HEAD-branch fallback (deprecation warning) | mission-aware target via `resolve_placement_only` | aligns with `spec.md`; can surface the same protected-branch refusals spec.md already gets |
| `mission_finalize.py:3183` `_planning_changed_since_pin` | ignored | counts as planning change | intended (more accurate refresh trigger); file not edited (C-003) |
| `consolidation/planning_recency.py:75` | excluded | included in #3942 recency restore | intended |
| `runtime/next/runtime_bridge_io.py:1311` | caller dir | `seam.read_dir(kind)` (primary dir) | same as research.md / data-model.md |
| `lanes/auto_rebase.py:225`, `missions/_create.py:185`, `coordination/coherence.py:251,275`, `coord_seed.py:238`, `commit_router.py:770,926,1393,1539`, `acceptance/__init__.py:204`, `acceptance/ledger_dirt.py:41` | — | — | no observable change (kind-specific checks for other kinds, or residue = `_PLACEMENT_ARTIFACT_KINDS` only) |

Residual risk:
- A legacy Mission that committed `quickstart.md` or `contracts/**` ONLY on the coordination ref after the checkpoint is no longer projected.
- The squash itself carries the mission-branch content, so the planning file still reaches the target whenever it is on the mission branch, which is the normal path.
- This is recorded, not mitigated.

### Write placement

Unknown kinds already fall back to PRIMARY placement, so routing through the seam does not change; the placement-guard tests prove it. `artifact_home_for(CONTRACT)` resolves PRIMARY.

### Gates referencing these files

- **`tests/architectural/test_write_surface_placement_guard.py:333-368`**: hard-codes `primary_kinds` and asserts they cover the enum (:367). Re-point it by adding `CONTRACT`; never loosen it.
- **`tests/architectural/test_merge_reconciliation_class_guard.py`**:
  - `_NON_DIVERGENT_CANONICAL_ARTIFACTS` (:215): add `quickstart.md`. It is single-writer human planning source, like `spec.md` and `research.md`.
  - `_NON_DIVERGENT_COORD_RESIDUE_DIRS` (:316): add `contracts`. The `divergent_dirs == {"traces"}` assertion stays as it is.
- **`tests/architectural/test_exemption_registry_ratchet.py:81-83`**: lists both modules in its scan scope. No allowlist edit is expected; run it.
- **`tests/architectural/test_trio_seam_only.py`**: references the classifier as a bypass target. No edit; run it.
- **`assert_partition_invariant`** (`artifacts.py:353`): runtime P-1 guard. Satisfied by the partition-set membership.

### Test seams and cost

- Pure classifier tests (`tests/mission_runtime/test_artifact_partition*.py`): milliseconds.
- `_post_checkpoint_mission_paths`: needs a real git repo with checkpoint and coordination commits; about 1 s.
- Full squash replay (`tests/terminus/test_repro_5038.py`): end-to-end, tens of seconds.

The red-first test uses the `_post_checkpoint_mission_paths` git seam, which is cheap and goes through the pre-existing entry point.

## 2. #5298 — accept blocks on missing `contracts/` (WP02)

### Responsibility map

- **`packs/built-in/missions/software-dev/mission.yaml`**: `artifacts.optional` lists `contracts/` (:28), while `paths.deliverables: "contracts/"` (:37) makes it a path convention.
- **`src/specify_cli/acceptance/summary_core.py::evaluate_path_conventions`** (:182): the only caller of `validators/paths.py::validate_mission_paths` (:229). It decides blocking (strict) vs warning (lenient), and returns dedup tokens so `contracts` is not double-reported (`test_accept_contracts_dedup.py`).
- **`acceptance/__init__.py:1523`**: caller. It passes `planning_read_dir`, the PRIMARY mission dir where `meta.json` lives.
- **`core/paths.py::read_retention_from_meta`** (:688): the field-level reader to mirror. It is a thin adapter over `load_meta_fail_closed`, which raises `MissionMetaReadError` on corrupt meta.

### Fix shape (operator-ruled)

- `meta.json` carries `"contracts": "none"` plus a non-empty string `contracts_rationale`.
- One helper in `core/paths.py` returns a typed verdict: waived, rationale, warning. It fails closed: an unknown value, a non-string value, or a missing or blank rationale keeps the requirement and warns.
- `evaluate_path_conventions` passes the waived artifact token down to `validate_mission_paths` (a new keyword, defaulting to empty), which skips that declared artifact path. The waiver applies at or below the single caller, so constraint C-002 holds.
- The rationale is surfaced as a warning so the waiver stays auditable in the accept output.
- No spec- or plan-frontmatter source (C-001).

### Invariants to keep

- The FR-002/FR-003 dedup behaviour (`test_accept_contracts_dedup.py`).
- #1892 lenient semantics.
- #3085a resolved-path reporting.
- #4254 candidate source roots.
- Fail-closed meta reads (`load_meta_fail_closed` contract).

### Gates

- **`tests/architectural/test_lifted_root_validate_mission_paths_single_caller.py`** and **`tests/specify_cli/test_validate_mission_paths_single_caller.py`**: set-equality on callers. Unchanged, because no new caller is added.
- **`tests/architectural/_load_meta_census.py`**: the new reader routes through `load_meta_fail_closed`, so no census row is needed.
- **`tests/architectural/test_no_dead_symbols.py`**: the new helper has a production caller in `summary_core.py`.

### Docs

- `MissionMetaOptional` in `mission_metadata.py` gains the two fields.
- A new ADR. The charter's Charter Resolution Hints say new ADRs land in `docs/adr/4.x/`; the brief said `3.x`. The charter wins, and the PR flags this.

## 3. #5653 — dry-run attestation notice (WP03, sequenced)

The notice is an inline `if dry_run:` block in `cli/commands/consolidate.py::consolidate()`. #5650 rewrites that function into `run_consolidate(options)`, so extracting the notice now would collide with it. Deferred until #5650 merges.

## 4. #5654 + #5186 (WP04, sequenced)

The fix uses the `tests/_support/eacces.py` helpers that #5656 adds, and edits `test_provision_kitty_env.py`, which #5656 also edits. Deferred until #5656 merges; not duplicated here.

## 5. Interactions

- **charter-test-cwd-isolation mission (#5317, #5601)**: no file overlap. Running from the repository root checkout (single_branch topology, no lane worktree) avoids its known environmental reds.
- **`mission_finalize.py` split (running session)**: not edited. The `_planning_changed_since_pin` behaviour change comes through the classifier only.
