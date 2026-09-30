---
title: 3.2.3 Architectural Investigation — Alphonso (SSOT / topology-alignment verdict)
description: Architect Alphonso's SSOT/topology-alignment verdict on the 3.2.3 surface-resolution regressions, read-only on the fix branch under the architectural-integrity directive.
doc_status: deprecated
updated: '2026-06-26'
---
# 3.2.3 Architectural Investigation — Alphonso (SSOT / topology-alignment verdict)

Branch `fix/3.2.3-coord-surface-regressions` @ `775ec32da`. Read-only.

**Directives applied** (architect-alphonso): DIRECTIVE_001 (Architectural Integrity —
component-boundary reasoning per ticket), DIRECTIVE_003 (Decision Documentation — ADR-need
verdict for the terminal-artifact home), DIRECTIVE_031 (Context-Aware Design — read-surface
vs write/teardown-surface bounded contexts), DIRECTIVE_032 (Conceptual Alignment — "handle"
vs "slug" vs "topology" vocabulary confirmed against the SSOT), DIRECTIVE_041 (Tests as
Scaffold — the existing `..._for_mid8_handle` red-first guard is the contract, not friction).

---

## The established SSOT (recap, from #2106/#2113/#2070)

- **Read surface**: `resolve_handle_to_read_path` (THE guarded read seam) — absorbs handle →
  concrete `MissionTopology` via `classify_from_meta`, threads `routes_through_coordination`
  down the existence-gated `_resolve_mission_read_path`.
  (`src/specify_cli/missions/_read_path_resolver.py:843`)
- **Kind partition**: `resolve_planning_read_dir(repo_root, slug, kind=…)` splits PRIMARY-vs-
  STATUS by `mission_runtime.is_primary_artifact_kind`. PRIMARY kinds → topology-blind
  `primary_feature_dir_for_mission`; STATUS kinds → topology-aware seam.
  (`_read_path_resolver.py:1244`)
- **Handle→slug disambiguation**: `_canonicalize_handle` / `resolve_mission` (mid8/ULID/
  numeric → canonical slug, no-silent-fallback). (`_read_path_resolver.py:467`)
- **Primary write/identity anchor**: `primary_feature_dir_for_mission` — topology-BLIND, but
  **also handle-BLIND**: it does `get_main_repo_root(repo_root)/KITTY_SPECS_DIR/<slug>`
  literally with only `assert_safe_path_segment`. It does NOT resolve a handle.
  (`_read_path_resolver.py:1212`)

The load-bearing seam fact for this cluster: **`resolve_planning_read_dir` is kind-aware and
topology-aware but is NOT handle-aware** — it forwards `mission_slug` verbatim into
`primary_feature_dir_for_mission`, which joins it literally.

---

## Per-ticket verdict

### #2122 — accept-gate mid8-handle read — **Y / pure-adoption** (read seam, missed handle step)

**Seam:** the two accept sites pass a raw `--mission` handle (possibly a mid8) straight into
`resolve_planning_read_dir(repo_root, feature, kind=…)`:
- `src/specify_cli/acceptance/__init__.py:406` `_iter_work_packages` → `_wp_tasks_read_dir` →
  `resolve_planning_read_dir(..., WORK_PACKAGE_TASK)` → `primary_feature_dir_for_mission`
  joins `kitty-specs/<mid8>/tasks` **literally** → `AcceptanceError: no tasks directory`.
- `src/specify_cli/acceptance/__init__.py:~823` `normalize_feature_encoding` → same
  `resolve_planning_read_dir(repo_root, feature, kind=spec)` pattern.

This is **pure SSOT adoption, not an authority gap.** The #2113 fix correctly moved to the
kind-aware partition but `resolve_planning_read_dir` → `primary_feature_dir_for_mission` is
handle-BLIND by design (`_read_path_resolver.py:1212-1241`, only `assert_safe_path_segment`).
The fix is to resolve the handle → canonical slug BEFORE the kind-aware read, i.e. consume the
EXISTING `_canonicalize_handle` / `resolve_mission` seam (which `resolve_feature_dir_for_mission`
already wrapped pre-#2113) and pass the canonical slug to `resolve_planning_read_dir`. No new
authority. **Audit obligation:** sweep every `resolve_planning_read_dir(... raw_handle ...)` call
site — the bug is structural to that primitive's handle-blindness, so any other gate-read that
forwards a `--mission` handle has the same latent defect.

**Design note (optional hardening, defer):** the cleanest long-term shape is to make
`resolve_planning_read_dir` itself handle-aware (canonicalize once at the seam), so callers
cannot forget the step. That is a seam-contract change touching all callers — out of scope for a
patch; the patch is the per-site canonicalize. File a follow-up.

---

### #2120 — `close --discard` teardown no-op — **Y / pure-adoption** (wrong-surface resolver pick)

**Seam:** `close_cmd` resolves the discard target via the WRONG read seam.
- `src/specify_cli/cli/commands/mission_type.py:595` →
  `resolve_feature_dir_for_mission(repo_root, mission_slug)` which routes through the **`tasks`-
  action** `resolve_action_context` (`_read_path_resolver.py:1393-1415`) → returns the
  **coord** status-only dir (no `meta.json`) when the coord worktree is materialized.
- `:610` `_read_mission_mid8(meta_path)` reads `coord/.../meta.json` → absent → returns `""`.
- `:716-718` `_teardown_coordination_worktree` early-returns on `if not mid8_value:` → no-op,
  yet `:627` prints `✓ discarded`.
- Contrast `reopen` (`:973`) → `_resolve_mission_handle` (`:860`) →
  `primary_feature_dir_for_mission` → PRIMARY dir WITH `meta.json`. The two commands resolve the
  same mission to different surfaces — an internal resolution asymmetry, exactly the SSOT
  divergence #2070 set out to kill.

This is **pure SSOT adoption**: the teardown path is a WRITE/identity operation and must anchor
on the PRIMARY identity surface (`primary_feature_dir_for_mission` / `resolve_mission`), the same
authority `reopen` already uses. No new authority needed. Sub-fixes B (tear down worktree BEFORE
`git branch -D` the checked-out coord branch — ordering bug at `:658`/`:691-705` vs `:624`) and C
(non-zero exit / no `✓` when teardown incomplete — `:716-737` swallows all failures, `:627`
prints success unconditionally) are local correctness, NOT authority questions — but they are
real defects in the SAME command and must ship together.

---

### #2119 — retrospectives trapped on coord branch — **Y / needs-new-authority** (write/teardown surface gap)

**Seam(s):**
- `canonical_record_path` (`src/specify_cli/retrospective/writer.py:36-49`) resolves the retro
  home via `resolve_feature_dir_for_slug` → topology-AWARE → for a coord mission returns the
  **coord worktree** `feature_dir`, then joins `/ "retrospective.yaml"`. So the retro is written
  INTO the ephemeral coord worktree on `kitty/mission-<slug>`.
- The durable path the `spec-kitty-mission-review` skill tells operators to verify —
  `.kittify/missions/<mission_id>/retrospective.yaml` — is **never written**. (`writer.py:56`
  comment references a `.kittify/missions/<id>/…` gitignored path, but the CANONICAL write goes
  to `feature_dir`.) `post_merge/retrospective_terminus.py:71` likewise checks
  `feature_dir/"retrospective.yaml"`.
- Teardown-vs-retro conflict: `merge` tears down the coord worktree/branch that HOLDS the only
  retro copy → undeletable branch OR destroyed retro.
- `retrospect create` hard-fails on a flattened/torn-down topology via `CoordinationBranchDeleted`
  and the message points at a NON-EXISTENT command: `spec-kitty agent worktree repair --mission`
  (`coordination/surface_resolver.py:21-22`, `:109`). Confirmed: NO `agent worktree` command
  surface exists — only `git worktree …` subprocess calls. Dead-end remediation.

**This is the NEW-authority case in the cluster.** The read SSOT and the planning kind-partition
do NOT yet cover a *terminal/post-merge artifact whose durable home must survive coord teardown*.
The retrospective is a **MissionArtifactKind placement question + a topology-aware teardown
resolver**, and BOTH halves are missing:
1. **Placement:** retrospective must be a PRIMARY-partition (durable) artifact home — either a
   PRIMARY-partition `MissionArtifactKind` (so `resolve_planning_read_dir`/the write twin route
   it to `primary_feature_dir_for_mission`, NOT the coord seam), or the
   `.kittify/missions/<mission_id>/` durable home the skill already promises. The current
   `resolve_feature_dir_for_slug` (topology-aware) is the WRONG authority for a terminal artifact.
2. **Teardown sequencing:** `merge` must persist-then-flatten — write the retro to the durable
   home, drop `coordination_branch` from `meta.json` (flatten), THEN delete the coord branch +
   worktree. There is **no topology-aware teardown authority** analogous to the read SSOT; today
   teardown is open-coded in `merge.py` and `mission_type.py` (#2120) with no shared persist-
   before-destroy contract.
3. `retrospect create` must tolerate a flattened/torn-down topology (don't hard-fail
   `CoordinationBranchDeleted` for an already-merged mission), and the remediation text must point
   at the real flatten path, not the phantom `agent worktree repair`.

So #2119 is the WRITE-surface twin of the read SSOT: a *terminal-artifact home* + a *topology-
aware teardown* surface the existing SSOT does not yet provide.

---

### #2112 — repo-root detection — **N / out-of-cluster** (git-anchored init detection)

**Seam:** `assert_initialized` (`src/specify_cli/workspace/assert_initialized.py:92-119`) →
`resolve_canonical_root(Path.cwd())` (`src/specify_cli/core/paths.py:381-437`). The resolver
anchors on a **`.git` marker** walking up ancestors; it does NOT anchor on the `.kittify`
marker except in the submodule/separate-git-dir arm (`:429`). `init` is **file-creation-only and
does NOT `git init`** (`init.py:604-610`, `:851` "No git initialization. init is file-creation-
only", `:941-957` prints "Git: not initialized / Required: run `git init`"). So a fresh
`spec-kitty init <name>` project has `.kittify/config.yaml` but no `.git` → `resolve_canonical_root`
either raises `WorkspaceRootNotFound` (no enclosing repo) or resolves to a git-anchored ANCESTOR
that lacks the config → `assert_initialized` reports `.kittify/config.yaml` "Missing" though the
file plainly exists in the project dir. "Works from Cursor" + `triage:maybe-duplicate` fit:
Cursor runs from a git-tracked workspace.

This is a **repo-root / initialization-detection** concern — the `.git`-vs-`.kittify` anchoring
disagreement and the init-doesn't-git-init UX — entirely OUTSIDE the coord/primary surface-
resolution cluster. It shares NO root with the topology SSOT. Cannot be argued in: it fails
BEFORE any mission/topology resolution, on a project with no missions at all. Fix candidates
(separate seam): make `assert_initialized` anchor on the `.kittify` marker (so a non-git but
initialized project is recognized), and/or make `init` run `git init` (or warn-loud), and/or have
`resolve_canonical_root` stop at a `.kittify` boundary the way it already stops at the submodule
`.kittify` boundary (`paths.py:429`).

---

### #2116 — tasks.py tech-debt — **N / out-of-cluster** (router-contract, adjacent)

Body-thinning (a), FR-007 coord exit-0 skip consolidation into the router (b), and the protected-
coord exit-semantics unification (c) are a **router-contract / command-flow** concern. The FR-007
arm (`_skip_target_branch_commit` / `_protected_branch_status_commit_error`) governs a coord-
topology exit-0 silent-skip + `--json` envelope reshape that `commit_for_mission` cannot reproduce
— adjacent to the surface authority but NOT the read/write SSOT. It is genuine tech-debt, not a
3.2.3 regression. Recommend it stays OFF the regression patch (it is a deliberate
behavior-neutral refactor with its own #2058/#2114 lineage). The cross-command inconsistency (c)
is a DIRECTIVE_032 conceptual-alignment fork worth recording but is pre-existing.

---

## One mission vs split

**Split into two seams** (do NOT force one mission):

- **Seam 1 — read-side handle resolution (pure SSOT adoption): #2122 + #2120.**
  Both are "consume the RIGHT existing resolver authority before the surface read": #2122 missed
  the handle→slug canonicalize before the kind-aware read; #2120 picked the coord read seam where
  it needed the PRIMARY identity seam. Shared root = *a caller bypassed/mis-selected an existing
  SSOT primitive*. Both pure-adoption, both small, both regression-class (P1), both have a clean
  red-first test. Ship together.

- **Seam 2 — terminal-artifact home + topology-aware teardown (needs-new-authority): #2119.**
  This needs a placement decision (retrospective → durable PRIMARY home) AND a new shared
  persist-before-destroy teardown contract. Different bounded context (write/teardown vs read),
  different size, ADR-worthy. It can READ the #2120 fix as a precursor (close/merge teardown both
  want the same topology-aware teardown authority), so sequence #2120 → #2119, but keep them
  distinct missions/PRs.

- #2112 and #2116 are **independent singles**, not part of either seam. #2112 is a fast init/
  root-detection fix (P1, ship standalone or with Seam 1 only as a convenience bundle). #2116 is
  deferred tech-debt — keep OFF the 3.2.3 patch.

---

## ADR need

**Yes — one ADR for #2119** (Seam 2): "Terminal/post-merge artifact home + topology-aware
teardown contract." It is the WRITE-surface twin of the read-surface SSOT and the kind-partition
ADRs — it records (a) that retrospective (and any terminal artifact) has a DURABLE PRIMARY home
that survives coord teardown, and (b) that teardown must persist-before-destroy + flatten
`meta.json`. This is exactly the DIRECTIVE_003 "decision with context/options/rationale" case and
mirrors the existing `2026-06-19-1-coord-empty-surface-fallback.md` placement-decision ADR.

No ADR for #2122/#2120 (pure adoption of recorded SSOT — covered by #2106/#2113/#2070 ADRs; just
cite them). No ADR for #2112 (UX/detection fix, not an architectural authority decision — though
the `.git`-vs-`.kittify` anchoring choice could warrant a one-line note). No ADR for #2116
(refactor follow-on, lineage already recorded in #2058/#2114).
