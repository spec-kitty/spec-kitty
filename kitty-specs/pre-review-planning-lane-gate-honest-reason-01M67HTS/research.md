# Discovery — #6792 pre-review gate reason for a planning-lane WP

## Decisions

### D-1 — The defect reproduces on `main@512567ee7`; it is the reason string, not the skip

Reproduced with the real git shape of a planning-lane WP (script kept out of the
tree; commands in D-1 evidence). A `planning_artifact` WP whose two deliverables
were committed on the target branch (`docs/gate.md`, `docs/more.md`, clean tree)
produced:

```
worktree: /tmp/repro6792-...        # the planning_artifact arm resolves to the repo root
changed_files: ()
verdict: no_coverage | no changed files detected for this WP — skipping the gate cheaply
```

The verdict is truthful about the *outcome* (nothing to scope, non-blocking) and
false about the *cause*: the WP did change files. This matches the issue's root
cause exactly.

**Evidence.**
- `src/specify_cli/cli/commands/agent/tasks_move_task_gates.py:1039` — the sole
  producer of the string, the `if not inputs.changed_files:` short-circuit in
  `_mt_collect_transition_gate_verdicts`.
- `_mt_pre_review_changed_files` (`:313`) diffs the workspace HEAD against
  `review_base_ref or target_branch` via `merge_base_changed_files` and adds
  dirty paths. For a planning-lane WP the workspace **is** the checkout sitting on
  the target branch, so the merge-base diff is empty by construction and a clean
  tree adds nothing.
- `_mt_resolve_pre_review_workspace` (`:274`) returns that checkout for a
  planning-lane WP through `workspace.context._resolve_planning_artifact_arm` /
  `_resolve_planning_lane_arm`, both of which return `resolution_kind="repo_root"`
  and `lane_id="lane-planning"`.

### D-2 — This is #2741's surviving message acceptance, not a duplicate of an open issue

- #2741 (closed) asked for "at minimum record 'committed-diff not inspected'
  rather than a misleading `no_coverage`". The rewritten gate kept the
  `no_coverage` outcome and did not add the honest reason for this shape.
- #3046 (open) is a different facet: advisory-gate blocking on its own timeout
  plus the 300 s budget. Out of scope here.
- `docs/development/how-to/review-gates.md:150` records the inherited
  working-tree-diff limitation as "tracked separately… must not be mistaken for a
  fix". This mission does not close that limitation either; it makes the recorded
  *reason* honest for the planning lane, which is what #6792 asks for.

### D-3 — Classification asks the existing seams; no new vocabulary

Planning-lane identity already has two canonical authorities and this mission
adds neither a third nor a string literal:

- `specify_cli.ownership.models.WorkProductKind.PLANNING_ARTIFACT` for the
  declared execution mode (written into WP frontmatter by `finalize-tasks`;
  `is_confined_planning_wp` in `mission_parsing.py` compares against
  `WorkProductKind.PLANNING_ARTIFACT.value`, the same shape this mission uses).
- `specify_cli.lanes.compute.is_planning_lane` for the lane membership question;
  `is_repo_root_lane` delegates to it and `compute.py` states call sites must ask
  the semantic question rather than compare the constant.

Order matters: an explicit `execution_mode: code_change` must win over lane
membership, because `workspace.context._resolve_repo_root_lane_arm` documents that
a **single_branch** mission's repo-root `lane-planning` can legitimately hold CODE
work packages. So the predicate is: declared `planning_artifact` → planning lane;
declared `code_change` → not; undeclared → ask `lanes.json` via the placement
seam (`MissionArtifactKind.LANE_STATE`), which keeps the "one reader per artifact"
rule.

### D-4 — Only the empty-diff short-circuit's reason changes

The issue's suggested fix ("chosen before the empty-diff short circuit") is
implemented as a *reinterpretation of the empty-diff arm*: the new reason is only
reachable when `changed_files` is empty. A planning-lane WP with dirty
deliverables keeps today's behaviour (the gate scopes and may dispatch), and the
non-planning empty-diff arm keeps its existing wording, so the change cannot
widen or narrow the gate's policy (C-001, NFR-002).

### D-5 — Placement

`spec`/`research`/`tasks`/`lanes.json` resolve to the primary checkout
(`placement_seam(...).read_dir(...)` → `kitty-specs/<slug>`); tracer files and
`status.events.jsonl` live in the coordination worktree. Planning artifacts are
committed from the primary checkout onto the coordination branch.

## Open questions

- None blocking. The reason wording is an operator-facing string; the issue itself
  proposes "planning-lane WP — gate not applicable (committed diff not inspected)",
  and the mission adopts that shape so the record matches the filed acceptance
  criterion.

## Plan-phase decisions (Phase 0, appended)

### D-6 — Where the classification lives and in what order it asks

A new pair of private helpers in `tasks_move_task_gates.py`, next to the
short-circuit they serve:

1. `_mt_pre_review_planning_lane_wp(st)` — declared `execution_mode` from the WP
   frontmatter first (`extract_scalar`, the same reader
   `_mt_pre_review_scope_override` already uses on `wp.frontmatter`); an explicit
   `planning_artifact` is a yes, an explicit `code_change` is a no.
2. Only when the frontmatter is silent, ask `lanes.json`:
   `placement_seam(st.main_repo_root, st.mission_slug, owned=st.owned).read_dir(
   MissionArtifactKind.LANE_STATE)` → `read_lanes_json` →
   `manifest.lane_for_wp(st.task_id)` → `is_planning_lane(lane)`.

Rejected alternatives:
- **Reuse the resolved workspace's `execution_mode`/`lane_id`.** Truest signal, but
  the gate resolves only the workspace *path*, and the owned-checkout arm returns
  the owned root without a resolution object — reaching the resolution would mean
  a new field on the frozen `_TransitionGateInputs` (constructed positionally in
  existing tests) for information the frontmatter already carries.
- **Inspect the committed diff** (share a merge-base with `review_base_ref`
  instead of the target branch). That is #2741's larger scope, changes gate
  policy, and can start running tests on a planning lane — explicitly out (D-2,
  C-001).
- **Only check lane membership.** Mislabels a `single_branch` mission's repo-root
  code WP, which `workspace/context._resolve_repo_root_lane_arm` documents as
  legitimate. Membership must stay the fallback.

Failure policy: `read_lanes_json` raises `CorruptLanesError` (a
`GuardedReadError`) and file reads can raise `OSError`; both are caught inside
the helper and degrade to "not a planning-lane WP", i.e. today's wording. A
malformed mission file must not convert a non-blocking skip into a resolution
failure warn.

### D-7 — What the test must be built from

The reproduction fixture is a real git repository (real `git init`, real commit,
clean tree) whose branch **is** the mission's `target_branch`, with
`lanes.json` placing WP09 in `lane-planning` and WP09's frontmatter declaring
`execution_mode: planning_artifact`. Patching `_mt_pre_review_changed_files`
would defeat the point: the reported shape is the *real* empty merge-base diff.
The control arm (a `code_change` WP with an empty diff) runs on the same fixture
and asserts the incumbent wording, so a blanket rewrite of the message fails the
suite.
