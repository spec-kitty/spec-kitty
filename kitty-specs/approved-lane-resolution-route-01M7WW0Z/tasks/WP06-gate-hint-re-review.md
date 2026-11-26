---
work_package_id: WP06
title: Gate hint names re-review for dropped merges
dependencies:
- WP01
- WP04
requirement_refs:
- FR-006
planning_base_branch: fix/approved-lane-resolution-route
merge_target_branch: fix/approved-lane-resolution-route
branch_strategy: Planning artifacts for this mission were generated on fix/approved-lane-resolution-route. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/approved-lane-resolution-route unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-approved-lane-resolution-route-01M7WW0Z
base_commit: 28452d1f50373f51506ed1127d3f5fc08b887347
created_at: '2026-11-25T09:40:02.096970+00:00'
subtasks:
- T029
- T030
- T031
phase: Phase 2 - Behaviour
history:
- at: '2026-11-20T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/consolidation/test_unreviewed_merge_hint.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/reconciliation_verifier.py
- tests/consolidation/test_unreviewed_merge_hint.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 - Gate hint names re-review for dropped merges

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

When the reconciliation gate (or the `--dry-run` forecast) FAILs on un-attributable content and **every** un-attributable item is content that a dropped, unreviewed post-approval merge brought in (an entry of the claim's new `unreviewed_merges` field, added by WP04), the recovery hint names the **re-review route** with the merge SHA, the lane and the work package(s), and does **not** suggest `--dependency-ref`.

Done means:

- The #5604 shape (hand merge with own content reaching the gate) prints the re-review hint and no `--dependency-ref` text.
- A canceled-content divergence, and a mixed divergence (un-attributable plus a canceled clause), show no re-review hint (negative control N4).
- Foreign content that no approved lane authored keeps today's `--dependency-ref` hint, byte for byte.
- `Divergence.describe()` is unchanged (terminus suites pin its wording).
- `_with_attribution_hint` stays at complexity <= 15.

Why a renderer-level test: once WP05 lands, the CLI refuses the #5604 shape at claim time, so this path is reachable end to end only for tool merges with own content (a recorded auto-rebase merge that auto-resolved a conflict), merges made during a run, and frozen claims read back on `--resume` (spec US4, architect F11). The hint must still be right there.

## Context & Constraints

Read before coding:

- `.kittify/charter/charter.md`, then `spec-kitty charter context --action implement`.
- `kitty-specs/approved-lane-resolution-route-01M7WW0Z/spec.md` (US4, FR-006), `plan.md` (IC-05), `research.md` (R-07), `data-model.md` (`ApprovedWpCommitSet.unreviewed_merges`, `UnreviewedMerge`).
- WP04's landed code: `UnreviewedMerge` in `src/specify_cli/consolidation/reconciliation_claim_types.py` (fields per data-model: `sha`, `lane_id`, `wp_ids`, `own_paths`, `own_blobs: tuple[(path, blob)]`) and the claim field `unreviewed_merges`. Read the landed names and how a deleted own path is represented before writing the matcher.

Integrity invariants:

- **C-001 / C-002**: this WP changes only a hint string. It never changes a verdict, never turns FAIL into PASS and never lifts anything. A wrong re-review hint is safe (review is the guard); dropping the `--dependency-ref` hint for genuinely foreign content is not, so foreign or partial matches keep today's hint.
- **C-003**: the hint reads the claim field WP04 fills where `_drop_unreviewed_merges` drops a merge; it does not re-derive which merges were dropped.
- **C-005**: do not change `--dependency-ref` behaviour (#7766 owns the laundering route); only the hint selection changes.
- **C-006**: one hint channel. Use `VerifyResult.attribution_hint` (`reconciliation_verifier.py:213-218`) and `_with_attribution_hint`; reuse `approved_bound.move_back_command` for the send-back wording (one recovery wording).
- **Fail closed**: the hint function must not raise on a malformed or empty claim field; when in doubt, fall back to today's hint.

Current code (HEAD of the planning base), `src/specify_cli/consolidation/reconciliation_verifier.py`:

- `Divergence` (`:94-169`): fields `missing_approved`, `reachable_excluded`, `unattributable_content` (`(sha, patch_id)`, merge/rebase strategy), `unattributable_blobs` (`(path, blob)`, squash axis), `unattributable_deletions` (paths, squash deletion axis), `canceled_content`, `approved_content_missing`, `canceled_reachable_via_dependency`; `describe()` (`:138-169`).
- `_with_attribution_hint` (`:172-193`): returns early when there is no divergence or the claim declared `external_dependency_refs`; adds the `--dependency-ref` hint when any un-attributable axis is non-empty.
- `VerifyResult.attribution_hint` (`:213-218`) is printed by `recovery_guidance` (`:224-241`) and by the forecast (`forecast.py`, the FAIL branch after `_forecast_verdict_or_exit`).
- Callers of the hint: `verify()` (`:405`), `forecast_content_verdict` (`:695`, `:702`). No caller changes.
- Existing hint behaviour is exercised by `tests/consolidation/test_dependency_ref_claim.py` (foreign dependency branch fixture); it must stay green.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on fix/approved-lane-resolution-route; completed changes must merge back into fix/approved-lane-resolution-route.
- **Planning base branch**: fix/approved-lane-resolution-route
- **Merge target branch**: fix/approved-lane-resolution-route

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Implement command: `spec-kitty agent action implement WP06 --agent claude --mission approved-lane-resolution-route-01M7WW0Z`

## Subtasks & Detailed Guidance

### Subtask T029 - Red renderer tests for the four shapes

- **Purpose**: pin the selection rule on claim fields, independent of git, so it cannot be faked by a coarse rule (for example "any path with two contributions").
- **Files**: `tests/consolidation/test_unreviewed_merge_hint.py` (new).
- **Approach**: build `ApprovedWpCommitSet(...)` by hand (all fields have defaults, `reconciliation_claim_types.py:137-327`), set `mission_slug`, `unreviewed_merges=(UnreviewedMerge(...),)`, and call `_with_attribution_hint(VerifyResult.failed(Divergence(...)), claim)` directly. Import private names through `tests/consolidation/reconciliation_family.py` if the facade re-exports them, else from `reconciliation_verifier`.
- **Tests (red at base because the field and the branch do not exist)**:
  1. `test_hand_merge_blob_names_re_review_not_dependency_ref` (squash shape): `Divergence(unattributable_blobs=(("src/x.py", "<blob>"),))` where `("src/x.py", "<blob>")` is in the merge's `own_blobs`. Assert the hint contains the merge's short SHA, the lane id, the WP id, the `move_back_command(...)` text for that WP and the word "independent", and does NOT contain `--dependency-ref`.
  2. `test_hand_merge_commit_names_re_review_under_merge_strategy`: `Divergence(unattributable_content=((merge_sha, pid),))` where `merge_sha` is an `unreviewed_merges` entry's `sha`. Same assertions. (Under the merge strategy the closed world reports the merge commit itself, `_unattributable_patch_id`, `:646-675`.)
  3. `test_canceled_clause_suppresses_re_review_hint` (N4): un-attributable blob matching a merge PLUS a `canceled_content=(CanceledPathState(...),)` entry. Assert no re-review hint. Repeat with `canceled_reachable_via_dependency=(CanceledDependencyContent(...),)` and with `reachable_excluded=((sha, pid),)` (removed work reachable). Decide and assert what the hint is in the mixed case: keep today's behaviour (the `--dependency-ref` hint when no refs were declared), and say so in the test docstring.
  4. `test_foreign_content_keeps_dependency_ref_hint`: un-attributable blob NOT in any `own_blobs` (and `unreviewed_merges` empty, and again non-empty but not matching). Assert the hint equals today's exact text (copy the constant; do not regex it loosely).
  5. `test_partial_match_keeps_dependency_ref_hint`: two un-attributable blobs, one from the merge and one foreign. Today's hint, no re-review hint.
  6. `test_declared_dependency_ref_keeps_no_hint`: claim with `external_dependency_refs=("dep",)` keeps returning the result unchanged (today's early return, `:183-184`).
  7. `test_deletion_from_merge_resolution`: `unattributable_deletions=("src/gone.py",)` where the path is an own path of a merge and the merge's own state for it is "deleted" (per WP04's representation). Re-review hint.
  8. `test_describe_is_unchanged`: `Divergence.describe()` output for the shapes above equals the text produced before your change (compute it from the unmodified divergence; the hint lives only in `attribution_hint`).
- **Validation**: record the red run in the WP history.

### Subtask T030 - Implement the hint branch

- **Purpose**: select between two hints with one rule; leave the verdict and `describe()` alone.
- **Files**: `src/specify_cli/consolidation/reconciliation_verifier.py`.
- **Steps**:
  1. Keep the early returns of `_with_attribution_hint` (no divergence; declared `external_dependency_refs`; no un-attributable axis).
  2. Add a pure helper `_dropped_merges_covering(divergence, claim) -> tuple[UnreviewedMerge, ...] | None` that returns the matching merges only when ALL of these hold, else `None`:
     - no canceled clause: `canceled_content`, `canceled_reachable_via_dependency` and `reachable_excluded` are empty (N4). Rationale for `reachable_excluded`: it names canceled or removed work too, so the route is not re-review;
     - `claim.unreviewed_merges` is non-empty;
     - every `(path, blob)` in `unattributable_blobs` is in the union of the merges' `own_blobs`;
     - every `sha` in `unattributable_content` is one of the merges' `sha`;
     - every path in `unattributable_deletions` is an own path a merge deleted (per WP04's representation of a deletion);
     - at least one un-attributable item exists (already guaranteed by the early return).
     The returned tuple is the merges that actually cover at least one item, in a stable order (lane id, then SHA).
  3. Add `_re_review_hint(merges, mission_slug) -> str`. Content, one sentence per merge plus one route sentence:
     - `Merge <sha7> on lane <lane_id> (<WP ids>) was made after that lane's last review approval and carries content of its own, so it authors nothing until a review approves it.`
     - `Route: send the work package back (<move_back_command(wp, slug)> for each WP), have the resolution reviewed and approved again by an independent reviewer (the new approval must reach the merge), then re-run spec-kitty consolidate.`
     - When `claim.mission_slug` is `None`, print the route without the command (never print a command that does not run as printed).
     - Reuse `approved_bound.move_back_command` (import it lazily or at module level; check `tests/architectural/test_layer_rules.py` stays green: both modules are in `specify_cli.consolidation`).
  4. In `_with_attribution_hint`, call the helper first; when it returns merges, set the re-review hint; otherwise keep today's `--dependency-ref` hint unchanged (same string, ideally hoisted to a module constant `_DEPENDENCY_REF_HINT` so the test can compare exactly, Sonar S1192 style).
  5. Do not touch `Divergence.describe()`, `VerifyResult.recovery_guidance()` or any verdict path.
  6. **Docstring correction (from WP01, which this WP depends on)**: `is_legitimate_merge_resolution` (`reconciliation_verifier.py:919`, docstring sentence at about `:957-962`) still says a custom `merge=` driver covering the path "may write bytes no side held on a clean exit, and this recognizer does not detect it". After WP01 the probe it calls (`git_probes.n_way_merge_blob`) refuses with `GitProbeError` whenever an unregistered merge attribute or driver applies (FR-010), so the sentence is false. Replace it with one sentence stating the FR-010 rule: an unregistered `merge=` attribute or driver on the path makes the fold raise `GitProbeError`, which the squash axis turns into a REFUSE; only git's built-in merge and spec-kitty's registered drivers (on their registered patterns, with their registered commands) are folded. Docstring only; no code change in that function.
  7. **Committed-attribute source (operator ruling: WP01's option (a))**: pass the claim's pre-run target tip, `claim.excluded_window_base`, as `attributes_source=` at the two probe call sites in this file (`merge_own_changed_paths` at about `:661`, `n_way_merge_blob` at about `:984`; read WP01's landed keyword name). `excluded_window_base` may be `None` on a hand-built claim: pass it through unchanged (`None` honours no committed value, the strict direction). Add one test in the new file that a committed `union` attribute is honoured at the merge-axis call only when the claim carries `excluded_window_base`.
- **Edge cases**:
  - A tool merge (recorded) that auto-resolved non-bookkeeping content reaches the gate and is dropped (US3 AS3). The hint now says re-review. That is correct: the operator's way out is a review that reaches it. Record this in the WP history as a design note.
  - A claim built before WP04 (frozen `--resume` record) has `unreviewed_merges=()`: today's hint, no crash.
  - Blob matching must compare the full blob id, not a prefix.

### Subtask T031 - Keep `_with_attribution_hint` at complexity <= 15

- **Purpose**: Sonar S3776 / ruff C901 alignment (`pyproject.toml` `max-complexity = 15`).
- **Steps**: keep `_with_attribution_hint` a short dispatcher; the coverage rule lives in `_dropped_merges_covering` (split per axis into `_blobs_covered`, `_commits_covered`, `_deletions_covered` if it nears 10); the text in `_re_review_hint`. Each helper gets a direct unit test in the new file (Sonar new-code coverage).
- **Shape to aim for** (illustrative, adapt to WP04's landed names):

  ```python
  def _with_attribution_hint(result: VerifyResult, claim: ApprovedWpCommitSet) -> VerifyResult:
      if result.divergence is None or claim.external_dependency_refs:
          return result
      if not _has_unattributable(result.divergence):
          return result
      merges = _dropped_merges_covering(result.divergence, claim)
      hint = _re_review_hint(merges, claim.mission_slug) if merges else _DEPENDENCY_REF_HINT
      return replace(result, attribution_hint=hint)
  ```

- **Direct helper tests** (in the new test file, one per branch, Sonar new-code coverage):
  - `_has_unattributable`: each of the three axes alone is True; an empty divergence is False.
  - `_dropped_merges_covering`: returns `None` for each N4 clause; `None` for a partial blob match, a partial commit match and an unmatched deletion; the covering merges (sorted) for a full match spanning two merges on two lanes; `None` when `unreviewed_merges` is empty.
  - `_re_review_hint`: one merge, two merges on one lane (one route sentence, both SHAs), `mission_slug=None` (no command printed), a WP list with two WPs (two `move_back_command` lines).
- **Constants**: hoist the existing `--dependency-ref` hint into `_DEPENDENCY_REF_HINT` and keep its bytes identical (the test compares exactly). Any new repeated literal used three or more times becomes a constant too (Sonar S1192).
- **Do not** grow `VerifyResult` or `Divergence` with new fields for this; the hint is a string on the existing field.
- **Validation**:
  - `uv run --frozen ruff check --select C901 src/specify_cli/consolidation/reconciliation_verifier.py` is clean;
  - the module's other functions are unchanged in complexity (compare `ruff check --select C901` output before and after: no new entries);
  - `mypy` reports no new findings (the helpers are fully typed; `UnreviewedMerge` is imported for typing only if it would create an import cycle, under `TYPE_CHECKING`).

## Test Strategy

```bash
uv run --frozen pytest tests/consolidation/test_unreviewed_merge_hint.py -q
# blast radius of reconciliation_verifier.py
uv run --frozen pytest tests/consolidation/test_dependency_ref_claim.py tests/consolidation/test_dependency_merge_attribution_7307.py tests/consolidation/test_mission_base_verifier.py tests/consolidation/test_forecast_squash_parity.py tests/consolidation/test_forecast_fresh_run_parity.py -q
grep -rln "MergeOutcomeVerifier\|recovery_guidance\|attribution_hint" tests/ --include="*.py"   # run the consolidation and terminus files it lists that pin gate text
uv run --frozen pytest tests/architectural/test_layer_rules.py tests/architectural/test_no_legacy_terminology.py -q
make test-fast
```

Optional real-git confirmation (recommended, not a substitute for the renderer tests): after WP05 lands, take the #7307 fixture with the FR-004 check bypassed (WP05 adds that bypass in `test_dependency_merge_attribution_7307.py`), run `MergeOutcomeVerifier(repo).verify("target-squash", ...)` and assert the result's `attribution_hint` names the evil merge. Keep that test in your own file.

Quality gates (zero findings, no new suppressions):

```bash
uv run --frozen ruff check src/specify_cli/consolidation/reconciliation_verifier.py tests/consolidation/test_unreviewed_merge_hint.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/consolidation/reconciliation_verifier.py tests/consolidation/test_unreviewed_merge_hint.py
uv run --frozen mypy src/specify_cli/consolidation/reconciliation_verifier.py tests/consolidation/test_unreviewed_merge_hint.py
```

Tracer notes: record approach, design decisions (the N4 suppression set, the mixed-case choice, the tool-merge note) and any friction with `spec-kitty agent tasks add-history WP06 --note "<trace: ...>" --mission approved-lane-resolution-route-01M7WW0Z`; this code WP cannot own `kitty-specs/traces/`.

## Risks & Mitigations

- **Over-broad match hides the `--dependency-ref` hint for foreign content**: mitigated by the all-items rule and the partial-match test.
- **Under-broad match on the merge strategy**: the merge axis reports `(sha, patch_id)` of the merge commit; matching by blob alone would miss it. Mitigated by test 2.
- **Wording drift between surfaces**: the gate and the forecast both print `attribution_hint`; one helper builds it.
- **WP04 field shape differs from data-model** (for example deletions are not represented in `own_blobs`): read the landed type, adapt the matcher, and record the decision; do not edit WP04's file.

## Review Guidance

- Anti-fake (renata LOW on FR-006): the rule is the dropped-merge blob/commit match, not a coarse `path_contributions` count. Check test 5 (partial match) exists and fails on a coarse rule.
- N4: a canceled clause and a mixed divergence suppress the hint (architect F11).
- Foreign content keeps today's exact hint (US4 AS3); `describe()` unchanged (daphne LOW 12).
- The hint text reuses `move_back_command`; every printed command carries the Mission slug.
- No verdict change: diff touches only hint selection, the `is_legitimate_merge_resolution` docstring (T030 step 6), and, only under WP01's confirmed default (a), the `attributes_source=` argument at the two probe call sites (T030 step 7).
- The stale "this recognizer does not detect it" sentence is gone from `is_legitimate_merge_resolution`.
- Ruff, format (`--force-exclude`) and mypy ran clean on the owned files; complexity <= 15.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) - never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history <WPID> --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task <WPID> --to <status>`
- **View history and status**: `spec-kitty agent tasks status`

### Optional Phase Subdirectories

For large missions, organize prompts under `tasks/` to keep bundles grouped while maintaining lexical ordering.
