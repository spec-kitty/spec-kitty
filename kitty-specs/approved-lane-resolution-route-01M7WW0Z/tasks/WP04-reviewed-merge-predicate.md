---
work_package_id: WP04
title: Shared reviewed-merge predicate and claim field
dependencies: []
requirement_refs:
- FR-004
- FR-006
- C-003
planning_base_branch: fix/approved-lane-resolution-route
merge_target_branch: fix/approved-lane-resolution-route
branch_strategy: Planning artifacts for this mission were generated on fix/approved-lane-resolution-route. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/approved-lane-resolution-route unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
- T013
phase: Phase 1 - Foundations
history:
- at: '2026-11-20T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/consolidation/test_reviewed_merge_predicate.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/reconciliation_authorship.py
- src/specify_cli/consolidation/reconciliation_claim_types.py
- tests/consolidation/test_reviewed_merge_predicate.py
- src/specify_cli/consolidation/reconciliation_claim.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 - Shared reviewed-merge predicate and claim field

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission approved-lane-resolution-route-01M7WW0Z`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: as you address each item, record it with `spec-kitty agent tasks add-history WP04 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

The reconciliation gate already decides which merges on an approved lane were reviewed. `reconciliation_authorship._drop_unreviewed_merges` (`src/specify_cli/consolidation/reconciliation_authorship.py:294-312`) keeps a merge on a lane's authorship spine only when one of THAT lane's own approval stamps reaches it. The stamps come from `_approved_stamps` (`:282-291`): each approved/done WP's newest approval stamp (`approval_stamp`, `approved_bound.py:312-319`, carried on `_PresenceScope.approval_stamps`, `:561-562`).

Two later WPs need the same answer:

- **WP05 (FR-004)**: the claim-time `RESOLUTION_MERGE_UNREVIEWED` refusal must classify exactly the merges the gate drops. Squad 2 showed a second definition would disagree on the three-lane case: lane-c's stamp reaches lane-b's hand merge, so an "any approved lane's stamp" rule (the approved bound's `lane_exempt_commits` anchors) exempts it, while the gate drops it.
- **WP06 (FR-006)**: the gate hint must know which merges were dropped, on which lane, for which WPs, and what each merge brought in of its own.

This WP:

1. extracts one public predicate, "this merge is reached by one of its own lane's approval stamps", plus the public "own stamps" reader, from `_drop_unreviewed_merges` / `_approved_stamps`, with no behaviour change;
2. adds the additive claim field `ApprovedWpCommitSet.unreviewed_merges: tuple[UnreviewedMerge, ...]`, filled where merges are dropped, with each merge's own paths and own blobs from the existing probe (`git_probes.merge_own_changed_paths`, `git_probes.py:740-766`);
3. proves every existing claim field is byte-identical.

Done when:

- the predicate and own-stamp reader are public, documented and unit-tested, including the three-lane case;
- `_drop_unreviewed_merges` and `_approved_stamps` delegate to them and every existing test is unchanged and green;
- a claim built on a post-approval hand merge carries one `UnreviewedMerge` with the right sha, lane, WPs, own paths and own blobs;
- the byte-identity check passes;
- ruff, `ruff format --check --force-exclude` and mypy are clean on every changed file; complexity <= 15; no suppressions.

## Context & Constraints

- Read first: `spec.md` (US3 AS6, FR-004, FR-006, C-003), `plan.md` (IC-03, IC-05), `research.md` (R-04, R-07), `data-model.md` ("ApprovedWpCommitSet (claim, additive field)"), `squads/01-pre-spec-and-post-specify.md` (squad 2, FR-004 rows), and `squad2/architect-alphonso.md` F7/F8, `squad2/doctrine-daphne.md` finding 3.
- Charter: `.kittify/charter/charter.md`; `spec-kitty charter context --action implement`.
- Integrity invariants:
  - **C-003**: the #7307 rule (a merge no approval stamp of its own lane reaches does not author content) is unchanged. This WP refactors it into a shared function; it does not redefine it.
  - **C-006 / single authority**: one predicate, one own-stamp reader. Do NOT touch `approved_bound.content_commits` (`approved_bound.py:464-478`) or `lane_exempt_commits`; they serve tier 1, tier 2 and the gate re-check with a different, intentionally wider anchor set (ADR 2026-10-04-5).
  - **C-002**: the new field is data for a hint. It never exempts, attributes or lifts anything; no verifier code may treat it as authorship.
  - **Fail closed**: the predicate keeps `sha_reachable_from`'s semantics (a git error reads as "not reachable", `git_probes.py:425-441`), so an unreadable reach makes a merge unreviewed (dropped), never reviewed.
- **Import cycle that constrains WP05**: `reconciliation_authorship.py` imports `approved_bound` at module top (`:24`, `approval_stamp`). WP05 must call this WP's predicate from `approved_bound.py`, which therefore can only import it **function-locally** (or through `reconciliation_bound.py`, which already imports both). State this in the predicate's docstring so WP05 does not create a cycle; `tests/consolidation/test_reconciliation_module_imports.py` (fresh-interpreter imports of every split module) catches it.
- **`reconciliation_claim.py` is owned by this WP**: the claim is CONSTRUCTED in `src/specify_cli/consolidation/reconciliation_claim.py` (`build_approved_wp_set`, `:391-420`), which unpacks `_collect_authored`'s six-tuple positionally (`:374-382`). Edit it directly (the two-line sink wiring of T012 step 4; nothing else in that file). Do NOT widen `_AuthoredClaim` (`reconciliation_authorship.py:532-540`): tests outside this WP unpack it positionally, including `tests/consolidation/test_canceled_dependency_lane.py:201` (six names) and `:454` (`*_, path_contributions, _content`, which a seventh field would silently shift).
- **Module size**: `tests/consolidation/test_reconciliation_split_shape.py` caps every `reconciliation*.py` module at 1200 lines and forbids a body defined in two split modules. `reconciliation_authorship.py` is 852 lines; stay well under.
- Terminology: Mission; lane consolidation; never "sync".

## Branch Strategy

- **Strategy**: populated by `finalize-tasks`
- **Planning base branch**: `fix/approved-lane-resolution-route`
- **Merge target branch**: `fix/approved-lane-resolution-route`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Implement command:
`spec-kitty agent action implement WP04 --agent claude --mission approved-lane-resolution-route-01M7WW0Z`

## Subtasks & Detailed Guidance

### Subtask T010 - Red tests: the predicate, the three-lane case, the claim field

- **Purpose**: pin the shared definition and the new field before the refactor.
- **File**: `tests/consolidation/test_reviewed_merge_predicate.py` (new), `pytestmark = pytest.mark.git_repo`.
- **Fixtures** (real git; write a minimal local builder; do not import private builders from other test modules):
  - **two lanes**: lane-c (WP03) and lane-b (WP02, depends on lane-c), the shape of `tests/consolidation/test_dependency_merge_attribution_7307.py:285-329` (`_build_post_approval_merge`): lane-b is approved at `b`; lane-c moves to `c2`; lane-b merges lane-c AFTER its approval with a hand-written `u/evil.txt` folded into the merge (`evil`). Approval events carry `policy_metadata.lane_head` (see `tests/consolidation/approval_stamps.py:27-33`, `with_lane_head`).
  - **reviewed variant**: the same merge made BEFORE lane-b's approval, so lane-b's stamp descends from it.
  - **clean variant**: the post-approval merge without the hand-written file (empty remerge-diff, `test_dependency_merge_attribution_7307.py:365-372`).
  - **three lanes**: lane-a and lane-b approved; lane-b's hand merge `M_b` of lane-a after lane-b's approval; lane-c depends on lane-b, merges lane-b (including `M_b`) and is approved after that merge, so lane-c's stamp reaches `M_b` while lane-b's stamps do not.
- **Tests**:
  1. `test_merge_reached_by_an_own_stamp_is_reviewed`: reviewed variant -> `merge_reviewed_by_own_stamps(repo, merge, own) is True`.
  2. `test_merge_after_the_newest_own_stamp_is_not_reviewed`: two-lane fixture -> False for `evil`.
  3. `test_another_lane_s_stamp_does_not_review_a_merge`: three-lane fixture -> False for `M_b` with lane-b's own stamps, although `git merge-base --is-ancestor M_b <lane-c stamp>` is true (assert that as a precondition, so the test is not vacuous).
  4. `test_no_own_stamp_reviews_nothing`: empty stamp tuple -> False.
  5. `test_own_stamps_are_the_newest_approval_of_approved_wps_only`: `own_approval_stamps(lane, work_packages, stamps)` returns the stamps of WPs whose status lane is `approved` or `done` (`_APPROVED_MEMBERSHIP_LANES`, `reconciliation_kernel.py:28`), skips a canceled WP, skips a WP with no stamp (`None`), keeps manifest order.
  6. `test_claim_records_the_dropped_merge`: `build_approved_wp_set(...)` on the two-lane fixture -> `claim.unreviewed_merges == (UnreviewedMerge(sha=evil, lane_id="lane-b", wp_ids=("WP02",), own_paths=("u/evil.txt",), own_blobs=(("u/evil.txt", <blob>),)),)`. Read `<blob>` with `git rev-parse evil:u/evil.txt`.
  7. `test_claim_records_a_clean_dropped_merge_with_no_own_content`: clean variant -> one entry with `own_paths == ()` and `own_blobs == ()` (a dropped merge is recorded whether or not it carries content; WP06 decides what that means).
  8. `test_claim_does_not_record_a_reviewed_merge`: reviewed variant -> `unreviewed_merges == ()`.
  9. `test_three_lane_claim_names_the_merge_s_own_lane`: the entry for `M_b` has `lane_id == "lane-b"`; no entry names lane-c for it (it is not on lane-c's first-parent spine).
  10. `test_hand_built_claim_defaults_to_no_unreviewed_merges`: `ApprovedWpCommitSet().unreviewed_merges == ()`.
- **Why red today**: the public names and `UnreviewedMerge` do not exist and the claim has no such field. To keep tests 6-9 failing on their assertions rather than on an import error, read the field with `getattr(claim, "unreviewed_merges", None)` and import the new names inside the tests that need them.
- **Validation**: run the file on HEAD; record which tests fail and how: `spec-kitty agent tasks add-history WP04 --note "T010 red: ..."`.
- **Edge cases to include**:
  - a planning (repo-root) lane: never contributes an entry (`_collect_authored` skips the drop for planning lanes, `reconciliation_authorship.py:758`);
  - a fully-canceled dependency lane's commits are subtracted before the drop (`canceled_lane_commits`, `:749`); an entry is never recorded for a commit that is not on the remaining spine.
- **Parallel?**: no; it defines the contract.

### Subtask T011 - Extract the public predicate; `_drop_unreviewed_merges` delegates

- **Purpose**: one function both the gate and WP05 call.
- **Steps**:
  1. Add to `reconciliation_authorship.py`, near `_approved_stamps` (`:282`):
     ```python
     def own_approval_stamps(lane: object, work_packages: Mapping[str, Mapping[str, object]], approval_stamps: Mapping[str, str | None]) -> tuple[str, ...]:
         """The newest approval stamp of each of *lane*'s approved or done WPs, in manifest order (#7307, FR-004)."""

     def merge_reviewed_by_own_stamps(repo_root: Path, sha: str, own_stamps: Sequence[str]) -> bool:
         """True iff one of *own_stamps* (the merge's OWN lane's approval stamps) reaches merge *sha* (#7307, FR-004).

         The single definition of a reviewed merge, shared by the gate (:func:`_drop_unreviewed_merges`)
         and the claim-time RESOLUTION_MERGE_UNREVIEWED check. Another lane's stamp never counts.
         A git error reads as "not reached" (fail closed). approved_bound imports this module's
         dependencies, so import this function there function-locally.
         """
     ```
  2. `_approved_stamps(lane, work_packages, presence)` becomes `() if presence is None else own_approval_stamps(lane, work_packages, presence.approval_stamps)`. Same order, same filtering (`_APPROVED_MEMBERSHIP_LANES`, a truthy stamp).
  3. `_drop_unreviewed_merges` (`:294-312`) calls `merge_reviewed_by_own_stamps(repo_root, sha, stamps)` in place of the inline `any(sha_reachable_from(...))` at `:308`. Everything else stays: the `GitProbeError` from `is_merge_commit` still drops (`:304-306`), and the function still returns `spine` ITSELF when nothing is dropped (`:312`). That identity is load-bearing: `_collect_authored` tests `reviewed is full_authored` (`:791`) to skip a second walk.
  4. Add both names to the module's `__all__` (`:823-852`). Do not add them to the facade `reconciliation.py` (not owned, not needed).
- **No behaviour change**: run `tests/consolidation/test_dependency_merge_attribution_7307.py`, `test_merge_derivation_7626.py` and `test_reconciliation.py` before and after; identical results.
- **Patch-lookup guard**: `tests/consolidation/test_reconciliation_family_guard.py` fails when a test patches a reconciliation-family name in a module that does not look it up. Do not patch `sha_reachable_from` on `reconciliation_authorship` in your tests; if a test needs to force a reach result, patch `merge_reviewed_by_own_stamps` where it is looked up, or use real git.
- **Edge cases**:
  - duplicate stamps (two WPs approved at the same commit): `any(...)` is unaffected; do not dedupe in `own_approval_stamps` (keeps `_approved_stamps` byte-identical) unless you prove no caller depends on the length;
  - a stamp that names a commit not in this clone: `sha_reachable_from` returns False, so the merge is unreviewed (fail closed), as today.
- **Validation**: T010 tests 1-5 green; the three files above unchanged and green.
- **Files**: `src/specify_cli/consolidation/reconciliation_authorship.py`.
- **Parallel?**: no.

### Subtask T012 - `UnreviewedMerge` and `unreviewed_merges`; populate where merges are dropped

- **Purpose**: the claim names every dropped merge, so the gate hint (WP06) can name the re-review route instead of `--dependency-ref`.
- **Steps**:
  1. In `reconciliation_claim_types.py`, add a frozen dataclass next to `LaneContribution` (before `ApprovedWpCommitSet`, `:151`):
     ```python
     @dataclass(frozen=True)
     class UnreviewedMerge:
         """A merge on an approved lane that no approval stamp of its own lane reaches (#7307; FR-006).

         Data for the gate's hint only: it never attributes, exempts or lifts anything (C-002).
         """
         sha: str
         lane_id: str
         wp_ids: tuple[str, ...]
         own_paths: tuple[str, ...]
         own_blobs: tuple[tuple[str, str], ...]
     ```
     Add it to `__all__` (`:335-344`).
  2. Append `unreviewed_merges: tuple[UnreviewedMerge, ...] = ()` as the LAST field of `ApprovedWpCommitSet`, after `window_gaps` (`:315-320`), with a comment in the style of the neighbours (what fills it, that a hand-built claim leaves it empty, that it is never authorship). The class docstring says some constructions are positional (module docstring `:1-6`), so the field must be last.
  3. In `reconciliation_authorship.py`, make the drop also report what it dropped, without changing `_drop_unreviewed_merges`'s signature or return identity:
     - add `_dropped_merges(repo_root, spine, stamps) -> tuple[str, ...]` (the merges `_drop_unreviewed_merges` would drop that are known merges; a SHA whose `is_merge_commit` raised is NOT listed: it is not known to be a merge), or refactor both on a shared private `_split_reviewed(...)`;
     - give `_collect_authored` a keyword-only parameter `unreviewed_sink: list[UnreviewedMerge] | None = None`. For each non-planning approved lane, after the drop at `:758`, append one `UnreviewedMerge` per dropped merge when the sink is given. `wp_ids` = the lane's approved WPs (the same filter `own_approval_stamps` uses), `own_paths` = `tuple(merge_own_changed_paths(repo_root, sha))`, `own_blobs` = `(path, blob)` for each own path present at `sha` (`git_probes.path_state_at`, `git_probes.py:769-797`; a path deleted by the merge has no blob and is skipped).
     - A `GitProbeError` from `merge_own_changed_paths` (old git, octopus, and after WP01 an unregistered merge attribute): do NOT raise out of the claim builder for this advisory field. Skip the entry and log at debug level with the SHA and the error. The gate still judges the merge (fail closed there), and WP06's hint then falls back to today's text, which is safe. Record this decision in history.
     - **This field is advisory and never a verdict.** A probe error swallowed here must never become a verdict anywhere: no code may read the absence of an `unreviewed_merges` entry as "the merge has no own content". WP05 takes its claim-time verdict from its own probe, which raises, never from this field (WP05's own guidance says the same). State this in the field's comment.
  4. In `reconciliation_claim.py::build_approved_wp_set`: create `unreviewed: list[UnreviewedMerge] = []`, pass `unreviewed_sink=unreviewed` to the `_collect_authored(...)` call at `:374-382`, and pass `unreviewed_merges=tuple(unreviewed)` to the `ApprovedWpCommitSet(...)` at `:391`. Nothing else in that file.
- **Ordering**: keep entries in manifest lane order, then spine order (deterministic for tests and for the hint text).
- **Cost (NFR-001)**: one remerge probe per dropped merge on a claim that passed the bound. **This WP adds no memo of any kind.** WP05 owns the per-claim probe memo (if it adds one) and the count test that bounds probes on a passing claim; any memo WP05 builds must be filled only from its raising probe, never from this WP's skip-on-error path. Do not add a cache across runs.
- **Validation**: T010 tests 6-10 green; `tests/consolidation/test_canceled_dependency_lane.py`, `tests/specify_cli/consolidation/test_single_branch_mission_to_target.py` and `tests/consolidation/test_presence_lane_base.py` (callers of `_collect_authored`) unchanged and green.
- **Edge cases**:
  - a dropped merge whose own paths are all bookkeeping: recorded as-is; filtering is the consumer's job (WP06 matches un-attributable blobs, which are never bookkeeping);
  - the #5968 own-base bound (`:793-799`) can drop reviewed commits from `authored`; it never adds a dropped merge back, so the sink reflects `_drop_unreviewed_merges` exactly;
  - a hand-built claim or a refusal claim (`reconciliation_claim.py:257`, `:472`) keeps the default `()`.
- **Files**: `src/specify_cli/consolidation/reconciliation_claim_types.py`, `src/specify_cli/consolidation/reconciliation_authorship.py`, `src/specify_cli/consolidation/reconciliation_claim.py`.
- **Parallel?**: no.

### Subtask T013 - Byte-identity check on the existing claim fields

- **Purpose**: prove the change is additive: every field that existed before this WP has the same value on the same repository (C-003; `plan.md` IC-05 risk "existing fields stay byte-identical").
- **Approach** (a golden recorded at the base, compared after the change):
  1. BEFORE any production edit, write a test that builds the claim on each T010 fixture with fixed commit dates, so commit SHAs are a function of the fixture alone. `deterministic_commit_dates(repo)` (`tests/consolidation/characterization_support.py:110-128`) needs an existing ref to read a date from; for a fixture built from scratch it is simpler to `monkeypatch.setenv` `GIT_AUTHOR_DATE` and `GIT_COMMITTER_DATE` to one fixed value for the whole build, and to fix `user.name`/`user.email` and the event `at` timestamps.
  2. **Determinism precondition (before any golden comparison)**: build each fixture TWICE in the test (two separate `tmp_path` subdirectories, same fixed env) and assert the two claims' per-field digests are equal. Any field that carries a status `event_id` (a random ULID), a wall-clock value or a temp path makes the two builds differ; fix the fixture (fixed event ids/timestamps, paths made relative) until the two builds agree. Only then compare with the stored golden. A golden compared without this precondition can be flaky, and a flaky golden is regenerated, which defeats it.
  3. Reduce the claim to a canonical form: for every field in `dataclasses.fields(ApprovedWpCommitSet)` except `unreviewed_merges`, `repr()` of the value with frozensets and mappings sorted, then a `hashlib.sha256` of the joined text per field. Store the expected per-field digests inline in the test module as a dict literal (no new data file: this WP owns no data path).
  4. Run it at the base: it passes there by construction (this is a ratchet, not a red test; say so in history).
  5. After T011/T012 it must still pass unchanged.
- **Also assert**:
  - `dataclasses.replace(claim, verify_reachability=False).unreviewed_merges == claim.unreviewed_merges` (the verifier's squash call path, `test_dependency_merge_attribution_7307.py:351`, copies the claim this way);
  - a positional construction with the pre-WP field count still works (`ApprovedWpCommitSet({}, frozenset(), ...)` with the old arity).
- **Why a golden and not a before/after call in one test**: after the change there is no "old" implementation left to call. A digest recorded at the base is the only honest witness. A differential against a monkeypatched `_drop_unreviewed_merges` would compare the new code with itself.
- **Canonical form helper** (in the test module):
  ```python
  def _field_digests(claim: ApprovedWpCommitSet) -> dict[str, str]:
      out = {}
      for f in dataclasses.fields(claim):
          if f.name == "unreviewed_merges":
              continue
          out[f.name] = hashlib.sha256(_canonical(getattr(claim, f.name)).encode()).hexdigest()
      return out
  ```
  `_canonical` sorts sets and mapping items recursively and uses `repr` for leaves; it must be deterministic across Python runs (no `hash()`-ordered iteration).
- **Coverage**: run the golden over at least the two-lane, reviewed, clean and three-lane fixtures, so a field that only some shapes populate (`path_contributions`, `approved_lane_content`, `bound_lane_tips`) is covered.
- **Edge cases**: if the digests differ only because the fixture's dates moved, the test is not deterministic; fix the fixture, never regenerate the golden after the production change without a recorded reason.
- **Validation**: the byte-identity test green before and after; record both runs in history.
- **Files**: `tests/consolidation/test_reviewed_merge_predicate.py`.
- **Parallel?**: T013 step 1-3 can be written in parallel with T010 (same file, different tests); it must run green BEFORE T011 starts.

## Test Strategy

Red first (T010), ratchet recorded (T013), then T011, T012. Commands (targeted files only):

```bash
uv run --frozen pytest -q tests/consolidation/test_reviewed_merge_predicate.py
uv run --frozen pytest -q tests/consolidation/test_dependency_merge_attribution_7307.py tests/consolidation/test_merge_derivation_7626.py \
  tests/consolidation/test_reconciliation.py tests/consolidation/test_canceled_dependency_lane.py tests/consolidation/test_presence_lane_base.py \
  tests/specify_cli/consolidation/test_single_branch_mission_to_target.py tests/consolidation/test_approved_bound.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_split_shape.py tests/consolidation/test_reconciliation_family_guard.py \
  tests/consolidation/test_reconciliation_module_imports.py
uv run --frozen pytest -q tests/architectural/test_layer_rules.py
make test-fast
```

No full heavy suites and no bare `tests/architectural/`.

Quality gates:

```bash
uv run --frozen ruff check src/specify_cli/consolidation/reconciliation_authorship.py src/specify_cli/consolidation/reconciliation_claim_types.py src/specify_cli/consolidation/reconciliation_claim.py tests/consolidation/test_reviewed_merge_predicate.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/consolidation/reconciliation_authorship.py src/specify_cli/consolidation/reconciliation_claim_types.py src/specify_cli/consolidation/reconciliation_claim.py tests/consolidation/test_reviewed_merge_predicate.py
uv run --frozen mypy src/specify_cli/consolidation/reconciliation_authorship.py src/specify_cli/consolidation/reconciliation_claim_types.py src/specify_cli/consolidation/reconciliation_claim.py
```

Complexity <= 15 (`_collect_authored` is already long: put the sink append in a helper such as `_record_unreviewed(repo_root, lane, work_packages, dropped, sink)`); no `# noqa`, no `# type: ignore`. Record commands and counts in WP history.

**Tracer notes**: record with `spec-kitty agent tasks add-history WP04 --note "trace(<tooling-friction|approach|design-decisions>): ..."`. Expected entries: the two-line `reconciliation_claim.py` wiring, the sink parameter instead of a wider `_AuthoredClaim`, the skip-on-probe-error decision, and the WP05 import constraint.

## Risks & Mitigations

- **Silent behaviour change in the gate.** Mitigation: the refactor is a pure delegation; the 7307, 7626 and reconciliation suites are the before/after oracle; T013 pins every other claim field.
- **Breaking positional unpacking.** Mitigation: `_AuthoredClaim` keeps six fields; the new data flows through a keyword-only sink.
- **Import cycle for WP05.** Mitigation: the docstring says import function-locally; the fresh-interpreter import test covers the family.
- **Probe cost.** One remerge per dropped merge; usually zero or one per Mission. Mitigation: noted for WP05; no cross-run cache.
- **An advisory field read as a verdict.** Mitigation: the field comment says it is advisory; a skipped probe error leaves no entry and is never read as "no own content"; WP05 owns any memo and its verdict comes from its own raising probe.

## Review Guidance

Anti-fake checks (from `squad2/reviewer-renata.md` FR-004 "wrong predicate and second authority", and `squad2/doctrine-daphne.md` finding 3):

- There is exactly one reach rule: `grep -n "sha_reachable_from" src/specify_cli/consolidation/reconciliation_authorship.py` shows it only inside the new predicate (and the unrelated `_authoring_merges` root check, `:389`).
- The three-lane test asserts its precondition (lane-c's stamp DOES reach `M_b`) before asserting the predicate is False; without it the test could pass on a broken fixture.
- `_drop_unreviewed_merges` still returns the identical list object when nothing is dropped.
- `content_commits`, `lane_exempt_commits` and `approved_bound.py` are untouched by this WP.
- The new field is last in `ApprovedWpCommitSet`, defaults to `()`, and no verifier or gate code reads it in this WP.
- The byte-identity digests were recorded BEFORE the production change (check the history timestamps).
- The golden test builds each fixture twice and asserts equal digests before comparing with the stored golden (determinism precondition).
- This WP adds no probe memo; `unreviewed_merges` is not read by any verdict code.
- Confirm mypy ran and passed in addition to pytest.

## Progress & Status

Progress, history, and status all live in the status event log (`status.events.jsonl`), never in this prompt file. Do **not** hand-edit a history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP04 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP04 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
