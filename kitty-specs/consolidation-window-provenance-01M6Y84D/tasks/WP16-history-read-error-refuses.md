---
work_package_id: WP16
title: A history-read error is never a deletion (#5048(b))
dependencies:
- WP15
requirement_refs:
- FR-014
- NFR-002
- NFR-010
- SC-004
planning_base_branch: feat/consolidation-window-provenance
merge_target_branch: feat/consolidation-window-provenance
branch_strategy: Planning artifacts for this mission were generated on feat/consolidation-window-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidation-window-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T083
- T084
- T085
- T086
phase: Phase 4 - Behaviour changes, red-first
history:
- at: '2026-11-08T19:52:39Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/reconciliation_authorship.py
create_intent:
- src/specify_cli/consolidation/reconciliation_authorship.py
- tests/consolidation/test_reconciliation_intended_verdicts.py
- tests/consolidation/characterization/verdict_corpus.json
- tests/consolidation/test_authored_walk_read_error.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/reconciliation_authorship.py
- tests/consolidation/test_authored_walk_read_error.py
- tests/consolidation/test_reconciliation_intended_verdicts.py
- tests/consolidation/characterization/verdict_corpus.json
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP16 – A history-read error is never a deletion (#5048(b))

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP16 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

While collecting an approved lane's authored content, the gate walks the lane's first-parent spine newest to oldest and records, per path, the final blob or "deleted". Today **any** error from the blob read is taken to mean "the file was deleted" (the deletion-inference defect of #5048(b), spec US4 (a)). A read failure then becomes a trusted deletion. This work package makes the walk tell the two apart (FR-014, research R-10, plan IC-14):

1. `_final_authored_walk` reads each path's state with `git_probes.path_state_at`. `None` (path absent at its newest touching commit) is a **genuine deletion** and is recorded exactly as today. A `GitProbeError` is a **read failure**: it propagates, so the claim refuses through the **existing** claim-time probe-error channel, naming the path and the error. No new refusal code, no new wording constant.
2. Still **one** git read per path (the `path_state_at` call replaces the `blob_id_at` call) and still **one** spine walk (`tests/consolidation/test_presence_lane_base.py` pins it).
3. A red-first test drives `consolidate` **in process** and is committed failing before the fix (NFR-002, NFR-010). It asserts that no branch moved.
4. A positive control (a genuine deletion on the same fixture) passes before and after the fix (US4-2).
5. The NFR-002 **(d)** intended-verdict pin `test_history_read_error_refuses_instead_of_deleting` loses its strict `xfail` marker in the fix commit, and only the golden-corpus cell(s) of scenario (d) change.

**NFR-002 flip covered: (d)** (FR-014, a history-read error). SC-004 (first half).

## Context & Constraints

- `kitty-specs/consolidation-window-provenance-01M6Y84D/spec.md` — US4 (a) and acceptance 1-2, FR-014, NFR-002 (d), NFR-010, C-004, SC-004.
- `kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md` — IC-14 (Purpose, Risks: no new refusal code, no second read, keep the single walk).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/research.md` — R-10.
- The code **before Phase 3** (for orientation; after WP15 the walk lives in `src/specify_cli/consolidation/reconciliation_authorship.py`, re-exported by the facade `reconciliation.py` — locate it by symbol name, not by line):
  - `reconciliation.py:3675-3728` `_final_authored_walk`. The defect is lines 3724-3727:
    ```python
    try:
        blobs.add((path, blob_id_at(repo_root, sha, path)))
    except GitProbeError:
        deletions.add(path)  # deleted at this (newest touching) commit — final state deleted
    ```
  - Its callers: `_collect_authored` (`:3936`, three call sites `:4016`, `:4061`, `:4067`), `_presence_lane_content` (`:3908`, `:3932`), `_verify_declared_ref` (`:3613`, `:3652`, already inside `except GitProbeError` → `_REFUSE_DEPENDENCY_PROBE`), and the thin wrappers `_final_authored_blobs` / `_final_authored_deletions` (`:3731`, `:3742`).
  - `git_probes.py:666-694` `path_state_at`: `git ls-tree --full-tree -z <ref> -- <path>` through `kernel.git.listing.tree_entry` (exact-path match, `src/kernel/git/listing.py:322`). Returns the blob id, `None` when the path is absent, raises `GitProbeError` only when the ref cannot be read.
  - `git_probes.py:565-588` `blob_id_at`: raises `GitProbeError` for an absent path **and** for a failed read. That is why the walk cannot tell them apart today.
- How a `GitProbeError` from the claim builder surfaces today (the "existing unreadable-history refusal wording" IC-14 tells you to reuse — do **not** add a new one):
  - Fresh run and resume: `phase_claim.py:533` `except GitProbeError as exc: _exit_on_claim_probe_error(exc)` (`phase_claim.py:792-806`): prints `Reconciliation refused (fail-closed): a git probe failed while building the approved-WP claim: {exc}. ... no refs/worktrees were mutated.` and exits 1, strictly before the first mutation.
  - Forecast: `forecast.py:447` prints `the closed-world reconciliation window could not be read ({exc}); ...` with `CLAIM_REFUSED_FORECAST`, exit 1.
  - Declared external dependency refs: `_verify_declared_ref` turns it into `_REFUSE_DEPENDENCY_PROBE` (`DEPENDENCY_REF_UNVERIFIABLE`).
  - Gate defensive rebuild (`phase_gate.py:72`, only when no claim was captured): propagates into the rollback door; unchanged.
- Test helpers you reuse (do not copy them):
  - `tests/consolidation/characterization_support.py` (WP02): `build_shape`, `run_in_process`, `regenerate_cells`, `assert_cells_match`.
  - `tests/consolidation/reconciliation_family.py` (WP04): `setattr_reconciliation_family(monkeypatch, name, value)`, `family_modules_binding(name)`.
  - `tests/terminus/rollback_harness.py`: `ref_shas`, `reflog_shas`.
  - The WP05 pin `tests/consolidation/test_reconciliation_intended_verdicts.py::test_history_read_error_refuses_instead_of_deleting` and its helper `_failing_probe_for(path)`.
- Cross-cutting: C-009 (no rollback or branch-restore caller outside `rollback.py`), C-013 (targeted runs only, never `make test-full`), C-014 (ruff, ruff format, mypy: zero findings, no new suppressions), NFR-004 (complexity <= 15), NFR-005 (0 new allowlist entries), NFR-009 (changed-line coverage >= 90%), C-004 (only the named (d) cells change).

## Branch Strategy

- **Strategy**: Planning artifacts were generated on kitty/mission-consolidation-window-provenance-01M6Y84D; completed changes must merge into feat/consolidation-window-provenance.
- **Planning base branch**: feat/consolidation-window-provenance
- **Merge target branch**: feat/consolidation-window-provenance

> Populated by `finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP16 --agent <name> --mission consolidation-window-provenance-01M6Y84D
```

## Commit plan (red first)

Make exactly these commits, in this order. Reviewers check the order with `git log --oneline`.

1. **Red commit** — `test(consolidation): red-first #5048(b) history-read error is a deletion (WP16)`: adds `tests/consolidation/test_authored_walk_read_error.py` with the T083 test and the T084 control. The T083 test **fails** on this commit; the control passes. Paste the failing pytest summary line and the commit SHA into the WP history note.
2. **Fix commit** — `fix(consolidation): a history-read error refuses the claim instead of recording a deletion (#5048(b), WP16)`: T085 + T086 (production fix, the WP05 pin's marker removal and retarget, the (d) golden cells).

Do not squash them. Do not amend the red commit after the fix.

## Subtasks & Detailed Guidance

### Subtask T083 – Red-first test through in-process `consolidate`

- **Purpose**: Prove the defect through the entry point the operator runs, and prove the fix stops it before anything moves (NFR-010). A real git history-read failure on one path is hard to produce, so the probe is patched at its lookup home (plan IC-14).
- **File**: `tests/consolidation/test_authored_walk_read_error.py` (new). Mark the module `pytest.mark.integration` and `pytest.mark.git_repo`, like `tests/consolidation/test_approved_bound_residuals.py`.
- **Fixture**:
  1. `mission = build_shape(tmp_path, "single_lane")` (a coordination Mission whose approved lane spine modifies at least one source path). Pick `P` = a non-bookkeeping path the lane's newest touching commit **modifies** (not deletes). Find `touch_sha`, the newest commit on the lane's first-parent spine that touches `P` (`git rev-list --first-parent <coord base>..<lane branch> -- P | head -1`, or the first match in `tests/terminus/canceled_dependency_support.first_parent_shas`): the walk reads `P` at exactly that commit.
  2. Build one fake that raises for **both** probe names, so the test reaches the walk before and after the fix:
     ```python
     def _failing_probe(original, *, path, touch_sha):
         def fake(repo_root, ref, p):
             if p == path and ref == touch_sha:
                 raise GitProbeError(f"injected history-read failure for {p}")
             return original(repo_root, ref, p)
         return fake
     ```
     Patch `blob_id_at` and `path_state_at` with `setattr_reconciliation_family(monkeypatch, name, _failing_probe(<original>, path=P, touch_sha=touch_sha))`. Raising **only for the lane commit that touches P** (post-tasks squad pedro #3) keeps every other read untouched: the verifier's gate-time target-tree reads (`blob_id_at(target_ref, path)`, `reconciliation.py` ~1370/~1596, and `path_state_at` ~1009-1076) and any other spine commit. A wider fake makes today's run refuse at the gate and roll back, which can look like the fix.
  3. Precondition (raise `RuntimeError`, never `assert`, so a broken fixture errors instead of looking like the defect): `family_modules_binding("path_state_at")` and `family_modules_binding("blob_id_at")` are non-empty; `P` is in the lane's changed paths.
- **Test `test_history_read_error_refuses_the_claim_and_moves_nothing`**:
  1. Record `before = ref_shas(mission)` and `reflog_before = {b: reflog_shas(mission, b) for b in (target, coord)}`.
  2. `result = run_in_process(mission, ["consolidate", "--mission", mission.slug, "--yes"])`.
  3. Assert: `result.exit_code == 1`; the output contains `a git probe failed while building the approved-WP claim`; the output names `P`; the output contains `injected history-read failure`.
  4. Assert no branch moved: `ref_shas(mission) == before` **and** each reflog is unchanged. The reflog check is the one that tells a claim-time refusal apart from a gate FAIL that moved the target and rolled it back.
  5. Assert the refusal was **claim-time, before any mutation**: the output contains `no refs/worktrees were mutated` (`phase_claim._exit_on_claim_probe_error`) and no pre-mutation snapshot remains (`rollback_harness.state_path(mission)` absent, or its `pre_mutation_refs` empty).
- **Why it is red on the parent**: there the walk calls `blob_id_at`, the fake raises, the walk records a deletion of `P`, the claim builds, and the run continues past claim time (it then passes or gate-FAILs with a rollback). Either way the claim-refusal text is absent and/or the reflog changed. Before committing, read the failure output and confirm it fails **for that reason** (not a fixture error). Record which of the two happened today (pass, or gate FAIL + rollback) with `spec-kitty agent tracer-append --category design-decisions`; it should match the (d) golden cell WP02 recorded.
- **Do not**: write `state.json` by hand; use the subprocess `run_terminus` (a monkeypatch cannot reach a child process); patch `specify_cli.consolidation.git_probes.<name>` (the walk does not look the name up there; the WP04 guard would flag it).

### Subtask T084 – Genuine-deletion positive control

- **Purpose**: A real deletion must still be recorded as a deletion (US4-2). This control must pass on the red commit **and** after the fix.
- **File**: same module.
- **Fixture**: same `single_lane` shape, plus one extra commit on the lane (in its worktree, `tests/terminus/post_approval_support.lane_worktree`) that **deletes** a path `D` the lane added earlier, committed before the approval stamp is taken. If the builder approves before you can add it, re-approve at the new tip with `tests/terminus/conftest.restamp_approvals_at_lane_tips(mission)` so the approved bound does not refuse the deletion commit. No probe patch.
- **Tests**:
  - `test_genuine_deletion_is_still_recorded_and_lands`: run `consolidate --mission <slug> --yes` in process; assert exit 0 and that `D` is absent from the target tree after landing (`git cat-file -e <target>:<D>` fails).
  - `test_final_authored_walk_records_an_absent_path_as_deleted` (unit, fast): call the walk through the facade (`from specify_cli.consolidation.reconciliation import _final_authored_walk`) on the lane spine; assert `D in deletions` and `D not in {p for p, _ in blobs}`.
  - `test_final_authored_walk_propagates_a_read_failure` (unit): patch `path_state_at` via `setattr_reconciliation_family` to raise for one path; call the walk; assert `pytest.raises(GitProbeError)` and that the message names the path. **This unit test is red on the red commit too** — that is fine, but put it in the fix commit instead (keep the red commit's only failing test the T083 entry-point test). Note it in the history.
- **Notes**: Keep the existing unit tests `tests/consolidation/test_reconciliation.py::test_final_authored_deletions_add_then_delete_is_recorded` and `::test_final_authored_deletions_delete_then_readd_is_not_recorded` green and unchanged; they are also positive controls.

### Subtask T085 – The fix with `path_state_at`

- **File**: `src/specify_cli/consolidation/reconciliation_authorship.py` (the walk's home after WP15).
- **Steps**:
  1. Replace the `try: blob_id_at ... except GitProbeError: deletions.add(path)` block with:
     ```python
     try:
         state = path_state_at(repo_root, sha, path)
     except GitProbeError as exc:
         raise GitProbeError(f"reading {path} at {sha[:10]} on the lane spine failed: {exc}") from exc
     if state is None:
         deletions.add(path)  # absent at its newest touching commit: final state deleted
     else:
         blobs.add((path, state))
     ```
     The re-raise names the path and the commit whatever the probe's own message says (FR-014: "naming the path and error"). Keep the `GitProbeError` type so every existing handler (claim, forecast, declared ref) catches it unchanged.
  2. Import `path_state_at` into `reconciliation_authorship.py` from `specify_cli.consolidation.git_probes` the way the module imports its other probes. If `blob_id_at` is now unused in this module, remove its import (ruff F401 will tell you); do **not** remove it from the facade's re-exports if `tests/consolidation/reconciliation_surface.json` pins it there — check `uv run --frozen pytest -q tests/consolidation/test_reconciliation_surface_pin.py`. If the surface pin requires the name on a module that no longer imports it, stop and ask the orchestrator; do not edit the surface JSON to drop a pinned name.
  3. Update the walk's docstring: replace the sentence "A path whose newest touching commit deletes it has no blob at that commit (:func:`blob_id_at` raises); it is marked seen and recorded in ``deletions``" with the `path_state_at` rule (`None` = deleted; a raised `GitProbeError` = unreadable, propagated so the claim refuses, #5048(b)).
  4. No other caller changes. `_collect_authored`, `_presence_lane_content` and the wrappers already let the error propagate; `_verify_declared_ref` already converts it. Do not add `try/except` in callers.
- **Checks**:
  - One read per path: the walk still makes exactly one probe call per newly seen path.
  - `tests/consolidation/test_presence_lane_base.py` (pins the single walk) stays green.
  - Complexity: `uv run --frozen ruff check --select C901 src/specify_cli/consolidation/reconciliation_authorship.py`.

### Subtask T086 – Flip the NFR-002 (d) pin and regenerate only its golden cells

- **Steps**:
  1. In `tests/consolidation/test_reconciliation_intended_verdicts.py`, remove the `@pytest.mark.xfail(strict=True, raises=AssertionError, ...)` marker from `test_history_read_error_refuses_instead_of_deleting`. Retarget its fake from `blob_id_at` to `path_state_at` (WP05's `_failing_probe_for(path)` helper was written for this). Restrict the fake to the lane spine refs as in T083 if it is not already. It must now **pass**.
  2. Find the (d) cells in the golden file. WP02 gave named cells a variant suffix; list candidates with:
     ```bash
     uv run --frozen python -c "import json;d=json.load(open('tests/consolidation/characterization/verdict_corpus.json'));c=d.get('cells',d);print([k for k in c if 'read' in k or '5048' in k])"
     ```
     Record the exact keys in the history note.
  3. Regenerate **only** those keys with WP02's `regenerate_cells(names)` (or its documented command-line switch for named cells). Never regenerate the whole file.
  4. Prove the golden diff is a subset of the (d) cells, **against the parent of the red commit** (post-tasks squad R-01/R-03; comparing with `HEAD:` prints `[]` once the regeneration is committed):
     ```bash
     RED=<the red commit's SHA from your history note>
     uv run --frozen python -c "from tests.consolidation.characterization_support import changed_cells; print(changed_cells('$RED^'))"
     ```
     Run it after the fix commit and again on the final commit. The printed list must equal the (d) keys. If any other cell changed, stop: the fix changed a verdict outside NFR-002 (C-004). Investigate and fix the code, never the golden.
  5. Expected new verdict in the (d) cells: refused at claim time (exit 1, the claim-probe text), for every mode the cell covers (fresh, resume, and forecast if WP02 recorded a forecast variant: the forecast reports `CLAIM_REFUSED_FORECAST`).

## Test Strategy

Red-first, ATDD: the entry-point test is written and committed failing before any production line changes; unit tests sit alongside, never instead (NFR-010).

## Definition of Done

Run exactly these and paste each final summary line into the WP history note:

```bash
uv run --frozen pytest -q tests/consolidation/test_authored_walk_read_error.py
uv run --frozen pytest -q -rxX tests/consolidation/test_reconciliation_intended_verdicts.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation.py tests/consolidation/test_presence_lane_base.py tests/consolidation/test_dependency_ref_claim.py tests/consolidation/test_approved_content_presence.py tests/consolidation/test_git_probes_seam.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_surface_pin.py tests/consolidation/test_reconciliation_family_guard.py tests/consolidation/test_refusal_precedence_matrix.py tests/consolidation/test_reconciliation_seeded_mutations.py
uv run --frozen pytest -q tests/consolidation/test_single_rollback_authority.py
uv run --frozen pytest -q -n auto --dist loadfile tests/consolidation/
uv run --frozen ruff check src/specify_cli/consolidation/reconciliation_authorship.py tests/consolidation/test_authored_walk_read_error.py tests/consolidation/test_reconciliation_intended_verdicts.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/consolidation/reconciliation_authorship.py tests/consolidation/test_authored_walk_read_error.py tests/consolidation/test_reconciliation_intended_verdicts.py
uv run --frozen mypy src/specify_cli/consolidation/reconciliation_authorship.py tests/consolidation/test_authored_walk_read_error.py
make test-fast
```

- [ ] Red evidence: the red commit SHA and the failing summary line of `test_history_read_error_refuses_the_claim_and_moves_nothing` on it are in the history note (and later in the PR's *Tests run*). The control `test_genuine_deletion_is_still_recorded_and_lands` passed on the red commit too. **Because lane SHAs can become unreachable after a squash consolidation with cleanup** (post-tasks squad R-14), also paste, for each red test, its full test id and the assertion message pytest printed (`uv run --frozen pytest -q -rf <test>` at the red SHA), so the PR and the post-merge mission review can check the red without checking out the SHA.
- [ ] `-rxX` shows `test_history_read_error_refuses_instead_of_deleting` as **passed** (no longer XFAIL) and every other intended-verdict test still XFAIL; zero XPASS.
- [ ] Golden diff = exactly the (d) cell keys (script in T086 step 4); keys recorded in the history.
- [ ] No new refusal code or wording constant; no new `try/except` outside the walk; one probe call per path.
- [ ] No new `# noqa` / `# type: ignore`; the walk <= 15 complexity.
- [ ] **Tracer files** (canonical writer only, no hand edits of `traces/*.md`, no `add-history` fallback; post-tasks squad R-02): `spec-kitty agent tracer-append --mission consolidation-window-provenance-01M6Y84D --category design-decisions --actor "implement WP16" --entry "<summary>. <detail>"` for today's verdict on the (d) fixture before the fix (pass or gate FAIL + rollback); the re-raise wording; the (d) keys; and the one-sentence operator-visible Before/After of the fix, which WP21 turns into the `7403-history-read-error-refuses.fixed.md` fragment (so this WP's reviewer checks the claim); `--category tooling-friction` for any friction. The command works from any checkout (lane worktree included) and commits to the coordination surface itself.
- [ ] Never run `make test-full`.

## Risks & Mitigations

- **Collateral patch**: patching `blob_id_at` across the family also hits the verifier. The `ref in spine` restriction keeps the verifier's target reads untouched.
- **Vacuous red**: a fake that the walk never calls would also "fail" the test. The precondition checks the names are bound in the family, and you read the red failure output before committing.
- **Second git read**: `path_state_at` replaces `blob_id_at`; do not call both.
- **Shared-prerequisite blast radius**: the walk feeds the authorship, presence and declared-ref axes. Their tests are in the DoD; the corpus catches any other verdict change.
- **`ls-tree` semantics**: `tree_entry` matches the exact path (`--full-tree`, entry equality), so glob characters in file names cannot widen the match.

## Review Guidance

- Reviewer profile: `reviewer-renata`.
- **Model tier: mid** (bounded change against a clear oracle: the corpus, the pin and the entry-point test).
- Check out the red commit and run `tests/consolidation/test_authored_walk_read_error.py`: the T083 test fails for the stated reason, the control passes. Then check out the fix commit: both pass.
- Confirm the golden diff touches only the (d) keys, and that the WP05 pin lost exactly its marker.
- Confirm no handler was added in callers and the claim-probe wording is unchanged (`phase_claim._exit_on_claim_probe_error`).

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP16 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP16 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`
