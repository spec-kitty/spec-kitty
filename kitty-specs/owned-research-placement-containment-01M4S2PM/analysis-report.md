# Grounding note — #5882: owned-checkout research placement + owned plan surface

**Branch:** `issue-5882-owned-research-placement-and-plan` (= origin/main, pkg 4.0.0rc7)
**Posture:** repro-first (`triage:repro-needed`). Report is on installed 3.2.7/macOS.

## 1. Reproduction on CURRENT main (4.0.0rc7) — CONFIRMED

Harness: canonical owned-checkout R/P/S fixtures (`tests/integration/conftest.py`
`owned_checkouts` + `stale_root_copy` + `r_snapshot`), driving the REAL
`research` command with real root resolution (no `find_repo_root` patch). New
red-first file `tests/integration/test_owned_research_placement.py`.

- **Surface A.1 — no owned selector.** `research --mission <slug> --owned-checkout <P>`
  → `Error: No such option: --owned-checkout` (exit 2). `research` is the only
  first-party lifecycle/authoring command still lacking an owned selector.
- **Surface A.2 — silent redirect into dirty primary.** Flagless
  `research --mission <slug>` run from inside the owned checkout P resolves the
  PRIMARY checkout R (proven by `Legacy asset resolved: .../primary/.kittify/templates/...`
  logs) and scaffolds `research.md`/`data-model.md`/the two CSV stubs into R's
  (stale same-slug) `kitty-specs/<slug>/`, NOT into P. With no copy in R it
  instead refuses `Mission not found` — the owned mission is unreachable either
  way. This is exactly #5882's "never silently redirect to an unowned dirty
  primary" violation, still live.

Verdict: **Surface A reproduces.** Surface B (below) is largely already fixed on
main; the narrow residual is the top-level `plan` wrapper.

## 2. Code grounding (file:line)

### Surface A — research placement (the defect)
- `src/specify_cli/cli/commands/research.py`:
  - `research(...)` signature (170-177): **only** `--mission`, `--force`. No
    `OwnedCheckoutOption`, no `resolve_owned_*` call anywhere in the file.
  - `repo_root = find_repo_root()` (183) → `task_utils/support.py` →
    `get_main_repo_root` follows a worktree `.git` pointer back to the PRIMARY.
  - `project_root = get_project_root_or_exit(repo_root)` (188).
  - `_read_mission_dir_or_exit(repo_root, slug, kind)` (137-167) →
    `placement_seam(repo_root, slug).read_dir(kind)` (159) — **no `owned=` arg**,
    unlike every fixed sibling. Used for STATUS_STATE (212), RESEARCH (248,
    then `planning_dir.mkdir`), FINALIZED_EXECUTION_PLAN (261).
  - The four assets map through `_write_research_asset` → `planning_dir/<rel>`
    (`_RESEARCH_ASSET_TEMPLATES`, 31-36). `planning_dir` = primary-resolved.
- `src/specify_cli/cli/commands/lifecycle.py`:
  - top-level `specify`/`plan`/`tasks` are thin wrappers over
    `agent_feature.{create_mission,setup_plan,finalize_tasks}` — all three seams
    ALREADY accept `owned_checkout: OwnedCheckoutOption`, but the top-level
    `plan` (246) exposes only `--mission`/`--json`, so it cannot forward owned.

### Fix pattern to MIRROR (the canonical owned threading)
- `_owned_checkout.py`: `OwnedCheckoutOption` / `owned_checkout_option(help=...)`;
  validators `resolve_owned_or_adopt` (explicit flag → `resolve_owned_mission`;
  flagless → `adopt_owned_checkout` when cwd is inside a validated owned
  checkout) and `resolve_owned_or_refuse`. Refusals render via
  `emit_owned_refusal` with typed `OwnedRefusalCode`.
- `OwnedCheckout` fact (`src/mission_runtime/owned_checkout.py`): `repository_root`
  (R), `owned_root` (P, must ≠ R), `mission_dir` (under P), `topology`,
  `write_branch`; `.files(paths)` validates containment.
- Exemplars: `mission_record_analysis.py` (option 401 → `resolve_owned_or_refuse`
  414-422 → `repo_root = owned.owned_root` → `placement_seam(..., owned=owned)`);
  `mission_setup_plan.py` (owned → `spec_read_dir = plan_read_dir = owned.mission_dir`).
- For an owned run, research.md/data-model.md/CSVs are PRIMARY-partition kinds,
  so the destination is simply `owned.mission_dir` — resolve the three
  `_read_mission_dir_or_exit` dirs from `owned` (thread `owned=owned` into the
  seam) and set `project_root = repo_root = owned.owned_root`.

### Surface B — owned plan authoring (mostly already landed)
- `agent mission setup-plan` **has** `--owned-checkout` and honors it fully
  (PR #6002). `record-analysis`, `check-prerequisites`, `decision`,
  `map-requirements`, `finalize-tasks`, `charter generate` likewise.
- Still refuse owned **by design** (intentional carve-outs, NOT bugs to fix):
  `agent action implement`/`review` → `OWNED_ACTION_UNSUPPORTED` (routed to
  `next`/`move-task`); `check-prerequisites --resume-probe` + owned →
  `OWNED_OPTION_UNSUPPORTED`; `tasks move-task`/`mark-status` non-auto-commit;
  `accept --diagnose`.
- The specify→plan `next` "No eligible steps: remaining steps have unmet
  dependencies" is a REAL `depends_on` DAG gate in
  `runtime/next/_internal_runtime/planner.py::_resolve_next_unified_step`
  (283-285, 394-402), downstream of composition guard-fact surface resolution —
  NOT a planner or driver-timeout bug. The reporter themselves walked this back
  (a 900s driver issued the plan step). No independent fix; it is a consequence
  of surface alignment. `next` already carries `--owned-checkout`.
- **Residual actionable gap:** top-level `spec-kitty plan` does not expose/forward
  `--owned-checkout` to its already-owned-aware `setup_plan` seam.

## 3. Tickets landscape (sibling/duplicate/superseding)

| Ticket | State | Relation | Respect |
|---|---|---|---|
| #2683 | OPEN P1 | **sibling — research/plan placement split, COORD topology** | #5882 is the owned-single-branch analog. Narrow to owned/single_branch; cross-link; do NOT duplicate its coord work. |
| #6002 | MERGED 2026-10-10 | prior-art / mirror | Owned-threading pattern (resolve → OwnedCheckout → placement/preflight/commit); add NO new resolver. |
| #5277, #5874, #4252, #5026 | CLOSED | prior-art (owned read-side + lifecycle) | Stay consistent with the owned-read model. |
| #5697 | OPEN P2 | must-respect (classifier) | research/** files have no artifact kind → placement treats unknown as PRIMARY. Resolving from `owned.mission_dir` sidesteps this. |
| #6001 | OPEN | must-coordinate (seam direction) | Don't entrench a 5th near-dup wrapper; align with the seam-bound-handle direction. |
| #5917 / #6003 | OPEN | must-respect (mypy) | Pre-existing strict-mypy baseline; attribute only NEW mypy findings. |
| #5380 | OPEN P2 | sibling | owned record-analysis deadlock residual — out of scope. |
| #2624 | OPEN P1 epic | parent | owns the detection mechanism; #5882 is a child on the owned-resolution half. |

**No open issue or open PR claims the research-placement fix** (verified #5882
timeline + source). Slice A is unclaimed and safe to implement. #5925/#5926
closed the owned-`next` decisions-lock commit; the "template captured before
agent authoring" scaffold-boundary half the reporter raised is unowned and is a
NON-GOAL here per the issue.

## 4. Scope decision
1. **research owned placement (priority).** Add `OwnedCheckoutOption`; auto-adopt
   from an owned cwd + explicit `--owned-checkout`; resolve the three mission
   dirs from `owned.mission_dir`; never redirect into an unowned/dirty primary.
   Red-first regression (in hand).
2. **top-level `plan` owned forwarding.** Expose `--owned-checkout` and forward
   to the owned-aware `setup_plan` seam (+ skip interactive interview in owned
   mode as it already is in `--json`/agent mode).
3. Render the owned selector affordance in the research discovery prompt.
4. Docs/CHANGELOG `[Unreleased]`.

Non-goals (issue): do not force runtime phases, hand-edit status, copy the Mission
into primary, or chase the scaffold template-capture boundary (unowned / #5925 family).
