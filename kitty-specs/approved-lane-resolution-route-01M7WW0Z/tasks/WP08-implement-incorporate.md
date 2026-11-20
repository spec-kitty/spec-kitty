---
work_package_id: WP08
title: implement --incorporate <lane>
dependencies: []
requirement_refs:
- FR-001
- C-004
- C-006
planning_base_branch: fix/approved-lane-resolution-route
merge_target_branch: fix/approved-lane-resolution-route
branch_strategy: Planning artifacts for this mission were generated on fix/approved-lane-resolution-route. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/approved-lane-resolution-route unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-approved-lane-resolution-route-01M7WW0Z
base_commit: 2c1a56fe6a9e857846650f6cfad7279b6eff15b1
created_at: '2026-11-20T17:56:09.595996+00:00'
subtasks:
- T014
- T015
- T016
- T017
phase: Phase 1 - Foundations
history:
- at: '2026-11-20T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- src/specify_cli/lanes/incorporate.py
- tests/lanes/test_incorporate_sibling_lane.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/lanes/incorporate.py
- src/specify_cli/cli/commands/agent/workflow.py
- tests/lanes/test_incorporate_sibling_lane.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – implement --incorporate <lane>

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Add the canonical incorporate step of the re-review route (R-01, operator ruling DM-01M7WX8AX56E23AXBZRWGNX4EM, option b):

```bash
spec-kitty agent action implement <WP> --mission <m> --incorporate <sibling lane id>
```

It runs on the canonical lane sync point (`agent action implement`), after the normal workspace materialization and claim, and merges the named sibling lane **at its newest approval stamp** (never its live tip) into this WP's lane checkout.

- A clean incorporation creates a merge commit whose second parent is exactly the sibling's stamp SHA.
- A conflict stops with the merge left in progress, lists the conflicted paths, and prints the next steps (resolve, commit, `for_review`).
- It refuses, before any side effect, for: an unknown lane; the WP's own lane; a planning (repository-root) lane; a sibling with no approval stamp; a stamp that is not on the sibling branch; a WP that is not `claimed` or `in_progress` (an approved WP that was not sent back).
- Without `--incorporate`, `implement` is byte-for-byte unchanged.

Why the stamp: `reconciliation_authorship._authoring_merges` (`src/specify_cli/consolidation/reconciliation_authorship.py:364-392`) lets a reviewed merge author what it brought in only when every non-first parent is reachable from a trusted root, and `_trusted_history_roots` (`:334-361`) trusts other approved lanes' **approval stamps**, not their live tips (#7626/#7630 trust model). A sibling merged past its stamp would fail the gate even after re-review.

## Context & Constraints

- Read: `.kittify/charter/charter.md`; mission `spec.md` (US1, US2, FR-001, C-004, C-006), `plan.md` (IC-04), `research.md` R-01, `contracts/stale-remedy.md` (WP07 prints your command), `data-model.md` (state transitions used by the route), `tasks.md`.
- Squad evidence: architect F1 and doctrine finding 2 in `squad2/` (A-10 forbids raw `git merge` in a remedy, so the route needs a CLI verb).
- **Integrity invariants**:
  - C-001: incorporating content is not approving it. The merge you create is a post-approval merge on an approved-then-sent-back lane; only a new independent review approval that reaches it makes it reviewed (WP05 refuses it otherwise). Never stamp, approve or attest anything here.
  - C-002: no new verdict-lifting flag. `--incorporate` changes no gate verdict and no status event.
  - C-004: re-approval is a real review. Do not add a shortcut that moves the WP to `for_review` or `approved` for the operator.
  - C-006 single authority: reuse `approved_bound.approval_stamp` (`src/specify_cli/consolidation/approved_bound.py:312-319`, which already skips forced non-review approvals and migration events) and `sha_reachable_from`; read status only through the status read door (`specify_cli.status.resolve_status_read`, `read_status_events`); read the lane manifest through `read_lanes_json` via the placement seam (as `lanes/lifecycle_sync.py:98-101` does); run the merge through the merge-conclusion owner `specify_cli.git.merge_conclusion.run_committing_op` (`src/specify_cli/git/merge_conclusion.py:186`). The class gate `tests/architectural/test_commit_scope_owner.py` has an empty allowlist: a raw `subprocess.run(["git", "merge", ...])` that commits will fail it.
  - Fail closed: any probe error (status unreadable, manifest corrupt, stamp unresolvable, reachability probe error) refuses with a named message; never merge on a guess.
- Agent commands consume the resolved workspace; never reconstruct a `.worktrees/` path (CLAUDE.md "Execution Workspace Strategy"; `tests/architectural/test_no_worktree_name_guess.py`). Use the `workspace.worktree_path` / `workspace.branch_name` / `workspace.lane_id` that `implement` already resolved (`ResolvedWorkspace`, `src/specify_cli/workspace/context.py:229-236`).
- Terminology: "incorporate", Mission, lane consolidation. Never "sync" in new text.

## Branch Strategy

- **Strategy**: set by finalize-tasks
- **Planning base branch**: fix/approved-lane-resolution-route
- **Merge target branch**: fix/approved-lane-resolution-route

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Implement command: `spec-kitty agent action implement WP08 --agent claude --mission approved-lane-resolution-route-01M7WW0Z`

## Current code at HEAD (read before editing)

- `src/specify_cli/cli/commands/agent/workflow.py`
  - `implement` (`:1729-2146`): options `:1731-1798`; `ImplementRequest` built at `:1829-1838`; mission/WP resolution `:1846-1876`; dependency gate `:1885`; workspace resolution `resolve_workspace_for_wp(..., write_intent=True)` `:1908`; `_ensure_workspace_materialized` `:1997` (the reuse path re-enters `reenter_lane_self_heal`, which is the lane's normal refresh); claim-ancestry gate `:2009-2040`; `_executor.implement_claim_transition` `:2045`; prompt build and print `:2092-2125`; the error funnel `:2127-2146`.
  - `_render_lane_auto_rebase_failure` (`:871-884`) shows the house style for a structured refusal print.
- `src/specify_cli/cli/commands/agent/workflow_executor.py::implement_claim_transition` (`:1133`) and its body (`:1179-1300`): an `in_progress` WP gets a resume refresh; any other lane with `--agent` tries the claim. An `approved` WP is refused there today with a generic transition error, which is why WP07's route sends it back first.
- `src/specify_cli/lanes/lifecycle_sync.py::sync_lane_after_coordination_commit` (`:83-191`): the existing lane sync point; it merges the **coordination branch** into the lane and cannot bring in a sibling after a rollback restored the Mission branch (#7755). Do not change it.
- `src/specify_cli/consolidation/approved_bound.py`: `approval_stamp` (`:312`), `approval_stamps` (`:491`), `stamp_refusal` (`:496-512`, the stamp-not-on-lane rule you mirror), `move_back_command` (`:95`).
- `src/specify_cli/lanes/models.py::LanesManifest.lane_for_wp` (`:163`); `lanes.compute.is_repo_root_lane` / `is_planning_lane`.
- `src/specify_cli/lanes/branch_naming.py::lane_branch_name` (the sibling's branch from the manifest; do not compose names by hand).

## Subtasks & Detailed Guidance

### Subtask T014 – Red tests at the CLI level

- **Purpose**: pin the behaviour of the new flag end to end before writing it. All tests are red today because the option does not exist (typer exits 2 with "No such option").
- **File**: `tests/lanes/test_incorporate_sibling_lane.py` (new). Marks: `pytest.mark.integration`, `pytest.mark.git_repo`.
- **Fixture**: a coordination Mission with two independent code lanes, both approved through the production status shell, following `tests/terminus/post_approval_support.py:103-151` (`allocate_lane_worktree`, `tests.terminus.mixed_lane_support.transition`, `tests.terminus.canceled_dependency_support._commit_in`, `_approve`). Lane-a (WP01) and lane-b (WP02) both edit `src/pkg/shared.py`; for the conflict case they edit adjacent lines (assert `kernel.git.listing.merge_tree(repo, lane_b_branch, lane_a_stamp).conflicted` is non-empty as a precondition); for the clean case they edit distant lines (assert `conflicted == ()`). Then send WP02 back with the production shell (`transition(mission, "WP02", "in_progress", actor=..., review_ref=...)`), the same state `move-task WP02 --to in_progress` produces. Invoke the CLI through `tests.terminus.conftest.run_terminus(mission, ["agent", "action", "implement", "WP02", "--agent", <implementer>, "--mission", slug, "--incorporate", "lane-a"])`.
- **Tests**:
  1. `test_clean_incorporate_merges_the_sibling_stamp`: exit 0; lane-b's tip is a merge whose parents are `[previous lane-b tip, lane-a stamp]` (read the stamp with `approved_bound.approval_stamp` from the status events, not from the lane tip); the merge message names the sibling lane and the stamp. Add one bookkeeping-only commit on lane-a **after** its approval (`kitty-ops/lifecycle/<ulid>.json`, as `test_lifecycle_closure_on_approved_lane_7346.py:22-24` does) so the stamp differs from the live tip: the test then fails if the code merges the live tip.
  2. `test_conflict_leaves_merge_in_progress`: exit code equals `INCORPORATE_CONFLICT_EXIT` (non-zero, distinct from 1 and 2, per the operator ruling); `MERGE_HEAD` equals the stamp in lane-b's checkout; output lists `src/pkg/shared.py` and the next steps; no commit was made.
  3. Refusals, each with its named code in the output and **no change** to lane-b's tip, its checkout, or the status log (compare `status.events.jsonl` bytes before/after):
     - `INCORPORATE_LANE_UNKNOWN` (`--incorporate lane-z`);
     - `INCORPORATE_OWN_LANE` (`--incorporate lane-b`);
     - `INCORPORATE_PLANNING_LANE` (a repository-root lane id, if the fixture has one; else a unit test on `lanes.incorporate` with a hand-built manifest);
     - `INCORPORATE_NO_APPROVAL_STAMP` (strip lane-a's stamps with `post_approval_support.strip_approval_stamps`);
     - `INCORPORATE_STAMP_NOT_ON_LANE` (rewrite lane-a with `git reset --hard <stamp>~1` then a new commit, so the recorded stamp is unreachable);
     - `INCORPORATE_WP_NOT_SENT_BACK` (WP02 still `approved`; the message prints `move_back_command("WP02", slug)`).
  4. `test_without_flag_implement_is_unchanged` (a **ratchet**, green at the base by construction; record it as such): same fixture, no flag. BEFORE any production edit, run the command on the fixture at the WP08 base and record its output as a golden stored inline in the test module (a string literal, or a tuple of lines): stdout and stderr (via `collapse`/`flat`), with volatile tokens normalised by one helper in the test (`_normalise(text)`: replace commit SHAs, ULIDs/event ids, timestamps, `tmp_path` and the isolated `HOME` with fixed placeholders; nothing else). Assert the normalised output equals the golden exactly, and the exit code equals the recorded one. Absence of the substring "incorporat" is NOT an acceptable assertion. Build the fixture twice and assert the two normalised outputs are equal first (determinism precondition), so the golden is not flaky. Never regenerate the golden after the production change without a recorded reason in history.
- **Validation**: record the red run in the WP history.

### Subtask T015 – New module `lanes/incorporate.py`

- **Purpose**: one small, testable unit that resolves the sibling and its stamp, checks preconditions, and performs the merge. No CLI printing here.
- **Shape** (adapt names, keep the responsibilities):

```python
class IncorporateCode(StrEnum):
    LANE_UNKNOWN = "INCORPORATE_LANE_UNKNOWN"
    OWN_LANE = "INCORPORATE_OWN_LANE"
    PLANNING_LANE = "INCORPORATE_PLANNING_LANE"
    NO_APPROVAL_STAMP = "INCORPORATE_NO_APPROVAL_STAMP"
    STAMP_NOT_ON_LANE = "INCORPORATE_STAMP_NOT_ON_LANE"
    WP_NOT_SENT_BACK = "INCORPORATE_WP_NOT_SENT_BACK"
    CHECKOUT_BUSY = "INCORPORATE_CHECKOUT_BUSY"        # merge already in progress / dirty tracked files
    PROBE_FAILED = "INCORPORATE_PROBE_FAILED"

@dataclass(frozen=True)
class SiblingStamp: lane_id: str; branch: str; stamp: str; wp_ids: tuple[str, ...]

@dataclass(frozen=True)
class IncorporateOutcome: sibling: SiblingStamp; merged: bool; already_present: bool; merge_sha: str | None; conflicted_paths: tuple[str, ...]; checkout: Path

class IncorporateRefused(RuntimeError): code: IncorporateCode; message: str

def check_wp_may_incorporate(lane: Lane, wp_id: str, mission_slug: str) -> None
def resolve_sibling_stamp(repo_root, mission_slug, manifest, own_lane_id, sibling_lane_id, events) -> SiblingStamp
def incorporate_sibling(checkout: Path, sibling: SiblingStamp, *, mission_slug: str) -> IncorporateOutcome
```

- **Steps**:
  1. `resolve_sibling_stamp`: find the lane by id in `manifest.lanes` (unknown → `LANE_UNKNOWN`); same as the WP's lane → `OWN_LANE`; `is_repo_root_lane` / `is_planning_lane` → `PLANNING_LANE`. Branch via `lane_branch_name(mission_slug, lane_id, target_branch=manifest.target_branch)` (the same composer `lanes/consolidation.py:316-320` uses).
  2. Stamps: for the sibling's WPs whose current lane (reduced from `events`) is `approved` or `done`, read `approval_stamp(events, wp_id)`. No such WP or every stamp `None` → `NO_APPROVAL_STAMP`. A sibling WP that is approved with no stamp while another has one: refuse `NO_APPROVAL_STAMP` naming that WP (the unstamped WP's content cannot be shown reviewed).
  3. Newest stamp: the stamp from which every other stamp is reachable (`sha_reachable_from`). If none qualifies (stamps diverged), refuse `STAMP_NOT_ON_LANE` with the stamps listed. Then the chosen stamp must be reachable from the sibling branch tip, else `STAMP_NOT_ON_LANE` (mirror `stamp_refusal`). Any `GitProbeError` → `PROBE_FAILED`.
  4. `incorporate_sibling`: refuse `CHECKOUT_BUSY` when `MERGE_HEAD`/`REBASE_HEAD`/`CHERRY_PICK_HEAD` exist, or when tracked files are modified (`kernel.git.status_entries`). If the stamp is already reachable from `HEAD`, return `already_present=True` without merging. Else run `run_committing_op(checkout, "merge", ["--no-ff", "-m", message, stamp], env=<merge env>, disable_gpgsign=False)`. Message: `Incorporate <sibling lane> at approval stamp <stamp12> (spec-kitty implement --incorporate)`. Exit 0 → `merged=True`, `merge_sha=HEAD`. Non-zero with unmerged entries (`git diff --name-only --diff-filter=U`) → `merged=False`, `conflicted_paths=...`, merge left in progress. Non-zero with no unmerged entries → raise `PROBE_FAILED` with git's stderr (do not abort silently; leave the tree as git left it and say so).
  5. Merge environment: use the same environment the auto-rebase merges with so spec-kitty's registered merge drivers are honoured (`lanes/consolidation._make_merge_env` is private to that module; if no public accessor exists, use `os.environ` copy plus nothing else and note that sibling lanes carry no status files in a lane checkout, sparse exclusion, `lanes/lane_checkout.py::open_lane_checkout`). Record the choice in the WP history.
  6. Keep every function at complexity ≤ 15; the module has no `print`.
- **Notes**: `lanes/incorporate.py` importing `specify_cli.consolidation.approved_bound` is within `specify_cli` (no layer rule crosses), but check `python -c "import specify_cli.lanes.incorporate"` for cycles; prefer a function-local import of `approved_bound` if a cycle shows.

### Subtask T016 – The `--incorporate` option on `agent action implement`

- **Purpose**: wire the module into the canonical lane sync point.
- **Steps**:
  1. Add the option to `implement` (`workflow.py:1731-1798`): `incorporate: Annotated[str | None, typer.Option("--incorporate", help="Merge the named sibling lane, at its newest approval stamp, into this work package's lane checkout. Stops on a conflict for hand resolution. Only for a work package that is claimed or in progress.")] = None`. Add it to `ImplementRequest` only if that type is in this file; otherwise keep it as a local.
  2. **Precondition check before any side effect**: right after `wp = _executor.implement_locate_wp(...)` (`:1875`) and before the charter precondition, when `incorporate` is set: read the status via the read door, reduce, and call `check_wp_may_incorporate`. A WP in `approved`/`done`/`for_review`/`in_review` refuses `INCORPORATE_WP_NOT_SENT_BACK` printing `move_back_command(wp, slug)` (with `--force --note "<why>"` for `done`). A `planned` WP refuses too: there is nothing to resolve yet. Also resolve the sibling stamp here (manifest + events), so every refusal of T014 test 3 happens before the workspace or the claim is touched.
  3. **Merge after the normal refresh**: after `_executor.implement_claim_transition(...)` returns (`:2045-2060`; for an `in_progress` WP this is the resume refresh and its commit, which also runs the lifecycle sync point), call `incorporate_sibling(workspace_path, sibling, mission_slug=...)`. A repository-root workspace (`workspace.runs_in_checkout_root`) refuses `PLANNING_LANE` (single_branch and planning work have no lane to incorporate into).
  4. Re-check the sibling stamp right before merging (cheap; the status log may have moved between the precondition read and the merge, e.g. a re-approval of the sibling). If it changed, use the new one and say so.
  5. Print the outcome (T017) and then continue to print the WP prompt as today, so the implementer has its instructions.
  6. Catch `IncorporateRefused` in `implement`'s existing error funnel (`:2127-2146`) with its own branch that prints `Error: <code>: <message>` and exits 1, like the `FeatureStatusLockTimeoutError` branch.
- **Edge cases**: `--incorporate` together with `--force` (operator override of the review lane): refuse the combination with a clear message; the route never forces. `--incorporate` given twice: typer keeps the last; document one sibling per invocation (WP07 prints one line per sibling).

### Subtask T017 – Messages and exit behaviour

- **Purpose**: the operator (or agent) knows exactly what happened and what to run next.
- **Operator ruling (2026-11-20, overrides the earlier exit-0 draft)**: on a conflict `implement --incorporate` exits NON-ZERO so scripts notice. Use a distinct exit code held in one module constant (for example `INCORPORATE_CONFLICT_EXIT = 3`, distinct from refusals' exit 1 and typer's usage exit 2). It still leaves the merge in progress and prints the conflict block and the next steps (resolve, commit, move to for_review). Document the code in the command's `--help` text for `--incorporate` and in the printed message. Tests assert the constant's value, never a literal.
- **Text** (one block, before the prompt):
  - merged: `Incorporated lane-a at approval stamp <stamp12> into <lane checkout> (merge <sha12>).`
  - already present: `lane-a's approval stamp <stamp12> is already in this lane; nothing to incorporate.`
  - conflict:
    ```
    INCORPORATE STOPPED ON A CONFLICT: lane-a at approval stamp <stamp12> into <lane checkout>
      conflicted: src/pkg/shared.py
    Next:
      1. Resolve the conflicts in <lane checkout> and commit the merge there.
      2. spec-kitty agent tasks move-task WP02 --to for_review --mission <slug>
      3. An independent reviewer reviews WP02 and approves it; the new approval must reach the resolution merge.
      4. spec-kitty consolidate --mission <slug>
    ```
  - The checkout path printed is `workspace.worktree_path` (the resolved workspace), never a composed glob.
- **Never print** `git merge` (A-10) or `cd .worktrees`. Concluding the merge with a commit inside the named checkout is the resolve step, worded as in `contracts/stale-remedy.md`.

## Test Strategy

Red first. Targeted commands:

```bash
uv run --frozen pytest -q tests/lanes/test_incorporate_sibling_lane.py
uv run --frozen pytest -q tests/lanes/test_stale_remediation_cli_command.py tests/lanes/test_auto_rebase_additive.py
uv run --frozen pytest -q tests/specify_cli/cli/commands/agent/test_workflow_cores.py tests/agent/test_workflow_mixed_dependency_review_context.py
uv run --frozen pytest -q tests/terminus/test_post_approval_commit_refused.py tests/terminus/test_lifecycle_closure_on_approved_lane_7346.py
uv run --frozen pytest -q tests/architectural/test_commit_scope_owner.py tests/architectural/test_no_worktree_name_guess.py tests/architectural/test_merge_pipeline_ratchets.py tests/architectural/test_layer_rules.py tests/architectural/test_no_legacy_terminology.py
make test-fast
```

Also run every test file that imports `specify_cli.cli.commands.agent.workflow` implement paths: `grep -rl "action\", \"implement\"\|agent action implement" tests/ --include="*.py"` and pick the implement-focused ones (for example `tests/specify_cli/cli/commands/agent/` implement tests; note `tests/specify_cli/cli/commands` is out-of-matrix in CI, run the files you touch locally). No `make test-full`, no bare `tests/architectural/`.

Quality gates:

```bash
uv run --frozen ruff check src/specify_cli/lanes/incorporate.py src/specify_cli/cli/commands/agent/workflow.py tests/lanes/test_incorporate_sibling_lane.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/lanes/incorporate.py src/specify_cli/cli/commands/agent/workflow.py tests/lanes/test_incorporate_sibling_lane.py
uv run --frozen mypy src/specify_cli/lanes/incorporate.py src/specify_cli/cli/commands/agent/workflow.py
```

`implement` is already long: add the new steps as one-line calls to helpers so its complexity does not grow past its current measure (and new helpers stay ≤ 15). No suppressions.

## Tracer notes

Record notes with `spec-kitty agent tasks add-history WP08 --note "<trace: ...> ..."` for `traces/tooling-friction.md`, `traces/approach.md`, `traces/design-decisions.md`: the exit-0-on-conflict decision; the merge environment choice; the new `INCORPORATE_*` codes (WP13 documents them; they are not in `contracts/refusal-codes.md`, which lists only gate and rollback codes); any friction with the lane checkout's sparse status exclusion (#5965) during the merge.

## Risks & Mitigations

- **Merging the live tip instead of the stamp** would make the route fail the gate after re-review. Mitigation: T014 test 1 puts a bookkeeping commit after the stamp.
- **Side effects before refusal.** Mitigation: precondition and stamp resolution before workspace materialization; tests compare the status log bytes and lane tip.
- **Lane checkout sparse exclusion** may surface status-file residue during the merge (#5965). Mitigation: the sibling lane branch carries no status files; if friction shows, record it as a tracer note and an issue, do not widen the exclusion here.
- **Commit-scope gate.** Use `run_committing_op`; a raw committing `git merge` fails `test_commit_scope_owner.py`.
- **Concurrency**: the merge runs outside the Mission write lock (the claim transition releases it). The lane checkout is owned by this WP's implementer; refuse `CHECKOUT_BUSY` on any in-progress operation.

## Review Guidance

Anti-fake checks (from `squad2/reviewer-renata.md` and architect F1):

- **Stamp, not tip**: the merge's second parent equals the newest approval stamp, proven against a sibling whose live tip is past the stamp.
- **Real conflict**: the conflict test asserts `merge-tree` reports a conflict as a fixture precondition, and asserts `MERGE_HEAD` afterwards.
- **No approval shortcut** (C-004): `--incorporate` emits no status event and no review artifact; the WP stays `in_progress`.
- **Refusals have no side effects**: lane tip, checkout and event log unchanged for each refusal code.
- **Unchanged without the flag**: test 4 compares against a golden recorded at the base (normalised volatile tokens only), not against the absence of a substring.
- **A-10 kept**: no `git merge` or `cd .worktrees` in any printed text.
- Confirm ruff, `ruff format --check --force-exclude` and mypy ran clean on the changed files.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP08 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP08 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
