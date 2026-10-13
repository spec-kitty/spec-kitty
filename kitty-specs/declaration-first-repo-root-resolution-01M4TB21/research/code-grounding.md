---
title: 'Code-grounding: declaration-first repo_root/branch resolution entry (Increment 1)'
updated: 2026-10-13
type: explanation
mission: declaration-first-repo-root-resolution-01M4TB21
issue: 6142
adr: docs/adr/4.x/2026-10-10-1-scoped-shadow-workspace-write-boundary-layers-onto-the-partition.md
---

# Code-grounding — #6142 Increment 1

Read-only grounding pass, committed **before** spec/plan/tasks (semi-auto-delivery:
"never specify before grounding"). It records the current resolution seams, the
invariants that must survive with citations, the architectural gates/ledgers that
reference these files and how to keep each green honestly, the test seams, the open
P0 / sibling interactions, and the two discovery-squad verdicts.

Terminology (named explicitly per the ADR and CLAUDE.md footguns):
- **`primary`** = the PRIMARY partition / repository-root checkout, **never** the
  Primary Branch `main` unless stated.
- **`merge`** = lane consolidation / branch integration, **never** publish-to-origin.
- **`routing`** = branch-target routing (which branch/checkout a write lands on) +
  placement (kind + topology → surface), **never** dispatch/model/event routing.

## 1. The shape of the defect (what Increment 1 removes)

The artifact-placement seam (`src/mission_runtime/resolution.py`, `artifacts.py`) is
**already CWD-invariant**: given a `repo_root` + `mission_slug`, it derives the physical
read/write surface from the Mission's **stored declaration** (`meta.json` `target_branch`
+ topology), never from the current checkout. `resolve_action_context`
(`resolution.py:3059`) resolves `target_branch` **exactly once**, declaration-first.

The gap is strictly **upstream** of that seam: command entries **compute the
`repo_root` and/or branch they hand in from ambient location** (cwd / the invoking
worktree / the checked-out HEAD) rather than from the Mission's stored declaration.
Today the "write/read target follows the declaration, not ambient location" invariant
is held by **hand-placed "never `Path.cwd()`" assertions and a caller-contract**, not
by construction. Any *new* mutating command re-exposes the 14-issue class by default.

Increment 1 (= ADR Option C's step, subsumed as Option B's first increment):
introduce **one typed, declaration-first `repo_root`/branch resolution entry** at the
command-entry layer, route the command-entry seeds through it, and fold the invariant
in **by construction**. It does **not** build the Increment-2 capability handle, does
**not** touch lane consolidation / branch integration / rollback / approval-stamp /
blob-attribution / coordination-teardown, and does **not** change what a lane is.

## 2. Resolver inventory (the surface the entry is built ON)

### `src/specify_cli/core/paths.py`
- `locate_project_root(start=None, *, stop=None) -> Path | None` (L197). Walks up from
  `(start or Path.cwd())`, follows worktree `.git` pointers to the **main** repo,
  `.kittify` marker fallback; honors `SPECIFY_REPO_ROOT`. **cwd fallback when `start`
  is None (L254).** The function behind every `locate_project_root() or Path.cwd()`
  prologue.
- `resolve_canonical_root(cwd=None) -> Path` (L380). The single worktree-pointer parser
  (IC-04). Raises `WorkspaceRootNotFound` if no git marker. **cwd fallback (L416).**
- `get_main_repo_root(current_path) -> Path` (L451). **Explicit path, no cwd fallback.**
  Follows a worktree pointer to the main-repo root; the canonical **WRITE**-root
  re-anchor (collapse worktree→primary). This collapse is *correct* for writes
  (CWD-invariant) — it is **not** the defect.
- `get_status_read_root(start=None) -> Path` (L552). READ-path resolver (#984):
  deliberately prefers the *current worktree root*. **cwd fallback (L588); contract is
  "READ paths only".** Must stay legitimately read-only.
- `read_target_branch_from_meta(feature_dir) -> str | None` (L658). The **single
  authority** for the field-absent vs read-failure distinction on `meta.json`
  `target_branch` (fail-closed; `MissionMetaReadError` on corruption). The declaration
  reader the typed entry prefers.
- `get_feature_target_branch(repo_root, mission_slug)` (≈L859) — declaration-first
  branch reader: `read_target_branch_from_meta(...)` else `resolve_primary_branch`.

### `src/specify_cli/core/git_ops.py`
- `resolve_primary_branch(repo_root, *, current_branch=None, bias=True) -> str` (L333).
  Order: (1) `origin/HEAD`; (2) **the checked-out branch, returned verbatim when
  `bias=True`** (the "feature-branch bias" = the ambient-HEAD bias); (3) common-branch
  ladder; (4) `"main"`. `bias=False` only honors current if it is itself a common
  primary name. **The ambient-HEAD bias enters here via `get_current_branch(repo_root)`.**
- `resolve_target_branch(...)` (L393) — declaration-first adapter returning
  `BranchResolution{target,current,should_notify,action}`; **never auto-checks-out**.

### `src/mission_runtime/*` (already CWD-invariant — the model, not the target)
- `PlacementSeam` (`resolution.py:2302`) + `placement_seam(...)` (L3033): `write_target`,
  `read_dir`, `write_dir` all derive from `repo_root`+`mission_slug`(+stored topology),
  never the checkout.
- `resolve_action_context(repo_root, *, action, ...)` (L3059): CWD-invariant,
  topology-aware; `target_branch` resolved once (L3108) declaration-first; `cwd` is only
  an optional mission-slug discovery hint, not a branch/root authority.
- `artifacts.py`: `MissionArtifactKind`, `kind_is_coordination_residue`,
  `routes_through_coordination` (actually in `context.py:174`).

## 3. Invariants that MUST survive (with citations)

1. **Enforced module chain** `kernel <- charter <- {glossary, runtime, mission_runtime}
   <- specify_cli` (`tests/architectural/test_layer_rules.py`, `conftest.py` landscape
   fixture L90–117; `test_pyproject_shape.py`). ⇒ the typed entry **must live in
   `specify_cli`** (it depends on `core.paths` / `core.git_ops`); it may import
   `mission_runtime`, never the reverse. The Increment-2 handle (a `mission_runtime`
   `WriteLocation` dual) is explicitly deferred.
2. **#3128 Seam-B fail-closed** `enforce_checkout_identity`
   (`src/mission_runtime/checkout_identity.py:121`) + its single supplier
   `resolve_workspace_for_wp(..., write_intent=True, current_cwd=...)`
   (`workspace/context.py:776,835`). Pure path comparison, raises `CheckoutIdentityError`
   (NOT an `ActionContextError`). **Preserve verbatim** — negative tests prove it still
   refuses a foreign-lane WP write.
3. **#3328 Seam-A fail-closed** `resolve_checkout_identity(cwd, intent)` /
   `FailClosedRefusal` (`src/specify_cli/core/checkout_identity.py:177`). Worktree
   WRITE invocation fails closed (the #2320/#3328 anchor). **Preserve** — negative test.
4. **Consolidation correctness surface** — approval-stamp bound, blob-attribution /
   closed-world, CAS ref advance, coordination-teardown CAS, single rollback authority.
   **Not touched** (ADR non-goal). No merge-target / branch-integration resolution is in
   scope (this excludes `mission_accept_merge.py`'s `resolve_primary_branch` merge-target
   derivation — see §6).
5. **`get_status_read_root` stays read-only** (ADR Negative consequence): the entry must
   not collapse a legitimate read to primary.

## 4. Architectural gates & shrink-only ledgers that reference these files

Keep each green **honestly** (re-point / extend, never loosen):

- **`test_no_write_side_rederivation.py`** (2062 lines; the FR-005 shrink-only ratchet).
  Flags write-side re-derivation grammars — `get_current_branch(...) or <fallback>`,
  `coord_branch or _current_branch`, `.parent.parent` root-walks, `mission_id[:8]`,
  and AST `CommitTarget(ref=<checkout-derived>)` / `safe_commit(destination_ref=...)`.
  Allowlists are **content-descriptor keyed and shrink-only**; each entry carries a
  rationale + tracker ref. `BOUNDARY_SANCTIONED_PREFIXES = ("src/mission_runtime/",
  "src/specify_cli/upgrade/migrations/")`. **How to stay green:** the new entry resolves
  *branch strings* (no `CommitTarget`/`safe_commit`), so the AST grammar never fires; it
  must **not** introduce a `get_current_branch(...) or ...` / `coord_branch or current`
  grammar — it routes through the existing public resolvers
  (`resolve_canonical_root`/`get_main_repo_root`/`get_feature_target_branch`/
  `read_target_branch_from_meta`), which is exactly the fix this ratchet prescribes.
  The `implement_claim.py:81` `get_current_branch(repo_root) or fallback_branch` selector
  is a **#2453-deferred allowlisted entry** with an explicit "routing it would change the
  guard's branch (a behavior change)" note ⇒ **out of Increment-1 scope** (do not touch;
  it would collide with the ledger).
- **`test_layer_rules.py` / `test_pyproject_shape.py`** — module chain + package set.
  The new module is a plain `specify_cli` module; no package-set change. Keep green by
  placing it correctly (§3.1).
- **`test_lifted_cli_project_root_resolution.py`** — always-on gate on
  `cli/helpers.py::get_project_root_or_exit` (worktree-resolving, fail-closed on git
  error). The repo-root half of the typed entry should compose with / extend this
  existing CLI entry resolver, keeping its worktree-resolution + fail-closed contract.
- **`test_no_dead_symbols.py` / `test_no_dead_modules.py`** (+ `__all__` convention for
  `src/charter` & `src/kernel`, charter C-007) — any new public symbol needs a real
  caller in `src/`. Keep green by routing real call sites to the entry in the same WP.
- **`test_workspace_resolution_doc.py`** — workspace-resolution doc must track behavior.
- **`test_guard_capability_call_sites.py`** — #3128 capability call-sites; untouched but
  verify the negative-test surface still holds.
- Terminology gate **`test_no_legacy_terminology.py`** (≈0.1 s) — run pre-push (prose).

No gate needs loosening for Increment 1; the typed entry *is* the constructed boundary
the ADR's "Confirmation" clause and Standing Order #5 ask for.

## 5. Current test seams and their cost

- Entry/branch resolution unit seams: `tests/specify_cli/cli/test_helpers.py`,
  `tests/specify_cli/core/` (paths/git_ops), `tests/cli/`, `tests/status/`. Fast.
- `resolve_workspace_for_wp` / `enforce_checkout_identity` seam:
  `tests/specify_cli/workspace/` + `tests/mission_runtime/` — the #3128 negative tests.
  `current_cwd` is injectable (context.py:836), so a foreign-lane refusal is unit-cheap.
- The typed entry's own branches (declaration present / absent→validated fallback /
  corrupt meta fail-closed / worktree collapse / ambient-disagrees→declaration-wins) are
  pure and cheap to unit-test with `tmp_path` git fixtures (mirror
  `test_lifted_cli_project_root_resolution.py`'s fixture shape).
- Calibrated blast radius (CLAUDE.md + NO_FULL_HEAVY_SUITES_IN_MISSION): `make
  test-fast` + the touched modules' test files + each owning subsystem's dir + the
  **specific** named gate files (`test_no_write_side_rederivation.py`,
  `test_layer_rules.py`, `test_pyproject_shape.py`,
  `test_lifted_cli_project_root_resolution.py`). Never the bare `tests/architectural/`.

## 6. Discovery-squad verdicts (folded into scope)

### Similar-surfaces squad (every ambient `repo_root`/branch seed)
The placement seam is already CWD-invariant; the defect is the *seed* fed into
mission-scoped commands. Dispositions:

- **in-scope-now** (mission-scoped root/branch target seeded from ambient location, safe
  to route): the `locate_project_root() or Path.cwd()` mission-scoped prologues —
  `cli/commands/decision.py` (×4), `agent/issue_verdict.py:362`, `verify.py` (×2),
  `context.py:96`; and the `specify_cli/mission.py` facade seeds + `agent_tasks_ports.py:448`
  (verify-then-route). These are where a declaration-first `(repo_root, target_branch)`
  should supersede the ambient seed.
- **file-and-link → Increment 2 / #2453 sweep**: `implement_claim.py:81`
  (`get_current_branch or fallback`, a protected-branch *guard* prediction — routing it is
  a behavior change on the guard, explicitly deferred by the ratchet allowlist).
- **file-and-link → consolidation non-goal**: `mission_accept_merge.py:191/361`
  (`resolve_primary_branch` **merge-target** derivation — branch-integration sense, ADR
  non-goal), `safe_commit_cmd.py:417` (generic commit-branch inference).
- **not a defect (file-and-link / leave)**: cwd captured as **honest invocation
  identity** fed to the ownership / `resolve_checkout_identity` / `enforce_checkout_identity`
  seams (C.3 — this is the intended input, not a seed); **create-time** seeds
  (`mission_create.py`, `mission_creation_*` — the declaration is being *minted*, so the
  current branch is a legitimate create-time input); **project-scoped** commands with no
  single mission (`lint`, `glossary`, `tracker`, `mission_type`, `charter*`, `init`,
  `upgrade`, `ops`, `retrospect`, `session_start`) where cwd is the correct anchor;
  **hosted-frozen** surfaces (`zeitgeist`, `routes`, `live_work`).

### "never `Path.cwd()`" assertion inventory (folded into the entry by construction)
Hand-placed guards defending this invariant today (file:line | guards):
`coordination/transaction.py:807–820` (the caller-contract — primary ADR citation),
`status/emit.py:1231`, `agent/tasks_mark_status.py:377`, `agent/tasks_map_requirements.py:574`,
`agent/tasks_move_task_executor.py:401,429`, `agent/tasks.py:1194`,
`agent/mission_setup_plan.py:378,1361`, `agent/mission_finalize.py:625`,
`agent/mission_finalize_branch_contract.py:189`, `orchestrator_api/wp_lifecycle.py:917`,
`migration/backfill_runtime_state.py:1117,1274,1886`,
`migration/runtime_state_cutover.py:19,263,298,547`,
`upgrade/migrations/m_zz_runtime_state_backfill.py:26`, `decisions/ownership.py:7`,
`acceptance/execution_context.py:14,142`, `mission_runtime/context.py:240`,
`mission_runtime/resolution.py:325,1415`, `mission_runtime/lifecycle_phase.py:250,253`,
`core/stale_detection.py:92`. Increment 1 makes the typed entry the **single
construction point** of the invariant; routed sites replace the hand comment with the
typed call. Un-routed sites keep their guard and are referenced by the follow-up issue.

### Tracked-issues squad (the 14-issue cluster + newer siblings)
- #6142 OPEN, parent spike **#3129 OPEN (stays open)** — Refs, not Closes.
- **All 14 cluster issues are CLOSED** by point-fixes (the premise of #6142: symptoms
  patched per-site, invariant still by-hand). Referenced as the class the entry now holds
  by construction: **#3124, #3051, #3049, #2613, #2702** (ambient `repo_root`/branch at
  command entry) + **#3128** (the fail-closed assertion folded in / preserved).
- **Two still-OPEN newer siblings the entry forecloses → Refs: #2802** (legacy-topology
  finalize-tasks resolves commit destination from process CWD instead of resolved
  repo_root) and **#5114** (mission-create vs branch-context use different
  primary-branch resolvers — the `resolve_primary_branch` dual-resolver split). Refs, not
  Closes (the full per-issue migration may exceed Increment 1; operator decides at merge).
- Out of Increment-1 Refs (non-goals, all closed): #2549 (Inc-2 write-handle), #2367,
  #2797, #2274, #2570, #2745, #1914 (consolidation / guard-comparison / self-write).

## 7. Open P0 / sibling-run interactions

- No open P0 touches these resolution seams (the 14 cluster point-fixes are merged). The
  baseline-red gotcha (CLAUDE.md) applies to any broad local run: classify category 1–4
  before attributing a red.
- **Sibling point-fix caution (per the brief):** a sibling run may be in flight on the
  same class (e.g. "owned-Mission research redirects into dirty primary", #5882). This
  mission introduces the entry and routes a *bounded, named* set; it does **not** touch
  the owned-authoring / research-redirect path. Coordinate, do not collide — if a routed
  site overlaps a sibling, file-and-link rather than widen.

## 8. 90-day churn / fix history

The cloud checkout is shallow (per-file local history is truncated), so churn is read
from the **issue history**: this class recurred across structurally unrelated command
families over multiple quarters (#3051 called itself "the third confirmed command family
hitting this exact mechanism"), producing 13 merged point-fixes downstream of the clean
seam (ADR §1). That recurrence *is* the churn signal, and it is the ADR's evidence that
the supply (one shared object store + ambient seed) is not exhausting — the motivation
for a constructed boundary over a fourteenth per-site patch.
