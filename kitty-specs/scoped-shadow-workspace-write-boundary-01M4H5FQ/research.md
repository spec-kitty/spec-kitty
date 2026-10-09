---
type: explanation
updated: 2026-10-09
audience: agentic-framework-core-team
mission: scoped-shadow-workspace-write-boundary-01M4H5FQ
status: decision-pending-operator
decides: "#3129 (write-boundary topology) and #2334 (kitty-specs duplication) scoping"
---

# Scoped shadow workspaces — the write-boundary topology question (#3129 / #2334)

> **This document is the decision record (DIRECTIVE_003).** It is design material for
> an owner's-call decision. It does **not** make the structural call and it changes no
> write-path seam. It ends at an escalation gate: the operator chooses the #3129
> direction, and only then (and only for a bounded, decision-independent #2334 slice,
> if approved) does implementation follow.

## 0. The question, precisely

#3129 asks **one** thing of the operator (quoting the issue): whether a
*scoped-shadow-workspace-handle boundary* — where "the canonical tree is not merely
off-limits, it is **not reachable** from the handle the agent holds" — is

- **(A)** a *replacement* for the current coordination/primary partition,
- **(B)** *compatible with / layered onto* it (per-lane isolation preserved), or
- **(C)** *incompatible*, in which case "X is then the thing to write down."

ThickTicket's `internal/workspace/shadow.go` (`OpenShadowWorkspace`, `ShadowDiff`,
`CheckShadowMerge`, `ApplyShadowMerge`, `ErrShadowMergeConflict`) is the cited reference
implementation of the alternative topology. A second prior art, SugarFang's mirrored
shadow (`internal/project/shadow*.go`), is raised in the issue thread as a
*complementary* provenance/attribution mechanism rather than an alternative.

#2334 is the one still-open concrete instance of the same class, one layer down: mission
planning artifacts in `kitty-specs/<mission>/` exist as parallel copies across the
repository-root checkout, the coordination worktree, and lane worktrees, and must be
hand-synced. Its own stated "Direction" — *one authoritative surface per artifact with
the machinery resolving reads/writes through it, OR an automatic sync step* — is the
same question #3129 poses, scoped to planning artifacts.

**Terminology (CLAUDE.md footguns, named explicitly throughout):** `primary` here almost
always means the **PRIMARY partition** (the artifact-home set that lands on the mission's
`target_branch` for every topology) or the **repository-root checkout**; it never means
the Primary Branch `main` unless stated. `merge` here means **branch integration** or
**lane consolidation**, never publish-to-origin. `routing` here means **branch-target
routing** (which branch/checkout a write lands on) and **placement** (kind + topology →
surface), never dispatch/model/event routing.

---

## 1. Current write-boundary topology, as-built

### 1.1 The shape in one sentence

Lane worktrees, the coordination worktree and the repository-root checkout **share one
object store and one set of refs** (they are `git worktree` siblings of one repository),
so any process standing in any of them can, with a bare `git` call, write to any branch
and any tree. On top of that shared substrate the code builds a **declared, CWD-invariant
placement authority** — but that authority is reached only through a `repo_root` argument
that is itself **manufactured from ambient location** at the edges.

### 1.2 The declared authority (clean, CWD-invariant)

The artifact-placement seam is the single authority that answers "which physical surface
does this mission artifact live on." It is built to derive the answer **only** from the
stored Mission declaration, never from the current checkout:

- `MissionArtifactKind` is partitioned into exactly two home sets
  (`src/mission_runtime/artifacts.py:174` `_PRIMARY_ARTIFACT_KINDS`,
  `:218` `_PLACEMENT_ARTIFACT_KINDS`). A **PRIMARY** kind (spec, plan, tasks, WP tasks,
  `lanes.json`, research, data-model, contracts, retrospective, analysis-report,
  decision-ledger, meta) resolves `read_surface = write_surface = PRIMARY` and lands on
  the mission's `target_branch` for **every** topology (`artifacts.py:357`). A **COORD**
  kind (acceptance-matrix, issue-matrix, status-state, decision-log, tracer-files,
  review-cycle) resolves to the coordination surface (`artifacts.py:365`).
- `artifact_home_for` (`artifacts.py:341`) is a pure function of `(kind, placement_ref)`;
  `kind_is_coordination_residue` (`:147`) derives coord-routing solely from the **stored**
  `MissionTopology` via the single `routes_through_coordination` predicate — "NEVER from a
  fabricated `CommitTarget` shim."
- `PlacementSeam` (`src/mission_runtime/resolution.py:2302`) states the invariant in its
  own docstring: *"Both projections are CWD-invariant: they derive from `repo_root` +
  `mission_slug` (the stored topology, read via `meta.json`), never from the current
  checkout (T-2)."* `resolve_artifact_surface` (`:2839`) and `resolve_action_context`
  (`:3059`, *"CWD-invariant, topology-aware, mode-correct"*) hold the same line.
- Even the primary write-dir re-anchors: `_declared_primary_write_dir`
  (`resolution.py:2502`) uses `get_main_repo_root(self.repo_root)` "never `self.repo_root`
  verbatim, which would disagree with `path` when called from a lane worktree."

The **partition itself is #2334's "one authoritative surface per artifact" Direction,
already built** for every artifact routed through the seam. This is the single most
important as-built fact for the decision below.

### 1.3 Where "ambient location" enters

Ambient location does not enter the seam; it enters **upstream of it**, in the
`repo_root` the seam is handed and in the branch it falls back to:

1. **`repo_root` is seeded from `Path.cwd()` at CLI entry points.** Many commands begin
   with `repo_root = Path.cwd()` or `locate_project_root() or Path.cwd()`
   (e.g. `cli/commands/tracker.py:244`, `glossary.py:319`, `mission_type.py:1745`,
   `decision.py:129`, `intake.py:82`, `mission.py:426`). The cwd-walking resolvers then
   normalize: `locate_project_root` (`core/paths.py:239`) walks up from cwd and
   **collapses a worktree to the primary checkout** (`:268`), as does `resolve_canonical_root`
   (`:380`) and `get_main_repo_root` (`:451`). So a *write* `repo_root` is normally
   re-anchored to primary — **but only because the caller chose a write-side resolver.**
2. **The read-side resolver deliberately prefers the ambient worktree.**
   `get_status_read_root` (`core/paths.py:552`) "Prefers the *current worktree root* over
   the primary checkout" and carries an explicit contract: *"Use this for READ paths only.
   For write paths … use `get_main_repo_root()`."* (`:569`). The write/read asymmetry is
   intentional; the defect class is a *write* that reaches the read-preferring root, or a
   *read* used to make a write decision.
3. **The primary-branch fallback is biased to the checked-out branch.**
   `resolve_primary_branch` (`core/git_ops.py:316`) returns the currently checked-out
   branch when biased (`:356`), on the documented theory that "the user is standing on it
   for a reason." This is a genuinely ambient input; it matters only when `meta.json` has
   no `target_branch`. (`resolve_target_branch` `:376` and `read_target_branch_from_meta`
   `core/paths.py:658` are the declared path that supersedes it.)
4. **Ownership/identity is recorded from cwd by design** — `resolve_checkout_identity(cwd,
   intent)` (`core/checkout_identity.py:177`) records the *ambient* invoking checkout and
   refuses a WRITE when `invoking_root != canonical_target`. This detects "you are standing
   in the wrong worktree"; it does not redirect the write.

The lane allocator and the lane-worktree grammar are **declared relative to the passed
`repo_root`**: `<repo_root>/.worktrees/<slug>-<lane-id>` (`lanes/branch_naming.py:644`,
`worktree_allocator.py:1064`); they inherit ambientness only from a cwd-derived
`repo_root`.

### 1.4 The one existing structural guard (#3128)

`enforce_checkout_identity` (`src/mission_runtime/checkout_identity.py:121`) is a
**pure-path refusal** (no git subprocess, NFR-004): it compares the invoking cwd's
working-tree root against the mission's declared workspace and raises
`CheckoutIdentityError` on mismatch. It is deliberately scoped to the **one WP-mutation
chokepoint** — `resolve_workspace_for_wp(write_intent=True)` (`workspace/context.py:776`),
which only `implement`/`review` set true. The ~20 read call sites and every other mutating
command (`doctor`, `move-task`, `add-history`, `record-analysis`, …) do **not** pass
through it. #3128 is correctly described in-issue as "the cheap mitigation": it makes the
`implement`/`review` write chokepoint fail closed; it does not generalize, and it refuses
rather than redirects.

### 1.5 The invariant the codebase is already defending by hand

The exact seam #3129 names is already load-bearing folklore: the comment *"never
`Path.cwd()` (C-003/#2647)"* is replicated across `coordination/transaction.py:807`,
`status/emit.py:1230`, the `tasks_*` executors, `runtime_state_cutover.py`,
`backfill_runtime_state.py`, and more. Each is a hand-placed assertion that *this* write
target comes from the declaration, not from cwd. The invariant exists; it is enforced
per-site, not by construction.

---

## 2. Pattern extraction from the 13 merged point-fixes

All 14 issues in #3129's table share one root: **a command derives its write/read target
from ambient location instead of from the Mission's declaration.** Thirteen are merged;
only #2334 is open. The merged fixes collapse into **four recurring shapes**:

| Shape | What it patched | Instances |
|---|---|---|
| **A — collapse-to-primary resolver reached at a read/lookup/report site** | A command whose job is "answer about the checkout I was invoked from" called the single-authority resolver that *deliberately* collapses worktree→primary; fixed by making that one site worktree/clone-aware. | #3124, #3051, #3049, #2613 — **all four closed by one PR (#3567)** because they are the same line reached from four commands |
| **B — placement-partition WRITE mis-routed by ambient cwd** | A mission-state write landed on whatever branch the agent stood in (lane branch / primary residue) instead of the declared coordination surface; fixed by routing to the resolved surface and reporting the true commit. | #2549, #2702 (PRs #3437, #3492) |
| **C — a fail-closed location assertion bolted on** | Rather than fix resolution, compare invoking checkout against the declared workspace and refuse on mismatch. | #3128 (PR #3437) |
| **D — a guard that self-churns, or judges by ambient history** | The guard's own tool-generated churn (uncommitted frontmatter, VCS-lock, status emits) or a merge-base/commit-history comparison tripped it against legitimate work; fixed by scoping to ignore own churn, comparing content vs the declared planning branch, or making the op transactional. | #2570, #2367, #2797, #2274, #2745, umbrella #1914 (PRs #3556, #4789, #5916, …) |

**Why the supply is not exhausting (the evidence that the cause is structural):**

1. **The resolver and the design premise were never changed — only call sites.** #3051's
   own write-up states the collapse-to-primary resolvers "are **not bugged** … explicit,
   documented single-authority resolvers whose entire purpose is to collapse." Every fix
   left the collapse in place and corrected the one command that reached it wrong — so any
   *next* command that reads/writes relative to cwd re-exposes the identical defect.
2. **It recurred across structurally unrelated command families over quarters.** #3051 calls
   itself "the **third** confirmed command family hitting this exact mechanism (after #3049
   and #2613)." Fixes span Aug→Oct 2026 across many parents — a steady drip, not a cluster.
3. **Two agents tripped it independently in one landing pass** (#3051) — it is a default
   behavior of the workflow, not a rare edge.
4. **Contributors recognized point-fixes weren't closing the class** — #3051 says the fix
   "belongs at the mechanism level (#2624), not as a patch local to `cutover-guard`";
   #3128 proposes the structural form.
5. **The canonical instance is still open** (#2334): the family still has live members
   after 13 point-fixes.

The structural reading is consistent with §1: the fixes are all *downstream* of the clean
placement seam, in the layer where `repo_root`/branch is manufactured from ambient
location. **None of the 13 changed what a lane fundamentally *is* — a checkout sharing
the object store and refs with every other checkout.** That shared substrate is the
permanent supply.

---

## 3. #3129 options analysis

Three options. Each is weighed against the current coordination/primary partition,
migration cost, and blast radius. The recommendation is in §3.5; **the choice is the
operator's.**

### 3.1 Option A — Scoped shadow handles *replace* the partition

A lane becomes a shadow workspace created from a recorded source HEAD, living **outside**
the repository object store (ThickTicket's `ShadowBaseDir`, gitignored). An agent receives
a service handle scoped to that shadow; the canonical tree is **not reachable** from the
handle. `ShadowDiff`/`CheckShadowMerge` answer "what did this produce / would it integrate"
without mutating; `ApplyShadowMerge` is the single explicit crossing point;
`ErrShadowMergeConflict` is a typed outcome (a fixit, not a blocked pipeline). The
coordination/primary partition — coordination worktree, lane worktrees, the whole
`routes_through_coordination` machinery — is retired in favor of shadow + explicit apply.

- **Upside:** the defect class becomes *unreachable*, not merely refused (§2 Shape C). "Do
  not write to someone else's tree" stops being prose discipline and becomes a property of
  the object graph — exactly the argument the issue draws to the MD→YAML charter swap. The
  shared-object-store substrate (the permanent supply) is gone.
- **Cost / blast radius — very high.** Consolidation is built entirely on *shared refs and
  one object store*: `advance_branch_ref` CAS (`git/ref_advance.py`), the approval-stamp
  bound, the blob-attribution/closed-world axes, the coordination-teardown CAS gate, the
  single rollback authority — all reason over branches and commits in **one** repository.
  A shadow-outside-the-store model re-expresses every one of those as a cross-repository
  merge-and-attribution problem. This is not a seam swap; it is a new consolidation engine.
  It also changes the status model: `status.events.jsonl` is an in-repo coordination
  artifact today.
- **Compatibility verdict:** replaces the partition wholesale. Highest value, highest risk;
  a multi-mission programme, not a spike follow-on.

### 3.2 Option B — Scoped shadow handles *layer onto* the partition (recommended)

Keep the coordination/primary partition and the consolidation engine exactly as they are.
Add a **scoped workspace handle** as the only object an execution agent (`implement` /
`review`) is given: a capability-narrowed façade over the lane worktree it already owns,
through which the canonical tree and sibling lanes are **not reachable**. Mechanically this
generalizes what already exists:

- The placement seam (§1.2) already yields the single declared surface per artifact; the
  handle would be the **write-side dual** — a `WriteLocation`-like capability
  (`mission_runtime/write_location.py`) that carries the *only* paths/branches the agent may
  touch, so a bare `git`/path write outside them has no handle to reach.
- #3128's `enforce_checkout_identity` (§1.4) is the **refusing** prototype of this boundary
  at one chokepoint. Option B turns "resolve, then refuse on mismatch" into "only ever hand
  out a handle that *cannot* address the foreign tree," and generalizes it from the
  `implement`/`review` chokepoint to the mutating-command surface.
- Lanes stay lanes; `routes_through_coordination`, consolidation, rollback, the approval
  bound are untouched. The handle changes *what an agent can address*, not *how lanes
  integrate*.

- **Upside:** preserves the proven consolidation/rollback machinery and per-lane
  parallelism; converts the §2 defect class from "patch each new call site" to "a write
  that bypasses the handle does not type-check / has no path to the foreign tree." Blast
  radius is bounded to the workspace-resolution + command-entry layer (`workspace/context.py`,
  the CLI entry points in §1.3) — the layer the 13 fixes already churn.
- **Cost / blast radius — moderate.** Every mutating command must be migrated to accept and
  honor a handle instead of a cwd-derived `repo_root`; the read-preferring
  `get_status_read_root` must be kept legitimately read-only. This is real work but it is
  *in the layer that already carries the "never `Path.cwd()`" invariant by hand* — it
  replaces hand-placed assertions with a constructed boundary.
- **Compatibility verdict:** compatible; complements the partition. The shadow property
  (unreachability) is applied to the agent's *handle*, not to the lane's *storage*.

### 3.3 Option C — Incompatible; name reason X and take the cheaper structural step

If the operator judges a true shadow-outside-the-store boundary incompatible, the concrete
**reason X** is: **the consolidation engine's correctness proofs are defined over a single
shared object store and ref namespace** (CAS ref advance, approval-stamp reachability,
blob-attribution closed world, coordination-teardown CAS, the single rollback authority —
all in `src/specify_cli/consolidation/` and `git/ref_advance.py`). A boundary that makes
the canonical tree *unreachable* (Option A) removes the shared substrate those proofs
assume, so it cannot be adopted without rebuilding them; a boundary that only narrows the
*agent's handle* (Option B) does not, which is precisely why B is compatible and A is not.

If C is chosen (no new boundary object at all), the cheaper structural step that still
attacks the §2 supply is: **make `repo_root`/branch resolution declaration-first by
construction at the command-entry layer** — a single typed "resolve the mission's write
target from its declaration" entry that every mutating command must call, replacing the
scattered `Path.cwd()` seeds (§1.3) and the hand-placed "never `Path.cwd()`" assertions
(§1.5) with one authority. That is strictly less than B (no capability handle, no
unreachability — writes are still *possible*, just *correctly targeted by default*) and
closes Shapes A/B by removing the ambient seed, while Shapes C/D remain per-site.

### 3.4 Prior art note — SugarFang (complementary, not a fourth option)

The issue thread raises SugarFang's mirrored shadow as a **provenance** mechanism: every
mutation is mirrored to a shadow git repo with a commit stamped `[mission:<id>]
[session:<id>]`, fired automatically on every mutation path. It does not prevent drift; it
makes drift *attributable and reversible*. It is orthogonal to A/B/C (it answers "who wrote
what, under what authority, and can I replay it," which today's `status.events.jsonl`
records as *transitions* but not as *disk mutations*). It can compose with any of the three
and is out of scope for this decision; worth a separate issue if the replayable-provenance
story is wanted.

### 3.5 Prior art already shipping incrementally — PR #5957 / #3215 (dev-env layer)

Open PR **#5957 "[#3215] Bind Shadow Clone activation to the current worktree"**
(author LynnColeArt — the same author whose ThickTicket `shadow.go` is #3129's cited
reference; verified via `gh api`: base `main`, +86/−9, 4 files, `mergeable:false` pending
rebase) is the **dev-environment / shell-activation half** of the worktree-isolation theme.
It touches only `scripts/dev/activate-isolated-env.sh`, its test, and docs/changelog —
**not** the `src/**` write-path seam this spike is about (no `resolve_workspace_for_wp`,
`get_main_repo_root`, placement seam, or consolidation code). It binds the Shadow Clone
*activation helper* to the current git worktree so a developer's CLI + state stay in that
worktree.

Relationship to the three options: it is **orthogonal and complementary**, not a
dependency or a blocker. It isolates the *human developer's shell session* at the
dev-env layer; Options A/B isolate the *execution agent's runtime write target* at the
`src/**` layer. A scoped-shadow-handle boundary in the runtime (Option B) would **not
subsume** #5957 — the two operate at different layers (shell activation vs. mission-write
resolution) — but they share a direction, and #5957 is evidence the author is already
landing worktree-binding incrementally and narrowly, which supports the incremental
sequencing in §5.2. Recorded here as prior art; it changes neither this spike's scope
nor its escalation gate.

### 3.6 Recommendation (operator's call)

**Recommend Option B (layer onto the partition), with Option C's single declaration-first
entry as its first, independently-valuable increment.** Rationale:

- It keeps the one part of the system with hard-won correctness proofs — consolidation and
  rollback — untouched, so it carries none of Option A's engine-rebuild risk.
- It converts the §2 defect class from a per-call-site patch stream into a constructed
  boundary, which is the only thing shown to actually stop the supply.
- Its blast radius sits in the exact layer (command-entry + workspace resolution) the 13
  fixes already modify, so the team is working in familiar code.
- It degrades gracefully: the Option C increment (declaration-first `repo_root`/branch
  entry) is useful on its own even if the full capability handle is never built, so the
  work can land incrementally behind the operator's pace.

Option A is the highest-value end state and the truest expression of the issue's argument,
but it is a programme (new consolidation engine), not a spike follow-on; it should be
recorded as the north star and deferred.

---

## 4. #2334 scoping verdict

**Verdict: PARTIALLY DECOUPLED. The authoritative-surface machinery #2334 asks for already
exists (the placement seam, §1.2); one bounded, decision-independent slice remains and can
be fixed now; full elimination of the N physical copies is GATED on the #3129 decision.**

Breakdown:

- **Already delivered.** #2334's "Direction" (one authoritative surface per artifact,
  machinery resolving reads/writes through it) is the placement-seam partition. Planning
  artifacts are PRIMARY-partition (`artifacts.py:174`): spec/plan/tasks/`lanes.json`/
  research/meta resolve to the mission `target_branch` for every topology, read and write.
  The matrices the issue names are COORD-partition and routed. The CLI writers the issue
  flagged now go through the seam — e.g. `add-history` resolves its write surface via
  `placement_seam(...).read_dir(TASKS_INDEX)` → PRIMARY and writes the authoritative copy
  (`cli/commands/agent/tasks.py:1161`, `:1195`); #2705 ("add-history writes to a noncanonical
  surface") and #2684 (evict runtime-mutable WP state into the event log) are **closed**.

- **The one bounded, decision-independent slice that remains = a dual *writer*, not a
  missing authority.** The WP-prompt Activity Log still has **two** writers for **one**
  authoritative surface: the CLI (`add-history`, authoritative, → PRIMARY) *and* the human/
  agent implementer, because the WP-prompt **template still instructs a hand-append** in the
  lane copy (`packs/built-in/missions/software-dev/templates/task-prompt-template.md:119-166`
  "## Activity Log … How to Add Activity Log Entries … APPEND the new entry at the END"; the
  same section exists in the `research` and `documentation` templates). The implementer edits
  the lane worktree's copy; the CLI writes the PRIMARY copy — the exact 2026-09-06 re-witness
  on single_branch ("patch does not apply"). The seam already names ONE authoritative surface;
  the drift persists only because a *second writer* is still instructed by template prose.
  This is a **template-level fix** (evict the hand-append instruction so the CLI is the sole
  writer — the completion #2334's own last comment names: "Once #2684's eviction reaches the
  template … the CLI becomes the only writer"). It touches no write-path seam and is
  independent of the #3129 direction.

  - Scope if approved: remove the "How to Add Activity Log Entries" procedure from the three
    `packs/built-in/missions/*/templates/task-prompt-template.md` source templates (SOURCE,
    not agent copies — AGENTS.md), leaving the read-only "the acceptance/review reader sees
    the log" framing; confirm `add-history` remains the sole authoritative writer and the
    acceptance/review readers resolve through the seam.
  - **Open design question for the operator (small), not for me to pick:** whether the end
    state is (i) `add-history` remains the canonical markdown writer with the template simply
    no longer asking humans to append, or (ii) the Activity Log markdown is fully superseded
    by `status.events.jsonl` and `add-history`'s markdown write is itself retired. #2684's
    title ("evict … activity-log … into the event log") points at (ii), but `add-history`
    still writes markdown today, so the intended end state is genuinely ambiguous. I flag
    this rather than guess.
  - Regression coverage if approved: a test asserting the three source templates contain no
    hand-append instruction; a test asserting `add-history` writes exactly the PRIMARY
    surface and that a lane checkout + a CLI `add-history` do not produce divergent copies
    for the same WP (the #2334 reproduction, following RED-first discipline).

- **Gated on #3129.** The *physical* N-copies (every lane/coord worktree carries its own
  working-tree copy of tracked `kitty-specs/` files) is inherent to `git worktree` sharing
  one object store. The seam makes one surface *authoritative*, but it cannot make the other
  physical copies *not exist*. Eliminating them is exactly the Option A/B question
  (unreachable canonical tree / capability-scoped handle). So "N copies truly collapse to
  one" is GATED; "one authoritative surface with a single writer per artifact" is not, and
  the Activity-Log slice is the last known place that invariant is still broken by a second
  writer.

---

## 5. Risks and sequencing

### 5.1 Risks

- **Over-reading the seam as "done."** The placement seam is clean and CWD-invariant, which
  can read as "#3129 is already solved." It is not: the ambient seed is *upstream* (§1.3) and
  the shared object store (the §2 supply) is untouched. The risk is closing #3129 on the
  strength of the seam and watching Shape A/B/D recur on the next new command.
- **Option A scope illusion.** A shadow-outside-the-store boundary looks like a workspace-
  layer change but lands as a consolidation-engine rewrite (§3.1 reason X). Mis-sizing it as
  a spike follow-on is the main planning risk.
- **#2334 template fix mis-scoped.** If the operator intends end state (ii) (retire the
  markdown Activity Log), a template-only edit is incomplete; if (i), retiring the markdown
  writer is over-reach. The ambiguity must be resolved *before* implementation, not during.
- **Terminology drift in the decision itself** (the `primary`/`merge`/`routing` footguns) —
  mitigated by naming every sense inline here.

### 5.2 Recommended sequencing

1. **Now (this escalation):** operator chooses the #3129 direction (A / B / C) and rules on
   the #2334 Activity-Log end state (i vs ii) + go/no-go for that bounded fix.
2. **Lands incrementally, independent of the #3129 choice (if approved):** the #2334
   Activity-Log dual-writer fix (template eviction + sole-writer confirmation + the #2334
   reproduction test). Bounded, no seam change.
3. **First increment of the chosen #3129 direction (if B or C):** the single declaration-
   first `repo_root`/branch resolution entry at the command-entry layer, replacing the
   `Path.cwd()` seeds (§1.3) and folding in the hand-placed "never `Path.cwd()`" assertions
   (§1.5). Valuable standalone; closes Shapes A/B.
4. **Design decision required before any structural step:** if B, the capability-handle
   design (write-side dual of the placement seam, generalized from #3128); if A, a dedicated
   multi-mission programme to re-express consolidation over the shadow model — not started
   until explicitly commissioned.
5. **Separate track, any time:** SugarFang-style mirrored-shadow provenance (§3.4), if the
   replayable-trust story is wanted — a new issue, orthogonal to this decision.
6. **Already in flight at the dev-env layer (not blocking):** PR #5957 / #3215 (§3.5) lands
   the shell-activation worktree binding independently; it neither waits on nor blocks any
   #3129 runtime decision.

---

## Appendix — primary code citations

| Claim | Location |
|---|---|
| Two-partition artifact home | `src/mission_runtime/artifacts.py:174` / `:218` / `:341` / `:357` / `:365` |
| Placement seam CWD-invariance | `src/mission_runtime/resolution.py:2302` / `:2502` / `:2839` / `:3059` |
| `repo_root` seeded from cwd (entry points) | `cli/commands/tracker.py:244`, `glossary.py:319`, `decision.py:129`, `intake.py:82`, `mission.py:426` |
| Worktree→primary collapse (write resolvers) | `core/paths.py:239` / `:380` / `:451` |
| Read-preferring root (reads only) | `core/paths.py:552` (`:569` contract) |
| Primary-branch ambient bias | `core/git_ops.py:316` (`:356`) |
| Declared target-branch read | `core/git_ops.py:376`, `core/paths.py:658` / `:817` |
| #3128 checkout-identity refusal | `src/mission_runtime/checkout_identity.py:121`; chokepoint `workspace/context.py:776` |
| Ambient-invariant folklore | `coordination/transaction.py:807`, `status/emit.py:1230` ("never `Path.cwd()`") |
| Lane worktree grammar | `lanes/branch_naming.py:644`, `worktree_allocator.py:1064` |
| #2334 add-history through seam | `cli/commands/agent/tasks.py:1161` / `:1195` |
| #2334 template second writer | `packs/built-in/missions/software-dev/templates/task-prompt-template.md:119-166` |
