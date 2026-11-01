---
title: 'Coordination-branch trust & reconciliation model — mission scope (#2841)'
description: 'Pre-spec scope for the coord-branch trust friction-remediation mission (#2841): the missing write-placement model, the solution shape, and the locked design decisions.'
doc_status: deprecated
updated: '2026-08-27'
related:
- docs/adr/3.x/2026-06-27-1-common-docs-reconciliation.md
- docs/plans/engineering-notes/index.md
---

# Mission-scoping brief — Coordination-branch trust & reconciliation model (#2841)

> **Retired (deprecated).** Design shipped/superseded via merged mission `coord-write-placement-closure-01KYCF83` (#2841; `kitty-specs/coord-write-placement-closure-01KYCF83/`). Preserved as a historical record.

Status: **pre-spec, for operator sign-off**. READ-ONLY analysis; no product code changed.
Grounded in the code at the state of branch `doctrine/drg-completeness-2843` (worktree copy).

---

## 1. Problem model — one missing model, three symptoms

**The single underlying gap: a mission's coordination-branch content has no trust or
reconciliation model.** The coord branch is minted as a *one-time snapshot* and thereafter
the toolchain has no notion of (a) whether that snapshot is still fresh relative to the
target it was cut from, (b) whether the bookkeeping written onto it still matches where the
real work landed, or (c) that the mission's *own* runtime state on that branch is trusted
self-managed content rather than a foreign surface to be policed. All three of #2841's
symptoms are facets of that one absence:

| Facet | What's missing | Direction |
|---|---|---|
| **Gap 1 — bootstrap staleness** | No *freshness contract*: coord branch is snapshotted once and never compared to target again. | Prevention |
| **Gap 2 — no reconciliation command** | No *content-trust contract*: nothing reconciles stale/corrupted coord bookkeeping (`review-cycle-N.md`, etc.) against where the WP's real commits live. | Cure |
| **Symptom B — gate blocks on own runtime state** | No *ownership contract*: the diff-compliance gate treats the mission's own `status.events.jsonl`/`status.json` as an unclassified foreign surface, forcing a hand-commit into coord to register an exception — itself an act of unreconciled coord mutation. | Friction |

They compose because each one is the system failing to answer *"is this coord content trusted,
current, and mine?"* — Gap 1 for freshness, Gap 2 for correctness, Symptom B for ownership. #2841 explicitly asks that Gap 1 + Gap 2 be designed as **one canonical fix on the
`doctor coordination --fix` seam** (citing #2392's consolidation precedent), not two point patches.

---

## 2. Evidence — the real surfaces (file:line)

### 2.1 Gap 1 — bootstrap snapshot, no re-sync

- `ensure_coordination_branch()` — `src/specify_cli/missions/_create.py:195-260`. On the
  happy path it does exactly `_create_branch(repo_root, branch, target_branch)` (L259): a
  one-shot branch off target at create time.
- The only staleness guard is `_is_ancestor()` (`_create.py:268-289`), and it only fires when
  an existing branch is **re-encountered** on a *re-run* of `mission create` (L249-257):
  ancestor → reusable, diverged → `CoordinationBranchDiverged`. It never asks "has target
  moved since I was cut."
- Nothing downstream (`specify`/`plan`/`tasks`/`finalize-tasks`) checks coord-vs-target.
- The only related doctor check, `_coord_worktree_stale_finding()`
  (`_coordination_doctor.py:312-359`), compares the coord **worktree HEAD** to **its own
  coord branch tip** (`refs/heads/{coord_branch}`, L328-332) — *not* to target/main. Confirms
  #2841's claim: no surface anywhere compares coord to the branch it was forked from.

### 2.2 Gap 2 — the narrow reconciliation that already exists (the extension point)

- `doctor coordination --fix` reconciles exactly **one** split-brain today: a stranded `done`
  status after a merge rollback. Driven by `pending_coord_reconcile` markers via
  `_check_stranded_coord_revert()` (`_coordination_doctor.py:780-802`) →
  `_finding_for_reconcile_marker()` (L680-777) → heal by `_heal_one_strand()` (L815) /
  `_fix_stranded_reverts()` (L892) / `_apply_stranded_revert_fix()` (L942).
- The staleness derivation is `coord_incoherent_done_wps(coord_ref, candidate_wps, ...)`
  (L742) — it re-derives from the **committed coord ref**, never from marker presence. That
  detect→re-verify→heal-or-fail-loud shape is precisely the engine to generalize: today it is
  hard-wired to *one status enum*; Gap 2 needs it to cover **arbitrary bookkeeping content**
  (a WP's `review-cycle-N.md`, issue-matrix rows, notes) reconciled against the real WP commit.
- The heal path already models the two non-happy terminals #2841 asks for: a healable live
  strand (`error`, `--fix` forwards) vs a pruned-worktree strand that stays `error` but
  becomes a manual-recovery hint (L749-766) — i.e. "forward when safe, fail loud otherwise."

### 2.3 The single-workspace rebase (why it did NOT cover Gap 2)

- `GitVCS.sync_workspace()` (formerly in `src/specify_cli/core/vcs/git.py`) fetched, resolved
  the workspace's own tracking/upstream branch, and rebased **that workspace's own commits**
  onto it — a per-workspace freshness tool with no sibling-branch / coord-vs-target awareness,
  not a cross-branch content reconciler, so it never covered Gap 2. **This method has since
  been deleted** (issue #424, PR #500 — "Delete dead GitVCS/VCSProtocol.sync_workspace, no live
  caller"). The chain: the CLI `sync.py` path that once cited it was removed by commit
  `66038e2a5` ("refactor(sync): remove sync transport surfaces from CLI registration and agent
  commands") ahead of the Ephemeral Team Status redesign (`PROGRAM.md` §1), leaving only test
  callers (issue #272); #424 then removed both `GitVCS.sync_workspace()` and the
  `VCSProtocol.sync_workspace` export from `specify_cli.core.vcs.__all__`. There is now no
  single-workspace rebase surface in this repo — if the Gap-2 distinction is still useful it
  must be drawn against a live mechanism, not this deleted one.
- **Still-stale sibling docs (their own follow-up, not fixed here):** the active guides
  `docs/guides/how-to/collaboration/sync-workspaces.md` and
  `docs/guides/how-to/missions/handle-dependencies.md` still document a `spec-kitty sync
  workspace` CLI command that no longer exists (no `sync` command is registered anywhere in
  `src/specify_cli/cli/`); they need their own correction or removal.

### 2.4 Symptom B — diff-compliance gate blocks on the mission's own runtime state

- Gate: `src/specify_cli/bulk_edit/diff_check.py`. `assess_file()` (L237) classifies each
  changed file via `classify_path()` (L118) against ordered `_PATH_RULES` (L41-110):
  - `.json` → `serialized_keys` (L77-85) — in a terminology bulk-edit this category is
    typically `do_not_change`/`manual_review`, so a churning `status.json` **violates**.
  - `.jsonl` → **matches no rule** → `classify_path` returns `None` → the FR-008
    "does not match any standard occurrence category ... unclassified surface touched"
    violation (L279-291). So `status.events.jsonl` blocks unconditionally.
- Runtime-state filenames are fixed constants: `EVENTS_FILENAME = "status.events.jsonl"`
  (`status/store.py:45`), `SNAPSHOT_FILENAME = "status.json"` (`status/reducer.py:83`); they
  live at `kitty-specs/<mission>/`.
- The caller has the mission context the classifier lacks: `check_review_diff_compliance(
  feature_dir, base_ref, head_ref, ...)` (`bulk_edit/gate.py:199-245`) collects **every**
  changed path via `_git_diff_files()` → `git diff --name-only base..head` (L129-196) and
  passes the raw list to `check_diff_compliance` (L245). The mission's own runtime writes are
  in that diff, so the only escape today is a hand-authored `occurrence_map.yaml` exception —
  which is itself a coord-content mutation. **This is the auto-exemption seam.**

### 2.5 Symptom A (out of scope — composes with PR#2612)

- `safe_commit()` (`git/commit_helpers.py:843`) path policy step **6a** rejects any staged
  path under `.worktrees/` → `SafeCommitPathPolicyError` (~L985-995). This is the failure
  where a status commit can't land in the coord **sub-worktree** from the primary root.
- **PR#2612 (OPEN, maintainer take-over)** — "auto-commit during agent action review fails on
  missions using a coordination worktree" — fixes the *write* path by threading
  `_worktree_root_for_feature_dir` (the sub-worktree root) into `safe_commit`. **This mission
  must NOT redo that.** It builds on top: once writes land correctly, this mission stops the
  gate from flagging them (B), detects when they've gone stale (Gap 2), and keeps the branch
  fresh (Gap 1).

---

## 3. Proposed solution shape (component by component)

### C1 — Gate auto-exemption for mission-owned runtime state (Symptom B)

Thread a *mission-owned runtime-state* predicate into the classifier. `check_review_diff_compliance`
already holds `feature_dir`; pass an allowlist of runtime-state basenames anchored to the
mission's **own** `feature_dir` into `assess_file`/`check_diff_compliance`. Add an exemption
branch **before** the path-heuristic (mirroring the existing move/exception exemptions at
`diff_check.py:239-275`): a path that is (mission's own feature_dir) + (runtime-state basename)
→ `FileAssessment(source="runtime-state", violation=False)`. No `occurrence_map` entry, no
hand-commit into coord ever needed.
- Extension points: `diff_check.py` `assess_file` (L237), `classify_path` (L118); `gate.py`
  `check_review_diff_compliance` (L199) to supply `feature_dir` + the allowlist.
- Composes with PR#2612: independent (gate is read-side); can land first.

### C2 — Coord-vs-target freshness check + safe re-sync (Gap 1)

A new `_coord_branch_stale_vs_target_finding()` in `_coordination_doctor.py` that compares the
**coord branch tip** against **target** (reusing the `merge-base --is-ancestor` plumbing that
`_is_ancestor` at `_create.py:268` and `_coord_worktree_stale_finding` at L338 already use):
- coord strict-ancestor of target → **stale, fast-forwardable** (safe auto-fix under `--fix`);
- diverged → **warn, fail loud**, no auto-mutation.
Surfaced through a new `spec-kitty doctor coordination --check-staleness` mode and (per cadence
decision, §4-D1) an optional non-blocking warn woven into `finalize-tasks`.
- Composes with PR#2612: reads only; fast-forward re-sync of the coord worktree must honor the
  sub-worktree root PR#2612 establishes.

### C3 — Generalized reconciliation engine + `mission repair` (Gap 2)

Generalize the existing `_finding_for_reconcile_marker` / `_heal_one_strand` engine
(`_coordination_doctor.py:680-942`) from "one `done`-status split-brain" to a pluggable
*bookkeeping-artifact reconciler*: detect(coord content vs real WP commit) →
forward-when-safe → fail-loud-with-unified-diff otherwise. Expose it as
`spec-kitty agent mission repair --mission <slug>` **as a thin entry over the same engine**
(one reconciliation authority, not two — this is #2841's "design as one canonical fix").
- Extension points: the marker/heal functions above; `coord_incoherent_done_wps` (L742)
  becomes one detector among several.
- Composes with PR#2612: forwarding correct content is a coord write → must go through
  `safe_commit` with the sub-worktree root PR#2612 threads. Hard dependency on #2612 landing.

### C4 — Cadence wiring (Gap 1 UX)

A warn-only hook at `finalize-tasks` (and/or `tasks`) that calls C2's detector. Non-blocking;
prints the suggested `doctor coordination --check-staleness`/`--fix` recovery command.

---

## 4. Open design decisions needing an operator call

**D1 — Gap 1 re-sync cadence/UX** *(the #2841 open question)*
- (a) explicit `doctor coordination --check-staleness` only (opt-in, read-only report);
- (b) + non-blocking warn woven into `finalize-tasks`/`tasks`;
- (c) automatic silent fast-forward at plan time.
- **Recommendation: (b).** Explicit doctor flag + a warn (not block) at finalize-tasks. Offer
  fast-forward *only* under an explicit `--fix` and *only* when coord is a strict ancestor of
  target (no divergence risk). Never mutate silently (rules out c).

**D2 — `mission repair` command surface**
- (a) a brand-new standalone reconciliation engine under `agent mission repair`;
- (b) generalize `doctor coordination --fix`'s engine and expose `mission repair` as a thin
  mission-scoped entry over it.
- **Recommendation: (b).** #2841 explicitly wants one canonical fix on the doctor seam. Two
  engines would re-fork the split-brain logic. `mission repair --mission <slug>` = single-mission
  view of the shared reconciler.

**D3 — Reconciliation "safe to auto-forward" policy**
- (a) auto-forward only when coord content is a strict-ancestor/subset of the real committed
  content (coord behind, real ahead) **and** the coord worktree has no uncommitted edits;
- (b) content-hash equality gate;
- (c) always require operator confirmation.
- **Recommendation: (a).** Fail loud with a unified diff in every other case (matches the
  existing pruned-worktree "stays error, manual hint" terminal at `_coordination_doctor.py:749-766`).
  This is the data-loss-sensitive decision — keep it conservative.

**D4 — Symptom B exemption scope**
- (a) exempt only `status.events.jsonl` + `status.json`;
- (b) a named allowlist of mission-owned runtime bookkeeping (status files **plus**
  `review-cycle-N.md`, issue-matrix, notes, trace);
- (c) exempt everything under the mission's own `feature_dir`.
- **Recommendation: (b), anchored to the mission's OWN feature_dir.** Not (c): `spec.md`/
  `plan.md`/`tasks.md` **are** reviewable product surface a bulk-edit legitimately touches and
  must keep classifying. Anchoring to the mission's own feature_dir stops a bulk-edit that
  renames *another* mission's files from being silently exempted.

**D5 — Freshness scope: coord-only vs coord + lane branches**
- #2841's Gap 1 field report also cites a **lane** branch missing a CLI flag added to main.
- (a) this mission covers coord only; (b) coord + lane branches.
- **Recommendation: (a).** Coord is the trust anchor and the shared `--fix` seam. Lane-branch
  freshness is `sync workspace`'s domain — file a scoped follow-up rather than widen blast
  radius. **Historical framing, not a current routing claim (2026-08-28; updated after #424):**
  the `spec-kitty sync workspace` CLI command this recommendation names was removed by
  `66038e2a5`, and its underlying `GitVCS.sync_workspace()` method has since been deleted
  outright (issue #424, PR #500 — see §2.3 above). A scoped lane-branch-freshness follow-up
  today therefore has neither a live `sync workspace` command nor a `sync_workspace()` method to
  land in; it must target whatever live freshness surface exists at the time, not either
  deleted one.

---

## 5. Rough WP/IC shape & size

| WP | Scope | Size | Depends on |
|---|---|---|---|
| **WP-A** | C1 gate auto-exemption (D4) — runtime-state allowlist threaded through `assess_file`/`check_diff_compliance`, new exemption branch + focused tests (incl. negative: a non-runtime file under feature_dir still classifies). | **S** | none (gate read-side; independent of #2612) |
| **WP-B** | C2 coord-vs-target staleness detector + `doctor coordination --check-staleness` + safe `--fix` fast-forward (D1). | **M** | #2612 for the FF write path |
| **WP-C** | C3 generalize the doctor reconcile engine to arbitrary bookkeeping + `agent mission repair` (D2, D3). | **L** | #2612 (writes), WP-B (shared detector plumbing) |
| **WP-D** | C4 cadence warn hook at finalize-tasks/tasks (D1-b). | **S** | WP-B |
| **WP-E** | Docs + runbook (`docs/architecture/execution-lanes.md`, coordination doctor reference). | **S** | WP-A..C |

**Suggested mission type: `software-dev`** (brownfield structural remediation). Given the four
open forks — especially D3's data-loss-sensitive auto-forward policy — **run a short research
step first** (or route through `/spec-kitty.research`) to lock the reconciliation-safety policy
before spec. WP-A is the fast, high-value, dependency-free slice and could ship as the first
increment even ahead of #2612.

---

## 6. Risk / blast-radius

- **WP-A touches the diff-compliance gate every bulk-edit mission depends on.** A too-broad
  exemption (esp. choosing D4-c) would let real surface changes slip past review. Mitigate:
  anchor to the mission's own feature_dir + a named allowlist; add a regression asserting a
  non-runtime file under the same feature_dir still gets classified/violated.
- **WP-B/WP-C touch the commit + reconciliation path.** Auto-forwarding coord content is
  data-loss-adjacent. Must fail-loud-by-default (D3-a), reuse `safe_commit`, and honor the
  sub-worktree root PR#2612 threads — bypassing it re-triggers the `SafeCommitPathPolicyError`
  at `commit_helpers.py:~985`.
- **Coord vs primary partition correctness.** Reconciliation must read/write the *right*
  partition (coord = lifecycle: status/notes/trace/matrix/review-cycle; primary = planning +
  meta.json). Getting this wrong re-introduces a #2834-class split-brain — treat the partition
  boundary as a hard invariant with tests.
- **Squash-merge "unreachable commits" is NOT a bug and NOT in scope.** #2841 flags the 11
  unreachable coord commits as an inherent consequence of the default squash strategy. Do not
  attempt to "fix" reachability; only freshness/reconciliation/ownership are in scope.
- **Hard sequencing dependency on PR#2612.** WP-C's forwarding writes depend on #2612's
  sub-worktree threading. Land WP-A independently; gate WP-C on #2612 to avoid re-solving the
  write path.
